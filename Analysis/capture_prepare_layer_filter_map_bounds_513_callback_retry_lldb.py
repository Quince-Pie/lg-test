"""Top-level callback transport for the 513-point FilterOp diagnostic.

The first geometry-adapted run stopped at the inherited ``prepare_layer+0``
breakpoint because LLDB could not resolve callback names in a normally
imported module.  This adapter combines the frozen 513 geometry override with
the already proven top-level callback-proxy transport.  It changes no
breakpoint, selector, memory range, instruction step, or acceptance rule.

LLDB imports this module with macOS system Python, so it avoids syntax newer
than that runtime.
"""

import capture_prepare_layer_filter_map_bounds_lldb as frozen


EXPECTED_GEOMETRY = "circle-513-center"
selected_base = frozen.selected_base
trace_base = frozen.base


def _configure_geometry():
    trace_base.EXPECTED_GEOMETRY = EXPECTED_GEOMETRY


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
        frozen._write_trace()
    except Exception as error:
        frozen._failure("callback-proxy-entry", error)
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


def trace_selected_filter_map_bounds():
    _configure_geometry()
    return frozen.trace_selected_filter_map_bounds()


def finalize():
    return frozen.finalize()


def __lldb_init_module(debugger, internal_dict):
    _configure_geometry()
    frozen.__lldb_init_module(debugger, internal_dict)
    try:
        _install_callback_proxies()
        frozen._write_trace()
    except Exception as error:
        frozen._failure("callback-proxy-initialization", error)
