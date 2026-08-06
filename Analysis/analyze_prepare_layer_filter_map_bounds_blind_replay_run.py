#!/usr/bin/env python3
"""Open and independently replay the frozen FilterOp blind-matrix run."""

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_prepare_layer_filter_map_bounds_blind_replay as blind_validator


RESULT_SCHEMA_VERSION = 1
EXPECTED_RUN_ID = 31072896015
EXPECTED_HEAD_SHA = "cf40cfdfe2f2fefc2b539f932048df5c434f6e26"
EXPECTED_PREREGISTRATION_SHA256 = (
    "fa4324d854ac1ee95a100269dd734260720b119dc2255932ab2ab2d5903eb251"
)
REQUIRED_STEP_NAMES = (
    "Verify frozen blind-replay contracts",
    "Build transition introspection probe",
    "Capture target-output-blind FilterOp operands",
    "Validate frozen exact FilterOp decoder",
    "Upload blind-replay evidence",
    "Enforce exact target-output-blind replay",
)


def load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot load {label}: {path}") from error


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} is not an object")
    return value


def sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{label} is not an array")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_job(raw_job: Any, expected_label: str) -> dict[str, Any]:
    job = mapping(raw_job, f"job {expected_label}")
    require(job.get("name") == expected_label, "job label differs")
    require(job.get("status") == "completed", "job did not complete")
    require(job.get("conclusion") == "success", "job did not succeed")
    steps = {
        mapping(raw_step, "job step").get("name"): mapping(raw_step, "job step")
        for raw_step in sequence(job.get("steps"), "job steps")
    }
    for name in REQUIRED_STEP_NAMES:
        step = steps.get(name)
        require(step is not None, f"required job step is absent: {name}")
        require(step.get("status") == "completed", f"job step did not complete: {name}")
        require(step.get("conclusion") == "success", f"job step failed: {name}")
    return {
        "jobID": int(job.get("databaseId")),
        "startedAt": job.get("startedAt"),
        "completedAt": job.get("completedAt"),
        "url": job.get("url"),
        "allRequiredStepsPassed": True,
    }


def validate_replay_result(result: Mapping[str, Any], expected_geometry: str) -> None:
    source = mapping(result.get("sourceBounds"), "source bounds")
    replay = mapping(result.get("floatingReplay"), "floating replay")
    selection = mapping(result.get("structuralSelection"), "structural selection")
    sealed = mapping(result.get("sealedConclusion"), "sealed conclusion")
    require(
        result.get("prepareLayerFilterMapBoundsBlindReplayValidationSchemaVersion")
        == 1,
        "blind validation schema differs",
    )
    require(result.get("conclusion") == "success", "blind validation failed")
    require(result.get("expectedGeometry") == expected_geometry, "geometry differs")
    require(source.get("sampleIndex") == 32, "source sample differs")
    require(
        source.get("cropOrProducerValuesUsed") is False,
        "source bounds are not crop blind",
    )
    require(replay.get("rectangleCount") == 32, "rectangle count differs")
    require(replay.get("componentCount") == 128, "component count differs")
    require(replay.get("exactRectangleCount") == 32, "rectangle replay differs")
    require(replay.get("exactComponentCount") == 128, "component replay differs")
    require(replay.get("mismatchedRectangleCount") == 0, "rectangle mismatch exists")
    require(replay.get("mismatchedComponentCount") == 0, "component mismatch exists")
    require(
        replay.get("maximumAbsoluteErrorsXYWH") == [0.0, 0.0, 0.0, 0.0],
        "absolute error is nonzero",
    )
    require(
        replay.get("maximumULPDistancesXYWH") == [0, 0, 0, 0],
        "ULP distance is nonzero",
    )
    require(replay.get("toleranceUsed") is False, "replay used tolerance")
    require(replay.get("allRectanglesExact") is True, "rectangle gate differs")
    require(replay.get("allComponentsExact") is True, "component gate differs")
    records = sequence(replay.get("records"), "replay records")
    require(len(records) == 32, "replay record count differs")
    require(
        all(
            mapping(record, "replay record").get("exact") is True for record in records
        ),
        "a replay record differs",
    )
    require(
        selection.get("cropOrProducerValuesUsedForSelection") is False,
        "producer selection inspected crop values",
    )
    require(selection.get("destinationMatchedUnionCount") == 64, "union count differs")
    require(selection.get("rejectedUnionCallCount") == 0, "a union call was rejected")
    require(selection.get("rejectedStoreCount") == 0, "a store was rejected")
    require(
        sealed.get("terminalSourceBoundsDerivedWithoutCropValues") is True,
        "source-bound conclusion differs",
    )
    require(
        sealed.get("exactFilterOperationOrderReplayed") is True,
        "operation-order conclusion differs",
    )
    require(
        sealed.get("allFloatingProducerRectanglesBitExact") is True,
        "floating replay conclusion differs",
    )
    require(
        sealed.get("allDownstreamIntegerCropsExact") is True,
        "downstream crop conclusion differs",
    )
    require(
        sealed.get("unseenGeometryCropReplayPassed") is True,
        "unseen transfer conclusion differs",
    )
    for key in (
        "materialAppearanceDirectionTransferPassed",
        "physicalRetina2xAndColorTransferPassed",
        "independentWalleZeroByteFrameParityPassed",
        "productionShaderAuthorized",
        "liquidGlassParityEstablished",
    ):
        require(sealed.get(key) is False, f"product boundary is open: {key}")


def analyze(
    preregistration_path: Path,
    run_path: Path,
    artifacts_metadata_path: Path,
    artifact_root: Path,
) -> dict[str, Any]:
    require(
        sha256(preregistration_path) == EXPECTED_PREREGISTRATION_SHA256,
        "preregistration bytes differ",
    )
    preregistration = mapping(
        load_json(preregistration_path, "preregistration"), "preregistration"
    )
    require(
        preregistration.get(
            "prepareLayerFilterMapBoundsBlindReplayPreregistrationSchemaVersion"
        )
        == 1,
        "preregistration schema differs",
    )
    require(
        preregistration.get("runtimeOutcomeFrozenBeforeDispatch") is None,
        "preregistration contains an outcome",
    )
    matrix = mapping(preregistration.get("blindMatrix"), "blind matrix")
    matrix_jobs = [
        mapping(raw_job, "matrix job")
        for raw_job in sequence(matrix.get("jobs"), "matrix jobs")
    ]
    require(len(matrix_jobs) == 8, "blind matrix job count differs")

    run = mapping(load_json(run_path, "run"), "run")
    require(run.get("databaseId") == EXPECTED_RUN_ID, "run ID differs")
    require(run.get("headSha") == EXPECTED_HEAD_SHA, "run head differs")
    require(run.get("status") == "completed", "run did not complete")
    require(run.get("conclusion") == "success", "run did not succeed")
    raw_jobs = {
        mapping(raw_job, "run job").get("name"): raw_job
        for raw_job in sequence(run.get("jobs"), "run jobs")
    }
    require(
        set(raw_jobs) == {job["label"] for job in matrix_jobs},
        "run job matrix differs",
    )

    metadata_root = mapping(
        load_json(artifacts_metadata_path, "artifact metadata"), "artifact metadata"
    )
    raw_artifacts = sequence(metadata_root.get("artifacts"), "artifacts")
    require(metadata_root.get("total_count") == 8, "artifact total differs")
    require(len(raw_artifacts) == 8, "artifact list count differs")
    artifacts = {
        mapping(raw_artifact, "artifact").get("name"): mapping(raw_artifact, "artifact")
        for raw_artifact in raw_artifacts
    }

    opened_jobs: list[dict[str, Any]] = []
    total_rectangles = 0
    total_components = 0
    for matrix_job in matrix_jobs:
        label = str(matrix_job["label"])
        geometry = str(matrix_job["geometry"])
        artifact_name = (
            f"liquid-glass-filter-map-bounds-blind-{label}-{EXPECTED_RUN_ID}"
        )
        artifact = artifacts.get(artifact_name)
        require(artifact is not None, f"artifact is absent: {artifact_name}")
        require(artifact.get("expired") is False, "artifact is expired")
        digest = artifact.get("digest")
        require(
            isinstance(digest, str) and digest.startswith("sha256:"),
            "artifact digest differs",
        )
        artifact_directory = artifact_root / artifact_name
        require(artifact_directory.is_dir(), "downloaded artifact is absent")
        trace_path = artifact_directory / "prepare-layer-crop-policy-holdout-trace.json"
        timeline_path = artifact_directory / "transition-timeline.json"
        validation_path = (
            artifact_directory
            / "prepare-layer-filter-map-bounds-blind-replay-validation.json"
        )
        contract_path = artifact_directory / "contracts.log"
        lldb_path = (
            artifact_directory / "lldb-prepare-layer-filter-map-bounds-blind-replay.log"
        )
        stderr_path = artifact_directory / "runtime-stderr.log"
        for path in (
            trace_path,
            timeline_path,
            validation_path,
            contract_path,
            lldb_path,
            stderr_path,
        ):
            require(path.is_file(), f"artifact file is absent: {path.name}")
        ci_validation = mapping(
            load_json(validation_path, "CI validation"), "CI validation"
        )
        local_validation = blind_validator.validate(trace_path, timeline_path, geometry)
        require(local_validation == ci_validation, "local validation bytes differ")
        validate_replay_result(ci_validation, geometry)
        replay = mapping(ci_validation["floatingReplay"], "floating replay")
        total_rectangles += int(replay["exactRectangleCount"])
        total_components += int(replay["exactComponentCount"])
        opened_jobs.append(
            {
                "label": label,
                "geometry": geometry,
                **validate_job(raw_jobs[label], label),
                "artifact": {
                    "artifactID": int(artifact.get("id")),
                    "name": artifact_name,
                    "sizeInBytes": int(artifact.get("size_in_bytes")),
                    "digest": digest,
                    "expired": False,
                },
                "sourceBounds": ci_validation["sourceBounds"],
                "exactRectangleCount": int(replay["exactRectangleCount"]),
                "exactComponentCount": int(replay["exactComponentCount"]),
                "maximumAbsoluteErrorsXYWH": replay["maximumAbsoluteErrorsXYWH"],
                "maximumULPDistancesXYWH": replay["maximumULPDistancesXYWH"],
                "localSemanticReplayByteIdenticalToCI": True,
                "files": {
                    "traceSHA256": sha256(trace_path),
                    "timelineSHA256": sha256(timeline_path),
                    "validationSHA256": sha256(validation_path),
                    "contractsSHA256": sha256(contract_path),
                    "lldbLogSHA256": sha256(lldb_path),
                    "runtimeStderrSHA256": sha256(stderr_path),
                },
            }
        )

    require(total_rectangles == 256, "aggregate rectangle count differs")
    require(total_components == 1024, "aggregate component count differs")
    prior = mapping(preregistration.get("priorEvidence"), "prior evidence")
    shader = mapping(
        mapping(
            preregistration.get("frozenImplementation"), "frozen implementation"
        ).get("productionShader"),
        "production shader",
    )
    return {
        "prepareLayerFilterMapBoundsBlindReplayResultSchemaVersion": (
            RESULT_SCHEMA_VERSION
        ),
        "classification": (
            "opened prospective target-output-blind result: all eight frozen "
            "boundary geometries pass exact binary64 FilterOp replay, and an "
            "independent local semantic rerun reproduces every CI validation byte"
        ),
        "run": {
            "runID": EXPECTED_RUN_ID,
            "headSHA": EXPECTED_HEAD_SHA,
            "status": "completed",
            "conclusion": "success",
            "createdAt": run.get("createdAt"),
            "updatedAt": run.get("updatedAt"),
            "url": run.get("url"),
            "preregistration": str(preregistration_path),
            "preregistrationSHA256": EXPECTED_PREREGISTRATION_SHA256,
        },
        "blindReplay": {
            "jobCount": 8,
            "passedJobCount": 8,
            "rectangleCount": total_rectangles,
            "exactRectangleCount": total_rectangles,
            "componentCount": total_components,
            "exactComponentCount": total_components,
            "mismatchedRectangleCount": 0,
            "mismatchedComponentCount": 0,
            "maximumAbsoluteErrorsXYWH": [0.0, 0.0, 0.0, 0.0],
            "maximumULPDistancesXYWH": [0, 0, 0, 0],
            "toleranceUsed": False,
            "jobs": opened_jobs,
        },
        "combinedCropEvidence": {
            "retrospectiveFloatingRectangleCount": int(
                prior["retrospectiveRectangleCount"]
            ),
            "retrospectiveFloatingComponentCount": int(
                prior["retrospectiveComponentCount"]
            ),
            "blindFloatingRectangleCount": total_rectangles,
            "blindFloatingComponentCount": total_components,
            "totalExactFloatingRectangleCount": (
                int(prior["retrospectiveRectangleCount"]) + total_rectangles
            ),
            "totalExactFloatingComponentCount": (
                int(prior["retrospectiveComponentCount"]) + total_components
            ),
            "priorExactIntegerCropCount": int(
                prior["downstreamCalibrationAndHoldoutIntegerCropCount"]
            ),
            "blindExactIntegerCropCount": total_rectangles,
            "totalExactIntegerCropCount": (
                int(prior["downstreamCalibrationAndHoldoutIntegerCropCount"])
                + total_rectangles
            ),
        },
        "conclusion": {
            "filterMapBoundsOwnerEstablished": True,
            "exactFilterMapBoundsArithmeticEstablished": True,
            "uniformCropBlindSourceBoundsRuleEstablished": True,
            "unchangedBlindRepeatPassed": True,
            "clearLightMaterializeOneXGeometryCropTransferPassed": True,
            "materialAppearanceDirectionTransferPassed": False,
            "physicalRetina2xAndColorTransferPassed": False,
            "independentWalleZeroByteFrameParityPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
        "remainingExactGates": [
            "material, appearance, and direction transfer",
            "physical Retina 2x plus color-space and pixel-format transfer",
            "independent Walle renders with zero unequal bytes over the declared parity domain",
            "production integration under the immutable shader-quality gate",
            "Tracy, VRAM, throughput, and latency optimization with every protected image still exact",
        ],
        "productionShader": shader,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("preregistration", type=Path)
    parser.add_argument("run", type=Path)
    parser.add_argument("artifacts_metadata", type=Path)
    parser.add_argument("artifact_root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = analyze(
        arguments.preregistration,
        arguments.run,
        arguments.artifacts_metadata,
        arguments.artifact_root,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
