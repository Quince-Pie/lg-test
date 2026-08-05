#!/usr/bin/env python3
"""Validate the prospective software-instruction aggregate trace."""

import argparse
import hashlib
import json
import math
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_capture_backdrop_writer_trace as writer_base
import validate_prepare_layer_active_frame_watch_trace as active_validator
import validate_prepare_layer_frame_correlated_writer_trace as frame_validator


full_base = frame_validator.full_base
merge_base = frame_validator.merge_base

LEGACY_TRACE_SCHEMA_VERSION = 5
LEGACY_VALIDATION_SCHEMA_VERSION = 5
EXPECTED_TRACE_SCHEMA_VERSION = 6
VALIDATION_SCHEMA_VERSION = 6
LEGACY_EXPECTED_CLASSIFICATION = (
    "preregistered-dual-source-linked-selected-glass-dod-full-register-software-"
    "instruction-trace; architectural-writers-opened; crop-policy-generalization-"
    "unseen-transfer-and-product-parity-remain-sealed"
)
EXPECTED_CLASSIFICATION = (
    "preregistered-dual-source-linked-background-filter-crop-full-register-"
    "software-instruction-trace; selected-glass-dod-and-architectural-writers-"
    "opened; crop-policy-generalization-unseen-transfer-and-product-parity-"
    "remain-sealed"
)
LEGACY_EXPECTED_VALIDATION_CLASSIFICATION = (
    "prospective-selected-glass-dod-complete-register-state-gate-for-exact-"
    "dynamic-semantic-replay; crop-policy-generalization-remains-sealed"
)
EXPECTED_VALIDATION_CLASSIFICATION = (
    "prospective-background-filter-crop-complete-register-state-gate-for-exact-"
    "dynamic-semantic-replay; crop-policy-generalization-remains-sealed"
)
PREPARE_LAYER_FULL_CODE_SHA256 = (
    "fe58001369708e0276599f26865be03fdf1dd2348524f92a72c1427be8d1817c"
)
EPOCH_MARKER_NAME = "zeroInitializationAfter"
EPOCH_MARKER_OFFSET = 0xB60
EPOCH_PRECEDING_INSTRUCTION_HEX = "60a6803d"
SELECTION_MARKER_NAME = "sourceLaterHandle"
SELECTION_MARKER_OFFSET = 0x3EF0
SELECTION_MARKER_INSTRUCTION_HEX = "28330b91"
TARGET_PREPARE_RECURSION_DEPTH = 4
SOURCE_LINK_CELL_SPECS = (
    {
        "name": "selectedSourceViaX10",
        "baseRegister": "x10",
        "signedOffset": 128,
    },
    {
        "name": "selectedSourceViaX20",
        "baseRegister": "x20",
        "signedOffset": -24,
    },
)
MAXIMUM_EPOCH_MARKER_HIT_COUNT = 4096
MAXIMUM_EPOCH_RECORD_COUNT = 128
MAXIMUM_SELECTION_MARKER_HIT_COUNT = 4096
MAXIMUM_REJECTED_MARKER_DIAGNOSTIC_COUNT = 128
MAXIMUM_INSTRUCTION_STEP_COUNT = 250000
MAXIMUM_OPAQUE_CALLEE_COUNT = 8192
MAXIMUM_UNEXPECTED_TERMINAL_CONTINUE_COUNT = 8
MAXIMUM_SEMANTIC_DOD_ENTRY_COUNT = 128
SEMANTIC_DOD_SCOPE_NAME = "glassBackgroundDOD"
SEMANTIC_DOD_ENTRY_OFFSET = 0
SEMANTIC_DOD_RETURN_OFFSET = 1128
SEMANTIC_DOD_RETURN_RAW_LITTLE_ENDIAN_HEX = "ff0f5fd6"
SEMANTIC_STACK_BYTE_COUNT = 256
SEMANTIC_CROP_SCOPE_NAME = "addBackgroundFilters"
SEMANTIC_CROP_EXPECTED_INVOCATION_COUNT = 4
SEMANTIC_CROP_MAXIMUM_INVOCATION_COUNT = 8
SEMANTIC_CROP_TARGET_BYTE_COUNT = 32
SEMANTIC_CROP_ARGUMENT_MEMORY_BYTE_COUNT = 1024
SEMANTIC_CROP_CALLER_ROLE_OFFSET = 0x290
SEMANTIC_CROP_CALLER_ROLE_BYTE_COUNT = 2048
CROP_INTEGER_SOURCE_OFFSET = 0x270
CROP_INTEGER_BYTE_COUNT = 16
CROP_DESTINATION_OFFSET = 0xB0
CROP_STORE_RELATIVE_OFFSET = 0x55C0
CROP_STORE_RAW_LITTLE_ENDIAN_HEX = "802f803d"
CROP_UNION_INPUT_RELATIVE_OFFSET = 0x8570
CROP_UNION_INPUT_RAW_LITTLE_ENDIAN_HEX = "88275729"
CROP_UNION_STATE_OFFSET = 0xA0
CROP_UNION_STATE_BYTE_COUNT = 48
CROP_RETURN_MNEMONICS = ("ret", "retab")
CROP_RETURN_RAW_LITTLE_ENDIAN_HEX = ("c0035fd6", "ff0f5fd6")
KNOWN_CANVAS_EXTENT = 1024.0
KNOWN_GLASS_EXTENT = 640.0
KNOWN_EDGE_PADDING = 8.0
EPOCH_FRAME_REGISTER_NAMES = ("x10", "x19", "x20", "x29", "pc")
SELECTION_FRAME_REGISTER_NAMES = ("x19", "x28", "x29", "pc")
RETIRED_INHERITED_WRITER_SITE_NAMES = tuple(
    site["name"]
    for site in frame_validator.WRITER_SITES
    if site["name"] != EPOCH_MARKER_NAME
)
RETAINED_CONTROL_BREAKPOINT_NAMES = (
    EPOCH_MARKER_NAME,
    SELECTION_MARKER_NAME,
)
WRITER_MNEMONIC_PREFIXES = (
    "st",
    "swp",
    "cas",
    "ldadd",
    "ldclr",
    "ldeor",
    "ldset",
    "ldsmax",
    "ldsmin",
    "ldumax",
    "ldumin",
)
CALL_MNEMONIC_PREFIXES = ("bl",)
FRAME_TRACE_OUTPUT_ENVIRONMENT = "LG_PREPARE_LAYER_FRAME_WRITER_TRACE_OUTPUT"

CHECKPOINT_SCOPE_SPECS = (
    {
        "name": "prepareLayer",
        "function": merge_base.PREPARE_LAYER_FUNCTION,
        "relativeToPrepareLayer": 0,
        "byteCount": full_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
        "expectedSHA256": PREPARE_LAYER_FULL_CODE_SHA256,
    },
    {
        "name": "rectApplyTransform",
        "function": "CA::Rect::apply_transform(CA::SimpleTransform const&)",
        "relativeToPrepareLayer": -1207212,
        "byteCount": 216,
        "expectedSHA256": (
            "33690a5426ab0ea58626fd32bac7793953f0b9d4bf5a2b9de070701c2b3f1905"
        ),
    },
    {
        "name": "rectUnapplyTransform",
        "function": "CA::Rect::unapply_transform(CA::SimpleTransform const&)",
        "relativeToPrepareLayer": -1202648,
        "byteCount": 216,
        "expectedSHA256": (
            "6cfb69c5706fce5a48b722499d708ea7e76ffdcaba41b8b5ec77ad2e4481b046"
        ),
    },
    {
        "name": "glassBackgroundDOD",
        "function": (
            "CA::OGL::GlassBackgroundFilter::DOD(CA::Render::Filter const*, "
            "CA::Render::Layer const*, CA::Rect&) const"
        ),
        "relativeToPrepareLayer": -90584,
        "byteCount": 1136,
        "expectedSHA256": (
            "8ac014e4a0e296c28b5ada0444a281d7609e93a239f4201f748d758defe6955e"
        ),
    },
    {
        "name": "filterApplyDOD",
        "function": (
            "CA::Render::Filter::apply_dod(CA::Render::Layer const*, CA::Rect&) const"
        ),
        "relativeToPrepareLayer": -609324,
        "byteCount": 1092,
        "expectedSHA256": None,
    },
    {
        "name": "filterApply",
        "function": "CA::Render::Updater::FilterOp::apply_filter(CA::Rect&, bool)",
        "relativeToPrepareLayer": -61476,
        "byteCount": 292,
        "expectedSHA256": None,
    },
    {
        "name": "filterMapBounds",
        "function": (
            "CA::Render::Updater::FilterOp::map_bounds("
            "CA::Render::Updater::LayerShapes&, bool)"
        ),
        "relativeToPrepareLayer": -61056,
        "byteCount": 788,
        "expectedSHA256": None,
    },
    {
        "name": SEMANTIC_CROP_SCOPE_NAME,
        "function": (
            "CA::Render::Updater::add_background_filters_("
            "CA::Render::Updater::GlobalState&, "
            "CA::Render::Updater::LocalState&, CA::Render::Layer const*, "
            "CA::Render::LayerNode*, CA::Render::Updater::LocalState*, "
            "CA::Render::Updater::LayerShapes*)"
        ),
        "relativeToPrepareLayer": 40128,
        "byteCount": 1564,
        "expectedSHA256": None,
    },
    {
        "name": "unionBounds",
        "function": full_base.UNION_HELPER_SYMBOL_NAME,
        "relativeToPrepareLayer": full_base.UNION_HELPER_RELATIVE_TO_PREPARE_LAYER,
        "byteCount": full_base.UNION_HELPER_SYMBOL_BYTE_COUNT,
        "expectedSHA256": full_base.UNION_HELPER_SYMBOL_SHA256,
    },
)

LEGACY_CHECKPOINT_SCOPE_SPECS = tuple(
    spec for spec in CHECKPOINT_SCOPE_SPECS if spec["name"] != SEMANTIC_CROP_SCOPE_NAME
)


def _scope_configuration() -> list[dict[str, Any]]:
    return [dict(spec) for spec in CHECKPOINT_SCOPE_SPECS]


EXPECTED_CONFIGURATION = {
    "prepareLayerFunction": merge_base.PREPARE_LAYER_FUNCTION,
    "prepareLayerSymbolByteCount": full_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
    "prepareLayerFullCodeSHA256": PREPARE_LAYER_FULL_CODE_SHA256,
    "aggregateOffset": full_base.AGGREGATE_OFFSET,
    "aggregateByteCount": full_base.AGGREGATE_BYTE_COUNT,
    "roleStateByteCount": full_base.ROLE_STATE_BYTE_COUNT,
    "epochMarkerName": EPOCH_MARKER_NAME,
    "epochMarkerOffset": EPOCH_MARKER_OFFSET,
    "epochPrecedingInstructionRawLittleEndianHex": (EPOCH_PRECEDING_INSTRUCTION_HEX),
    "selectionMarkerName": SELECTION_MARKER_NAME,
    "selectionMarkerOffset": SELECTION_MARKER_OFFSET,
    "selectionMarkerInstructionRawLittleEndianHex": (SELECTION_MARKER_INSTRUCTION_HEX),
    "targetPrepareRecursionDepth": TARGET_PREPARE_RECURSION_DEPTH,
    "sourceLinkCells": [dict(spec) for spec in SOURCE_LINK_CELL_SPECS],
    "maximumEpochMarkerHitCount": MAXIMUM_EPOCH_MARKER_HIT_COUNT,
    "maximumEpochRecordCount": MAXIMUM_EPOCH_RECORD_COUNT,
    "maximumSelectionMarkerHitCount": MAXIMUM_SELECTION_MARKER_HIT_COUNT,
    "maximumRejectedMarkerDiagnosticCount": (MAXIMUM_REJECTED_MARKER_DIAGNOSTIC_COUNT),
    "maximumInstructionStepCount": MAXIMUM_INSTRUCTION_STEP_COUNT,
    "maximumOpaqueCalleeCount": MAXIMUM_OPAQUE_CALLEE_COUNT,
    "maximumUnexpectedTerminalContinueCount": (
        MAXIMUM_UNEXPECTED_TERMINAL_CONTINUE_COUNT
    ),
    "maximumSemanticDODEntryCount": MAXIMUM_SEMANTIC_DOD_ENTRY_COUNT,
    "semanticDODScopeName": SEMANTIC_DOD_SCOPE_NAME,
    "semanticDODEntryOffset": SEMANTIC_DOD_ENTRY_OFFSET,
    "semanticDODReturnOffset": SEMANTIC_DOD_RETURN_OFFSET,
    "semanticDODReturnRawLittleEndianHex": (SEMANTIC_DOD_RETURN_RAW_LITTLE_ENDIAN_HEX),
    "semanticStackByteCount": SEMANTIC_STACK_BYTE_COUNT,
    "semanticGeneralRegisterNames": list(full_base.GENERAL_REGISTER_NAMES),
    "semanticSIMDRegisterNames": list(full_base.SIMD_REGISTER_NAMES),
    "semanticCropScopeName": SEMANTIC_CROP_SCOPE_NAME,
    "semanticCropExpectedInvocationCount": SEMANTIC_CROP_EXPECTED_INVOCATION_COUNT,
    "semanticCropMaximumInvocationCount": SEMANTIC_CROP_MAXIMUM_INVOCATION_COUNT,
    "semanticCropTargetByteCount": SEMANTIC_CROP_TARGET_BYTE_COUNT,
    "semanticCropArgumentMemoryByteCount": (SEMANTIC_CROP_ARGUMENT_MEMORY_BYTE_COUNT),
    "semanticCropCallerRoleOffset": SEMANTIC_CROP_CALLER_ROLE_OFFSET,
    "semanticCropCallerRoleByteCount": SEMANTIC_CROP_CALLER_ROLE_BYTE_COUNT,
    "cropIntegerSourceOffset": CROP_INTEGER_SOURCE_OFFSET,
    "cropIntegerByteCount": CROP_INTEGER_BYTE_COUNT,
    "cropDestinationOffset": CROP_DESTINATION_OFFSET,
    "cropStoreRelativeOffset": CROP_STORE_RELATIVE_OFFSET,
    "cropStoreRawLittleEndianHex": CROP_STORE_RAW_LITTLE_ENDIAN_HEX,
    "cropUnionInputRelativeOffset": CROP_UNION_INPUT_RELATIVE_OFFSET,
    "cropUnionInputRawLittleEndianHex": CROP_UNION_INPUT_RAW_LITTLE_ENDIAN_HEX,
    "cropUnionStateOffset": CROP_UNION_STATE_OFFSET,
    "cropUnionStateByteCount": CROP_UNION_STATE_BYTE_COUNT,
    "cropReturnMnemonics": list(CROP_RETURN_MNEMONICS),
    "cropReturnRawLittleEndianHex": list(CROP_RETURN_RAW_LITTLE_ENDIAN_HEX),
    "knownCanvasExtent": KNOWN_CANVAS_EXTENT,
    "knownGlassExtent": KNOWN_GLASS_EXTENT,
    "knownEdgePadding": KNOWN_EDGE_PADDING,
    "epochFrameRegisterNames": list(EPOCH_FRAME_REGISTER_NAMES),
    "selectionFrameRegisterNames": list(SELECTION_FRAME_REGISTER_NAMES),
    "structuralFramePointerSource": "SBFrame.GetFP",
    "retiredInheritedWriterSiteNames": list(RETIRED_INHERITED_WRITER_SITE_NAMES),
    "retainedControlBreakpointNames": list(RETAINED_CONTROL_BREAKPOINT_NAMES),
    "checkpointScopes": _scope_configuration(),
    "writerMnemonicPrefixes": list(WRITER_MNEMONIC_PREFIXES),
    "callMnemonicPrefixes": list(CALL_MNEMONIC_PREFIXES),
    "frameTraceOutputEnvironment": FRAME_TRACE_OUTPUT_ENVIRONMENT,
    "frameTraceSchemaVersion": frame_validator.EXPECTED_TRACE_SCHEMA_VERSION,
    "selectionRule": (
        "stop at the first source-known exact-depth-four zero epoch whose "
        "uint64 cells at x10+128 and x20-24 both equal the independently "
        "selected source; then single-step that live thread/x19/x29 frame "
        "until its exact +0x3ef0 marker"
    ),
    "sourceLinkRule": (
        "retain both exact eight-byte cells and reject every epoch unless "
        "both decoded uint64 values equal the independently selected source"
    ),
    "steppingRule": (
        "disable every software breakpoint before stepping; execute one "
        "architectural instruction at a time inside every frozen scope; step "
        "out of every other callee as a named atomic boundary"
    ),
    "synchronousDebuggerRule": (
        "set SBDebugger async mode false and read it back false before the "
        "first SBThread stepping operation"
    ),
    "hardwareWatchpointRule": (
        "the target must contain zero hardware watchpoints before instruction stepping"
    ),
    "opaqueBoundaryRule": (
        "a passing trace permits no aggregate change across an opaque callee boundary"
    ),
    "knownStateTransferRule": (
        "the continuous instruction state sequence must contain, bit-for-bit "
        "and in order, zero; [P,1024-P-640,640,640]; "
        "[P,1024-P-640-8,640,648]; and [floor(P)-1,"
        "1024-P-640-8,P+640-(floor(P)-1),P+648-(floor(P)-1)]"
    ),
    "semanticInvocationRule": (
        "at every glassBackgroundDOD +0x0 entry retain x3; select the unique "
        "entry where x3 equals selected roleBase+aggregateOffset; for every "
        "executed instruction in that invocation retain the complete scalar "
        "and SIMD register files and 256 bytes at sp before execution, then "
        "retain the complete return state"
    ),
    "semanticCropInvocationRule": (
        "retain all four add_background_filters_ entries in execution order; "
        "require x5=x19+0x290; from each entry through its exact return retain "
        "every executed opened-scope instruction with complete scalar/SIMD "
        "registers, 256 stack bytes, and the fixed 32-byte x5 target; retain "
        "1024 bytes at every entry argument pointer and the complete 2048-byte "
        "caller role at entry and return"
    ),
    "semanticCropLinkRule": (
        "link the first three invocations by caller x19 to the exact "
        "prepare_layer +0x55c0 q0 store and then to the exact +0x8570 nested-"
        "crop union input; require the fourth invocation to target the "
        "prospectively selected role aggregate"
    ),
}

_LEGACY_CONFIGURATION_EXCLUDED_FIELDS = {
    "semanticCropScopeName",
    "semanticCropExpectedInvocationCount",
    "semanticCropMaximumInvocationCount",
    "semanticCropTargetByteCount",
    "semanticCropArgumentMemoryByteCount",
    "semanticCropCallerRoleOffset",
    "semanticCropCallerRoleByteCount",
    "cropIntegerSourceOffset",
    "cropIntegerByteCount",
    "cropDestinationOffset",
    "cropStoreRelativeOffset",
    "cropStoreRawLittleEndianHex",
    "cropUnionInputRelativeOffset",
    "cropUnionInputRawLittleEndianHex",
    "cropUnionStateOffset",
    "cropUnionStateByteCount",
    "cropReturnMnemonics",
    "cropReturnRawLittleEndianHex",
    "semanticCropInvocationRule",
    "semanticCropLinkRule",
}
LEGACY_EXPECTED_CONFIGURATION = {
    name: (
        [dict(spec) for spec in LEGACY_CHECKPOINT_SCOPE_SPECS]
        if name == "checkpointScopes"
        else value
    )
    for name, value in EXPECTED_CONFIGURATION.items()
    if name not in _LEGACY_CONFIGURATION_EXCLUDED_FIELDS
}


mapping = frame_validator.mapping
sequence = frame_validator.sequence
integer = frame_validator.integer


def _payload(value: Any, byte_count: int, label: str) -> bytes:
    return frame_validator._payload(value, byte_count, label)


def _memory_payload(
    value: Any,
    label: str,
    *,
    expected_address: int,
    expected_byte_count: int,
) -> bytes:
    return frame_validator._memory_payload(
        value,
        label,
        expected_address=expected_address,
        expected_byte_count=expected_byte_count,
    )


def _callback_order(trace: Mapping[str, Any]) -> dict[int, str]:
    return frame_validator._callback_order(trace)


def _require_callback(
    order: Mapping[int, str], value: Any, kind: str, label: str
) -> int:
    return frame_validator._require_callback(order, value, kind, label)


def _identity(value: Any, label: str) -> dict[str, int]:
    item = mapping(value, label)
    if set(item) != {"threadID", "roleBase", "framePointer"}:
        raise ValueError(f"{label} fields differ")
    result = {
        name: integer(item.get(name), f"{label} {name}")
        for name in ("threadID", "roleBase", "framePointer")
    }
    if any(field <= 0 for field in result.values()):
        raise ValueError(f"{label} values differ")
    return result


def _module(value: Any, label: str) -> dict[str, Any]:
    item = mapping(value, label)
    if (
        item.get("valid") is not True
        or not isinstance(item.get("path"), str)
        or not item["path"]
        or integer(item.get("loadAddress"), f"{label} load address") <= 0
        or not isinstance(item.get("uuid"), (str, type(None)))
    ):
        raise ValueError(f"{label} differs")
    return dict(item)


def _role_aggregate(value: Any, label: str, identity: Mapping[str, int]) -> bytes:
    role = _memory_payload(
        value,
        label,
        expected_address=identity["roleBase"],
        expected_byte_count=full_base.ROLE_STATE_BYTE_COUNT,
    )
    return role[
        full_base.AGGREGATE_OFFSET : full_base.AGGREGATE_OFFSET
        + full_base.AGGREGATE_BYTE_COUNT
    ]


def _static_trace(
    trace: Mapping[str, Any],
    order: Mapping[int, str],
    inherited: Mapping[str, Any],
    scope_specs: Sequence[Mapping[str, Any]],
) -> tuple[int, dict[str, Any], dict[str, dict[str, Any]], bytes]:
    prepare = mapping(trace.get("prepareLayer"), "prepare layer")
    entry = _require_callback(
        order, prepare.get("callbackSequence"), "prepare-layer-entry", "entry"
    )
    if entry != 1:
        raise ValueError("prepare entry order differs")
    start = integer(prepare.get("symbolStart"), "prepare start")
    end = integer(prepare.get("symbolEnd"), "prepare end")
    if (
        prepare.get("callbackPC") != start
        or prepare.get("callbackLocationAddress") != start
        or prepare.get("function") != merge_base.PREPARE_LAYER_FUNCTION
        or end - start != full_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT
        or prepare.get("symbolByteCount") != full_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT
        or prepare.get("fullCodeSHA256") != PREPARE_LAYER_FULL_CODE_SHA256
    ):
        raise ValueError("prepare identity differs")
    module = _module(prepare.get("module"), "prepare module")
    inherited_module = mapping(inherited.get("prepareModule"), "inherited module")
    if (
        module["path"] != inherited_module.get("path")
        or module["loadAddress"] != inherited_module.get("loadAddress")
        or start != inherited.get("prepareStart")
    ):
        raise ValueError("prepare module differs from inherited context")
    epoch = mapping(prepare.get("epochMarker"), "epoch marker")
    selection = mapping(prepare.get("selectionMarker"), "selection marker")
    if (
        epoch.get("address") != start + EPOCH_MARKER_OFFSET
        or integer(epoch.get("breakpointID"), "epoch breakpoint") <= 0
        or selection.get("address") != start + SELECTION_MARKER_OFFSET
        or integer(selection.get("breakpointID"), "selection breakpoint") <= 0
        or epoch["breakpointID"] == selection["breakpointID"]
    ):
        raise ValueError("control marker identity differs")

    values = list(sequence(trace.get("checkpointScopes"), "checkpoint scopes"))
    if len(values) != len(scope_specs):
        raise ValueError("checkpoint scope count differs")
    scopes: dict[str, dict[str, Any]] = {}
    prepare_code = b""
    for index, (raw, spec) in enumerate(zip(values, scope_specs, strict=True)):
        label = f"checkpoint scope {index}"
        item = mapping(raw, label)
        expected_start = start + spec["relativeToPrepareLayer"]
        expected_end = expected_start + spec["byteCount"]
        if (
            item.get("scopeIndex") != index
            or item.get("name") != spec["name"]
            or item.get("function") != spec["function"]
            or item.get("relativeToPrepareLayer") != spec["relativeToPrepareLayer"]
            or item.get("startAddress") != expected_start
            or item.get("endAddress") != expected_end
            or item.get("byteCount") != spec["byteCount"]
            or item.get("expectedSHA256") != spec["expectedSHA256"]
        ):
            raise ValueError(f"{label} identity differs")
        code = _payload(item.get("hex"), spec["byteCount"], f"{label} code")
        digest = hashlib.sha256(code).hexdigest()
        if item.get("observedSHA256") != digest or (
            spec["expectedSHA256"] is not None and digest != spec["expectedSHA256"]
        ):
            raise ValueError(f"{label} digest differs")
        scope_module = _module(item.get("module"), f"{label} module")
        if (
            scope_module["path"] != module["path"]
            or scope_module["loadAddress"] != module["loadAddress"]
            or scope_module["uuid"] != module["uuid"]
        ):
            raise ValueError(f"{label} module differs")
        scopes[spec["name"]] = {**dict(item), "code": code}
        if spec["name"] == "prepareLayer":
            prepare_code = code
    if (
        prepare_code[EPOCH_MARKER_OFFSET - 4 : EPOCH_MARKER_OFFSET].hex()
        != EPOCH_PRECEDING_INSTRUCTION_HEX
        or prepare_code[SELECTION_MARKER_OFFSET : SELECTION_MARKER_OFFSET + 4].hex()
        != SELECTION_MARKER_INSTRUCTION_HEX
    ):
        raise ValueError("marker instruction bytes differ")
    return start, module, scopes, prepare_code


def _retirement(
    trace: Mapping[str, Any],
    order: Mapping[int, str],
    prepare: Mapping[str, Any],
    selected_source: int,
) -> set[int]:
    record = mapping(
        trace.get("inheritedWriterBreakpointRetirement"), "writer retirement"
    )
    callback = _require_callback(
        order,
        record.get("callbackSequence"),
        "inherited-writer-breakpoints-retired",
        "writer retirement",
    )
    if (
        callback != 2
        or record.get("selectedSource") != selected_source
        or integer(record.get("threadID"), "retirement thread") <= 0
        or integer(record.get("pc"), "retirement PC") <= 0
        or trace.get("inheritedWriterBreakpointsRetired") is not True
    ):
        raise ValueError("writer retirement identity differs")
    retired = [
        mapping(value, "retired breakpoint")
        for value in sequence(record.get("retired"), "retired breakpoints")
    ]
    retained = [
        mapping(value, "retained breakpoint")
        for value in sequence(
            record.get("retainedControlBreakpoints"), "retained breakpoints"
        )
    ]
    if [item.get("name") for item in retired] != list(
        RETIRED_INHERITED_WRITER_SITE_NAMES
    ) or [item.get("name") for item in retained] != list(
        RETAINED_CONTROL_BREAKPOINT_NAMES
    ):
        raise ValueError("writer retirement inventory differs")
    if any(item.get("enabledAfterRetirement") is not False for item in retired):
        raise ValueError("retired breakpoint remained enabled")
    if any(item.get("enabledAfterRetirement") is not True for item in retained):
        raise ValueError("control breakpoint was not retained")
    identifiers = {
        integer(item.get("breakpointID"), "breakpoint ID")
        for item in retired + retained
    }
    if len(identifiers) != len(retired) + len(retained):
        raise ValueError("breakpoint IDs differ")
    epoch = mapping(prepare.get("epochMarker"), "prepare epoch marker")
    selection = mapping(prepare.get("selectionMarker"), "prepare selection marker")
    if retained[0].get("breakpointID") != epoch.get("breakpointID") or retained[1].get(
        "breakpointID"
    ) != selection.get("breakpointID"):
        raise ValueError("retained control IDs differ")
    return identifiers


def _source_link_cells(
    value: Any,
    label: str,
    registers: Mapping[str, int],
    selected_source: int,
) -> bool:
    values = list(sequence(value, f"{label} source-link cells"))
    if len(values) != len(SOURCE_LINK_CELL_SPECS):
        raise ValueError(f"{label} source-link inventory differs")
    matches = []
    expected_fields = {
        "name",
        "baseRegister",
        "signedOffset",
        "baseValue",
        "address",
        "memory",
        "observedValue",
        "selectedSourceMatches",
    }
    for index, (raw, spec) in enumerate(
        zip(values, SOURCE_LINK_CELL_SPECS, strict=True)
    ):
        cell_label = f"{label} source-link cell {index}"
        item = mapping(raw, cell_label)
        base = registers[spec["baseRegister"]]
        address = base + spec["signedOffset"]
        payload = _memory_payload(
            item.get("memory"),
            cell_label,
            expected_address=address,
            expected_byte_count=8,
        )
        observed = int.from_bytes(payload, "little", signed=False)
        matches_source = observed == selected_source
        if (
            set(item) != expected_fields
            or item.get("name") != spec["name"]
            or item.get("baseRegister") != spec["baseRegister"]
            or item.get("signedOffset") != spec["signedOffset"]
            or item.get("baseValue") != base
            or item.get("address") != address
            or item.get("observedValue") != observed
            or item.get("selectedSourceMatches") is not matches_source
        ):
            raise ValueError(f"{cell_label} differs")
        matches.append(matches_source)
    return all(matches)


def _epoch_records(
    trace: Mapping[str, Any],
    order: Mapping[int, str],
    prepare_start: int,
    selected_source: int,
) -> tuple[dict[str, int], bytes, int]:
    values = list(sequence(trace.get("epochRecords"), "epoch records"))
    if not 1 <= len(values) <= MAXIMUM_EPOCH_RECORD_COUNT:
        raise ValueError("prospective epoch inventory differs")
    zero = bytes(full_base.AGGREGATE_BYTE_COUNT)
    selected_identity: dict[str, int] | None = None
    selected_index = -1
    previous_callback = 2
    for index, raw in enumerate(values):
        label = f"epoch record {index}"
        item = mapping(raw, label)
        callback = _require_callback(
            order,
            item.get("callbackSequence"),
            "source-known-depth-four-zero-epoch",
            label,
        )
        identity = _identity(item.get("identity"), f"{label} identity")
        aggregate = _role_aggregate(
            item.get("roleStateAtEpoch"), f"{label} role", identity
        )
        registers = frame_validator._registers(
            item.get("registers"), EPOCH_FRAME_REGISTER_NAMES, f"{label} registers"
        )
        source_linked = _source_link_cells(
            item.get("sourceLinkCells"), label, registers, selected_source
        )
        if (
            item.get("recordIndex") != index
            or callback <= previous_callback
            or item.get("sourceKnownDepthFourOrdinal") != index + 1
            or item.get("pc") != prepare_start + EPOCH_MARKER_OFFSET
            or item.get("prepareRecursionDepth") != TARGET_PREPARE_RECURSION_DEPTH
            or item.get("selectedSourceKnown") != selected_source
            or _payload(
                item.get("aggregateAtEpochHex"),
                full_base.AGGREGATE_BYTE_COUNT,
                f"{label} aggregate",
            )
            != aggregate
            or aggregate != zero
            or item.get("sourceLinkMatched") is not source_linked
            or item.get("prospectiveTraceTarget") is not source_linked
        ):
            raise ValueError(f"{label} differs")
        if (
            registers["x19"] != identity["roleBase"]
            or registers["x29"] != identity["framePointer"]
            or registers["pc"] != prepare_start + EPOCH_MARKER_OFFSET
        ):
            raise ValueError(f"{label} registers differ")
        prepare_frames = list(
            sequence(item.get("prepareFrames"), f"{label} prepare frames")
        )
        if (
            len(prepare_frames) != TARGET_PREPARE_RECURSION_DEPTH
            or mapping(prepare_frames[0], f"{label} top prepare").get(
                "unwindFramePointer"
            )
            != identity["framePointer"]
        ):
            raise ValueError(f"{label} structural frames differ")
        if source_linked:
            if selected_identity is not None or index != len(values) - 1:
                raise ValueError(
                    "source-linked epoch selection is not first or terminal"
                )
            selected_identity = identity
            selected_index = index
        previous_callback = callback
    if selected_identity is None:
        raise ValueError("selected epoch is absent")
    if (
        trace.get("sourceKnownDepthFourEpochCount") != len(values)
        or trace.get("sourceLinkedDepthFourEpochCount") != 1
        or trace.get("rejectedSourceLinkEpochCount") != len(values) - 1
        or trace.get("finalEpochRecordCount") != len(values)
        or trace.get("discardedEpochRecordCount") != 0
        or trace.get("epochMarkerHitCount", 0) > MAXIMUM_EPOCH_MARKER_HIT_COUNT
    ):
        raise ValueError("epoch accounting differs")
    return selected_identity, zero, selected_index


def _breakpoint_disablement(
    trace: Mapping[str, Any], order: Mapping[int, str], required_ids: set[int]
) -> int:
    record = mapping(trace.get("breakpointDisablement"), "breakpoint disablement")
    callback = _require_callback(
        order,
        record.get("callbackSequence"),
        "all-software-breakpoints-disabled",
        "breakpoint disablement",
    )
    values = [
        mapping(value, "disabled breakpoint")
        for value in sequence(record.get("breakpoints"), "disabled breakpoints")
    ]
    identifiers = []
    if record.get("watchpointCount") != 0:
        raise ValueError("hardware watchpoint inventory differs")
    for item in values:
        identifier = integer(item.get("breakpointID"), "disabled breakpoint ID")
        if (
            item.get("enabledAfterDisableAll") is not False
            or integer(item.get("locationCount"), "disabled location count") < 0
        ):
            raise ValueError("software breakpoint was not disabled")
        identifiers.append(identifier)
    if len(identifiers) != len(set(identifiers)) or not required_ids <= set(
        identifiers
    ):
        raise ValueError("disabled breakpoint inventory differs")
    return callback


def _instruction(
    value: Any,
    label: str,
    scopes: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    item = mapping(value, label)
    scope_name = item.get("scopeName")
    if scope_name not in scopes:
        raise ValueError(f"{label} scope differs")
    scope = scopes[scope_name]
    pc = integer(item.get("pc"), f"{label} PC")
    offset = integer(item.get("scopeOffset"), f"{label} scope offset")
    raw = _payload(item.get("rawLittleEndianHex"), 4, f"{label} bytes")
    if (
        offset < 0
        or offset + 4 > scope["byteCount"]
        or offset % 4 != 0
        or pc != scope["startAddress"] + offset
        or item.get("prepareLayerRelativeOffset")
        != pc - scopes["prepareLayer"]["startAddress"]
        or raw != scope["code"][offset : offset + 4]
        or not isinstance(item.get("mnemonic"), str)
        or not isinstance(item.get("operands"), str)
        or not isinstance(item.get("comment"), str)
        or not isinstance(item.get("potentialWriter"), bool)
        or not isinstance(item.get("potentialCall"), bool)
    ):
        raise ValueError(f"{label} differs")
    return dict(item)


def _context(
    value: Any,
    label: str,
    identity: Mapping[str, int],
    addresses: Mapping[str, Any],
    expected_aggregate: bytes,
) -> None:
    item = mapping(value, label)
    frame = writer_base.frame_record(item.get("frame"), f"{label} frame")
    role = _role_aggregate(item.get("roleState"), f"{label} role", identity)
    if role != expected_aggregate:
        raise ValueError(f"{label} aggregate differs")
    backtrace = list(sequence(item.get("backtrace"), f"{label} backtrace"))
    if not backtrace:
        raise ValueError(f"{label} backtrace differs")
    writer_base.private_fields(item.get("privateFields"), f"{label} private fields")
    writer_base.operand_snapshot(
        item.get("operandSnapshot"),
        f"{label} operands",
        addresses,
        is_prepare_layer=frame.get("function") == merge_base.PREPARE_LAYER_FUNCTION,
    )


def _after_context(
    value: Any,
    label: str,
    identity: Mapping[str, int],
    expected_aggregate: bytes,
) -> None:
    item = mapping(value, label)
    if not list(sequence(item.get("backtrace"), f"{label} backtrace")):
        raise ValueError(f"{label} backtrace differs")
    if (
        _role_aggregate(item.get("roleState"), f"{label} role", identity)
        != expected_aggregate
    ):
        raise ValueError(f"{label} aggregate differs")
    writer_base.private_fields(item.get("privateFields"), f"{label} private fields")


def _known_state_sequence(states: Sequence[bytes]) -> dict[str, Any]:
    if not states or states[0] != bytes(full_base.AGGREGATE_BYTE_COUNT):
        raise ValueError("instruction state sequence does not start at zero")
    final_values = struct.unpack("<4d", states[-1])
    if any(not math.isfinite(value) for value in final_values):
        raise ValueError("final aggregate is non-finite")
    p = KNOWN_CANVAS_EXTENT - KNOWN_GLASS_EXTENT - KNOWN_EDGE_PADDING - final_values[1]
    origin = math.floor(p) - 1
    expected_values = (
        (0.0, 0.0, 0.0, 0.0),
        (p, KNOWN_CANVAS_EXTENT - p - KNOWN_GLASS_EXTENT, 640.0, 640.0),
        (
            p,
            KNOWN_CANVAS_EXTENT - p - KNOWN_GLASS_EXTENT - KNOWN_EDGE_PADDING,
            640.0,
            640.0 + KNOWN_EDGE_PADDING,
        ),
        (
            float(origin),
            KNOWN_CANVAS_EXTENT - p - KNOWN_GLASS_EXTENT - KNOWN_EDGE_PADDING,
            p + KNOWN_GLASS_EXTENT - origin,
            p + KNOWN_GLASS_EXTENT + KNOWN_EDGE_PADDING - origin,
        ),
    )
    expected = [struct.pack("<4d", *values) for values in expected_values]
    cursor = 0
    indices = []
    for item in expected:
        try:
            index = states.index(item, cursor)
        except ValueError as error:
            raise ValueError("known aggregate state transfer differs") from error
        indices.append(index)
        cursor = index + 1
    if states[-1] != expected[-1]:
        raise ValueError("known final aggregate differs")
    return {
        "carrierP": p,
        "integerOriginL": origin,
        "orderedStateIndices": indices,
        "orderedStatesHex": [item.hex() for item in expected],
    }


def _steps_and_transitions(
    trace: Mapping[str, Any],
    order: Mapping[int, str],
    scopes: Mapping[str, Mapping[str, Any]],
    identity: Mapping[str, int],
    initial: bytes,
    addresses: Mapping[str, Any],
) -> tuple[list[bytes], list[dict[str, Any]]]:
    raw_steps = list(sequence(trace.get("instructionSteps"), "instruction steps"))
    if not 1 <= len(raw_steps) <= MAXIMUM_INSTRUCTION_STEP_COUNT:
        raise ValueError("instruction step count differs")
    raw_transitions = list(
        sequence(trace.get("aggregateTransitions"), "aggregate transitions")
    )
    raw_boundaries = list(
        sequence(trace.get("opaqueCalleeBoundaries"), "opaque boundaries")
    )
    states = [initial]
    transitions: list[dict[str, Any]] = []
    boundary_index = 0
    transition_index = 0
    previous = initial
    for index, raw in enumerate(raw_steps):
        label = f"instruction step {index}"
        step = mapping(raw, label)
        before = _payload(
            step.get("aggregateBeforeHex"),
            full_base.AGGREGATE_BYTE_COUNT,
            f"{label} before",
        )
        after = _payload(
            step.get("aggregateAfterHex"),
            full_base.AGGREGATE_BYTE_COUNT,
            f"{label} after",
        )
        changed = before != after
        expected_lanes = [
            offset
            for offset in (0, 8, 16, 24)
            if before[offset : offset + 8] != after[offset : offset + 8]
        ]
        if (
            step.get("stepIndex") != index
            or before != previous
            or step.get("aggregateChanged") is not changed
            or step.get("changedLaneOffsets") != expected_lanes
            or not isinstance(step.get("resultPC"), int)
            or not isinstance(step.get("resultFunction"), (str, type(None)))
        ):
            raise ValueError(f"{label} continuity differs")
        kind = step.get("kind")
        instruction = None
        if kind == "scope-instruction":
            instruction = _instruction(
                step.get("instruction"), f"{label} instruction", scopes
            )
            if step.get("opaqueBoundary") is not None:
                raise ValueError(f"{label} opaque field differs")
        elif kind == "opaque-callee-step-out":
            if step.get("instruction") is not None or boundary_index >= len(
                raw_boundaries
            ):
                raise ValueError(f"{label} boundary differs")
            boundary = mapping(
                raw_boundaries[boundary_index], f"opaque boundary {boundary_index}"
            )
            if (
                boundary.get("boundaryIndex") != boundary_index
                or step.get("opaqueBoundary") != boundary
                or boundary.get("aggregateChanged") is not changed
                or changed
            ):
                raise ValueError(f"{label} opaque mutation differs")
            boundary_index += 1
        else:
            raise ValueError(f"{label} kind differs")
        value = step.get("transitionIndex")
        if changed:
            if value != transition_index or transition_index >= len(raw_transitions):
                raise ValueError(f"{label} transition reference differs")
            transition = mapping(
                raw_transitions[transition_index],
                f"aggregate transition {transition_index}",
            )
            callback = _require_callback(
                order,
                transition.get("callbackSequence"),
                "aggregate-instruction-transition",
                f"transition {transition_index}",
            )
            if (
                transition.get("transitionIndex") != transition_index
                or transition.get("stepIndex") != index
                or transition.get("kind") != kind
                or transition.get("aggregateBeforeHex") != before.hex()
                or transition.get("aggregateAfterHex") != after.hex()
                or transition.get("changedLaneOffsets") != expected_lanes
                or transition.get("instruction") != step.get("instruction")
                or transition.get("opaqueBoundary") != step.get("opaqueBoundary")
                or callback <= 0
                or instruction is None
                or not (instruction["potentialWriter"] or instruction["potentialCall"])
            ):
                raise ValueError(f"aggregate transition {transition_index} differs")
            _context(
                transition.get("beforeContext"),
                f"transition {transition_index} before context",
                identity,
                addresses,
                before,
            )
            _after_context(
                transition.get("afterContext"),
                f"transition {transition_index} after context",
                identity,
                after,
            )
            transitions.append(dict(transition))
            transition_index += 1
        elif value is not None:
            raise ValueError(f"{label} unexpected transition differs")
        previous = after
        states.append(after)
    if transition_index != len(raw_transitions) or boundary_index != len(
        raw_boundaries
    ):
        raise ValueError("transition or boundary accounting differs")
    if len(raw_boundaries) > MAXIMUM_OPAQUE_CALLEE_COUNT:
        raise ValueError("opaque boundary bound differs")
    return states, transitions


def _semantic_registers(value: Any, label: str) -> dict[str, int]:
    snapshot = mapping(value, label)
    if set(snapshot) != {"general", "simd"}:
        raise ValueError(f"{label} fields differ")
    general_values = list(sequence(snapshot.get("general"), f"{label} general"))
    simd_values = list(sequence(snapshot.get("simd"), f"{label} SIMD"))
    if len(general_values) != len(full_base.GENERAL_REGISTER_NAMES) or len(
        simd_values
    ) != len(full_base.SIMD_REGISTER_NAMES):
        raise ValueError(f"{label} inventory differs")
    general = {}
    for name, raw in zip(full_base.GENERAL_REGISTER_NAMES, general_values, strict=True):
        byte_count = 4 if name == "cpsr" else 8
        record = writer_base.register_record(raw, name, byte_count, f"{label} {name}")
        general[name] = integer(record.get("unsignedValue"), f"{label} {name} value")
    for name, raw in zip(full_base.SIMD_REGISTER_NAMES, simd_values, strict=True):
        byte_count = 4 if name in {"fpsr", "fpcr"} else 16
        writer_base.register_record(raw, name, byte_count, f"{label} {name}")
    return general


def _semantic_dod_trace(
    trace: Mapping[str, Any],
    scopes: Mapping[str, Mapping[str, Any]],
    identity: Mapping[str, int],
) -> dict[str, Any]:
    target = identity["roleBase"] + full_base.AGGREGATE_OFFSET
    raw_steps = list(sequence(trace.get("instructionSteps"), "instruction steps"))
    dod_entry_steps = []
    for index, raw in enumerate(raw_steps):
        step = mapping(raw, f"instruction step {index}")
        instruction_value = step.get("instruction")
        if not isinstance(instruction_value, Mapping):
            continue
        if (
            instruction_value.get("scopeName") == SEMANTIC_DOD_SCOPE_NAME
            and instruction_value.get("scopeOffset") == SEMANTIC_DOD_ENTRY_OFFSET
        ):
            dod_entry_steps.append(index)

    raw_entries = list(sequence(trace.get("semanticDODEntries"), "semantic entries"))
    if (
        not raw_entries
        or len(raw_entries) > MAXIMUM_SEMANTIC_DOD_ENTRY_COUNT
        or len(raw_entries) != len(dod_entry_steps)
    ):
        raise ValueError("semantic DOD entry inventory differs")
    entries = []
    selected_entry = None
    expected_entry_fields = {
        "entryIndex",
        "stepIndex",
        "pc",
        "argumentX3",
        "x3Register",
        "targetAggregateAddress",
        "argumentMatchesTarget",
    }
    for index, (raw, step_index) in enumerate(
        zip(raw_entries, dod_entry_steps, strict=True)
    ):
        label = f"semantic DOD entry {index}"
        entry = mapping(raw, label)
        step = mapping(raw_steps[step_index], f"{label} step")
        instruction = _instruction(step.get("instruction"), label, scopes)
        x3_record = writer_base.register_record(
            entry.get("x3Register"), "x3", 8, f"{label} x3"
        )
        x3 = integer(x3_record.get("unsignedValue"), f"{label} x3 value")
        matched = x3 == target
        if (
            set(entry) != expected_entry_fields
            or entry.get("entryIndex") != index
            or entry.get("stepIndex") != step_index
            or entry.get("pc") != instruction["pc"]
            or entry.get("argumentX3") != x3
            or entry.get("targetAggregateAddress") != target
            or entry.get("argumentMatchesTarget") is not matched
        ):
            raise ValueError(f"{label} differs")
        entries.append(dict(entry))
        if matched:
            if selected_entry is not None:
                raise ValueError("semantic DOD target entry is not unique")
            selected_entry = dict(entry)
    if selected_entry is None:
        raise ValueError("semantic DOD target entry is absent")

    invocation = mapping(trace.get("semanticDODInvocation"), "semantic invocation")
    expected_invocation_fields = {
        "entryRecordIndex",
        "entryStepIndex",
        "entryPC",
        "entryArgumentX3",
        "targetAggregateAddress",
        "aggregateAtEntryHex",
        "returnStepIndex",
        "returnInstructionStateIndex",
        "returnPC",
        "returnFunction",
        "aggregateAtReturnHex",
        "instructionStateCount",
        "instructionStatesSHA256",
        "returnRegisters",
        "returnStack",
    }
    if set(invocation) != expected_invocation_fields:
        raise ValueError("semantic invocation fields differ")
    entry_step_index = integer(invocation.get("entryStepIndex"), "semantic entry step")
    if (
        invocation.get("entryRecordIndex") != selected_entry["entryIndex"]
        or entry_step_index != selected_entry["stepIndex"]
        or invocation.get("entryPC") != selected_entry["pc"]
        or invocation.get("entryArgumentX3") != target
        or invocation.get("targetAggregateAddress") != target
    ):
        raise ValueError("semantic invocation entry differs")

    expected_step_indices = []
    terminal_step_index = None
    for step_index in range(entry_step_index, len(raw_steps)):
        step = mapping(raw_steps[step_index], f"semantic span step {step_index}")
        raw_instruction = step.get("instruction")
        if not isinstance(raw_instruction, Mapping):
            continue
        if raw_instruction.get("scopeName") != SEMANTIC_DOD_SCOPE_NAME:
            continue
        instruction = _instruction(
            raw_instruction, f"semantic span instruction {step_index}", scopes
        )
        expected_step_indices.append(step_index)
        if instruction["scopeOffset"] == SEMANTIC_DOD_RETURN_OFFSET:
            if (
                instruction["rawLittleEndianHex"]
                != SEMANTIC_DOD_RETURN_RAW_LITTLE_ENDIAN_HEX
                or instruction["mnemonic"].lower() != "retab"
            ):
                raise ValueError("semantic DOD return instruction differs")
            terminal_step_index = step_index
            break
    if terminal_step_index is None:
        raise ValueError("semantic DOD terminal instruction is absent")

    raw_states = list(
        sequence(
            trace.get("semanticDODInstructionStates"),
            "semantic instruction states",
        )
    )
    if len(raw_states) != len(expected_step_indices):
        raise ValueError("semantic instruction state inventory differs")
    expected_state_fields = {
        "stateIndex",
        "stepIndex",
        "instruction",
        "aggregateBeforeHex",
        "registers",
        "stack",
    }
    first_general = None
    for state_index, (raw, step_index) in enumerate(
        zip(raw_states, expected_step_indices, strict=True)
    ):
        label = f"semantic instruction state {state_index}"
        state = mapping(raw, label)
        step = mapping(raw_steps[step_index], f"{label} step")
        instruction = _instruction(state.get("instruction"), label, scopes)
        general = _semantic_registers(state.get("registers"), f"{label} registers")
        _memory_payload(
            state.get("stack"),
            f"{label} stack",
            expected_address=general["sp"],
            expected_byte_count=SEMANTIC_STACK_BYTE_COUNT,
        )
        aggregate = _payload(
            state.get("aggregateBeforeHex"),
            full_base.AGGREGATE_BYTE_COUNT,
            f"{label} aggregate",
        )
        if (
            set(state) != expected_state_fields
            or state.get("stateIndex") != state_index
            or state.get("stepIndex") != step_index
            or state.get("instruction") != step.get("instruction")
            or aggregate.hex() != step.get("aggregateBeforeHex")
            or general["pc"] != instruction["pc"]
        ):
            raise ValueError(f"{label} differs")
        if state_index == 0:
            first_general = general
    if first_general is None or first_general["x3"] != target:
        raise ValueError("semantic invocation entry register differs")

    entry_step = mapping(raw_steps[entry_step_index], "semantic entry step")
    terminal_step = mapping(raw_steps[terminal_step_index], "semantic terminal step")
    entry_aggregate = _payload(
        invocation.get("aggregateAtEntryHex"),
        full_base.AGGREGATE_BYTE_COUNT,
        "semantic entry aggregate",
    )
    return_aggregate = _payload(
        invocation.get("aggregateAtReturnHex"),
        full_base.AGGREGATE_BYTE_COUNT,
        "semantic return aggregate",
    )
    return_general = _semantic_registers(
        invocation.get("returnRegisters"), "semantic return registers"
    )
    _memory_payload(
        invocation.get("returnStack"),
        "semantic return stack",
        expected_address=return_general["sp"],
        expected_byte_count=SEMANTIC_STACK_BYTE_COUNT,
    )
    state_digest = hashlib.sha256(
        json.dumps(
            raw_states,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    if (
        invocation.get("returnStepIndex") != terminal_step_index
        or invocation.get("returnInstructionStateIndex") != len(raw_states) - 1
        or invocation.get("returnPC") != terminal_step.get("resultPC")
        or invocation.get("returnFunction") != terminal_step.get("resultFunction")
        or not isinstance(invocation.get("returnFunction"), str)
        or not invocation["returnFunction"]
        or return_general["pc"] != invocation.get("returnPC")
        or entry_aggregate.hex() != entry_step.get("aggregateBeforeHex")
        or return_aggregate.hex() != terminal_step.get("aggregateAfterHex")
        or invocation.get("instructionStateCount") != len(raw_states)
        or invocation.get("instructionStatesSHA256") != state_digest
        or trace.get("semanticDODActive") is not False
        or trace.get("semanticDODFinished") is not True
        or trace.get("finalSemanticDODEntryCount") != len(entries)
        or trace.get("finalSemanticDODInstructionStateCount") != len(raw_states)
    ):
        raise ValueError("semantic DOD closure differs")
    return {
        "targetAggregateAddress": target,
        "entryRecordIndex": selected_entry["entryIndex"],
        "entryStepIndex": entry_step_index,
        "returnStepIndex": terminal_step_index,
        "instructionStateCount": len(raw_states),
        "instructionStatesSHA256": state_digest,
    }


def _semantic_simd_payload(value: Any, name: str, label: str) -> bytes:
    snapshot = mapping(value, label)
    values = list(sequence(snapshot.get("simd"), f"{label} SIMD"))
    try:
        index = full_base.SIMD_REGISTER_NAMES.index(name)
    except ValueError as error:
        raise ValueError(f"{label} SIMD register name differs") from error
    if len(values) != len(full_base.SIMD_REGISTER_NAMES):
        raise ValueError(f"{label} SIMD inventory differs")
    byte_count = 4 if name in {"fpsr", "fpcr"} else 16
    record = writer_base.register_record(
        values[index], name, byte_count, f"{label} {name}"
    )
    return _payload(record.get("hex"), byte_count, f"{label} {name}")


def _crop_argument_memory(value: Any, addresses: Mapping[str, int], label: str) -> None:
    values = list(sequence(value, label))
    names = ("x0", "x1", "x2", "x3", "x4", "x5")
    if len(values) != len(names):
        raise ValueError(f"{label} inventory differs")
    for index, (raw, name) in enumerate(zip(values, names, strict=True)):
        item = mapping(raw, f"{label} {index}")
        if set(item) != {"registerName", "memory"} or item.get("registerName") != name:
            raise ValueError(f"{label} {index} identity differs")
        _memory_payload(
            item.get("memory"),
            f"{label} {name}",
            expected_address=addresses[name],
            expected_byte_count=SEMANTIC_CROP_ARGUMENT_MEMORY_BYTE_COUNT,
        )


def _semantic_crop_trace(
    trace: Mapping[str, Any],
    scopes: Mapping[str, Mapping[str, Any]],
    identity: Mapping[str, int],
) -> dict[str, Any]:
    raw_steps = list(sequence(trace.get("instructionSteps"), "instruction steps"))
    entry_steps = [
        index
        for index, raw in enumerate(raw_steps)
        if isinstance(raw, Mapping)
        and isinstance(raw.get("instruction"), Mapping)
        and raw["instruction"].get("scopeName") == SEMANTIC_CROP_SCOPE_NAME
        and raw["instruction"].get("scopeOffset") == 0
    ]
    raw_invocations = list(
        sequence(trace.get("semanticCropInvocations"), "semantic crop invocations")
    )
    if (
        len(raw_invocations) != SEMANTIC_CROP_EXPECTED_INVOCATION_COUNT
        or len(raw_invocations) > SEMANTIC_CROP_MAXIMUM_INVOCATION_COUNT
        or len(entry_steps) != len(raw_invocations)
    ):
        raise ValueError("semantic crop invocation inventory differs")
    raw_states = list(
        sequence(
            trace.get("semanticCropInstructionStates"),
            "semantic crop instruction states",
        )
    )
    expected_invocation_fields = {
        "invocationIndex",
        "entryStepIndex",
        "entryPC",
        "entryArgumentRegisters",
        "entryArgumentAddresses",
        "entryArgumentMemory",
        "callerRoleBase",
        "callerRoleAtEntry",
        "targetAddress",
        "targetAtEntry",
        "aggregateAtEntryHex",
        "instructionStateStartIndex",
        "storeLinkIndex",
        "returnStepIndex",
        "returnInstructionStateIndex",
        "returnInstructionScopeOffset",
        "returnInstructionRawLittleEndianHex",
        "returnInstructionMnemonic",
        "returnPC",
        "returnFunction",
        "returnArgumentMemory",
        "callerRoleAtReturn",
        "targetAtReturn",
        "aggregateAtReturnHex",
        "instructionStateCount",
        "instructionStatesSHA256",
        "returnRegisters",
        "returnStack",
    }
    expected_state_fields = {
        "stateIndex",
        "invocationIndex",
        "invocationStateIndex",
        "stepIndex",
        "instruction",
        "aggregateBeforeHex",
        "registers",
        "stack",
        "target",
    }
    state_cursor = 0
    previous_return_step = -1
    invocations = []
    for invocation_index, (raw, entry_step_index) in enumerate(
        zip(raw_invocations, entry_steps, strict=True)
    ):
        label = f"semantic crop invocation {invocation_index}"
        invocation = mapping(raw, label)
        if set(invocation) != expected_invocation_fields:
            raise ValueError(f"{label} fields differ")
        entry_step = mapping(raw_steps[entry_step_index], f"{label} entry step")
        entry_instruction = _instruction(
            entry_step.get("instruction"), f"{label} entry instruction", scopes
        )
        return_step_index = integer(
            invocation.get("returnStepIndex"), f"{label} return step"
        )
        if not entry_step_index <= return_step_index < len(raw_steps):
            raise ValueError(f"{label} span differs")
        return_step = mapping(raw_steps[return_step_index], f"{label} return step")
        return_instruction = _instruction(
            return_step.get("instruction"), f"{label} return instruction", scopes
        )
        expected_step_indices = [
            index
            for index in range(entry_step_index, return_step_index + 1)
            if mapping(raw_steps[index], f"{label} span step {index}").get("kind")
            == "scope-instruction"
        ]
        count = integer(invocation.get("instructionStateCount"), f"{label} state count")
        start = integer(
            invocation.get("instructionStateStartIndex"), f"{label} state start"
        )
        end = start + count
        if (
            invocation.get("invocationIndex") != invocation_index
            or invocation.get("entryStepIndex") != entry_step_index
            or invocation.get("entryPC") != entry_instruction["pc"]
            or entry_step_index <= previous_return_step
            or (
                invocation_index + 1 < len(entry_steps)
                and return_step_index >= entry_steps[invocation_index + 1]
            )
            or start != state_cursor
            or count != len(expected_step_indices)
            or end > len(raw_states)
            or return_instruction["scopeName"] != SEMANTIC_CROP_SCOPE_NAME
            or return_instruction["mnemonic"].lower() not in CROP_RETURN_MNEMONICS
            or return_instruction["rawLittleEndianHex"]
            not in CROP_RETURN_RAW_LITTLE_ENDIAN_HEX
            or invocation.get("returnInstructionStateIndex") != end - 1
            or invocation.get("returnInstructionScopeOffset")
            != return_instruction["scopeOffset"]
            or invocation.get("returnInstructionRawLittleEndianHex")
            != return_instruction["rawLittleEndianHex"]
            or invocation.get("returnInstructionMnemonic")
            != return_instruction["mnemonic"].lower()
        ):
            raise ValueError(f"{label} identity differs")

        raw_addresses = mapping(
            invocation.get("entryArgumentAddresses"), f"{label} arguments"
        )
        argument_names = ("x0", "x1", "x2", "x3", "x4", "x5")
        if set(raw_addresses) != set(argument_names):
            raise ValueError(f"{label} argument fields differ")
        addresses = {
            name: integer(raw_addresses.get(name), f"{label} {name}")
            for name in argument_names
        }
        argument_records = list(
            sequence(
                invocation.get("entryArgumentRegisters"),
                f"{label} argument registers",
            )
        )
        if len(argument_records) != len(argument_names):
            raise ValueError(f"{label} argument register inventory differs")
        for raw_record, name in zip(argument_records, argument_names, strict=True):
            record = writer_base.register_record(
                raw_record, name, 8, f"{label} {name} register"
            )
            if record.get("unsignedValue") != addresses[name]:
                raise ValueError(f"{label} {name} register differs")
        caller_role = integer(invocation.get("callerRoleBase"), f"{label} caller")
        target = integer(invocation.get("targetAddress"), f"{label} target")
        if target != caller_role + SEMANTIC_CROP_CALLER_ROLE_OFFSET:
            raise ValueError(f"{label} target relation differs")
        _crop_argument_memory(
            invocation.get("entryArgumentMemory"), addresses, f"{label} entry memory"
        )
        _crop_argument_memory(
            invocation.get("returnArgumentMemory"),
            addresses,
            f"{label} return memory",
        )
        _memory_payload(
            invocation.get("callerRoleAtEntry"),
            f"{label} caller role at entry",
            expected_address=caller_role,
            expected_byte_count=SEMANTIC_CROP_CALLER_ROLE_BYTE_COUNT,
        )
        _memory_payload(
            invocation.get("callerRoleAtReturn"),
            f"{label} caller role at return",
            expected_address=caller_role,
            expected_byte_count=SEMANTIC_CROP_CALLER_ROLE_BYTE_COUNT,
        )
        target_at_entry = _memory_payload(
            invocation.get("targetAtEntry"),
            f"{label} target at entry",
            expected_address=target,
            expected_byte_count=SEMANTIC_CROP_TARGET_BYTE_COUNT,
        )
        target_at_return = _memory_payload(
            invocation.get("targetAtReturn"),
            f"{label} target at return",
            expected_address=target,
            expected_byte_count=SEMANTIC_CROP_TARGET_BYTE_COUNT,
        )

        invocation_states = raw_states[start:end]
        for local_index, (raw_state, step_index) in enumerate(
            zip(invocation_states, expected_step_indices, strict=True)
        ):
            state_index = start + local_index
            state_label = f"{label} state {local_index}"
            state = mapping(raw_state, state_label)
            step = mapping(raw_steps[step_index], f"{state_label} step")
            instruction = _instruction(
                state.get("instruction"), f"{state_label} instruction", scopes
            )
            general = _semantic_registers(
                state.get("registers"), f"{state_label} registers"
            )
            _memory_payload(
                state.get("stack"),
                f"{state_label} stack",
                expected_address=general["sp"],
                expected_byte_count=SEMANTIC_STACK_BYTE_COUNT,
            )
            state_target = _memory_payload(
                state.get("target"),
                f"{state_label} target",
                expected_address=target,
                expected_byte_count=SEMANTIC_CROP_TARGET_BYTE_COUNT,
            )
            aggregate = _payload(
                state.get("aggregateBeforeHex"),
                full_base.AGGREGATE_BYTE_COUNT,
                f"{state_label} aggregate",
            )
            if (
                set(state) != expected_state_fields
                or state.get("stateIndex") != state_index
                or state.get("invocationIndex") != invocation_index
                or state.get("invocationStateIndex") != local_index
                or state.get("stepIndex") != step_index
                or state.get("instruction") != step.get("instruction")
                or aggregate.hex() != step.get("aggregateBeforeHex")
                or general["pc"] != instruction["pc"]
                or (local_index == 0 and state_target != target_at_entry)
            ):
                raise ValueError(f"{state_label} differs")
            if local_index == 0 and any(
                general[name] != addresses[name] for name in argument_names
            ):
                raise ValueError(f"{label} entry arguments differ")
        if not invocation_states:
            raise ValueError(f"{label} states are absent")
        terminal_target = _memory_payload(
            mapping(invocation_states[-1], f"{label} terminal state").get("target"),
            f"{label} terminal target",
            expected_address=target,
            expected_byte_count=SEMANTIC_CROP_TARGET_BYTE_COUNT,
        )
        return_general = _semantic_registers(
            invocation.get("returnRegisters"), f"{label} return registers"
        )
        _memory_payload(
            invocation.get("returnStack"),
            f"{label} return stack",
            expected_address=return_general["sp"],
            expected_byte_count=SEMANTIC_STACK_BYTE_COUNT,
        )
        entry_aggregate = _payload(
            invocation.get("aggregateAtEntryHex"),
            full_base.AGGREGATE_BYTE_COUNT,
            f"{label} entry aggregate",
        )
        return_aggregate = _payload(
            invocation.get("aggregateAtReturnHex"),
            full_base.AGGREGATE_BYTE_COUNT,
            f"{label} return aggregate",
        )
        digest = hashlib.sha256(
            json.dumps(
                invocation_states,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        expected_store = invocation_index if invocation_index < 3 else None
        if (
            invocation.get("storeLinkIndex") != expected_store
            or invocation.get("returnPC") != return_step.get("resultPC")
            or invocation.get("returnFunction") != return_step.get("resultFunction")
            or not isinstance(invocation.get("returnFunction"), str)
            or not invocation["returnFunction"]
            or return_general["pc"] != invocation.get("returnPC")
            or entry_aggregate.hex() != entry_step.get("aggregateBeforeHex")
            or return_aggregate.hex() != return_step.get("aggregateAfterHex")
            or target_at_return != terminal_target
            or invocation.get("instructionStatesSHA256") != digest
        ):
            raise ValueError(f"{label} closure differs")
        invocations.append(
            {
                "invocationIndex": invocation_index,
                "entryStepIndex": entry_step_index,
                "returnStepIndex": return_step_index,
                "callerRoleBase": caller_role,
                "targetAddress": target,
                "instructionStateCount": count,
                "instructionStatesSHA256": digest,
                "targetAtEntryHex": target_at_entry.hex(),
                "targetAtReturnHex": target_at_return.hex(),
                "storeLinkIndex": expected_store,
            }
        )
        state_cursor = end
        previous_return_step = return_step_index
    if state_cursor != len(raw_states):
        raise ValueError("semantic crop state accounting differs")
    if (
        invocations[-1]["callerRoleBase"] != identity["roleBase"]
        or invocations[-1]["targetAddress"]
        != identity["roleBase"] + full_base.AGGREGATE_OFFSET
    ):
        raise ValueError("semantic crop selected aggregate link differs")

    raw_stores = list(
        sequence(trace.get("semanticCropStoreLinks"), "semantic crop store links")
    )
    store_step_indices = [
        index
        for index, raw in enumerate(raw_steps)
        if isinstance(raw, Mapping)
        and isinstance(raw.get("instruction"), Mapping)
        and raw["instruction"].get("scopeName") == "prepareLayer"
        and raw["instruction"].get("scopeOffset") == CROP_STORE_RELATIVE_OFFSET
    ]
    if len(raw_stores) != 3 or len(store_step_indices) != 3:
        raise ValueError("semantic crop store inventory differs")
    stores = []
    expected_store_fields = {
        "storeLinkIndex",
        "sourceInvocationIndex",
        "stepIndex",
        "instruction",
        "registers",
        "callerRoleBase",
        "sourceIntegerAddress",
        "sourceInteger",
        "destinationAddress",
        "destinationBefore",
        "destinationAfter",
        "returnPC",
        "unionInputIndex",
    }
    for index, (raw, step_index) in enumerate(
        zip(raw_stores, store_step_indices, strict=True)
    ):
        label = f"semantic crop store {index}"
        store = mapping(raw, label)
        step = mapping(raw_steps[step_index], f"{label} step")
        instruction = _instruction(store.get("instruction"), label, scopes)
        general = _semantic_registers(store.get("registers"), f"{label} registers")
        q0 = _semantic_simd_payload(store.get("registers"), "v0", label)
        caller_role = general["x19"]
        destination = general["x28"] + CROP_DESTINATION_OFFSET
        source = _memory_payload(
            store.get("sourceInteger"),
            f"{label} source",
            expected_address=caller_role + CROP_INTEGER_SOURCE_OFFSET,
            expected_byte_count=CROP_INTEGER_BYTE_COUNT,
        )
        _memory_payload(
            store.get("destinationBefore"),
            f"{label} destination before",
            expected_address=destination,
            expected_byte_count=CROP_INTEGER_BYTE_COUNT,
        )
        after = _memory_payload(
            store.get("destinationAfter"),
            f"{label} destination after",
            expected_address=destination,
            expected_byte_count=CROP_INTEGER_BYTE_COUNT,
        )
        if (
            set(store) != expected_store_fields
            or store.get("storeLinkIndex") != index
            or store.get("sourceInvocationIndex") != index
            or store.get("stepIndex") != step_index
            or store.get("instruction") != step.get("instruction")
            or instruction["rawLittleEndianHex"] != CROP_STORE_RAW_LITTLE_ENDIAN_HEX
            or instruction["mnemonic"].lower() != "str"
            or store.get("callerRoleBase") != caller_role
            or store.get("sourceIntegerAddress")
            != caller_role + CROP_INTEGER_SOURCE_OFFSET
            or caller_role != invocations[index]["callerRoleBase"]
            or step_index <= invocations[index]["returnStepIndex"]
            or store.get("destinationAddress") != destination
            or source != q0
            or after != source
            or store.get("returnPC") != step.get("resultPC")
            or store.get("unionInputIndex") != index
        ):
            raise ValueError(f"{label} differs")
        stores.append(
            {
                "storeLinkIndex": index,
                "sourceInvocationIndex": index,
                "stepIndex": step_index,
                "destinationAddress": destination,
                "cropI32": list(struct.unpack("<4i", after)),
            }
        )

    raw_unions = list(
        sequence(trace.get("semanticCropUnionInputs"), "semantic crop union inputs")
    )
    union_step_indices = [
        index
        for index, raw in enumerate(raw_steps)
        if isinstance(raw, Mapping)
        and isinstance(raw.get("instruction"), Mapping)
        and raw["instruction"].get("scopeName") == "prepareLayer"
        and raw["instruction"].get("scopeOffset") == CROP_UNION_INPUT_RELATIVE_OFFSET
    ]
    if len(raw_unions) != 3 or len(union_step_indices) != 3:
        raise ValueError("semantic crop union inventory differs")
    unions = []
    expected_union_fields = {
        "unionInputIndex",
        "sourceStoreLinkIndex",
        "stepIndex",
        "instruction",
        "registers",
        "layerShapesBase",
        "stateAddress",
        "state",
    }
    crop_offset = CROP_DESTINATION_OFFSET - CROP_UNION_STATE_OFFSET
    for index, (raw, step_index) in enumerate(
        zip(raw_unions, union_step_indices, strict=True)
    ):
        label = f"semantic crop union input {index}"
        union = mapping(raw, label)
        step = mapping(raw_steps[step_index], f"{label} step")
        instruction = _instruction(union.get("instruction"), label, scopes)
        general = _semantic_registers(union.get("registers"), f"{label} registers")
        base = general["x28"]
        state = _memory_payload(
            union.get("state"),
            f"{label} state",
            expected_address=base + CROP_UNION_STATE_OFFSET,
            expected_byte_count=CROP_UNION_STATE_BYTE_COUNT,
        )
        crop = state[crop_offset : crop_offset + CROP_INTEGER_BYTE_COUNT]
        if (
            set(union) != expected_union_fields
            or union.get("unionInputIndex") != index
            or union.get("sourceStoreLinkIndex") != index
            or union.get("stepIndex") != step_index
            or union.get("instruction") != step.get("instruction")
            or instruction["rawLittleEndianHex"]
            != CROP_UNION_INPUT_RAW_LITTLE_ENDIAN_HEX
            or instruction["mnemonic"].lower() != "ldp"
            or union.get("layerShapesBase") != base
            or union.get("stateAddress") != base + CROP_UNION_STATE_OFFSET
            or base + CROP_DESTINATION_OFFSET != stores[index]["destinationAddress"]
            or crop != struct.pack("<4i", *stores[index]["cropI32"])
            or step_index <= stores[index]["stepIndex"]
        ):
            raise ValueError(f"{label} differs")
        unions.append(
            {
                "unionInputIndex": index,
                "sourceStoreLinkIndex": index,
                "stepIndex": step_index,
                "cropI32": list(struct.unpack("<4i", crop)),
            }
        )

    raw_boundaries = list(
        sequence(trace.get("opaqueCalleeBoundaries"), "opaque boundaries")
    )
    boundary_step_indices = {}
    for step_index, raw_step in enumerate(raw_steps):
        step = mapping(raw_step, f"instruction step {step_index}")
        if step.get("kind") != "opaque-callee-step-out":
            continue
        boundary = mapping(step.get("opaqueBoundary"), f"step {step_index} boundary")
        boundary_index = integer(
            boundary.get("boundaryIndex"), f"step {step_index} boundary index"
        )
        if boundary_index in boundary_step_indices:
            raise ValueError("semantic crop opaque boundary step identity differs")
        boundary_step_indices[boundary_index] = step_index
    if set(boundary_step_indices) != set(range(len(raw_boundaries))):
        raise ValueError("semantic crop opaque boundary step inventory differs")
    crop_opaque_boundaries = []
    for boundary_index, raw in enumerate(raw_boundaries):
        boundary = mapping(raw, f"opaque boundary {boundary_index}")
        invocation_index = boundary.get("semanticCropInvocationIndex")
        crop_fields = {
            "semanticCropInvocationIndex",
            "semanticCropTargetBefore",
            "semanticCropTargetAfter",
            "semanticCropTargetChanged",
        }
        present = crop_fields.intersection(boundary)
        step_index = boundary_step_indices[boundary_index]
        expected_invocation = next(
            (
                item["invocationIndex"]
                for item in invocations
                if item["entryStepIndex"] < step_index < item["returnStepIndex"]
            ),
            None,
        )
        if expected_invocation is None:
            if present:
                raise ValueError(f"opaque boundary {boundary_index} crop fields differ")
            continue
        if (
            present != crop_fields
            or invocation_index != expected_invocation
            or not 0 <= invocation_index < len(invocations)
        ):
            raise ValueError(f"opaque boundary {boundary_index} crop link differs")
        target = invocations[invocation_index]["targetAddress"]
        before = _memory_payload(
            boundary.get("semanticCropTargetBefore"),
            f"opaque boundary {boundary_index} crop before",
            expected_address=target,
            expected_byte_count=SEMANTIC_CROP_TARGET_BYTE_COUNT,
        )
        after = _memory_payload(
            boundary.get("semanticCropTargetAfter"),
            f"opaque boundary {boundary_index} crop after",
            expected_address=target,
            expected_byte_count=SEMANTIC_CROP_TARGET_BYTE_COUNT,
        )
        changed = before != after
        if boundary.get("semanticCropTargetChanged") is not changed:
            raise ValueError(f"opaque boundary {boundary_index} crop mutation differs")
        crop_opaque_boundaries.append(
            {
                "boundaryIndex": boundary_index,
                "invocationIndex": invocation_index,
                "targetChanged": changed,
            }
        )

    if (
        trace.get("semanticCropActiveInvocationIndex") is not None
        or trace.get("semanticCropCompletedInvocationCount")
        != SEMANTIC_CROP_EXPECTED_INVOCATION_COUNT
        or trace.get("finalSemanticCropInvocationCount") != len(invocations)
        or trace.get("finalSemanticCropInstructionStateCount") != len(raw_states)
        or trace.get("finalSemanticCropStoreLinkCount") != len(stores)
        or trace.get("finalSemanticCropUnionInputCount") != len(unions)
    ):
        raise ValueError("semantic crop closure differs")
    return {
        "invocationCount": len(invocations),
        "instructionStateCount": len(raw_states),
        "invocations": invocations,
        "storeLinks": stores,
        "unionInputs": unions,
        "opaqueBoundaryCount": len(crop_opaque_boundaries),
        "changedOpaqueTargetBoundaryCount": sum(
            item["targetChanged"] for item in crop_opaque_boundaries
        ),
    }


def _manual_selection_markers(
    trace: Mapping[str, Any],
    order: Mapping[int, str],
    prepare_start: int,
    identity: Mapping[str, int],
    selected_source: int,
) -> tuple[int, int]:
    values = list(
        sequence(trace.get("manualSelectionMarkers"), "manual selection markers")
    )
    if not values or len(values) > MAXIMUM_REJECTED_MARKER_DIAGNOSTIC_COUNT:
        raise ValueError("manual selection marker inventory differs")
    previous_hit = 0
    selected_index = -1
    selected_callback = -1
    for index, raw in enumerate(values):
        label = f"manual selection marker {index}"
        item = mapping(raw, label)
        marker_identity = _identity(item.get("selectedIdentity"), f"{label} identity")
        marker_hit = integer(item.get("markerHitIndex"), f"{label} hit")
        thread_id = integer(item.get("threadID"), f"{label} thread")
        frame_pointer = integer(item.get("framePointer"), f"{label} frame pointer")
        role_base = integer(item.get("observedRoleBase"), f"{label} role")
        observed_x28 = integer(item.get("observedX28"), f"{label} x28")
        identity_matches = (
            thread_id == identity["threadID"]
            and frame_pointer == identity["framePointer"]
            and role_base == identity["roleBase"]
        )
        source_matches = observed_x28 == selected_source
        if (
            item.get("manualSelectionMarkerIndex") != index
            or marker_hit <= previous_hit
            or item.get("pc") != prepare_start + SELECTION_MARKER_OFFSET
            or marker_identity != identity
            or item.get("selectedSource") != selected_source
            or integer(item.get("prepareRecursionDepth"), f"{label} recursion depth")
            <= 0
            or item.get("frameIdentityMatches") is not identity_matches
            or item.get("sourceRegisterMatches") is not source_matches
        ):
            raise ValueError(f"{label} differs")
        result = item.get("result")
        if result == "selected":
            if (
                index != len(values) - 1
                or not identity_matches
                or not source_matches
                or item.get("prepareRecursionDepth") != TARGET_PREPARE_RECURSION_DEPTH
            ):
                raise ValueError(f"{label} selected identity differs")
            selected_callback = _require_callback(
                order,
                item.get("callbackSequence"),
                "selected-instruction-path-closed",
                label,
            )
            selected_index = index
        elif result == "rejected":
            if identity_matches and source_matches:
                raise ValueError(f"{label} rejection differs")
            if item.get("callbackSequence") is not None:
                raise ValueError(f"{label} rejected callback differs")
        else:
            raise ValueError(f"{label} result differs")
        previous_hit = marker_hit
    if selected_index < 0:
        raise ValueError("manual selected marker is absent")
    return selected_index, selected_callback


def validate_documents(
    trace: Mapping[str, Any], inherited_trace: Mapping[str, Any]
) -> dict[str, Any]:
    schema_version = trace.get("prepareLayerInstructionTraceSchemaVersion")
    legacy = schema_version == LEGACY_TRACE_SCHEMA_VERSION
    expected_schema_version = (
        LEGACY_TRACE_SCHEMA_VERSION if legacy else EXPECTED_TRACE_SCHEMA_VERSION
    )
    expected_classification = (
        LEGACY_EXPECTED_CLASSIFICATION if legacy else EXPECTED_CLASSIFICATION
    )
    expected_configuration = (
        LEGACY_EXPECTED_CONFIGURATION if legacy else EXPECTED_CONFIGURATION
    )
    scope_specs = LEGACY_CHECKPOINT_SCOPE_SPECS if legacy else CHECKPOINT_SCOPE_SPECS
    if (
        schema_version != expected_schema_version
        or trace.get("classification") != expected_classification
        or trace.get("status") != "finalized"
        or trace.get("statusBeforeFinalization")
        != "selected-software-instruction-path-closed"
        or mapping(trace.get("configuration"), "configuration")
        != expected_configuration
        or list(sequence(trace.get("failures"), "failures"))
        or trace.get("finalFailureCount") != 0
    ):
        raise ValueError("instruction trace envelope differs")
    inherited = active_validator._inherited_frame_context(inherited_trace)
    order = _callback_order(trace)
    prepare_start, _module_value, scopes, _prepare_code = _static_trace(
        trace, order, inherited, scope_specs
    )
    selected_source = integer(inherited.get("selectedSource"), "selected source")
    prepare = mapping(trace.get("prepareLayer"), "prepare layer")
    required_ids = _retirement(trace, order, prepare, selected_source)
    identity, zero, epoch_index = _epoch_records(
        trace, order, prepare_start, selected_source
    )
    disable_callback = _breakpoint_disablement(trace, order, required_ids)
    manual = mapping(trace.get("manualTraceStart"), "manual trace start")
    start_callback = _require_callback(
        order,
        manual.get("callbackSequence"),
        "selected-instruction-stepping-started",
        "manual trace start",
    )
    if (
        start_callback <= disable_callback
        or manual.get("epochRecordIndex") != epoch_index
        or _identity(manual.get("identity"), "manual identity") != identity
        or manual.get("selectedSource") != selected_source
        or manual.get("debuggerAsyncAfterSynchronousSet") is not False
    ):
        raise ValueError("manual trace start differs")
    object_chain = mapping(inherited.get("objectChain"), "inherited object chain")
    addresses = mapping(object_chain.get("addresses"), "object addresses")
    states, transitions = _steps_and_transitions(
        trace, order, scopes, identity, zero, addresses
    )
    known = _known_state_sequence(states)
    semantic_dod = _semantic_dod_trace(trace, scopes, identity)
    semantic_crop = None if legacy else _semantic_crop_trace(trace, scopes, identity)
    manual_marker_index, manual_selected_callback = _manual_selection_markers(
        trace, order, prepare_start, identity, selected_source
    )

    selected = mapping(trace.get("selectedFrame"), "selected frame")
    selected_callback = _require_callback(
        order,
        selected.get("callbackSequence"),
        "selected-instruction-path-closed",
        "selected frame",
    )
    marker_pc = prepare_start + SELECTION_MARKER_OFFSET
    marker_aggregate = _role_aggregate(
        selected.get("roleStateAtMarker"), "selected marker role", identity
    )
    if (
        selected_callback != manual_selected_callback
        or selected_callback <= start_callback
        or selected_callback != len(order)
        or selected.get("pc") != marker_pc
        or selected.get("markerHitIndex") != trace.get("selectionMarkerHitCount")
        or selected.get("manualSelectionMarkerIndex") != manual_marker_index
        or selected.get("prepareRecursionDepth") != TARGET_PREPARE_RECURSION_DEPTH
        or _identity(selected.get("frameIdentity"), "selected identity") != identity
        or selected.get("selectedSource") != selected_source
        or selected.get("selectedEpochRecordIndex") != epoch_index
        or selected.get("instructionStepCount") != len(states) - 1
        or selected.get("aggregateTransitionCount") != len(transitions)
        or _payload(
            selected.get("aggregateAtMarkerHex"),
            full_base.AGGREGATE_BYTE_COUNT,
            "selected marker aggregate",
        )
        != marker_aggregate
        or marker_aggregate != states[-1]
        or selected.get("objectChain") != object_chain
        or marker_aggregate != inherited.get("markerAggregate")
    ):
        raise ValueError("selected marker closure differs")
    registers = frame_validator._registers(
        selected.get("registers"),
        SELECTION_FRAME_REGISTER_NAMES,
        "selected registers",
    )
    if (
        registers["x19"] != identity["roleBase"]
        or registers["x28"] != selected_source
        or registers["x29"] != identity["framePointer"]
        or registers["pc"] != marker_pc
    ):
        raise ValueError("selected marker registers differ")
    prepare_frames = list(
        sequence(selected.get("prepareFrames"), "selected prepare frames")
    )
    if (
        len(prepare_frames) != TARGET_PREPARE_RECURSION_DEPTH
        or mapping(prepare_frames[0], "selected top prepare").get("unwindFramePointer")
        != identity["framePointer"]
    ):
        raise ValueError("selected structural frames differ")

    terminal = mapping(trace.get("terminalProcess"), "terminal process")
    if (
        terminal.get("exited") is not True
        or terminal.get("detached") is not False
        or terminal.get("exitStatus") != 0
        or list(sequence(terminal.get("unexpectedStops"), "unexpected stops"))
    ):
        raise ValueError("terminal process differs")
    diagnostics = list(
        sequence(trace.get("rejectedMarkerDiagnostics"), "marker diagnostics")
    )
    if (
        len(diagnostics) > MAXIMUM_REJECTED_MARKER_DIAGNOSTIC_COUNT
        or trace.get("unretainedRejectedMarkerDiagnosticCount") != 0
        or trace.get("finalRejectedMarkerDiagnosticCount") != len(diagnostics)
        or trace.get("manualTraceStarted") is not True
        or trace.get("manualTraceFinished") is not True
        or trace.get("finalInstructionStepCount") != len(states) - 1
        or trace.get("finalAggregateTransitionCount") != len(transitions)
        or trace.get("finalOpaqueCalleeBoundaryCount")
        != len(trace.get("opaqueCalleeBoundaries", []))
        or trace.get("finalManualSelectionMarkerRecordCount")
        != len(trace.get("manualSelectionMarkers", []))
        or trace.get("finalChangedOpaqueCalleeBoundaryCount") != 0
        or trace.get("finalDistinctAggregateStateCount") != len(set(states))
        or len(transitions) < 3
        or len(set(states)) < 4
        or trace.get("selectionMarkerHitCount")
        != trace.get("rejectedSelectionMarkerHitCount", 0) + 1
    ):
        raise ValueError("final instruction accounting differs")

    result = {
        "prepareLayerInstructionTraceValidationSchemaVersion": (
            LEGACY_VALIDATION_SCHEMA_VERSION if legacy else VALIDATION_SCHEMA_VERSION
        ),
        "classification": (
            LEGACY_EXPECTED_VALIDATION_CLASSIFICATION
            if legacy
            else EXPECTED_VALIDATION_CLASSIFICATION
        ),
        "conclusion": "success",
        "prospectiveGatePassed": True,
        "selectedSource": selected_source,
        "selectedIdentity": identity,
        "selectedEpochOrdinal": epoch_index + 1,
        "selectedEpochRecordIndex": epoch_index,
        "instructionStepCount": len(states) - 1,
        "aggregateTransitionCount": len(transitions),
        "distinctAggregateStateCount": len(set(states)),
        "opaqueCalleeBoundaryCount": len(
            sequence(trace.get("opaqueCalleeBoundaries"), "opaque boundaries")
        ),
        "knownStateTransfer": known,
        "semanticDODTrace": semantic_dod,
        "observedScopeSHA256": {
            name: scope["observedSHA256"] for name, scope in scopes.items()
        },
        "changedInstructionTransitions": [
            {
                "transitionIndex": item["transitionIndex"],
                "stepIndex": item["stepIndex"],
                "instruction": item["instruction"],
                "aggregateBeforeHex": item["aggregateBeforeHex"],
                "aggregateAfterHex": item["aggregateAfterHex"],
                "changedLaneOffsets": item["changedLaneOffsets"],
            }
            for item in transitions
        ],
        "sealedConclusion": {
            "inheritedStaticSourceMarkerContextPassed": True,
            "hardwareWatchpointsUsed": False,
            "allSoftwareBreakpointsDisabledDuringStepping": True,
            "prospectivelySelectedEpochReached": True,
            "prospectiveDualSourceLinkSelectorPassed": True,
            "continuousInstructionStateChainCaptured": True,
            "zeroOpaqueAggregateMutations": True,
            "knownAggregateStateTransferPassed": True,
            "changedInstructionBytesAndOperandsCaptured": True,
            "selectedGlassDODCompleteRegisterStateCaptured": True,
            "selectedGlassDODExactDynamicReplayOpened": True,
            "writerInstructionSemanticsDecoded": False,
            "completeCropAllocationPolicyOpened": False,
            "unseenGeometryTransferPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }
    if not legacy:
        result["semanticCropTrace"] = semantic_crop
        result["sealedConclusion"].update(
            {
                "backgroundFilterCropCompleteRegisterStateCaptured": True,
                "backgroundFilterCropExactDynamicReplayOpened": True,
                "backgroundFilterCropStoreAndUnionLinkPassed": True,
                "backgroundFilterCropInstructionSemanticsDecoded": False,
            }
        )
    return result


def validate_files(
    trace_path: Path, inherited_trace_path: Path, output_path: Path | None
) -> dict[str, Any]:
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    inherited = json.loads(inherited_trace_path.read_text(encoding="utf-8"))
    result = validate_documents(trace, inherited)
    result["traceSHA256"] = hashlib.sha256(trace_path.read_bytes()).hexdigest()
    result["inheritedTraceSHA256"] = hashlib.sha256(
        inherited_trace_path.read_bytes()
    ).hexdigest()
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("inherited_trace", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = validate_files(
        arguments.trace, arguments.inherited_trace, arguments.output
    )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
