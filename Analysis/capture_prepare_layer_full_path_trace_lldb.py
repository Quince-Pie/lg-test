"""LLDB capture of full ``prepare_layer`` code, path markers, and its writer.

The preceding early-arm experiment proved that the selected workload executes
neither of the two initially suspected construction branches.  This probe
therefore captures the complete Apple function, records bounded markers on
both the skipped region and later known-live sites, and arms one hardware
watchpoint on the selected source's aggregate origin for a subsequent update.
"""

import hashlib
import json
import os
import struct
from pathlib import Path

import lldb


TRACE_SCHEMA_VERSION = 1
CAPTURE_BACKDROP_SYMBOL = "_ZN2CA3OGL16capture_backdropERNS0_8RendererEPKNS0_5LayerE"
PREPARE_LAYER_FUNCTION = (
    "CA::Render::Updater::prepare_layer(CA::Render::Updater::GlobalState&, "
    "CA::Render::Updater::LocalState&, CA::Render::LayerNode*, "
    "CA::Render::Updater::LayerShapes&, unsigned long long&)"
)
CAPTURE_BACKDROP_CODE_BYTE_COUNT = 0x4000
CAPTURE_BACKDROP_CODE_SHA256 = (
    "14f25960556bec9e88ba8ade176ee7f1d39b84726226ade3eb1b0f1be00b70d2"
)
CAPTURE_BACKDROP_LATE_OFFSET = 0x2B58
PREPARE_LAYER_SYMBOL_BYTE_COUNT = 40128
KNOWN_PREPARE_LAYER_WINDOWS = (
    (12764, 0x1000, "91fbe43da3533d7cd4578195b77c5a1aa0844105493c70635687e76adb7af768"),
    (14064, 0x1000, "9f67889b8a095f620d078f0c5c61eb0dca92e76916301a4ada40cf3b63eff9df"),
    (17944, 0x1000, "6472a0a0dbbb1fcdcbc75dcea63f28f2645cb58770ab0dc00ea17464db597c7f"),
    (19212, 0x1000, "756da544c0ac96badc07fc651b127e7eb8dcb244f98801335748e27feed2b5fa"),
    (19216, 0x1000, "e28e801599441f3aaf171ccc7ca5df86a0dc4c32a0d18062ab9a8c4627e9bc37"),
)
UNION_HELPER_RELATIVE_TO_PREPARE_LAYER = -0xAA0
UNION_HELPER_SYMBOL_NAME = (
    "CA::Render::Updater::LayerShapes::union_bounds(CA::Rect const&, bool)"
)
UNION_HELPER_SYMBOL_BYTE_COUNT = 404
UNION_HELPER_SYMBOL_SHA256 = (
    "246257a9bc1a608f59dbc07345397a8851b49528c59407eb775e9b9895a2c4b7"
)
PATH_MARKERS = (
    ("constructionWindowEntry", 0x31DC, False),
    ("preSelectorCall", 0x327C, False),
    ("postSelectorBranch", 0x3284, False),
    ("directLabel", 0x32B4, False),
    ("directUnionCall", 0x32C0, False),
    ("alternateLabel", 0x32C8, False),
    ("alternateSourceLoad", 0x33E8, False),
    ("alternateAggregateStore", 0x33F0, False),
    ("constructionJoin", 0x3458, False),
    ("sourceLaterHandle", 0x3EF0, True),
    ("sourceLaterOwnerRectangle", 0x4E18, True),
    ("sourceLaterIntegerOrigin", 0x530C, True),
    ("sourceLaterIntegerTail", 0x5310, True),
)
LATER_SELECTED_MARKER_NAMES = tuple(
    name for name, _offset, watch_arm in PATH_MARKERS if watch_arm
)
ROLE_STATE_BYTE_COUNT = 0x800
AGGREGATE_OFFSET = 656
AGGREGATE_BYTE_COUNT = 32
ALTERNATE_SOURCE_OFFSET = 1312
RECURSIVE_CHILD_OFFSET = 1568
MAXIMUM_LATE_CANDIDATE_COUNT = 512
MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT = 16
MAXIMUM_MARKER_HIT_COUNT = 4096
MAXIMUM_RECORD_COUNT_PER_MARKER = 128
MAXIMUM_BACKTRACE_FRAME_COUNT = 24
WATCHPOINT_BYTE_COUNT = 8
MAXIMUM_WATCHPOINT_HIT_COUNT = 24
PC_CENTERED_CODE_WINDOW_BYTE_COUNT = 0x1000
PC_CENTERED_CODE_WINDOW_BACKTRACK = 0x800
STACK_SNAPSHOT_BYTE_COUNT = 0x800
REGISTER_POINTER_SNAPSHOT_BYTE_COUNT = 0x100
REGISTER_POINTER_SNAPSHOT_BACKTRACK = 0x40
MINIMUM_POINTER_PROBE_ADDRESS = 0x1_0000_0000
MAXIMUM_POINTER_PROBE_ADDRESS = 0x0000_FFFF_FFFF_FFFF
MARKER_REGISTER_NAMES = (
    "x0",
    "x1",
    "x2",
    "x3",
    "x4",
    "x19",
    "x23",
    "x24",
    "x27",
    "x28",
    "x29",
    "x30",
    "sp",
    "pc",
)
GENERAL_REGISTER_NAMES = tuple("x%d" % index for index in range(31)) + (
    "sp",
    "pc",
    "cpsr",
)
SIMD_REGISTER_NAMES = tuple("v%d" % index for index in range(32)) + (
    "fpsr",
    "fpcr",
)
POINTER_PROBE_REGISTER_NAMES = tuple("x%d" % index for index in range(29))
PREPARE_LAYER_ROLE_REGISTER_NAMES = tuple("x%d" % index for index in range(19, 29))
OBJECT_SNAPSHOT_SPECS = (
    ("source", 0x180),
    ("owner", 0x300),
    ("layer", 0x200),
    ("layerState", 0x180),
)
TRACE_OUTPUT_ENVIRONMENT = "LG_PREPARE_LAYER_FULL_PATH_TRACE_OUTPUT"
DEFAULT_TRACE_OUTPUT = "transition-introspection/prepare-layer-full-path-trace.json"


_state = {
    "debugger": None,
    "captureEntryBreakpoint": None,
    "captureLateBreakpoint": None,
    "prepareEntryBreakpoint": None,
    "markerBreakpoints": {},
    "markerHitCounts": {name: 0 for name, _offset, _arm in PATH_MARKERS},
    "rejectedMarkerCounts": {name: 0 for name, _offset, _arm in PATH_MARKERS},
    "discardedMarkerCounts": {name: 0 for name, _offset, _arm in PATH_MARKERS},
    "lateCandidateCount": 0,
    "objectAddresses": {},
    "prepareLayer": None,
    "callbackSequence": 0,
    "aggregateWatchpoint": None,
    "aggregateWatchpointSpec": None,
    "watchpointHitCount": 0,
    "trace": None,
}


def _trace_path():
    return Path(os.environ.get(TRACE_OUTPUT_ENVIRONMENT, DEFAULT_TRACE_OUTPUT))


def _marker_configuration():
    return [
        {"name": name, "offset": offset, "watchArmCandidate": watch_arm}
        for name, offset, watch_arm in PATH_MARKERS
    ]


def _new_trace():
    return {
        "prepareLayerFullPathTraceSchemaVersion": TRACE_SCHEMA_VERSION,
        "classification": (
            "preregistered-complete-prepare-layer-code-path-marker-and-selected-"
            "aggregate-origin-watchpoint-trace; writer-semantics-public-crop-law-"
            "unseen-transfer-and-product-parity-remain-sealed"
        ),
        "status": "initialized",
        "configuration": {
            "captureBackdropSymbol": CAPTURE_BACKDROP_SYMBOL,
            "captureBackdropCodeByteCount": CAPTURE_BACKDROP_CODE_BYTE_COUNT,
            "captureBackdropCodeSHA256": CAPTURE_BACKDROP_CODE_SHA256,
            "captureBackdropLateOffset": CAPTURE_BACKDROP_LATE_OFFSET,
            "prepareLayerFunction": PREPARE_LAYER_FUNCTION,
            "prepareLayerSymbolByteCount": PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            "knownPrepareLayerWindows": [
                {"offset": offset, "byteCount": count, "sha256": digest}
                for offset, count, digest in KNOWN_PREPARE_LAYER_WINDOWS
            ],
            "unionHelperRelativeToPrepareLayer": (
                UNION_HELPER_RELATIVE_TO_PREPARE_LAYER
            ),
            "unionHelperSymbolName": UNION_HELPER_SYMBOL_NAME,
            "unionHelperSymbolByteCount": UNION_HELPER_SYMBOL_BYTE_COUNT,
            "unionHelperSymbolSHA256": UNION_HELPER_SYMBOL_SHA256,
            "pathMarkers": _marker_configuration(),
            "laterSelectedMarkerNames": list(LATER_SELECTED_MARKER_NAMES),
            "roleStateByteCount": ROLE_STATE_BYTE_COUNT,
            "aggregateOffset": AGGREGATE_OFFSET,
            "aggregateByteCount": AGGREGATE_BYTE_COUNT,
            "alternateSourceOffset": ALTERNATE_SOURCE_OFFSET,
            "recursiveChildOffset": RECURSIVE_CHILD_OFFSET,
            "maximumLateCandidateCount": MAXIMUM_LATE_CANDIDATE_COUNT,
            "maximumLateCandidateDiagnosticCount": (
                MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT
            ),
            "maximumMarkerHitCount": MAXIMUM_MARKER_HIT_COUNT,
            "maximumRecordCountPerMarker": MAXIMUM_RECORD_COUNT_PER_MARKER,
            "maximumBacktraceFrameCount": MAXIMUM_BACKTRACE_FRAME_COUNT,
            "watchpointByteCount": WATCHPOINT_BYTE_COUNT,
            "maximumWatchpointHitCount": MAXIMUM_WATCHPOINT_HIT_COUNT,
            "pcCenteredCodeWindowByteCount": (
                PC_CENTERED_CODE_WINDOW_BYTE_COUNT
            ),
            "pcCenteredCodeWindowBacktrack": PC_CENTERED_CODE_WINDOW_BACKTRACK,
            "stackSnapshotByteCount": STACK_SNAPSHOT_BYTE_COUNT,
            "registerPointerSnapshotByteCount": (
                REGISTER_POINTER_SNAPSHOT_BYTE_COUNT
            ),
            "registerPointerSnapshotBacktrack": (
                REGISTER_POINTER_SNAPSHOT_BACKTRACK
            ),
            "pointerProbeAddressRange": [
                MINIMUM_POINTER_PROBE_ADDRESS,
                MAXIMUM_POINTER_PROBE_ADDRESS,
            ],
            "markerRegisterNames": list(MARKER_REGISTER_NAMES),
            "generalRegisterNames": list(GENERAL_REGISTER_NAMES),
            "simdRegisterNames": list(SIMD_REGISTER_NAMES),
            "pointerProbeRegisterNames": list(POINTER_PROBE_REGISTER_NAMES),
            "prepareLayerRoleRegisterNames": list(
                PREPARE_LAYER_ROLE_REGISTER_NAMES
            ),
            "objectSnapshotSpecs": [
                {"base": base, "byteCount": byte_count}
                for base, byte_count in OBJECT_SNAPSHOT_SPECS
            ],
            "markerRecordRule": (
                "retain every bounded preselection marker; after source selection "
                "retain only exact x28 source matches"
            ),
            "watchpointArmRule": (
                "after source selection arm from the most recent retained "
                "watch-arm marker retrospectively classified as the exact x28 "
                "source; if none exists, arm at the first later live exact-x28 "
                "watch-arm marker; target x19+656 for eight bytes"
            ),
        },
        "callbackOrder": [],
        "captureBackdrop": {},
        "prepareLayer": {},
        "lateCandidateCount": 0,
        "lateCandidateDiagnostics": [],
        "objectChain": {},
        "markerRecords": [],
        "aggregateWatchpoint": {},
        "codeWindows": [],
        "watchpointEvents": [],
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


def _failure(stage, message):
    _state["trace"]["failures"].append(
        {"stage": str(stage), "message": str(message)}
    )
    _write_trace()


def _next_sequence(kind):
    _state["callbackSequence"] += 1
    sequence = _state["callbackSequence"]
    _state["trace"]["callbackOrder"].append(
        {"sequence": sequence, "kind": str(kind)}
    )
    return sequence


def _read_memory(process, address, byte_count, label):
    error = lldb.SBError()
    payload = process.ReadMemory(address, byte_count, error)
    if not error.Success() or payload is None or len(payload) != byte_count:
        detail = error.GetCString() or "partial memory read"
        raise RuntimeError("%s at 0x%016x failed: %s" % (label, address, detail))
    return bytes(payload)


def _try_read_memory(process, address, byte_count):
    error = lldb.SBError()
    payload = process.ReadMemory(address, byte_count, error)
    if not error.Success() or payload is None or len(payload) != byte_count:
        return None, error.GetCString() or "partial memory read"
    return bytes(payload), None


def _read_u64(process, address, label):
    return struct.unpack("<Q", _read_memory(process, address, 8, label))[0]


def _register(frame, name):
    value = frame.FindRegister(name)
    if not value.IsValid():
        raise RuntimeError("missing register %s" % name)
    return value.GetValueAsUnsigned(0)


def _register_record(frame, name):
    value = frame.FindRegister(name)
    if not value.IsValid():
        raise RuntimeError("missing register %s" % name)
    byte_count = value.GetByteSize()
    data = value.GetData()
    if byte_count <= 0 or not data.IsValid() or data.GetByteSize() != byte_count:
        raise RuntimeError("register %s data is unavailable" % name)
    error = lldb.SBError()
    payload = bytearray()
    for offset in range(byte_count):
        payload.append(data.GetUnsignedInt8(error, offset))
        if not error.Success():
            raise RuntimeError(
                "register %s byte %d failed: %s"
                % (name, offset, error.GetCString() or "unknown SBData error")
            )
    record = {
        "name": name,
        "byteCount": byte_count,
        "hex": bytes(payload).hex(),
        "valueString": value.GetValue(),
    }
    if byte_count <= 8:
        record["unsignedValue"] = value.GetValueAsUnsigned(0)
    return record


def _register_snapshot(frame, names):
    return [_register_record(frame, name) for name in names]


def _full_register_snapshot(frame):
    return {
        "general": _register_snapshot(frame, GENERAL_REGISTER_NAMES),
        "simd": _register_snapshot(frame, SIMD_REGISTER_NAMES),
    }


def _memory_snapshot(process, address, byte_count, label):
    payload = _read_memory(process, address, byte_count, label)
    return {
        "address": address,
        "byteCount": byte_count,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "hex": payload.hex(),
    }


def _file_spec_path(file_spec):
    directory = file_spec.GetDirectory()
    filename = file_spec.GetFilename()
    if directory and filename:
        return str(Path(directory) / filename)
    if filename:
        return str(filename)
    if directory:
        return str(directory)
    return ""


def _module_record(module, target):
    if not module.IsValid():
        return {"valid": False}
    header = module.GetObjectFileHeaderAddress().GetLoadAddress(target)
    return {
        "valid": True,
        "path": _file_spec_path(module.GetFileSpec()),
        "loadAddress": None if header == lldb.LLDB_INVALID_ADDRESS else header,
    }


def _symbol_record(symbol, target):
    if not symbol.IsValid():
        return {"valid": False}
    start = symbol.GetStartAddress().GetLoadAddress(target)
    end = symbol.GetEndAddress().GetLoadAddress(target)
    if start == lldb.LLDB_INVALID_ADDRESS or end == lldb.LLDB_INVALID_ADDRESS:
        return {"valid": False}
    return {
        "valid": True,
        "name": symbol.GetName(),
        "startAddress": start,
        "endAddress": end,
    }


def _frame_record(frame, target):
    pc = frame.GetPC()
    symbol = frame.GetSymbol()
    start = lldb.LLDB_INVALID_ADDRESS
    end = lldb.LLDB_INVALID_ADDRESS
    if symbol.IsValid():
        start = symbol.GetStartAddress().GetLoadAddress(target)
        end = symbol.GetEndAddress().GetLoadAddress(target)
    return {
        "frameIndex": frame.GetFrameID(),
        "pc": pc,
        "function": frame.GetFunctionName(),
        "symbolStart": None if start == lldb.LLDB_INVALID_ADDRESS else start,
        "symbolEnd": None if end == lldb.LLDB_INVALID_ADDRESS else end,
        "symbolOffset": (
            None if start == lldb.LLDB_INVALID_ADDRESS or pc < start else pc - start
        ),
        "module": _module_record(frame.GetModule(), target),
    }


def _backtrace(thread):
    target = thread.GetProcess().GetTarget()
    count = min(thread.GetNumFrames(), MAXIMUM_BACKTRACE_FRAME_COUNT)
    return [
        _frame_record(thread.GetFrameAtIndex(index), target) for index in range(count)
    ]


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


def _classify_marker_records():
    source = _selected_source()
    if source is None:
        return
    for record in _state["trace"]["markerRecords"]:
        record["selectedSource"] = record["addresses"]["source"] == source


def _retrospective_watchpoint_candidate():
    candidates = [
        record
        for record in _state["trace"]["markerRecords"]
        if record.get("watchArmCandidate") is True
        and record.get("selectedSource") is True
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda record: record["callbackSequence"])


def _snapshot_private_fields(process):
    addresses = _state["objectAddresses"]
    source = addresses["source"]
    owner = addresses["owner"]
    layer_state = addresses["layerState"]
    return {
        "layerStateInputBoundsI32": list(
            struct.unpack(
                "<4i",
                _read_memory(process, layer_state + 0xA0, 16, "input bounds"),
            )
        ),
        "layerStateSelectedRectI32": list(
            struct.unpack(
                "<4i",
                _read_memory(
                    process, layer_state + 0xB0, 16, "layer-state rectangle"
                ),
            )
        ),
        "sourceSelectedRectI32": list(
            struct.unpack(
                "<4i",
                _read_memory(process, source + 0x50, 16, "source rectangle"),
            )
        ),
        "ownerSelectedRectF64": list(
            struct.unpack(
                "<4d",
                _read_memory(process, owner + 0xE0, 32, "owner rectangle"),
            )
        ),
        "ownerRegion248Handle": _read_u64(
            process, owner + 0x248, "owner +0x248 region"
        ),
        "ownerRegion270Handle": _read_u64(
            process, owner + 0x270, "owner +0x270 region"
        ),
    }


def _code_window(frame):
    process = frame.GetThread().GetProcess()
    pc = frame.GetPC()
    start = max(0, pc - PC_CENTERED_CODE_WINDOW_BACKTRACK)
    payload = _read_memory(
        process, start, PC_CENTERED_CODE_WINDOW_BYTE_COUNT, "writer code window"
    )
    digest = hashlib.sha256(payload).hexdigest()
    windows = _state["trace"]["codeWindows"]
    for index, item in enumerate(windows):
        if item["startAddress"] == start and item["sha256"] == digest:
            return index
    windows.append(
        {
            "startAddress": start,
            "byteCount": len(payload),
            "source": "pc-centered",
            "stopPCOffset": pc - start,
            "containsStopPC": start <= pc < start + len(payload),
            "sha256": digest,
            "hex": payload.hex(),
        }
    )
    return len(windows) - 1


def _operand_snapshot(frame):
    process = frame.GetThread().GetProcess()
    registers = _full_register_snapshot(frame)
    general = {item["name"]: item for item in registers["general"]}
    stack_pointer = general["sp"]["unsignedValue"]
    objects = {
        base: _memory_snapshot(
            process,
            _state["objectAddresses"][base],
            byte_count,
            base + " writer object",
        )
        for base, byte_count in OBJECT_SNAPSHOT_SPECS
    }
    pointer_registers = {}
    for name in POINTER_PROBE_REGISTER_NAMES:
        address = general[name]["unsignedValue"]
        if not MINIMUM_POINTER_PROBE_ADDRESS <= address <= MAXIMUM_POINTER_PROBE_ADDRESS:
            continue
        start = address - REGISTER_POINTER_SNAPSHOT_BACKTRACK
        pointer_registers.setdefault(start, []).append(name)
    pointer_probes = []
    pointer_probe_failures = []
    for start, names in sorted(pointer_registers.items()):
        payload, error = _try_read_memory(
            process, start, REGISTER_POINTER_SNAPSHOT_BYTE_COUNT
        )
        if payload is None:
            pointer_probe_failures.append(
                {
                    "registerNames": names,
                    "registerValue": start + REGISTER_POINTER_SNAPSHOT_BACKTRACK,
                    "address": start,
                    "message": error,
                }
            )
            continue
        pointer_probes.append(
            {
                "registerNames": names,
                "registerValue": start + REGISTER_POINTER_SNAPSHOT_BACKTRACK,
                "address": start,
                "byteCount": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "hex": payload.hex(),
            }
        )
    role_registers = {}
    if frame.GetFunctionName() == PREPARE_LAYER_FUNCTION:
        for name in PREPARE_LAYER_ROLE_REGISTER_NAMES:
            address = general[name]["unsignedValue"]
            if (
                MINIMUM_POINTER_PROBE_ADDRESS
                <= address
                <= MAXIMUM_POINTER_PROBE_ADDRESS
            ):
                role_registers.setdefault(address, []).append(name)
    role_probes = []
    role_probe_failures = []
    for address, names in sorted(role_registers.items()):
        payload, error = _try_read_memory(process, address, ROLE_STATE_BYTE_COUNT)
        if payload is None:
            role_probe_failures.append(
                {
                    "registerNames": names,
                    "registerValue": address,
                    "address": address,
                    "message": error,
                }
            )
            continue
        role_probes.append(
            {
                "registerNames": names,
                "registerValue": address,
                "address": address,
                "byteCount": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "hex": payload.hex(),
            }
        )
    return {
        "registers": registers,
        "stack": _memory_snapshot(
            process,
            stack_pointer,
            STACK_SNAPSHOT_BYTE_COUNT,
            "writer stack operands",
        ),
        "objects": objects,
        "registerPointerProbeCount": len(pointer_registers),
        "registerPointerProbes": pointer_probes,
        "registerPointerProbeFailures": pointer_probe_failures,
        "prepareLayerRoleProbeCount": len(role_registers),
        "prepareLayerRoleProbes": role_probes,
        "prepareLayerRoleProbeFailures": role_probe_failures,
    }


def capture_backdrop_entry(frame, _breakpoint_location, _internal_dict):
    """Gate capture_backdrop and arm its exact downstream selector."""
    try:
        sequence = _next_sequence("capture-backdrop-entry")
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        symbol_address = frame.GetPC()
        code = _read_memory(
            process,
            symbol_address,
            CAPTURE_BACKDROP_CODE_BYTE_COUNT,
            "capture_backdrop code",
        )
        digest = hashlib.sha256(code).hexdigest()
        _state["trace"]["captureBackdrop"] = {
            "callbackSequence": sequence,
            "symbolAddress": symbol_address,
            "codeByteCount": len(code),
            "codeSHA256": digest,
            "module": _module_record(frame.GetModule(), target),
        }
        if digest != CAPTURE_BACKDROP_CODE_SHA256:
            raise RuntimeError("capture_backdrop code SHA-256 differs")
        late = _address_breakpoint(
            target,
            symbol_address + CAPTURE_BACKDROP_LATE_OFFSET,
            "capture_backdrop_late",
            "capture_backdrop late",
        )
        _state["captureLateBreakpoint"] = late
        _state["trace"]["captureBackdrop"]["lateBreakpointID"] = late.GetID()
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
    if len(trace["lateCandidateDiagnostics"]) < MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT:
        trace["lateCandidateDiagnostics"].append(candidate)
    if _state["lateCandidateCount"] >= MAXIMUM_LATE_CANDIDATE_COUNT:
        _failure(
            "capture-backdrop-late-candidate-limit",
            "no exact late candidate within %d invocations"
            % MAXIMUM_LATE_CANDIDATE_COUNT,
        )
        _state["captureLateBreakpoint"].SetEnabled(False)
    else:
        _write_trace()


def capture_backdrop_late(frame, _breakpoint_location, _internal_dict):
    """Select the exact preconvergence source and classify marker records."""
    try:
        process = frame.GetThread().GetProcess()
        source = _register(frame, "x19")
        owner = _register(frame, "x20")
        layer = _register(frame, "x24")
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
        layer_state = _read_u64(process, layer + 0x10, "layer-state pointer")
        candidate["layerState"] = layer_state
        if layer_state == 0:
            candidate["rejection"] = "null layer-state pointer"
            _reject_late_candidate(candidate)
            return False
        source_owner = _read_u64(process, source + 0x48, "source owner pointer")
        layer_state_source = _read_u64(
            process, layer_state + 0x120, "layer-state source pointer"
        )
        pointer_chain_exact = source_owner == owner and layer_state_source == source
        candidate.update(
            {
                "sourceOwner": source_owner,
                "layerStateSource": layer_state_source,
                "pointerChainExact": pointer_chain_exact,
            }
        )
        if not pointer_chain_exact:
            candidate["rejection"] = "object pointer chain differs"
            _reject_late_candidate(candidate)
            return False
        source_bytes = _read_memory(process, source + 0x50, 16, "source rectangle")
        layer_state_bytes = _read_memory(
            process, layer_state + 0xB0, 16, "layer-state rectangle"
        )
        owner_bytes = _read_memory(process, owner + 0xE0, 32, "owner rectangle")
        source_rectangle = list(struct.unpack("<4i", source_bytes))
        layer_state_rectangle = list(struct.unpack("<4i", layer_state_bytes))
        owner_rectangle = list(struct.unpack("<4d", owner_bytes))
        owner_equals_layer_state = owner_rectangle == [
            float(value) for value in layer_state_rectangle
        ]
        source_equals_layer_state = source_rectangle == layer_state_rectangle
        preconvergence_exact = owner_equals_layer_state and not source_equals_layer_state
        candidate.update(
            {
                "ownerEqualsLayerStateRectangle": owner_equals_layer_state,
                "sourceEqualsLayerStateRectangle": source_equals_layer_state,
                "preconvergenceExact": preconvergence_exact,
            }
        )
        if not preconvergence_exact:
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
            "ownerEqualsLayerStateRectangle": owner_equals_layer_state,
            "sourceEqualsLayerStateRectangle": source_equals_layer_state,
            "preconvergenceExact": preconvergence_exact,
            "sourceSelectedRectI32": source_rectangle,
            "sourceSelectedRectI32Hex": source_bytes.hex(),
            "layerStateSelectedRectI32": layer_state_rectangle,
            "layerStateSelectedRectI32Hex": layer_state_bytes.hex(),
            "ownerSelectedRectF64": owner_rectangle,
            "ownerSelectedRectF64Hex": owner_bytes.hex(),
        }
        _classify_marker_records()
        retrospective = _retrospective_watchpoint_candidate()
        if retrospective is not None:
            _install_aggregate_watchpoint(
                frame,
                retrospective["markerName"],
                retrospective["addresses"]["x19"],
                "retrospective-source-selection",
                retrospective["recordIndex"],
            )
        _state["captureLateBreakpoint"].SetEnabled(False)
        _state["trace"]["status"] = "source-selected-path-trace-active"
        _write_trace()
    except Exception as error:
        _failure("capture-backdrop-late", error)
        if _state["captureLateBreakpoint"] is not None:
            _state["captureLateBreakpoint"].SetEnabled(False)
    return False


def prepare_layer_entry(frame, breakpoint_location, _internal_dict):
    """Capture the entire function and arm every marker before it proceeds."""
    try:
        sequence = _next_sequence("prepare-layer-entry")
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        symbol = frame.GetSymbol()
        if frame.GetFunctionName() != PREPARE_LAYER_FUNCTION or not symbol.IsValid():
            raise RuntimeError("prepare_layer function identity differs")
        start = symbol.GetStartAddress().GetLoadAddress(target)
        end = symbol.GetEndAddress().GetLoadAddress(target)
        location_address = breakpoint_location.GetAddress().GetLoadAddress(target)
        if (
            start == lldb.LLDB_INVALID_ADDRESS
            or end == lldb.LLDB_INVALID_ADDRESS
            or end - start != PREPARE_LAYER_SYMBOL_BYTE_COUNT
            or frame.GetPC() != start
            or location_address != start
        ):
            raise RuntimeError("prepare_layer exact entry differs")
        code = _read_memory(
            process, start, PREPARE_LAYER_SYMBOL_BYTE_COUNT, "full prepare_layer code"
        )
        for offset, count, digest in KNOWN_PREPARE_LAYER_WINDOWS:
            if hashlib.sha256(code[offset : offset + count]).hexdigest() != digest:
                raise RuntimeError("known prepare_layer code window differs")
        helper_address = start + UNION_HELPER_RELATIVE_TO_PREPARE_LAYER
        helper_resolved = target.ResolveLoadAddress(helper_address)
        helper_symbol = _symbol_record(helper_resolved.GetSymbol(), target)
        helper_code = _read_memory(
            process,
            helper_address,
            UNION_HELPER_SYMBOL_BYTE_COUNT,
            "union_bounds symbol code",
        )
        if (
            helper_symbol.get("valid") is not True
            or helper_symbol.get("name") != UNION_HELPER_SYMBOL_NAME
            or helper_symbol.get("startAddress") != helper_address
            or helper_symbol.get("endAddress")
            != helper_address + UNION_HELPER_SYMBOL_BYTE_COUNT
            or hashlib.sha256(helper_code).hexdigest()
            != UNION_HELPER_SYMBOL_SHA256
        ):
            raise RuntimeError("union_bounds identity differs")
        prepare = {
            "callbackSequence": sequence,
            "callbackPC": frame.GetPC(),
            "callbackLocationAddress": location_address,
            "entryBreakpointID": _state["prepareEntryBreakpoint"].GetID(),
            "entryBreakpointLocationAddresses": _breakpoint_location_addresses(
                _state["prepareEntryBreakpoint"], target
            ),
            "function": PREPARE_LAYER_FUNCTION,
            "symbolStart": start,
            "symbolEnd": end,
            "symbolByteCount": end - start,
            "module": _module_record(frame.GetModule(), target),
            "fullCode": {
                "address": start,
                "byteCount": len(code),
                "sha256": hashlib.sha256(code).hexdigest(),
                "hex": code.hex(),
            },
            "knownWindows": [
                {
                    "offset": offset,
                    "byteCount": count,
                    "sha256": hashlib.sha256(code[offset : offset + count]).hexdigest(),
                }
                for offset, count, _digest in KNOWN_PREPARE_LAYER_WINDOWS
            ],
            "unionHelper": {
                "address": helper_address,
                "relativeToPrepareLayer": helper_address - start,
                "module": _module_record(helper_resolved.GetModule(), target),
                "symbol": helper_symbol,
                "symbolCodeSHA256": hashlib.sha256(helper_code).hexdigest(),
            },
            "markers": [],
        }
        _state["prepareLayer"] = prepare
        _state["trace"]["prepareLayer"] = prepare
        for name, offset, watch_arm in PATH_MARKERS:
            address = start + offset
            breakpoint = _address_breakpoint(
                target, address, "prepare_layer_marker", name
            )
            _state["markerBreakpoints"][name] = breakpoint
            prepare["markers"].append(
                {
                    "name": name,
                    "offset": offset,
                    "address": address,
                    "breakpointID": breakpoint.GetID(),
                    "watchArmCandidate": watch_arm,
                    "instructionRawLittleEndianHex": code[offset : offset + 4].hex(),
                }
            )
        _state["prepareEntryBreakpoint"].SetEnabled(False)
        _state["trace"]["status"] = "full-code-and-path-markers-armed"
        _write_trace()
    except Exception as error:
        _failure("prepare-layer-entry", error)
        if _state["prepareEntryBreakpoint"] is not None:
            _state["prepareEntryBreakpoint"].SetEnabled(False)
    return False


def _marker_spec_for_pc(pc):
    start = _state["prepareLayer"]["symbolStart"]
    for name, offset, watch_arm in PATH_MARKERS:
        if pc == start + offset:
            return name, offset, watch_arm
    raise RuntimeError("unknown prepare_layer marker PC")


def _install_aggregate_watchpoint(
    frame, marker_name, role_base, arm_mode, marker_record_index
):
    if _state["aggregateWatchpoint"] is not None:
        return
    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    address = role_base + AGGREGATE_OFFSET
    initial = _read_memory(
        process, address, WATCHPOINT_BYTE_COUNT, "aggregate origin initial value"
    )
    initial_role = _read_memory(
        process, role_base, ROLE_STATE_BYTE_COUNT, "aggregate role state at arm"
    )
    error = lldb.SBError()
    watchpoint = target.WatchAddress(
        address, WATCHPOINT_BYTE_COUNT, False, True, error
    )
    if not error.Success() or not watchpoint.IsValid():
        raise RuntimeError(
            "aggregate watchpoint failed: %s"
            % (error.GetCString() or "invalid watchpoint")
        )
    result = lldb.SBCommandReturnObject()
    command = "watchpoint command add -F %s.aggregate_origin_watchpoint %d" % (
        __name__,
        watchpoint.GetID(),
    )
    _state["debugger"].GetCommandInterpreter().HandleCommand(command, result)
    if not result.Succeeded():
        raise RuntimeError("aggregate watchpoint callback failed: %s" % result.GetError())
    sequence = _next_sequence("aggregate-watchpoint-armed")
    spec = {
        "callbackSequence": sequence,
        "id": watchpoint.GetID(),
        "deprecatedHardwareIndex": watchpoint.GetHardwareIndex(),
        "markerName": marker_name,
        "markerRecordIndex": marker_record_index,
        "armMode": arm_mode,
        "selectedSource": _selected_source(),
        "roleBase": role_base,
        "address": address,
        "byteCount": WATCHPOINT_BYTE_COUNT,
        "initialHex": initial.hex(),
        "initialRoleStateSHA256": hashlib.sha256(initial_role).hexdigest(),
        "initialRoleStateHex": initial_role.hex(),
        "lastValue": initial,
    }
    _state["aggregateWatchpoint"] = watchpoint
    _state["aggregateWatchpointSpec"] = spec
    _state["trace"]["aggregateWatchpoint"] = {
        name: value for name, value in spec.items() if name != "lastValue"
    }
    _write_trace()


def prepare_layer_marker(frame, _breakpoint_location, _internal_dict):
    """Retain bounded path state and arm the selected aggregate watchpoint."""
    try:
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        thread = frame.GetThread()
        pc = frame.GetPC()
        name, offset, watch_arm = _marker_spec_for_pc(pc)
        _state["markerHitCounts"][name] += 1
        if _state["markerHitCounts"][name] > MAXIMUM_MARKER_HIT_COUNT:
            _state["discardedMarkerCounts"][name] += 1
            _state["markerBreakpoints"][name].SetEnabled(False)
            return False
        x19 = _register(frame, "x19")
        x28 = _register(frame, "x28")
        source = _selected_source()
        if source is not None and x28 != source:
            _state["rejectedMarkerCounts"][name] += 1
            return False
        retained_for_marker = sum(
            record["markerName"] == name
            for record in _state["trace"]["markerRecords"]
        )
        if retained_for_marker >= MAXIMUM_RECORD_COUNT_PER_MARKER:
            _state["discardedMarkerCounts"][name] += 1
            _state["markerBreakpoints"][name].SetEnabled(False)
            return False
        role = _read_memory(
            process, x19, ROLE_STATE_BYTE_COUNT, name + " role state"
        )
        sequence = _next_sequence("marker:" + name)
        record = {
            "recordIndex": len(_state["trace"]["markerRecords"]),
            "callbackSequence": sequence,
            "markerName": name,
            "markerOffset": offset,
            "watchArmCandidate": watch_arm,
            "selectedSource": None if source is None else True,
            "sourceKnownAtHit": source is not None,
            "threadID": thread.GetThreadID(),
            "pc": pc,
            "frame": _frame_record(frame, target),
            "backtrace": _backtrace(thread),
            "registers": _register_snapshot(frame, MARKER_REGISTER_NAMES),
            "addresses": {
                "x19": x19,
                "source": x28,
                "aggregate": x19 + AGGREGATE_OFFSET,
                "alternateSource": x19 + ALTERNATE_SOURCE_OFFSET,
                "recursiveChild": x19 + RECURSIVE_CHILD_OFFSET,
            },
            "roleState": {
                "address": x19,
                "byteCount": len(role),
                "sha256": hashlib.sha256(role).hexdigest(),
                "hex": role.hex(),
            },
            "aggregateHex": role[
                AGGREGATE_OFFSET : AGGREGATE_OFFSET + AGGREGATE_BYTE_COUNT
            ].hex(),
            "alternateSourceHex": role[
                ALTERNATE_SOURCE_OFFSET : ALTERNATE_SOURCE_OFFSET
                + AGGREGATE_BYTE_COUNT
            ].hex(),
            "recursiveChildHex": role[
                RECURSIVE_CHILD_OFFSET : RECURSIVE_CHILD_OFFSET
                + AGGREGATE_BYTE_COUNT
            ].hex(),
        }
        _state["trace"]["markerRecords"].append(record)
        if watch_arm and source is not None:
            _install_aggregate_watchpoint(
                frame,
                name,
                x19,
                "live-selected-marker",
                record["recordIndex"],
            )
        _write_trace()
    except Exception as error:
        _failure("prepare-layer-marker", error)
        for breakpoint in _state["markerBreakpoints"].values():
            breakpoint.SetEnabled(False)
    return False


def aggregate_origin_watchpoint(frame, watchpoint, _internal_dict):
    """Capture the actual instruction that next writes selected aggregate x."""
    try:
        spec = _state["aggregateWatchpointSpec"]
        if spec is None or watchpoint.GetID() != spec["id"]:
            raise RuntimeError("aggregate watchpoint identity differs")
        process = frame.GetThread().GetProcess()
        after = _read_memory(
            process,
            spec["address"],
            WATCHPOINT_BYTE_COUNT,
            "aggregate origin after write",
        )
        role_after = _read_memory(
            process,
            spec["roleBase"],
            ROLE_STATE_BYTE_COUNT,
            "aggregate role after write",
        )
        before = spec["lastValue"]
        _state["watchpointHitCount"] += 1
        sequence = _next_sequence("aggregate-watchpoint-hit")
        event = {
            "eventIndex": len(_state["trace"]["watchpointEvents"]),
            "callbackSequence": sequence,
            "watchpointID": watchpoint.GetID(),
            "watchpointHitIndex": _state["watchpointHitCount"],
            "threadID": frame.GetThread().GetThreadID(),
            "stopPC": frame.GetPC(),
            "watchedAddress": spec["address"],
            "beforeHex": before.hex(),
            "afterHex": after.hex(),
            "valueChanged": before != after,
            "frame": _frame_record(frame, process.GetTarget()),
            "backtrace": _backtrace(frame.GetThread()),
            "codeWindowIndex": _code_window(frame),
            "roleStateAfter": {
                "address": spec["roleBase"],
                "byteCount": len(role_after),
                "sha256": hashlib.sha256(role_after).hexdigest(),
                "hex": role_after.hex(),
            },
            "privateFieldsAfter": _snapshot_private_fields(process),
            "operandSnapshot": _operand_snapshot(frame),
        }
        _state["trace"]["watchpointEvents"].append(event)
        spec["lastValue"] = after
        if _state["watchpointHitCount"] >= MAXIMUM_WATCHPOINT_HIT_COUNT:
            watchpoint.SetEnabled(False)
            _state["trace"]["status"] = "watchpoint-hit-limit-reached"
        _write_trace()
    except Exception as error:
        _failure("aggregate-origin-watchpoint", error)
        watchpoint.SetEnabled(False)
    return False


def finalize():
    """Finalize counts after LLDB's synchronous run command returns."""
    trace = _state["trace"]
    if trace is None:
        return
    _classify_marker_records()
    trace["statusBeforeFinalization"] = trace["status"]
    trace["status"] = "finalized"
    trace["finalFailureCount"] = len(trace["failures"])
    trace["finalCallbackSequence"] = _state["callbackSequence"]
    trace["markerHitCounts"] = dict(_state["markerHitCounts"])
    trace["rejectedMarkerCounts"] = dict(_state["rejectedMarkerCounts"])
    trace["discardedMarkerCounts"] = dict(_state["discardedMarkerCounts"])
    trace["finalMarkerRecordCount"] = len(trace["markerRecords"])
    trace["finalSelectedMarkerRecordCount"] = sum(
        record.get("selectedSource") is True for record in trace["markerRecords"]
    )
    trace["finalSelectedLaterMarkerRecordCount"] = sum(
        record.get("selectedSource") is True
        and record.get("markerName") in LATER_SELECTED_MARKER_NAMES
        for record in trace["markerRecords"]
    )
    trace["finalWatchpointEventCount"] = len(trace["watchpointEvents"])
    trace["finalChangedWatchpointEventCount"] = sum(
        event.get("valueChanged") is True for event in trace["watchpointEvents"]
    )
    trace["watchpointHitCount"] = _state["watchpointHitCount"]
    _write_trace()


def __lldb_init_module(debugger, _internal_dict):
    """Install pending exact-name breakpoints for source and full function."""
    _state["debugger"] = debugger
    _state["trace"] = _new_trace()
    target = debugger.GetSelectedTarget()
    capture = target.BreakpointCreateByName(CAPTURE_BACKDROP_SYMBOL)
    if not capture.IsValid():
        _failure("initialization", "capture_backdrop breakpoint is invalid")
        return
    _set_callback(capture, "capture_backdrop_entry", "capture_backdrop entry")
    prepare = target.BreakpointCreateByName(PREPARE_LAYER_FUNCTION)
    if not prepare.IsValid():
        _failure("initialization", "prepare_layer breakpoint is invalid")
        return
    _set_callback(prepare, "prepare_layer_entry", "prepare_layer entry")
    _state["captureEntryBreakpoint"] = capture
    _state["prepareEntryBreakpoint"] = prepare
    _state["trace"]["captureBackdropEntryBreakpointID"] = capture.GetID()
    _state["trace"]["prepareLayerEntryBreakpointID"] = prepare.GetID()
    _write_trace()
