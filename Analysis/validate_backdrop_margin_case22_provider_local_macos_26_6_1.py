#!/usr/bin/env python3
"""Validate the exact local case-22 DesignLibrary provider trace."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import validate_backdrop_margin_case22_callee as frozen_case22
import validate_backdrop_margin_group_execution as frozen_group
import validate_backdrop_margin_writer_execution as base
import validate_backdrop_margin_writer_execution_retry as writer_retry


VALIDATION_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 1
PROVIDER_TRACE_SCHEMA_VERSION = 1

SWIFTUICORE_UUID = "99606D45-C40A-3C69-AE51-5F0C4E32E531"
QUARTZCORE_UUID = "F1BA3189-E95A-3ECA-B59A-5A6872754484"
DESIGN_LIBRARY_UUID = "1E980802-69F5-3E69-89EF-50088297FCF5"

COPY_FUNCTION = "-[CABackdropLayer _copyRenderLayer:layerFlags:commitFlags:]"
COPY_BYTE_COUNT = 1640
COPY_CODE_SHA256 = "5bdf866c13bfb00d9becada24ff9876f84515fa36acb4ee274785d5176593a1e"
SETTER_FUNCTION = "-[CABackdropLayer setMarginWidth:]"
SETTER_BYTE_COUNT = 96
SETTER_CODE_SHA256 = "2421048e418c6cdcc7622dd65f881e514e0852687f7920e6c4bdaf75a301f6dd"

GROUP_MODULE_OFFSET = 0x3715D0
GROUP_BYTE_COUNT = 732
GROUP_CODE_SHA256 = "5414dac1e2dce7753af9afe072ceb3b7f938ec894df81bd621866f50d03b015d"

THUNK_MODULE_OFFSET = 0xB7F4C
THUNK_FUNCTION = "___lldb_unnamed_symbol_240918f4c"
THUNK_BYTE_COUNT = 4
THUNK_CODE_SHA256 = "a4bd0b217d6f1355f73bffde7d725de4a4b3eaf5d4cd3f3c5915da27bc44add3"
THUNK_INSTRUCTION_HEX = "5afcff17"
THUNK_BRANCH_DISPLACEMENT = -3736

PROVIDER_MODULE_OFFSET = 0xB70B4
PROVIDER_FUNCTION = "___lldb_unnamed_symbol_2409180b4"
PROVIDER_BYTE_COUNT = 984
PROVIDER_CODE_SHA256 = (
    "a76c6f0b03cc6b64c6b040220f495c5f22d7e1e5322efb3cb139554dd397c10b"
)
PROVIDER_OBJECT_BYTE_COUNT = 0x180
PROVIDER_RETURN_TO_WRAPPER_OFFSET = 0x68

HELPER_MODULE_OFFSET = 0xC682C
HELPER_FUNCTION = "___lldb_unnamed_symbol_24092782c"
HELPER_BYTE_COUNT = 276
HELPER_CODE_SHA256 = "f58da9879a4b367144e8acaf1ad099161b3e27f00e0769dd4fa6e18e9ef9edc1"

MAXIMUM_PROVIDER_INSTRUCTION_COUNT = 512
MAXIMUM_PROVIDER_HELPER_COUNT = 8
MAXIMUM_PROVIDER_HELPER_CODE_BYTE_COUNT = 4096


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_preregistration(value: Any, repository_root: Path) -> dict[str, Any]:
    preregistration = base.mapping(value, "local provider preregistration")
    if (
        preregistration.get(
            "backdropMarginCase22ProviderLocalMacOSPreregistrationSchemaVersion"
        )
        != PREREGISTRATION_SCHEMA_VERSION
    ):
        raise ValueError("local provider preregistration schema differs")
    host = base.mapping(preregistration.get("host"), "local provider host")
    if (
        host.get("macOSProductVersion") != "26.6.1"
        or host.get("macOSBuildVersion") != "25G76"
        or host.get("architecture") != "arm64"
        or host.get("windowBackingScaleFactor") != 2
        or host.get("swiftUICoreUUID") != SWIFTUICORE_UUID
        or host.get("quartzCoreUUID") != QUARTZCORE_UUID
        or host.get("designLibraryUUID") != DESIGN_LIBRARY_UUID
    ):
        raise ValueError("local provider host identity differs")
    selection = base.mapping(
        preregistration.get("selection"), "local provider selection"
    )
    if selection.get("groupInvocationIndex") != 20:
        raise ValueError("local provider ordinal differs")
    for key in (
        "capturedMarginUsedForRuntimeSelection",
        "capturedCropUsedForRuntimeSelection",
        "capturedImageUsedForRuntimeSelection",
        "capturedPixelUsedForRuntimeSelection",
        "prospectiveTransferAuthority",
    ):
        if selection.get(key) is not False:
            raise ValueError(f"local provider selection field {key} differs")
    contract = base.mapping(
        preregistration.get("captureContract"), "local provider contract"
    )
    for key in (
        "parentCase22AdapterUnchanged",
        "localProviderOverlayOnly",
        "requireExactDesignLibraryUUID",
        "requireExactThunkOffsetInstructionAndCode",
        "requireExactDecodedProviderTargetOffset",
        "requireCompleteProviderSymbolAndCode",
        "requireFullGeneralAndSIMDRegistersPerProviderInstruction",
        "requireStackPerProviderInstruction",
        "requireProviderEntryAndReturnObject",
        "requireExactHelperSymbolAndCompleteCode",
        "requireHelperEntryAndReturnRegisters",
        "requireContinuousProviderExecutionChain",
        "requireExactReturnToSwiftUIWrapper",
        "zeroTolerance",
    ):
        if contract.get(key) is not True:
            raise ValueError(f"local provider contract field {key} differs")
    if (
        contract.get("maximumProviderInstructionCount")
        != MAXIMUM_PROVIDER_INSTRUCTION_COUNT
        or contract.get("maximumProviderHelperCount") != MAXIMUM_PROVIDER_HELPER_COUNT
        or contract.get("maximumProviderHelperCodeByteCount")
        != MAXIMUM_PROVIDER_HELPER_CODE_BYTE_COUNT
    ):
        raise ValueError("local provider capture bounds differ")
    unknown = base.mapping(
        preregistration.get("unknownBeforeDispatch"), "local provider unknowns"
    )
    if any(item is not None for item in unknown.values()):
        raise ValueError("a local provider runtime outcome was not sealed")
    if preregistration.get("runtimeOutcomeFrozenBeforeDispatch") is not None:
        raise ValueError("local provider runtime outcome was predeclared")
    for record_value in base.sequence(
        base.mapping(
            preregistration.get("frozenImplementation"), "frozen implementation"
        ).get("files"),
        "frozen implementation files",
    ):
        record = base.mapping(record_value, "frozen implementation file")
        path = repository_root / str(record.get("path"))
        if sha256(path) != record.get("sha256"):
            raise ValueError(f"frozen implementation hash differs for {path}")
    authority = base.mapping(
        preregistration.get("productAuthority"), "local provider authority"
    )
    if authority.get("selectedProviderArithmeticMayBeDecodedOnPass") is not True:
        raise ValueError("selected provider decode authority differs")
    for key, granted in authority.items():
        if (
            key != "selectedProviderArithmeticMayBeDecodedOnPass"
            and granted is not False
        ):
            raise ValueError(f"local provider authority {key} is not closed")
    return preregistration


def validate_module(
    value: Any, label: str, expected_uuid: str, path_suffix: str
) -> dict[str, Any]:
    module = base.mapping(value, label)
    if (
        module.get("valid") is not True
        or module.get("uuid") != expected_uuid
        or not isinstance(module.get("path"), str)
        or not module["path"].endswith(path_suffix)
        or base.integer(module.get("loadAddress"), f"{label} load address") <= 0
    ):
        raise ValueError(f"{label} differs")
    return module


def validate_quartz_gate(
    value: Any,
    label: str,
    function: str,
    byte_count: int,
    code_sha256: str,
) -> dict[str, Any]:
    gate = base.mapping(value, label)
    start = base.integer(gate.get("symbolStart"), f"{label} start")
    end = base.integer(gate.get("symbolEnd"), f"{label} end")
    validate_module(
        gate.get("module"), f"{label} module", QUARTZCORE_UUID, "/QuartzCore"
    )
    if (
        gate.get("function") != function
        or gate.get("symbolByteCount") != byte_count
        or end - start != byte_count
        or gate.get("codeSHA256") != code_sha256
    ):
        raise ValueError(f"{label} identity differs")
    return gate


def validate_local_parent(trace: dict[str, Any]) -> dict[str, Any]:
    configuration = base.mapping(trace.get("configuration"), "trace configuration")
    if (
        trace.get("status") != "finalized"
        or trace.get("statusBeforeFinalization") != "breakpoints-armed"
        or trace.get("failures") != []
        or trace.get("finalFailureCount") != 0
        or configuration.get("material") != "regular"
        or configuration.get("appearance") != "light"
        or configuration.get("direction") != "materialize"
        or configuration.get("geometry") != "circle-127-center"
        or configuration.get("quartzCoreUUID") != QUARTZCORE_UUID
        or configuration.get("capturedMarginUsedForSelection") is not False
        or configuration.get("capturedCropUsedForSelection") is not False
        or configuration.get("capturedImageUsedForSelection") is not False
    ):
        raise ValueError("local inherited trace identity differs")
    gates = base.mapping(trace.get("codeGates"), "local QuartzCore gates")
    if set(gates) != {"copy", "setter"}:
        raise ValueError("local QuartzCore gate set differs")
    validate_quartz_gate(
        gates["copy"],
        "copy gate",
        COPY_FUNCTION,
        COPY_BYTE_COUNT,
        COPY_CODE_SHA256,
    )
    validate_quartz_gate(
        gates["setter"],
        "setter gate",
        SETTER_FUNCTION,
        SETTER_BYTE_COUNT,
        SETTER_CODE_SHA256,
    )
    local_profile = base.mapping(trace.get("localHostProfile"), "local host profile")
    for key, expected in {
        "macOSProductVersion": "26.6.1",
        "macOSBuildVersion": "25G76",
        "swiftUICoreUUID": SWIFTUICORE_UUID,
        "quartzCoreUUID": QUARTZCORE_UUID,
        "groupCodeSHA256": GROUP_CODE_SHA256,
        "groupModuleOffset": GROUP_MODULE_OFFSET,
        "case22TargetModuleOffset": frozen_case22.CASE22_TARGET_MODULE_OFFSET,
        "copyCodeSHA256": COPY_CODE_SHA256,
        "setterCodeSHA256": SETTER_CODE_SHA256,
        "retinaBaselineBackingScaleFactor": 2,
        "capturedMarginUsedForRuntimeSelection": False,
        "capturedCropUsedForRuntimeSelection": False,
        "capturedImageUsedForRuntimeSelection": False,
        "capturedPixelUsedForRuntimeSelection": False,
    }.items():
        if local_profile.get(key) != expected:
            raise ValueError(f"local host profile field {key} differs")

    group_extension = base.mapping(
        trace.get("groupMarginExecution"), "group execution extension"
    )
    if (
        group_extension.get("status") != "finalized"
        or group_extension.get("statusBeforeFinalization") != "breakpoints-armed"
        or group_extension.get("failures") != []
    ):
        raise ValueError("local group execution did not finalize cleanly")
    previous_writer_uuid = writer_retry.SWIFTUICORE_UUID
    previous_group_uuid = frozen_group.SWIFTUICORE_UUID
    try:
        writer_retry.SWIFTUICORE_UUID = SWIFTUICORE_UUID
        frozen_group.SWIFTUICORE_UUID = SWIFTUICORE_UUID
        producer_gate = frozen_group.validate_producer_gate(group_extension)
        breakpoints = frozen_group.validate_breakpoints(group_extension, producer_gate)
        direct = frozen_group.validate_direct_calls(group_extension, producer_gate)
        events = [
            base.mapping(value, "writer event")
            for value in base.sequence(trace.get("events"), "writer events")
        ]
        execution = frozen_group.validate_invocations(
            group_extension, producer_gate, events
        )
        parent_case22 = frozen_case22.validate_trace_extension(trace, {})
    finally:
        writer_retry.SWIFTUICORE_UUID = previous_writer_uuid
        frozen_group.SWIFTUICORE_UUID = previous_group_uuid
    return {
        "quartzCoreCodeGateCount": len(gates),
        "writerEventCount": len(events),
        "groupBreakpoints": breakpoints,
        "groupDirectCalls": direct,
        "groupExecution": execution,
        "case22Execution": parent_case22,
    }


def decode_b_target(instruction_hex: Any, instruction_address: int) -> int:
    payload = base.exact_hex(instruction_hex, 4, "DesignLibrary B instruction")
    word = int.from_bytes(payload, "little")
    if word & 0xFC000000 != 0x14000000:
        raise ValueError("DesignLibrary dispatch instruction is not B")
    displacement = word & 0x03FFFFFF
    if displacement & 0x02000000:
        displacement -= 0x04000000
    return instruction_address + displacement * 4


def validate_design_symbol(
    value: Any,
    label: str,
    module_offset: int,
    function: str,
    byte_count: int,
    code_sha256: str,
) -> tuple[dict[str, Any], bytes]:
    symbol, payload = frozen_case22.validate_symbol(value, label)
    module = validate_module(
        symbol.get("module"), f"{label} module", DESIGN_LIBRARY_UUID, "/DesignLibrary"
    )
    if (
        symbol.get("selectedAddress") - module["loadAddress"] != module_offset
        or symbol.get("function") != function
        or symbol.get("symbolByteCount") != byte_count
        or symbol.get("symbolOffset") != 0
        or symbol.get("codeSHA256") != code_sha256
        or hashlib.sha256(payload).hexdigest() != code_sha256
    ):
        raise ValueError(f"{label} exact identity differs")
    return symbol, payload


def validate_provider_extension(
    trace: Mapping[str, Any], parent: Mapping[str, Any]
) -> dict[str, Any]:
    extension = base.mapping(trace.get("case22ProviderTrace"), "provider extension")
    if (
        extension.get("case22ProviderTraceSchemaVersion")
        != PROVIDER_TRACE_SCHEMA_VERSION
        or extension.get("status") != "finalized"
        or extension.get("statusBeforeFinalization") != "provider-trace-closed"
        or extension.get("failures") != []
        or extension.get("finalFailureCount") != 0
    ):
        raise ValueError("provider extension did not finalize cleanly")
    expected_configuration = {
        "selection": (
            "the exact four-byte DesignLibrary thunk reached by the frozen "
            "case-22 ordinal and authenticated SwiftUI wrapper"
        ),
        "designLibraryUUID": DESIGN_LIBRARY_UUID,
        "thunkModuleOffset": THUNK_MODULE_OFFSET,
        "thunkFunction": THUNK_FUNCTION,
        "thunkByteCount": THUNK_BYTE_COUNT,
        "thunkCodeSHA256": THUNK_CODE_SHA256,
        "thunkInstructionHex": THUNK_INSTRUCTION_HEX,
        "thunkBranchDisplacement": THUNK_BRANCH_DISPLACEMENT,
        "providerModuleOffset": PROVIDER_MODULE_OFFSET,
        "providerFunction": PROVIDER_FUNCTION,
        "providerByteCount": PROVIDER_BYTE_COUNT,
        "providerCodeSHA256": PROVIDER_CODE_SHA256,
        "providerObjectByteCount": PROVIDER_OBJECT_BYTE_COUNT,
        "providerReturnToWrapperOffset": PROVIDER_RETURN_TO_WRAPPER_OFFSET,
        "helperModuleOffset": HELPER_MODULE_OFFSET,
        "helperFunction": HELPER_FUNCTION,
        "helperByteCount": HELPER_BYTE_COUNT,
        "helperCodeSHA256": HELPER_CODE_SHA256,
        "maximumProviderInstructionCount": MAXIMUM_PROVIDER_INSTRUCTION_COUNT,
        "maximumProviderHelperCount": MAXIMUM_PROVIDER_HELPER_COUNT,
        "maximumProviderHelperCodeByteCount": MAXIMUM_PROVIDER_HELPER_CODE_BYTE_COUNT,
        "capturedMarginUsedForRuntimeSelection": False,
        "capturedCropUsedForRuntimeSelection": False,
        "capturedImageUsedForRuntimeSelection": False,
        "capturedPixelUsedForRuntimeSelection": False,
    }
    if base.mapping(extension.get("configuration"), "provider configuration") != (
        expected_configuration
    ):
        raise ValueError("provider configuration differs")

    dispatch, dispatch_code = validate_design_symbol(
        extension.get("dispatchThunk"),
        "provider dispatch thunk",
        THUNK_MODULE_OFFSET,
        THUNK_FUNCTION,
        THUNK_BYTE_COUNT,
        THUNK_CODE_SHA256,
    )
    if dispatch_code.hex() != THUNK_INSTRUCTION_HEX:
        raise ValueError("provider dispatch instruction differs")
    provider, provider_code = validate_design_symbol(
        extension.get("provider"),
        "case-22 provider",
        PROVIDER_MODULE_OFFSET,
        PROVIDER_FUNCTION,
        PROVIDER_BYTE_COUNT,
        PROVIDER_CODE_SHA256,
    )
    decoded_target = decode_b_target(dispatch_code.hex(), dispatch["selectedAddress"])
    if decoded_target != provider["selectedAddress"]:
        raise ValueError("provider dispatch target differs")

    case_extension = base.mapping(trace.get("case22CalleeTrace"), "case-22 extension")
    outer_boundaries = base.sequence(
        case_extension.get("opaqueCallees"), "case-22 opaque boundaries"
    )
    if (
        len(outer_boundaries) != 1
        or base.mapping(outer_boundaries[0], "provider outer boundary").get("callee")
        != dispatch
    ):
        raise ValueError("provider dispatch is not the exact outer boundary")

    entry = base.mapping(extension.get("entry"), "provider entry")
    entry_frame = frozen_case22.validate_frame(
        entry.get("frame"), "provider entry frame"
    )
    entry_registers = frozen_case22.validate_register_snapshot(
        entry.get("registers"), "provider entry registers"
    )
    if (
        entry_frame["pc"] != provider["selectedAddress"]
        or entry_registers["pc"] != entry_frame["pc"]
    ):
        raise ValueError("provider entry identity differs")
    entry_stack = base.mapping(entry.get("stack"), "provider entry stack")
    frozen_case22.validate_snapshot(
        entry_stack,
        entry_registers["sp"],
        frozen_case22.STACK_BYTE_COUNT,
        "provider entry stack",
    )
    entry_object = base.mapping(entry.get("object"), "provider entry object")
    entry_object_payload = frozen_case22.validate_snapshot(
        entry_object,
        entry_registers["x20"],
        PROVIDER_OBJECT_BYTE_COUNT,
        "provider entry object",
    )

    states = base.sequence(extension.get("instructionStates"), "provider states")
    helpers = base.sequence(extension.get("helperCallees"), "provider helpers")
    events = base.sequence(extension.get("executionEvents"), "provider events")
    if (
        not 0 < len(states) <= MAXIMUM_PROVIDER_INSTRUCTION_COUNT
        or len(helpers) != 1
        or extension.get("finalInstructionStateCount") != len(states)
        or extension.get("finalHelperCalleeCount") != len(helpers)
        or extension.get("finalExecutionEventCount") != len(events)
        or len(events) != len(states) + len(helpers)
    ):
        raise ValueError("provider trace counts differ")

    validated_states: list[dict[str, Any]] = []
    for index, value in enumerate(states):
        state = base.mapping(value, f"provider state {index}")
        pc = base.integer(state.get("pc"), "provider state PC")
        offset = base.integer(state.get("symbolOffset"), "provider state offset")
        if (
            state.get("stateIndex") != index
            or not provider["symbolStart"] <= pc < provider["symbolEnd"]
            or offset != pc - provider["symbolStart"]
            or state.get("instructionHex") != provider_code[offset : offset + 4].hex()
        ):
            raise ValueError(f"provider state {index} identity differs")
        frame = frozen_case22.validate_frame(
            state.get("frame"), f"provider state {index} frame"
        )
        registers = frozen_case22.validate_register_snapshot(
            state.get("registersBefore"), f"provider state {index} registers"
        )
        frozen_case22.validate_snapshot(
            state.get("stackBefore"),
            registers["sp"],
            frozen_case22.STACK_BYTE_COUNT,
            f"provider state {index} stack",
        )
        result_frame = frozen_case22.validate_frame(
            state.get("resultFrame"), f"provider state {index} result frame"
        )
        result_pc = base.integer(state.get("resultPC"), "provider state result PC")
        if (
            frame["pc"] != pc
            or registers["pc"] != pc
            or result_frame["pc"] != result_pc
            or state.get("resultFunction") != result_frame["function"]
        ):
            raise ValueError(f"provider state {index} machine state differs")
        validated_states.append(dict(state))

    validated_helpers: list[dict[str, Any]] = []
    helper_code_bytes = 0
    for index, value in enumerate(helpers):
        boundary = base.mapping(value, f"provider helper {index}")
        helper, helper_code = validate_design_symbol(
            boundary.get("callee"),
            f"provider helper {index} callee",
            HELPER_MODULE_OFFSET,
            HELPER_FUNCTION,
            HELPER_BYTE_COUNT,
            HELPER_CODE_SHA256,
        )
        helper_code_bytes += len(helper_code)
        entry_frame_value = frozen_case22.validate_frame(
            boundary.get("entryFrame"), f"provider helper {index} entry frame"
        )
        entry_register_values = frozen_case22.validate_register_snapshot(
            boundary.get("registersAtEntry"),
            f"provider helper {index} entry registers",
        )
        frozen_case22.validate_snapshot(
            boundary.get("stackAtEntry"),
            entry_register_values["sp"],
            frozen_case22.STACK_BYTE_COUNT,
            f"provider helper {index} entry stack",
        )
        return_frame_value = frozen_case22.validate_frame(
            boundary.get("returnFrame"), f"provider helper {index} return frame"
        )
        return_register_values = frozen_case22.validate_register_snapshot(
            boundary.get("registersAtReturn"),
            f"provider helper {index} return registers",
        )
        frozen_case22.validate_snapshot(
            boundary.get("stackAtReturn"),
            return_register_values["sp"],
            frozen_case22.STACK_BYTE_COUNT,
            f"provider helper {index} return stack",
        )
        if (
            boundary.get("boundaryIndex") != index
            or boundary.get("expectedReturnFunction") != PROVIDER_FUNCTION
            or entry_frame_value["pc"] != helper["selectedAddress"]
            or entry_register_values["pc"] != entry_frame_value["pc"]
            or return_register_values["pc"] != return_frame_value["pc"]
        ):
            raise ValueError(f"provider helper {index} identity differs")
        validated_helpers.append(dict(boundary))
    if (
        helper_code_bytes > MAXIMUM_PROVIDER_HELPER_CODE_BYTE_COUNT
        or extension.get("finalHelperCodeByteCount") != helper_code_bytes
    ):
        raise ValueError("provider helper code-byte total differs")

    cursor = provider["selectedAddress"]
    for event_index, value in enumerate(events):
        event = base.mapping(value, f"provider event {event_index}")
        record_index = base.integer(event.get("recordIndex"), "provider event index")
        if event.get("kind") == "provider-instruction":
            if not 0 <= record_index < len(validated_states):
                raise ValueError("provider instruction event index differs")
            state = validated_states[record_index]
            if state.get("eventIndex") != event_index or state["pc"] != cursor:
                raise ValueError("provider instruction event chain differs")
            cursor = state["resultPC"]
        elif event.get("kind") == "provider-helper":
            if not 0 <= record_index < len(validated_helpers):
                raise ValueError("provider helper event index differs")
            helper = validated_helpers[record_index]
            if (
                helper.get("eventIndex") != event_index
                or helper["entryFrame"]["pc"] != cursor
            ):
                raise ValueError("provider helper event chain differs")
            cursor = helper["returnFrame"]["pc"]
        else:
            raise ValueError("provider event kind differs")
    wrapper = base.mapping(case_extension.get("target"), "SwiftUI wrapper")
    wrapper_return_pc = wrapper["symbolStart"] + PROVIDER_RETURN_TO_WRAPPER_OFFSET
    if cursor != wrapper_return_pc:
        raise ValueError("provider execution does not end at the SwiftUI wrapper")

    returned = base.mapping(extension.get("return"), "provider return")
    return_frame = frozen_case22.validate_frame(
        returned.get("frame"), "provider return frame"
    )
    return_registers = frozen_case22.validate_register_snapshot(
        returned.get("registers"), "provider return registers"
    )
    frozen_case22.validate_snapshot(
        returned.get("stack"),
        return_registers["sp"],
        frozen_case22.STACK_BYTE_COUNT,
        "provider return stack",
    )
    return_object = base.mapping(returned.get("object"), "provider return object")
    return_object_payload = frozen_case22.validate_snapshot(
        return_object,
        entry_registers["x20"],
        PROVIDER_OBJECT_BYTE_COUNT,
        "provider return object",
    )
    object_changed = return_object_payload != entry_object_payload
    if (
        return_frame["pc"] != wrapper_return_pc
        or return_registers["pc"] != wrapper_return_pc
        or returned.get("objectChanged") is not object_changed
    ):
        raise ValueError("provider return identity differs")
    provider_return = frozen_case22.register_raw(
        base.mapping(returned.get("registers"), "provider return registers"), "v0"
    )[:8]
    parent_return = frozen_case22.register_raw(
        base.mapping(
            base.mapping(case_extension.get("return"), "case-22 return").get(
                "registers"
            ),
            "case-22 return registers",
        ),
        "v0",
    )[:8]
    if provider_return != parent_return:
        raise ValueError("provider return differs from the SwiftUI wrapper return")

    helper_call_states = [
        state for state in validated_states if state["symbolOffset"] == 0x38
    ]
    if (
        len(helper_call_states) != 1
        or helper_call_states[0]["resultPC"] != validated_helpers[0]["entryFrame"]["pc"]
    ):
        raise ValueError("provider helper callsite differs")
    return {
        "providerFunction": provider["function"],
        "providerModuleOffset": PROVIDER_MODULE_OFFSET,
        "providerSymbolByteCount": provider["symbolByteCount"],
        "providerCodeSHA256": provider["codeSHA256"],
        "instructionStateCount": len(states),
        "helperCalleeCount": len(helpers),
        "executionEventCount": len(events),
        "helperCodeByteCount": helper_code_bytes,
        "returnF64": struct.unpack("<d", provider_return)[0],
        "returnF64RawLittleEndianHex": provider_return.hex(),
        "objectChanged": object_changed,
        "completeExecutionChain": True,
        "parentCase22ReturnMatchedBitwise": True,
        "parentCase22Execution": parent["case22Execution"],
    }


def validate(trace_path: Path, preregistration_path: Path) -> dict[str, Any]:
    repository_root = Path(__file__).resolve().parent.parent
    preregistration = validate_preregistration(
        base.load_json(preregistration_path, "local provider preregistration"),
        repository_root,
    )
    trace = base.mapping(base.load_json(trace_path, "provider trace"), "provider trace")
    parent = validate_local_parent(trace)
    provider = validate_provider_extension(trace, parent)
    return {
        "backdropMarginCase22ProviderLocalMacOSValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "classification": (
            "exact output-blind instruction validation of the selected local "
            "DesignLibrary provider; selected-call arithmetic may be decoded, "
            "but public-input transfer and product parity remain open"
        ),
        "conclusion": "success",
        "inputs": {
            "trace": str(trace_path),
            "traceSHA256": sha256(trace_path),
            "preregistration": str(preregistration_path),
            "preregistrationSHA256": sha256(preregistration_path),
        },
        "parentExecution": parent,
        "providerExecution": provider,
        "sealedConclusion": {
            "completeProviderCodeCaptured": True,
            "completeSelectedProviderInstructionTraceCaptured": True,
            "selectedProviderArithmeticMayBeDecoded": True,
            "publicInputMarginLawDecoded": False,
            "unobservedProviderBranchesMapped": False,
            "prospectiveUnseenProfileTransferPassed": False,
            "capturedInputOpticalParityPassed": False,
            "physicalOutputTransferPassed": False,
            "independentWalleZeroByteFrameParityPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
        "preregistrationClassification": preregistration["classification"],
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
