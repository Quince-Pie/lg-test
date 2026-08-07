"""Report exact SwiftUICore and DesignLibrary identities at bootstrap."""

import json
import sys
from pathlib import Path

import lldb


ANALYSIS = Path.cwd() / "Analysis"
if str(ANALYSIS) not in sys.path:
    sys.path.insert(0, str(ANALYSIS))

import capture_backdrop_margin_case22_provider_public_render_interval_transfer_local_macos_26_6_1_lldb as capture


OUTPUT = Path("/tmp/lg-public-render-framework-symbol-identity.json")
_breakpoint = None


def _record_or_error(process, module, offset, label):
    try:
        value = capture.case22._capture_symbol(
            process,
            module["loadAddress"] + offset,
            label,
        )
        value.pop("hex", None)
        return value
    except Exception as error:
        return {"diagnosticError": repr(error)}


def write_report(frame):
    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    swift_module = capture.field._module_by_uuid(
        target,
        capture.SWIFTUICORE_UUID,
        "/SwiftUICore",
        "SwiftUICore",
    )
    design_module = capture.field._module_by_uuid(
        target,
        capture.DESIGN_LIBRARY_UUID,
        "/DesignLibrary",
        "DesignLibrary",
    )
    report = {
        "designLibraryModule": design_module,
        "expected": {
            "provider": {
                "codeSHA256": capture.field.PROVIDER_CODE_SHA256,
                "moduleOffset": capture.field.PROVIDER_MODULE_OFFSET,
                "symbolByteCount": capture.field.PROVIDER_BYTE_COUNT,
            },
            "wrapper": {
                "codeSHA256": capture.field.WRAPPER_CODE_SHA256,
                "moduleOffset": capture.field.WRAPPER_MODULE_OFFSET,
                "symbolByteCount": capture.field.WRAPPER_BYTE_COUNT,
            },
        },
        "provider": _record_or_error(
            process,
            design_module,
            capture.field.PROVIDER_MODULE_OFFSET,
            "case-22 DesignLibrary provider",
        ),
        "swiftUICoreModule": swift_module,
        "wrapper": _record_or_error(
            process,
            swift_module,
            capture.field.WRAPPER_MODULE_OFFSET,
            "case-22 SwiftUICore wrapper",
        ),
    }
    OUTPUT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def bootstrap(frame, _breakpoint_location, _internal_dict):
    try:
        write_report(frame)
    except Exception as error:
        OUTPUT.write_text(
            json.dumps({"diagnosticError": repr(error)}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    _breakpoint.SetEnabled(False)
    return False


def __lldb_init_module(debugger, _internal_dict):
    global _breakpoint
    _breakpoint = debugger.GetSelectedTarget().BreakpointCreateByName(
        capture.BACKGROUND_MANGLED
    )
    if not _breakpoint.IsValid() or _breakpoint.GetNumLocations() != 1:
        raise RuntimeError("background bootstrap is unresolved")
    error = _breakpoint.SetScriptCallbackFunction(__name__ + ".bootstrap")
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or "bootstrap callback rejected")
