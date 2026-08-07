"""Gate weighted live-dimension Parameters builds at exact Apple code."""

import capture_designlibrary_public_parameters_local_macos_26_6_1_lldb as base


CASE_NAMES = tuple("sample_{0:02d}".format(index) for index in range(1, 33))
EXPECTED_CASE_NAMES = tuple(
    "material_context_weighted_live:" + name for name in CASE_NAMES
)


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
