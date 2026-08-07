#!/usr/bin/env python3
"""Capture exact Parameters under fixed Material.Context shape ranges."""

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
import capture_designlibrary_material_appearance_parameters_local_macos_26_6_1 as profiles
import capture_designlibrary_parameters_mixer_basis_local_macos_26_6_1 as basis
import capture_designlibrary_public_parameters_local_macos_26_6_1 as public


SCHEMA_VERSION = 1
FRESH_PROCESS_COUNT = 3
EXPECTED_CONTEXT_METADATA_RESULT_SHA256 = (
    "22f720d8e4349245a5986a2dfe3c2803992b87c02d999771ad6191f51a8cbf61"
)
EXPECTED_PROFILE_RESULT_SHA256 = (
    "fd0b181ef72b27a8738c67601b05a1813081cf125f3b82d277829db05567eb3b"
)

PROBE_SOURCE_NAME = (
    "probe_designlibrary_material_context_parameters_local_macos_26_6_1.c"
)
BASE_PUBLIC_PROBE_SOURCE_NAME = public.PROBE_SOURCE_NAME
BRIDGE_SOURCE_NAME = public.BRIDGE_SOURCE_NAME
LLDB_ADAPTER_NAME = (
    "capture_designlibrary_material_context_parameters_local_macos_26_6_1_lldb.py"
)
BASE_LLDB_ADAPTER_NAME = (
    "capture_designlibrary_public_parameters_local_macos_26_6_1_lldb.py"
)
CONTEXT_METADATA_RESULT_NAME = (
    "swiftuicore_material_context_metadata_local_macos_26_6_1_result.json"
)
PROFILE_RESULT_NAME = (
    "designlibrary_material_appearance_parameters_local_macos_26_6_1_result.json"
)
PREREGISTRATION_NAME = (
    "designlibrary_material_context_parameters_local_macos_26_6_1_preregistration.json"
)

Case = Tuple[str, str, str, bool, float, float, str]
CASES: Tuple[Case, ...] = (
    ("regular_light_nil", "regular", "light", False, 0.0, 0.0, "0x0000000000099183"),
    ("regular_light_127", "regular", "light", True, 127.0, 127.0, "0x0000000000099183"),
    (
        "regular_light_127_5",
        "regular",
        "light",
        True,
        127.5,
        127.5,
        "0x0000000000099183",
    ),
    ("regular_light_128", "regular", "light", True, 128.0, 128.0, "0x0000000000099183"),
    ("regular_light_135", "regular", "light", True, 135.0, 135.0, "0x0000000000099183"),
    (
        "regular_light_142_5",
        "regular",
        "light",
        True,
        142.5,
        142.5,
        "0x0000000000099183",
    ),
    ("regular_light_143", "regular", "light", True, 143.0, 143.0, "0x0000000000099183"),
    ("regular_light_347", "regular", "light", True, 347.0, 347.0, "0x0000000000099183"),
    ("regular_light_640", "regular", "light", True, 640.0, 640.0, "0x0000000000099183"),
    (
        "regular_light_1535",
        "regular",
        "light",
        True,
        1535.0,
        1535.0,
        "0x0000000000099183",
    ),
    (
        "regular_light_range_127_143",
        "regular",
        "light",
        True,
        127.0,
        143.0,
        "0x0000000000099183",
    ),
    (
        "regular_light_range_127_640",
        "regular",
        "light",
        True,
        127.0,
        640.0,
        "0x0000000000099183",
    ),
    ("clear_light_127", "clear", "light", True, 127.0, 127.0, "0x0000000000088183"),
    ("clear_light_143", "clear", "light", True, 143.0, 143.0, "0x0000000000088183"),
    ("clear_light_640", "clear", "light", True, 640.0, 640.0, "0x0000000000088183"),
    ("regular_dark_127", "regular", "dark", True, 127.0, 127.0, "0x0000000000099183"),
    ("regular_dark_143", "regular", "dark", True, 143.0, 143.0, "0x0000000000099183"),
    ("regular_dark_640", "regular", "dark", True, 640.0, 640.0, "0x0000000000099183"),
    ("clear_dark_127", "clear", "dark", True, 127.0, 127.0, "0x0000000000088183"),
    ("clear_dark_143", "clear", "dark", True, 143.0, 143.0, "0x0000000000088183"),
    ("clear_dark_640", "clear", "dark", True, 640.0, 640.0, "0x0000000000088183"),
)
EXPECTED_CASE_NAMES = tuple("material_context:" + case[0] for case in CASES)
PROFILE_NAMES = ("regular_light", "regular_dark", "clear_light", "clear_dark")
GEOMETRY_FIELDS = (
    "shadow.amount",
    "shadow.height",
    "blur.radius",
    "refraction.innerHeight",
    "refraction.innerAmount",
    "edgeBleed.amount",
    "edgeBleed.height",
)

CASE_PATTERN = re.compile(
    r"^MATERIAL_CONTEXT_CASE (material_context:\S+) "
    r"flags=(0x[0-9a-f]{16}) present=([01]) "
    r"lower_bits=(0x[0-9a-f]{16}) upper_bits=(0x[0-9a-f]{16})$"
)


class CaptureError(RuntimeError):
    """Raised when the Material.Context Parameters capture differs."""


def load_json(path: Path, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CaptureError(label + " is unreadable") from error
    if not isinstance(value, dict):
        raise CaptureError(label + " is not an object")
    return value


def binary64_bits(value: float) -> str:
    return "0x{0:016x}".format(struct.unpack("<Q", struct.pack("<d", value))[0])


def validate_predecessors(
    metadata_path: Path,
    profile_path: Path,
) -> Mapping[str, bytes]:
    if environment.sha256(metadata_path) != EXPECTED_CONTEXT_METADATA_RESULT_SHA256:
        raise CaptureError("Material.Context metadata result identity differs")
    if environment.sha256(profile_path) != EXPECTED_PROFILE_RESULT_SHA256:
        raise CaptureError("material/appearance profile result identity differs")
    context = load_json(metadata_path, "Material.Context metadata result")
    profile = load_json(profile_path, "material/appearance profile result")
    if (
        context.get("swiftUICoreMaterialContextMetadataAnalysisSchemaVersion") != 1
        or context.get("claims", {}).get("materialContextLayoutEstablished") is not True
        or context.get("claims", {}).get("shapeMetricsLayoutEstablished") is not True
        or profile.get("designLibraryMaterialAppearanceParametersCaptureSchemaVersion")
        != 1
        or profile.get("claims", {}).get(
            "controlledRegularClearLightDarkParametersTableEstablished"
        )
        is not True
    ):
        raise CaptureError("Material.Context predecessor authority differs")
    unique = profile.get("uniqueNormalizedParameters")
    records = profile.get("cases")
    if not isinstance(unique, dict) or not isinstance(records, list):
        raise CaptureError("material/appearance profile table is absent")
    baselines: Dict[str, bytes] = {}
    for record in records:
        if not isinstance(record, dict):
            raise CaptureError("material/appearance profile record differs")
        name = str(record.get("name"))
        digest = str(record.get("normalizedParametersSHA256"))
        value = unique.get(digest)
        if name in PROFILE_NAMES and isinstance(value, dict):
            try:
                baselines[name] = bytes.fromhex(str(value["normalizedHex"]))
            except (KeyError, ValueError) as error:
                raise CaptureError("profile Parameters hex differs") from error
    if set(baselines) != set(PROFILE_NAMES):
        raise CaptureError("material/appearance baseline set differs")
    if any(len(value) != basis.PARAMETERS_BYTE_COUNT for value in baselines.values()):
        raise CaptureError("material/appearance baseline size differs")
    return baselines


def validate_preregistration(path: Path) -> None:
    value = load_json(path, "Material.Context preregistration")
    if (
        value.get("designLibraryMaterialContextParametersPreregistrationSchemaVersion")
        != 1
    ):
        raise CaptureError("Material.Context preregistration schema differs")
    expected = [
        [
            name,
            material,
            appearance,
            present,
            binary64_bits(lower),
            binary64_bits(upper),
            flags,
        ]
        for name, material, appearance, present, lower, upper, flags in CASES
    ]
    if value.get("cases") != expected:
        raise CaptureError("Material.Context preregistered case matrix differs")
    acceptance = value.get("acceptance")
    if not isinstance(acceptance, dict) or acceptance.get("freshProcessCount") != 3:
        raise CaptureError("Material.Context preregistered acceptance differs")
    if any(outcome is not None for outcome in value.get("outcomes", {}).values()):
        raise CaptureError("Material.Context preregistration outcomes are opened")


def parse_extended_runtime(output: str) -> Sequence[Mapping[str, object]]:
    producer_code = None
    records: List[Mapping[str, object]] = []
    for line in output.splitlines():
        producer_match = environment.PRODUCER_PATTERN.fullmatch(line)
        if producer_match is not None:
            if producer_code is not None:
                raise CaptureError("duplicate EnvironmentFlags producer code")
            try:
                producer_code = bytes.fromhex(producer_match.group(1))
            except ValueError as error:
                raise CaptureError(
                    "EnvironmentFlags producer code is invalid"
                ) from error
            continue
        match = CASE_PATTERN.fullmatch(line)
        if match is None:
            continue
        records.append(
            {
                "qualifiedName": match.group(1),
                "flagsBits": match.group(2),
                "dimensionsPresent": match.group(3) == "1",
                "lowerBoundBits": match.group(4),
                "upperBoundBits": match.group(5),
            }
        )
    if (
        producer_code is None
        or len(producer_code) != environment.ENVIRONMENT_FLAGS_PRODUCER_BYTE_COUNT
        or environment.digest_bytes(producer_code)
        != environment.EXPECTED_ENVIRONMENT_FLAGS_PRODUCER_SHA256
    ):
        raise CaptureError("EnvironmentFlags producer identity differs")
    expected = []
    for name, _material, _appearance, present, lower, upper, flags in CASES:
        expected.append(
            {
                "qualifiedName": "material_context:" + name,
                "flagsBits": flags,
                "dimensionsPresent": present,
                "lowerBoundBits": binary64_bits(lower),
                "upperBoundBits": binary64_bits(upper),
            }
        )
    if records != expected:
        raise CaptureError("Material.Context runtime case records differ")
    return records


def scalar_value(payload: bytes, name: str) -> Mapping[str, object]:
    matches = [field for field in basis.SCALAR_FIELDS if field.name == name]
    if len(matches) != 1:
        raise CaptureError("unknown Parameters scalar field " + name)
    field = matches[0]
    value = struct.unpack_from("<" + field.format, payload, field.offset)[0]
    raw = payload[field.offset : field.offset + struct.calcsize(field.format)]
    return {
        "offset": field.offset,
        "storage": "binary32" if field.format == "f" else "binary64",
        "value": value,
        "rawLittleEndianHex": raw.hex(),
    }


def profile_name(material: str, appearance: str) -> str:
    return material + "_" + appearance


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
    public_probe = analysis_directory / BASE_PUBLIC_PROBE_SOURCE_NAME
    bridge_source = analysis_directory / BRIDGE_SOURCE_NAME
    adapter = analysis_directory / LLDB_ADAPTER_NAME
    base_adapter = analysis_directory / BASE_LLDB_ADAPTER_NAME
    basis_source = Path(basis.__file__).resolve()
    public_capture_source = Path(public.__file__).resolve()
    environment_capture_source = Path(environment.__file__).resolve()
    profile_capture_source = Path(profiles.__file__).resolve()
    context_metadata = analysis_directory / CONTEXT_METADATA_RESULT_NAME
    profile_result = analysis_directory / PROFILE_RESULT_NAME
    preregistration = analysis_directory / PREREGISTRATION_NAME
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
        profile_capture_source,
        context_metadata,
        profile_result,
        preregistration,
    )
    if any(not path.is_file() for path in required):
        raise CaptureError("Material.Context source set is incomplete")
    if any("/nix/store" in str(path) for path in required):
        raise CaptureError("capture source path contains a Nix store path")
    baselines = validate_predecessors(context_metadata, profile_result)
    validate_preregistration(preregistration)

    traces = []
    runtimes = []
    extensions = []
    lldb_log_sha256 = []
    with tempfile.TemporaryDirectory(prefix="lg-material-context-") as temporary:
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
        raise CaptureError("Material.Context Parameters vary across fresh processes")
    if any(runtime != runtimes[0] for runtime in runtimes[1:]):
        raise CaptureError("Material.Context runtime records vary")
    if any(extension != extensions[0] for extension in extensions[1:]):
        raise CaptureError("Material.Context input records vary")

    unique_parameters: Dict[str, Mapping[str, object]] = {}
    cases: List[Mapping[str, object]] = []
    for index, (specification, payload) in enumerate(zip(CASES, normalized_by_run[0])):
        name, material, appearance, present, lower, upper, flags = specification
        baseline_name = profile_name(material, appearance)
        baseline = baselines[baseline_name]
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
        fields = {field: scalar_value(payload, field) for field in GEOMETRY_FIELDS}
        cases.append(
            {
                "index": index,
                "name": name,
                "qualifiedName": "material_context:" + name,
                "material": material,
                "appearance": appearance,
                "producedFlagsBits": flags,
                "shapeDimensions": {
                    "present": present,
                    "lowerBound": lower,
                    "lowerBoundBits": binary64_bits(lower),
                    "upperBound": upper,
                    "upperBoundBits": binary64_bits(upper),
                },
                "baselineProfile": baseline_name,
                "normalizedParametersSHA256": digest,
                "changedSemanticByteOffsetsFromBaseline": changed_offsets,
                "changedFieldsFromBaseline": environment.semantic_changes(
                    baseline, payload
                ),
                "geometryScalarFields": fields,
                "rawParametersSHA256ByFreshProcess": [
                    environment.digest_bytes(raw_by_run[run_index][index])
                    for run_index in range(FRESH_PROCESS_COUNT)
                ],
            }
        )
    if normalized_by_run[0][0] != baselines["regular_light"]:
        raise CaptureError("nil-context regular/light baseline did not reproduce")

    result = {
        "designLibraryMaterialContextParametersCaptureSchemaVersion": SCHEMA_VERSION,
        "classification": (
            "prospectively fixed direct Material.Context shapeDimensions storage "
            "interventions followed by Apple's exact EnvironmentFlags, provider, "
            "and ResolvedRecipe.Parameters path; calibration matrix, no live context "
            "producer, GUI, render, image, crop, pixel, or Nix store path"
        ),
        "host": {
            "system": platform.system(),
            "machine": platform.machine(),
            "macOSProductVersion": product_version,
            "macOSBuildVersion": build_version,
            "hardwareModel": hardware_model,
        },
        "predecessors": {
            "materialContextMetadata": {
                "path": "Analysis/" + context_metadata.name,
                "sha256": environment.sha256(context_metadata),
            },
            "materialAppearanceParameters": {
                "path": "Analysis/" + profile_result.name,
                "sha256": environment.sha256(profile_result),
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
            "profileParametersCaptureSourceSHA256": environment.sha256(
                profile_capture_source
            ),
            "probeExecutableSHA256": executable_sha256,
            "probeExecutableContainsNixStorePath": False,
            "freshProcessCount": FRESH_PROCESS_COUNT,
            "lldbLogSHA256ByFreshProcess": lldb_log_sha256,
        },
        "materialContextLayout": {
            "byteCount": 73,
            "stride": 80,
            "shapeDimensionsLowerBoundOffset": 24,
            "shapeDimensionsUpperBoundOffset": 32,
            "shapeDimensionsOptionalTagOffset": 40,
            "nilOptionalTag": 1,
            "presentOptionalTag": 0,
        },
        "cases": cases,
        "uniqueNormalizedParameters": unique_parameters,
        "measuredInvariants": {
            "caseCount": len(cases),
            "parametersBuildsPerCase": 1,
            "uniqueNormalizedParametersCount": len(unique_parameters),
            "freshProcessSemanticStabilityEstablished": True,
            "nilContextBaselineReproducedBitwise": True,
            "capturedParametersUsedForSelection": False,
        },
        "claims": {
            "controlledMaterialContextShapeDimensionParametersTableEstablished": True,
            "generalContextToParametersValueLawEstablished": False,
            "liveContextValueProductionEstablished": False,
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
