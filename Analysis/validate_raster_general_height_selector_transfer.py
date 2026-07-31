#!/usr/bin/env python3
"""Validate fresh-input transfer of recovered general-height selectors."""

import argparse
import functools
import hashlib
import json
import struct
import zlib
from collections import Counter
from pathlib import Path
from typing import Any

import model_raster_general_height_arithmetic as two_stage
import recover_raster_general_height_reciprocals as recovery
import validate_raster_general_height_factorization as factorization
import validate_raster_quotient_fine_mantissa as fine_mantissa


type JsonObject = dict[str, Any]

SCHEMA_VERSION = 7
RIG_VERSION = "metal-raster-general-height-selector-transfer-7.0.0"
ROLE = "prospective-unique-selector-transfer-with-ambiguous-selector-discovery"
TARGET_WIDTH = 64
TARGET_HEIGHT = 256
VIEWPORT_WIDTH = 32_768
ORIGIN_Y = 11
HEIGHTS = (47, 61, 79, 113)
SAMPLE_XS = (0, 15, 31)
SAMPLE_POSITION_COUNT = len(SAMPLE_XS)
WITNESS_SIGNIFICANDS = (
    0xE2_B8_4A,
    0x88_E3_E7,
    0x89_14_5A,
    0x90_73_83,
    0x97_D2_AC,
    0xA9_75_16,
    0xB0_D4_3F,
    0xB8_33_68,
    0xC9_D5_D2,
    0xCC_2B_94,
    0xD8_94_24,
    0xE5_2D_27,
    0xEC_8C_50,
    0xFE_2E_BA,
)
WITNESS_COUNT = len(WITNESS_SIGNIFICANDS)
WIDTHS = tuple(range(8_192, 16_384))
WIDTH_COUNT = len(WIDTHS)
HEIGHT_COUNT = len(HEIGHTS)
CASE_COUNT = WIDTH_COUNT * HEIGHT_COUNT
COEFFICIENT_COUNT = CASE_COUNT * WITNESS_COUNT
CANDIDATE_RADIUS_FLOAT_ULPS = 8
RECORD = struct.Struct("<2I")
RAW_BYTES = COEFFICIENT_COUNT * SAMPLE_POSITION_COUNT * RECORD.size
SENTINEL = (0xFFFF_FFFF, 0xFFFF_FFFF)
MASK_PATH = Path(__file__).with_name(
    "raster_general_height_reciprocal_candidate_masks.zlib"
)
MASK_RAW_BYTES = 262_144
MASK_RAW_SHA256 = "fde68ee1cc04fb5fbba75d04b72abb6e74954c66405de174bca0202b12169ce9"
MASK_COMPRESSED_BYTES = 4_635
MASK_COMPRESSED_SHA256 = (
    "0257dd6718ddabd584952fcb86949c3c0b657186a03405c1b653e4f4cddf425f"
)
PREREGISTRATION_PATH = Path(__file__).with_name(
    "raster_general_height_selector_transfer_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "1bdd548c3ecac3fd5f7ed1dd18d8075e88bd18f7870da385830c67f852530ab6"
)
WITNESS_SIGNIFICANDS_SHA256 = (
    "c6aa0a1d8d751850a0b81ec7bc447d00abb144b4a40dc86019c7eecd348b1dbd"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def uint32_sha256(values: list[int] | tuple[int, ...]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(struct.pack("<I", value))
    return digest.hexdigest()


@functools.cache
def load_candidate_masks() -> bytes:
    compressed = MASK_PATH.read_bytes()
    if (
        len(compressed) != MASK_COMPRESSED_BYTES
        or sha256_bytes(compressed) != MASK_COMPRESSED_SHA256
    ):
        raise ValueError("compressed selector candidate masks differ")
    masks = zlib.decompress(compressed)
    if len(masks) != MASK_RAW_BYTES or sha256_bytes(masks) != MASK_RAW_SHA256:
        raise ValueError("selector candidate masks differ")
    return masks


def candidate_reciprocals(
    masks: bytes,
    *,
    case_index: int,
    determinant: int,
) -> tuple[int, ...]:
    (mask,) = recovery.MASK.unpack_from(
        masks,
        case_index * recovery.MASK.size,
    )
    nearest = factorization.top_left.arithmetic.nearest_even_reciprocal_index(
        determinant
    )
    return tuple(
        nearest + offset
        for offset in range(-recovery.CANDIDATE_RADIUS, recovery.CANDIDATE_RADIUS + 1)
        if mask & (1 << (offset + recovery.CANDIDATE_RADIUS))
    )


def scaled_delta_bits(width_index: int, significand: int) -> int:
    shift = 0x0100_0000 if width_index == 0 else 0x0080_0000
    return (0x3F00_0000 | (significand & 0x7F_FFFF)) - shift


def sample_position(width: int, height: int, sample_index: int) -> JsonObject:
    if sample_index not in range(SAMPLE_POSITION_COUNT):
        raise ValueError("selector-transfer sample index differs")
    x = SAMPLE_XS[sample_index]
    signed_interior = width * (2 * height - 1) - height * (2 * x + 1)
    if (
        not 0 <= x < TARGET_WIDTH
        or ORIGIN_Y + height > TARGET_HEIGHT
        or width > VIEWPORT_WIDTH
        or signed_interior <= 1_024
    ):
        raise ValueError("selector-transfer sample is not safely interior")
    return {
        "x": x,
        "y": ORIGIN_Y,
        "tileLocalX": x,
        "signedInteriorArea": signed_interior,
    }


@functools.cache
def predicted_layout() -> JsonObject:
    prior_significands = (
        set(factorization.generate_significands())
        | set(fine_mantissa.generate_significands())
        | set(factorization.top_left.arithmetic.WITNESS_SIGNIFICANDS)
    )
    if not set(WITNESS_SIGNIFICANDS).isdisjoint(prior_significands):
        raise ValueError("selector-transfer witnesses overlap prior input banks")
    masks = load_candidate_masks()
    candidate_set_digest = hashlib.sha256()
    selector_signature_digest = hashlib.sha256()
    unique_prediction_digest = hashlib.sha256()
    width_delta_digest = hashlib.sha256()
    case_delta_digest = hashlib.sha256()
    candidate_slope_multiplicity: Counter[int] = Counter()
    candidate_path_direct_offsets: Counter[int] = Counter()
    unique_determinant_count = 0
    ambiguous_determinant_count = 0
    unique_prediction_count = 0
    ambiguous_prediction_count = 0
    ambiguous_distinguished_count = 0

    for width_index, width in enumerate(WIDTHS):
        for significand in WITNESS_SIGNIFICANDS:
            width_delta_digest.update(
                struct.pack("<I", scaled_delta_bits(width_index, significand))
            )
        for height_index, height in enumerate(HEIGHTS):
            case_index = width_index * HEIGHT_COUNT + height_index
            determinant = width * height
            reciprocals = candidate_reciprocals(
                masks,
                case_index=case_index,
                determinant=determinant,
            )
            selector_signature_digest.update(struct.pack("<I", len(reciprocals)))
            selector_distinguished = False
            if len(reciprocals) == 1:
                unique_determinant_count += 1
            else:
                ambiguous_determinant_count += 1
            for significand in WITNESS_SIGNIFICANDS:
                case_delta_digest.update(
                    struct.pack("<I", scaled_delta_bits(width_index, significand))
                )
            for reciprocal in reciprocals:
                selector_signature_digest.update(struct.pack("<I", reciprocal))
            for significand in WITNESS_SIGNIFICANDS:
                delta_bits = scaled_delta_bits(width_index, significand)
                direct = factorization.top_left.arithmetic.float32_bits(
                    factorization.top_left.arithmetic.float32_value(delta_bits)
                    / width
                )
                candidate_slopes = tuple(
                    two_stage.slope_bits(
                        delta_bits,
                        opposite_edge=height,
                        determinant=determinant,
                        reciprocal_index=reciprocal,
                        first_stage_bias_units=(
                            two_stage.FIRST_STAGE_BIAS_UNITS[0]
                        ),
                    )
                    for reciprocal in reciprocals
                )
                if any(
                    two_stage.slope_bits(
                        delta_bits,
                        opposite_edge=height,
                        determinant=determinant,
                        reciprocal_index=reciprocal,
                        first_stage_bias_units=(
                            two_stage.FIRST_STAGE_BIAS_UNITS[1]
                        ),
                    )
                    != slope_bits
                    for reciprocal, slope_bits in zip(
                        reciprocals,
                        candidate_slopes,
                        strict=True,
                    )
                ):
                    raise ValueError("integer-edge bias equivalence differs")
                distinct_slopes = tuple(sorted(set(candidate_slopes)))
                candidate_slope_multiplicity[len(distinct_slopes)] += 1
                selector_distinguished |= len(distinct_slopes) == len(reciprocals)
                candidate_set_digest.update(struct.pack("<I", len(distinct_slopes)))
                for slope_bits in distinct_slopes:
                    candidate_set_digest.update(struct.pack("<I", slope_bits))
                for reciprocal, slope_bits in zip(
                    reciprocals,
                    candidate_slopes,
                    strict=True,
                ):
                    selector_signature_digest.update(struct.pack("<I", slope_bits))
                    candidate_path_direct_offsets[slope_bits - direct] += 1
                if len(reciprocals) == 1:
                    unique_prediction_digest.update(
                        struct.pack("<I", candidate_slopes[0])
                    )
                    unique_prediction_count += 1
                else:
                    ambiguous_prediction_count += 1
            ambiguous_distinguished_count += (
                len(reciprocals) > 1 and selector_distinguished
            )

    case_words = [
        value
        for width in WIDTHS
        for height in HEIGHTS
        for value in (width, height, width * height)
    ]
    return {
        "widthCount": WIDTH_COUNT,
        "heightCount": HEIGHT_COUNT,
        "caseCount": CASE_COUNT,
        "witnessCount": WITNESS_COUNT,
        "coefficientCount": COEFFICIENT_COUNT,
        "samplePositionCount": SAMPLE_POSITION_COUNT,
        "recordCount": COEFFICIENT_COUNT * SAMPLE_POSITION_COUNT,
        "rawBytes": RAW_BYTES,
        "widthsSha256": uint32_sha256(WIDTHS),
        "caseWordsSha256": uint32_sha256(case_words),
        "sampleXsSha256": uint32_sha256(SAMPLE_XS),
        "witnessSignificandsSha256": uint32_sha256(WITNESS_SIGNIFICANDS),
        "widthDeltaBitsSha256": width_delta_digest.hexdigest(),
        "caseDeltaBitsSha256": case_delta_digest.hexdigest(),
        "candidateSlopeSetSha256": candidate_set_digest.hexdigest(),
        "selectorSignatureSha256": selector_signature_digest.hexdigest(),
        "uniquePredictionSha256": unique_prediction_digest.hexdigest(),
        "uniqueDeterminantCount": unique_determinant_count,
        "ambiguousDeterminantCount": ambiguous_determinant_count,
        "uniquePredictionCount": unique_prediction_count,
        "ambiguousPredictionCount": ambiguous_prediction_count,
        "candidateSlopeMultiplicity": {
            str(key): value
            for key, value in sorted(candidate_slope_multiplicity.items())
        },
        "candidatePathDirectOffsetDistribution": {
            str(key): value
            for key, value in sorted(candidate_path_direct_offsets.items())
        },
        "ambiguousDeterminantsDistinguishedByWitnessSet": (
            ambiguous_distinguished_count
        ),
    }


def load_preregistration() -> JsonObject:
    preregistration: JsonObject = json.loads(
        PREREGISTRATION_PATH.read_text(encoding="utf-8")
    )
    if (
        sha256_path(PREREGISTRATION_PATH) != PREREGISTRATION_SHA256
        or preregistration.get("schemaVersion") != 1
        or preregistration.get("role") != ROLE
        or preregistration.get("observedAtPreregistration") is not False
        or preregistration.get("frozenLayout") != predicted_layout()
    ):
        raise ValueError("selector-transfer preregistration differs")
    return preregistration


def validate_manifest(root: Path) -> tuple[JsonObject, Path]:
    manifest: JsonObject = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    evidence = manifest.get("rasterGeneralHeightSelectorTransfer", {})
    path = root / str(evidence.get("file", ""))
    layout = predicted_layout()
    if (
        manifest.get("schemaVersion") != SCHEMA_VERSION
        or manifest.get("rigVersion") != RIG_VERSION
        or not isinstance(manifest.get("ciCommit"), str)
        or len(str(manifest.get("ciCommit"))) != 40
        or evidence.get("role") != ROLE
        or evidence.get("preregistrationFile")
        != "Analysis/raster_general_height_selector_transfer_preregistration.json"
        or evidence.get("preregistrationSha256") != PREREGISTRATION_SHA256
        or evidence.get("layout") != layout
        or evidence.get("targetWidth") != TARGET_WIDTH
        or evidence.get("targetHeight") != TARGET_HEIGHT
        or evidence.get("viewportWidth") != VIEWPORT_WIDTH
        or evidence.get("originY") != ORIGIN_Y
        or evidence.get("heights") != list(HEIGHTS)
        or evidence.get("sampleXs") != list(SAMPLE_XS)
        or evidence.get("witnessSignificands") != list(WITNESS_SIGNIFICANDS)
        or evidence.get("candidateMaskRawSha256") != MASK_RAW_SHA256
        or evidence.get("recordBytes") != RECORD.size
        or evidence.get("bytes") != RAW_BYTES
        or not path.is_file()
        or path.stat().st_size != RAW_BYTES
        or evidence.get("sha256") != sha256_path(path)
    ):
        raise ValueError("selector-transfer manifest differs")
    return manifest, path


def finite_float_bits(bits: int) -> bool:
    return bits & 0x7F80_0000 != 0x7F80_0000


def recover_slope(
    data: bytes,
    *,
    coefficient_index: int,
    direct_bits: int,
) -> tuple[int, tuple[int, ...]]:
    records = [
        RECORD.unpack_from(
            data,
            (coefficient_index * SAMPLE_POSITION_COUNT + sample_index)
            * RECORD.size,
        )
        for sample_index in range(SAMPLE_POSITION_COUNT)
    ]
    if any(
        record == SENTINEL
        or not all(finite_float_bits(component) for component in record)
        for record in records
    ):
        raise ValueError("selector-transfer capture has missing records")
    observations = tuple(component for record in records for component in record)
    positions = tuple(
        position
        for x in SAMPLE_XS
        for position in (float(x), float(x) + 0.9375)
    )
    constant = factorization.top_left.arithmetic.float32_value(observations[0])
    accepted = tuple(
        direct_bits + offset
        for offset in range(
            -CANDIDATE_RADIUS_FLOAT_ULPS,
            CANDIDATE_RADIUS_FLOAT_ULPS + 1,
        )
        if all(
            factorization.top_left.arithmetic.float32_bits(
                position
                * factorization.top_left.arithmetic.float32_value(
                    direct_bits + offset
                )
                + constant
            )
            == observation
            for position, observation in zip(positions, observations, strict=True)
        )
    )
    return (accepted[0] if len(accepted) == 1 else 0xFFFF_FFFF), accepted


def counter_json(counter: Counter[int | str]) -> JsonObject:
    return {
        str(key): value
        for key, value in sorted(counter.items(), key=lambda item: str(item[0]))
    }


def validate(root: Path) -> JsonObject:
    load_preregistration()
    manifest, raw_path = validate_manifest(root)
    data = raw_path.read_bytes()
    masks = load_candidate_masks()
    recovered_digest = hashlib.sha256()
    resolved_selector_digest = hashlib.sha256()
    slope_multiplicity: Counter[int] = Counter()
    selector_multiplicity: Counter[int] = Counter()
    selector_offsets: Counter[int] = Counter()
    first_failures: list[JsonObject] = []
    unique_prediction_match_count = 0
    unique_prediction_count = 0
    ambiguous_resolved_count = 0

    for width_index, width in enumerate(WIDTHS):
        for height_index, height in enumerate(HEIGHTS):
            case_index = width_index * HEIGHT_COUNT + height_index
            determinant = width * height
            reciprocals = candidate_reciprocals(
                masks,
                case_index=case_index,
                determinant=determinant,
            )
            recovered: list[int] = []
            for witness_index, significand in enumerate(WITNESS_SIGNIFICANDS):
                coefficient_index = case_index * WITNESS_COUNT + witness_index
                delta_bits = scaled_delta_bits(width_index, significand)
                direct_bits = factorization.top_left.arithmetic.float32_bits(
                    factorization.top_left.arithmetic.float32_value(delta_bits)
                    / width
                )
                slope_bits, accepted = recover_slope(
                    data,
                    coefficient_index=coefficient_index,
                    direct_bits=direct_bits,
                )
                slope_multiplicity[len(accepted)] += 1
                recovered.append(slope_bits)
                recovered_digest.update(struct.pack("<I", slope_bits))
                if len(accepted) != 1 and len(first_failures) < 32:
                    first_failures.append(
                        {
                            "width": width,
                            "height": height,
                            "witnessIndex": witness_index,
                            "reason": "slope is not unique",
                            "acceptedOffsets": [
                                value - direct_bits for value in accepted
                            ],
                        }
                    )
            accepted_reciprocals = tuple(
                reciprocal
                for reciprocal in reciprocals
                if all(
                    two_stage.slope_bits(
                        scaled_delta_bits(width_index, significand),
                        opposite_edge=height,
                        determinant=determinant,
                        reciprocal_index=reciprocal,
                        first_stage_bias_units=(
                            two_stage.FIRST_STAGE_BIAS_UNITS[0]
                        ),
                    )
                    == actual
                    for significand, actual in zip(
                        WITNESS_SIGNIFICANDS,
                        recovered,
                        strict=True,
                    )
                )
            )
            selector_multiplicity[len(accepted_reciprocals)] += 1
            resolved = (
                accepted_reciprocals[0]
                if len(accepted_reciprocals) == 1
                else recovery.AMBIGUOUS_SELECTOR
            )
            resolved_selector_digest.update(struct.pack("<I", resolved))
            nearest = factorization.top_left.arithmetic.nearest_even_reciprocal_index(
                determinant
            )
            if len(accepted_reciprocals) == 1:
                selector_offsets[resolved - nearest] += 1
            if len(reciprocals) == 1:
                for witness_index, significand in enumerate(WITNESS_SIGNIFICANDS):
                    predicted = two_stage.slope_bits(
                        scaled_delta_bits(width_index, significand),
                        opposite_edge=height,
                        determinant=determinant,
                        reciprocal_index=reciprocals[0],
                        first_stage_bias_units=(
                            two_stage.FIRST_STAGE_BIAS_UNITS[0]
                        ),
                    )
                    unique_prediction_count += 1
                    unique_prediction_match_count += (
                        recovered[witness_index] == predicted
                    )
            else:
                ambiguous_resolved_count += len(accepted_reciprocals) == 1
            if len(accepted_reciprocals) != 1 and len(first_failures) < 32:
                first_failures.append(
                    {
                        "width": width,
                        "height": height,
                        "reason": "reciprocal selector is not unique",
                        "frozenCandidateOffsets": [
                            value - nearest for value in reciprocals
                        ],
                        "acceptedCandidateOffsets": [
                            value - nearest for value in accepted_reciprocals
                        ],
                    }
                )

    layout = predicted_layout()
    slopes_unique = slope_multiplicity == Counter({1: COEFFICIENT_COUNT})
    unique_gate = (
        unique_prediction_count == int(layout["uniquePredictionCount"])
        and unique_prediction_match_count == unique_prediction_count
    )
    ambiguous_gate = (
        ambiguous_resolved_count == int(layout["ambiguousDeterminantCount"])
        and selector_multiplicity == Counter({1: CASE_COUNT})
    )
    valid = slopes_unique and unique_gate and ambiguous_gate
    return {
        "liquidGlassRasterGeneralHeightSelectorTransferValidationSchemaVersion": 1,
        "classification": ROLE,
        "probe": str(root),
        "ciCommit": manifest.get("ciCommit"),
        "manifestSha256": sha256_path(root / "manifest.json"),
        "rawSha256": sha256_path(raw_path),
        "preregistrationSha256": PREREGISTRATION_SHA256,
        "measurement": {
            "coefficientCount": COEFFICIENT_COUNT,
            "slopeCandidateMultiplicity": counter_json(slope_multiplicity),
            "recoveredSlopeTableSha256": recovered_digest.hexdigest(),
            "selectorCandidateMultiplicity": counter_json(selector_multiplicity),
            "resolvedSelectorOffsetFromNearestDistribution": counter_json(
                selector_offsets
            ),
            "resolvedSelectorTableSha256": resolved_selector_digest.hexdigest(),
            "uniquePredictionCount": unique_prediction_count,
            "uniquePredictionExactMatchCount": unique_prediction_match_count,
            "ambiguousSelectorResolvedCount": ambiguous_resolved_count,
            "allSamplesSafelyInsideTopLeftPrimitive": True,
            "freshUniqueSelectorTransferGate": unique_gate,
            "ambiguousSelectorResolutionGate": ambiguous_gate,
            "captureValidForComparison": valid,
            "firstFailures": first_failures,
        },
        "conclusions": {
            "twoStageGeneralHeightArithmeticTransferredToFreshInputs": unique_gate,
            "measuredGeneralHeightSelectorMatrixComplete": ambiguous_gate,
            "portableNonExactDeterminantSelectorLawEstablished": False,
            "clippedSetupEstablished": False,
            "endToEndLiquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.root is None:
        print(json.dumps(predicted_layout(), indent=2, sort_keys=True))
        return
    if arguments.output is None:
        raise SystemExit("--output is required with a capture root")
    report = validate(arguments.root)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    raise SystemExit(0 if report["measurement"]["captureValidForComparison"] else 1)


if __name__ == "__main__":
    main()
