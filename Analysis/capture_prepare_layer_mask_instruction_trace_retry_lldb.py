"""Namespace-only retry for the frozen ``prepare_layer_mask`` body trace.

Run 31063528744 captured the complete helper code before its first callback
failed because the base extension looked up ``PREPARE_LAYER_FUNCTION`` on the
crop-transfer module instead of on that module's capture dependency.  This
top-level LLDB module installs only that missing alias and forwards inherited
callbacks through names visible to LLDB.  It adds no breakpoint, memory read,
selector, stepping rule, or acceptance rule.
"""

import capture_prepare_layer_mask_instruction_trace_lldb as base


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _install_callback_proxies():
    entry = base.crop_base._state.get("prepareEntryBreakpoint")
    marker = base.crop_base._state.get("markerBreakpoint")
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
    result = base.prepare_layer_entry(frame, breakpoint_location, internal_dict)
    try:
        _install_callback_proxies()
        base._write_trace()
    except Exception as error:
        base._failure("namespace-retry-entry", error)
    return result


def crop_union_call(frame, breakpoint_location, internal_dict):
    return base.crop_union_call(frame, breakpoint_location, internal_dict)


def crop_union_return(frame, breakpoint_location, internal_dict):
    return base.crop_union_return(frame, breakpoint_location, internal_dict)


def nested_crop_store(frame, breakpoint_location, internal_dict):
    return base.nested_crop_store(frame, breakpoint_location, internal_dict)


def crop_transfer_marker(frame, breakpoint_location, internal_dict):
    return base.crop_transfer_marker(frame, breakpoint_location, internal_dict)


def prepare_layer_mask_entry(frame, breakpoint_location, internal_dict):
    return base.prepare_layer_mask_entry(
        frame, breakpoint_location, internal_dict
    )


def trace_selected_helper():
    base.trace_selected_helper()


def finalize():
    base.finalize()


def __lldb_init_module(debugger, internal_dict):
    base.crop_base.PREPARE_LAYER_FUNCTION = base.capture_base.PREPARE_LAYER_FUNCTION
    base.__lldb_init_module(debugger, internal_dict)
    try:
        _install_callback_proxies()
        base._write_trace()
    except Exception as error:
        base._failure("namespace-retry-initialization", error)
