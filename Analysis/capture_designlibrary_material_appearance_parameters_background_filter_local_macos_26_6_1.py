#!/usr/bin/env python3
"""Join four exact material profiles to Apple's filter and margin provider."""

from __future__ import annotations

import argparse
import json
import struct
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple

import capture_designlibrary_environment_parameters_background_filter_local_macos_26_6_1 as join


SCHEMA_VERSION = 1
EXPECTED_PROFILE_PARAMETERS_RESULT_SHA256 = (
    "fd0b181ef72b27a8738c67601b05a1813081cf125f3b82d277829db05567eb3b"
)
EXPECTED_ENVIRONMENT_PROBE_SOURCE_SHA256 = (
    "9536abaf99ae6d78663981c90afcd80aab5654fde12366c996039dd71b01f52c"
)

PROFILE_PARAMETERS_RESULT_NAME = (
    "designlibrary_material_appearance_parameters_local_macos_26_6_1_result.json"
)
PROBE_SOURCE_NAME = join.PROBE_SOURCE_NAME

# Predicted before this direct native join from the frozen Parameters blobs,
# constructor byte-copy proof, exact flags, and authenticated provider replay.
EXPECTED_CASES = (
    (
        "regular_light",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "regular_dark",
        "5f5d46ac6cf8abf6a67f721a58a7664e51ad039dc9c463beb2d824e695c69ac9",
        "3433333333332340",
    ),
    (
        "clear_light",
        "663fc54ebeb85cdfc3b1c6eafcc76b0f4b3e4021ed648fd36d4faaa490242857",
        "0000000000000000",
    ),
    (
        "clear_dark",
        "663fc54ebeb85cdfc3b1c6eafcc76b0f4b3e4021ed648fd36d4faaa490242857",
        "0000000000000000",
    ),
)


class CaptureError(join.CaptureError):
    """Raised when the exact profile-to-filter join differs."""


def load_inputs(path: Path) -> Tuple[List[str], List[str], List[str]]:
    if join.base.sha256(path) != EXPECTED_PROFILE_PARAMETERS_RESULT_SHA256:
        raise CaptureError("material/appearance Parameters result differs")
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CaptureError(
            "material/appearance Parameters result is unreadable"
        ) from error
    if (
        result.get("designLibraryMaterialAppearanceParametersCaptureSchemaVersion") != 1
        or result.get("claims", {}).get(
            "controlledRegularClearLightDarkParametersTableEstablished"
        )
        is not True
        or result.get("parametersLayout", {}).get("byteCount")
        != join.base.PARAMETERS_BYTE_COUNT
    ):
        raise CaptureError("material/appearance Parameters authority differs")
    cases = result.get("cases")
    unique = result.get("uniqueNormalizedParameters")
    if not isinstance(cases, list) or not isinstance(unique, dict):
        raise CaptureError("material/appearance Parameters table is absent")
    if [str(case.get("name")) for case in cases] != [
        expected[0] for expected in EXPECTED_CASES
    ]:
        raise CaptureError("material/appearance case order differs")

    payloads = []
    parameter_digests = []
    flags_bits = []
    for case in cases:
        digest = str(case.get("normalizedParametersSHA256"))
        record = unique.get(digest)
        if not isinstance(record, dict):
            raise CaptureError("material/appearance Parameters blob is absent")
        try:
            parameters = bytes.fromhex(str(record.get("normalizedHex", "")))
            flags = int(str(case.get("producedFlagsBits")), 16)
            flags_raw = flags.to_bytes(8, "little")
        except (ValueError, OverflowError) as error:
            raise CaptureError("material/appearance input is invalid") from error
        if (
            len(parameters) != join.base.PARAMETERS_BYTE_COUNT
            or join.base.digest_bytes(parameters) != digest
        ):
            raise CaptureError("material/appearance Parameters identity differs")
        payloads.append(flags_raw.hex() + ":" + parameters.hex())
        parameter_digests.append(digest)
        flags_bits.append("0x{0:016x}".format(flags))
    return payloads, parameter_digests, flags_bits


def invoke_probe(
    executable: Path,
    payloads: Sequence[str],
    flags_bits: Sequence[str],
) -> Mapping[str, object]:
    original_expected_cases = join.EXPECTED_CASES
    try:
        join.EXPECTED_CASES = EXPECTED_CASES
        return join.invoke_probe(executable, payloads, flags_bits)
    finally:
        join.EXPECTED_CASES = original_expected_cases


def capture(output_path: Path) -> Mapping[str, object]:
    host = join.base.require_host()
    analysis_directory = Path(__file__).resolve().parent
    capture_source = Path(__file__).resolve()
    probe_source = analysis_directory / PROBE_SOURCE_NAME
    base_probe_source = analysis_directory / join.base.PROBE_SOURCE_NAME
    bridge_source = analysis_directory / join.base.BRIDGE_SOURCE_NAME
    parameters_result = analysis_directory / PROFILE_PARAMETERS_RESULT_NAME
    dependencies = (
        capture_source,
        probe_source,
        base_probe_source,
        bridge_source,
        parameters_result,
        Path(join.__file__).resolve(),
    )
    for source in dependencies:
        if not source.is_file():
            raise CaptureError("required source or predecessor is absent")
        if "/nix/store" in str(source):
            raise CaptureError("source path contains a Nix store path")
    if join.base.sha256(probe_source) != EXPECTED_ENVIRONMENT_PROBE_SOURCE_SHA256:
        raise CaptureError("generic Environment filter probe differs")
    if join.base.sha256(base_probe_source) != join.EXPECTED_BASE_PROBE_SOURCE_SHA256:
        raise CaptureError("included base probe source differs")
    payloads, parameter_digests, flags_bits = load_inputs(parameters_result)

    runs = []
    with tempfile.TemporaryDirectory(prefix="lg-profile-filter-") as temporary:
        temporary_directory = Path(temporary)
        executable = temporary_directory / "probe"
        join.base.run_command(
            (
                str(join.base.XCRUN),
                "clang",
                "-std=c2x",
                "-arch",
                "arm64",
                "-O2",
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
        )
        executable_raw = executable.read_bytes()
        if b"/nix/store" in executable_raw:
            raise CaptureError("native probe embeds a Nix store path")
        executable_sha256 = join.base.digest_bytes(executable_raw)
        for _ in range(join.base.FRESH_PROCESS_COUNT):
            runs.append(invoke_probe(executable, payloads, flags_bits))

    canonical_records = runs[0]["records"]
    if any(run["code"] != runs[0]["code"] for run in runs[1:]):
        raise CaptureError("exact-code identity varies across fresh processes")
    if any(run["records"] != canonical_records for run in runs[1:]):
        raise CaptureError("profile filter results vary across fresh processes")

    unique_objects: Dict[str, Mapping[str, object]] = {}
    cases = []
    for index, (record, parameters_digest) in enumerate(
        zip(canonical_records, parameter_digests)
    ):
        object_digest = str(record["backgroundFilterSHA256"])
        if object_digest not in unique_objects:
            unique_objects[object_digest] = {
                "hex": record["backgroundFilterHex"],
                "caseNames": [],
            }
        unique_objects[object_digest]["caseNames"].append(record["name"])
        margin_raw = bytes.fromhex(str(record["marginRawLittleEndianHex"]))
        cases.append(
            {
                "index": index,
                "name": record["name"],
                "normalizedParametersSHA256": parameters_digest,
                "producedFlagsBits": record["producedFlagsBits"],
                "producedFlagsRawLittleEndianHex": record[
                    "producedFlagsRawLittleEndianHex"
                ],
                "backgroundFilterSHA256": object_digest,
                "marginRawLittleEndianHex": margin_raw.hex(),
                "margin": struct.unpack("<d", margin_raw)[0],
            }
        )

    result = {
        "designLibraryMaterialAppearanceParametersBackgroundFilterCaptureSchemaVersion": (
            SCHEMA_VERSION
        ),
        "classification": (
            "prospectively predicted direct invocation of Apple's exact "
            "BackgroundFilter constructor and sdfBackdropMargin getter over "
            "the regular/clear by light/dark Parameters table with each real "
            "flags word; no live SwiftUI updater, GUI, render, image, crop, "
            "pixel, or Nix store path"
        ),
        "host": host,
        "framework": {
            "path": str(join.base.DESIGNLIBRARY),
            "uuid": join.base.EXPECTED_DESIGNLIBRARY_UUID,
        },
        "predecessor": {
            "path": "Analysis/" + parameters_result.name,
            "sha256": join.base.sha256(parameters_result),
            "caseCount": len(payloads),
            "parametersByteCount": join.base.PARAMETERS_BYTE_COUNT,
        },
        "tool": {
            "python": sys.version.split()[0],
            "clang": join.base.run_command(
                (str(join.base.XCRUN), "clang", "--version")
            ).splitlines()[0],
            "captureSource": "Analysis/" + capture_source.name,
            "captureSourceSHA256": join.base.sha256(capture_source),
            "probeSource": "Analysis/" + probe_source.name,
            "probeSourceSHA256": join.base.sha256(probe_source),
            "includedBaseProbeSource": "Analysis/" + base_probe_source.name,
            "includedBaseProbeSourceSHA256": join.base.sha256(base_probe_source),
            "assemblyBridge": "Analysis/" + bridge_source.name,
            "assemblyBridgeSHA256": join.base.sha256(bridge_source),
            "genericJoinSourceSHA256": join.base.sha256(Path(join.__file__).resolve()),
            "probeExecutableSHA256": executable_sha256,
            "probeExecutableContainsNixStorePath": False,
            "freshProcessCount": join.base.FRESH_PROCESS_COUNT,
        },
        "exactCodeGate": {
            "constructorModuleOffset": 0xBAD00,
            "constructorByteCount": join.base.CONSTRUCTOR_CODE_BYTE_COUNT,
            "constructorSHA256": join.base.EXPECTED_CONSTRUCTOR_CODE_SHA256,
            "providerModuleOffset": 0xB70B4,
            "providerByteCount": join.base.PROVIDER_CODE_BYTE_COUNT,
            "providerSHA256": join.base.EXPECTED_PROVIDER_CODE_SHA256,
            "codeAuthenticatedBeforeInputsWritten": True,
        },
        "predictionBasis": {
            "constructorCopyLawUsed": True,
            "exactEnvironmentFlagsUsed": True,
            "authenticatedProviderInstructionReplayUsed": True,
            "expectedObjectAndMarginIdentitiesFixedBeforeNativeJoin": True,
        },
        "cases": cases,
        "uniqueBackgroundFilters": unique_objects,
        "measuredInvariants": {
            "profileCaseCount": len(cases),
            "parametersByteCount": join.base.PARAMETERS_BYTE_COUNT,
            "backgroundFilterByteCount": join.base.BACKGROUND_FILTER_BYTE_COUNT,
            "uniqueBackgroundFilterCount": len(unique_objects),
            "regularAppearanceObjectsDistinct": (
                cases[0]["backgroundFilterSHA256"] != cases[1]["backgroundFilterSHA256"]
            ),
            "clearAppearanceObjectsBitwiseEqual": (
                cases[2]["backgroundFilterSHA256"] == cases[3]["backgroundFilterSHA256"]
            ),
            "regularMarginRawWord": cases[0]["marginRawLittleEndianHex"],
            "clearMarginRawWord": cases[2]["marginRawLittleEndianHex"],
            "environmentFlagsEmbeddedBitwiseAtObjectOffset496": True,
            "freshProcessBitwiseStabilityEstablished": True,
            "constructorAndProviderCodeAuthenticatedBeforeInput": True,
            "capturedObjectOrMarginUsedForSelection": False,
        },
        "claims": {
            "controlledRegularClearLightDarkBackgroundFilterTableEstablished": True,
            "controlledMaterialSpecificMarginBoundaryEstablished": True,
            "liveSwiftUIEnvironmentUpdaterEstablished": False,
            "liveTransitionProgressProductionLawEstablished": False,
            "liveTransitionMarginMaximumPolicyEstablished": False,
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
