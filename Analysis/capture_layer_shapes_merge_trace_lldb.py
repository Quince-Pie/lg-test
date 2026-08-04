"""LLDB callbacks for Apple's selected-source LayerShapes merge call.

The probe byte-gates the already-opened ``prepare_layer`` construction window,
decodes its direct AArch64 ``BL`` target, and records bounded pre/post operands
only after the exact ``capture_backdrop`` object chain selects the source.
Every callback resumes the process without interactive debugger input.
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
PREPARE_LAYER_CODE_WINDOW_OFFSET = 12764
PREPARE_LAYER_CODE_WINDOW_BYTE_COUNT = 0x1000
PREPARE_LAYER_CODE_WINDOW_SHA256 = (
    "91fbe43da3533d7cd4578195b77c5a1aa0844105493c70635687e76adb7af768"
)
MERGE_CALL_OFFSET = 0x32C0
MERGE_RETURN_OFFSET = 0x32C4
MERGE_CALL_RAW_LITTLE_ENDIAN = bytes.fromhex("a8f0ff97")
MERGE_CALL_WORD = 0x97FFF0A8
MERGE_CALL_DISPLACEMENT = -0x3D60
MERGE_TARGET_RELATIVE_TO_PREPARE_LAYER = -0xAA0
MERGE_TARGET_CODE_BYTE_COUNT = 0x1000
LAYER_SHAPES_BYTE_COUNT = 0x20
ROLE_STATE_BYTE_COUNT = 0x800
SOURCE_OBJECT_BYTE_COUNT = 0x180
MAXIMUM_LATE_CANDIDATE_COUNT = 512
MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT = 16
MAXIMUM_MERGE_CALL_SITE_HIT_COUNT = 4096
MAXIMUM_COMPLETE_RECORD_COUNT = 64
MAXIMUM_BACKTRACE_FRAME_COUNT = 24
TRACE_OUTPUT_ENVIRONMENT = "LG_LAYER_SHAPES_MERGE_TRACE_OUTPUT"
DEFAULT_TRACE_OUTPUT = "transition-introspection/layer-shapes-merge-trace.json"
REGISTER_NAMES = ("x0", "x1", "x2", "x19", "x28", "x30", "sp", "pc")


_state = {
    "debugger": None,
    "captureEntryBreakpoint": None,
    "captureLateBreakpoint": None,
    "prepareEntryBreakpoint": None,
    "mergeCallBreakpoint": None,
    "mergeReturnBreakpoint": None,
    "lateCandidateCount": 0,
    "objectAddresses": {},
    "prepareLayer": None,
    "pendingByThread": {},
    "mergeCallSiteHitCount": 0,
    "selectedSourceCallCount": 0,
    "rejectedSourceCallCount": 0,
    "rejectedSourceReturnCount": 0,
    "trace": None,
}


def _trace_path():
    return Path(os.environ.get(TRACE_OUTPUT_ENVIRONMENT, DEFAULT_TRACE_OUTPUT))


def _new_trace():
    return {
        "layerShapesMergeTraceSchemaVersion": TRACE_SCHEMA_VERSION,
        "classification": (
            "preregistered-bounded-selected-source-prepare-layer-shapes-merge-"
            "trace; helper-semantics-public-crop-law-unseen-transfer-and-product-"
            "parity-remain-sealed"
        ),
        "status": "initialized",
        "configuration": {
            "captureBackdropSymbol": CAPTURE_BACKDROP_SYMBOL,
            "captureBackdropCodeByteCount": CAPTURE_BACKDROP_CODE_BYTE_COUNT,
            "captureBackdropCodeSHA256": CAPTURE_BACKDROP_CODE_SHA256,
            "captureBackdropLateOffset": CAPTURE_BACKDROP_LATE_OFFSET,
            "prepareLayerFunction": PREPARE_LAYER_FUNCTION,
            "prepareLayerSymbolByteCount": PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            "prepareLayerCodeWindowOffset": PREPARE_LAYER_CODE_WINDOW_OFFSET,
            "prepareLayerCodeWindowByteCount": (
                PREPARE_LAYER_CODE_WINDOW_BYTE_COUNT
            ),
            "prepareLayerCodeWindowSHA256": PREPARE_LAYER_CODE_WINDOW_SHA256,
            "mergeCallOffset": MERGE_CALL_OFFSET,
            "mergeReturnOffset": MERGE_RETURN_OFFSET,
            "mergeCallRawLittleEndianHex": (
                MERGE_CALL_RAW_LITTLE_ENDIAN.hex()
            ),
            "mergeCallWord": MERGE_CALL_WORD,
            "mergeCallDisplacement": MERGE_CALL_DISPLACEMENT,
            "mergeTargetRelativeToPrepareLayer": (
                MERGE_TARGET_RELATIVE_TO_PREPARE_LAYER
            ),
            "mergeTargetCodeByteCount": MERGE_TARGET_CODE_BYTE_COUNT,
            "layerShapesByteCount": LAYER_SHAPES_BYTE_COUNT,
            "roleStateByteCount": ROLE_STATE_BYTE_COUNT,
            "sourceObjectByteCount": SOURCE_OBJECT_BYTE_COUNT,
            "maximumLateCandidateCount": MAXIMUM_LATE_CANDIDATE_COUNT,
            "maximumLateCandidateDiagnosticCount": (
                MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT
            ),
            "maximumMergeCallSiteHitCount": MAXIMUM_MERGE_CALL_SITE_HIT_COUNT,
            "maximumCompleteRecordCount": MAXIMUM_COMPLETE_RECORD_COUNT,
            "maximumBacktraceFrameCount": MAXIMUM_BACKTRACE_FRAME_COUNT,
            "registerNames": list(REGISTER_NAMES),
            "selectionRule": (
                "first exact capture_backdrop x19/x20/x24 pointer chain whose owner "
                "rectangle equals layer-state while source differs"
            ),
            "recordRule": (
                "exact prepare_layer+0x32c0 calls whose live x28 is the selected "
                "source and whose x0/x1/w2 aliases are x19+656/x19+1568/1"
            ),
        },
        "captureBackdrop": {},
        "prepareLayer": {},
        "mergeHelper": {},
        "lateCandidateCount": 0,
        "lateCandidateDiagnostics": [],
        "objectChain": {},
        "records": [],
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


def _read_memory(process, address, byte_count, label):
    error = lldb.SBError()
    payload = process.ReadMemory(address, byte_count, error)
    if not error.Success() or payload is None or len(payload) != byte_count:
        detail = error.GetCString() or "partial memory read"
        raise RuntimeError("%s at 0x%016x failed: %s" % (label, address, detail))
    return bytes(payload)


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
    return {
        "name": name,
        "byteCount": byte_count,
        "hex": bytes(payload).hex(),
        "unsignedValue": value.GetValueAsUnsigned(0),
        "valueString": value.GetValue(),
    }


def _register_snapshot(frame):
    return [_register_record(frame, name) for name in REGISTER_NAMES]


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
    symbol_start = lldb.LLDB_INVALID_ADDRESS
    symbol_end = lldb.LLDB_INVALID_ADDRESS
    if symbol.IsValid():
        symbol_start = symbol.GetStartAddress().GetLoadAddress(target)
        symbol_end = symbol.GetEndAddress().GetLoadAddress(target)
    return {
        "frameIndex": frame.GetFrameID(),
        "pc": pc,
        "function": frame.GetFunctionName(),
        "symbolStart": (
            None if symbol_start == lldb.LLDB_INVALID_ADDRESS else symbol_start
        ),
        "symbolEnd": None if symbol_end == lldb.LLDB_INVALID_ADDRESS else symbol_end,
        "symbolOffset": (
            None
            if symbol_start == lldb.LLDB_INVALID_ADDRESS or pc < symbol_start
            else pc - symbol_start
        ),
        "module": _module_record(frame.GetModule(), target),
    }


def _backtrace(thread):
    target = thread.GetProcess().GetTarget()
    count = min(thread.GetNumFrames(), MAXIMUM_BACKTRACE_FRAME_COUNT)
    return [
        _frame_record(thread.GetFrameAtIndex(index), target) for index in range(count)
    ]


def _decode_bl_target(instruction_address, payload):
    if len(payload) != 4:
        raise ValueError("AArch64 BL payload must be four bytes")
    word = struct.unpack("<I", payload)[0]
    if word & 0xFC000000 != 0x94000000:
        raise ValueError("instruction is not an AArch64 BL immediate")
    immediate = word & 0x03FFFFFF
    if immediate & 0x02000000:
        immediate -= 1 << 26
    displacement = immediate << 2
    return word, displacement, instruction_address + displacement


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


def _try_arm_merge_breakpoints(target):
    if _state["mergeCallBreakpoint"] is not None:
        return
    if not _state["objectAddresses"] or _state["prepareLayer"] is None:
        return
    prepare = _state["prepareLayer"]
    call = _address_breakpoint(
        target,
        prepare["callAddress"],
        "merge_call",
        "merge call",
    )
    returned = _address_breakpoint(
        target,
        prepare["returnAddress"],
        "merge_return",
        "merge return",
    )
    _state["mergeCallBreakpoint"] = call
    _state["mergeReturnBreakpoint"] = returned
    _state["trace"]["mergeHelper"]["callBreakpointID"] = call.GetID()
    _state["trace"]["mergeHelper"]["returnBreakpointID"] = returned.GetID()
    _state["trace"]["status"] = "merge-breakpoints-armed"
    _write_trace()


def capture_backdrop_entry(frame, _breakpoint_location, _internal_dict):
    """Gate capture_backdrop and arm its exact late-state selector."""
    try:
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
    """Select the first exact preconvergence source/owner/layer chain."""
    try:
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
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
            process,
            layer_state + 0x120,
            "layer-state source pointer",
        )
        candidate.update(
            {
                "sourceOwner": source_owner,
                "layerStateSource": layer_state_source,
            }
        )
        pointer_chain_exact = (
            layer_state != 0
            and source_owner == owner
            and layer_state_source == source
        )
        candidate["pointerChainExact"] = pointer_chain_exact
        if not pointer_chain_exact:
            candidate["rejection"] = "object pointer chain differs"
            _reject_late_candidate(candidate)
            return False
        source_bytes = _read_memory(
            process, source + 0x50, 16, "source selected rectangle candidate"
        )
        layer_state_bytes = _read_memory(
            process,
            layer_state + 0xB0,
            16,
            "layer-state selected rectangle candidate",
        )
        owner_bytes = _read_memory(
            process, owner + 0xE0, 32, "owner selected rectangle candidate"
        )
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
        _state["objectAddresses"] = {
            "source": source,
            "owner": owner,
            "layer": layer,
            "layerState": layer_state,
        }
        _state["trace"]["lateCandidateCount"] = _state["lateCandidateCount"]
        _state["trace"]["objectChain"] = {
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
        _state["captureLateBreakpoint"].SetEnabled(False)
        _state["trace"]["status"] = "selected-source-ready"
        _try_arm_merge_breakpoints(target)
        _write_trace()
    except Exception as error:
        _failure("capture-backdrop-late", error)
        if _state["captureLateBreakpoint"] is not None:
            _state["captureLateBreakpoint"].SetEnabled(False)
    return False


def prepare_layer_entry(frame, _breakpoint_location, _internal_dict):
    """Gate the opened construction window and capture the decoded helper."""
    try:
        if frame.GetFunctionName() != PREPARE_LAYER_FUNCTION:
            raise RuntimeError("prepare_layer function identity differs")
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        symbol = frame.GetSymbol()
        if not symbol.IsValid():
            raise RuntimeError("prepare_layer symbol is unavailable")
        symbol_start = symbol.GetStartAddress().GetLoadAddress(target)
        symbol_end = symbol.GetEndAddress().GetLoadAddress(target)
        if (
            symbol_start == lldb.LLDB_INVALID_ADDRESS
            or symbol_end == lldb.LLDB_INVALID_ADDRESS
            or symbol_end - symbol_start != PREPARE_LAYER_SYMBOL_BYTE_COUNT
        ):
            raise RuntimeError("prepare_layer symbol bounds differ")
        window_address = symbol_start + PREPARE_LAYER_CODE_WINDOW_OFFSET
        code = _read_memory(
            process,
            window_address,
            PREPARE_LAYER_CODE_WINDOW_BYTE_COUNT,
            "prepare_layer construction window",
        )
        digest = hashlib.sha256(code).hexdigest()
        if digest != PREPARE_LAYER_CODE_WINDOW_SHA256:
            raise RuntimeError("prepare_layer construction window SHA-256 differs")
        call_address = symbol_start + MERGE_CALL_OFFSET
        call_payload = _read_memory(
            process, call_address, 4, "prepare_layer merge BL"
        )
        word, displacement, helper_address = _decode_bl_target(
            call_address, call_payload
        )
        if (
            call_payload != MERGE_CALL_RAW_LITTLE_ENDIAN
            or word != MERGE_CALL_WORD
            or displacement != MERGE_CALL_DISPLACEMENT
            or helper_address
            != symbol_start + MERGE_TARGET_RELATIVE_TO_PREPARE_LAYER
        ):
            raise RuntimeError("prepare_layer merge BL decode differs")
        helper_code = _read_memory(
            process,
            helper_address,
            MERGE_TARGET_CODE_BYTE_COUNT,
            "LayerShapes merge helper code",
        )
        helper_resolved = target.ResolveLoadAddress(helper_address)
        helper_module = helper_resolved.GetModule()
        prepare_module = frame.GetModule()
        helper_module_record = _module_record(helper_module, target)
        prepare_module_record = _module_record(prepare_module, target)
        if (
            not helper_module_record.get("valid")
            or helper_module_record != prepare_module_record
        ):
            raise RuntimeError("LayerShapes merge helper module differs")
        prepare_record = {
            "function": PREPARE_LAYER_FUNCTION,
            "symbolStart": symbol_start,
            "symbolEnd": symbol_end,
            "symbolByteCount": symbol_end - symbol_start,
            "module": prepare_module_record,
            "constructionCodeWindow": {
                "address": window_address,
                "symbolOffset": PREPARE_LAYER_CODE_WINDOW_OFFSET,
                "byteCount": len(code),
                "sha256": digest,
                "hex": code.hex(),
            },
            "callAddress": call_address,
            "returnAddress": symbol_start + MERGE_RETURN_OFFSET,
            "callInstructionRawLittleEndianHex": call_payload.hex(),
            "callInstructionWord": word,
            "callDisplacement": displacement,
            "decodedHelperAddress": helper_address,
        }
        _state["prepareLayer"] = prepare_record
        _state["trace"]["prepareLayer"] = prepare_record
        _state["trace"]["mergeHelper"] = {
            "address": helper_address,
            "relativeToPrepareLayer": helper_address - symbol_start,
            "module": helper_module_record,
            "symbol": _symbol_record(helper_resolved.GetSymbol(), target),
            "codeWindow": {
                "address": helper_address,
                "byteCount": len(helper_code),
                "sha256": hashlib.sha256(helper_code).hexdigest(),
                "hex": helper_code.hex(),
            },
        }
        _state["prepareEntryBreakpoint"].SetEnabled(False)
        _state["trace"]["status"] = "prepare-layer-helper-decoded"
        _try_arm_merge_breakpoints(target)
        _write_trace()
    except Exception as error:
        _failure("prepare-layer-entry", error)
        if _state["prepareEntryBreakpoint"] is not None:
            _state["prepareEntryBreakpoint"].SetEnabled(False)
    return False


def _disable_merge_breakpoints(status):
    if _state["mergeCallBreakpoint"] is not None:
        _state["mergeCallBreakpoint"].SetEnabled(False)
    if not _state["pendingByThread"] and _state["mergeReturnBreakpoint"] is not None:
        _state["mergeReturnBreakpoint"].SetEnabled(False)
    _state["trace"]["status"] = status


def merge_call(frame, _breakpoint_location, _internal_dict):
    """Capture exact selected-source operands immediately before the BL."""
    try:
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        _state["mergeCallSiteHitCount"] += 1
        source = _state["objectAddresses"]["source"]
        x28 = _register(frame, "x28")
        if x28 != source:
            _state["rejectedSourceCallCount"] += 1
            if _state["mergeCallSiteHitCount"] >= MAXIMUM_MERGE_CALL_SITE_HIT_COUNT:
                _disable_merge_breakpoints("merge-call-site-limit-reached")
                _write_trace()
            return False
        _state["selectedSourceCallCount"] += 1
        if thread_id in _state["pendingByThread"]:
            raise RuntimeError("selected-source merge call is nested on one thread")
        x0 = _register(frame, "x0")
        x1 = _register(frame, "x1")
        x2 = _register(frame, "x2")
        x19 = _register(frame, "x19")
        if x0 != x19 + 656 or x1 != x19 + 1568 or x2 != 1:
            raise RuntimeError("selected-source merge call aliases differ")
        prepare = _state["prepareLayer"]
        if frame.GetPC() != prepare["callAddress"]:
            raise RuntimeError("selected-source merge call PC differs")
        record = {
            "recordIndex": len(_state["trace"]["records"]),
            "complete": False,
            "threadID": thread_id,
            "selectedSource": source,
            "callPC": frame.GetPC(),
            "callFrame": _frame_record(frame, target),
            "callBacktrace": _backtrace(thread),
            "registersBefore": _register_snapshot(frame),
            "addresses": {
                "x19": x19,
                "aggregate": x0,
                "recursiveChild": x1,
                "source": x28,
            },
            "aggregateBefore": _memory_snapshot(
                process, x0, LAYER_SHAPES_BYTE_COUNT, "aggregate before merge"
            ),
            "recursiveChildBefore": _memory_snapshot(
                process, x1, LAYER_SHAPES_BYTE_COUNT, "child before merge"
            ),
            "roleStateBefore": _memory_snapshot(
                process, x19, ROLE_STATE_BYTE_COUNT, "role state before merge"
            ),
            "sourceObjectBefore": _memory_snapshot(
                process, x28, SOURCE_OBJECT_BYTE_COUNT, "source before merge"
            ),
        }
        _state["trace"]["records"].append(record)
        _state["pendingByThread"][thread_id] = record["recordIndex"]
        if len(_state["trace"]["records"]) >= MAXIMUM_COMPLETE_RECORD_COUNT:
            _state["mergeCallBreakpoint"].SetEnabled(False)
        _write_trace()
    except Exception as error:
        _failure("merge-call", error)
        _disable_merge_breakpoints("merge-call-failed")
    return False


def merge_return(frame, _breakpoint_location, _internal_dict):
    """Complete a selected-source record immediately after the BL returns."""
    try:
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        source = _state["objectAddresses"]["source"]
        if _register(frame, "x28") != source:
            _state["rejectedSourceReturnCount"] += 1
            return False
        record_index = _state["pendingByThread"].get(thread_id)
        if record_index is None:
            raise RuntimeError("selected-source merge return has no pending call")
        record = _state["trace"]["records"][record_index]
        addresses = record["addresses"]
        if (
            frame.GetPC() != _state["prepareLayer"]["returnAddress"]
            or _register(frame, "x19") != addresses["x19"]
            or _register(frame, "x28") != addresses["source"]
        ):
            raise RuntimeError("selected-source merge return identity differs")
        aggregate_after = _memory_snapshot(
            process,
            addresses["aggregate"],
            LAYER_SHAPES_BYTE_COUNT,
            "aggregate after merge",
        )
        child_after = _memory_snapshot(
            process,
            addresses["recursiveChild"],
            LAYER_SHAPES_BYTE_COUNT,
            "child after merge",
        )
        role_after = _memory_snapshot(
            process,
            addresses["x19"],
            ROLE_STATE_BYTE_COUNT,
            "role state after merge",
        )
        source_after = _memory_snapshot(
            process,
            addresses["source"],
            SOURCE_OBJECT_BYTE_COUNT,
            "source after merge",
        )
        record.update(
            {
                "complete": True,
                "returnPC": frame.GetPC(),
                "returnFrame": _frame_record(frame, target),
                "returnBacktrace": _backtrace(thread),
                "registersAfter": _register_snapshot(frame),
                "aggregateAfter": aggregate_after,
                "recursiveChildAfter": child_after,
                "roleStateAfter": role_after,
                "sourceObjectAfter": source_after,
                "aggregateChanged": (
                    record["aggregateBefore"]["hex"] != aggregate_after["hex"]
                ),
                "recursiveChildChanged": (
                    record["recursiveChildBefore"]["hex"] != child_after["hex"]
                ),
                "roleStateChanged": (
                    record["roleStateBefore"]["hex"] != role_after["hex"]
                ),
                "sourceObjectChanged": (
                    record["sourceObjectBefore"]["hex"] != source_after["hex"]
                ),
            }
        )
        del _state["pendingByThread"][thread_id]
        complete_count = sum(item["complete"] for item in _state["trace"]["records"])
        if complete_count >= MAXIMUM_COMPLETE_RECORD_COUNT:
            _disable_merge_breakpoints("record-limit-reached")
        _write_trace()
    except Exception as error:
        _failure("merge-return", error)
        _disable_merge_breakpoints("merge-return-failed")
    return False


def finalize():
    """Finalize the raw trace after LLDB's synchronous run command returns."""
    trace = _state["trace"]
    if trace is None:
        return
    trace["statusBeforeFinalization"] = trace["status"]
    trace["status"] = "finalized"
    trace["finalFailureCount"] = len(trace["failures"])
    trace["finalRecordCount"] = len(trace["records"])
    trace["finalCompleteRecordCount"] = sum(
        item.get("complete") is True for item in trace["records"]
    )
    trace["finalPendingRecordCount"] = len(_state["pendingByThread"])
    trace["mergeCallSiteHitCount"] = _state["mergeCallSiteHitCount"]
    trace["selectedSourceCallCount"] = _state["selectedSourceCallCount"]
    trace["rejectedSourceCallCount"] = _state["rejectedSourceCallCount"]
    trace["rejectedSourceReturnCount"] = _state["rejectedSourceReturnCount"]
    _write_trace()


def __lldb_init_module(debugger, _internal_dict):
    """Install pending exact-name breakpoints for both required Apple stages."""
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
