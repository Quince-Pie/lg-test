#!/usr/bin/env python3
"""Analyze four-profile materialize uniform calibration at binary32 precision."""

import argparse
import hashlib
import json
import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RESULT_SCHEMA_VERSION = 1
CLASSIFICATION = (
    "opened four-profile materialize calibration of the complete numeric "
    "glassBackground input model; no prospective transfer authority"
)
EXPECTED_TIMELINE_SCHEMA_VERSION = 5
EXPECTED_DYNAMIC_EVIDENCE_MODE = "allocation-metadata-v1"
EXPECTED_DYNAMIC_SAMPLE_INDICES = tuple(range(1, 33))
EXPECTED_BINARY_SHA256 = (
    "b9cb4068e77a61ff87794fa20a5c273e007f3ee20dd74503b1ab78839104e8dd"
)
CLAMP_FIELD = "inputClamp"


@dataclass(frozen=True, slots=True, kw_only=True)
class CalibrationCase:
    name: str
    material: str
    appearance: str
    geometry: str
    diameter: int
    timeline_sha256: str


CALIBRATION_CASES = (
    CalibrationCase(
        name="clear-light-circle451",
        material="clear",
        appearance="light",
        geometry="circle-451-center",
        diameter=451,
        timeline_sha256=(
            "20390dd67902eb8411e1d368fdb1f112d49714ba5c630a0ffc744ec040c0f54a"
        ),
    ),
    CalibrationCase(
        name="clear-dark-circle459",
        material="clear",
        appearance="dark",
        geometry="circle-459-center",
        diameter=459,
        timeline_sha256=(
            "ae643a8dbab081ce95153533c6119926be97eb04e12ce2c9e4bdfb7113a66280"
        ),
    ),
    CalibrationCase(
        name="regular-light-circle467",
        material="regular",
        appearance="light",
        geometry="circle-467-center",
        diameter=467,
        timeline_sha256=(
            "c83c91e2bdf32ff82fb303a25179f4d705e9c9e9aa0426475fa5fe51a9e2c8b3"
        ),
    ),
    CalibrationCase(
        name="regular-dark-circle475",
        material="regular",
        appearance="dark",
        geometry="circle-475-center",
        diameter=475,
        timeline_sha256=(
            "387f609c8bc1d98386ae84318590294673e47680193e5bfb20eea349d6e8daff"
        ),
    ),
)


@dataclass(frozen=True, slots=True, kw_only=True)
class Profile:
    face_black: float
    face_saturation: float
    face_white: float
    bleed_black: float
    bleed_saturation: float
    bleed_white: float
    shadow_black: float
    shadow_saturation: float
    shadow_white: float
    bleed_opacity: float


PROFILES = {
    ("clear", "light"): Profile(
        face_black=0.075,
        face_saturation=1.06,
        face_white=1.15,
        bleed_black=0.75,
        bleed_saturation=1.2,
        bleed_white=1.0,
        shadow_black=0.0,
        shadow_saturation=1.2,
        shadow_white=1.0,
        bleed_opacity=0.0,
    ),
    ("clear", "dark"): Profile(
        face_black=0.075,
        face_saturation=1.06,
        face_white=1.15,
        bleed_black=0.75,
        bleed_saturation=1.2,
        bleed_white=1.0,
        shadow_black=0.0,
        shadow_saturation=1.2,
        shadow_white=1.0,
        bleed_opacity=0.0,
    ),
    ("regular", "light"): Profile(
        face_black=0.5,
        face_saturation=1.0,
        face_white=1.03,
        bleed_black=0.9,
        bleed_saturation=1.2,
        bleed_white=1.0,
        shadow_black=0.0,
        shadow_saturation=1.8,
        shadow_white=1.0,
        bleed_opacity=0.5,
    ),
    ("regular", "dark"): Profile(
        face_black=0.2,
        face_saturation=1.0,
        face_white=0.6,
        bleed_black=0.0,
        bleed_saturation=1.0,
        bleed_white=0.5,
        shadow_black=0.0,
        shadow_saturation=1.0,
        shadow_white=0.5,
        bleed_opacity=0.8,
    ),
}


NUMERIC_FIELDS = (
    "inputBleedAmount",
    "inputBleedBlurRadius",
    "inputBleedColorMatrixBlack",
    "inputBleedColorMatrixSaturation",
    "inputBleedColorMatrixWhite",
    "inputBleedDistance0",
    "inputBleedDistance1",
    "inputBleedHeight",
    "inputBleedOpacity",
    "inputBlurDistance0",
    "inputBlurDistance1",
    "inputBlurDistance2",
    "inputBlurDistance3",
    "inputBlurDistance4",
    "inputBlurOpacity0",
    "inputBlurOpacity1",
    "inputBlurOpacity2",
    "inputBlurOpacity3",
    "inputBlurOpacity4",
    "inputBlurRadius",
    CLAMP_FIELD,
    "inputFaceColorMatrixBlack",
    "inputFaceColorMatrixSaturation",
    "inputFaceColorMatrixWhite",
    "inputFaceOpacity",
    "inputInnerRefractionAmount",
    "inputInnerRefractionHeight",
    "inputMaxHeadroom",
    "inputOuterRefractionAmount",
    "inputOuterRefractionHeight",
    "inputRefractionDistance0",
    "inputRefractionDistance1",
    "inputRefractionOpacity",
    "inputSDRGradientDistance0",
    "inputSDRGradientDistance1",
    "inputSDRHoldingToneWhite",
    "inputSDRShadowOpacity",
    "inputShadowAmount",
    "inputShadowBlurRadius",
    "inputShadowColorMatrixBlack",
    "inputShadowColorMatrixSaturation",
    "inputShadowColorMatrixWhite",
    "inputShadowDistanceOffset",
    "inputShadowHeight",
    "inputShadowOpacity",
    "inputShadowRadius",
    "inputShadowVibrancyContribution",
)
PREDICTED_PYTHON_FIELDS = tuple(
    field for field in NUMERIC_FIELDS if field != CLAMP_FIELD
)


class AnalysisError(RuntimeError):
    """Raised when calibration evidence differs from its frozen contract."""


def mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AnalysisError(f"{name} is not an object")
    return value


def numeric(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise AnalysisError(f"{name} is not numeric")
    return float(value)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def float32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def float32_bits(value: float) -> str:
    return f"{struct.unpack('<I', struct.pack('<f', value))[0]:08x}"


def float32_multiply(left: float, right: float) -> float:
    return float32(float32(left) * float32(right))


def float32_add(left: float, right: float) -> float:
    return float32(float32(left) + float32(right))


def float32_mix(start: float, end: float, fraction: float) -> float:
    fraction = float32(fraction)
    start_weight = float32(1.0 - fraction)
    start_product = float32_multiply(start_weight, start)
    end_product = float32_multiply(fraction, end)
    return float32_add(start_product, end_product)


def predict_numeric_fields(
    *, material: str, appearance: str, diameter: int, fraction: float
) -> dict[str, float]:
    try:
        profile = PROFILES[(material, appearance)]
    except KeyError as error:
        raise AnalysisError(f"unsupported profile {material}/{appearance}") from error
    if diameter <= 0:
        raise AnalysisError("geometry diameter must be positive")

    fraction = float32(fraction)
    geometry = fraction * (float(diameter) + 16.0 * (1.0 - fraction))
    blur_weight = float32_multiply(fraction, float32_mix(0.2, 0.5, fraction))
    doubled_blur_weight = float32_multiply(2.0, blur_weight)
    regular = material == "regular"

    predicted = {
        "inputBleedAmount": 0.35 * geometry if regular else 0.0,
        "inputBleedBlurRadius": float32_multiply(160.0, fraction) if regular else 0.0,
        "inputBleedColorMatrixBlack": float32_mix(0.0, profile.bleed_black, fraction),
        "inputBleedColorMatrixSaturation": float32_mix(
            1.0, profile.bleed_saturation, fraction
        ),
        "inputBleedColorMatrixWhite": float32_mix(1.0, profile.bleed_white, fraction),
        "inputBleedDistance0": fraction,
        "inputBleedDistance1": 0.0,
        "inputBleedHeight": 0.35 * geometry if regular else 0.0,
        "inputBleedOpacity": float32_mix(0.0, profile.bleed_opacity, fraction),
        "inputBlurDistance0": -geometry / 2.0,
        "inputBlurDistance1": -fraction,
        "inputBlurDistance2": 0.0,
        "inputBlurDistance3": 0.0,
        "inputBlurDistance4": geometry / 5.0 if regular else 0.0,
        "inputBlurOpacity0": fraction,
        "inputBlurOpacity1": blur_weight,
        "inputBlurOpacity2": blur_weight,
        "inputBlurOpacity3": doubled_blur_weight,
        "inputBlurOpacity4": doubled_blur_weight,
        "inputBlurRadius": float32_multiply(4.0 if regular else 1.0, fraction),
        "inputFaceColorMatrixBlack": float32_mix(0.0, profile.face_black, fraction),
        "inputFaceColorMatrixSaturation": float32_mix(
            1.0, profile.face_saturation, fraction
        ),
        "inputFaceColorMatrixWhite": float32_mix(1.0, profile.face_white, fraction),
        "inputFaceOpacity": fraction,
        "inputInnerRefractionAmount": float32_multiply(-60.0, fraction),
        "inputInnerRefractionHeight": float32_multiply(20.0, fraction),
        "inputMaxHeadroom": float32_mix(1.2, 9999.0, fraction),
        "inputOuterRefractionAmount": geometry / 5.0,
        "inputOuterRefractionHeight": geometry / 8.0,
        "inputRefractionDistance0": -fraction,
        "inputRefractionDistance1": -fraction / 2.0,
        "inputRefractionOpacity": float32_mix(0.0, 0.3, fraction) if regular else 0.0,
        "inputSDRGradientDistance0": -fraction,
        "inputSDRGradientDistance1": -fraction / 2.0,
        "inputSDRHoldingToneWhite": float32_mix(1.0, 0.97, fraction),
        "inputSDRShadowOpacity": float32_mix(0.0, 0.24, fraction),
        "inputShadowAmount": float32_multiply(75.0, fraction),
        "inputShadowBlurRadius": float32_multiply(40.0, fraction) if regular else 0.0,
        "inputShadowColorMatrixBlack": float32_mix(0.0, profile.shadow_black, fraction),
        "inputShadowColorMatrixSaturation": float32_mix(
            1.0, profile.shadow_saturation, fraction
        ),
        "inputShadowColorMatrixWhite": float32_mix(1.0, profile.shadow_white, fraction),
        "inputShadowDistanceOffset": 0.0,
        "inputShadowHeight": 2.0 * geometry / 5.0,
        "inputShadowOpacity": float32_mix(0.0, 0.25, fraction) if regular else 0.0,
        "inputShadowRadius": float32_multiply(24.0, fraction) if regular else 0.0,
        "inputShadowVibrancyContribution": fraction if regular else 0.0,
    }
    if tuple(predicted) != PREDICTED_PYTHON_FIELDS:
        raise AssertionError("numeric predictor field order differs")
    return predicted


def validate_structured_fields(
    inputs: Mapping[str, Any], *, material: str, appearance: str, fraction: float
) -> None:
    if (
        inputs.get("inputBleedColorMatrixFillColor") is not None
        or inputs.get("inputClampPreserveHue") is not False
        or inputs.get("inputSDRHoldingToneEnabled") is not True
        or inputs.get("inputSourceSublayerName") != "@0"
    ):
        raise AnalysisError("common structured input law differs")
    shadow_offset = mapping(inputs.get("inputShadowOffset"), "shadow offset")
    if (
        shadow_offset.get("hex") != "00000000000000000000000000002040"
        or shadow_offset.get("objCType") != "{CGSize=dd}"
        or shadow_offset.get("lengthBytes") != 16
    ):
        raise AnalysisError("exact [0,8] shadow offset differs")

    expected_darken = appearance == "light" or (
        material == "clear" and fraction >= float32(0.5)
    )
    if inputs.get("inputBleedDarkenBlend") is not expected_darken:
        raise AnalysisError("edge-darken profile law differs")

    face = inputs.get("inputFaceColorMatrixFillColor")
    shadow = inputs.get("inputShadowColorMatrixFillColor")
    if material == "clear":
        if (face is None) != (fraction < 1.0):
            raise AnalysisError("clear face fill optionality differs")
        if face is not None:
            validate_color(face, expected_components=(1.0, 1.0, 1.0, 0.0))
        validate_color(
            shadow,
            expected_components=(
                0.0,
                0.0,
                0.0,
                float32_mix(0.0, 0.1, fraction),
            ),
        )
    else:
        if face is None:
            raise AnalysisError("regular face fill is absent")
        face_color = mapping(face, "regular face fill")
        face_components = face_color.get("components")
        if not isinstance(face_components, list) or len(face_components) != 4:
            raise AnalysisError("regular face fill components differ")
        expected_face_alpha = float32_mix(0.0, 0.4, fraction)
        if float32_bits(numeric(face_components[3], "face alpha")) != float32_bits(
            expected_face_alpha
        ):
            raise AnalysisError("regular face alpha differs")
        validate_color_metadata(face_color)
        if appearance == "dark":
            if any(
                float32_bits(numeric(value, "face RGB")) != "00000000"
                for value in face_components[:3]
            ):
                raise AnalysisError("regular-dark face RGB differs")
            if shadow is not None:
                raise AnalysisError("regular-dark shadow fill is present")
        else:
            for value in face_components[:3]:
                component = numeric(value, "face RGB")
                if not 0.999999 <= component <= 1.0:
                    raise AnalysisError(
                        "regular-light face RGB leaves proved mixer range"
                    )
            validate_color(
                shadow,
                expected_components=(
                    0.0,
                    0.0,
                    0.0,
                    float32_mix(0.0, 0.12, fraction),
                ),
            )


def validate_color_metadata(color: Mapping[str, Any]) -> None:
    if (
        color.get("class") != "__NSCFType"
        or color.get("colorSpaceName") != "kCGColorSpaceExtendedSRGB"
        or color.get("numberOfComponents") != 4
    ):
        raise AnalysisError("resolved color metadata differs")


def validate_color(value: object, *, expected_components: Sequence[float]) -> None:
    color = mapping(value, "resolved color")
    validate_color_metadata(color)
    components = color.get("components")
    if not isinstance(components, list) or len(components) != len(expected_components):
        raise AnalysisError("resolved color component count differs")
    for index, (observed, expected) in enumerate(
        zip(components, expected_components, strict=True)
    ):
        if float32_bits(numeric(observed, f"color component {index}")) != float32_bits(
            expected
        ):
            raise AnalysisError(f"resolved color component {index} differs")
    if float32_bits(numeric(color.get("alpha"), "color alpha")) != float32_bits(
        expected_components[3]
    ):
        raise AnalysisError("resolved color alpha differs")


def load_native_clamp_result(path: Path) -> Mapping[str, Any]:
    result = mapping(
        json.loads(path.read_text(encoding="utf-8")), "native clamp result"
    )
    if (
        result.get("transitionUniformProfileClampAnalysisSchemaVersion") != 1
        or result.get("classification")
        != "native Darwin.powf four-profile opened calibration"
        or result.get("allCandidateWordsExact") is not True
    ):
        raise AnalysisError("native clamp result contract differs")
    return result


def native_clamp_records_by_case(
    result: Mapping[str, Any],
) -> dict[str, Mapping[int, Mapping[str, Any]]]:
    untyped_cases = result.get("cases")
    if not isinstance(untyped_cases, list):
        raise AnalysisError("native clamp cases are absent")
    cases: dict[str, Mapping[int, Mapping[str, Any]]] = {}
    for untyped_case in untyped_cases:
        case = mapping(untyped_case, "native clamp case")
        name = case.get("name")
        records = case.get("records")
        if not isinstance(name, str) or not isinstance(records, list):
            raise AnalysisError("native clamp case shape differs")
        indexed: dict[int, Mapping[str, Any]] = {}
        for untyped_record in records:
            record = mapping(untyped_record, "native clamp record")
            sample_index = record.get("sampleIndex")
            if not isinstance(sample_index, int) or isinstance(sample_index, bool):
                raise AnalysisError("native clamp sample index differs")
            indexed[sample_index] = record
        if tuple(sorted(indexed)) != EXPECTED_DYNAMIC_SAMPLE_INDICES:
            raise AnalysisError("native clamp sample coverage differs")
        cases[name] = indexed
    if set(cases) != {case.name for case in CALIBRATION_CASES}:
        raise AnalysisError("native clamp profile coverage differs")
    return cases


def analyze_case(
    case: CalibrationCase,
    path: Path,
    clamp_records: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    if sha256_file(path) != case.timeline_sha256:
        raise AnalysisError(f"{case.name} timeline SHA-256 differs")
    timeline = mapping(json.loads(path.read_text(encoding="utf-8")), case.name)
    geometry = mapping(timeline.get("geometry"), f"{case.name} geometry")
    uniforms = mapping(
        timeline.get("dynamicBackgroundUniforms"), f"{case.name} uniforms"
    )
    records = uniforms.get("records")
    if (
        timeline.get("schemaVersion") != EXPECTED_TIMELINE_SCHEMA_VERSION
        or timeline.get("material") != case.material
        or timeline.get("appearance") != case.appearance
        or timeline.get("direction") != "materialize"
        or timeline.get("sampleCount") != 33
        or timeline.get("sampleProgressRule") != "index/(sampleCount-1)"
        or timeline.get("windowBackingScaleFactor") != 2
        or timeline.get("expectedWindowPixels") != [2048, 2048]
        or geometry.get("name") != case.geometry
        or geometry.get("shape") != "circle"
        or geometry.get("width") != case.diameter
        or geometry.get("height") != case.diameter
        or uniforms.get("requested") is not True
        or uniforms.get("executed") is not True
        or uniforms.get("evidenceMode") != EXPECTED_DYNAMIC_EVIDENCE_MODE
        or uniforms.get("executedSampleCount") != 32
        or not isinstance(records, list)
        or len(records) != 32
    ):
        raise AnalysisError(f"{case.name} capture contract differs")

    field_matches = {field: 0 for field in NUMERIC_FIELDS}
    structured_matches = 0
    summarized_records: list[dict[str, Any]] = []
    for expected_index, untyped_record in zip(
        EXPECTED_DYNAMIC_SAMPLE_INDICES, records, strict=True
    ):
        record = mapping(untyped_record, f"{case.name} record {expected_index}")
        if record.get("sampleIndex") != expected_index:
            raise AnalysisError(f"{case.name} sample sequence differs")
        fraction = numeric(record.get("remaining"), "remaining")
        if float32(fraction) != fraction or not 0.0 < fraction <= 1.0:
            raise AnalysisError(f"{case.name} fraction is not a valid binary32 state")
        filter_value = mapping(record.get("filter"), "background filter")
        inputs = mapping(filter_value.get("inputValues"), "background inputs")
        observed_numeric = {
            key: numeric(value, key)
            for key, value in inputs.items()
            if isinstance(value, int | float) and not isinstance(value, bool)
        }
        if tuple(sorted(observed_numeric)) != tuple(sorted(NUMERIC_FIELDS)):
            raise AnalysisError(f"{case.name} numeric field inventory differs")
        predicted = predict_numeric_fields(
            material=case.material,
            appearance=case.appearance,
            diameter=case.diameter,
            fraction=fraction,
        )
        mismatches: list[dict[str, str]] = []
        for field in PREDICTED_PYTHON_FIELDS:
            observed_bits = float32_bits(observed_numeric[field])
            predicted_bits = float32_bits(predicted[field])
            if observed_bits != predicted_bits:
                mismatches.append(
                    {
                        "field": field,
                        "observedBits": observed_bits,
                        "predictedBits": predicted_bits,
                    }
                )
            else:
                field_matches[field] += 1

        clamp = clamp_records[expected_index]
        observed_clamp_bits = float32_bits(observed_numeric[CLAMP_FIELD])
        if (
            clamp.get("observedBits") != observed_clamp_bits
            or clamp.get("candidateBits") != observed_clamp_bits
            or clamp.get("exact") is not True
        ):
            mismatches.append(
                {
                    "field": CLAMP_FIELD,
                    "observedBits": observed_clamp_bits,
                    "predictedBits": str(clamp.get("candidateBits")),
                }
            )
        else:
            field_matches[CLAMP_FIELD] += 1
        if mismatches:
            raise AnalysisError(
                f"{case.name} sample {expected_index} numeric mismatch: {mismatches}"
            )
        validate_structured_fields(
            inputs,
            material=case.material,
            appearance=case.appearance,
            fraction=fraction,
        )
        structured_matches += 1
        summarized_records.append(
            {
                "sampleIndex": expected_index,
                "fractionBits": float32_bits(fraction),
                "inputClampBits": observed_clamp_bits,
            }
        )

    if set(field_matches.values()) != {32}:
        raise AnalysisError(f"{case.name} field match counts differ")
    return {
        "name": case.name,
        "material": case.material,
        "appearance": case.appearance,
        "direction": "materialize",
        "geometry": case.geometry,
        "diameter": case.diameter,
        "timelineSHA256": case.timeline_sha256,
        "dynamicSampleCount": len(records),
        "numericFieldCount": len(NUMERIC_FIELDS),
        "numericComparisonCount": len(NUMERIC_FIELDS) * len(records),
        "numericExactMatchCount": sum(field_matches.values()),
        "structuredRecordCount": structured_matches,
        "fieldExactMatchCounts": field_matches,
        "records": summarized_records,
    }


def analyze(
    timeline_paths: Mapping[str, Path], native_clamp_result_path: Path
) -> dict[str, Any]:
    expected_names = {case.name for case in CALIBRATION_CASES}
    if set(timeline_paths) != expected_names:
        raise AnalysisError("timeline case set differs")
    clamp_result = load_native_clamp_result(native_clamp_result_path)
    clamp_cases = native_clamp_records_by_case(clamp_result)
    cases = [
        analyze_case(case, timeline_paths[case.name], clamp_cases[case.name])
        for case in CALIBRATION_CASES
    ]
    comparison_count = sum(case["numericComparisonCount"] for case in cases)
    exact_match_count = sum(case["numericExactMatchCount"] for case in cases)
    if comparison_count != 6016 or exact_match_count != comparison_count:
        raise AnalysisError("four-profile numeric aggregate differs")
    return {
        "transitionUniformProfileCalibrationAnalysisSchemaVersion": (
            RESULT_SCHEMA_VERSION
        ),
        "classification": CLASSIFICATION,
        "target": {
            "os": "macOS 26.6.1",
            "build": "25G76",
            "architecture": "arm64",
            "display": "built-in Retina 3456x2234 physical, 1728x1117 points, 2x",
            "captureBinarySHA256": EXPECTED_BINARY_SHA256,
        },
        "nativeClampResult": {
            "path": native_clamp_result_path.name,
            "sha256": sha256_file(native_clamp_result_path),
            "sourceSHA256": clamp_result.get("sourceSHA256"),
            "comparisonCount": clamp_result.get("comparisonCount"),
        },
        "model": {
            "numericFieldCount": len(NUMERIC_FIELDS),
            "pythonPredictedFieldCount": len(PREDICTED_PYTHON_FIELDS),
            "nativeDarwinPowfField": CLAMP_FIELD,
            "comparisonPrecision": "IEEE-754 binary32 words",
            "geometryTerm": "k * (D + 16 * (1 - k)) in binary64",
            "scalarMix": (
                "separately rounded binary32 products and binary32 add after "
                "binary32 rounding of 1-k"
            ),
            "historicalCorrection": {
                "inputRefractionDistance1": "-k/2",
                "inputSDRGradientDistance0": "-k",
                "inputSDRGradientDistance1": "-k/2",
            },
        },
        "aggregate": {
            "profileCount": len(cases),
            "dynamicSampleCount": sum(case["dynamicSampleCount"] for case in cases),
            "numericComparisonCount": comparison_count,
            "numericExactMatchCount": exact_match_count,
            "numericMismatchCount": 0,
            "structuredRecordCount": sum(
                case["structuredRecordCount"] for case in cases
            ),
        },
        "cases": cases,
        "conclusion": {
            "openedCalibrationExact": True,
            "prospectiveTransferEstablished": False,
            "dematerializeTransferEstablished": False,
            "physicalPixelParityEstablished": False,
            "independentWalleZeroByteFrameEstablished": False,
            "liquidGlassParityEstablished": False,
            "productionShaderChangeAuthorized": False,
        },
    }


def parse_case_arguments(values: Sequence[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        name, separator, path = value.partition("=")
        if not separator or not name or not path or name in result:
            raise AnalysisError("each --case must be a unique NAME=PATH")
        result[name] = Path(path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--native-clamp-result", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = analyze(
        parse_case_arguments(arguments.case), arguments.native_clamp_result
    )
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")
        print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
