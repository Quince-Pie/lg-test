#!/usr/bin/env python3
"""Materialize the resolved general-height reciprocal selector table."""

import argparse
import hashlib
import json
import struct
import zlib
from collections import Counter
from pathlib import Path
from typing import Any

import model_raster_general_height_arithmetic as two_stage
import validate_raster_general_height_selector_transfer as selector


type JsonObject = dict[str, Any]


def exact_normalized_class(area: int) -> tuple[int, int] | None:
    shift = area.bit_length() - 14
    if shift < 0:
        return None
    normalized, remainder = divmod(area, 1 << shift)
    if remainder != 0 or not 8_192 <= normalized <= 16_383:
        return None
    return normalized, shift


def analyze(root: Path) -> tuple[bytes, JsonObject]:
    selector.load_preregistration()
    manifest, raw_path = selector.validate_manifest(root)
    data = raw_path.read_bytes()
    masks = selector.load_candidate_masks()
    resolved = bytearray()
    slope_digest = hashlib.sha256()
    offset_from_nearest: Counter[int] = Counter()
    endpoint_from_floor: Counter[int] = Counter()
    endpoint_by_height: dict[int, Counter[int]] = {
        height: Counter() for height in selector.HEIGHTS
    }
    prior_ambiguous_resolutions: list[JsonObject] = []
    exact_normalized_count = 0
    exact_normalized_canonical_match_count = 0
    canonical = selector.factorization.low_exponent.factorized.canonical_reciprocals()

    for width_index, width in enumerate(selector.WIDTHS):
        for height_index, height in enumerate(selector.HEIGHTS):
            case_index = width_index * selector.HEIGHT_COUNT + height_index
            determinant = width * height
            candidates = selector.candidate_reciprocals(
                masks,
                case_index=case_index,
                determinant=determinant,
            )
            slopes: list[int] = []
            for witness_index, significand in enumerate(
                selector.WITNESS_SIGNIFICANDS
            ):
                coefficient_index = case_index * selector.WITNESS_COUNT + witness_index
                delta_bits = selector.scaled_delta_bits(width_index, significand)
                direct_bits = selector.factorization.top_left.arithmetic.float32_bits(
                    selector.factorization.top_left.arithmetic.float32_value(delta_bits)
                    / width
                )
                slope_bits, accepted = selector.recover_slope(
                    data,
                    coefficient_index=coefficient_index,
                    direct_bits=direct_bits,
                )
                if accepted != (slope_bits,):
                    raise ValueError("selector-transfer slope is not unique")
                slopes.append(slope_bits)
                slope_digest.update(struct.pack("<I", slope_bits))
            accepted_selectors = tuple(
                reciprocal
                for reciprocal in candidates
                if all(
                    two_stage.slope_bits(
                        selector.scaled_delta_bits(width_index, significand),
                        opposite_edge=height,
                        determinant=determinant,
                        reciprocal_index=reciprocal,
                        first_stage_bias_units=(
                            two_stage.FIRST_STAGE_BIAS_UNITS[0]
                        ),
                    )
                    == slope_bits
                    for significand, slope_bits in zip(
                        selector.WITNESS_SIGNIFICANDS,
                        slopes,
                        strict=True,
                    )
                )
            )
            if len(accepted_selectors) != 1:
                raise ValueError("selector-transfer reciprocal is not unique")
            reciprocal = accepted_selectors[0]
            resolved.extend(struct.pack("<I", reciprocal))
            nearest = (
                selector.factorization.top_left.arithmetic.nearest_even_reciprocal_index(
                    determinant
                )
            )
            offset_from_nearest[reciprocal - nearest] += 1
            reciprocal_power = 1 << (24 + (determinant - 1).bit_length())
            floor_reciprocal = reciprocal_power // determinant
            endpoint = reciprocal - floor_reciprocal
            if endpoint not in (0, 1):
                raise ValueError("resolved reciprocal is not an exact endpoint")
            endpoint_from_floor[endpoint] += 1
            endpoint_by_height[height][endpoint] += 1
            normalized = exact_normalized_class(determinant)
            if normalized is not None:
                normalized_class, _ = normalized
                exact_normalized_count += 1
                exact_normalized_canonical_match_count += (
                    reciprocal == canonical[normalized_class - 8_192]
                )
            if len(candidates) > 1:
                prior_ambiguous_resolutions.append(
                    {
                        "width": width,
                        "height": height,
                        "determinant": determinant,
                        "candidateOffsetsFromNearest": [
                            candidate - nearest for candidate in candidates
                        ],
                        "selectedOffsetFromNearest": reciprocal - nearest,
                    }
                )

    resolved_bytes = bytes(resolved)
    report: JsonObject = {
        "ciRunId": 30_670_953_328,
        "ciCommit": manifest.get("ciCommit"),
        "manifestSha256": selector.sha256_path(root / "manifest.json"),
        "rawSha256": selector.sha256_path(raw_path),
        "preregistrationSha256": selector.PREREGISTRATION_SHA256,
        "determinantCount": selector.CASE_COUNT,
        "coefficientCount": selector.COEFFICIENT_COUNT,
        "recoveredSlopeTableSha256": slope_digest.hexdigest(),
        "resolvedSelectorTableBytes": len(resolved_bytes),
        "resolvedSelectorTableSha256": hashlib.sha256(resolved_bytes).hexdigest(),
        "resolvedSelectorOffsetFromNearestDistribution": {
            str(key): value for key, value in sorted(offset_from_nearest.items())
        },
        "resolvedSelectorEndpointFromFloorDistribution": {
            str(key): value for key, value in sorted(endpoint_from_floor.items())
        },
        "resolvedSelectorEndpointFromFloorByHeight": {
            str(height): {
                str(key): value for key, value in sorted(counts.items())
            }
            for height, counts in endpoint_by_height.items()
        },
        "exactNormalizedDeterminantCount": exact_normalized_count,
        "exactNormalizedCanonicalMatchCount": (
            exact_normalized_canonical_match_count
        ),
        "priorAmbiguousResolutionCount": len(prior_ambiguous_resolutions),
        "priorAmbiguousResolutions": prior_ambiguous_resolutions,
        "portableSelectorLawEstablished": False,
        "clippedSetupEstablished": False,
        "endToEndLiquidGlassParityEstablished": False,
    }
    return resolved_bytes, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--selector-output", type=Path)
    parser.add_argument("--report", type=Path)
    arguments = parser.parse_args()
    selectors, report = analyze(arguments.root)
    compressed = zlib.compress(selectors, level=9)
    report["compressedSelectorTableBytes"] = len(compressed)
    report["compressedSelectorTableSha256"] = hashlib.sha256(compressed).hexdigest()
    if arguments.selector_output is not None:
        arguments.selector_output.write_bytes(compressed)
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.report is not None:
        arguments.report.write_text(serialized, encoding="utf-8")
    print(serialized, end="")


if __name__ == "__main__":
    main()
