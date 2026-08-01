#!/usr/bin/env python3
"""Classify opened schema-7 center coefficients against arithmetic laws."""

import argparse
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

import open_raster_tile_center_origin_holdout as opening
import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v5 as v5
import recover_raster_tile_center_arithmetic as recovery
import validate_raster_tile_center_origin_holdout as capture


type JsonObject = dict[str, Any]
type CoefficientLaw = Callable[[object, object, int, int], int]


def exact_slope(capture_case: object, endpoint: object, axis: int) -> Fraction:
    extent = capture_case.width if axis == 0 else capture_case.height
    return (
        v1.float32_bits_fraction(endpoint.highBits)
        - v1.float32_bits_fraction(endpoint.lowBits)
    ) / extent


def rounded_exact_law(mode: str) -> CoefficientLaw:
    def law(
        capture_case: object,
        endpoint: object,
        axis: int,
        base_bits: int,
    ) -> int:
        if endpoint.lowBits == 0 or endpoint.highBits == 0:
            return base_bits
        return recovery.directed_float32_bits(
            exact_slope(capture_case, endpoint, axis),
            mode,
        )

    return law


def v5_law(
    capture_case: object,
    endpoint: object,
    axis: int,
    base_bits: int,
) -> int:
    if endpoint.lowBits == 0 or endpoint.highBits == 0:
        return base_bits
    origin = capture_case.originX if axis == 0 else capture_case.originY
    if origin % capture.TILE_SIZE == capture.TILE_SIZE // 2:
        return base_bits
    return v5.round_fraction_to_float32_down_bits(
        exact_slope(capture_case, endpoint, axis)
    )


def determinant_law(
    _: object,
    __: object,
    ___: int,
    base_bits: int,
) -> int:
    return base_bits


LAWS: dict[str, CoefficientLaw] = {
    "v5": v5_law,
    "determinant-nearest": determinant_law,
    **{
        f"exact-quotient-{mode}": rounded_exact_law(mode)
        for mode in recovery.ROUNDING_MODES
    },
}

RECOVERY_FALLBACK_OFFSETS = tuple(range(-64, 65))


def law_offsets(
    capture_case: object,
    endpoint: object,
    axis: int,
    base_bits: int,
) -> set[int]:
    return {
        law(capture_case, endpoint, axis, base_bits) - base_bits
        for law in LAWS.values()
    }


def setup_metadata(
    setup: recovery.Setup,
    selector_table: tuple[int, ...],
) -> JsonObject:
    metadata = recovery.informative_setup_metadata(setup, selector_table)
    lower_bits = min(setup.endpoint.lowBits, setup.endpoint.highBits)
    predicted_bits = {
        name: law(
            setup.capture_case,
            setup.endpoint,
            setup.axis,
            setup.base_bits,
        )
        for name, law in LAWS.items()
    }
    matches = {
        name: bits in setup.accepted_bits for name, bits in predicted_bits.items()
    }
    base_matches = matches["determinant-nearest"]
    down_matches = matches["exact-quotient-down"]
    if base_matches and down_matches:
        observed_class = "determinant-and-exact-down-ambiguous"
    elif base_matches:
        observed_class = "determinant-only"
    elif down_matches:
        observed_class = "exact-down-only"
    else:
        observed_class = "neither-determinant-nor-exact-down"
    return {
        **metadata,
        "lowerEndpointBits": f"0x{lower_bits:08x}",
        "lowerEndpointResidue32": lower_bits % 32,
        "observedClass": observed_class,
        "candidateOffsetsFromDeterminant": {
            name: bits - setup.base_bits for name, bits in predicted_bits.items()
        },
        "candidateMatches": matches,
    }


def evaluate_word_errors(root: Path) -> JsonObject:
    _, streams = opening.actual_case_streams(root)
    selector_table = v1.load_selector_table()
    totals: dict[str, Counter[str]] = {name: Counter() for name in LAWS}
    by_case: dict[str, dict[str, Counter[str]]] = {
        name: {} for name in LAWS
    }
    for capture_case in capture.CASES:
        samples = capture.sample_positions(capture_case)
        stream = streams[capture_case.name]
        offset = 0
        for endpoint in capture.ENDPOINTS:
            for sample in samples:
                actual = capture.RECORD.unpack_from(stream, offset)
                offset += capture.RECORD.size
                base_bits = v4.determinant_slope(
                    capture_case,
                    endpoint,
                    axis=sample.axis,
                    selector_table=selector_table,
                )[0]
                _, constant_bits = v4.selected_constant_bits(
                    capture_case,
                    endpoint,
                    sample,
                    selector_table=selector_table,
                )
                for name, law in LAWS.items():
                    slope_bits = law(
                        capture_case,
                        endpoint,
                        sample.axis,
                        base_bits,
                    )
                    predicted = v2.predict_record_with_setup(
                        sample,
                        slope=v1.bits_float32(slope_bits),
                        constant=v1.bits_float32(constant_bits),
                    )
                    differing = tuple(
                        index
                        for index in range(capture.PULL_COUNT, len(actual))
                        if actual[index] != predicted[index]
                    )
                    counter = totals[name]
                    case_counter = by_case[name].setdefault(
                        capture_case.name,
                        Counter(),
                    )
                    counter["records"] += 1
                    case_counter["records"] += 1
                    if not differing:
                        continue
                    counter["recordMismatches"] += 1
                    counter["wordMismatches"] += len(differing)
                    case_counter["recordMismatches"] += 1
                    case_counter["wordMismatches"] += len(differing)
                    for index in differing:
                        component = (
                            "center"
                            if index == capture.PULL_COUNT
                            else "axisDerivative"
                        )
                        counter[f"{component}Mismatches"] += 1
                        case_counter[f"{component}Mismatches"] += 1
    return {
        name: {
            **dict(counter),
            "cases": {
                case: dict(case_counter)
                for case, case_counter in case_counters.items()
                if case_counter["wordMismatches"]
            },
        }
        for name, counter in totals.items()
        for case_counters in (by_case[name],)
    }


def analyze(root: Path) -> JsonObject:
    corpus = recovery.Corpus("schema7", capture, opening, root)
    setups = recovery.recover_corpus(
        corpus,
        additional_offsets=law_offsets,
        fallback_offsets=RECOVERY_FALLBACK_OFFSETS,
        require_match=False,
    )
    translated = [
        setup
        for setup in setups
        if setup.endpoint.lowBits != 0 and setup.endpoint.highBits != 0
    ]
    selector_table = v1.load_selector_table()
    metadata = [setup_metadata(setup, selector_table) for setup in translated]

    matches_by_law: dict[str, Counter[str]] = {
        name: Counter() for name in LAWS
    }
    observed_classes: Counter[str] = Counter()
    accepted_signatures: Counter[tuple[int, ...]] = Counter()
    for setup, item in zip(translated, metadata, strict=True):
        observed_classes[str(item["observedClass"])] += 1
        accepted_signatures[setup.accepted_offsets] += 1
        for name, matched in item["candidateMatches"].items():
            matches_by_law[name]["matches"] += bool(matched)
            matches_by_law[name]["failures"] += not bool(matched)

    discriminating = [
        item
        for item in metadata
        if len(set(item["candidateOffsetsFromDeterminant"].values())) > 1
        and len(set(item["candidateMatches"].values())) > 1
    ]
    failures = {
        name: [
            item
            for item in metadata
            if not bool(item["candidateMatches"][name])
        ]
        for name in LAWS
    }
    return {
        "rasterTileCenterOriginOpenedAnalysisSchemaVersion": 1,
        "openedCalibrationOnly": True,
        "prospectiveEvidence": False,
        "productionShaderAuthorized": False,
        "source": str(root),
        "setupCount": len(setups),
        "translatedSetupCount": len(translated),
        "observedClassCounts": dict(sorted(observed_classes.items())),
        "acceptedOffsetSignatures": {
            ",".join(map(str, signature)): count
            for signature, count in sorted(accepted_signatures.items())
        },
        "coefficientLawResults": {
            name: dict(counter) for name, counter in matches_by_law.items()
        },
        "centerWordErrorResults": evaluate_word_errors(root),
        "discriminatingSetupCount": len(discriminating),
        "discriminatingSetups": discriminating,
        "failuresByLaw": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    report = analyze(arguments.root)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
