"""Open the two helpers left opaque by the small-geometry arithmetic trace.

The inherited sample, marker, ordinal, FilterOp, and SDFOp selectors remain
unchanged.  Before the frozen instruction trace starts, this adapter reads and
disassembles the complete code ranges of ``gaussian_expansion_factor`` and
``BackdropLayer::get_bounds`` using only their structural symbol identities.
Neither code hash nor any rectangle value is accepted before capture.

LLDB imports this module with macOS system Python, so it avoids syntax newer
than that runtime.
"""

import hashlib

import capture_prepare_layer_filter_sdf_small_geometry_lldb as frozen


trace_base = frozen.trace_base
capture_base = trace_base.capture_base

EXTENSION_SCHEMA_VERSION = 1
HELPER_SPECS = (
    {
        "name": "gaussianExpansionFactor",
        "function": "CA::OGL::gaussian_expansion_factor(double)",
        "relativeToPrepareLayer": -96880,
        "symbolByteCount": 200,
        "expectedCodeSHA256": None,
    },
    {
        "name": "backdropGetBounds",
        "function": (
            "CA::Render::BackdropLayer::get_bounds("
            "CA::Render::Layer const*, CA::Rect&, CA::Rect*) const"
        ),
        "relativeToPrepareLayer": 364616,
        "symbolByteCount": 80,
        "expectedCodeSHA256": None,
    },
)


def _new_extension():
    return {
        "prepareLayerSmallGeometryHelperCodeExtensionSchemaVersion": (
            EXTENSION_SCHEMA_VERSION
        ),
        "classification": (
            "prospective output-blind static code opening of the two helpers "
            "left opaque by the exact circle-127 Filter/SDF arithmetic trace"
        ),
        "status": "initialized",
        "configuration": {
            "material": "regular",
            "appearance": "light",
            "direction": "materialize",
            "geometry": frozen.EXPECTED_GEOMETRY,
            "selectedSampleIndex": 2,
            "selectedMarkerInterval": 2,
            "selectedQualifiedHelperOrdinal": 14,
            "filterDispatchOrdinal": 4,
            "sdfDispatchOrdinal": 2,
            "helperSpecifications": [dict(spec) for spec in HELPER_SPECS],
            "captureRule": (
                "while stopped at the unchanged structurally selected helper, "
                "resolve each preregistered function by prepare_layer-relative "
                "address, exact function name, and byte count; retain every "
                "code byte and static ARM64 instruction before starting the "
                "unchanged Filter/SDF execution trace"
            ),
            "staticMemoryReadsOnly": True,
            "breakpointsAdded": 0,
            "instructionStepsAdded": 0,
            "expectedCodeSHA256": None,
            "cropValuesUsedForSelection": False,
            "outputValuesUsedForSelection": False,
            "filterAndSDFCaptureChanged": False,
        },
        "targets": [],
        "failures": [],
    }


def _trace():
    return trace_base.crop_base._state.get("trace")


def _extension():
    trace = _trace()
    if trace is None:
        return None
    return trace.get("prepareLayerSmallGeometryHelperCodeExtension")


def _write_trace():
    frozen.frozen._write_trace()


def _failure(stage, error):
    extension = _extension()
    if extension is not None:
        extension["failures"].append(
            {"stage": str(stage), "message": str(error)}
        )
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
    result = frozen.prepare_layer_entry(
        frame, breakpoint_location, internal_dict
    )
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
    return frozen.prepare_layer_mask_entry(
        frame, breakpoint_location, internal_dict
    )


def _instruction_record(target, process, start, offset, code):
    pc = start + offset
    instructions = target.ReadInstructions(target.ResolveLoadAddress(pc), 1)
    if instructions.GetSize() != 1:
        raise RuntimeError("helper static instruction decode differs")
    instruction = instructions.GetInstructionAtIndex(0)
    instruction_pc = instruction.GetAddress().GetLoadAddress(target)
    raw = capture_base._read_memory(
        process, pc, 4, "helper static instruction"
    )
    if instruction_pc != pc or raw != code[offset : offset + 4]:
        raise RuntimeError("helper static instruction bytes differ")
    return {
        "pc": pc,
        "offset": offset,
        "rawLittleEndianHex": raw.hex(),
        "mnemonic": instruction.GetMnemonic(target) or "",
        "operands": instruction.GetOperands(target) or "",
        "comment": instruction.GetComment(target) or "",
    }


def _capture_target(process, prepare_start, spec):
    target = process.GetTarget()
    expected_start = prepare_start + spec["relativeToPrepareLayer"]
    resolved = target.ResolveLoadAddress(expected_start)
    symbol = resolved.GetSymbol()
    if not symbol.IsValid():
        raise RuntimeError(spec["name"] + " symbol is invalid")
    start = symbol.GetStartAddress().GetLoadAddress(target)
    end = symbol.GetEndAddress().GetLoadAddress(target)
    function = resolved.GetFunction().GetName() or symbol.GetName()
    if (
        start != expected_start
        or end - start != spec["symbolByteCount"]
        or function != spec["function"]
    ):
        raise RuntimeError(spec["name"] + " symbol identity differs")
    code = capture_base._read_memory(
        process, start, end - start, spec["name"] + " complete code"
    )
    instructions = [
        _instruction_record(target, process, start, offset, code)
        for offset in range(0, len(code), 4)
    ]
    return {
        "name": spec["name"],
        "function": spec["function"],
        "relativeToPrepareLayer": spec["relativeToPrepareLayer"],
        "symbolStart": start,
        "symbolEnd": end,
        "symbolByteCount": len(code),
        "expectedSHA256": None,
        "observedSHA256": hashlib.sha256(code).hexdigest(),
        "hex": code.hex(),
        "instructionCount": len(instructions),
        "instructions": instructions,
        "module": trace_base._module_record(resolved.GetModule(), target),
        "cropValuesUsedForSelection": False,
        "outputValuesUsedForSelection": False,
    }


def _capture_helper_code():
    extension = _extension()
    if extension is None:
        raise RuntimeError("helper-code extension is absent")
    if extension["status"] != "initialized" or extension["targets"]:
        raise RuntimeError("helper-code capture was invoked twice")
    process = trace_base._state["debugger"].GetSelectedTarget().GetProcess()
    trace_base._require_stopped(process, "small-geometry helper-code capture")
    trace = _trace()
    prepare_start = trace["prepareLayer"]["symbolStart"]
    extension["status"] = "static-code-capture-active"
    extension["targets"] = [
        _capture_target(process, prepare_start, spec) for spec in HELPER_SPECS
    ]
    extension["status"] = "static-code-capture-closed"
    _write_trace()


def trace_selected_sdf_filter_map_bounds():
    try:
        _capture_helper_code()
    except Exception as error:
        extension = _extension()
        if extension is not None:
            extension["status"] = "static-code-capture-failed"
        _failure("static-code-capture", error)
    return frozen.trace_selected_sdf_filter_map_bounds()


def finalize():
    frozen.finalize()
    extension = _extension()
    if extension is not None:
        extension["statusBeforeFinalization"] = extension["status"]
        extension["status"] = "finalized"
        extension["finalTargetCount"] = len(extension["targets"])
        extension["finalInstructionCount"] = sum(
            target["instructionCount"] for target in extension["targets"]
        )
        extension["finalFailureCount"] = len(extension["failures"])
    _write_trace()


def __lldb_init_module(debugger, internal_dict):
    frozen.__lldb_init_module(debugger, internal_dict)
    trace = _trace()
    if trace is None:
        return
    trace["prepareLayerSmallGeometryHelperCodeExtension"] = _new_extension()
    try:
        _install_callback_proxies()
        _write_trace()
    except Exception as error:
        _failure("initialization", error)
