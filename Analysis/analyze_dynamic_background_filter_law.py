#!/usr/bin/env python3
"""Audit recovered clear/light dynamic glass-background input laws."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


EXPECTED_GEOMETRIES = frozenset(
    {
        "circle-256-center",
        "circle-512-offset",
        "circle-640-fractional",
        "circle-1536-center",
    }
)
EXPECTED_SAMPLE_INDICES = tuple(range(1, 33))
UNKNOWN_NUMERIC_FIELDS = frozenset({"inputClamp"})

ZERO_FIELDS = frozenset(
    {
        "inputBleedAmount",
        "inputBleedBlurRadius",
        "inputBleedDistance1",
        "inputBleedHeight",
        "inputBleedOpacity",
        "inputBlurDistance2",
        "inputBlurDistance3",
        "inputBlurDistance4",
        "inputRefractionDistance1",
        "inputRefractionOpacity",
        "inputShadowBlurRadius",
        "inputShadowColorMatrixBlack",
        "inputShadowDistanceOffset",
        "inputShadowOpacity",
        "inputShadowRadius",
        "inputShadowVibrancyContribution",
    }
)
ONE_FIELDS = frozenset(
    {
        "inputBleedColorMatrixWhite",
        "inputShadowColorMatrixWhite",
    }
)


def mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} is not an object")
    return value


def sequence(value: object, name: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{name} is not an array")
    return value


def numeric(value: object, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{name} is not numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} is not finite")
    return result


def float32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def float32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def float32_mix(start: float, end: float, amount: float) -> float:
    k = float32(amount)
    start_term = float32(float32(1.0 - k) * float32(start))
    end_term = float32(k * float32(end))
    return float32(start_term + end_term)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def predicted_numeric_fields(
    geometry: Mapping[str, Any], remaining: float
) -> dict[str, float]:
    if not 0.0 < remaining <= 1.0:
        raise ValueError("remaining value is outside (0, 1]")
    diameter = numeric(geometry.get("width"), "geometry width")
    if numeric(geometry.get("height"), "geometry height") != diameter:
        raise ValueError("background-filter audit requires a circle")
    effective_diameter = remaining * (diameter + 16.0 * (1.0 - remaining))
    blur_weight = float32(float32(remaining) * float32_mix(0.2, 0.5, remaining))
    result = {field: 0.0 for field in ZERO_FIELDS}
    result.update({field: 1.0 for field in ONE_FIELDS})
    result.update(
        {
            "inputBleedColorMatrixBlack": float32_mix(0.0, 0.75, remaining),
            "inputBleedColorMatrixSaturation": float32_mix(1.0, 1.2, remaining),
            "inputBleedDistance0": remaining,
            "inputBlurDistance0": -effective_diameter / 2.0,
            "inputBlurDistance1": -remaining,
            "inputBlurOpacity0": remaining,
            "inputBlurOpacity1": blur_weight,
            "inputBlurOpacity2": blur_weight,
            "inputBlurOpacity3": float32(2.0 * blur_weight),
            "inputBlurOpacity4": float32(2.0 * blur_weight),
            "inputBlurRadius": remaining,
            "inputFaceColorMatrixBlack": float32_mix(0.0, 0.075, remaining),
            "inputFaceColorMatrixSaturation": float32_mix(1.0, 1.06, remaining),
            "inputFaceColorMatrixWhite": float32_mix(1.0, 1.15, remaining),
            "inputFaceOpacity": remaining,
            "inputInnerRefractionAmount": -60.0 * remaining,
            "inputInnerRefractionHeight": 20.0 * remaining,
            "inputMaxHeadroom": float32_mix(1.2, 9_999.0, remaining),
            "inputOuterRefractionAmount": effective_diameter / 5.0,
            "inputOuterRefractionHeight": effective_diameter / 8.0,
            "inputRefractionDistance0": -remaining,
            "inputSDRGradientDistance0": -2.0 * remaining,
            "inputSDRGradientDistance1": -remaining,
            "inputSDRHoldingToneWhite": float32_mix(1.0, 0.97, remaining),
            "inputSDRShadowOpacity": float32_mix(0.0, 0.24, remaining),
            "inputShadowAmount": 75.0 * remaining,
            "inputShadowColorMatrixSaturation": float32_mix(1.0, 1.2, remaining),
            "inputShadowHeight": 2.0 * effective_diameter / 5.0,
        }
    )
    return result


def validate_nonnumeric_fields(values: Mapping[str, Any], remaining: float) -> int:
    if (
        values.get("inputBleedColorMatrixFillColor") is not None
        or values.get("inputBleedDarkenBlend") is not True
        or values.get("inputClampPreserveHue") is not False
        or values.get("inputSDRHoldingToneEnabled") is not True
        or values.get("inputSourceSublayerName") != "@0"
    ):
        raise ValueError("constant nonnumeric background-filter fields differ")
    face_fill_value = values.get("inputFaceColorMatrixFillColor")
    if remaining < 1.0:
        if face_fill_value is not None:
            raise ValueError("non-endpoint face matrix fill color differs")
    else:
        face_fill = mapping(face_fill_value, "endpoint face matrix fill color")
        face_components = sequence(
            face_fill.get("components"), "endpoint face fill components"
        )
        if (
            face_fill.get("numberOfComponents") != 4
            or face_fill.get("colorSpaceName") != "kCGColorSpaceExtendedSRGB"
            or list(face_components) != [1, 1, 1, 0]
            or numeric(face_fill.get("alpha"), "endpoint face fill alpha") != 0.0
        ):
            raise ValueError("endpoint face matrix fill color differs")
    fill = mapping(
        values.get("inputShadowColorMatrixFillColor"),
        "shadow matrix fill color",
    )
    expected_alpha = float32_mix(0.0, 0.1, remaining)
    components = sequence(fill.get("components"), "shadow fill components")
    if (
        fill.get("numberOfComponents") != 4
        or fill.get("colorSpaceName") != "kCGColorSpaceExtendedSRGB"
        or len(components) != 4
        or any(numeric(value, "shadow fill RGB") != 0.0 for value in components[:3])
        or float32_bits(numeric(fill.get("alpha"), "shadow fill alpha"))
        != float32_bits(expected_alpha)
        or float32_bits(numeric(components[3], "shadow fill component alpha"))
        != float32_bits(expected_alpha)
    ):
        raise ValueError("shadow matrix fill-color law differs")
    offset = mapping(values.get("inputShadowOffset"), "shadow offset")
    encoded_offset = sequence(offset.get("float32LittleEndian"), "shadow offset words")
    if (
        offset.get("objCType") != "{CGSize=dd}"
        or offset.get("lengthBytes") != 16
        or list(encoded_offset) != [0, 0, 0, 2.5]
    ):
        raise ValueError("shadow offset differs")
    return 20


def analyze(timeline_paths: Sequence[Path], *, run_id: int) -> dict[str, Any]:
    if run_id <= 0:
        raise ValueError("run ID must be positive")
    geometry_names: set[str] = set()
    inputs: list[dict[str, Any]] = []
    state_count = 0
    predicted_components = 0
    predicted_mismatches = 0
    nonnumeric_components = 0
    clamp_values: list[dict[str, Any]] = []
    predicted_field_names: set[str] | None = None

    for timeline_path in sorted(timeline_paths):
        report = mapping(
            json.loads(timeline_path.read_text(encoding="utf-8")),
            "transition timeline",
        )
        geometry = mapping(report.get("geometry"), "geometry")
        geometry_name = geometry.get("name")
        if (
            not isinstance(geometry_name, str)
            or geometry_name not in EXPECTED_GEOMETRIES
        ):
            raise ValueError(f"unexpected geometry: {geometry_name!r}")
        if geometry_name in geometry_names:
            raise ValueError(f"duplicate geometry: {geometry_name}")
        geometry_names.add(geometry_name)
        uniforms = mapping(
            report.get("dynamicBackgroundUniforms"),
            "dynamic background uniforms",
        )
        records = sequence(uniforms.get("records"), "dynamic background records")
        indices = tuple(
            int(mapping(record, "dynamic background record")["sampleIndex"])
            for record in records
        )
        if indices != EXPECTED_SAMPLE_INDICES:
            raise ValueError(f"sample indices differ for {geometry_name}")

        for untyped_record in records:
            record = mapping(untyped_record, "dynamic background record")
            sample_index = int(record["sampleIndex"])
            remaining = numeric(record.get("remaining"), "remaining")
            background_filter = mapping(record.get("filter"), "background filter")
            values = mapping(
                background_filter.get("inputValues"),
                "background filter values",
            )
            prediction = predicted_numeric_fields(geometry, remaining)
            current_names = set(prediction)
            if predicted_field_names is None:
                predicted_field_names = current_names
            elif current_names != predicted_field_names:
                raise ValueError("predicted numeric field set changed")
            observed_numeric_names = {
                name
                for name, value in values.items()
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            }
            if observed_numeric_names != current_names | UNKNOWN_NUMERIC_FIELDS:
                raise ValueError("numeric background-filter field set differs")
            for field, predicted in prediction.items():
                observed = numeric(values.get(field), field)
                predicted_components += 1
                predicted_mismatches += float32_bits(predicted) != float32_bits(
                    observed
                )
            nonnumeric_components += validate_nonnumeric_fields(values, remaining)
            clamp_values.append(
                {
                    "geometry": geometry_name,
                    "sampleIndex": sample_index,
                    "remaining": remaining,
                    "observed": numeric(values.get("inputClamp"), "inputClamp"),
                }
            )
        state_count += len(records)
        inputs.append(
            {
                "geometry": geometry_name,
                "timelineArtifact": timeline_path.parent.name
                + "/"
                + timeline_path.name,
                "timelineSHA256": sha256_file(timeline_path),
            }
        )

    if geometry_names != EXPECTED_GEOMETRIES:
        missing = sorted(EXPECTED_GEOMETRIES - geometry_names)
        extra = sorted(geometry_names - EXPECTED_GEOMETRIES)
        raise ValueError(f"geometry set differs; missing={missing}, extra={extra}")
    if predicted_field_names is None:
        raise ValueError("no background-filter records were analyzed")
    return {
        "dynamicBackgroundFilterLawAnalysisSchemaVersion": 1,
        "classification": (
            "post-opening-retrospective-clear-light-temporal-law-analysis"
        ),
        "runID": run_id,
        "inputs": inputs,
        "aggregate": {
            "geometryCount": len(geometry_names),
            "stateCount": state_count,
            "numericFieldCount": len(predicted_field_names)
            + len(UNKNOWN_NUMERIC_FIELDS),
            "predictedNumericFieldCount": len(predicted_field_names),
            "predictedNumericBinary32": {
                "componentCount": predicted_components,
                "mismatchedComponents": predicted_mismatches,
                "exact": predicted_mismatches == 0,
            },
            "constantAndStructuredNonnumeric": {
                "componentCount": nonnumeric_components,
                "mismatchedComponents": 0,
                "exact": True,
            },
            "unrecoveredNumericFields": sorted(UNKNOWN_NUMERIC_FIELDS),
            "inputClampDiagnostic": clamp_values,
        },
        "recoveredStructure": {
            "effectiveDiameter": "G = k * (requestedDiameter + 16 * (1 - k))",
            "geometryFields": {
                "inputBlurDistance0": "-G/2",
                "inputOuterRefractionAmount": "G/5",
                "inputOuterRefractionHeight": "G/8",
                "inputShadowHeight": "2*G/5",
            },
            "blurWeight": (
                "w = float32(k * float32Mix(0.2, 0.5, k)); "
                "opacities 1/2 are w and 3/4 are float32(2*w)"
            ),
            "maxHeadroom": "float32Mix(1.2, 9999, k)",
        },
        "conclusion": {
            "clearLightNumericBackgroundInputsRecoveredAtMetalPrecision": (
                predicted_mismatches == 0
            ),
            "completeBackgroundInputLawRecovered": False,
            "remainingNumericField": "inputClamp",
            "requiresUnseenTemporalHoldout": True,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    timelines = sorted(arguments.artifact_root.glob("*/transition-timeline.json"))
    result = analyze(timelines, run_id=arguments.run_id)
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")
        print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
