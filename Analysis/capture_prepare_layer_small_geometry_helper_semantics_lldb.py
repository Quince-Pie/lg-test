"""Open Gaussian data words and the delegated backdrop-bounds function.

The accepted helper-code trace fixes every static address used here.  This
adapter reads the eight binary64 words referenced by the accepted Gaussian
instructions, its structurally referenced global-mode byte, and the complete
symbol reached by the accepted ``get_bounds+36`` call.  All values and the
callee code hash remain unknown before capture.  No breakpoint, selector,
instruction step, or inherited execution rule changes.

LLDB imports this module with macOS system Python, so it avoids syntax newer
than that runtime.
"""

import hashlib
import struct

import capture_prepare_layer_small_geometry_helper_code_callback_retry_lldb as frozen


helper_base = frozen.frozen
trace_base = helper_base.trace_base
capture_base = helper_base.capture_base

EXTENSION_SCHEMA_VERSION = 1
GAUSSIAN_RELATIVE_TO_PREPARE_LAYER = -96880
GAUSSIAN_BYTE_COUNT = 200
GAUSSIAN_CODE_SHA256 = (
    "7834bbb95f84915a6544d34b4148f7f267fcc94d2ae730888644535ffc57c0dd"
)
BACKDROP_WRAPPER_RELATIVE_TO_PREPARE_LAYER = 364616
BACKDROP_WRAPPER_BYTE_COUNT = 80
BACKDROP_WRAPPER_CODE_SHA256 = (
    "85a99558cc08c2a693969b55c804cd811e8ef710ac2d02460830f8bf9d6ec85a"
)
QUARTZCORE_UUID = "4D34EB4E-2BBB-3751-A362-8E2EB74656E8"
GET_BACKDROP_BOUNDS_RELATIVE_TO_PREPARE_LAYER = 364696
GET_BACKDROP_BOUNDS_FUNCTION = (
    "CA::Render::BackdropLayer::get_backdrop_bounds("
    "CA::Render::Layer const*, CA::Rect&) const"
)
GET_BACKDROP_BOUNDS_MAXIMUM_BYTE_COUNT = 65536
GLOBAL_FLAG_INSTRUCTION_OFFSET = 0
GLOBAL_FLAG_LOAD_OFFSET = 0xA8B
CONSTANT_SPECS = (
    {"name": "highThreshold", "moduleRelativeOffset": 0x394910},
    {"name": "lowThreshold", "moduleRelativeOffset": 0x394928},
    {"name": "activeShift", "moduleRelativeOffset": 0x394930},
    {"name": "logIntercept", "moduleRelativeOffset": 0x394938},
    {"name": "logSlope", "moduleRelativeOffset": 0x394940},
    {"name": "highIntercept", "moduleRelativeOffset": 0x394918},
    {"name": "highSlope", "moduleRelativeOffset": 0x394920},
    {"name": "alternateModeReturn", "moduleRelativeOffset": 0x3944F8},
)


def _new_extension():
    return {
        "prepareLayerSmallGeometryHelperSemanticsExtensionSchemaVersion": (
            EXTENSION_SCHEMA_VERSION
        ),
        "classification": (
            "prospective output-blind static opening of the data words and "
            "delegated function structurally referenced by accepted helper code"
        ),
        "status": "initialized",
        "configuration": {
            "material": "regular",
            "appearance": "light",
            "direction": "materialize",
            "geometry": "circle-127-center",
            "selectedSampleIndex": 2,
            "selectedMarkerInterval": 2,
            "selectedQualifiedHelperOrdinal": 14,
            "filterDispatchOrdinal": 4,
            "sdfDispatchOrdinal": 2,
            "gaussianCodeSHA256": GAUSSIAN_CODE_SHA256,
            "backdropWrapperCodeSHA256": BACKDROP_WRAPPER_CODE_SHA256,
            "quartzCoreUUID": QUARTZCORE_UUID,
            "constantSpecifications": [dict(spec) for spec in CONSTANT_SPECS],
            "constantValuesAcceptedBeforeCapture": None,
            "globalModeFlagValueAcceptedBeforeCapture": None,
            "getBackdropBoundsRelativeToPrepareLayer": (
                GET_BACKDROP_BOUNDS_RELATIVE_TO_PREPARE_LAYER
            ),
            "getBackdropBoundsFunction": GET_BACKDROP_BOUNDS_FUNCTION,
            "getBackdropBoundsMaximumByteCount": (
                GET_BACKDROP_BOUNDS_MAXIMUM_BYTE_COUNT
            ),
            "getBackdropBoundsExpectedCodeSHA256": None,
            "staticMemoryReadsOnly": True,
            "breakpointsAdded": 0,
            "instructionStepsAdded": 0,
            "cropValuesUsedForSelection": False,
            "outputValuesUsedForSelection": False,
            "inheritedCaptureChanged": False,
        },
        "gaussian": None,
        "getBackdropBounds": None,
        "failures": [],
    }


def _trace():
    return helper_base._trace()


def _extension():
    trace = _trace()
    if trace is None:
        return None
    return trace.get("prepareLayerSmallGeometryHelperSemanticsExtension")


def _write_trace():
    frozen._write_trace()


def _failure(stage, error):
    extension = _extension()
    if extension is not None:
        extension["failures"].append({"stage": str(stage), "message": str(error)})
    _write_trace()


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _install_callback_proxies():
    entry = trace_base.crop_base._state.get("prepareEntryBreakpoint")
    marker = trace_base.crop_base._state.get("markerBreakpoint")
    union_call = trace_base.union_base._state.get("unionCallBreakpoint")
    union_return = trace_base.union_base._state.get("unionReturnBreakpoint")
    store = trace_base.holdout_base._state.get("storeBreakpoint")
    helper = trace_base._state.get("helperBreakpoint")
    callbacks = (
        (entry, "prepare_layer_entry", "prepare entry"),
        (marker, "crop_transfer_marker", "crop transfer marker"),
        (union_call, "crop_union_call", "crop union call"),
        (union_return, "crop_union_return", "crop union return"),
        (store, "nested_crop_store", "nested crop store"),
        (helper, "prepare_layer_mask_entry", "prepare_layer_mask entry"),
    )
    for breakpoint, callback, label in callbacks:
        if breakpoint is not None:
            _set_callback(breakpoint, callback, label)


def prepare_layer_entry(frame, breakpoint_location, internal_dict):
    result = frozen.prepare_layer_entry(frame, breakpoint_location, internal_dict)
    try:
        _install_callback_proxies()
        _write_trace()
    except Exception as error:
        _failure("callback-proxy-entry", error)
    return result


def crop_union_call(frame, breakpoint_location, internal_dict):
    return frozen.crop_union_call(frame, breakpoint_location, internal_dict)


def crop_union_return(frame, breakpoint_location, internal_dict):
    return frozen.crop_union_return(frame, breakpoint_location, internal_dict)


def nested_crop_store(frame, breakpoint_location, internal_dict):
    return frozen.nested_crop_store(frame, breakpoint_location, internal_dict)


def crop_transfer_marker(frame, breakpoint_location, internal_dict):
    return frozen.crop_transfer_marker(frame, breakpoint_location, internal_dict)


def prepare_layer_mask_entry(frame, breakpoint_location, internal_dict):
    return frozen.prepare_layer_mask_entry(frame, breakpoint_location, internal_dict)


def _resolve_exact_code(process, start, function, byte_count, label):
    target = process.GetTarget()
    resolved = target.ResolveLoadAddress(start)
    symbol = resolved.GetSymbol()
    if not symbol.IsValid():
        raise RuntimeError(label + " symbol is invalid")
    observed_start = symbol.GetStartAddress().GetLoadAddress(target)
    observed_end = symbol.GetEndAddress().GetLoadAddress(target)
    observed_function = resolved.GetFunction().GetName() or symbol.GetName()
    if (
        observed_start != start
        or observed_end - observed_start != byte_count
        or observed_function != function
    ):
        raise RuntimeError(label + " symbol identity differs")
    code = capture_base._read_memory(
        process, observed_start, byte_count, label + " complete code"
    )
    return resolved, code


def _decode_adrp_target(pc, code):
    word = int.from_bytes(code, "little")
    if word & 0x9F000000 != 0x90000000:
        raise RuntimeError("Gaussian global flag instruction is not ADRP")
    immediate = (((word >> 5) & 0x7FFFF) << 2) | ((word >> 29) & 0x3)
    if immediate & (1 << 20):
        immediate -= 1 << 21
    return (pc & ~0xFFF) + (immediate << 12)


def _constant_record(process, module_base, spec):
    address = module_base + spec["moduleRelativeOffset"]
    raw = capture_base._read_memory(
        process, address, 8, spec["name"] + " binary64 word"
    )
    value = struct.unpack("<d", raw)[0]
    return {
        "name": spec["name"],
        "moduleRelativeOffset": spec["moduleRelativeOffset"],
        "address": address,
        "byteCount": len(raw),
        "rawLittleEndianHex": raw.hex(),
        "binary64Bits": int.from_bytes(raw, "little"),
        "binary64": value,
        "binary64Hex": value.hex(),
        "valueAcceptedBeforeCapture": None,
    }


def _capture_get_backdrop_bounds(process, prepare_start):
    target = process.GetTarget()
    expected_start = prepare_start + GET_BACKDROP_BOUNDS_RELATIVE_TO_PREPARE_LAYER
    resolved = target.ResolveLoadAddress(expected_start)
    symbol = resolved.GetSymbol()
    if not symbol.IsValid():
        raise RuntimeError("get_backdrop_bounds symbol is invalid")
    start = symbol.GetStartAddress().GetLoadAddress(target)
    end = symbol.GetEndAddress().GetLoadAddress(target)
    function = resolved.GetFunction().GetName() or symbol.GetName()
    byte_count = end - start
    if (
        start != expected_start
        or function != GET_BACKDROP_BOUNDS_FUNCTION
        or byte_count <= 0
        or byte_count > GET_BACKDROP_BOUNDS_MAXIMUM_BYTE_COUNT
        or byte_count % 4 != 0
    ):
        raise RuntimeError("get_backdrop_bounds symbol identity or size differs")
    code = capture_base._read_memory(
        process, start, byte_count, "get_backdrop_bounds complete code"
    )
    instructions = [
        helper_base._instruction_record(target, process, start, offset, code)
        for offset in range(0, byte_count, 4)
    ]
    return {
        "function": function,
        "relativeToPrepareLayer": GET_BACKDROP_BOUNDS_RELATIVE_TO_PREPARE_LAYER,
        "symbolStart": start,
        "symbolEnd": end,
        "symbolByteCount": byte_count,
        "maximumAcceptedByteCount": GET_BACKDROP_BOUNDS_MAXIMUM_BYTE_COUNT,
        "expectedCodeSHA256": None,
        "observedCodeSHA256": hashlib.sha256(code).hexdigest(),
        "hex": code.hex(),
        "instructionCount": len(instructions),
        "instructions": instructions,
        "module": trace_base._module_record(resolved.GetModule(), target),
        "cropValuesUsedForSelection": False,
        "outputValuesUsedForSelection": False,
    }


def _capture_semantics():
    extension = _extension()
    if extension is None:
        raise RuntimeError("helper-semantics extension is absent")
    if (
        extension["status"] != "initialized"
        or extension["gaussian"] is not None
        or extension["getBackdropBounds"] is not None
    ):
        raise RuntimeError("helper-semantics capture was invoked twice")
    process = trace_base._state["debugger"].GetSelectedTarget().GetProcess()
    trace_base._require_stopped(process, "small-geometry helper semantics")
    trace = _trace()
    prepare_start = trace["prepareLayer"]["symbolStart"]
    extension["status"] = "static-semantics-capture-active"

    gaussian_start = prepare_start + GAUSSIAN_RELATIVE_TO_PREPARE_LAYER
    gaussian_resolved, gaussian_code = _resolve_exact_code(
        process,
        gaussian_start,
        "CA::OGL::gaussian_expansion_factor(double)",
        GAUSSIAN_BYTE_COUNT,
        "Gaussian helper",
    )
    if hashlib.sha256(gaussian_code).hexdigest() != GAUSSIAN_CODE_SHA256:
        raise RuntimeError("Gaussian helper code SHA-256 differs")
    target = process.GetTarget()
    module = trace_base._module_record(gaussian_resolved.GetModule(), target)
    if module["uuid"] != QUARTZCORE_UUID:
        raise RuntimeError("QuartzCore UUID differs")
    module_base = module["loadAddress"]
    global_page = _decode_adrp_target(
        gaussian_start + GLOBAL_FLAG_INSTRUCTION_OFFSET,
        gaussian_code[
            GLOBAL_FLAG_INSTRUCTION_OFFSET : GLOBAL_FLAG_INSTRUCTION_OFFSET + 4
        ],
    )
    global_address = global_page + GLOBAL_FLAG_LOAD_OFFSET
    global_raw = capture_base._read_memory(
        process, global_address, 1, "Gaussian global mode flag"
    )

    wrapper_start = prepare_start + BACKDROP_WRAPPER_RELATIVE_TO_PREPARE_LAYER
    wrapper_resolved, wrapper_code = _resolve_exact_code(
        process,
        wrapper_start,
        (
            "CA::Render::BackdropLayer::get_bounds("
            "CA::Render::Layer const*, CA::Rect&, CA::Rect*) const"
        ),
        BACKDROP_WRAPPER_BYTE_COUNT,
        "backdrop wrapper",
    )
    if hashlib.sha256(wrapper_code).hexdigest() != BACKDROP_WRAPPER_CODE_SHA256:
        raise RuntimeError("backdrop wrapper code SHA-256 differs")
    wrapper_module = trace_base._module_record(wrapper_resolved.GetModule(), target)
    if wrapper_module != module:
        raise RuntimeError("helper modules differ")

    extension["gaussian"] = {
        "codeSHA256": GAUSSIAN_CODE_SHA256,
        "module": module,
        "globalModeFlag": {
            "instructionOffset": GLOBAL_FLAG_INSTRUCTION_OFFSET,
            "loadOffset": GLOBAL_FLAG_LOAD_OFFSET,
            "address": global_address,
            "byteCount": len(global_raw),
            "rawLittleEndianHex": global_raw.hex(),
            "unsignedValue": int.from_bytes(global_raw, "little"),
            "valueAcceptedBeforeCapture": None,
        },
        "constants": [
            _constant_record(process, module_base, spec) for spec in CONSTANT_SPECS
        ],
    }
    extension["getBackdropBounds"] = _capture_get_backdrop_bounds(
        process, prepare_start
    )
    extension["status"] = "static-semantics-capture-closed"
    _write_trace()


def trace_selected_sdf_filter_map_bounds():
    try:
        _capture_semantics()
    except Exception as error:
        extension = _extension()
        if extension is not None:
            extension["status"] = "static-semantics-capture-failed"
        _failure("static-semantics-capture", error)
    return frozen.trace_selected_sdf_filter_map_bounds()


def finalize():
    frozen.finalize()
    extension = _extension()
    if extension is not None:
        extension["statusBeforeFinalization"] = extension["status"]
        extension["status"] = "finalized"
        extension["finalFailureCount"] = len(extension["failures"])
    _write_trace()


def __lldb_init_module(debugger, internal_dict):
    frozen.__lldb_init_module(debugger, internal_dict)
    trace = _trace()
    if trace is None:
        return
    trace["prepareLayerSmallGeometryHelperSemanticsExtension"] = _new_extension()
    try:
        _install_callback_proxies()
        _write_trace()
    except Exception as error:
        _failure("initialization", error)
