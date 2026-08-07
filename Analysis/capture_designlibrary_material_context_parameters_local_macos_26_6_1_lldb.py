"""Apply the exact Parameters builder gate to fixed Material.Context inputs."""

import capture_designlibrary_public_parameters_local_macos_26_6_1_lldb as base


CASE_NAMES = (
    "regular_light_nil",
    "regular_light_127",
    "regular_light_127_5",
    "regular_light_128",
    "regular_light_135",
    "regular_light_142_5",
    "regular_light_143",
    "regular_light_347",
    "regular_light_640",
    "regular_light_1535",
    "regular_light_range_127_143",
    "regular_light_range_127_640",
    "clear_light_127",
    "clear_light_143",
    "clear_light_640",
    "regular_dark_127",
    "regular_dark_143",
    "regular_dark_640",
    "clear_dark_127",
    "clear_dark_143",
    "clear_dark_640",
)
EXPECTED_CASE_NAMES = tuple("material_context:" + name for name in CASE_NAMES)


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
