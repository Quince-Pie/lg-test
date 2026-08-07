#!/usr/bin/env python3
"""Reject or accept the controlled weighted Parameters value at the live boundary."""

import argparse
import hashlib
import json
import math
import struct
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import capture_designlibrary_parameters_mixer_basis_local_macos_26_6_1 as basis


SCHEMA_VERSION = 1
PROJECTION_SCHEMA_VERSION = 1
CASE_COUNT = 32
PUBLIC_NUMERIC_INPUT_COUNT = 47
WEIGHTED_RESULT_NAME = (
    "designlibrary_material_context_weighted_live_timeline_parameters_"
    "local_macos_26_6_1_result.json"
)
BACKGROUND_FILTER_METADATA_RESULT_NAME = (
    "designlibrary_background_filter_metadata_local_macos_26_6_1_result.json"
)
PUBLIC_PROJECTION_NAME = (
    "designlibrary_material_context_weighted_live_public_projection.json"
)
EXPECTED_WEIGHTED_RESULT_SHA256 = (
    "adbb81b77b6d414e249c2febecf3752b6cb5ca292c5e882956d4d9bd2edecab7"
)
EXPECTED_BACKGROUND_FILTER_METADATA_RESULT_SHA256 = (
    "dc2202be02d3831126866236661173c92bf492498a4cc2d2717931ba296b0757"
)
EXPECTED_PUBLIC_PROJECTION_SHA256 = (
    "d4d8471355e0cbba4578d2b3786951116a372f5fcc94798ed9384687008d4573"
)
EXPECTED_SOURCE_TIMELINE_SHA256 = (
    "0a7db5d9416c4c69f19b608de73e9225e7edf8629e112de2be0d07cab1adc711"
)
SOURCE_TIMELINE_ARTIFACT = "gh-run-31118243811/transition-timeline.json"
EXPECTED_FILTER_ARRAY_GETTER = {
    "byteCount": 2592,
    "directBLCallsites": [],
    "end": "0x240918eac",
    "sha256": "0abc68898237c57aa2c31d54568649f57750241ea6cd4fe9c995d0b9857f826a",
    "start": "0x24091848c",
}
EXPECTED_BACKGROUND_FILTER_CONSTRUCTOR = {
    "byteCount": 1044,
    "directBLCallsites": ["0x240919334"],
    "end": "0x24091c114",
    "sha256": "71a592bc8a187fe8bcca0fa50c3f4d36ea3c2916dbd5d16f3fa1df05b86f131d",
    "start": "0x24091bd00",
}


type JSONObject = dict[str, object]


class AnalysisError(RuntimeError):
    """Raised when retained evidence violates its exact boundary contract."""


class PublicTransform(StrEnum):
    IDENTITY = "identity"
    HALF = "multiply-by-binary64-0.5"
    BLUR_OPACITY_PRODUCT = "binary32-multiply-by-blur-opacity"
    CONSTANT_ZERO = "constant-binary64-positive-zero"


@dataclass(frozen=True, slots=True, kw_only=True)
class PublicScalarMapping:
    parameters_field: str | None
    public_input: str
    transform: PublicTransform = PublicTransform.IDENTITY
    result_field: str | None = None
    storage_format: str | None = None


PUBLIC_SCALAR_MAPPINGS = (
    PublicScalarMapping(
        parameters_field="edgeBleed.amount", public_input="inputBleedAmount"
    ),
    PublicScalarMapping(
        parameters_field="edgeBleed.blurRadius",
        public_input="inputBleedBlurRadius",
    ),
    PublicScalarMapping(
        parameters_field="edgeBleed.ycc.black",
        public_input="inputBleedColorMatrixBlack",
    ),
    PublicScalarMapping(
        parameters_field="edgeBleed.ycc.saturation",
        public_input="inputBleedColorMatrixSaturation",
    ),
    PublicScalarMapping(
        parameters_field="edgeBleed.ycc.white",
        public_input="inputBleedColorMatrixWhite",
    ),
    PublicScalarMapping(
        parameters_field="edgeBleed.distances.0",
        public_input="inputBleedDistance0",
    ),
    PublicScalarMapping(
        parameters_field="edgeBleed.distances.1",
        public_input="inputBleedDistance1",
    ),
    PublicScalarMapping(
        parameters_field="edgeBleed.height", public_input="inputBleedHeight"
    ),
    PublicScalarMapping(
        parameters_field="edgeBleed.opacity", public_input="inputBleedOpacity"
    ),
    PublicScalarMapping(
        parameters_field="blur.distances.0", public_input="inputBlurDistance0"
    ),
    PublicScalarMapping(
        parameters_field="blur.distances.1", public_input="inputBlurDistance1"
    ),
    PublicScalarMapping(
        parameters_field="blur.distances.2", public_input="inputBlurDistance2"
    ),
    PublicScalarMapping(
        parameters_field="blur.distances.3", public_input="inputBlurDistance3"
    ),
    PublicScalarMapping(
        parameters_field=None,
        public_input="inputBlurDistance4",
        transform=PublicTransform.CONSTANT_ZERO,
        result_field="filterArrayGetter.inputBlurDistance4.constantZero",
        storage_format="d",
    ),
    PublicScalarMapping(
        parameters_field="blur.opacities.0",
        public_input="inputBlurOpacity0",
        transform=PublicTransform.BLUR_OPACITY_PRODUCT,
    ),
    PublicScalarMapping(
        parameters_field="blur.opacities.1",
        public_input="inputBlurOpacity1",
        transform=PublicTransform.BLUR_OPACITY_PRODUCT,
    ),
    PublicScalarMapping(
        parameters_field="blur.opacities.2",
        public_input="inputBlurOpacity2",
        transform=PublicTransform.BLUR_OPACITY_PRODUCT,
    ),
    PublicScalarMapping(
        parameters_field="blur.opacities.3",
        public_input="inputBlurOpacity3",
        transform=PublicTransform.BLUR_OPACITY_PRODUCT,
    ),
    PublicScalarMapping(
        parameters_field="blur.opacities.4",
        public_input="inputBlurOpacity4",
        transform=PublicTransform.BLUR_OPACITY_PRODUCT,
    ),
    PublicScalarMapping(
        parameters_field="blur.radius",
        public_input="inputBlurRadius",
        transform=PublicTransform.HALF,
    ),
    PublicScalarMapping(
        parameters_field="faceEffects.ycc.black",
        public_input="inputFaceColorMatrixBlack",
    ),
    PublicScalarMapping(
        parameters_field="faceEffects.ycc.saturation",
        public_input="inputFaceColorMatrixSaturation",
    ),
    PublicScalarMapping(
        parameters_field="faceEffects.ycc.white",
        public_input="inputFaceColorMatrixWhite",
    ),
    PublicScalarMapping(
        parameters_field="faceEffects.opacity", public_input="inputFaceOpacity"
    ),
    PublicScalarMapping(
        parameters_field="refraction.innerAmount",
        public_input="inputInnerRefractionAmount",
    ),
    PublicScalarMapping(
        parameters_field="refraction.innerHeight",
        public_input="inputInnerRefractionHeight",
    ),
    PublicScalarMapping(
        parameters_field="refraction.outerAmount",
        public_input="inputOuterRefractionAmount",
    ),
    PublicScalarMapping(
        parameters_field="refraction.outerHeight",
        public_input="inputOuterRefractionHeight",
    ),
    PublicScalarMapping(
        parameters_field="refraction.outerDistances.0",
        public_input="inputRefractionDistance0",
    ),
    PublicScalarMapping(
        parameters_field="refraction.outerDistances.1",
        public_input="inputRefractionDistance1",
    ),
    PublicScalarMapping(
        parameters_field="refraction.outerOpacity",
        public_input="inputRefractionOpacity",
    ),
    PublicScalarMapping(
        parameters_field="sdrAdjustment.faceDimming.distances.0",
        public_input="inputSDRGradientDistance0",
    ),
    PublicScalarMapping(
        parameters_field="sdrAdjustment.faceDimming.distances.1",
        public_input="inputSDRGradientDistance1",
    ),
    PublicScalarMapping(
        parameters_field="sdrAdjustment.faceDimming.whitePointShift",
        public_input="inputSDRHoldingToneWhite",
    ),
    PublicScalarMapping(
        parameters_field="sdrAdjustment.shadowOpacityShift",
        public_input="inputSDRShadowOpacity",
    ),
    PublicScalarMapping(
        parameters_field="sdrAdjustment.headroomTransitionPoint",
        public_input="inputMaxHeadroom",
    ),
    PublicScalarMapping(
        parameters_field="shadow.amount", public_input="inputShadowAmount"
    ),
    PublicScalarMapping(
        parameters_field="shadow.blurRadius",
        public_input="inputShadowBlurRadius",
    ),
    PublicScalarMapping(
        parameters_field="shadow.ycc.black",
        public_input="inputShadowColorMatrixBlack",
    ),
    PublicScalarMapping(
        parameters_field="shadow.ycc.saturation",
        public_input="inputShadowColorMatrixSaturation",
    ),
    PublicScalarMapping(
        parameters_field="shadow.ycc.white",
        public_input="inputShadowColorMatrixWhite",
    ),
    PublicScalarMapping(
        parameters_field="shadow.inset", public_input="inputShadowDistanceOffset"
    ),
    PublicScalarMapping(
        parameters_field="shadow.height", public_input="inputShadowHeight"
    ),
    PublicScalarMapping(
        parameters_field="shadow.opacity", public_input="inputShadowOpacity"
    ),
    PublicScalarMapping(
        parameters_field="shadow.shadowRadius", public_input="inputShadowRadius"
    ),
    PublicScalarMapping(
        parameters_field="shadow.vibrancyContribution",
        public_input="inputShadowVibrancyContribution",
    ),
)

REQUIRED_COUNTEREXAMPLE_FIELDS = frozenset(
    {
        "shadow.offset.height",
        "filterArrayGetter.inputBlurDistance4.constantZero",
        "blur.opacities.0",
        "blur.opacities.1",
        "edgeBleed.useDarkenBlending",
        "sdrAdjustment.headroomTransitionPoint",
        "sdrAdjustment.faceDimming.whitePointShift",
    }
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def digest_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def object_value(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AnalysisError(label + " is not an object")
    return value


def array_value(value: object, label: str) -> Sequence[object]:
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
    return object_value(value, label)


def field_by_name(name: str):
    matches = [field for field in basis.SCALAR_FIELDS if field.name == name]
    if len(matches) != 1:
        raise AnalysisError("unknown Parameters scalar field " + name)
    return matches[0]


def binary64_bits(value: float) -> str:
    return "0x{0:016x}".format(struct.unpack("<Q", struct.pack("<d", value))[0])


def walk_objects(root: object) -> Iterator[Mapping[str, object]]:
    pending = [root]
    while pending:
        value = pending.pop()
        if isinstance(value, Mapping):
            yield value
            pending.extend(value.values())
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            pending.extend(value)


def extract_public_projection(timeline_path: Path, output_path: Path) -> JSONObject:
    if sha256(timeline_path) != EXPECTED_SOURCE_TIMELINE_SHA256:
        raise AnalysisError("source timeline identity differs")
    timeline = load_json(timeline_path, "source timeline")
    uniforms = object_value(
        timeline.get("dynamicBackgroundUniforms"), "dynamic background uniforms"
    )
    records = array_value(uniforms.get("records"), "dynamic background records")
    if len(records) != CASE_COUNT:
        raise AnalysisError("source timeline record count differs")

    samples: list[JSONObject] = []
    expected_numeric_names: set[str] | None = None
    for expected_index, untyped_record in enumerate(records, start=1):
        record = object_value(untyped_record, "dynamic background record")
        if record.get("sampleIndex") != expected_index:
            raise AnalysisError("source timeline sample order differs")
        values = object_value(
            object_value(record.get("filter"), "public background filter").get(
                "inputValues"
            ),
            "public background filter inputs",
        )
        numeric_inputs = {
            str(name): numeric(value, str(name))
            for name, value in values.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }
        numeric_names = set(numeric_inputs)
        if len(numeric_names) != PUBLIC_NUMERIC_INPUT_COUNT:
            raise AnalysisError("public numeric input count differs")
        if expected_numeric_names is None:
            expected_numeric_names = numeric_names
        elif numeric_names != expected_numeric_names:
            raise AnalysisError("public numeric input names differ between samples")

        offset = object_value(values.get("inputShadowOffset"), "shadow offset")
        offset_hex = offset.get("hex")
        if not isinstance(offset_hex, str) or len(offset_hex) != 32:
            raise AnalysisError("shadow offset raw bytes differ")
        try:
            if len(bytes.fromhex(offset_hex)) != 16:
                raise ValueError
        except ValueError as error:
            raise AnalysisError("shadow offset raw bytes differ") from error

        backdrop_scales = {
            numeric(candidate.get("backdropScale"), "backdrop scale")
            for candidate in walk_objects(record)
            if candidate.get("class") == "CABackdropLayer"
            and candidate.get("backdropScale") is not None
        }
        if len(backdrop_scales) != 1:
            raise AnalysisError("public backdrop scale is not unique")
        darken = values.get("inputBleedDarkenBlend")
        if not isinstance(darken, bool):
            raise AnalysisError("public edge darken value is not Boolean")
        samples.append(
            {
                "sampleIndex": expected_index,
                "fraction": numeric(record.get("remaining"), "remaining fraction"),
                "numericInputs": dict(sorted(numeric_inputs.items())),
                "shadowOffsetRawLittleEndianHex": offset_hex,
                "backdropScale": backdrop_scales.pop(),
                "edgeBleedDarkenBlending": darken,
            }
        )

    projection: JSONObject = {
        "designLibraryMaterialContextWeightedLivePublicProjectionSchemaVersion": (
            PROJECTION_SCHEMA_VERSION
        ),
        "classification": (
            "lossless scalar/discrete projection of the retained public Retina "
            "timeline; no captured value selected a runtime case"
        ),
        "sourceTimeline": {
            "artifact": SOURCE_TIMELINE_ARTIFACT,
            "sha256": EXPECTED_SOURCE_TIMELINE_SHA256,
        },
        "numericInputNames": sorted(expected_numeric_names or ()),
        "samples": samples,
    }
    output_path.write_text(
        json.dumps(projection, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return projection


def validate_weighted_result(
    result: Mapping[str, object],
) -> tuple[Sequence[object], Mapping[str, object]]:
    if (
        result.get(
            "designLibraryMaterialContextWeightedLiveTimelineParametersCaptureSchemaVersion"
        )
        != 1
    ):
        raise AnalysisError("weighted Parameters schema differs")
    claims = object_value(result.get("claims"), "weighted Parameters claims")
    invariants = object_value(
        result.get("measuredInvariants"), "weighted Parameters invariants"
    )
    cases = array_value(result.get("cases"), "weighted Parameters cases")
    unique = object_value(
        result.get("uniqueWeightedNormalizedParameters"),
        "unique weighted Parameters",
    )
    if (
        claims.get("controlledCompleteWeightedParametersCandidateEstablished")
        is not True
        or claims.get("completeLiveParametersTransferEstablished") is not False
        or invariants.get("caseCount") != CASE_COUNT
        or invariants.get("openedPublicPredictionCount") != 128
        or invariants.get("openedPublicPredictionMatchCount") != 128
        or len(cases) != CASE_COUNT
        or len(unique) != 8
    ):
        raise AnalysisError("weighted Parameters authority differs")
    return cases, unique


def weighted_payload(case: Mapping[str, object], unique: Mapping[str, object]) -> bytes:
    digest = case.get("weightedParametersSHA256")
    if not isinstance(digest, str):
        raise AnalysisError("weighted Parameters digest is absent")
    record = object_value(unique.get(digest), "weighted Parameters record")
    encoded = record.get("normalizedHex")
    if not isinstance(encoded, str):
        raise AnalysisError("weighted Parameters payload is absent")
    try:
        payload = bytes.fromhex(encoded)
    except ValueError as error:
        raise AnalysisError("weighted Parameters payload is malformed") from error
    if (
        len(payload) != basis.PARAMETERS_BYTE_COUNT
        or digest_bytes(payload) != digest
        or basis.normalize_parameters(payload) != payload
    ):
        raise AnalysisError("weighted Parameters payload identity differs")
    return payload


def scalar_observation(
    mapping: PublicScalarMapping,
    payload: bytes,
    sample: Mapping[str, object],
) -> JSONObject:
    observed_inputs = object_value(sample.get("numericInputs"), "numeric inputs")
    public_value = numeric(
        observed_inputs.get(mapping.public_input), mapping.public_input
    )

    candidate_raw: bytes | None
    candidate_value: float | None
    if mapping.parameters_field is None:
        if (
            mapping.transform is not PublicTransform.CONSTANT_ZERO
            or mapping.storage_format not in {"f", "d"}
        ):
            raise AnalysisError("constant exporter mapping is malformed")
        storage_format = mapping.storage_format
        candidate_raw = None
        candidate_value = None
        predicted_public_value = 0.0
    else:
        field = field_by_name(mapping.parameters_field)
        if mapping.storage_format is not None:
            raise AnalysisError("Parameters-backed mapping overrides its storage")
        storage_format = field.format
        size = struct.calcsize("<" + storage_format)
        candidate_raw = payload[field.offset : field.offset + size]
        candidate_value = struct.unpack("<" + storage_format, candidate_raw)[0]
        match mapping.transform:
            case PublicTransform.IDENTITY:
                predicted_public_value = candidate_value
            case PublicTransform.HALF:
                predicted_public_value = candidate_value * 0.5
            case PublicTransform.BLUR_OPACITY_PRODUCT:
                opacity_field = field_by_name("blur.opacity")
                opacity_raw = payload[
                    opacity_field.offset : opacity_field.offset
                    + struct.calcsize("<" + opacity_field.format)
                ]
                blur_opacity = struct.unpack(
                    "<" + opacity_field.format, opacity_raw
                )[0]
                predicted_public_value = candidate_value * blur_opacity
            case PublicTransform.CONSTANT_ZERO:
                raise AnalysisError("Parameters-backed mapping cannot be constant")
    predicted_public_raw = struct.pack("<" + storage_format, predicted_public_value)
    predicted_public_value = struct.unpack(
        "<" + storage_format, predicted_public_raw
    )[0]
    public_raw = struct.pack("<" + storage_format, public_value)
    return {
        "sampleIndex": sample["sampleIndex"],
        "candidateValue": candidate_value,
        "predictedPublicValue": predicted_public_value,
        "publicValue": public_value,
        "candidateRawLittleEndianHex": (
            None if candidate_raw is None else candidate_raw.hex()
        ),
        "predictedPublicRawLittleEndianHex": predicted_public_raw.hex(),
        "publicRawLittleEndianHex": public_raw.hex(),
        "matchedBitwise": predicted_public_raw == public_raw,
    }


def summarize_field(
    name: str,
    source_parameters_field: str | None,
    public_input: str,
    storage: str,
    transform: str,
    observations: list[JSONObject],
) -> JSONObject:
    matches = sum(item["matchedBitwise"] is True for item in observations)
    return {
        "parametersField": name,
        "sourceParametersField": source_parameters_field,
        "publicInput": public_input,
        "storage": storage,
        "candidateToPublicTransform": transform,
        "componentCount": len(observations),
        "bitwiseMatchCount": matches,
        "bitwiseMismatchCount": len(observations) - matches,
        "observations": observations,
    }


def analyze(output_path: Path) -> Mapping[str, object]:
    analysis_directory = Path(__file__).resolve().parent
    source_path = Path(__file__).resolve()
    weighted_path = analysis_directory / WEIGHTED_RESULT_NAME
    metadata_path = analysis_directory / BACKGROUND_FILTER_METADATA_RESULT_NAME
    projection_path = analysis_directory / PUBLIC_PROJECTION_NAME
    if sha256(weighted_path) != EXPECTED_WEIGHTED_RESULT_SHA256:
        raise AnalysisError("weighted Parameters result identity differs")
    if sha256(projection_path) != EXPECTED_PUBLIC_PROJECTION_SHA256:
        raise AnalysisError("public projection identity differs")
    if sha256(metadata_path) != EXPECTED_BACKGROUND_FILTER_METADATA_RESULT_SHA256:
        raise AnalysisError("BackgroundFilter metadata identity differs")

    weighted_result = load_json(weighted_path, "weighted Parameters result")
    metadata_result = load_json(metadata_path, "BackgroundFilter metadata result")
    projection = load_json(projection_path, "public timeline projection")
    cases, unique = validate_weighted_result(weighted_result)
    code_regions = object_value(
        metadata_result.get("codeRegions"), "BackgroundFilter code regions"
    )
    if (
        metadata_result.get(
            "designLibraryBackgroundFilterMetadataAnalysisSchemaVersion"
        )
        != 1
        or object_value(
            code_regions.get("backgroundFilterConstructor"),
            "BackgroundFilter constructor",
        )
        != EXPECTED_BACKGROUND_FILTER_CONSTRUCTOR
        or object_value(code_regions.get("filterArrayGetter"), "filter-array getter")
        != EXPECTED_FILTER_ARRAY_GETTER
    ):
        raise AnalysisError("authenticated filter-array getter differs")
    if (
        projection.get(
            "designLibraryMaterialContextWeightedLivePublicProjectionSchemaVersion"
        )
        != PROJECTION_SCHEMA_VERSION
    ):
        raise AnalysisError("public projection schema differs")
    source_timeline = object_value(
        projection.get("sourceTimeline"), "projection source timeline"
    )
    if source_timeline != {
        "artifact": SOURCE_TIMELINE_ARTIFACT,
        "sha256": EXPECTED_SOURCE_TIMELINE_SHA256,
    }:
        raise AnalysisError("projection source timeline identity differs")
    samples = array_value(projection.get("samples"), "public projection samples")
    if len(samples) != CASE_COUNT:
        raise AnalysisError("public projection case count differs")

    typed_cases: list[Mapping[str, object]] = []
    typed_samples: list[Mapping[str, object]] = []
    payloads: list[bytes] = []
    for expected_index, (untyped_case, untyped_sample) in enumerate(
        zip(cases, samples, strict=True), start=1
    ):
        case = object_value(untyped_case, "weighted Parameters case")
        sample = object_value(untyped_sample, "public projection sample")
        if (
            case.get("index") != expected_index
            or case.get("name") != "sample_{0:02d}".format(expected_index)
            or sample.get("sampleIndex") != expected_index
            or binary64_bits(numeric(sample.get("fraction"), "public fraction"))
            != case.get("fractionBits")
        ):
            raise AnalysisError("weighted/public case alignment differs")
        predictions = array_value(
            case.get("openedPublicPredictions"), "opened public predictions"
        )
        if len(predictions) != 4 or not all(
            object_value(item, "opened public prediction").get("matchedBitwise") is True
            for item in predictions
        ):
            raise AnalysisError("frozen four-field public gate differs")
        typed_cases.append(case)
        typed_samples.append(sample)
        payloads.append(weighted_payload(case, unique))

    field_results: list[JSONObject] = []
    for mapping in PUBLIC_SCALAR_MAPPINGS:
        if mapping.parameters_field is None:
            if mapping.result_field is None or mapping.storage_format is None:
                raise AnalysisError("constant exporter mapping lacks identity")
            result_name = mapping.result_field
            storage_format = mapping.storage_format
        else:
            field = field_by_name(mapping.parameters_field)
            result_name = mapping.result_field or mapping.parameters_field
            storage_format = field.format
        observations = [
            scalar_observation(mapping, payload, sample)
            for payload, sample in zip(payloads, typed_samples, strict=True)
        ]
        field_results.append(
            summarize_field(
                result_name,
                mapping.parameters_field,
                mapping.public_input,
                "binary32" if storage_format == "f" else "binary64",
                mapping.transform.value,
                observations,
            )
        )

    for field_name, offset in (
        ("shadow.offset.width", 24),
        ("shadow.offset.height", 32),
    ):
        observations = []
        lane = 0 if offset == 24 else 1
        for payload, sample in zip(payloads, typed_samples, strict=True):
            expected_offset = bytes.fromhex(
                str(sample["shadowOffsetRawLittleEndianHex"])
            )
            candidate_raw = payload[offset : offset + 8]
            public_raw = expected_offset[lane * 8 : lane * 8 + 8]
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
        field_results.append(
            summarize_field(
                field_name,
                field_name,
                "inputShadowOffset." + ("width" if lane == 0 else "height"),
                "binary64",
                "identity",
                observations,
            )
        )

    darken_observations = []
    for payload, sample in zip(payloads, typed_samples, strict=True):
        candidate_byte = payload[497]
        predicted_byte = candidate_byte & 1
        public_value = sample.get("edgeBleedDarkenBlending")
        if not isinstance(public_value, bool):
            raise AnalysisError("projected public darken value differs")
        expected_byte = int(public_value)
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
                "publicRawLittleEndianHex": bytes([expected_byte]).hex(),
                "matchedBitwise": predicted_byte == expected_byte,
            }
        )
    field_results.append(
        summarize_field(
            "edgeBleed.useDarkenBlending",
            "edgeBleed.useDarkenBlending",
            "inputBleedDarkenBlend",
            "Boolean-or-nil byte",
            "Boolean identity",
            darken_observations,
        )
    )

    field_count = len(field_results)
    component_count = sum(int(field["componentCount"]) for field in field_results)
    match_count = sum(int(field["bitwiseMatchCount"]) for field in field_results)
    mismatch_count = component_count - match_count
    exact_fields = [
        str(field["parametersField"])
        for field in field_results
        if field["bitwiseMismatchCount"] == 0
    ]
    rejected_fields = [
        str(field["parametersField"])
        for field in field_results
        if field["bitwiseMismatchCount"] != 0
    ]
    if not REQUIRED_COUNTEREXAMPLE_FIELDS.issubset(rejected_fields):
        raise AnalysisError("required complete-candidate counterexamples differ")
    if mismatch_count == 0:
        raise AnalysisError("controlled candidate unexpectedly matches public state")

    per_case = []
    for sample_index in range(1, CASE_COUNT + 1):
        matches = sum(
            field["observations"][sample_index - 1]["matchedBitwise"] is True
            for field in field_results
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
        "designLibraryMaterialContextWeightedLivePublicBoundaryAnalysisSchemaVersion": (
            SCHEMA_VERSION
        ),
        "classification": (
            "retrospective fail-closed comparison of a prospectively frozen "
            "controlled weighted Parameters candidate with an independently "
            "retained public Retina timeline; no captured value selected runtime "
            "behavior"
        ),
        "inputs": {
            "weightedParametersCandidate": {
                "path": "Analysis/" + weighted_path.name,
                "sha256": sha256(weighted_path),
            },
            "authenticatedBackgroundFilterExporter": {
                "path": "Analysis/" + metadata_path.name,
                "sha256": sha256(metadata_path),
                "constructor": EXPECTED_BACKGROUND_FILTER_CONSTRUCTOR,
                "filterArrayGetter": EXPECTED_FILTER_ARRAY_GETTER,
                "decodedOperationsApplied": {
                    "blurRadius": "binary64 multiply by exact 0.5",
                    "blurTapOpacities": (
                        "binary32 multiply by BackgroundFilter.blur.opacity"
                    ),
                    "inputBlurDistance4": "constant binary64 positive zero",
                    "edgeBleedDarkenBlending": "low bit of optional-Boolean byte",
                    "remainingMappedScalars": "identity",
                },
            },
            "publicTimelineProjection": {
                "path": "Analysis/" + projection_path.name,
                "sha256": sha256(projection_path),
                "sourceTimelineArtifact": SOURCE_TIMELINE_ARTIFACT,
                "sourceTimelineSHA256": EXPECTED_SOURCE_TIMELINE_SHA256,
            },
            "analysisSource": {
                "path": "Analysis/" + source_path.name,
                "sha256": sha256(source_path),
            },
        },
        "mappedFields": field_results,
        "perCase": per_case,
        "measuredInvariants": {
            "caseCount": CASE_COUNT,
            "uniqueControlledWeightedParametersCount": len(unique),
            "frozenOpenedPublicFieldPredictionCount": 128,
            "frozenOpenedPublicFieldPredictionMatchCount": 128,
            "publicNumericInputCount": PUBLIC_NUMERIC_INPUT_COUNT,
            "exporterMappedNumericFieldCount": len(PUBLIC_SCALAR_MAPPINGS),
            "additionalMappedFieldCount": field_count - len(PUBLIC_SCALAR_MAPPINGS),
            "mappedFieldCount": field_count,
            "mappedComponentCount": component_count,
            "mappedComponentBitwiseMatchCount": match_count,
            "mappedComponentBitwiseMismatchCount": mismatch_count,
            "fullyExactMappedFieldCount": len(exact_fields),
            "rejectedMappedFieldCount": len(rejected_fields),
            "fullyExactMappedFields": exact_fields,
            "rejectedMappedFields": rejected_fields,
            "requiredCounterexampleFields": sorted(REQUIRED_COUNTEREXAMPLE_FIELDS),
            "endpointMappedFieldBitwiseMatchCount": per_case[-1]["bitwiseMatchCount"],
            "capturedValuesUsedForRuntimeSelection": False,
        },
        "interpretation": {
            "acceptedBoundary": (
                "the controlled one-key weighted builder exactly reproduces the "
                "four preregistered opened zero-baseline fields"
            ),
            "rejectedBoundary": (
                "the controlled weighted Parameters value is not the complete "
                "live BackgroundFilter source state under the authenticated "
                "constructor and filter-array getter mapping"
            ),
            "nextUnknown": (
                "authenticate the distinct live presentation producer or "
                "interpolation stage that supplies the nonzero-baseline and "
                "discrete fields"
            ),
            "excludedFromScalarProjection": (
                "backdropScale is not exported by this BackgroundFilter getter; "
                "inputClamp and exported CGColor payloads require their already "
                "separate nonlinear/color-space transfer laws. The authenticated "
                "scalar/discrete failures alone reject the complete candidate"
            ),
        },
        "claims": {
            "controlledCompleteWeightedParametersCandidateEstablished": True,
            "allFrozenOpenedZeroBaselinePublicFieldsReplayBitwise": True,
            "controlledCandidateMatchesCompleteMappedPublicState": False,
            "controlledCandidateRejectedAsCompleteLivePresentationState": True,
            "distinctLivePresentationTransformationRequired": True,
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
    parser.add_argument(
        "--extract-timeline",
        type=Path,
        help="authenticate the retained full timeline and refresh its projection",
    )
    arguments = parser.parse_args()
    analysis_directory = Path(__file__).resolve().parent
    try:
        if arguments.extract_timeline is not None:
            extract_public_projection(
                arguments.extract_timeline.resolve(),
                analysis_directory / PUBLIC_PROJECTION_NAME,
            )
        analyze(arguments.output.resolve())
    except AnalysisError as error:
        print("ANALYSIS_ERROR: " + str(error))
        return 1
    print(str(arguments.output.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
