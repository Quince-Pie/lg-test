#!/usr/bin/env python3
"""Validate the bounded live execution trace of ``SDFStyle.Group.margin``."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from collections import Counter
from pathlib import Path
from typing import Any

import validate_backdrop_margin_writer_execution as base
import validate_backdrop_margin_writer_execution_retry as writer_retry


VALIDATION_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 1
TRACE_EXTENSION_SCHEMA_VERSION = 1
SWIFTUICORE_UUID = "A8FC6D2D-DFE9-3557-A734-7F2B231F8C97"
PRODUCER_FUNCTION = "SwiftUI.SDFStyle.Group.margin.getter : CoreGraphics.CGFloat"
PRODUCER_BYTE_COUNT = 732
PRODUCER_CODE_SHA256 = (
    "5414dac1e2dce7753af9afe072ceb3b7f938ec894df81bd621866f50d03b015d"
)
PRODUCER_MODULE_OFFSET = 0x3715D0
CALLER_FUNCTION = writer_retry.CALLER_FUNCTION
CALLER_RETURN_AFTER_PRODUCER_OFFSET = 5764

DIRECT_CALL_OFFSETS = [0x0B8, 0x0D4, 0x144, 0x168, 0x180, 0x208, 0x254, 0x25C, 0x274]
DIRECT_TARGET_MODULE_OFFSETS = [
    0x144E24,
    0x4F38,
    0xB6CD0,
    0x4F38,
    0x4F38,
    0x4F38,
    0x4F38,
    0xD64010,
    0xB7F38,
]
STAGES = {
    0x0BC: ("discriminator", "1f500071"),
    0x0D8: ("case23Projected", "000040fd"),
    0x148: ("case23Contribution", "00216a1e"),
    0x16C: ("case21Projected", "080040fd"),
    0x184: ("case1Projected", "087840b9"),
    0x1F8: ("case1Reduction", "0021601e"),
    0x20C: ("case22Projected", "140040f9"),
    0x268: ("case22IndirectCall", "910b3fd7"),
    0x26C: ("case22Return", "081ca04e"),
    0x278: ("loopAccumulator", "18070091"),
    0x2B0: ("getterReturn", "001da84e"),
}
PROJECTION_STAGES = {0x0D8, 0x16C, 0x184, 0x20C}
VECTOR_NAMES = {"v0", "v8", "v9", "v10"}
REGISTER_NAMES = {"x0", "x8", "x9", "x17", "x20", "x21", "x22", "x23", "x24", "x28"}
SELECTION = (
    "all Group.margin invocations whose immediate caller is the opened "
    "SwiftUICore updateSDFEffects symbol at return offset 5764"
)


def validate_snapshot(
    value: Any,
    address: int,
    byte_count: int,
    label: str,
) -> bytes:
    snapshot = base.mapping(value, label)
    payload = base.exact_hex(snapshot.get("hex"), byte_count, f"{label} bytes")
    if (
        snapshot.get("address") != address
        or snapshot.get("byteCount") != byte_count
        or snapshot.get("sha256") != hashlib.sha256(payload).hexdigest()
    ):
        raise ValueError(f"{label} metadata differs")
    return payload


def validate_preregistration(value: Any) -> dict[str, Any]:
    prereg = base.mapping(value, "group execution preregistration")
    if (
        prereg.get("backdropMarginGroupExecutionPreregistrationSchemaVersion")
        != PREREGISTRATION_SCHEMA_VERSION
    ):
        raise ValueError("group execution preregistration schema differs")
    profile = base.mapping(prereg.get("profile"), "profile")
    if profile != {
        "material": "regular",
        "appearance": "light",
        "direction": "materialize",
        "geometry": "circle-127-center",
        "exactPublicProfilePreviouslyCaptured": True,
        "exactGroupExecutionPreviouslyCaptured": False,
    }:
        raise ValueError("group execution profile differs")
    producer = base.mapping(prereg.get("openedProducer"), "opened producer")
    if (
        producer.get("function") != PRODUCER_FUNCTION
        or producer.get("swiftUICoreUUID") != SWIFTUICORE_UUID
        or producer.get("moduleOffset") != PRODUCER_MODULE_OFFSET
        or producer.get("symbolByteCount") != PRODUCER_BYTE_COUNT
        or producer.get("codeSHA256") != PRODUCER_CODE_SHA256
        or producer.get("callerFunction") != CALLER_FUNCTION
        or producer.get("callerReturnAfterProducerOffset")
        != CALLER_RETURN_AFTER_PRODUCER_OFFSET
        or producer.get("directCallInstructionOffsets") != DIRECT_CALL_OFFSETS
        or producer.get("directCallTargetModuleOffsets") != DIRECT_TARGET_MODULE_OFFSETS
        or producer.get("stageInstructionOffsets") != sorted(STAGES)
    ):
        raise ValueError("opened producer preregistration differs")
    unknown = base.mapping(prereg.get("unknownBeforeCapture"), "unknown fields")
    for key in (
        "groupRecordCount",
        "groupRecordBytes",
        "sideTableBytes",
        "taggedPayloadBytes",
        "discriminatorSequence",
        "directCalleeSymbols",
        "directCalleeCodeHashes",
        "branchOperands",
        "accumulatorWords",
        "nestedIndirectTarget",
    ):
        if unknown.get(key) is not None:
            raise ValueError(f"unknown field {key} was not sealed")
    acceptance = base.mapping(prereg.get("acceptance"), "acceptance")
    for key in (
        "requireExactProducerCode",
        "requireExactCallerCallsite",
        "requireCompleteSelectedInvocations",
        "requireRawGroupRecords",
        "requireRawSideTableAndTaggedPayloads",
        "requireEveryDiscriminatorAndAccumulatorStage",
        "requireExactBranchStageSequence",
        "requireGetterReturnToMatchAdjacentSetterBitwise",
        "requireNoValueBasedSelection",
        "zeroTolerance",
    ):
        if acceptance.get(key) is not True:
            raise ValueError(f"acceptance field {key} differs")
    return prereg


def validate_producer_gate(extension: dict[str, Any]) -> dict[str, Any]:
    gate = base.mapping(extension.get("producerCodeGate"), "producer code gate")
    module = writer_retry.validate_swiftui_module(
        gate.get("module"), "producer code-gate module"
    )
    start = base.integer(gate.get("symbolStart"), "producer start")
    end = base.integer(gate.get("symbolEnd"), "producer end")
    payload = base.exact_hex(gate.get("hex"), PRODUCER_BYTE_COUNT, "producer code")
    if (
        gate.get("function") != PRODUCER_FUNCTION
        or end - start != PRODUCER_BYTE_COUNT
        or gate.get("symbolByteCount") != PRODUCER_BYTE_COUNT
        or start - module["loadAddress"] != PRODUCER_MODULE_OFFSET
        or gate.get("codeSHA256") != PRODUCER_CODE_SHA256
        or hashlib.sha256(payload).hexdigest() != PRODUCER_CODE_SHA256
    ):
        raise ValueError("producer code gate differs")
    return gate


def validate_direct_calls(
    extension: dict[str, Any], gate: dict[str, Any]
) -> dict[str, Any]:
    calls = base.sequence(extension.get("directCalls"), "direct calls")
    targets = base.sequence(extension.get("directTargets"), "direct targets")
    if len(calls) != len(DIRECT_CALL_OFFSETS) or not targets:
        raise ValueError("direct call or target count differs")
    module_base = base.mapping(gate.get("module"), "producer module")["loadAddress"]
    captured_target_bytes = 0
    for index, value in enumerate(targets):
        target = base.mapping(value, f"direct target {index}")
        selected = base.integer(target.get("selectedTarget"), "direct target address")
        module = writer_retry.validate_swiftui_module(
            target.get("module"), "direct target module"
        )
        if module.get("loadAddress") != module_base:
            raise ValueError("direct target module differs")
        if target.get("completeCodeCaptured") is True:
            byte_count = base.integer(
                target.get("symbolByteCount"), "direct target byte count"
            )
            symbol_start = base.integer(
                target.get("symbolStart"), "direct target symbol start"
            )
            symbol_end = base.integer(
                target.get("symbolEnd"), "direct target symbol end"
            )
            payload = base.exact_hex(
                target.get("hex"), byte_count, "direct target code"
            )
            if (
                not 0 < byte_count <= 131072
                or target.get("codeSHA256") != hashlib.sha256(payload).hexdigest()
                or symbol_end - symbol_start != byte_count
                or not symbol_start <= selected < symbol_end
                or target.get("symbolOffset") != selected - symbol_start
                or target.get("completeCodeFailure") is not None
            ):
                raise ValueError("captured direct target differs")
            captured_target_bytes += byte_count
        elif not isinstance(target.get("completeCodeFailure"), str):
            raise ValueError("uncaptured direct target lacks a reason")
    if (
        captured_target_bytes > 2 * 1024 * 1024
        or extension.get("finalDirectTargetCodeByteCount") != captured_target_bytes
    ):
        raise ValueError("direct target byte total differs")
    for index, value in enumerate(calls):
        call = base.mapping(value, f"direct call {index}")
        offset = DIRECT_CALL_OFFSETS[index]
        target_offset = DIRECT_TARGET_MODULE_OFFSETS[index]
        target_index = base.integer(call.get("targetIndex"), "direct target index")
        if (
            call.get("instructionOffset") != offset
            or call.get("targetModuleOffset") != target_offset
            or call.get("target") != module_base + target_offset
            or not 0 <= target_index < len(targets)
            or targets[target_index].get("selectedTarget") != call.get("target")
        ):
            raise ValueError("direct call identity differs")
        decoded_target = writer_retry.decode_bl_target(
            call.get("instructionHex"), gate["symbolStart"] + offset
        )
        if decoded_target != call.get("target"):
            raise ValueError("direct call instruction target differs")
    complete_count = sum(
        target.get("completeCodeCaptured") is True for target in targets
    )
    if complete_count < 1:
        raise ValueError("no complete direct target was captured")
    return {
        "directCallCount": len(calls),
        "uniqueDirectTargetCount": len(targets),
        "completeDirectTargetCount": complete_count,
        "directTargetFunctions": [target.get("function", "") for target in targets],
    }


def validate_breakpoints(
    extension: dict[str, Any], gate: dict[str, Any]
) -> dict[str, int]:
    records = base.sequence(extension.get("breakpoints"), "group breakpoints")
    if len(records) != len(STAGES) + 1:
        raise ValueError("group breakpoint count differs")
    entry = base.mapping(records[0], "producer entry breakpoint")
    if (
        entry.get("name") != "producerEntry"
        or entry.get("function") != PRODUCER_FUNCTION
        or entry.get("selection")
        != "all exact symbol invocations, filtered by caller code identity"
    ):
        raise ValueError("producer entry breakpoint differs")
    identifiers = {base.integer(entry.get("id"), "producer entry breakpoint ID")}
    for index, (offset, (name, instruction_hex)) in enumerate(STAGES.items(), 1):
        record = base.mapping(records[index], f"stage breakpoint {name}")
        identifier = base.integer(record.get("id"), f"stage breakpoint {name} ID")
        if (
            record.get("name") != name
            or record.get("address") != gate["symbolStart"] + offset
            or record.get("instructionOffset") != offset
            or record.get("instructionHex") != instruction_hex
            or record.get("selection") != "fixed offset in exact producer code"
            or identifier in identifiers
        ):
            raise ValueError(f"stage breakpoint {name} differs")
        identifiers.add(identifier)
    return {"breakpointCount": len(records)}


def validate_vector(value: Any, label: str) -> bytes:
    vector = base.mapping(value, label)
    byte_count = base.integer(vector.get("byteCount"), f"{label} byte count")
    payload = base.exact_hex(
        vector.get("rawLittleEndianHex"), byte_count, f"{label} bytes"
    )
    low = base.exact_hex(
        vector.get("lowF64RawLittleEndianHex"), 8, f"{label} low binary64"
    )
    if payload[:8] != low:
        raise ValueError(f"{label} low word differs")
    number = struct.unpack("<d", low)[0]
    finite = math.isfinite(number)
    if vector.get("lowF64Finite") is not finite:
        raise ValueError(f"{label} finite marker differs")
    if finite and vector.get("lowF64") != number:
        raise ValueError(f"{label} numeric value differs")
    if not finite and vector.get("lowF64") is not None:
        raise ValueError(f"{label} non-finite value is serialized")
    return low


def validate_group(value: Any, label: str) -> tuple[int | None, int | None]:
    group = base.mapping(value, label)
    self_address = base.integer(group.get("self"), f"{label} self")
    self_payload = validate_snapshot(
        group.get("selfSnapshot"), self_address, 0x60, f"{label} self snapshot"
    )
    tag = self_payload[0x10]
    side_storage = struct.unpack_from("<Q", self_payload, 0x18)[0]
    record_storage = struct.unpack_from("<Q", self_payload, 0x20)[0]
    if (
        group.get("collectionTagByte") != tag
        or group.get("sideStorage") != side_storage
        or group.get("recordStorage") != record_storage
    ):
        raise ValueError(f"{label} collection header differs")
    inline_first_word = struct.unpack_from("<Q", self_payload, 0x00)[0]
    inline_second_word = struct.unpack_from("<Q", self_payload, 0x08)[0]
    uses_direct_storage = tag >> 6 < 2
    uses_bridged_storage = (
        tag == 0x80 and inline_first_word == 3 and inline_second_word == 0
    )
    expected_storage_path = (
        "direct"
        if uses_direct_storage
        else "bridged-0x80"
        if uses_bridged_storage
        else "none"
    )
    if group.get("storagePath") != expected_storage_path:
        raise ValueError(f"{label} storage path differs")
    if not uses_direct_storage and not uses_bridged_storage:
        for key in (
            "sideStorageHeader",
            "recordStorageHeader",
            "sideEntryCount",
            "recordCount",
            "sideEntriesSnapshot",
            "recordsSnapshot",
        ):
            if group.get(key) is not None:
                raise ValueError(f"{label} non-native collection field differs")
        if group.get("taggedSidePayloads") != []:
            raise ValueError(f"{label} non-native tagged payloads differ")
        return None, None
    side_header = validate_snapshot(
        group.get("sideStorageHeader"), side_storage, 0x20, f"{label} side header"
    )
    record_header = validate_snapshot(
        group.get("recordStorageHeader"),
        record_storage,
        0x20,
        f"{label} record header",
    )
    side_count = struct.unpack_from("<Q", side_header, 0x10)[0]
    record_count = struct.unpack_from("<Q", record_header, 0x10)[0]
    if (
        side_count > 64
        or record_count > 64
        or group.get("sideEntryCount") != side_count
        or group.get("recordCount") != record_count
    ):
        raise ValueError(f"{label} bounded counts differ")
    side_entries = validate_snapshot(
        group.get("sideEntriesSnapshot"),
        side_storage + 0x20,
        side_count * 0x38,
        f"{label} side entries",
    )
    validate_snapshot(
        group.get("recordsSnapshot"),
        record_storage + 0x20,
        record_count * 0x80,
        f"{label} records",
    )
    payloads = base.sequence(group.get("taggedSidePayloads"), f"{label} payloads")
    if len(payloads) != side_count:
        raise ValueError(f"{label} tagged payload count differs")
    for index, value in enumerate(payloads):
        payload = base.mapping(value, f"{label} payload {index}")
        tagged = struct.unpack_from("<Q", side_entries, index * 0x38)[0]
        tag_value = tagged >> 60
        address = tagged & 0x0FFFFFFFFFFFFFFF
        if (
            payload.get("sideEntryIndex") != index
            or payload.get("taggedWordRawLittleEndianHex")
            != side_entries[index * 0x38 : index * 0x38 + 8].hex()
            or payload.get("tag") != tag_value
            or payload.get("payloadAddress") != address
        ):
            raise ValueError(f"{label} tagged payload identity differs")
        if tag_value in (2, 5) and address != 0:
            retained = validate_snapshot(
                payload.get("payloadSnapshot"),
                address,
                0x80,
                f"{label} payload {index} bytes",
            )
            if tag_value == 2:
                values = base.mapping(
                    payload.get("tag2ValueStorage"),
                    f"{label} payload {index} tag-2 storage",
                )
                value_storage = struct.unpack_from("<Q", retained, 0x18)[0]
                header = validate_snapshot(
                    values.get("headerSnapshot"),
                    value_storage,
                    0x20,
                    f"{label} payload {index} tag-2 header",
                )
                value_count = struct.unpack_from("<Q", header, 0x10)[0]
                if (
                    value_count > 256
                    or values.get("address") != value_storage
                    or values.get("valueCount") != value_count
                ):
                    raise ValueError(f"{label} tag-2 value count differs")
                validate_snapshot(
                    values.get("valuesSnapshot"),
                    value_storage + 0x20,
                    value_count * 8,
                    f"{label} payload {index} tag-2 values",
                )
            elif payload.get("tag2ValueStorage") is not None:
                raise ValueError(f"{label} tag-5 has tag-2 storage")
        elif (
            payload.get("payloadSnapshot") is not None
            or payload.get("tag2ValueStorage") is not None
        ):
            raise ValueError(f"{label} unreferenced payload was dereferenced")
    return side_count, record_count


def expected_record_stage_offsets(discriminator_case: int) -> list[int]:
    if discriminator_case in (2, 3):
        return [0x0BC, 0x0D8, 0x148, 0x278]
    if discriminator_case == 21:
        return [0x0BC, 0x16C, 0x278]
    if discriminator_case == 22:
        return [0x0BC, 0x20C, 0x268, 0x26C, 0x278]
    if discriminator_case == 1:
        return [0x0BC, 0x184, 0x1F8, 0x278]
    return [0x0BC, 0x278]


def validate_stage(
    value: Any,
    label: str,
    gate: dict[str, Any],
    expected_stage_index: int,
    expected_invocation_stage_index: int,
) -> tuple[dict[str, Any], bytes]:
    stage = base.mapping(value, label)
    offset = base.integer(stage.get("instructionOffset"), f"{label} offset")
    if offset not in STAGES:
        raise ValueError(f"{label} offset differs")
    name, _instruction = STAGES[offset]
    if (
        stage.get("stageIndex") != expected_stage_index
        or stage.get("invocationStageIndex") != expected_invocation_stage_index
        or stage.get("name") != name
        or stage.get("pc") != gate["symbolStart"] + offset
    ):
        raise ValueError(f"{label} identity differs")
    registers = base.mapping(stage.get("registers"), f"{label} registers")
    if set(registers) != REGISTER_NAMES:
        raise ValueError(f"{label} register set differs")
    for register, register_value in registers.items():
        base.integer(register_value, f"{label} {register}")
    vectors = base.mapping(stage.get("vectors"), f"{label} vectors")
    if set(vectors) != VECTOR_NAMES:
        raise ValueError(f"{label} vector set differs")
    lows = {
        register: validate_vector(vector, f"{label} {register}")
        for register, vector in vectors.items()
    }
    if offset == 0x0BC:
        if (
            stage.get("discriminatorCase") != registers["x0"] & 0xFFFFFFFF
            or stage.get("groupRecordIndex") != registers["x24"]
        ):
            raise ValueError(f"{label} discriminator differs")
    if offset in PROJECTION_STAGES:
        validate_snapshot(
            stage.get("projectionSnapshot"),
            registers["x0"],
            0x80,
            f"{label} projection",
        )
    elif "projectionSnapshot" in stage:
        raise ValueError(f"{label} unexpected projection snapshot")
    if offset == 0x268 and (
        stage.get("authenticatedIndirectTargetRaw") != registers["x28"]
        or stage.get("authenticatedIndirectModifierRaw") != registers["x17"]
    ):
        raise ValueError(f"{label} authenticated call registers differ")
    return stage, lows["v8"]


def validate_invocations(
    extension: dict[str, Any],
    gate: dict[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    invocations = base.sequence(extension.get("invocations"), "group invocations")
    if (
        not 0 < len(invocations) <= 512
        or extension.get("finalInvocationCount") != len(invocations)
        or extension.get("finalCompleteInvocationCount") != len(invocations)
        or extension.get("finalSetterLinkedInvocationCount") != len(invocations)
        or extension.get("unfinishedSelectedInvocationCount") != 0
    ):
        raise ValueError("group invocation totals differ")
    all_stage_indices: list[int] = []
    case_counts: Counter[int] = Counter()
    total_records = 0
    total_side_entries = 0
    tag_counts: Counter[int] = Counter()
    for index, value in enumerate(invocations):
        invocation = base.mapping(value, f"invocation {index}")
        caller = writer_retry.validate_swiftui_module(
            base.mapping(invocation.get("caller"), "invocation caller").get("module"),
            "invocation caller module",
        )
        caller_record = base.mapping(invocation.get("caller"), "invocation caller")
        if (
            invocation.get("invocationIndex") != index
            or invocation.get("entryPC") != gate["symbolStart"]
            or invocation.get("complete") is not True
            or invocation.get("selectedByCapturedMargin") is not False
            or caller_record.get("function") != CALLER_FUNCTION
            or caller_record.get("symbolOffset") != CALLER_RETURN_AFTER_PRODUCER_OFFSET
            or caller_record.get("pc")
            != caller_record.get("symbolStart") + CALLER_RETURN_AFTER_PRODUCER_OFFSET
            or caller["uuid"] != SWIFTUICORE_UUID
        ):
            raise ValueError(f"invocation {index} selection differs")
        side_count, record_count = validate_group(
            invocation.get("group"), f"invocation {index} group"
        )
        if side_count is not None:
            total_side_entries += side_count
        if record_count is not None:
            total_records += record_count
        tag_counts[
            base.mapping(invocation.get("group"), "group")["collectionTagByte"]
        ] += 1
        stages = base.sequence(invocation.get("stages"), f"invocation {index} stages")
        if not stages:
            raise ValueError(f"invocation {index} has no stages")
        validated_stages = []
        return_raw = None
        for invocation_stage_index, stage_value in enumerate(stages):
            stage_index = base.integer(
                base.mapping(stage_value, "stage").get("stageIndex"),
                f"invocation {index} stage {invocation_stage_index} global index",
            )
            stage, v8_raw = validate_stage(
                stage_value,
                f"invocation {index} stage {invocation_stage_index}",
                gate,
                stage_index,
                invocation_stage_index,
            )
            all_stage_indices.append(stage_index)
            validated_stages.append(stage)
            if stage["instructionOffset"] == 0x0BC:
                case_counts[stage["discriminatorCase"]] += 1
            if stage["instructionOffset"] == 0x2B0:
                if return_raw is not None:
                    raise ValueError(f"invocation {index} has multiple returns")
                return_raw = v8_raw
        offsets = [stage["instructionOffset"] for stage in validated_stages]
        if offsets[-1] != 0x2B0 or offsets.count(0x2B0) != 1:
            raise ValueError(f"invocation {index} return stage differs")
        invocation_cases = [
            stage["discriminatorCase"]
            for stage in validated_stages
            if stage["instructionOffset"] == 0x0BC
        ]
        expected_offsets = [
            offset
            for discriminator_case in invocation_cases
            for offset in expected_record_stage_offsets(discriminator_case)
        ]
        expected_offsets.append(0x2B0)
        if offsets != expected_offsets:
            raise ValueError(f"invocation {index} branch-stage sequence differs")
        if record_count is not None and len(invocation_cases) != record_count:
            raise ValueError(f"invocation {index} loop stage count differs")
        setter_index = base.integer(
            invocation.get("setterEventIndex"), f"invocation {index} setter index"
        )
        if not 0 <= setter_index < len(events):
            raise ValueError(f"invocation {index} setter index is outside events")
        setter = events[setter_index]
        raw_hex = return_raw.hex()
        if (
            setter.get("type") != "marginSetter"
            or setter.get("threadID") != invocation.get("threadID")
            or setter.get("marginF64RawLittleEndianHex") != raw_hex
            or setter.get("producerInvocation", {}).get("groupMarginInvocationIndex")
            != index
            or invocation.get("returnF64RawLittleEndianHex") != raw_hex
            or invocation.get("setterMarginF64RawLittleEndianHex") != raw_hex
            or invocation.get("returnMatchesSetterBitwise") is not True
            or struct.pack(
                "<d", base.finite_number(invocation.get("returnF64"), "return")
            )
            != return_raw
        ):
            raise ValueError(f"invocation {index} return/setter join differs")
    if sorted(all_stage_indices) != list(
        range(len(all_stage_indices))
    ) or extension.get("finalStageCount") != len(all_stage_indices):
        raise ValueError("group global stage total differs")
    if not case_counts:
        raise ValueError("no Group.margin discriminator was retained")
    return {
        "invocationCount": len(invocations),
        "stageCount": len(all_stage_indices),
        "recordCount": total_records,
        "sideEntryCount": total_side_entries,
        "collectionTagByteCounts": {
            str(key): value for key, value in sorted(tag_counts.items())
        },
        "discriminatorCaseCounts": {
            str(key): value for key, value in sorted(case_counts.items())
        },
        "allSelectedInvocationsComplete": True,
        "allGetterReturnsMatchAdjacentSetterBitwise": True,
        "capturedMarginUsedForSelection": False,
    }


def validate(trace_path: Path, preregistration_path: Path) -> dict[str, Any]:
    prereg = validate_preregistration(
        base.load_json(preregistration_path, "group execution preregistration")
    )
    trace = base.mapping(base.load_json(trace_path, "trace"), "trace")
    if trace.get("status") != "finalized" or trace.get("failures") != []:
        raise ValueError("inherited writer trace did not finalize cleanly")
    gates = base.validate_code_gates(trace)
    callers = base.validate_callers(trace)
    events = writer_retry.validate_events(trace, gates, callers)
    producer_provenance = writer_retry.validate_producer_provenance(
        trace, events, callers
    )
    extension = base.mapping(
        trace.get("groupMarginExecution"), "group execution extension"
    )
    if (
        extension.get("groupMarginExecutionTraceSchemaVersion")
        != TRACE_EXTENSION_SCHEMA_VERSION
        or extension.get("status") != "finalized"
        or extension.get("failures") != []
    ):
        raise ValueError("group execution extension did not finalize cleanly")
    configuration = base.mapping(extension.get("configuration"), "configuration")
    expected_configuration = {
        "producerFunction": PRODUCER_FUNCTION,
        "producerByteCount": PRODUCER_BYTE_COUNT,
        "producerCodeSHA256": PRODUCER_CODE_SHA256,
        "producerModuleOffset": PRODUCER_MODULE_OFFSET,
        "callerFunction": CALLER_FUNCTION,
        "callerReturnAfterProducerOffset": CALLER_RETURN_AFTER_PRODUCER_OFFSET,
        "groupSelfByteCount": 0x60,
        "groupTagByteOffset": 0x10,
        "groupSideStorageOffset": 0x18,
        "groupRecordStorageOffset": 0x20,
        "collectionCountOffset": 0x10,
        "collectionElementsOffset": 0x20,
        "groupRecordByteCount": 0x80,
        "sideEntryByteCount": 0x38,
        "sidePayloadByteCount": 0x80,
        "maximumCollectionCount": 64,
        "maximumTag2ValueCount": 256,
        "maximumInvocationCount": 512,
        "maximumStageCount": 8192,
        "maximumDirectTargetCount": 16,
        "maximumDirectTargetByteCount": 131072,
        "maximumTotalDirectTargetByteCount": 2 * 1024 * 1024,
        "directCallOffsets": DIRECT_CALL_OFFSETS,
        "directCallTargetModuleOffsets": DIRECT_TARGET_MODULE_OFFSETS,
        "stageOffsets": sorted(STAGES),
        "selection": SELECTION,
        "capturedMarginUsedForSelection": False,
        "capturedCropUsedForSelection": False,
        "capturedImageUsedForSelection": False,
        "capturedPixelUsedForSelection": False,
    }
    if configuration != expected_configuration:
        raise ValueError("group execution configuration differs")
    gate = validate_producer_gate(extension)
    breakpoints = validate_breakpoints(extension, gate)
    direct = validate_direct_calls(extension, gate)
    execution = validate_invocations(extension, gate, events)
    profile = base.mapping(prereg.get("profile"), "profile")
    return {
        "backdropMarginGroupExecutionValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "classification": (
            "bounded output-blind live operand diagnostic for the already-opened "
            "Group.margin getter; public-input arithmetic and product parity remain open"
        ),
        "conclusion": "success",
        "inputs": {
            "trace": str(trace_path),
            "preregistration": str(preregistration_path),
        },
        "profile": {
            "material": profile["material"],
            "appearance": profile["appearance"],
            "direction": profile["direction"],
            "geometry": profile["geometry"],
            "diagnosticProfilePreviouslyOpened": True,
            "groupExecutionFrozenBeforeCapture": True,
        },
        "inheritedWriter": {
            "eventCount": len(events),
            "exactCodeGateCount": len(gates),
            "producerProvenance": producer_provenance,
        },
        "producer": {
            "function": PRODUCER_FUNCTION,
            "swiftUICoreUUID": SWIFTUICORE_UUID,
            "moduleOffset": PRODUCER_MODULE_OFFSET,
            "symbolByteCount": PRODUCER_BYTE_COUNT,
            "codeSHA256": PRODUCER_CODE_SHA256,
            **breakpoints,
            **direct,
        },
        "execution": execution,
        "sealedConclusion": {
            "exactGroupMarginExecutionCaptured": True,
            "publicSDFStyleCaseNamesDecoded": False,
            "publicInputMarginLawDecoded": False,
            "prospectiveUnseenProfileTransferPassed": False,
            "independentTemporalInputGenerationPassed": False,
            "capturedInputOpticalParityPassed": False,
            "physicalOutputTransferPassed": False,
            "independentWalleZeroByteFrameParityPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("preregistration", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate(arguments.trace, arguments.preregistration)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
