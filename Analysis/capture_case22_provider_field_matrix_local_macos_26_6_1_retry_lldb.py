"""Retry the frozen field matrix with the local SwiftUICore UUID boundary.

The v1 capture and every runtime selection remain byte-identical.  This overlay
only replaces a reused symbol helper whose optional check still referenced the
historical CI UUID instead of the already-frozen local UUID.
"""

import capture_case22_provider_field_matrix_local_macos_26_6_1_lldb as frozen


def _capture_local_wrapper(process, module):
    address = module["loadAddress"] + frozen.WRAPPER_MODULE_OFFSET
    record = frozen.case22._capture_symbol(
        process,
        address,
        "case-22 provider wrapper",
    )
    identity = record.get("module", {})
    if (
        identity.get("uuid") != frozen.SWIFTUICORE_UUID
        or not str(identity.get("path", "")).endswith("/SwiftUICore")
        or identity.get("loadAddress") != module["loadAddress"]
        or address - identity.get("loadAddress", 0) != frozen.WRAPPER_MODULE_OFFSET
        or record.get("function") != frozen.WRAPPER_FUNCTION
        or record.get("symbolStart") != address
        or record.get("symbolByteCount") != frozen.WRAPPER_BYTE_COUNT
        or record.get("codeSHA256") != frozen.WRAPPER_CODE_SHA256
    ):
        raise RuntimeError("case-22 provider local wrapper exact identity differs")
    return record


def finalize():
    frozen.finalize()


def __lldb_init_module(debugger, internal_dict):
    frozen._capture_wrapper = _capture_local_wrapper
    frozen.__lldb_init_module(debugger, internal_dict)
