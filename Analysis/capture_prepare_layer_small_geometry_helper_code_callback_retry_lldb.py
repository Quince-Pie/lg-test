"""Repair only the failed helper-code adapter's LLDB transport.

Run 31086167113 retained both preregistered static code ranges, then failed
because its trace writer stopped at the callback-retry module instead of the
diagnostic module that owns ``_write_trace``.  This adapter redirects that
single internal route and keeps all inherited callbacks visible through the
top-level LLDB command-script module.  It adds no target, selector, breakpoint,
memory read, instruction step, or acceptance rule.

LLDB imports this module with macOS system Python, so it avoids syntax newer
than that runtime.
"""

import capture_prepare_layer_small_geometry_helper_code_lldb as frozen


trace_base = frozen.trace_base


def _write_trace():
    frozen.frozen.frozen.frozen._write_trace()


def _repair_trace_writer():
    frozen._write_trace = _write_trace


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
        frozen._failure("transport-retry-callback-proxy-entry", error)
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


def trace_selected_sdf_filter_map_bounds():
    _repair_trace_writer()
    return frozen.trace_selected_sdf_filter_map_bounds()


def finalize():
    _repair_trace_writer()
    return frozen.finalize()


def __lldb_init_module(debugger, internal_dict):
    _repair_trace_writer()
    frozen.__lldb_init_module(debugger, internal_dict)
    try:
        _install_callback_proxies()
        _write_trace()
    except Exception as error:
        frozen._failure("transport-retry-initialization", error)
