#!/usr/bin/env python3
"""Replay the opened crop-transfer matrix with exact binary64 comparisons.

This analysis deliberately stops at the strongest rule supported by run
31055266553.  It does not repair mismatches with a tolerance or a fitted
exception.  The remaining component words are emitted verbatim so the next
prospective capture can target their missing operand.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


ANALYSIS_SCHEMA_VERSION = 1
TRACE_FILE_NAME = "prepare-layer-crop-transfer-trace.json"
VALIDATION_FILE_NAME = "prepare-layer-crop-transfer-validation.json"
TIMELINE_FILE_NAME = "transition-timeline.json"
ROLE_STATE_BYTE_COUNT = 0x800
ROLE_AGGREGATE_OFFSET = 0x290
ROLE_RECURSIVE_CHILD_OFFSET = 0x620
EXPECTED_LABELS = (
    "crop-1536-clipped",
    "crop-256-center",
    "crop-512-offset",
    "crop-640-center",
    "crop-640-fractional",
    "crop-640-half-even",
    "crop-640-half-signed",
    "crop-640-integer",
)
LOWER_BOUND = -536_870_911.0
UPPER_BOUND = 536_870_912.0

type RectF64 = tuple[float, float, float, float]
type RectI32 = tuple[int, int, int, int]


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} is not an object")
    return value


def sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        raise ValueError(f"{label} is not an array")
    return value


def finite_rect(value: Any, label: str) -> RectF64:
    raw = sequence(value, label)
    if len(raw) != 4:
        raise ValueError(f"{label} component count differs")
    result = tuple(float(component) for component in raw)
    if not all(math.isfinite(component) for component in result):
        raise ValueError(f"{label} is not finite")
    return result  # type: ignore[return-value]


def load_json(path: Path, label: str) -> Mapping[str, Any]:
    try:
        return mapping(json.loads(path.read_text(encoding="utf-8")), label)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is unreadable: {error}") from error


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def snapshot_bytes(value: Any, byte_count: int, label: str) -> bytes:
    record = mapping(value, label)
    if record.get("byteCount") != byte_count:
        raise ValueError(f"{label} byte count differs")
    encoded = record.get("hex")
    if not isinstance(encoded, str):
        raise ValueError(f"{label} is not hexadecimal")
    try:
        result = bytes.fromhex(encoded)
    except ValueError as error:
        raise ValueError(f"{label} is not hexadecimal") from error
    if len(result) != byte_count:
        raise ValueError(f"{label} payload length differs")
    if record.get("sha256") != hashlib.sha256(result).hexdigest():
        raise ValueError(f"{label} SHA-256 differs")
    return result


def component_record(value: float) -> dict[str, Any]:
    return {
        "value": value,
        "valueHex": value.hex(),
        "littleEndianHex": struct.pack("<d", value).hex(),
    }


def same_f64(left: float, right: float) -> bool:
    return struct.pack("<d", left) == struct.pack("<d", right)


def integer_crop(rectangle: RectF64) -> RectI32:
    """Replay the opened finite enclosure and fractional border branch."""
    origin_x = max(rectangle[0], LOWER_BOUND)
    origin_y = max(rectangle[1], LOWER_BOUND)
    width = min(rectangle[2], UPPER_BOUND - origin_x)
    height = min(rectangle[3], UPPER_BOUND - origin_y)
    clamped = (origin_x, origin_y, width, height)
    lower_x = math.floor(origin_x)
    lower_y = math.floor(origin_y)
    enclosed = (
        lower_x,
        lower_y,
        math.ceil(origin_x + width) - lower_x,
        math.ceil(origin_y + height) - lower_y,
    )
    if any(float(integer) != value for integer, value in zip(enclosed, clamped)):
        return (
            enclosed[0] - 1,
            enclosed[1] - 1,
            enclosed[2] + 2,
            enclosed[3] + 2,
        )
    return enclosed


def intersect_i32(left: RectI32, right: RectI32) -> RectI32:
    """Replay the opened signed integer-rectangle intersection order."""
    left_far_x = left[0] + left[2]
    left_far_y = left[1] + left[3]
    right_far_x = right[0] + right[2]
    right_far_y = right[1] + right[3]
    origin_x = max(left[0], right[0])
    origin_y = max(left[1], right[1])
    far_x = min(left_far_x, right_far_x)
    far_y = min(left_far_y, right_far_y)
    return (
        origin_x,
        origin_y,
        max(0, far_x - origin_x),
        max(0, far_y - origin_y),
    )


def union_bounds_f64(left: RectF64, right: RectF64) -> RectF64:
    """Replay the opened ``LayerShapes::union_bounds`` floating core."""
    left_far_x = left[0] + left[2]
    left_far_y = left[1] + left[3]
    right_far_x = right[0] + right[2]
    right_far_y = right[1] + right[3]
    origin_x = min(left[0], right[0])
    origin_y = min(left[1], right[1])
    far_x = max(left_far_x, right_far_x)
    far_y = max(left_far_y, right_far_y)
    return (origin_x, origin_y, far_x - origin_x, far_y - origin_y)


def transform_child(
    carrier_position: Sequence[Any], child: RectF64, canvas_height: float
) -> RectF64:
    if len(carrier_position) != 2:
        raise ValueError("carrier position component count differs")
    position_x = float(carrier_position[0])
    position_y = float(carrier_position[1])
    # Keep the observed operation grouping explicit.  It matters at the final
    # bit for translated signed zero and large fractional coordinates.
    return (
        position_x + child[0],
        (canvas_height - position_y) - (child[1] + child[3]),
        child[2],
        child[3],
    )


def analyze_record(
    label: str,
    record_index: int,
    validation_record: Mapping[str, Any],
    trace_record: Mapping[str, Any],
    canvas_height: float,
) -> dict[str, Any]:
    ordinal = record_index + 1
    if validation_record.get("sampleIndex") != ordinal:
        raise ValueError(f"{label} public sample ordinal differs")
    if trace_record.get("recordIndex") != record_index:
        raise ValueError(f"{label} trace record ordinal differs")

    role = snapshot_bytes(
        trace_record.get("roleState"),
        ROLE_STATE_BYTE_COUNT,
        f"{label} sample {ordinal} role state",
    )
    private = mapping(validation_record.get("private"), "private crop record")
    observed = finite_rect(private.get("aggregateF64"), "observed aggregate")
    observed_bytes = role[ROLE_AGGREGATE_OFFSET : ROLE_AGGREGATE_OFFSET + 32]
    if observed_bytes != struct.pack("<4d", *observed):
        raise ValueError(f"{label} sample {ordinal} aggregate bytes differ")
    if private.get("aggregateF64Hex") != observed_bytes.hex():
        raise ValueError(f"{label} sample {ordinal} aggregate hex differs")

    child = finite_rect(private.get("recursiveChildF64"), "recursive child")
    if role[
        ROLE_RECURSIVE_CHILD_OFFSET : ROLE_RECURSIVE_CHILD_OFFSET + 32
    ] != struct.pack("<4d", *child):
        raise ValueError(f"{label} sample {ordinal} recursive child differs")

    prepare_frames = sequence(trace_record.get("prepareFrames"), "prepare frames")
    if len(prepare_frames) < 2:
        raise ValueError(f"{label} sample {ordinal} lacks an ancestor frame")
    ancestor = mapping(prepare_frames[1], "first ancestor frame")
    ancestor_role = snapshot_bytes(
        ancestor.get("roleState"),
        ROLE_STATE_BYTE_COUNT,
        f"{label} sample {ordinal} ancestor role state",
    )
    ancestor_aggregate = struct.unpack_from(
        "<4d", ancestor_role, ROLE_AGGREGATE_OFFSET
    )
    if not all(math.isfinite(component) for component in ancestor_aggregate):
        raise ValueError(f"{label} sample {ordinal} ancestor aggregate is not finite")

    transformed_child = transform_child(
        sequence(validation_record.get("carrierPosition"), "carrier position"),
        child,
        canvas_height,
    )
    child_crop = integer_crop(transformed_child)
    ancestor_crop = integer_crop(ancestor_aggregate)
    proxy_intersection = intersect_i32(child_crop, ancestor_crop)
    predicted = union_bounds_f64(
        transformed_child, tuple(float(value) for value in proxy_intersection)
    )
    mismatched_components = [
        index
        for index, (candidate, actual) in enumerate(zip(predicted, observed))
        if not same_f64(candidate, actual)
    ]
    return {
        "label": label,
        "sampleIndex": ordinal,
        "transformedChildF64": list(transformed_child),
        "ancestorAggregateF64": list(ancestor_aggregate),
        "childCropI32": list(child_crop),
        "ancestorCropI32": list(ancestor_crop),
        "proxyIntersectionI32": list(proxy_intersection),
        "predictedF64": list(predicted),
        "observedF64": list(observed),
        "mismatchedComponentIndices": mismatched_components,
        "mismatches": [
            {
                "componentIndex": index,
                "predicted": component_record(predicted[index]),
                "observed": component_record(observed[index]),
            }
            for index in mismatched_components
        ],
    }


def analyze_matrix(root: Path, run_id: int | None = None) -> dict[str, Any]:
    directories = {path.name: path for path in root.iterdir() if path.is_dir()}
    if set(directories) != set(EXPECTED_LABELS):
        missing = sorted(set(EXPECTED_LABELS) - set(directories))
        extra = sorted(set(directories) - set(EXPECTED_LABELS))
        raise ValueError(f"matrix directory inventory differs: missing={missing}, extra={extra}")

    mismatch_records = []
    geometry_results = []
    component_count = 0
    exact_component_count = 0
    record_count = 0
    exact_record_count = 0

    for label in EXPECTED_LABELS:
        directory = directories[label]
        trace_path = directory / TRACE_FILE_NAME
        validation_path = directory / VALIDATION_FILE_NAME
        timeline_path = directory / TIMELINE_FILE_NAME
        trace = load_json(trace_path, f"{label} trace")
        validation = load_json(validation_path, f"{label} validation")
        timeline_sha256 = sha256_file(timeline_path)
        trace_sha256 = sha256_file(trace_path)
        inputs = mapping(validation.get("inputs"), f"{label} validation inputs")
        if (
            inputs.get("timelineSHA256") != timeline_sha256
            or inputs.get("traceSHA256") != trace_sha256
        ):
            raise ValueError(f"{label} validation input hashes differ")
        if (
            trace.get("status") != "finalized"
            or trace.get("finalFailureCount") != 0
            or trace.get("finalQualifiedRecordCount") != 32
            or validation.get("conclusion") != "success"
            or validation.get("prospectiveCaptureIntegrityGatePassed") is not True
            or validation.get("recordCount") != 32
        ):
            raise ValueError(f"{label} prospective integrity gate differs")

        trace_records = sequence(trace.get("qualifiedRecords"), "trace records")
        validation_records = sequence(validation.get("records"), "validation records")
        if len(trace_records) != 32 or len(validation_records) != 32:
            raise ValueError(f"{label} record count differs")
        geometry = mapping(validation.get("geometry"), f"{label} geometry")
        canvas_height = float(geometry.get("windowHeight"))
        if not math.isfinite(canvas_height) or canvas_height <= 0:
            raise ValueError(f"{label} canvas height differs")

        geometry_mismatch_count = 0
        geometry_exact_records = 0
        for index, (validation_record, trace_record) in enumerate(
            zip(validation_records, trace_records, strict=True)
        ):
            result = analyze_record(
                label,
                index,
                mapping(validation_record, "validation record"),
                mapping(trace_record, "trace record"),
                canvas_height,
            )
            mismatches = len(result["mismatchedComponentIndices"])
            component_count += 4
            exact_component_count += 4 - mismatches
            record_count += 1
            geometry_mismatch_count += mismatches
            if mismatches:
                mismatch_records.append(result)
            else:
                exact_record_count += 1
                geometry_exact_records += 1

        geometry_results.append(
            {
                "label": label,
                "geometry": geometry.get("name"),
                "recordCount": 32,
                "componentCount": 128,
                "exactRecordCount": geometry_exact_records,
                "mismatchedRecordCount": 32 - geometry_exact_records,
                "exactComponentCount": 128 - geometry_mismatch_count,
                "mismatchedComponentCount": geometry_mismatch_count,
                "traceSHA256": trace_sha256,
                "timelineSHA256": timeline_sha256,
                "validationSHA256": sha256_file(validation_path),
            }
        )

    return {
        "prepareLayerCropTransferMatrixAnalysisSchemaVersion": (
            ANALYSIS_SCHEMA_VERSION
        ),
        "classification": (
            "opened exact replay of the eight-regime crop discovery matrix; "
            "the ancestor aggregate is explicitly a proxy for the uncaptured "
            "nested LayerShapes integer operand, and every disagreement remains "
            "an exact binary64 mismatch rather than a tolerance"
        ),
        "runID": run_id,
        "geometryCount": len(geometry_results),
        "recordCount": record_count,
        "componentCount": component_count,
        "exactRecordCount": exact_record_count,
        "mismatchedRecordCount": record_count - exact_record_count,
        "exactComponentCount": exact_component_count,
        "mismatchedComponentCount": component_count - exact_component_count,
        "geometryResults": geometry_results,
        "mismatchRecords": mismatch_records,
        "conclusion": {
            "discoveryMatrixIntegrityRechecked": True,
            "transformedGlassDODReplayed": True,
            "openedIntegerCropReplayed": True,
            "openedIntegerIntersectionReplayed": True,
            "openedFloatingUnionReplayed": True,
            "ancestorAggregateProxyExactForEveryComponent": False,
            "missingExactOperand": (
                "the signed-int rectangle converted at prepare_layer+0x8570 "
                "and passed at +0x85dc to LayerShapes::union_bounds"
            ),
            "generalCropPolicyRecovered": False,
            "unseenTransferPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_root", type=Path)
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = analyze_matrix(arguments.artifact_root, arguments.run_id)
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")


if __name__ == "__main__":
    main()
