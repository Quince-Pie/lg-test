"""Retain live backdrop state and discover its class-scoped writer code.

The accepted FilterOp tracer already steps over the unique structurally joined
``BackdropLayer::get_bounds`` boundary.  This adapter wraps that existing step
without adding a breakpoint or instruction step, snapshots the receiver and
layer objects on both sides, and statically inventories complete QuartzCore
code symbols containing ``BackdropLayer``.  Field values, pointer layout,
symbol inventory, code hashes, and writer identity are all unknown before
capture.

LLDB imports this module with macOS system Python, so it avoids syntax newer
than that runtime.
"""

import hashlib

import lldb

import capture_prepare_layer_small_geometry_helper_semantics_lldb as frozen


trace_base = frozen.trace_base
capture_base = frozen.capture_base
helper_base = frozen.helper_base
filter_module = helper_base.frozen.frozen.frozen.frozen
producer_base = filter_module.producer_base
_original_trace_opaque_callee = producer_base._trace_opaque_callee

EXTENSION_SCHEMA_VERSION = 1
BACKDROP_WRAPPER_FUNCTION = (
    "CA::Render::BackdropLayer::get_bounds("
    "CA::Render::Layer const*, CA::Rect&, CA::Rect*) const"
)
BACKDROP_WRAPPER_RELATIVE_TO_PREPARE_LAYER = 364616
BACKDROP_WRAPPER_CODE_SHA256 = (
    "85a99558cc08c2a693969b55c804cd811e8ef710ac2d02460830f8bf9d6ec85a"
)
GET_BACKDROP_BOUNDS_CODE_SHA256 = (
    "3296daa4d858acc2a259be7771e48c312ff7010fa3d7cd590a9f28bd17a4ff17"
)
QUARTZCORE_UUID = "4D34EB4E-2BBB-3751-A362-8E2EB74656E8"
BACKDROP_OBJECT_BYTE_COUNT = 0x90
LAYER_OBJECT_BYTE_COUNT = 0x140
RECT_BYTE_COUNT = 0x20
SYMBOL_NAME_SUBSTRING = "BackdropLayer"
MAXIMUM_MATCHED_CODE_SYMBOL_COUNT = 256
MAXIMUM_INDIVIDUAL_SYMBOL_BYTE_COUNT = 65536
MAXIMUM_TOTAL_SYMBOL_BYTE_COUNT = 2 * 1024 * 1024


def _new_extension():
    return {
        "prepareLayerBackdropStateWriterDiscoveryExtensionSchemaVersion": (
            EXTENSION_SCHEMA_VERSION
        ),
        "classification": (
            "prospective output-blind live-object snapshot at an accepted opaque "
            "boundary plus static class-scoped QuartzCore writer discovery"
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
            "backdropWrapperFunction": BACKDROP_WRAPPER_FUNCTION,
            "backdropWrapperRelativeToPrepareLayer": (
                BACKDROP_WRAPPER_RELATIVE_TO_PREPARE_LAYER
            ),
            "backdropWrapperCodeSHA256": BACKDROP_WRAPPER_CODE_SHA256,
            "getBackdropBoundsCodeSHA256": GET_BACKDROP_BOUNDS_CODE_SHA256,
            "quartzCoreUUID": QUARTZCORE_UUID,
            "backdropObjectByteCount": BACKDROP_OBJECT_BYTE_COUNT,
            "layerObjectByteCount": LAYER_OBJECT_BYTE_COUNT,
            "primaryRectByteCount": RECT_BYTE_COUNT,
            "selfLayerPointerDeltaAcceptedBeforeCapture": None,
            "backdropFieldValuesAcceptedBeforeCapture": None,
            "layerFieldValuesAcceptedBeforeCapture": None,
            "symbolNameSubstring": SYMBOL_NAME_SUBSTRING,
            "maximumMatchedCodeSymbolCount": MAXIMUM_MATCHED_CODE_SYMBOL_COUNT,
            "maximumIndividualSymbolByteCount": (MAXIMUM_INDIVIDUAL_SYMBOL_BYTE_COUNT),
            "maximumTotalSymbolByteCount": MAXIMUM_TOTAL_SYMBOL_BYTE_COUNT,
            "symbolInventoryCountAcceptedBeforeCapture": None,
            "symbolNamesAcceptedBeforeCapture": None,
            "symbolCodeHashesAcceptedBeforeCapture": None,
            "newBreakpointsAdded": 0,
            "newInstructionStepsAdded": 0,
            "existingOpaqueBoundaryStepWrapped": True,
            "cropValuesUsedForSelection": False,
            "outputValuesUsedForSelection": False,
            "inheritedCaptureChanged": False,
        },
        "symbolInventory": None,
        "boundaryObjects": [],
        "failures": [],
    }


def _trace():
    return helper_base._trace()


def _extension():
    trace = _trace()
    if trace is None:
        return None
    return trace.get("prepareLayerBackdropStateWriterDiscoveryExtension")


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


def _general_values(registers):
    return trace_base._full_register_values(registers)


def _snapshot(process, address, byte_count, label):
    return trace_base._snapshot(process, address, byte_count, label)


def _wrapper_identity(frame, process):
    target = process.GetTarget()
    trace = _trace()
    prepare_start = trace["prepareLayer"]["symbolStart"]
    resolved = target.ResolveLoadAddress(frame.GetPC())
    symbol = resolved.GetSymbol()
    if not symbol.IsValid():
        raise RuntimeError("backdrop wrapper symbol is invalid")
    start = symbol.GetStartAddress().GetLoadAddress(target)
    end = symbol.GetEndAddress().GetLoadAddress(target)
    code = capture_base._read_memory(
        process, start, end - start, "backdrop wrapper complete code"
    )
    if (
        frame.GetFunctionName() != BACKDROP_WRAPPER_FUNCTION
        or start - prepare_start != BACKDROP_WRAPPER_RELATIVE_TO_PREPARE_LAYER
        or hashlib.sha256(code).hexdigest() != BACKDROP_WRAPPER_CODE_SHA256
    ):
        raise RuntimeError("backdrop wrapper identity differs")
    return capture_base._frame_record(frame, target)


def _trace_opaque_callee_with_backdrop_state(thread, frame, expected_return_function):
    if frame.GetFunctionName() != BACKDROP_WRAPPER_FUNCTION:
        return _original_trace_opaque_callee(thread, frame, expected_return_function)
    extension = _extension()
    if extension is None:
        raise RuntimeError("backdrop-state extension is absent")
    if extension["boundaryObjects"]:
        raise RuntimeError("backdrop wrapper boundary is not unique")
    process = thread.GetProcess()
    registers = capture_base._full_register_snapshot(frame)
    values = _general_values(registers)
    self_address = values["x0"]
    layer_address = values["x1"]
    output_address = values["x2"]
    record = {
        "boundaryIndex": 0,
        "wrapperFrame": _wrapper_identity(frame, process),
        "registersAtEntry": registers,
        "selfAddress": self_address,
        "layerAddress": layer_address,
        "outputAddress": output_address,
        "selfMinusLayer": self_address - layer_address,
        "selfLayerPointerDeltaAcceptedBeforeCapture": None,
        "backdropBefore": _snapshot(
            process,
            self_address,
            BACKDROP_OBJECT_BYTE_COUNT,
            "BackdropLayer object before get_bounds",
        ),
        "layerBefore": _snapshot(
            process,
            layer_address,
            LAYER_OBJECT_BYTE_COUNT,
            "Layer object before get_bounds",
        ),
        "primaryRectBefore": _snapshot(
            process,
            output_address,
            RECT_BYTE_COUNT,
            "primary Rect before get_bounds",
        ),
        "fieldValuesAcceptedBeforeCapture": None,
        "cropValuesUsedForSelection": False,
        "outputValuesUsedForSelection": False,
    }
    extension["boundaryObjects"].append(record)
    _write_trace()
    result = _original_trace_opaque_callee(thread, frame, expected_return_function)
    record["backdropAfter"] = _snapshot(
        process,
        self_address,
        BACKDROP_OBJECT_BYTE_COUNT,
        "BackdropLayer object after get_bounds",
    )
    record["layerAfter"] = _snapshot(
        process,
        layer_address,
        LAYER_OBJECT_BYTE_COUNT,
        "Layer object after get_bounds",
    )
    record["primaryRectAfter"] = _snapshot(
        process,
        output_address,
        RECT_BYTE_COUNT,
        "primary Rect after get_bounds",
    )
    _write_trace()
    return result


def _install_opaque_boundary_hook():
    producer_base._trace_opaque_callee = _trace_opaque_callee_with_backdrop_state


def _batch_instructions(target, symbol, start, code):
    instruction_list = target.ReadInstructions(symbol.GetStartAddress(), len(code) // 4)
    if instruction_list.GetSize() != len(code) // 4:
        raise RuntimeError("BackdropLayer symbol instruction coverage differs")
    result = []
    for index in range(instruction_list.GetSize()):
        instruction = instruction_list.GetInstructionAtIndex(index)
        pc = instruction.GetAddress().GetLoadAddress(target)
        offset = index * 4
        if pc != start + offset:
            raise RuntimeError("BackdropLayer instruction address differs")
        result.append(
            {
                "pc": pc,
                "offset": offset,
                "rawLittleEndianHex": code[offset : offset + 4].hex(),
                "mnemonic": instruction.GetMnemonic(target) or "",
                "operands": instruction.GetOperands(target) or "",
                "comment": instruction.GetComment(target) or "",
            }
        )
    return result


def _capture_symbol_inventory():
    extension = _extension()
    if extension is None:
        raise RuntimeError("backdrop-state extension is absent")
    if extension["symbolInventory"] is not None:
        raise RuntimeError("BackdropLayer symbol inventory was captured twice")
    process = trace_base._state["debugger"].GetSelectedTarget().GetProcess()
    trace_base._require_stopped(process, "BackdropLayer symbol inventory")
    target = process.GetTarget()
    prepare_start = _trace()["prepareLayer"]["symbolStart"]
    module = target.ResolveLoadAddress(prepare_start).GetModule()
    module_record = trace_base._module_record(module, target)
    if module_record["uuid"] != QUARTZCORE_UUID:
        raise RuntimeError("QuartzCore UUID differs")

    grouped = {}
    matched_name_count = 0
    for index in range(module.GetNumSymbols()):
        symbol = module.GetSymbolAtIndex(index)
        name = symbol.GetName() or ""
        if (
            SYMBOL_NAME_SUBSTRING not in name
            or symbol.GetType() != lldb.eSymbolTypeCode
        ):
            continue
        matched_name_count += 1
        start = symbol.GetStartAddress().GetLoadAddress(target)
        end = symbol.GetEndAddress().GetLoadAddress(target)
        if (
            start == lldb.LLDB_INVALID_ADDRESS
            or end == lldb.LLDB_INVALID_ADDRESS
            or end <= start
            or (end - start) % 4 != 0
            or end - start > MAXIMUM_INDIVIDUAL_SYMBOL_BYTE_COUNT
        ):
            raise RuntimeError("BackdropLayer matched code symbol bounds differ")
        key = (start, end)
        if key not in grouped:
            grouped[key] = {"symbol": symbol, "names": []}
        grouped[key]["names"].append(name)

    if not grouped or len(grouped) > MAXIMUM_MATCHED_CODE_SYMBOL_COUNT:
        raise RuntimeError("BackdropLayer matched code symbol count differs")
    total = sum(end - start for start, end in grouped)
    if total > MAXIMUM_TOTAL_SYMBOL_BYTE_COUNT:
        raise RuntimeError("BackdropLayer total code byte count differs")

    ranges = []
    for (start, end), group in sorted(grouped.items()):
        code = capture_base._read_memory(
            process, start, end - start, "BackdropLayer complete symbol code"
        )
        symbol = group["symbol"]
        ranges.append(
            {
                "names": sorted(group["names"]),
                "symbolStart": start,
                "symbolEnd": end,
                "moduleRelativeStart": start - module_record["loadAddress"],
                "symbolByteCount": len(code),
                "expectedCodeSHA256": None,
                "observedCodeSHA256": hashlib.sha256(code).hexdigest(),
                "hex": code.hex(),
                "instructionCount": len(code) // 4,
                "instructions": _batch_instructions(target, symbol, start, code),
                "fieldOrOutputValuesUsedForSelection": False,
            }
        )
    extension["symbolInventory"] = {
        "module": module_record,
        "selectionRule": (
            "every positive bounded QuartzCore code symbol whose demangled "
            "name contains the preregistered BackdropLayer substring"
        ),
        "symbolNameSubstring": SYMBOL_NAME_SUBSTRING,
        "matchedNameCount": matched_name_count,
        "uniqueRangeCount": len(ranges),
        "totalCodeByteCount": total,
        "expectedMatchedNameCount": None,
        "expectedUniqueRangeCount": None,
        "expectedNames": None,
        "expectedCodeSHA256": None,
        "ranges": ranges,
    }
    _write_trace()


def trace_selected_sdf_filter_map_bounds():
    extension = _extension()
    if extension is None:
        return
    try:
        extension["status"] = "writer-discovery-active"
        _capture_symbol_inventory()
        _install_opaque_boundary_hook()
        frozen.trace_selected_sdf_filter_map_bounds()
        extension["status"] = "writer-discovery-closed"
    except Exception as error:
        extension["status"] = "writer-discovery-failed"
        _failure("writer-discovery", error)
    _write_trace()


def finalize():
    frozen.finalize()
    extension = _extension()
    if extension is not None:
        extension["statusBeforeFinalization"] = extension["status"]
        extension["status"] = "finalized"
        extension["finalFailureCount"] = len(extension["failures"])
        extension["finalBoundaryObjectCount"] = len(extension["boundaryObjects"])
    _write_trace()


def __lldb_init_module(debugger, internal_dict):
    frozen.__lldb_init_module(debugger, internal_dict)
    trace = _trace()
    if trace is None:
        return
    trace["prepareLayerBackdropStateWriterDiscoveryExtension"] = _new_extension()
    try:
        _install_callback_proxies()
        _install_opaque_boundary_hook()
        _write_trace()
    except Exception as error:
        _failure("initialization", error)
