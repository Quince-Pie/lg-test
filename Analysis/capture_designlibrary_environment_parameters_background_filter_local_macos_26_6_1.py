#!/usr/bin/env python3
"""Join exact flags-produced Environment Parameters to Apple's filter object."""

from __future__ import annotations

import argparse
import json
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple

import capture_designlibrary_public_parameters_background_filter_local_macos_26_6_1 as base


SCHEMA_VERSION = 1
EXPECTED_ENVIRONMENT_PARAMETERS_RESULT_SHA256 = (
    "8a2048183aae7ebca49b8385891408e0fccbf75bc25e71d1e7b3b13be9d3d595"
)
EXPECTED_BASE_PROBE_SOURCE_SHA256 = (
    "674bec9de543da7827e283ef493ec5f10bd82458b1afec6bc3c65d09e403ef06"
)

PROBE_SOURCE_NAME = (
    "probe_designlibrary_environment_parameters_background_filter_local_macos_26_6_1.c"
)
ENVIRONMENT_PARAMETERS_RESULT_NAME = (
    "designlibrary_environment_parameters_local_macos_26_6_1_result.json"
)
RESULT_PATTERN = base.RESULT_PATTERN

# These object and margin identities were predicted from the frozen Parameters
# blobs, exact constructor copy law, and real flags before the canonical run.
EXPECTED_CASES = (
    (
        "baseline",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "pixel_length_half",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "pixel_length_two",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "color_scheme_light",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "color_scheme_dark",
        "5f5d46ac6cf8abf6a67f721a58a7664e51ad039dc9c463beb2d824e695c69ac9",
        "3433333333332340",
    ),
    (
        "contrast_standard",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "contrast_increased",
        "7b88ad22566b1a944da9d7942bc0b5b396b7241418f6055d7f034ad062d0e552",
        "3433333333332340",
    ),
    (
        "appears_active_false",
        "cc61ebdebb0dd701e2fd1bcbf5c246d642af63d940d8847450e0cfd9eaa85481",
        "3433333333332340",
    ),
    (
        "appears_active_true",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "window_active_false",
        "4cfa13139ce4e4586413c2b3f7fb38930f3f5f73067fb89bf0e2b38b9e0ccca7",
        "0000000000000000",
    ),
    (
        "window_active_true",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "window_opaque_false",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "window_opaque_true",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "glass_foreground_false",
        "e501c79e4fda378cfc936a1abf0ada28421ca0d3d7db39c378bf8e169050c24f",
        "0000000000000000",
    ),
    (
        "glass_foreground_true",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "has_tinted_elements_false",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "has_tinted_elements_true",
        "93a467234ba44d428843c30924827ea0b9c7d4c9cce5e7e4ef1773bacce3688d",
        "3433333333332340",
    ),
    (
        "reduce_transparency_false",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "reduce_transparency_true",
        "8c9cc6b2a65bc09d405bf473d487fdc99fdf486428f60855fae6336d6dc7c99f",
        "0000000000000000",
    ),
    (
        "reduce_motion_false",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "reduce_motion_true",
        "9cbaa377d7702409350f35ab0eda45c5ee1f9a7861036ca1c0a94f055ad70730",
        "3433333333332340",
    ),
    (
        "show_button_shapes_false",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "show_button_shapes_true",
        "4cd63e7ed6cb934088bcf4a26d527d63b83cdd824319509a03e65cc0037015ca",
        "3433333333332340",
    ),
    (
        "low_power_false",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "low_power_true",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "idiom_universal",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "idiom_mac",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "idiom_phone",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "idiom_pad",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "idiom_tv",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "idiom_watch",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "idiom_spatial",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "idiom_car_play",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "idiom_touch_bar",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "diffusion_automatic",
        "824af01d066a23b7f8a8bcc24583c198b6c136508bdc89d266ec1048a014cc91",
        "3433333333332340",
    ),
    (
        "diffusion_increased",
        "e48ad44dbd813a10187a9e1bd1292b05553e36fd7c595ddd773a7c515c7d7691",
        "3433333333332340",
    ),
)


class CaptureError(base.CaptureError):
    """Raised when the exact Environment-to-filter join differs."""


def load_inputs(path: Path) -> Tuple[List[str], List[str], List[str]]:
    if base.sha256(path) != EXPECTED_ENVIRONMENT_PARAMETERS_RESULT_SHA256:
        raise CaptureError("Environment Parameters canonical result differs")
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CaptureError("Environment Parameters result is unreadable") from error
    if (
        result.get("designLibraryEnvironmentParametersCaptureSchemaVersion") != 1
        or result.get("claims", {}).get(
            "environmentFlagsProducerToParametersJoinEstablished"
        )
        is not True
        or result.get("parametersLayout", {}).get("byteCount")
        != base.PARAMETERS_BYTE_COUNT
    ):
        raise CaptureError("Environment Parameters result authority differs")
    cases = result.get("cases")
    unique = result.get("uniqueNormalizedParameters")
    if not isinstance(cases, list) or not isinstance(unique, dict):
        raise CaptureError("Environment Parameters table is absent")
    if [str(case.get("name")) for case in cases] != [
        expected[0] for expected in EXPECTED_CASES
    ]:
        raise CaptureError("Environment Parameters case order differs")

    payloads = []
    parameter_digests = []
    flags_bits = []
    for case in cases:
        digest = str(case.get("normalizedParametersSHA256"))
        record = unique.get(digest)
        if not isinstance(record, dict):
            raise CaptureError("Environment Parameters blob is absent")
        try:
            parameters = bytes.fromhex(str(record.get("normalizedHex", "")))
            flags = int(str(case.get("producedFlagsBits")), 16)
            flags_raw = flags.to_bytes(8, "little")
        except (ValueError, OverflowError) as error:
            raise CaptureError("Environment Parameters input is invalid") from error
        if (
            len(parameters) != base.PARAMETERS_BYTE_COUNT
            or base.digest_bytes(parameters) != digest
        ):
            raise CaptureError("Environment Parameters blob identity differs")
        payloads.append(flags_raw.hex() + ":" + parameters.hex())
        parameter_digests.append(digest)
        flags_bits.append("0x{0:016x}".format(flags))
    return payloads, parameter_digests, flags_bits


def invoke_probe(
    executable: Path,
    payloads: Sequence[str],
    flags_bits: Sequence[str],
) -> Mapping[str, object]:
    try:
        process = subprocess.Popen(
            [str(executable)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=base.native_environment(),
        )
    except OSError as error:
        raise CaptureError("native probe launch failed") from error
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    try:
        code = base.read_code_header(process)
        for payload in payloads:
            process.stdin.write(payload + "\n")
        process.stdin.close()
        records = []
        for ordinal, (expected, flags_text) in enumerate(
            zip(EXPECTED_CASES, flags_bits)
        ):
            line = process.stdout.readline().rstrip("\n")
            match = RESULT_PATTERN.fullmatch(line)
            if match is None or int(match.group(1)) != ordinal:
                raise CaptureError("native result is absent or reordered")
            try:
                object_raw = bytes.fromhex(match.group(2))
                margin_raw = bytes.fromhex(match.group(3))
                flags_raw = int(flags_text, 16).to_bytes(8, "little")
            except (ValueError, OverflowError) as error:
                raise CaptureError("native result payload is invalid") from error
            object_digest = base.digest_bytes(object_raw)
            if (
                len(object_raw) != base.BACKGROUND_FILTER_BYTE_COUNT
                or object_digest != expected[1]
                or object_raw[496:504] != flags_raw
                or len(margin_raw) != 8
                or margin_raw.hex() != expected[2]
            ):
                raise CaptureError("native constructor or margin result differs")
            records.append(
                {
                    "ordinal": ordinal,
                    "name": expected[0],
                    "producedFlagsBits": flags_text,
                    "producedFlagsRawLittleEndianHex": flags_raw.hex(),
                    "backgroundFilterHex": object_raw.hex(),
                    "backgroundFilterSHA256": object_digest,
                    "marginRawLittleEndianHex": margin_raw.hex(),
                }
            )
        completion = process.stdout.readline().rstrip("\n")
        if completion != "COMPLETE cases={0}".format(len(EXPECTED_CASES)):
            raise CaptureError("native completion record differs")
        remaining_stdout = process.stdout.read()
        stderr = process.stderr.read()
        returncode = process.wait()
        if returncode != 0 or remaining_stdout or stderr:
            raise CaptureError(
                "native process did not close cleanly: status={0}, "
                "stdout={1!r}, stderr={2!r}".format(
                    returncode,
                    remaining_stdout,
                    stderr,
                )
            )
        return {"code": code, "records": records, "exitStatus": returncode}
    except Exception:
        process.kill()
        process.wait()
        raise


def capture(output_path: Path) -> Mapping[str, object]:
    host = base.require_host()
    analysis_directory = Path(__file__).resolve().parent
    capture_source = Path(__file__).resolve()
    probe_source = analysis_directory / PROBE_SOURCE_NAME
    base_probe_source = analysis_directory / base.PROBE_SOURCE_NAME
    bridge_source = analysis_directory / base.BRIDGE_SOURCE_NAME
    parameters_result = analysis_directory / ENVIRONMENT_PARAMETERS_RESULT_NAME
    dependencies = (
        capture_source,
        probe_source,
        base_probe_source,
        bridge_source,
        parameters_result,
    )
    for source in dependencies:
        if not source.is_file():
            raise CaptureError("required source or predecessor is absent")
        if "/nix/store" in str(source):
            raise CaptureError("source path contains a Nix store path")
    if base.sha256(base_probe_source) != EXPECTED_BASE_PROBE_SOURCE_SHA256:
        raise CaptureError("included base probe source differs")
    payloads, parameter_digests, flags_bits = load_inputs(parameters_result)

    runs = []
    with tempfile.TemporaryDirectory(prefix="lg-environment-filter-") as temporary:
        temporary_directory = Path(temporary)
        executable = temporary_directory / "probe"
        base.run_command(
            (
                str(base.XCRUN),
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
        executable_sha256 = base.digest_bytes(executable_raw)
        for _ in range(base.FRESH_PROCESS_COUNT):
            runs.append(invoke_probe(executable, payloads, flags_bits))

    canonical_records = runs[0]["records"]
    if any(run["code"] != runs[0]["code"] for run in runs[1:]):
        raise CaptureError("exact-code identity varies across fresh processes")
    if any(run["records"] != canonical_records for run in runs[1:]):
        raise CaptureError("constructor or margin results vary across processes")

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
        "designLibraryEnvironmentParametersBackgroundFilterCaptureSchemaVersion": (
            SCHEMA_VERSION
        ),
        "classification": (
            "prospectively frozen direct invocation of Apple's exact "
            "BackgroundFilter constructor and sdfBackdropMargin getter over "
            "the canonical flags-produced internal Environment Parameters "
            "table; the real produced flags word is passed per case; no GUI, "
            "render, image, crop, pixel, or Nix store path"
        ),
        "host": host,
        "framework": {
            "path": str(base.DESIGNLIBRARY),
            "uuid": base.EXPECTED_DESIGNLIBRARY_UUID,
        },
        "predecessor": {
            "path": "Analysis/" + parameters_result.name,
            "sha256": base.sha256(parameters_result),
            "caseCount": len(payloads),
            "parametersByteCount": base.PARAMETERS_BYTE_COUNT,
        },
        "tool": {
            "python": sys.version.split()[0],
            "clang": base.run_command(
                (str(base.XCRUN), "clang", "--version")
            ).splitlines()[0],
            "captureSource": "Analysis/" + capture_source.name,
            "captureSourceSHA256": base.sha256(capture_source),
            "probeSource": "Analysis/" + probe_source.name,
            "probeSourceSHA256": base.sha256(probe_source),
            "includedBaseProbeSource": "Analysis/" + base_probe_source.name,
            "includedBaseProbeSourceSHA256": base.sha256(base_probe_source),
            "assemblyBridge": "Analysis/" + bridge_source.name,
            "assemblyBridgeSHA256": base.sha256(bridge_source),
            "probeExecutableSHA256": executable_sha256,
            "probeExecutableContainsNixStorePath": False,
            "freshProcessCount": base.FRESH_PROCESS_COUNT,
        },
        "exactCodeGate": {
            "constructorModuleOffset": 0xBAD00,
            "constructorByteCount": base.CONSTRUCTOR_CODE_BYTE_COUNT,
            "constructorSHA256": base.EXPECTED_CONSTRUCTOR_CODE_SHA256,
            "providerModuleOffset": 0xB70B4,
            "providerByteCount": base.PROVIDER_CODE_BYTE_COUNT,
            "providerSHA256": base.EXPECTED_PROVIDER_CODE_SHA256,
            "codeAuthenticatedBeforeInputsWritten": True,
        },
        "controlledConstructorArguments": {
            "layerIndex": 0,
            "environmentFlagsSource": "exact producedFlagsBits for each case",
        },
        "cases": cases,
        "uniqueBackgroundFilters": unique_objects,
        "measuredInvariants": {
            "environmentCaseCount": len(cases),
            "parametersByteCount": base.PARAMETERS_BYTE_COUNT,
            "backgroundFilterByteCount": base.BACKGROUND_FILTER_BYTE_COUNT,
            "uniqueBackgroundFilterCount": len(unique_objects),
            "distinctMarginRawWords": sorted(
                {case["marginRawLittleEndianHex"] for case in cases}
            ),
            "environmentFlagsEmbeddedBitwiseAtObjectOffset496": True,
            "freshProcessBitwiseStabilityEstablished": True,
            "constructorAndProviderCodeAuthenticatedBeforeInput": True,
            "capturedObjectOrMarginUsedForSelection": False,
        },
        "claims": {
            "controlledFlagsProducedEnvironmentToBackgroundFilterEstablished": True,
            "controlledFlagsProducedEnvironmentToMarginTableEstablished": True,
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
