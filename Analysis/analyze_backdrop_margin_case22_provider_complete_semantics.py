#!/usr/bin/env python3
"""Replay the captured case-22 provider directly from its ARM64 code.

This is an output-blind offline interpreter for the small instruction subset
used by the authenticated DesignLibrary provider.  It exists to distinguish a
complete code replay from the narrower selected-path algebra already decoded
by ``analyze_backdrop_margin_case22_provider_local_macos_26_6_1.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import struct
import subprocess
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import analyze_backdrop_margin_case22_provider_local_macos_26_6_1 as selected
import validate_backdrop_margin_case22_provider_local_macos_26_6_1 as validator


ANALYSIS_SCHEMA_VERSION = 1
MAXIMUM_EXECUTED_INSTRUCTIONS = 1024


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{path} is unreadable: {error}") from error
    return selected.mapping(value, str(path))


def provider_record(trace: Mapping[str, Any]) -> Mapping[str, Any]:
    extension = trace.get("case22ProviderTrace")
    if extension is not None:
        return selected.mapping(extension, "selected provider extension")["provider"]
    return selected.mapping(trace.get("provider"), "matrix provider")


def provider_code(trace: Mapping[str, Any]) -> bytes:
    record = selected.mapping(provider_record(trace), "provider record")
    try:
        code = bytes.fromhex(str(record.get("hex")))
    except ValueError as error:
        raise ValueError("provider code is not hexadecimal") from error
    if (
        len(code) != validator.PROVIDER_BYTE_COUNT
        or record.get("symbolByteCount") != len(code)
        or record.get("codeSHA256") != validator.PROVIDER_CODE_SHA256
        or sha256_bytes(code) != validator.PROVIDER_CODE_SHA256
    ):
        raise ValueError("provider code identity differs")
    return code


def disassemble(code: bytes, llvm_mc: str) -> tuple[str, ...]:
    encoded = "\n".join(
        " ".join(f"0x{byte:02x}" for byte in code[offset : offset + 4])
        for offset in range(0, len(code), 4)
    )
    try:
        process = subprocess.run(
            [
                llvm_mc,
                "--disassemble",
                "--triple=arm64e-apple-darwin",
            ],
            input=encoded + "\n",
            text=True,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f"provider disassembly failed: {error}") from error
    instructions = tuple(line.strip() for line in process.stdout.splitlines() if line)
    if process.stderr or len(instructions) != len(code) // 4:
        raise ValueError("provider disassembly is incomplete")
    return instructions


def disassembler_version(llvm_mc: str) -> str:
    try:
        process = subprocess.run(
            [llvm_mc, "--version"],
            text=True,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f"provider disassembler identity failed: {error}") from error
    lines = [line.strip() for line in process.stdout.splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError("provider disassembler version is empty")
    return " | ".join(lines[:3])


def register_index(name: str, prefixes: str) -> int:
    if len(name) < 2 or name[0] not in prefixes or not name[1:].isdigit():
        raise ValueError(f"unsupported SIMD register {name}")
    index = int(name[1:])
    if not 0 <= index < 32:
        raise ValueError(f"SIMD register index differs for {name}")
    return index


def scalar_width(name: str) -> int:
    if name.startswith("d"):
        return 8
    if name.startswith("s"):
        return 4
    raise ValueError(f"unsupported scalar register {name}")


def scalar_raw(vectors: Sequence[bytearray], name: str) -> bytes:
    index = register_index(name, "ds")
    return bytes(vectors[index][: scalar_width(name)])


def write_scalar_raw(vectors: Sequence[bytearray], name: str, raw: bytes) -> None:
    width = scalar_width(name)
    if len(raw) != width:
        raise ValueError(f"raw scalar width differs for {name}")
    index = register_index(name, "ds")
    vectors[index][:] = raw + bytes(16 - width)


def scalar_value(vectors: Sequence[bytearray], name: str) -> float:
    raw = scalar_raw(vectors, name)
    return struct.unpack("<d" if len(raw) == 8 else "<f", raw)[0]


def write_scalar_value(vectors: Sequence[bytearray], name: str, value: float) -> None:
    write_scalar_raw(
        vectors,
        name,
        struct.pack("<d" if scalar_width(name) == 8 else "<f", value),
    )


def floating_compare(left: float, right: float) -> tuple[bool, bool, bool, bool]:
    """Return ARM64 NZCV after FCMP."""
    if math.isnan(left) or math.isnan(right):
        return False, False, True, True
    if left == right:
        return False, True, True, False
    if left < right:
        return True, False, False, False
    return False, False, True, False


def condition_passed(condition: str, flags: tuple[bool, bool, bool, bool]) -> bool:
    negative, zero, carry, overflow = flags
    conditions = {
        "ge": negative == overflow,
        "gt": not zero and negative == overflow,
        "hi": carry and not zero,
        "le": zero or negative != overflow,
        "ls": not carry or zero,
        "lt": negative != overflow,
    }
    try:
        return conditions[condition]
    except KeyError as error:
        raise ValueError(f"unsupported ARM64 condition {condition}") from error


def branch_target(pc: int, operand: str) -> int:
    if not re.fullmatch(r"#-?\d+", operand):
        raise ValueError(f"unsupported branch operand {operand}")
    return pc + int(operand[1:])


def replay(
    instructions: Sequence[str],
    object_raw: bytes,
    helper: Callable[[float], float] = selected.replay_helper,
) -> dict[str, Any]:
    if len(object_raw) != validator.PROVIDER_OBJECT_BYTE_COUNT:
        raise ValueError("provider object byte count differs")
    vectors = [bytearray(16) for _ in range(32)]
    flags = (False, False, False, False)
    pc = 0
    executed: list[int] = []
    branches: list[tuple[int, bool]] = []
    loaded_ranges: set[tuple[int, int]] = set()
    loaded_values_are_finite = True

    for _ in range(MAXIMUM_EXECUTED_INSTRUCTIONS):
        if pc % 4 or not 0 <= pc // 4 < len(instructions):
            raise ValueError(f"provider PC escaped the authenticated symbol at {pc:#x}")
        executed.append(pc)
        instruction = instructions[pc // 4]
        mnemonic, _, operands = instruction.partition("\t")
        if not operands:
            mnemonic, _, operands = instruction.partition(" ")
        mnemonic = mnemonic.strip()
        operands = operands.strip()
        next_pc = pc + 4

        if mnemonic in {"pacibsp", "stp", "add"}:
            pass
        elif mnemonic == "retab":
            return {
                "returnRawLittleEndianHex": scalar_raw(vectors, "d0").hex(),
                "executedInstructionOffsets": executed,
                "branchOutcomes": branches,
                "loadedObjectRanges": sorted(loaded_ranges),
                "loadedObjectValuesAreFinite": loaded_values_are_finite,
            }
        elif mnemonic == "ldp":
            match = re.fullmatch(r"(d\d+), (d\d+), \[x20, #(\d+)\]", operands)
            if match:
                first, second, offset_text = match.groups()
                offset = int(offset_text)
                write_scalar_raw(vectors, first, object_raw[offset : offset + 8])
                write_scalar_raw(vectors, second, object_raw[offset + 8 : offset + 16])
                loaded_values_are_finite &= math.isfinite(
                    scalar_value(vectors, first)
                ) and math.isfinite(scalar_value(vectors, second))
                loaded_ranges.add((offset, 16))
            elif "[sp" not in operands:
                raise ValueError(f"unsupported LDP at {pc:#x}: {operands}")
        elif mnemonic == "ldr":
            match = re.fullmatch(r"([ds]\d+), \[x20, #(\d+)\]", operands)
            if not match:
                raise ValueError(f"unsupported LDR at {pc:#x}: {operands}")
            destination, offset_text = match.groups()
            offset = int(offset_text)
            width = scalar_width(destination)
            write_scalar_raw(vectors, destination, object_raw[offset : offset + width])
            loaded_values_are_finite &= math.isfinite(
                scalar_value(vectors, destination)
            )
            loaded_ranges.add((offset, width))
        elif mnemonic == "mov":
            match = re.fullmatch(r"v(\d+)\.16b, v(\d+)\.16b", operands)
            if not match:
                raise ValueError(f"unsupported MOV at {pc:#x}: {operands}")
            destination, source = (int(value) for value in match.groups())
            vectors[destination][:] = vectors[source]
        elif mnemonic == "movi":
            match = re.fullmatch(r"v(\d+)\.2d, #0+", operands)
            if not match:
                raise ValueError(f"unsupported MOVI at {pc:#x}: {operands}")
            vectors[int(match.group(1))][:] = bytes(16)
        elif mnemonic in {"fabs", "fneg"}:
            match = re.fullmatch(r"(d\d+), (d\d+)", operands)
            if not match:
                raise ValueError(f"unsupported {mnemonic.upper()} at {pc:#x}")
            destination, source = match.groups()
            bits = int.from_bytes(scalar_raw(vectors, source), "little")
            if mnemonic == "fabs":
                bits &= ~(1 << 63)
            else:
                bits ^= 1 << 63
            write_scalar_raw(vectors, destination, bits.to_bytes(8, "little"))
        elif mnemonic in {"fadd", "fmul"}:
            match = re.fullmatch(r"(d\d+), (d\d+), (d\d+)", operands)
            if not match:
                raise ValueError(f"unsupported {mnemonic.upper()} at {pc:#x}")
            destination, left, right = match.groups()
            left_value = scalar_value(vectors, left)
            right_value = scalar_value(vectors, right)
            value = (
                left_value + right_value
                if mnemonic == "fadd"
                else left_value * right_value
            )
            write_scalar_value(vectors, destination, value)
        elif mnemonic == "fcmp":
            match = re.fullmatch(r"([ds]\d+), (#0\.0|[ds]\d+)", operands)
            if not match:
                raise ValueError(f"unsupported FCMP at {pc:#x}: {operands}")
            left, right = match.groups()
            right_value = 0.0 if right == "#0.0" else scalar_value(vectors, right)
            flags = floating_compare(scalar_value(vectors, left), right_value)
        elif mnemonic == "fcsel":
            match = re.fullmatch(r"(d\d+), (d\d+), (d\d+), ([a-z]+)", operands)
            if not match:
                raise ValueError(f"unsupported FCSEL at {pc:#x}: {operands}")
            destination, first, second, condition = match.groups()
            source = first if condition_passed(condition, flags) else second
            write_scalar_raw(vectors, destination, scalar_raw(vectors, source))
        elif mnemonic == "bl":
            if pc != 0x038:
                raise ValueError(f"unexpected provider call at {pc:#x}")
            write_scalar_value(vectors, "d0", helper(scalar_value(vectors, "s0")))
        elif mnemonic == "b":
            next_pc = branch_target(pc, operands)
        elif mnemonic.startswith("b."):
            condition = mnemonic[2:]
            taken = condition_passed(condition, flags)
            branches.append((pc, taken))
            if taken:
                next_pc = branch_target(pc, operands)
        else:
            raise ValueError(f"unsupported instruction at {pc:#x}: {instruction}")
        pc = next_pc
    raise ValueError("provider exceeded the instruction execution bound")


def trace_samples(
    trace: Mapping[str, Any], label: str
) -> list[tuple[str, bytes, str, tuple[int, ...]]]:
    extension_value = trace.get("case22ProviderTrace")
    if extension_value is not None:
        extension = selected.mapping(extension_value, f"{label} provider extension")
        entry = selected.mapping(extension.get("entry"), f"{label} provider entry")
        object_raw = selected.snapshot_raw(entry.get("object"), f"{label} object")
        return_record = selected.mapping(
            extension.get("return"), f"{label} provider return"
        )
        expected = selected.register_raw(
            return_record.get("registers"), "v0", f"{label} provider return"
        )[:8].hex()
        states = [
            selected.mapping(value, f"{label} provider instruction state")
            for value in selected.sequence(
                extension.get("instructionStates"), f"{label} provider states"
            )
        ]
        expected_path = tuple(int(state["symbolOffset"]) for state in states)
        return [("selected", object_raw, expected, expected_path)]

    calls = [
        selected.mapping(value, f"{label} provider call")
        for value in selected.sequence(trace.get("calls"), f"{label} calls")
    ]
    samples = []
    for index, call in enumerate(calls):
        object_raw = selected.snapshot_raw(
            call.get("providerEntryObject"), f"{label} call {index} object"
        )
        expected = str(call.get("returnF64RawLittleEndianHex", ""))
        if len(bytes.fromhex(expected)) != 8:
            raise ValueError(f"{label} call {index} return word differs")
        samples.append((str(index), object_raw, expected, ()))
    return samples


def analyze(paths: Sequence[Path], llvm_mc: str) -> dict[str, Any]:
    if not paths:
        raise ValueError("at least one provider trace is required")
    loaded = [(path, load_json(path)) for path in paths]
    code = provider_code(loaded[0][1])
    instructions = disassemble(code, llvm_mc)
    conditional_branch_offsets = {
        index * 4
        for index, instruction in enumerate(instructions)
        if instruction.split(None, 1)[0].startswith("b.")
    }
    datasets = []
    all_expected: set[str] = set()
    all_replayed: set[str] = set()
    all_instruction_offsets: set[int] = set()
    branch_outcomes: dict[int, set[bool]] = defaultdict(set)
    path_counts: Counter[tuple[int, ...]] = Counter()
    mismatch_records = []
    total_samples = 0
    matching_samples = 0
    finite_samples = 0
    retained_path_samples = 0
    matching_retained_path_samples = 0

    for path, trace in loaded:
        if provider_code(trace) != code:
            raise ValueError(f"{path} provider code differs")
        samples = trace_samples(trace, str(path))
        dataset_matches = 0
        for sample_name, object_raw, expected, expected_path in samples:
            result = replay(instructions, object_raw)
            observed = str(result["returnRawLittleEndianHex"])
            total_samples += 1
            finite_samples += bool(result["loadedObjectValuesAreFinite"])
            all_expected.add(expected)
            all_replayed.add(observed)
            executed = tuple(result["executedInstructionOffsets"])
            if expected_path:
                retained_path_samples += 1
                if executed != expected_path:
                    raise ValueError(
                        f"{path} {sample_name} replayed instruction path differs"
                    )
                matching_retained_path_samples += 1
            all_instruction_offsets.update(executed)
            path_counts[executed] += 1
            for offset, taken in result["branchOutcomes"]:
                branch_outcomes[offset].add(taken)
            if observed == expected:
                matching_samples += 1
                dataset_matches += 1
            elif len(mismatch_records) < 16:
                mismatch_records.append(
                    {
                        "trace": str(path),
                        "sample": sample_name,
                        "expectedRawLittleEndianHex": expected,
                        "replayedRawLittleEndianHex": observed,
                    }
                )
        datasets.append(
            {
                "path": str(path),
                "sha256": selected.sha256(path),
                "sampleCount": len(samples),
                "matchingReturnCount": dataset_matches,
            }
        )

    return {
        "backdropMarginCase22ProviderCompleteSemanticsAnalysisSchemaVersion": ANALYSIS_SCHEMA_VERSION,
        "classification": (
            "retrospective output-blind instruction-level replay of the "
            "authenticated finite DesignLibrary case-22 provider over retained "
            "object matrices"
        ),
        "inputs": {
            "analysisSource": {
                "path": f"Analysis/{Path(__file__).name}",
                "sha256": selected.sha256(Path(__file__).resolve()),
            },
            "traces": datasets,
        },
        "disassembler": {
            "executable": llvm_mc,
            "targetTriple": "arm64e-apple-darwin",
            "version": disassembler_version(llvm_mc),
        },
        "provider": {
            "codeSHA256": sha256_bytes(code),
            "codeByteCount": len(code),
            "instructionCount": len(instructions),
        },
        "replay": {
            "sampleCount": total_samples,
            "matchingReturnCount": matching_samples,
            "finiteLoadedObjectSampleCount": finite_samples,
            "retainedInstructionPathSampleCount": retained_path_samples,
            "matchingRetainedInstructionPathSampleCount": (
                matching_retained_path_samples
            ),
            "allReturnWordsMatchedBitwise": matching_samples == total_samples,
            "distinctExpectedReturnWords": sorted(all_expected),
            "distinctReplayedReturnWords": sorted(all_replayed),
            "executedInstructionCount": len(all_instruction_offsets),
            "executedInstructionOffsets": sorted(all_instruction_offsets),
            "distinctExecutionPathCount": len(path_counts),
            "executionPathSampleCounts": sorted(path_counts.values(), reverse=True),
            "staticConditionalBranchCount": len(conditional_branch_offsets),
            "observedConditionalBranchCount": len(branch_outcomes),
            "bothOutcomeConditionalBranchCount": sum(
                len(outcomes) == 2 for outcomes in branch_outcomes.values()
            ),
            "unobservedConditionalBranchOffsets": sorted(
                conditional_branch_offsets - branch_outcomes.keys()
            ),
            "singleOutcomeConditionalBranchOffsets": sorted(
                offset
                for offset, outcomes in branch_outcomes.items()
                if len(outcomes) == 1
            ),
            "branchOutcomes": [
                {
                    "instructionOffset": offset,
                    "observedTaken": True in outcomes,
                    "observedNotTaken": False in outcomes,
                }
                for offset, outcomes in sorted(branch_outcomes.items())
            ],
            "mismatches": mismatch_records,
        },
        "authority": {
            "authenticatedProviderCodeReplayed": True,
            "retainedFiniteObjectReturnsReplayedBitwise": (
                matching_samples == total_samples and finite_samples == total_samples
            ),
            "everyStaticBranchOutcomeObserved": all(
                len(outcomes) == 2 for outcomes in branch_outcomes.values()
            )
            and set(branch_outcomes) == conditional_branch_offsets,
            "publicInputFieldMappingEstablished": False,
            "unseenObjectTransferEstablished": False,
            "liquidGlassParityEstablished": False,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("traces", nargs="+", type=Path)
    parser.add_argument("--llvm-mc", default="llvm-mc")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        result = analyze(arguments.traces, arguments.llvm_mc)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(payload, end="")
    else:
        arguments.output.write_text(payload, encoding="utf-8")
    return 0 if result["replay"]["allReturnWordsMatchedBitwise"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
