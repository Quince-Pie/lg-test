"""Capture public Configuration-to-Parameters builds at an exact code gate.

The native probe fixes every case and interval before execution.  This adapter
arms the exact DesignLibrary ResolvedRecipe.Parameters builder only inside
those intervals, retains every builder result, and never uses captured values
to select a case, call, field, or byte.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Mapping, Optional

import lldb


TRACE_SCHEMA_VERSION = 1
DESIGN_LIBRARY_UUID = "1E980802-69F5-3E69-89EF-50088297FCF5"
DESIGN_LIBRARY_PATH_SUFFIX = "/DesignLibrary"

MARKER_NAME = "lg_parameters_case_marker"
MARKER_BEFORE = 0
MARKER_AFTER = 1

PARAMETERS_BUILDER_MODULE_OFFSET = 0x120B4C
PARAMETERS_BUILDER_BYTE_COUNT = 0x1334
PARAMETERS_BUILDER_CODE_SHA256 = (
    "07d9b8571ca8fed42e1d8e71b312f00a9c9713ce19f406d6f2c15a9d2403fde4"
)
PARAMETERS_CALLER_MODULE_OFFSET = 0x11F1BC
PARAMETERS_CALLER_BYTE_COUNT = 0xD7C
PARAMETERS_CALLER_CODE_SHA256 = (
    "ba0ad1081cece802ccd1e148660a542145f95bf57a92de4407a3fad55f4679c6"
)
PARAMETERS_CALLER_RETURN_OFFSET = 0xD38
PARAMETERS_BYTE_COUNT = 0x401
MAXIMUM_CALLS_PER_CASE = 16

STATIC_NAMES = (
    "regular",
    "clear",
    "control",
    "text",
    "identity",
    "menu",
    "dock",
    "appIcons",
    "widgets",
    "avplayer",
    "facetime",
    "controlCenter",
    "notificationCenter",
    "monogram",
    "bubbles",
    "focusBorder",
    "focusPlatter",
    "keyboard",
    "sidebar",
    "abuttedSidebar",
    "inspector",
    "loupe",
    "slider",
    "camera",
    "cartouchePopover",
    "siriSnippet",
    "carplayUltra",
)
MIX_NAMES = (
    "negative_quarter",
    "zero",
    "quarter",
    "half",
    "three_quarters",
    "one",
    "five_quarters",
)
MODIFIER_NAMES = (
    "color_scheme_light",
    "color_scheme_dark",
    "adaptive_false",
    "adaptive_true",
    "adaptive_light",
    "adaptive_dark",
    "adaptive_animatable_false",
    "adaptive_animatable_true",
)
EXPECTED_CASE_NAMES = tuple("static:" + name for name in STATIC_NAMES) + tuple(
    "mix:" + name for name in MIX_NAMES
) + tuple("modifier:" + name for name in MODIFIER_NAMES)

_debugger = None
_state = {
    "trace": None,
    "activeCaseIndex": None,
    "pendingByThread": {},
    "builderBreakpoint": None,
    "returnBreakpoint": None,
}


def _trace_path() -> Path:
    raw = os.environ.get("LG_DESIGNLIBRARY_PUBLIC_PARAMETERS_TRACE_OUTPUT")
    if not raw:
        raise RuntimeError(
            "LG_DESIGNLIBRARY_PUBLIC_PARAMETERS_TRACE_OUTPUT is required"
        )
    return Path(raw)


def _write_trace() -> None:
    trace = _state["trace"]
    if trace is None:
        return
    path = _trace_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(trace, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _new_trace() -> Mapping[str, object]:
    return {
        "designLibraryPublicParametersLocalMacOSLldbTraceSchemaVersion": (
            TRACE_SCHEMA_VERSION
        ),
        "classification": (
            "prospectively fixed, output-blind native public API capture of "
            "every exact ResolvedRecipe.Parameters build; captured Parameters "
            "bytes never select a case, call, field, byte, or breakpoint"
        ),
        "status": "initialized",
        "configuration": {
            "macOSProductVersion": "26.6.1",
            "macOSBuildVersion": "25G76",
            "architecture": "arm64",
            "designLibraryUUID": DESIGN_LIBRARY_UUID,
            "markerName": MARKER_NAME,
            "markerBeforePhase": MARKER_BEFORE,
            "markerAfterPhase": MARKER_AFTER,
            "parametersBuilderModuleOffset": PARAMETERS_BUILDER_MODULE_OFFSET,
            "parametersBuilderByteCount": PARAMETERS_BUILDER_BYTE_COUNT,
            "parametersBuilderCodeSHA256": PARAMETERS_BUILDER_CODE_SHA256,
            "parametersCallerModuleOffset": PARAMETERS_CALLER_MODULE_OFFSET,
            "parametersCallerByteCount": PARAMETERS_CALLER_BYTE_COUNT,
            "parametersCallerCodeSHA256": PARAMETERS_CALLER_CODE_SHA256,
            "parametersCallerReturnOffset": PARAMETERS_CALLER_RETURN_OFFSET,
            "parametersByteCount": PARAMETERS_BYTE_COUNT,
            "maximumCallsPerCase": MAXIMUM_CALLS_PER_CASE,
            "expectedCaseNames": list(EXPECTED_CASE_NAMES),
            "capturedParametersUsedForSelection": False,
            "capturedBuilderArgumentsUsedForSelection": False,
            "allBuilderCallsInsideEveryFixedIntervalRetained": True,
        },
        "markerBreakpoint": {},
        "module": {},
        "parametersBuilder": {},
        "parametersCaller": {},
        "cases": [],
        "calls": [],
        "events": [],
        "failures": [],
    }


def _failure(stage: str, error: Exception) -> None:
    trace = _state["trace"]
    if trace is not None:
        trace["failures"].append({"stage": str(stage), "message": str(error)})
        trace["status"] = "failed"
        _write_trace()


def _set_callback(breakpoint, callback: str, label: str) -> None:
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _file_spec_path(file_spec) -> str:
    directory = file_spec.GetDirectory()
    filename = file_spec.GetFilename()
    if directory and filename:
        return str(Path(directory) / filename)
    return str(filename or directory or "")


def _module_record(module, target) -> Mapping[str, object]:
    header = module.GetObjectFileHeaderAddress().GetLoadAddress(target)
    if header == lldb.LLDB_INVALID_ADDRESS:
        raise RuntimeError("module header has no load address")
    return {
        "path": _file_spec_path(module.GetFileSpec()),
        "uuid": module.GetUUIDString() or "",
        "loadAddress": header,
    }


def _designlibrary_module(target) -> Mapping[str, object]:
    matches = []
    for index in range(target.GetNumModules()):
        module = target.GetModuleAtIndex(index)
        if not module.IsValid():
            continue
        record = _module_record(module, target)
        if record["uuid"] == DESIGN_LIBRARY_UUID:
            matches.append(record)
    if (
        len(matches) != 1
        or not str(matches[0]["path"]).endswith(DESIGN_LIBRARY_PATH_SUFFIX)
        or int(matches[0]["loadAddress"]) <= 0
    ):
        raise RuntimeError("DesignLibrary module identity differs")
    return matches[0]


def _read_memory(process, address: int, byte_count: int, label: str) -> bytes:
    if address <= 0 or byte_count <= 0:
        raise RuntimeError(label + " has an invalid memory range")
    error = lldb.SBError()
    payload = process.ReadMemory(address, byte_count, error)
    if not error.Success() or payload is None or len(payload) != byte_count:
        raise RuntimeError(
            label
            + " memory read failed: "
            + (error.GetCString() or "short read")
        )
    if isinstance(payload, str):
        return payload.encode("latin-1")
    return bytes(payload)


def _register(frame, name: str) -> int:
    value = frame.FindRegister(name)
    if not value.IsValid():
        raise RuntimeError("register " + name + " is unavailable")
    return int(value.GetValueAsUnsigned())


def _frame_record(frame) -> Mapping[str, object]:
    target = frame.GetThread().GetProcess().GetTarget()
    symbol = frame.GetSymbol()
    start = lldb.LLDB_INVALID_ADDRESS
    end = lldb.LLDB_INVALID_ADDRESS
    if symbol.IsValid():
        start = symbol.GetStartAddress().GetLoadAddress(target)
        end = symbol.GetEndAddress().GetLoadAddress(target)
    return {
        "pc": frame.GetPC(),
        "function": frame.GetFunctionName() or "",
        "symbolStart": None if start == lldb.LLDB_INVALID_ADDRESS else start,
        "symbolEnd": None if end == lldb.LLDB_INVALID_ADDRESS else end,
    }


def _read_case_name(process, address: int) -> str:
    if address <= 0:
        raise RuntimeError("marker case-name address is null")
    error = lldb.SBError()
    value = process.ReadCStringFromMemory(address, 128, error)
    if not error.Success() or value is None:
        raise RuntimeError(
            "marker case-name read failed: "
            + (error.GetCString() or "unknown error")
        )
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def _exact_code_record(
    process,
    module: Mapping[str, object],
    offset: int,
    byte_count: int,
    expected_sha256: str,
    label: str,
) -> Mapping[str, object]:
    address = int(module["loadAddress"]) + offset
    payload = _read_memory(process, address, byte_count, label)
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected_sha256:
        raise RuntimeError(label + " exact code identity differs")
    return {
        "moduleOffset": offset,
        "loadAddress": address,
        "byteCount": byte_count,
        "codeSHA256": digest,
        "hex": payload.hex(),
    }


def _install_exact_breakpoints(frame) -> None:
    if _state["builderBreakpoint"] is not None:
        return
    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    module = _designlibrary_module(target)
    builder = _exact_code_record(
        process,
        module,
        PARAMETERS_BUILDER_MODULE_OFFSET,
        PARAMETERS_BUILDER_BYTE_COUNT,
        PARAMETERS_BUILDER_CODE_SHA256,
        "ResolvedRecipe.Parameters builder",
    )
    caller = _exact_code_record(
        process,
        module,
        PARAMETERS_CALLER_MODULE_OFFSET,
        PARAMETERS_CALLER_BYTE_COUNT,
        PARAMETERS_CALLER_CODE_SHA256,
        "ResolvedRecipe.Parameters caller",
    )
    return_address = caller["loadAddress"] + PARAMETERS_CALLER_RETURN_OFFSET
    builder_breakpoint = target.BreakpointCreateByAddress(builder["loadAddress"])
    return_breakpoint = target.BreakpointCreateByAddress(return_address)
    for breakpoint, callback, label in (
        (builder_breakpoint, "parameters_builder_entry", "builder entry"),
        (return_breakpoint, "parameters_builder_return", "builder return"),
    ):
        if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
            raise RuntimeError(label + " breakpoint is unresolved")
        _set_callback(breakpoint, callback, label)
        breakpoint.SetEnabled(False)
    _state["builderBreakpoint"] = builder_breakpoint
    _state["returnBreakpoint"] = return_breakpoint
    trace = _state["trace"]
    trace["module"] = module
    trace["parametersBuilder"] = builder
    trace["parametersCaller"] = dict(
        caller,
        returnOffset=PARAMETERS_CALLER_RETURN_OFFSET,
        returnAddress=return_address,
    )
    trace["status"] = "exact-code-gate-ready"
    _write_trace()


def _set_capture_breakpoints_enabled(enabled: bool) -> None:
    for key in ("builderBreakpoint", "returnBreakpoint"):
        breakpoint = _state[key]
        if breakpoint is not None:
            breakpoint.SetEnabled(enabled)


def _append_event(kind: str, case_index: int, call_index: Optional[int]) -> int:
    events = _state["trace"]["events"]
    index = len(events)
    events.append(
        {
            "index": index,
            "kind": kind,
            "caseIndex": case_index,
            "callIndex": call_index,
        }
    )
    return index


def marker(frame, _breakpoint_location, _internal_dict):
    try:
        process = frame.GetThread().GetProcess()
        name = _read_case_name(process, _register(frame, "x0"))
        phase = _register(frame, "x1")
        trace = _state["trace"]
        cases = trace["cases"]
        if phase == MARKER_BEFORE:
            if _state["activeCaseIndex"] is not None:
                raise RuntimeError("before marker overlaps an active case")
            case_index = len(cases)
            if case_index >= len(EXPECTED_CASE_NAMES):
                raise RuntimeError("unexpected extra case")
            if name != EXPECTED_CASE_NAMES[case_index]:
                raise RuntimeError(
                    "case order differs: "
                    + name
                    + " != "
                    + EXPECTED_CASE_NAMES[case_index]
                )
            _install_exact_breakpoints(frame)
            case = {
                "index": case_index,
                "name": name,
                "status": "active",
                "callIndices": [],
                "beforeFrame": _frame_record(frame),
            }
            cases.append(case)
            _state["activeCaseIndex"] = case_index
            case["beforeEventIndex"] = _append_event(
                "case-before", case_index, None
            )
            _set_capture_breakpoints_enabled(True)
            trace["status"] = "case-active"
        elif phase == MARKER_AFTER:
            case_index = _state["activeCaseIndex"]
            if case_index is None:
                raise RuntimeError("after marker has no active case")
            case = cases[case_index]
            if name != case["name"]:
                raise RuntimeError("after marker case name differs")
            if _state["pendingByThread"]:
                raise RuntimeError("after marker reached with a pending builder call")
            _set_capture_breakpoints_enabled(False)
            case["afterFrame"] = _frame_record(frame)
            case["afterEventIndex"] = _append_event(
                "case-after", case_index, None
            )
            case["builderCallCount"] = len(case["callIndices"])
            case["status"] = "closed"
            _state["activeCaseIndex"] = None
            trace["status"] = (
                "all-cases-closed"
                if len(cases) == len(EXPECTED_CASE_NAMES)
                else "case-closed"
            )
            _write_trace()
        else:
            raise RuntimeError("marker phase differs")
    except Exception as error:
        _failure("marker", error)
        return True
    return False


def parameters_builder_entry(frame, _breakpoint_location, _internal_dict):
    try:
        trace = _state["trace"]
        case_index = _state["activeCaseIndex"]
        if case_index is None:
            raise RuntimeError("builder entry is outside a fixed case interval")
        builder_address = trace["parametersBuilder"]["loadAddress"]
        return_address = trace["parametersCaller"]["returnAddress"]
        if frame.GetPC() != builder_address:
            raise RuntimeError("builder entry PC differs")
        if _register(frame, "x30") != return_address:
            raise RuntimeError("builder caller return address differs")
        thread_id = frame.GetThread().GetThreadID()
        if thread_id in _state["pendingByThread"]:
            raise RuntimeError("builder calls are unexpectedly nested")
        case = trace["cases"][case_index]
        if len(case["callIndices"]) >= MAXIMUM_CALLS_PER_CASE:
            raise RuntimeError("builder call count exceeds the prospective bound")
        call_index = len(trace["calls"])
        output_address = _register(frame, "x8")
        if output_address <= 0:
            raise RuntimeError("builder output address is null")
        call = {
            "index": call_index,
            "caseIndex": case_index,
            "indexWithinCase": len(case["callIndices"]),
            "threadID": thread_id,
            "entryFrame": _frame_record(frame),
            "registers": {
                name: "0x{0:016x}".format(_register(frame, name))
                for name in ("x0", "x1", "x2", "x8", "x20", "x30")
            },
            "outputAddress": output_address,
            "status": "entered",
        }
        trace["calls"].append(call)
        case["callIndices"].append(call_index)
        call["entryEventIndex"] = _append_event(
            "builder-entry", case_index, call_index
        )
        _state["pendingByThread"][thread_id] = call_index
    except Exception as error:
        _failure("parameters-builder-entry", error)
        return True
    return False


def parameters_builder_return(frame, _breakpoint_location, _internal_dict):
    try:
        trace = _state["trace"]
        case_index = _state["activeCaseIndex"]
        if case_index is None:
            raise RuntimeError("builder return is outside a fixed case interval")
        if frame.GetPC() != trace["parametersCaller"]["returnAddress"]:
            raise RuntimeError("builder return PC differs")
        thread = frame.GetThread()
        thread_id = thread.GetThreadID()
        call_index = _state["pendingByThread"].pop(thread_id, None)
        if call_index is None:
            raise RuntimeError("builder return has no paired entry")
        call = trace["calls"][call_index]
        if call["caseIndex"] != case_index or call["status"] != "entered":
            raise RuntimeError("builder return pair differs")
        payload = _read_memory(
            thread.GetProcess(),
            call["outputAddress"],
            PARAMETERS_BYTE_COUNT,
            "ResolvedRecipe.Parameters output",
        )
        call["parametersRawHex"] = payload.hex()
        call["parametersRawSHA256"] = hashlib.sha256(payload).hexdigest()
        call["returnFrame"] = _frame_record(frame)
        call["returnEventIndex"] = _append_event(
            "builder-return", case_index, call_index
        )
        call["status"] = "returned"
    except Exception as error:
        _failure("parameters-builder-return", error)
        return True
    return False


def finalize() -> None:
    trace = _state["trace"]
    if trace is None:
        return
    trace["statusBeforeFinalization"] = trace["status"]
    target = _debugger.GetSelectedTarget() if _debugger is not None else None
    process = target.GetProcess() if target is not None else None
    exit_status = process.GetExitStatus() if process is not None else -1
    trace["processExitStatus"] = exit_status
    trace["finalCaseCount"] = len(trace["cases"])
    trace["finalCallCount"] = len(trace["calls"])
    trace["finalEventCount"] = len(trace["events"])
    trace["finalFailureCount"] = len(trace["failures"])
    trace["finalPendingCallCount"] = len(_state["pendingByThread"])
    trace["allExpectedCasesClosed"] = (
        len(trace["cases"]) == len(EXPECTED_CASE_NAMES)
        and all(case.get("status") == "closed" for case in trace["cases"])
    )
    trace["allCallsReturned"] = all(
        call.get("status") == "returned" for call in trace["calls"]
    )
    if (
        not trace["failures"]
        and exit_status == 0
        and trace["allExpectedCasesClosed"]
        and trace["allCallsReturned"]
        and not _state["pendingByThread"]
        and _state["activeCaseIndex"] is None
    ):
        trace["status"] = "complete"
    else:
        trace["status"] = "failed"
    _write_trace()


def __lldb_init_module(debugger, _internal_dict) -> None:
    global _debugger
    _debugger = debugger
    _state["trace"] = _new_trace()
    _write_trace()
    target = debugger.GetSelectedTarget()
    breakpoint = target.BreakpointCreateByName(MARKER_NAME)
    if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
        raise RuntimeError("public Parameters marker breakpoint is unresolved")
    _set_callback(breakpoint, "marker", "public Parameters marker")
    _state["trace"]["markerBreakpoint"] = {
        "id": breakpoint.GetID(),
        "requestedName": MARKER_NAME,
        "locationCount": breakpoint.GetNumLocations(),
        "selection": "every before/after marker in frozen source order",
    }
    _state["trace"]["status"] = "marker-armed"
    _write_trace()
