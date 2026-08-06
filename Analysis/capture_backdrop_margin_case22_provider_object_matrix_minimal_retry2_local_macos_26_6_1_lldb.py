"""Raise only the frozen all-live provider-matrix observation bound.

The callsite-gated retry completed the application timeline but reached the
512-call bound inherited from the much slower instruction-stage diagnostic.
Removing those stages increased the observed render cadence.  This overlay
retains the exact caller, Group, wrapper, provider, object, and return gates
while raising the finite call bound to 4096.  No captured value participates
in selection or in the new bound.
"""

import capture_backdrop_margin_case22_provider_object_matrix_minimal_retry_local_macos_26_6_1_lldb as frozen


MAXIMUM_CALL_COUNT = 4096

minimal = frozen.frozen
_retry_new_trace = frozen._new_trace


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _new_trace():
    trace = _retry_new_trace()
    trace["classification"] = (
        "output-blind bound-only retry of the exact callsite-gated minimal "
        "provider-object capture; the finite bound is raised after the "
        "previous transport reached 512 calls, and no captured value "
        "participates in selection"
    )
    trace["configuration"].update(
        {
            "maximumCallCount": MAXIMUM_CALL_COUNT,
            "previousMaximumCallCount": 512,
            "boundChangeOnly": True,
            "capturedValueUsedToSelectNewBound": False,
        }
    )
    return trace


selected_callsite = frozen.selected_callsite
wrapper_entry = frozen.wrapper_entry
provider_entry = frozen.provider_entry
provider_return = frozen.provider_return
group_return = frozen.group_return
selected_caller_return = frozen.selected_caller_return


def finalize():
    frozen.finalize()


def __lldb_init_module(debugger, internal_dict):
    minimal.MAXIMUM_CALL_COUNT = MAXIMUM_CALL_COUNT
    frozen._set_callback = _set_callback
    frozen._new_trace = _new_trace
    frozen.__lldb_init_module(debugger, internal_dict)
