#!/usr/bin/env python3
"""Decode the opened prepare_layer integer-crop construction path."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_prepare_layer_instruction_trace as validator


ANALYSIS_SCHEMA_VERSION = 1
CLASSIFICATION = (
    "post-opening-analysis-of-preregistered-background-filter-call-and-inline-"
    "prepare-layer-integer-crop-path; selected-finite-input-arithmetic-opened-"
    "while-general-policy-unseen-transfer-and-product-parity-remain-sealed"
)

LOWER_BOUND_BITS = 0xC1BFFFFF_FF000000
UPPER_BOUND_BITS = 0x41C00000_00000000
LOWER_BOUND = struct.unpack("<d", struct.pack("<Q", LOWER_BOUND_BITS))[0]
UPPER_BOUND = struct.unpack("<d", struct.pack("<Q", UPPER_BOUND_BITS))[0]

CORE_INSTRUCTIONS = {
    0x3938: "682a42f9",
    0x393C: "090d40f9",
    0x3940: "c9042037",
    0x3944: "ea5f68b2",
    0x3948: "ea37f8f2",
    0x394C: "400d084e",
    0x3950: "618a54ad",
    0x3954: "03e4e16e",
    0x3958: "201ce36e",
    0x395C: "0a38e8d2",
    0x3960: "410d084e",
    0x3964: "21d4e04e",
    0x3968: "43e4e16e",
    0x396C: "411ce36e",
    0x3970: "608614ad",
    0x3974: "22d8e04e",
    0x3978: "4304184e",
    0x397C: "621ca24e",
    0x3980: "4a00669e",
    0x3984: "4a05f8b7",
    0x3988: "22e4614e",
    0x398C: "4358206e",
    0x3990: "6304184e",
    0x3994: "621ce24e",
    0x3998: "4a00669e",
    0x399C: "8a04f8b7",
    0x39A0: "ea5f68b2",
    0x39A4: "ea37f8f2",
    0x39A8: "420d084e",
    0x39AC: "02c4624e",
    0x39B0: "03d4614e",
    0x39B4: "0a38e8d2",
    0x39B8: "440d084e",
    0x39BC: "63c4e44e",
    0x39C0: "42b8614e",
    0x39C4: "63a8e14e",
    0x39C8: "6384e26e",
    0x39CC: "4218834e",
    0x39D0: "629e803d",
    0x39D4: "19000014",
}

FRACTIONAL_GUARD_INSTRUCTIONS = {
    0x3A38: "6a2e42f9",
    0x3A3C: "4a1540f9",
    0x3A40: "8a05f0b6",
    0x3A44: "4a0d7892",
    0x3A48: "4a0500b4",
    0x3A4C: "43a4200f",
    0x3A50: "63d8614e",
    0x3A54: "44a4204f",
    0x3A58: "84d8614e",
    0x3A5C: "24e4644e",
    0x3A60: "03e4634e",
    0x3A64: "6318844e",
    0x3A68: "6358206e",
    0x3A6C: "6328610e",
    0x3A70: "63a8702e",
    0x3A74: "6a00261e",
    0x3A78: "ca030036",
}

PADDING_PATH_INSTRUCTIONS = {
    0x3A7C: "a9034037",
    0x3A80: "a90240f9",
    0x3A84: "29f14339",
    0x3A88: "49031837",
    0x3A8C: "4a3c140e",
    0x3A90: "493c1c0e",
    0x3A94: "5f01096b",
    0x3A98: "4cc1891a",
    0x3A9C: "4bb1891a",
    0x3AA0: "ed731f32",
    0x3AA4: "9f010d6b",
    0x3AA8: "4c020054",
    0x3AAC: "7f050071",
    0x3AB0: "0b020054",
    0x3AB4: "4b3c0c0e",
    0x3AB8: "4c00261e",
    0x3ABC: "8c050051",
    0x3AC0: "6b050051",
    0x3AC4: "6c7202b9",
    0x3AC8: "6b7602b9",
    0x3ACC: "4a090011",
    0x3AD0: "29090011",
    0x3AD4: "6a7a02b9",
    0x3AD8: "697e02b9",
    0x3ADC: "5f050071",
    0x3AE0: "6b000054",
    0x3AE4: "3f010071",
    0x3AE8: "4c000054",
}

ADD_BACKGROUND_NO_OP_OFFSETS = (
    *range(0x000, 0x058, 4),
    0x060,
    0x064,
    0x068,
    0x06C,
    0x070,
    0x074,
    0x1E8,
    0x1EC,
    0x1F0,
    *range(0x420, 0x458, 4),
)


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} is not an object")
    return value


def sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{label} is not an array")
    return value


def payload(value: Any, byte_count: int, label: str) -> bytes:
    if not isinstance(value, str):
        raise ValueError(f"{label} is not hexadecimal")
    try:
        result = bytes.fromhex(value)
    except ValueError as error:
        raise ValueError(f"{label} is not hexadecimal") from error
    if len(result) != byte_count:
        raise ValueError(f"{label} byte count differs")
    return result


def sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def memory_bytes(value: Any, byte_count: int, label: str) -> bytes:
    snapshot = mapping(value, label)
    data = payload(snapshot.get("hex"), byte_count, label)
    if (
        snapshot.get("byteCount") != byte_count
        or snapshot.get("sha256") != hashlib.sha256(data).hexdigest()
    ):
        raise ValueError(f"{label} metadata differs")
    return data


def register_unsigned(value: Any, name: str, label: str) -> int:
    snapshot = mapping(value, label)
    records = list(sequence(snapshot.get("general"), f"{label} general registers"))
    names = validator.full_base.GENERAL_REGISTER_NAMES
    if len(records) != len(names):
        raise ValueError(f"{label} general register inventory differs")
    try:
        index = names.index(name)
    except ValueError as error:
        raise ValueError(f"unknown register {name}") from error
    record = mapping(records[index], f"{label} {name}")
    byte_count = 4 if name == "cpsr" else 8
    data = payload(record.get("hex"), byte_count, f"{label} {name}")
    if record.get("name") != name or record.get("byteCount") != byte_count:
        raise ValueError(f"{label} {name} identity differs")
    return int.from_bytes(data, "little", signed=False)


def f64_rect(data: bytes, label: str) -> tuple[float, float, float, float]:
    if len(data) != 32:
        raise ValueError(f"{label} byte count differs")
    values = struct.unpack("<4d", data)
    if not all(math.isfinite(value) for value in values):
        raise ValueError(f"{label} is not finite")
    return values


def f64_record(values: Sequence[float]) -> list[dict[str, Any]]:
    result = []
    for value in values:
        bits = struct.pack("<d", value)
        result.append(
            {
                "bitsHex": bits.hex(),
                "value": value,
                "valueHex": value.hex(),
            }
        )
    return result


def integer_enclosure(
    rect: Sequence[float],
) -> tuple[tuple[float, float, float, float], tuple[int, int, int, int]]:
    if len(rect) != 4 or not all(math.isfinite(value) for value in rect):
        raise ValueError("crop rectangle is not four finite binary64 values")
    origin_x = max(rect[0], LOWER_BOUND)
    origin_y = max(rect[1], LOWER_BOUND)
    width = min(rect[2], UPPER_BOUND - origin_x)
    height = min(rect[3], UPPER_BOUND - origin_y)
    clamped = (origin_x, origin_y, width, height)
    lower_x = math.floor(origin_x)
    lower_y = math.floor(origin_y)
    enclosed = (
        lower_x,
        lower_y,
        math.ceil(origin_x + width) - lower_x,
        math.ceil(origin_y + height) - lower_y,
    )
    return clamped, enclosed


def padded(enclosed: Sequence[int]) -> tuple[int, int, int, int]:
    if len(enclosed) != 4:
        raise ValueError("integer crop inventory differs")
    return (enclosed[0] - 1, enclosed[1] - 1, enclosed[2] + 2, enclosed[3] + 2)


def instruction_projection(step: Any, label: str) -> dict[str, Any]:
    value = mapping(step, label)
    instruction = mapping(value.get("instruction"), f"{label} instruction")
    return {
        "stepIndex": value.get("stepIndex"),
        "scopeName": instruction.get("scopeName"),
        "scopeOffset": instruction.get("scopeOffset"),
        "rawLittleEndianHex": instruction.get("rawLittleEndianHex"),
        "mnemonic": instruction.get("mnemonic"),
        "operands": instruction.get("operands"),
    }


def require_instruction_map(
    steps: Sequence[Any], expected: Mapping[int, str], label: str
) -> list[dict[str, Any]]:
    by_offset = {}
    for raw in steps:
        step = mapping(raw, label)
        if step.get("kind") != "scope-instruction":
            continue
        item = instruction_projection(raw, label)
        if item["scopeName"] != "prepareLayer":
            continue
        offset = item["scopeOffset"]
        if offset in expected:
            if offset in by_offset:
                raise ValueError(f"{label} repeats +0x{offset:x}")
            by_offset[offset] = item
    if list(by_offset) != list(expected):
        raise ValueError(f"{label} instruction order differs")
    for offset, raw in expected.items():
        if by_offset[offset]["rawLittleEndianHex"] != raw:
            raise ValueError(f"{label} instruction +0x{offset:x} differs")
    return list(by_offset.values())


def code_identity(path: Sequence[Mapping[str, Any]]) -> list[tuple[Any, ...]]:
    return [
        (
            item["scopeName"],
            item["scopeOffset"],
            item["rawLittleEndianHex"],
            item["mnemonic"],
            item["operands"],
        )
        for item in path
    ]


def argument_memory(invocation: Mapping[str, Any], phase: str) -> dict[str, bytes]:
    field = "entryArgumentMemory" if phase == "entry" else "returnArgumentMemory"
    values = list(sequence(invocation.get(field), f"{phase} argument memory"))
    names = ("x0", "x1", "x2", "x3", "x4", "x5")
    if len(values) != len(names):
        raise ValueError(f"{phase} argument memory inventory differs")
    result = {}
    for raw, name in zip(values, names, strict=True):
        item = mapping(raw, f"{phase} argument {name}")
        if item.get("registerName") != name:
            raise ValueError(f"{phase} argument {name} identity differs")
        result[name] = memory_bytes(
            item.get("memory"),
            validator.SEMANTIC_CROP_ARGUMENT_MEMORY_BYTE_COUNT,
            f"{phase} argument {name}",
        )
    return result


def analyze_documents(
    trace: Mapping[str, Any],
    inherited_trace: Mapping[str, Any],
    validation: Mapping[str, Any],
) -> dict[str, Any]:
    expected_validation = validator.validate_documents(trace, inherited_trace)
    validation_core = dict(validation)
    retained_hash_fields = {
        name: validation_core.pop(name)
        for name in ("traceSHA256", "inheritedTraceSHA256")
        if name in validation_core
    }
    if retained_hash_fields and set(retained_hash_fields) != {
        "traceSHA256",
        "inheritedTraceSHA256",
    }:
        raise ValueError("stored validation file-hash inventory differs")
    if validation_core != expected_validation:
        raise ValueError("stored validation differs from composed revalidation")

    semantic = mapping(validation_core.get("semanticCropTrace"), "crop validation")
    if (
        semantic.get("invocationCount") != 4
        or semantic.get("changedOpaqueTargetBoundaryCount") != 0
    ):
        raise ValueError("crop validation boundary differs")
    steps = list(sequence(trace.get("instructionSteps"), "instruction steps"))
    invocations = list(
        sequence(trace.get("semanticCropInvocations"), "crop invocations")
    )
    states = list(sequence(trace.get("semanticCropInstructionStates"), "crop states"))
    stores = list(sequence(semantic.get("storeLinks"), "crop store links"))
    if len(invocations) != 4 or len(stores) != 3:
        raise ValueError("crop invocation or store inventory differs")

    decoded = []
    add_paths = []
    core_paths = []
    guard_paths = []
    padding_paths = []
    for index, raw_invocation in enumerate(invocations):
        invocation = mapping(raw_invocation, f"crop invocation {index}")
        start = invocation.get("instructionStateStartIndex")
        count = invocation.get("instructionStateCount")
        if not isinstance(start, int) or not isinstance(count, int):
            raise ValueError(f"crop invocation {index} state bounds differ")
        invocation_states = states[start : start + count]
        add_path = [
            instruction_projection(
                mapping(state, f"crop invocation {index} state"),
                f"crop invocation {index} state",
            )
            for state in invocation_states
        ]
        if (
            len(add_path) != len(ADD_BACKGROUND_NO_OP_OFFSETS)
            or tuple(item["scopeOffset"] for item in add_path)
            != ADD_BACKGROUND_NO_OP_OFFSETS
        ):
            raise ValueError(f"crop invocation {index} add-background path differs")
        if index and [
            (item["scopeOffset"], item["rawLittleEndianHex"]) for item in add_path
        ] != [
            (item["scopeOffset"], item["rawLittleEndianHex"]) for item in add_paths[0]
        ]:
            raise ValueError("add-background paths differ across invocations")
        add_paths.append(add_path)

        states_by_offset = {
            mapping(state, f"crop invocation {index} state")["instruction"][
                "scopeOffset"
            ]: mapping(state, f"crop invocation {index} state")
            for state in invocation_states
        }
        if (
            register_unsigned(
                states_by_offset[0x054].get("registers"),
                "x24",
                f"crop invocation {index} +0x54",
            )
            != 0
            or register_unsigned(
                states_by_offset[0x074].get("registers"),
                "x19",
                f"crop invocation {index} +0x74",
            )
            != 0
            or register_unsigned(
                states_by_offset[0x1F0].get("registers"),
                "x14",
                f"crop invocation {index} +0x1f0",
            )
            & 1
        ):
            raise ValueError(f"crop invocation {index} no-op predicates differ")

        entry_arguments = argument_memory(invocation, "entry")
        return_arguments = argument_memory(invocation, "return")
        caller_entry = memory_bytes(
            invocation.get("callerRoleAtEntry"),
            validator.SEMANTIC_CROP_CALLER_ROLE_BYTE_COUNT,
            f"crop invocation {index} caller entry",
        )
        caller_return = memory_bytes(
            invocation.get("callerRoleAtReturn"),
            validator.SEMANTIC_CROP_CALLER_ROLE_BYTE_COUNT,
            f"crop invocation {index} caller return",
        )
        target_entry = memory_bytes(
            invocation.get("targetAtEntry"),
            validator.SEMANTIC_CROP_TARGET_BYTE_COUNT,
            f"crop invocation {index} target entry",
        )
        target_return = memory_bytes(
            invocation.get("targetAtReturn"),
            validator.SEMANTIC_CROP_TARGET_BYTE_COUNT,
            f"crop invocation {index} target return",
        )
        if (
            entry_arguments != return_arguments
            or caller_entry != caller_return
            or target_entry != target_return
        ):
            raise ValueError(f"crop invocation {index} add-background memory changed")

        return_step = invocation.get("returnStepIndex")
        if not isinstance(return_step, int):
            raise ValueError(f"crop invocation {index} return step differs")
        next_entry = (
            mapping(invocations[index + 1], "next crop invocation").get(
                "entryStepIndex"
            )
            if index + 1 < len(invocations)
            else len(steps)
        )
        if not isinstance(next_entry, int) or next_entry <= return_step:
            raise ValueError(f"crop invocation {index} successor span differs")
        successor_steps = steps[return_step + 1 : next_entry]
        core = require_instruction_map(
            successor_steps, CORE_INSTRUCTIONS, f"crop invocation {index} core"
        )
        guard = require_instruction_map(
            successor_steps,
            FRACTIONAL_GUARD_INSTRUCTIONS,
            f"crop invocation {index} fractional guard",
        )
        observed_padding_offsets = {
            instruction_projection(step, "padding candidate")["scopeOffset"]
            for step in successor_steps
            if mapping(step, "padding candidate").get("kind") == "scope-instruction"
        }.intersection(PADDING_PATH_INSTRUCTIONS)
        padding_executed = bool(observed_padding_offsets)
        if padding_executed:
            padding_path = require_instruction_map(
                successor_steps,
                PADDING_PATH_INSTRUCTIONS,
                f"crop invocation {index} padding path",
            )
        else:
            padding_path = []
        core_paths.append(core)
        guard_paths.append(guard)
        padding_paths.append(padding_path)

        input_rect = f64_rect(target_entry, f"crop invocation {index} input")
        clamped, enclosure = integer_enclosure(input_rect)
        fractional_mismatch = tuple(
            float(integer) != value
            for integer, value in zip(enclosure, clamped, strict=True)
        )
        if padding_executed != any(fractional_mismatch):
            raise ValueError(f"crop invocation {index} fractional branch differs")
        result = padded(enclosure) if padding_executed else enclosure
        observed = None
        if index < len(stores):
            raw_store = mapping(stores[index], f"crop store {index}")
            observed_value = raw_store.get("cropI32")
            if list(result) != observed_value:
                raise ValueError(f"crop invocation {index} replay differs")
            observed = list(observed_value)
        decoded.append(
            {
                "invocationIndex": index,
                "callerRoleBase": invocation.get("callerRoleBase"),
                "inputRectF64": f64_record(input_rect),
                "clampedRectF64": f64_record(clamped),
                "integerEnclosureI32": list(enclosure),
                "fractionalComponentMismatch": list(fractional_mismatch),
                "onePixelBorderExecuted": padding_executed,
                "replayedWorkingCropI32": list(result),
                "observedDownstreamCropI32": observed,
                "downstreamCropObserved": observed is not None,
                "addBackgroundArgumentMemoryChanged": False,
                "addBackgroundCallerRoleChanged": False,
                "addBackgroundTargetChanged": False,
            }
        )

    if any(
        code_identity(path) != code_identity(core_paths[0]) for path in core_paths[1:]
    ):
        raise ValueError("inline crop core differs across invocations")
    if any(
        code_identity(path) != code_identity(guard_paths[0]) for path in guard_paths[1:]
    ):
        raise ValueError("inline crop fractional guard differs across invocations")
    nonempty_padding = [path for path in padding_paths if path]
    if any(
        code_identity(path) != code_identity(nonempty_padding[0])
        for path in nonempty_padding[1:]
    ):
        raise ValueError("inline crop padding path differs across invocations")

    return {
        "prepareLayerCropWriterSemanticAnalysisSchemaVersion": (
            ANALYSIS_SCHEMA_VERSION
        ),
        "classification": CLASSIFICATION,
        "inputSemanticCropInstructionStateSHA256": sha256_json(states),
        "addBackgroundExecutedPathSHA256": sha256_json(add_paths[0]),
        "inlineCropCorePathSHA256": sha256_json(core_paths[0]),
        "fractionalGuardPathSHA256": sha256_json(guard_paths[0]),
        "paddingPathSHA256": sha256_json(nonempty_padding[0]),
        "bounds": {
            "lowerBitsHex": struct.pack("<Q", LOWER_BOUND_BITS).hex(),
            "lowerValue": LOWER_BOUND,
            "lowerValueHex": LOWER_BOUND.hex(),
            "upperBitsHex": struct.pack("<Q", UPPER_BOUND_BITS).hex(),
            "upperValue": UPPER_BOUND,
            "upperValueHex": UPPER_BOUND.hex(),
        },
        "selectedPathRule": {
            "finiteInputClamp": (
                "origin=max(origin,-536870911); "
                "size=min(size,536870912-origin) componentwise"
            ),
            "integerEnclosure": (
                "lower=floor(origin); extent=ceil(origin+size)-lower componentwise"
            ),
            "fractionalGuard": (
                "compare clamped [origin,size] to binary64(integer enclosure); "
                "the selected enabled branch expands only when any component "
                "differs and its remaining flags and extent guards pass"
            ),
            "onePixelBorder": "origin-=1; extent+=2 componentwise",
        },
        "invocationCount": len(decoded),
        "addBackgroundNoOpInvocationCount": sum(
            not item["addBackgroundTargetChanged"] for item in decoded
        ),
        "observedDownstreamCropCount": sum(
            item["downstreamCropObserved"] for item in decoded
        ),
        "invocations": decoded,
        "conclusion": {
            "composedValidatorRepassed": True,
            "addBackgroundFiltersIsCropWriterOnSelectedPath": False,
            "inlineFiniteCropEnclosureDecoded": True,
            "selectedPaddingBranchDecoded": True,
            "firstThreeDownstreamCropsReplayedBitExactly": True,
            "fourthRootWorkingCropInstructionDerivedOnly": True,
            "generalCropAllocationPolicyOpened": False,
            "unseenGeometryTransferPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }


def analyze_files(
    trace_path: Path,
    inherited_trace_path: Path,
    validation_path: Path,
) -> dict[str, Any]:
    trace = mapping(json.loads(trace_path.read_text(encoding="utf-8")), "trace")
    inherited = mapping(
        json.loads(inherited_trace_path.read_text(encoding="utf-8")),
        "inherited trace",
    )
    validation = mapping(
        json.loads(validation_path.read_text(encoding="utf-8")), "validation"
    )
    expected_file_hashes = {
        "traceSHA256": hashlib.sha256(trace_path.read_bytes()).hexdigest(),
        "inheritedTraceSHA256": hashlib.sha256(
            inherited_trace_path.read_bytes()
        ).hexdigest(),
    }
    if {
        name: validation.get(name) for name in expected_file_hashes
    } != expected_file_hashes:
        raise ValueError("stored validation input file hashes differ")
    return analyze_documents(trace, inherited, validation)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("inherited_trace", type=Path)
    parser.add_argument("validation", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = analyze_files(
        arguments.trace,
        arguments.inherited_trace,
        arguments.validation,
    )
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
