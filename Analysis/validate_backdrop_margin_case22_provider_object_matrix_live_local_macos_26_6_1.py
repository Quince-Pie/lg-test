#!/usr/bin/env python3
"""Seal the locked-session live-profile provider matrix as negative evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import validate_backdrop_margin_case22_provider_object_matrix_minimal_retry2_local_macos_26_6_1 as allocation
import validate_backdrop_margin_case22_provider_object_matrix_normal_local_macos_26_6_1 as normal


RESULT_SCHEMA_VERSION = 1
EXPECTED_SHA256 = {
    "preregistration": "a63b70c878509ce6837810a9efc0861cfcfaf34155f5a8c1658aab1e397899aa",
    "captureContext": "e29b1c553c2e803211e1b2403f02820dc03a8a22e51d737c7514fec924f5eac9",
    "lldbExitStatus": "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa",
    "lldbLog": "f3eb98eabc460807fbb6878b5d2ea42c3a28dc997e9a1349f51a733a1e7671d7",
    "trace": "8539c9bb226831970b242a95530378bbad86cc3287bdaf1a6f541a91dcfa15fa",
    "timeline": "4df34cd327097767a802b52316e5b60b1dd5eef02731bbfab56c83b53c96c3cc",
    "progress": "53130eba7abb3b9c05877c68411b8e2f363d486546fdefcea5be6e25c46d2991",
    "runtimeStdout": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "runtimeStderr": "abac63a1355aa59a48f4ba13bc48d1d00c96cbdd4c0a0ad1280523efab3378dd",
}
EXPECTED_COMMIT = "3a3a64b3ebdadb97c33b780d156e4cf006875df4"
EXPECTED_ENVIRONMENT = {
    **allocation.EXPECTED_ENVIRONMENT,
    "LG_TRANSITION_ALLOCATION_ONLY": "0",
    "LG_TRANSITION_ALLOCATION_DENSE": "0",
    "LG_TRANSITION_UNIFORMS": "0",
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
        output is not None
        and output.endswith("/provider-object-matrix-trace.json"),
        "trace output environment differs",
    )
    allocation.require(
        environment == EXPECTED_ENVIRONMENT, "capture environment differs"
    )


def validate_timeline(
    value: Any, artifact_directory: Path
) -> dict[str, Any]:
    timeline = allocation.mapping(value, "timeline")
    allocation.require(
        timeline.get("schemaVersion") == 5, "timeline schema differs"
    )
    allocation.require(
        timeline.get("material") == "regular", "timeline material differs"
    )
    allocation.require(
        timeline.get("appearance") == "light", "timeline appearance differs"
    )
    allocation.require(
        allocation.mapping(
            timeline.get("geometry"), "timeline geometry"
        ).get("name")
        == "circle-127-center",
        "timeline geometry differs",
    )
    allocation.require(
        timeline.get("direction") == "materialize",
        "timeline direction differs",
    )
    allocation.require(
        timeline.get("windowBackingScaleFactor") == 2,
        "timeline is not Retina 2x",
    )
    allocation.require(
        timeline.get("sampleCount") == 33,
        "timeline sample count differs",
    )
    allocation.require(
        timeline.get("failedSamples") == 0,
        "timeline has failed samples",
    )
    allocation.require("error" not in timeline, "timeline contains an error")
    samples = allocation.sequence(timeline.get("samples"), "timeline samples")
    allocation.require(len(samples) == 33, "timeline sample length differs")
    expected_names = {
        f"transition-materialize-{index:02d}-rgba8.png"
        for index in range(33)
    }
    observed_names = {
        path.name
        for path in artifact_directory.glob(
            "transition-materialize-*-rgba8.png"
        )
    }
    allocation.require(
        observed_names == expected_names, "canonical image set differs"
    )
    dimensions: set[tuple[int, int]] = set()
    for index, sample_value in enumerate(samples):
        sample = allocation.mapping(sample_value, f"timeline sample {index}")
        capture = allocation.mapping(
            sample.get("windowCapture"), f"timeline sample {index} capture"
        )
        image = (
            artifact_directory
            / f"transition-materialize-{index:02d}-rgba8.png"
        )
        allocation.require(
            sample.get("executed") is True,
            f"sample {index} did not execute",
        )
        allocation.require(
            capture.get("pngFile") == image.name,
            f"sample {index} image name differs",
        )
        allocation.require(
            capture.get("pngSHA256") == allocation.sha256(image),
            f"sample {index} image hash differs",
        )
        dimensions.add(allocation.png_dimensions(image))
        allocation.require(
            allocation.png_dimensions(image)
            == (capture.get("width"), capture.get("height")),
            f"sample {index} image dimensions differ",
        )
    dynamic = allocation.mapping(
        timeline.get("dynamicBackgroundUniforms"),
        "dynamic background uniforms",
    )
    allocation.require(
        dynamic.get("requested") is False,
        "dynamic capture was unexpectedly requested",
    )
    allocation.require(
        dynamic.get("executed") is False,
        "dynamic capture unexpectedly executed",
    )
    allocation.require(
        dynamic.get("evidenceMode") == "disabled",
        "dynamic evidence mode differs",
    )
    return {
        "schemaVersion": 5,
        "sampleCount": 33,
        "failedSamples": 0,
        "canonicalImageCount": 33,
        "canonicalImageDimensions": [list(value) for value in sorted(dimensions)],
        "windowBackingScaleFactor": 2,
        "dynamicEvidenceMode": "disabled",
    }


def validate(
    preregistration_path: Path, artifact_directory: Path
) -> dict[str, Any]:
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
    hashes = {name: allocation.sha256(path) for name, path in paths.items()}
    allocation.require(hashes == EXPECTED_SHA256, "input SHA-256 identity differs")
    preregistration = allocation.mapping(
        allocation.load_json(preregistration_path, "preregistration"),
        "preregistration",
    )
    allocation.require(
        preregistration.get("runtimeOutcomeFrozenBeforeDispatch") is None,
        "outcome was not unknown before dispatch",
    )
    validate_context(paths["captureContext"])
    allocation.require(
        paths["lldbExitStatus"].read_text(encoding="utf-8") == "0\n",
        "LLDB exit status differs",
    )
    lldb_log = paths["lldbLog"].read_text(encoding="utf-8")
    allocation.require(
        "Process 7982 exited with status = 0" in lldb_log,
        "application process did not exit zero",
    )
    allocation.require(
        "Traceback" not in lldb_log, "LLDB log contains a traceback"
    )
    trace = allocation.load_json(paths["trace"], "trace")
    timeline = allocation.load_json(paths["timeline"], "timeline")
    trace_result = allocation.validate_trace(trace)
    timeline_result = validate_timeline(timeline, artifact_directory)
    gates = normal.validate_early_zero_gates(trace)
    allocation.require(
        trace_result["callCount"] == 1222, "live provider call count differs"
    )
    allocation.require(
        trace_result["providerReturnWords"] == ["0000000000000000"],
        "live provider return word differs",
    )
    return {
        "backdropMarginCase22ProviderObjectMatrixLiveLocalMacOSValidationSchemaVersion": RESULT_SCHEMA_VERSION,
        "classification": (
            "exact validation of 1,222 observed post-main call chains in a "
            "prospectively frozen live-profile retry; the nonzero branch and "
            "the corrected complete-process/all-iteration domain did not pass"
        ),
        "inputs": {
            name: {"path": str(path), "sha256": hashes[name]}
            for name, path in paths.items()
        },
        "application": {"processExitStatus": 0, **timeline_result},
        "trace": {
            "observedCallCount": trace_result["callCount"],
            "observedGroupLinkedCallCount": trace_result[
                "providerGroupLinkedCallCount"
            ],
            "observedDistinctProviderObjectCount": trace_result[
                "distinctProviderObjectCount"
            ],
            "observedDistinctProviderReturnCount": trace_result[
                "distinctProviderReturnCount"
            ],
            "observedProviderReturnWords": trace_result[
                "providerReturnWords"
            ],
            "observedFailureCount": trace_result["failureCount"],
            "observedPendingCallCount": trace_result["pendingCallCount"],
            "earlyProviderGates": gates,
        },
        "observedCallChainIntegrityPassed": True,
        "captureContractPassed": False,
        "failedRequirements": [
            "requireCompleteProcessLifetimeSelection",
            "requireEveryCase22IterationUntilSelectedCallerReturn",
            "requireAtLeastTwoDistinctProviderReturnWords",
            "requireAtLeastOneFinitePositiveProviderReturn",
            "requireAtLeastOnePositiveGaussianInputAndGateObject",
        ],
        "dynamicUniformHypothesisPassed": False,
        "completeProcessDomainEstablished": False,
        "publicInputMappingAuthority": False,
        "completeFiniteProviderLaw": False,
        "independentWalleZeroByteFrameParity": False,
        "productionShaderAuthorized": False,
        "liquidGlassParityEstablished": False,
        "conclusion": (
            "disabling dynamic-uniform capture does not open the provider: "
            "all 1,222 observed objects retain exact zero gaussianInput and "
            "gaussianGate and return positive zero; this is a negative result, "
            "not evidence that the live provider is globally zero"
        ),
        "nextExactGate": (
            "require an unlocked, awake Retina session before launch, import "
            "the pending caller-entry adapter before run, and retain every "
            "case-22 iteration until the enclosing caller returns"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--artifact-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        result = validate(
            arguments.preregistration, arguments.artifact_directory
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(payload, end="")
    else:
        arguments.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
