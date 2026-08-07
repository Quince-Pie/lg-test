"""Apply the exact Parameters builder gate to frozen Environment cases."""

import capture_designlibrary_public_parameters_local_macos_26_6_1_lldb as base


ENVIRONMENT_NAMES = (
    "baseline",
    "pixel_length_half",
    "pixel_length_two",
    "color_scheme_light",
    "color_scheme_dark",
    "contrast_standard",
    "contrast_increased",
    "appears_active_false",
    "appears_active_true",
    "window_active_false",
    "window_active_true",
    "window_opaque_false",
    "window_opaque_true",
    "glass_foreground_false",
    "glass_foreground_true",
    "has_tinted_elements_false",
    "has_tinted_elements_true",
    "reduce_transparency_false",
    "reduce_transparency_true",
    "reduce_motion_false",
    "reduce_motion_true",
    "show_button_shapes_false",
    "show_button_shapes_true",
    "low_power_false",
    "low_power_true",
    "idiom_universal",
    "idiom_mac",
    "idiom_phone",
    "idiom_pad",
    "idiom_tv",
    "idiom_watch",
    "idiom_spatial",
    "idiom_car_play",
    "idiom_touch_bar",
    "diffusion_automatic",
    "diffusion_increased",
)
EXPECTED_CASE_NAMES = tuple("environment:" + name for name in ENVIRONMENT_NAMES)


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
