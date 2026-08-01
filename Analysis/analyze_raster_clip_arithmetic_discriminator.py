#!/usr/bin/env python3
"""Pin and analyze the fixed-post-clip Apple Metal capture."""

import argparse
import hashlib
import json
import struct
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

import analyze_raster_clip_boundary_tomography as boundary_analysis
import model_raster_general_height_arithmetic as two_stage
import validate_raster_clip_arithmetic_discriminator as capture


type JsonObject = dict[str, Any]
type RecordArray = NDArray[np.uint32]

CI_RUN_ID = 30_678_295_250
CI_COMMIT = "b8116cdc9e2fd239b04f86f1c8167031f530b9e8"
MANIFEST_SHA256 = (
    "f41407aea23c6e2b1e7d1b80dea94f8f135892613e55d161e30bfb1d43e4cae2"
)
RAW_SHA256 = (
    "2bb66f13e77c57bcd8ea376046aadd37aac5855f98dcbb729e101639d752646a"
)
MATCHED_DISTANCE_COUNT = capture.DISTANCE_COUNT // 2 + 1
EFFECTIVE_DELTA_SEARCH_RADIUS = 2
PULL_POSITIONS = (0.0, 0.9375, 15.0, 15.9375, 31.0, 31.9375)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def float32_value(bits: int) -> float:
    return boundary_analysis.boundary.float32_value(bits)


def float32_bits(value: float) -> int:
    return boundary_analysis.boundary.float32_bits(value)


def exact_generated_delta(
    delta_bits: int,
    *,
    post_clip_span_fixed: int,
    distance_fixed: int,
) -> Fraction:
    return (
        boundary_analysis.float32_fraction(delta_bits)
        * post_clip_span_fixed
        / (post_clip_span_fixed + distance_fixed)
    )


def quantize_nearest_even(value: Fraction, precision_bits: int) -> Fraction:
    step = boundary_analysis.power_of_two(
        boundary_analysis.floor_binary_exponent(value) - precision_bits + 1
    )
    scaled = value / step
    quotient, remainder = divmod(scaled.numerator, scaled.denominator)
    doubled = 2 * remainder
    if doubled > scaled.denominator or (
        doubled == scaled.denominator and quotient & 1
    ):
        quotient += 1
    return quotient * step


def quantize_up(value: Fraction, precision_bits: int) -> Fraction:
    step = boundary_analysis.power_of_two(
        boundary_analysis.floor_binary_exponent(value) - precision_bits + 1
    )
    scaled = value / step
    quotient, remainder = divmod(scaled.numerator, scaled.denominator)
    return (quotient + (remainder != 0)) * step


def load_records(raw_path: Path) -> RecordArray:
    return np.memmap(
        raw_path,
        dtype="<u4",
        mode="r",
        shape=(
            capture.CASE_COUNT,
            capture.SAMPLE_COUNT,
            capture.RECORD_WORD_COUNT,
        ),
    )


def witness_pull_words(records: RecordArray, witness_index: int) -> tuple[int, ...]:
    component = witness_index % 4
    center_word = 8 + 16 * (witness_index // 4) + component
    pull_zero_word = center_word + 4
    pull_fifteen_word = center_word + 8
    return tuple(
        int(records[sample_index, word])
        for sample_index in range(capture.SAMPLE_COUNT)
        for word in (pull_zero_word, pull_fifteen_word)
    )


def accepts_slope(
    records: RecordArray,
    *,
    witness_index: int,
    slope_bits: int,
) -> bool:
    observations = witness_pull_words(records, witness_index)
    slope = float32_value(slope_bits)
    constant = float32_value(observations[0])
    return all(
        float32_bits(position * slope + constant) == observed
        for position, observed in zip(
            PULL_POSITIONS,
            observations,
            strict=True,
        )
    )


def case_records(
    records: RecordArray,
    group: capture.ProbeGroup,
    distance_fixed: int,
) -> RecordArray:
    return records[group.first_case + distance_fixed]


def raster_slopes_for_delta(
    selectors: tuple[int, ...],
    *,
    viewport: int,
    delta_bits: int,
) -> dict[int, int]:
    span_fixed = 5 * viewport * capture.UNITS_PER_PIXEL // 4
    return {
        cross_span: boundary_analysis.modeled_slope(
            selectors,
            delta_bits,
            width_fixed=span_fixed,
            height_fixed=cross_span * capture.UNITS_PER_PIXEL,
        )
        for cross_span in capture.CROSS_SPANS
    }


def accepted_by_groups(
    records: RecordArray,
    groups: tuple[capture.ProbeGroup, ...],
    selectors: tuple[int, ...],
    *,
    viewport: int,
    distance_fixed: int,
    witness_index: int,
    delta_bits: int,
) -> int:
    slopes = raster_slopes_for_delta(
        selectors,
        viewport=viewport,
        delta_bits=delta_bits,
    )
    return sum(
        accepts_slope(
            case_records(records, group, distance_fixed),
            witness_index=witness_index,
            slope_bits=slopes[group.cross_span],
        )
        for group in groups
        if group.viewport == viewport
    )


def recover_matched_scale_effective_deltas(
    records: RecordArray,
    groups: tuple[capture.ProbeGroup, ...],
    selectors: tuple[int, ...],
) -> tuple[list[tuple[int, int, int, int, int]], JsonObject]:
    """Recover effective binary32 deltas at equal normalized 256/512 cases."""

    recovered: list[tuple[int, int, int, int, int]] = []
    multiplicity: Counter[int] = Counter()
    offset_distribution: Counter[int] = Counter()
    digest = hashlib.sha256()
    first_ambiguous: list[JsonObject] = []
    span_fixed = 5 * 256 * capture.UNITS_PER_PIXEL // 4

    for distance_fixed in range(MATCHED_DISTANCE_COUNT):
        for witness_index, source_bits in enumerate(capture.DELTA_BITS):
            exact = exact_generated_delta(
                source_bits,
                post_clip_span_fixed=span_fixed,
                distance_fixed=distance_fixed,
            )
            center_bits = boundary_analysis.fraction_float32_bits(exact)
            accepted: list[int] = []
            for candidate_bits in range(
                center_bits - EFFECTIVE_DELTA_SEARCH_RADIUS,
                center_bits + EFFECTIVE_DELTA_SEARCH_RADIUS + 1,
            ):
                accepted_count = accepted_by_groups(
                    records,
                    groups,
                    selectors,
                    viewport=256,
                    distance_fixed=distance_fixed,
                    witness_index=witness_index,
                    delta_bits=candidate_bits,
                )
                accepted_count += accepted_by_groups(
                    records,
                    groups,
                    selectors,
                    viewport=512,
                    distance_fixed=2 * distance_fixed,
                    witness_index=witness_index,
                    delta_bits=candidate_bits,
                )
                if accepted_count == len(groups):
                    accepted.append(candidate_bits)

            multiplicity[len(accepted)] += 1
            if len(accepted) == 1:
                effective_bits = accepted[0]
                recovered.append(
                    (
                        distance_fixed,
                        witness_index,
                        source_bits,
                        center_bits,
                        effective_bits,
                    )
                )
                offset_distribution[effective_bits - center_bits] += 1
                digest.update(struct.pack("<I", effective_bits))
            else:
                digest.update(struct.pack("<I", 0xFFFF_FFFF))
                if len(first_ambiguous) < 32:
                    first_ambiguous.append(
                        {
                            "distanceFixed": distance_fixed,
                            "witnessIndex": witness_index,
                            "centerBits": f"0x{center_bits:08x}",
                            "acceptedOffsets": [
                                bits - center_bits for bits in accepted
                            ],
                        }
                    )

    coefficient_count = MATCHED_DISTANCE_COUNT * capture.WITNESS_COUNT
    return recovered, {
        "coefficientCount": coefficient_count,
        "uniqueCoefficientCount": len(recovered),
        "candidateMultiplicity": {
            str(key): value for key, value in sorted(multiplicity.items())
        },
        "uniqueOffsetFromCorrectlyRoundedDistribution": {
            str(key): value
            for key, value in sorted(offset_distribution.items())
        },
        "effectiveDeltaStreamSha256": digest.hexdigest(),
        "firstAmbiguous": first_ambiguous,
        "powerOfTwoScaleTransferUsed": True,
        "effectiveDeltaIsHiddenClipState": True,
    }


def quantizer_report(
    recovered: list[tuple[int, int, int, int, int]],
) -> JsonObject:
    candidates: JsonObject = {}
    for precision_bits in range(24, 31):
        for mode in ("down", "nearest-even", "up"):
            matches = 0
            for distance_fixed, _, source_bits, _, observed_bits in recovered:
                exact = exact_generated_delta(
                    source_bits,
                    post_clip_span_fixed=(
                        5 * 256 * capture.UNITS_PER_PIXEL // 4
                    ),
                    distance_fixed=distance_fixed,
                )
                if mode == "down":
                    quantized = boundary_analysis.quantize_down(
                        exact,
                        precision_bits,
                    )
                elif mode == "nearest-even":
                    quantized = quantize_nearest_even(exact, precision_bits)
                else:
                    quantized = quantize_up(exact, precision_bits)
                predicted_bits = boundary_analysis.fraction_float32_bits(
                    quantized
                )
                matches += predicted_bits == observed_bits
            name = f"{precision_bits}-bit-{mode}"
            candidates[name] = {
                "coefficientCount": len(recovered),
                "matchCount": matches,
                "mismatchCount": len(recovered) - matches,
                "exact": matches == len(recovered),
            }

    correctly_rounded_matches = sum(
        center_bits == observed_bits
        for _, _, _, center_bits, observed_bits in recovered
    )
    candidates["correctly-rounded-binary32"] = {
        "coefficientCount": len(recovered),
        "matchCount": correctly_rounded_matches,
        "mismatchCount": len(recovered) - correctly_rounded_matches,
        "exact": correctly_rounded_matches == len(recovered),
    }
    ranked = sorted(
        candidates,
        key=lambda name: (-int(candidates[name]["matchCount"]), name),
    )
    return {
        "models": candidates,
        "ranking": ranked,
        "bestSimpleCandidate": ranked[0],
        "exactModelSelected": bool(candidates[ranked[0]]["exact"]),
    }


def full_down26_gate(
    records: RecordArray,
    groups: tuple[capture.ProbeGroup, ...],
    selectors: tuple[int, ...],
) -> JsonObject:
    by_viewport: JsonObject = {}
    total_group_coefficients = 0
    accepted_group_coefficients = 0
    fully_accepted_inputs = 0
    input_count = 0

    for viewport in capture.VIEWPORTS:
        span_fixed = 5 * viewport * capture.UNITS_PER_PIXEL // 4
        viewport_groups = tuple(
            group for group in groups if group.viewport == viewport
        )
        viewport_accepted = 0
        viewport_fully_accepted = 0
        viewport_inputs = 0
        for distance_fixed in range(capture.DISTANCE_COUNT):
            for witness_index, source_bits in enumerate(capture.DELTA_BITS):
                exact = exact_generated_delta(
                    source_bits,
                    post_clip_span_fixed=span_fixed,
                    distance_fixed=distance_fixed,
                )
                candidate_bits = boundary_analysis.fraction_float32_bits(
                    boundary_analysis.quantize_down(exact, 26)
                )
                accepted = accepted_by_groups(
                    records,
                    viewport_groups,
                    selectors,
                    viewport=viewport,
                    distance_fixed=distance_fixed,
                    witness_index=witness_index,
                    delta_bits=candidate_bits,
                )
                viewport_accepted += accepted
                viewport_fully_accepted += accepted == len(viewport_groups)
                viewport_inputs += 1

        viewport_group_coefficients = viewport_inputs * len(viewport_groups)
        by_viewport[str(viewport)] = {
            "inputCount": viewport_inputs,
            "groupCoefficientCount": viewport_group_coefficients,
            "acceptedGroupCoefficientCount": viewport_accepted,
            "rejectedGroupCoefficientCount": (
                viewport_group_coefficients - viewport_accepted
            ),
            "fullyAcceptedInputCount": viewport_fully_accepted,
        }
        total_group_coefficients += viewport_group_coefficients
        accepted_group_coefficients += viewport_accepted
        fully_accepted_inputs += viewport_fully_accepted
        input_count += viewport_inputs

    return {
        "model": "26-significant-bit-directed-down-generated-delta",
        "byViewport": by_viewport,
        "inputCount": input_count,
        "groupCoefficientCount": total_group_coefficients,
        "acceptedGroupCoefficientCount": accepted_group_coefficients,
        "rejectedGroupCoefficientCount": (
            total_group_coefficients - accepted_group_coefficients
        ),
        "fullyAcceptedInputCount": fully_accepted_inputs,
        "notFullyAcceptedInputCount": input_count - fully_accepted_inputs,
        "exact": accepted_group_coefficients == total_group_coefficients,
    }


def analyze(root: Path) -> JsonObject:
    manifest, raw_path = capture.validate_manifest(root)
    if (
        manifest.get("ciCommit") != CI_COMMIT
        or sha256_path(root / "manifest.json") != MANIFEST_SHA256
        or sha256_path(raw_path) != RAW_SHA256
    ):
        raise ValueError("clip-arithmetic capture identity differs")

    records = load_records(raw_path)
    _, groups = capture.case_catalog()
    selectors = boundary_analysis.load_fractional_selectors()
    recovered, recovery = recover_matched_scale_effective_deltas(
        records,
        groups,
        selectors,
    )
    quantizers = quantizer_report(recovered)
    down26 = full_down26_gate(records, groups, selectors)
    if down26["exact"]:
        raise ValueError("expected the preregistered discriminator to reject down26")

    return {
        "rasterClipArithmeticDiscriminatorAnalysisSchemaVersion": 1,
        "classification": "post-capture-fixed-post-clip-arithmetic-discovery",
        "source": {
            "ciRunId": CI_RUN_ID,
            "ciCommit": CI_COMMIT,
            "manifestSha256": MANIFEST_SHA256,
            "rawSha256": RAW_SHA256,
            "preregistrationSha256": capture.PREREGISTRATION_SHA256,
        },
        "integrity": capture.validate_records(raw_path),
        "matchedPowerOfTwoScaleRecovery": recovery,
        "simpleGeneratedDeltaQuantizers": quantizers,
        "fullDown26Gate": down26,
        "conclusions": {
            "captureValidForAnalysis": True,
            "fixedPostClipGeometryConfirmedByConstruction": True,
            "effectiveGeneratedDeltaMostlyUniquelyLocalized": True,
            "correctlyRoundedGeneratedDeltaFalsified": True,
            "fixedDown26GeneratedDeltaFalsified": True,
            "hiddenClipStateOrPrecisionRemains": True,
            "clipArithmeticEstablished": False,
            "endToEndLiquidGlassParityEstablished": False,
            "productionShaderChangeAuthorized": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = analyze(arguments.root)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(rendered, end="")
    else:
        arguments.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
