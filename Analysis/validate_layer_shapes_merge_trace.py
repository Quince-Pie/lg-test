#!/usr/bin/env python3
"""Validate the preregistered LayerShapes merge trace without opening semantics."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


EXPECTED_TRACE_SCHEMA_VERSION = 1
VALIDATION_SCHEMA_VERSION = 1
EXPECTED_CLASSIFICATION = (
    "preregistered-bounded-selected-source-prepare-layer-shapes-merge-trace; "
    "helper-semantics-public-crop-law-unseen-transfer-and-product-parity-remain-"
    "sealed"
)
EXPECTED_VALIDATION_CLASSIFICATION = (
    "prospective-integrity-gate-for-selected-source-layer-shapes-merge-trace; "
    "helper-and-public-crop-semantics-remain-sealed"
)
CAPTURE_BACKDROP_SYMBOL = "_ZN2CA3OGL16capture_backdropERNS0_8RendererEPKNS0_5LayerE"
CAPTURE_BACKDROP_CODE_SHA256 = (
    "14f25960556bec9e88ba8ade176ee7f1d39b84726226ade3eb1b0f1be00b70d2"
)
PREPARE_LAYER_FUNCTION = (
    "CA::Render::Updater::prepare_layer(CA::Render::Updater::GlobalState&, "
    "CA::Render::Updater::LocalState&, CA::Render::LayerNode*, "
    "CA::Render::Updater::LayerShapes&, unsigned long long&)"
)
PREPARE_LAYER_SYMBOL_BYTE_COUNT = 40128
PREPARE_LAYER_CODE_WINDOW_OFFSET = 12764
PREPARE_LAYER_CODE_WINDOW_BYTE_COUNT = 0x1000
PREPARE_LAYER_CODE_WINDOW_SHA256 = (
    "91fbe43da3533d7cd4578195b77c5a1aa0844105493c70635687e76adb7af768"
)
MERGE_CALL_OFFSET = 0x32C0
MERGE_RETURN_OFFSET = 0x32C4
MERGE_CALL_RAW_LITTLE_ENDIAN_HEX = "a8f0ff97"
MERGE_CALL_WORD = 0x97FFF0A8
MERGE_CALL_DISPLACEMENT = -0x3D60
MERGE_TARGET_RELATIVE_TO_PREPARE_LAYER = -0xAA0
MERGE_TARGET_CODE_BYTE_COUNT = 0x1000
LAYER_SHAPES_BYTE_COUNT = 0x20
ROLE_STATE_BYTE_COUNT = 0x800
SOURCE_OBJECT_BYTE_COUNT = 0x180
MAXIMUM_LATE_CANDIDATE_COUNT = 512
MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT = 16
MAXIMUM_MERGE_CALL_SITE_HIT_COUNT = 4096
MAXIMUM_COMPLETE_RECORD_COUNT = 64
MAXIMUM_BACKTRACE_FRAME_COUNT = 24
MINIMUM_COMPLETE_RECORD_COUNT = 16
MINIMUM_DISTINCT_INPUT_PAIR_COUNT = 8
REGISTER_NAMES = ("x0", "x1", "x2", "x19", "x28", "x30", "sp", "pc")
QUARTZ_CORE_PATH_FRAGMENT = "/QuartzCore.framework/"
EXPECTED_CONFIGURATION = {
    "captureBackdropSymbol": CAPTURE_BACKDROP_SYMBOL,
    "captureBackdropCodeByteCount": 0x4000,
    "captureBackdropCodeSHA256": CAPTURE_BACKDROP_CODE_SHA256,
    "captureBackdropLateOffset": 0x2B58,
    "prepareLayerFunction": PREPARE_LAYER_FUNCTION,
    "prepareLayerSymbolByteCount": PREPARE_LAYER_SYMBOL_BYTE_COUNT,
    "prepareLayerCodeWindowOffset": PREPARE_LAYER_CODE_WINDOW_OFFSET,
    "prepareLayerCodeWindowByteCount": PREPARE_LAYER_CODE_WINDOW_BYTE_COUNT,
    "prepareLayerCodeWindowSHA256": PREPARE_LAYER_CODE_WINDOW_SHA256,
    "mergeCallOffset": MERGE_CALL_OFFSET,
    "mergeReturnOffset": MERGE_RETURN_OFFSET,
    "mergeCallRawLittleEndianHex": MERGE_CALL_RAW_LITTLE_ENDIAN_HEX,
    "mergeCallWord": MERGE_CALL_WORD,
    "mergeCallDisplacement": MERGE_CALL_DISPLACEMENT,
    "mergeTargetRelativeToPrepareLayer": MERGE_TARGET_RELATIVE_TO_PREPARE_LAYER,
    "mergeTargetCodeByteCount": MERGE_TARGET_CODE_BYTE_COUNT,
    "layerShapesByteCount": LAYER_SHAPES_BYTE_COUNT,
    "roleStateByteCount": ROLE_STATE_BYTE_COUNT,
    "sourceObjectByteCount": SOURCE_OBJECT_BYTE_COUNT,
    "maximumLateCandidateCount": MAXIMUM_LATE_CANDIDATE_COUNT,
    "maximumLateCandidateDiagnosticCount": MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT,
    "maximumMergeCallSiteHitCount": MAXIMUM_MERGE_CALL_SITE_HIT_COUNT,
    "maximumCompleteRecordCount": MAXIMUM_COMPLETE_RECORD_COUNT,
    "maximumBacktraceFrameCount": MAXIMUM_BACKTRACE_FRAME_COUNT,
    "registerNames": list(REGISTER_NAMES),
    "selectionRule": (
        "first exact capture_backdrop x19/x20/x24 pointer chain whose owner "
        "rectangle equals layer-state while source differs"
    ),
    "recordRule": (
        "exact prepare_layer+0x32c0 calls whose live x28 is the selected source "
        "and whose x0/x1/w2 aliases are x19+656/x19+1568/1"
    ),
}


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} differs")
    return value


def sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{label} differs")
    return value


def integer(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} differs")
    return value


def hexadecimal_payload(value: Any, byte_count: int, label: str) -> bytes:
    if not isinstance(value, str):
        raise ValueError(f"{label} differs")
    try:
        payload = bytes.fromhex(value)
    except ValueError as error:
        raise ValueError(f"{label} differs") from error
    if len(payload) != byte_count:
        raise ValueError(f"{label} differs")
    return payload


def memory_snapshot(
    value: Any,
    label: str,
    *,
    expected_address: int,
    expected_byte_count: int,
) -> bytes:
    snapshot = mapping(value, label)
    if (
        integer(snapshot.get("address"), f"{label} address") != expected_address
        or integer(snapshot.get("byteCount"), f"{label} byte count")
        != expected_byte_count
    ):
        raise ValueError(f"{label} bounds differ")
    payload = hexadecimal_payload(snapshot.get("hex"), expected_byte_count, label)
    if snapshot.get("sha256") != hashlib.sha256(payload).hexdigest():
        raise ValueError(f"{label} identity differs")
    return payload


def module_record(value: Any, label: str) -> Mapping[str, Any]:
    module = mapping(value, label)
    path = module.get("path")
    if (
        module.get("valid") is not True
        or not isinstance(path, str)
        or QUARTZ_CORE_PATH_FRAGMENT not in path
    ):
        raise ValueError(f"{label} identity differs")
    integer(module.get("loadAddress"), f"{label} load address")
    return module


def frame_record(
    value: Any,
    label: str,
    *,
    expected_pc: int,
    expected_symbol_start: int,
    expected_module: Mapping[str, Any],
) -> Mapping[str, Any]:
    frame = mapping(value, label)
    if (
        integer(frame.get("pc"), f"{label} PC") != expected_pc
        or frame.get("function") != PREPARE_LAYER_FUNCTION
        or integer(frame.get("symbolStart"), f"{label} symbol start")
        != expected_symbol_start
        or integer(frame.get("symbolEnd"), f"{label} symbol end")
        != expected_symbol_start + PREPARE_LAYER_SYMBOL_BYTE_COUNT
        or integer(frame.get("symbolOffset"), f"{label} symbol offset")
        != expected_pc - expected_symbol_start
        or mapping(frame.get("module"), f"{label} module") != expected_module
    ):
        raise ValueError(f"{label} identity differs")
    integer(frame.get("frameIndex"), f"{label} frame index")
    return frame


def register_snapshot(value: Any, label: str) -> dict[str, int]:
    records = list(sequence(value, label))
    if len(records) != len(REGISTER_NAMES):
        raise ValueError(f"{label} inventory differs")
    result = {}
    for expected_name, value_record in zip(REGISTER_NAMES, records, strict=True):
        record = mapping(value_record, f"{label} {expected_name}")
        if (
            record.get("name") != expected_name
            or integer(record.get("byteCount"), f"{label} {expected_name} size")
            != 8
            or record.get("valueString") is not None
            and not isinstance(record.get("valueString"), str)
        ):
            raise ValueError(f"{label} {expected_name} identity differs")
        payload = hexadecimal_payload(
            record.get("hex"), 8, f"{label} {expected_name}"
        )
        unsigned = integer(
            record.get("unsignedValue"), f"{label} {expected_name} unsigned"
        )
        if unsigned != int.from_bytes(payload, "little"):
            raise ValueError(f"{label} {expected_name} payload differs")
        result[expected_name] = unsigned
    return result


def backtrace(
    value: Any,
    label: str,
    *,
    expected_first_pc: int,
    expected_symbol_start: int,
    expected_module: Mapping[str, Any],
) -> None:
    frames = list(sequence(value, label))
    if not frames or len(frames) > MAXIMUM_BACKTRACE_FRAME_COUNT:
        raise ValueError(f"{label} bounds differ")
    frame_record(
        frames[0],
        f"{label} first frame",
        expected_pc=expected_first_pc,
        expected_symbol_start=expected_symbol_start,
        expected_module=expected_module,
    )
    for index, value_frame in enumerate(frames[1:], start=1):
        frame = mapping(value_frame, f"{label} frame {index}")
        integer(frame.get("pc"), f"{label} frame {index} PC")
        module = mapping(frame.get("module"), f"{label} frame {index} module")
        if module.get("valid") not in {True, False}:
            raise ValueError(f"{label} frame {index} module differs")


def validate(trace_path: Path) -> dict[str, Any]:
    trace_bytes = trace_path.read_bytes()
    trace_sha256 = hashlib.sha256(trace_bytes).hexdigest()
    trace = mapping(json.loads(trace_bytes), "LayerShapes merge trace")
    configuration = mapping(trace.get("configuration"), "trace configuration")
    failures = list(sequence(trace.get("failures"), "trace failures"))
    if (
        trace.get("layerShapesMergeTraceSchemaVersion")
        != EXPECTED_TRACE_SCHEMA_VERSION
        or trace.get("classification") != EXPECTED_CLASSIFICATION
        or trace.get("status") != "finalized"
        or trace.get("statusBeforeFinalization")
        not in {"merge-breakpoints-armed", "record-limit-reached"}
        or configuration != EXPECTED_CONFIGURATION
        or failures
        or trace.get("finalFailureCount") != 0
    ):
        raise ValueError("trace envelope differs")

    capture = mapping(trace.get("captureBackdrop"), "capture_backdrop gate")
    capture_module = module_record(capture.get("module"), "capture_backdrop module")
    if (
        integer(capture.get("symbolAddress"), "capture_backdrop address") <= 0
        or capture.get("codeByteCount") != 0x4000
        or capture.get("codeSHA256") != CAPTURE_BACKDROP_CODE_SHA256
    ):
        raise ValueError("capture_backdrop gate differs")

    prepare = mapping(trace.get("prepareLayer"), "prepare_layer gate")
    prepare_start = integer(prepare.get("symbolStart"), "prepare_layer start")
    prepare_end = integer(prepare.get("symbolEnd"), "prepare_layer end")
    prepare_module = module_record(prepare.get("module"), "prepare_layer module")
    if (
        prepare.get("function") != PREPARE_LAYER_FUNCTION
        or prepare_end - prepare_start != PREPARE_LAYER_SYMBOL_BYTE_COUNT
        or prepare.get("symbolByteCount") != PREPARE_LAYER_SYMBOL_BYTE_COUNT
        or prepare_module != capture_module
        or prepare.get("callAddress") != prepare_start + MERGE_CALL_OFFSET
        or prepare.get("returnAddress") != prepare_start + MERGE_RETURN_OFFSET
        or prepare.get("callInstructionRawLittleEndianHex")
        != MERGE_CALL_RAW_LITTLE_ENDIAN_HEX
        or prepare.get("callInstructionWord") != MERGE_CALL_WORD
        or prepare.get("callDisplacement") != MERGE_CALL_DISPLACEMENT
        or prepare.get("decodedHelperAddress")
        != prepare_start + MERGE_TARGET_RELATIVE_TO_PREPARE_LAYER
    ):
        raise ValueError("prepare_layer identity differs")
    prepare_window = mapping(
        prepare.get("constructionCodeWindow"), "prepare_layer construction window"
    )
    prepare_payload = memory_snapshot(
        prepare_window,
        "prepare_layer construction window",
        expected_address=prepare_start + PREPARE_LAYER_CODE_WINDOW_OFFSET,
        expected_byte_count=PREPARE_LAYER_CODE_WINDOW_BYTE_COUNT,
    )
    if (
        prepare_window.get("symbolOffset") != PREPARE_LAYER_CODE_WINDOW_OFFSET
        or hashlib.sha256(prepare_payload).hexdigest()
        != PREPARE_LAYER_CODE_WINDOW_SHA256
    ):
        raise ValueError("prepare_layer construction code differs")
    call_index = MERGE_CALL_OFFSET - PREPARE_LAYER_CODE_WINDOW_OFFSET
    if (
        prepare_payload[call_index : call_index + 4].hex()
        != MERGE_CALL_RAW_LITTLE_ENDIAN_HEX
    ):
        raise ValueError("prepare_layer embedded merge BL differs")
    word = struct.unpack("<I", prepare_payload[call_index : call_index + 4])[0]
    immediate = word & 0x03FFFFFF
    if word & 0xFC000000 != 0x94000000:
        raise ValueError("prepare_layer embedded instruction is not BL")
    if immediate & 0x02000000:
        immediate -= 1 << 26
    if immediate << 2 != MERGE_CALL_DISPLACEMENT:
        raise ValueError("prepare_layer embedded BL displacement differs")

    helper = mapping(trace.get("mergeHelper"), "merge helper")
    helper_address = integer(helper.get("address"), "merge helper address")
    helper_module = module_record(helper.get("module"), "merge helper module")
    if (
        helper_address != prepare_start + MERGE_TARGET_RELATIVE_TO_PREPARE_LAYER
        or helper.get("relativeToPrepareLayer")
        != MERGE_TARGET_RELATIVE_TO_PREPARE_LAYER
        or helper_module != prepare_module
        or integer(helper.get("callBreakpointID"), "merge call breakpoint") <= 0
        or integer(helper.get("returnBreakpointID"), "merge return breakpoint") <= 0
    ):
        raise ValueError("merge helper identity differs")
    helper_symbol = mapping(helper.get("symbol"), "merge helper symbol")
    if helper_symbol.get("valid") not in {True, False}:
        raise ValueError("merge helper symbol validity differs")
    if helper_symbol.get("valid") is True:
        if helper_symbol.get("name") is not None and not isinstance(
            helper_symbol.get("name"), str
        ):
            raise ValueError("merge helper symbol name differs")
        integer(helper_symbol.get("startAddress"), "merge helper symbol start")
        integer(helper_symbol.get("endAddress"), "merge helper symbol end")
    helper_window = mapping(helper.get("codeWindow"), "merge helper code window")
    helper_payload = memory_snapshot(
        helper_window,
        "merge helper code window",
        expected_address=helper_address,
        expected_byte_count=MERGE_TARGET_CODE_BYTE_COUNT,
    )
    helper_sha256 = hashlib.sha256(helper_payload).hexdigest()

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
            hexadecimal_payload(
                chain.get("sourceSelectedRectI32Hex"),
                16,
                "selected source rectangle",
            ),
        )
    )
    layer_state_rectangle = list(
        struct.unpack(
            "<4i",
            hexadecimal_payload(
                chain.get("layerStateSelectedRectI32Hex"),
                16,
                "selected layer-state rectangle",
            ),
        )
    )
    owner_rectangle = list(
        struct.unpack(
            "<4d",
            hexadecimal_payload(
                chain.get("ownerSelectedRectF64Hex"),
                32,
                "selected owner rectangle",
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
        or owner_rectangle != [float(value) for value in layer_state_rectangle]
        or source_rectangle == layer_state_rectangle
    ):
        raise ValueError("selected object state differs")

    records = list(sequence(trace.get("records"), "merge records"))
    final_record_count = integer(trace.get("finalRecordCount"), "record count")
    complete_record_count = integer(
        trace.get("finalCompleteRecordCount"), "complete record count"
    )
    pending_record_count = integer(
        trace.get("finalPendingRecordCount"), "pending record count"
    )
    if (
        not MINIMUM_COMPLETE_RECORD_COUNT
        <= len(records)
        <= MAXIMUM_COMPLETE_RECORD_COUNT
        or final_record_count != len(records)
        or complete_record_count != len(records)
        or pending_record_count != 0
    ):
        raise ValueError("merge record bounds differ")

    input_pairs = set()
    changed_aggregate_count = 0
    changed_child_count = 0
    changed_role_count = 0
    changed_source_count = 0
    call_address = prepare_start + MERGE_CALL_OFFSET
    return_address = prepare_start + MERGE_RETURN_OFFSET
    source = integer(addresses.get("source"), "selected source")
    for index, value_record in enumerate(records):
        label = f"merge record {index}"
        record = mapping(value_record, label)
        if (
            record.get("recordIndex") != index
            or record.get("complete") is not True
            or integer(record.get("threadID"), f"{label} thread") <= 0
            or record.get("selectedSource") != source
            or record.get("callPC") != call_address
            or record.get("returnPC") != return_address
        ):
            raise ValueError(f"{label} identity differs")
        frame_record(
            record.get("callFrame"),
            f"{label} call frame",
            expected_pc=call_address,
            expected_symbol_start=prepare_start,
            expected_module=prepare_module,
        )
        frame_record(
            record.get("returnFrame"),
            f"{label} return frame",
            expected_pc=return_address,
            expected_symbol_start=prepare_start,
            expected_module=prepare_module,
        )
        backtrace(
            record.get("callBacktrace"),
            f"{label} call backtrace",
            expected_first_pc=call_address,
            expected_symbol_start=prepare_start,
            expected_module=prepare_module,
        )
        backtrace(
            record.get("returnBacktrace"),
            f"{label} return backtrace",
            expected_first_pc=return_address,
            expected_symbol_start=prepare_start,
            expected_module=prepare_module,
        )
        before_registers = register_snapshot(
            record.get("registersBefore"), f"{label} registers before"
        )
        after_registers = register_snapshot(
            record.get("registersAfter"), f"{label} registers after"
        )
        record_addresses = mapping(record.get("addresses"), f"{label} addresses")
        x19 = integer(record_addresses.get("x19"), f"{label} x19")
        aggregate_address = integer(
            record_addresses.get("aggregate"), f"{label} aggregate address"
        )
        child_address = integer(
            record_addresses.get("recursiveChild"), f"{label} child address"
        )
        if (
            record_addresses.get("source") != source
            or aggregate_address != x19 + 656
            or child_address != x19 + 1568
            or before_registers["x0"] != aggregate_address
            or before_registers["x1"] != child_address
            or before_registers["x2"] != 1
            or before_registers["x19"] != x19
            or before_registers["x28"] != source
            or before_registers["pc"] != call_address
            or after_registers["x19"] != x19
            or after_registers["x28"] != source
            or after_registers["pc"] != return_address
        ):
            raise ValueError(f"{label} register aliases differ")
        aggregate_before = memory_snapshot(
            record.get("aggregateBefore"),
            f"{label} aggregate before",
            expected_address=aggregate_address,
            expected_byte_count=LAYER_SHAPES_BYTE_COUNT,
        )
        aggregate_after = memory_snapshot(
            record.get("aggregateAfter"),
            f"{label} aggregate after",
            expected_address=aggregate_address,
            expected_byte_count=LAYER_SHAPES_BYTE_COUNT,
        )
        child_before = memory_snapshot(
            record.get("recursiveChildBefore"),
            f"{label} child before",
            expected_address=child_address,
            expected_byte_count=LAYER_SHAPES_BYTE_COUNT,
        )
        child_after = memory_snapshot(
            record.get("recursiveChildAfter"),
            f"{label} child after",
            expected_address=child_address,
            expected_byte_count=LAYER_SHAPES_BYTE_COUNT,
        )
        role_before = memory_snapshot(
            record.get("roleStateBefore"),
            f"{label} role state before",
            expected_address=x19,
            expected_byte_count=ROLE_STATE_BYTE_COUNT,
        )
        role_after = memory_snapshot(
            record.get("roleStateAfter"),
            f"{label} role state after",
            expected_address=x19,
            expected_byte_count=ROLE_STATE_BYTE_COUNT,
        )
        source_before = memory_snapshot(
            record.get("sourceObjectBefore"),
            f"{label} source before",
            expected_address=source,
            expected_byte_count=SOURCE_OBJECT_BYTE_COUNT,
        )
        source_after = memory_snapshot(
            record.get("sourceObjectAfter"),
            f"{label} source after",
            expected_address=source,
            expected_byte_count=SOURCE_OBJECT_BYTE_COUNT,
        )
        if (
            role_before[656:688] != aggregate_before
            or role_before[1568:1600] != child_before
            or role_after[656:688] != aggregate_after
            or role_after[1568:1600] != child_after
        ):
            raise ValueError(f"{label} role-state aliases differ")
        changes = {
            "aggregateChanged": aggregate_before != aggregate_after,
            "recursiveChildChanged": child_before != child_after,
            "roleStateChanged": role_before != role_after,
            "sourceObjectChanged": source_before != source_after,
        }
        if any(record.get(name) is not changed for name, changed in changes.items()):
            raise ValueError(f"{label} change flags differ")
        changed_aggregate_count += changes["aggregateChanged"]
        changed_child_count += changes["recursiveChildChanged"]
        changed_role_count += changes["roleStateChanged"]
        changed_source_count += changes["sourceObjectChanged"]
        input_pairs.add(
            (
                hashlib.sha256(aggregate_before).digest(),
                hashlib.sha256(child_before).digest(),
            )
        )

    if (
        len(input_pairs) < MINIMUM_DISTINCT_INPUT_PAIR_COUNT
        or changed_aggregate_count == 0
    ):
        raise ValueError("merge input diversity differs")

    call_site_hits = integer(
        trace.get("mergeCallSiteHitCount"), "merge call-site hit count"
    )
    selected_calls = integer(
        trace.get("selectedSourceCallCount"), "selected-source call count"
    )
    rejected_calls = integer(
        trace.get("rejectedSourceCallCount"), "rejected-source call count"
    )
    rejected_returns = integer(
        trace.get("rejectedSourceReturnCount"), "rejected-source return count"
    )
    if (
        call_site_hits != selected_calls + rejected_calls
        or selected_calls != len(records)
        or rejected_returns != rejected_calls
        or call_site_hits > MAXIMUM_MERGE_CALL_SITE_HIT_COUNT
        or trace.get("lateCandidateCount")
        != chain.get("selectedLateCandidateIndex")
        or not 1 <= trace.get("lateCandidateCount") <= MAXIMUM_LATE_CANDIDATE_COUNT
        or len(
            sequence(trace.get("lateCandidateDiagnostics"), "late diagnostics")
        )
        > MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT
    ):
        raise ValueError("merge callback accounting differs")

    return {
        "layerShapesMergeTraceValidationSchemaVersion": VALIDATION_SCHEMA_VERSION,
        "classification": EXPECTED_VALIDATION_CLASSIFICATION,
        "inputTrace": trace_path.name,
        "inputTraceSHA256": trace_sha256,
        "conclusion": "success",
        "prospectiveGatePassed": True,
        "aggregate": {
            "completeRecordCount": len(records),
            "distinctInputPairCount": len(input_pairs),
            "changedAggregateRecordCount": changed_aggregate_count,
            "changedRecursiveChildRecordCount": changed_child_count,
            "changedRoleStateRecordCount": changed_role_count,
            "changedSourceObjectRecordCount": changed_source_count,
            "mergeCallSiteHitCount": call_site_hits,
            "selectedSourceCallCount": selected_calls,
            "rejectedSourceCallCount": rejected_calls,
            "helperCodeByteCount": len(helper_payload),
            "helperCodeSHA256": helper_sha256,
        },
        "sealedConclusion": {
            "selectedSourceCallPairsCaptured": True,
            "helperTargetCodeCaptured": True,
            "helperSemanticsOpened": False,
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
