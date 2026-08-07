#!/usr/bin/env python3
"""Prove the unobserved case-22 branch outcomes infeasible for finite fields."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_backdrop_margin_case22_provider_complete_semantics as complete


PROOF_SCHEMA_VERSION = 1
WRITING_MNEMONICS = {
    "fabs",
    "fadd",
    "fcsel",
    "fmul",
    "fneg",
    "ldp",
    "ldr",
    "mov",
    "movi",
}
EXPECTED_INSTRUCTIONS = {
    0x0BC: "ldr\td2, [x20, #232]",
    0x0C0: "ldr\td4, [x20, #248]",
    0x0E4: "fcmp\td2, #0.0",
    0x0E8: "b.ge\t#500",
    0x22C: "fcmp\td2, #0.0",
    0x230: "b.ge\t#172",
    0x254: "movi\tv1.2d, #0000000000000000",
    0x258: "fmul\td4, d4, d1",
    0x270: "fcmp\td4, #0.0",
    0x274: "b.ge\t#156",
    0x298: "movi\tv1.2d, #0000000000000000",
    0x29C: "fmul\td4, d4, d1",
    0x2B4: "fcmp\td4, #0.0",
    0x2B8: "b.ge\t#88",
    0x2BC: "fcmp\ts3, #0.0",
    0x2C0: "b.le\t#260",
    0x2D4: "b.ls\t#-252",
    0x2E0: "fcmp\td2, d4",
    0x2E4: "b.ls\t#56",
    0x344: "movi\tv2.2d, #0000000000000000",
    0x348: "fmul\td1, d1, d2",
    0x34C: "fcmp\td0, #0.0",
    0x350: "b.ls\t#92",
    0x3AC: "fcmp\td4, #0.0",
    0x3B0: "b.ge\t#-464",
}
EXPECTED_INFEASIBLE_OUTCOMES = {
    (0x274, False),
    (0x2B8, False),
    (0x2C0, False),
    (0x2C0, True),
    (0x2D4, False),
    (0x2D4, True),
    (0x3B0, False),
}


def load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{path} is unreadable: {error}") from error
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} is not a JSON object")
    return value


def instruction_parts(instruction: str) -> tuple[str, str]:
    mnemonic, separator, operands = instruction.partition("\t")
    if not separator:
        mnemonic, separator, operands = instruction.partition(" ")
    if not separator:
        return instruction.strip(), ""
    return mnemonic.strip(), operands.strip()


def successors(instructions: Sequence[str]) -> dict[int, set[int]]:
    result = {}
    byte_count = len(instructions) * 4
    for index, instruction in enumerate(instructions):
        offset = index * 4
        mnemonic, operands = instruction_parts(instruction)
        if mnemonic == "retab":
            targets: set[int] = set()
        elif mnemonic == "b":
            targets = {complete.branch_target(offset, operands)}
        elif mnemonic.startswith("b."):
            targets = {offset + 4, complete.branch_target(offset, operands)}
        else:
            targets = {offset + 4} if offset + 4 < byte_count else set()
        if any(target not in range(0, byte_count, 4) for target in targets):
            raise ValueError(f"control-flow target escapes provider at {offset:#x}")
        result[offset] = targets
    return result


def predecessors(edges: Mapping[int, set[int]]) -> dict[int, set[int]]:
    result = {offset: set() for offset in edges}
    for source, targets in edges.items():
        for target in targets:
            result[target].add(source)
    return result


def written_vector_indices(instruction: str) -> set[int]:
    mnemonic, operands = instruction_parts(instruction)
    if mnemonic not in WRITING_MNEMONICS:
        return set()
    operand_values = operands.split(", ")
    destinations = operand_values[:2] if mnemonic == "ldp" else operand_values[:1]
    result = set()
    for destination in destinations:
        match = re.fullmatch(r"[dsv](\d+)(?:\.[0-9]+[bd])?", destination)
        if match:
            result.add(int(match.group(1)))
    return result


def reaching_definitions(
    instructions: Sequence[str],
    edges: Mapping[int, set[int]],
    register_index: int,
) -> dict[int, set[int]]:
    incoming_edges = predecessors(edges)
    writes = {
        offset
        for offset, instruction in enumerate(instructions)
        if register_index in written_vector_indices(instruction)
    }
    writes = {index * 4 for index in writes}
    incoming = {offset: set() for offset in edges}
    outgoing = {offset: ({offset} if offset in writes else set()) for offset in edges}
    while True:
        changed = False
        for offset in sorted(edges):
            new_incoming = set().union(
                *(outgoing[source] for source in incoming_edges[offset])
            )
            new_outgoing = {offset} if offset in writes else new_incoming
            if new_incoming != incoming[offset] or new_outgoing != outgoing[offset]:
                incoming[offset] = new_incoming
                outgoing[offset] = new_outgoing
                changed = True
        if not changed:
            return incoming


def dominators(edges: Mapping[int, set[int]]) -> dict[int, set[int]]:
    incoming_edges = predecessors(edges)
    nodes = set(edges)
    result = {offset: ({0} if offset == 0 else set(nodes)) for offset in nodes}
    while True:
        updated = {0: {0}}
        for offset in sorted(nodes - {0}):
            sources = incoming_edges[offset]
            updated[offset] = (
                {offset} | set.intersection(*(result[source] for source in sources))
                if sources
                else {offset}
            )
        if updated == result:
            return result
        result = updated


def branch_successors(
    offset: int, instruction: str
) -> tuple[tuple[int, bool], tuple[int, bool]]:
    mnemonic, operands = instruction_parts(instruction)
    if not mnemonic.startswith("b."):
        raise ValueError(f"instruction {offset:#x} is not conditional")
    return (offset + 4, False), (complete.branch_target(offset, operands), True)


def paths_preserving_d4_load(
    instructions: Sequence[str], edges: Mapping[int, set[int]]
) -> list[tuple[tuple[int, ...], tuple[tuple[int, bool], ...]]]:
    paths = []

    def visit(
        offset: int,
        path: tuple[int, ...],
        decisions: tuple[tuple[int, bool], ...],
    ) -> None:
        if offset == 0x3AC:
            paths.append((path + (offset,), decisions))
            return
        if offset in path:
            raise ValueError("provider control flow unexpectedly cycles")
        if offset != 0x0C0 and 4 in written_vector_indices(instructions[offset // 4]):
            return
        mnemonic, _ = instruction_parts(instructions[offset // 4])
        if mnemonic.startswith("b."):
            for target, taken in branch_successors(offset, instructions[offset // 4]):
                visit(target, path + (offset,), decisions + ((offset, taken),))
        else:
            for target in edges[offset]:
                visit(target, path + (offset,), decisions)

    visit(0x0C0, (), ())
    return paths


def parse_outcome_label(value: Any) -> tuple[int, bool]:
    if not isinstance(value, str):
        raise ValueError("branch outcome label is not a string")
    match = re.fullmatch(r"0x([0-9a-f]+):(taken|not-taken)", value)
    if match is None:
        raise ValueError(f"branch outcome label differs: {value!r}")
    return int(match.group(1), 16), match.group(2) == "taken"


def outcome_label(value: tuple[int, bool]) -> str:
    offset, taken = value
    return f"0x{offset:03x}:{'taken' if taken else 'not-taken'}"


def prove(trace_path: Path, validation_path: Path, llvm_mc: str) -> dict[str, Any]:
    trace = complete.load_json(trace_path)
    code = complete.provider_code(trace)
    instructions = complete.disassemble(code, llvm_mc)
    for offset, expected in EXPECTED_INSTRUCTIONS.items():
        if instructions[offset // 4] != expected:
            raise ValueError(f"proof instruction differs at {offset:#x}")
    edges = successors(instructions)
    incoming_edges = predecessors(edges)
    dominance = dominators(edges)
    d1_definitions = reaching_definitions(instructions, edges, 1)
    d2_definitions = reaching_definitions(instructions, edges, 2)
    d4_definitions = reaching_definitions(instructions, edges, 4)

    if (
        d4_definitions[0x254] != {0x0C0}
        or d1_definitions[0x258] != {0x254}
        or d4_definitions[0x258] != {0x0C0}
        or d4_definitions[0x270] != {0x258}
    ):
        raise ValueError("+0x274 forced-zero reaching definitions differ")
    if (
        d4_definitions[0x298] != {0x0C0}
        or d1_definitions[0x29C] != {0x298}
        or d4_definitions[0x29C] != {0x0C0}
        or d4_definitions[0x2B4] != {0x29C}
    ):
        raise ValueError("+0x2b8 forced-zero reaching definitions differ")
    if incoming_edges[0x2BC] != {0x2B8} or 0x2BC not in dominance[0x2D4]:
        raise ValueError("downstream unreachable-branch control flow differs")
    if d2_definitions[0x0E4] != {0x0BC} or d2_definitions[0x22C] != {0x0BC}:
        raise ValueError("+0x3b0 lower-bound operand definition differs")
    if d2_definitions[0x2E0] != {0x0BC}:
        raise ValueError("+0x3b0 ordering operand definition differs")
    if d4_definitions[0x3AC] != {0x0C0, 0x258, 0x29C}:
        raise ValueError("+0x3b0 reaching definitions differ")

    retained_load_paths = paths_preserving_d4_load(instructions, edges)
    if len(retained_load_paths) != 2:
        raise ValueError("+0x3b0 finite-load path count differs")
    path_evidence = []
    for path, decisions in retained_load_paths:
        decision_set = set(decisions)
        lower_bound_branches = decision_set & {(0x0E8, True), (0x230, True)}
        if len(lower_bound_branches) != 1 or (0x2E4, True) not in decision_set:
            raise ValueError("+0x3b0 retained path constraints differ")
        lower_bound_offset = next(iter(lower_bound_branches))[0]
        lower_compare = lower_bound_offset - 4
        lower_index = path.index(lower_compare)
        ordering_index = path.index(0x2E0)
        if any(
            2 in written_vector_indices(instructions[offset // 4])
            for offset in path[lower_index + 1 : ordering_index]
        ):
            raise ValueError("+0x3b0 d2 changed between retained constraints")
        path_evidence.append(
            {
                "instructionOffsets": list(path),
                "lowerBoundBranchOffset": lower_bound_offset,
                "lowerBoundTaken": True,
                "orderingBranchOffset": 0x2E4,
                "orderingTaken": True,
                "derivedRelation": "finite d4 >= finite d2 >= +0",
            }
        )

    validation = load_json(validation_path)
    hypothesis = validation.get("hypothesis")
    coverage = validation.get("coverage")
    if (
        validation.get("structuralValidationPassed") is not True
        or not isinstance(hypothesis, Mapping)
        or hypothesis.get("recordCount") != 22
        or hypothesis.get("matchingReturnCount") != 22
        or hypothesis.get("allAppleReturnsMatchedPredictionsBitwise") is not True
        or not isinstance(coverage, Mapping)
    ):
        raise ValueError("prospective finite-branch validation did not pass")
    observed = {
        parse_outcome_label(value)
        for value in coverage.get("observedBranchOutcomes", [])
    }
    static_branches = (
        complete.conditional_branch_offsets(instructions)
        if hasattr(complete, "conditional_branch_offsets")
        else {
            index * 4
            for index, instruction in enumerate(instructions)
            if instruction_parts(instruction)[0].startswith("b.")
        }
    )
    universe = {
        (offset, outcome) for offset in static_branches for outcome in (False, True)
    }
    missing = universe - observed
    if len(static_branches) != 41 or len(observed) != 75:
        raise ValueError("prospective branch-universe cardinality differs")
    if missing != EXPECTED_INFEASIBLE_OUTCOMES:
        raise ValueError("missing branch outcome set differs")

    return {
        "backdropMarginCase22ProviderFiniteBranchUniverseProofSchemaVersion": (
            PROOF_SCHEMA_VERSION
        ),
        "classification": (
            "exact authenticated-code control-flow and reaching-definition proof "
            "that the seven unobserved branch outcomes are infeasible when every "
            "provider-loaded field is finite"
        ),
        "inputs": {
            "trace": {
                "path": str(trace_path),
                "sha256": complete.selected.sha256(trace_path),
            },
            "prospectiveValidation": {
                "path": str(validation_path),
                "sha256": complete.selected.sha256(validation_path),
            },
            "proofSource": {
                "path": f"Analysis/{Path(__file__).name}",
                "sha256": complete.selected.sha256(Path(__file__).resolve()),
            },
        },
        "provider": {
            "codeSHA256": complete.sha256_bytes(code),
            "codeByteCount": len(code),
            "instructionCount": len(instructions),
        },
        "finiteBranchUniverse": {
            "conditionalBranchCount": len(static_branches),
            "totalOutcomeCount": len(universe),
            "prospectivelyTransferredOutcomeCount": len(observed),
            "provedInfeasibleOutcomeCount": len(missing),
            "partitionIsExact": observed | missing == universe
            and not observed & missing,
            "provedInfeasibleOutcomes": [
                outcome_label(value) for value in sorted(missing)
            ],
        },
        "proofs": [
            {
                "outcomes": ["0x274:not-taken"],
                "reason": (
                    "the sole reaching d4 definition is finite object +0xf8; "
                    "+0x254 writes exact zero to d1 and +0x258 computes "
                    "finite*d1, so +0x270 compares signed zero equal to +0"
                ),
            },
            {
                "outcomes": ["0x2b8:not-taken"],
                "reason": (
                    "the sole reaching d4 definition is finite object +0xf8; "
                    "+0x298 writes exact zero to d1 and +0x29c computes "
                    "finite*d1, so +0x2b4 compares signed zero equal to +0"
                ),
            },
            {
                "outcomes": [
                    "0x2c0:not-taken",
                    "0x2c0:taken",
                    "0x2d4:not-taken",
                    "0x2d4:taken",
                ],
                "reason": (
                    "+0x2bc has only the forced-taken +0x2b8 fallthrough as "
                    "predecessor and dominates +0x2d4, so neither branch is "
                    "reachable for finite loaded fields"
                ),
            },
            {
                "outcomes": ["0x3b0:not-taken"],
                "reason": (
                    "reaching d4 is either a forced signed zero from +0x258/"
                    "+0x29c or the finite +0xf8 load; both retained-load paths "
                    "take d2>=0 and d2<=d4 constraints, deriving d4>=0"
                ),
                "retainedLoadPaths": path_evidence,
            },
        ],
        "authority": {
            "finiteConditionalBranchOutcomeUniverseClosed": True,
            "allFeasibleFiniteBranchOutcomesProspectivelyTransferred": True,
            "completeFiniteProviderLaw": False,
            "publicInputFieldMappingEstablished": False,
            "liquidGlassParityEstablished": False,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--validation", required=True, type=Path)
    parser.add_argument("--llvm-mc", default="llvm-mc")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        result = prove(arguments.trace, arguments.validation, arguments.llvm_mc)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(payload, end="")
    else:
        arguments.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
