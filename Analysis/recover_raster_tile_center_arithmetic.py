#!/usr/bin/env python3
"""Search opened schemas 5 and 6 for one center-coefficient arithmetic law."""

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Iterable

import analyze_raster_tile_phase_arithmetic as arithmetic
import open_raster_tile_double_rounding_holdout as opening6
import open_raster_tile_translation_discriminator as opening5
import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v4 as v4
import validate_raster_tile_double_rounding_holdout as capture6
import validate_raster_tile_translation_discriminator as capture5


type JsonObject = dict[str, Any]
type SlopeModel = Callable[[object, object, int, tuple[int, ...]], Fraction]
type OffsetProvider = Callable[[object, object, int, int], Iterable[int]]

SEARCH_OFFSETS = tuple(range(-8, 9))
ROUNDING_MODES = ("nearest-even", "down", "up", "toward-zero", "away-zero")
CENTER_COMPONENT = capture6.PULL_COUNT
DERIVATIVE_COMPONENT = CENTER_COMPONENT + 1


@dataclass(frozen=True)
class Corpus:
    name: str
    capture: ModuleType
    opening: ModuleType
    root: Path


@dataclass(frozen=True)
class Setup:
    corpus: str
    capture_case: object
    endpoint: object
    axis: int
    base_bits: int
    accepted_bits: frozenset[int]
    accepted_offsets: tuple[int, ...]


def center_matches(
    samples: Iterable[object],
    actual_records: Iterable[tuple[int, ...]],
    constants: Iterable[int],
    *,
    slope_bits: int,
) -> bool:
    slope = v1.bits_float32(slope_bits)
    return all(
        actual[CENTER_COMPONENT:]
        == v2.predict_record_with_setup(
            sample,
            slope=slope,
            constant=v1.bits_float32(constant_bits),
        )[CENTER_COMPONENT:]
        for sample, actual, constant_bits in zip(
            samples,
            actual_records,
            constants,
            strict=True,
        )
    )


def recover_corpus(
    corpus: Corpus,
    *,
    additional_offsets: OffsetProvider | None = None,
    fallback_offsets: Iterable[int] = (),
    require_match: bool = True,
) -> list[Setup]:
    _, streams = corpus.opening.actual_case_streams(corpus.root)
    selector_table = v1.load_selector_table()
    setups: list[Setup] = []
    for capture_case in corpus.capture.CASES:
        samples = corpus.capture.sample_positions(capture_case)
        stream = streams[capture_case.name]
        offset = 0
        for endpoint in corpus.capture.ENDPOINTS:
            records = tuple(
                corpus.capture.RECORD.unpack_from(
                    stream,
                    offset + index * corpus.capture.RECORD.size,
                )
                for index in range(len(samples))
            )
            offset += len(samples) * corpus.capture.RECORD.size
            for axis in range(corpus.capture.AXIS_COUNT):
                axis_samples = tuple(
                    sample for sample in samples if sample.axis == axis
                )
                axis_records = tuple(
                    actual
                    for sample, actual in zip(samples, records, strict=True)
                    if sample.axis == axis
                )
                constants = tuple(
                    v4.selected_constant_bits(
                        capture_case,
                        endpoint,
                        sample,
                        selector_table=selector_table,
                    )[1]
                    for sample in axis_samples
                )
                base_bits = v4.determinant_slope(
                    capture_case,
                    endpoint,
                    axis=axis,
                    selector_table=selector_table,
                )[0]
                search_offsets = set(SEARCH_OFFSETS)
                if additional_offsets is not None:
                    search_offsets.update(
                        additional_offsets(
                            capture_case,
                            endpoint,
                            axis,
                            base_bits,
                        )
                    )
                accepted_offsets = tuple(
                    candidate
                    for candidate in sorted(search_offsets)
                    if center_matches(
                        axis_samples,
                        axis_records,
                        constants,
                        slope_bits=base_bits + candidate,
                    )
                )
                if not accepted_offsets:
                    accepted_offsets = tuple(
                        candidate
                        for candidate in fallback_offsets
                        if candidate not in search_offsets
                        and center_matches(
                            axis_samples,
                            axis_records,
                            constants,
                            slope_bits=base_bits + candidate,
                        )
                    )
                if not accepted_offsets and require_match:
                    raise ValueError(
                        f"{corpus.name}:{capture_case.name}:{endpoint.name}:"
                        f"{axis} has no center coefficient in the search window"
                    )
                setups.append(
                    Setup(
                        corpus=corpus.name,
                        capture_case=capture_case,
                        endpoint=endpoint,
                        axis=axis,
                        base_bits=base_bits,
                        accepted_bits=frozenset(
                            base_bits + candidate for candidate in accepted_offsets
                        ),
                        accepted_offsets=accepted_offsets,
                    )
                )
    return setups


def directed_float32_bits(value: Fraction, mode: str) -> int:
    nearest_bits = v1.round_fraction_to_float32_bits(value)
    nearest = v1.float32_bits_fraction(nearest_bits)
    if mode == "nearest-even" or nearest == value:
        return nearest_bits
    if mode == "down":
        if nearest > value:
            return nearest_bits + 1 if value < 0 else nearest_bits - 1
        return nearest_bits
    if mode == "up":
        if nearest < value:
            return nearest_bits - 1 if value < 0 else nearest_bits + 1
        return nearest_bits
    if mode == "toward-zero":
        return directed_float32_bits(value, "up" if value < 0 else "down")
    if mode == "away-zero":
        return directed_float32_bits(value, "down" if value < 0 else "up")
    raise ValueError(f"unknown binary32 rounding mode: {mode}")


def setup_identity(setup: Setup) -> JsonObject:
    capture_case = setup.capture_case
    endpoint = setup.endpoint
    extent = capture_case.width if setup.axis == 0 else capture_case.height
    origin = capture_case.originX if setup.axis == 0 else capture_case.originY
    return {
        "corpus": setup.corpus,
        "case": capture_case.name,
        "endpoint": endpoint.name,
        "axis": "x" if setup.axis == 0 else "y",
        "extent": extent,
        "origin": origin,
        "lowBits": f"0x{endpoint.lowBits:08x}",
        "highBits": f"0x{endpoint.highBits:08x}",
        "acceptedOffsetsFromDeterminant": list(setup.accepted_offsets),
    }


def informative_setup_metadata(
    setup: Setup,
    selector_table: tuple[int, ...],
) -> JsonObject:
    capture_case = setup.capture_case
    endpoint = setup.endpoint
    extent = capture_case.width if setup.axis == 0 else capture_case.height
    opposite = capture_case.height if setup.axis == 0 else capture_case.width
    delta = v1.float32_bits_fraction(endpoint.highBits) - v1.float32_bits_fraction(
        endpoint.lowBits
    )
    exact = delta / extent
    nearest_bits = v1.round_fraction_to_float32_bits(exact)
    down_bits = directed_float32_bits(exact, "down")
    _, phase, internal = v4.determinant_slope(
        capture_case,
        endpoint,
        axis=setup.axis,
        selector_table=selector_table,
    )
    return {
        **setup_identity(setup),
        "oppositeExtent": opposite,
        "determinant": extent * opposite,
        "originModuloTile": (
            capture_case.originX if setup.axis == 0 else capture_case.originY
        )
        % capture6.TILE_SIZE,
        "nativeSpan": abs(endpoint.highBits - endpoint.lowBits),
        "direction": "forward" if delta > 0 else "reverse",
        "reducedExactSlopeDenominator": exact.denominator,
        "p27Phase": str(phase),
        "exactNearestOffsetFromDeterminant": nearest_bits - setup.base_bits,
        "exactDownOffsetFromDeterminant": down_bits - setup.base_bits,
        "determinantInternalNumerator": Fraction.from_float(internal).numerator,
        "determinantInternalDenominator": Fraction.from_float(internal).denominator,
        "extentReciprocalIndex": v1.reciprocal_selector(extent, selector_table),
        "determinantReciprocalIndex": v1.reciprocal_selector(
            extent * opposite,
            selector_table,
        ),
    }


def evaluate_model(
    name: str,
    slope_model: SlopeModel,
    setups: list[Setup],
    selector_table: tuple[int, ...],
    *,
    failure_limit: int = 64,
) -> list[JsonObject]:
    matches: Counter[str] = Counter()
    matches_by_corpus: dict[str, Counter[str]] = {
        rounding: Counter() for rounding in ROUNDING_MODES
    }
    totals_by_corpus: Counter[str] = Counter()
    offsets: dict[str, Counter[int | None]] = {
        rounding: Counter() for rounding in ROUNDING_MODES
    }
    failures: dict[str, list[JsonObject]] = {
        rounding: [] for rounding in ROUNDING_MODES
    }
    for setup in setups:
        totals_by_corpus[setup.corpus] += 1
        try:
            slope = slope_model(
                setup.capture_case,
                setup.endpoint,
                setup.axis,
                selector_table,
            )
        except ValueError:
            slope = None
        for rounding in ROUNDING_MODES:
            if slope is None:
                bits = -1
                offset = None
            else:
                bits = directed_float32_bits(slope, rounding)
                offset = bits - setup.base_bits
            offsets[rounding][offset] += 1
            accepted = bits in setup.accepted_bits
            matches[rounding] += accepted
            matches_by_corpus[rounding][setup.corpus] += accepted
            if not accepted and len(failures[rounding]) < failure_limit:
                failures[rounding].append(
                    {
                        **setup_identity(setup),
                        "predictedOffsetFromDeterminant": offset,
                    }
                )
    return [
        {
            "name": f"{name}/{rounding}",
            "matchCount": matches[rounding],
            "setupCount": len(setups),
            "matchesByCorpus": {
                corpus: {
                    "matches": matches_by_corpus[rounding][corpus],
                    "setups": totals_by_corpus[corpus],
                }
                for corpus in sorted(totals_by_corpus)
            },
            "offsetDistribution": {
                str(offset): count
                for offset, count in sorted(
                    offsets[rounding].items(),
                    key=lambda item: (item[0] is None, item[0]),
                )
            },
            "firstFailures": failures[rounding],
        }
        for rounding in ROUNDING_MODES
    ]


def determinant_model(
    capture_case: object,
    endpoint: object,
    axis: int,
    selector_table: tuple[int, ...],
) -> Fraction:
    internal = v4.determinant_slope(
        capture_case,
        endpoint,
        axis=axis,
        selector_table=selector_table,
    )[2]
    return Fraction.from_float(internal)


def exact_quotient_model(
    capture_case: object,
    endpoint: object,
    axis: int,
    _: tuple[int, ...],
) -> Fraction:
    extent = capture_case.width if axis == 0 else capture_case.height
    return (
        v1.float32_bits_fraction(endpoint.highBits)
        - v1.float32_bits_fraction(endpoint.lowBits)
    ) / extent


def direct_extent_reciprocal_model(
    capture_case: object,
    endpoint: object,
    axis: int,
    selector_table: tuple[int, ...],
) -> Fraction:
    """Apply the measured reciprocal/product stage directly to the axis extent."""

    extent = capture_case.width if axis == 0 else capture_case.height
    delta = v1.float32_bits_fraction(endpoint.highBits) - v1.float32_bits_fraction(
        endpoint.lowBits
    )
    return arithmetic.reciprocal_product(delta, extent, selector_table)


def direct_extent_partial_model(
    input_bits: int,
    output_bits: int,
    truncation_bits: int,
    bias_units: int,
) -> SlopeModel:
    def model(
        capture_case: object,
        endpoint: object,
        axis: int,
        selector_table: tuple[int, ...],
    ) -> Fraction:
        extent = capture_case.width if axis == 0 else capture_case.height
        delta = v1.float32_bits_fraction(endpoint.highBits) - v1.float32_bits_fraction(
            endpoint.lowBits
        )
        sign = -1 if delta < 0 else 1
        significand, exponent = arithmetic.normalized_significand(
            abs(delta),
            input_bits,
        )
        reciprocal = v1.reciprocal_selector(extent, selector_table)
        reciprocal_exponent = -(extent - 1).bit_length() - 24
        coefficient, coefficient_exponent = v1.product_stage(
            significand,
            exponent,
            reciprocal,
            reciprocal_exponent,
            output_bits=output_bits,
            truncation_bits=truncation_bits,
            bias_units=bias_units,
        )
        return sign * coefficient * v1.power_of_two(coefficient_exponent)

    return model


def direct_extent_model_matrix() -> dict[str, SlopeModel]:
    return {
        f"direct-extent-i{input_bits}-p{output_bits}-t{truncation_bits}-b{bias_units}": (
            direct_extent_partial_model(
                input_bits,
                output_bits,
                truncation_bits,
                bias_units,
            )
        )
        for input_bits in (24, 27)
        for output_bits in range(25, 31)
        for truncation_bits in (8, 12, 16, 19)
        for bias_units in range(32)
    }


def analyze(corpora: tuple[Corpus, ...]) -> JsonObject:
    setups = [setup for corpus in corpora for setup in recover_corpus(corpus)]
    translated = [
        setup
        for setup in setups
        if setup.endpoint.lowBits != 0 and setup.endpoint.highBits != 0
    ]
    selector_table = v1.load_selector_table()
    models: dict[str, SlopeModel] = {
        "direct-extent-reciprocal": direct_extent_reciprocal_model,
        "determinant-internal": determinant_model,
        "exact-quotient": exact_quotient_model,
        **arithmetic.model_matrix(),
    }
    candidates = [
        candidate
        for name, slope_model in models.items()
        for candidate in evaluate_model(
            name,
            slope_model,
            translated,
            selector_table,
        )
    ]
    candidates.sort(key=lambda value: (-int(value["matchCount"]), str(value["name"])))
    best_match_count = int(candidates[0]["matchCount"])
    signatures = Counter(setup.accepted_offsets for setup in translated)
    return {
        "rasterTileCenterArithmeticRecoverySchemaVersion": 1,
        "openedCalibrationOnly": True,
        "prospectiveEvidence": False,
        "productionShaderAuthorized": False,
        "corpora": [
            {"name": corpus.name, "root": str(corpus.root)} for corpus in corpora
        ],
        "setupCount": len(setups),
        "translatedSetupCount": len(translated),
        "acceptedOffsetSignatures": {
            ",".join(map(str, signature)): count
            for signature, count in sorted(signatures.items())
        },
        "candidateCount": len(candidates),
        "bestMatchCount": best_match_count,
        "bestCandidates": [
            candidate
            for candidate in candidates
            if candidate["matchCount"] == best_match_count
        ],
        "allCandidates": candidates,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("schema5_root", type=Path)
    parser.add_argument("schema6_root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    report = analyze(
        (
            Corpus("schema5", capture5, opening5, arguments.schema5_root),
            Corpus("schema6", capture6, opening6, arguments.schema6_root),
        )
    )
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
