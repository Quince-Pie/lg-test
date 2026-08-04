#!/usr/bin/env python3
"""Validate the preregistered early/direct and dynamic/alternate trace."""

import argparse
import hashlib
import json
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_layer_shapes_merge_trace as base


EXPECTED_TRACE_SCHEMA_VERSION = 1
VALIDATION_SCHEMA_VERSION = 1
EXPECTED_CLASSIFICATION = (
    "preregistered-bounded-early-direct-and-dynamic-alternate-layer-shapes-"
    "construction-trace; branch-semantics-public-crop-law-unseen-transfer-and-"
    "product-parity-remain-sealed"
)
EXPECTED_VALIDATION_CLASSIFICATION = (
    "prospective-integrity-gate-for-early-direct-and-dynamic-alternate-layer-"
    "shapes-construction; semantics-remain-sealed"
)
DIRECT_CALL_OFFSET = 0x32C0
DIRECT_RETURN_OFFSET = 0x32C4
DIRECT_CALL_RAW_LITTLE_ENDIAN_HEX = "a8f0ff97"
DIRECT_CALL_WORD = 0x97FFF0A8
DIRECT_CALL_DISPLACEMENT = -0x3D60
UNION_HELPER_RELATIVE_TO_PREPARE_LAYER = -0xAA0
UNION_HELPER_SYMBOL_NAME = (
    "CA::Render::Updater::LayerShapes::union_bounds(CA::Rect const&, bool)"
)
UNION_HELPER_SYMBOL_BYTE_COUNT = 404
UNION_HELPER_SYMBOL_SHA256 = (
    "246257a9bc1a608f59dbc07345397a8851b49528c59407eb775e9b9895a2c4b7"
)
UNION_HELPER_CODE_WINDOW_BYTE_COUNT = 0x1000
UNION_HELPER_CODE_WINDOW_SHA256 = (
    "6ef1454472d8fe5754253f26faa8db1f5473396b9879b74dcbe16fb7ffd4d10b"
)
ALTERNATE_STORE_OFFSET = 0x33F0
ALTERNATE_AFTER_OFFSET = 0x33F4
ALTERNATE_STORE_RAW_LITTLE_ENDIAN_HEX = "608614ad"
LAYER_SHAPES_BYTE_COUNT = 0x20
ROLE_STATE_BYTE_COUNT = 0x800
MAXIMUM_LATE_CANDIDATE_COUNT = 512
MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT = 16
MAXIMUM_DIRECT_CALL_SITE_HIT_COUNT = 4096
MAXIMUM_DIRECT_RECORD_COUNT = 64
MAXIMUM_ALTERNATE_STORE_HIT_COUNT = 4096
MAXIMUM_ALTERNATE_RECORD_COUNT = 96
MAXIMUM_BACKTRACE_FRAME_COUNT = 20
MINIMUM_DIRECT_RECORD_COUNT = 1
MINIMUM_SELECTED_DIRECT_RECORD_COUNT = 1
MINIMUM_SELECTED_ALTERNATE_RECORD_COUNT = 8
MINIMUM_DISTINCT_SELECTED_ALTERNATE_SOURCE_COUNT = 8
GENERAL_REGISTER_NAMES = ("x0", "x1", "x2", "x19", "x28", "x30", "sp", "pc")
ALTERNATE_SIMD_REGISTER_NAMES = ("v0", "v1")
EXPECTED_CONFIGURATION = {
    "captureBackdropSymbol": base.CAPTURE_BACKDROP_SYMBOL,
    "captureBackdropCodeByteCount": 0x4000,
    "captureBackdropCodeSHA256": base.CAPTURE_BACKDROP_CODE_SHA256,
    "captureBackdropLateOffset": 0x2B58,
    "prepareLayerFunction": base.PREPARE_LAYER_FUNCTION,
    "prepareLayerSymbolByteCount": base.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
    "prepareLayerCodeWindowOffset": base.PREPARE_LAYER_CODE_WINDOW_OFFSET,
    "prepareLayerCodeWindowByteCount": base.PREPARE_LAYER_CODE_WINDOW_BYTE_COUNT,
    "prepareLayerCodeWindowSHA256": base.PREPARE_LAYER_CODE_WINDOW_SHA256,
    "directCallOffset": DIRECT_CALL_OFFSET,
    "directReturnOffset": DIRECT_RETURN_OFFSET,
    "directCallRawLittleEndianHex": DIRECT_CALL_RAW_LITTLE_ENDIAN_HEX,
    "directCallWord": DIRECT_CALL_WORD,
    "directCallDisplacement": DIRECT_CALL_DISPLACEMENT,
    "unionHelperRelativeToPrepareLayer": UNION_HELPER_RELATIVE_TO_PREPARE_LAYER,
    "unionHelperSymbolName": UNION_HELPER_SYMBOL_NAME,
    "unionHelperSymbolByteCount": UNION_HELPER_SYMBOL_BYTE_COUNT,
    "unionHelperSymbolSHA256": UNION_HELPER_SYMBOL_SHA256,
    "unionHelperCodeWindowByteCount": UNION_HELPER_CODE_WINDOW_BYTE_COUNT,
    "unionHelperCodeWindowSHA256": UNION_HELPER_CODE_WINDOW_SHA256,
    "alternateStoreOffset": ALTERNATE_STORE_OFFSET,
    "alternateAfterOffset": ALTERNATE_AFTER_OFFSET,
    "alternateStoreRawLittleEndianHex": ALTERNATE_STORE_RAW_LITTLE_ENDIAN_HEX,
    "layerShapesByteCount": LAYER_SHAPES_BYTE_COUNT,
    "roleStateByteCount": ROLE_STATE_BYTE_COUNT,
    "maximumLateCandidateCount": MAXIMUM_LATE_CANDIDATE_COUNT,
    "maximumLateCandidateDiagnosticCount": MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT,
    "maximumDirectCallSiteHitCount": MAXIMUM_DIRECT_CALL_SITE_HIT_COUNT,
    "maximumDirectRecordCount": MAXIMUM_DIRECT_RECORD_COUNT,
    "maximumAlternateStoreHitCount": MAXIMUM_ALTERNATE_STORE_HIT_COUNT,
    "maximumAlternateRecordCount": MAXIMUM_ALTERNATE_RECORD_COUNT,
    "maximumBacktraceFrameCount": MAXIMUM_BACKTRACE_FRAME_COUNT,
    "generalRegisterNames": list(GENERAL_REGISTER_NAMES),
    "alternateSIMDRegisterNames": list(ALTERNATE_SIMD_REGISTER_NAMES),
    "directRecordRule": (
        "retain every early prepare_layer+0x32c0 call pair up to the bound, then "
        "classify x28 against the downstream selected source"
    ),
    "alternateRecordRule": (
        "retain every preselection prepare_layer+0x33f0 store pair; after "
        "selection retain only pairs whose x28 is the selected source"
    ),
}


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    return base.mapping(value, label)


def sequence(value: Any, label: str) -> Sequence[Any]:
    return base.sequence(value, label)


def integer(value: Any, label: str) -> int:
    return base.integer(value, label)


def _validate_backtrace(
    value: Any,
    label: str,
    *,
    expected_first_pc: int,
    expected_symbol_start: int,
    expected_module: Mapping[str, Any],
) -> None:
    frames = sequence(value, label)
    if len(frames) > MAXIMUM_BACKTRACE_FRAME_COUNT:
        raise ValueError(f"{label} bounds differ")
    base.backtrace(
        frames,
        label,
        expected_first_pc=expected_first_pc,
        expected_symbol_start=expected_symbol_start,
        expected_module=expected_module,
    )


def _simd_source_registers(value: Any, label: str) -> bytes:
    records = list(sequence(value, label))
    if len(records) != len(ALTERNATE_SIMD_REGISTER_NAMES):
        raise ValueError(f"{label} inventory differs")
    payload = bytearray()
    for expected_name, value_record in zip(
        ALTERNATE_SIMD_REGISTER_NAMES, records, strict=True
    ):
        record = mapping(value_record, f"{label} {expected_name}")
        if (
            record.get("name") != expected_name
            or record.get("byteCount") != 16
            or "unsignedValue" in record
            or record.get("valueString") is not None
            and not isinstance(record.get("valueString"), str)
        ):
            raise ValueError(f"{label} {expected_name} identity differs")
        payload.extend(
            base.hexadecimal_payload(
                record.get("hex"), 16, f"{label} {expected_name}"
            )
        )
    return bytes(payload)


def _selected_object_chain(trace: Mapping[str, Any]) -> tuple[Mapping[str, Any], int]:
    chain = mapping(trace.get("objectChain"), "selected object chain")
    addresses = mapping(chain.get("addresses"), "selected object addresses")
    if set(addresses) != {"source", "owner", "layer", "layerState"}:
        raise ValueError("selected object inventory differs")
    for name, address in addresses.items():
        if integer(address, f"selected {name} address") <= 0:
            raise ValueError(f"selected {name} address differs")
    source_rectangle = list(
        struct.unpack(
            "<4i",
            base.hexadecimal_payload(
                chain.get("sourceSelectedRectI32Hex"), 16, "source rectangle"
            ),
        )
    )
    layer_state_rectangle = list(
        struct.unpack(
            "<4i",
            base.hexadecimal_payload(
                chain.get("layerStateSelectedRectI32Hex"),
                16,
                "layer-state rectangle",
            ),
        )
    )
    owner_rectangle = list(
        struct.unpack(
            "<4d",
            base.hexadecimal_payload(
                chain.get("ownerSelectedRectF64Hex"), 32, "owner rectangle"
            ),
        )
    )
    if (
        chain.get("exact") is not True
        or chain.get("pointerChainExact") is not True
        or chain.get("preconvergenceExact") is not True
        or chain.get("ownerEqualsLayerStateRectangle") is not True
        or chain.get("sourceEqualsLayerStateRectangle") is not False
        or chain.get("sourceSelectedRectI32") != source_rectangle
        or chain.get("layerStateSelectedRectI32") != layer_state_rectangle
        or chain.get("ownerSelectedRectF64") != owner_rectangle
        or owner_rectangle != [float(item) for item in layer_state_rectangle]
        or source_rectangle == layer_state_rectangle
    ):
        raise ValueError("selected object state differs")
    return chain, integer(addresses.get("source"), "selected source")


def _validate_static_gates(trace: Mapping[str, Any]):
    capture = mapping(trace.get("captureBackdrop"), "capture_backdrop gate")
    capture_module = base.module_record(
        capture.get("module"), "capture_backdrop module"
    )
    if (
        integer(capture.get("symbolAddress"), "capture_backdrop address") <= 0
        or capture.get("codeByteCount") != 0x4000
        or capture.get("codeSHA256") != base.CAPTURE_BACKDROP_CODE_SHA256
    ):
        raise ValueError("capture_backdrop gate differs")
    prepare = mapping(trace.get("prepareLayer"), "prepare_layer gate")
    start = integer(prepare.get("symbolStart"), "prepare_layer start")
    end = integer(prepare.get("symbolEnd"), "prepare_layer end")
    module = base.module_record(prepare.get("module"), "prepare_layer module")
    if (
        prepare.get("function") != base.PREPARE_LAYER_FUNCTION
        or end - start != base.PREPARE_LAYER_SYMBOL_BYTE_COUNT
        or prepare.get("symbolByteCount") != base.PREPARE_LAYER_SYMBOL_BYTE_COUNT
        or module != capture_module
        or prepare.get("directCallAddress") != start + DIRECT_CALL_OFFSET
        or prepare.get("directReturnAddress") != start + DIRECT_RETURN_OFFSET
        or prepare.get("directCallRawLittleEndianHex")
        != DIRECT_CALL_RAW_LITTLE_ENDIAN_HEX
        or prepare.get("directCallWord") != DIRECT_CALL_WORD
        or prepare.get("directCallDisplacement") != DIRECT_CALL_DISPLACEMENT
        or prepare.get("alternateStoreAddress") != start + ALTERNATE_STORE_OFFSET
        or prepare.get("alternateAfterAddress") != start + ALTERNATE_AFTER_OFFSET
        or prepare.get("alternateStoreRawLittleEndianHex")
        != ALTERNATE_STORE_RAW_LITTLE_ENDIAN_HEX
    ):
        raise ValueError("prepare_layer gate differs")
    window = mapping(
        prepare.get("constructionCodeWindow"), "prepare_layer construction window"
    )
    payload = base.memory_snapshot(
        window,
        "prepare_layer construction window",
        expected_address=start + base.PREPARE_LAYER_CODE_WINDOW_OFFSET,
        expected_byte_count=base.PREPARE_LAYER_CODE_WINDOW_BYTE_COUNT,
    )
    if (
        window.get("symbolOffset") != base.PREPARE_LAYER_CODE_WINDOW_OFFSET
        or hashlib.sha256(payload).hexdigest()
        != base.PREPARE_LAYER_CODE_WINDOW_SHA256
    ):
        raise ValueError("prepare_layer construction code differs")
    direct_index = DIRECT_CALL_OFFSET - base.PREPARE_LAYER_CODE_WINDOW_OFFSET
    alternate_index = ALTERNATE_STORE_OFFSET - base.PREPARE_LAYER_CODE_WINDOW_OFFSET
    if (
        payload[direct_index : direct_index + 4].hex()
        != DIRECT_CALL_RAW_LITTLE_ENDIAN_HEX
        or payload[alternate_index : alternate_index + 4].hex()
        != ALTERNATE_STORE_RAW_LITTLE_ENDIAN_HEX
    ):
        raise ValueError("prepare_layer embedded branch bytes differ")
    helper = mapping(trace.get("unionHelper"), "union helper")
    helper_address = integer(helper.get("address"), "union helper address")
    helper_module = base.module_record(helper.get("module"), "union helper module")
    helper_symbol = mapping(helper.get("symbol"), "union helper symbol")
    if (
        helper_address != start + UNION_HELPER_RELATIVE_TO_PREPARE_LAYER
        or helper.get("relativeToPrepareLayer")
        != UNION_HELPER_RELATIVE_TO_PREPARE_LAYER
        or helper_module != module
        or helper_symbol.get("valid") is not True
        or helper_symbol.get("name") != UNION_HELPER_SYMBOL_NAME
        or helper_symbol.get("startAddress") != helper_address
        or helper_symbol.get("endAddress")
        != helper_address + UNION_HELPER_SYMBOL_BYTE_COUNT
    ):
        raise ValueError("union helper identity differs")
    helper_payload = base.memory_snapshot(
        helper.get("codeWindow"),
        "union helper code",
        expected_address=helper_address,
        expected_byte_count=UNION_HELPER_CODE_WINDOW_BYTE_COUNT,
    )
    if (
        hashlib.sha256(helper_payload).hexdigest()
        != UNION_HELPER_CODE_WINDOW_SHA256
        or hashlib.sha256(
            helper_payload[:UNION_HELPER_SYMBOL_BYTE_COUNT]
        ).hexdigest()
        != UNION_HELPER_SYMBOL_SHA256
    ):
        raise ValueError("union helper code differs")
    for name in (
        "directCallBreakpointID",
        "directReturnBreakpointID",
        "alternateStoreBreakpointID",
        "alternateAfterBreakpointID",
    ):
        if integer(prepare.get(name), name) <= 0:
            raise ValueError("construction breakpoint identity differs")
    return start, module, helper_payload


def _validate_direct_records(
    trace: Mapping[str, Any],
    prepare_start: int,
    prepare_module: Mapping[str, Any],
    selected_source: int,
) -> tuple[int, int, int]:
    records = list(sequence(trace.get("directRecords"), "direct records"))
    if (
        not MINIMUM_DIRECT_RECORD_COUNT <= len(records) <= MAXIMUM_DIRECT_RECORD_COUNT
        or trace.get("finalDirectRecordCount") != len(records)
        or trace.get("finalCompleteDirectRecordCount") != len(records)
        or trace.get("finalPendingDirectRecordCount") != 0
    ):
        raise ValueError("direct record bounds differ")
    selected_count = 0
    selected_changed_count = 0
    for index, value_record in enumerate(records):
        label = f"direct record {index}"
        record = mapping(value_record, label)
        addresses = mapping(record.get("addresses"), f"{label} addresses")
        x19 = integer(addresses.get("x19"), f"{label} x19")
        aggregate_address = integer(
            addresses.get("aggregate"), f"{label} aggregate address"
        )
        child_address = integer(
            addresses.get("recursiveChild"), f"{label} child address"
        )
        source = integer(addresses.get("source"), f"{label} source")
        selected = source == selected_source
        if (
            record.get("recordIndex") != index
            or record.get("complete") is not True
            or record.get("selectedSource") is not selected
            or not isinstance(record.get("sourceKnownAtCall"), bool)
            or integer(record.get("threadID"), f"{label} thread") <= 0
            or record.get("callPC") != prepare_start + DIRECT_CALL_OFFSET
            or record.get("returnPC") != prepare_start + DIRECT_RETURN_OFFSET
            or aggregate_address != x19 + 656
            or child_address != x19 + 1568
        ):
            raise ValueError(f"{label} identity differs")
        base.frame_record(
            record.get("callFrame"),
            f"{label} call frame",
            expected_pc=prepare_start + DIRECT_CALL_OFFSET,
            expected_symbol_start=prepare_start,
            expected_module=prepare_module,
        )
        base.frame_record(
            record.get("returnFrame"),
            f"{label} return frame",
            expected_pc=prepare_start + DIRECT_RETURN_OFFSET,
            expected_symbol_start=prepare_start,
            expected_module=prepare_module,
        )
        _validate_backtrace(
            record.get("callBacktrace"),
            f"{label} call backtrace",
            expected_first_pc=prepare_start + DIRECT_CALL_OFFSET,
            expected_symbol_start=prepare_start,
            expected_module=prepare_module,
        )
        _validate_backtrace(
            record.get("returnBacktrace"),
            f"{label} return backtrace",
            expected_first_pc=prepare_start + DIRECT_RETURN_OFFSET,
            expected_symbol_start=prepare_start,
            expected_module=prepare_module,
        )
        before_registers = base.register_snapshot(
            record.get("registersBefore"), f"{label} registers before"
        )
        after_registers = base.register_snapshot(
            record.get("registersAfter"), f"{label} registers after"
        )
        if (
            before_registers["x0"] != aggregate_address
            or before_registers["x1"] != child_address
            or before_registers["x2"] != 1
            or before_registers["x19"] != x19
            or before_registers["x28"] != source
            or before_registers["pc"] != prepare_start + DIRECT_CALL_OFFSET
            or after_registers["x19"] != x19
            or after_registers["x28"] != source
            or after_registers["pc"] != prepare_start + DIRECT_RETURN_OFFSET
        ):
            raise ValueError(f"{label} register aliases differ")
        aggregate_before = base.memory_snapshot(
            record.get("aggregateBefore"),
            f"{label} aggregate before",
            expected_address=aggregate_address,
            expected_byte_count=LAYER_SHAPES_BYTE_COUNT,
        )
        aggregate_after = base.memory_snapshot(
            record.get("aggregateAfter"),
            f"{label} aggregate after",
            expected_address=aggregate_address,
            expected_byte_count=LAYER_SHAPES_BYTE_COUNT,
        )
        child_before = base.memory_snapshot(
            record.get("recursiveChildBefore"),
            f"{label} child before",
            expected_address=child_address,
            expected_byte_count=LAYER_SHAPES_BYTE_COUNT,
        )
        child_after = base.memory_snapshot(
            record.get("recursiveChildAfter"),
            f"{label} child after",
            expected_address=child_address,
            expected_byte_count=LAYER_SHAPES_BYTE_COUNT,
        )
        role_before = base.memory_snapshot(
            record.get("roleStateBefore"),
            f"{label} role before",
            expected_address=x19,
            expected_byte_count=ROLE_STATE_BYTE_COUNT,
        )
        role_after = base.memory_snapshot(
            record.get("roleStateAfter"),
            f"{label} role after",
            expected_address=x19,
            expected_byte_count=ROLE_STATE_BYTE_COUNT,
        )
        if (
            role_before[656:688] != aggregate_before
            or role_before[1568:1600] != child_before
            or role_after[656:688] != aggregate_after
            or role_after[1568:1600] != child_after
        ):
            raise ValueError(f"{label} role aliases differ")
        changes = {
            "aggregateChanged": aggregate_before != aggregate_after,
            "recursiveChildChanged": child_before != child_after,
            "roleStateChanged": role_before != role_after,
        }
        if any(record.get(name) is not change for name, change in changes.items()):
            raise ValueError(f"{label} change flags differ")
        selected_count += selected
        selected_changed_count += selected and changes["aggregateChanged"]
    if (
        selected_count < MINIMUM_SELECTED_DIRECT_RECORD_COUNT
        or selected_changed_count == 0
        or trace.get("finalSelectedDirectRecordCount") != selected_count
        or trace.get("directCallSiteHitCount") != len(records)
    ):
        raise ValueError("selected direct record coverage differs")
    return len(records), selected_count, selected_changed_count


def _validate_alternate_records(
    trace: Mapping[str, Any],
    prepare_start: int,
    prepare_module: Mapping[str, Any],
    selected_source: int,
) -> tuple[int, int, int]:
    records = list(sequence(trace.get("alternateRecords"), "alternate records"))
    if (
        len(records) > MAXIMUM_ALTERNATE_RECORD_COUNT
        or trace.get("finalAlternateRecordCount") != len(records)
        or trace.get("finalCompleteAlternateRecordCount") != len(records)
        or trace.get("finalPendingAlternateRecordCount") != 0
    ):
        raise ValueError("alternate record bounds differ")
    selected_count = 0
    selected_sources = set()
    for index, value_record in enumerate(records):
        label = f"alternate record {index}"
        record = mapping(value_record, label)
        addresses = mapping(record.get("addresses"), f"{label} addresses")
        x19 = integer(addresses.get("x19"), f"{label} x19")
        aggregate_address = integer(
            addresses.get("aggregate"), f"{label} aggregate address"
        )
        alternate_address = integer(
            addresses.get("alternateSource"), f"{label} alternate source address"
        )
        source = integer(addresses.get("source"), f"{label} source")
        selected = source == selected_source
        source_known = record.get("sourceKnownAtStore")
        if (
            record.get("recordIndex") != index
            or record.get("complete") is not True
            or record.get("selectedSource") is not selected
            or not isinstance(source_known, bool)
            or source_known and not selected
            or integer(record.get("threadID"), f"{label} thread") <= 0
            or record.get("storePC") != prepare_start + ALTERNATE_STORE_OFFSET
            or record.get("afterPC") != prepare_start + ALTERNATE_AFTER_OFFSET
            or aggregate_address != x19 + 656
            or alternate_address != x19 + 1312
        ):
            raise ValueError(f"{label} identity differs")
        base.frame_record(
            record.get("storeFrame"),
            f"{label} store frame",
            expected_pc=prepare_start + ALTERNATE_STORE_OFFSET,
            expected_symbol_start=prepare_start,
            expected_module=prepare_module,
        )
        base.frame_record(
            record.get("afterFrame"),
            f"{label} after frame",
            expected_pc=prepare_start + ALTERNATE_AFTER_OFFSET,
            expected_symbol_start=prepare_start,
            expected_module=prepare_module,
        )
        _validate_backtrace(
            record.get("storeBacktrace"),
            f"{label} store backtrace",
            expected_first_pc=prepare_start + ALTERNATE_STORE_OFFSET,
            expected_symbol_start=prepare_start,
            expected_module=prepare_module,
        )
        _validate_backtrace(
            record.get("afterBacktrace"),
            f"{label} after backtrace",
            expected_first_pc=prepare_start + ALTERNATE_AFTER_OFFSET,
            expected_symbol_start=prepare_start,
            expected_module=prepare_module,
        )
        before_registers = base.register_snapshot(
            record.get("registersBefore"), f"{label} registers before"
        )
        after_registers = base.register_snapshot(
            record.get("registersAfter"), f"{label} registers after"
        )
        if (
            before_registers["x19"] != x19
            or before_registers["x28"] != source
            or before_registers["pc"] != prepare_start + ALTERNATE_STORE_OFFSET
            or after_registers["x19"] != x19
            or after_registers["x28"] != source
            or after_registers["pc"] != prepare_start + ALTERNATE_AFTER_OFFSET
        ):
            raise ValueError(f"{label} register aliases differ")
        simd_payload = _simd_source_registers(
            record.get("simdSourceRegisters"), f"{label} SIMD source"
        )
        aggregate_before = base.memory_snapshot(
            record.get("aggregateBefore"),
            f"{label} aggregate before",
            expected_address=aggregate_address,
            expected_byte_count=LAYER_SHAPES_BYTE_COUNT,
        )
        aggregate_after = base.memory_snapshot(
            record.get("aggregateAfter"),
            f"{label} aggregate after",
            expected_address=aggregate_address,
            expected_byte_count=LAYER_SHAPES_BYTE_COUNT,
        )
        alternate_before = base.memory_snapshot(
            record.get("alternateSourceBefore"),
            f"{label} alternate source before",
            expected_address=alternate_address,
            expected_byte_count=LAYER_SHAPES_BYTE_COUNT,
        )
        alternate_after = base.memory_snapshot(
            record.get("alternateSourceAfter"),
            f"{label} alternate source after",
            expected_address=alternate_address,
            expected_byte_count=LAYER_SHAPES_BYTE_COUNT,
        )
        role_before = base.memory_snapshot(
            record.get("roleStateBefore"),
            f"{label} role before",
            expected_address=x19,
            expected_byte_count=ROLE_STATE_BYTE_COUNT,
        )
        role_after = base.memory_snapshot(
            record.get("roleStateAfter"),
            f"{label} role after",
            expected_address=x19,
            expected_byte_count=ROLE_STATE_BYTE_COUNT,
        )
        if (
            role_before[656:688] != aggregate_before
            or role_before[1312:1344] != alternate_before
            or role_after[656:688] != aggregate_after
            or role_after[1312:1344] != alternate_after
            or simd_payload != alternate_before
            or aggregate_after != alternate_before
        ):
            raise ValueError(f"{label} exact store replay differs")
        changes = {
            "aggregateChanged": aggregate_before != aggregate_after,
            "alternateSourceChanged": alternate_before != alternate_after,
            "roleStateChanged": role_before != role_after,
        }
        if any(record.get(name) is not change for name, change in changes.items()):
            raise ValueError(f"{label} change flags differ")
        selected_count += selected
        if selected:
            selected_sources.add(hashlib.sha256(alternate_before).digest())
    rejected_store = integer(
        trace.get("rejectedAlternateStoreCount"), "rejected alternate store count"
    )
    rejected_after = integer(
        trace.get("rejectedAlternateAfterCount"), "rejected alternate after count"
    )
    alternate_hits = integer(
        trace.get("alternateStoreHitCount"), "alternate store hit count"
    )
    if (
        selected_count < MINIMUM_SELECTED_ALTERNATE_RECORD_COUNT
        or len(selected_sources) < MINIMUM_DISTINCT_SELECTED_ALTERNATE_SOURCE_COUNT
        or trace.get("finalSelectedAlternateRecordCount") != selected_count
        or alternate_hits != len(records) + rejected_store
        or rejected_after != rejected_store
        or alternate_hits > MAXIMUM_ALTERNATE_STORE_HIT_COUNT
    ):
        raise ValueError("selected alternate record coverage differs")
    return len(records), selected_count, len(selected_sources)


def validate(trace_path: Path) -> dict[str, Any]:
    trace_bytes = trace_path.read_bytes()
    trace = mapping(json.loads(trace_bytes), "LayerShapes construction trace")
    if (
        trace.get("layerShapesConstructionTraceSchemaVersion")
        != EXPECTED_TRACE_SCHEMA_VERSION
        or trace.get("classification") != EXPECTED_CLASSIFICATION
        or trace.get("status") != "finalized"
        or trace.get("statusBeforeFinalization")
        not in {
            "source-selected-construction-active",
            "construction-breakpoints-armed",
        }
        or mapping(trace.get("configuration"), "trace configuration")
        != EXPECTED_CONFIGURATION
        or list(sequence(trace.get("failures"), "trace failures"))
        or trace.get("finalFailureCount") != 0
    ):
        raise ValueError("trace envelope differs")
    prepare_start, prepare_module, helper_payload = _validate_static_gates(trace)
    chain, selected_source = _selected_object_chain(trace)
    late_count = integer(trace.get("lateCandidateCount"), "late candidate count")
    if (
        late_count != chain.get("selectedLateCandidateIndex")
        or not 1 <= late_count <= MAXIMUM_LATE_CANDIDATE_COUNT
        or len(
            sequence(trace.get("lateCandidateDiagnostics"), "late diagnostics")
        )
        > MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT
    ):
        raise ValueError("late candidate accounting differs")
    direct_count, selected_direct_count, changed_direct_count = (
        _validate_direct_records(
            trace, prepare_start, prepare_module, selected_source
        )
    )
    alternate_count, selected_alternate_count, distinct_alternate_count = (
        _validate_alternate_records(
            trace, prepare_start, prepare_module, selected_source
        )
    )
    direct_hits = integer(trace.get("directCallSiteHitCount"), "direct hit count")
    if direct_hits > MAXIMUM_DIRECT_CALL_SITE_HIT_COUNT:
        raise ValueError("direct callback accounting differs")
    return {
        "layerShapesConstructionTraceValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "classification": EXPECTED_VALIDATION_CLASSIFICATION,
        "inputTrace": trace_path.name,
        "inputTraceSHA256": hashlib.sha256(trace_bytes).hexdigest(),
        "conclusion": "success",
        "prospectiveGatePassed": True,
        "aggregate": {
            "directRecordCount": direct_count,
            "selectedDirectRecordCount": selected_direct_count,
            "changedSelectedDirectRecordCount": changed_direct_count,
            "alternateRecordCount": alternate_count,
            "selectedAlternateRecordCount": selected_alternate_count,
            "distinctSelectedAlternateSourceCount": distinct_alternate_count,
            "unionHelperCodeByteCount": len(helper_payload),
            "unionHelperCodeSHA256": hashlib.sha256(helper_payload).hexdigest(),
        },
        "sealedConclusion": {
            "selectedSourceDirectPairCaptured": True,
            "selectedSourceDynamicAlternatePairsCaptured": True,
            "directUnionSemanticsOpenedByThisGate": False,
            "alternateProducerSemanticsOpened": False,
            "completePublicCropRuleRecovered": False,
            "unseenGeometryTransferPassed": False,
            "productionShaderAuthorized": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = validate(arguments.trace)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
