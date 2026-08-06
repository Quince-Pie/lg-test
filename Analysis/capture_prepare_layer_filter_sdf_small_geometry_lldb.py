"""Expose the frozen Filter/SDF instruction diagnostic at 127 points.

The inherited selector remains sample 2, marker interval 2, helper ordinal 14,
and dynamic dispatch ordinals 4 and 2.  This adapter changes only the public
geometry guard and keeps every inherited callback visible to LLDB's top-level
command-script module.

LLDB imports this module with macOS system Python, so it avoids syntax newer
than that runtime.
"""

import capture_prepare_layer_sdf_map_bounds_diagnostic_callback_retry_lldb as frozen


EXPECTED_GEOMETRY = "circle-127-center"
regular = frozen.regular
trace_base = frozen.trace_base


def _configure_geometry():
    regular.EXPECTED_GEOMETRY = EXPECTED_GEOMETRY
    regular.trace_base.EXPECTED_GEOMETRY = EXPECTED_GEOMETRY


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
        frozen.frozen._write_trace()
    except Exception as error:
        diagnostic = frozen.frozen._diagnostic()
        if diagnostic is not None:
            diagnostic["failures"].append(
                {"stage": "small-geometry-callback-proxy-entry", "message": str(error)}
            )
        frozen.frozen._write_trace()
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


def trace_selected_sdf_filter_map_bounds():
    _configure_geometry()
    return frozen.trace_selected_sdf_filter_map_bounds()


def finalize():
    return frozen.finalize()


def __lldb_init_module(debugger, internal_dict):
    _configure_geometry()
    frozen.__lldb_init_module(debugger, internal_dict)
    try:
        _install_callback_proxies()
        frozen.frozen._write_trace()
    except Exception as error:
        diagnostic = frozen.frozen._diagnostic()
        if diagnostic is not None:
            diagnostic["failures"].append(
                {
                    "stage": "small-geometry-callback-proxy-initialization",
                    "message": str(error),
                }
            )
        frozen.frozen._write_trace()
