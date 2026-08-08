#!/usr/bin/env python3
"""Validate the frozen current-highlight source pixel-influence intervention."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
import struct
from typing import Any


type JsonObject = dict[str, Any]

RESULT_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 1
INTERVENTION_SCHEMA_VERSION = 1
REPOSITORY = Path(__file__).resolve().parents[1]
PREREGISTRATION_SHA256 = (
    "fd33002fa5e1f8ba87cf62da5f7568b63fbb9ceee1c942d5422d1202a70200c7"
)
TIMELINE_SHA256 = "232122b1e486d90d888efb982e7b8effbd3db9dbe631b80cd717a190229dd06d"
CAPTURE_BINARY_SHA256 = (
    "bb445ce4debad491f4ec9c7862200e09acd932be224b20ab57c125e798c1c4fb"
)
PREFLIGHT_SHA256 = "a424b3c50899149ba79ef5e70687a01f896e8fbf058da5437a5a564c71a14034"
RAW_SHA256 = "bb9f8df61474d25e71fa00722318cd387396ca1736605e1248821cc0de3d3af8"
RAW_BYTE_COUNT = 4_194_304
PIPELINE = "com.apple.coreanimation.PBGRAXm_TkfhBvcmA2Xhfc_Iscd"
REFERENCE_FILE = "transition-background-uniform-01-exact-pass-replay-bgra8.raw"
PREFLIGHT_FILE = "lg-final-source-intervention-v2-preflight.json"
BINARY_FILE = "glassintrospect-v2"
EXPECTED_INTERVENTIONS = {
    "zero-float2": {
        "hex": "00" * 32,
        "streamSHA256": (
            "66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925"
        ),
        "rawFile": (
            "transition-background-uniform-01-final-highlight-source-"
            "zero-float2-bgra8.raw"
        ),
        "statusFile": (
            "transition-background-uniform-01-final-highlight-source-"
            "zero-float2-status.json"
        ),
        "statusSHA256": (
            "db1d5f555f9fefc28c58864d62bde2bec999dc20fa4514f3d1ab7a9fb63820ee"
        ),
    },
    "finite-asymmetric-float2": {
        "hex": ("0000003e000080be0000003f0000403f000080bf0000c03f00000040000020c0"),
        "streamSHA256": (
            "3a6adc6d309e496fa0228867f34c7691ec8193d089c9fbec54b3e2bc6141bc19"
        ),
        "rawFile": (
            "transition-background-uniform-01-final-highlight-source-"
            "finite-asymmetric-float2-bgra8.raw"
        ),
        "statusFile": (
            "transition-background-uniform-01-final-highlight-source-"
            "finite-asymmetric-float2-status.json"
        ),
        "statusSHA256": (
            "72508b67adbff889b06a8757f22829a7b9eb298061e3ac867bf17945f56f2084"
        ),
    },
}
ORIGINAL_STREAM_SHA256 = (
    "c2ac2a828040438c6ae75420022d8f2fcd9856c4883c56826428dc1824e8b866"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def mapping(value: object, name: str) -> Mapping[str, Any]:
    require(isinstance(value, Mapping), f"{name} is not an object")
    return value


def sequence(value: object, name: str) -> Sequence[Any]:
    require(isinstance(value, list), f"{name} is not an array")
    return value


def load_object(path: Path, name: str) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{name} is not an object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def validate_preregistration_value(value: Mapping[str, Any]) -> None:
    require(
        value.get("finalHighlightSourceInterventionPreregistrationSchemaVersion")
        == PREREGISTRATION_SCHEMA_VERSION,
        "preregistration schema differs",
    )
    require(
        value.get("authority")
        == "prospective current-build pixel-influence intervention",
        "preregistration authority differs",
    )
    require(
        value.get("appleOutputsObservedAtFreeze") is False,
        "preregistration is not output-blind",
    )
    scope = mapping(value.get("scope"), "scope")
    require(
        scope.get("operatingSystem") == "macOS 26.6.1 build 25G76"
        and scope.get("device") == "Apple M1 Max"
        and scope.get("display") == "active physical 2x Retina"
        and scope.get("material") == "clear"
        and scope.get("appearance") == "dark"
        and scope.get("direction") == "materialize"
        and scope.get("geometry") == "circle-combined-holdout-02"
        and scope.get("windowPixels") == [2048, 2048]
        and scope.get("pipeline") == PIPELINE
        and scope.get("candidateSampleIndices") == list(range(1, 32)),
        "preregistered scope differs",
    )
    layout = mapping(value.get("frozenVertexLayout"), "vertex layout")
    require(
        layout.get("bufferIndex") == 1
        and layout.get("vertexCount") == 4
        and layout.get("stride") == 48
        and layout.get("attributeIndex") == 2
        and layout.get("attributeOffset") == 24
        and layout.get("attributeFormat") == "float2"
        and layout.get("attributeBytesPerVertex") == 8,
        "frozen vertex layout differs",
    )
    observed_interventions = {
        str(mapping(item, "intervention").get("name")): str(
            mapping(item, "intervention").get("littleEndianHex")
        )
        for item in sequence(value.get("interventions"), "interventions")
    }
    require(
        observed_interventions
        == {
            name: str(expected["hex"])
            for name, expected in EXPECTED_INTERVENTIONS.items()
        },
        "frozen intervention streams differ",
    )
    acceptance = mapping(value.get("acceptance"), "acceptance")
    require(
        acceptance.get("interventionCount") == 2
        and acceptance.get("comparisonBytesPerIntervention") == RAW_BYTE_COUNT
        and acceptance.get("requiredUnequalByteCount") == 0
        and acceptance.get("requiredUnequalPixelCount") == 0
        and acceptance.get("requiredMaximumChannelDelta") == 0
        and acceptance.get("tolerance") == 0
        and acceptance.get("bothReplacementStreamsMustDifferFromOriginal") is True
        and acceptance.get("allCandidateSamplesMustReportSelectionState") is True,
        "frozen acceptance differs",
    )


def validate_source_hashes(preregistration: Mapping[str, Any]) -> JsonObject:
    expected = mapping(preregistration.get("sourceSHA256"), "source SHA-256")
    observed: JsonObject = {}
    for relative, digest in expected.items():
        require(isinstance(relative, str), "source path is not text")
        require(isinstance(digest, str), f"{relative} SHA-256 is not text")
        actual = sha256_file(REPOSITORY / relative)
        require(actual == digest, f"{relative} SHA-256 differs")
        observed[relative] = actual
    return observed


def macho_build_version(path: Path) -> tuple[int, int, int]:
    raw = path.read_bytes()
    require(len(raw) >= 32, "capture binary is truncated")
    magic, cpu_type, _, _, command_count, command_bytes, _ = struct.unpack_from(
        "<IiiIIII", raw
    )
    require(magic == 0xFEEDFACF, "capture binary is not little-endian Mach-O 64")
    require(cpu_type == 0x0100000C, "capture binary is not arm64")
    offset = 32
    limit = offset + command_bytes
    require(limit <= len(raw), "Mach-O load commands are truncated")
    versions = []
    for _ in range(command_count):
        require(offset + 8 <= limit, "Mach-O load command header is truncated")
        command, size = struct.unpack_from("<II", raw, offset)
        require(size >= 8 and offset + size <= limit, "Mach-O load command differs")
        if command == 0x32:
            require(size >= 24, "LC_BUILD_VERSION is truncated")
            versions.append(struct.unpack_from("<III", raw, offset + 8))
        offset += size
    require(offset == limit, "Mach-O load command extent differs")
    require(len(versions) == 1, "capture binary lacks one LC_BUILD_VERSION")
    return versions[0]


def validate_preflight(path: Path) -> JsonObject:
    require(sha256_file(path) == PREFLIGHT_SHA256, "Retina preflight SHA-256 differs")
    value = load_object(path, "Retina preflight")
    require(
        value.get("localRetinaCaptureSessionPreflightSchemaVersion") == 2
        and value.get("passed") is True
        and value.get("displayActive") is True
        and value.get("displayAsleep") is False
        and value.get("sessionLocked") is False
        and value.get("sessionLoginDone") is True
        and value.get("sessionOnConsole") is True
        and value.get("physicalPixels") == [3456, 2234]
        and value.get("logicalPoints") == [1728, 1117]
        and value.get("backingScaleFactor") == 2,
        "Retina preflight differs",
    )
    return value


def validate_output(output: Mapping[str, Any], expected_file: str) -> None:
    require(
        output.get("bytesPerRow") == 4096
        and output.get("fnv1a64") == "f8e3e56ce9222325"
        and output.get("height") == 1024
        and output.get("width") == 1024
        and output.get("pixelFormat") == 80
        and output.get("rawBytes") == RAW_BYTE_COUNT
        and output.get("rawCapture") is True
        and output.get("rawFile") == expected_file,
        f"{expected_file} output metadata differs",
    )


def validate_comparison(value: Mapping[str, Any]) -> None:
    require(
        value.get("byteCount") == RAW_BYTE_COUNT
        and value.get("compared") is True
        and value.get("exactByteMatch") is True
        and value.get("firstMismatchedByte") == -1
        and value.get("matchingPixelFraction") == 1
        and value.get("maximumChannelDelta") == 0
        and value.get("meanAbsoluteChannelDelta") == 0
        and value.get("mismatchedByteCount") == 0
        and value.get("mismatchedPixelCount") == 0
        and value.get("rootMeanSquareChannelDelta") == 0,
        "intervention comparison differs",
    )


def validate_intervention(
    value: Mapping[str, Any], expected: Mapping[str, Any]
) -> JsonObject:
    name = str(value.get("name"))
    require(
        value.get("float2LittleEndianHex") == expected["hex"],
        f"{name} replacement bytes differ",
    )
    stream_sha256 = str(value.get("mutatedAttributeStreamSHA256"))
    require(stream_sha256 == expected["streamSHA256"], f"{name} stream differs")
    require(stream_sha256 != ORIGINAL_STREAM_SHA256, f"{name} did not change input")
    comparison = mapping(value.get("comparison"), f"{name} comparison")
    validate_comparison(comparison)
    replay = mapping(value.get("replay"), f"{name} replay")
    require(
        replay.get("executed") is True
        and replay.get("encodedCommandCount") == 8
        and replay.get("glassDrawCount") == 0
        and replay.get("stoppedAfterGlass") is False,
        f"{name} replay differs",
    )
    validate_output(
        mapping(replay.get("output"), f"{name} output"), str(expected["rawFile"])
    )
    return {
        "name": name,
        "replacementLittleEndianHex": expected["hex"],
        "mutatedAttributeStreamSHA256": stream_sha256,
        "rawFile": expected["rawFile"],
        "comparedBytes": RAW_BYTE_COUNT,
        "unequalBytes": 0,
        "unequalPixels": 0,
        "maximumChannelDelta": 0,
    }


def validate_timeline(path: Path) -> tuple[JsonObject, list[JsonObject]]:
    require(sha256_file(path) == TIMELINE_SHA256, "timeline SHA-256 differs")
    timeline = load_object(path, "transition timeline")
    geometry = mapping(timeline.get("geometry"), "geometry")
    require(
        timeline.get("schemaVersion") == 5
        and timeline.get("material") == "clear"
        and timeline.get("appearance") == "dark"
        and timeline.get("direction") == "materialize"
        and timeline.get("expectedWindowPixels") == [2048, 2048]
        and timeline.get("windowBackingScaleFactor") == 2
        and geometry.get("name") == "circle-combined-holdout-02",
        "timeline envelope differs",
    )
    dynamic = mapping(timeline.get("dynamicBackgroundUniforms"), "dynamic capture")
    require(
        dynamic.get("schemaVersion") == 9
        and dynamic.get("evidenceMode") == "controlled-replay-v1"
        and dynamic.get("requested") is True
        and dynamic.get("executed") is True
        and dynamic.get("sampleCount") == 32
        and dynamic.get("executedSampleCount") == 32
        and dynamic.get("sampleIndices") == list(range(1, 33)),
        "dynamic capture envelope differs",
    )
    records = [
        mapping(value, "dynamic record")
        for value in sequence(dynamic.get("records"), "dynamic records")
    ]
    require(
        [record.get("sampleIndex") for record in records] == list(range(1, 33)),
        "dynamic record order differs",
    )

    selected_count = 0
    eligible_count = 0
    rejected_count = 0
    intervention_results: list[JsonObject] = []
    for record in records[:31]:
        sample_index = int(record["sampleIndex"])
        render = mapping(record.get("render"), "dynamic render")
        replay = mapping(render.get("exactPassReplay"), "exact pass replay")
        if sample_index >= 28:
            require(
                replay.get("executed") is False
                and replay.get("reason")
                == "captured no-background Iscd render pass unavailable",
                f"sample {sample_index} ineligible selection state differs",
            )
            rejected_count += 1
            continue

        source = mapping(
            replay.get("finalHighlightSourceIntervention"),
            "final highlight source intervention",
        )
        require(
            source.get("schemaVersion") == INTERVENTION_SCHEMA_VERSION
            and source.get("eligible") is True
            and source.get("pipelineLabel") == PIPELINE
            and source.get("indexCount") == 6,
            f"sample {sample_index} source selection differs",
        )
        eligible_count += 1
        if sample_index != 1:
            require(
                source.get("selected") is False
                and source.get("executed") is False
                and source.get("selectedCapture") == "transition-background-uniform-01"
                and source.get("reason") == "earlier eligible Iscd candidate selected",
                f"sample {sample_index} later-candidate state differs",
            )
            continue

        selected_count += 1
        require(
            source.get("selected") is True
            and source.get("executed") is True
            and source.get("classification")
            == "captured Apple Iscd source pixel-influence intervention"
            and source.get("liveAppleFrameMutated") is False
            and source.get("capturedApplePipelinesUnmodified") is True
            and source.get("currentBackgroundDrawObserved") is False
            and source.get("vertexCount") == 4
            and source.get("stride") == 48
            and source.get("attributeIndex") == 2
            and source.get("attributeOffset") == 24
            and source.get("attributeFormat") == "float2"
            and source.get("pipelineDescriptorAvailable") is False
            and source.get("descriptorMatchesFrozenLayout") is False
            and source.get("originalAttributeStreamSHA256") == ORIGINAL_STREAM_SHA256
            and source.get("interventionCount") == 2
            and source.get("allInterventionsExact") is True,
            "selected intervention metadata differs",
        )
        observed = {
            str(mapping(item, "intervention").get("name")): mapping(
                item, "intervention"
            )
            for item in sequence(source.get("interventions"), "interventions")
        }
        require(
            set(observed) == set(EXPECTED_INTERVENTIONS),
            "intervention inventory differs",
        )
        for name, expected in EXPECTED_INTERVENTIONS.items():
            intervention_results.append(validate_intervention(observed[name], expected))

    require(selected_count == 1, "selected sample count differs")
    require(eligible_count == 27, "eligible sample count differs")
    require(rejected_count == 4, "ineligible sample count differs")
    return (
        {
            "selectedSampleIndex": 1,
            "eligibleSampleCount": eligible_count,
            "ineligibleSampleCount": rejected_count,
            "candidateSampleCount": 31,
        },
        intervention_results,
    )


def compare_raw_files(root: Path, name: str, expected: Mapping[str, Any]) -> JsonObject:
    reference_path = root / REFERENCE_FILE
    candidate_path = root / str(expected["rawFile"])
    require(reference_path.stat().st_size == RAW_BYTE_COUNT, "reference size differs")
    require(candidate_path.stat().st_size == RAW_BYTE_COUNT, f"{name} size differs")
    require(sha256_file(reference_path) == RAW_SHA256, "reference SHA-256 differs")
    require(sha256_file(candidate_path) == RAW_SHA256, f"{name} SHA-256 differs")
    reference = reference_path.read_bytes()
    candidate = candidate_path.read_bytes()
    unequal = [
        index
        for index, (left, right) in enumerate(zip(reference, candidate, strict=True))
        if left != right
    ]
    unequal_pixels = {index // 4 for index in unequal}
    maximum_delta = max(
        (abs(reference[index] - candidate[index]) for index in unequal), default=0
    )
    require(not unequal, f"{name} raw output differs")

    status_path = root / str(expected["statusFile"])
    require(
        sha256_file(status_path) == expected["statusSHA256"],
        f"{name} status SHA-256 differs",
    )
    status = load_object(status_path, f"{name} status")
    require(
        status.get("schemaVersion") == 75
        and status.get("capture") == "transition-background-uniform-01"
        and status.get("candidate") == f"final-highlight-source-{name}"
        and status.get("commandBufferStatus") == 4
        and status.get("commandBufferError") == "",
        f"{name} command status differs",
    )
    return {
        "name": name,
        "referenceSHA256": RAW_SHA256,
        "candidateSHA256": RAW_SHA256,
        "comparedBytes": RAW_BYTE_COUNT,
        "unequalBytes": len(unequal),
        "unequalPixels": len(unequal_pixels),
        "maximumChannelDelta": maximum_delta,
        "exact": not unequal,
    }


def validate(root: Path, preregistration_path: Path) -> JsonObject:
    require(
        sha256_file(preregistration_path) == PREREGISTRATION_SHA256,
        "preregistration SHA-256 differs",
    )
    preregistration = load_object(preregistration_path, "preregistration")
    validate_preregistration_value(preregistration)
    source_hashes = validate_source_hashes(preregistration)

    binary = root / BINARY_FILE
    require(sha256_file(binary) == CAPTURE_BINARY_SHA256, "capture binary differs")
    require(
        b"/nix/store/" not in binary.read_bytes(), "capture binary contains Nix path"
    )
    platform, minimum_os, sdk = macho_build_version(binary)
    require(
        (platform, minimum_os, sdk) == (1, 0x1A0000, 0x1A0500), "build version differs"
    )
    preflight = validate_preflight(root / PREFLIGHT_FILE)
    selection, interventions = validate_timeline(root / "transition-timeline.json")

    raw_results = []
    for name, expected in EXPECTED_INTERVENTIONS.items():
        raw_results.append(compare_raw_files(root, name, expected))
    require(all(item["exact"] for item in raw_results), "raw comparison is not exact")

    return {
        "finalHighlightSourceInterventionResultSchemaVersion": RESULT_SCHEMA_VERSION,
        "classification": (
            "prospective exact complete-frame pixel-influence intervention"
        ),
        "status": "exact-pixel-noninfluence",
        "preregistrationSHA256": PREREGISTRATION_SHA256,
        "timelineSHA256": TIMELINE_SHA256,
        "captureBinarySHA256": CAPTURE_BINARY_SHA256,
        "captureBinary": {
            "architecture": "arm64",
            "minimumOS": "26.0",
            "declaredSDK": "26.5",
            "containsNixStorePath": False,
        },
        "capturePlatform": {
            "operatingSystem": "macOS 26.6.1 build 25G76",
            "device": "Apple M1 Max",
            "physicalPixels": preflight["physicalPixels"],
            "logicalPoints": preflight["logicalPoints"],
            "backingScaleFactor": preflight["backingScaleFactor"],
            "activeUnlockedOnConsole": True,
        },
        "sourceSHA256": source_hashes,
        "selection": selection,
        "pipeline": PIPELINE,
        "vertexLayout": {
            "bufferIndex": 1,
            "vertexCount": 4,
            "stride": 48,
            "attributeIndex": 2,
            "attributeOffset": 24,
            "attributeFormat": "float2",
            "pipelineDescriptorAvailableInCapture": False,
            "authority": "frozen previously decoded current Iscd layout",
        },
        "originalAttributeStreamSHA256": ORIGINAL_STREAM_SHA256,
        "interventions": interventions,
        "independentRawComparisons": raw_results,
        "totalComparedBytes": 2 * RAW_BYTE_COUNT,
        "totalUnequalBytes": 0,
        "totalUnequalPixels": 0,
        "maximumChannelDelta": 0,
        "tolerance": 0,
        "closedAlgorithmBoundary": (
            "current Iscd no-background attribute-2 bytes 24..31 are "
            "observationally pixel-irrelevant"
        ),
        "remainingAppleAlgorithmBoundaries": [
            "small-clear Tghn/Tmua/Tkfh/A2Xghfc construction and pixels"
        ],
        "walleIntegrationMayBeginBehindGates": True,
        "productionParityAuthorized": False,
        "productionShaderChanged": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate(arguments.artifact_root, arguments.preregistration)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
