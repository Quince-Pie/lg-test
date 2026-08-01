#!/usr/bin/env python3
"""Replay the post-opening v5 model over schemas 5 and 6 without tolerance."""

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import open_raster_tile_double_rounding_holdout as opening6
import open_raster_tile_translation_discriminator as opening5
import raster_tile_selector_model as v1
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v5 as model
import validate_raster_tile_double_rounding_holdout as capture6
import validate_raster_tile_translation_discriminator as capture5


type JsonObject = dict[str, Any]


@dataclass(frozen=True)
class Corpus:
    name: str
    capture: ModuleType
    opening: ModuleType
    root: Path


def analyze_corpus(corpus: Corpus) -> JsonObject:
    validation, streams = corpus.opening.actual_case_streams(corpus.root)
    selector_table = v1.load_selector_table()
    component_names = (
        *(f"pull@{value}/16" for value in corpus.capture.PULL_NUMERATORS),
        "center",
        "axis-derivative(center)",
    )
    records = 0
    record_mismatches = 0
    word_mismatches = 0
    component_mismatches: Counter[str] = Counter()
    mismatches_by_role: Counter[str] = Counter()
    pull_selectors: Counter[str] = Counter()
    center_selectors: Counter[str] = Counter()
    constant_selectors: Counter[str] = Counter()
    seen_slopes: set[tuple[str, str, int]] = set()
    seen_constants: set[tuple[str, str, int, int, int]] = set()

    for capture_case in corpus.capture.CASES:
        samples = corpus.capture.sample_positions(capture_case)
        stream = streams[capture_case.name]
        offset = 0
        for endpoint in corpus.capture.ENDPOINTS:
            for sample in samples:
                actual = corpus.capture.RECORD.unpack_from(stream, offset)
                offset += corpus.capture.RECORD.size
                predicted = model.predict_record(
                    capture_case,
                    endpoint,
                    sample,
                    selector_table,
                )
                pull_name, _, center_name, _, _, _ = model.selected_slope_bits(
                    capture_case,
                    endpoint,
                    axis=sample.axis,
                    selector_table=selector_table,
                )
                constant_name, _ = v4.selected_constant_bits(
                    capture_case,
                    endpoint,
                    sample,
                    selector_table=selector_table,
                )
                slope_key = (capture_case.name, endpoint.name, sample.axis)
                if slope_key not in seen_slopes:
                    pull_selectors[pull_name] += 1
                    center_selectors[center_name] += 1
                    seen_slopes.add(slope_key)
                constant_key = (
                    capture_case.name,
                    endpoint.name,
                    sample.axis,
                    sample.primitive,
                    sample.tile,
                )
                if constant_key not in seen_constants:
                    constant_selectors[constant_name] += 1
                    seen_constants.add(constant_key)

                differing = tuple(
                    index
                    for index, (left, right) in enumerate(
                        zip(predicted, actual, strict=True)
                    )
                    if left != right
                )
                records += 1
                if not differing:
                    continue
                record_mismatches += 1
                word_mismatches += len(differing)
                mismatches_by_role[capture_case.role] += len(differing)
                component_mismatches.update(
                    component_names[index] for index in differing
                )

    return {
        "name": corpus.name,
        "source": str(corpus.root),
        "sourceRawSha256": validation["rawSha256"],
        "recordCount": records,
        "wordCount": records * corpus.capture.RECORD_COMPONENT_COUNT,
        "recordMismatchCount": record_mismatches,
        "wordMismatchCount": word_mismatches,
        "wordMismatchesByRole": dict(sorted(mismatches_by_role.items())),
        "componentMismatchCounts": dict(sorted(component_mismatches.items())),
        "pullSelectorCounts": dict(sorted(pull_selectors.items())),
        "centerSelectorCounts": dict(sorted(center_selectors.items())),
        "constantSelectorCounts": dict(sorted(constant_selectors.items())),
        "exact": word_mismatches == 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("schema5_root", type=Path)
    parser.add_argument("schema6_root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    corpora = (
        Corpus("schema5", capture5, opening5, arguments.schema5_root),
        Corpus("schema6", capture6, opening6, arguments.schema6_root),
    )
    reports = [analyze_corpus(corpus) for corpus in corpora]
    report = {
        "rasterTileOpenedV5AnalysisSchemaVersion": 1,
        "openedCalibrationOnly": True,
        "prospectiveEvidence": False,
        "productionShaderAuthorized": False,
        "corpora": reports,
        "recordCount": sum(value["recordCount"] for value in reports),
        "wordCount": sum(value["wordCount"] for value in reports),
        "recordMismatchCount": sum(value["recordMismatchCount"] for value in reports),
        "wordMismatchCount": sum(value["wordMismatchCount"] for value in reports),
        "exact": all(value["exact"] for value in reports),
    }
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not report["exact"]:
        raise SystemExit("post-opening v5 replay differs")


if __name__ == "__main__":
    main()
