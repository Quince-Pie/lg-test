#!/usr/bin/env python3
"""Transfer zero-flags shape-context Parameters into retained live words."""

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
import capture_designlibrary_parameters_mixer_basis_local_macos_26_6_1 as basis
import capture_designlibrary_public_parameters_local_macos_26_6_1 as public


SCHEMA_VERSION = 1
FRESH_PROCESS_COUNT = 3
EXPECTED_CONTEXT_RESULT_SHA256 = (
    "e707178e4f5e6e14d75fa0a953daa834e538be3981e855a2ecc18325aca0167b"
)
EXPECTED_JOIN_RESULT_SHA256 = (
    "00fab84d0c6163629da387ea4e0f50884ee40b9f04842646fe01a36936b50e3d"
)
EXPECTED_PUBLIC_TIMELINE_SHA256 = (
    "1dd73cfa4e696c43a0612c107e9a5edcb78c72b14ba80e67a53e4e99b06d931f"
)

PROBE_SOURCE_NAME = (
    "probe_designlibrary_material_context_live_timeline_transfer_local_macos_26_6_1.c"
)
BASE_CONTEXT_PROBE_SOURCE_NAME = (
    "probe_designlibrary_material_context_parameters_local_macos_26_6_1.c"
)
BASE_PUBLIC_PROBE_SOURCE_NAME = public.PROBE_SOURCE_NAME
BRIDGE_SOURCE_NAME = public.BRIDGE_SOURCE_NAME
LLDB_ADAPTER_NAME = "capture_designlibrary_material_context_live_timeline_transfer_local_macos_26_6_1_lldb.py"
BASE_LLDB_ADAPTER_NAME = (
    "capture_designlibrary_public_parameters_local_macos_26_6_1_lldb.py"
)
PREREGISTRATION_NAME = "designlibrary_material_context_live_timeline_transfer_local_macos_26_6_1_preregistration.json"
CONTEXT_RESULT_NAME = (
    "designlibrary_material_context_parameters_local_macos_26_6_1_result.json"
)
JOIN_RESULT_NAME = (
    "backdrop_margin_case22_provider_public_timeline_join_retrospective_result.json"
)

CASE_NAMES = tuple("sample_{0:02d}".format(index) for index in range(1, 32))
EXPECTED_CASE_NAMES = tuple("material_context_live:" + name for name in CASE_NAMES)
EXPECTED_FLAGS_BITS = "0x0000000000000000"
RUNTIME_PATTERN = re.compile(
    r"^LIVE_MATERIAL_CONTEXT_CASE (material_context_live:\S+) "
    r"flags=(0x[0-9a-f]{16}) fraction_bits=(0x[0-9a-f]{16}) "
    r"dimension_bits=(0x[0-9a-f]{16})$"
)
FIELD_TRANSFER = (
    ("shadow.amount", 40, 24),
    ("blur.radius", 176, 152),
    ("refraction.innerAmount", 264, 232),
    ("edgeBleed.amount", 392, 352),
)


class CaptureError(RuntimeError):
    """Raised when the frozen live-timeline transfer differs."""


def load_json(path: Path, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CaptureError(label + " is unreadable") from error
    if not isinstance(value, dict):
        raise CaptureError(label + " is not an object")
    return value


def binary64_from_bits(bits: str) -> float:
    try:
        word = int(bits, 16)
        return struct.unpack("<d", struct.pack("<Q", word))[0]
    except (ValueError, struct.error) as error:
        raise CaptureError("invalid binary64 word " + str(bits)) from error


def binary64_raw(value: float) -> str:
    return struct.pack("<d", value).hex()


def validate_preregistration(
    path: Path,
) -> Tuple[Sequence[Sequence[object]], Sequence[Sequence[object]]]:
    value = load_json(path, "live-timeline transfer preregistration")
    if (
        value.get(
            "designLibraryMaterialContextLiveTimelineTransferPreregistrationSchemaVersion"
        )
        != 1
    ):
        raise CaptureError("live-timeline transfer preregistration schema differs")
    predecessors = value.get("predecessors")
    if not isinstance(predecessors, dict) or predecessors != {
        "flagsProducedContextMatrixSHA256": EXPECTED_CONTEXT_RESULT_SHA256,
        "providerPublicTimelineJoinSHA256": EXPECTED_JOIN_RESULT_SHA256,
        "publicTimelineSHA256": EXPECTED_PUBLIC_TIMELINE_SHA256,
    }:
        raise CaptureError("live-timeline predecessor identities differ")
    cases = value.get("cases")
    expected_words = value.get("expectedLiveSignatureWords")
    if not isinstance(cases, list) or not isinstance(expected_words, list):
        raise CaptureError("live-timeline frozen table is absent")
    if len(cases) != 31 or len(expected_words) != 31:
        raise CaptureError("live-timeline frozen table length differs")
    for index, (case, words) in enumerate(zip(cases, expected_words), start=1):
        expected_name = "sample_{0:02d}".format(index)
        if (
            not isinstance(case, list)
            or len(case) != 3
            or case[0] != expected_name
            or not isinstance(words, list)
            or len(words) != 5
            or words[0] != index
        ):
            raise CaptureError("live-timeline frozen case order differs")
        for raw in tuple(case[1:]) + tuple(words[1:]):
            if not isinstance(raw, str):
                raise CaptureError("live-timeline frozen word is not text")
            expected_length = 18 if raw.startswith("0x") else 16
            if len(raw) != expected_length:
                raise CaptureError("live-timeline frozen word width differs")
            try:
                int(raw, 16)
            except ValueError as error:
                raise CaptureError("live-timeline frozen word is invalid") from error
    acceptance = value.get("acceptance")
    if not isinstance(acceptance, dict) or acceptance.get("freshProcessCount") != 3:
        raise CaptureError("live-timeline frozen acceptance differs")
    outcomes = value.get("outcomes")
    if not isinstance(outcomes, dict) or any(
        outcome is not None for outcome in outcomes.values()
    ):
        raise CaptureError("live-timeline preregistration outcomes are opened")
    return cases, expected_words


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
            "qualifiedName": "material_context_live:" + str(case[0]),
            "flagsBits": EXPECTED_FLAGS_BITS,
            "fractionBits": str(case[1]),
            "dimensionBits": str(case[2]),
        }
        for case in frozen_cases
    ]
    if records != expected:
        raise CaptureError("live-timeline runtime input records differ")
    return records


def scalar(payload: bytes, offset: int) -> Mapping[str, object]:
    raw = payload[offset : offset + 8]
    if len(raw) != 8:
        raise CaptureError("Parameters scalar range differs")
    return {
        "offset": offset,
        "value": struct.unpack("<d", raw)[0],
        "rawLittleEndianHex": raw.hex(),
    }


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
    base_context_probe = analysis_directory / BASE_CONTEXT_PROBE_SOURCE_NAME
    base_public_probe = analysis_directory / BASE_PUBLIC_PROBE_SOURCE_NAME
    bridge_source = analysis_directory / BRIDGE_SOURCE_NAME
    adapter = analysis_directory / LLDB_ADAPTER_NAME
    base_adapter = analysis_directory / BASE_LLDB_ADAPTER_NAME
    basis_source = Path(basis.__file__).resolve()
    context_result = analysis_directory / CONTEXT_RESULT_NAME
    join_result = analysis_directory / JOIN_RESULT_NAME
    preregistration = analysis_directory / PREREGISTRATION_NAME
    required = (
        capture_source,
        probe_source,
        base_context_probe,
        base_public_probe,
        bridge_source,
        adapter,
        base_adapter,
        basis_source,
        context_result,
        join_result,
        preregistration,
    )
    if any(not path.is_file() for path in required):
        raise CaptureError("live-timeline transfer source set is incomplete")
    if any("/nix/store" in str(path) for path in required):
        raise CaptureError("capture source path contains a Nix store path")
    if environment.sha256(context_result) != EXPECTED_CONTEXT_RESULT_SHA256:
        raise CaptureError("flags-produced context result identity differs")
    if environment.sha256(join_result) != EXPECTED_JOIN_RESULT_SHA256:
        raise CaptureError("provider/public timeline join identity differs")
    frozen_cases, expected_words = validate_preregistration(preregistration)

    traces = []
    runtimes = []
    runtime_records = []
    lldb_log_sha256 = []
    with tempfile.TemporaryDirectory(prefix="lg-context-live-transfer-") as temporary:
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
        raise CaptureError("live-timeline Parameters vary across fresh processes")
    if any(runtime != runtimes[0] for runtime in runtimes[1:]):
        raise CaptureError("live-timeline process records vary")
    if any(record != runtime_records[0] for record in runtime_records[1:]):
        raise CaptureError("live-timeline runtime inputs vary")

    unique_parameters: Dict[str, Mapping[str, object]] = {}
    cases: List[Mapping[str, object]] = []
    match_counts = {name: 0 for name, _source, _provider in FIELD_TRANSFER}
    total_matches = 0
    for index, (frozen, expected, payload) in enumerate(
        zip(frozen_cases, expected_words, normalized_by_run[0]), start=1
    ):
        name = str(frozen[0])
        fraction_bits = str(frozen[1])
        dimension_bits = str(frozen[2])
        fraction = binary64_from_bits(fraction_bits)
        dimension = binary64_from_bits(dimension_bits)
        digest = environment.digest_bytes(payload)
        if digest not in unique_parameters:
            unique_parameters[digest] = {
                "normalizedHex": payload.hex(),
                "caseNames": [],
            }
        unique_parameters[digest]["caseNames"].append(name)
        predictions = []
        for field_index, (field_name, source_offset, provider_offset) in enumerate(
            FIELD_TRANSFER, start=1
        ):
            source = scalar(payload, source_offset)
            predicted_raw = binary64_raw(float(source["value"]) * fraction)
            expected_raw = str(expected[field_index])
            matched = predicted_raw == expected_raw
            if matched:
                match_counts[field_name] += 1
                total_matches += 1
            predictions.append(
                {
                    "field": field_name,
                    "parametersOffset": source_offset,
                    "providerOffset": provider_offset,
                    "headlessRawLittleEndianHex": source["rawLittleEndianHex"],
                    "headlessValue": source["value"],
                    "predictedLiveRawLittleEndianHex": predicted_raw,
                    "expectedLiveRawLittleEndianHex": expected_raw,
                    "matchedBitwise": matched,
                }
            )
        cases.append(
            {
                "index": index,
                "name": name,
                "qualifiedName": "material_context_live:" + name,
                "fraction": fraction,
                "fractionBits": fraction_bits,
                "shapeDimension": dimension,
                "shapeDimensionBits": dimension_bits,
                "environmentFlagsBits": EXPECTED_FLAGS_BITS,
                "normalizedParametersSHA256": digest,
                "providerPredictions": predictions,
                "allProviderPredictionsMatchBitwise": all(
                    prediction["matchedBitwise"] for prediction in predictions
                ),
                "rawParametersSHA256ByFreshProcess": [
                    environment.digest_bytes(raw_by_run[run_index][index - 1])
                    for run_index in range(FRESH_PROCESS_COUNT)
                ],
            }
        )
    expected_matches_per_field = len(CASE_NAMES)
    expected_total_matches = expected_matches_per_field * len(FIELD_TRANSFER)
    if total_matches != expected_total_matches or any(
        count != expected_matches_per_field for count in match_counts.values()
    ):
        raise CaptureError("zero-flags live provider transfer differs")

    result = {
        "designLibraryMaterialContextLiveTimelineTransferCaptureSchemaVersion": (
            SCHEMA_VERSION
        ),
        "classification": (
            "prospectively frozen zero-flags Material.Context dimensions run "
            "through Apple's exact Parameters builder in fresh headless native "
            "processes, then transferred by the already-proved binary64 scale "
            "operation into independently retained live provider words"
        ),
        "host": {
            "system": platform.system(),
            "machine": platform.machine(),
            "macOSProductVersion": product_version,
            "macOSBuildVersion": build_version,
            "hardwareModel": hardware_model,
        },
        "predecessors": {
            "flagsProducedContextMatrix": {
                "path": "Analysis/" + context_result.name,
                "sha256": environment.sha256(context_result),
            },
            "providerPublicTimelineJoin": {
                "path": "Analysis/" + join_result.name,
                "sha256": environment.sha256(join_result),
            },
            "publicTimeline": {
                "path": (
                    "artifacts/local-case22-provider-object-matrix-minimal-"
                    "retry2-b694a91-run1/transition-timeline.json"
                ),
                "sha256": EXPECTED_PUBLIC_TIMELINE_SHA256,
            },
            "preregistration": {
                "path": "Analysis/" + preregistration.name,
                "sha256": environment.sha256(preregistration),
            },
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
            "baseContextProbeSourceSHA256": environment.sha256(base_context_probe),
            "basePublicProbeSourceSHA256": environment.sha256(base_public_probe),
            "assemblyBridgeSHA256": environment.sha256(bridge_source),
            "lldbAdapter": "Analysis/" + adapter.name,
            "lldbAdapterSHA256": environment.sha256(adapter),
            "baseLldbAdapterSHA256": environment.sha256(base_adapter),
            "parametersBasisSourceSHA256": environment.sha256(basis_source),
            "probeExecutableSHA256": executable_sha256,
            "probeExecutableContainsNixStorePath": False,
            "freshProcessCount": FRESH_PROCESS_COUNT,
            "lldbLogSHA256ByFreshProcess": lldb_log_sha256,
        },
        "cases": cases,
        "uniqueNormalizedParameters": unique_parameters,
        "measuredInvariants": {
            "caseCount": len(cases),
            "parametersBuildsPerCase": 1,
            "freshProcessSemanticStabilityEstablished": True,
            "environmentFlagsAreExactZero": True,
            "capturedParametersUsedForSelection": False,
            "providerPredictionMatchCounts": match_counts,
            "totalProviderPredictionCount": expected_total_matches,
            "totalProviderPredictionMatchCount": total_matches,
        },
        "claims": {
            "exactZeroFlagsContextToOpenedLiveProviderFieldsTransferEstablished": True,
            "allThirtyOneNonendpointOpenedLiveProviderFieldsReplayBitwise": True,
            "zeroFlagsAndFlagsProducedProfilesAreDistinctEstablished": True,
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
