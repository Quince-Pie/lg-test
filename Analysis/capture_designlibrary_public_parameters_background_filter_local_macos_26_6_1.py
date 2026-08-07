#!/usr/bin/env python3
"""Join frozen public Parameters to Apple's constructor and margin getter."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple


SCHEMA_VERSION = 1
EXPECTED_PRODUCT_VERSION = "26.6.1"
EXPECTED_BUILD_VERSION = "25G76"
EXPECTED_HARDWARE_MODEL = "MacBookPro18,2"
EXPECTED_DESIGNLIBRARY_UUID = "1E980802-69F5-3E69-89EF-50088297FCF5"
EXPECTED_DESIGNLIBRARY_UUID_HEX = "1e98080269f53e6989ef50088297fcf5"
EXPECTED_PUBLIC_PARAMETERS_RESULT_SHA256 = (
    "9cbf0a22a9c313b46147dfb2dacb6d64be4e5a928e0199470e08439ec070e02a"
)
EXPECTED_CONSTRUCTOR_CODE_SHA256 = (
    "71a592bc8a187fe8bcca0fa50c3f4d36ea3c2916dbd5d16f3fa1df05b86f131d"
)
EXPECTED_PROVIDER_CODE_SHA256 = (
    "a76c6f0b03cc6b64c6b040220f495c5f22d7e1e5322efb3cb139554dd397c10b"
)

PARAMETERS_BYTE_COUNT = 1025
BACKGROUND_FILTER_BYTE_COUNT = 504
CONSTRUCTOR_CODE_BYTE_COUNT = 1044
PROVIDER_CODE_BYTE_COUNT = 984
FRESH_PROCESS_COUNT = 3

DESIGNLIBRARY = Path(
    "/System/Library/PrivateFrameworks/DesignLibrary.framework/Versions/A/DesignLibrary"
)
DYLD_INFO = Path("/Library/Developer/CommandLineTools/usr/bin/dyld_info")
XCRUN = Path("/usr/bin/xcrun")
PROBE_SOURCE_NAME = (
    "probe_designlibrary_public_parameters_background_filter_local_macos_26_6_1.c"
)
BRIDGE_SOURCE_NAME = "invoke_designlibrary_public_parameters_background_filter_arm64.S"
PUBLIC_PARAMETERS_RESULT_NAME = (
    "designlibrary_public_parameters_local_macos_26_6_1_result.json"
)

EXPECTED_CASES = (
    (
        "static:regular",
        "ba1b5c3f6be3bcc624a29269230ac89d6fee2607e213650f1e8b74ffd00fc4fc",
        "0000000000000000",
    ),
    (
        "static:clear",
        "b7781bdee34a9b7517e4cf615f6f6876ae8be187088152d52240ddcd82bd31fc",
        "0000000000000000",
    ),
    (
        "static:control",
        "76e1f27c61955b07e82cd766ac04c9317534b007507e94c40fa491a0ef021273",
        "0000000000000000",
    ),
    (
        "static:text",
        "cff618f8beb075599ccc87dd6ed89660984783145831fbb839bab48748915fdc",
        "0000000000005040",
    ),
    (
        "static:identity",
        "b185b6c30d259e0fe55afc337f793efcd99af1cdccaf93a346821209d898765a",
        "0000000000000000",
    ),
    (
        "static:menu",
        "d36c35711acf7ade18f9fb49aa6fdd8ca7815a60635ad78176c4485d65cdf52a",
        "0000000000000000",
    ),
    (
        "static:dock",
        "ba3f4f22e00060472dd052fd1e9a4add5ee56e17b42f41b00a9b4d1481b14614",
        "0000000000000000",
    ),
    (
        "static:appIcons",
        "94818791aab4fa5f097e442f6d5af828b102e2f781aa791c7b13b941925821e9",
        "0000000000000000",
    ),
    (
        "static:widgets",
        "ec82167ea578a87e02c56d40c8006f3558b99d0a3407c5988843c9e3326a164d",
        "0000000000000000",
    ),
    (
        "static:avplayer",
        "b7781bdee34a9b7517e4cf615f6f6876ae8be187088152d52240ddcd82bd31fc",
        "0000000000000000",
    ),
    (
        "static:facetime",
        "b7781bdee34a9b7517e4cf615f6f6876ae8be187088152d52240ddcd82bd31fc",
        "0000000000000000",
    ),
    (
        "static:controlCenter",
        "b7781bdee34a9b7517e4cf615f6f6876ae8be187088152d52240ddcd82bd31fc",
        "0000000000000000",
    ),
    (
        "static:notificationCenter",
        "b85a3df94f602aedd87d63c185e8eb3c948d49ba9b47991212de67ea50b4b402",
        "0000000000000000",
    ),
    (
        "static:monogram",
        "ea49fba2b6bc20f5d44a918fc444312efa26309a5c8cc636814630e424c49bdf",
        "0000000000000000",
    ),
    (
        "static:bubbles",
        "ba1b5c3f6be3bcc624a29269230ac89d6fee2607e213650f1e8b74ffd00fc4fc",
        "0000000000000000",
    ),
    (
        "static:focusBorder",
        "a6e84b318f04171c4bf5041be15ff3d99e368d9bc22df57ea0880e69824cdc48",
        "0000000000000000",
    ),
    (
        "static:focusPlatter",
        "a6e84b318f04171c4bf5041be15ff3d99e368d9bc22df57ea0880e69824cdc48",
        "0000000000000000",
    ),
    (
        "static:keyboard",
        "8cfa1b89c5bc6a8b98abc45525f07f8260568a9e1bea7d67a0425df589c3a6c8",
        "0000000000000000",
    ),
    (
        "static:sidebar",
        "ba1b5c3f6be3bcc624a29269230ac89d6fee2607e213650f1e8b74ffd00fc4fc",
        "0000000000000000",
    ),
    (
        "static:abuttedSidebar",
        "6a9419535c5ea553b9c2035a2aede1359e520d2b8266a908d77a66f846cf6dce",
        "0000000000000000",
    ),
    (
        "static:inspector",
        "da55d0af247e4c7ed97b0d3fe7a62e3d25ad705f7451e218e762249419f5de76",
        "0000000000000000",
    ),
    (
        "static:loupe",
        "7710bba6a3553755bd1052ac5b66330dfe36ac0a5d8b7f292e5921282428b714",
        "0000000000000000",
    ),
    (
        "static:slider",
        "d53e5e9435d6dddade51afff4a37368d341518a5d5b6b5dad6ee72c3fcfdf8be",
        "0000000000000000",
    ),
    (
        "static:camera",
        "c204590b51a53ecf88f231e0bcb3710aa6c3807fb4ee56548a7ccf0d37efc2c1",
        "0000000000000000",
    ),
    (
        "static:cartouchePopover",
        "0c261f56dbf7158fbd02c5f4f9c716423a5daaa531289ad670e239c2e937fd59",
        "0000000000000000",
    ),
    (
        "static:siriSnippet",
        "8abb9188cf84f4b15f5d1d2e284c834fd417e14acfa00dc38f81c716cf5b6df7",
        "3433333333332340",
    ),
    (
        "static:carplayUltra",
        "b85a3df94f602aedd87d63c185e8eb3c948d49ba9b47991212de67ea50b4b402",
        "0000000000000000",
    ),
    (
        "mix:negative_quarter",
        "95477dc3115ad1d4866739cfb5d79a62c31f64e33b3c15aeb6e960b20e1b3aed",
        "3433333333332340",
    ),
    (
        "mix:zero",
        "10a49e6e4eb25b22049abfdb2258fa6adb27497c9603c3f5aa0e7908e446c505",
        "3433333333332340",
    ),
    (
        "mix:quarter",
        "3da0feb16daecf3c1b920f795ed72de6ea2fa33b86e17ee8de6f8fe4c36d4748",
        "3433333333332340",
    ),
    (
        "mix:half",
        "7e630272f23845778186c4713a71f04264b33c7a6f0a5bba68d753083058abd8",
        "3433333333332340",
    ),
    (
        "mix:three_quarters",
        "8ca883dcab7f5df5b81de521a5c950edd144db75eace1daf07caa73d160dc9b0",
        "3433333333332340",
    ),
    (
        "mix:one",
        "8b902437838987361b22206f597725c15899b1dfbc8f9b24e6928432454036f5",
        "0000000000000000",
    ),
    (
        "mix:five_quarters",
        "acdcd62cc7138651c692727294633b6c58403e006acf52013f01c5563c178fd6",
        "0000000000000000",
    ),
    (
        "modifier:color_scheme_light",
        "ba1b5c3f6be3bcc624a29269230ac89d6fee2607e213650f1e8b74ffd00fc4fc",
        "0000000000000000",
    ),
    (
        "modifier:color_scheme_dark",
        "ba1b5c3f6be3bcc624a29269230ac89d6fee2607e213650f1e8b74ffd00fc4fc",
        "0000000000000000",
    ),
    (
        "modifier:adaptive_false",
        "ba1b5c3f6be3bcc624a29269230ac89d6fee2607e213650f1e8b74ffd00fc4fc",
        "0000000000000000",
    ),
    (
        "modifier:adaptive_true",
        "ba1b5c3f6be3bcc624a29269230ac89d6fee2607e213650f1e8b74ffd00fc4fc",
        "0000000000000000",
    ),
    (
        "modifier:adaptive_light",
        "ba1b5c3f6be3bcc624a29269230ac89d6fee2607e213650f1e8b74ffd00fc4fc",
        "0000000000000000",
    ),
    (
        "modifier:adaptive_dark",
        "ba1b5c3f6be3bcc624a29269230ac89d6fee2607e213650f1e8b74ffd00fc4fc",
        "0000000000000000",
    ),
    (
        "modifier:adaptive_animatable_false",
        "ba1b5c3f6be3bcc624a29269230ac89d6fee2607e213650f1e8b74ffd00fc4fc",
        "0000000000000000",
    ),
    (
        "modifier:adaptive_animatable_true",
        "ba1b5c3f6be3bcc624a29269230ac89d6fee2607e213650f1e8b74ffd00fc4fc",
        "0000000000000000",
    ),
)

RESULT_PATTERN = re.compile(r"^RESULT=(\d+):OBJECT=([0-9a-f]+):MARGIN=([0-9a-f]+)$")


class CaptureError(RuntimeError):
    """Raised when the exact native join differs from its frozen contract."""


def digest_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def native_environment() -> Dict[str, str]:
    environment = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": "C",
        "LC_ALL": "C",
    }
    for name in ("HOME", "USER", "LOGNAME", "SHELL", "TMPDIR"):
        value = os.environ.get(name)
        if value:
            environment[name] = value
    if any("/nix/store" in value for value in environment.values()):
        raise CaptureError("native child environment contains a Nix store path")
    return environment


def run_command(arguments: Sequence[str], cwd: Optional[Path] = None) -> str:
    completed = subprocess.run(
        list(arguments),
        cwd=str(cwd) if cwd is not None else None,
        env=native_environment(),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise CaptureError(
            "command failed ({0}): {1}\n{2}".format(
                completed.returncode,
                " ".join(arguments),
                completed.stderr.strip(),
            )
        )
    return completed.stdout


def require_host() -> Mapping[str, str]:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise CaptureError("capture requires native arm64 macOS")
    host = {
        "system": platform.system(),
        "machine": platform.machine(),
        "macOSProductVersion": run_command(
            ("/usr/bin/sw_vers", "-productVersion")
        ).strip(),
        "macOSBuildVersion": run_command(("/usr/bin/sw_vers", "-buildVersion")).strip(),
        "hardwareModel": run_command(("/usr/sbin/sysctl", "-n", "hw.model")).strip(),
    }
    if (
        host["macOSProductVersion"] != EXPECTED_PRODUCT_VERSION
        or host["macOSBuildVersion"] != EXPECTED_BUILD_VERSION
        or host["hardwareModel"] != EXPECTED_HARDWARE_MODEL
    ):
        raise CaptureError("host differs from the frozen target profile")
    uuid_output = run_command((str(DYLD_INFO), "-uuid", str(DESIGNLIBRARY)))
    if EXPECTED_DESIGNLIBRARY_UUID not in uuid_output:
        raise CaptureError("DesignLibrary UUID differs")
    return host


def load_parameters(path: Path) -> Tuple[List[str], List[str]]:
    if sha256(path) != EXPECTED_PUBLIC_PARAMETERS_RESULT_SHA256:
        raise CaptureError("public Parameters canonical result differs")
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CaptureError("public Parameters result is unreadable") from error
    if (
        result.get("designLibraryPublicParametersCaptureSchemaVersion") != 1
        or result.get("claims", {}).get(
            "defaultContextPublicConfigurationToParametersTableEstablished"
        )
        is not True
        or result.get("parametersLayout", {}).get("byteCount") != PARAMETERS_BYTE_COUNT
    ):
        raise CaptureError("public Parameters result authority differs")
    cases = result.get("cases")
    unique = result.get("uniqueNormalizedParameters")
    if not isinstance(cases, list) or not isinstance(unique, dict):
        raise CaptureError("public Parameters result table is absent")
    names = [str(case.get("qualifiedName")) for case in cases]
    if names != [case[0] for case in EXPECTED_CASES]:
        raise CaptureError("public Parameters case order differs")
    payloads = []
    parameter_digests = []
    for case in cases:
        digest = str(case.get("normalizedParametersSHA256"))
        record = unique.get(digest)
        if not isinstance(record, dict):
            raise CaptureError("public Parameters blob is absent")
        try:
            payload = bytes.fromhex(str(record.get("normalizedHex", "")))
        except ValueError as error:
            raise CaptureError("public Parameters blob is invalid") from error
        if len(payload) != PARAMETERS_BYTE_COUNT or digest_bytes(payload) != digest:
            raise CaptureError("public Parameters blob identity differs")
        payloads.append(payload.hex())
        parameter_digests.append(digest)
    return payloads, parameter_digests


def read_code_header(process) -> Mapping[str, object]:
    assert process.stdout is not None
    uuid_line = process.stdout.readline().rstrip("\n")
    constructor_line = process.stdout.readline().rstrip("\n")
    provider_line = process.stdout.readline().rstrip("\n")
    if uuid_line != "DESIGN_LIBRARY_UUID=" + EXPECTED_DESIGNLIBRARY_UUID_HEX:
        raise CaptureError("native DesignLibrary identity header differs")
    if not constructor_line.startswith("CONSTRUCTOR_CODE="):
        raise CaptureError("native constructor code header is absent")
    if not provider_line.startswith("PROVIDER_CODE="):
        raise CaptureError("native provider code header is absent")
    try:
        constructor = bytes.fromhex(constructor_line.split("=", 1)[1])
        provider = bytes.fromhex(provider_line.split("=", 1)[1])
    except ValueError as error:
        raise CaptureError("native exact-code header is invalid") from error
    if (
        len(constructor) != CONSTRUCTOR_CODE_BYTE_COUNT
        or digest_bytes(constructor) != EXPECTED_CONSTRUCTOR_CODE_SHA256
        or len(provider) != PROVIDER_CODE_BYTE_COUNT
        or digest_bytes(provider) != EXPECTED_PROVIDER_CODE_SHA256
    ):
        raise CaptureError("native exact-code identity differs")
    return {
        "constructorByteCount": len(constructor),
        "constructorSHA256": digest_bytes(constructor),
        "providerByteCount": len(provider),
        "providerSHA256": digest_bytes(provider),
    }


def invoke_probe(executable: Path, payloads: Sequence[str]) -> Mapping[str, object]:
    try:
        process = subprocess.Popen(
            [str(executable)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=native_environment(),
        )
    except OSError as error:
        raise CaptureError("native probe launch failed") from error
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    try:
        code = read_code_header(process)
        for payload in payloads:
            process.stdin.write(payload + "\n")
        process.stdin.close()
        records = []
        for ordinal, expected in enumerate(EXPECTED_CASES):
            line = process.stdout.readline().rstrip("\n")
            match = RESULT_PATTERN.fullmatch(line)
            if match is None or int(match.group(1)) != ordinal:
                raise CaptureError("native result is absent or reordered")
            try:
                object_raw = bytes.fromhex(match.group(2))
                margin_raw = bytes.fromhex(match.group(3))
            except ValueError as error:
                raise CaptureError("native result payload is invalid") from error
            object_digest = digest_bytes(object_raw)
            if (
                len(object_raw) != BACKGROUND_FILTER_BYTE_COUNT
                or object_digest != expected[1]
                or len(margin_raw) != 8
                or margin_raw.hex() != expected[2]
            ):
                raise CaptureError("native constructor or margin result differs")
            records.append(
                {
                    "ordinal": ordinal,
                    "qualifiedName": expected[0],
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
    host = require_host()
    analysis_directory = Path(__file__).resolve().parent
    capture_source = Path(__file__).resolve()
    probe_source = analysis_directory / PROBE_SOURCE_NAME
    bridge_source = analysis_directory / BRIDGE_SOURCE_NAME
    parameters_result = analysis_directory / PUBLIC_PARAMETERS_RESULT_NAME
    for source in (capture_source, probe_source, bridge_source, parameters_result):
        if not source.is_file():
            raise CaptureError("required source or predecessor is absent")
        if "/nix/store" in str(source):
            raise CaptureError("source path contains a Nix store path")
    payloads, parameter_digests = load_parameters(parameters_result)

    runs = []
    with tempfile.TemporaryDirectory(prefix="lg-parameters-filter-") as temporary:
        temporary_directory = Path(temporary)
        executable = temporary_directory / "probe"
        run_command(
            (
                str(XCRUN),
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
        executable_sha256 = digest_bytes(executable_raw)
        for _ in range(FRESH_PROCESS_COUNT):
            runs.append(invoke_probe(executable, payloads))

    canonical_records = runs[0]["records"]
    if any(run["code"] != runs[0]["code"] for run in runs[1:]):
        raise CaptureError("exact-code identity varies across fresh processes")
    if any(run["records"] != canonical_records for run in runs[1:]):
        raise CaptureError("constructor or margin results vary across fresh processes")

    unique_objects: Dict[str, Mapping[str, object]] = {}
    cases = []
    for index, (record, parameters_digest) in enumerate(
        zip(canonical_records, parameter_digests)
    ):
        object_digest = record["backgroundFilterSHA256"]
        if object_digest not in unique_objects:
            unique_objects[object_digest] = {
                "hex": record["backgroundFilterHex"],
                "caseNames": [],
            }
        unique_objects[object_digest]["caseNames"].append(record["qualifiedName"])
        margin_raw = bytes.fromhex(record["marginRawLittleEndianHex"])
        cases.append(
            {
                "index": index,
                "qualifiedName": record["qualifiedName"],
                "normalizedParametersSHA256": parameters_digest,
                "backgroundFilterSHA256": object_digest,
                "marginRawLittleEndianHex": margin_raw.hex(),
                "margin": struct.unpack("<d", margin_raw)[0],
            }
        )

    result = {
        "designLibraryPublicParametersBackgroundFilterCaptureSchemaVersion": (
            SCHEMA_VERSION
        ),
        "classification": (
            "prospectively frozen direct invocation of Apple's exact "
            "BackgroundFilter constructor and sdfBackdropMargin getter over "
            "the canonical default-context public Parameters table; controlled "
            "layer index and environment flags are zero; no GUI, render, image, "
            "crop, pixel, or Nix store path"
        ),
        "host": host,
        "framework": {
            "path": str(DESIGNLIBRARY),
            "uuid": EXPECTED_DESIGNLIBRARY_UUID,
        },
        "predecessor": {
            "path": "Analysis/" + parameters_result.name,
            "sha256": sha256(parameters_result),
            "caseCount": len(payloads),
            "parametersByteCount": PARAMETERS_BYTE_COUNT,
        },
        "tool": {
            "python": sys.version.split()[0],
            "clang": run_command((str(XCRUN), "clang", "--version")).splitlines()[0],
            "captureSource": "Analysis/" + capture_source.name,
            "captureSourceSHA256": sha256(capture_source),
            "probeSource": "Analysis/" + probe_source.name,
            "probeSourceSHA256": sha256(probe_source),
            "assemblyBridge": "Analysis/" + bridge_source.name,
            "assemblyBridgeSHA256": sha256(bridge_source),
            "probeExecutableSHA256": executable_sha256,
            "probeExecutableContainsNixStorePath": False,
            "freshProcessCount": FRESH_PROCESS_COUNT,
        },
        "exactCodeGate": {
            "constructorModuleOffset": 0xBAD00,
            "constructorByteCount": CONSTRUCTOR_CODE_BYTE_COUNT,
            "constructorSHA256": EXPECTED_CONSTRUCTOR_CODE_SHA256,
            "providerModuleOffset": 0xB70B4,
            "providerByteCount": PROVIDER_CODE_BYTE_COUNT,
            "providerSHA256": EXPECTED_PROVIDER_CODE_SHA256,
            "codeAuthenticatedBeforeInputsWritten": True,
        },
        "controlledConstructorArguments": {
            "layerIndex": 0,
            "environmentFlagsRawValue": "0x0000000000000000",
        },
        "cases": cases,
        "uniqueBackgroundFilters": unique_objects,
        "measuredInvariants": {
            "caseCount": len(cases),
            "parametersByteCount": PARAMETERS_BYTE_COUNT,
            "backgroundFilterByteCount": BACKGROUND_FILTER_BYTE_COUNT,
            "uniqueBackgroundFilterCount": len(unique_objects),
            "distinctMarginRawWords": sorted(
                {case["marginRawLittleEndianHex"] for case in cases}
            ),
            "freshProcessBitwiseStabilityEstablished": True,
            "constructorAndProviderCodeAuthenticatedBeforeInput": True,
            "capturedObjectOrMarginUsedForSelection": False,
        },
        "claims": {
            "defaultContextPublicParametersToBackgroundFilterEstablished": True,
            "defaultContextPublicParametersToMarginTableEstablished": True,
            "liveTransitionParametersProductionEstablished": False,
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
