#!/usr/bin/env python3
"""Recover the signed p27 center-coefficient selector from opened schemas 5-7."""

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from types import ModuleType
from typing import Any

import open_raster_tile_center_origin_holdout as opening7
import open_raster_tile_double_rounding_holdout as opening6
import open_raster_tile_translation_discriminator as opening5
import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v4 as v4
import validate_raster_tile_center_origin_holdout as capture7
import validate_raster_tile_double_rounding_holdout as capture6
import validate_raster_tile_translation_discriminator as capture5


type JsonObject = dict[str, Any]

PRECISION_BITS = 27
ACTIONS = (-2, -1, 0, 1, 2)


@dataclass(frozen=True)
class Corpus:
    name: str
    capture: ModuleType
    opening: ModuleType
    root: Path


def fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def signed_lattice(value: Fraction) -> tuple[Fraction, Fraction, Fraction]:
    magnitude = abs(value)
    exponent = v1.floor_binary_exponent(magnitude)
    step = v1.power_of_two(exponent - PRECISION_BITS + 1)
    scaled = value / step
    floor_index = scaled.numerator // scaled.denominator
    floor_value = floor_index * step
    magnitude_index = int(magnitude / step)
    phase = (magnitude - magnitude_index * step) / step
    return floor_value, step, phase


def analyze_corpus(
    corpus: Corpus,
    selector_table: tuple[int, ...],
) -> tuple[JsonObject, list[JsonObject]]:
    validation, streams = corpus.opening.actual_case_streams(corpus.root)
    capture = corpus.capture
    reports: list[JsonObject] = []
    accepted_counts: Counter[str] = Counter()
    for capture_case in capture.CASES:
        samples = capture.sample_positions(capture_case)
        stream = streams[capture_case.name]
        offset = 0
        for endpoint in capture.ENDPOINTS:
            records = tuple(
                capture.RECORD.unpack_from(
                    stream,
                    offset + index * capture.RECORD.size,
                )
                for index in range(len(samples))
            )
            offset += len(samples) * capture.RECORD.size
            if endpoint.lowBits == 0 or endpoint.highBits == 0:
                continue
            for axis in range(capture.AXIS_COUNT):
                extent = capture_case.width if axis == 0 else capture_case.height
                origin = capture_case.originX if axis == 0 else capture_case.originY
                opposite = (
                    capture_case.height if axis == 0 else capture_case.width
                )
                delta = v1.float32_bits_fraction(
                    endpoint.highBits
                ) - v1.float32_bits_fraction(endpoint.lowBits)
                floor_value, step, phase = signed_lattice(delta / extent)
                word_errors: dict[int, int] = {}
                for action in ACTIONS:
                    slope = float(floor_value + action * step)
                    errors = 0
                    for sample, actual in zip(samples, records, strict=True):
                        if sample.axis != axis:
                            continue
                        _, constant_bits = v4.selected_constant_bits(
                            capture_case,
                            endpoint,
                            sample,
                            selector_table=selector_table,
                        )
                        predicted = v2.predict_record_with_setup(
                            sample,
                            slope=slope,
                            constant=v1.bits_float32(constant_bits),
                        )
                        errors += sum(
                            actual[index] != predicted[index]
                            for index in range(
                                capture.PULL_COUNT,
                                capture.RECORD_COMPONENT_COUNT,
                            )
                        )
                    word_errors[action] = errors
                accepted = tuple(
                    action for action, errors in word_errors.items() if errors == 0
                )
                accepted_counts[",".join(map(str, accepted))] += 1
                if len(accepted) == len(ACTIONS):
                    continue
                lower_bits = min(endpoint.lowBits, endpoint.highBits)
                reports.append(
                    {
                        "corpus": corpus.name,
                        "case": capture_case.name,
                        "endpoint": endpoint.name,
                        "axis": "x" if axis == 0 else "y",
                        "extent": extent,
                        "oppositeExtent": opposite,
                        "determinant": extent * opposite,
                        "origin": origin,
                        "originModuloTile": origin % capture.TILE_SIZE,
                        "direction": "forward" if delta > 0 else "reverse",
                        "nativeSpan": abs(endpoint.highBits - endpoint.lowBits),
                        "lowerEndpointBits": f"0x{lower_bits:08x}",
                        "lowerEndpointResidue32": lower_bits % 32,
                        "p27Phase": fraction_text(phase),
                        "acceptedSignedFloorOffsets": list(accepted),
                        "wordErrorsBySignedFloorOffset": {
                            str(action): errors
                            for action, errors in word_errors.items()
                        },
                    }
                )
    return (
        {
            "name": corpus.name,
            "source": str(corpus.root),
            "sourceRawSha256": validation["rawSha256"],
            "acceptedSignatureCounts": dict(sorted(accepted_counts.items())),
        },
        reports,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("schema5_root", type=Path)
    parser.add_argument("schema6_root", type=Path)
    parser.add_argument("schema7_root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    corpora = (
        Corpus("schema5", capture5, opening5, arguments.schema5_root),
        Corpus("schema6", capture6, opening6, arguments.schema6_root),
        Corpus("schema7", capture7, opening7, arguments.schema7_root),
    )
    selector_table = v1.load_selector_table()
    results = [analyze_corpus(corpus, selector_table) for corpus in corpora]
    setups = [setup for _, reports in results for setup in reports]
    report = {
        "rasterTileCenterLatticeRecoverySchemaVersion": 1,
        "openedCalibrationOnly": True,
        "prospectiveEvidence": False,
        "productionShaderAuthorized": False,
        "precisionBits": PRECISION_BITS,
        "testedSignedFloorOffsets": list(ACTIONS),
        "corpora": [summary for summary, _ in results],
        "informativeSetupCount": len(setups),
        "informativeSetups": setups,
    }
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
