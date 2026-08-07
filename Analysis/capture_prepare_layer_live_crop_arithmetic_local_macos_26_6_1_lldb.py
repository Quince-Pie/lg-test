"""Authenticate live crop-arithmetic symbols during an exact Retina capture.

The overlay reads complete code bytes only.  It adds no arithmetic breakpoint
and reads no rectangle, crop, producer, image, or shader value.
"""

import hashlib

import capture_prepare_layer_crop_policy_holdout_live_local_macos_26_6_1_lldb as live_base
import prepare_layer_live_crop_arithmetic_local_macos_26_6_1 as arithmetic


holdout_base = live_base.holdout_base
crop_base = holdout_base.union_base.crop_base
capture_base = crop_base.capture_base

EXTENSION_KEY = "liveCropArithmeticCodeIdentity"

_state = {"authenticated": False}


def _extension():
    trace = crop_base._state.get("trace")
    if trace is None:
        return None
    return trace.get(EXTENSION_KEY)


def _write_trace():
    crop_base._write_trace()


def _failure(stage, error):
    crop_base._failure("live-crop-arithmetic-" + str(stage), error)


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _install_proxy_callbacks():
    callbacks = (
        (
            crop_base._state.get("prepareEntryBreakpoint"),
            "prepare_layer_entry",
            "prepare entry",
        ),
        (
            crop_base._state.get("markerBreakpoint"),
            "crop_transfer_marker",
            "crop marker",
        ),
        (
            holdout_base.union_base._state.get("unionCallBreakpoint"),
            "crop_union_call",
            "union call",
        ),
        (
            holdout_base.union_base._state.get("unionReturnBreakpoint"),
            "crop_union_return",
            "union return",
        ),
        (
            holdout_base._state.get("storeBreakpoint"),
            "nested_crop_store",
            "crop store",
        ),
    )
    for breakpoint, callback, label in callbacks:
        if breakpoint is not None:
            _set_callback(breakpoint, callback, label)


def _authenticate_symbols(frame):
    if _state["authenticated"]:
        return
    extension = _extension()
    if extension is None:
        raise RuntimeError("live crop-arithmetic extension is absent")
    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    prepare_start = crop_base._state["prepareLayer"]["symbolStart"]
    records = []
    for specification in arithmetic.ARITHMETIC_CODE_SPECS:
        contexts = target.FindFunctions(specification["function"])
        if contexts.GetSize() != 1:
            raise RuntimeError(specification["name"] + " live symbol count differs")
        symbol = contexts.GetContextAtIndex(0).GetSymbol()
        if not symbol.IsValid():
            raise RuntimeError(specification["name"] + " live symbol is invalid")
        start_address = symbol.GetStartAddress()
        end_address = symbol.GetEndAddress()
        start = start_address.GetLoadAddress(target)
        end = end_address.GetLoadAddress(target)
        module = start_address.GetModule()
        if (
            start - prepare_start != specification["relativeToPrepareLayer"]
            or end - start != specification["symbolByteCount"]
            or module.GetUUIDString() != arithmetic.QUARTZCORE_UUID
        ):
            raise RuntimeError(specification["name"] + " live bounds differ")
        code = capture_base._read_memory(
            process,
            start,
            end - start,
            specification["name"] + " complete code",
        )
        digest = hashlib.sha256(code).hexdigest()
        if digest != specification["codeSHA256"]:
            raise RuntimeError(specification["name"] + " live code differs")
        records.append(
            {
                **specification,
                "symbolStart": start,
                "symbolEnd": end,
                "quartzCoreUUID": module.GetUUIDString(),
                "modulePath": module.GetFileSpec().fullpath or "",
            }
        )
    extension["records"] = records
    extension["status"] = "authenticated"
    extension["recordCount"] = len(records)
    _state["authenticated"] = True


def prepare_layer_entry(frame, breakpoint_location, internal_dict):
    result = live_base.prepare_layer_entry(frame, breakpoint_location, internal_dict)
    try:
        _authenticate_symbols(frame)
        _install_proxy_callbacks()
        _write_trace()
    except Exception as error:
        _failure("prepare-entry", error)
    return result


def crop_transfer_marker(frame, breakpoint_location, internal_dict):
    return live_base.crop_transfer_marker(frame, breakpoint_location, internal_dict)


def crop_union_call(frame, breakpoint_location, internal_dict):
    return live_base.crop_union_call(frame, breakpoint_location, internal_dict)


def crop_union_return(frame, breakpoint_location, internal_dict):
    return live_base.crop_union_return(frame, breakpoint_location, internal_dict)


def nested_crop_store(frame, breakpoint_location, internal_dict):
    return live_base.nested_crop_store(frame, breakpoint_location, internal_dict)


def finalize():
    live_base.finalize()
    extension = _extension()
    if extension is not None:
        extension["status"] = (
            "finalized" if _state["authenticated"] else "unauthenticated"
        )
        extension["authenticated"] = _state["authenticated"]
    _write_trace()


def __lldb_init_module(debugger, internal_dict):
    live_base.__lldb_init_module(debugger, internal_dict)
    trace = crop_base._state.get("trace")
    if trace is None:
        return
    trace[EXTENSION_KEY] = {
        "liveCropArithmeticCodeIdentitySchemaVersion": (
            arithmetic.IDENTITY_SCHEMA_VERSION
        ),
        "classification": (
            "value-blind direct-M1 complete-symbol authentication for exact "
            "SDF, transform, FilterOp, and Glass DOD arithmetic"
        ),
        "status": "initialized",
        "selection": {
            "exactSymbolNamesAndBoundsOnly": True,
            "cropOrProducerValuesUsed": False,
            "imageValuesUsed": False,
            "hardwareWatchpointsUsed": False,
            "instructionSteppingUsed": False,
        },
        "expectedRecords": arithmetic.frozen_code_records(),
        "records": [],
    }
    try:
        _install_proxy_callbacks()
        _write_trace()
    except Exception as error:
        _failure("initialization", error)
