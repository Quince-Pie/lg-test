"""Run the frozen FilterOp trace against the 513-point geometry.

The retained 1025-point capture implementation deliberately freezes its
expected geometry.  This adapter changes only that inherited configuration
constant before LLDB initialization; callbacks, selection, memory reads,
instruction stepping, and acceptance remain owned by the frozen module.

LLDB imports this module with macOS system Python, so it avoids syntax newer
than that runtime.
"""

import capture_prepare_layer_filter_map_bounds_lldb as frozen


EXPECTED_GEOMETRY = "circle-513-center"


def _configure_geometry():
    frozen.base.EXPECTED_GEOMETRY = EXPECTED_GEOMETRY


def trace_selected_filter_map_bounds():
    _configure_geometry()
    return frozen.trace_selected_filter_map_bounds()


def finalize():
    return frozen.finalize()


def __lldb_init_module(debugger, internal_dict):
    _configure_geometry()
    frozen.__lldb_init_module(debugger, internal_dict)
