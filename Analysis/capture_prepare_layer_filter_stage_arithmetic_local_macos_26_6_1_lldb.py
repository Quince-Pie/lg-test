"""Capture exact live FilterOp and Glass DOD arithmetic stage boundaries.

This diagnostic overlay installs code-hashed breakpoints at fixed instruction
boundaries in every FilterOp::apply_filter and GlassBackgroundFilter::DOD
execution.  Selection is structural: every hit is retained, and no rectangle
value influences capture.  LLDB imports this module with Apple's Python 3.9.
"""

import hashlib

import capture_prepare_layer_live_crop_arithmetic_local_macos_26_6_1_lldb as live_base


holdout_base = live_base.holdout_base
crop_base = live_base.crop_base
capture_base = live_base.capture_base

EXTENSION_KEY = "liveFilterStageArithmeticExtension"
EXTENSION_SCHEMA_VERSION = 1
MAXIMUM_RECORD_COUNT = 4096

FILTER_FUNCTION = "CA::Render::Updater::FilterOp::apply_filter(CA::Rect&, bool)"
FILTER_RELATIVE_TO_PREPARE_LAYER = -61476
FILTER_SYMBOL_BYTE_COUNT = 292
FILTER_CODE_SHA256 = "4dba83cf41031189caf8813b9eed5e833ee13484d4fa2f98cb4010f6e357cada"
FILTER_STAGE_SPECS = (
    ("entry", 0, "7f2303d5", "filter_entry"),
    ("afterUnapply", 88, "810242a9", "filter_after_unapply"),
    ("afterApplyDOD", 100, "6006416d", "filter_after_apply_dod"),
    ("afterApplyTransform", 140, "75000037", "filter_after_apply_transform"),
    ("final", 268, "fd7b45a9", "filter_final"),
)

DOD_FUNCTION = (
    "CA::OGL::GlassBackgroundFilter::DOD(CA::Render::Filter const*, "
    "CA::Render::Layer const*, CA::Rect&) const"
)
DOD_RELATIVE_TO_PREPARE_LAYER = -90656
DOD_SYMBOL_BYTE_COUNT = 1136
DOD_CODE_SHA256 = "d44b226f8edbfcb8fd37bc0f15a48b583df08063dc812e28cd06b1398d2f1678"
DOD_STAGE_SPECS = (
    ("entry", 0, "7f2303d5", "dod_entry"),
    ("beforePrimaryUnion", 408, "e50bc03d", "dod_before_primary_union"),
    ("afterPrimaryUnion", 504, "a082c43c", "dod_after_primary_union"),
    ("afterLayerSource", 592, "e51bc03d", "dod_after_layer_source"),
    ("afterBleedUnion", 940, "e002c03d", "dod_after_bleed_union"),
    ("beforeSourceIntersection", 988, "6202c03d", "dod_before_source_intersection"),
    ("final", 1072, "a88359f8", "dod_final"),
)

FILTER_STAGE_REGISTER_NAMES = (
    "x19",
    "x20",
    "x21",
    "sp",
    "pc",
    "v0",
    "v1",
    "v2",
    "v3",
    "v8",
)
DOD_STAGE_REGISTER_NAMES = (
    "x19",
    "x20",
    "x21",
    "sp",
    "pc",
    "v0",
    "v1",
    "v2",
    "v3",
    "v4",
    "v5",
    "v6",
    "v8",
    "v9",
    "v10",
    "v11",
    "v12",
)

_state = {
    "installed": False,
    "breakpoints": [],
    "eventSequence": 0,
    "filterHitCount": 0,
    "dodHitCount": 0,
    "pendingFilterByThread": {},
    "pendingDODByThread": {},
}


def _extension():
    trace = crop_base._state.get("trace")
    if trace is None:
        return None
    return trace.get(EXTENSION_KEY)


def _write_trace():
    crop_base._write_trace()


def _failure(stage, error):
    extension = _extension()
    if extension is not None:
        extension["failures"].append(
            {"stage": str(stage), "message": str(error)}
        )
    crop_base._failure("filter-stage-arithmetic-" + str(stage), error)


def _next_event(kind, record_kind, record_index):
    _state["eventSequence"] += 1
    event = {
        "sequence": _state["eventSequence"],
        "kind": str(kind),
        "recordKind": str(record_kind),
        "recordIndex": int(record_index),
    }
    _extension()["events"].append(event)
    return event


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _address_breakpoint(target, address, callback, label):
    breakpoint = target.BreakpointCreateByAddress(address)
    if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
        raise RuntimeError(label + " breakpoint is unresolved")
    _set_callback(breakpoint, callback, label)
    _state["breakpoints"].append(breakpoint)
    return breakpoint


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


def _authenticate_and_install_symbol(
    frame,
    function,
    relative_start,
    byte_count,
    expected_digest,
    stage_specs,
):
    process = frame.GetThread().GetProcess()
    target = process.GetTarget()
    prepare_start = crop_base._state["prepareLayer"]["symbolStart"]
    start = prepare_start + relative_start
    resolved = target.ResolveLoadAddress(start)
    symbol = resolved.GetSymbol()
    if not symbol.IsValid():
        raise RuntimeError(function + " symbol is invalid")
    if resolved.GetFunction().GetName() != function and symbol.GetName() != function:
        raise RuntimeError(function + " identity differs")
    if (
        symbol.GetStartAddress().GetLoadAddress(target) != start
        or symbol.GetEndAddress().GetLoadAddress(target) != start + byte_count
    ):
        raise RuntimeError(function + " bounds differ")
    code = capture_base._read_memory(process, start, byte_count, function + " code")
    digest = hashlib.sha256(code).hexdigest()
    if digest != expected_digest:
        raise RuntimeError(function + " complete code differs")
    stages = []
    for name, offset, expected_instruction, callback in stage_specs:
        instruction = code[offset : offset + 4]
        if instruction.hex() != expected_instruction:
            raise RuntimeError(function + " " + name + " instruction differs")
        breakpoint = _address_breakpoint(
            target,
            start + offset,
            callback,
            function + " " + name,
        )
        stages.append(
            {
                "name": name,
                "offset": offset,
                "address": start + offset,
                "instructionRawLittleEndianHex": instruction.hex(),
                "breakpointID": breakpoint.GetID(),
            }
        )
    return {
        "function": function,
        "relativeToPrepareLayer": relative_start,
        "symbolStart": start,
        "symbolEnd": start + byte_count,
        "symbolByteCount": byte_count,
        "codeSHA256": digest,
        "quartzCoreUUID": resolved.GetModule().GetUUIDString(),
        "stages": stages,
    }


def _install_stage_breakpoints(frame):
    if _state["installed"]:
        return
    extension = _extension()
    extension["filterCodeIdentity"] = _authenticate_and_install_symbol(
        frame,
        FILTER_FUNCTION,
        FILTER_RELATIVE_TO_PREPARE_LAYER,
        FILTER_SYMBOL_BYTE_COUNT,
        FILTER_CODE_SHA256,
        FILTER_STAGE_SPECS,
    )
    extension["dodCodeIdentity"] = _authenticate_and_install_symbol(
        frame,
        DOD_FUNCTION,
        DOD_RELATIVE_TO_PREPARE_LAYER,
        DOD_SYMBOL_BYTE_COUNT,
        DOD_CODE_SHA256,
        DOD_STAGE_SPECS,
    )
    _state["installed"] = True
    extension["status"] = "stage-breakpoints-active"


def _snapshot_rectangle(process, address, label):
    return capture_base._memory_snapshot(process, address, 32, label)


def _snapshot_stage(frame, rectangle_address, register_names, label):
    process = frame.GetThread().GetProcess()
    return {
        "pc": frame.GetPC(),
        "rectangle": _snapshot_rectangle(process, rectangle_address, label),
        "registers": capture_base._register_snapshot(frame, register_names),
    }


def _pending_record(kind, frame):
    thread_id = frame.GetThread().GetThreadID()
    key = "pendingFilterByThread" if kind == "filter" else "pendingDODByThread"
    pending = _state[key].get(thread_id, [])
    if not pending:
        raise RuntimeError(kind + " stage has no pending entry")
    records_key = "filterRecords" if kind == "filter" else "dodRecords"
    return _extension()[records_key][pending[-1]]


def _record_filter_stage(frame, stage, final):
    record = _pending_record("filter", frame)
    rectangle_address = capture_base._register(frame, "x19")
    if rectangle_address != record["rectangleAddress"]:
        raise RuntimeError("FilterOp rectangle address changed")
    snapshot = _snapshot_stage(
        frame,
        rectangle_address,
        FILTER_STAGE_REGISTER_NAMES,
        "FilterOp " + stage + " rectangle",
    )
    snapshot["name"] = stage
    snapshot["originalRectangleOnStack"] = capture_base._memory_snapshot(
        frame.GetThread().GetProcess(),
        capture_base._register(frame, "sp"),
        32,
        "FilterOp original rectangle",
    )
    event = _next_event(stage, "filter", record["recordIndex"])
    snapshot["eventSequence"] = event["sequence"]
    record["stages"].append(snapshot)
    if final:
        thread_id = frame.GetThread().GetThreadID()
        _state["pendingFilterByThread"][thread_id].pop()
        record["complete"] = True


def _record_dod_stage(frame, stage, final):
    record = _pending_record("dod", frame)
    rectangle_address = capture_base._register(frame, "x19")
    if rectangle_address != record["rectangleAddress"]:
        raise RuntimeError("Glass DOD rectangle address changed")
    process = frame.GetThread().GetProcess()
    snapshot = _snapshot_stage(
        frame,
        rectangle_address,
        DOD_STAGE_REGISTER_NAMES,
        "Glass DOD " + stage + " rectangle",
    )
    snapshot["name"] = stage
    snapshot["stack"] = capture_base._memory_snapshot(
        process,
        capture_base._register(frame, "sp"),
        144,
        "Glass DOD " + stage + " stack",
    )
    event = _next_event(stage, "dod", record["recordIndex"])
    snapshot["eventSequence"] = event["sequence"]
    record["stages"].append(snapshot)
    if final:
        thread_id = frame.GetThread().GetThreadID()
        _state["pendingDODByThread"][thread_id].pop()
        record["complete"] = True


def prepare_layer_entry(frame, breakpoint_location, internal_dict):
    result = live_base.prepare_layer_entry(frame, breakpoint_location, internal_dict)
    try:
        if crop_base._state.get("prepareLayer") is not None:
            _install_stage_breakpoints(frame)
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


def filter_entry(frame, _breakpoint_location, _internal_dict):
    try:
        _state["filterHitCount"] += 1
        if _state["filterHitCount"] > MAXIMUM_RECORD_COUNT:
            raise RuntimeError("FilterOp record bound exceeded")
        extension = _extension()
        process = frame.GetThread().GetProcess()
        thread_id = frame.GetThread().GetThreadID()
        operation_address = capture_base._register(frame, "x0")
        rectangle_address = capture_base._register(frame, "x1")
        transform_address = capture_base._read_u64(
            process, operation_address + 0x18, "FilterOp transform pointer"
        )
        record = {
            "recordIndex": len(extension["filterRecords"]),
            "hitIndex": _state["filterHitCount"],
            "threadID": thread_id,
            "entryPC": frame.GetPC(),
            "entrySP": capture_base._register(frame, "sp"),
            "operationAddress": operation_address,
            "rectangleAddress": rectangle_address,
            "mergeArgument": capture_base._register(frame, "w2"),
            "operationObject": capture_base._memory_snapshot(
                process, operation_address, 64, "FilterOp object"
            ),
            "transformAddress": transform_address,
            "transform": capture_base._memory_snapshot(
                process, transform_address, 48, "FilterOp transform"
            ),
            "entryRectangle": _snapshot_rectangle(
                process, rectangle_address, "FilterOp entry rectangle"
            ),
            "stages": [],
            "complete": False,
        }
        extension["filterRecords"].append(record)
        _state["pendingFilterByThread"].setdefault(thread_id, []).append(
            record["recordIndex"]
        )
        event = _next_event("entry", "filter", record["recordIndex"])
        record["entryEventSequence"] = event["sequence"]
    except Exception as error:
        _failure("filter-entry", error)
    return False


def filter_after_unapply(frame, _breakpoint_location, _internal_dict):
    try:
        _record_filter_stage(frame, "afterUnapply", False)
    except Exception as error:
        _failure("filter-after-unapply", error)
    return False


def filter_after_apply_dod(frame, _breakpoint_location, _internal_dict):
    try:
        _record_filter_stage(frame, "afterApplyDOD", False)
    except Exception as error:
        _failure("filter-after-apply-dod", error)
    return False


def filter_after_apply_transform(frame, _breakpoint_location, _internal_dict):
    try:
        _record_filter_stage(frame, "afterApplyTransform", False)
    except Exception as error:
        _failure("filter-after-apply-transform", error)
    return False


def filter_final(frame, _breakpoint_location, _internal_dict):
    try:
        _record_filter_stage(frame, "final", True)
    except Exception as error:
        _failure("filter-final", error)
    return False


def dod_entry(frame, _breakpoint_location, _internal_dict):
    try:
        _state["dodHitCount"] += 1
        if _state["dodHitCount"] > MAXIMUM_RECORD_COUNT:
            raise RuntimeError("Glass DOD record bound exceeded")
        extension = _extension()
        process = frame.GetThread().GetProcess()
        thread_id = frame.GetThread().GetThreadID()
        rectangle_address = capture_base._register(frame, "x3")
        filter_pending = _state["pendingFilterByThread"].get(thread_id, [])
        parent_index = filter_pending[-1] if filter_pending else None
        record = {
            "recordIndex": len(extension["dodRecords"]),
            "hitIndex": _state["dodHitCount"],
            "threadID": thread_id,
            "entryPC": frame.GetPC(),
            "entrySP": capture_base._register(frame, "sp"),
            "implementationAddress": capture_base._register(frame, "x0"),
            "filterAddress": capture_base._register(frame, "x1"),
            "layerAddress": capture_base._register(frame, "x2"),
            "rectangleAddress": rectangle_address,
            "parentFilterRecordIndex": parent_index,
            "entryRectangle": _snapshot_rectangle(
                process, rectangle_address, "Glass DOD entry rectangle"
            ),
            "stages": [],
            "complete": False,
        }
        extension["dodRecords"].append(record)
        _state["pendingDODByThread"].setdefault(thread_id, []).append(
            record["recordIndex"]
        )
        event = _next_event("entry", "dod", record["recordIndex"])
        record["entryEventSequence"] = event["sequence"]
    except Exception as error:
        _failure("dod-entry", error)
    return False


def dod_before_primary_union(frame, _breakpoint_location, _internal_dict):
    try:
        _record_dod_stage(frame, "beforePrimaryUnion", False)
    except Exception as error:
        _failure("dod-before-primary-union", error)
    return False


def dod_after_primary_union(frame, _breakpoint_location, _internal_dict):
    try:
        _record_dod_stage(frame, "afterPrimaryUnion", False)
    except Exception as error:
        _failure("dod-after-primary-union", error)
    return False


def dod_after_layer_source(frame, _breakpoint_location, _internal_dict):
    try:
        _record_dod_stage(frame, "afterLayerSource", False)
    except Exception as error:
        _failure("dod-after-layer-source", error)
    return False


def dod_after_bleed_union(frame, _breakpoint_location, _internal_dict):
    try:
        _record_dod_stage(frame, "afterBleedUnion", False)
    except Exception as error:
        _failure("dod-after-bleed-union", error)
    return False


def dod_before_source_intersection(frame, _breakpoint_location, _internal_dict):
    try:
        _record_dod_stage(frame, "beforeSourceIntersection", False)
    except Exception as error:
        _failure("dod-before-source-intersection", error)
    return False


def dod_final(frame, _breakpoint_location, _internal_dict):
    try:
        _record_dod_stage(frame, "final", True)
    except Exception as error:
        _failure("dod-final", error)
    return False


def finalize():
    live_base.finalize()
    extension = _extension()
    if extension is not None:
        extension["status"] = "finalized"
        extension["finalEventSequence"] = _state["eventSequence"]
        extension["finalFilterHitCount"] = _state["filterHitCount"]
        extension["finalDODHitCount"] = _state["dodHitCount"]
        extension["finalCompleteFilterRecordCount"] = sum(
            record.get("complete") is True
            for record in extension["filterRecords"]
        )
        extension["finalCompleteDODRecordCount"] = sum(
            record.get("complete") is True for record in extension["dodRecords"]
        )
        extension["finalPendingFilterRecordCount"] = sum(
            len(records) for records in _state["pendingFilterByThread"].values()
        )
        extension["finalPendingDODRecordCount"] = sum(
            len(records) for records in _state["pendingDODByThread"].values()
        )
        extension["finalFailureCount"] = len(extension["failures"])
    _write_trace()


def __lldb_init_module(debugger, internal_dict):
    live_base.__lldb_init_module(debugger, internal_dict)
    trace = crop_base._state.get("trace")
    if trace is None:
        return
    trace[EXTENSION_KEY] = {
        "liveFilterStageArithmeticExtensionSchemaVersion": (
            EXTENSION_SCHEMA_VERSION
        ),
        "classification": (
            "retrospective value-blind inventory of every exact live FilterOp "
            "and Glass DOD arithmetic stage"
        ),
        "status": "initialized",
        "configuration": {
            "filterFunction": FILTER_FUNCTION,
            "filterRelativeToPrepareLayer": FILTER_RELATIVE_TO_PREPARE_LAYER,
            "filterSymbolByteCount": FILTER_SYMBOL_BYTE_COUNT,
            "filterCodeSHA256": FILTER_CODE_SHA256,
            "filterStageSpecifications": [
                {
                    "name": name,
                    "offset": offset,
                    "instructionRawLittleEndianHex": instruction,
                }
                for name, offset, instruction, _callback in FILTER_STAGE_SPECS
            ],
            "dodFunction": DOD_FUNCTION,
            "dodRelativeToPrepareLayer": DOD_RELATIVE_TO_PREPARE_LAYER,
            "dodSymbolByteCount": DOD_SYMBOL_BYTE_COUNT,
            "dodCodeSHA256": DOD_CODE_SHA256,
            "dodStageSpecifications": [
                {
                    "name": name,
                    "offset": offset,
                    "instructionRawLittleEndianHex": instruction,
                }
                for name, offset, instruction, _callback in DOD_STAGE_SPECS
            ],
            "selectionRule": (
                "retain every hit at every frozen code-hashed stage boundary; "
                "pair nested calls only by thread-local call order"
            ),
            "rectangleValuesUsedForSelection": False,
            "cropOrProducerValuesUsedForSelection": False,
            "hardwareWatchpointsUsed": False,
            "instructionSteppingUsed": False,
            "maximumRecordCount": MAXIMUM_RECORD_COUNT,
        },
        "filterCodeIdentity": {},
        "dodCodeIdentity": {},
        "events": [],
        "filterRecords": [],
        "dodRecords": [],
        "failures": [],
    }
    try:
        _install_proxy_callbacks()
        _write_trace()
    except Exception as error:
        _failure("initialization", error)
