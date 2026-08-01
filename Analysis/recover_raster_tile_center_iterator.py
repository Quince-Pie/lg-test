#!/usr/bin/env python3
"""Recover per-sample center-iterator decisions from opened schemas 5-7."""

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
import raster_tile_selector_model_v5 as v5
import validate_raster_tile_center_origin_holdout as capture7
import validate_raster_tile_double_rounding_holdout as capture6
import validate_raster_tile_translation_discriminator as capture5


type JsonObject = dict[str, Any]


@dataclass(frozen=True)
class Corpus:
    name: str
    capture: ModuleType
    opening: ModuleType
    root: Path


def fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def classification_metadata(
    corpus: Corpus,
    capture_case: object,
    endpoint: object,
    sample: object,
    actual: tuple[int, ...],
    base_bits: int,
    down_bits: int,
    base_record: tuple[int, ...],
    down_record: tuple[int, ...],
    phase: Fraction,
    internal: float,
    constant_bits: int,
    classification: str,
) -> JsonObject:
    capture = corpus.capture
    axis = sample.axis
    extent = capture_case.width if axis == 0 else capture_case.height
    opposite = capture_case.height if axis == 0 else capture_case.width
    origin = capture_case.originX if axis == 0 else capture_case.originY
    coordinate = sample.x if axis == 0 else sample.y
    tile_origin = sample.tile * capture.TILE_SIZE
    low = v1.float32_bits_fraction(endpoint.lowBits)
    high = v1.float32_bits_fraction(endpoint.highBits)
    delta = high - low
    exact_constant = low + delta * Fraction(tile_origin - origin, extent)
    internal_constant = v1.quantize_binary_significand(
        abs(exact_constant),
        v4.CONSTANT_INTERNAL_PRECISION_BITS,
        rounding="nearest-even",
    )
    if exact_constant < 0:
        internal_constant = -internal_constant
    exact_center = low + delta * Fraction(2 * (coordinate - origin) + 1, 2 * extent)
    center_index = capture.PULL_COUNT
    derivative_index = center_index + 1
    lower_bits = min(endpoint.lowBits, endpoint.highBits)
    return {
        "corpus": corpus.name,
        "case": capture_case.name,
        "endpoint": endpoint.name,
        "axis": "x" if axis == 0 else "y",
        "primitive": sample.primitive,
        "tile": sample.tile,
        "edge": sample.edge,
        "coordinate": coordinate,
        "extent": extent,
        "oppositeExtent": opposite,
        "determinant": extent * opposite,
        "origin": origin,
        "originModuloTile": origin % capture.TILE_SIZE,
        "positionFromOrigin": coordinate - origin,
        "positionFromFarEdge": origin + extent - 1 - coordinate,
        "tileLocalPixel": coordinate - tile_origin,
        "tileOriginDisplacement": tile_origin - origin,
        "firstGeometryPixel": coordinate == origin,
        "lastGeometryPixel": coordinate == origin + extent - 1,
        "firstGeometryTile": sample.tile == origin // capture.TILE_SIZE,
        "lastGeometryTile": sample.tile
        == (origin + extent - 1) // capture.TILE_SIZE,
        "direction": "forward" if delta > 0 else "reverse",
        "nativeSpan": abs(endpoint.highBits - endpoint.lowBits),
        "lowerEndpointBits": f"0x{lower_bits:08x}",
        "lowerEndpointResidue32": lower_bits % 32,
        "p27Phase": fraction_text(phase),
        "determinantBits": f"0x{base_bits:08x}",
        "exactDownBits": f"0x{down_bits:08x}",
        "exactDownOffsetFromDeterminant": down_bits - base_bits,
        "determinantInternal": fraction_text(Fraction.from_float(internal)),
        "exactSlope": fraction_text(delta / extent),
        "constantBits": f"0x{constant_bits:08x}",
        "constantInternalP28": fraction_text(internal_constant),
        "constantExact": fraction_text(exact_constant),
        "centerExact": fraction_text(exact_center),
        "actualCenterBits": f"0x{actual[center_index]:08x}",
        "actualDerivativeBits": f"0x{actual[derivative_index]:08x}",
        "determinantCenterBits": f"0x{base_record[center_index]:08x}",
        "determinantDerivativeBits": f"0x{base_record[derivative_index]:08x}",
        "exactDownCenterBits": f"0x{down_record[center_index]:08x}",
        "exactDownDerivativeBits": f"0x{down_record[derivative_index]:08x}",
        "classification": classification,
    }


def analyze_corpus(
    corpus: Corpus,
    selector_table: tuple[int, ...],
) -> tuple[JsonObject, list[JsonObject]]:
    validation, streams = corpus.opening.actual_case_streams(corpus.root)
    capture = corpus.capture
    classes: Counter[str] = Counter()
    classes_by_case: dict[str, Counter[str]] = {}
    decisive: list[JsonObject] = []
    for capture_case in capture.CASES:
        case_classes: Counter[str] = Counter()
        classes_by_case[capture_case.name] = case_classes
        samples = capture.sample_positions(capture_case)
        stream = streams[capture_case.name]
        offset = 0
        for endpoint in capture.ENDPOINTS:
            setups: dict[int, tuple[int, int, Fraction, float]] = {}
            for axis in range(capture.AXIS_COUNT):
                extent = capture_case.width if axis == 0 else capture_case.height
                base_bits, phase, internal = v4.determinant_slope(
                    capture_case,
                    endpoint,
                    axis=axis,
                    selector_table=selector_table,
                )
                delta = v1.float32_bits_fraction(
                    endpoint.highBits
                ) - v1.float32_bits_fraction(endpoint.lowBits)
                down_bits = v5.round_fraction_to_float32_down_bits(delta / extent)
                setups[axis] = base_bits, down_bits, phase, internal
            for sample in samples:
                actual = capture.RECORD.unpack_from(stream, offset)
                offset += capture.RECORD.size
                if endpoint.lowBits == 0 or endpoint.highBits == 0:
                    continue
                base_bits, down_bits, phase, internal = setups[sample.axis]
                _, constant_bits = v4.selected_constant_bits(
                    capture_case,
                    endpoint,
                    sample,
                    selector_table=selector_table,
                )
                base_record = v2.predict_record_with_setup(
                    sample,
                    slope=v1.bits_float32(base_bits),
                    constant=v1.bits_float32(constant_bits),
                )
                down_record = v2.predict_record_with_setup(
                    sample,
                    slope=v1.bits_float32(down_bits),
                    constant=v1.bits_float32(constant_bits),
                )
                center_slice = slice(capture.PULL_COUNT, capture.RECORD_COMPONENT_COUNT)
                base_matches = actual[center_slice] == base_record[center_slice]
                down_matches = actual[center_slice] == down_record[center_slice]
                if base_matches and down_matches:
                    classification = "ambiguous"
                elif base_matches:
                    classification = "determinant-only"
                elif down_matches:
                    classification = "exact-down-only"
                else:
                    classification = "neither"
                classes[classification] += 1
                case_classes[classification] += 1
                if classification != "ambiguous":
                    decisive.append(
                        classification_metadata(
                            corpus,
                            capture_case,
                            endpoint,
                            sample,
                            actual,
                            base_bits,
                            down_bits,
                            base_record,
                            down_record,
                            phase,
                            internal,
                            constant_bits,
                            classification,
                        )
                    )
    return (
        {
            "name": corpus.name,
            "source": str(corpus.root),
            "sourceRawSha256": validation["rawSha256"],
            "classificationCounts": dict(sorted(classes.items())),
            "classificationCountsByCase": {
                name: dict(sorted(counter.items()))
                for name, counter in classes_by_case.items()
                if counter["determinant-only"]
                or counter["exact-down-only"]
                or counter["neither"]
            },
        },
        decisive,
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
    decisive = [record for _, records in results for record in records]
    report = {
        "rasterTileCenterIteratorRecoverySchemaVersion": 1,
        "openedCalibrationOnly": True,
        "prospectiveEvidence": False,
        "productionShaderAuthorized": False,
        "corpora": [summary for summary, _ in results],
        "decisiveRecordCount": len(decisive),
        "decisiveRecords": decisive,
    }
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
