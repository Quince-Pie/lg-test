"""Single-step the selected ``prepare_layer`` aggregate dependency path.

The preceding hardware-watch experiment proved that one LLDB watch callback
does not imply one architectural store on Apple silicon.  This successor uses
no hardware watchpoints.  It stops at the first source-known depth-four epoch
whose two independently opened source-link cells both equal the selected
source, disables every software breakpoint, and advances that selected thread
until the exact-source marker, one instruction at a time through
``prepare_layer`` and the eight opened QuartzCore helpers. Calls outside
that frozen scope are stepped out as named boundaries and must not change the
aggregate for the gate to pass.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

import lldb


ANALYSIS_ROOT = Path(__file__).resolve().parent
if str(ANALYSIS_ROOT) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_ROOT))
import capture_prepare_layer_frame_correlated_writer_trace_lldb as frame_base  # noqa: E402


capture_base = frame_base.capture_base

TRACE_SCHEMA_VERSION = 6
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
    for site in frame_base.WRITER_SITES
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
TRACE_OUTPUT_ENVIRONMENT = "LG_PREPARE_LAYER_INSTRUCTION_TRACE_OUTPUT"
DEFAULT_TRACE_OUTPUT = "transition-introspection/prepare-layer-instruction-trace.json"

# Every range was fixed from run 31034880031 before this experiment.  A null
# expected digest means that the prior artifact exposed exact symbol bounds but
# not the complete bytes.  The new trace captures and hashes those bytes before
# any selected epoch resumes; exhaustive stepping does not depend on their
# contents.
CHECKPOINT_SCOPE_SPECS = (
    {
        "name": "prepareLayer",
        "function": capture_base.PREPARE_LAYER_FUNCTION,
        "relativeToPrepareLayer": 0,
        "byteCount": capture_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
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
        "function": ("CA::Render::Updater::FilterOp::apply_filter(CA::Rect&, bool)"),
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
        "function": capture_base.UNION_HELPER_SYMBOL_NAME,
        "relativeToPrepareLayer": capture_base.UNION_HELPER_RELATIVE_TO_PREPARE_LAYER,
        "byteCount": capture_base.UNION_HELPER_SYMBOL_BYTE_COUNT,
        "expectedSHA256": capture_base.UNION_HELPER_SYMBOL_SHA256,
    },
)


def _fresh_state():
    return {
        "debugger": None,
        "trace": None,
        "prepareEntryBreakpoint": None,
        "epochBreakpoint": None,
        "selectionBreakpoint": None,
        "prepareLayer": None,
        "scopeByName": {},
        "callbackSequence": 0,
        "epochMarkerHitCount": 0,
        "sourceUnknownEpochCount": 0,
        "rejectedEpochDepthCount": 0,
        "sourceKnownDepthFourEpochCount": 0,
        "sourceLinkedDepthFourEpochCount": 0,
        "rejectedSourceLinkEpochCount": 0,
        "discardedEpochRecordCount": 0,
        "selectionMarkerHitCount": 0,
        "rejectedSelectionMarkerHitCount": 0,
        "unretainedRejectedMarkerDiagnosticCount": 0,
        "inheritedWriterBreakpointsRetired": False,
        "pendingCandidate": None,
        "manualTraceStarted": False,
        "manualTraceFinished": False,
        "semanticDODActive": False,
        "semanticDODFinished": False,
        "semanticCropActiveInvocationIndex": None,
        "semanticCropCompletedInvocationCount": 0,
    }


_state = _fresh_state()


def _reset_state():
    _state.clear()
    _state.update(_fresh_state())


def _trace_path():
    return Path(os.environ.get(TRACE_OUTPUT_ENVIRONMENT, DEFAULT_TRACE_OUTPUT))


def _scope_configuration():
    return [
        {
            "name": spec["name"],
            "function": spec["function"],
            "relativeToPrepareLayer": spec["relativeToPrepareLayer"],
            "byteCount": spec["byteCount"],
            "expectedSHA256": spec["expectedSHA256"],
        }
        for spec in CHECKPOINT_SCOPE_SPECS
    ]


def _new_trace():
    return {
        "prepareLayerInstructionTraceSchemaVersion": TRACE_SCHEMA_VERSION,
        "classification": (
            "preregistered-dual-source-linked-background-filter-crop-full-"
            "register-software-instruction-trace; selected-glass-dod-and-"
            "architectural-writers-opened; crop-policy-generalization-unseen-"
            "transfer-and-product-parity-remain-sealed"
        ),
        "status": "initialized",
        "configuration": {
            "prepareLayerFunction": capture_base.PREPARE_LAYER_FUNCTION,
            "prepareLayerSymbolByteCount": (
                capture_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT
            ),
            "prepareLayerFullCodeSHA256": PREPARE_LAYER_FULL_CODE_SHA256,
            "aggregateOffset": capture_base.AGGREGATE_OFFSET,
            "aggregateByteCount": capture_base.AGGREGATE_BYTE_COUNT,
            "roleStateByteCount": capture_base.ROLE_STATE_BYTE_COUNT,
            "epochMarkerName": EPOCH_MARKER_NAME,
            "epochMarkerOffset": EPOCH_MARKER_OFFSET,
            "epochPrecedingInstructionRawLittleEndianHex": (
                EPOCH_PRECEDING_INSTRUCTION_HEX
            ),
            "selectionMarkerName": SELECTION_MARKER_NAME,
            "selectionMarkerOffset": SELECTION_MARKER_OFFSET,
            "selectionMarkerInstructionRawLittleEndianHex": (
                SELECTION_MARKER_INSTRUCTION_HEX
            ),
            "targetPrepareRecursionDepth": TARGET_PREPARE_RECURSION_DEPTH,
            "sourceLinkCells": [dict(spec) for spec in SOURCE_LINK_CELL_SPECS],
            "maximumEpochMarkerHitCount": MAXIMUM_EPOCH_MARKER_HIT_COUNT,
            "maximumEpochRecordCount": MAXIMUM_EPOCH_RECORD_COUNT,
            "maximumSelectionMarkerHitCount": MAXIMUM_SELECTION_MARKER_HIT_COUNT,
            "maximumRejectedMarkerDiagnosticCount": (
                MAXIMUM_REJECTED_MARKER_DIAGNOSTIC_COUNT
            ),
            "maximumInstructionStepCount": MAXIMUM_INSTRUCTION_STEP_COUNT,
            "maximumOpaqueCalleeCount": MAXIMUM_OPAQUE_CALLEE_COUNT,
            "maximumUnexpectedTerminalContinueCount": (
                MAXIMUM_UNEXPECTED_TERMINAL_CONTINUE_COUNT
            ),
            "maximumSemanticDODEntryCount": MAXIMUM_SEMANTIC_DOD_ENTRY_COUNT,
            "semanticDODScopeName": SEMANTIC_DOD_SCOPE_NAME,
            "semanticDODEntryOffset": SEMANTIC_DOD_ENTRY_OFFSET,
            "semanticDODReturnOffset": SEMANTIC_DOD_RETURN_OFFSET,
            "semanticDODReturnRawLittleEndianHex": (
                SEMANTIC_DOD_RETURN_RAW_LITTLE_ENDIAN_HEX
            ),
            "semanticStackByteCount": SEMANTIC_STACK_BYTE_COUNT,
            "semanticGeneralRegisterNames": list(capture_base.GENERAL_REGISTER_NAMES),
            "semanticSIMDRegisterNames": list(capture_base.SIMD_REGISTER_NAMES),
            "semanticCropScopeName": SEMANTIC_CROP_SCOPE_NAME,
            "semanticCropExpectedInvocationCount": (
                SEMANTIC_CROP_EXPECTED_INVOCATION_COUNT
            ),
            "semanticCropMaximumInvocationCount": (
                SEMANTIC_CROP_MAXIMUM_INVOCATION_COUNT
            ),
            "semanticCropTargetByteCount": SEMANTIC_CROP_TARGET_BYTE_COUNT,
            "semanticCropArgumentMemoryByteCount": (
                SEMANTIC_CROP_ARGUMENT_MEMORY_BYTE_COUNT
            ),
            "semanticCropCallerRoleOffset": SEMANTIC_CROP_CALLER_ROLE_OFFSET,
            "semanticCropCallerRoleByteCount": (SEMANTIC_CROP_CALLER_ROLE_BYTE_COUNT),
            "cropIntegerSourceOffset": CROP_INTEGER_SOURCE_OFFSET,
            "cropIntegerByteCount": CROP_INTEGER_BYTE_COUNT,
            "cropDestinationOffset": CROP_DESTINATION_OFFSET,
            "cropStoreRelativeOffset": CROP_STORE_RELATIVE_OFFSET,
            "cropStoreRawLittleEndianHex": CROP_STORE_RAW_LITTLE_ENDIAN_HEX,
            "cropUnionInputRelativeOffset": CROP_UNION_INPUT_RELATIVE_OFFSET,
            "cropUnionInputRawLittleEndianHex": (
                CROP_UNION_INPUT_RAW_LITTLE_ENDIAN_HEX
            ),
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
            "retiredInheritedWriterSiteNames": list(
                RETIRED_INHERITED_WRITER_SITE_NAMES
            ),
            "retainedControlBreakpointNames": list(RETAINED_CONTROL_BREAKPOINT_NAMES),
            "checkpointScopes": _scope_configuration(),
            "writerMnemonicPrefixes": list(WRITER_MNEMONIC_PREFIXES),
            "callMnemonicPrefixes": list(CALL_MNEMONIC_PREFIXES),
            "frameTraceOutputEnvironment": frame_base.TRACE_OUTPUT_ENVIRONMENT,
            "frameTraceSchemaVersion": frame_base.TRACE_SCHEMA_VERSION,
            "selectionRule": (
                "stop at the first source-known exact-depth-four zero epoch "
                "whose uint64 cells at x10+128 and x20-24 both equal the "
                "independently selected source; then single-step that live "
                "thread/x19/x29 frame until its exact +0x3ef0 marker"
            ),
            "sourceLinkRule": (
                "retain both exact eight-byte cells and reject every epoch "
                "unless both decoded uint64 values equal the independently "
                "selected source"
            ),
            "steppingRule": (
                "disable every software breakpoint before stepping; execute one "
                "architectural instruction at a time inside every frozen scope; "
                "step out of every other callee as a named atomic boundary"
            ),
            "synchronousDebuggerRule": (
                "set SBDebugger async mode false and read it back false before "
                "the first SBThread stepping operation"
            ),
            "hardwareWatchpointRule": (
                "the target must contain zero hardware watchpoints before "
                "instruction stepping"
            ),
            "opaqueBoundaryRule": (
                "a passing trace permits no aggregate change across an opaque "
                "callee boundary"
            ),
            "knownStateTransferRule": (
                "the continuous instruction state sequence must contain, bit-"
                "for-bit and in order, zero; [P,1024-P-640,640,640]; "
                "[P,1024-P-640-8,640,648]; and [floor(P)-1,"
                "1024-P-640-8,P+640-(floor(P)-1),P+648-(floor(P)-1)]"
            ),
            "semanticInvocationRule": (
                "at every glassBackgroundDOD +0x0 entry retain x3; select the "
                "unique entry where x3 equals selected roleBase+aggregateOffset; "
                "for every executed instruction in that invocation retain the "
                "complete scalar and SIMD register files and 256 bytes at sp "
                "before execution, then retain the complete return state"
            ),
            "semanticCropInvocationRule": (
                "retain all four add_background_filters_ entries in execution "
                "order; require x5=x19+0x290; from each entry through its exact "
                "return retain every executed opened-scope instruction with "
                "complete scalar/SIMD registers, 256 stack bytes, and the "
                "fixed 32-byte x5 target; retain 1024 bytes at every entry "
                "argument pointer and the complete 2048-byte caller role at "
                "entry and return"
            ),
            "semanticCropLinkRule": (
                "link the first three invocations by caller x19 to the exact "
                "prepare_layer +0x55c0 q0 store and then to the exact +0x8570 "
                "nested-crop union input; require the fourth invocation to "
                "target the prospectively selected role aggregate"
            ),
        },
        "callbackOrder": [],
        "prepareLayer": {},
        "checkpointScopes": [],
        "epochRecords": [],
        "rejectedMarkerDiagnostics": [],
        "inheritedWriterBreakpointRetirement": {},
        "breakpointDisablement": {},
        "instructionSteps": [],
        "aggregateTransitions": [],
        "opaqueCalleeBoundaries": [],
        "semanticDODEntries": [],
        "semanticDODInvocation": {},
        "semanticDODInstructionStates": [],
        "semanticCropInvocations": [],
        "semanticCropInstructionStates": [],
        "semanticCropStoreLinks": [],
        "semanticCropUnionInputs": [],
        "manualSelectionMarkers": [],
        "selectedFrame": {},
        "terminalProcess": {},
        "failures": [],
    }


def _write_trace():
    trace = _state["trace"]
    if trace is None:
        return
    path = _trace_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(trace, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _failure(stage, error):
    _state["trace"]["failures"].append({"stage": str(stage), "message": str(error)})
    _write_trace()


def _next_sequence(kind):
    _state["callbackSequence"] += 1
    sequence = _state["callbackSequence"]
    _state["trace"]["callbackOrder"].append({"sequence": sequence, "kind": str(kind)})
    return sequence


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _selected_source():
    return frame_base._selected_source()


def _identity(thread_id, role_base, frame_pointer):
    return {
        "threadID": thread_id,
        "roleBase": role_base,
        "framePointer": frame_pointer,
    }


def _exact_prepare_frames(thread):
    """Count exact structural frames without requiring unwound registers."""
    target = thread.GetProcess().GetTarget()
    start = _state["prepareLayer"]["symbolStart"]
    end = _state["prepareLayer"]["symbolEnd"]
    records = []
    for index in range(
        min(thread.GetNumFrames(), capture_base.MAXIMUM_BACKTRACE_FRAME_COUNT)
    ):
        candidate = thread.GetFrameAtIndex(index)
        if candidate.GetFunctionName() != capture_base.PREPARE_LAYER_FUNCTION:
            continue
        symbol = candidate.GetSymbol()
        if not symbol.IsValid():
            continue
        if (
            symbol.GetStartAddress().GetLoadAddress(target) != start
            or symbol.GetEndAddress().GetLoadAddress(target) != end
        ):
            continue
        frame_pointer = candidate.GetFP()
        if frame_pointer in (0, lldb.LLDB_INVALID_ADDRESS):
            frame_pointer = None
        records.append(
            {
                "frame": candidate,
                "frameIndex": index,
                "framePointer": frame_pointer,
            }
        )
    return records


def _matching_identity(exact, identity, thread_id):
    if thread_id != identity["threadID"]:
        return None, None
    for ordinal, item in enumerate(exact):
        if item["framePointer"] == identity["framePointer"]:
            return ordinal, item
    return None, None


def _public_prepare_frames(exact, target):
    return [
        {
            "frameIndex": item["frameIndex"],
            "frame": capture_base._frame_record(item["frame"], target),
            "unwindFramePointer": item["framePointer"],
        }
        for item in exact
    ]


def _memory_payload(process, address, byte_count, label):
    payload = capture_base._read_memory(process, address, byte_count, label)
    return payload, {
        "address": address,
        "byteCount": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "hex": payload.hex(),
    }


def _source_link_cells(process, register_values, selected_source):
    records = []
    for spec in SOURCE_LINK_CELL_SPECS:
        base = register_values[spec["baseRegister"]]
        address = base + spec["signedOffset"]
        payload, memory = _memory_payload(
            process,
            address,
            8,
            "instruction epoch " + spec["name"],
        )
        observed = int.from_bytes(payload, "little", signed=False)
        records.append(
            {
                **spec,
                "baseValue": base,
                "address": address,
                "memory": memory,
                "observedValue": observed,
                "selectedSourceMatches": observed == selected_source,
            }
        )
    return records, all(item["selectedSourceMatches"] for item in records)


def _aggregate(process, identity, label):
    address = identity["roleBase"] + capture_base.AGGREGATE_OFFSET
    return capture_base._read_memory(
        process, address, capture_base.AGGREGATE_BYTE_COUNT, label
    )


def _changed_lane_offsets(before, after):
    return [
        offset
        for offset in (0, 8, 16, 24)
        if before[offset : offset + 8] != after[offset : offset + 8]
    ]


def _module_record(module, target):
    record = capture_base._module_record(module, target)
    if record.get("valid") is True:
        uuid = module.GetUUIDString()
        record["uuid"] = uuid if uuid else None
    return record


def _record_marker_rejection(marker, frame, reason, exact, source=None, x28=None):
    diagnostics = _state["trace"]["rejectedMarkerDiagnostics"]
    if len(diagnostics) >= MAXIMUM_REJECTED_MARKER_DIAGNOSTIC_COUNT:
        _state["unretainedRejectedMarkerDiagnosticCount"] += 1
        return
    target = frame.GetThread().GetProcess().GetTarget()
    hit_index = (
        _state["epochMarkerHitCount"]
        if marker == "epoch"
        else _state["selectionMarkerHitCount"]
    )
    diagnostics.append(
        {
            "diagnosticIndex": len(diagnostics),
            "marker": marker,
            "reason": str(reason),
            "markerHitIndex": hit_index,
            "threadID": frame.GetThread().GetThreadID(),
            "pc": frame.GetPC(),
            "selectedSource": source,
            "observedX28": x28,
            "structuralPrepareRecursionDepth": len(exact),
            "backtrace": capture_base._backtrace(frame.GetThread()),
            "prepareFrames": _public_prepare_frames(exact, target),
        }
    )


def _resolve_checkpoint_scopes(process, prepare_start, prepare_code):
    target = process.GetTarget()
    records = []
    runtime = {}
    for spec in CHECKPOINT_SCOPE_SPECS:
        start = prepare_start + spec["relativeToPrepareLayer"]
        end = start + spec["byteCount"]
        resolved = target.ResolveLoadAddress(start)
        symbol = resolved.GetSymbol()
        if not symbol.IsValid():
            raise RuntimeError(spec["name"] + " checkpoint symbol is invalid")
        symbol_start = symbol.GetStartAddress().GetLoadAddress(target)
        symbol_end = symbol.GetEndAddress().GetLoadAddress(target)
        if (
            resolved.GetFunction().GetName() != spec["function"]
            and symbol.GetName() != spec["function"]
        ):
            raise RuntimeError(spec["name"] + " checkpoint function differs")
        if symbol_start != start or symbol_end != end:
            raise RuntimeError(spec["name"] + " checkpoint symbol bounds differ")
        if spec["name"] == "prepareLayer":
            code = prepare_code
        else:
            code = capture_base._read_memory(
                process, start, spec["byteCount"], spec["name"] + " full code"
            )
        digest = hashlib.sha256(code).hexdigest()
        expected = spec["expectedSHA256"]
        if expected is not None and digest != expected:
            raise RuntimeError(spec["name"] + " checkpoint code hash differs")
        record = {
            "scopeIndex": len(records),
            "name": spec["name"],
            "function": spec["function"],
            "relativeToPrepareLayer": spec["relativeToPrepareLayer"],
            "startAddress": start,
            "endAddress": end,
            "byteCount": len(code),
            "expectedSHA256": expected,
            "observedSHA256": digest,
            "hex": code.hex(),
            "module": _module_record(resolved.GetModule(), target),
        }
        records.append(record)
        runtime[spec["name"]] = record
    return records, runtime


def _scope_for_pc(pc):
    for record in _state["scopeByName"].values():
        if record["startAddress"] <= pc < record["endAddress"]:
            return record
    return None


def _instruction_record(frame, scope):
    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    pc = frame.GetPC()
    raw = capture_base._read_memory(process, pc, 4, "instruction checkpoint")
    mnemonic = ""
    operands = ""
    comment = ""
    try:
        instructions = target.ReadInstructions(frame.GetPCAddress(), 1)
        if instructions.GetSize() == 1:
            instruction = instructions.GetInstructionAtIndex(0)
            mnemonic = instruction.GetMnemonic(target) or ""
            operands = instruction.GetOperands(target) or ""
            comment = instruction.GetComment(target) or ""
    except Exception:
        # Raw bytes and the frozen symbol are authoritative.  Decode text is
        # diagnostic and may vary between LLDB Python builds.
        pass
    lowered = mnemonic.lower()
    return {
        "pc": pc,
        "scopeName": scope["name"],
        "scopeOffset": pc - scope["startAddress"],
        "prepareLayerRelativeOffset": pc - _state["prepareLayer"]["symbolStart"],
        "rawLittleEndianHex": raw.hex(),
        "mnemonic": mnemonic,
        "operands": operands,
        "comment": comment,
        "potentialWriter": lowered.startswith(WRITER_MNEMONIC_PREFIXES),
        "potentialCall": lowered.startswith(CALL_MNEMONIC_PREFIXES),
    }


def _semantic_register_and_stack_snapshot(frame, label):
    process = frame.GetThread().GetProcess()
    registers = capture_base._full_register_snapshot(frame)
    general = {item["name"]: item for item in registers["general"]}
    stack_pointer = general["sp"]["unsignedValue"]
    return registers, capture_base._memory_snapshot(
        process,
        stack_pointer,
        SEMANTIC_STACK_BYTE_COUNT,
        label + " stack",
    )


def _semantic_state_before(frame, instruction, aggregate):
    if instruction["scopeName"] != SEMANTIC_DOD_SCOPE_NAME:
        return
    trace = _state["trace"]
    step_index = len(trace["instructionSteps"])
    if instruction["scopeOffset"] == SEMANTIC_DOD_ENTRY_OFFSET:
        entries = trace["semanticDODEntries"]
        if len(entries) >= MAXIMUM_SEMANTIC_DOD_ENTRY_COUNT:
            raise RuntimeError("semantic DOD entry bound exceeded")
        target = (
            _state["pendingCandidate"]["identity"]["roleBase"]
            + capture_base.AGGREGATE_OFFSET
        )
        x3_register = capture_base._register_snapshot(frame, ("x3",))[0]
        argument = x3_register["unsignedValue"]
        matched = argument == target
        entry = {
            "entryIndex": len(entries),
            "stepIndex": step_index,
            "pc": frame.GetPC(),
            "argumentX3": argument,
            "x3Register": x3_register,
            "targetAggregateAddress": target,
            "argumentMatchesTarget": matched,
        }
        entries.append(entry)
        if matched:
            if _state["semanticDODActive"] or _state["semanticDODFinished"]:
                raise RuntimeError("semantic DOD target entry is not unique")
            _state["semanticDODActive"] = True
            trace["semanticDODInvocation"] = {
                "entryRecordIndex": entry["entryIndex"],
                "entryStepIndex": step_index,
                "entryPC": frame.GetPC(),
                "entryArgumentX3": argument,
                "targetAggregateAddress": target,
                "aggregateAtEntryHex": aggregate.hex(),
            }
    if not _state["semanticDODActive"]:
        return
    registers, stack = _semantic_register_and_stack_snapshot(
        frame, "semantic DOD instruction"
    )
    states = trace["semanticDODInstructionStates"]
    states.append(
        {
            "stateIndex": len(states),
            "stepIndex": step_index,
            "instruction": instruction,
            "aggregateBeforeHex": aggregate.hex(),
            "registers": registers,
            "stack": stack,
        }
    )
    if len(states) % 64 == 0:
        _write_trace()


def _finish_semantic_instruction(instruction, result_frame, aggregate):
    if (
        not _state["semanticDODActive"]
        or instruction["scopeName"] != SEMANTIC_DOD_SCOPE_NAME
    ):
        return
    result_scope = _scope_for_pc(result_frame.GetPC())
    returned_outside = (
        result_scope is None or result_scope["name"] != SEMANTIC_DOD_SCOPE_NAME
    )
    terminal = instruction["scopeOffset"] == SEMANTIC_DOD_RETURN_OFFSET
    if terminal:
        if (
            instruction["rawLittleEndianHex"]
            != SEMANTIC_DOD_RETURN_RAW_LITTLE_ENDIAN_HEX
            or instruction["mnemonic"].lower() != "retab"
            or not returned_outside
        ):
            raise RuntimeError("semantic DOD return instruction differs")
        registers, stack = _semantic_register_and_stack_snapshot(
            result_frame, "semantic DOD return"
        )
        states = _state["trace"]["semanticDODInstructionStates"]
        invocation = _state["trace"]["semanticDODInvocation"]
        invocation.update(
            {
                "returnStepIndex": len(_state["trace"]["instructionSteps"]) - 1,
                "returnInstructionStateIndex": len(states) - 1,
                "returnPC": result_frame.GetPC(),
                "returnFunction": result_frame.GetFunctionName(),
                "aggregateAtReturnHex": aggregate.hex(),
                "instructionStateCount": len(states),
                "instructionStatesSHA256": hashlib.sha256(
                    json.dumps(
                        states,
                        sort_keys=True,
                        separators=(",", ":"),
                        allow_nan=False,
                    ).encode("utf-8")
                ).hexdigest(),
                "returnRegisters": registers,
                "returnStack": stack,
            }
        )
        _state["semanticDODActive"] = False
        _state["semanticDODFinished"] = True
        _write_trace()
    elif returned_outside and not instruction["potentialCall"]:
        raise RuntimeError("semantic DOD escaped at a non-return instruction")


def _register_records_by_name(registers):
    return {record["name"]: record for record in registers["general"]}


def _crop_argument_memory(process, addresses, label):
    result = []
    for name in ("x0", "x1", "x2", "x3", "x4", "x5"):
        address = addresses[name]
        if address <= 0:
            raise RuntimeError(label + " " + name + " pointer is invalid")
        _payload, memory = _memory_payload(
            process,
            address,
            SEMANTIC_CROP_ARGUMENT_MEMORY_BYTE_COUNT,
            label + " " + name,
        )
        result.append({"registerName": name, "memory": memory})
    return result


def _crop_memory(process, address, byte_count, label):
    _payload, memory = _memory_payload(process, address, byte_count, label)
    return memory


def _semantic_crop_state_before(frame, instruction, aggregate):
    trace = _state["trace"]
    step_index = len(trace["instructionSteps"])
    active_index = _state["semanticCropActiveInvocationIndex"]
    is_entry = (
        instruction["scopeName"] == SEMANTIC_CROP_SCOPE_NAME
        and instruction["scopeOffset"] == 0
    )
    if not is_entry and active_index is None:
        return
    if is_entry:
        if active_index is not None:
            raise RuntimeError("semantic crop writer re-entered before return")
        invocations = trace["semanticCropInvocations"]
        if len(invocations) >= SEMANTIC_CROP_MAXIMUM_INVOCATION_COUNT:
            raise RuntimeError("semantic crop invocation bound exceeded")
        registers, stack = _semantic_register_and_stack_snapshot(
            frame, "semantic crop entry"
        )
        records = _register_records_by_name(registers)
        arguments = {
            name: records[name]["unsignedValue"]
            for name in (
                "x0",
                "x1",
                "x2",
                "x3",
                "x4",
                "x5",
            )
        }
        caller_role = records["x19"]["unsignedValue"]
        target = arguments["x5"]
        if target != caller_role + SEMANTIC_CROP_CALLER_ROLE_OFFSET:
            raise RuntimeError("semantic crop x5 and caller role differ")
        process = frame.GetThread().GetProcess()
        invocation = {
            "invocationIndex": len(invocations),
            "entryStepIndex": step_index,
            "entryPC": frame.GetPC(),
            "entryArgumentRegisters": [records[name] for name in arguments],
            "entryArgumentAddresses": arguments,
            "entryArgumentMemory": _crop_argument_memory(
                process, arguments, "semantic crop entry argument"
            ),
            "callerRoleBase": caller_role,
            "callerRoleAtEntry": _crop_memory(
                process,
                caller_role,
                SEMANTIC_CROP_CALLER_ROLE_BYTE_COUNT,
                "semantic crop caller role at entry",
            ),
            "targetAddress": target,
            "targetAtEntry": _crop_memory(
                process,
                target,
                SEMANTIC_CROP_TARGET_BYTE_COUNT,
                "semantic crop target at entry",
            ),
            "aggregateAtEntryHex": aggregate.hex(),
            "instructionStateStartIndex": len(trace["semanticCropInstructionStates"]),
            "storeLinkIndex": None,
        }
        invocations.append(invocation)
        active_index = invocation["invocationIndex"]
        _state["semanticCropActiveInvocationIndex"] = active_index
    else:
        registers, stack = _semantic_register_and_stack_snapshot(
            frame, "semantic crop instruction"
        )
    invocation = trace["semanticCropInvocations"][active_index]
    process = frame.GetThread().GetProcess()
    states = trace["semanticCropInstructionStates"]
    states.append(
        {
            "stateIndex": len(states),
            "invocationIndex": active_index,
            "invocationStateIndex": (
                len(states) - invocation["instructionStateStartIndex"]
            ),
            "stepIndex": step_index,
            "instruction": instruction,
            "aggregateBeforeHex": aggregate.hex(),
            "registers": registers,
            "stack": stack,
            "target": _crop_memory(
                process,
                invocation["targetAddress"],
                SEMANTIC_CROP_TARGET_BYTE_COUNT,
                "semantic crop instruction target",
            ),
        }
    )
    if len(states) % 64 == 0:
        _write_trace()


def _finish_semantic_crop_instruction(instruction, result_frame, aggregate):
    active_index = _state["semanticCropActiveInvocationIndex"]
    if active_index is None or instruction["scopeName"] != SEMANTIC_CROP_SCOPE_NAME:
        return
    result_scope = _scope_for_pc(result_frame.GetPC())
    returned_outside = (
        result_scope is None or result_scope["name"] != SEMANTIC_CROP_SCOPE_NAME
    )
    if not returned_outside:
        return
    if instruction["potentialCall"]:
        return
    if (
        instruction["mnemonic"].lower() not in CROP_RETURN_MNEMONICS
        or instruction["rawLittleEndianHex"] not in CROP_RETURN_RAW_LITTLE_ENDIAN_HEX
    ):
        raise RuntimeError("semantic crop writer escaped at a non-return instruction")
    trace = _state["trace"]
    invocation = trace["semanticCropInvocations"][active_index]
    registers, stack = _semantic_register_and_stack_snapshot(
        result_frame, "semantic crop return"
    )
    process = result_frame.GetThread().GetProcess()
    states = trace["semanticCropInstructionStates"]
    start = invocation["instructionStateStartIndex"]
    invocation_states = states[start:]
    arguments = invocation["entryArgumentAddresses"]
    invocation.update(
        {
            "returnStepIndex": len(trace["instructionSteps"]) - 1,
            "returnInstructionStateIndex": len(states) - 1,
            "returnInstructionScopeOffset": instruction["scopeOffset"],
            "returnInstructionRawLittleEndianHex": instruction["rawLittleEndianHex"],
            "returnInstructionMnemonic": instruction["mnemonic"].lower(),
            "returnPC": result_frame.GetPC(),
            "returnFunction": result_frame.GetFunctionName(),
            "returnArgumentMemory": _crop_argument_memory(
                process, arguments, "semantic crop return argument"
            ),
            "callerRoleAtReturn": _crop_memory(
                process,
                invocation["callerRoleBase"],
                SEMANTIC_CROP_CALLER_ROLE_BYTE_COUNT,
                "semantic crop caller role at return",
            ),
            "targetAtReturn": _crop_memory(
                process,
                invocation["targetAddress"],
                SEMANTIC_CROP_TARGET_BYTE_COUNT,
                "semantic crop target at return",
            ),
            "aggregateAtReturnHex": aggregate.hex(),
            "instructionStateCount": len(invocation_states),
            "instructionStatesSHA256": hashlib.sha256(
                json.dumps(
                    invocation_states,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
            ).hexdigest(),
            "returnRegisters": registers,
            "returnStack": stack,
        }
    )
    _state["semanticCropActiveInvocationIndex"] = None
    _state["semanticCropCompletedInvocationCount"] += 1
    _write_trace()


def _crop_store_before(frame, instruction):
    if not (
        instruction["scopeName"] == "prepareLayer"
        and instruction["scopeOffset"] == CROP_STORE_RELATIVE_OFFSET
    ):
        return None
    if (
        instruction["rawLittleEndianHex"] != CROP_STORE_RAW_LITTLE_ENDIAN_HEX
        or instruction["mnemonic"].lower() != "str"
    ):
        raise RuntimeError("semantic crop store instruction differs")
    registers = capture_base._full_register_snapshot(frame)
    records = _register_records_by_name(registers)
    caller_role = records["x19"]["unsignedValue"]
    destination_base = records["x28"]["unsignedValue"]
    invocations = _state["trace"]["semanticCropInvocations"]
    candidates = [
        item
        for item in invocations
        if item["callerRoleBase"] == caller_role
        and "returnStepIndex" in item
        and item["storeLinkIndex"] is None
    ]
    if len(candidates) != 1:
        raise RuntimeError("semantic crop store source invocation differs")
    invocation = candidates[0]
    process = frame.GetThread().GetProcess()
    stores = _state["trace"]["semanticCropStoreLinks"]
    record = {
        "storeLinkIndex": len(stores),
        "sourceInvocationIndex": invocation["invocationIndex"],
        "stepIndex": len(_state["trace"]["instructionSteps"]),
        "instruction": instruction,
        "registers": registers,
        "callerRoleBase": caller_role,
        "sourceIntegerAddress": caller_role + CROP_INTEGER_SOURCE_OFFSET,
        "sourceInteger": _crop_memory(
            process,
            caller_role + CROP_INTEGER_SOURCE_OFFSET,
            CROP_INTEGER_BYTE_COUNT,
            "semantic crop integer source",
        ),
        "destinationAddress": destination_base + CROP_DESTINATION_OFFSET,
        "destinationBefore": _crop_memory(
            process,
            destination_base + CROP_DESTINATION_OFFSET,
            CROP_INTEGER_BYTE_COUNT,
            "semantic crop destination before",
        ),
        "destinationAfter": None,
        "returnPC": None,
        "unionInputIndex": None,
    }
    stores.append(record)
    invocation["storeLinkIndex"] = record["storeLinkIndex"]
    return record


def _finish_crop_store(record, result_frame):
    if record is None:
        return
    record["destinationAfter"] = _crop_memory(
        result_frame.GetThread().GetProcess(),
        record["destinationAddress"],
        CROP_INTEGER_BYTE_COUNT,
        "semantic crop destination after",
    )
    record["returnPC"] = result_frame.GetPC()


def _crop_union_input_before(frame, instruction):
    if not (
        instruction["scopeName"] == "prepareLayer"
        and instruction["scopeOffset"] == CROP_UNION_INPUT_RELATIVE_OFFSET
    ):
        return
    if (
        instruction["rawLittleEndianHex"] != CROP_UNION_INPUT_RAW_LITTLE_ENDIAN_HEX
        or instruction["mnemonic"].lower() != "ldp"
    ):
        raise RuntimeError("semantic crop union input instruction differs")
    registers = capture_base._full_register_snapshot(frame)
    records = _register_records_by_name(registers)
    destination_base = records["x28"]["unsignedValue"]
    destination = destination_base + CROP_DESTINATION_OFFSET
    stores = _state["trace"]["semanticCropStoreLinks"]
    candidates = [
        item
        for item in stores
        if item["destinationAddress"] == destination and item["unionInputIndex"] is None
    ]
    if len(candidates) != 1:
        raise RuntimeError("semantic crop union source store differs")
    store = candidates[0]
    process = frame.GetThread().GetProcess()
    values = _state["trace"]["semanticCropUnionInputs"]
    record = {
        "unionInputIndex": len(values),
        "sourceStoreLinkIndex": store["storeLinkIndex"],
        "stepIndex": len(_state["trace"]["instructionSteps"]),
        "instruction": instruction,
        "registers": registers,
        "layerShapesBase": destination_base,
        "stateAddress": destination_base + CROP_UNION_STATE_OFFSET,
        "state": _crop_memory(
            process,
            destination_base + CROP_UNION_STATE_OFFSET,
            CROP_UNION_STATE_BYTE_COUNT,
            "semantic crop union state",
        ),
    }
    values.append(record)
    store["unionInputIndex"] = record["unionInputIndex"]


def _candidate_context(frame, identity, label):
    process = frame.GetThread().GetProcess()
    role, role_record = _memory_payload(
        process,
        identity["roleBase"],
        capture_base.ROLE_STATE_BYTE_COUNT,
        label + " role state",
    )
    aggregate = role[
        capture_base.AGGREGATE_OFFSET : capture_base.AGGREGATE_OFFSET
        + capture_base.AGGREGATE_BYTE_COUNT
    ]
    return aggregate, {
        "frame": capture_base._frame_record(frame, process.GetTarget()),
        "backtrace": capture_base._backtrace(frame.GetThread()),
        "roleState": role_record,
        "operandSnapshot": capture_base._operand_snapshot(frame),
        "privateFields": capture_base._snapshot_private_fields(process),
    }


def _post_transition_context(thread, identity, label):
    process = thread.GetProcess()
    role, role_record = _memory_payload(
        process,
        identity["roleBase"],
        capture_base.ROLE_STATE_BYTE_COUNT,
        label + " role state",
    )
    return {
        "backtrace": capture_base._backtrace(thread),
        "roleState": role_record,
        "privateFields": capture_base._snapshot_private_fields(process),
    }


def _thread_for_identity(process, identity):
    thread = process.GetThreadByID(identity["threadID"])
    if not thread.IsValid():
        raise RuntimeError("selected instruction thread is unavailable")
    return thread


def _require_stopped(process, label):
    if process.GetState() != lldb.eStateStopped:
        raise RuntimeError(label + " did not stop the process")


def _record_step(
    kind,
    before,
    after,
    instruction=None,
    result_frame=None,
    before_context=None,
    opaque=None,
):
    steps = _state["trace"]["instructionSteps"]
    changed = before != after
    record = {
        "stepIndex": len(steps),
        "kind": kind,
        "aggregateBeforeHex": before.hex(),
        "aggregateAfterHex": after.hex(),
        "aggregateChanged": changed,
        "changedLaneOffsets": _changed_lane_offsets(before, after),
        "instruction": instruction,
        "opaqueBoundary": opaque,
        "resultPC": None if result_frame is None else result_frame.GetPC(),
        "resultFunction": (
            None if result_frame is None else result_frame.GetFunctionName()
        ),
        "transitionIndex": None,
    }
    if changed:
        if before_context is None:
            raise RuntimeError("changed instruction lacks before context")
        sequence = _next_sequence("aggregate-instruction-transition")
        transition = {
            "transitionIndex": len(_state["trace"]["aggregateTransitions"]),
            "callbackSequence": sequence,
            "stepIndex": record["stepIndex"],
            "kind": kind,
            "aggregateBeforeHex": before.hex(),
            "aggregateAfterHex": after.hex(),
            "changedLaneOffsets": record["changedLaneOffsets"],
            "instruction": instruction,
            "opaqueBoundary": opaque,
            "beforeContext": before_context,
            "afterContext": _post_transition_context(
                result_frame.GetThread(),
                _state["pendingCandidate"]["identity"],
                "instruction transition after",
            ),
        }
        _state["trace"]["aggregateTransitions"].append(transition)
        record["transitionIndex"] = transition["transitionIndex"]
    steps.append(record)
    if changed or len(steps) % 256 == 0:
        _write_trace()


def multiplexed_prepare_layer_entry(frame, breakpoint_location, internal_dict):
    """Run inherited setup before the instruction-trace setup."""
    frame_base.prepare_layer_entry(frame, breakpoint_location, internal_dict)
    prepare_layer_entry(frame, breakpoint_location, internal_dict)
    return False


def forwarded_capture_backdrop_entry(frame, breakpoint_location, internal_dict):
    """Run inherited source setup and export its dynamic callback."""
    frame_base.capture_backdrop_entry(frame, breakpoint_location, internal_dict)
    try:
        late = frame_base._state["captureLateBreakpoint"]
        if late is None or not late.IsValid():
            raise RuntimeError("inherited capture late breakpoint differs")
        _set_callback(
            late,
            "forwarded_capture_backdrop_late",
            "forwarded inherited capture late",
        )
    except Exception as error:
        _failure("inherited-capture-callback-forwarding", error)
    return False


def _retire_inherited_writer_breakpoints(frame):
    if _state["inheritedWriterBreakpointsRetired"]:
        return
    source = _selected_source()
    if source is None:
        return
    if _state["prepareLayer"] is None or _state["callbackSequence"] != 1:
        raise RuntimeError("writer retirement did not immediately follow setup")
    breakpoints = frame_base._state["writerBreakpoints"]
    if set(breakpoints) != {site["name"] for site in frame_base.WRITER_SITES}:
        raise RuntimeError("inherited writer breakpoint inventory differs")
    retired = []
    for name in RETIRED_INHERITED_WRITER_SITE_NAMES:
        breakpoint = breakpoints[name]
        if breakpoint is None or not breakpoint.IsValid():
            raise RuntimeError(name + " inherited writer breakpoint is invalid")
        breakpoint.SetEnabled(False)
        if breakpoint.IsEnabled():
            raise RuntimeError(name + " inherited writer breakpoint remained enabled")
        retired.append(
            {
                "name": name,
                "breakpointID": breakpoint.GetID(),
                "enabledAfterRetirement": breakpoint.IsEnabled(),
            }
        )
    controls = (
        (EPOCH_MARKER_NAME, breakpoints[EPOCH_MARKER_NAME]),
        (SELECTION_MARKER_NAME, _state["selectionBreakpoint"]),
    )
    retained = []
    for name, breakpoint in controls:
        if breakpoint is None or not breakpoint.IsValid() or not breakpoint.IsEnabled():
            raise RuntimeError(name + " control breakpoint was not retained")
        retained.append(
            {
                "name": name,
                "breakpointID": breakpoint.GetID(),
                "enabledAfterRetirement": breakpoint.IsEnabled(),
            }
        )
    identifiers = [item["breakpointID"] for item in retired + retained]
    if any(value <= 0 for value in identifiers) or len(identifiers) != len(
        set(identifiers)
    ):
        raise RuntimeError("isolated breakpoint identities differ")
    sequence = _next_sequence("inherited-writer-breakpoints-retired")
    _state["trace"]["inheritedWriterBreakpointRetirement"] = {
        "callbackSequence": sequence,
        "threadID": frame.GetThread().GetThreadID(),
        "pc": frame.GetPC(),
        "selectedSource": source,
        "retired": retired,
        "retainedControlBreakpoints": retained,
    }
    _state["inheritedWriterBreakpointsRetired"] = True
    _state["trace"]["status"] = "sampled-writer-breakpoints-retired"
    _write_trace()


def forwarded_capture_backdrop_late(frame, breakpoint_location, internal_dict):
    """Forward the independent source selector, then isolate checkpoints."""
    frame_base.capture_backdrop_late(frame, breakpoint_location, internal_dict)
    try:
        _retire_inherited_writer_breakpoints(frame)
    except Exception as error:
        _failure("inherited-writer-breakpoint-retirement", error)
    return False


def forwarded_writer_site(frame, breakpoint_location, internal_dict):
    frame_base.writer_site(frame, breakpoint_location, internal_dict)
    return False


def multiplexed_epoch_marker(frame, breakpoint_location, internal_dict):
    frame_base.writer_site(frame, breakpoint_location, internal_dict)
    return prepare_layer_epoch_marker(frame, breakpoint_location, internal_dict)


def multiplexed_selection_marker(frame, breakpoint_location, internal_dict):
    frame_base.live_selection_marker(frame, breakpoint_location, internal_dict)
    prepare_layer_selection_marker(frame, breakpoint_location, internal_dict)
    return False


def prepare_layer_entry(frame, breakpoint_location, _internal_dict):
    """Freeze complete scope bytes and reuse the inherited control sites."""
    try:
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        symbol = frame.GetSymbol()
        if not symbol.IsValid():
            raise RuntimeError("instruction trace prepare_layer symbol is invalid")
        start = symbol.GetStartAddress().GetLoadAddress(target)
        end = symbol.GetEndAddress().GetLoadAddress(target)
        callback_location = breakpoint_location.GetAddress().GetLoadAddress(target)
        if (
            frame.GetFunctionName() != capture_base.PREPARE_LAYER_FUNCTION
            or frame.GetPC() != start
            or callback_location != start
            or end - start != capture_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT
        ):
            raise RuntimeError("instruction trace exact prepare_layer entry differs")
        code = capture_base._read_memory(
            process,
            start,
            capture_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            "instruction trace complete prepare_layer code",
        )
        if hashlib.sha256(code).hexdigest() != PREPARE_LAYER_FULL_CODE_SHA256:
            raise RuntimeError("instruction trace prepare_layer hash differs")
        if (
            code[EPOCH_MARKER_OFFSET - 4 : EPOCH_MARKER_OFFSET].hex()
            != EPOCH_PRECEDING_INSTRUCTION_HEX
            or code[SELECTION_MARKER_OFFSET : SELECTION_MARKER_OFFSET + 4].hex()
            != SELECTION_MARKER_INSTRUCTION_HEX
        ):
            raise RuntimeError("instruction trace marker bytes differ")
        epoch = frame_base._state["writerBreakpoints"].get(EPOCH_MARKER_NAME)
        selection = frame_base._state["selectionMarkerBreakpoint"]
        for name, breakpoint in frame_base._state["writerBreakpoints"].items():
            if name != EPOCH_MARKER_NAME:
                _set_callback(
                    breakpoint,
                    "forwarded_writer_site",
                    "forwarded inherited writer site " + name,
                )
        if (
            epoch is None
            or not epoch.IsValid()
            or epoch.GetNumLocations() != 1
            or epoch.GetLocationAtIndex(0).GetAddress().GetLoadAddress(target)
            != start + EPOCH_MARKER_OFFSET
            or selection is None
            or not selection.IsValid()
            or selection.GetNumLocations() != 1
            or selection.GetLocationAtIndex(0).GetAddress().GetLoadAddress(target)
            != start + SELECTION_MARKER_OFFSET
        ):
            raise RuntimeError("inherited shared instruction breakpoints differ")
        _set_callback(epoch, "multiplexed_epoch_marker", "shared zero epoch")
        _set_callback(
            selection,
            "multiplexed_selection_marker",
            "shared source selection marker",
        )
        scopes, runtime = _resolve_checkpoint_scopes(process, start, code)
        sequence = _next_sequence("prepare-layer-entry")
        prepare = {
            "callbackSequence": sequence,
            "callbackPC": frame.GetPC(),
            "callbackLocationAddress": callback_location,
            "function": capture_base.PREPARE_LAYER_FUNCTION,
            "symbolStart": start,
            "symbolEnd": end,
            "symbolByteCount": len(code),
            "fullCodeSHA256": hashlib.sha256(code).hexdigest(),
            "module": _module_record(frame.GetModule(), target),
            "epochMarker": {
                "address": start + EPOCH_MARKER_OFFSET,
                "breakpointID": epoch.GetID(),
            },
            "selectionMarker": {
                "address": start + SELECTION_MARKER_OFFSET,
                "breakpointID": selection.GetID(),
            },
        }
        _state["prepareLayer"] = prepare
        _state["scopeByName"] = runtime
        _state["trace"]["prepareLayer"] = prepare
        _state["trace"]["checkpointScopes"] = scopes
        _state["epochBreakpoint"] = epoch
        _state["selectionBreakpoint"] = selection
        _state["prepareEntryBreakpoint"].SetEnabled(False)
        _state["trace"]["status"] = "instruction-scopes-and-markers-frozen"
        _write_trace()
    except Exception as error:
        _failure("prepare-layer-entry", error)
        if _state["prepareEntryBreakpoint"] is not None:
            _state["prepareEntryBreakpoint"].SetEnabled(False)
    return False


def prepare_layer_epoch_marker(frame, _breakpoint_location, _internal_dict):
    """Stop at the first exact-depth-four zero epoch linked to the source."""
    try:
        _state["epochMarkerHitCount"] += 1
        if _state["epochMarkerHitCount"] > MAXIMUM_EPOCH_MARKER_HIT_COUNT:
            raise RuntimeError("instruction epoch marker hit bound exceeded")
        exact = _exact_prepare_frames(frame.GetThread())
        source = _selected_source()
        if source is None:
            _state["sourceUnknownEpochCount"] += 1
            _record_marker_rejection("epoch", frame, "source-unknown", exact)
            return False
        if len(exact) != TARGET_PREPARE_RECURSION_DEPTH or exact[0]["frameIndex"] != 0:
            _state["rejectedEpochDepthCount"] += 1
            _record_marker_rejection(
                "epoch", frame, "structural-depth-differs", exact, source=source
            )
            return False
        _state["sourceKnownDepthFourEpochCount"] += 1
        ordinal = _state["sourceKnownDepthFourEpochCount"]
        records = _state["trace"]["epochRecords"]
        if len(records) >= MAXIMUM_EPOCH_RECORD_COUNT:
            _state["discardedEpochRecordCount"] += 1
            raise RuntimeError("instruction epoch record bound exceeded")
        process = frame.GetThread().GetProcess()
        registers = capture_base._register_snapshot(frame, EPOCH_FRAME_REGISTER_NAMES)
        values = {item["name"]: item["unsignedValue"] for item in registers}
        identity = _identity(
            frame.GetThread().GetThreadID(), values["x19"], values["x29"]
        )
        if exact[0]["framePointer"] != identity["framePointer"]:
            raise RuntimeError("instruction epoch x29 and unwind FP differ")
        role, role_record = _memory_payload(
            process,
            identity["roleBase"],
            capture_base.ROLE_STATE_BYTE_COUNT,
            "instruction epoch role state",
        )
        aggregate = role[
            capture_base.AGGREGATE_OFFSET : capture_base.AGGREGATE_OFFSET
            + capture_base.AGGREGATE_BYTE_COUNT
        ]
        if aggregate != bytes(capture_base.AGGREGATE_BYTE_COUNT):
            raise RuntimeError("source-known depth-four epoch aggregate is not zero")
        source_links, source_linked = _source_link_cells(process, values, source)
        if source_linked:
            _state["sourceLinkedDepthFourEpochCount"] += 1
        else:
            _state["rejectedSourceLinkEpochCount"] += 1
        sequence = _next_sequence("source-known-depth-four-zero-epoch")
        record = {
            "recordIndex": len(records),
            "callbackSequence": sequence,
            "markerHitIndex": _state["epochMarkerHitCount"],
            "sourceKnownDepthFourOrdinal": ordinal,
            "pc": frame.GetPC(),
            "frame": capture_base._frame_record(frame, process.GetTarget()),
            "backtrace": capture_base._backtrace(frame.GetThread()),
            "prepareRecursionDepth": len(exact),
            "prepareFrames": _public_prepare_frames(exact, process.GetTarget()),
            "registers": registers,
            "identity": identity,
            "selectedSourceKnown": source,
            "roleStateAtEpoch": role_record,
            "aggregateAtEpochHex": aggregate.hex(),
            "sourceLinkCells": source_links,
            "sourceLinkMatched": source_linked,
            "prospectiveTraceTarget": source_linked,
        }
        records.append(record)
        if source_linked:
            if _state["sourceLinkedDepthFourEpochCount"] != 1:
                raise RuntimeError("more than one prospective source-linked epoch")
            _state["pendingCandidate"] = {
                "epochRecordIndex": record["recordIndex"],
                "identity": identity,
                "selectedSource": source,
                "initialAggregate": aggregate,
            }
            _state["trace"]["status"] = "prospective-selected-epoch-stopped"
            _write_trace()
            return True
        _write_trace()
    except Exception as error:
        _failure("source-known-depth-four-zero-epoch", error)
        if _state["epochBreakpoint"] is not None:
            _state["epochBreakpoint"].SetEnabled(False)
    return False


def prepare_layer_selection_marker(frame, _breakpoint_location, _internal_dict):
    """Reject an exact-source marker reached before its linked zero epoch."""
    try:
        _state["selectionMarkerHitCount"] += 1
        if _state["selectionMarkerHitCount"] > MAXIMUM_SELECTION_MARKER_HIT_COUNT:
            raise RuntimeError("instruction selection marker hit bound exceeded")
        exact = _exact_prepare_frames(frame.GetThread())
        source = _selected_source()
        x28 = capture_base._register(frame, "x28")
        if source is None or x28 != source:
            _state["rejectedSelectionMarkerHitCount"] += 1
            _record_marker_rejection(
                "selection",
                frame,
                "source-register-differs",
                exact,
                source=source,
                x28=x28,
            )
            return False
        if not _state["manualTraceStarted"]:
            raise RuntimeError("exact-source marker preceded source-linked epoch")
    except Exception as error:
        _failure("pretrace-selection-marker", error)
        if _state["selectionBreakpoint"] is not None:
            _state["selectionBreakpoint"].SetEnabled(False)
    return False


def _disable_all_breakpoints(target):
    if target.GetNumWatchpoints() != 0:
        raise RuntimeError("instruction trace target contains a watchpoint")
    if not target.DisableAllBreakpoints():
        raise RuntimeError("software breakpoint disable-all operation failed")
    records = []
    for index in range(target.GetNumBreakpoints()):
        breakpoint = target.GetBreakpointAtIndex(index)
        records.append(
            {
                "breakpointID": breakpoint.GetID(),
                "enabledAfterDisableAll": breakpoint.IsEnabled(),
                "locationCount": breakpoint.GetNumLocations(),
            }
        )
    if not records or any(item["enabledAfterDisableAll"] for item in records):
        raise RuntimeError("software breakpoint disablement differs")
    _state["trace"]["breakpointDisablement"] = {
        "callbackSequence": _next_sequence("all-software-breakpoints-disabled"),
        "watchpointCount": target.GetNumWatchpoints(),
        "breakpoints": records,
    }


def _selected_marker(frame, exact, aggregate):
    pending = _state["pendingCandidate"]
    identity = pending["identity"]
    source = pending["selectedSource"]
    _state["selectionMarkerHitCount"] += 1
    marker_hit_index = _state["selectionMarkerHitCount"]
    x28 = capture_base._register(frame, "x28")
    identity_matches = (
        frame.GetThread().GetThreadID() == identity["threadID"]
        and frame.GetFP() == identity["framePointer"]
        and capture_base._register(frame, "x19") == identity["roleBase"]
    )
    record = {
        "manualSelectionMarkerIndex": len(_state["trace"]["manualSelectionMarkers"]),
        "markerHitIndex": marker_hit_index,
        "pc": frame.GetPC(),
        "threadID": frame.GetThread().GetThreadID(),
        "framePointer": frame.GetFP(),
        "observedRoleBase": capture_base._register(frame, "x19"),
        "observedX28": x28,
        "selectedSource": source,
        "selectedIdentity": dict(identity),
        "prepareRecursionDepth": len(exact),
        "frameIdentityMatches": identity_matches,
        "sourceRegisterMatches": x28 == source,
        "result": "rejected",
    }
    if len(_state["trace"]["manualSelectionMarkers"]) >= (
        MAXIMUM_REJECTED_MARKER_DIAGNOSTIC_COUNT
    ):
        raise RuntimeError("manual selection marker record bound exceeded")
    if not identity_matches:
        _state["rejectedSelectionMarkerHitCount"] += 1
        _state["trace"]["manualSelectionMarkers"].append(record)
        _record_marker_rejection(
            "selection",
            frame,
            "selected-frame-identity-differs-during-manual-trace",
            exact,
            source=source,
            x28=x28,
        )
        _write_trace()
        return False
    if x28 != source:
        _state["rejectedSelectionMarkerHitCount"] += 1
        _state["trace"]["manualSelectionMarkers"].append(record)
        _record_marker_rejection(
            "selection",
            frame,
            "source-register-differs-during-manual-trace",
            exact,
            source=source,
            x28=x28,
        )
        _write_trace()
        return False
    if _state["semanticDODActive"] or not _state["semanticDODFinished"]:
        raise RuntimeError("selected marker preceded semantic DOD closure")
    crop_invocations = _state["trace"]["semanticCropInvocations"]
    crop_stores = _state["trace"]["semanticCropStoreLinks"]
    crop_unions = _state["trace"]["semanticCropUnionInputs"]
    if (
        _state["semanticCropActiveInvocationIndex"] is not None
        or _state["semanticCropCompletedInvocationCount"]
        != SEMANTIC_CROP_EXPECTED_INVOCATION_COUNT
        or len(crop_invocations) != SEMANTIC_CROP_EXPECTED_INVOCATION_COUNT
        or len(crop_stores) != SEMANTIC_CROP_EXPECTED_INVOCATION_COUNT - 1
        or len(crop_unions) != SEMANTIC_CROP_EXPECTED_INVOCATION_COUNT - 1
        or [item["storeLinkIndex"] for item in crop_invocations] != [0, 1, 2, None]
        or crop_invocations[-1]["callerRoleBase"] != identity["roleBase"]
        or crop_invocations[-1]["targetAddress"]
        != identity["roleBase"] + capture_base.AGGREGATE_OFFSET
    ):
        raise RuntimeError("selected marker preceded semantic crop closure")
    # Reuse the inherited marker recorder directly while the physical
    # breakpoint remains disabled.  This closes its independent source/frame
    # context without reintroducing a stop collision.
    frame_base.live_selection_marker(frame, None, {})
    inherited_selected = frame_base._state["trace"].get("selectedFrame", {})
    if not inherited_selected:
        raise RuntimeError("inherited marker context did not close")
    process = frame.GetThread().GetProcess()
    role, role_record = _memory_payload(
        process,
        identity["roleBase"],
        capture_base.ROLE_STATE_BYTE_COUNT,
        "instruction selected marker role",
    )
    if (
        role[
            capture_base.AGGREGATE_OFFSET : capture_base.AGGREGATE_OFFSET
            + capture_base.AGGREGATE_BYTE_COUNT
        ]
        != aggregate
    ):
        raise RuntimeError("instruction marker aggregate alias differs")
    registers = capture_base._register_snapshot(frame, SELECTION_FRAME_REGISTER_NAMES)
    sequence = _next_sequence("selected-instruction-path-closed")
    record["result"] = "selected"
    record["callbackSequence"] = sequence
    _state["trace"]["manualSelectionMarkers"].append(record)
    _state["trace"]["selectedFrame"] = {
        "callbackSequence": sequence,
        "markerHitIndex": marker_hit_index,
        "manualSelectionMarkerIndex": record["manualSelectionMarkerIndex"],
        "pc": frame.GetPC(),
        "frame": capture_base._frame_record(frame, process.GetTarget()),
        "backtrace": capture_base._backtrace(frame.GetThread()),
        "registers": registers,
        "prepareRecursionDepth": len(exact),
        "prepareFrames": _public_prepare_frames(exact, process.GetTarget()),
        "frameIdentity": dict(identity),
        "selectedSource": source,
        "selectedEpochRecordIndex": pending["epochRecordIndex"],
        "instructionStepCount": len(_state["trace"]["instructionSteps"]),
        "aggregateTransitionCount": len(_state["trace"]["aggregateTransitions"]),
        "roleStateAtMarker": role_record,
        "aggregateAtMarkerHex": aggregate.hex(),
        "objectChain": json.loads(
            json.dumps(frame_base._state["trace"]["objectChain"])
        ),
    }
    _state["manualTraceFinished"] = True
    _state["trace"]["status"] = "selected-software-instruction-path-closed"
    _write_trace()
    return True


def _trace_one_instruction(thread, frame, scope, before):
    process = thread.GetProcess()
    instruction = _instruction_record(frame, scope)
    _semantic_state_before(frame, instruction, before)
    _semantic_crop_state_before(frame, instruction, before)
    crop_store = _crop_store_before(frame, instruction)
    _crop_union_input_before(frame, instruction)
    context = None
    if instruction["potentialWriter"] or instruction["potentialCall"]:
        observed, context = _candidate_context(
            frame,
            _state["pendingCandidate"]["identity"],
            "instruction before",
        )
        if observed != before:
            raise RuntimeError("instruction candidate before aggregate differs")
    error = lldb.SBError()
    thread.StepInstruction(False, error)
    if not error.Success():
        raise RuntimeError(error.GetCString() or "single instruction failed")
    _require_stopped(process, "single instruction")
    current_thread = _thread_for_identity(
        process, _state["pendingCandidate"]["identity"]
    )
    result_frame = current_thread.GetFrameAtIndex(0)
    after = _aggregate(
        process,
        _state["pendingCandidate"]["identity"],
        "aggregate after single instruction",
    )
    if after != before and context is None:
        raise RuntimeError(
            "aggregate changed at an instruction not decoded as writer or call"
        )
    _record_step(
        "scope-instruction",
        before,
        after,
        instruction=instruction,
        result_frame=result_frame,
        before_context=context,
    )
    _finish_semantic_instruction(instruction, result_frame, after)
    _finish_semantic_crop_instruction(instruction, result_frame, after)
    _finish_crop_store(crop_store, result_frame)
    return current_thread, result_frame, after


def _trace_opaque_callee(thread, frame, before):
    process = thread.GetProcess()
    boundaries = _state["trace"]["opaqueCalleeBoundaries"]
    if len(boundaries) >= MAXIMUM_OPAQUE_CALLEE_COUNT:
        raise RuntimeError("opaque callee boundary bound exceeded")
    observed, context = _candidate_context(
        frame,
        _state["pendingCandidate"]["identity"],
        "opaque callee before",
    )
    if observed != before:
        raise RuntimeError("opaque callee before aggregate differs")
    crop_index = _state["semanticCropActiveInvocationIndex"]
    crop_target_before = None
    if crop_index is not None:
        invocation = _state["trace"]["semanticCropInvocations"][crop_index]
        crop_target_before = _crop_memory(
            process,
            invocation["targetAddress"],
            SEMANTIC_CROP_TARGET_BYTE_COUNT,
            "semantic crop opaque target before",
        )
    entry = capture_base._frame_record(frame, process.GetTarget())
    error = lldb.SBError()
    thread.StepOut(error)
    if not error.Success():
        raise RuntimeError(error.GetCString() or "opaque callee step-out failed")
    _require_stopped(process, "opaque callee step-out")
    current_thread = _thread_for_identity(
        process, _state["pendingCandidate"]["identity"]
    )
    result_frame = current_thread.GetFrameAtIndex(0)
    after = _aggregate(
        process,
        _state["pendingCandidate"]["identity"],
        "aggregate after opaque callee",
    )
    opaque = {
        "boundaryIndex": len(boundaries),
        "entryFrame": entry,
        "returnFrame": capture_base._frame_record(result_frame, process.GetTarget()),
        "aggregateChanged": before != after,
    }
    if crop_index is not None:
        if _state["semanticCropActiveInvocationIndex"] != crop_index:
            raise RuntimeError("semantic crop invocation changed across opaque callee")
        crop_target_after = _crop_memory(
            process,
            invocation["targetAddress"],
            SEMANTIC_CROP_TARGET_BYTE_COUNT,
            "semantic crop opaque target after",
        )
        opaque.update(
            {
                "semanticCropInvocationIndex": crop_index,
                "semanticCropTargetBefore": crop_target_before,
                "semanticCropTargetAfter": crop_target_after,
                "semanticCropTargetChanged": (
                    crop_target_before["hex"] != crop_target_after["hex"]
                ),
            }
        )
    boundaries.append(opaque)
    _record_step(
        "opaque-callee-step-out",
        before,
        after,
        result_frame=result_frame,
        before_context=context,
        opaque=opaque,
    )
    return current_thread, result_frame, after


def _continue_to_terminal(process):
    unexpected = []
    for _attempt in range(MAXIMUM_UNEXPECTED_TERMINAL_CONTINUE_COUNT):
        state = process.GetState()
        if state in (lldb.eStateExited, lldb.eStateDetached):
            break
        error = process.Continue()
        if error is not None and hasattr(error, "Success") and not error.Success():
            raise RuntimeError(error.GetCString() or "terminal continue failed")
        state = process.GetState()
        if state in (lldb.eStateExited, lldb.eStateDetached):
            break
        unexpected.append(
            {
                "state": int(state),
                "selectedThreadStopReason": int(
                    process.GetSelectedThread().GetStopReason()
                ),
            }
        )
    state = process.GetState()
    _state["trace"]["terminalProcess"] = {
        "state": int(state),
        "exited": state == lldb.eStateExited,
        "detached": state == lldb.eStateDetached,
        "exitStatus": process.GetExitStatus() if state == lldb.eStateExited else None,
        "unexpectedStops": unexpected,
    }
    if state != lldb.eStateExited or process.GetExitStatus() != 0 or unexpected:
        raise RuntimeError("capture target did not exit normally after trace")


def trace_selected_path():
    """Drive the first dual-source-linked epoch to its exact marker."""
    trace = _state["trace"]
    if trace is None:
        return
    process = _state["debugger"].GetSelectedTarget().GetProcess()
    try:
        if _state["manualTraceStarted"]:
            raise RuntimeError("selected instruction trace was invoked twice")
        pending = _state["pendingCandidate"]
        if pending is None:
            raise RuntimeError("prospective source-linked epoch was not reached")
        _require_stopped(process, "prospective source-linked epoch")
        _state["manualTraceStarted"] = True
        _state["debugger"].SetAsync(False)
        if _state["debugger"].GetAsync():
            raise RuntimeError("debugger remained asynchronous before stepping")
        _disable_all_breakpoints(process.GetTarget())
        sequence = _next_sequence("selected-instruction-stepping-started")
        trace["manualTraceStart"] = {
            "callbackSequence": sequence,
            "epochRecordIndex": pending["epochRecordIndex"],
            "identity": dict(pending["identity"]),
            "selectedSource": pending["selectedSource"],
            "debuggerAsyncAfterSynchronousSet": _state["debugger"].GetAsync(),
        }
        thread = _thread_for_identity(process, pending["identity"])
        frame = thread.GetFrameAtIndex(0)
        current = _aggregate(
            process, pending["identity"], "manual trace initial aggregate"
        )
        if current != pending["initialAggregate"]:
            raise RuntimeError("manual trace initial aggregate differs from epoch")
        while len(trace["instructionSteps"]) < MAXIMUM_INSTRUCTION_STEP_COUNT:
            thread = _thread_for_identity(process, pending["identity"])
            exact = _exact_prepare_frames(thread)
            _ordinal, matched = _matching_identity(
                exact, pending["identity"], thread.GetThreadID()
            )
            if matched is None:
                raise RuntimeError("selected prepare frame returned before marker")
            frame = thread.GetFrameAtIndex(0)
            if frame.GetPC() == _state["prepareLayer"][
                "symbolStart"
            ] + SELECTION_MARKER_OFFSET and _selected_marker(frame, exact, current):
                break
            scope = _scope_for_pc(frame.GetPC())
            if scope is None:
                thread, frame, current = _trace_opaque_callee(thread, frame, current)
            else:
                thread, frame, current = _trace_one_instruction(
                    thread, frame, scope, current
                )
        else:
            raise RuntimeError("instruction step bound exceeded before marker")
        if not _state["manualTraceFinished"]:
            raise RuntimeError("instruction path did not close at selected marker")
        if _state["semanticDODActive"] or not _state["semanticDODFinished"]:
            raise RuntimeError("semantic DOD invocation did not close")
        if (
            _state["semanticCropActiveInvocationIndex"] is not None
            or _state["semanticCropCompletedInvocationCount"]
            != SEMANTIC_CROP_EXPECTED_INVOCATION_COUNT
        ):
            raise RuntimeError("semantic crop invocations did not close")
    except Exception as error:
        _failure("selected-instruction-path", error)
        trace["status"] = "selected-instruction-path-failed"
    finally:
        try:
            process.GetTarget().DisableAllBreakpoints()
            _continue_to_terminal(process)
        except Exception as error:
            _failure("terminal-process", error)
        _write_trace()


def finalize():
    """Finalize independent context plus software-instruction accounting."""
    frame_base.finalize()
    trace = _state["trace"]
    if trace is None:
        return
    trace["statusBeforeFinalization"] = trace["status"]
    trace["status"] = "finalized"
    trace["finalFailureCount"] = len(trace["failures"])
    trace["finalCallbackSequence"] = _state["callbackSequence"]
    trace["epochMarkerHitCount"] = _state["epochMarkerHitCount"]
    trace["sourceUnknownEpochCount"] = _state["sourceUnknownEpochCount"]
    trace["rejectedEpochDepthCount"] = _state["rejectedEpochDepthCount"]
    trace["sourceKnownDepthFourEpochCount"] = _state["sourceKnownDepthFourEpochCount"]
    trace["sourceLinkedDepthFourEpochCount"] = _state["sourceLinkedDepthFourEpochCount"]
    trace["rejectedSourceLinkEpochCount"] = _state["rejectedSourceLinkEpochCount"]
    trace["discardedEpochRecordCount"] = _state["discardedEpochRecordCount"]
    trace["finalEpochRecordCount"] = len(trace["epochRecords"])
    trace["selectionMarkerHitCount"] = _state["selectionMarkerHitCount"]
    trace["rejectedSelectionMarkerHitCount"] = _state["rejectedSelectionMarkerHitCount"]
    trace["unretainedRejectedMarkerDiagnosticCount"] = _state[
        "unretainedRejectedMarkerDiagnosticCount"
    ]
    trace["finalRejectedMarkerDiagnosticCount"] = len(
        trace["rejectedMarkerDiagnostics"]
    )
    trace["inheritedWriterBreakpointsRetired"] = _state[
        "inheritedWriterBreakpointsRetired"
    ]
    trace["manualTraceStarted"] = _state["manualTraceStarted"]
    trace["manualTraceFinished"] = _state["manualTraceFinished"]
    trace["finalInstructionStepCount"] = len(trace["instructionSteps"])
    trace["finalAggregateTransitionCount"] = len(trace["aggregateTransitions"])
    trace["finalOpaqueCalleeBoundaryCount"] = len(trace["opaqueCalleeBoundaries"])
    trace["finalManualSelectionMarkerRecordCount"] = len(
        trace["manualSelectionMarkers"]
    )
    trace["finalChangedOpaqueCalleeBoundaryCount"] = sum(
        item["aggregateChanged"] for item in trace["opaqueCalleeBoundaries"]
    )
    trace["semanticDODActive"] = _state["semanticDODActive"]
    trace["semanticDODFinished"] = _state["semanticDODFinished"]
    trace["finalSemanticDODEntryCount"] = len(trace["semanticDODEntries"])
    trace["finalSemanticDODInstructionStateCount"] = len(
        trace["semanticDODInstructionStates"]
    )
    trace["semanticCropActiveInvocationIndex"] = _state[
        "semanticCropActiveInvocationIndex"
    ]
    trace["semanticCropCompletedInvocationCount"] = _state[
        "semanticCropCompletedInvocationCount"
    ]
    trace["finalSemanticCropInvocationCount"] = len(trace["semanticCropInvocations"])
    trace["finalSemanticCropInstructionStateCount"] = len(
        trace["semanticCropInstructionStates"]
    )
    trace["finalSemanticCropStoreLinkCount"] = len(trace["semanticCropStoreLinks"])
    trace["finalSemanticCropUnionInputCount"] = len(trace["semanticCropUnionInputs"])
    states = []
    pending = _state["pendingCandidate"]
    if pending is not None:
        states.append(pending["initialAggregate"].hex())
        states.extend(step["aggregateAfterHex"] for step in trace["instructionSteps"])
    trace["finalDistinctAggregateStateCount"] = len(set(states))
    _write_trace()


def __lldb_init_module(debugger, internal_dict):
    """Reuse independent source/frame setup and add prospective stepping."""
    frame_base.__lldb_init_module(debugger, internal_dict)
    _reset_state()
    _state["debugger"] = debugger
    _state["trace"] = _new_trace()
    capture = frame_base._state["captureEntryBreakpoint"]
    prepare = frame_base._state["prepareEntryBreakpoint"]
    if (
        capture is None
        or not capture.IsValid()
        or prepare is None
        or not prepare.IsValid()
    ):
        _failure("initialization", "inherited instruction entry breakpoint is invalid")
        return
    _set_callback(
        capture,
        "forwarded_capture_backdrop_entry",
        "forwarded inherited capture_backdrop entry",
    )
    _set_callback(
        prepare,
        "multiplexed_prepare_layer_entry",
        "shared instruction prepare_layer entry",
    )
    _state["prepareEntryBreakpoint"] = prepare
    _state["trace"]["prepareLayerEntryBreakpointID"] = prepare.GetID()
    _write_trace()
