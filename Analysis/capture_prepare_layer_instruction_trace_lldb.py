"""Single-step the selected ``prepare_layer`` aggregate dependency path.

The preceding hardware-watch experiment proved that one LLDB watch callback
does not imply one architectural store on Apple silicon.  This successor uses
no hardware watchpoints.  It stops at the prospectively fixed selected epoch,
disables every software breakpoint, and advances the selected thread one
instruction at a time through ``prepare_layer`` and the six already opened
QuartzCore helpers.  Calls outside that frozen scope are stepped out as named
boundaries and must not change the aggregate for the gate to pass.
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

TRACE_SCHEMA_VERSION = 1
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
TARGET_SOURCE_KNOWN_DEPTH_FOUR_EPOCH_ORDINAL = 7
MAXIMUM_EPOCH_MARKER_HIT_COUNT = 4096
MAXIMUM_EPOCH_RECORD_COUNT = 128
MAXIMUM_SELECTION_MARKER_HIT_COUNT = 4096
MAXIMUM_REJECTED_MARKER_DIAGNOSTIC_COUNT = 128
MAXIMUM_INSTRUCTION_STEP_COUNT = 250000
MAXIMUM_OPAQUE_CALLEE_COUNT = 8192
MAXIMUM_UNEXPECTED_TERMINAL_CONTINUE_COUNT = 8
KNOWN_CANVAS_EXTENT = 1024.0
KNOWN_GLASS_EXTENT = 640.0
KNOWN_EDGE_PADDING = 8.0
IDENTITY_FRAME_REGISTER_NAMES = ("x19", "x29", "pc")
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
DEFAULT_TRACE_OUTPUT = (
    "transition-introspection/prepare-layer-instruction-trace.json"
)

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
        "name": "filterApply",
        "function": (
            "CA::Render::Updater::FilterOp::apply_filter(CA::Rect&, bool)"
        ),
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
        "discardedEpochRecordCount": 0,
        "selectionMarkerHitCount": 0,
        "rejectedSelectionMarkerHitCount": 0,
        "unretainedRejectedMarkerDiagnosticCount": 0,
        "inheritedWriterBreakpointsRetired": False,
        "pendingCandidate": None,
        "manualTraceStarted": False,
        "manualTraceFinished": False,
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
            "preregistered-selected-epoch-software-instruction-trace; "
            "hardware-watch-callback-coalescing-eliminated; crop-policy-"
            "generalization-unseen-transfer-and-product-parity-remain-sealed"
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
            "targetSourceKnownDepthFourEpochOrdinal": (
                TARGET_SOURCE_KNOWN_DEPTH_FOUR_EPOCH_ORDINAL
            ),
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
            "knownCanvasExtent": KNOWN_CANVAS_EXTENT,
            "knownGlassExtent": KNOWN_GLASS_EXTENT,
            "knownEdgePadding": KNOWN_EDGE_PADDING,
            "identityFrameRegisterNames": list(IDENTITY_FRAME_REGISTER_NAMES),
            "selectionFrameRegisterNames": list(SELECTION_FRAME_REGISTER_NAMES),
            "structuralFramePointerSource": "SBFrame.GetFP",
            "retiredInheritedWriterSiteNames": list(
                RETIRED_INHERITED_WRITER_SITE_NAMES
            ),
            "retainedControlBreakpointNames": list(
                RETAINED_CONTROL_BREAKPOINT_NAMES
            ),
            "checkpointScopes": _scope_configuration(),
            "writerMnemonicPrefixes": list(WRITER_MNEMONIC_PREFIXES),
            "callMnemonicPrefixes": list(CALL_MNEMONIC_PREFIXES),
            "frameTraceOutputEnvironment": frame_base.TRACE_OUTPUT_ENVIRONMENT,
            "frameTraceSchemaVersion": frame_base.TRACE_SCHEMA_VERSION,
            "selectionRule": (
                "stop only at the seventh source-known exact-depth-four zero "
                "epoch fixed by run 31034880031, then require the same live "
                "thread/x19/x29 identity and future x28 source at +0x3ef0"
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
    _state["trace"]["failures"].append(
        {"stage": str(stage), "message": str(error)}
    )
    _write_trace()


def _next_sequence(kind):
    _state["callbackSequence"] += 1
    sequence = _state["callbackSequence"]
    _state["trace"]["callbackOrder"].append(
        {"sequence": sequence, "kind": str(kind)}
    )
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
            or code[
                SELECTION_MARKER_OFFSET : SELECTION_MARKER_OFFSET + 4
            ].hex()
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
    """Stop only at the prospectively fixed selected-depth epoch ordinal."""
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
        registers = capture_base._register_snapshot(
            frame, IDENTITY_FRAME_REGISTER_NAMES
        )
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
            "prospectiveTraceTarget": (
                ordinal == TARGET_SOURCE_KNOWN_DEPTH_FOUR_EPOCH_ORDINAL
            ),
        }
        records.append(record)
        if ordinal == TARGET_SOURCE_KNOWN_DEPTH_FOUR_EPOCH_ORDINAL:
            _state["pendingCandidate"] = {
                "epochRecordIndex": record["recordIndex"],
                "identity": identity,
                "selectedSource": source,
                "initialAggregate": aggregate,
            }
            _state["trace"]["status"] = "prospective-selected-epoch-stopped"
            _write_trace()
            return True
        if ordinal > TARGET_SOURCE_KNOWN_DEPTH_FOUR_EPOCH_ORDINAL:
            raise RuntimeError("prospective selected epoch ordinal was bypassed")
        _write_trace()
    except Exception as error:
        _failure("source-known-depth-four-zero-epoch", error)
        if _state["epochBreakpoint"] is not None:
            _state["epochBreakpoint"].SetEnabled(False)
    return False


def prepare_layer_selection_marker(frame, _breakpoint_location, _internal_dict):
    """Reject any exact-source selection reached before the frozen epoch."""
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
            raise RuntimeError("exact-source marker preceded prospective epoch")
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
    if frame.GetFP() != identity["framePointer"]:
        return False
    x28 = capture_base._register(frame, "x28")
    if x28 != source:
        raise RuntimeError("prospective epoch reached marker with different source")
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
    registers = capture_base._register_snapshot(
        frame, SELECTION_FRAME_REGISTER_NAMES
    )
    sequence = _next_sequence("selected-instruction-path-closed")
    _state["trace"]["selectedFrame"] = {
        "callbackSequence": sequence,
        "markerHitIndex": _state["selectionMarkerHitCount"] + 1,
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
        "aggregateTransitionCount": len(
            _state["trace"]["aggregateTransitions"]
        ),
        "roleStateAtMarker": role_record,
        "aggregateAtMarkerHex": aggregate.hex(),
        "objectChain": json.loads(
            json.dumps(frame_base._state["trace"]["objectChain"])
        ),
    }
    _state["selectionMarkerHitCount"] += 1
    _state["manualTraceFinished"] = True
    _state["trace"]["status"] = "selected-software-instruction-path-closed"
    _write_trace()
    return True


def _trace_one_instruction(thread, frame, scope, before):
    process = thread.GetProcess()
    instruction = _instruction_record(frame, scope)
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
        "returnFrame": capture_base._frame_record(
            result_frame, process.GetTarget()
        ),
        "aggregateChanged": before != after,
    }
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
    """Drive the stopped selected epoch to its exact-source marker."""
    trace = _state["trace"]
    if trace is None:
        return
    process = _state["debugger"].GetSelectedTarget().GetProcess()
    try:
        if _state["manualTraceStarted"]:
            raise RuntimeError("selected instruction trace was invoked twice")
        pending = _state["pendingCandidate"]
        if pending is None:
            raise RuntimeError("prospective selected epoch was not reached")
        _require_stopped(process, "prospective selected epoch")
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
            if (
                frame.GetPC()
                == _state["prepareLayer"]["symbolStart"]
                + SELECTION_MARKER_OFFSET
                and _selected_marker(frame, exact, current)
            ):
                break
            scope = _scope_for_pc(frame.GetPC())
            if scope is None:
                thread, frame, current = _trace_opaque_callee(
                    thread, frame, current
                )
            else:
                thread, frame, current = _trace_one_instruction(
                    thread, frame, scope, current
                )
        else:
            raise RuntimeError("instruction step bound exceeded before marker")
        if not _state["manualTraceFinished"]:
            raise RuntimeError("instruction path did not close at selected marker")
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
    trace["sourceKnownDepthFourEpochCount"] = _state[
        "sourceKnownDepthFourEpochCount"
    ]
    trace["discardedEpochRecordCount"] = _state["discardedEpochRecordCount"]
    trace["finalEpochRecordCount"] = len(trace["epochRecords"])
    trace["selectionMarkerHitCount"] = _state["selectionMarkerHitCount"]
    trace["rejectedSelectionMarkerHitCount"] = _state[
        "rejectedSelectionMarkerHitCount"
    ]
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
    trace["finalOpaqueCalleeBoundaryCount"] = len(
        trace["opaqueCalleeBoundaries"]
    )
    trace["finalChangedOpaqueCalleeBoundaryCount"] = sum(
        item["aggregateChanged"] for item in trace["opaqueCalleeBoundaries"]
    )
    states = []
    pending = _state["pendingCandidate"]
    if pending is not None:
        states.append(pending["initialAggregate"].hex())
        states.extend(
            step["aggregateAfterHex"] for step in trace["instructionSteps"]
        )
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
