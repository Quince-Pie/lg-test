#!/usr/bin/env python3
"""Capture exact Parameters for regular/clear by light/dark profiles."""

from __future__ import annotations

import argparse
import json
import platform
import re
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Mapping

import capture_designlibrary_environment_parameters_local_macos_26_6_1 as environment
import capture_designlibrary_parameters_mixer_basis_local_macos_26_6_1 as basis
import capture_designlibrary_public_parameters_local_macos_26_6_1 as public


SCHEMA_VERSION = 1
EXPECTED_CONFIGURATION_FLAG_SEED_RESULT_SHA256 = (
    "1cf97c5ccf4b51c85c882cce1f8b0b91335ab80508908c4fcc763d9b2768390a"
)
EXPECTED_ENVIRONMENT_FLAGS_RESULT_SHA256 = (
    "3b65ba5764c786a7f82eb3f92084653e0a9f9e85267d70eca7108243dfc8d597"
)
FRESH_PROCESS_COUNT = 3

PROBE_SOURCE_NAME = (
    "probe_designlibrary_material_appearance_parameters_local_macos_26_6_1.c"
)
BASE_PUBLIC_PROBE_SOURCE_NAME = public.PROBE_SOURCE_NAME
BRIDGE_SOURCE_NAME = public.BRIDGE_SOURCE_NAME
LLDB_ADAPTER_NAME = (
    "capture_designlibrary_material_appearance_parameters_local_macos_26_6_1_lldb.py"
)
BASE_LLDB_ADAPTER_NAME = (
    "capture_designlibrary_public_parameters_local_macos_26_6_1_lldb.py"
)
CONFIGURATION_FLAG_SEED_RESULT_NAME = (
    "designlibrary_configuration_flag_seed_local_macos_26_6_1_result.json"
)
ENVIRONMENT_FLAGS_RESULT_NAME = (
    "designlibrary_environment_flags_resolution_local_macos_26_6_1_result.json"
)

PROFILE_CASES = (
    ("regular_light", "regular", "light", "0x0000000000099183"),
    ("regular_dark", "regular", "dark", "0x0000000000099183"),
    ("clear_light", "clear", "light", "0x0000000000088183"),
    ("clear_dark", "clear", "dark", "0x0000000000088183"),
)
EXPECTED_CASE_NAMES = tuple("material_appearance:" + case[0] for case in PROFILE_CASES)

PRODUCER_PATTERN = environment.PRODUCER_PATTERN
FLAGS_PATTERN = re.compile(
    r"^MATERIAL_APPEARANCE_FLAGS "
    r"(material_appearance:\S+) bits=(0x[0-9a-f]{16})$"
)


class CaptureError(RuntimeError):
    """Raised when the exact four-profile Parameters capture differs."""


def load_json(path: Path, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CaptureError(label + " is unreadable") from error
    if not isinstance(value, dict):
        raise CaptureError(label + " is not an object")
    return value


def validate_predecessors(
    configuration_path: Path,
    environment_path: Path,
) -> Mapping[str, object]:
    if (
        environment.sha256(configuration_path)
        != EXPECTED_CONFIGURATION_FLAG_SEED_RESULT_SHA256
        or environment.sha256(environment_path)
        != EXPECTED_ENVIRONMENT_FLAGS_RESULT_SHA256
    ):
        raise CaptureError("profile flags predecessor identity differs")
    configuration = load_json(configuration_path, "Configuration flag-seed result")
    flags = load_json(environment_path, "EnvironmentFlags result")
    if (
        configuration.get("designLibraryConfigurationFlagSeedCaptureSchemaVersion") != 1
        or configuration.get("claims", {}).get("configurationToFlagSeedLawEstablished")
        is not True
        or flags.get("designLibraryEnvironmentFlagsResolutionCaptureSchemaVersion") != 1
        or flags.get("claims", {}).get(
            "publicEnvironmentFlagsProducerBoundaryEstablished"
        )
        is not True
    ):
        raise CaptureError("profile flags predecessor authority differs")
    static_configurations = flags.get("staticConfigurations")
    producer = flags.get("environmentFlagsProducer")
    if not isinstance(static_configurations, list) or not isinstance(producer, dict):
        raise CaptureError("profile flags predecessor table is absent")
    by_name = {
        str(record.get("name")): str(record.get("producedFlagsBits"))
        for record in static_configurations
        if isinstance(record, dict)
    }
    if (
        by_name.get("regular") != PROFILE_CASES[0][3]
        or by_name.get("clear") != PROFILE_CASES[2][3]
    ):
        raise CaptureError("regular/clear baseline flags differ")
    not_read = producer.get("notDirectlyReadEnvironmentFields")
    if not isinstance(not_read, list) or "colorScheme" not in not_read:
        raise CaptureError("color-scheme non-read proof is absent")
    return {
        "regularFlagsBits": by_name["regular"],
        "clearFlagsBits": by_name["clear"],
        "colorSchemeDirectlyReadByFlagsProducer": False,
    }


def parse_extended_runtime(output: str) -> Mapping[str, object]:
    producer_code = None
    flags = []
    for line in output.splitlines():
        match = PRODUCER_PATTERN.fullmatch(line)
        if match is not None:
            if producer_code is not None:
                raise CaptureError("duplicate EnvironmentFlags producer code")
            try:
                producer_code = bytes.fromhex(match.group(1))
            except ValueError as error:
                raise CaptureError("EnvironmentFlags code is invalid") from error
            continue
        match = FLAGS_PATTERN.fullmatch(line)
        if match is not None:
            flags.append((match.group(1), match.group(2)))
    if (
        producer_code is None
        or len(producer_code) != environment.ENVIRONMENT_FLAGS_PRODUCER_BYTE_COUNT
        or environment.digest_bytes(producer_code)
        != environment.EXPECTED_ENVIRONMENT_FLAGS_PRODUCER_SHA256
    ):
        raise CaptureError("EnvironmentFlags producer exact-code identity differs")
    expected = [("material_appearance:" + case[0], case[3]) for case in PROFILE_CASES]
    if flags != expected:
        raise CaptureError("material/appearance flags differ")
    return {
        "producerCodeSHA256": environment.digest_bytes(producer_code),
        "flags": flags,
    }


def profile_changes(
    baseline: bytes,
    payload: bytes,
) -> List[Mapping[str, object]]:
    return environment.semantic_changes(baseline, payload)


def capture(output_path: Path) -> Mapping[str, object]:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise CaptureError("capture requires native arm64 macOS")
    public.EXPECTED_CASE_NAMES = EXPECTED_CASE_NAMES
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
    design_uuid = public.command_output(
        (str(public.DYLD_INFO), "-uuid", str(public.DESIGNLIBRARY))
    )
    swift_uuid = public.command_output(
        (str(public.DYLD_INFO), "-uuid", str(public.SWIFTUICORE))
    )
    if public.EXPECTED_DESIGNLIBRARY_UUID not in design_uuid:
        raise CaptureError("DesignLibrary UUID differs")
    if public.EXPECTED_SWIFTUICORE_UUID not in swift_uuid:
        raise CaptureError("SwiftUICore UUID differs")

    analysis_directory = Path(__file__).resolve().parent
    capture_source = Path(__file__).resolve()
    probe_source = analysis_directory / PROBE_SOURCE_NAME
    public_probe = analysis_directory / BASE_PUBLIC_PROBE_SOURCE_NAME
    bridge_source = analysis_directory / BRIDGE_SOURCE_NAME
    adapter = analysis_directory / LLDB_ADAPTER_NAME
    base_adapter = analysis_directory / BASE_LLDB_ADAPTER_NAME
    basis_source = Path(basis.__file__).resolve()
    public_capture_source = Path(public.__file__).resolve()
    environment_capture_source = Path(environment.__file__).resolve()
    configuration_predecessor = analysis_directory / CONFIGURATION_FLAG_SEED_RESULT_NAME
    environment_predecessor = analysis_directory / ENVIRONMENT_FLAGS_RESULT_NAME
    required = (
        capture_source,
        probe_source,
        public_probe,
        bridge_source,
        adapter,
        base_adapter,
        basis_source,
        public_capture_source,
        environment_capture_source,
        configuration_predecessor,
        environment_predecessor,
    )
    if any(not path.is_file() for path in required):
        raise CaptureError("material/appearance source set is incomplete")
    if any("/nix/store" in str(path) for path in required):
        raise CaptureError("capture source path contains a Nix store path")
    predecessor_law = validate_predecessors(
        configuration_predecessor,
        environment_predecessor,
    )

    traces = []
    runtimes = []
    extensions = []
    lldb_log_sha256 = []
    with tempfile.TemporaryDirectory(prefix="lg-material-appearance-") as temporary:
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
                executable,
                adapter,
                run_directory,
            )
            runtime_output = (run_directory / "runtime-stdout.log").read_text(
                encoding="utf-8"
            )
            extensions.append(parse_extended_runtime(runtime_output))
            traces.append(trace)
            runtimes.append(runtime)
            lldb_log_sha256.append(log_digest)

    raw_by_run = [public.validate_trace(trace) for trace in traces]
    normalized_by_run = [
        [basis.normalize_parameters(payload) for payload in payloads]
        for payloads in raw_by_run
    ]
    if any(run != normalized_by_run[0] for run in normalized_by_run[1:]):
        raise CaptureError("profile Parameters vary across fresh processes")
    if any(runtime != runtimes[0] for runtime in runtimes[1:]):
        raise CaptureError("profile runtime records vary across fresh processes")
    if any(extension != extensions[0] for extension in extensions[1:]):
        raise CaptureError("profile exact-code or flags records vary")

    unique_parameters: Dict[str, Mapping[str, object]] = {}
    baseline = normalized_by_run[0][0]
    cases = []
    for index, (profile, payload) in enumerate(
        zip(PROFILE_CASES, normalized_by_run[0])
    ):
        name, material, appearance, flags_bits = profile
        digest = environment.digest_bytes(payload)
        if digest not in unique_parameters:
            unique_parameters[digest] = {
                "normalizedHex": payload.hex(),
                "caseNames": [],
            }
        unique_parameters[digest]["caseNames"].append(name)
        changed_offsets = [
            offset
            for offset in sorted(basis.SEMANTIC_BYTE_OFFSETS)
            if baseline[offset] != payload[offset]
        ]
        cases.append(
            {
                "index": index,
                "name": name,
                "qualifiedName": "material_appearance:" + name,
                "material": material,
                "appearance": appearance,
                "producedFlagsBits": flags_bits,
                "normalizedParametersSHA256": digest,
                "changedSemanticByteOffsetsFromRegularLight": changed_offsets,
                "changedFieldsFromRegularLight": profile_changes(baseline, payload),
                "rawParametersSHA256ByFreshProcess": [
                    environment.digest_bytes(raw_by_run[run_index][index])
                    for run_index in range(FRESH_PROCESS_COUNT)
                ],
            }
        )

    result = {
        "designLibraryMaterialAppearanceParametersCaptureSchemaVersion": (
            SCHEMA_VERSION
        ),
        "classification": (
            "prospectively fixed direct exact-code EnvironmentFlags production "
            "followed by Apple provider resolution and ResolvedRecipe.Parameters "
            "construction for regular/clear crossed with light/dark internal "
            "Environment state under a default Material.Context; no live SwiftUI "
            "updater, GUI, render, image, crop, pixel, or Nix store path"
        ),
        "host": {
            "system": platform.system(),
            "machine": platform.machine(),
            "macOSProductVersion": product_version,
            "macOSBuildVersion": build_version,
            "hardwareModel": hardware_model,
        },
        "frameworks": {
            "DesignLibrary": {
                "path": str(public.DESIGNLIBRARY),
                "uuid": public.EXPECTED_DESIGNLIBRARY_UUID,
            },
            "SwiftUICore": {
                "path": str(public.SWIFTUICORE),
                "uuid": public.EXPECTED_SWIFTUICORE_UUID,
            },
        },
        "predecessors": {
            "configurationFlagSeed": {
                "path": "Analysis/" + configuration_predecessor.name,
                "sha256": environment.sha256(configuration_predecessor),
            },
            "environmentFlagsResolution": {
                "path": "Analysis/" + environment_predecessor.name,
                "sha256": environment.sha256(environment_predecessor),
            },
            "prospectiveFlagsLaw": predecessor_law,
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
            "basePublicProbeSourceSHA256": environment.sha256(public_probe),
            "assemblyBridgeSHA256": environment.sha256(bridge_source),
            "lldbAdapter": "Analysis/" + adapter.name,
            "lldbAdapterSHA256": environment.sha256(adapter),
            "baseLldbAdapterSHA256": environment.sha256(base_adapter),
            "parametersBasisSourceSHA256": environment.sha256(basis_source),
            "publicParametersCaptureSourceSHA256": environment.sha256(
                public_capture_source
            ),
            "environmentParametersCaptureSourceSHA256": environment.sha256(
                environment_capture_source
            ),
            "probeExecutableSHA256": executable_sha256,
            "probeExecutableContainsNixStorePath": False,
            "freshProcessCount": FRESH_PROCESS_COUNT,
            "lldbLogSHA256ByFreshProcess": lldb_log_sha256,
        },
        "exactCodeGate": {
            "environmentFlagsProducerModuleOffset": 0x1127F8,
            "environmentFlagsProducerByteCount": (
                environment.ENVIRONMENT_FLAGS_PRODUCER_BYTE_COUNT
            ),
            "environmentFlagsProducerSHA256": (
                environment.EXPECTED_ENVIRONMENT_FLAGS_PRODUCER_SHA256
            ),
            "parametersBuilderModuleOffset": 0x120B4C,
            "parametersBuilderByteCount": 0x1334,
            "parametersBuilderSHA256": public.EXPECTED_PARAMETERS_BUILDER_SHA256,
            "parametersCallerModuleOffset": 0x11F1BC,
            "parametersCallerByteCount": 0xD7C,
            "parametersCallerSHA256": public.EXPECTED_PARAMETERS_CALLER_SHA256,
        },
        "parametersLayout": {
            "byteCount": basis.PARAMETERS_BYTE_COUNT,
            "semanticByteCount": len(basis.SEMANTIC_BYTE_OFFSETS),
            "normalizedPaddingRanges": [
                [start, end] for start, end in basis.SEMANTIC_PADDING_RANGES
            ],
        },
        "cases": cases,
        "uniqueNormalizedParameters": unique_parameters,
        "measuredInvariants": {
            "profileCaseCount": len(cases),
            "parametersBuildsPerCase": 1,
            "uniqueNormalizedParametersCount": len(unique_parameters),
            "freshProcessSemanticStabilityEstablished": True,
            "prospectiveFlagsMatchedBitwise": True,
            "capturedParametersUsedForSelection": False,
            "defaultMaterialContextUsed": True,
        },
        "claims": {
            "controlledRegularClearLightDarkParametersTableEstablished": True,
            "environmentFlagsProducerToProfileParametersJoinEstablished": True,
            "liveSwiftUIEnvironmentUpdaterEstablished": False,
            "liveTransitionProgressProductionLawEstablished": False,
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
