#!/usr/bin/env python3
"""Recover reciprocal candidates using the two-stage odd-height model."""

import argparse
import hashlib
import json
import struct
import zlib
from collections import Counter
from pathlib import Path
from typing import Any

import explore_exact_general_height_numerator as previous
import model_raster_general_height_arithmetic as two_stage
import validate_raster_low_exponent_power2 as low_exponent


type JsonObject = dict[str, Any]

CANDIDATE_RADIUS = 16
MASK = struct.Struct("<Q")
SELECTOR = struct.Struct("<I")
AMBIGUOUS_SELECTOR = 0xFFFF_FFFF


def recover() -> tuple[bytes, JsonObject]:
    widths = low_exponent.factorized.geometry_widths()
    delta_shifts = low_exponent.factorized.delta_exponent_shift_bits()
    witness_bits = low_exponent.arithmetic.witness_delta_bits()
    slopes = previous.recovered_slopes()
    canonical = low_exponent.factorized.canonical_reciprocals()
    masks = bytearray()
    selected = bytearray()
    multiplicity: Counter[int] = Counter()
    candidate_offsets: Counter[int] = Counter()
    candidate_sets: Counter[tuple[int, ...]] = Counter()
    ambiguous: list[JsonObject] = []
    exact_normalized_count = 0
    exact_normalized_canonical_match_count = 0

    for width_index, width in enumerate(widths):
        scaled_deltas = [
            bits - delta_shifts[width_index] for bits in witness_bits
        ]
        for geometry_index, height in enumerate(previous.HEIGHTS):
            determinant = width * height
            nearest = low_exponent.arithmetic.nearest_even_reciprocal_index(
                determinant
            )
            actual = [
                slopes[
                    (width_index * len(witness_bits) + witness_index)
                    * len(previous.HEIGHTS)
                    + geometry_index
                ]
                for witness_index in range(len(witness_bits))
            ]
            accepted = tuple(
                nearest + offset
                for offset in range(-CANDIDATE_RADIUS, CANDIDATE_RADIUS + 1)
                if all(
                    two_stage.slope_bits(
                        delta_bits,
                        opposite_edge=height,
                        determinant=determinant,
                        reciprocal_index=nearest + offset,
                        first_stage_bias_units=(
                            two_stage.FIRST_STAGE_BIAS_UNITS[0]
                        ),
                    )
                    == actual_bits
                    for delta_bits, actual_bits in zip(
                        scaled_deltas,
                        actual,
                        strict=True,
                    )
                )
            )
            offsets = tuple(value - nearest for value in accepted)
            mask = sum(1 << (offset + CANDIDATE_RADIUS) for offset in offsets)
            masks.extend(MASK.pack(mask))
            selected.extend(
                SELECTOR.pack(
                    accepted[0] if len(accepted) == 1 else AMBIGUOUS_SELECTOR
                )
            )
            multiplicity[len(accepted)] += 1
            candidate_offsets.update(offsets)
            candidate_sets[offsets] += 1
            normalized = previous.exact_normalized_class(determinant)
            if normalized is not None:
                normalized_class, _ = normalized
                exact_normalized_count += 1
                exact_normalized_canonical_match_count += accepted == (
                    canonical[normalized_class - 8_192],
                )
            if len(accepted) != 1:
                ambiguous.append(
                    {
                        "widthIndex": width_index,
                        "width": width,
                        "height": height,
                        "determinant": determinant,
                        "nearestReciprocalIndex": nearest,
                        "candidateOffsetsFromNearest": list(offsets),
                    }
                )

    mask_bytes = bytes(masks)
    selector_bytes = bytes(selected)
    report: JsonObject = {
        "model": {
            "firstStageOutputBits": two_stage.FIRST_STAGE_OUTPUT_BITS,
            "firstStageTruncationBits": (
                two_stage.FIRST_STAGE_TRUNCATION_BITS
            ),
            "firstStageBiasEquivalenceClass": list(
                two_stage.FIRST_STAGE_BIAS_UNITS
            ),
            "secondStageOutputBits": two_stage.SECOND_STAGE_OUTPUT_BITS,
            "secondStageTruncationBits": (
                two_stage.SECOND_STAGE_TRUNCATION_BITS
            ),
            "secondStageBiasUnits": two_stage.SECOND_STAGE_BIAS_UNITS,
        },
        "determinantCount": len(widths) * len(previous.HEIGHTS),
        "coefficientCount": len(slopes),
        "candidateRadiusReciprocalUlps": CANDIDATE_RADIUS,
        "candidateMultiplicity": {
            str(key): value for key, value in sorted(multiplicity.items())
        },
        "candidateOffsetDistribution": {
            str(key): value for key, value in sorted(candidate_offsets.items())
        },
        "candidateSetDistribution": {
            json.dumps(key): value
            for key, value in sorted(
                candidate_sets.items(),
                key=lambda item: (len(item[0]), item[0]),
            )
        },
        "exactNormalizedDeterminantCount": exact_normalized_count,
        "exactNormalizedCanonicalMatchCount": (
            exact_normalized_canonical_match_count
        ),
        "candidateMaskBytes": len(mask_bytes),
        "candidateMaskSha256": hashlib.sha256(mask_bytes).hexdigest(),
        "uniqueSelectorTableBytes": len(selector_bytes),
        "uniqueSelectorTableSha256": hashlib.sha256(selector_bytes).hexdigest(),
        "ambiguousCases": ambiguous,
    }
    return mask_bytes, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mask-output", type=Path)
    parser.add_argument("--report", type=Path)
    arguments = parser.parse_args()
    masks, report = recover()
    compressed = zlib.compress(masks, level=9)
    report["compressedCandidateMaskBytes"] = len(compressed)
    report["compressedCandidateMaskSha256"] = hashlib.sha256(compressed).hexdigest()
    if arguments.mask_output is not None:
        arguments.mask_output.write_bytes(compressed)
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.report is not None:
        arguments.report.write_text(serialized, encoding="utf-8")
    print(serialized, end="")


if __name__ == "__main__":
    main()
