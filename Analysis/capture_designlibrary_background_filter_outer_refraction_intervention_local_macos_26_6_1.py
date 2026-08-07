#!/usr/bin/env python3
"""Prospectively test the getter's outer-refraction/blur-distance separation."""

import argparse
import hashlib
import json
import os
import platform
import re
import struct
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path


SCHEMA_VERSION = 1
FRESH_PROCESS_COUNT = 3
CASE_COUNT = 9
PARAMETERS_BYTE_COUNT = 1_025
BACKGROUND_FILTER_BYTE_COUNT = 504
OUTER_AMOUNT_PARAMETERS_OFFSET = 280
ENVIRONMENT_FLAGS = 0x0000_0000_0009_9183
PREREGISTRATION_NAME = (
    "designlibrary_background_filter_outer_refraction_intervention_"
    "local_macos_26_6_1_preregistration.json"
)
WEIGHTED_RESULT_NAME = (
    "designlibrary_material_context_weighted_live_timeline_parameters_"
    "local_macos_26_6_1_result.json"
)
CORRECTED_EXPORT_RESULT_NAME = (
    "designlibrary_weighted_parameters_background_filter_export_"
    "local_macos_26_6_1_result.json"
)
BOUNDARY_RESULT_NAME = (
    "designlibrary_material_context_weighted_live_public_boundary_analysis_result.json"
)
PROBE_SOURCE_NAME = (
    "probe_designlibrary_background_filter_outer_refraction_intervention_"
    "local_macos_26_6_1.c"
)
BRIDGE_SOURCE_NAME = (
    "invoke_designlibrary_weighted_parameters_background_filter_export_arm64.S"
)
CONTEXT_SOURCE_NAME = (
    "designlibrary_background_filter_outer_refraction_intervention_context.swift"
)
EXPECTED_PREREGISTRATION_SHA256 = (
    "7e73960ba18e9f265b5cf1ad07fa0ec6758c41abf049630b81f1e909975cdb4f"
)
EXPECTED_WEIGHTED_RESULT_SHA256 = (
    "adbb81b77b6d414e249c2febecf3752b6cb5ca292c5e882956d4d9bd2edecab7"
)
EXPECTED_CORRECTED_EXPORT_RESULT_SHA256 = (
    "d080175c56e380685d43c54e9712a56576ae8f54f5fddfd6650ecbf82beef19f"
)
EXPECTED_BOUNDARY_RESULT_SHA256 = (
    "308943d6d5cb16166cd7a1a3f63a824a2b4e47f93bab18e13f7fccac51b94767"
)
EXPECTED_BASE_PARAMETERS_SHA256 = (
    "320ce340bec7a7c25bb711077d8c43fda6d0dd98978d5348a5108375459d68c7"
)
EXPECTED_CONSTRUCTOR_CODE_SHA256 = (
    "71a592bc8a187fe8bcca0fa50c3f4d36ea3c2916dbd5d16f3fa1df05b86f131d"
)
EXPECTED_GETTER_CODE_SHA256 = (
    "0abc68898237c57aa2c31d54568649f57750241ea6cd4fe9c995d0b9857f826a"
)
EXPECTED_CONTEXT_THUNK_CODE_SHA256 = (
    "dd3179c1362f9b95fb87fc260e91e43d78e2d13aba07a2767707b3676e96eed7"
)
EXPECTED_DESIGNLIBRARY_UUID = "1e98080269f53e6989ef50088297fcf5"
EXPECTED_SWIFTUICORE_UUID = "99606d45c40a3c69ae515f0c4e32e531"
EXPECTED_PRODUCT_VERSION = "26.6.1"
EXPECTED_BUILD_VERSION = "25G76"
EXPECTED_HARDWARE_MODEL = "MacBookPro18,2"
CASE_PATTERN = re.compile(r"^CASE case_index=(\d+) object=([0-9a-f]{1008})$")
INTERVENTION_PATTERN = re.compile(r"^INTERVENTION_JSON=(\{.*\})$")
COMPLETE_PATTERN = re.compile(r"^COMPLETE cases=(\d+)$")


type JSONObject = dict[str, object]


class CaptureError(RuntimeError):
    """Raised when the frozen intervention contract differs."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def digest_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def normalized_capture_source_sha256(path: Path) -> str:
    payload = path.read_bytes()
    needle = EXPECTED_PREREGISTRATION_SHA256.encode()
    if payload.count(needle) != 1:
        raise CaptureError("capture preregistration hash slot differs")
    return digest_bytes(payload.replace(needle, b"0" * 64))


def native_environment() -> dict[str, str]:
    environment = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": "C",
        "LC_ALL": "C",
        "SHELL": "/bin/bash",
    }
    for name in ("HOME", "USER", "LOGNAME", "TMPDIR"):
        value = os.environ.get(name)
        if value and "/nix/store" not in value:
            environment[name] = value
    if any("/nix/store" in value for value in environment.values()):
        raise CaptureError("sanitized native environment contains a Nix store path")
    return environment


def run_command(
    arguments: Sequence[str],
    *,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(arguments),
        cwd=cwd,
        env=native_environment(),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise CaptureError(
            "command failed ({0}): {1}\nstdout:\n{2}\nstderr:\n{3}".format(
                completed.returncode,
                " ".join(arguments),
                completed.stdout.strip(),
                completed.stderr.strip(),
            )
        )
    return completed


def command_output(arguments: Sequence[str]) -> str:
    return run_command(arguments).stdout


def load_json(path: Path, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CaptureError(label + " is unreadable") from error
    return mapping(value, label)


def mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CaptureError(label + " is not an object")
    return value


def array(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise CaptureError(label + " is not an array")
    return value


def base_parameters(weighted_result: Mapping[str, object]) -> bytes:
    cases = array(weighted_result.get("cases"), "weighted cases")
    if len(cases) != 32:
        raise CaptureError("weighted case count differs")
    sample_two = mapping(cases[1], "weighted sample two")
    if (
        sample_two.get("index") != 2
        or sample_two.get("weightedParametersSHA256")
        != EXPECTED_BASE_PARAMETERS_SHA256
    ):
        raise CaptureError("base weighted Parameters identity differs")
    unique = mapping(
        weighted_result.get("uniqueWeightedNormalizedParameters"),
        "unique weighted Parameters",
    )
    record = mapping(
        unique.get(EXPECTED_BASE_PARAMETERS_SHA256),
        "base weighted Parameters",
    )
    encoded = record.get("normalizedHex")
    if not isinstance(encoded, str):
        raise CaptureError("base weighted Parameters payload is absent")
    try:
        payload = bytes.fromhex(encoded)
    except ValueError as error:
        raise CaptureError("base weighted Parameters payload is malformed") from error
    if (
        len(payload) != PARAMETERS_BYTE_COUNT
        or digest_bytes(payload) != EXPECTED_BASE_PARAMETERS_SHA256
    ):
        raise CaptureError("base weighted Parameters payload differs")
    return payload


def intervention_payloads(
    preregistration: Mapping[str, object],
    weighted_result: Mapping[str, object],
) -> tuple[list[bytes], list[Mapping[str, object]]]:
    base = base_parameters(weighted_result)
    unique = mapping(
        weighted_result.get("uniqueWeightedNormalizedParameters"),
        "unique weighted Parameters",
    )
    previously_opened = {
        bytes.fromhex(str(mapping(record, "weighted Parameters").get("normalizedHex")))[
            OUTER_AMOUNT_PARAMETERS_OFFSET : OUTER_AMOUNT_PARAMETERS_OFFSET + 8
        ]
        for record in unique.values()
    }
    cases = [
        mapping(item, "intervention case")
        for item in array(preregistration.get("interventionCases"), "interventions")
    ]
    if len(cases) != CASE_COUNT:
        raise CaptureError("intervention case count differs")
    payloads: list[bytes] = []
    for expected_index, case in enumerate(cases, start=1):
        encoded = case.get("outerAmountRawLittleEndianHex")
        if case.get("caseIndex") != expected_index or not isinstance(encoded, str):
            raise CaptureError("intervention case order differs")
        try:
            raw = bytes.fromhex(encoded)
        except ValueError as error:
            raise CaptureError("intervention word is malformed") from error
        if len(raw) != 8 or raw in previously_opened:
            raise CaptureError("intervention word is not unseen")
        bits = "0x{0:016x}".format(struct.unpack("<Q", raw)[0])
        if case.get("outerAmountBits") != bits:
            raise CaptureError("intervention bit identity differs")
        payload = bytearray(base)
        payload[
            OUTER_AMOUNT_PARAMETERS_OFFSET : OUTER_AMOUNT_PARAMETERS_OFFSET + 8
        ] = raw
        frozen_digest = case.get("syntheticParametersSHA256")
        if not isinstance(frozen_digest, str) or digest_bytes(payload) != frozen_digest:
            raise CaptureError("synthetic Parameters identity differs")
        payloads.append(bytes(payload))
    return payloads, cases


def expected_background_filter(parameters: bytes) -> bytes:
    output = bytearray(BACKGROUND_FILTER_BYTE_COUNT)
    for output_start, output_end, input_start, input_end in (
        (8, 152, 24, 168),
        (152, 224, 176, 248),
        (224, 276, 256, 308),
        (276, 349, 312, 385),
        (352, 458, 392, 498),
        (464, 476, 784, 796),
        (480, 496, 800, 816),
    ):
        output[output_start:output_end] = parameters[input_start:input_end]
    output[496:504] = struct.pack("<Q", ENVIRONMENT_FLAGS)
    return bytes(output)


def decode_code_line(
    lines: Mapping[str, str],
    name: str,
    byte_count: int,
    expected_sha256: str,
) -> None:
    encoded = lines.get(name)
    if encoded is None:
        raise CaptureError(name + " identity line is absent")
    try:
        payload = bytes.fromhex(encoded)
    except ValueError as error:
        raise CaptureError(name + " code is malformed") from error
    if len(payload) != byte_count or digest_bytes(payload) != expected_sha256:
        raise CaptureError(name + " code identity differs")


def parse_native_output(
    output: str,
    payloads: Sequence[bytes],
    interventions: Sequence[Mapping[str, object]],
) -> tuple[list[JSONObject], JSONObject]:
    identity_lines: dict[str, str] = {}
    objects: dict[int, bytes] = {}
    records: dict[int, Mapping[str, object]] = {}
    complete_count: int | None = None
    for line in output.splitlines():
        if "=" in line and line.split("=", 1)[0] in {
            "DESIGN_LIBRARY_UUID",
            "SWIFTUI_CORE_UUID",
            "CONSTRUCTOR_CODE",
            "GETTER_CODE",
            "CONTEXT_THUNK_CODE",
        }:
            name, value = line.split("=", 1)
            if name in identity_lines:
                raise CaptureError("duplicate native identity line " + name)
            identity_lines[name] = value
            continue
        case_match = CASE_PATTERN.fullmatch(line)
        if case_match is not None:
            case_index = int(case_match.group(1))
            if case_index in objects:
                raise CaptureError("duplicate constructor result")
            objects[case_index] = bytes.fromhex(case_match.group(2))
            continue
        intervention_match = INTERVENTION_PATTERN.fullmatch(line)
        if intervention_match is not None:
            try:
                value = json.loads(intervention_match.group(1))
            except json.JSONDecodeError as error:
                raise CaptureError("native intervention JSON is malformed") from error
            record = mapping(value, "native intervention")
            case_index = record.get("caseIndex")
            if not isinstance(case_index, int) or case_index in records:
                raise CaptureError("native intervention index differs")
            records[case_index] = record
            continue
        complete_match = COMPLETE_PATTERN.fullmatch(line)
        if complete_match is not None:
            complete_count = int(complete_match.group(1))
    if identity_lines.get("DESIGN_LIBRARY_UUID") != EXPECTED_DESIGNLIBRARY_UUID:
        raise CaptureError("native DesignLibrary UUID differs")
    if identity_lines.get("SWIFTUI_CORE_UUID") != EXPECTED_SWIFTUICORE_UUID:
        raise CaptureError("native SwiftUICore UUID differs")
    decode_code_line(
        identity_lines,
        "CONSTRUCTOR_CODE",
        1_044,
        EXPECTED_CONSTRUCTOR_CODE_SHA256,
    )
    decode_code_line(
        identity_lines,
        "GETTER_CODE",
        2_592,
        EXPECTED_GETTER_CODE_SHA256,
    )
    decode_code_line(
        identity_lines,
        "CONTEXT_THUNK_CODE",
        20,
        EXPECTED_CONTEXT_THUNK_CODE_SHA256,
    )
    expected_indices = list(range(1, CASE_COUNT + 1))
    if (
        complete_count != CASE_COUNT
        or list(objects) != expected_indices
        or list(records) != expected_indices
    ):
        raise CaptureError("native intervention topology differs")

    results: list[JSONObject] = []
    for case_index, (parameters, intervention) in enumerate(
        zip(payloads, interventions, strict=True),
        start=1,
    ):
        object_payload = objects[case_index]
        if object_payload != expected_background_filter(parameters):
            raise CaptureError("native constructor output differs")
        record = records[case_index]
        blur = mapping(record.get("inputBlurDistance4"), "blur distance four")
        outer = mapping(
            record.get("inputOuterRefractionAmount"),
            "outer refraction amount",
        )
        blur_raw = blur.get("rawLittleEndianHex")
        outer_raw = outer.get("rawLittleEndianHex")
        predicted_outer = intervention.get("outerAmountRawLittleEndianHex")
        if blur.get("objCType") != "d" or outer.get("objCType") != "d":
            raise CaptureError("native intervention NSNumber type differs")
        if blur_raw != "0000000000000000" or outer_raw != predicted_outer:
            raise CaptureError("prospectively frozen intervention outcome differs")
        results.append(
            {
                "caseIndex": case_index,
                "label": intervention.get("label"),
                "parametersSHA256": digest_bytes(parameters),
                "backgroundFilterSHA256": digest_bytes(object_payload),
                "inputOuterRefractionAmountRawLittleEndianHex": outer_raw,
                "inputBlurDistance4RawLittleEndianHex": blur_raw,
                "outerAmountIdentityMatchedBitwise": True,
                "blurDistance4PositiveZeroMatchedBitwise": True,
            }
        )
    identity: JSONObject = {
        "designLibraryUUID": EXPECTED_DESIGNLIBRARY_UUID,
        "swiftUICoreUUID": EXPECTED_SWIFTUICORE_UUID,
        "constructorCodeSHA256": EXPECTED_CONSTRUCTOR_CODE_SHA256,
        "getterCodeSHA256": EXPECTED_GETTER_CODE_SHA256,
        "contextThunkCodeSHA256": EXPECTED_CONTEXT_THUNK_CODE_SHA256,
    }
    return results, identity


def capture(output_path: Path) -> Mapping[str, object]:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise CaptureError("capture requires native arm64 macOS")
    product_version = command_output(("/usr/bin/sw_vers", "-productVersion")).strip()
    build_version = command_output(("/usr/bin/sw_vers", "-buildVersion")).strip()
    hardware_model = command_output(("/usr/sbin/sysctl", "-n", "hw.model")).strip()
    if (
        product_version != EXPECTED_PRODUCT_VERSION
        or build_version != EXPECTED_BUILD_VERSION
        or hardware_model != EXPECTED_HARDWARE_MODEL
    ):
        raise CaptureError("host differs from frozen target")

    analysis_directory = Path(__file__).resolve().parent
    source_path = Path(__file__).resolve()
    paths = {
        "preregistration": analysis_directory / PREREGISTRATION_NAME,
        "weightedParameters": analysis_directory / WEIGHTED_RESULT_NAME,
        "correctedExporter": analysis_directory / CORRECTED_EXPORT_RESULT_NAME,
        "boundary": analysis_directory / BOUNDARY_RESULT_NAME,
        "probe": analysis_directory / PROBE_SOURCE_NAME,
        "bridge": analysis_directory / BRIDGE_SOURCE_NAME,
        "context": analysis_directory / CONTEXT_SOURCE_NAME,
    }
    expected_hashes = {
        "preregistration": EXPECTED_PREREGISTRATION_SHA256,
        "weightedParameters": EXPECTED_WEIGHTED_RESULT_SHA256,
        "correctedExporter": EXPECTED_CORRECTED_EXPORT_RESULT_SHA256,
        "boundary": EXPECTED_BOUNDARY_RESULT_SHA256,
    }
    if any(not path.is_file() for path in paths.values()):
        raise CaptureError("capture source set is incomplete")
    if any("/nix/store" in str(path) for path in paths.values()):
        raise CaptureError("capture source path contains a Nix store path")
    for name, expected_hash in expected_hashes.items():
        if sha256(paths[name]) != expected_hash:
            raise CaptureError(name + " identity differs")

    preregistration = load_json(paths["preregistration"], "preregistration")
    weighted_result = load_json(paths["weightedParameters"], "weighted Parameters")
    if (
        preregistration.get(
            "designLibraryBackgroundFilterOuterRefractionInterventionPreregistrationSchemaVersion"
        )
        != 1
        or preregistration.get("caseCount") != CASE_COUNT
        or preregistration.get("freshProcessCount") != FRESH_PROCESS_COUNT
        or preregistration.get("capturedValuesUsedForRuntimeSelection") is not False
    ):
        raise CaptureError("preregistration contract differs")
    predecessors = mapping(preregistration.get("predecessors"), "predecessors")
    if predecessors != {
        "weightedParametersResultSHA256": EXPECTED_WEIGHTED_RESULT_SHA256,
        "correctedExporterResultSHA256": EXPECTED_CORRECTED_EXPORT_RESULT_SHA256,
        "weightedPublicBoundaryResultSHA256": EXPECTED_BOUNDARY_RESULT_SHA256,
    }:
        raise CaptureError("preregistered predecessors differ")
    source_identity = mapping(preregistration.get("sourceIdentity"), "source identity")
    if source_identity != {
        "captureSourceNormalizedSHA256": normalized_capture_source_sha256(source_path),
        "probeSourceSHA256": sha256(paths["probe"]),
        "bridgeSourceSHA256": sha256(paths["bridge"]),
        "contextSourceSHA256": sha256(paths["context"]),
    }:
        raise CaptureError("preregistered source identity differs")
    payloads, interventions = intervention_payloads(preregistration, weighted_result)
    native_input = "".join(payload.hex() + "\n" for payload in payloads)

    with tempfile.TemporaryDirectory(prefix="lg-outer-refraction-intervention-") as temp:
        directory = Path(temp)
        probe_object = directory / "probe.o"
        bridge_object = directory / "bridge.o"
        context_object = directory / "context.o"
        executable = directory / "probe"
        run_command(
            (
                "/usr/bin/xcrun",
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
                "-c",
                str(paths["probe"]),
                "-o",
                str(probe_object),
            ),
            cwd=directory,
        )
        run_command(
            (
                "/usr/bin/xcrun",
                "clang",
                "-arch",
                "arm64",
                "-c",
                str(paths["bridge"]),
                "-o",
                str(bridge_object),
            ),
            cwd=directory,
        )
        run_command(
            (
                "/usr/bin/xcrun",
                "swiftc",
                "-parse-as-library",
                "-emit-object",
                str(paths["context"]),
                "-o",
                str(context_object),
            ),
            cwd=directory,
        )
        run_command(
            (
                "/usr/bin/xcrun",
                "swiftc",
                str(probe_object),
                str(bridge_object),
                str(context_object),
                "-o",
                str(executable),
            ),
            cwd=directory,
        )
        executable_payload = executable.read_bytes()
        if b"/nix/store" in executable_payload:
            raise CaptureError("native executable embeds a Nix store path")

        runs: list[JSONObject] = []
        canonical_results: list[JSONObject] | None = None
        canonical_identity: JSONObject | None = None
        for run_index in range(FRESH_PROCESS_COUNT):
            completed = subprocess.run(
                [str(executable)],
                input=native_input,
                cwd=directory,
                env=native_environment(),
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
            )
            if completed.returncode != 0 or completed.stderr:
                raise CaptureError(
                    "native intervention failed: status={0} stderr={1}".format(
                        completed.returncode,
                        completed.stderr.strip(),
                    )
                )
            results, identity = parse_native_output(
                completed.stdout,
                payloads,
                interventions,
            )
            semantic = json.dumps(
                results,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
            if canonical_results is None:
                canonical_results = results
                canonical_identity = identity
            elif results != canonical_results or identity != canonical_identity:
                raise CaptureError("native intervention differs between processes")
            runs.append(
                {
                    "runIndex": run_index,
                    "stdoutSHA256": digest_bytes(completed.stdout.encode()),
                    "stderrSHA256": digest_bytes(completed.stderr.encode()),
                    "semanticSHA256": digest_bytes(semantic),
                }
            )
        if canonical_results is None or canonical_identity is None:
            raise CaptureError("native intervention produced no result")

        result: JSONObject = {
            "designLibraryBackgroundFilterOuterRefractionInterventionCaptureSchemaVersion": (
                SCHEMA_VERSION
            ),
            "classification": (
                "prospective single-variable intervention over nine previously unseen "
                "binary64 refraction.outerAmount words; every synthetic Parameters "
                "hash, raw output prediction, source identity, process count, and "
                "acceptance rule was frozen before the Apple getter was opened"
            ),
            "host": {
                "system": platform.system(),
                "machine": platform.machine(),
                "macOSProductVersion": product_version,
                "macOSBuildVersion": build_version,
                "hardwareModel": hardware_model,
            },
            "toolchain": {
                "python": platform.python_version(),
                "clang": command_output(("/usr/bin/xcrun", "clang", "--version")).strip(),
                "swift": command_output(("/usr/bin/xcrun", "swiftc", "--version")).strip(),
            },
            "inputs": {
                name: {
                    "path": "Analysis/" + path.name,
                    "sha256": sha256(path),
                }
                for name, path in paths.items()
            }
            | {
                "captureSource": {
                    "path": "Analysis/" + source_path.name,
                    "sha256": sha256(source_path),
                }
            },
            "nativeIdentity": canonical_identity,
            "nativeExecutable": {
                "sha256": digest_bytes(executable_payload),
                "containsNixStorePath": False,
            },
            "runs": runs,
            "cases": canonical_results,
            "measuredInvariants": {
                "caseCount": CASE_COUNT,
                "previouslyUnseenInterventionCount": CASE_COUNT,
                "freshProcessCount": FRESH_PROCESS_COUNT,
                "freshProcessSemanticMatchCount": FRESH_PROCESS_COUNT,
                "constructorOutputExactCount": CASE_COUNT,
                "outerAmountIdentityBitwiseMatchCount": CASE_COUNT,
                "blurDistance4PositiveZeroBitwiseMatchCount": CASE_COUNT,
                "capturedValuesUsedForRuntimeSelection": False,
            },
            "interpretation": {
                "established": (
                    "the authenticated getter exports refraction.outerAmount only as "
                    "inputOuterRefractionAmount and independently emits exact binary64 "
                    "positive zero for inputBlurDistance4"
                ),
                "rejected": (
                    "inputBlurDistance4 is an identity copy or alias of "
                    "refraction.outerAmount"
                ),
                "nextUnknown": (
                    "capture the distinct actual live producer that supplies the "
                    "retained public nonzero inputBlurDistance4 values"
                ),
            },
            "claims": {
                "outerRefractionGetterSeparationEstablishedProspectively": True,
                "actualLiveCallbackCompleteParametersObserved": False,
                "completeLiveParametersTransferEstablished": False,
                "generalIntegerCropAllocationPolicyEstablished": False,
                "retinaCompositorColorLawEstablished": False,
                "independentWalleZeroByteFrameParityEstablished": False,
                "liquidGlassParityEstablished": False,
                "productionShaderChangeAuthorized": False,
            },
        }
        output_path.write_text(
            json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, suggest_on_error=True)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    try:
        capture(arguments.output.resolve())
    except (CaptureError, subprocess.TimeoutExpired) as error:
        print("CAPTURE_ERROR: " + str(error))
        return 1
    print(str(arguments.output.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
