"""Apply the exact Parameters builder gate to four material profiles."""

import capture_designlibrary_public_parameters_local_macos_26_6_1_lldb as base


PROFILE_NAMES = (
    "regular_light",
    "regular_dark",
    "clear_light",
    "clear_dark",
)
EXPECTED_CASE_NAMES = tuple("material_appearance:" + name for name in PROFILE_NAMES)


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def marker(frame, breakpoint_location, internal_dict):
    return base.marker(frame, breakpoint_location, internal_dict)


def parameters_builder_entry(frame, breakpoint_location, internal_dict):
    return base.parameters_builder_entry(frame, breakpoint_location, internal_dict)


def parameters_builder_return(frame, breakpoint_location, internal_dict):
    return base.parameters_builder_return(frame, breakpoint_location, internal_dict)


def finalize():
    base.finalize()


def __lldb_init_module(debugger, internal_dict):
    base.EXPECTED_CASE_NAMES = EXPECTED_CASE_NAMES
    base._set_callback = _set_callback
    base.__lldb_init_module(debugger, internal_dict)
