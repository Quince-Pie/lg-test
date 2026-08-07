#!/usr/bin/env python3
"""Generate a deterministic finite-object branch corpus for case-22.

The corpus is selected without consulting native Apple outputs.  Candidate
objects contain finite values at every field loaded by the authenticated
DesignLibrary provider.  A stable SplitMix64 stream and a greedy path-cover
selection make the result independent of Python's ``random`` implementation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_backdrop_margin_case22_provider_complete_semantics as complete
import analyze_backdrop_margin_case22_provider_local_macos_26_6_1 as selected


GENERATOR_SCHEMA_VERSION = 1
DEFAULT_SEED = 0xCACE22
DEFAULT_CANDIDATE_COUNT = 200_000
MASK_U64 = (1 << 64) - 1

F64_OFFSETS = tuple(selected.OBJECT_F64_FIELDS.values())
F32_OFFSETS = tuple(selected.OBJECT_F32_FIELDS.values())
VALUE_CATALOG = (
    -16.0,
    -5.6,
    -4.0,
    -2.8,
    -2.0,
    -1.0,
    -0.505,
    -0.25,
    -0.0625,
    -(2.0**-20),
    -0.0,
    0.0,
    2.0**-20,
    0.005,
    0.05,
    0.0625,
    0.1,
    0.25,
    0.5,
    0.505,
    1.0,
    2.0,
    2.8,
    4.0,
    5.6,
    16.0,
)

EXPECTED_STATIC_CONDITIONAL_BRANCH_COUNT = 41
EXPECTED_OBSERVED_CONDITIONAL_BRANCH_COUNT = 39
EXPECTED_BOTH_OUTCOME_CONDITIONAL_BRANCH_COUNT = 36
EXPECTED_OBSERVED_BRANCH_OUTCOME_COUNT = 75
EXPECTED_DISTINCT_PATH_COUNT = 348
EXPECTED_CORPUS_COUNT = 22


class SplitMix64:
    """Small, specified PRNG used only to make the corpus reproducible."""

    def __init__(self, seed: int) -> None:
        self._state = seed & MASK_U64

    def next_u64(self) -> int:
        self._state = (self._state + 0x9E3779B97F4A7C15) & MASK_U64
        value = self._state
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK_U64
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK_U64
        return (value ^ (value >> 31)) & MASK_U64


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def candidate_value(random_word: int) -> float:
    if random_word & 7:
        return VALUE_CATALOG[random_word % len(VALUE_CATALOG)]
    sign = -1.0 if random_word >> 63 else 1.0
    return sign * ((random_word >> 11) & 0xFFFFF) / 65536.0


def candidate_object(generator: SplitMix64) -> bytes:
    raw = bytearray(selected.validator.PROVIDER_OBJECT_BYTE_COUNT)
    for offset in F64_OFFSETS:
        struct.pack_into("<d", raw, offset, candidate_value(generator.next_u64()))
    for offset in F32_OFFSETS:
        struct.pack_into("<f", raw, offset, candidate_value(generator.next_u64()))
    return bytes(raw)


def conditional_branch_offsets(instructions: Sequence[str]) -> set[int]:
    return {
        index * 4
        for index, instruction in enumerate(instructions)
        if instruction.split(None, 1)[0].startswith("b.")
    }


def outcome_label(outcome: tuple[int, bool]) -> str:
    offset, taken = outcome
    return f"0x{offset:03x}:{'taken' if taken else 'not-taken'}"


def corpus_digest(records: Sequence[Mapping[str, Any]]) -> str:
    canonical = b"".join(
        bytes.fromhex(str(record["objectHex"]))
        + bytes.fromhex(str(record["predictedReturnRawLittleEndianHex"]))
        for record in records
    )
    return sha256_bytes(canonical)


def generate(
    instructions: Sequence[str],
    *,
    seed: int = DEFAULT_SEED,
    candidate_count: int = DEFAULT_CANDIDATE_COUNT,
) -> dict[str, Any]:
    if candidate_count <= 0:
        raise ValueError("candidate count must be positive")
    generator = SplitMix64(seed)
    by_path: dict[tuple[int, ...], tuple[bytes, frozenset[tuple[int, bool]], str]] = {}
    all_outcomes: set[tuple[int, bool]] = set()

    for _ in range(candidate_count):
        object_raw = candidate_object(generator)
        replay = complete.replay(instructions, object_raw)
        if replay["loadedObjectValuesAreFinite"] is not True:
            raise ValueError("generator emitted a non-finite loaded field")
        path = tuple(replay["executedInstructionOffsets"])
        outcomes = frozenset(tuple(value) for value in replay["branchOutcomes"])
        by_path.setdefault(
            path,
            (object_raw, outcomes, str(replay["returnRawLittleEndianHex"])),
        )
        all_outcomes.update(outcomes)

    remaining = set(all_outcomes)
    selected_records: list[tuple[bytes, frozenset[tuple[int, bool]], str]] = []
    candidates = list(by_path.values())
    while remaining:
        best = max(candidates, key=lambda item: len(item[1] & remaining))
        gained = best[1] & remaining
        if not gained:
            raise ValueError("greedy corpus selection stopped before full coverage")
        selected_records.append(best)
        remaining.difference_update(gained)

    records = [
        {
            "ordinal": ordinal,
            "objectByteCount": len(object_raw),
            "objectHex": object_raw.hex(),
            "objectSHA256": sha256_bytes(object_raw),
            "predictedReturnRawLittleEndianHex": predicted,
            "branchOutcomes": [outcome_label(value) for value in sorted(outcomes)],
        }
        for ordinal, (object_raw, outcomes, predicted) in enumerate(selected_records)
    ]
    static_branches = conditional_branch_offsets(instructions)
    observed_sites = {offset for offset, _ in all_outcomes}
    both_outcome_sites = {
        offset
        for offset in static_branches
        if (offset, False) in all_outcomes and (offset, True) in all_outcomes
    }
    result = {
        "backdropMarginCase22ProviderFiniteBranchCorpusSchemaVersion": (
            GENERATOR_SCHEMA_VERSION
        ),
        "classification": (
            "deterministic output-blind finite-object corpus selected solely "
            "from authenticated-provider emulator branch coverage"
        ),
        "generation": {
            "prng": "SplitMix64",
            "seedHex": f"0x{seed:x}",
            "candidateCount": candidate_count,
            "valueCatalogHex": [value.hex() for value in VALUE_CATALOG],
            "continuousCandidateFormula": (
                "sign(u[63]) * ((u >> 11) & 0xfffff) / 65536"
            ),
            "distinctExecutionPathCount": len(by_path),
        },
        "coverage": {
            "staticConditionalBranchCount": len(static_branches),
            "observedConditionalBranchCount": len(observed_sites),
            "bothOutcomeConditionalBranchCount": len(both_outcome_sites),
            "observedBranchOutcomeCount": len(all_outcomes),
            "observedBranchOutcomes": [
                outcome_label(value) for value in sorted(all_outcomes)
            ],
            "unobservedConditionalBranchOffsets": [
                f"0x{offset:03x}" for offset in sorted(static_branches - observed_sites)
            ],
            "singleOutcomeConditionalBranchOffsets": [
                f"0x{offset:03x}"
                for offset in sorted(observed_sites - both_outcome_sites)
            ],
        },
        "corpus": {
            "recordCount": len(records),
            "rawObjectsAndPredictionsSHA256": corpus_digest(records),
            "records": records,
        },
        "authority": {
            "appleOutputsConsultedForCandidateGeneration": False,
            "finiteLoadedProviderFields": True,
            "prospectiveAppleTransferEstablished": False,
            "unobservedOutcomesProvedInfeasible": False,
            "publicInputFieldMappingEstablished": False,
            "liquidGlassParityEstablished": False,
            "productionShaderAuthorized": False,
        },
    }
    if candidate_count == DEFAULT_CANDIDATE_COUNT and seed == DEFAULT_SEED:
        expected = (
            EXPECTED_STATIC_CONDITIONAL_BRANCH_COUNT,
            EXPECTED_OBSERVED_CONDITIONAL_BRANCH_COUNT,
            EXPECTED_BOTH_OUTCOME_CONDITIONAL_BRANCH_COUNT,
            EXPECTED_OBSERVED_BRANCH_OUTCOME_COUNT,
            EXPECTED_DISTINCT_PATH_COUNT,
            EXPECTED_CORPUS_COUNT,
        )
        observed = (
            len(static_branches),
            len(observed_sites),
            len(both_outcome_sites),
            len(all_outcomes),
            len(by_path),
            len(records),
        )
        if observed != expected:
            raise ValueError(
                f"frozen full-corpus cardinalities differ: {observed} != {expected}"
            )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("--llvm-mc", default="llvm-mc")
    parser.add_argument(
        "--seed", type=lambda value: int(value, 0), default=DEFAULT_SEED
    )
    parser.add_argument("--candidate-count", type=int, default=DEFAULT_CANDIDATE_COUNT)
    arguments = parser.parse_args()
    try:
        trace = complete.load_json(arguments.trace)
        code = complete.provider_code(trace)
        instructions = complete.disassemble(code, arguments.llvm_mc)
        result = generate(
            instructions,
            seed=arguments.seed,
            candidate_count=arguments.candidate_count,
        )
        result["provider"] = {
            "codeByteCount": len(code),
            "codeSHA256": complete.sha256_bytes(code),
            "instructionCount": len(instructions),
        }
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
