#!/usr/bin/env python3
"""Open run 31057364064 without rewriting its failed prospective gate.

The preregistered validator required one destination-matched union per normal
marker.  Apple emitted two.  This analyzer preserves that failure, validates
the retained bytes independently, selects the *last* match by event order, and
tests one public-state crop candidate without tolerances or value-based record
selection.
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

import validate_prepare_layer_crop_transfer as crop_validator
import validate_prepare_layer_crop_union_operand as union_validator


ANALYSIS_SCHEMA_VERSION = 1
RUN_ID = 31_057_364_064
TRACE_FILE_NAME = "prepare-layer-crop-union-operand-trace.json"
TIMELINE_FILE_NAME = "transition-timeline.json"
PUBLIC_CROP_LAYER_PATH = (1, 0, 1)
LOWER_BOUND = -536_870_911.0
UPPER_BOUND = 536_870_912.0
EXPECTED_GEOMETRIES = {
    "crop-1536-clipped": "circle-1536-center",
    "crop-256-center": "circle-256-center",
    "crop-512-offset": "circle-512-offset",
    "crop-640-center": "circle-640-center",
    "crop-640-fractional": "circle-640-fractional",
    "crop-640-half-even": "circle-640-phase-0500-even",
    "crop-640-half-signed": "circle-640-phase-0500-signed",
    "crop-640-integer": "circle-640-integer",
}

type RectF64 = tuple[float, float, float, float]
type RectI32 = tuple[int, int, int, int]


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} is not an object")
    return value


def sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{label} is not an array")
    return value


def integer(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} is not an integer")
    return value


def finite(value: Any, label: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(result := float(value))
    ):
        raise ValueError(f"{label} is not finite")
    return result


def finite_rect(value: Any, label: str) -> RectF64:
    raw = sequence(value, label)
    if len(raw) != 4:
        raise ValueError(f"{label} component count differs")
    result = tuple(finite(component, label) for component in raw)
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


def same_f64_rect(left: RectF64, right: RectF64) -> bool:
    return struct.pack("<4d", *left) == struct.pack("<4d", *right)


def integer_crop(rectangle: RectF64) -> RectI32:
    """Replay the opened finite enclosure and fractional-border branch."""
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
    if any(float(component) != value for component, value in zip(enclosed, clamped)):
        return (
            enclosed[0] - 1,
            enclosed[1] - 1,
            enclosed[2] + 2,
            enclosed[3] + 2,
        )
    return enclosed


def intersect_i32(left: RectI32, right: RectI32) -> RectI32:
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


def public_crop_float_candidate(
    carrier_position: Sequence[Any],
    public_bounds: RectF64,
    transformed_dod: RectF64,
    canvas_height: float,
    blur_radius: float,
    bleed_blur_radius: float,
) -> tuple[RectF64, float, RectF64]:
    """Return the frozen edge-intersection candidate and its public ROI."""
    if len(carrier_position) != 2:
        raise ValueError("carrier position component count differs")
    position_x = finite(carrier_position[0], "carrier x")
    position_y = finite(carrier_position[1], "carrier y")
    expansion = 2.8 * max(2.0 * blur_radius, bleed_blur_radius)
    support = 9.0 + expansion

    bounds_far_x = public_bounds[0] + public_bounds[2]
    bounds_far_y = public_bounds[1] + public_bounds[3]
    public_lower_x = (position_x + public_bounds[0]) - support
    public_lower_y = ((canvas_height - position_y) - bounds_far_y) - 17.0
    public_far_x = (position_x + bounds_far_x) + support
    public_far_y = ((canvas_height - position_y) - public_bounds[1]) + support
    public_roi = (
        public_lower_x,
        public_lower_y,
        max(0.0, public_far_x - public_lower_x),
        max(0.0, public_far_y - public_lower_y),
    )

    dod_far_x = transformed_dod[0] + transformed_dod[2]
    dod_far_y = transformed_dod[1] + transformed_dod[3]
    lower_x = max(transformed_dod[0], public_lower_x)
    lower_y = max(transformed_dod[1], public_lower_y)
    far_x = min(dod_far_x, public_far_x)
    far_y = min(dod_far_y, public_far_y)
    candidate = (
        lower_x,
        lower_y,
        max(0.0, far_x - lower_x),
        max(0.0, far_y - lower_y),
    )
    return candidate, expansion, public_roi


def public_layer(record: Mapping[str, Any]) -> Mapping[str, Any]:
    matches = [
        mapping(raw, "captured layer")
        for raw in sequence(record.get("capturedLayerStates"), "captured layers")
        if tuple(mapping(raw, "captured layer").get("path") or ())
        == PUBLIC_CROP_LAYER_PATH
    ]
    if len(matches) != 1:
        raise ValueError("public crop layer is not unique")
    return matches[0]


def validate_extension(
    trace: Mapping[str, Any],
    base_result: Mapping[str, Any],
    timeline: Mapping[str, Any],
    label: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    extension = mapping(trace.get("cropUnionOperandExtension"), "crop union extension")
    if (
        extension.get("cropUnionOperandExtensionSchemaVersion")
        != union_validator.EXTENSION_SCHEMA_VERSION
        or extension.get("configuration")
        != union_validator.EXPECTED_EXTENSION_CONFIGURATION
        or extension.get("status") != "finalized"
        or extension.get("statusBeforeFinalization") != "crop-union-breakpoints-active"
    ):
        raise ValueError(f"{label} extension identity differs")

    prepare = mapping(trace.get("prepareLayer"), "prepare layer")
    prepare_start = integer(prepare.get("symbolStart"), "prepare start")
    if extension.get("prepareLayerSymbolStart") != prepare_start:
        raise ValueError(f"{label} extension prepare start differs")
    call_digest = hashlib.sha256(
        bytes.fromhex(union_validator.UNION_CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX)
    ).hexdigest()
    return_digest = hashlib.sha256(
        bytes.fromhex(union_validator.UNION_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX)
    ).hexdigest()
    if (
        extension.get("unionCallInstructionSHA256") != call_digest
        or extension.get("unionReturnInstructionSHA256") != return_digest
    ):
        raise ValueError(f"{label} extension instruction identity differs")

    raw_records = sequence(extension.get("unionRecords"), "union records")
    decoded = [
        union_validator.validate_union_record(raw, index, prepare_start)
        for index, raw in enumerate(raw_records)
    ]
    event_sequences = [
        event
        for record in decoded
        for event in (record["callEventSequence"], record["returnEventSequence"])
    ]
    if sorted(event_sequences) != list(range(1, len(event_sequences) + 1)):
        raise ValueError(f"{label} union event sequence differs")

    rejected_calls = integer(
        extension.get("finalRejectedUnionCallCount"), "rejected union calls"
    )
    rejected_returns = integer(
        extension.get("finalRejectedUnionReturnCount"), "rejected union returns"
    )
    grouped_rejections = sum(
        integer(mapping(raw, "rejection group").get("hitCount"), "rejection count")
        for raw in sequence(extension.get("rejectionGroups"), "rejection groups")
    )
    if (
        rejected_calls != rejected_returns
        or rejected_calls != grouped_rejections
        or extension.get("finalQualifiedUnionRecordCount") != len(decoded)
        or extension.get("finalCompleteUnionRecordCount") != len(decoded)
        or extension.get("finalEventSequence") != len(decoded) * 2
        or extension.get("finalUnionCallHitCount") != len(decoded) + rejected_calls
        or extension.get("finalUnionReturnHitCount") != len(decoded) + rejected_returns
    ):
        raise ValueError(f"{label} union accounting differs")

    marker_records = sequence(trace.get("qualifiedRecords"), "marker records")
    public_records = sequence(base_result.get("records"), "public records")
    timeline_records = sequence(
        mapping(timeline.get("dynamicBackgroundUniforms"), "timeline uniforms").get(
            "records"
        ),
        "timeline uniform records",
    )
    links = sequence(extension.get("markerLinks"), "marker links")
    if (
        not len(marker_records)
        == len(public_records)
        == len(timeline_records)
        == len(links)
        == 32
    ):
        raise ValueError(f"{label} marker inventory differs")

    geometry = mapping(base_result.get("geometry"), "geometry")
    finite(geometry.get("windowWidth"), "canvas width")
    canvas_height = finite(geometry.get("windowHeight"), "canvas height")
    joined: list[dict[str, Any]] = []
    previous_end = 0
    for index, (raw_link, raw_marker, raw_public, raw_timeline) in enumerate(
        zip(links, marker_records, public_records, timeline_records, strict=True)
    ):
        link = mapping(raw_link, "marker link")
        marker = mapping(raw_marker, "marker record")
        public = mapping(raw_public, "public record")
        timeline_record = mapping(raw_timeline, "timeline record")
        start = integer(link.get("startUnionRecordIndex"), "link start")
        end = integer(link.get("endUnionRecordIndexExclusive"), "link end")
        identity = mapping(marker.get("frameIdentity"), "marker identity")
        destination = (
            integer(identity.get("roleBase"), "marker role base")
            + union_validator.UNION_DESTINATION_ROLE_OFFSET
        )
        matching = list(
            sequence(link.get("matchingUnionRecordIndices"), "matching unions")
        )
        recomputed = [
            record["recordIndex"]
            for record in decoded[start:end]
            if record["destinationAddress"] == destination
        ]
        embedded = mapping(marker.get("cropUnionOperandWindow"), "union window")
        if (
            start != previous_end
            or not start < end <= len(decoded)
            or matching != recomputed
            or len(matching) != 2
            or matching[-1] != end - 1
            or link.get("destinationAddress") != destination
            or embedded.get("matchingRecordIndices") != matching
        ):
            raise ValueError(f"{label} sample {index + 1} two-union topology differs")
        first = decoded[matching[0]]
        selected = decoded[matching[-1]]
        if (
            first["prepareRecursionDepth"] != selected["prepareRecursionDepth"]
            or selected["roleBase"] != first["roleBase"] + 48
            or not same_f64_rect(
                finite_rect(first["targetBeforeF64"], "first target before"),
                (0.0, 0.0, 0.0, 0.0),
            )
        ):
            raise ValueError(f"{label} sample {index + 1} union roles differ")

        private = mapping(public.get("private"), "private record")
        child = finite_rect(private.get("recursiveChildF64"), "recursive child")
        transformed = union_validator.transform_child(
            sequence(public.get("carrierPosition"), "carrier position"),
            child,
            canvas_height,
        )
        before = finite_rect(selected["targetBeforeF64"], "selected target before")
        union_input = finite_rect(selected["inputF64"], "selected union input")
        after = finite_rect(selected["targetAfterF64"], "selected target after")
        observed = finite_rect(private.get("aggregateF64"), "observed aggregate")
        if (
            not same_f64_rect(before, transformed)
            or not same_f64_rect(
                union_validator.replay_union(before, union_input), after
            )
            or not same_f64_rect(after, observed)
        ):
            raise ValueError(f"{label} sample {index + 1} final union replay differs")

        layer = public_layer(timeline_record)
        bounds = finite_rect(layer.get("bounds"), "public layer bounds")
        filter_values = mapping(
            mapping(timeline_record.get("filter"), "background filter").get(
                "inputValues"
            ),
            "background filter inputs",
        )
        blur = finite(filter_values.get("inputBlurRadius"), "blur radius")
        bleed_blur = finite(
            filter_values.get("inputBleedBlurRadius"), "bleed blur radius"
        )
        candidate_float, expansion, public_roi = public_crop_float_candidate(
            sequence(public.get("carrierPosition"), "carrier position"),
            bounds,
            transformed,
            canvas_height,
            blur,
            bleed_blur,
        )
        candidate_enclosure = integer_crop(candidate_float)
        viewport_f64 = finite_rect(private.get("viewportF64"), "viewport")
        if any(not value.is_integer() for value in viewport_f64):
            raise ValueError(f"{label} sample {index + 1} viewport is fractional")
        viewport = tuple(int(value) for value in viewport_f64)
        candidate_crop = intersect_i32(candidate_enclosure, viewport)  # type: ignore[arg-type]
        actual_crop = tuple(selected["nestedInputI32"])
        if candidate_crop != actual_crop:
            raise ValueError(
                f"{label} sample {index + 1} public crop candidate differs: "
                f"{candidate_crop} != {actual_crop}"
            )
        joined.append(
            {
                "label": label,
                "sampleIndex": index + 1,
                "firstUnionRecordIndex": first["recordIndex"],
                "selectedLastUnionRecordIndex": selected["recordIndex"],
                "carrierPosition": public.get("carrierPosition"),
                "publicBoundsF64": list(bounds),
                "blurRadius": blur,
                "bleedBlurRadius": bleed_blur,
                "glassDODExpansion": expansion,
                "transformedGlassDODF64": list(transformed),
                "publicROIF64": list(public_roi),
                "candidateIntersectionF64": list(candidate_float),
                "candidateEnclosureI32": list(candidate_enclosure),
                "viewportI32": list(viewport),
                "candidateViewportIntersectionI32": list(candidate_crop),
                "observedNestedInputI32": list(actual_crop),
                "observedAggregateF64": list(observed),
            }
        )
        previous_end = end

    trailing = len(decoded) - previous_end
    if (
        extension.get("finalTrailingUnionRecordCount") != trailing
        or extension.get("finalLinkedUnionRecordCount") != 64
    ):
        raise ValueError(f"{label} trailing or linked union accounting differs")
    return joined, {
        "unionRecordCount": len(decoded),
        "rejectedUnionCallCount": rejected_calls,
        "destinationMatchedUnionCount": 64,
        "structurallyRetainedTrailingUnionCount": trailing,
    }


def artifact_directories(root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for label in EXPECTED_GEOMETRIES:
        matches = [
            path
            for path in root.iterdir()
            if path.is_dir()
            and path.name.startswith(
                f"liquid-glass-prepare-layer-crop-union-operand-{label}-"
            )
        ]
        if len(matches) != 1:
            raise ValueError(f"{label} artifact directory is not unique")
        result[label] = matches[0]
    return result


def analyze_matrix(root: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    geometries = []
    for label, directory in artifact_directories(root).items():
        trace_path = directory / TRACE_FILE_NAME
        timeline_path = directory / TIMELINE_FILE_NAME
        trace = load_json(trace_path, f"{label} trace")
        timeline = load_json(timeline_path, f"{label} timeline")
        base_result = crop_validator.validate(
            trace_path, timeline_path, EXPECTED_GEOMETRIES[label]
        )
        geometry_records, accounting = validate_extension(
            trace, base_result, timeline, label
        )
        records.extend(geometry_records)
        geometries.append(
            {
                "label": label,
                "geometry": EXPECTED_GEOMETRIES[label],
                "recordCount": len(geometry_records),
                "componentCount": len(geometry_records) * 4,
                "traceSHA256": sha256_file(trace_path),
                "timelineSHA256": sha256_file(timeline_path),
                **accounting,
            }
        )
    return {
        "prepareLayerCropUnionOperandMatrixAnalysisSchemaVersion": (
            ANALYSIS_SCHEMA_VERSION
        ),
        "classification": (
            "retrospective opening of a prospectively failed two-union capture; "
            "the failed one-match assumption is preserved, the last match is "
            "selected only by event order, and one public crop candidate is "
            "replayed exactly without tolerances"
        ),
        "runID": RUN_ID,
        "prospectiveGatePassed": False,
        "falsifiedProspectiveAssumption": (
            "exactly one destination-matched union exists in each marker interval"
        ),
        "observedDestinationMatchedUnionCountPerMarker": 2,
        "openedSelectionRule": (
            "select the last destination-matched union record in the marker "
            "interval; it is also the interval's final qualified union record"
        ),
        "geometryCount": len(geometries),
        "recordCount": len(records),
        "componentCount": len(records) * 4,
        "exactPublicCropRecordCount": len(records),
        "mismatchedPublicCropRecordCount": 0,
        "geometryResults": geometries,
        "records": records,
        "candidate": {
            "publicLayerPath": list(PUBLIC_CROP_LAYER_PATH),
            "glassDODExpansion": "e = 2.8 * max(2 * inputBlurRadius, inputBleedBlurRadius)",
            "support": "s = 9 + e",
            "publicROIEdges": {
                "lowerX": "Px + Bx - s",
                "lowerY": "H - Py - (By + Bh) - 17",
                "farX": "Px + (Bx + Bw) + s",
                "farY": "H - Py - By + s",
            },
            "composition": (
                "intersect the floating public ROI with the transformed Glass "
                "DOD; apply the opened finite floor/ceil enclosure and optional "
                "one-pixel border; intersect the signed integer result with the "
                "integer viewport"
            ),
            "toleranceUsed": False,
            "exceptionFitUsed": False,
        },
        "conclusion": {
            "retainedCaptureIntegrityRechecked": True,
            "prospectiveOneMatchGateFalsified": True,
            "lastMatchStructuralSelectorClosedEveryRecord": True,
            "allSignedIntegerOperandsReplayedExactly": True,
            "allFinalFloatingUnionsReplayedBitForBit": True,
            "calibrationMatrixExact": True,
            "preIntegerFloatingProducerCapturedAcrossMatrix": False,
            "unseenTransferPassed": False,
            "generalCropPolicyRecovered": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_root", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = analyze_matrix(arguments.artifact_root)
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")


if __name__ == "__main__":
    main()
