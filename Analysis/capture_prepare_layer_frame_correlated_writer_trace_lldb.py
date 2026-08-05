"""Capture early aggregate writers and correlate them to a later live frame.

Run 30960697537 proved that x28 does not identify the selected source when the
early stores execute.  This probe records the exact opened writer after-sites
before the first ``prepare_layer`` invocation resumes, then selects only the
suffix belonging to the live +0x3ef0 frame by thread ID, x19, and x29.
"""

import hashlib
import json
import os
import struct
import sys
from pathlib import Path

import lldb


ANALYSIS_ROOT = Path(__file__).resolve().parent
if str(ANALYSIS_ROOT) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_ROOT))
import capture_prepare_layer_full_path_trace_lldb as capture_base  # noqa: E402


TRACE_SCHEMA_VERSION = 1
PREPARE_LAYER_FULL_CODE_SHA256 = (
    "fe58001369708e0276599f26865be03fdf1dd2348524f92a72c1427be8d1817c"
)
LIVE_SELECTION_MARKER_NAME = "sourceLaterHandle"
LIVE_SELECTION_MARKER_OFFSET = 0x3EF0
PREPARE_FRAME_REGISTER_NAMES = ("x19", "x28", "x29", "x30", "sp", "pc")
MAXIMUM_WRITER_SITE_HIT_COUNT = 4096
MAXIMUM_RECORD_COUNT_PER_WRITER_SITE = 512
MAXIMUM_LIVE_SELECTION_MARKER_HIT_COUNT = 4096
MAXIMUM_PRESELECTION_MARKER_DIAGNOSTIC_COUNT = 32
MAXIMUM_REJECTED_WRITER_DIAGNOSTIC_COUNT = 64
TRACE_OUTPUT_ENVIRONMENT = "LG_PREPARE_LAYER_FRAME_WRITER_TRACE_OUTPUT"
DEFAULT_TRACE_OUTPUT = "transition-introspection/prepare-layer-frame-writer-trace.json"

WRITER_SITES = (
    {
        "name": "rectApplyTransformAfter",
        "relativeToPrepareLayer": -1207012,
        "function": "CA::Rect::apply_transform(CA::SimpleTransform const&)",
        "epochStart": False,
        "openedByHardwareWatchpoint": True,
    },
    {
        "name": "rectUnapplyTransformAfter",
        "relativeToPrepareLayer": -1202604,
        "function": "CA::Rect::unapply_transform(CA::SimpleTransform const&)",
        "epochStart": False,
        "openedByHardwareWatchpoint": True,
    },
    {
        "name": "glassDODAfter0",
        "relativeToPrepareLayer": -90080,
        "function": (
            "CA::OGL::GlassBackgroundFilter::DOD(CA::Render::Filter const*, "
            "CA::Render::Layer const*, CA::Rect&) const"
        ),
        "epochStart": False,
        "openedByHardwareWatchpoint": True,
    },
    {
        "name": "glassDODAfter1",
        "relativeToPrepareLayer": -89720,
        "function": (
            "CA::OGL::GlassBackgroundFilter::DOD(CA::Render::Filter const*, "
            "CA::Render::Layer const*, CA::Rect&) const"
        ),
        "epochStart": False,
        "openedByHardwareWatchpoint": True,
    },
    {
        "name": "glassDODAfter2",
        "relativeToPrepareLayer": -89512,
        "function": (
            "CA::OGL::GlassBackgroundFilter::DOD(CA::Render::Filter const*, "
            "CA::Render::Layer const*, CA::Rect&) const"
        ),
        "epochStart": False,
        "openedByHardwareWatchpoint": True,
    },
    {
        "name": "unionBoundsStoreAfter",
        "relativeToPrepareLayer": -2588,
        "function": capture_base.UNION_HELPER_SYMBOL_NAME,
        "epochStart": False,
        "openedByHardwareWatchpoint": True,
        "precedingInstructionRelativeToPrepareLayer": -2592,
        "precedingInstructionRawLittleEndianHex": "800600ad",
    },
    {
        "name": "zeroInitializationAfter",
        "relativeToPrepareLayer": 0xB60,
        "function": capture_base.PREPARE_LAYER_FUNCTION,
        "epochStart": True,
        "openedByHardwareWatchpoint": True,
        "precedingInstructionRelativeToPrepareLayer": 0xB5C,
        "precedingInstructionRawLittleEndianHex": "60a6803d",
    },
    {
        "name": "alternateAggregateCopyAfter",
        "relativeToPrepareLayer": 0x33F4,
        "function": capture_base.PREPARE_LAYER_FUNCTION,
        "epochStart": False,
        "openedByHardwareWatchpoint": False,
        "precedingInstructionRelativeToPrepareLayer": 0x33F0,
        "precedingInstructionRawLittleEndianHex": "608614ad",
    },
    {
        "name": "rangeClampStoreAfter",
        "relativeToPrepareLayer": 0x3974,
        "function": capture_base.PREPARE_LAYER_FUNCTION,
        "epochStart": False,
        "openedByHardwareWatchpoint": True,
        "precedingInstructionRelativeToPrepareLayer": 0x3970,
        "precedingInstructionRawLittleEndianHex": "608614ad",
    },
)


def _fresh_state():
    return {
        "debugger": None,
        "trace": None,
        "captureEntryBreakpoint": None,
        "captureLateBreakpoint": None,
        "prepareEntryBreakpoint": None,
        "selectionMarkerBreakpoint": None,
        "writerBreakpoints": {},
        "writerSiteByAddress": {},
        "prepareLayer": None,
        "objectAddresses": {},
        "lateCandidateCount": 0,
        "callbackSequence": 0,
        "writerSiteHitCounts": {site["name"]: 0 for site in WRITER_SITES},
        "rejectedWriterSiteHitCounts": {
            site["name"]: 0 for site in WRITER_SITES
        },
        "discardedWriterSiteHitCounts": {
            site["name"]: 0 for site in WRITER_SITES
        },
        "rejectedWriterGroups": {},
        "unretainedRejectedWriterHitCount": 0,
        "lastCandidateByFrame": {},
        "selectionMarkerHitCount": 0,
        "rejectedSelectionMarkerHitCount": 0,
        "discardedSelectionMarkerHitCount": 0,
    }


_state = _fresh_state()
capture_base._state = _state


def _reset_state():
    _state.clear()
    _state.update(_fresh_state())
    capture_base._state = _state


def _trace_path():
    return Path(os.environ.get(TRACE_OUTPUT_ENVIRONMENT, DEFAULT_TRACE_OUTPUT))


def _new_trace():
    return {
        "prepareLayerFrameWriterTraceSchemaVersion": TRACE_SCHEMA_VERSION,
        "classification": (
            "preregistered-still-live-frame-correlated-prepare-layer-writer-"
            "trace; writer-semantics-public-crop-law-unseen-transfer-and-"
            "product-parity-remain-sealed"
        ),
        "status": "initialized",
        "configuration": {
            "captureBackdropSymbol": capture_base.CAPTURE_BACKDROP_SYMBOL,
            "captureBackdropCodeByteCount": capture_base.CAPTURE_BACKDROP_CODE_BYTE_COUNT,
            "captureBackdropCodeSHA256": capture_base.CAPTURE_BACKDROP_CODE_SHA256,
            "captureBackdropLateOffset": capture_base.CAPTURE_BACKDROP_LATE_OFFSET,
            "prepareLayerFunction": capture_base.PREPARE_LAYER_FUNCTION,
            "prepareLayerSymbolByteCount": capture_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            "prepareLayerFullCodeSHA256": PREPARE_LAYER_FULL_CODE_SHA256,
            "knownPrepareLayerWindows": [
                {"offset": offset, "byteCount": count, "sha256": digest}
                for offset, count, digest in capture_base.KNOWN_PREPARE_LAYER_WINDOWS
            ],
            "unionHelperRelativeToPrepareLayer": (
                capture_base.UNION_HELPER_RELATIVE_TO_PREPARE_LAYER
            ),
            "unionHelperSymbolName": capture_base.UNION_HELPER_SYMBOL_NAME,
            "unionHelperSymbolByteCount": capture_base.UNION_HELPER_SYMBOL_BYTE_COUNT,
            "unionHelperSymbolSHA256": capture_base.UNION_HELPER_SYMBOL_SHA256,
            "liveSelectionMarkerName": LIVE_SELECTION_MARKER_NAME,
            "liveSelectionMarkerOffset": LIVE_SELECTION_MARKER_OFFSET,
            "writerSites": [dict(site) for site in WRITER_SITES],
            "maximumWriterSiteHitCount": MAXIMUM_WRITER_SITE_HIT_COUNT,
            "maximumRecordCountPerWriterSite": MAXIMUM_RECORD_COUNT_PER_WRITER_SITE,
            "maximumLiveSelectionMarkerHitCount": (
                MAXIMUM_LIVE_SELECTION_MARKER_HIT_COUNT
            ),
            "maximumPreselectionMarkerDiagnosticCount": (
                MAXIMUM_PRESELECTION_MARKER_DIAGNOSTIC_COUNT
            ),
            "maximumRejectedWriterDiagnosticCount": (
                MAXIMUM_REJECTED_WRITER_DIAGNOSTIC_COUNT
            ),
            "roleStateByteCount": capture_base.ROLE_STATE_BYTE_COUNT,
            "aggregateOffset": capture_base.AGGREGATE_OFFSET,
            "aggregateByteCount": capture_base.AGGREGATE_BYTE_COUNT,
            "prepareFrameRegisterNames": list(PREPARE_FRAME_REGISTER_NAMES),
            "maximumLateCandidateCount": capture_base.MAXIMUM_LATE_CANDIDATE_COUNT,
            "maximumLateCandidateDiagnosticCount": (
                capture_base.MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT
            ),
            "maximumBacktraceFrameCount": capture_base.MAXIMUM_BACKTRACE_FRAME_COUNT,
            "pcCenteredCodeWindowByteCount": (
                capture_base.PC_CENTERED_CODE_WINDOW_BYTE_COUNT
            ),
            "pcCenteredCodeWindowBacktrack": (
                capture_base.PC_CENTERED_CODE_WINDOW_BACKTRACK
            ),
            "stackSnapshotByteCount": capture_base.STACK_SNAPSHOT_BYTE_COUNT,
            "registerPointerSnapshotByteCount": (
                capture_base.REGISTER_POINTER_SNAPSHOT_BYTE_COUNT
            ),
            "registerPointerSnapshotBacktrack": (
                capture_base.REGISTER_POINTER_SNAPSHOT_BACKTRACK
            ),
            "pointerProbeAddressRange": [
                capture_base.MINIMUM_POINTER_PROBE_ADDRESS,
                capture_base.MAXIMUM_POINTER_PROBE_ADDRESS,
            ],
            "generalRegisterNames": list(capture_base.GENERAL_REGISTER_NAMES),
            "simdRegisterNames": list(capture_base.SIMD_REGISTER_NAMES),
            "pointerProbeRegisterNames": list(
                capture_base.POINTER_PROBE_REGISTER_NAMES
            ),
            "objectSnapshotSpecs": [
                {"base": base, "byteCount": byte_count}
                for base, byte_count in capture_base.OBJECT_SNAPSHOT_SPECS
            ],
            "frameCorrelationRule": (
                "at the first source-known +0x3ef0 marker whose x28 is the "
                "selected source, select only the writer suffix with identical "
                "thread ID, x19 role base, and x29 frame pointer, beginning at "
                "that frame identity's latest +0xb60 epoch-start record"
            ),
        },
        "callbackOrder": [],
        "captureBackdrop": {},
        "prepareLayer": {},
        "lateCandidateCount": 0,
        "lateCandidateDiagnostics": [],
        "objectChain": {},
        "writerCandidateEvents": [],
        "rejectedWriterDiagnostics": [],
        "preselectionMarkerDiagnostics": [],
        "selectedFrame": {},
        "selectedWriterEventIndices": [],
        "codeWindows": [],
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


def _address_breakpoint(target, address, callback, label):
    breakpoint = target.BreakpointCreateByAddress(address)
    if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
        raise RuntimeError(label + " breakpoint is unresolved")
    _set_callback(breakpoint, callback, label)
    return breakpoint


def _breakpoint_location_addresses(breakpoint, target):
    return [
        breakpoint.GetLocationAtIndex(index).GetAddress().GetLoadAddress(target)
        for index in range(breakpoint.GetNumLocations())
    ]


def _selected_source():
    return _state["objectAddresses"].get("source")


def _disable_internal_breakpoints():
    marker = _state["selectionMarkerBreakpoint"]
    if marker is not None:
        marker.SetEnabled(False)
    for breakpoint in _state["writerBreakpoints"].values():
        breakpoint.SetEnabled(False)


def _top_operand_snapshot(frame):
    process = frame.GetThread().GetProcess()
    registers = capture_base._full_register_snapshot(frame)
    general = {item["name"]: item for item in registers["general"]}
    stack_pointer = general["sp"]["unsignedValue"]
    pointer_registers = {}
    for name in capture_base.POINTER_PROBE_REGISTER_NAMES:
        address = general[name]["unsignedValue"]
        if not (
            capture_base.MINIMUM_POINTER_PROBE_ADDRESS
            <= address
            <= capture_base.MAXIMUM_POINTER_PROBE_ADDRESS
        ):
            continue
        start = address - capture_base.REGISTER_POINTER_SNAPSHOT_BACKTRACK
        pointer_registers.setdefault(start, []).append(name)
    probes = []
    failures = []
    for start, names in sorted(pointer_registers.items()):
        payload, error = capture_base._try_read_memory(
            process, start, capture_base.REGISTER_POINTER_SNAPSHOT_BYTE_COUNT
        )
        common = {
            "registerNames": names,
            "registerValue": (
                start + capture_base.REGISTER_POINTER_SNAPSHOT_BACKTRACK
            ),
            "address": start,
        }
        if payload is None:
            failures.append({**common, "message": error})
        else:
            probes.append(
                {
                    **common,
                    "byteCount": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "hex": payload.hex(),
                }
            )
    return {
        "registers": registers,
        "stack": capture_base._memory_snapshot(
            process,
            stack_pointer,
            capture_base.STACK_SNAPSHOT_BYTE_COUNT,
            "frame-correlated writer stack operands",
        ),
        "registerPointerProbeCount": len(pointer_registers),
        "registerPointerProbes": probes,
        "registerPointerProbeFailures": failures,
    }


def _matching_prepare_frame(thread):
    target = thread.GetProcess().GetTarget()
    prepare = _state["prepareLayer"]
    start = prepare["symbolStart"]
    end = prepare["symbolEnd"]
    count = min(thread.GetNumFrames(), capture_base.MAXIMUM_BACKTRACE_FRAME_COUNT)
    for index in range(count):
        candidate = thread.GetFrameAtIndex(index)
        if candidate.GetFunctionName() != capture_base.PREPARE_LAYER_FUNCTION:
            continue
        symbol = candidate.GetSymbol()
        if not symbol.IsValid():
            continue
        symbol_start = symbol.GetStartAddress().GetLoadAddress(target)
        symbol_end = symbol.GetEndAddress().GetLoadAddress(target)
        if symbol_start != start or symbol_end != end:
            continue
        try:
            registers = capture_base._register_snapshot(
                candidate, PREPARE_FRAME_REGISTER_NAMES
            )
        except Exception:
            return None, None, None, None
        values = {
            record["name"]: record["unsignedValue"] for record in registers
        }
        return candidate, index, registers, values
    return None, None, None, None


def capture_backdrop_entry(frame, _breakpoint_location, _internal_dict):
    """Gate ``capture_backdrop`` and arm the exact independent selector."""
    try:
        sequence = _next_sequence("capture-backdrop-entry")
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        address = frame.GetPC()
        code = capture_base._read_memory(
            process,
            address,
            capture_base.CAPTURE_BACKDROP_CODE_BYTE_COUNT,
            "capture_backdrop code",
        )
        digest = hashlib.sha256(code).hexdigest()
        if digest != capture_base.CAPTURE_BACKDROP_CODE_SHA256:
            raise RuntimeError("capture_backdrop code SHA-256 differs")
        late = _address_breakpoint(
            target,
            address + capture_base.CAPTURE_BACKDROP_LATE_OFFSET,
            "capture_backdrop_late",
            "capture_backdrop late",
        )
        _state["captureLateBreakpoint"] = late
        _state["trace"]["captureBackdrop"] = {
            "callbackSequence": sequence,
            "symbolAddress": address,
            "codeByteCount": len(code),
            "codeSHA256": digest,
            "module": capture_base._module_record(frame.GetModule(), target),
            "lateBreakpointID": late.GetID(),
        }
        _state["captureEntryBreakpoint"].SetEnabled(False)
        _state["trace"]["status"] = "capture-backdrop-late-armed"
        _write_trace()
    except Exception as error:
        _failure("capture-backdrop-entry", error)
        if _state["captureEntryBreakpoint"] is not None:
            _state["captureEntryBreakpoint"].SetEnabled(False)
    return False


def _reject_late_candidate(candidate):
    trace = _state["trace"]
    trace["lateCandidateCount"] = _state["lateCandidateCount"]
    if (
        len(trace["lateCandidateDiagnostics"])
        < capture_base.MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT
    ):
        trace["lateCandidateDiagnostics"].append(candidate)
    if _state["lateCandidateCount"] >= capture_base.MAXIMUM_LATE_CANDIDATE_COUNT:
        _failure(
            "capture-backdrop-late-candidate-limit",
            "no exact late candidate within %d invocations"
            % capture_base.MAXIMUM_LATE_CANDIDATE_COUNT,
        )
        _state["captureLateBreakpoint"].SetEnabled(False)


def capture_backdrop_late(frame, _breakpoint_location, _internal_dict):
    """Select the first exact preconvergence source independently."""
    try:
        process = frame.GetThread().GetProcess()
        source = capture_base._register(frame, "x19")
        owner = capture_base._register(frame, "x20")
        layer = capture_base._register(frame, "x24")
        _state["lateCandidateCount"] += 1
        candidate = {
            "lateCandidateIndex": _state["lateCandidateCount"],
            "source": source,
            "owner": owner,
            "layer": layer,
        }
        if 0 in (source, owner, layer):
            candidate["rejection"] = "null primary object pointer"
            _reject_late_candidate(candidate)
            return False
        layer_state = capture_base._read_u64(
            process, layer + 0x10, "layer-state pointer"
        )
        candidate["layerState"] = layer_state
        if layer_state == 0:
            candidate["rejection"] = "null layer-state pointer"
            _reject_late_candidate(candidate)
            return False
        source_owner = capture_base._read_u64(
            process, source + 0x48, "source owner pointer"
        )
        layer_state_source = capture_base._read_u64(
            process, layer_state + 0x120, "layer-state source pointer"
        )
        exact_chain = source_owner == owner and layer_state_source == source
        candidate.update(
            {
                "sourceOwner": source_owner,
                "layerStateSource": layer_state_source,
                "pointerChainExact": exact_chain,
            }
        )
        if not exact_chain:
            candidate["rejection"] = "object pointer chain differs"
            _reject_late_candidate(candidate)
            return False
        source_bytes = capture_base._read_memory(
            process, source + 0x50, 16, "source rectangle"
        )
        layer_bytes = capture_base._read_memory(
            process, layer_state + 0xB0, 16, "layer-state rectangle"
        )
        owner_bytes = capture_base._read_memory(
            process, owner + 0xE0, 32, "owner rectangle"
        )
        source_rect = list(struct.unpack("<4i", source_bytes))
        layer_rect = list(struct.unpack("<4i", layer_bytes))
        owner_rect = list(struct.unpack("<4d", owner_bytes))
        owner_equal = owner_rect == [float(value) for value in layer_rect]
        source_equal = source_rect == layer_rect
        preconvergence = owner_equal and not source_equal
        candidate.update(
            {
                "ownerEqualsLayerStateRectangle": owner_equal,
                "sourceEqualsLayerStateRectangle": source_equal,
                "preconvergenceExact": preconvergence,
            }
        )
        if not preconvergence:
            candidate["rejection"] = "preconvergence rectangle state differs"
            _reject_late_candidate(candidate)
            return False
        sequence = _next_sequence("source-selected")
        _state["objectAddresses"] = {
            "source": source,
            "owner": owner,
            "layer": layer,
            "layerState": layer_state,
        }
        _state["trace"]["lateCandidateCount"] = _state["lateCandidateCount"]
        _state["trace"]["objectChain"] = {
            "callbackSequence": sequence,
            "addresses": dict(_state["objectAddresses"]),
            "exact": True,
            "pointerChainExact": True,
            "selectedLateCandidateIndex": _state["lateCandidateCount"],
            "ownerEqualsLayerStateRectangle": owner_equal,
            "sourceEqualsLayerStateRectangle": source_equal,
            "preconvergenceExact": preconvergence,
            "sourceSelectedRectI32": source_rect,
            "sourceSelectedRectI32Hex": source_bytes.hex(),
            "layerStateSelectedRectI32": layer_rect,
            "layerStateSelectedRectI32Hex": layer_bytes.hex(),
            "ownerSelectedRectF64": owner_rect,
            "ownerSelectedRectF64Hex": owner_bytes.hex(),
        }
        _state["captureLateBreakpoint"].SetEnabled(False)
        _state["trace"]["status"] = "source-selected-awaiting-frame-correlation"
        _write_trace()
    except Exception as error:
        _failure("capture-backdrop-late", error)
        if _state["captureLateBreakpoint"] is not None:
            _state["captureLateBreakpoint"].SetEnabled(False)
    return False


def prepare_layer_entry(frame, breakpoint_location, _internal_dict):
    """Gate the complete function and install every writer before resume."""
    try:
        sequence = _next_sequence("prepare-layer-entry")
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        symbol = frame.GetSymbol()
        if (
            frame.GetFunctionName() != capture_base.PREPARE_LAYER_FUNCTION
            or not symbol.IsValid()
        ):
            raise RuntimeError("prepare_layer function identity differs")
        start = symbol.GetStartAddress().GetLoadAddress(target)
        end = symbol.GetEndAddress().GetLoadAddress(target)
        location = breakpoint_location.GetAddress().GetLoadAddress(target)
        if (
            start == lldb.LLDB_INVALID_ADDRESS
            or end == lldb.LLDB_INVALID_ADDRESS
            or end - start != capture_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT
            or frame.GetPC() != start
            or location != start
        ):
            raise RuntimeError("prepare_layer exact entry differs")
        code = capture_base._read_memory(
            process,
            start,
            capture_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            "full prepare_layer code",
        )
        digest = hashlib.sha256(code).hexdigest()
        if digest != PREPARE_LAYER_FULL_CODE_SHA256:
            raise RuntimeError("full prepare_layer code SHA-256 differs")
        for offset, count, expected in capture_base.KNOWN_PREPARE_LAYER_WINDOWS:
            if hashlib.sha256(code[offset : offset + count]).hexdigest() != expected:
                raise RuntimeError("known prepare_layer code window differs")
        helper_address = start + capture_base.UNION_HELPER_RELATIVE_TO_PREPARE_LAYER
        helper_resolved = target.ResolveLoadAddress(helper_address)
        helper_symbol = capture_base._symbol_record(
            helper_resolved.GetSymbol(), target
        )
        helper_code = capture_base._read_memory(
            process,
            helper_address,
            capture_base.UNION_HELPER_SYMBOL_BYTE_COUNT,
            "union_bounds symbol code",
        )
        if (
            helper_symbol.get("valid") is not True
            or helper_symbol.get("name") != capture_base.UNION_HELPER_SYMBOL_NAME
            or helper_symbol.get("startAddress") != helper_address
            or helper_symbol.get("endAddress")
            != helper_address + capture_base.UNION_HELPER_SYMBOL_BYTE_COUNT
            or hashlib.sha256(helper_code).hexdigest()
            != capture_base.UNION_HELPER_SYMBOL_SHA256
        ):
            raise RuntimeError("union_bounds identity differs")
        records = []
        for site in WRITER_SITES:
            address = start + site["relativeToPrepareLayer"]
            resolved = target.ResolveLoadAddress(address)
            resolved_symbol = capture_base._symbol_record(
                resolved.GetSymbol(), target
            )
            if (
                resolved_symbol.get("valid") is not True
                or resolved_symbol.get("name") != site["function"]
                or not (
                    resolved_symbol["startAddress"]
                    <= address
                    < resolved_symbol["endAddress"]
                )
            ):
                raise RuntimeError(site["name"] + " resolved identity differs")
            preceding = capture_base._read_memory(
                process, address - 4, 4, site["name"] + " preceding instruction"
            )
            expected = site.get("precedingInstructionRawLittleEndianHex")
            if expected is not None and preceding.hex() != expected:
                raise RuntimeError(site["name"] + " preceding instruction differs")
            breakpoint = _address_breakpoint(
                target, address, "writer_site", site["name"]
            )
            _state["writerBreakpoints"][site["name"]] = breakpoint
            _state["writerSiteByAddress"][address] = site
            records.append(
                {
                    **site,
                    "address": address,
                    "breakpointID": breakpoint.GetID(),
                    "module": capture_base._module_record(
                        resolved.GetModule(), target
                    ),
                    "symbol": resolved_symbol,
                    "precedingInstructionRawLittleEndianHex": preceding.hex(),
                }
            )
        marker_address = start + LIVE_SELECTION_MARKER_OFFSET
        marker = _address_breakpoint(
            target,
            marker_address,
            "live_selection_marker",
            "live selection marker",
        )
        _state["selectionMarkerBreakpoint"] = marker
        prepare = {
            "callbackSequence": sequence,
            "callbackPC": frame.GetPC(),
            "callbackLocationAddress": location,
            "entryBreakpointID": _state["prepareEntryBreakpoint"].GetID(),
            "entryBreakpointLocationAddresses": _breakpoint_location_addresses(
                _state["prepareEntryBreakpoint"], target
            ),
            "function": capture_base.PREPARE_LAYER_FUNCTION,
            "symbolStart": start,
            "symbolEnd": end,
            "symbolByteCount": end - start,
            "module": capture_base._module_record(frame.GetModule(), target),
            "fullCode": {
                "address": start,
                "byteCount": len(code),
                "sha256": digest,
                "hex": code.hex(),
            },
            "knownWindows": [
                {
                    "offset": offset,
                    "byteCount": count,
                    "sha256": hashlib.sha256(
                        code[offset : offset + count]
                    ).hexdigest(),
                }
                for offset, count, _expected in capture_base.KNOWN_PREPARE_LAYER_WINDOWS
            ],
            "unionHelper": {
                "address": helper_address,
                "relativeToPrepareLayer": helper_address - start,
                "module": capture_base._module_record(
                    helper_resolved.GetModule(), target
                ),
                "symbol": helper_symbol,
                "symbolCodeSHA256": hashlib.sha256(helper_code).hexdigest(),
            },
            "writerSites": records,
            "liveSelectionMarker": {
                "name": LIVE_SELECTION_MARKER_NAME,
                "offset": LIVE_SELECTION_MARKER_OFFSET,
                "address": marker_address,
                "breakpointID": marker.GetID(),
                "instructionRawLittleEndianHex": code[
                    LIVE_SELECTION_MARKER_OFFSET : LIVE_SELECTION_MARKER_OFFSET + 4
                ].hex(),
            },
        }
        _state["prepareLayer"] = prepare
        _state["trace"]["prepareLayer"] = prepare
        _state["prepareEntryBreakpoint"].SetEnabled(False)
        _state["trace"]["status"] = "writer-sites-and-selection-marker-active"
        _write_trace()
    except Exception as error:
        _failure("prepare-layer-entry", error)
        if _state["prepareEntryBreakpoint"] is not None:
            _state["prepareEntryBreakpoint"].SetEnabled(False)
        _disable_internal_breakpoints()
    return False


def _record_rejected_writer(frame, site, reason):
    name = site["name"]
    _state["rejectedWriterSiteHitCounts"][name] += 1
    target = frame.GetThread().GetProcess().GetTarget()
    key = (name, frame.GetPC(), frame.GetFunctionName(), str(reason))
    groups = _state["rejectedWriterGroups"]
    if key in groups:
        groups[key]["hitCount"] += 1
    elif len(groups) < MAXIMUM_REJECTED_WRITER_DIAGNOSTIC_COUNT:
        groups[key] = {
            "siteName": name,
            "stopPC": frame.GetPC(),
            "function": frame.GetFunctionName(),
            "module": capture_base._module_record(frame.GetModule(), target),
            "reason": str(reason),
            "hitCount": 1,
        }
    else:
        _state["unretainedRejectedWriterHitCount"] += 1


def writer_site(frame, breakpoint_location, _internal_dict):
    """Record one exact writer after-site and its nearest prepare frame."""
    try:
        target = frame.GetThread().GetProcess().GetTarget()
        address = breakpoint_location.GetAddress().GetLoadAddress(target)
        site = _state["writerSiteByAddress"].get(address)
        if site is None or frame.GetPC() != address:
            raise RuntimeError("writer site identity differs")
        name = site["name"]
        _state["writerSiteHitCounts"][name] += 1
        if _state["writerSiteHitCounts"][name] > MAXIMUM_WRITER_SITE_HIT_COUNT:
            _state["discardedWriterSiteHitCounts"][name] += 1
            raise RuntimeError(name + " hit bound exceeded")
        if frame.GetFunctionName() != site["function"]:
            _record_rejected_writer(frame, site, "top function differs")
            return False
        prepare_frame, prepare_index, prepare_registers, values = (
            _matching_prepare_frame(frame.GetThread())
        )
        if prepare_frame is None:
            _record_rejected_writer(frame, site, "exact prepare frame absent")
            return False
        events = _state["trace"]["writerCandidateEvents"]
        retained = sum(event["siteName"] == name for event in events)
        if retained >= MAXIMUM_RECORD_COUNT_PER_WRITER_SITE:
            _state["discardedWriterSiteHitCounts"][name] += 1
            raise RuntimeError(name + " record bound exceeded")
        process = frame.GetThread().GetProcess()
        role_base = values["x19"]
        role = capture_base._read_memory(
            process,
            role_base,
            capture_base.ROLE_STATE_BYTE_COUNT,
            name + " prepare role state",
        )
        aggregate = role[
            capture_base.AGGREGATE_OFFSET : capture_base.AGGREGATE_OFFSET
            + capture_base.AGGREGATE_BYTE_COUNT
        ]
        thread_id = frame.GetThread().GetThreadID()
        frame_key = (thread_id, role_base, values["x29"])
        previous_index = (
            None
            if site["epochStart"]
            else _state["lastCandidateByFrame"].get(frame_key)
        )
        previous = (
            None
            if previous_index is None
            else bytes.fromhex(events[previous_index]["aggregateAfterHex"])
        )
        sequence = _next_sequence("writer-site:" + name)
        event = {
            "eventIndex": len(events),
            "callbackSequence": sequence,
            "siteName": name,
            "siteRelativeToPrepareLayer": site["relativeToPrepareLayer"],
            "epochStart": site["epochStart"],
            "sourceKnownAtHit": _selected_source() is not None,
            "threadID": thread_id,
            "stopPC": frame.GetPC(),
            "frame": capture_base._frame_record(frame, target),
            "backtrace": capture_base._backtrace(frame.GetThread()),
            "prepareFrameIndex": prepare_index,
            "prepareFrame": capture_base._frame_record(prepare_frame, target),
            "prepareFrameRegisters": prepare_registers,
            "frameIdentity": {
                "threadID": thread_id,
                "roleBase": role_base,
                "framePointer": values["x29"],
            },
            "previousSameFrameCandidateEventIndex": previous_index,
            "aggregateChangedFromPreviousSameFrameCandidate": (
                None if previous is None else aggregate != previous
            ),
            "roleStateAfter": {
                "address": role_base,
                "byteCount": len(role),
                "sha256": hashlib.sha256(role).hexdigest(),
                "hex": role.hex(),
            },
            "aggregateAfterHex": aggregate.hex(),
            "codeWindowIndex": capture_base._code_window(frame),
            "topOperandSnapshot": _top_operand_snapshot(frame),
        }
        events.append(event)
        _state["lastCandidateByFrame"][frame_key] = event["eventIndex"]
        if sequence % 16 == 0:
            _write_trace()
    except Exception as error:
        _failure("writer-site", error)
        _disable_internal_breakpoints()
    return False


def _selected_object_snapshots(process):
    return {
        base: capture_base._memory_snapshot(
            process,
            _state["objectAddresses"][base],
            byte_count,
            "selected " + base + " at live marker",
        )
        for base, byte_count in capture_base.OBJECT_SNAPSHOT_SPECS
    }


def live_selection_marker(frame, _breakpoint_location, _internal_dict):
    """Select one still-live invocation and its latest writer epoch."""
    try:
        _state["selectionMarkerHitCount"] += 1
        if _state["selectionMarkerHitCount"] > MAXIMUM_LIVE_SELECTION_MARKER_HIT_COUNT:
            _state["discardedSelectionMarkerHitCount"] += 1
            raise RuntimeError("live selection marker hit bound exceeded")
        x19 = capture_base._register(frame, "x19")
        x28 = capture_base._register(frame, "x28")
        x29 = capture_base._register(frame, "x29")
        source = _selected_source()
        if source is None:
            diagnostics = _state["trace"]["preselectionMarkerDiagnostics"]
            if len(diagnostics) >= MAXIMUM_PRESELECTION_MARKER_DIAGNOSTIC_COUNT:
                _state["discardedSelectionMarkerHitCount"] += 1
                raise RuntimeError("preselection marker diagnostic bound exceeded")
            diagnostics.append(
                {
                    "markerHitIndex": _state["selectionMarkerHitCount"],
                    "threadID": frame.GetThread().GetThreadID(),
                    "roleBase": x19,
                    "sourceRegister": x28,
                    "framePointer": x29,
                }
            )
            _write_trace()
            return False
        if x28 != source:
            _state["rejectedSelectionMarkerHitCount"] += 1
            return False
        process = frame.GetThread().GetProcess()
        thread_id = frame.GetThread().GetThreadID()
        identity = {"threadID": thread_id, "roleBase": x19, "framePointer": x29}
        matching = [
            event
            for event in _state["trace"]["writerCandidateEvents"]
            if event["frameIdentity"] == identity
        ]
        epochs = [event for event in matching if event["epochStart"] is True]
        if not epochs:
            raise RuntimeError("selected live frame has no writer epoch start")
        epoch = max(epochs, key=lambda event: event["callbackSequence"])
        selected = [
            event
            for event in matching
            if event["callbackSequence"] >= epoch["callbackSequence"]
        ]
        selected.sort(key=lambda event: event["callbackSequence"])
        role = capture_base._read_memory(
            process,
            x19,
            capture_base.ROLE_STATE_BYTE_COUNT,
            "selected live marker role state",
        )
        aggregate = role[
            capture_base.AGGREGATE_OFFSET : capture_base.AGGREGATE_OFFSET
            + capture_base.AGGREGATE_BYTE_COUNT
        ]
        sequence = _next_sequence("live-selected-frame-correlated")
        _state["trace"]["selectedFrame"] = {
            "callbackSequence": sequence,
            "markerHitIndex": _state["selectionMarkerHitCount"],
            "threadID": thread_id,
            "pc": frame.GetPC(),
            "frame": capture_base._frame_record(frame, process.GetTarget()),
            "backtrace": capture_base._backtrace(frame.GetThread()),
            "registers": capture_base._register_snapshot(
                frame, PREPARE_FRAME_REGISTER_NAMES
            ),
            "frameIdentity": identity,
            "selectedSource": source,
            "epochStartEventIndex": epoch["eventIndex"],
            "selectedWriterEventCount": len(selected),
            "roleStateAtMarker": {
                "address": x19,
                "byteCount": len(role),
                "sha256": hashlib.sha256(role).hexdigest(),
                "hex": role.hex(),
            },
            "aggregateAtMarkerHex": aggregate.hex(),
            "privateFieldsAtMarker": capture_base._snapshot_private_fields(process),
            "selectedObjectsAtMarker": _selected_object_snapshots(process),
        }
        _state["trace"]["selectedWriterEventIndices"] = [
            event["eventIndex"] for event in selected
        ]
        _state["trace"]["status"] = "live-selected-frame-correlated"
        _disable_internal_breakpoints()
        _write_trace()
    except Exception as error:
        _failure("live-selection-marker", error)
        _disable_internal_breakpoints()
    return False


def finalize():
    """Finalize exact writer, rejection, marker, and suffix accounting."""
    trace = _state["trace"]
    if trace is None:
        return
    trace["rejectedWriterDiagnostics"] = sorted(
        _state["rejectedWriterGroups"].values(),
        key=lambda item: (item["siteName"], item["stopPC"], item["reason"]),
    )
    trace["statusBeforeFinalization"] = trace["status"]
    trace["status"] = "finalized"
    trace["finalFailureCount"] = len(trace["failures"])
    trace["finalCallbackSequence"] = _state["callbackSequence"]
    trace["writerSiteHitCounts"] = dict(_state["writerSiteHitCounts"])
    trace["rejectedWriterSiteHitCounts"] = dict(
        _state["rejectedWriterSiteHitCounts"]
    )
    trace["discardedWriterSiteHitCounts"] = dict(
        _state["discardedWriterSiteHitCounts"]
    )
    trace["unretainedRejectedWriterHitCount"] = _state[
        "unretainedRejectedWriterHitCount"
    ]
    trace["finalWriterCandidateEventCount"] = len(trace["writerCandidateEvents"])
    trace["selectionMarkerHitCount"] = _state["selectionMarkerHitCount"]
    trace["rejectedSelectionMarkerHitCount"] = _state[
        "rejectedSelectionMarkerHitCount"
    ]
    trace["discardedSelectionMarkerHitCount"] = _state[
        "discardedSelectionMarkerHitCount"
    ]
    selected = trace["selectedWriterEventIndices"]
    trace["finalSelectedWriterEventCount"] = len(selected)
    trace["finalSelectedDistinctAggregateCount"] = len(
        {trace["writerCandidateEvents"][index]["aggregateAfterHex"] for index in selected}
    )
    trace["finalSelectedChangingTransitionCount"] = sum(
        trace["writerCandidateEvents"][index].get(
            "aggregateChangedFromPreviousSameFrameCandidate"
        )
        is True
        for index in selected
    )
    _write_trace()


def __lldb_init_module(debugger, _internal_dict):
    """Install pending exact-name entry breakpoints."""
    _reset_state()
    _state["debugger"] = debugger
    _state["trace"] = _new_trace()
    target = debugger.GetSelectedTarget()
    capture = target.BreakpointCreateByName(capture_base.CAPTURE_BACKDROP_SYMBOL)
    if not capture.IsValid():
        _failure("initialization", "capture_backdrop breakpoint is invalid")
        return
    _set_callback(capture, "capture_backdrop_entry", "capture_backdrop entry")
    prepare = target.BreakpointCreateByName(capture_base.PREPARE_LAYER_FUNCTION)
    if not prepare.IsValid():
        _failure("initialization", "prepare_layer breakpoint is invalid")
        return
    _set_callback(prepare, "prepare_layer_entry", "prepare_layer entry")
    _state["captureEntryBreakpoint"] = capture
    _state["prepareEntryBreakpoint"] = prepare
    _state["trace"]["captureBackdropEntryBreakpointID"] = capture.GetID()
    _state["trace"]["prepareLayerEntryBreakpointID"] = prepare.GetID()
    _write_trace()
