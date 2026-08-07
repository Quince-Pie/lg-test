"""Apply the frozen live-QuartzCore transport to the exact crop capture.

This top-level LLDB module changes code identity and translated instruction
offsets only.  It re-exports every dynamically installed callback because
Apple's LLDB resolves callback names only from the directly imported module.
The inherited structural selectors and captured byte ranges remain unchanged.
"""

import capture_prepare_layer_crop_policy_holdout_lldb as holdout_base
import prepare_layer_live_transport_local_macos_26_6_1 as live


live.patch_capture_modules(holdout_base)


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _install_callback_proxies():
    crop_base = holdout_base.union_base.crop_base
    callbacks = (
        (crop_base._state.get("prepareEntryBreakpoint"), "prepare_layer_entry", "prepare entry"),
        (crop_base._state.get("markerBreakpoint"), "crop_transfer_marker", "crop marker"),
        (holdout_base.union_base._state.get("unionCallBreakpoint"), "crop_union_call", "union call"),
        (holdout_base.union_base._state.get("unionReturnBreakpoint"), "crop_union_return", "union return"),
        (holdout_base._state.get("storeBreakpoint"), "nested_crop_store", "crop store"),
    )
    for breakpoint, callback, label in callbacks:
        if breakpoint is not None:
            _set_callback(breakpoint, callback, label)


def _record_live_identity(frame):
    module_uuid = frame.GetModule().GetUUIDString()
    if module_uuid != live.QUARTZCORE_UUID:
        raise RuntimeError("live QuartzCore UUID differs")


def prepare_layer_entry(frame, breakpoint_location, internal_dict):
    try:
        _record_live_identity(frame)
    except Exception as error:
        holdout_base.union_base.crop_base._failure(
            "live-prepare-layer-identity", error
        )
        entry = holdout_base.union_base.crop_base._state.get(
            "prepareEntryBreakpoint"
        )
        if entry is not None:
            entry.SetEnabled(False)
        return False

    result = holdout_base.prepare_layer_entry(
        frame, breakpoint_location, internal_dict
    )
    try:
        live.rewrite_capture_trace(holdout_base)
        _install_callback_proxies()
        holdout_base.union_base.crop_base._write_trace()
    except Exception as error:
        holdout_base.union_base.crop_base._failure(
            "live-crop-callback-proxy-entry", error
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
    return holdout_base.nested_crop_store(
        frame, breakpoint_location, internal_dict
    )


def crop_transfer_marker(frame, breakpoint_location, internal_dict):
    return holdout_base.crop_transfer_marker(
        frame, breakpoint_location, internal_dict
    )


def finalize():
    holdout_base.finalize()
    live.rewrite_capture_trace(holdout_base)
    holdout_base.union_base.crop_base._write_trace()


def __lldb_init_module(debugger, internal_dict):
    live.patch_capture_modules(holdout_base)
    holdout_base.__lldb_init_module(debugger, internal_dict)
    try:
        live.rewrite_capture_trace(holdout_base)
        _install_callback_proxies()
        holdout_base.union_base.crop_base._write_trace()
    except Exception as error:
        holdout_base.union_base.crop_base._failure(
            "live-crop-callback-proxy-initialization", error
        )
