#!/usr/bin/env python3
"""Validate one frozen dematerialize numeric-uniform holdout case."""

import argparse
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import analyze_transition_uniform_dematerialize_calibration as model
import validate_transition_uniform_profile_holdout as common


VALIDATION_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 1
EXPECTED_BINARY_SHA256 = (
    "6711ec851453405e2c19a1f731465f1f40b1db1b05f1bd5cd3835a3974cc351d"
)
EXPECTED_CASES = {
    ("clear", "light", "circle-456-center"): ("clear-light-circle456", 456),
    ("clear", "dark", "circle-464-center"): ("clear-dark-circle464", 464),
    ("regular", "light", "circle-472-center"): (
        "regular-light-circle472",
        472,
    ),
    ("regular", "dark", "circle-480-center"): (
        "regular-dark-circle480",
        480,
    ),
}
CALIBRATION_RESULT = Path(__file__).with_name(
    "transition_uniform_dematerialize_calibration_result.json"
)
MATERIALIZE_MODEL_SOURCE = Path(__file__).with_name(
    "analyze_transition_uniform_profile_calibration.py"
)
DEMATERIALIZE_MODEL_SOURCE = Path(__file__).with_name(
    "analyze_transition_uniform_dematerialize_calibration.py"
)
NATIVE_CLAMP_SOURCE = Path(__file__).with_name(
    "analyze_transition_uniform_dematerialize_clamp_holdout_local_macos_26_6_1.swift"
)
AGGREGATOR_SOURCE = Path(__file__).with_name(
    "aggregate_transition_uniform_dematerialize_holdout.py"
)
PREFLIGHT_SOURCE = Path(__file__).with_name(
    "check_local_retina_capture_session_v2.swift"
)
TOPOLOGY_RESULT = Path(__file__).with_name(
    "transition_presentation_lifetime_a001c21_holdout_result.json"
)


def validate_preregistration(
    path: Path, identity: tuple[str, str, str]
) -> tuple[Mapping[str, Any], str, int]:
    preregistration = common.load_json(path, "dematerialize preregistration")
    common.require(
        preregistration.get(
            "transitionUniformDematerializeHoldoutPreregistrationSchemaVersion"
        )
        == PREREGISTRATION_SCHEMA_VERSION,
        "dematerialize preregistration schema differs",
    )
    case_matrix = common.sequence(
        preregistration.get("caseMatrix"), "dematerialize case matrix"
    )
    observed_cases = {
        (case.get("material"), case.get("appearance"), case.get("geometry"))
        for untyped_case in case_matrix
        for case in [common.mapping(untyped_case, "dematerialize holdout case")]
    }
    common.require(
        observed_cases == set(EXPECTED_CASES) and len(case_matrix) == 4,
        "dematerialize four-profile matrix differs",
    )
    selected = [
        case
        for untyped_case in case_matrix
        for case in [common.mapping(untyped_case, "dematerialize holdout case")]
        if (case.get("material"), case.get("appearance"), case.get("geometry"))
        == identity
    ]
    common.require(len(selected) == 1, "runtime profile is not one frozen case")
    selected_case = selected[0]
    case_name, diameter = EXPECTED_CASES[identity]
    common.require(
        selected_case.get("caseId") == case_name
        and selected_case.get("direction") == "dematerialize"
        and selected_case.get("role") == "prospective-holdout"
        and selected_case.get("appleOutputAvailableAtFreeze") is False
        and selected_case.get("timelineSHA256") is None
        and selected_case.get("numericFieldWords") is None
        and selected_case.get("inputClampWords") is None
        and selected_case.get("windowServerFrameWords") is None,
        "dematerialize case was not frozen output-blind",
    )
    calibration = common.mapping(
        preregistration.get("openedCalibrationEvidence"), "calibration evidence"
    )
    common.require(
        calibration.get("path")
        == "Analysis/transition_uniform_dematerialize_calibration_result.json"
        and calibration.get("sha256") == common.sha256_file(CALIBRATION_RESULT)
        and calibration.get("numericComparisonCount") == 5_828
        and calibration.get("numericMismatchCount") == 0
        and calibration.get("prospectiveAuthority") is False,
        "dematerialize calibration evidence differs",
    )
    topology = common.mapping(
        preregistration.get("priorTopologyEvidence"), "prior topology evidence"
    )
    common.require(
        topology.get("path")
        == "Analysis/transition_presentation_lifetime_a001c21_holdout_result.json"
        and topology.get("sha256") == common.sha256_file(TOPOLOGY_RESULT)
        and topology.get("dematerializeDynamicFilterSamples") == "1...31"
        and topology.get("absentEndpointSample") == 32
        and topology.get("absentEndpointFilterCount") == 0
        and topology.get("commonAbsentEndpointSHA256")
        == "f93a15f6884c8eccdf4b94203f748def9512e3137538aea2b99a53ece39b48a8"
        and topology.get("derivedBeforeTargetOutput") is True,
        "prior dematerialize topology evidence differs",
    )
    implementation = common.mapping(
        preregistration.get("frozenImplementation"), "frozen implementation"
    )
    common.require(
        implementation.get("materializeModel")
        == "Analysis/analyze_transition_uniform_profile_calibration.py"
        and implementation.get("materializeModelSHA256")
        == common.sha256_file(MATERIALIZE_MODEL_SOURCE)
        and implementation.get("dematerializeModel")
        == "Analysis/analyze_transition_uniform_dematerialize_calibration.py"
        and implementation.get("dematerializeModelSHA256")
        == common.sha256_file(DEMATERIALIZE_MODEL_SOURCE)
        and implementation.get("nativeClamp")
        == (
            "Analysis/analyze_transition_uniform_dematerialize_clamp_holdout_"
            "local_macos_26_6_1.swift"
        )
        and implementation.get("nativeClampSHA256")
        == common.sha256_file(NATIVE_CLAMP_SOURCE)
        and implementation.get("validator")
        == "Analysis/validate_transition_uniform_dematerialize_holdout.py"
        and implementation.get("validatorSHA256")
        == common.sha256_file(Path(__file__))
        and implementation.get("aggregator")
        == "Analysis/aggregate_transition_uniform_dematerialize_holdout.py"
        and implementation.get("aggregatorSHA256")
        == common.sha256_file(AGGREGATOR_SOURCE)
        and implementation.get("preflight")
        == "Analysis/check_local_retina_capture_session_v2.swift"
        and implementation.get("preflightSHA256")
        == common.sha256_file(PREFLIGHT_SOURCE),
        "frozen dematerialize implementation differs",
    )
    acceptance = common.mapping(
        preregistration.get("acceptance"), "dematerialize acceptance"
    )
    common.require(
        acceptance.get("numericFieldCountPerState") == 47
        and acceptance.get("dynamicStateCountPerCase") == 31
        and acceptance.get("numericComparisonCountPerCase") == 1_457
        and acceptance.get("numericComparisonCountAcrossMatrix") == 5_828
        and acceptance.get("requiredNumericMismatchCount") == 0
        and acceptance.get("expectedMatrixFrameCount") == 132
        and acceptance.get("expectedDistinctMatrixFrameCount") == 129
        and acceptance.get("expectedCommonAbsentEndpointCount") == 4
        and acceptance.get("commonAbsentEndpointFrame")
        == "transition-dematerialize-32-rgba8.png"
        and acceptance.get("commonAbsentEndpointSHA256")
        == "f93a15f6884c8eccdf4b94203f748def9512e3137538aea2b99a53ece39b48a8"
        and acceptance.get("requireOnlySampleThirtyTwoCrossCaseDuplicate") is True
        and acceptance.get("requireExactBinary32Words") is True
        and acceptance.get("requireNativeDarwinPowfClamp") is True
        and acceptance.get("requireRealRecordsWithoutSyntheticEndpoint") is True
        and acceptance.get("requireAllFourCasesFromOneFrozenCommit") is True
        and acceptance.get("requireDirectActiveRetinaSession") is True
        and acceptance.get("requireNoDebugger") is True
        and acceptance.get("requireNoGitHubActions") is True,
        "dematerialize acceptance contract differs",
    )
    return preregistration, case_name, diameter


def validate_native_clamp(
    path: Path, *, case_name: str, timeline_sha256: str
) -> Mapping[int, Mapping[str, Any]]:
    result = common.load_json(path, "native dematerialize clamp holdout")
    cases = common.sequence(result.get("cases"), "native clamp cases")
    common.require(
        result.get("transitionUniformDematerializeClampHoldoutSchemaVersion") == 1
        and result.get("classification")
        == (
            "prospectively frozen native Darwin.powf dematerialize holdout; "
            "one case of the four-profile matrix"
        )
        and result.get("sourceSHA256") == common.sha256_file(NATIVE_CLAMP_SOURCE)
        and result.get("comparisonCount") == 31
        and result.get("exactMatchCount") == 31
        and result.get("allCandidateWordsExact") is True
        and len(cases) == 1,
        "native dematerialize inputClamp contract differs",
    )
    case = common.mapping(cases[0], "native clamp case")
    records = common.sequence(case.get("records"), "native clamp records")
    common.require(
        case.get("name") == case_name
        and case.get("direction") == "dematerialize"
        and case.get("timelineSHA256") == timeline_sha256
        and case.get("comparisonCount") == 31
        and case.get("exactMatchCount") == 31
        and len(records) == 31,
        "native dematerialize inputClamp case differs",
    )
    indexed = {
        int(record["sampleIndex"]): record
        for untyped_record in records
        for record in [common.mapping(untyped_record, "native clamp record")]
    }
    common.require(
        tuple(sorted(indexed)) == tuple(range(1, 32))
        and all(
            record.get("exact") is True
            and record.get("observedBits") == record.get("candidateBits")
            and re.fullmatch(r"[0-9a-f]{8}", str(record.get("baseBits")))
            is not None
            for record in indexed.values()
        ),
        "native dematerialize inputClamp words differ",
    )
    return indexed


def validate_capture_context(
    path: Path, *, material: str, appearance: str, geometry: str
) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    fields: dict[str, str] = {}
    for line in lines:
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key] = value
    commit = fields.get("CAPTURE_COMMIT", "")
    common.require(
        re.fullmatch(r"[0-9a-f]{40}", commit) is not None,
        "capture commit differs",
    )
    expected = {
        "NATIVE_CAPTURE_DEBUGGER_USED": "0",
        "GITHUB_ACTIONS_USED": "0",
        "LG_GLASS_MATERIAL": material,
        "LG_GLASS_APPEARANCE": appearance,
        "LG_GLASS_GEOMETRY": geometry,
        "LG_TRANSITION_DIRECTION": "dematerialize",
        "LG_TRANSITION_TIMELINE": "1",
        "LG_TRANSITION_UNIFORMS": "1",
        "LG_TRANSITION_ALLOCATION_ONLY": "1",
        "LG_TRANSITION_ALLOCATION_DENSE": "1",
        "LG_TRANSITION_CONTROLLED_BACKDROP": "0",
    }
    common.require(
        all(fields.get(key) == value for key, value in expected.items()),
        "native dematerialize capture environment differs",
    )
    common.require(
        any(
            line.startswith(EXPECTED_BINARY_SHA256 + "  ")
            and line.endswith("glass-transition-introspect-9b5c502")
            for line in lines
        ),
        "dematerialize capture binary identity differs",
    )
    common.require(
        not any("/nix/store/" in line for line in lines),
        "native dematerialize context contains a Nix store path",
    )
    return commit


def png_evidence(directory: Path) -> dict[str, Any]:
    paths = sorted(directory.glob("transition-dematerialize-??-rgba8.png"))
    common.require(len(paths) == 33, "WindowServer frame count differs")
    digests = [common.sha256_file(path) for path in paths]
    common.require(len(set(digests)) == 33, "WindowServer frames are not distinct")
    return {
        "count": len(paths),
        "distinctSHA256Count": len(set(digests)),
        "sha256": dict(zip((path.name for path in paths), digests, strict=True)),
    }


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
    common.require(identity in EXPECTED_CASES, "runtime profile is outside matrix")
    preregistration, case_name, diameter = validate_preregistration(
        preregistration_path, identity
    )
    timeline_sha256 = common.sha256_file(timeline_path)
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
    common.require(
        analysis["numericComparisonCount"] == 1_457
        and analysis["numericExactMatchCount"] == 1_457
        and analysis["structuredRecordCount"] == 31,
        "dematerialize uniform holdout is incomplete",
    )
    directory = timeline_path.parent
    preflight_path = directory / "capture-session-preflight.json"
    context_path = directory / "capture-context.txt"
    preflight = common.validate_preflight(preflight_path)
    capture_commit = validate_capture_context(
        context_path,
        material=material,
        appearance=appearance,
        geometry=geometry,
    )
    frames = png_evidence(directory)
    return {
        "transitionUniformDematerializeHoldoutValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "classification": (
            "prospective direct-Retina dematerialize numeric uniform transfer; "
            "one case of the frozen four-profile matrix"
        ),
        "caseId": case_name,
        "profile": {
            "material": material,
            "appearance": appearance,
            "direction": "dematerialize",
            "geometry": geometry,
        },
        "captureCommit": capture_commit,
        "inputs": {
            "timeline": timeline_path.name,
            "timelineSHA256": timeline_sha256,
            "preregistrationSHA256": common.sha256_file(preregistration_path),
            "nativeClampResultSHA256": common.sha256_file(native_clamp_path),
            "captureContextSHA256": common.sha256_file(context_path),
            "preflightSHA256": common.sha256_file(preflight_path),
        },
        "retinaPreflight": preflight,
        "windowServerFrames": frames,
        "uniformAnalysis": analysis,
        "openedCalibrationSHA256": preregistration["openedCalibrationEvidence"][
            "sha256"
        ],
        "conclusion": {
            "captureIntegrityPassed": True,
            "numericDematerializeTransferPassedForCase": True,
            "allNumericWordsExact": True,
            "numericMismatchCount": 0,
            "fourProfileMatrixComplete": False,
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
