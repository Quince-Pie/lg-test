#!/usr/bin/env python3
"""Validate the normal-flags transfer that retained an exact zero branch."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path
from typing import Any

import validate_backdrop_margin_case22_provider_object_matrix_minimal_retry2_local_macos_26_6_1 as allocation


RESULT_SCHEMA_VERSION = 1
EXPECTED_SHA256 = {
    "preregistration": "b63b45c0b9be9d48a2c472a5be028f5bee2e38995fdd071b1eef6d29efeedbe6",
    "captureContext": "a627f94a6a15ea2462c26a14d2dd4d46d304f85bde08ffd451f5a12001cdf3a0",
    "lldbExitStatus": "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa",
    "lldbLog": "3fba944bfec1cdcf90a20df6f3f92c76b0554f395aec6c394fda213ded6352d7",
    "trace": "32f82fab6a209831347bd2673a6c83fb304cdc72fb04045f37ed23c1ea0be614",
    "timeline": "e6fa2d9a2f9916f077f2af1b02d9e24a26a90bc60d72a84e0bb27fda5ef65345",
    "progress": "d3b4c102d7171a00481a5cadfec81c3874dfa86b6d4eb6856af68ba0da70aa93",
    "runtimeStdout": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "runtimeStderr": "b2b2ff8502b1f298fdd1793844029f76867348d14f4387a27150b130d8d96ff9",
}
EXPECTED_COMMIT = "d28806a1ad328e6a56f2c7fd33e3d3a6b91d8d26"
EXPECTED_ENVIRONMENT = {
    **allocation.EXPECTED_ENVIRONMENT,
    "LG_TRANSITION_ALLOCATION_ONLY": "0",
    "LG_TRANSITION_ALLOCATION_DENSE": "0",
}
EARLY_GATE_FIELDS = {
    "gaussianInput": (136, "f"),
    "gaussianGate": (144, "d"),
}


def validate_context(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    allocation.require(lines[0] == EXPECTED_COMMIT, "capture commit differs")
    allocation.require(
        lines[1].startswith(allocation.EXPECTED_BINARY_SHA256 + "  "),
        "binary context hash differs",
    )
    allocation.require(
        lines[2].startswith(allocation.EXPECTED_CAPTURE_SHA256 + "  "),
        "capture source context hash differs",
    )
    allocation.require(
        lines[3].startswith(EXPECTED_SHA256["preregistration"] + "  "),
        "preregistration context hash differs",
    )
    environment = dict(line.split("=", 1) for line in lines[4:])
    output = environment.pop(
        "LG_CASE22_PROVIDER_OBJECT_MATRIX_MINIMAL_TRACE_OUTPUT", None
    )
    allocation.require(
        output is not None and output.endswith("/provider-object-matrix-trace.json"),
        "trace output environment differs",
    )
    allocation.require(environment == EXPECTED_ENVIRONMENT, "capture environment differs")


def validate_timeline(value: Any, artifact_directory: Path) -> dict[str, Any]:
    timeline = allocation.mapping(value, "timeline")
    allocation.require(timeline.get("schemaVersion") == 5, "timeline schema differs")
    allocation.require(timeline.get("material") == "regular", "timeline material differs")
    allocation.require(timeline.get("appearance") == "light", "timeline appearance differs")
    allocation.require(
        allocation.mapping(timeline.get("geometry"), "timeline geometry").get("name")
        == "circle-127-center",
        "timeline geometry differs",
    )
    allocation.require(timeline.get("direction") == "materialize", "timeline direction differs")
    allocation.require(timeline.get("windowBackingScaleFactor") == 2, "timeline is not Retina 2x")
    allocation.require(timeline.get("sampleCount") == 33, "timeline sample count differs")
    allocation.require(timeline.get("failedSamples") == 0, "timeline has failed samples")
    allocation.require("error" not in timeline, "timeline contains an error")
    samples = allocation.sequence(timeline.get("samples"), "timeline samples")
    allocation.require(len(samples) == 33, "timeline sample length differs")
    expected_names = {
        f"transition-materialize-{index:02d}-rgba8.png" for index in range(33)
    }
    observed_names = {
        path.name
        for path in artifact_directory.glob("transition-materialize-*-rgba8.png")
    }
    allocation.require(observed_names == expected_names, "canonical image set differs")
    for index, sample_value in enumerate(samples):
        sample = allocation.mapping(sample_value, f"timeline sample {index}")
        capture = allocation.mapping(
            sample.get("windowCapture"), f"timeline sample {index} capture"
        )
        image = artifact_directory / f"transition-materialize-{index:02d}-rgba8.png"
        allocation.require(sample.get("executed") is True, f"sample {index} did not execute")
        allocation.require(capture.get("pngFile") == image.name, f"sample {index} image name differs")
        allocation.require(capture.get("pngSHA256") == allocation.sha256(image), f"sample {index} image hash differs")
        allocation.require(
            allocation.png_dimensions(image)
            == (capture.get("width"), capture.get("height")),
            f"sample {index} image dimensions differ",
        )
    dynamic = allocation.mapping(
        timeline.get("dynamicBackgroundUniforms"), "dynamic background uniforms"
    )
    allocation.require(dynamic.get("requested") is True, "dynamic capture was not requested")
    allocation.require(dynamic.get("executed") is True, "dynamic capture did not execute")
    allocation.require(dynamic.get("evidenceMode") == "controlled-replay-v1", "dynamic evidence mode differs")
    records = allocation.sequence(dynamic.get("records"), "dynamic records")
    allocation.require(len(records) == dynamic.get("executedSampleCount") == 9, "controlled replay count differs")
    unequal_bytes = 0
    for index, record_value in enumerate(records):
        record = allocation.mapping(record_value, f"controlled replay {index}")
        render = allocation.mapping(record.get("render"), f"controlled replay {index} render")
        replay = allocation.mapping(
            render.get("exactPassReplay"), f"controlled replay {index} exact pass"
        )
        allocation.require(replay.get("exactByteMatch") is True, f"controlled replay {index} is not exact")
        allocation.require(replay.get("mismatchedByteCount") == 0, f"controlled replay {index} byte mismatch differs")
        allocation.require(replay.get("mismatchedPixelCount") == 0, f"controlled replay {index} pixel mismatch differs")
        unequal_bytes += replay["mismatchedByteCount"]
    return {
        "schemaVersion": 5,
        "sampleCount": 33,
        "failedSamples": 0,
        "canonicalImageCount": 33,
        "windowBackingScaleFactor": 2,
        "dynamicEvidenceMode": "controlled-replay-v1",
        "controlledReplayCount": len(records),
        "controlledReplayUnequalByteCount": unequal_bytes,
    }


def validate_early_zero_gates(trace_value: Any) -> dict[str, Any]:
    trace = allocation.mapping(trace_value, "trace")
    calls = allocation.sequence(trace.get("calls"), "provider calls")
    counts = dict.fromkeys(EARLY_GATE_FIELDS, 0)
    for index, call_value in enumerate(calls):
        call = allocation.mapping(call_value, f"provider call {index}")
        snapshot = allocation.mapping(
            call.get("providerEntryObject"), f"provider call {index} object"
        )
        payload = bytes.fromhex(str(snapshot.get("hex", "")))
        for name, (offset, format_code) in EARLY_GATE_FIELDS.items():
            value = struct.unpack_from("<" + format_code, payload, offset)[0]
            allocation.require(value == 0.0, f"provider call {index} {name} is nonzero")
            counts[name] += 1
    return {
        "allCallGaussianInputPositiveGate": False,
        "allCallGaussianGatePositiveGate": False,
        "zeroGaussianInputCount": counts["gaussianInput"],
        "zeroGaussianGateCount": counts["gaussianGate"],
    }


def validate(preregistration_path: Path, artifact_directory: Path) -> dict[str, Any]:
    paths = {
        "preregistration": preregistration_path,
        "captureContext": artifact_directory / "capture-context.txt",
        "lldbExitStatus": artifact_directory / "lldb-exit-status.txt",
        "lldbLog": artifact_directory / "lldb.log",
        "trace": artifact_directory / "provider-object-matrix-trace.json",
        "timeline": artifact_directory / "transition-timeline.json",
        "progress": artifact_directory / "transition-progress.json",
        "runtimeStdout": artifact_directory / "runtime-stdout.log",
        "runtimeStderr": artifact_directory / "runtime-stderr.log",
    }
    observed_hashes = {name: allocation.sha256(path) for name, path in paths.items()}
    allocation.require(observed_hashes == EXPECTED_SHA256, "input SHA-256 identity differs")
    preregistration = allocation.mapping(
        allocation.load_json(preregistration_path, "preregistration"),
        "preregistration",
    )
    allocation.require(
        preregistration.get("runtimeOutcomeFrozenBeforeDispatch") is None,
        "outcome was not sealed before dispatch",
    )
    validate_context(paths["captureContext"])
    allocation.require(
        paths["lldbExitStatus"].read_text(encoding="utf-8") == "0\n",
        "LLDB exit status differs",
    )
    lldb_log = paths["lldbLog"].read_text(encoding="utf-8")
    allocation.require(
        "Process 7884 exited with status = 0" in lldb_log,
        "application process did not exit zero",
    )
    allocation.require("Traceback" not in lldb_log, "LLDB log contains a traceback")
    trace = allocation.load_json(paths["trace"], "trace")
    timeline = allocation.load_json(paths["timeline"], "timeline")
    trace_result = allocation.validate_trace(trace)
    timeline_result = validate_timeline(timeline, artifact_directory)
    gates = validate_early_zero_gates(trace)
    contract = allocation.mapping(
        preregistration.get("captureContract"), "capture contract"
    )
    allocation.require(
        contract.get("requireAtLeastTwoDistinctProviderReturnWords") is True,
        "nonzero transfer contract differs",
    )
    allocation.require(
        trace_result["distinctProviderReturnCount"] == 1,
        "normal transfer unexpectedly has multiple return words",
    )
    allocation.require(
        trace_result["providerReturnWords"] == ["0000000000000000"],
        "normal transfer return word differs",
    )
    return {
        "backdropMarginCase22ProviderObjectMatrixNormalLocalMacOSValidationSchemaVersion": RESULT_SCHEMA_VERSION,
        "classification": "exact validation of a prospectively frozen normal-flags transfer whose transport, object, return, timeline, and captured-input replay gates passed but whose required nonzero provider branch did not open",
        "inputs": {
            name: {"path": str(path), "sha256": observed_hashes[name]}
            for name, path in paths.items()
        },
        "application": {"processExitStatus": 0, **timeline_result},
        "trace": {**trace_result, "earlyProviderGates": gates},
        "transportAndObjectCapturePassed": True,
        "captureContractPassed": False,
        "failedRequirements": [
            "requireAtLeastTwoDistinctProviderReturnWords",
            "requireAtLeastOneFinitePositiveProviderReturn",
        ],
        "conclusion": "disabling allocation-only and dense-allocation while retaining dynamic-uniform controlled replay leaves gaussianInput and gaussianGate exactly zero in every live provider object, so the provider takes its exact zero-return path",
        "nextExactGate": "freeze a live-transition transfer with LG_TRANSITION_UNIFORMS disabled in addition to allocation-only and dense-allocation, retaining the same binary and exact provider capture",
        "publicInputMappingAuthority": False,
        "completeFiniteProviderLaw": False,
        "independentWalleZeroByteFrameParity": False,
        "productionShaderAuthorized": False,
        "liquidGlassParityEstablished": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--artifact-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        result = validate(arguments.preregistration, arguments.artifact_directory)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(payload, end="")
    else:
        arguments.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
