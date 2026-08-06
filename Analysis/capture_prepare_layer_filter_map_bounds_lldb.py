"""Trace the structurally selected FilterOp crop-producer execution.

Run 31068498526 falsified the static ``prepare_layer+0xf5c`` hypothesis but
retained the selected caller long enough to expose the real owner.  The same
``prepare_layer+0x2864`` authenticated indirect call dispatches, in order,
FlattenZ, SDF, FlattenZ, Filter, and FlattenZ operations.  The fourth dispatch
is the already frozen and code-hashed ``FilterOp::map_bounds`` symbol, and its
opaque boundary changes the exact floating producer rectangle.

This extension reuses the output-blind marker-two, ordinal-fourteen helper
selector.  It follows the same caller to the fourth authenticated dispatch,
selects that call only by ordinal and frozen code identity, then retains every
executed instruction, register, stack, caller-role, destination, and opaque
callee boundary until return.  Rectangle bytes are captured but never read by
the selector.

LLDB imports this module with macOS system Python, so it avoids syntax newer
than that runtime.
"""

import hashlib

import capture_prepare_layer_crop_producer_callee_lldb as producer_base


selected_base = producer_base.selected_base
base = producer_base.base
capture_base = producer_base.capture_base
crop_base = producer_base.crop_base

EXTENSION_SCHEMA_VERSION = 1
CALLER_CONTINUATION_START_OFFSET = 0xD94
DYNAMIC_CALL_OFFSET = 0x2864
DYNAMIC_RETURN_OFFSET = 0x2868
DYNAMIC_CALL_RAW_LITTLE_ENDIAN_HEX = "10093fd7"
TARGET_DISPATCH_ORDINAL = 4
FILTER_FUNCTION = (
    "CA::Render::Updater::FilterOp::map_bounds(CA::Render::Updater::LayerShapes&, bool)"
)
FILTER_RELATIVE_TO_PREPARE_LAYER = -61056
FILTER_SYMBOL_BYTE_COUNT = 788
FILTER_CODE_SHA256 = "e8766dcefdadc0074f7bb4e2bf62955072891858009dca6c72a7eef1c96789d0"
OPENED_SCOPE_SPECS = (
    {
        "name": "rectApplyTransform",
        "function": "CA::Rect::apply_transform(CA::SimpleTransform const&)",
        "relativeToPrepareLayer": -1207212,
        "symbolByteCount": 216,
        "codeSHA256": (
            "33690a5426ab0ea58626fd32bac7793953f0b9d4bf5a2b9de070701c2b3f1905"
        ),
    },
    {
        "name": "rectUnapplyTransform",
        "function": "CA::Rect::unapply_transform(CA::SimpleTransform const&)",
        "relativeToPrepareLayer": -1202648,
        "symbolByteCount": 216,
        "codeSHA256": (
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
        "symbolByteCount": 1136,
        "codeSHA256": (
            "8ac014e4a0e296c28b5ada0444a281d7609e93a239f4201f748d758defe6955e"
        ),
    },
    {
        "name": "filterApplyDOD",
        "function": (
            "CA::Render::Filter::apply_dod(CA::Render::Layer const*, CA::Rect&) const"
        ),
        "relativeToPrepareLayer": -609324,
        "symbolByteCount": 1092,
        "codeSHA256": (
            "1fbe87e96831c11eee633b58c2b0a39968d75ea29a48673aa95ccb761eaa30dd"
        ),
    },
    {
        "name": "filterApply",
        "function": "CA::Render::Updater::FilterOp::apply_filter(CA::Rect&, bool)",
        "relativeToPrepareLayer": -61476,
        "symbolByteCount": 292,
        "codeSHA256": (
            "855b03e09d815f83985994344be2867e6ac40938e80897183bcd06afc89f252f"
        ),
    },
    {
        "name": "filterMapBounds",
        "function": FILTER_FUNCTION,
        "relativeToPrepareLayer": FILTER_RELATIVE_TO_PREPARE_LAYER,
        "symbolByteCount": FILTER_SYMBOL_BYTE_COUNT,
        "codeSHA256": FILTER_CODE_SHA256,
    },
    {
        "name": "unionBounds",
        "function": (
            "CA::Render::Updater::LayerShapes::union_bounds(CA::Rect const&, bool)"
        ),
        "relativeToPrepareLayer": -2720,
        "symbolByteCount": 404,
        "codeSHA256": (
            "246257a9bc1a608f59dbc07345397a8851b49528c59407eb775e9b9895a2c4b7"
        ),
    },
)
EXPECTED_DISPATCH_FUNCTIONS = (
    "CA::Render::Updater::FlattenZOp::map_bounds("
    "CA::Render::Updater::LayerShapes&, bool)",
    "CA::Render::Updater::SDFOp::map_bounds(CA::Render::Updater::LayerShapes&, bool)",
    "CA::Render::Updater::FlattenZOp::map_bounds("
    "CA::Render::Updater::LayerShapes&, bool)",
    FILTER_FUNCTION,
)
STACK_BYTE_COUNT = producer_base.STACK_BYTE_COUNT
CALLER_ROLE_BYTE_COUNT = producer_base.CALLER_ROLE_BYTE_COUNT
OUTPUT_BYTE_COUNT = producer_base.OUTPUT_BYTE_COUNT
FILTER_OBJECT_BYTE_COUNT = 0x400
MAXIMUM_CALLER_INSTRUCTION_COUNT = 768
MAXIMUM_FILTER_INSTRUCTION_COUNT = 4096
MAXIMUM_OPAQUE_CALLEE_COUNT = producer_base.MAXIMUM_OPAQUE_CALLEE_COUNT
TRACE_CHECKPOINT_INSTRUCTION_INTERVAL = (
    producer_base.TRACE_CHECKPOINT_INSTRUCTION_INTERVAL
)
TRACE_CHECKPOINT_BOUNDARY_INTERVAL = producer_base.TRACE_CHECKPOINT_BOUNDARY_INTERVAL


def _new_extension_trace():
    return {
        "prepareLayerFilterMapBoundsExtensionSchemaVersion": (EXTENSION_SCHEMA_VERSION),
        "classification": (
            "prospective output-blind complete execution trace of the fourth "
            "prepare_layer+0x2864 dynamic dispatch, selected by the frozen "
            "ordinal-fourteen caller and exact FilterOp::map_bounds identity"
        ),
        "status": "initialized",
        "configuration": {
            "selectedMarkerInterval": base.TARGET_MARKER_INTERVAL,
            "selectedQualifiedHelperOrdinal": selected_base._target_ordinal,
            "callerContinuationStartOffset": CALLER_CONTINUATION_START_OFFSET,
            "dynamicCallOffset": DYNAMIC_CALL_OFFSET,
            "dynamicReturnOffset": DYNAMIC_RETURN_OFFSET,
            "dynamicCallRawLittleEndianHex": (DYNAMIC_CALL_RAW_LITTLE_ENDIAN_HEX),
            "targetDispatchOrdinal": TARGET_DISPATCH_ORDINAL,
            "expectedDispatchFunctions": list(EXPECTED_DISPATCH_FUNCTIONS),
            "filterFunction": FILTER_FUNCTION,
            "filterRelativeToPrepareLayer": (FILTER_RELATIVE_TO_PREPARE_LAYER),
            "filterSymbolByteCount": FILTER_SYMBOL_BYTE_COUNT,
            "filterCodeSHA256": FILTER_CODE_SHA256,
            "openedScopeSpecifications": [dict(spec) for spec in OPENED_SCOPE_SPECS],
            "callerOutputOffset": producer_base.CALLER_OUTPUT_OFFSET,
            "stackByteCount": STACK_BYTE_COUNT,
            "callerRoleByteCount": CALLER_ROLE_BYTE_COUNT,
            "outputByteCount": OUTPUT_BYTE_COUNT,
            "filterObjectByteCount": FILTER_OBJECT_BYTE_COUNT,
            "maximumCallerInstructionCount": (MAXIMUM_CALLER_INSTRUCTION_COUNT),
            "maximumFilterInstructionCount": (MAXIMUM_FILTER_INSTRUCTION_COUNT),
            "maximumOpaqueCalleeCount": MAXIMUM_OPAQUE_CALLEE_COUNT,
            "traceCheckpointInstructionInterval": (
                TRACE_CHECKPOINT_INSTRUCTION_INTERVAL
            ),
            "traceCheckpointBoundaryInterval": (TRACE_CHECKPOINT_BOUNDARY_INTERVAL),
            "selectionRule": (
                "reuse marker interval 2 prepare_layer_mask ordinal 14 from "
                "the frozen output-blind helper/store/marker inventory; "
                "follow only its exact thread, x19 role, and frame; at "
                "prepare_layer+0x2864 require the frozen raw instruction and "
                "the exact first four dynamic function identities; select "
                "only ordinal 4 after its relative start, byte count, and "
                "complete code SHA-256 match; read no crop or output value"
            ),
            "steppingRule": (
                "with every breakpoint disabled and LLDB synchronous, retain "
                "complete scalar/SIMD registers, 256 stack bytes, 2048 caller "
                "role bytes, and 512 destination bytes before and after every "
                "caller instruction and every instruction in the seven "
                "previously code-hashed FilterOp arithmetic scopes; step out "
                "of every other callee as an explicit boundary"
            ),
            "correlationRule": (
                "after the FilterOp returns and normal capture resumes, "
                "require its first rectangle to equal the independent "
                "sample-two producer on the same caller role bit for bit"
            ),
            "hardwareWatchpointsUsed": False,
            "cropValuesUsedForSelection": False,
            "outputValuesUsedForSelection": False,
        },
        "selectedCaller": {},
        "callerContinuationStates": [],
        "dynamicDispatches": [],
        "openedScopes": [],
        "filter": {},
        "filterInstructionStates": [],
        "opaqueCalleeBoundaries": [],
        "executionEvents": [],
        "failures": [],
    }


def _extension_trace():
    trace = crop_base._state.get("trace")
    if trace is None:
        return None
    return trace.get("prepareLayerFilterMapBoundsExtension")


def _write_trace():
    base._write_trace()


def _failure(stage, error):
    extension = _extension_trace()
    if extension is not None:
        extension["failures"].append({"stage": str(stage), "message": str(error)})
    base._failure("filter-map-bounds-" + str(stage), error)


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _install_callback_proxies():
    entry = crop_base._state.get("prepareEntryBreakpoint")
    marker = crop_base._state.get("markerBreakpoint")
    union_call = base.union_base._state.get("unionCallBreakpoint")
    union_return = base.union_base._state.get("unionReturnBreakpoint")
    store = base.holdout_base._state.get("storeBreakpoint")
    helper = base._state.get("helperBreakpoint")
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
    result = selected_base.prepare_layer_entry(
        frame, breakpoint_location, internal_dict
    )
    try:
        _install_callback_proxies()
        _write_trace()
    except Exception as error:
        _failure("callback-proxy-entry", error)
    return result


def crop_union_call(frame, breakpoint_location, internal_dict):
    return selected_base.crop_union_call(frame, breakpoint_location, internal_dict)


def crop_union_return(frame, breakpoint_location, internal_dict):
    return selected_base.crop_union_return(frame, breakpoint_location, internal_dict)


def nested_crop_store(frame, breakpoint_location, internal_dict):
    return selected_base.nested_crop_store(frame, breakpoint_location, internal_dict)


def crop_transfer_marker(frame, breakpoint_location, internal_dict):
    return selected_base.crop_transfer_marker(frame, breakpoint_location, internal_dict)


def prepare_layer_mask_entry(frame, breakpoint_location, internal_dict):
    return selected_base.prepare_layer_mask_entry(
        frame, breakpoint_location, internal_dict
    )


def _capture_filter_identity(process, frame, prepare_start, call_pc):
    target = process.GetTarget()
    entry_pc = frame.GetPC()
    expected_entry = prepare_start + FILTER_RELATIVE_TO_PREPARE_LAYER
    if entry_pc != expected_entry:
        raise RuntimeError("FilterOp entry address differs")
    resolved = target.ResolveLoadAddress(entry_pc)
    symbol = resolved.GetSymbol()
    if not symbol.IsValid():
        raise RuntimeError("FilterOp symbol is invalid")
    start = symbol.GetStartAddress().GetLoadAddress(target)
    end = symbol.GetEndAddress().GetLoadAddress(target)
    if (
        start != entry_pc
        or end - start != FILTER_SYMBOL_BYTE_COUNT
        or frame.GetFunctionName() != FILTER_FUNCTION
    ):
        raise RuntimeError("FilterOp symbol identity differs")
    code = capture_base._read_memory(
        process, start, end - start, "FilterOp complete code"
    )
    observed_sha = hashlib.sha256(code).hexdigest()
    if observed_sha != FILTER_CODE_SHA256:
        raise RuntimeError("FilterOp complete code SHA-256 differs")
    return {
        "function": frame.GetFunctionName(),
        "symbolName": symbol.GetName(),
        "relativeToPrepareLayer": entry_pc - prepare_start,
        "entryPC": entry_pc,
        "entryOffset": entry_pc - start,
        "symbolRelativeToPrepareLayer": start - prepare_start,
        "symbolStart": start,
        "symbolEnd": end,
        "symbolByteCount": len(code),
        "expectedSHA256": FILTER_CODE_SHA256,
        "observedSHA256": observed_sha,
        "hex": code.hex(),
        "module": base._module_record(resolved.GetModule(), target),
        "callPC": call_pc,
        "callReturnPC": prepare_start + DYNAMIC_RETURN_OFFSET,
        "callInstructionSHA256": hashlib.sha256(
            bytes.fromhex(DYNAMIC_CALL_RAW_LITTLE_ENDIAN_HEX)
        ).hexdigest(),
    }


def _record_dispatch(process, frame, prepare_start, call_state_index, ordinal):
    target = process.GetTarget()
    resolved = target.ResolveLoadAddress(frame.GetPC())
    symbol = resolved.GetSymbol()
    start = symbol.GetStartAddress().GetLoadAddress(target)
    end = symbol.GetEndAddress().GetLoadAddress(target)
    function = frame.GetFunctionName()
    expected = EXPECTED_DISPATCH_FUNCTIONS[ordinal - 1]
    if function != expected or not symbol.IsValid() or not start <= frame.GetPC() < end:
        raise RuntimeError("dynamic map_bounds dispatch sequence differs")
    record = {
        "dispatchOrdinal": ordinal,
        "callerStateIndex": call_state_index,
        "function": function,
        "entryPC": frame.GetPC(),
        "symbolStart": start,
        "symbolEnd": end,
        "symbolByteCount": end - start,
        "symbolRelativeToPrepareLayer": start - prepare_start,
        "module": base._module_record(resolved.GetModule(), target),
        "cropValuesUsedForSelection": False,
        "outputValuesUsedForSelection": False,
    }
    _extension_trace()["dynamicDispatches"].append(record)
    return record


def _capture_opened_scopes(process, prepare_start):
    target = process.GetTarget()
    opened = []
    for spec in OPENED_SCOPE_SPECS:
        expected_start = prepare_start + spec["relativeToPrepareLayer"]
        resolved = target.ResolveLoadAddress(expected_start)
        symbol = resolved.GetSymbol()
        if not symbol.IsValid():
            raise RuntimeError(spec["name"] + " symbol is invalid")
        start = symbol.GetStartAddress().GetLoadAddress(target)
        end = symbol.GetEndAddress().GetLoadAddress(target)
        function = resolved.GetFunction().GetName()
        symbol_name = symbol.GetName()
        if (
            start != expected_start
            or end - start != spec["symbolByteCount"]
            or (function != spec["function"] and symbol_name != spec["function"])
        ):
            raise RuntimeError(spec["name"] + " symbol identity differs")
        code = capture_base._read_memory(
            process, start, end - start, spec["name"] + " complete code"
        )
        digest = hashlib.sha256(code).hexdigest()
        if digest != spec["codeSHA256"]:
            raise RuntimeError(spec["name"] + " complete code SHA-256 differs")
        opened.append(
            {
                "name": spec["name"],
                "function": spec["function"],
                "relativeToPrepareLayer": spec["relativeToPrepareLayer"],
                "symbolStart": start,
                "symbolEnd": end,
                "symbolByteCount": len(code),
                "expectedSHA256": spec["codeSHA256"],
                "observedSHA256": digest,
                "hex": code.hex(),
                "module": base._module_record(resolved.GetModule(), target),
            }
        )
    return opened


def _opened_scope_for_pc(pc):
    for scope in _extension_trace()["openedScopes"]:
        if scope["symbolStart"] <= pc < scope["symbolEnd"]:
            return scope
    return None


def _trace_opened_scope_instruction(thread, frame, scope):
    states = _extension_trace()["filterInstructionStates"]
    thread, result_frame = producer_base._trace_instruction(
        thread,
        frame,
        "producerCallee",
        scope["symbolStart"],
        states,
    )
    state = states[-1]
    state["openedScopeName"] = scope["name"]
    state["openedScopeFunction"] = scope["function"]
    state["openedScopeCodeSHA256"] = scope["observedSHA256"]
    if len(states) % TRACE_CHECKPOINT_INSTRUCTION_INTERVAL == 0:
        _write_trace()
    return thread, result_frame


def trace_selected_filter_map_bounds():
    """Trace ordinal fourteen through the fourth dynamic map-bounds call."""
    extension = _extension_trace()
    if extension is None:
        return
    process = base._state["debugger"].GetSelectedTarget().GetProcess()
    try:
        if selected_base._mode != selected_base.SELECTED_MODE:
            raise RuntimeError("FilterOp trace requires selected mode")
        if base._state["manualTraceStarted"]:
            raise RuntimeError("FilterOp trace was invoked twice")
        if base._state["selected"] is None:
            raise RuntimeError("structurally selected mask call was not reached")
        base._require_stopped(process, "selected prepare_layer_mask entry")
        base._state["manualTraceStarted"] = True
        base._state["debugger"].SetAsync(False)
        if base._state["debugger"].GetAsync():
            raise RuntimeError("debugger remained asynchronous")
        base._disable_breakpoints(process.GetTarget())
        prepare_start = crop_base._state["prepareLayer"]["symbolStart"]
        extension["openedScopes"] = _capture_opened_scopes(process, prepare_start)
        helper_extension = base._extension_trace()
        helper = helper_extension["helper"]
        helper_extension["manualTraceStart"] = {
            "selectedRecordIndex": base._state["selected"]["recordIndex"],
            "threadID": base._state["selected"]["threadID"],
            "entryPC": helper["symbolStart"],
            "debuggerAsyncAfterSynchronousSet": (base._state["debugger"].GetAsync()),
        }
        helper_extension["status"] = "selected-helper-instruction-trace-active"
        helper_return_pc = prepare_start + CALLER_CONTINUATION_START_OFFSET
        while (
            len(helper_extension["instructionStates"])
            < base.MAXIMUM_HELPER_INSTRUCTION_COUNT
        ):
            thread = base._selected_thread(process)
            frame = thread.GetFrameAtIndex(0)
            pc = frame.GetPC()
            if (
                frame.GetFunctionName() == crop_base.PREPARE_LAYER_FUNCTION
                and pc == helper_return_pc
            ):
                break
            if helper["symbolStart"] <= pc < helper["symbolEnd"]:
                base._trace_helper_instruction(thread, frame, helper)
            else:
                base._trace_opaque_callee(thread, frame)
        else:
            raise RuntimeError("prepare_layer_mask instruction bound exceeded")

        caller_frame, helper_return_registers = producer_base._record_helper_return(
            process, prepare_start
        )
        helper_extension["status"] = "selected-helper-instruction-trace-closed"
        extension["status"] = "caller-continuation-trace-active"
        extension["selectedCaller"] = {
            "threadID": base._state["selected"]["threadID"],
            "callerRoleBase": base._state["selected"]["callerRoleBase"],
            "outputAddress": base._state["selected"]["outputAddress"],
            "helperReturnFrame": capture_base._frame_record(
                caller_frame, process.GetTarget()
            ),
            "helperReturnRegisters": helper_return_registers,
            "outputAtHelperReturn": base._snapshot(
                process,
                base._state["selected"]["outputAddress"],
                OUTPUT_BYTE_COUNT,
                "FilterOp output at helper return",
            ),
            "callerRoleAtHelperReturn": base._snapshot(
                process,
                base._state["selected"]["callerRoleBase"],
                CALLER_ROLE_BYTE_COUNT,
                "FilterOp role at helper return",
            ),
        }
        _write_trace()

        call_pc = prepare_start + DYNAMIC_CALL_OFFSET
        dispatch_ordinal = 0
        filter_frame = None
        while (
            len(extension["callerContinuationStates"])
            < MAXIMUM_CALLER_INSTRUCTION_COUNT
        ):
            thread = base._selected_thread(process)
            frame = thread.GetFrameAtIndex(0)
            if frame.GetFunctionName() == crop_base.PREPARE_LAYER_FUNCTION:
                if frame.GetPC() == call_pc:
                    raw_call = capture_base._read_memory(
                        process, call_pc, 4, "dynamic map_bounds call"
                    )
                    registers = capture_base._full_register_snapshot(frame)
                    values = base._full_register_values(registers)
                    if (
                        raw_call.hex() != DYNAMIC_CALL_RAW_LITTLE_ENDIAN_HEX
                        or values["x19"] != base._state["selected"]["callerRoleBase"]
                        or values["x29"]
                        != base._full_register_values(
                            extension["selectedCaller"]["helperReturnRegisters"]
                        )["x29"]
                    ):
                        raise RuntimeError("dynamic map_bounds caller differs")
                    call_state_index = len(extension["callerContinuationStates"])
                    thread, result_frame = producer_base._trace_instruction(
                        thread,
                        frame,
                        "prepareLayer",
                        prepare_start,
                        extension["callerContinuationStates"],
                    )
                    dispatch_ordinal += 1
                    _record_dispatch(
                        process,
                        result_frame,
                        prepare_start,
                        call_state_index,
                        dispatch_ordinal,
                    )
                    if dispatch_ordinal == TARGET_DISPATCH_ORDINAL:
                        filter_frame = result_frame
                        break
                    producer_base._trace_opaque_callee(
                        thread, result_frame, crop_base.PREPARE_LAYER_FUNCTION
                    )
                else:
                    producer_base._trace_instruction(
                        thread,
                        frame,
                        "prepareLayer",
                        prepare_start,
                        extension["callerContinuationStates"],
                    )
            else:
                producer_base._trace_opaque_callee(
                    thread, frame, crop_base.PREPARE_LAYER_FUNCTION
                )
        else:
            raise RuntimeError("fourth dynamic map_bounds dispatch was not reached")
        if filter_frame is None or dispatch_ordinal != TARGET_DISPATCH_ORDINAL:
            raise RuntimeError("FilterOp dynamic dispatch was not selected")

        filter_identity = _capture_filter_identity(
            process, filter_frame, prepare_start, call_pc
        )
        extension["filter"] = filter_identity
        filter_registers = capture_base._full_register_snapshot(filter_frame)
        filter_values = base._full_register_values(filter_registers)
        if filter_values["x1"] != base._state["selected"][
            "outputAddress"
        ] or filter_values["x2"] not in (0, 1):
            raise RuntimeError("FilterOp entry arguments differ")
        extension["filterEntry"] = {
            "frame": capture_base._frame_record(filter_frame, process.GetTarget()),
            "registers": filter_registers,
            "stack": base._snapshot(
                process,
                filter_values["sp"],
                STACK_BYTE_COUNT,
                "FilterOp entry stack",
            ),
            "filterObject": base._snapshot(
                process,
                filter_values["x0"],
                FILTER_OBJECT_BYTE_COUNT,
                "FilterOp object",
            ),
            "output": base._snapshot(
                process,
                base._state["selected"]["outputAddress"],
                OUTPUT_BYTE_COUNT,
                "FilterOp entry output",
            ),
            "callerRole": base._snapshot(
                process,
                base._state["selected"]["callerRoleBase"],
                CALLER_ROLE_BYTE_COUNT,
                "FilterOp entry role",
            ),
            "cropValuesUsedForSelection": False,
            "outputValuesUsedForSelection": False,
        }
        _write_trace()
        extension["status"] = "filter-map-bounds-instruction-trace-active"
        return_pc = prepare_start + DYNAMIC_RETURN_OFFSET
        while (
            len(extension["filterInstructionStates"]) < MAXIMUM_FILTER_INSTRUCTION_COUNT
        ):
            thread = base._selected_thread(process)
            frame = thread.GetFrameAtIndex(0)
            pc = frame.GetPC()
            if (
                frame.GetFunctionName() == crop_base.PREPARE_LAYER_FUNCTION
                and pc == return_pc
            ):
                break
            opened_scope = _opened_scope_for_pc(pc)
            if opened_scope is not None:
                _trace_opened_scope_instruction(thread, frame, opened_scope)
            else:
                parent = thread.GetFrameAtIndex(1)
                expected_return_function = parent.GetFunctionName()
                if not expected_return_function:
                    raise RuntimeError("opaque callee parent identity is absent")
                producer_base._trace_opaque_callee(
                    thread, frame, expected_return_function
                )
        else:
            raise RuntimeError("FilterOp instruction bound exceeded")

        return_frame = base._selected_thread(process).GetFrameAtIndex(0)
        return_registers = capture_base._full_register_snapshot(return_frame)
        return_values = base._full_register_values(return_registers)
        if (
            return_frame.GetFunctionName() != crop_base.PREPARE_LAYER_FUNCTION
            or return_frame.GetPC() != return_pc
            or return_values["x19"] != base._state["selected"]["callerRoleBase"]
        ):
            raise RuntimeError("FilterOp return identity differs")
        extension["filterReturn"] = {
            "frame": capture_base._frame_record(return_frame, process.GetTarget()),
            "registers": return_registers,
            "stack": base._snapshot(
                process,
                return_values["sp"],
                STACK_BYTE_COUNT,
                "FilterOp return stack",
            ),
            "output": base._snapshot(
                process,
                base._state["selected"]["outputAddress"],
                OUTPUT_BYTE_COUNT,
                "FilterOp return output",
            ),
            "callerRole": base._snapshot(
                process,
                base._state["selected"]["callerRoleBase"],
                CALLER_ROLE_BYTE_COUNT,
                "FilterOp return role",
            ),
        }
        extension["status"] = "filter-map-bounds-instruction-trace-closed"
        base._state["manualTraceFinished"] = True
        base._restore_breakpoints(process.GetTarget())
        _write_trace()
        base._continue_to_terminal(process)
    except Exception as error:
        _failure("manual-trace", error)
        extension["status"] = "filter-map-bounds-instruction-trace-failed"
        try:
            process.GetTarget().DisableAllBreakpoints()
            base._continue_to_terminal(process)
        except Exception as terminal_error:
            _failure("terminal-process", terminal_error)
    _write_trace()


def finalize():
    extension = _extension_trace()
    if extension is not None:
        extension["statusBeforeFinalization"] = extension["status"]
        extension["status"] = "finalized"
        extension["finalCallerContinuationStateCount"] = len(
            extension["callerContinuationStates"]
        )
        extension["finalDynamicDispatchCount"] = len(extension["dynamicDispatches"])
        extension["finalFilterInstructionStateCount"] = len(
            extension["filterInstructionStates"]
        )
        extension["finalOpaqueCalleeBoundaryCount"] = len(
            extension["opaqueCalleeBoundaries"]
        )
        extension["finalExecutionEventCount"] = len(extension["executionEvents"])
        extension["finalFailureCount"] = len(extension["failures"])
    selected_base.finalize()


def __lldb_init_module(debugger, internal_dict):
    producer_base.__lldb_init_module(debugger, internal_dict)
    trace = crop_base._state.get("trace")
    if trace is None:
        return
    trace.pop("prepareLayerCropProducerCalleeExtension", None)
    trace["prepareLayerFilterMapBoundsExtension"] = _new_extension_trace()
    producer_base._extension_trace = _extension_trace
    try:
        if (
            selected_base._mode != selected_base.SELECTED_MODE
            or selected_base._target_ordinal != 14
        ):
            raise RuntimeError("FilterOp structural selector differs")
        _install_callback_proxies()
        _write_trace()
    except Exception as error:
        _failure("initialization", error)
