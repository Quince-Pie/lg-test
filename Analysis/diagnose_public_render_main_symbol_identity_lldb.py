"""Report the exact main-symbol identity seen at the frozen bootstrap."""

import json
import sys
from pathlib import Path

import lldb


ANALYSIS = Path.cwd() / "Analysis"
if str(ANALYSIS) not in sys.path:
    sys.path.insert(0, str(ANALYSIS))

import capture_backdrop_margin_case22_provider_public_render_interval_transfer_local_macos_26_6_1_lldb as capture


OUTPUT = Path("/tmp/lg-public-render-main-symbol-identity.json")
_breakpoint = None


def _record(process, module, offset, label):
    value = capture.case22._capture_symbol(
        process,
        module["loadAddress"] + offset,
        label,
    )
    value.pop("hex", None)
    return value


def _record_or_error(process, module, offset, label):
    try:
        return _record(process, module, offset, label)
    except Exception as error:
        return {"diagnosticError": repr(error)}


def write_report(frame=None):
    if frame is None:
        target = lldb.debugger.GetSelectedTarget()
        process = target.GetProcess()
    else:
        process = frame.GetThread().GetProcess()
        target = process.GetTarget()
    module = capture.field._module_by_uuid(
        target,
        capture.MAIN_UUID,
        capture.MAIN_PATH_SUFFIX,
        "main executable",
    )
    background = _record_or_error(
        process,
        module,
        capture.BACKGROUND_MODULE_OFFSET,
        "transition background uniform function",
    )
    render = _record_or_error(
        process,
        module,
        capture.RENDER_MODULE_OFFSET,
        "local transition CARenderer function",
    )
    report = {
        "background": background,
        "expected": {
            "background": {
                "codeSHA256": capture.BACKGROUND_CODE_SHA256,
                "moduleOffset": capture.BACKGROUND_MODULE_OFFSET,
                "symbolByteCount": capture.BACKGROUND_BYTE_COUNT,
            },
            "render": {
                "codeSHA256": capture.RENDER_CODE_SHA256,
                "moduleOffset": capture.RENDER_MODULE_OFFSET,
                "symbolByteCount": capture.RENDER_BYTE_COUNT,
            },
        },
        "mainModule": module,
        "render": render,
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
