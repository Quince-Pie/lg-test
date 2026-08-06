"""Top-level LLDB callback transport for the frozen producer-callee trace.

Run 31068004888 stopped at the inherited ``prepare_layer+0`` breakpoint
because LLDB could not resolve callback names in a normally imported module.
This retry forwards every inherited dynamic callback through the module loaded
by ``command script import``.  It changes no breakpoint, selector, memory
range, instruction step, validator, or acceptance rule.
"""

import capture_prepare_layer_crop_producer_callee_lldb as producer_base


selected_base = producer_base.selected_base
trace_base = producer_base.base


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
    result = selected_base.prepare_layer_entry(
        frame, breakpoint_location, internal_dict
    )
    try:
        _install_callback_proxies()
        producer_base._write_trace()
    except Exception as error:
        producer_base._failure("callback-proxy-entry", error)
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


def trace_selected_producer_callee():
    producer_base.trace_selected_producer_callee()


def finalize():
    producer_base.finalize()


def __lldb_init_module(debugger, internal_dict):
    producer_base.__lldb_init_module(debugger, internal_dict)
    try:
        _install_callback_proxies()
        producer_base._write_trace()
    except Exception as error:
        producer_base._failure("callback-proxy-initialization", error)
