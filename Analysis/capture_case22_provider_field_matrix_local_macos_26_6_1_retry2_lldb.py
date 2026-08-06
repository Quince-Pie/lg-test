"""Bind the frozen field-matrix callbacks through LLDB's imported namespace.

The first local-UUID retry exposed the frozen capture as a Python dependency.
LLDB created its marker breakpoint but does not resolve callback names through a
dependency-only module.  This overlay exports the same frozen callables from
the directly imported module and changes only the callback-name prefix.
"""

import capture_case22_provider_field_matrix_local_macos_26_6_1_retry_lldb as retry


frozen = retry.frozen


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


marker = frozen.marker
provider_entry = frozen.provider_entry
provider_return = frozen.provider_return


def finalize():
    retry.finalize()


def __lldb_init_module(debugger, internal_dict):
    frozen._set_callback = _set_callback
    retry.__lldb_init_module(debugger, internal_dict)
