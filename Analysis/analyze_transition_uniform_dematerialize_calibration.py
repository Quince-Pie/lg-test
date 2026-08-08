#!/usr/bin/env python3
"""Analyze four-profile dematerialize uniforms at exact binary32 precision."""

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import analyze_transition_uniform_profile_calibration as materialize


RESULT_SCHEMA_VERSION = 1
CLASSIFICATION = (
    "opened four-profile dematerialize calibration of the complete numeric "
    "glassBackground input model; no prospective transfer authority"
)
EXPECTED_TIMELINE_SCHEMA_VERSION = 5
EXPECTED_DYNAMIC_EVIDENCE_MODE = "allocation-metadata-v1"
EXPECTED_DYNAMIC_SAMPLE_INDICES = tuple(range(1, 32))
EXPECTED_BINARY_SHA256 = (
    "6711ec851453405e2c19a1f731465f1f40b1db1b05f1bd5cd3835a3974cc351d"
)
EXPECTED_NATIVE_CLAMP_SOURCE_SHA256 = (
    "c6ade2038ce727da44a978869d3f6407a156c8f9d0db8f2fb0aa22d7b984cba2"
)
NATIVE_CLAMP_CLASSIFICATION = (
    "native Darwin.powf four-profile dematerialize opened calibration; "
    "no prospective transfer authority"
)


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
        name="clear-light-circle453",
        material="clear",
        appearance="light",
        geometry="circle-453-center",
        diameter=453,
        timeline_sha256=(
            "395def791d64757b1a8954f54cfad08b8398ea780a4ed90ce670ae94a21d65e9"
        ),
    ),
    CalibrationCase(
        name="clear-dark-circle461",
        material="clear",
        appearance="dark",
        geometry="circle-461-center",
        diameter=461,
        timeline_sha256=(
            "17826c6d978362f048208ca663164c51e0a8a2a8a1fcf4b3cd07f90383d38be1"
        ),
    ),
    CalibrationCase(
        name="regular-light-circle469",
        material="regular",
        appearance="light",
        geometry="circle-469-center",
        diameter=469,
        timeline_sha256=(
            "297305a3dd4dc5f65679e7a11144a6ddb91a25eea64670419b6739a82e6ff9f8"
        ),
    ),
    CalibrationCase(
        name="regular-dark-circle477",
        material="regular",
        appearance="dark",
        geometry="circle-477-center",
        diameter=477,
        timeline_sha256=(
            "888568d228ee967a7525a1febf833bb1411757599d58362efd7635fabbb864df"
        ),
    ),
)


def load_native_clamp_result(path: Path) -> Mapping[str, Any]:
    result = materialize.mapping(
        json.loads(path.read_text(encoding="utf-8")), "native clamp result"
    )
    if (
        result.get("transitionUniformDematerializeClampCalibrationSchemaVersion")
        != 1
        or result.get("classification") != NATIVE_CLAMP_CLASSIFICATION
        or result.get("sourceSHA256") != EXPECTED_NATIVE_CLAMP_SOURCE_SHA256
        or result.get("comparisonCount") != 124
        or result.get("exactMatchCount") != 124
        or result.get("allCandidateWordsExact") is not True
    ):
        raise materialize.AnalysisError("native dematerialize clamp contract differs")
    return result


def native_clamp_records_by_case(
    result: Mapping[str, Any],
) -> dict[str, Mapping[int, Mapping[str, Any]]]:
    untyped_cases = result.get("cases")
    if not isinstance(untyped_cases, list):
        raise materialize.AnalysisError("native clamp cases are absent")
    cases: dict[str, Mapping[int, Mapping[str, Any]]] = {}
    for untyped_case in untyped_cases:
        case = materialize.mapping(untyped_case, "native clamp case")
        name = case.get("name")
        records = case.get("records")
        if not isinstance(name, str) or not isinstance(records, list):
            raise materialize.AnalysisError("native clamp case shape differs")
        indexed: dict[int, Mapping[str, Any]] = {}
        for untyped_record in records:
            record = materialize.mapping(untyped_record, "native clamp record")
            sample_index = record.get("sampleIndex")
            if not isinstance(sample_index, int) or isinstance(sample_index, bool):
                raise materialize.AnalysisError("native clamp sample index differs")
            if sample_index in indexed:
                raise materialize.AnalysisError("native clamp sample is duplicated")
            indexed[sample_index] = record
        if tuple(sorted(indexed)) != EXPECTED_DYNAMIC_SAMPLE_INDICES:
            raise materialize.AnalysisError("native clamp sample coverage differs")
        cases[name] = indexed
    if set(cases) != {case.name for case in CALIBRATION_CASES}:
        raise materialize.AnalysisError("native clamp profile coverage differs")
    return cases


def analyze_case(
    case: CalibrationCase,
    path: Path,
    clamp_records: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    if materialize.sha256_file(path) != case.timeline_sha256:
        raise materialize.AnalysisError(f"{case.name} timeline SHA-256 differs")
    timeline = materialize.mapping(
        json.loads(path.read_text(encoding="utf-8")), case.name
    )
    geometry = materialize.mapping(timeline.get("geometry"), f"{case.name} geometry")
    uniforms = materialize.mapping(
        timeline.get("dynamicBackgroundUniforms"), f"{case.name} uniforms"
    )
    records = uniforms.get("records")
    if (
        timeline.get("schemaVersion") != EXPECTED_TIMELINE_SCHEMA_VERSION
        or timeline.get("material") != case.material
        or timeline.get("appearance") != case.appearance
        or timeline.get("direction") != "dematerialize"
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
        or uniforms.get("sampleIndices") != list(EXPECTED_DYNAMIC_SAMPLE_INDICES)
        or uniforms.get("sampleCount") != 31
        or uniforms.get("executedSampleCount") != 31
        or not isinstance(records, list)
        or len(records) != 31
    ):
        raise materialize.AnalysisError(f"{case.name} capture contract differs")

    field_matches = {field: 0 for field in materialize.NUMERIC_FIELDS}
    structured_matches = 0
    summarized_records: list[dict[str, Any]] = []
    for expected_index, untyped_record in zip(
        EXPECTED_DYNAMIC_SAMPLE_INDICES, records, strict=True
    ):
        record = materialize.mapping(
            untyped_record, f"{case.name} record {expected_index}"
        )
        if record.get("sampleIndex") != expected_index:
            raise materialize.AnalysisError(f"{case.name} sample sequence differs")
        fraction = materialize.numeric(record.get("remaining"), "remaining")
        if materialize.float32(fraction) != fraction or not 0.0 < fraction < 1.0:
            raise materialize.AnalysisError(
                f"{case.name} fraction is not a valid binary32 dynamic state"
            )
        filter_value = materialize.mapping(record.get("filter"), "background filter")
        inputs = materialize.mapping(
            filter_value.get("inputValues"), "background inputs"
        )
        observed_numeric = {
            key: materialize.numeric(value, key)
            for key, value in inputs.items()
            if isinstance(value, int | float) and not isinstance(value, bool)
        }
        if tuple(sorted(observed_numeric)) != tuple(
            sorted(materialize.NUMERIC_FIELDS)
        ):
            raise materialize.AnalysisError(
                f"{case.name} numeric field inventory differs"
            )
        predicted = materialize.predict_numeric_fields(
            material=case.material,
            appearance=case.appearance,
            diameter=case.diameter,
            fraction=fraction,
        )
        mismatches: list[dict[str, str]] = []
        for field in materialize.PREDICTED_PYTHON_FIELDS:
            observed_bits = materialize.float32_bits(observed_numeric[field])
            predicted_bits = materialize.float32_bits(predicted[field])
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
        observed_clamp_bits = materialize.float32_bits(
            observed_numeric[materialize.CLAMP_FIELD]
        )
        if (
            clamp.get("observedBits") != observed_clamp_bits
            or clamp.get("candidateBits") != observed_clamp_bits
            or clamp.get("exact") is not True
        ):
            mismatches.append(
                {
                    "field": materialize.CLAMP_FIELD,
                    "observedBits": observed_clamp_bits,
                    "predictedBits": str(clamp.get("candidateBits")),
                }
            )
        else:
            field_matches[materialize.CLAMP_FIELD] += 1
        if mismatches:
            raise materialize.AnalysisError(
                f"{case.name} sample {expected_index} numeric mismatch: {mismatches}"
            )
        materialize.validate_structured_fields(
            inputs,
            material=case.material,
            appearance=case.appearance,
            fraction=fraction,
        )
        structured_matches += 1
        summarized_records.append(
            {
                "sampleIndex": expected_index,
                "fractionBits": materialize.float32_bits(fraction),
                "inputClampBaseBits": clamp.get("baseBits"),
                "inputClampBits": observed_clamp_bits,
            }
        )

    if set(field_matches.values()) != {31}:
        raise materialize.AnalysisError(f"{case.name} field match counts differ")
    return {
        "name": case.name,
        "material": case.material,
        "appearance": case.appearance,
        "direction": "dematerialize",
        "geometry": case.geometry,
        "diameter": case.diameter,
        "timelineSHA256": case.timeline_sha256,
        "dynamicSampleCount": len(records),
        "numericFieldCount": len(materialize.NUMERIC_FIELDS),
        "numericComparisonCount": len(materialize.NUMERIC_FIELDS) * len(records),
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
        raise materialize.AnalysisError("timeline case set differs")
    clamp_result = load_native_clamp_result(native_clamp_result_path)
    clamp_cases = native_clamp_records_by_case(clamp_result)
    cases = [
        analyze_case(case, timeline_paths[case.name], clamp_cases[case.name])
        for case in CALIBRATION_CASES
    ]
    comparison_count = sum(case["numericComparisonCount"] for case in cases)
    exact_match_count = sum(case["numericExactMatchCount"] for case in cases)
    if comparison_count != 5_828 or exact_match_count != comparison_count:
        raise materialize.AnalysisError("dematerialize numeric aggregate differs")
    return {
        "transitionUniformDematerializeCalibrationAnalysisSchemaVersion": (
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
            "sha256": materialize.sha256_file(native_clamp_result_path),
            "sourceSHA256": clamp_result.get("sourceSHA256"),
            "comparisonCount": clamp_result.get("comparisonCount"),
        },
        "model": {
            "directionLaw": (
                "the materialize 47-field model evaluated at the exact captured "
                "binary32 remaining fraction k"
            ),
            "numericFieldCount": len(materialize.NUMERIC_FIELDS),
            "pythonPredictedFieldCount": len(materialize.PREDICTED_PYTHON_FIELDS),
            "nativeDarwinPowfField": materialize.CLAMP_FIELD,
            "comparisonPrecision": "IEEE-754 binary32 words",
        },
        "aggregate": {
            "profileCount": len(cases),
            "dynamicSampleCount": sum(case["dynamicSampleCount"] for case in cases),
            "numericComparisonCount": comparison_count,
            "numericExactMatchCount": exact_match_count,
            "numericMismatchCount": 0,
            "nonClampComparisonCount": 5_704,
            "nativeClampComparisonCount": 124,
            "structuredRecordCount": sum(
                case["structuredRecordCount"] for case in cases
            ),
        },
        "cases": cases,
        "conclusion": {
            "openedCalibrationExact": True,
            "sameLawAsFunctionOfRemainingFraction": True,
            "prospectiveDematerializeTransferEstablished": False,
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
            raise materialize.AnalysisError(
                "each --case must be a unique NAME=PATH"
            )
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
