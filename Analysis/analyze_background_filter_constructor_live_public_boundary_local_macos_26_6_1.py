#!/usr/bin/env python3
"""Join captured live Parameters to same-run public CAFilter scalars bitwise."""

import argparse
import hashlib
import json
import math
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path

import analyze_designlibrary_material_context_weighted_live_public_boundary as boundary
import capture_designlibrary_parameters_mixer_basis_local_macos_26_6_1 as basis


SCHEMA_VERSION = 1
CASE_COUNT = 32
PUBLIC_NUMERIC_INPUT_COUNT = 47
EXPECTED_ARTIFACT_DIRECTORY_NAME = (
    "local-background-filter-constructor-public-render-interval-parameters-v1-run1"
)
PREREGISTRATION_NAME = (
    "background_filter_constructor_live_public_boundary_"
    "local_macos_26_6_1_preregistration.json"
)
CONSTRUCTOR_PREREGISTRATION_NAME = (
    "background_filter_constructor_public_render_interval_"
    "local_macos_26_6_1_preregistration.json"
)
EXPECTED_PREREGISTRATION_SHA256 = (
    "f634ac687b0b86f614fef18e6f4929d56cf31cd0b77d5a4b14034a03cb0a6030"
)
EXPECTED_CONSTRUCTOR_PREREGISTRATION_SHA256 = (
    "f4bdc79e079ba516b2e92d9326739fcf4491585d5c0295a273f748804ba60461"
)
EXPECTED_VALIDATOR_SHA256 = (
    "02827c0fc473b762ed6422e895ee7a1d599c0b1609680668e70a3c6a1ceb5a7e"
)
EXPECTED_BOUNDARY_SOURCE_SHA256 = (
    "d9406c8d9390d58ed9c399426b8a1fee1436de49e6198bd9c0b7c5bcddf24e7f"
)
EXPECTED_BOUNDARY_RESULT_SHA256 = (
    "308943d6d5cb16166cd7a1a3f63a824a2b4e47f93bab18e13f7fccac51b94767"
)
EXPECTED_BASIS_SOURCE_SHA256 = (
    "829e758062d1905ed5635b09bf458337bebce3e41f506ec301d80c66112d2442"
)
EXPECTED_CAPTURE_SOURCE_COMMIT = "53686e3e3b80b2654b085628dbbb8c27f1b1cadd"


type JSONObject = dict[str, object]


class AnalysisError(RuntimeError):
    """Raised when the frozen live/public comparison contract differs."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def digest_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def normalized_source_sha256(path: Path) -> str:
    payload = path.read_bytes()
    needle = EXPECTED_PREREGISTRATION_SHA256.encode()
    if payload.count(needle) != 1:
        raise AnalysisError("analysis preregistration hash slot differs")
    return digest_bytes(payload.replace(needle, b"0" * 64))


def mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AnalysisError(label + " is not an object")
    return value


def array(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise AnalysisError(label + " is not an array")
    return value


def numeric(value: object, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise AnalysisError(label + " is not numeric")
    result = float(value)
    if not math.isfinite(result):
        raise AnalysisError(label + " is not finite")
    return result


def load_json(path: Path, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AnalysisError(label + " is unreadable") from error
    return mapping(value, label)


def validate_frozen_inputs(analysis_directory: Path, source_path: Path) -> JSONObject:
    paths = {
        "preregistration": analysis_directory / PREREGISTRATION_NAME,
        "constructorPreregistration": (
            analysis_directory / CONSTRUCTOR_PREREGISTRATION_NAME
        ),
        "constructorValidator": (
            analysis_directory
            / "validate_background_filter_constructor_public_render_interval_"
            "local_macos_26_6_1.py"
        ),
        "authenticatedGetterMappingSource": Path(boundary.__file__).resolve(),
        "authenticatedGetterMappingResult": (
            analysis_directory
            / "designlibrary_material_context_weighted_live_public_boundary_"
            "analysis_result.json"
        ),
        "parametersBasisSource": Path(basis.__file__).resolve(),
    }
    expected = {
        "preregistration": EXPECTED_PREREGISTRATION_SHA256,
        "constructorPreregistration": (EXPECTED_CONSTRUCTOR_PREREGISTRATION_SHA256),
        "constructorValidator": EXPECTED_VALIDATOR_SHA256,
        "authenticatedGetterMappingSource": EXPECTED_BOUNDARY_SOURCE_SHA256,
        "authenticatedGetterMappingResult": EXPECTED_BOUNDARY_RESULT_SHA256,
        "parametersBasisSource": EXPECTED_BASIS_SOURCE_SHA256,
    }
    for name, path in paths.items():
        if not path.is_file() or sha256(path) != expected[name]:
            raise AnalysisError(name + " identity differs")

    preregistration = load_json(paths["preregistration"], "preregistration")
    if (
        preregistration.get(
            "backgroundFilterConstructorLivePublicBoundaryPreregistrationSchemaVersion"
        )
        != 1
        or preregistration.get("artifactDirectoryName")
        != EXPECTED_ARTIFACT_DIRECTORY_NAME
        or preregistration.get("caseCount") != CASE_COUNT
        or preregistration.get("capturedValuesUsedForAnalysisSelection") is not False
    ):
        raise AnalysisError("preregistration contract differs")
    source_identity = mapping(preregistration.get("sourceIdentity"), "source identity")
    if source_identity != {
        "analysisSourceNormalizedSHA256": normalized_source_sha256(source_path),
        "authenticatedGetterMappingResultSHA256": (EXPECTED_BOUNDARY_RESULT_SHA256),
        "authenticatedGetterMappingSourceSHA256": (EXPECTED_BOUNDARY_SOURCE_SHA256),
        "constructorPreregistrationSHA256": (
            EXPECTED_CONSTRUCTOR_PREREGISTRATION_SHA256
        ),
        "constructorValidatorSHA256": EXPECTED_VALIDATOR_SHA256,
        "parametersBasisSourceSHA256": EXPECTED_BASIS_SOURCE_SHA256,
    }:
        raise AnalysisError("preregistered source identity differs")
    return {
        name: {
            "path": "Analysis/" + path.name,
            "sha256": sha256(path),
        }
        for name, path in paths.items()
    }


def validate_artifact(
    artifact_directory: Path,
) -> tuple[
    Mapping[str, object],
    Mapping[str, object],
    Mapping[str, object],
    JSONObject,
]:
    if artifact_directory.name != EXPECTED_ARTIFACT_DIRECTORY_NAME:
        raise AnalysisError("artifact directory identity differs")
    validation_path = artifact_directory / "validation.json"
    trace_path = (
        artifact_directory
        / "background-filter-constructor-public-render-interval-trace.json"
    )
    timeline_path = artifact_directory / "transition-timeline.json"
    validation = load_json(validation_path, "constructor validation")
    trace = load_json(trace_path, "constructor trace")
    timeline = load_json(timeline_path, "same-run public timeline")
    inputs = mapping(validation.get("inputs"), "validation inputs")
    validation_preregistration = mapping(
        inputs.get("preregistration"), "validation preregistration"
    )
    trace_identity = mapping(inputs.get("constructorTrace"), "trace identity")
    timeline_identity = mapping(inputs.get("publicTimeline"), "timeline identity")
    authority = mapping(validation.get("authority"), "validation authority")
    if (
        validation.get(
            "backgroundFilterConstructorPublicRenderIntervalLocalMacOSValidationSchemaVersion"
        )
        != 2
        or validation.get("captureContractPassed") is not True
        or inputs.get("sourceCommit") != EXPECTED_CAPTURE_SOURCE_COMMIT
        or validation_preregistration.get("sha256")
        != EXPECTED_CONSTRUCTOR_PREREGISTRATION_SHA256
        or trace_identity.get("sha256") != sha256(trace_path)
        or timeline_identity.get("sha256") != sha256(timeline_path)
        or authority.get("sameProfilePublicParametersConstructionJoinEstablished")
        is not True
        or authority.get("sameProfilePublicParametersBlendProvenanceEstablished")
        is not True
        or authority.get("allInitializedBackgroundFilterProviderBytesJoinedBitwise")
        is not True
    ):
        raise AnalysisError("validated constructor artifact differs")
    identities: JSONObject = {
        "validation": {
            "path": str(validation_path),
            "sha256": sha256(validation_path),
        },
        "constructorTrace": {
            "path": str(trace_path),
            "sha256": sha256(trace_path),
        },
        "sameRunPublicTimeline": {
            "path": str(timeline_path),
            "sha256": sha256(timeline_path),
        },
    }
    return validation, trace, timeline, identities


def live_parameters(
    validation: Mapping[str, object],
    trace: Mapping[str, object],
) -> tuple[list[bytes], list[JSONObject]]:
    constructor_join = mapping(
        validation.get("constructorProviderJoin"), "constructor/provider join"
    )
    joins = [
        mapping(item, "constructor/provider sample join")
        for item in array(constructor_join.get("joins"), "sample joins")
    ]
    builder_calls = [
        mapping(item, "Parameters builder call")
        for item in array(trace.get("parametersBuilderCalls"), "builder calls")
    ]
    if len(joins) != CASE_COUNT or [join.get("sampleIndex") for join in joins] != list(
        range(1, CASE_COUNT + 1)
    ):
        raise AnalysisError("validated sample join topology differs")

    payloads: list[bytes] = []
    records: list[JSONObject] = []
    for expected_sample, join in enumerate(joins, start=1):
        indices = array(
            join.get("parametersBuilderCallIndices"), "builder call indices"
        )
        candidates: set[bytes] = set()
        for value in indices:
            if not isinstance(value, int) or not 0 <= value < len(builder_calls):
                raise AnalysisError("builder call index differs")
            call = builder_calls[value]
            snapshot = mapping(
                call.get("outputParametersAtReturn"), "builder output Parameters"
            )
            encoded = snapshot.get("hex")
            if call.get("assignedSampleIndex") != expected_sample or not isinstance(
                encoded, str
            ):
                raise AnalysisError("builder output sample assignment differs")
            try:
                payload = bytes.fromhex(encoded)
            except ValueError as error:
                raise AnalysisError("builder output Parameters is malformed") from error
            if len(payload) != basis.PARAMETERS_BYTE_COUNT:
                raise AnalysisError("builder output Parameters size differs")
            candidates.add(payload)
        if len(candidates) != 1:
            raise AnalysisError("sample has non-unique joined Parameters")
        payload = candidates.pop()
        if digest_bytes(payload) != join.get("parametersSHA256"):
            raise AnalysisError("joined Parameters identity differs")
        normalized = basis.normalize_parameters(payload)
        payloads.append(payload)
        records.append(
            {
                "sampleIndex": expected_sample,
                "parametersBuilderCallIndices": list(indices),
                "rawParametersSHA256": digest_bytes(payload),
                "normalizedParametersSHA256": digest_bytes(normalized),
                "rawParametersHex": payload.hex(),
                "normalizedParametersHex": normalized.hex(),
            }
        )
    return payloads, records


def same_run_public_samples(timeline: Mapping[str, object]) -> list[JSONObject]:
    uniforms = mapping(
        timeline.get("dynamicBackgroundUniforms"), "dynamic background uniforms"
    )
    records = array(uniforms.get("records"), "dynamic background records")
    if len(records) != CASE_COUNT:
        raise AnalysisError("same-run public record count differs")
    samples: list[JSONObject] = []
    expected_names: set[str] | None = None
    for expected_index, untyped_record in enumerate(records, start=1):
        record = mapping(untyped_record, "dynamic background record")
        values = mapping(
            mapping(record.get("filter"), "public background filter").get(
                "inputValues"
            ),
            "public background filter inputs",
        )
        numeric_inputs = {
            str(name): numeric(value, str(name))
            for name, value in values.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }
        names = set(numeric_inputs)
        if (
            record.get("sampleIndex") != expected_index
            or len(names) != PUBLIC_NUMERIC_INPUT_COUNT
        ):
            raise AnalysisError("same-run public sample identity differs")
        if expected_names is None:
            expected_names = names
        elif names != expected_names:
            raise AnalysisError("same-run public numeric domain differs")
        offset = mapping(values.get("inputShadowOffset"), "public shadow offset")
        offset_hex = offset.get("hex")
        if not isinstance(offset_hex, str):
            raise AnalysisError("public shadow offset bytes are absent")
        try:
            offset_raw = bytes.fromhex(offset_hex)
        except ValueError as error:
            raise AnalysisError("public shadow offset bytes are malformed") from error
        if len(offset_raw) != 16:
            raise AnalysisError("public shadow offset width differs")
        darken = values.get("inputBleedDarkenBlend")
        if not isinstance(darken, bool):
            raise AnalysisError("public darken value differs")
        samples.append(
            {
                "sampleIndex": expected_index,
                "numericInputs": dict(sorted(numeric_inputs.items())),
                "shadowOffsetRawLittleEndianHex": offset_hex,
                "edgeBleedDarkenBlending": darken,
            }
        )
    return samples


def mapped_field_results(
    payloads: Sequence[bytes],
    samples: Sequence[Mapping[str, object]],
) -> list[JSONObject]:
    results: list[JSONObject] = []
    for scalar in boundary.PUBLIC_SCALAR_MAPPINGS:
        if scalar.parameters_field is None:
            if scalar.result_field is None or scalar.storage_format is None:
                raise AnalysisError("constant scalar mapping differs")
            name = scalar.result_field
            storage_format = scalar.storage_format
        else:
            field = boundary.field_by_name(scalar.parameters_field)
            name = scalar.result_field or scalar.parameters_field
            storage_format = field.format
        observations = [
            boundary.scalar_observation(scalar, payload, sample)
            for payload, sample in zip(payloads, samples, strict=True)
        ]
        results.append(
            boundary.summarize_field(
                name,
                scalar.parameters_field,
                scalar.public_input,
                "binary32" if storage_format == "f" else "binary64",
                scalar.transform.value,
                observations,
            )
        )

    for field_name, offset in (
        ("shadow.offset.width", 24),
        ("shadow.offset.height", 32),
    ):
        lane = 0 if offset == 24 else 1
        observations: list[JSONObject] = []
        for payload, sample in zip(payloads, samples, strict=True):
            public_offset = bytes.fromhex(str(sample["shadowOffsetRawLittleEndianHex"]))
            candidate_raw = payload[offset : offset + 8]
            public_raw = public_offset[lane * 8 : lane * 8 + 8]
            observations.append(
                {
                    "sampleIndex": sample["sampleIndex"],
                    "candidateValue": struct.unpack("<d", candidate_raw)[0],
                    "predictedPublicValue": struct.unpack("<d", candidate_raw)[0],
                    "publicValue": struct.unpack("<d", public_raw)[0],
                    "candidateRawLittleEndianHex": candidate_raw.hex(),
                    "predictedPublicRawLittleEndianHex": candidate_raw.hex(),
                    "publicRawLittleEndianHex": public_raw.hex(),
                    "matchedBitwise": candidate_raw == public_raw,
                }
            )
        results.append(
            boundary.summarize_field(
                field_name,
                field_name,
                "inputShadowOffset." + ("width" if lane == 0 else "height"),
                "binary64",
                "identity",
                observations,
            )
        )

    darken_observations: list[JSONObject] = []
    for payload, sample in zip(payloads, samples, strict=True):
        candidate_byte = payload[497]
        predicted_byte = candidate_byte & 1
        public_value = sample["edgeBleedDarkenBlending"]
        public_byte = int(bool(public_value))
        darken_observations.append(
            {
                "sampleIndex": sample["sampleIndex"],
                "candidateValue": (
                    "false"
                    if candidate_byte == 0
                    else "true"
                    if candidate_byte == 1
                    else "nil"
                    if candidate_byte == 2
                    else "invalid"
                ),
                "predictedPublicValue": predicted_byte == 1,
                "publicValue": public_value,
                "candidateRawLittleEndianHex": bytes([candidate_byte]).hex(),
                "predictedPublicRawLittleEndianHex": bytes([predicted_byte]).hex(),
                "publicRawLittleEndianHex": bytes([public_byte]).hex(),
                "matchedBitwise": predicted_byte == public_byte,
            }
        )
    results.append(
        boundary.summarize_field(
            "edgeBleed.useDarkenBlending",
            "edgeBleed.useDarkenBlending",
            "inputBleedDarkenBlend",
            "Boolean-or-nil byte",
            "Boolean identity",
            darken_observations,
        )
    )
    return results


def analyze(artifact_directory: Path, output_path: Path) -> Mapping[str, object]:
    analysis_directory = Path(__file__).resolve().parent
    source_path = Path(__file__).resolve()
    frozen_inputs = validate_frozen_inputs(analysis_directory, source_path)
    validation, trace, timeline, artifact_inputs = validate_artifact(
        artifact_directory.resolve()
    )
    payloads, parameter_records = live_parameters(validation, trace)
    samples = same_run_public_samples(timeline)
    fields = mapped_field_results(payloads, samples)
    field_count = len(fields)
    component_count = sum(int(field["componentCount"]) for field in fields)
    match_count = sum(int(field["bitwiseMatchCount"]) for field in fields)
    mismatch_count = component_count - match_count
    exact_fields = [
        str(field["parametersField"])
        for field in fields
        if field["bitwiseMismatchCount"] == 0
    ]
    rejected_fields = [
        str(field["parametersField"])
        for field in fields
        if field["bitwiseMismatchCount"] != 0
    ]
    per_case: list[JSONObject] = []
    for sample_index in range(1, CASE_COUNT + 1):
        matches = sum(
            field["observations"][sample_index - 1]["matchedBitwise"] is True
            for field in fields
        )
        per_case.append(
            {
                "sampleIndex": sample_index,
                "mappedFieldCount": field_count,
                "bitwiseMatchCount": matches,
                "bitwiseMismatchCount": field_count - matches,
            }
        )

    result: JSONObject = {
        "backgroundFilterConstructorLivePublicBoundaryAnalysisSchemaVersion": (
            SCHEMA_VERSION
        ),
        "classification": (
            "prospectively frozen value-blind bitwise comparison of all 32 "
            "structurally joined live Parameters builder outputs with the same-run "
            "public CAFilter scalar/discrete state through the independently "
            "authenticated Apple getter mapping"
        ),
        "inputs": frozen_inputs
        | artifact_inputs
        | {
            "analysisSource": {
                "path": "Analysis/" + source_path.name,
                "sha256": sha256(source_path),
            }
        },
        "liveParameters": parameter_records,
        "mappedFields": fields,
        "perCase": per_case,
        "measuredInvariants": {
            "caseCount": CASE_COUNT,
            "structurallyJoinedLiveParametersCount": len(payloads),
            "sameRunPublicSampleCount": len(samples),
            "mappedFieldCount": field_count,
            "mappedComponentCount": component_count,
            "mappedComponentBitwiseMatchCount": match_count,
            "mappedComponentBitwiseMismatchCount": mismatch_count,
            "fullyExactMappedFieldCount": len(exact_fields),
            "rejectedMappedFieldCount": len(rejected_fields),
            "fullyExactMappedFields": exact_fields,
            "rejectedMappedFields": rejected_fields,
            "capturedValuesUsedForAnalysisSelection": False,
        },
        "interpretation": {
            "acceptedBoundary": (
                "the validated capture directly observes every complete live "
                "Parameters value joined to the same-sample constructor/provider"
            ),
            "mappedTransfer": (
                "all 49 frozen scalar/discrete getter mappings match same-run public "
                "state bitwise"
                if mismatch_count == 0
                else "at least one frozen getter mapping differs from same-run public "
                "state, proving a distinct post-builder construction or mutation stage"
            ),
            "excludedBoundary": (
                "CGColor transfer, inputClamp, crop/allocation, physical compositor "
                "color, and final Walle pixels remain separate gates"
            ),
        },
        "claims": {
            "actualLiveCallbackCompleteParametersObserved": True,
            "sameRunPublicScalarDiscreteStateObserved": True,
            "allMappedScalarDiscreteGetterFieldsTransferBitwise": (mismatch_count == 0),
            "distinctPostBuilderPublicConstructionStageRequired": (mismatch_count != 0),
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
    parser.add_argument("artifact_directory", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    try:
        analyze(arguments.artifact_directory, arguments.output.resolve())
    except AnalysisError as error:
        print("ANALYSIS_ERROR: " + str(error))
        return 1
    print(str(arguments.output.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
