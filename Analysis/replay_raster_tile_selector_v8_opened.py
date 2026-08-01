#!/usr/bin/env python3
"""Replay the v8 tile-center model over opened schema-5 through schema-9 captures."""

import argparse
import importlib
import json
import mmap
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any

import raster_tile_selector_model as v1
import raster_tile_selector_model_v8 as model


type JsonObject = dict[str, Any]

SCHEMAS = (
    (
        5,
        "validate_raster_tile_translation_discriminator",
        "3cd6a35830a3d71af0252b87bce94e97917fdd68234805216d432b0bedbc1cc3",
    ),
    (
        6,
        "validate_raster_tile_double_rounding_holdout",
        "3b84d1376edc4d354672ff6367a9a66437ba23425342218f3c87952537e92665",
    ),
    (
        7,
        "validate_raster_tile_center_origin_holdout",
        "0e20ff958ea6ce7326adb8dc0f9d3945bfb984dea010a0ff23a707a16c4d826c",
    ),
    (
        8,
        "validate_raster_tile_center_lattice_holdout",
        "7550032284d1570684efa2201de8a8bfabfb0254a8d130774b6e781ddde7d395",
    ),
    (
        9,
        "validate_raster_tile_center_scale_holdout",
        "61b63ec92eec0ce4d203ea366825652513973b9e2ef7d7fc3b22e3552acae5a0",
    ),
)


def replay_schema(
    schema: int,
    capture: ModuleType,
    root: Path,
    expected_raw_sha256: str,
) -> JsonObject:
    validation = capture.validate(root)
    if validation["rawSha256"] != expected_raw_sha256:
        raise ValueError(f"schema-{schema} raw capture hash differs")
    manifest: JsonObject = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    raw_path = root / str(manifest["rasterTileNumerator"]["file"])
    selector_table = v1.load_selector_table()
    records = 0
    word_mismatches = 0
    record_mismatches = 0
    mismatches_by_component: Counter[int] = Counter()
    mismatches_by_case: Counter[str] = Counter()
    mismatches_by_endpoint: Counter[str] = Counter()
    with (
        raw_path.open("rb") as stream,
        mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as raw,
    ):
        for case_index, capture_case in enumerate(capture.CASES):
            for endpoint_index, endpoint in enumerate(capture.ENDPOINTS):
                for sample in capture.sample_positions(capture_case):
                    record_index = (
                        case_index * len(capture.ENDPOINTS) + endpoint_index
                    ) * capture.SLOT_COUNT + sample.slot
                    actual = capture.RECORD.unpack_from(
                        raw,
                        record_index * capture.RECORD.size,
                    )
                    predicted = model.predict_record(
                        capture_case,
                        endpoint,
                        sample,
                        selector_table,
                    )
                    differing = [
                        index
                        for index, (actual_word, predicted_word) in enumerate(
                            zip(actual, predicted, strict=True)
                        )
                        if actual_word != predicted_word
                    ]
                    records += 1
                    if differing:
                        record_mismatches += 1
                        word_mismatches += len(differing)
                        mismatches_by_component.update(differing)
                        mismatches_by_case[capture_case.name] += len(differing)
                        mismatches_by_endpoint[endpoint.name] += len(differing)
    return {
        "schemaVersion": schema,
        "source": str(root),
        "rawSha256": validation["rawSha256"],
        "recordCount": records,
        "wordCount": records * capture.RECORD_COMPONENT_COUNT,
        "recordMismatchCount": record_mismatches,
        "wordMismatchCount": word_mismatches,
        "wordMismatchesByComponentIndex": {
            str(key): value for key, value in sorted(mismatches_by_component.items())
        },
        "wordMismatchesByCase": dict(sorted(mismatches_by_case.items())),
        "wordMismatchesByEndpoint": dict(sorted(mismatches_by_endpoint.items())),
        "exact": record_mismatches == 0,
    }


def replay(roots: tuple[Path, ...]) -> JsonObject:
    if len(roots) != len(SCHEMAS):
        raise ValueError("one capture root is required for each schema")
    reports = [
        replay_schema(
            schema,
            importlib.import_module(module_name),
            root,
            raw_sha256,
        )
        for (schema, module_name, raw_sha256), root in zip(
            SCHEMAS,
            roots,
            strict=True,
        )
    ]
    return {
        "rasterTileSelectorV8OpenedReplaySchemaVersion": 1,
        "model": "Analysis/raster_tile_selector_model_v8.py",
        "schemas": reports,
        "recordCount": sum(int(report["recordCount"]) for report in reports),
        "wordCount": sum(int(report["wordCount"]) for report in reports),
        "recordMismatchCount": sum(
            int(report["recordMismatchCount"]) for report in reports
        ),
        "wordMismatchCount": sum(
            int(report["wordMismatchCount"]) for report in reports
        ),
        "exact": all(bool(report["exact"]) for report in reports),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for schema, _, _ in SCHEMAS:
        parser.add_argument(f"--schema{schema}", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    roots = tuple(getattr(arguments, f"schema{schema}") for schema, _, _ in SCHEMAS)
    report = replay(roots)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(rendered, end="")
    else:
        arguments.output.write_text(rendered, encoding="utf-8")
    if not report["exact"]:
        raise SystemExit("v8 differs from opened raster captures")


if __name__ == "__main__":
    main()
