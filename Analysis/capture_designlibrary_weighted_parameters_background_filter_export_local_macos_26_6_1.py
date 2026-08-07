#!/usr/bin/env python3
"""Consolidate the corrected weighted Parameters-to-CAFilter exporter law."""

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
FIRST_HOLDOUT_SAMPLE_INDEX = 2
LAST_HOLDOUT_SAMPLE_INDEX = 32
HOLDOUT_SAMPLE_COUNT = 31
MAPPED_FIELD_COUNT = 49
MAPPED_COMPONENT_COUNT = 1_519
EXPECTED_PUBLIC_MATCH_COUNT = 1_054
EXPECTED_PUBLIC_MISMATCH_COUNT = 465
PARAMETERS_BYTE_COUNT = 1_025
BACKGROUND_FILTER_BYTE_COUNT = 504
ENVIRONMENT_FLAGS = 0x0000_0000_0009_9183
PREREGISTRATION_NAME = (
    "designlibrary_weighted_parameters_background_filter_export_"
    "local_macos_26_6_1_preregistration.json"
)
WEIGHTED_RESULT_NAME = (
    "designlibrary_material_context_weighted_live_timeline_parameters_"
    "local_macos_26_6_1_result.json"
)
BOUNDARY_RESULT_NAME = (
    "designlibrary_material_context_weighted_live_public_boundary_analysis_result.json"
)
METADATA_RESULT_NAME = (
    "designlibrary_background_filter_metadata_local_macos_26_6_1_result.json"
)
PUBLIC_PROJECTION_NAME = (
    "designlibrary_material_context_weighted_live_public_projection.json"
)
PROBE_SOURCE_NAME = (
    "probe_designlibrary_weighted_parameters_background_filter_export_"
    "local_macos_26_6_1.c"
)
BRIDGE_SOURCE_NAME = (
    "invoke_designlibrary_weighted_parameters_background_filter_export_arm64.S"
)
CONTEXT_SOURCE_NAME = (
    "designlibrary_weighted_parameters_background_filter_export_context.swift"
)
EXPECTED_PREREGISTRATION_SHA256 = (
    "8ef67f6b6106097162cdfb998f81a765da2a8b71b8ba86dafa79f4a5c505bba5"
)
EXPECTED_WEIGHTED_RESULT_SHA256 = (
    "adbb81b77b6d414e249c2febecf3752b6cb5ca292c5e882956d4d9bd2edecab7"
)
EXPECTED_BOUNDARY_RESULT_SHA256 = (
    "308943d6d5cb16166cd7a1a3f63a824a2b4e47f93bab18e13f7fccac51b94767"
)
EXPECTED_METADATA_RESULT_SHA256 = (
    "dc2202be02d3831126866236661173c92bf492498a4cc2d2717931ba296b0757"
)
EXPECTED_PUBLIC_PROJECTION_SHA256 = (
    "d4d8471355e0cbba4578d2b3786951116a372f5fcc94798ed9384687008d4573"
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
CASE_PATTERN = re.compile(r"^CASE sample_index=(\d+) object=([0-9a-f]{1008})$")
FILTER_PATTERN = re.compile(r"^FILTER_JSON=(\{.*\})$")
COMPLETE_PATTERN = re.compile(r"^COMPLETE cases=(\d+)$")


type JSONObject = dict[str, object]


class CaptureError(RuntimeError):
    """Raised when the prospective native export violates its contract."""


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


def canonical_digest(value: object) -> str:
    return digest_bytes(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    )


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
    if not isinstance(value, Mapping):
        raise CaptureError(label + " is not an object")
    return value


def mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CaptureError(label + " is not an object")
    return value


def array(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise CaptureError(label + " is not an array")
    return value


def prediction_contract(boundary: Mapping[str, object]) -> list[JSONObject]:
    result: list[JSONObject] = []
    for untyped_field in array(boundary.get("mappedFields"), "mapped fields"):
        field = mapping(untyped_field, "mapped field")
        observations = array(field.get("observations"), "mapped observations")
        if len(observations) != 32:
            raise CaptureError("mapped observation count differs")
        result.append(
            {
                "parametersField": field.get("parametersField"),
                "publicInput": field.get("publicInput"),
                "storage": field.get("storage"),
                "candidateToPublicTransform": field.get("candidateToPublicTransform"),
                "holdoutObservations": [
                    {
                        "sampleIndex": observation.get("sampleIndex"),
                        "predictedPublicRawLittleEndianHex": observation.get(
                            "predictedPublicRawLittleEndianHex"
                        ),
                        "retainedPublicRawLittleEndianHex": observation.get(
                            "publicRawLittleEndianHex"
                        ),
                        "predictedMatchesRetainedPublic": observation.get(
                            "matchedBitwise"
                        ),
                    }
                    for untyped_observation in observations[1:]
                    for observation in [
                        mapping(untyped_observation, "mapped observation")
                    ]
                ],
            }
        )
    return result


def validate_predecessors(
    preregistration: Mapping[str, object],
    weighted_result: Mapping[str, object],
    boundary_result: Mapping[str, object],
) -> tuple[list[Mapping[str, object]], Mapping[str, object], list[JSONObject]]:
    if (
        preregistration.get(
            "designLibraryWeightedParametersBackgroundFilterExportPreregistrationSchemaVersion"
        )
        != 1
    ):
        raise CaptureError("preregistration schema differs")
    predecessors = mapping(preregistration.get("predecessors"), "predecessors")
    if predecessors != {
        "weightedParametersResultSHA256": EXPECTED_WEIGHTED_RESULT_SHA256,
        "weightedPublicBoundaryResultSHA256": EXPECTED_BOUNDARY_RESULT_SHA256,
        "backgroundFilterMetadataResultSHA256": EXPECTED_METADATA_RESULT_SHA256,
        "publicProjectionSHA256": EXPECTED_PUBLIC_PROJECTION_SHA256,
    }:
        raise CaptureError("preregistered predecessors differ")
    contract = prediction_contract(boundary_result)
    prediction = mapping(preregistration.get("prediction"), "prediction")
    if (
        prediction.get("calibrationSampleIndexExcluded") != 1
        or prediction.get("firstHoldoutSampleIndex") != FIRST_HOLDOUT_SAMPLE_INDEX
        or prediction.get("lastHoldoutSampleIndex") != LAST_HOLDOUT_SAMPLE_INDEX
        or prediction.get("holdoutSampleCount") != HOLDOUT_SAMPLE_COUNT
        or prediction.get("mappedFieldCount") != MAPPED_FIELD_COUNT
        or prediction.get("mappedComponentCount") != MAPPED_COMPONENT_COUNT
        or prediction.get("exporterPredictionMatchCount") != MAPPED_COMPONENT_COUNT
        or prediction.get("retainedPublicMatchCount") != EXPECTED_PUBLIC_MATCH_COUNT
        or prediction.get("retainedPublicMismatchCount")
        != EXPECTED_PUBLIC_MISMATCH_COUNT
        or prediction.get("predictionContractSHA256") != canonical_digest(contract)
    ):
        raise CaptureError("preregistered prediction differs")
    cases = [
        mapping(item, "weighted case")
        for item in array(weighted_result.get("cases"), "weighted cases")
    ]
    unique = mapping(
        weighted_result.get("uniqueWeightedNormalizedParameters"),
        "unique weighted Parameters",
    )
    holdout_cases = cases[1:]
    derived_cases = [
        {
            "sampleIndex": case.get("index"),
            "fractionBits": case.get("fractionBits"),
            "weightedParametersSHA256": case.get("weightedParametersSHA256"),
        }
        for case in holdout_cases
    ]
    if preregistration.get("holdoutCases") != derived_cases:
        raise CaptureError("preregistered holdout cases differ")
    if [case.get("index") for case in holdout_cases] != list(range(2, 33)):
        raise CaptureError("weighted holdout case order differs")
    return holdout_cases, unique, contract


def parameters_payload(
    case: Mapping[str, object],
    unique: Mapping[str, object],
) -> bytes:
    digest = case.get("weightedParametersSHA256")
    record = mapping(unique.get(digest), "weighted Parameters record")
    encoded = record.get("normalizedHex")
    if not isinstance(digest, str) or not isinstance(encoded, str):
        raise CaptureError("weighted Parameters payload is absent")
    try:
        payload = bytes.fromhex(encoded)
    except ValueError as error:
        raise CaptureError("weighted Parameters payload is malformed") from error
    if len(payload) != PARAMETERS_BYTE_COUNT or digest_bytes(payload) != digest:
        raise CaptureError("weighted Parameters payload identity differs")
    return payload


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
) -> bytes:
    encoded = lines.get(name)
    if encoded is None:
        raise CaptureError(name + " identity line is absent")
    try:
        payload = bytes.fromhex(encoded)
    except ValueError as error:
        raise CaptureError(name + " code is malformed") from error
    if len(payload) != byte_count or digest_bytes(payload) != expected_sha256:
        raise CaptureError(name + " code identity differs")
    return payload


def parse_native_output(
    output: str,
    payloads: Sequence[bytes],
) -> tuple[list[JSONObject], Mapping[str, object]]:
    identity_lines: dict[str, str] = {}
    objects: dict[int, bytes] = {}
    filters: dict[int, Mapping[str, object]] = {}
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
            sample_index = int(case_match.group(1))
            if sample_index in objects:
                raise CaptureError("duplicate native object")
            objects[sample_index] = bytes.fromhex(case_match.group(2))
            continue
        filter_match = FILTER_PATTERN.fullmatch(line)
        if filter_match is not None:
            try:
                record = json.loads(filter_match.group(1))
            except json.JSONDecodeError as error:
                raise CaptureError("native filter JSON is malformed") from error
            typed_record = mapping(record, "native filter record")
            sample_index = typed_record.get("sampleIndex")
            if not isinstance(sample_index, int) or sample_index in filters:
                raise CaptureError("native filter sample index differs")
            filters[sample_index] = typed_record
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
    expected_indices = list(range(2, 33))
    if (
        complete_count != HOLDOUT_SAMPLE_COUNT
        or list(objects) != expected_indices
        or list(filters) != expected_indices
    ):
        raise CaptureError("native case topology differs")
    cases: list[JSONObject] = []
    for sample_index, parameters in zip(expected_indices, payloads, strict=True):
        object_payload = objects[sample_index]
        if object_payload != expected_background_filter(parameters):
            raise CaptureError("native constructor output differs")
        filter_record = filters[sample_index]
        input_keys = array(filter_record.get("inputKeys"), "native input keys")
        input_values = mapping(filter_record.get("inputValues"), "native inputs")
        if input_keys != sorted(input_keys) or set(input_keys) != set(input_values):
            raise CaptureError("native input-key domain differs")
        cases.append(
            {
                "sampleIndex": sample_index,
                "parametersSHA256": digest_bytes(parameters),
                "backgroundFilterSHA256": digest_bytes(object_payload),
                "backgroundFilterHex": object_payload.hex(),
                "filter": dict(filter_record),
            }
        )
    identity: JSONObject = {
        "designLibraryUUID": EXPECTED_DESIGNLIBRARY_UUID,
        "swiftUICoreUUID": EXPECTED_SWIFTUICORE_UUID,
        "constructorCodeSHA256": EXPECTED_CONSTRUCTOR_CODE_SHA256,
        "getterCodeSHA256": EXPECTED_GETTER_CODE_SHA256,
        "contextThunkCodeSHA256": EXPECTED_CONTEXT_THUNK_CODE_SHA256,
    }
    return cases, identity


def raw_actual_value(
    field: Mapping[str, object],
    values: Mapping[str, object],
) -> bytes:
    public_input = field.get("publicInput")
    storage = field.get("storage")
    if not isinstance(public_input, str) or not isinstance(storage, str):
        raise CaptureError("mapped field metadata differs")
    if public_input.startswith("inputShadowOffset."):
        offset = mapping(values.get("inputShadowOffset"), "native shadow offset")
        encoded = offset.get("hex")
        if not isinstance(encoded, str):
            raise CaptureError("native shadow offset bytes are absent")
        try:
            payload = bytes.fromhex(encoded)
        except ValueError as error:
            raise CaptureError("native shadow offset bytes are malformed") from error
        lane = 0 if public_input.endswith(".width") else 1
        return payload[lane * 8 : lane * 8 + 8]
    value = values.get(public_input)
    if public_input == "inputBleedDarkenBlend":
        if not isinstance(value, (bool, int)):
            raise CaptureError("native edge-darken value differs")
        return bytes([int(value) & 1])
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise CaptureError("native mapped scalar differs")
    if storage == "binary32":
        return struct.pack("<f", float(value))
    if storage == "binary64":
        return struct.pack("<d", float(value))
    raise CaptureError("native mapped storage differs")


def compare_mapped_fields(
    contract: Sequence[Mapping[str, object]],
    cases: Sequence[Mapping[str, object]],
) -> tuple[list[JSONObject], int, int]:
    field_results: list[JSONObject] = []
    exporter_matches = 0
    public_matches = 0
    for field in contract:
        observations = array(field.get("holdoutObservations"), "holdout observations")
        if len(observations) != len(cases):
            raise CaptureError("holdout observation count differs")
        records: list[JSONObject] = []
        for case, untyped_observation in zip(cases, observations, strict=True):
            observation = mapping(untyped_observation, "holdout observation")
            filter_record = mapping(case.get("filter"), "native filter")
            values = mapping(filter_record.get("inputValues"), "native filter inputs")
            actual = raw_actual_value(field, values)
            predicted = bytes.fromhex(
                str(observation.get("predictedPublicRawLittleEndianHex"))
            )
            retained_public = bytes.fromhex(
                str(observation.get("retainedPublicRawLittleEndianHex"))
            )
            exporter_match = actual == predicted
            public_match = actual == retained_public
            exporter_matches += exporter_match
            public_matches += public_match
            records.append(
                {
                    "sampleIndex": case.get("sampleIndex"),
                    "actualRawLittleEndianHex": actual.hex(),
                    "predictedRawLittleEndianHex": predicted.hex(),
                    "retainedPublicRawLittleEndianHex": retained_public.hex(),
                    "actualMatchesPrediction": exporter_match,
                    "actualMatchesRetainedPublic": public_match,
                }
            )
        field_results.append(
            {
                "parametersField": field.get("parametersField"),
                "publicInput": field.get("publicInput"),
                "storage": field.get("storage"),
                "candidateToPublicTransform": field.get("candidateToPublicTransform"),
                "observations": records,
                "predictionMatchCount": sum(
                    record["actualMatchesPrediction"] is True for record in records
                ),
                "retainedPublicMatchCount": sum(
                    record["actualMatchesRetainedPublic"] is True for record in records
                ),
            }
        )
    return field_results, exporter_matches, public_matches


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
        "weighted": analysis_directory / WEIGHTED_RESULT_NAME,
        "boundary": analysis_directory / BOUNDARY_RESULT_NAME,
        "metadata": analysis_directory / METADATA_RESULT_NAME,
        "projection": analysis_directory / PUBLIC_PROJECTION_NAME,
        "probe": analysis_directory / PROBE_SOURCE_NAME,
        "bridge": analysis_directory / BRIDGE_SOURCE_NAME,
        "context": analysis_directory / CONTEXT_SOURCE_NAME,
    }
    expected_hashes = {
        "preregistration": EXPECTED_PREREGISTRATION_SHA256,
        "weighted": EXPECTED_WEIGHTED_RESULT_SHA256,
        "boundary": EXPECTED_BOUNDARY_RESULT_SHA256,
        "metadata": EXPECTED_METADATA_RESULT_SHA256,
        "projection": EXPECTED_PUBLIC_PROJECTION_SHA256,
    }
    if any(not path.is_file() for path in paths.values()):
        raise CaptureError("capture source set is incomplete")
    if any("/nix/store" in str(path) for path in paths.values()):
        raise CaptureError("capture source path contains a Nix store path")
    for name, expected_hash in expected_hashes.items():
        if sha256(paths[name]) != expected_hash:
            raise CaptureError(name + " identity differs")

    preregistration = load_json(paths["preregistration"], "preregistration")
    weighted_result = load_json(paths["weighted"], "weighted result")
    boundary_result = load_json(paths["boundary"], "boundary result")
    source_identity = mapping(preregistration.get("sourceIdentity"), "source identity")
    if source_identity != {
        "captureSourceNormalizedSHA256": normalized_capture_source_sha256(source_path),
        "probeSourceSHA256": sha256(paths["probe"]),
        "bridgeSourceSHA256": sha256(paths["bridge"]),
        "contextSourceSHA256": sha256(paths["context"]),
    }:
        raise CaptureError("preregistered source identity differs")
    holdout_cases, unique, contract = validate_predecessors(
        preregistration,
        weighted_result,
        boundary_result,
    )
    payloads = [parameters_payload(case, unique) for case in holdout_cases]
    native_input = "".join(payload.hex() + "\n" for payload in payloads)

    with tempfile.TemporaryDirectory(prefix="lg-weighted-filter-export-") as temporary:
        directory = Path(temporary)
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
        canonical_cases: list[JSONObject] | None = None
        canonical_identity: Mapping[str, object] | None = None
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
                    "native export failed: status={0} stderr={1}".format(
                        completed.returncode,
                        completed.stderr.strip(),
                    )
                )
            cases, identity = parse_native_output(completed.stdout, payloads)
            semantic_sha256 = canonical_digest(cases)
            if canonical_cases is None:
                canonical_cases = cases
                canonical_identity = identity
            elif cases != canonical_cases or identity != canonical_identity:
                raise CaptureError("native export differs between fresh processes")
            runs.append(
                {
                    "runIndex": run_index,
                    "stdoutSHA256": digest_bytes(completed.stdout.encode()),
                    "stderrSHA256": digest_bytes(completed.stderr.encode()),
                    "semanticSHA256": semantic_sha256,
                }
            )

        if canonical_cases is None or canonical_identity is None:
            raise CaptureError("native export produced no canonical cases")
        field_results, exporter_matches, public_matches = compare_mapped_fields(
            contract,
            canonical_cases,
        )
        public_mismatches = MAPPED_COMPONENT_COUNT - public_matches
        if (
            exporter_matches != MAPPED_COMPONENT_COUNT
            or public_matches != EXPECTED_PUBLIC_MATCH_COUNT
            or public_mismatches != EXPECTED_PUBLIC_MISMATCH_COUNT
        ):
            raise CaptureError("corrected exporter outcome differs")
        input_key_counts = {
            len(array(mapping(case["filter"], "filter").get("inputKeys"), "keys"))
            for case in canonical_cases
        }
        if len(input_key_counts) != 1:
            raise CaptureError("native filter input-key count differs")

        result: JSONObject = {
            "designLibraryWeightedParametersBackgroundFilterExportCaptureSchemaVersion": (
                SCHEMA_VERSION
            ),
            "classification": (
                "retrospective exact consolidation after the original prospective "
                "31-case holdout genuinely falsified one decoded exporter field; the "
                "unchanged controlled Parameters values pass through Apple's exact "
                "constructor, CAFilterContext dispatch thunk, and filter-array getter "
                "before KVC readback; the disclosed correction makes "
                "inputBlurDistance4 constant binary64 positive zero"
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
                "clang": command_output(
                    ("/usr/bin/xcrun", "clang", "--version")
                ).strip(),
                "swift": command_output(
                    ("/usr/bin/xcrun", "swiftc", "--version")
                ).strip(),
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
            "nativeIdentity": dict(canonical_identity),
            "nativeExecutable": {
                "sha256": digest_bytes(executable_payload),
                "containsNixStorePath": False,
            },
            "runs": runs,
            "cases": canonical_cases,
            "mappedFields": field_results,
            "measuredInvariants": {
                "calibrationSampleIndexExcluded": 1,
                "holdoutSampleCount": HOLDOUT_SAMPLE_COUNT,
                "freshProcessCount": FRESH_PROCESS_COUNT,
                "freshProcessSemanticMatchCount": FRESH_PROCESS_COUNT,
                "filterInputKeyCount": input_key_counts.pop(),
                "constructorOutputExactCount": HOLDOUT_SAMPLE_COUNT,
                "mappedFieldCount": MAPPED_FIELD_COUNT,
                "mappedComponentCount": MAPPED_COMPONENT_COUNT,
                "mappedComponentExporterPredictionMatchCount": exporter_matches,
                "mappedComponentExporterPredictionMismatchCount": (
                    MAPPED_COMPONENT_COUNT - exporter_matches
                ),
                "mappedComponentRetainedPublicMatchCount": public_matches,
                "mappedComponentRetainedPublicMismatchCount": public_mismatches,
                "endpointMappedFieldExporterPredictionMatchCount": sum(
                    field["observations"][-1]["actualMatchesPrediction"] is True
                    for field in field_results
                ),
                "capturedValuesUsedForRuntimeSelection": False,
            },
            "interpretation": {
                "established": (
                    "after the prospective falsification, the corrected hand-decoded "
                    "constructor/getter projection is exact on every reopened mapped "
                    "component; a separate unseen intervention is required for fresh "
                    "prospective authority over the corrected field"
                ),
                "rejected": (
                    "the controlled one-key weighted Parameters candidate is the "
                    "complete source of the retained live public CAFilter state"
                ),
                "nextUnknown": (
                    "capture the actual live ResolvedRecipe Parameters producer inside "
                    "the authenticated public render intervals"
                ),
            },
            "claims": {
                "controlledCandidateExporterTransferEstablished": True,
                "controlledCandidateMatchesCompleteMappedPublicState": False,
                "controlledCandidateRejectedAsCompleteLivePresentationState": True,
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
