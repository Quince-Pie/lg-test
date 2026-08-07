#!/usr/bin/env python3
"""Validate one corrected v2 materialize uniform holdout case."""

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import analyze_transition_uniform_profile_calibration as model
import validate_transition_uniform_profile_holdout as v1


VALIDATION_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 2
EXPECTED_CASES = {
    ("clear", "light", "circle-455-center"): ("clear-light-circle455", 455),
    ("clear", "dark", "circle-463-center"): ("clear-dark-circle463", 463),
    ("regular", "light", "circle-471-center"): (
        "regular-light-circle471",
        471,
    ),
    ("regular", "dark", "circle-479-center"): ("regular-dark-circle479", 479),
}
CALIBRATION_RESULT = Path(__file__).with_name(
    "transition_uniform_profile_calibration_result.json"
)
MODEL_SOURCE = Path(__file__).with_name(
    "analyze_transition_uniform_profile_calibration.py"
)
NATIVE_CLAMP_SOURCE = Path(__file__).with_name(
    "analyze_transition_uniform_profile_clamp_v2_local_macos_26_6_1.swift"
)


def validate_preregistration(
    path: Path, identity: tuple[str, str, str]
) -> tuple[Mapping[str, Any], str, int]:
    preregistration = v1.load_json(path, "v2 preregistration")
    v1.require(
        preregistration.get(
            "transitionUniformProfileHoldoutPreregistrationSchemaVersion"
        )
        == PREREGISTRATION_SCHEMA_VERSION,
        "v2 preregistration schema differs",
    )
    case_matrix = v1.sequence(preregistration.get("caseMatrix"), "v2 case matrix")
    observed_cases = {
        (case.get("material"), case.get("appearance"), case.get("geometry"))
        for untyped_case in case_matrix
        for case in [v1.mapping(untyped_case, "v2 holdout case")]
    }
    v1.require(
        observed_cases == set(EXPECTED_CASES) and len(case_matrix) == 4,
        "v2 four-profile matrix differs",
    )
    selected = [
        case
        for untyped_case in case_matrix
        for case in [v1.mapping(untyped_case, "v2 holdout case")]
        if (case.get("material"), case.get("appearance"), case.get("geometry"))
        == identity
    ]
    v1.require(len(selected) == 1, "runtime profile is not one frozen v2 case")
    selected_case = selected[0]
    case_name, diameter = EXPECTED_CASES[identity]
    v1.require(
        selected_case.get("caseId") == case_name
        and selected_case.get("direction") == "materialize"
        and selected_case.get("role") == "prospective-holdout-v2"
        and selected_case.get("appleOutputAvailableAtFreeze") is False
        and selected_case.get("timelineSHA256") is None
        and selected_case.get("numericFieldWords") is None
        and selected_case.get("inputClampWords") is None,
        "v2 holdout case was not frozen output-blind",
    )
    calibration = v1.mapping(
        preregistration.get("openedCalibrationEvidence"), "calibration evidence"
    )
    v1.require(
        calibration.get("path")
        == "Analysis/transition_uniform_profile_calibration_result.json"
        and calibration.get("sha256") == v1.sha256_file(CALIBRATION_RESULT)
        and calibration.get("numericComparisonCount") == 6_016
        and calibration.get("numericMismatchCount") == 0
        and calibration.get("prospectiveAuthority") is False,
        "v2 calibration evidence differs",
    )
    failure = v1.mapping(
        preregistration.get("v1FailureEvidence"), "v1 failure evidence"
    )
    v1.require(
        failure.get("path")
        == "Analysis/transition_uniform_profile_06150f0_v1_aggregate_failure_result.json"
        and failure.get("sha256")
        == v1.sha256_file(Path(__file__).with_name(failure["path"].split("/")[-1]))
        and failure.get("reason")
        == "common absent sample-zero endpoint invalidates global 132-image uniqueness",
        "v1 failure evidence differs",
    )
    implementation = v1.mapping(
        preregistration.get("frozenImplementation"), "v2 implementation"
    )
    v1.require(
        implementation.get("model")
        == "Analysis/analyze_transition_uniform_profile_calibration.py"
        and implementation.get("modelSHA256") == v1.sha256_file(MODEL_SOURCE)
        and implementation.get("nativeClamp")
        == "Analysis/analyze_transition_uniform_profile_clamp_v2_local_macos_26_6_1.swift"
        and implementation.get("nativeClampSHA256")
        == v1.sha256_file(NATIVE_CLAMP_SOURCE)
        and implementation.get("validator")
        == "Analysis/validate_transition_uniform_profile_holdout_v2.py"
        and implementation.get("validatorSHA256") == v1.sha256_file(Path(__file__)),
        "v2 frozen implementation differs",
    )
    acceptance = v1.mapping(preregistration.get("acceptance"), "v2 acceptance")
    v1.require(
        acceptance.get("numericComparisonCountAcrossMatrix") == 6_016
        and acceptance.get("requiredNumericMismatchCount") == 0
        and acceptance.get("expectedMatrixFrameCount") == 132
        and acceptance.get("expectedDistinctMatrixFrameCount") == 129
        and acceptance.get("expectedCommonAbsentEndpointCount") == 4
        and acceptance.get("requireOnlySampleZeroCrossCaseDuplicate") is True
        and acceptance.get("requireExactBinary32Words") is True
        and acceptance.get("requireNativeDarwinPowfClamp") is True
        and acceptance.get("requireAllFourCasesFromOneFrozenCommit") is True,
        "v2 acceptance contract differs",
    )
    return preregistration, case_name, diameter


def validate_native_clamp(
    path: Path, *, case_name: str, timeline_sha256: str
) -> Mapping[int, Mapping[str, Any]]:
    result = v1.load_json(path, "native clamp v2 holdout")
    cases = v1.sequence(result.get("cases"), "native clamp v2 cases")
    v1.require(
        result.get("transitionUniformProfileClampV2AnalysisSchemaVersion") == 1
        and result.get("classification")
        == "prospectively frozen native Darwin.powf v2 profile holdout"
        and result.get("sourceSHA256") == v1.sha256_file(NATIVE_CLAMP_SOURCE)
        and result.get("comparisonCount") == 32
        and result.get("exactMatchCount") == 32
        and result.get("allCandidateWordsExact") is True
        and len(cases) == 1,
        "native inputClamp v2 contract differs",
    )
    case = v1.mapping(cases[0], "native clamp v2 case")
    records = v1.sequence(case.get("records"), "native clamp v2 records")
    v1.require(
        case.get("name") == case_name
        and case.get("timelineSHA256") == timeline_sha256
        and case.get("comparisonCount") == 32
        and case.get("exactMatchCount") == 32
        and len(records) == 32,
        "native inputClamp v2 case differs",
    )
    indexed = {
        int(record["sampleIndex"]): record
        for untyped_record in records
        for record in [v1.mapping(untyped_record, "native clamp v2 record")]
    }
    v1.require(
        tuple(sorted(indexed)) == model.EXPECTED_DYNAMIC_SAMPLE_INDICES
        and all(
            record.get("exact") is True
            and record.get("observedBits") == record.get("candidateBits")
            for record in indexed.values()
        ),
        "native inputClamp v2 words differ",
    )
    return indexed


def validate(
    timeline_path: Path,
    preregistration_path: Path,
    native_clamp_path: Path,
    *,
    material: str,
    appearance: str,
    geometry: str,
) -> dict[str, Any]:
    identity = (material, appearance, geometry)
    v1.require(identity in EXPECTED_CASES, "runtime profile is outside v2 matrix")
    preregistration, case_name, diameter = validate_preregistration(
        preregistration_path, identity
    )
    timeline_sha256 = v1.sha256_file(timeline_path)
    clamp_records = validate_native_clamp(
        native_clamp_path, case_name=case_name, timeline_sha256=timeline_sha256
    )
    case = model.CalibrationCase(
        name=case_name,
        material=material,
        appearance=appearance,
        geometry=geometry,
        diameter=diameter,
        timeline_sha256=timeline_sha256,
    )
    analysis = model.analyze_case(case, timeline_path, clamp_records)
    v1.require(
        analysis["numericComparisonCount"] == 1_504
        and analysis["numericExactMatchCount"] == 1_504
        and analysis["structuredRecordCount"] == 32,
        "v2 uniform holdout is incomplete",
    )
    directory = timeline_path.parent
    preflight_path = directory / "capture-session-preflight.json"
    context_path = directory / "capture-context.txt"
    preflight = v1.validate_preflight(preflight_path)
    capture_commit = v1.validate_capture_context(
        context_path,
        material=material,
        appearance=appearance,
        geometry=geometry,
    )
    frames = v1.png_evidence(directory)
    return {
        "transitionUniformProfileHoldoutV2ValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "classification": (
            "corrected prospective direct-Retina v2 materialize numeric uniform "
            "transfer; one case of the frozen four-profile matrix"
        ),
        "caseId": case_name,
        "profile": {
            "material": material,
            "appearance": appearance,
            "direction": "materialize",
            "geometry": geometry,
        },
        "captureCommit": capture_commit,
        "inputs": {
            "timeline": timeline_path.name,
            "timelineSHA256": timeline_sha256,
            "preregistrationSHA256": v1.sha256_file(preregistration_path),
            "nativeClampResultSHA256": v1.sha256_file(native_clamp_path),
            "captureContextSHA256": v1.sha256_file(context_path),
            "preflightSHA256": v1.sha256_file(preflight_path),
        },
        "retinaPreflight": preflight,
        "windowServerFrames": frames,
        "uniformAnalysis": analysis,
        "openedCalibrationSHA256": preregistration["openedCalibrationEvidence"][
            "sha256"
        ],
        "conclusion": {
            "captureIntegrityPassed": True,
            "numericMaterializeTransferPassedForCase": True,
            "allNumericWordsExact": True,
            "numericMismatchCount": 0,
            "fourProfileMatrixComplete": False,
            "dematerializeTransferEstablished": False,
            "nestedResolvedColorTransferEstablished": False,
            "physicalPixelParityEstablished": False,
            "independentWalleZeroByteFrameEstablished": False,
            "liquidGlassParityEstablished": False,
            "productionShaderChangeAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("preregistration", type=Path)
    parser.add_argument("native_clamp_result", type=Path)
    parser.add_argument("--material", required=True)
    parser.add_argument("--appearance", required=True)
    parser.add_argument("--geometry", required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = validate(
        arguments.timeline,
        arguments.preregistration,
        arguments.native_clamp_result,
        material=arguments.material,
        appearance=arguments.appearance,
        geometry=arguments.geometry,
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
