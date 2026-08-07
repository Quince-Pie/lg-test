#!/usr/bin/env python3
"""Capture complete Parameters for the frozen weighted live Context inputs."""

from __future__ import annotations

import argparse
import json
import platform
import re
import struct
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple

import capture_designlibrary_environment_parameters_local_macos_26_6_1 as environment
import capture_designlibrary_material_context_flags_live_timeline_transfer_local_macos_26_6_1 as flags
import capture_designlibrary_material_context_live_timeline_transfer_local_macos_26_6_1 as base
import capture_designlibrary_parameters_mixer_basis_local_macos_26_6_1 as basis
import capture_designlibrary_public_parameters_local_macos_26_6_1 as public


SCHEMA_VERSION = 1
FRESH_PROCESS_COUNT = 3
PROBE_SOURCE_NAME = (
    "probe_designlibrary_material_context_weighted_live_timeline_"
    "parameters_local_macos_26_6_1.c"
)
LLDB_ADAPTER_NAME = (
    "capture_designlibrary_material_context_weighted_live_timeline_"
    "parameters_local_macos_26_6_1_lldb.py"
)
PREREGISTRATION_NAME = (
    "designlibrary_material_context_weighted_live_timeline_"
    "parameters_local_macos_26_6_1_preregistration.json"
)
FLAGS_PREREGISTRATION_NAME = (
    "designlibrary_material_context_flags_live_timeline_"
    "transfer_local_macos_26_6_1_preregistration.json"
)
FLAGS_RESULT_NAME = (
    "designlibrary_material_context_flags_live_timeline_"
    "transfer_local_macos_26_6_1_result.json"
)
CONTEXT_LAW_RESULT_NAME = (
    "designlibrary_material_context_live_timeline_law_analysis_result.json"
)
BLEND_PIPELINE_RESULT_NAME = (
    "designlibrary_parameters_animatable_blend_pipeline_local_macos_26_6_1_result.json"
)
WEIGHT_PIPELINE_RESULT_NAME = (
    "designlibrary_resolved_composite_weight_pipeline_local_macos_26_6_1_result.json"
)
EXPECTED_PREREGISTRATION_SHA256 = (
    "ad258aac128dc1f4b6e636b63e4f412a57ad80450bb7f0b66d904e9096a46771"
)
EXPECTED_FLAGS_PREREGISTRATION_SHA256 = (
    "e9bb1fd4e05d1744961366721f6118cd206a141cce61ce08550bf9341d60ad8b"
)
EXPECTED_FLAGS_RESULT_SHA256 = (
    "7df7230548463675d00a7bc78dac0003cd08a9beb19e9b53268b3a6073c15ac7"
)
EXPECTED_CONTEXT_LAW_RESULT_SHA256 = (
    "e3520a6819728117646fa2e4bb53801fa50cf1546e4901061f4e7c2d05e18c6e"
)
EXPECTED_BLEND_PIPELINE_RESULT_SHA256 = (
    "ab702bb92880f277cc525d19c405c15909c8ece1d778d4f27895b694e54f0f2b"
)
EXPECTED_WEIGHT_PIPELINE_RESULT_SHA256 = (
    "f5e87599e3eb8e6a734e0618b51b077742bb04558355b2dad48a580b51edb558"
)
EXPECTED_FLAGS_BITS = "0x0000000000099183"
CASE_NAMES = tuple("sample_{0:02d}".format(index) for index in range(1, 33))
EXPECTED_CASE_NAMES = tuple(
    "material_context_weighted_live:" + name for name in CASE_NAMES
)
RUNTIME_PATTERN = re.compile(
    r"^WEIGHTED_LIVE_MATERIAL_CONTEXT_CASE "
    r"(material_context_weighted_live:\S+) flags=(0x[0-9a-f]{16}) "
    r"fraction_bits=(0x[0-9a-f]{16}) "
    r"dimension_bits=(0x[0-9a-f]{16})$"
)
FIELD_TRANSFER = (
    ("shadow.amount", 40, "inputShadowAmount"),
    ("blur.radius", 176, "inputBlurRadiusTimesTwo"),
    ("refraction.innerAmount", 264, "inputInnerRefractionAmount"),
    ("edgeBleed.amount", 392, "inputBleedAmount"),
)


class CaptureError(RuntimeError):
    """Raised when the weighted live-timeline capture differs."""


def load_json(path: Path, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CaptureError(label + " is unreadable") from error
    if not isinstance(value, dict):
        raise CaptureError(label + " is not an object")
    return value


def parse_runtime(
    output: str,
    frozen_cases: Sequence[Sequence[object]],
) -> Sequence[Mapping[str, object]]:
    records: List[Mapping[str, object]] = []
    for line in output.splitlines():
        match = RUNTIME_PATTERN.fullmatch(line)
        if match is None:
            continue
        records.append(
            {
                "qualifiedName": match.group(1),
                "flagsBits": match.group(2),
                "fractionBits": match.group(3),
                "dimensionBits": match.group(4),
            }
        )
    expected = [
        {
            "qualifiedName": "material_context_weighted_live:" + str(case[0]),
            "flagsBits": EXPECTED_FLAGS_BITS,
            "fractionBits": str(case[1]),
            "dimensionBits": str(case[2]),
        }
        for case in frozen_cases
    ]
    if records != expected:
        raise CaptureError("weighted live-timeline runtime inputs differ")
    return records


def normalized_payload(
    case: Mapping[str, object],
    unique: Mapping[str, object],
) -> bytes:
    digest = case.get("normalizedParametersSHA256")
    record = unique.get(digest)
    if not isinstance(digest, str) or not isinstance(record, dict):
        raise CaptureError("direct Parameters record is absent")
    try:
        payload = bytes.fromhex(str(record["normalizedHex"]))
    except (KeyError, ValueError) as error:
        raise CaptureError("direct Parameters payload differs") from error
    if (
        len(payload) != basis.PARAMETERS_BYTE_COUNT
        or environment.digest_bytes(payload) != digest
        or basis.normalize_parameters(payload) != payload
    ):
        raise CaptureError("direct Parameters identity differs")
    return payload


def scalar_record(payload: bytes, offset: int) -> Mapping[str, object]:
    raw = payload[offset : offset + 8]
    if len(raw) != 8:
        raise CaptureError("Parameters scalar range differs")
    return {
        "offset": offset,
        "value": struct.unpack("<d", raw)[0],
        "rawLittleEndianHex": raw.hex(),
    }


def changed_field_records(
    direct: bytes,
    weighted: bytes,
) -> Tuple[
    Sequence[Mapping[str, object]],
    Sequence[str],
    Sequence[str],
    Sequence[str],
]:
    scalars: List[Mapping[str, object]] = []
    for field in basis.SCALAR_FIELDS:
        size = struct.calcsize("<" + field.format)
        direct_raw = direct[field.offset : field.offset + size]
        weighted_raw = weighted[field.offset : field.offset + size]
        if direct_raw == weighted_raw:
            continue
        scalars.append(
            {
                "field": field.name,
                "offset": field.offset,
                "storage": "binary32" if field.format == "f" else "binary64",
                "directRawLittleEndianHex": direct_raw.hex(),
                "weightedRawLittleEndianHex": weighted_raw.hex(),
                "directValue": struct.unpack("<" + field.format, direct_raw)[0],
                "weightedValue": struct.unpack("<" + field.format, weighted_raw)[0],
            }
        )
    colors = [
        field.name
        for field in basis.COLOR_FIELDS
        if direct[field.offset : field.offset + 17]
        != weighted[field.offset : field.offset + 17]
    ]
    presences = []
    discrete = []
    for name, (offset, _present, nil_value) in basis.CONTAINER_PRESENCE.items():
        direct_present = direct[offset] != nil_value
        weighted_present = weighted[offset] != nil_value
        if direct_present != weighted_present:
            presences.append(name)
        elif name == "edgeBleed" and direct[offset] != weighted[offset]:
            discrete.append("edgeBleed.useDarkenBlending")
    return scalars, colors, presences, discrete


def validate_predecessors(
    paths: Mapping[str, Path],
) -> Tuple[
    Sequence[Sequence[object]],
    Sequence[Sequence[object]],
    Mapping[str, object],
]:
    expected_hashes = {
        "preregistration": EXPECTED_PREREGISTRATION_SHA256,
        "flagsPreregistration": EXPECTED_FLAGS_PREREGISTRATION_SHA256,
        "flagsResult": EXPECTED_FLAGS_RESULT_SHA256,
        "contextLawResult": EXPECTED_CONTEXT_LAW_RESULT_SHA256,
        "blendPipelineResult": EXPECTED_BLEND_PIPELINE_RESULT_SHA256,
        "weightPipelineResult": EXPECTED_WEIGHT_PIPELINE_RESULT_SHA256,
    }
    for name, expected in expected_hashes.items():
        if environment.sha256(paths[name]) != expected:
            raise CaptureError(name + " identity differs")
    preregistration = load_json(paths["preregistration"], "preregistration")
    if preregistration.get(
        "designLibraryMaterialContextWeightedLiveTimelineParametersPreregistrationSchemaVersion"
    ) != 1 or preregistration.get("predecessors") != {
        "flagsLiveTransferPreregistrationSHA256": (
            EXPECTED_FLAGS_PREREGISTRATION_SHA256
        ),
        "flagsLiveTransferResultSHA256": EXPECTED_FLAGS_RESULT_SHA256,
        "contextLiveTimelineLawResultSHA256": (EXPECTED_CONTEXT_LAW_RESULT_SHA256),
        "parametersAnimatableBlendPipelineResultSHA256": (
            EXPECTED_BLEND_PIPELINE_RESULT_SHA256
        ),
        "resolvedCompositeWeightPipelineResultSHA256": (
            EXPECTED_WEIGHT_PIPELINE_RESULT_SHA256
        ),
    }:
        raise CaptureError("weighted preregistration authority differs")
    outcomes = preregistration.get("outcomes")
    if not isinstance(outcomes, dict) or any(
        value is not None for value in outcomes.values()
    ):
        raise CaptureError("weighted preregistration outcomes are opened")
    frozen_cases, expected_words = flags.validate_preregistration(
        paths["flagsPreregistration"]
    )
    direct_result = load_json(paths["flagsResult"], "direct flags-live result")
    context_law = load_json(paths["contextLawResult"], "Context law result")
    blend = load_json(paths["blendPipelineResult"], "blend pipeline result")
    weights = load_json(paths["weightPipelineResult"], "weight pipeline result")
    if (
        direct_result.get("claims", {}).get(
            "exactFlagsProducedContextToOpenedLivePublicFieldsTransferEstablished"
        )
        is not True
        or context_law.get("claims", {}).get(
            "exactObservedTimelineContextValueLawEstablished"
        )
        is not True
        or blend.get("claims", {}).get("weightedParametersBlendPipelineEstablished")
        is not True
        or weights.get("claims", {}).get(
            "recipeBuilderD9FactorComesFromResolvedCompositeValues"
        )
        is not True
    ):
        raise CaptureError("weighted predecessor authority differs")
    direct_cases = direct_result.get("cases")
    if not isinstance(direct_cases, list) or len(direct_cases) != len(frozen_cases):
        raise CaptureError("direct flags-live case table differs")
    for direct, frozen in zip(direct_cases, frozen_cases):
        if (
            direct.get("name") != frozen[0]
            or direct.get("fractionBits") != frozen[1]
            or direct.get("shapeDimensionBits") != frozen[2]
        ):
            raise CaptureError("direct flags-live input identity differs")
    return frozen_cases, expected_words, direct_result


def capture(output_path: Path) -> Mapping[str, object]:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise CaptureError("capture requires native arm64 macOS")
    public.EXPECTED_CASE_NAMES = EXPECTED_CASE_NAMES
    public.EXPECTED_LAYOUTS = {
        "Configuration": (144, 144, "0x00030007", 2147483647),
        "GlassMaterialProvider": (144, 144, "0x00030007", 2147483647),
        "State": (305, 312, "0x00030007", 2147483647),
        "Resolved": (321, 328, "0x00030007", 2147483647),
        "Material.Context": (73, 80, "0x02030007", 2147483646),
        "Material.ShapeMetrics": (24, 24, "0x02000007", 0),
    }
    product_version = public.command_output(
        ("/usr/bin/sw_vers", "-productVersion")
    ).strip()
    build_version = public.command_output(("/usr/bin/sw_vers", "-buildVersion")).strip()
    hardware_model = public.command_output(
        ("/usr/sbin/sysctl", "-n", "hw.model")
    ).strip()
    if (
        product_version != public.EXPECTED_PRODUCT_VERSION
        or build_version != public.EXPECTED_BUILD_VERSION
        or hardware_model != public.EXPECTED_HARDWARE_MODEL
    ):
        raise CaptureError("host differs from the frozen target profile")

    analysis_directory = Path(__file__).resolve().parent
    capture_source = Path(__file__).resolve()
    probe_source = analysis_directory / PROBE_SOURCE_NAME
    adapter = analysis_directory / LLDB_ADAPTER_NAME
    bridge_source = analysis_directory / public.BRIDGE_SOURCE_NAME
    paths = {
        "preregistration": analysis_directory / PREREGISTRATION_NAME,
        "flagsPreregistration": analysis_directory / FLAGS_PREREGISTRATION_NAME,
        "flagsResult": analysis_directory / FLAGS_RESULT_NAME,
        "contextLawResult": analysis_directory / CONTEXT_LAW_RESULT_NAME,
        "blendPipelineResult": analysis_directory / BLEND_PIPELINE_RESULT_NAME,
        "weightPipelineResult": analysis_directory / WEIGHT_PIPELINE_RESULT_NAME,
    }
    required = (capture_source, probe_source, adapter, bridge_source, *paths.values())
    if any(not path.is_file() for path in required):
        raise CaptureError("weighted capture source set is incomplete")
    if any("/nix/store" in str(path) for path in required):
        raise CaptureError("weighted capture source path contains a Nix store path")
    frozen_cases, expected_words, direct_result = validate_predecessors(paths)

    traces = []
    runtimes = []
    runtime_records = []
    lldb_log_sha256 = []
    with tempfile.TemporaryDirectory(prefix="lg-context-weighted-live-") as temporary:
        temporary_directory = Path(temporary)
        executable = temporary_directory / "probe"
        public.run_command(
            (
                str(public.XCRUN),
                "clang",
                "-std=c2x",
                "-arch",
                "arm64",
                "-O2",
                "-g",
                "-Wall",
                "-Wextra",
                "-Wconversion",
                "-Wsign-conversion",
                "-Werror",
                str(probe_source),
                str(bridge_source),
                "-o",
                str(executable),
            ),
            cwd=temporary_directory,
            environment=public.native_environment(),
        )
        executable_raw = executable.read_bytes()
        if b"/nix/store" in executable_raw:
            raise CaptureError("native probe embeds a Nix store path")
        executable_sha256 = environment.digest_bytes(executable_raw)
        for run_index in range(FRESH_PROCESS_COUNT):
            run_directory = temporary_directory / "run-{0}".format(run_index)
            run_directory.mkdir()
            trace, runtime, log_digest = public.run_lldb_capture(
                executable, adapter, run_directory
            )
            runtime_output = (run_directory / "runtime-stdout.log").read_text(
                encoding="utf-8"
            )
            traces.append(trace)
            runtimes.append(runtime)
            runtime_records.append(parse_runtime(runtime_output, frozen_cases))
            lldb_log_sha256.append(log_digest)

    raw_by_run = [public.validate_trace(trace) for trace in traces]
    normalized_by_run = [
        [basis.normalize_parameters(payload) for payload in payloads]
        for payloads in raw_by_run
    ]
    if any(run != normalized_by_run[0] for run in normalized_by_run[1:]):
        raise CaptureError("weighted Parameters vary across fresh processes")
    if any(runtime != runtimes[0] for runtime in runtimes[1:]):
        raise CaptureError("weighted process records vary")
    if any(record != runtime_records[0] for record in runtime_records[1:]):
        raise CaptureError("weighted runtime inputs vary")

    direct_cases = direct_result["cases"]
    direct_unique = direct_result["uniqueNormalizedParameters"]
    if not isinstance(direct_cases, list) or not isinstance(direct_unique, dict):
        raise CaptureError("direct Parameters table differs")
    unique_weighted: Dict[str, Mapping[str, object]] = {}
    cases: List[Mapping[str, object]] = []
    match_counts = {field: 0 for field, _offset, _public_input in FIELD_TRANSFER}
    total_matches = 0
    endpoint_matches_direct = False
    for index, (frozen, expected, weighted, direct_case) in enumerate(
        zip(
            frozen_cases,
            expected_words,
            normalized_by_run[0],
            direct_cases,
        ),
        start=1,
    ):
        name = str(frozen[0])
        fraction_bits = str(frozen[1])
        dimension_bits = str(frozen[2])
        direct = normalized_payload(direct_case, direct_unique)
        digest = environment.digest_bytes(weighted)
        if digest not in unique_weighted:
            unique_weighted[digest] = {
                "normalizedHex": weighted.hex(),
                "caseNames": [],
            }
        unique_weighted[digest]["caseNames"].append(name)
        predictions = []
        for field_index, (field_name, offset, public_input) in enumerate(
            FIELD_TRANSFER, start=1
        ):
            observed = scalar_record(weighted, offset)
            expected_raw = str(expected[field_index])
            matched = observed["rawLittleEndianHex"] == expected_raw
            if matched:
                match_counts[field_name] += 1
                total_matches += 1
            predictions.append(
                {
                    "field": field_name,
                    "parametersOffset": offset,
                    "publicInput": public_input,
                    "weightedRawLittleEndianHex": observed["rawLittleEndianHex"],
                    "weightedValue": observed["value"],
                    "expectedPublicRawLittleEndianHex": expected_raw,
                    "matchedBitwise": matched,
                }
            )
        changed_offsets = sorted(
            offset
            for offset in basis.SEMANTIC_BYTE_OFFSETS
            if direct[offset] != weighted[offset]
        )
        (
            scalar_changes,
            color_changes,
            presence_changes,
            discrete_changes,
        ) = changed_field_records(direct, weighted)
        if index == len(frozen_cases):
            endpoint_matches_direct = weighted == direct
        cases.append(
            {
                "index": index,
                "name": name,
                "qualifiedName": "material_context_weighted_live:" + name,
                "fraction": base.binary64_from_bits(fraction_bits),
                "fractionBits": fraction_bits,
                "shapeDimension": base.binary64_from_bits(dimension_bits),
                "shapeDimensionBits": dimension_bits,
                "environmentFlagsBits": EXPECTED_FLAGS_BITS,
                "directFactorOneParametersSHA256": environment.digest_bytes(direct),
                "weightedParametersSHA256": digest,
                "changedSemanticByteOffsetsFromDirectFactorOne": changed_offsets,
                "changedSemanticByteCountFromDirectFactorOne": len(changed_offsets),
                "changedScalarFieldsFromDirectFactorOne": scalar_changes,
                "changedColorFieldsFromDirectFactorOne": color_changes,
                "changedContainerPresenceFieldsFromDirectFactorOne": (presence_changes),
                "changedDiscreteFieldsFromDirectFactorOne": discrete_changes,
                "openedPublicPredictions": predictions,
                "allOpenedPublicPredictionsMatchBitwise": all(
                    prediction["matchedBitwise"] for prediction in predictions
                ),
                "rawParametersSHA256ByFreshProcess": [
                    environment.digest_bytes(raw_by_run[run_index][index - 1])
                    for run_index in range(FRESH_PROCESS_COUNT)
                ],
            }
        )
    expected_total_matches = len(frozen_cases) * len(FIELD_TRANSFER)
    if total_matches != expected_total_matches or any(
        count != len(frozen_cases) for count in match_counts.values()
    ):
        raise CaptureError("weighted Parameters opened-public transfer differs")
    if not endpoint_matches_direct:
        raise CaptureError("factor-one endpoint is not the exact direct payload")

    result = {
        "designLibraryMaterialContextWeightedLiveTimelineParametersCaptureSchemaVersion": (
            SCHEMA_VERSION
        ),
        "classification": (
            "prospectively frozen controlled headless reconstruction candidate: "
            "each retained produced-flags regular-light fraction is installed as "
            "the sole ResolvedComposite dictionary weight, its exact Context "
            "dimension is installed independently, and Apple's authenticated "
            "weighted recipe builder returns the complete Parameters value; no "
            "GUI callback or captured Parameters byte selects runtime behavior"
        ),
        "host": {
            "system": platform.system(),
            "machine": platform.machine(),
            "macOSProductVersion": product_version,
            "macOSBuildVersion": build_version,
            "hardwareModel": hardware_model,
        },
        "predecessors": {
            name: {
                "path": "Analysis/" + path.name,
                "sha256": environment.sha256(path),
            }
            for name, path in paths.items()
        },
        "tool": {
            "python": sys.version.split()[0],
            "clang": public.command_output(
                (str(public.XCRUN), "clang", "--version")
            ).splitlines()[0],
            "captureSource": "Analysis/" + capture_source.name,
            "captureSourceSHA256": environment.sha256(capture_source),
            "probeSource": "Analysis/" + probe_source.name,
            "probeSourceSHA256": environment.sha256(probe_source),
            "lldbAdapter": "Analysis/" + adapter.name,
            "lldbAdapterSHA256": environment.sha256(adapter),
            "assemblyBridgeSHA256": environment.sha256(bridge_source),
            "probeExecutableSHA256": executable_sha256,
            "probeExecutableContainsNixStorePath": False,
            "freshProcessCount": FRESH_PROCESS_COUNT,
            "lldbLogSHA256ByFreshProcess": lldb_log_sha256,
        },
        "cases": cases,
        "uniqueWeightedNormalizedParameters": unique_weighted,
        "measuredInvariants": {
            "caseCount": len(cases),
            "parametersBuildsPerCase": 1,
            "freshProcessSemanticStabilityEstablished": True,
            "environmentFlagsMatchProducedRegularLight": True,
            "resolvedCompositeDictionaryHasOneFrozenBinary64Weight": True,
            "capturedParametersUsedForSelection": False,
            "openedPublicPredictionMatchCounts": match_counts,
            "openedPublicPredictionCount": expected_total_matches,
            "openedPublicPredictionMatchCount": total_matches,
            "factorOneEndpointMatchesDirectParametersBitwise": (
                endpoint_matches_direct
            ),
            "uniqueWeightedNormalizedParametersCount": len(unique_weighted),
        },
        "claims": {
            "controlledCompleteWeightedParametersCandidateEstablished": True,
            "allOpenedLivePublicFieldsReplayBitwise": True,
            "factorOneFastPathReproducedBitwise": True,
            "actualLiveCallbackCompleteParametersObserved": False,
            "completeLiveParametersTransferEstablished": False,
            "generalContextToParametersValueLawEstablished": False,
            "generalIntegerCropAllocationPolicyEstablished": False,
            "retinaCompositorColorLawEstablished": False,
            "independentWalleZeroByteFrameParityEstablished": False,
            "liquidGlassParityEstablished": False,
            "productionShaderChangeAuthorized": False,
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    try:
        capture(arguments.output.resolve())
    except CaptureError as error:
        print("CAPTURE_ERROR: " + str(error), file=sys.stderr)
        return 1
    print(str(arguments.output.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
