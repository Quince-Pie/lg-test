"""LLDB callback-visibility retry for the frozen crop-policy holdout.

The first holdout run proved that callbacks registered from a normally imported
dependency module are not visible to LLDB's script callback resolver.  This
top-level module changes transport only: it forwards every inherited callback
through names in the module loaded by ``command script import``.  Capture
selection, addresses, byte ranges, formula, validator, and acceptance remain
unchanged.
"""

import capture_prepare_layer_crop_policy_holdout_lldb as holdout_base


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _install_callback_proxies():
    entry = holdout_base.union_base.crop_base._state.get("prepareEntryBreakpoint")
    marker = holdout_base.union_base.crop_base._state.get("markerBreakpoint")
    union_call = holdout_base.union_base._state.get("unionCallBreakpoint")
    union_return = holdout_base.union_base._state.get("unionReturnBreakpoint")
    store = holdout_base._state.get("storeBreakpoint")
    callbacks = (
        (entry, "prepare_layer_entry", "prepare entry"),
        (marker, "crop_transfer_marker", "crop transfer marker"),
        (union_call, "crop_union_call", "crop union call"),
        (union_return, "crop_union_return", "crop union return"),
        (store, "nested_crop_store", "nested crop store"),
    )
    for breakpoint, callback, label in callbacks:
        if breakpoint is not None:
            _set_callback(breakpoint, callback, label)


def prepare_layer_entry(frame, breakpoint_location, internal_dict):
    result = holdout_base.prepare_layer_entry(frame, breakpoint_location, internal_dict)
    try:
        _install_callback_proxies()
        holdout_base.union_base.crop_base._write_trace()
    except Exception as error:
        holdout_base.union_base.crop_base._failure(
            "crop-policy-callback-proxy-entry", error
        )
    return result


def crop_union_call(frame, breakpoint_location, internal_dict):
    return holdout_base.union_base.crop_union_call(
        frame, breakpoint_location, internal_dict
    )


def crop_union_return(frame, breakpoint_location, internal_dict):
    return holdout_base.union_base.crop_union_return(
        frame, breakpoint_location, internal_dict
    )


def nested_crop_store(frame, breakpoint_location, internal_dict):
    return holdout_base.nested_crop_store(frame, breakpoint_location, internal_dict)


def crop_transfer_marker(frame, breakpoint_location, internal_dict):
    return holdout_base.crop_transfer_marker(frame, breakpoint_location, internal_dict)


def finalize():
    holdout_base.finalize()


def __lldb_init_module(debugger, internal_dict):
    holdout_base.__lldb_init_module(debugger, internal_dict)
    try:
        _install_callback_proxies()
        holdout_base.union_base.crop_base._write_trace()
    except Exception as error:
        holdout_base.union_base.crop_base._failure(
            "crop-policy-callback-proxy-initialization", error
        )
