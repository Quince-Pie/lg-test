"""Two-pass, output-blind calibration for the true producer helper call.

The inventory pass retains every structurally qualified ``prepare_layer_mask``
entry and never stops at one.  An offline validator joins caller role identity
to the independently opened producer-store role.  The selected pass reads only
that validator's ordinal and traces the corresponding call in a fresh process.
No rectangle or helper output participates in either capture-time selector.
"""

import hashlib
import json
import os

import capture_prepare_layer_mask_instruction_trace_lldb as base


TRANSPORT_SCHEMA_VERSION = 1
INVENTORY_MODE = "inventory"
SELECTED_MODE = "selected"
INVENTORY_SENTINEL_ORDINAL = 4097
KNOWN_HELPER_CODE_SHA256 = (
    "f78c5fd222dc429152882dffb0b88a5535050351e3a2a5d7102a5abeca5c4c0c"
)
MODE_ENVIRONMENT_NAME = "LG_PREPARE_LAYER_MASK_CAPTURE_MODE"
INVENTORY_VALIDATION_ENVIRONMENT_NAME = (
    "LG_PREPARE_LAYER_MASK_INVENTORY_VALIDATION"
)


_mode = None
_target_ordinal = None
_inventory_source = None
_callback_events = []


def _sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def _selection_rule(ordinal):
    return (
        "among exact direct-normal transition callers, select marker interval "
        "2 ordinal "
        + str(ordinal)
        + ", then require x1=x19+0x420 and x3=x19+0x290; do not inspect "
        "any rectangle or output bytes"
    )


def _load_configuration():
    mode = os.environ.get(MODE_ENVIRONMENT_NAME)
    if mode == INVENTORY_MODE:
        return mode, INVENTORY_SENTINEL_ORDINAL, None
    if mode != SELECTED_MODE:
        raise RuntimeError("prepare_layer_mask calibration mode differs")
    path = os.environ.get(INVENTORY_VALIDATION_ENVIRONMENT_NAME)
    if not path:
        raise RuntimeError("prepare_layer_mask inventory validation is absent")
    with open(path, "rb") as stream:
        payload = stream.read()
    document = json.loads(payload.decode("utf-8"))
    selection = document.get("structuralSelection") or {}
    helper = document.get("helper") or {}
    sealed = document.get("sealedConclusion") or {}
    ordinal = selection.get("sample2TargetQualifiedOrdinal")
    if (
        document.get("prepareLayerMaskInstructionInventoryValidationSchemaVersion")
        != 1
        or document.get("conclusion") != "success"
        or helper.get("codeSHA256") != KNOWN_HELPER_CODE_SHA256
        or selection.get("sampleIndex") != 2
        or not isinstance(ordinal, int)
        or not 1 <= ordinal <= base.MAXIMUM_QUALIFIED_HELPER_ENTRY_COUNT
        or sealed.get("allHelperEntriesRetainedWithoutSelection") is not True
        or sealed.get("sample2ProducerRoleMappedByLastPriorHelper") is not True
        or sealed.get("cropOrOutputValuesUsedForSelection") is not False
        or sealed.get("exactHelperSemanticsDecoded") is not False
        or sealed.get("productionShaderAuthorized") is not False
    ):
        raise RuntimeError("prepare_layer_mask inventory validation differs")
    source = {
        "fileName": os.path.basename(path),
        "sha256": _sha256(payload),
        "inventoryTraceSHA256": (document.get("inputs") or {}).get("traceSHA256"),
        "inventoryTimelineSHA256": (document.get("inputs") or {}).get(
            "timelineSHA256"
        ),
    }
    return mode, ordinal, source


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _install_callback_proxies():
    entry = base.crop_base._state.get("prepareEntryBreakpoint")
    marker = base.crop_base._state.get("markerBreakpoint")
    union_call = base.union_base._state.get("unionCallBreakpoint")
    union_return = base.union_base._state.get("unionReturnBreakpoint")
    store = base.holdout_base._state.get("storeBreakpoint")
    helper = base._state.get("helperBreakpoint")
    callbacks = (
        (entry, "prepare_layer_entry", "prepare entry"),
        (marker, "crop_transfer_marker", "crop transfer marker"),
        (union_call, "crop_union_call", "crop union call"),
        (union_return, "crop_union_return", "crop union return"),
        (store, "nested_crop_store", "nested crop store"),
        (helper, "prepare_layer_mask_entry", "prepare_layer_mask entry"),
    )
    for breakpoint, callback, label in callbacks:
        if breakpoint is not None:
            _set_callback(breakpoint, callback, label)


def _append_callback_event(kind, record):
    event = {
        "eventIndex": len(_callback_events),
        "kind": kind,
        "markerIntervalIndex": (
            len(base.crop_base._state["trace"]["qualifiedRecords"]) + 1
        ),
    }
    event.update(record)
    _callback_events.append(event)


def prepare_layer_entry(frame, breakpoint_location, internal_dict):
    result = base.prepare_layer_entry(frame, breakpoint_location, internal_dict)
    try:
        _install_callback_proxies()
        base._write_trace()
    except Exception as error:
        base._failure("inventory-calibration-entry", error)
    return result


def crop_union_call(frame, breakpoint_location, internal_dict):
    return base.crop_union_call(frame, breakpoint_location, internal_dict)


def crop_union_return(frame, breakpoint_location, internal_dict):
    return base.crop_union_return(frame, breakpoint_location, internal_dict)


def nested_crop_store(frame, breakpoint_location, internal_dict):
    records = base.holdout_base._extension_trace()["storeRecords"]
    before = len(records)
    result = base.nested_crop_store(frame, breakpoint_location, internal_dict)
    if len(records) == before + 1:
        record = records[-1]
        _append_callback_event(
            "nested-crop-store",
            {
                "storeRecordIndex": record["recordIndex"],
                "callerRoleBase": record["frameIdentity"]["roleBase"],
                "prepareRecursionDepth": record["prepareRecursionDepth"],
            },
        )
    elif len(records) != before:
        base._failure("inventory-store-event", "store record count differs")
    return result


def crop_transfer_marker(frame, breakpoint_location, internal_dict):
    records = base.crop_base._state["trace"]["qualifiedRecords"]
    before = len(records)
    result = base.crop_transfer_marker(frame, breakpoint_location, internal_dict)
    if len(records) == before + 1:
        record = records[-1]
        _append_callback_event(
            "crop-transfer-marker",
            {
                "markerRecordIndex": record["recordIndex"],
                "markerIntervalIndex": len(records),
            },
        )
    elif len(records) != before:
        base._failure("inventory-marker-event", "marker record count differs")
    return result


def prepare_layer_mask_entry(frame, breakpoint_location, internal_dict):
    records = base._extension_trace()["helperEntryRecords"]
    before = len(records)
    result = base.prepare_layer_mask_entry(
        frame, breakpoint_location, internal_dict
    )
    if len(records) == before + 1:
        record = records[-1]
        identity = record["frameIdentity"]
        _append_callback_event(
            "prepare-layer-mask-entry",
            {
                "helperRecordIndex": record["recordIndex"],
                "qualifiedOrdinalWithinMarkerInterval": record[
                    "qualifiedOrdinalWithinMarkerInterval"
                ],
                "callerRoleBase": identity["callerRoleBase"],
                "outputLayerShapesAddress": identity["outputLayerShapesX3"],
                "prepareRecursionDepth": record["prepareRecursionDepth"],
            },
        )
    elif len(records) != before:
        base._failure("inventory-helper-event", "helper record count differs")
    return result


def trace_selected_helper():
    if _mode != SELECTED_MODE or _target_ordinal == INVENTORY_SENTINEL_ORDINAL:
        raise RuntimeError("prepare_layer_mask selected trace requested in inventory")
    base.trace_selected_helper()


def finalize():
    extension = base._extension_trace()
    if extension is not None:
        transport = extension.get("prepareLayerMaskInventoryCalibrationTransport")
        if transport is not None:
            transport["callbackEvents"] = list(_callback_events)
            transport["finalCallbackEventCount"] = len(_callback_events)
    base.finalize()


def __lldb_init_module(debugger, internal_dict):
    global _mode, _target_ordinal, _inventory_source
    del _callback_events[:]
    _mode, _target_ordinal, _inventory_source = _load_configuration()
    base.crop_base.PREPARE_LAYER_FUNCTION = base.capture_base.PREPARE_LAYER_FUNCTION
    base.TARGET_QUALIFIED_ORDINAL = _target_ordinal
    base.__lldb_init_module(debugger, internal_dict)
    extension = base._extension_trace()
    if extension is None:
        return
    extension["configuration"]["entrySelectionRule"] = _selection_rule(
        _target_ordinal
    )
    extension["classification"] = (
        "output-blind complete helper-entry inventory for structural role "
        "correlation"
        if _mode == INVENTORY_MODE
        else "fresh helper-body calibration selected only by the frozen "
        "inventory role correlation"
    )
    extension["prepareLayerMaskInventoryCalibrationTransport"] = {
        "prepareLayerMaskInventoryCalibrationTransportSchemaVersion": (
            TRANSPORT_SCHEMA_VERSION
        ),
        "mode": _mode,
        "targetQualifiedOrdinal": _target_ordinal,
        "inventorySentinelOrdinal": INVENTORY_SENTINEL_ORDINAL,
        "knownHelperCodeSHA256": KNOWN_HELPER_CODE_SHA256,
        "inventoryValidationSource": _inventory_source,
        "cropOrOutputValuesReadByTransport": False,
        "newBreakpointAddedByTransport": False,
        "captureByteRangeChangedByTransport": False,
        "steppingRuleChangedByTransport": False,
    }
    try:
        _install_callback_proxies()
        base._write_trace()
    except Exception as error:
        base._failure("inventory-calibration-initialization", error)
