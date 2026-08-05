#!/usr/bin/env python3
"""Decode the validated selected Glass DOD dynamic instruction state."""

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
    "post-opening-analysis-of-preregistered-selected-glass-dod-complete-"
    "register-state; general-crop-policy-unseen-transfer-and-product-parity-"
    "remain-sealed"
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


def register_payloads(value: Any, label: str) -> dict[str, bytes]:
    snapshot = mapping(value, label)
    result = {}
    inventories = (
        ("general", validator.full_base.GENERAL_REGISTER_NAMES),
        ("simd", validator.full_base.SIMD_REGISTER_NAMES),
    )
    for group, names in inventories:
        records = sequence(snapshot.get(group), f"{label} {group}")
        if len(records) != len(names):
            raise ValueError(f"{label} {group} inventory differs")
        for expected_name, raw in zip(names, records, strict=True):
            record = mapping(raw, f"{label} {expected_name}")
            byte_count = 4 if expected_name in {"cpsr", "fpsr", "fpcr"} else 8
            if expected_name.startswith("v"):
                byte_count = 16
            if (
                record.get("name") != expected_name
                or record.get("byteCount") != byte_count
            ):
                raise ValueError(f"{label} {expected_name} identity differs")
            result[expected_name] = payload(
                record.get("hex"), byte_count, f"{label} {expected_name}"
            )
    return result


def unsigned(registers: Mapping[str, bytes], name: str) -> int:
    return int.from_bytes(registers[name], "little", signed=False)


def f64_lanes(register: bytes) -> list[dict[str, Any]]:
    if len(register) % 8:
        raise ValueError("binary64 register width differs")
    result = []
    for offset in range(0, len(register), 8):
        lane = register[offset : offset + 8]
        value = struct.unpack("<d", lane)[0]
        result.append(
            {
                "bitsHex": lane.hex(),
                "valueHex": value.hex(),
                "finiteValue": value if math.isfinite(value) else None,
            }
        )
    return result


def changed_registers(
    before: Mapping[str, bytes],
    after: Mapping[str, bytes],
    names: Sequence[str],
) -> list[dict[str, Any]]:
    result = []
    for name in names:
        if before[name] == after[name]:
            continue
        record: dict[str, Any] = {
            "name": name,
            "beforeHex": before[name].hex(),
            "afterHex": after[name].hex(),
        }
        if len(before[name]) <= 8:
            record["beforeUnsigned"] = unsigned(before, name)
            record["afterUnsigned"] = unsigned(after, name)
        if name.startswith("v"):
            record["beforeF64"] = f64_lanes(before[name])
            record["afterF64"] = f64_lanes(after[name])
        result.append(record)
    return result


def memory_bytes(value: Any, label: str) -> tuple[int, bytes]:
    snapshot = mapping(value, label)
    address = snapshot.get("address")
    byte_count = snapshot.get("byteCount")
    if not isinstance(address, int) or address <= 0 or not isinstance(byte_count, int):
        raise ValueError(f"{label} bounds differ")
    data = payload(snapshot.get("hex"), byte_count, label)
    if snapshot.get("sha256") != hashlib.sha256(data).hexdigest():
        raise ValueError(f"{label} digest differs")
    return address, data


def changed_memory_ranges(before_value: Any, after_value: Any) -> list[dict[str, Any]]:
    before_address, before = memory_bytes(before_value, "stack before")
    after_address, after = memory_bytes(after_value, "stack after")
    lower = max(before_address, after_address)
    upper = min(before_address + len(before), after_address + len(after))
    changed = []
    if lower < upper:
        for address in range(lower, upper):
            old = before[address - before_address]
            new = after[address - after_address]
            if old != new:
                changed.append((address, old, new))
    ranges = []
    cursor = 0
    while cursor < len(changed):
        end = cursor + 1
        while end < len(changed) and changed[end][0] == changed[end - 1][0] + 1:
            end += 1
        group = changed[cursor:end]
        ranges.append(
            {
                "address": group[0][0],
                "byteCount": len(group),
                "beforeHex": bytes(item[1] for item in group).hex(),
                "afterHex": bytes(item[2] for item in group).hex(),
            }
        )
        cursor = end
    return ranges


def aggregate_lanes(value: Any, label: str) -> list[dict[str, Any]]:
    data = payload(value, validator.full_base.AGGREGATE_BYTE_COUNT, label)
    return [
        {
            "laneOffset": offset,
            "bitsHex": data[offset : offset + 8].hex(),
            "valueHex": struct.unpack("<d", data[offset : offset + 8])[0].hex(),
        }
        for offset in range(0, len(data), 8)
    ]


def call_record(
    effect: Mapping[str, Any],
    before: Mapping[str, bytes],
    after: Mapping[str, bytes],
) -> dict[str, Any]:
    boundaries = sequence(effect.get("opaqueBoundaries"), "opaque boundaries")
    if len(boundaries) != 1:
        raise ValueError("DOD helper call boundary count differs")
    boundary = mapping(boundaries[0], "opaque boundary")
    entry = mapping(boundary.get("entryFrame"), "opaque entry frame")
    function = entry.get("function")
    if not isinstance(function, str) or not function:
        raise ValueError("opaque helper function differs")
    record: dict[str, Any] = {
        "instructionStateIndex": effect["instructionStateIndex"],
        "stepIndex": effect["stepIndex"],
        "scopeOffset": effect["scopeOffset"],
        "function": function,
        "arguments": {
            name: unsigned(before, name) for name in ("x0", "x1", "x2", "x3")
        },
        "argumentV0F64": f64_lanes(before["v0"]),
        "argumentV1F64": f64_lanes(before["v1"]),
        "returns": {name: unsigned(after, name) for name in ("x0", "x1")},
        "returnV0F64": f64_lanes(after["v0"]),
        "returnV1F64": f64_lanes(after["v1"]),
        "changedStackRanges": list(
            sequence(effect.get("changedStackRanges"), "helper stack changes")
        ),
    }
    if "KeyValueArray::get_" in function:
        record["keyID"] = unsigned(before, "x1") & 0xFFFF_FFFF
    return record


def analyze_documents(
    trace: Mapping[str, Any],
    inherited_trace: Mapping[str, Any],
    validation: Mapping[str, Any],
) -> dict[str, Any]:
    expected_validation = validator.validate_documents(trace, inherited_trace)
    if validation != expected_validation:
        raise ValueError("stored validation differs from composed revalidation")
    semantic = mapping(validation.get("semanticDODTrace"), "semantic validation")
    states = list(
        sequence(trace.get("semanticDODInstructionStates"), "semantic states")
    )
    invocation = mapping(trace.get("semanticDODInvocation"), "semantic invocation")
    if (
        not states
        or semantic.get("instructionStateCount") != len(states)
        or semantic.get("instructionStatesSHA256") != sha256_json(states)
    ):
        raise ValueError("semantic state validation differs")
    steps = list(sequence(trace.get("instructionSteps"), "instruction steps"))
    return_registers = register_payloads(
        invocation.get("returnRegisters"), "return registers"
    )
    effects = []
    helpers = []
    writers = []
    for index, raw_state in enumerate(states):
        state = mapping(raw_state, f"semantic state {index}")
        instruction = mapping(state.get("instruction"), f"semantic instruction {index}")
        before_registers = register_payloads(
            state.get("registers"), f"semantic registers {index}"
        )
        if index + 1 < len(states):
            next_state = mapping(states[index + 1], f"semantic state {index + 1}")
            after_registers = register_payloads(
                next_state.get("registers"), f"semantic registers {index + 1}"
            )
            after_stack = next_state.get("stack")
            after_aggregate = next_state.get("aggregateBeforeHex")
            next_step_index = next_state.get("stepIndex")
        else:
            after_registers = return_registers
            after_stack = invocation.get("returnStack")
            after_aggregate = invocation.get("aggregateAtReturnHex")
            next_step_index = invocation.get("returnStepIndex", -1) + 1
        step_index = state.get("stepIndex")
        if not isinstance(step_index, int) or not isinstance(next_step_index, int):
            raise ValueError(f"semantic effect {index} step identity differs")
        intervening = [
            mapping(steps[position], f"intervening step {position}")
            for position in range(step_index + 1, next_step_index)
        ]
        boundaries = [
            mapping(step.get("opaqueBoundary"), "opaque boundary")
            for step in intervening
            if step.get("kind") == "opaque-callee-step-out"
        ]
        before_aggregate = state.get("aggregateBeforeHex")
        effect = {
            "instructionStateIndex": index,
            "stepIndex": step_index,
            "scopeOffset": instruction.get("scopeOffset"),
            "rawLittleEndianHex": instruction.get("rawLittleEndianHex"),
            "mnemonic": instruction.get("mnemonic"),
            "operands": instruction.get("operands"),
            "comment": instruction.get("comment"),
            "nextStepIndex": next_step_index,
            "interveningStepCount": len(intervening),
            "opaqueBoundaries": boundaries,
            "changedGeneralRegisters": changed_registers(
                before_registers,
                after_registers,
                validator.full_base.GENERAL_REGISTER_NAMES,
            ),
            "changedSIMDRegisters": changed_registers(
                before_registers,
                after_registers,
                validator.full_base.SIMD_REGISTER_NAMES,
            ),
            "changedStackRanges": changed_memory_ranges(
                state.get("stack"), after_stack
            ),
            "aggregateBefore": aggregate_lanes(
                before_aggregate, f"effect {index} aggregate before"
            ),
            "aggregateAfter": aggregate_lanes(
                after_aggregate, f"effect {index} aggregate after"
            ),
            "aggregateChanged": before_aggregate != after_aggregate,
        }
        effects.append(effect)
        if boundaries:
            helpers.append(call_record(effect, before_registers, after_registers))
        if effect["aggregateChanged"]:
            writers.append(
                {
                    key: effect[key]
                    for key in (
                        "instructionStateIndex",
                        "stepIndex",
                        "scopeOffset",
                        "rawLittleEndianHex",
                        "mnemonic",
                        "operands",
                        "aggregateBefore",
                        "aggregateAfter",
                    )
                }
            )
    return {
        "prepareLayerDODSemanticAnalysisSchemaVersion": ANALYSIS_SCHEMA_VERSION,
        "classification": CLASSIFICATION,
        "inputInstructionStateSHA256": sha256_json(states),
        "selectedInvocation": dict(semantic),
        "instructionEffectCount": len(effects),
        "opaqueHelperReturnCount": len(helpers),
        "aggregateWriterCount": len(writers),
        "opaqueHelperReturns": helpers,
        "aggregateWriters": writers,
        "instructionEffects": effects,
        "conclusion": {
            "composedValidatorRepassed": True,
            "selectedGlassDODExactDynamicEffectsDecoded": True,
            "opaqueHelperArgumentsAndReturnsOpened": True,
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
