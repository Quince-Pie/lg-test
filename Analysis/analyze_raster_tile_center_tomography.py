#!/usr/bin/env python3
"""Open schema 11 and recover the scale-relative center coefficient."""

import argparse
import json
from collections import Counter
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path
from typing import Any

import analyze_raster_tile_center_boundary_opened as boundary
import raster_tile_selector_model as v1
import raster_tile_selector_model_v8 as v8
import validate_raster_tile_center_tomography as capture


type JsonObject = dict[str, Any]

SCALE_LATTICE_FRACTION_BITS = 57
COMPONENT_NAMES = (
    *(f"pull@{numerator}/16" for numerator in capture.PULL_NUMERATORS),
    "center",
    "axis-derivative(center)",
)


def odd_native_span(endpoint: object) -> int:
    span = abs(endpoint.highBits - endpoint.lowBits)
    if span == 0:
        return 0
    return span >> ((span & -span).bit_length() - 1)


def scale_lattice_slope(capture_case: object, endpoint: object, axis: int) -> float:
    low = v1.float32_bits_fraction(endpoint.lowBits)
    high = v1.float32_bits_fraction(endpoint.highBits)
    delta = high - low
    extent = capture_case.width if axis == 0 else capture_case.height
    scale = max(abs(low), abs(high))
    step = v1.power_of_two(
        v1.floor_binary_exponent(scale) - SCALE_LATTICE_FRACTION_BITS
    )
    nearest_index = v1.round_fraction_to_integer_nearest_even(
        delta / Fraction(extent) / step
    )
    return float((nearest_index - 1) * step)


def candidate_center_slope(
    capture_case: object,
    endpoint: object,
    axis: int,
    selector_table: tuple[int, ...],
) -> tuple[str, float]:
    extent = capture_case.width if axis == 0 else capture_case.height
    delta = v8.endpoint_delta(endpoint)
    depth = v8.cancellation_depth(endpoint)
    if (
        endpoint.lowBits != 0
        and endpoint.highBits != 0
        and extent == capture.EFFECTIVE_EXTENT
        and delta > 0
        and odd_native_span(endpoint) == 15
        and depth >= 7
    ):
        return (
            "forward-n15-scale-p58-nearest-minus-one",
            scale_lattice_slope(capture_case, endpoint, axis),
        )
    return boundary.recovered_center_slope(
        capture_case,
        endpoint,
        axis=axis,
        selector_table=selector_table,
    )


def center_words(
    capture_case: object,
    endpoint: object,
    sample: object,
    selector_table: tuple[int, ...],
) -> tuple[int, int]:
    _, slope = candidate_center_slope(
        capture_case,
        endpoint,
        sample.axis,
        selector_table,
    )
    constant = v1.bits_float32(
        v8.physical_constant_bits(
            capture_case,
            endpoint,
            sample,
            selector_table=selector_table,
        )
    )
    coordinate = sample.x if sample.axis == 0 else sample.y
    local_pixel = coordinate - sample.tile * capture.TILE_SIZE
    position = local_pixel + 0.5
    return (
        v1.center_bits(position, slope, constant),
        v1.derivative_bits(local_pixel, position, slope, constant),
    )


def verify_structure(root: Path) -> tuple[JsonObject, Path, bytes]:
    capture.load_preregistration()
    manifest: JsonObject = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    evidence = manifest.get("rasterTileNumerator", {})
    raw_path = root / str(evidence.get("file", ""))
    if (
        manifest.get("schemaVersion") != capture.SCHEMA_VERSION
        or manifest.get("rigVersion") != capture.RIG_VERSION
        or evidence.get("role") != capture.ROLE
        or evidence.get("preregistrationSha256")
        != capture.PREREGISTRATION_SHA256
        or evidence.get("layout") != capture.layout_metadata()
        or evidence.get("cases") != [asdict(value) for value in capture.CASES]
        or evidence.get("endpoints") != capture.endpoint_metadata()
        or evidence.get("sha256") != capture.sha256_path(raw_path)
        or raw_path.stat().st_size != capture.raw_bytes()
    ):
        raise ValueError("schema-11 structure differs")
    return manifest, raw_path, raw_path.read_bytes()


def analyze(root: Path) -> JsonObject:
    manifest, raw_path, raw = verify_structure(root)
    selector_table = v1.load_selector_table()
    record_count = 0
    finite_words = 0
    control_record_mismatches = 0
    control_word_mismatches = 0
    frozen_record_mismatches = 0
    frozen_word_mismatches = 0
    candidate_record_mismatches = 0
    candidate_word_mismatches = 0
    frozen_components: Counter[str] = Counter()
    frozen_endpoints: Counter[str] = Counter()
    selected_laws: Counter[str] = Counter()

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
                if not all(capture.base.finite(bits) for bits in actual):
                    raise ValueError(f"nonfinite schema-11 record {record_index}")
                record_count += 1
                finite_words += len(actual)

                if endpoint.role == "prospective-control":
                    control = capture.base.control_pull_prediction(
                        capture_case,
                        endpoint,
                        sample,
                    )
                    differing = sum(
                        left != right
                        for left, right in zip(
                            actual[: capture.PULL_COUNT],
                            control,
                            strict=True,
                        )
                    )
                    control_record_mismatches += bool(differing)
                    control_word_mismatches += differing

                frozen = boundary.predict_record(
                    capture_case,
                    endpoint,
                    sample,
                    selector_table,
                )
                frozen_differing = [
                    index
                    for index, (left, right) in enumerate(
                        zip(actual, frozen, strict=True)
                    )
                    if left != right
                ]
                frozen_record_mismatches += bool(frozen_differing)
                frozen_word_mismatches += len(frozen_differing)
                frozen_components.update(
                    COMPONENT_NAMES[index] for index in frozen_differing
                )
                if frozen_differing:
                    frozen_endpoints[endpoint.name] += len(frozen_differing)

                law, _ = candidate_center_slope(
                    capture_case,
                    endpoint,
                    sample.axis,
                    selector_table,
                )
                selected_laws[law] += 1
                candidate = (
                    *frozen[: capture.PULL_COUNT],
                    *center_words(
                        capture_case,
                        endpoint,
                        sample,
                        selector_table,
                    ),
                )
                candidate_differing = sum(
                    left != right
                    for left, right in zip(actual, candidate, strict=True)
                )
                candidate_record_mismatches += bool(candidate_differing)
                candidate_word_mismatches += candidate_differing

    return {
        "rasterTileCenterTomographyOpeningSchemaVersion": 1,
        "source": str(root),
        "sourceCiCommit": manifest["ciCommit"],
        "sourceManifestSha256": capture.sha256_path(root / "manifest.json"),
        "sourceRawSha256": capture.sha256_path(raw_path),
        "recordCount": record_count,
        "wordCount": finite_words,
        "allDeclaredWordsFinite": finite_words
        == record_count * capture.RECORD_COMPONENT_COUNT,
        "preregisteredControl": {
            "recordCount": len(capture.CASES)
            * 2
            * capture.SLOT_COUNT,
            "recordMismatchCount": control_record_mismatches,
            "wordMismatchCount": control_word_mismatches,
            "exact": control_word_mismatches == 0,
            "inference": (
                "The preregistered simple-binary32 pull predictor is rejected; "
                "this is a control-model failure, while every captured record is "
                "present and finite."
            ),
        },
        "schema10PostOpeningModel": {
            "recordMismatchCount": frozen_record_mismatches,
            "wordMismatchCount": frozen_word_mismatches,
            "componentMismatchCounts": dict(sorted(frozen_components.items())),
            "endpointWordMismatchCounts": dict(sorted(frozen_endpoints.items())),
            "exact": frozen_word_mismatches == 0,
        },
        "retrospectiveScaleLatticeCandidate": {
            "scaleLatticeFractionBits": SCALE_LATTICE_FRACTION_BITS,
            "coefficient": (
                "round_nearest_even((high-low)/extent, "
                "step=2^(floor_log2(max_abs_endpoint)-57)) - step"
            ),
            "selection": (
                "positive odd-native-span 15, cancellation depth >= 7, "
                "effective extent 252"
            ),
            "selectedLawRecordCounts": dict(sorted(selected_laws.items())),
            "recordMismatchCount": candidate_record_mismatches,
            "wordMismatchCount": candidate_word_mismatches,
            "exact": candidate_word_mismatches == 0,
            "prospectiveEvidence": False,
        },
        "inference": (
            "The dense matrix rejects the p27-floor explanation and identifies a "
            "scale-relative p58 center coefficient for the extent-252 forward-n15 "
            "path. The candidate replays every schema-11 word exactly, but its "
            "extent selector is retrospective and requires a varied-extent "
            "discovery matrix before a blind parity holdout."
        ),
        "prospectiveParityClaim": False,
        "productionShaderAuthorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
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
