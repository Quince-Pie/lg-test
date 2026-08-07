#!/usr/bin/env python3
"""Capture exact Parameters for frozen internal Environment mutations."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import struct
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

import capture_designlibrary_parameters_mixer_basis_local_macos_26_6_1 as basis
import capture_designlibrary_public_parameters_local_macos_26_6_1 as public


SCHEMA_VERSION = 1
EXPECTED_ENVIRONMENT_FLAGS_RESULT_SHA256 = (
    "3b65ba5764c786a7f82eb3f92084653e0a9f9e85267d70eca7108243dfc8d597"
)
EXPECTED_ENVIRONMENT_FLAGS_PRODUCER_SHA256 = (
    "69bd75dcc4daad7956b6b41560fc39a1ec5bd4187712c945788477ec6dd97090"
)
ENVIRONMENT_FLAGS_PRODUCER_BYTE_COUNT = 1252
FRESH_PROCESS_COUNT = 3

PROBE_SOURCE_NAME = "probe_designlibrary_environment_parameters_local_macos_26_6_1.c"
BASE_PROBE_SOURCE_NAME = public.PROBE_SOURCE_NAME
BRIDGE_SOURCE_NAME = public.BRIDGE_SOURCE_NAME
LLDB_ADAPTER_NAME = (
    "capture_designlibrary_environment_parameters_local_macos_26_6_1_lldb.py"
)
BASE_LLDB_ADAPTER_NAME = (
    "capture_designlibrary_public_parameters_local_macos_26_6_1_lldb.py"
)
ENVIRONMENT_FLAGS_RESULT_NAME = (
    "designlibrary_environment_flags_resolution_local_macos_26_6_1_result.json"
)

ENVIRONMENT_NAMES = (
    "baseline",
    "pixel_length_half",
    "pixel_length_two",
    "color_scheme_light",
    "color_scheme_dark",
    "contrast_standard",
    "contrast_increased",
    "appears_active_false",
    "appears_active_true",
    "window_active_false",
    "window_active_true",
    "window_opaque_false",
    "window_opaque_true",
    "glass_foreground_false",
    "glass_foreground_true",
    "has_tinted_elements_false",
    "has_tinted_elements_true",
    "reduce_transparency_false",
    "reduce_transparency_true",
    "reduce_motion_false",
    "reduce_motion_true",
    "show_button_shapes_false",
    "show_button_shapes_true",
    "low_power_false",
    "low_power_true",
    "idiom_universal",
    "idiom_mac",
    "idiom_phone",
    "idiom_pad",
    "idiom_tv",
    "idiom_watch",
    "idiom_spatial",
    "idiom_car_play",
    "idiom_touch_bar",
    "diffusion_automatic",
    "diffusion_increased",
)
EXPECTED_CASE_NAMES = tuple("environment:" + name for name in ENVIRONMENT_NAMES)

PRODUCER_PATTERN = re.compile(r"^ENVIRONMENT_FLAGS_PRODUCER_CODE=([0-9a-f]+)$")
FLAGS_PATTERN = re.compile(
    r"^ENVIRONMENT_FLAGS (environment:\S+) bits=(0x[0-9a-f]{16})$"
)


class CaptureError(RuntimeError):
    """Raised when Environment-to-Parameters evidence differs."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def digest_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_environment_predecessor(path: Path) -> List[Mapping[str, object]]:
    if sha256(path) != EXPECTED_ENVIRONMENT_FLAGS_RESULT_SHA256:
        raise CaptureError("EnvironmentFlags predecessor differs")
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CaptureError("EnvironmentFlags predecessor is unreadable") from error
    if (
        result.get("designLibraryEnvironmentFlagsResolutionCaptureSchemaVersion") != 1
        or result.get("claims", {}).get(
            "publicEnvironmentFlagsProducerBoundaryEstablished"
        )
        is not True
    ):
        raise CaptureError("EnvironmentFlags predecessor authority differs")
    cases = result.get("environmentCases")
    if not isinstance(cases, list):
        raise CaptureError("EnvironmentFlags predecessor cases are absent")
    if [case.get("name") for case in cases] != list(ENVIRONMENT_NAMES):
        raise CaptureError("EnvironmentFlags predecessor case order differs")
    return cases


def parse_extended_runtime(
    output: str,
    predecessor_cases: Sequence[Mapping[str, object]],
) -> Mapping[str, object]:
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
                raise CaptureError(
                    "EnvironmentFlags producer code is invalid"
                ) from error
            continue
        match = FLAGS_PATTERN.fullmatch(line)
        if match is not None:
            flags.append((match.group(1), match.group(2)))
    if (
        producer_code is None
        or len(producer_code) != ENVIRONMENT_FLAGS_PRODUCER_BYTE_COUNT
        or digest_bytes(producer_code) != EXPECTED_ENVIRONMENT_FLAGS_PRODUCER_SHA256
    ):
        raise CaptureError("EnvironmentFlags producer exact-code identity differs")
    expected_flags = [
        (
            "environment:" + str(case["name"]),
            str(case["producedFlagsBits"]),
        )
        for case in predecessor_cases
    ]
    if flags != expected_flags:
        raise CaptureError("EnvironmentFlags runtime records differ")
    return {
        "producerCodeSHA256": digest_bytes(producer_code),
        "flags": flags,
    }


def scalar_change(
    field,
    baseline: bytes,
    payload: bytes,
) -> Mapping[str, object]:
    byte_count = struct.calcsize("<" + field.format)
    baseline_raw = baseline[field.offset : field.offset + byte_count]
    payload_raw = payload[field.offset : field.offset + byte_count]
    return {
        "name": field.name,
        "kind": "scalar",
        "offset": field.offset,
        "format": field.format,
        "baselineRawLittleEndianHex": baseline_raw.hex(),
        "rawLittleEndianHex": payload_raw.hex(),
        "baselineValue": struct.unpack("<" + field.format, baseline_raw)[0],
        "value": struct.unpack("<" + field.format, payload_raw)[0],
    }


def semantic_changes(baseline: bytes, payload: bytes) -> List[Mapping[str, object]]:
    changes = []
    for field in basis.SCALAR_FIELDS:
        byte_count = struct.calcsize("<" + field.format)
        if (
            baseline[field.offset : field.offset + byte_count]
            != payload[field.offset : field.offset + byte_count]
        ):
            changes.append(scalar_change(field, baseline, payload))
    for field in basis.COLOR_FIELDS:
        baseline_raw = baseline[field.offset : field.offset + 17]
        payload_raw = payload[field.offset : field.offset + 17]
        if baseline_raw != payload_raw:
            changes.append(
                {
                    "name": field.name,
                    "kind": "color",
                    "offset": field.offset,
                    "baselineHex": baseline_raw.hex(),
                    "hex": payload_raw.hex(),
                }
            )
    for name, (offset, _present, _absent) in basis.CONTAINER_PRESENCE.items():
        if baseline[offset] != payload[offset]:
            changes.append(
                {
                    "name": name + ".presence",
                    "kind": "presence",
                    "offset": offset,
                    "baselineStorage": baseline[offset],
                    "storage": payload[offset],
                }
            )
    changes.sort(key=lambda record: (int(record["offset"]), str(record["name"])))
    return changes


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
    base_probe_source = analysis_directory / BASE_PROBE_SOURCE_NAME
    bridge_source = analysis_directory / BRIDGE_SOURCE_NAME
    adapter = analysis_directory / LLDB_ADAPTER_NAME
    base_adapter = analysis_directory / BASE_LLDB_ADAPTER_NAME
    basis_source = Path(basis.__file__).resolve()
    public_capture_source = Path(public.__file__).resolve()
    predecessor_path = analysis_directory / ENVIRONMENT_FLAGS_RESULT_NAME
    required = (
        capture_source,
        probe_source,
        base_probe_source,
        bridge_source,
        adapter,
        base_adapter,
        basis_source,
        public_capture_source,
        predecessor_path,
    )
    if any(not path.is_file() for path in required):
        raise CaptureError("Environment Parameters source set is incomplete")
    if any("/nix/store" in str(path) for path in required):
        raise CaptureError("capture source path contains a Nix store path")
    predecessor_cases = load_environment_predecessor(predecessor_path)

    traces = []
    runtimes = []
    extensions = []
    lldb_log_sha256 = []
    with tempfile.TemporaryDirectory(prefix="lg-environment-parameters-") as temporary:
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
        executable_sha256 = digest_bytes(executable_raw)
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
            extensions.append(parse_extended_runtime(runtime_output, predecessor_cases))
            traces.append(trace)
            runtimes.append(runtime)
            lldb_log_sha256.append(log_digest)

    raw_by_run = [public.validate_trace(trace) for trace in traces]
    normalized_by_run = [
        [basis.normalize_parameters(payload) for payload in payloads]
        for payloads in raw_by_run
    ]
    if any(run != normalized_by_run[0] for run in normalized_by_run[1:]):
        raise CaptureError("Environment Parameters vary across fresh processes")
    if any(runtime != runtimes[0] for runtime in runtimes[1:]):
        raise CaptureError("Environment runtime records vary across fresh processes")
    if any(extension != extensions[0] for extension in extensions[1:]):
        raise CaptureError("Environment exact-code or flags records vary")

    unique_parameters: Dict[str, Mapping[str, object]] = {}
    baseline = normalized_by_run[0][0]
    cases = []
    for index, (name, payload, predecessor) in enumerate(
        zip(ENVIRONMENT_NAMES, normalized_by_run[0], predecessor_cases)
    ):
        digest = digest_bytes(payload)
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
                "qualifiedName": "environment:" + name,
                "mutationOffset": predecessor["mutationOffset"],
                "mutationStorageHex": predecessor["mutationStorageHex"],
                "producedFlagsBits": predecessor["producedFlagsBits"],
                "normalizedParametersSHA256": digest,
                "changedSemanticByteOffsetsFromBaseline": changed_offsets,
                "changedFieldsFromBaseline": semantic_changes(baseline, payload),
                "rawParametersSHA256ByFreshProcess": [
                    digest_bytes(raw_by_run[run_index][index])
                    for run_index in range(FRESH_PROCESS_COUNT)
                ],
            }
        )

    result = {
        "designLibraryEnvironmentParametersCaptureSchemaVersion": SCHEMA_VERSION,
        "classification": (
            "direct exact-code EnvironmentFlags production followed by Apple "
            "provider resolution and ResolvedRecipe.Parameters construction for "
            "36 frozen internal Environment mutations under a default "
            "Material.Context; no live SwiftUI updater, GUI, render, image, crop, "
            "pixel, or Nix store path"
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
        "predecessor": {
            "path": "Analysis/" + predecessor_path.name,
            "sha256": sha256(predecessor_path),
            "caseCount": len(predecessor_cases),
        },
        "tool": {
            "python": sys.version.split()[0],
            "clang": public.command_output(
                (str(public.XCRUN), "clang", "--version")
            ).splitlines()[0],
            "captureSource": "Analysis/" + capture_source.name,
            "captureSourceSHA256": sha256(capture_source),
            "probeSource": "Analysis/" + probe_source.name,
            "probeSourceSHA256": sha256(probe_source),
            "baseProbeSource": "Analysis/" + base_probe_source.name,
            "baseProbeSourceSHA256": sha256(base_probe_source),
            "assemblyBridge": "Analysis/" + bridge_source.name,
            "assemblyBridgeSHA256": sha256(bridge_source),
            "lldbAdapter": "Analysis/" + adapter.name,
            "lldbAdapterSHA256": sha256(adapter),
            "baseLldbAdapter": "Analysis/" + base_adapter.name,
            "baseLldbAdapterSHA256": sha256(base_adapter),
            "parametersBasisSourceSHA256": sha256(basis_source),
            "publicParametersCaptureSourceSHA256": sha256(public_capture_source),
            "probeExecutableSHA256": executable_sha256,
            "probeExecutableContainsNixStorePath": False,
            "freshProcessCount": FRESH_PROCESS_COUNT,
            "lldbLogSHA256ByFreshProcess": lldb_log_sha256,
        },
        "exactCodeGate": {
            "environmentFlagsProducerModuleOffset": 0x1127F8,
            "environmentFlagsProducerByteCount": (
                ENVIRONMENT_FLAGS_PRODUCER_BYTE_COUNT
            ),
            "environmentFlagsProducerSHA256": (
                EXPECTED_ENVIRONMENT_FLAGS_PRODUCER_SHA256
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
            "environmentCaseCount": len(cases),
            "parametersBuildsPerCase": 1,
            "uniqueNormalizedParametersCount": len(unique_parameters),
            "freshProcessSemanticStabilityEstablished": True,
            "environmentFlagsMatchedPredecessorBitwise": True,
            "capturedParametersUsedForSelection": False,
            "defaultMaterialContextUsed": True,
        },
        "claims": {
            "controlledInternalEnvironmentToParametersTableEstablished": True,
            "environmentFlagsProducerToParametersJoinEstablished": True,
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
