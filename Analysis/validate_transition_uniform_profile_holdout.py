#!/usr/bin/env python3
"""Validate one frozen four-profile materialize uniform holdout case."""

import argparse
import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import analyze_transition_uniform_profile_calibration as model


VALIDATION_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 1
PREFLIGHT_SCHEMA_VERSION = 2
EXPECTED_PHYSICAL_PIXELS = [3456, 2234]
EXPECTED_LOGICAL_POINTS = [1728, 1117]
EXPECTED_BINARY_SHA256 = model.EXPECTED_BINARY_SHA256
EXPECTED_CASES = {
    ("clear", "light", "circle-454-center"): (
        "clear-light-circle454",
        454,
    ),
    ("clear", "dark", "circle-462-center"): (
        "clear-dark-circle462",
        462,
    ),
    ("regular", "light", "circle-470-center"): (
        "regular-light-circle470",
        470,
    ),
    ("regular", "dark", "circle-478-center"): (
        "regular-dark-circle478",
        478,
    ),
}
CALIBRATION_RESULT = Path(__file__).with_name(
    "transition_uniform_profile_calibration_result.json"
)
MODEL_SOURCE = Path(__file__).with_name(
    "analyze_transition_uniform_profile_calibration.py"
)
NATIVE_CLAMP_SOURCE = Path(__file__).with_name(
    "analyze_transition_uniform_profile_clamp_local_macos_26_6_1.swift"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def mapping(value: object, label: str) -> Mapping[str, Any]:
    require(isinstance(value, Mapping), f"{label} is not an object")
    return value


def sequence(value: object, label: str) -> list[Any]:
    require(isinstance(value, list), f"{label} is not an array")
    return value


def load_json(path: Path, label: str) -> Mapping[str, Any]:
    try:
        return mapping(json.loads(path.read_text(encoding="utf-8")), label)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        error.add_note(f"while reading {path}")
        raise


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_preregistration(
    path: Path, identity: tuple[str, str, str]
) -> tuple[Mapping[str, Any], str, int]:
    preregistration = load_json(path, "preregistration")
    require(
        preregistration.get(
            "transitionUniformProfileHoldoutPreregistrationSchemaVersion"
        )
        == PREREGISTRATION_SCHEMA_VERSION,
        "preregistration schema differs",
    )
    case_matrix = sequence(preregistration.get("caseMatrix"), "case matrix")
    observed_cases = {
        (case.get("material"), case.get("appearance"), case.get("geometry"))
        for untyped_case in case_matrix
        for case in [mapping(untyped_case, "holdout case")]
    }
    require(
        observed_cases == set(EXPECTED_CASES) and len(case_matrix) == 4,
        "four-profile holdout matrix differs",
    )
    selected = [
        case
        for untyped_case in case_matrix
        for case in [mapping(untyped_case, "holdout case")]
        if (case.get("material"), case.get("appearance"), case.get("geometry"))
        == identity
    ]
    require(len(selected) == 1, "runtime profile is not one frozen case")
    selected_case = selected[0]
    case_name, diameter = EXPECTED_CASES[identity]
    require(
        selected_case.get("caseId") == case_name
        and selected_case.get("direction") == "materialize"
        and selected_case.get("role") == "prospective-holdout"
        and selected_case.get("appleOutputAvailableAtFreeze") is False
        and selected_case.get("timelineSHA256") is None
        and selected_case.get("numericFieldWords") is None
        and selected_case.get("inputClampWords") is None,
        "holdout case was not frozen output-blind",
    )

    calibration = mapping(
        preregistration.get("openedCalibrationEvidence"), "calibration evidence"
    )
    require(
        CALIBRATION_RESULT.is_file()
        and calibration.get("path")
        == "Analysis/transition_uniform_profile_calibration_result.json"
        and calibration.get("sha256") == sha256_file(CALIBRATION_RESULT)
        and calibration.get("numericComparisonCount") == 6_016
        and calibration.get("numericMismatchCount") == 0
        and calibration.get("prospectiveAuthority") is False,
        "opened calibration evidence differs",
    )
    implementation = mapping(
        preregistration.get("frozenImplementation"), "frozen implementation"
    )
    require(
        implementation.get("model")
        == "Analysis/analyze_transition_uniform_profile_calibration.py"
        and implementation.get("modelSHA256") == sha256_file(MODEL_SOURCE)
        and implementation.get("nativeClamp")
        == "Analysis/analyze_transition_uniform_profile_clamp_local_macos_26_6_1.swift"
        and implementation.get("nativeClampSHA256") == sha256_file(NATIVE_CLAMP_SOURCE)
        and implementation.get("validator")
        == "Analysis/validate_transition_uniform_profile_holdout.py"
        and implementation.get("validatorSHA256") == sha256_file(Path(__file__)),
        "frozen implementation identity differs",
    )
    acceptance = mapping(preregistration.get("acceptance"), "acceptance")
    require(
        acceptance.get("numericFieldCountPerState") == 47
        and acceptance.get("dynamicStateCountPerCase") == 32
        and acceptance.get("numericComparisonCountPerCase") == 1_504
        and acceptance.get("numericComparisonCountAcrossMatrix") == 6_016
        and acceptance.get("requiredNumericMismatchCount") == 0
        and acceptance.get("requireExactBinary32Words") is True
        and acceptance.get("requireNativeDarwinPowfClamp") is True
        and acceptance.get("requireAllFourCasesFromOneFrozenCommit") is True
        and acceptance.get("requireDirectActiveRetinaSession") is True
        and acceptance.get("requireNoDebugger") is True,
        "acceptance contract differs",
    )
    return preregistration, case_name, diameter


def validate_preflight(path: Path) -> Mapping[str, Any]:
    preflight = load_json(path, "Retina preflight")
    require(
        preflight.get("localRetinaCaptureSessionPreflightSchemaVersion")
        == PREFLIGHT_SCHEMA_VERSION
        and preflight.get("passed") is True
        and preflight.get("displayActive") is True
        and preflight.get("displayAsleep") is False
        and preflight.get("sessionLocked") is False
        and preflight.get("sessionLoginDone") is True
        and preflight.get("sessionOnConsole") is True
        and preflight.get("backingScaleFactor") == 2
        and preflight.get("physicalPixels") == EXPECTED_PHYSICAL_PIXELS
        and preflight.get("logicalPoints") == EXPECTED_LOGICAL_POINTS,
        "physical Retina session differs",
    )
    return preflight


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
    require(re.fullmatch(r"[0-9a-f]{40}", commit) is not None, "capture commit differs")
    expected = {
        "NATIVE_CAPTURE_DEBUGGER_USED": "0",
        "LG_GLASS_MATERIAL": material,
        "LG_GLASS_APPEARANCE": appearance,
        "LG_GLASS_GEOMETRY": geometry,
        "LG_TRANSITION_DIRECTION": "materialize",
        "LG_TRANSITION_TIMELINE": "1",
        "LG_TRANSITION_UNIFORMS": "1",
        "LG_TRANSITION_ALLOCATION_ONLY": "1",
        "LG_TRANSITION_ALLOCATION_DENSE": "1",
        "LG_TRANSITION_CONTROLLED_BACKDROP": "0",
    }
    require(
        all(fields.get(key) == value for key, value in expected.items()),
        "native capture environment differs",
    )
    require(
        any(
            line.startswith(EXPECTED_BINARY_SHA256 + "  ")
            and line.endswith("glass-transition-introspect-721293f")
            for line in lines
        ),
        "capture binary identity differs",
    )
    require(
        not any("/nix/store/" in line for line in lines),
        "native capture context contains a Nix store path",
    )
    return commit


def validate_native_clamp(
    path: Path, *, case_name: str, timeline_sha256: str
) -> Mapping[int, Mapping[str, Any]]:
    result = load_json(path, "native clamp holdout")
    cases = sequence(result.get("cases"), "native clamp cases")
    require(
        result.get("transitionUniformProfileClampAnalysisSchemaVersion") == 1
        and result.get("classification")
        == "prospectively frozen native Darwin.powf profile holdout"
        and result.get("mode") == "holdout"
        and result.get("sourceSHA256") == sha256_file(NATIVE_CLAMP_SOURCE)
        and result.get("comparisonCount") == 32
        and result.get("exactMatchCount") == 32
        and result.get("allCandidateWordsExact") is True
        and len(cases) == 1,
        "native inputClamp holdout contract differs",
    )
    case = mapping(cases[0], "native clamp case")
    records = sequence(case.get("records"), "native clamp records")
    require(
        case.get("name") == case_name
        and case.get("timelineSHA256") == timeline_sha256
        and case.get("comparisonCount") == 32
        and case.get("exactMatchCount") == 32
        and len(records) == 32,
        "native inputClamp case differs",
    )
    indexed = {
        int(record["sampleIndex"]): record
        for untyped_record in records
        for record in [mapping(untyped_record, "native clamp record")]
    }
    require(
        tuple(sorted(indexed)) == model.EXPECTED_DYNAMIC_SAMPLE_INDICES
        and all(
            record.get("exact") is True
            and record.get("observedBits") == record.get("candidateBits")
            for record in indexed.values()
        ),
        "native inputClamp record words differ",
    )
    return indexed


def png_evidence(directory: Path) -> dict[str, Any]:
    paths = sorted(directory.glob("transition-materialize-??-rgba8.png"))
    require(len(paths) == 33, "WindowServer frame count differs")
    digests = [sha256_file(path) for path in paths]
    require(len(set(digests)) == 33, "WindowServer frames are not all distinct")
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
    require(identity in EXPECTED_CASES, "runtime profile is outside holdout matrix")
    preregistration, case_name, diameter = validate_preregistration(
        preregistration_path, identity
    )
    timeline_sha256 = sha256_file(timeline_path)
    clamp_records = validate_native_clamp(
        native_clamp_path,
        case_name=case_name,
        timeline_sha256=timeline_sha256,
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
    require(
        analysis["numericComparisonCount"] == 1_504
        and analysis["numericExactMatchCount"] == 1_504
        and analysis["structuredRecordCount"] == 32,
        "profile uniform holdout is incomplete",
    )
    directory = timeline_path.parent
    preflight_path = directory / "capture-session-preflight.json"
    context_path = directory / "capture-context.txt"
    preflight = validate_preflight(preflight_path)
    capture_commit = validate_capture_context(
        context_path,
        material=material,
        appearance=appearance,
        geometry=geometry,
    )
    frames = png_evidence(directory)
    return {
        "transitionUniformProfileHoldoutValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "classification": (
            "prospective direct-Retina materialize numeric uniform transfer; "
            "one case of the frozen four-profile matrix"
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
            "preregistrationSHA256": sha256_file(preregistration_path),
            "nativeClampResultSHA256": sha256_file(native_clamp_path),
            "captureContextSHA256": sha256_file(context_path),
            "preflightSHA256": sha256_file(preflight_path),
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
