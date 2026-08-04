"""LLDB callbacks for both Apple LayerShapes aggregate-construction branches.

The direct ``union_bounds`` call executes before the downstream source selector,
so this probe arms at the first ``prepare_layer`` entry, retains a bounded
preselection prefix, and classifies recorded x28 identities retrospectively.
It also pairs the alternate x19+1312 to x19+656 store used by later updates.
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
DIRECT_CALL_OFFSET = 0x32C0
DIRECT_RETURN_OFFSET = 0x32C4
DIRECT_CALL_RAW_LITTLE_ENDIAN = bytes.fromhex("a8f0ff97")
DIRECT_CALL_WORD = 0x97FFF0A8
DIRECT_CALL_DISPLACEMENT = -0x3D60
UNION_HELPER_RELATIVE_TO_PREPARE_LAYER = -0xAA0
UNION_HELPER_SYMBOL_NAME = (
    "CA::Render::Updater::LayerShapes::union_bounds(CA::Rect const&, bool)"
)
UNION_HELPER_SYMBOL_BYTE_COUNT = 404
UNION_HELPER_SYMBOL_SHA256 = (
    "246257a9bc1a608f59dbc07345397a8851b49528c59407eb775e9b9895a2c4b7"
)
UNION_HELPER_CODE_WINDOW_BYTE_COUNT = 0x1000
UNION_HELPER_CODE_WINDOW_SHA256 = (
    "6ef1454472d8fe5754253f26faa8db1f5473396b9879b74dcbe16fb7ffd4d10b"
)
ALTERNATE_STORE_OFFSET = 0x33F0
ALTERNATE_AFTER_OFFSET = 0x33F4
ALTERNATE_STORE_RAW_LITTLE_ENDIAN = bytes.fromhex("608614ad")
LAYER_SHAPES_BYTE_COUNT = 0x20
ROLE_STATE_BYTE_COUNT = 0x800
MAXIMUM_LATE_CANDIDATE_COUNT = 512
MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT = 16
MAXIMUM_DIRECT_CALL_SITE_HIT_COUNT = 4096
MAXIMUM_DIRECT_RECORD_COUNT = 64
MAXIMUM_ALTERNATE_STORE_HIT_COUNT = 4096
MAXIMUM_ALTERNATE_RECORD_COUNT = 96
MAXIMUM_BACKTRACE_FRAME_COUNT = 20
TRACE_OUTPUT_ENVIRONMENT = "LG_LAYER_SHAPES_CONSTRUCTION_TRACE_OUTPUT"
DEFAULT_TRACE_OUTPUT = (
    "transition-introspection/layer-shapes-construction-trace.json"
)
GENERAL_REGISTER_NAMES = ("x0", "x1", "x2", "x19", "x28", "x30", "sp", "pc")
ALTERNATE_SIMD_REGISTER_NAMES = ("v0", "v1")


_state = {
    "captureEntryBreakpoint": None,
    "captureLateBreakpoint": None,
    "prepareEntryBreakpoint": None,
    "directCallBreakpoint": None,
    "directReturnBreakpoint": None,
    "alternateStoreBreakpoint": None,
    "alternateAfterBreakpoint": None,
    "lateCandidateCount": 0,
    "objectAddresses": {},
    "prepareLayer": None,
    "pendingDirectByThread": {},
    "pendingAlternateByThread": {},
    "directCallSiteHitCount": 0,
    "alternateStoreHitCount": 0,
    "rejectedAlternateStoreCount": 0,
    "rejectedAlternateAfterCount": 0,
    "trace": None,
}


def _trace_path():
    return Path(os.environ.get(TRACE_OUTPUT_ENVIRONMENT, DEFAULT_TRACE_OUTPUT))


def _new_trace():
    return {
        "layerShapesConstructionTraceSchemaVersion": TRACE_SCHEMA_VERSION,
        "classification": (
            "preregistered-bounded-early-direct-and-dynamic-alternate-layer-"
            "shapes-construction-trace; branch-semantics-public-crop-law-unseen-"
            "transfer-and-product-parity-remain-sealed"
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
            "prepareLayerCodeWindowByteCount": PREPARE_LAYER_CODE_WINDOW_BYTE_COUNT,
            "prepareLayerCodeWindowSHA256": PREPARE_LAYER_CODE_WINDOW_SHA256,
            "directCallOffset": DIRECT_CALL_OFFSET,
            "directReturnOffset": DIRECT_RETURN_OFFSET,
            "directCallRawLittleEndianHex": DIRECT_CALL_RAW_LITTLE_ENDIAN.hex(),
            "directCallWord": DIRECT_CALL_WORD,
            "directCallDisplacement": DIRECT_CALL_DISPLACEMENT,
            "unionHelperRelativeToPrepareLayer": (
                UNION_HELPER_RELATIVE_TO_PREPARE_LAYER
            ),
            "unionHelperSymbolName": UNION_HELPER_SYMBOL_NAME,
            "unionHelperSymbolByteCount": UNION_HELPER_SYMBOL_BYTE_COUNT,
            "unionHelperSymbolSHA256": UNION_HELPER_SYMBOL_SHA256,
            "unionHelperCodeWindowByteCount": UNION_HELPER_CODE_WINDOW_BYTE_COUNT,
            "unionHelperCodeWindowSHA256": UNION_HELPER_CODE_WINDOW_SHA256,
            "alternateStoreOffset": ALTERNATE_STORE_OFFSET,
            "alternateAfterOffset": ALTERNATE_AFTER_OFFSET,
            "alternateStoreRawLittleEndianHex": (
                ALTERNATE_STORE_RAW_LITTLE_ENDIAN.hex()
            ),
            "layerShapesByteCount": LAYER_SHAPES_BYTE_COUNT,
            "roleStateByteCount": ROLE_STATE_BYTE_COUNT,
            "maximumLateCandidateCount": MAXIMUM_LATE_CANDIDATE_COUNT,
            "maximumLateCandidateDiagnosticCount": (
                MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT
            ),
            "maximumDirectCallSiteHitCount": MAXIMUM_DIRECT_CALL_SITE_HIT_COUNT,
            "maximumDirectRecordCount": MAXIMUM_DIRECT_RECORD_COUNT,
            "maximumAlternateStoreHitCount": MAXIMUM_ALTERNATE_STORE_HIT_COUNT,
            "maximumAlternateRecordCount": MAXIMUM_ALTERNATE_RECORD_COUNT,
            "maximumBacktraceFrameCount": MAXIMUM_BACKTRACE_FRAME_COUNT,
            "generalRegisterNames": list(GENERAL_REGISTER_NAMES),
            "alternateSIMDRegisterNames": list(ALTERNATE_SIMD_REGISTER_NAMES),
            "directRecordRule": (
                "retain every early prepare_layer+0x32c0 call pair up to the "
                "bound, then classify x28 against the downstream selected source"
            ),
            "alternateRecordRule": (
                "retain every preselection prepare_layer+0x33f0 store pair; after "
                "selection retain only pairs whose x28 is the selected source"
            ),
        },
        "captureBackdrop": {},
        "prepareLayer": {},
        "unionHelper": {},
        "lateCandidateCount": 0,
        "lateCandidateDiagnostics": [],
        "objectChain": {},
        "directRecords": [],
        "alternateRecords": [],
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


def _selected_source():
    return _state["objectAddresses"].get("source")


def _classify_records():
    source = _selected_source()
    if source is None:
        return
    for collection in ("directRecords", "alternateRecords"):
        for record in _state["trace"][collection]:
            record["selectedSource"] = record["addresses"]["source"] == source


def capture_backdrop_entry(frame, _breakpoint_location, _internal_dict):
    """Gate capture_backdrop and arm its exact downstream source selector."""
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
    """Select the exact source and classify already-captured construction."""
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
            process,
            layer_state + 0x120,
            "layer-state source pointer",
        )
        pointer_chain_exact = (
            source_owner == owner and layer_state_source == source
        )
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
        _classify_records()
        _state["captureLateBreakpoint"].SetEnabled(False)
        _state["trace"]["status"] = "source-selected-construction-active"
        _write_trace()
    except Exception as error:
        _failure("capture-backdrop-late", error)
        if _state["captureLateBreakpoint"] is not None:
            _state["captureLateBreakpoint"].SetEnabled(False)
    return False


def prepare_layer_entry(frame, _breakpoint_location, _internal_dict):
    """Gate all opened bytes and arm both branches before this call proceeds."""
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
        if hashlib.sha256(code).hexdigest() != PREPARE_LAYER_CODE_WINDOW_SHA256:
            raise RuntimeError("prepare_layer construction window SHA-256 differs")
        direct_call_address = symbol_start + DIRECT_CALL_OFFSET
        direct_payload = _read_memory(
            process, direct_call_address, 4, "prepare_layer direct union BL"
        )
        word, displacement, helper_address = _decode_bl_target(
            direct_call_address, direct_payload
        )
        if (
            direct_payload != DIRECT_CALL_RAW_LITTLE_ENDIAN
            or word != DIRECT_CALL_WORD
            or displacement != DIRECT_CALL_DISPLACEMENT
            or helper_address
            != symbol_start + UNION_HELPER_RELATIVE_TO_PREPARE_LAYER
        ):
            raise RuntimeError("prepare_layer direct union BL differs")
        alternate_address = symbol_start + ALTERNATE_STORE_OFFSET
        alternate_payload = _read_memory(
            process, alternate_address, 4, "prepare_layer alternate store"
        )
        if alternate_payload != ALTERNATE_STORE_RAW_LITTLE_ENDIAN:
            raise RuntimeError("prepare_layer alternate store bytes differ")
        helper_code = _read_memory(
            process,
            helper_address,
            UNION_HELPER_CODE_WINDOW_BYTE_COUNT,
            "union_bounds code window",
        )
        if hashlib.sha256(helper_code).hexdigest() != UNION_HELPER_CODE_WINDOW_SHA256:
            raise RuntimeError("union_bounds code window SHA-256 differs")
        helper_resolved = target.ResolveLoadAddress(helper_address)
        helper_module = _module_record(helper_resolved.GetModule(), target)
        prepare_module = _module_record(frame.GetModule(), target)
        helper_symbol = _symbol_record(helper_resolved.GetSymbol(), target)
        if (
            helper_module != prepare_module
            or helper_symbol.get("valid") is not True
            or helper_symbol.get("name") != UNION_HELPER_SYMBOL_NAME
            or helper_symbol.get("startAddress") != helper_address
            or helper_symbol.get("endAddress") - helper_address
            != UNION_HELPER_SYMBOL_BYTE_COUNT
            or hashlib.sha256(
                helper_code[:UNION_HELPER_SYMBOL_BYTE_COUNT]
            ).hexdigest()
            != UNION_HELPER_SYMBOL_SHA256
        ):
            raise RuntimeError("union_bounds symbol identity differs")
        prepare_record = {
            "function": PREPARE_LAYER_FUNCTION,
            "symbolStart": symbol_start,
            "symbolEnd": symbol_end,
            "symbolByteCount": symbol_end - symbol_start,
            "module": prepare_module,
            "constructionCodeWindow": {
                "address": window_address,
                "symbolOffset": PREPARE_LAYER_CODE_WINDOW_OFFSET,
                "byteCount": len(code),
                "sha256": hashlib.sha256(code).hexdigest(),
                "hex": code.hex(),
            },
            "directCallAddress": direct_call_address,
            "directReturnAddress": symbol_start + DIRECT_RETURN_OFFSET,
            "directCallRawLittleEndianHex": direct_payload.hex(),
            "directCallWord": word,
            "directCallDisplacement": displacement,
            "alternateStoreAddress": alternate_address,
            "alternateAfterAddress": symbol_start + ALTERNATE_AFTER_OFFSET,
            "alternateStoreRawLittleEndianHex": alternate_payload.hex(),
        }
        _state["prepareLayer"] = prepare_record
        _state["trace"]["prepareLayer"] = prepare_record
        _state["trace"]["unionHelper"] = {
            "address": helper_address,
            "relativeToPrepareLayer": helper_address - symbol_start,
            "module": helper_module,
            "symbol": helper_symbol,
            "codeWindow": {
                "address": helper_address,
                "byteCount": len(helper_code),
                "sha256": hashlib.sha256(helper_code).hexdigest(),
                "hex": helper_code.hex(),
            },
        }
        breakpoint_specs = (
            (
                "directCallBreakpoint",
                direct_call_address,
                "direct_union_call",
                "direct union call",
            ),
            (
                "directReturnBreakpoint",
                symbol_start + DIRECT_RETURN_OFFSET,
                "direct_union_return",
                "direct union return",
            ),
            (
                "alternateStoreBreakpoint",
                alternate_address,
                "alternate_store_before",
                "alternate store",
            ),
            (
                "alternateAfterBreakpoint",
                symbol_start + ALTERNATE_AFTER_OFFSET,
                "alternate_store_after",
                "alternate after store",
            ),
        )
        for state_name, address, callback, label in breakpoint_specs:
            breakpoint = _address_breakpoint(target, address, callback, label)
            _state[state_name] = breakpoint
            _state["trace"]["prepareLayer"][state_name + "ID"] = breakpoint.GetID()
        _state["prepareEntryBreakpoint"].SetEnabled(False)
        _state["trace"]["status"] = "construction-breakpoints-armed"
        _write_trace()
    except Exception as error:
        _failure("prepare-layer-entry", error)
        if _state["prepareEntryBreakpoint"] is not None:
            _state["prepareEntryBreakpoint"].SetEnabled(False)
    return False


def _disable_pair_breakpoints(prefix, pending):
    before = _state[prefix + "Breakpoint"]
    after = _state[
        "directReturnBreakpoint"
        if prefix == "directCall"
        else "alternateAfterBreakpoint"
    ]
    if before is not None:
        before.SetEnabled(False)
    if not pending and after is not None:
        after.SetEnabled(False)


def direct_union_call(frame, _breakpoint_location, _internal_dict):
    """Retain every bounded direct pair before source identity is known."""
    try:
        _state["directCallSiteHitCount"] += 1
        if _state["directCallSiteHitCount"] > MAXIMUM_DIRECT_CALL_SITE_HIT_COUNT:
            _disable_pair_breakpoints("directCall", _state["pendingDirectByThread"])
            return False
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        if thread_id in _state["pendingDirectByThread"]:
            raise RuntimeError("direct union call is nested on one thread")
        x0 = _register(frame, "x0")
        x1 = _register(frame, "x1")
        x2 = _register(frame, "x2")
        x19 = _register(frame, "x19")
        x28 = _register(frame, "x28")
        if (
            frame.GetPC() != _state["prepareLayer"]["directCallAddress"]
            or x0 != x19 + 656
            or x1 != x19 + 1568
            or x2 != 1
        ):
            raise RuntimeError("direct union call identity differs")
        record = {
            "recordIndex": len(_state["trace"]["directRecords"]),
            "complete": False,
            "selectedSource": (
                None if _selected_source() is None else x28 == _selected_source()
            ),
            "sourceKnownAtCall": _selected_source() is not None,
            "threadID": thread_id,
            "callPC": frame.GetPC(),
            "callFrame": _frame_record(frame, target),
            "callBacktrace": _backtrace(thread),
            "registersBefore": _register_snapshot(frame, GENERAL_REGISTER_NAMES),
            "addresses": {
                "x19": x19,
                "aggregate": x0,
                "recursiveChild": x1,
                "source": x28,
            },
            "aggregateBefore": _memory_snapshot(
                process, x0, LAYER_SHAPES_BYTE_COUNT, "direct aggregate before"
            ),
            "recursiveChildBefore": _memory_snapshot(
                process, x1, LAYER_SHAPES_BYTE_COUNT, "direct child before"
            ),
            "roleStateBefore": _memory_snapshot(
                process, x19, ROLE_STATE_BYTE_COUNT, "direct role state before"
            ),
        }
        _state["trace"]["directRecords"].append(record)
        _state["pendingDirectByThread"][thread_id] = record["recordIndex"]
        if len(_state["trace"]["directRecords"]) >= MAXIMUM_DIRECT_RECORD_COUNT:
            _state["directCallBreakpoint"].SetEnabled(False)
        _write_trace()
    except Exception as error:
        _failure("direct-union-call", error)
        _disable_pair_breakpoints("directCall", _state["pendingDirectByThread"])
    return False


def direct_union_return(frame, _breakpoint_location, _internal_dict):
    """Complete one direct union pair at prepare_layer+0x32c4."""
    try:
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        record_index = _state["pendingDirectByThread"].get(thread_id)
        if record_index is None:
            raise RuntimeError("direct union return has no pending call")
        record = _state["trace"]["directRecords"][record_index]
        addresses = record["addresses"]
        if (
            frame.GetPC() != _state["prepareLayer"]["directReturnAddress"]
            or _register(frame, "x19") != addresses["x19"]
            or _register(frame, "x28") != addresses["source"]
        ):
            raise RuntimeError("direct union return identity differs")
        aggregate_after = _memory_snapshot(
            process,
            addresses["aggregate"],
            LAYER_SHAPES_BYTE_COUNT,
            "direct aggregate after",
        )
        child_after = _memory_snapshot(
            process,
            addresses["recursiveChild"],
            LAYER_SHAPES_BYTE_COUNT,
            "direct child after",
        )
        role_after = _memory_snapshot(
            process,
            addresses["x19"],
            ROLE_STATE_BYTE_COUNT,
            "direct role state after",
        )
        record.update(
            {
                "complete": True,
                "returnPC": frame.GetPC(),
                "returnFrame": _frame_record(frame, target),
                "returnBacktrace": _backtrace(thread),
                "registersAfter": _register_snapshot(frame, GENERAL_REGISTER_NAMES),
                "aggregateAfter": aggregate_after,
                "recursiveChildAfter": child_after,
                "roleStateAfter": role_after,
                "aggregateChanged": (
                    record["aggregateBefore"]["hex"] != aggregate_after["hex"]
                ),
                "recursiveChildChanged": (
                    record["recursiveChildBefore"]["hex"] != child_after["hex"]
                ),
                "roleStateChanged": (
                    record["roleStateBefore"]["hex"] != role_after["hex"]
                ),
            }
        )
        del _state["pendingDirectByThread"][thread_id]
        if len(_state["trace"]["directRecords"]) >= MAXIMUM_DIRECT_RECORD_COUNT:
            _disable_pair_breakpoints("directCall", _state["pendingDirectByThread"])
        _write_trace()
    except Exception as error:
        _failure("direct-union-return", error)
        _disable_pair_breakpoints("directCall", _state["pendingDirectByThread"])
    return False


def alternate_store_before(frame, _breakpoint_location, _internal_dict):
    """Capture x19+1312 and q0/q1 immediately before the aggregate store."""
    try:
        _state["alternateStoreHitCount"] += 1
        if _state["alternateStoreHitCount"] > MAXIMUM_ALTERNATE_STORE_HIT_COUNT:
            _disable_pair_breakpoints(
                "alternateStore", _state["pendingAlternateByThread"]
            )
            return False
        x28 = _register(frame, "x28")
        source = _selected_source()
        if source is not None and x28 != source:
            _state["rejectedAlternateStoreCount"] += 1
            return False
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        if thread_id in _state["pendingAlternateByThread"]:
            raise RuntimeError("alternate store is nested on one thread")
        x19 = _register(frame, "x19")
        if frame.GetPC() != _state["prepareLayer"]["alternateStoreAddress"]:
            raise RuntimeError("alternate store PC differs")
        aggregate_address = x19 + 656
        alternate_source_address = x19 + 1312
        record = {
            "recordIndex": len(_state["trace"]["alternateRecords"]),
            "complete": False,
            "selectedSource": None if source is None else True,
            "sourceKnownAtStore": source is not None,
            "threadID": thread_id,
            "storePC": frame.GetPC(),
            "storeFrame": _frame_record(frame, target),
            "storeBacktrace": _backtrace(thread),
            "registersBefore": _register_snapshot(frame, GENERAL_REGISTER_NAMES),
            "simdSourceRegisters": _register_snapshot(
                frame, ALTERNATE_SIMD_REGISTER_NAMES
            ),
            "addresses": {
                "x19": x19,
                "aggregate": aggregate_address,
                "alternateSource": alternate_source_address,
                "source": x28,
            },
            "aggregateBefore": _memory_snapshot(
                process,
                aggregate_address,
                LAYER_SHAPES_BYTE_COUNT,
                "alternate aggregate before",
            ),
            "alternateSourceBefore": _memory_snapshot(
                process,
                alternate_source_address,
                LAYER_SHAPES_BYTE_COUNT,
                "alternate source before",
            ),
            "roleStateBefore": _memory_snapshot(
                process, x19, ROLE_STATE_BYTE_COUNT, "alternate role state before"
            ),
        }
        _state["trace"]["alternateRecords"].append(record)
        _state["pendingAlternateByThread"][thread_id] = record["recordIndex"]
        if len(_state["trace"]["alternateRecords"]) >= MAXIMUM_ALTERNATE_RECORD_COUNT:
            _state["alternateStoreBreakpoint"].SetEnabled(False)
        _write_trace()
    except Exception as error:
        _failure("alternate-store-before", error)
        _disable_pair_breakpoints(
            "alternateStore", _state["pendingAlternateByThread"]
        )
    return False


def alternate_store_after(frame, _breakpoint_location, _internal_dict):
    """Complete one x19+1312 to x19+656 store pair."""
    try:
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        x28 = _register(frame, "x28")
        source = _selected_source()
        record_index = _state["pendingAlternateByThread"].get(thread_id)
        if record_index is None:
            if source is not None and x28 != source:
                _state["rejectedAlternateAfterCount"] += 1
                return False
            raise RuntimeError("alternate after-store has no pending record")
        process = thread.GetProcess()
        target = process.GetTarget()
        record = _state["trace"]["alternateRecords"][record_index]
        addresses = record["addresses"]
        if (
            frame.GetPC() != _state["prepareLayer"]["alternateAfterAddress"]
            or _register(frame, "x19") != addresses["x19"]
            or x28 != addresses["source"]
        ):
            raise RuntimeError("alternate after-store identity differs")
        aggregate_after = _memory_snapshot(
            process,
            addresses["aggregate"],
            LAYER_SHAPES_BYTE_COUNT,
            "alternate aggregate after",
        )
        alternate_source_after = _memory_snapshot(
            process,
            addresses["alternateSource"],
            LAYER_SHAPES_BYTE_COUNT,
            "alternate source after",
        )
        role_after = _memory_snapshot(
            process,
            addresses["x19"],
            ROLE_STATE_BYTE_COUNT,
            "alternate role state after",
        )
        record.update(
            {
                "complete": True,
                "afterPC": frame.GetPC(),
                "afterFrame": _frame_record(frame, target),
                "afterBacktrace": _backtrace(thread),
                "registersAfter": _register_snapshot(frame, GENERAL_REGISTER_NAMES),
                "aggregateAfter": aggregate_after,
                "alternateSourceAfter": alternate_source_after,
                "roleStateAfter": role_after,
                "aggregateChanged": (
                    record["aggregateBefore"]["hex"] != aggregate_after["hex"]
                ),
                "alternateSourceChanged": (
                    record["alternateSourceBefore"]["hex"]
                    != alternate_source_after["hex"]
                ),
                "roleStateChanged": (
                    record["roleStateBefore"]["hex"] != role_after["hex"]
                ),
            }
        )
        del _state["pendingAlternateByThread"][thread_id]
        if len(_state["trace"]["alternateRecords"]) >= MAXIMUM_ALTERNATE_RECORD_COUNT:
            _disable_pair_breakpoints(
                "alternateStore", _state["pendingAlternateByThread"]
            )
        _write_trace()
    except Exception as error:
        _failure("alternate-store-after", error)
        _disable_pair_breakpoints(
            "alternateStore", _state["pendingAlternateByThread"]
        )
    return False


def finalize():
    """Finalize the trace after LLDB's synchronous run command returns."""
    trace = _state["trace"]
    if trace is None:
        return
    _classify_records()
    trace["statusBeforeFinalization"] = trace["status"]
    trace["status"] = "finalized"
    trace["finalFailureCount"] = len(trace["failures"])
    trace["directCallSiteHitCount"] = _state["directCallSiteHitCount"]
    trace["alternateStoreHitCount"] = _state["alternateStoreHitCount"]
    trace["rejectedAlternateStoreCount"] = _state[
        "rejectedAlternateStoreCount"
    ]
    trace["rejectedAlternateAfterCount"] = _state[
        "rejectedAlternateAfterCount"
    ]
    trace["finalDirectRecordCount"] = len(trace["directRecords"])
    trace["finalCompleteDirectRecordCount"] = sum(
        item.get("complete") is True for item in trace["directRecords"]
    )
    trace["finalSelectedDirectRecordCount"] = sum(
        item.get("complete") is True and item.get("selectedSource") is True
        for item in trace["directRecords"]
    )
    trace["finalPendingDirectRecordCount"] = len(_state["pendingDirectByThread"])
    trace["finalAlternateRecordCount"] = len(trace["alternateRecords"])
    trace["finalCompleteAlternateRecordCount"] = sum(
        item.get("complete") is True for item in trace["alternateRecords"]
    )
    trace["finalSelectedAlternateRecordCount"] = sum(
        item.get("complete") is True and item.get("selectedSource") is True
        for item in trace["alternateRecords"]
    )
    trace["finalPendingAlternateRecordCount"] = len(
        _state["pendingAlternateByThread"]
    )
    _write_trace()


def __lldb_init_module(debugger, _internal_dict):
    """Install pending exact-name breakpoints for the two Apple stages."""
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
