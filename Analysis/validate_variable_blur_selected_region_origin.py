#!/usr/bin/env python3
"""Validate Apple's selected-region origin and allocation helper end to end."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_dynamic_allocation_holdout as allocation


_BASE_PIPELINE_FRAGMENT = allocation.pipeline_fragment
EXPECTED_TRACE_SCHEMA = 1
EXPECTED_TIMELINE_SCHEMA = 5
EXPECTED_HELPER_FUNCTION = (
    "_ZN2CA3OGL32compute_variable_blur_parametersEjjRKNS_6BoundsEff"
)
EXPECTED_HELPER_BYTE_COUNT = 1_124
EXPECTED_HELPER_SHA256 = (
    "a00a4e174475ce1e6baf29b7dfea28528332f4a1f8bc0bc0e17becdeba98ee8c"
)
EXPECTED_QUARTZCORE_UUID = "F1BA3189-E95A-3ECA-B59A-5A6872754484"
EXPECTED_PRODUCER_PIPELINES = {
    "com.apple.coreanimation.PBGRAXm_TimgA2Xhfc_Isrc": "TimgA2Xhfc_Isrc",
    "com.apple.coreanimation.PBGRAXm_Tds4A2Xhf_Isrc": "Tds4A2Xhf_Isrc",
}
EXPECTED_SAMPLE_INDICES = tuple(range(1, 33))
EXPECTED_MATERIAL = "regular"
EXPECTED_APPEARANCE = "dark"
EXPECTED_DIRECTION = "materialize"
ALLOCATION_QUANTUM = 64
MAXIMUM_ALIGNMENT_EXPONENT = 7
RADIUS_SCALE = 1.6
DOD_EXPANSION = 2.8
DOD_SIZE_INCREMENT = -5.6


def mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(name + " is not an object")
    return value


def sequence(value: object, name: str) -> Sequence[Any]:
    if not isinstance(value, list):
        raise ValueError(name + " is not an array")
    return value


def integer(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(name + " is not an integer")
    return value


def numeric(value: object, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(name + " is not numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(name + " is not finite")
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def float32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def float32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def align_up(value: int, quantum: int = ALLOCATION_QUANTUM) -> int:
    if value <= 0 or quantum <= 0:
        raise ValueError("allocation extent and quantum must be positive")
    return quantum * ((value + quantum - 1) // quantum)


def predict_radius1(
    *,
    blur_radius: float,
    bleed_blur_radius: float,
    backdrop_scale: float,
) -> float:
    radius = 0.5 * max(2.0 * blur_radius, bleed_blur_radius)
    return float32(radius * backdrop_scale)


def predict_mip_policy(
    *,
    radius1: float,
    source_extent: Sequence[int],
) -> dict[str, int | float]:
    if len(source_extent) != 2 or any(value <= 0 for value in source_extent):
        raise ValueError("source extent differs")
    scaled_radius = float32(float32(radius1) * float32(RADIUS_SCALE))
    maximum_level_count = (
        math.floor(float32(math.log2(float32(max(source_extent))))) + 1
    )
    if scaled_radius == 0.0:
        requested_level_count = 1
    else:
        requested_level_count = (
            max(
                math.ceil(float32(math.log2(scaled_radius))),
                0,
            )
            + 1
        )
        if requested_level_count == 1:
            requested_level_count = 2
    level_count = min(requested_level_count, maximum_level_count)
    alignment_exponent = min(level_count, MAXIMUM_ALIGNMENT_EXPONENT)
    return {
        "scaledRadius": scaled_radius,
        "maximumLevelCount": maximum_level_count,
        "levelCount": level_count,
        "alignmentExponent": alignment_exponent,
        "alignmentScale": 1 << alignment_exponent,
    }


def predict_integer_bounds(
    *,
    bounds: Sequence[int],
    radius1: float,
    alignment_scale: int,
) -> list[int]:
    if len(bounds) != 4 or bounds[2] <= 0 or bounds[3] <= 0 or alignment_scale <= 0:
        raise ValueError("helper bounds differ")
    axes: list[tuple[int, int]] = []
    reciprocal = 1.0 / alignment_scale
    for lower, extent in ((bounds[0], bounds[2]), (bounds[1], bounds[3])):
        expanded_lower = float(lower) + ((-float(radius1)) * DOD_EXPANSION)
        expanded_extent = math.fma(
            -float(radius1),
            DOD_SIZE_INCREMENT,
            float(extent),
        )
        reduced_lower = expanded_lower * reciprocal
        reduced_extent = expanded_extent * reciprocal
        integer_lower = math.floor(reduced_lower)
        integer_upper = math.ceil(reduced_lower + reduced_extent)
        axes.append(
            (
                integer_lower * alignment_scale,
                (integer_upper - integer_lower) * alignment_scale,
            )
        )
    return [axes[0][0], axes[1][0], axes[0][1], axes[1][1]]


def _producer_fragment(record: Mapping[str, Any]) -> str:
    opened = _BASE_PIPELINE_FRAGMENT(record)
    if opened:
        return opened
    return EXPECTED_PRODUCER_PIPELINES.get(allocation.pipeline_label(record), "")


def observed_policy(
    record: Mapping[str, Any],
    *,
    scale: float,
) -> dict[str, Any]:
    original_fragment = allocation.pipeline_fragment
    original_fragments = allocation.PRODUCER_FRAGMENTS
    allocation.pipeline_fragment = _producer_fragment
    allocation.PRODUCER_FRAGMENTS = frozenset(
        set(original_fragments) | set(EXPECTED_PRODUCER_PIPELINES.values())
    )
    try:
        return allocation.observed_policy(
            record,
            scale=scale,
            require_primary_source_q_exact=False,
        )
    finally:
        allocation.pipeline_fragment = original_fragment
        allocation.PRODUCER_FRAGMENTS = original_fragments


def copy_destination_mipmap_count(record: Mapping[str, Any]) -> int:
    render = mapping(record.get("render"), "dynamic render")
    probe = mapping(render.get("metalUniformProbe"), "Metal uniform probe")
    records = sequence(probe.get("records"), "Metal records")
    matches = []
    for untyped in records:
        item = mapping(untyped, "Metal record")
        if (
            item.get("kind") == "texture"
            and item.get("stage") == "compute"
            and item.get("index") == 1
            and allocation.pipeline_label(item) == allocation.COPY_BASE_PIPELINE
        ):
            matches.append(item)
    if len(matches) != 1:
        raise ValueError("copy-base destination texture count differs")
    texture = allocation.texture(matches[0])
    return integer(texture.get("mipmapLevelCount"), "destination mip count")


def _vector(value: object, name: str, count: int) -> list[int]:
    items = sequence(value, name)
    if len(items) != count:
        raise ValueError(name + " length differs")
    return [integer(item, name + " component") for item in items]


def _float_vector(value: object, name: str, count: int) -> list[float]:
    items = sequence(value, name)
    if len(items) != count:
        raise ValueError(name + " length differs")
    return [numeric(item, name + " component") for item in items]


def _validate_trace_envelope(trace: Mapping[str, Any]) -> None:
    if trace.get("variableBlurParameterTraceSchemaVersion") != EXPECTED_TRACE_SCHEMA:
        raise ValueError("trace schema differs")
    if trace.get("status") != "complete" or trace.get("failures") != []:
        raise ValueError("trace did not complete cleanly")
    if trace.get("capturedImageOrPixelUsedForSelection") is not False:
        raise ValueError("image or pixel was used for trace selection")
    if trace.get("capturedResultUsedForSelection") is not False:
        raise ValueError("helper result was used for trace selection")
    configuration = mapping(trace.get("configuration"), "trace configuration")
    if (
        configuration.get("function") != EXPECTED_HELPER_FUNCTION
        or configuration.get("outputCompleteOffset") != 0x370
        or configuration.get("resultByteCount") != 72
    ):
        raise ValueError("trace configuration differs")
    code = mapping(trace.get("code"), "helper code")
    encoded = code.get("hex")
    if not isinstance(encoded, str):
        raise ValueError("helper code bytes are missing")
    payload = bytes.fromhex(encoded)
    if (
        code.get("symbolByteCount") != EXPECTED_HELPER_BYTE_COUNT
        or len(payload) != EXPECTED_HELPER_BYTE_COUNT
        or code.get("sha256") != EXPECTED_HELPER_SHA256
        or hashlib.sha256(payload).hexdigest() != EXPECTED_HELPER_SHA256
        or code.get("moduleUUID") != EXPECTED_QUARTZCORE_UUID
        or not str(code.get("module", "")).endswith("/QuartzCore")
    ):
        raise ValueError("helper code identity differs")


def _validate_timeline_envelope(
    timeline: Mapping[str, Any],
    *,
    expected_geometry: str,
) -> list[Mapping[str, Any]]:
    geometry = mapping(timeline.get("geometry"), "timeline geometry")
    if (
        timeline.get("schemaVersion") != EXPECTED_TIMELINE_SCHEMA
        or geometry.get("name") != expected_geometry
        or timeline.get("material") != EXPECTED_MATERIAL
        or timeline.get("appearance") != EXPECTED_APPEARANCE
        or timeline.get("direction") != EXPECTED_DIRECTION
        or timeline.get("windowBackingScaleFactor") != 2
        or timeline.get("sampleCount") != 33
        or timeline.get("failedSamples") != 0
    ):
        raise ValueError("timeline envelope differs")
    uniforms = mapping(
        timeline.get("dynamicBackgroundUniforms"),
        "dynamic background uniforms",
    )
    records = [
        mapping(value, "dynamic record")
        for value in sequence(uniforms.get("records"), "dynamic records")
    ]
    indices = tuple(record.get("sampleIndex") for record in records)
    if (
        uniforms.get("executed") is not True
        or uniforms.get("executedSampleCount") != 32
        or indices != EXPECTED_SAMPLE_INDICES
    ):
        raise ValueError("dynamic sample sequence differs")
    return records


def validate(
    trace: Mapping[str, Any],
    timeline: Mapping[str, Any],
    *,
    expected_geometry: str,
    authority: str,
    trace_sha256: str,
    timeline_sha256: str,
) -> dict[str, Any]:
    if authority not in {"calibration", "holdout"}:
        raise ValueError("authority differs")
    _validate_trace_envelope(trace)
    dynamic_records = _validate_timeline_envelope(
        timeline,
        expected_geometry=expected_geometry,
    )
    helper_records = [
        mapping(value, "helper record")
        for value in sequence(trace.get("records"), "helper records")
    ]
    if len(helper_records) != len(dynamic_records):
        raise ValueError("helper and dynamic record counts differ")

    states = []
    for expected_index, (dynamic, helper) in enumerate(
        zip(dynamic_records, helper_records, strict=True),
        1,
    ):
        if helper.get("index") != expected_index - 1:
            raise ValueError("helper record order differs")
        bounds = _vector(helper.get("bounds"), "helper bounds", 4)
        source_extent = _vector(
            helper.get("sourceExtent"),
            "helper source extent",
            2,
        )
        if source_extent != bounds[2:]:
            raise ValueError("helper source extent and bounds differ")
        radius1_record = mapping(helper.get("radius1"), "helper radius1")
        radius1 = numeric(radius1_record.get("binary32"), "helper radius1")
        radius_hex = radius1_record.get("hex")
        if not isinstance(radius_hex, str) or len(bytes.fromhex(radius_hex)) < 4:
            raise ValueError("helper radius1 bytes differ")
        if (
            float32_bits(radius1)
            != struct.unpack("<I", bytes.fromhex(radius_hex)[:4])[0]
        ):
            raise ValueError("helper radius1 value and bytes differ")

        scale, _ = allocation.captured_scale(dynamic)
        filter_record = mapping(dynamic.get("filter"), "filter")
        input_values = mapping(filter_record.get("inputValues"), "filter inputs")
        predicted_radius1 = predict_radius1(
            blur_radius=numeric(input_values.get("inputBlurRadius"), "blur radius"),
            bleed_blur_radius=numeric(
                input_values.get("inputBleedBlurRadius"),
                "bleed blur radius",
            ),
            backdrop_scale=scale,
        )
        if float32_bits(predicted_radius1) != float32_bits(radius1):
            raise ValueError("public-input helper radius differs")

        mip = predict_mip_policy(
            radius1=radius1,
            source_extent=source_extent,
        )
        result = mapping(helper.get("result"), "helper result")
        radius_values = _float_vector(
            result.get("radiusValues"),
            "helper radius values",
            2,
        )
        mip_values = _vector(result.get("mipValues"), "helper mip values", 2)
        alignment_scale = numeric(
            result.get("alignmentScale"),
            "helper alignment scale",
        )
        if (
            float32_bits(radius_values[1]) != float32_bits(float(mip["scaledRadius"]))
            or mip_values[1] != mip["levelCount"]
            or alignment_scale != mip["alignmentScale"]
        ):
            raise ValueError("helper mip policy differs")
        predicted_bounds = predict_integer_bounds(
            bounds=bounds,
            radius1=radius1,
            alignment_scale=int(mip["alignmentScale"]),
        )
        integer_bounds = _vector(
            result.get("integerBounds"),
            "helper integer bounds",
            4,
        )
        floating_bounds = _float_vector(
            result.get("floatingBounds"),
            "helper floating bounds",
            4,
        )
        if predicted_bounds != integer_bounds or floating_bounds != integer_bounds:
            raise ValueError("helper integer-bounds replay differs")

        observed = observed_policy(dynamic, scale=scale)
        crop_origin = _vector(observed.get("cropOrigin"), "crop origin", 2)
        clamp = _vector(
            observed.get("textureCoordinateClamp"),
            "copy clamp",
            4,
        )
        if (
            bounds[:2] != crop_origin
            or bounds[2:] != [clamp[2] + 1, clamp[3] + 1]
            or observed.get("producerExtent")
            != [align_up(bounds[2]), align_up(bounds[3])]
        ):
            raise ValueError("helper input and producer crop differ")
        effective_origin = _vector(
            observed.get("effectiveOrigin"),
            "effective origin",
            2,
        )
        destination_extent = _vector(
            observed.get("destinationExtent"),
            "destination extent",
            2,
        )
        allocated_extent = [
            align_up(integer_bounds[2]),
            align_up(integer_bounds[3]),
        ]
        destination_mips = copy_destination_mipmap_count(dynamic)
        if (
            integer_bounds[:2] != effective_origin
            or allocated_extent != destination_extent
            or destination_mips != mip_values[1]
        ):
            raise ValueError("helper output and copy-base allocation differ")
        copy_offset = _vector(observed.get("copyOffset"), "copy offset", 2)
        if [
            crop_origin[0] + copy_offset[0],
            crop_origin[1] + copy_offset[1],
        ] != integer_bounds[:2]:
            raise ValueError("producer-crop plus copy-base origin differs")
        states.append(
            {
                "sampleIndex": expected_index,
                "remaining": numeric(dynamic.get("remaining"), "remaining"),
                "backdropScale": scale,
                "bounds": bounds,
                "radius1": radius1,
                "alignmentExponent": mip["alignmentExponent"],
                "alignmentScale": mip["alignmentScale"],
                "helperIntegerBounds": integer_bounds,
                "producerCropOrigin": crop_origin,
                "copyOffset": copy_offset,
                "effectiveOrigin": effective_origin,
                "helperDesiredExtent": integer_bounds[2:],
                "allocatedExtent": allocated_extent,
                "destinationMipCount": destination_mips,
            }
        )

    holdout_passed = authority == "holdout"
    return {
        "variableBlurSelectedRegionOriginResultSchemaVersion": 1,
        "classification": (
            "unseen selected-region origin/allocation transfer"
            if holdout_passed
            else "opened selected-region origin/allocation calibration"
        ),
        "status": "passed",
        "authority": authority,
        "geometry": expected_geometry,
        "traceSHA256": trace_sha256,
        "timelineSHA256": timeline_sha256,
        "helperCodeSHA256": EXPECTED_HELPER_SHA256,
        "sampleCount": len(states),
        "originComponentCount": 2 * len(states),
        "originMismatchedComponents": 0,
        "desiredExtentComponentCount": 2 * len(states),
        "desiredExtentMismatchedComponents": 0,
        "allocationExtentComponentCount": 2 * len(states),
        "allocationExtentMismatchedComponents": 0,
        "radiusBinary32Count": len(states),
        "radiusBinary32Mismatches": 0,
        "selectedRegionOriginTransferPassed": holdout_passed,
        "selectedRegionAllocationTransferPassed": holdout_passed,
        "appearanceDependentPresentationLifetimePassed": False,
        "capturedInputOpticalTransferPassed": False,
        "temporalMeshSourceMipTransferPassed": False,
        "physicalRetinaOutputTransferPassed": False,
        "independentWalleZeroByteParityPassed": False,
        "liquidGlassParityEstablished": False,
        "productionShaderChanged": False,
        "states": states,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("--expected-geometry", required=True)
    parser.add_argument(
        "--authority",
        choices=("calibration", "holdout"),
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    trace = json.loads(arguments.trace.read_text(encoding="utf-8"))
    timeline = json.loads(arguments.timeline.read_text(encoding="utf-8"))
    result = validate(
        mapping(trace, "trace"),
        mapping(timeline, "timeline"),
        expected_geometry=arguments.expected_geometry,
        authority=arguments.authority,
        trace_sha256=sha256_file(arguments.trace),
        timeline_sha256=sha256_file(arguments.timeline),
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
