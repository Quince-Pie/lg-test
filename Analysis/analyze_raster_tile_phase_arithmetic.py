#!/usr/bin/env python3
"""Discriminate endpoint-composition laws using the opened schema-4 corpus."""

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

import open_raster_tile_phase_holdout as opening
import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import validate_raster_tile_phase_holdout as capture


type JsonObject = dict[str, Any]
type SlopeModel = Callable[
    [capture.CaptureCase, capture.EndpointCase, int, tuple[int, ...]], Fraction
]

SEARCH_OFFSETS = tuple(range(-2, 4))


@dataclass(frozen=True)
class Setup:
    capture_case: capture.CaptureCase
    endpoint: capture.EndpointCase
    axis: int
    accepted_offsets: tuple[int, ...]
    internal_offset: int
    phase: Fraction


def normalized_significand(value: Fraction, precision_bits: int) -> tuple[int, int]:
    """Represent an exact dyadic value with a normalized integer significand."""
    if value <= 0:
        raise ValueError("a positive value is required")
    exponent = v1.floor_binary_exponent(value) - precision_bits + 1
    scaled = value / v1.power_of_two(exponent)
    if scaled.denominator != 1:
        raise ValueError("value exceeds the requested exact precision")
    significand = scaled.numerator
    if not 1 << (precision_bits - 1) <= significand < 1 << precision_bits:
        raise ValueError("normalized significand has the wrong width")
    return significand, exponent


def p27_lattice(
    capture_case: capture.CaptureCase,
    endpoint: capture.EndpointCase,
    axis: int,
) -> tuple[int, Fraction, Fraction, int]:
    extent = capture_case.width if axis == 0 else capture_case.height
    delta = v1.float32_bits_fraction(endpoint.highBits) - v1.float32_bits_fraction(
        endpoint.lowBits
    )
    if delta == 0:
        return 0, Fraction(0), Fraction(0), 0
    magnitude = abs(delta) / extent
    exponent = v1.floor_binary_exponent(magnitude)
    step = v1.power_of_two(exponent - v1.SLOPE_PRECISION_BITS + 1)
    floor_index = int(magnitude / step)
    return (-1 if delta < 0 else 1), step, magnitude - floor_index * step, floor_index


def slope_offset(
    slope: Fraction,
    capture_case: capture.CaptureCase,
    endpoint: capture.EndpointCase,
    axis: int,
) -> int | None:
    sign, step, _, floor_index = p27_lattice(capture_case, endpoint, axis)
    if sign == 0:
        return 0 if slope == 0 else None
    offset = abs(slope) / step - floor_index
    return int(offset) if offset.denominator == 1 else None


def setup_matches(
    actual_records: tuple[tuple[int, ...], ...],
    samples: tuple[capture.SamplePosition, ...],
    capture_case: capture.CaptureCase,
    endpoint: capture.EndpointCase,
    axis: int,
    slope: Fraction,
) -> bool:
    value = float(slope)
    constants = {
        sample.tile: v1.bits_float32(
            v2.tile_constant_bits(
                capture_case,
                endpoint,
                axis=axis,
                tile=sample.tile,
            )
        )
        for sample in samples
        if sample.axis == axis
    }
    return all(
        actual == v2.predict_record_with_setup(
            sample,
            slope=value,
            constant=constants[sample.tile],
        )
        for sample, actual in zip(samples, actual_records, strict=True)
        if sample.axis == axis
    )


def recover_setups(root: Path) -> list[Setup]:
    _, streams = opening.actual_case_streams(root)
    selector_table = v1.load_selector_table()
    setups: list[Setup] = []
    for capture_case in capture.CASES:
        samples = capture.sample_positions(capture_case)
        stream = streams[capture_case.name]
        offset = 0
        for endpoint in capture.ENDPOINTS:
            if endpoint.role != "selector-discovery":
                continue
            records = tuple(
                capture.RECORD.unpack_from(
                    stream,
                    offset + sample_index * capture.RECORD.size,
                )
                for sample_index in range(len(samples))
            )
            offset += len(samples) * capture.RECORD.size
            for axis in range(capture.AXIS_COUNT):
                sign, step, remainder, floor_index = p27_lattice(
                    capture_case,
                    endpoint,
                    axis,
                )
                accepted = tuple(
                    candidate_offset
                    for candidate_offset in SEARCH_OFFSETS
                    if setup_matches(
                        records,
                        samples,
                        capture_case,
                        endpoint,
                        axis,
                        sign * (floor_index + candidate_offset) * step,
                    )
                )
                opposite = capture_case.height if axis == 0 else capture_case.width
                determinant = capture_case.width * capture_case.height
                delta = v1.bits_float32(endpoint.highBits) - v1.bits_float32(
                    endpoint.lowBits
                )
                internal = v1.fixed_product_slope(
                    delta,
                    opposite_edge=opposite,
                    determinant=determinant,
                    reciprocal_index=v1.reciprocal_selector(
                        determinant,
                        selector_table,
                    ),
                )
                internal_offset = slope_offset(
                    Fraction.from_float(internal),
                    capture_case,
                    endpoint,
                    axis,
                )
                if not accepted or internal_offset is None:
                    raise ValueError("schema-4 setup is outside the tested p27 lattice")
                setups.append(
                    Setup(
                        capture_case=capture_case,
                        endpoint=endpoint,
                        axis=axis,
                        accepted_offsets=accepted,
                        internal_offset=internal_offset,
                        phase=remainder / step,
                    )
                )
    return setups


def quantized_product(
    value: Fraction,
    precision_bits: int,
    rounding: str,
) -> Fraction:
    if value == 0:
        return value
    return v1.quantize_binary_significand(
        value,
        precision_bits,
        rounding=rounding,
    )


def direct_quantized_slope(
    capture_case: capture.CaptureCase,
    endpoint: capture.EndpointCase,
    axis: int,
    *,
    precision_bits: int,
    rounding: str,
) -> Fraction:
    extent = capture_case.width if axis == 0 else capture_case.height
    delta = v1.float32_bits_fraction(endpoint.highBits) - v1.float32_bits_fraction(
        endpoint.lowBits
    )
    if delta == 0:
        return Fraction(0)
    magnitude = quantized_product(
        abs(delta) / extent,
        precision_bits,
        rounding,
    )
    return -magnitude if delta < 0 else magnitude


def analyze_direct_quantizer(
    root: Path,
    *,
    precision_bits: int,
    rounding: str,
) -> JsonObject:
    _, streams = opening.actual_case_streams(root)
    setup_count = 0
    matching_setups = 0
    record_count = 0
    mismatched_records = 0
    mismatched_words = 0
    component_mismatches: Counter[str] = Counter()
    case_record_mismatches: Counter[str] = Counter()
    case_word_mismatches: Counter[str] = Counter()
    failures: list[JsonObject] = []
    for capture_case in capture.CASES:
        samples = capture.sample_positions(capture_case)
        stream = streams[capture_case.name]
        offset = 0
        for endpoint in capture.ENDPOINTS:
            if endpoint.role != "selector-discovery":
                continue
            records = tuple(
                capture.RECORD.unpack_from(
                    stream,
                    offset + sample_index * capture.RECORD.size,
                )
                for sample_index in range(len(samples))
            )
            offset += len(samples) * capture.RECORD.size
            for axis in range(capture.AXIS_COUNT):
                setup_count += 1
                slope = direct_quantized_slope(
                    capture_case,
                    endpoint,
                    axis,
                    precision_bits=precision_bits,
                    rounding=rounding,
                )
                constants = {
                    sample.tile: v1.bits_float32(
                        v2.tile_constant_bits(
                            capture_case,
                            endpoint,
                            axis=axis,
                            tile=sample.tile,
                        )
                    )
                    for sample in samples
                    if sample.axis == axis
                }
                setup_mismatches = 0
                for sample, actual in zip(samples, records, strict=True):
                    if sample.axis != axis:
                        continue
                    record_count += 1
                    predicted = v2.predict_record_with_setup(
                        sample,
                        slope=float(slope),
                        constant=constants[sample.tile],
                    )
                    differing = tuple(
                        component
                        for component, (predicted_word, actual_word) in enumerate(
                            zip(predicted, actual, strict=True)
                        )
                        if predicted_word != actual_word
                    )
                    if differing:
                        setup_mismatches += 1
                        mismatched_records += 1
                        mismatched_words += len(differing)
                        case_record_mismatches[capture_case.name] += 1
                        case_word_mismatches[capture_case.name] += len(differing)
                        component_mismatches.update(
                            (
                                f"pull@{component}/16"
                                if component < capture.PULL_COUNT
                                else "center"
                                if component == capture.PULL_COUNT
                                else "axis-derivative(center)"
                            )
                            for component in differing
                        )
                matching_setups += setup_mismatches == 0
                if setup_mismatches and len(failures) < 64:
                    failures.append(
                        {
                            "case": capture_case.name,
                            "caseRole": capture_case.role,
                            "endpoint": endpoint.name,
                            "axis": "x" if axis == 0 else "y",
                            "mismatchedRecords": setup_mismatches,
                        }
                    )
    return {
        "rasterTileDirectQuantizerAnalysisSchemaVersion": 1,
        "source": str(root),
        "precisionBits": precision_bits,
        "rounding": rounding,
        "setupCount": setup_count,
        "matchingSetupCount": matching_setups,
        "recordCount": record_count,
        "mismatchedRecordCount": mismatched_records,
        "mismatchedWordCount": mismatched_words,
        "componentMismatchCounts": dict(sorted(component_mismatches.items())),
        "caseMismatchCounts": {
            name: {
                "records": case_record_mismatches[name],
                "words": case_word_mismatches[name],
            }
            for name in sorted(case_record_mismatches)
        },
        "firstFailures": failures,
        "exact": mismatched_words == 0,
    }


def reciprocal_product(
    numerator: Fraction,
    determinant: int,
    selector_table: tuple[int, ...],
) -> Fraction:
    sign = -1 if numerator < 0 else 1
    significand, exponent = normalized_significand(
        abs(numerator),
        v1.FIRST_STAGE_OUTPUT_BITS,
    )
    reciprocal = v1.reciprocal_selector(determinant, selector_table)
    reciprocal_exponent = -(determinant - 1).bit_length() - 24
    coefficient, coefficient_exponent = v1.product_stage(
        significand,
        exponent,
        reciprocal,
        reciprocal_exponent,
        output_bits=v1.SECOND_STAGE_OUTPUT_BITS,
        truncation_bits=v1.SECOND_STAGE_TRUNCATION_BITS,
        bias_units=v1.SECOND_STAGE_BIAS_UNITS,
    )
    return sign * coefficient * v1.power_of_two(coefficient_exponent)


def exact_endpoint_product_model(
    precision_bits: int,
    rounding: str,
) -> SlopeModel:
    def model(
        capture_case: capture.CaptureCase,
        endpoint: capture.EndpointCase,
        axis: int,
        selector_table: tuple[int, ...],
    ) -> Fraction:
        opposite = capture_case.height if axis == 0 else capture_case.width
        determinant = capture_case.width * capture_case.height
        low = v1.float32_bits_fraction(endpoint.lowBits)
        high = v1.float32_bits_fraction(endpoint.highBits)
        numerator = quantized_product(
            high * opposite,
            precision_bits,
            rounding,
        ) - quantized_product(
            low * opposite,
            precision_bits,
            rounding,
        )
        return reciprocal_product(numerator, determinant, selector_table)

    return model


def partial_endpoint_product_model(
    output_bits: int,
    truncation_bits: int,
    bias_units: int,
) -> SlopeModel:
    def model(
        capture_case: capture.CaptureCase,
        endpoint: capture.EndpointCase,
        axis: int,
        selector_table: tuple[int, ...],
    ) -> Fraction:
        opposite = capture_case.height if axis == 0 else capture_case.width
        determinant = capture_case.width * capture_case.height
        edge_significand, edge_exponent = v1.float_significand_and_lsb_exponent(
            v1.float32_bits(float(opposite))
        )
        terms: list[tuple[int, int]] = []
        for endpoint_bits in (endpoint.lowBits, endpoint.highBits):
            endpoint_significand, endpoint_exponent = (
                v1.float_significand_and_lsb_exponent(endpoint_bits)
            )
            terms.append(
                v1.product_stage(
                    endpoint_significand,
                    endpoint_exponent,
                    edge_significand,
                    edge_exponent,
                    output_bits=output_bits,
                    truncation_bits=truncation_bits,
                    bias_units=bias_units,
                )
            )
        common_exponent = min(terms[0][1], terms[1][1])
        scaled = [
            significand << (exponent - common_exponent)
            for significand, exponent in terms
        ]
        numerator = (scaled[1] - scaled[0]) * v1.power_of_two(common_exponent)
        return reciprocal_product(numerator, determinant, selector_table)

    return model


def model_matrix() -> dict[str, SlopeModel]:
    result: dict[str, SlopeModel] = {}
    for precision_bits in range(24, 34):
        for rounding in ("down", "nearest-even", "up"):
            result[f"endpoint-p{precision_bits}-{rounding}"] = (
                exact_endpoint_product_model(precision_bits, rounding)
            )
    for output_bits in range(25, 31):
        for truncation_bits in (8, 12, 16, 19):
            for bias_units in range(0, 32):
                result[
                    f"endpoint-partial-p{output_bits}-t{truncation_bits}-b{bias_units}"
                ] = partial_endpoint_product_model(
                    output_bits,
                    truncation_bits,
                    bias_units,
                )
    return result


def analyze(root: Path) -> JsonObject:
    setups = recover_setups(root)
    selector_table = v1.load_selector_table()
    candidates: list[JsonObject] = []
    best_match_count = 0
    for name, model in model_matrix().items():
        matches = 0
        offset_distribution: Counter[int | None] = Counter()
        failures: list[JsonObject] = []
        for setup in setups:
            try:
                predicted = model(
                    setup.capture_case,
                    setup.endpoint,
                    setup.axis,
                    selector_table,
                )
                offset = slope_offset(
                    predicted,
                    setup.capture_case,
                    setup.endpoint,
                    setup.axis,
                )
            except ValueError:
                offset = None
            offset_distribution[offset] += 1
            accepted = offset in setup.accepted_offsets
            matches += accepted
            if not accepted and len(failures) < 8:
                failures.append(
                    {
                        "case": setup.capture_case.name,
                        "endpoint": setup.endpoint.name,
                        "axis": "x" if setup.axis == 0 else "y",
                        "phase": str(setup.phase),
                        "predictedOffset": offset,
                        "acceptedOffsets": list(setup.accepted_offsets),
                    }
                )
        best_match_count = max(best_match_count, matches)
        candidates.append(
            {
                "name": name,
                "matchCount": matches,
                "offsetDistribution": {
                    str(key): value
                    for key, value in sorted(
                        offset_distribution.items(),
                        key=lambda item: (item[0] is None, item[0]),
                    )
                },
                "firstFailures": failures,
            }
        )
    best = sorted(
        (candidate for candidate in candidates if candidate["matchCount"] == best_match_count),
        key=lambda candidate: str(candidate["name"]),
    )
    return {
        "rasterTilePhaseArithmeticAnalysisSchemaVersion": 1,
        "source": str(root),
        "setupCount": len(setups),
        "acceptedOffsetSignatures": {
            ",".join(map(str, signature)): count
            for signature, count in sorted(
                Counter(setup.accepted_offsets for setup in setups).items()
            )
        },
        "internalOffsetDistribution": {
            str(key): value
            for key, value in sorted(
                Counter(setup.internal_offset for setup in setups).items()
            )
        },
        "modelCount": len(candidates),
        "bestMatchCount": best_match_count,
        "bestModels": best,
        "allModels": sorted(
            candidates,
            key=lambda candidate: (-int(candidate["matchCount"]), str(candidate["name"])),
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--direct-precision", type=int)
    parser.add_argument(
        "--direct-rounding",
        choices=("down", "nearest-even", "up"),
        default="nearest-even",
    )
    arguments = parser.parse_args()
    report = (
        analyze_direct_quantizer(
            arguments.root,
            precision_bits=arguments.direct_precision,
            rounding=arguments.direct_rounding,
        )
        if arguments.direct_precision is not None
        else analyze(arguments.root)
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(rendered, end="")
    else:
        arguments.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
