#!/usr/bin/env python3
"""Replay the post-opening v4 law over every schema-5 record."""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import open_raster_tile_translation_discriminator as opening
import raster_tile_selector_model as v1
import raster_tile_selector_model_v4 as model
import validate_raster_tile_translation_discriminator as capture


type JsonObject = dict[str, Any]

COMPONENT_NAMES = (
    *(f"pull@{numerator}/16" for numerator in capture.PULL_NUMERATORS),
    "center",
    "axis-derivative(center)",
)
MAX_MISMATCH_EXAMPLES = 64


def analyze(root: Path) -> JsonObject:
    validation, streams = opening.actual_case_streams(root)
    selector_table = v1.load_selector_table()
    record_count = 0
    record_mismatches = 0
    word_mismatches = 0
    component_mismatches: Counter[str] = Counter()
    pull_selectors: Counter[str] = Counter()
    center_selectors: Counter[str] = Counter()
    constant_selectors: Counter[str] = Counter()
    records_by_role: Counter[str] = Counter()
    mismatches_by_role: Counter[str] = Counter()
    double_rounding_changed_groups = 0
    split_center_groups = 0
    seen_constant_groups: set[tuple[str, str, int, int, int]] = set()
    seen_slope_groups: set[tuple[str, str, int]] = set()
    mismatch_examples: list[JsonObject] = []

    for capture_case in capture.CASES:
        samples = capture.sample_positions(capture_case)
        stream = streams[capture_case.name]
        offset = 0
        for endpoint in capture.ENDPOINTS:
            for sample in samples:
                actual = capture.RECORD.unpack_from(stream, offset)
                offset += capture.RECORD.size
                predicted = model.predict_record(
                    capture_case,
                    endpoint,
                    sample,
                    selector_table,
                )
                (
                    pull_name,
                    pull_bits,
                    center_name,
                    center_bits,
                    _,
                    _,
                ) = model.selected_slope_bits(
                    capture_case,
                    endpoint,
                    axis=sample.axis,
                    selector_table=selector_table,
                )
                constant_name, constant_bits = model.selected_constant_bits(
                    capture_case,
                    endpoint,
                    sample,
                    selector_table=selector_table,
                )
                slope_group = (capture_case.name, endpoint.name, sample.axis)
                if slope_group not in seen_slope_groups:
                    pull_selectors[pull_name] += 1
                    center_selectors[center_name] += 1
                    split_center_groups += pull_bits != center_bits
                    seen_slope_groups.add(slope_group)
                constant_group = (
                    capture_case.name,
                    endpoint.name,
                    sample.axis,
                    sample.primitive,
                    sample.tile,
                )
                if constant_group not in seen_constant_groups:
                    constant_selectors[constant_name] += 1
                    if endpoint.lowBits == 0 or endpoint.highBits == 0:
                        composite = model.zero_physical_composite(
                            capture_case,
                            endpoint,
                            sample,
                            selector_table=selector_table,
                        )
                        direct_bits = v1.round_fraction_to_float32_bits(composite)
                        double_rounding_changed_groups += direct_bits != constant_bits
                    seen_constant_groups.add(constant_group)

                differing = [
                    index
                    for index, (predicted_word, actual_word) in enumerate(
                        zip(predicted, actual, strict=True)
                    )
                    if predicted_word != actual_word
                ]
                record_count += 1
                records_by_role[capture_case.role] += 1
                if not differing:
                    continue
                record_mismatches += 1
                word_mismatches += len(differing)
                mismatches_by_role[capture_case.role] += len(differing)
                component_mismatches.update(
                    COMPONENT_NAMES[index] for index in differing
                )
                if len(mismatch_examples) < MAX_MISMATCH_EXAMPLES:
                    mismatch_examples.append(
                        {
                            "case": capture_case.name,
                            "role": capture_case.role,
                            "endpoint": endpoint.name,
                            "axis": "x" if sample.axis == 0 else "y",
                            "primitive": sample.primitive,
                            "tile": sample.tile,
                            "edge": sample.edge,
                            "components": [
                                {
                                    "name": COMPONENT_NAMES[index],
                                    "predictedBits": f"0x{predicted[index]:08x}",
                                    "actualBits": f"0x{actual[index]:08x}",
                                }
                                for index in differing
                            ],
                        }
                    )

    exact = record_mismatches == 0 and word_mismatches == 0
    return {
        "rasterTileTranslationOpenedV4AnalysisSchemaVersion": 1,
        "source": str(root),
        "sourceRawSha256": validation["rawSha256"],
        "recordCount": record_count,
        "wordCount": record_count * capture.RECORD_COMPONENT_COUNT,
        "recordsByCaseRole": dict(sorted(records_by_role.items())),
        "recordMismatchCount": record_mismatches,
        "wordMismatchCount": word_mismatches,
        "wordMismatchesByCaseRole": dict(sorted(mismatches_by_role.items())),
        "componentMismatchCounts": dict(sorted(component_mismatches.items())),
        "pullSlopeSetupSelectorCounts": dict(sorted(pull_selectors.items())),
        "centerSlopeSetupSelectorCounts": dict(sorted(center_selectors.items())),
        "constantGroupSelectorCounts": dict(sorted(constant_selectors.items())),
        "constantGroupCount": len(seen_constant_groups),
        "zeroConstantGroupsChangedByP28DoubleRounding": double_rounding_changed_groups,
        "slopeSetupCount": len(seen_slope_groups),
        "pullCenterSplitSetupCount": split_center_groups,
        "mismatchExamples": mismatch_examples,
        "exact": exact,
        "sealedHoldoutWasAlreadyOpenedBeforeV4Fit": True,
        "prospectiveEvidence": False,
        "productionShaderAuthorized": False,
        "nextGate": (
            "Commit the v4 model and every schema-6 prediction byte before "
            "capturing the fresh double-rounding and center-path holdout."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    report = analyze(arguments.root)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not report["exact"]:
        raise SystemExit("post-opening schema-5 v4 replay differs")


if __name__ == "__main__":
    main()
