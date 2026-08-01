#!/usr/bin/env python3
"""Replay the schema-8 p27 model against opened schemas 5, 6, and 7."""

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import open_raster_tile_center_origin_holdout as opening7
import open_raster_tile_double_rounding_holdout as opening6
import open_raster_tile_translation_discriminator as opening5
import raster_tile_selector_model as v1
import raster_tile_selector_model_v6 as model
import validate_raster_tile_center_origin_holdout as capture7
import validate_raster_tile_double_rounding_holdout as capture6
import validate_raster_tile_translation_discriminator as capture5


type JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True, kw_only=True)
class Corpus:
    name: str
    capture: ModuleType
    opening: ModuleType
    root: Path


def compare_corpus(
    corpus: Corpus,
    selector_table: tuple[int, ...],
) -> JsonObject:
    validation, actual_streams = corpus.opening.actual_case_streams(corpus.root)
    totals: Counter[str] = Counter()
    cases: list[JsonObject] = []
    for capture_case in corpus.capture.CASES:
        actual = actual_streams[capture_case.name]
        predicted = model.case_stream(
            corpus.capture,
            capture_case,
            selector_table,
        )
        if len(actual) != len(predicted) or len(actual) % corpus.capture.RECORD.size:
            raise ValueError(f"{corpus.name}/{capture_case.name} stream length differs")
        record_mismatches = 0
        word_mismatches = 0
        for offset in range(0, len(actual), corpus.capture.RECORD.size):
            actual_record = corpus.capture.RECORD.unpack_from(actual, offset)
            predicted_record = corpus.capture.RECORD.unpack_from(predicted, offset)
            changed = sum(
                left != right
                for left, right in zip(actual_record, predicted_record, strict=True)
            )
            record_mismatches += changed != 0
            word_mismatches += changed
        record_count = len(actual) // corpus.capture.RECORD.size
        totals["records"] += record_count
        totals["words"] += record_count * corpus.capture.RECORD_COMPONENT_COUNT
        totals["recordMismatches"] += record_mismatches
        totals["wordMismatches"] += word_mismatches
        cases.append(
            {
                "name": capture_case.name,
                "recordCount": record_count,
                "recordMismatchCount": record_mismatches,
                "wordMismatchCount": word_mismatches,
                "exact": word_mismatches == 0,
            }
        )
    return {
        "name": corpus.name,
        "source": str(corpus.root),
        "sourceRawSha256": validation["rawSha256"],
        "recordCount": totals["records"],
        "wordCount": totals["words"],
        "recordMismatchCount": totals["recordMismatches"],
        "wordMismatchCount": totals["wordMismatches"],
        "exact": totals["wordMismatches"] == 0,
        "cases": cases,
    }


def replay(corpora: tuple[Corpus, ...]) -> JsonObject:
    selector_table = v1.load_selector_table()
    reports = [compare_corpus(corpus, selector_table) for corpus in corpora]
    record_count = sum(int(report["recordCount"]) for report in reports)
    word_count = sum(int(report["wordCount"]) for report in reports)
    record_mismatches = sum(
        int(report["recordMismatchCount"]) for report in reports
    )
    word_mismatches = sum(int(report["wordMismatchCount"]) for report in reports)
    return {
        "rasterTileCenterLatticeRetrospectiveReplaySchemaVersion": 1,
        "openedCalibrationOnly": True,
        "prospectiveEvidence": False,
        "productionShaderAuthorized": False,
        "recordCount": record_count,
        "wordCount": word_count,
        "recordMismatchCount": record_mismatches,
        "wordMismatchCount": word_mismatches,
        "exact": word_mismatches == 0,
        "corpora": reports,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("schema5_root", type=Path)
    parser.add_argument("schema6_root", type=Path)
    parser.add_argument("schema7_root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    report = replay(
        (
            Corpus(
                name="schema5",
                capture=capture5,
                opening=opening5,
                root=arguments.schema5_root,
            ),
            Corpus(
                name="schema6",
                capture=capture6,
                opening=opening6,
                root=arguments.schema6_root,
            ),
            Corpus(
                name="schema7",
                capture=capture7,
                opening=opening7,
                root=arguments.schema7_root,
            ),
        )
    )
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not report["exact"]:
        raise SystemExit("retrospective p27 replay differs")


if __name__ == "__main__":
    main()
