#!/usr/bin/env python3
"""Pin and analyze the completed Apple clip-boundary tomography capture."""

import argparse
import hashlib
import json
import struct
import zlib
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

import model_raster_general_height_arithmetic as two_stage
import validate_raster_clip_boundary_tomography as boundary


type JsonObject = dict[str, Any]

CI_RUN_ID = 30_676_628_218
CI_COMMIT = "51636e834750e1346e3fb044e6874a89afb1dc16"
MANIFEST_SHA256 = "5e13bf5e6c89732d339365e6415b14f6b9e1faed4e64ce888acfa94ac7e9abf9"
RAW_SHA256 = "486d227a49ab90a5744cf2dff827253b9e25effcaf3b7adaf5b0176d1e0527c8"
FRACTIONAL_SELECTOR_PATH = Path(__file__).with_name(
    "raster_fractional_subpixel_resolved_selectors.zlib"
)
FRACTIONAL_SELECTOR_SHA256 = (
    "b0990c2ce17fff5ebf06124497a38d38c9cf22e7e9210ccb6f95adb2c6834d53"
)
FRACTIONAL_SELECTOR_COUNT = 2_097_153
ANALYZED_FINE_DISTANCE_COUNT = 257
ANALYZED_WITNESS_COUNT = len(boundary.DELTA_BITS)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def round_integer_nearest_even(numerator: int, denominator: int) -> int:
    quotient, remainder = divmod(numerator, denominator)
    doubled = 2 * remainder
    return quotient + (
        doubled > denominator
        or (doubled == denominator and quotient & 1)
    )


def power_of_two(exponent: int) -> Fraction:
    return Fraction(1 << exponent) if exponent >= 0 else Fraction(1, 1 << -exponent)


def float32_fraction(bits: int) -> Fraction:
    sign = -1 if bits & 0x8000_0000 else 1
    exponent = (bits >> 23) & 0xFF
    significand = bits & 0x7F_FFFF
    if exponent == 0xFF:
        raise ValueError("non-finite binary32 value")
    if exponent == 0:
        return sign * significand * power_of_two(-149)
    return sign * ((1 << 23) | significand) * power_of_two(exponent - 150)


def fraction_float32_bits(value: Fraction) -> int:
    return boundary.float32_bits(float(value))


def floor_binary_exponent(value: Fraction) -> int:
    if value <= 0:
        raise ValueError("positive value required")
    exponent = value.numerator.bit_length() - value.denominator.bit_length()
    return exponent - (value < power_of_two(exponent))


def quantize_down(value: Fraction, precision_bits: int) -> Fraction:
    step = power_of_two(floor_binary_exponent(value) - precision_bits + 1)
    scaled = value / step
    return (scaled.numerator // scaled.denominator) * step


def load_fractional_selectors() -> tuple[int, ...]:
    raw = zlib.decompress(FRACTIONAL_SELECTOR_PATH.read_bytes())
    if (
        sha256_bytes(raw) != FRACTIONAL_SELECTOR_SHA256
        or len(raw) != FRACTIONAL_SELECTOR_COUNT * 4
    ):
        raise ValueError("fractional selector table differs")
    return tuple(value for (value,) in struct.iter_unpack("<I", raw))


def determinant_selector(selectors: tuple[int, ...], determinant: int) -> int:
    exponent = determinant.bit_length() - 1
    if exponent <= 23:
        normalized = determinant << (23 - exponent)
    else:
        normalized = round_integer_nearest_even(
            determinant,
            1 << (exponent - 23),
        )
    if normalized == 1 << 24:
        normalized >>= 1
    mantissa = normalized - (1 << 23)
    quantized = ((mantissa + 2) // 4) * 4
    return selectors[quantized // 4]


def modeled_slope(
    selectors: tuple[int, ...],
    delta_bits: int,
    *,
    width_fixed: int,
    height_fixed: int,
) -> int:
    determinant = width_fixed * height_fixed
    return two_stage.slope_bits(
        delta_bits + (8 << 23),
        opposite_edge=height_fixed,
        determinant=determinant,
        reciprocal_index=determinant_selector(selectors, determinant),
        first_stage_bias_units=two_stage.FIRST_STAGE_BIAS_UNITS[0],
    )


def pair_slope_candidates(
    data: bytes,
    case: boundary.ProbeCase,
    *,
    witness_index: int,
    span_pixels: int,
) -> tuple[int, ...]:
    records = boundary.case_records(data, case)[:2]
    if records[0][2] != records[1][2]:
        raise ValueError(f"{case.name} crosses primitives in its recovery pair")
    row = (7 + witness_index) * 4
    observations = []
    for record_index, record in enumerate(records):
        position = boundary.tile_local_position(case, record_index, "x")
        observations.extend(
            (
                (position, record[row]),
                (position + boundary.PULL_OFFSET, record[row + 1]),
            )
        )
    direct = boundary.float32_bits(
        boundary.float32_value(boundary.DELTA_BITS[witness_index])
        / span_pixels
    )
    return tuple(
        candidate
        for candidate in range(direct - 64, direct + 65)
        if boundary.factorization.top_left.factorized.shared_plane_accepts_slope(
            candidate,
            observations=observations,
        )
    )


def recover_pair_slope(
    data: bytes,
    case: boundary.ProbeCase,
    *,
    witness_index: int,
    span_pixels: int,
) -> int:
    accepted = pair_slope_candidates(
        data,
        case,
        witness_index=witness_index,
        span_pixels=span_pixels,
    )
    if len(accepted) != 1:
        raise ValueError(
            f"{case.name} witness {witness_index} has {len(accepted)} slopes"
        )
    return accepted[0]


def paired_fine_slopes(data: bytes) -> tuple[tuple[int, ...], ...]:
    cases, groups = boundary.case_catalog()
    left = next(group for group in groups if group.name == "v256-left")
    right = next(group for group in groups if group.name == "v256-right")

    def edge_case(group: boundary.BoundaryGroup, edge: int) -> boundary.ProbeCase:
        component = 0 if group.plane == "left" else 1
        return next(
            cases[index]
            for index in range(
                group.first_case,
                group.first_case + group.case_count,
            )
            if cases[index].geometry_fixed[component] == edge
        )

    recovered = []
    for distance in range(ANALYZED_FINE_DISTANCE_COUNT):
        left_case = edge_case(left, left.candidate_edge_fixed - distance)
        right_case = edge_case(right, right.candidate_edge_fixed + distance)
        left_slopes = tuple(
            recover_pair_slope(
                data,
                left_case,
                witness_index=witness_index,
                span_pixels=320,
            )
            for witness_index in range(ANALYZED_WITNESS_COUNT)
        )
        right_candidates = tuple(
            pair_slope_candidates(
                data,
                right_case,
                witness_index=witness_index,
                span_pixels=320,
            )
            for witness_index in range(ANALYZED_WITNESS_COUNT)
        )
        if any(
            slope not in candidates
            for slope, candidates in zip(
                left_slopes,
                right_candidates,
                strict=True,
            )
        ):
            raise ValueError(f"mirrored fine slopes differ at distance {distance}")
        recovered.append(left_slopes)
    return tuple(recovered)


def generated_delta(
    delta_bits: int,
    *,
    numerator: int,
    denominator: int,
    mode: str,
) -> int:
    exact = float32_fraction(delta_bits) * Fraction(numerator, denominator)
    if mode == "exact-ratio-binary32":
        return fraction_float32_bits(exact)
    if mode == "27-bit-down":
        return fraction_float32_bits(quantize_down(exact, 27))
    if mode == "binary32-clip-cancellation":
        delta = float32_fraction(delta_bits)
        t = float32_fraction(
            fraction_float32_bits(Fraction(denominator - numerator, denominator))
        )
        clipped = float32_fraction(fraction_float32_bits(-delta / 2 + delta * t))
        return fraction_float32_bits(delta / 2 - clipped)
    raise ValueError(f"unknown generated-delta mode {mode}")


def candidate_model_report(
    slopes: tuple[tuple[int, ...], ...],
) -> JsonObject:
    selectors = load_fractional_selectors()
    modes = {
        "guardExactRatioBinary32": ("guard", "exact-ratio-binary32"),
        "guard27BitDown": ("guard", "27-bit-down"),
        "guardBinary32ClipCancellation": (
            "guard",
            "binary32-clip-cancellation",
        ),
        "viewportExactRatioBinary32": ("viewport", "exact-ratio-binary32"),
    }
    reports: JsonObject = {}
    total = ANALYZED_FINE_DISTANCE_COUNT * ANALYZED_WITNESS_COUNT
    for name, (plane, mode) in modes.items():
        matches = 0
        full_distances = 0
        error_distribution: Counter[int] = Counter()
        for distance, observed in enumerate(slopes):
            distance_matches = 0
            if distance == 0:
                width_fixed = 320 * boundary.UNITS_PER_PIXEL
                generated = boundary.DELTA_BITS
            else:
                width_fixed = (
                    (320 if plane == "guard" else 256)
                    * boundary.UNITS_PER_PIXEL
                    - distance
                )
                generated = tuple(
                    generated_delta(
                        delta_bits,
                        numerator=width_fixed,
                        denominator=320 * boundary.UNITS_PER_PIXEL,
                        mode=mode,
                    )
                    for delta_bits in boundary.DELTA_BITS
                )
            for witness_index, delta_bits in enumerate(generated):
                predicted = modeled_slope(
                    selectors,
                    delta_bits,
                    width_fixed=width_fixed,
                    height_fixed=47 * boundary.UNITS_PER_PIXEL,
                )
                error = observed[witness_index] - predicted
                error_distribution[error] += 1
                distance_matches += error == 0
                matches += error == 0
            full_distances += distance_matches == ANALYZED_WITNESS_COUNT
        reports[name] = {
            "coefficientCount": total,
            "matchCount": matches,
            "mismatchCount": total - matches,
            "exactDistanceCount": full_distances,
            "floatUlpErrorDistribution": {
                str(error): count
                for error, count in sorted(error_distribution.items())
            },
            "exact": matches == total,
        }
    return reports


def duplicate_geometry_report(data: bytes) -> JsonObject:
    cases, groups = boundary.case_catalog()
    group_map = {(group.viewport, group.plane): group for group in groups}
    pair_reports = []
    total_geometry_pairs = 0
    total_record_pairs = 0
    differing_payload_words = 0
    for viewport in (256, 512):
        for first_plane, second_plane in (("left", "right"), ("top", "bottom")):
            first_group = group_map[(viewport, first_plane)]
            second_group = group_map[(viewport, second_plane)]
            first_cases = {
                cases[index].geometry_fixed: cases[index]
                for index in range(
                    first_group.first_case,
                    first_group.first_case + first_group.case_count,
                )
            }
            second_cases = {
                cases[index].geometry_fixed: cases[index]
                for index in range(
                    second_group.first_case,
                    second_group.first_case + second_group.case_count,
                )
            }
            geometries = sorted(first_cases.keys() & second_cases.keys())
            record_pairs = 0
            differences = 0
            for geometry in geometries:
                first_records = boundary.case_records(data, first_cases[geometry])
                second_records = boundary.case_records(data, second_cases[geometry])
                for first, second in zip(first_records, second_records, strict=True):
                    record_pairs += 1
                    differences += sum(
                        left != right
                        for index, (left, right) in enumerate(
                            zip(first, second, strict=True)
                        )
                        if index != 3
                    )
            pair_reports.append(
                {
                    "viewport": viewport,
                    "planes": [first_plane, second_plane],
                    "geometryPairCount": len(geometries),
                    "recordPairCount": record_pairs,
                    "differingPayloadWordCount": differences,
                }
            )
            total_geometry_pairs += len(geometries)
            total_record_pairs += record_pairs
            differing_payload_words += differences
    if total_geometry_pairs != 388 or differing_payload_words != 0:
        raise ValueError("duplicate geometry controls differ")
    return {
        "pairs": pair_reports,
        "geometryPairCount": total_geometry_pairs,
        "recordPairCount": total_record_pairs,
        "comparedPayloadWordCount": total_record_pairs * 59,
        "differingPayloadWordCount": differing_payload_words,
        "bitExactIgnoringIntentionalCaseIndex": True,
    }


def analyze(root: Path) -> JsonObject:
    manifest, raw_path = boundary.validate_manifest(root)
    if (
        manifest.get("ciCommit") != CI_COMMIT
        or boundary.sha256_path(root / "manifest.json") != MANIFEST_SHA256
        or boundary.sha256_path(raw_path) != RAW_SHA256
    ):
        raise ValueError("clip-boundary capture identity differs")
    data = boundary.load_records(raw_path)
    prospective = boundary.validate(root)
    groups = prospective["measurement"]["boundaryGroups"]
    inside_count = sum(int(group["insideCaseCount"]) for group in groups.values())
    inside_failures = sum(
        int(group["insideFailureCount"]) for group in groups.values()
    )
    outside_count = sum(int(group["outsideCaseCount"]) for group in groups.values())
    outside_collisions = sum(
        int(group["outsideObservationalCollisionCount"])
        for group in groups.values()
    )
    immediate_or_second_step_rejection = all(
        any(
            not bool(step["allBaselineSlopesAccepted"])
            for step in group["firstTwoOutwardSteps"]
        )
        for group in groups.values()
    )
    slopes = paired_fine_slopes(data)
    models = candidate_model_report(slopes)
    best_name, best = max(
        models.items(),
        key=lambda item: int(item[1]["matchCount"]),
    )
    return {
        "rasterClipBoundaryTomographyAnalysisSchemaVersion": 1,
        "classification": "post-capture-clip-boundary-and-topology-discovery",
        "source": {
            "ciRunId": CI_RUN_ID,
            "ciCommit": CI_COMMIT,
            "manifestSha256": MANIFEST_SHA256,
            "rawSha256": RAW_SHA256,
            "preregistrationSha256": boundary.PREREGISTRATION_SHA256,
        },
        "integrity": prospective["measurement"]["integrity"],
        "samplingAudit": {
            "preregisteredSameTilePairCount": 2,
            "actualSameTilePairCount": 1,
            "tileLocalPositions": [0, 30, 28, 26],
            "descriptionGateFalsified": True,
            "captureInvalidated": False,
        },
        "duplicateGeometryControl": duplicate_geometry_report(data),
        "boundaryDiscovery": {
            "groups": groups,
            "insideOrOnCandidateCaseCount": inside_count,
            "insideFailureCount": inside_failures,
            "outsideCaseCount": outside_count,
            "outsideRejectedCaseCount": outside_count - outside_collisions,
            "outsideObservationalCollisionCount": outside_collisions,
            "allGroupsRejectWithinTwoFixedSteps": immediate_or_second_step_rejection,
            "fixedStepPixels": 1 / boundary.UNITS_PER_PIXEL,
            "normalizedNDCOnePointFiveCandidateConsistent": (
                inside_failures == 0 and immediate_or_second_step_rejection
            ),
            "prospectivelyEstablished": False,
        },
        "clippedArithmeticCandidateModels": {
            "mirroredV256FineCoefficientCount": (
                ANALYZED_FINE_DISTANCE_COUNT * ANALYZED_WITNESS_COUNT
            ),
            "mirroredLeftRightSlopeMismatchCount": 0,
            "models": models,
            "bestSimpleCandidate": best_name,
            "bestSimpleCandidateMismatchCount": int(best["mismatchCount"]),
            "exactModelSelected": bool(best["exact"]),
        },
        "conclusions": {
            "captureValidForAnalysis": True,
            "normalizedGuardCandidateStronglySupportedAsDiscovery": True,
            "generatedTopologyCorpusComplete": True,
            "simpleClipArithmeticCandidatesFalsified": True,
            "clipArithmeticEstablished": False,
            "targetedClipArithmeticDiscriminatorRequired": True,
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
