#!/usr/bin/env python3
"""Open schema-3 tile-selector records against the frozen prediction."""

import argparse
import hashlib
import json
import mmap
from collections import Counter
from pathlib import Path
from typing import Any

import raster_tile_selector_model as model
import validate_raster_tile_numerator as capture


type JsonObject = dict[str, Any]

PREREGISTRATION_PATH = Path(__file__).with_name(
    "raster_tile_selector_holdout_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "6b31251975e55bfea2fa56ebbfcc0737b789316a7f11d9158d3dc9493365ea9c"
)
MAX_MISMATCH_EXAMPLES = 32
COMPONENT_NAMES = (
    *(f"pull@{numerator}/16" for numerator in capture.PULL_NUMERATORS),
    "center",
    "axis-derivative(center)",
)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def expected_model_payload() -> JsonObject:
    return {
        "name": "agx-near-equal-tile-selector-v1",
        "source": "Analysis/raster_tile_selector_model.py",
        "sourceSha256": sha256_path(Path(model.__file__)),
        "selectorTable": (
            "Analysis/raster_fractional_subpixel_resolved_selectors.zlib"
        ),
        "selectorTableSha256": model.SELECTOR_TABLE_COMPRESSED_SHA256,
        "slopePrecisionBits": model.SLOPE_PRECISION_BITS,
        "fixedProductPhaseIntervals": ["[3/8,1/2)", "[15/16,1)"],
        "lowerBranch": "one-27-bit-lattice-step-below-directed-floor",
        "upperBranch": "fixed-partial-product-coefficient",
        "constantPrecisionBits": model.CONSTANT_PRECISION_BITS,
        "constantRounding": "nearest-even-then-binary32-nearest-even",
        "pullRounding": "binary32-nearest-even-fused-multiply-add",
        "centerRounding": "binary32-toward-zero",
        "derivativeRule": "odd-minus-even-within-2x2-quad",
    }


def expected_prediction_payload(metadata: JsonObject) -> JsonObject:
    return {
        "dtype": "little-endian uint32 binary32 bits",
        "recordComponentCount": metadata["recordComponentCount"],
        "recordBytes": metadata["recordBytes"],
        "recordCount": metadata["recordCount"],
        "bytes": metadata["bytes"],
        "sha256": metadata["sha256"],
        "cases": metadata["cases"],
    }


def load_preregistration() -> tuple[JsonObject, JsonObject]:
    preregistration: JsonObject = json.loads(
        PREREGISTRATION_PATH.read_text(encoding="utf-8")
    )
    metadata = model.prediction_metadata()
    sealed_cases = [
        capture_case.name
        for capture_case in capture.CASES
        if capture_case.role == "sealed-holdout"
    ]
    selector_endpoint_count = sum(
        endpoint.role == "selector-discovery" for endpoint in capture.ENDPOINTS
    )
    domain = preregistration.get("domain", {})
    acceptance = preregistration.get("acceptance", {})
    if (
        sha256_path(PREREGISTRATION_PATH) != PREREGISTRATION_SHA256
        or preregistration.get("schemaVersion") != 1
        or preregistration.get("role") != "sealed-holdout-prediction"
        or preregistration.get("holdoutOpenedAtPreregistration") is not False
        or preregistration.get("model") != expected_model_payload()
        or domain
        != {
            "caseRole": "sealed-holdout",
            "cases": sealed_cases,
            "endpointRole": "selector-discovery",
            "endpointCount": selector_endpoint_count,
            "ordering": model.PREDICTION_ORDERING,
        }
        or preregistration.get("predictedTruthStream")
        != expected_prediction_payload(metadata)
        or acceptance
        != {
            "recordMismatchCount": 0,
            "wordMismatchCount": 0,
            "allCaseStreamsExact": True,
            "noTolerance": True,
            "noAdaptiveFit": True,
        }
    ):
        raise ValueError("tile-selector holdout preregistration differs")
    return preregistration, metadata


def actual_streams(root: Path) -> tuple[JsonObject, dict[str, bytes]]:
    validation = capture.validate(root)
    manifest: JsonObject = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    evidence = manifest["rasterTileNumerator"]
    raw_path = root / str(evidence["file"])
    streams: dict[str, bytes] = {}
    endpoint_indices = [
        (endpoint_index, endpoint)
        for endpoint_index, endpoint in enumerate(capture.ENDPOINTS)
        if endpoint.role == "selector-discovery"
    ]
    with (
        raw_path.open("rb") as stream,
        mmap.mmap(
            stream.fileno(),
            0,
            access=mmap.ACCESS_READ,
        ) as raw,
    ):
        for case_index, capture_case in enumerate(capture.CASES):
            if capture_case.role != "sealed-holdout":
                continue
            case_stream = bytearray()
            for endpoint_index, _ in endpoint_indices:
                for sample in capture.sample_positions(capture_case):
                    record_index = (
                        case_index * len(capture.ENDPOINTS) + endpoint_index
                    ) * capture.SLOT_COUNT + sample.slot
                    offset = record_index * capture.RECORD.size
                    case_stream.extend(raw[offset : offset + capture.RECORD.size])
            streams[capture_case.name] = bytes(case_stream)
    return validation, streams


def case_comparison(
    capture_case: capture.CaptureCase,
    actual: bytes,
    predicted: bytes,
) -> tuple[JsonObject, list[JsonObject]]:
    if len(actual) != len(predicted) or len(actual) % capture.RECORD.size:
        raise ValueError(f"{capture_case.name} comparison stream length differs")
    record_mismatches = 0
    word_mismatches = 0
    component_mismatches: Counter[str] = Counter()
    examples: list[JsonObject] = []
    offset = 0
    for endpoint in capture.ENDPOINTS:
        if endpoint.role != "selector-discovery":
            continue
        for sample in capture.sample_positions(capture_case):
            actual_record = capture.RECORD.unpack_from(actual, offset)
            predicted_record = capture.RECORD.unpack_from(predicted, offset)
            differing = [
                index
                for index, (actual_word, predicted_word) in enumerate(
                    zip(actual_record, predicted_record, strict=True)
                )
                if actual_word != predicted_word
            ]
            if differing:
                record_mismatches += 1
                word_mismatches += len(differing)
                component_mismatches.update(
                    COMPONENT_NAMES[index] for index in differing
                )
                if len(examples) < MAX_MISMATCH_EXAMPLES:
                    examples.append(
                        {
                            "case": capture_case.name,
                            "endpoint": endpoint.name,
                            "axis": "x" if sample.axis == 0 else "y",
                            "primitive": sample.primitive,
                            "tile": sample.tile,
                            "edge": sample.edge,
                            "x": sample.x,
                            "y": sample.y,
                            "components": [
                                {
                                    "name": COMPONENT_NAMES[index],
                                    "predictedBits": f"0x{predicted_record[index]:08x}",
                                    "actualBits": f"0x{actual_record[index]:08x}",
                                }
                                for index in differing
                            ],
                        }
                    )
            offset += capture.RECORD.size
    return (
        {
            "name": capture_case.name,
            "recordCount": len(actual) // capture.RECORD.size,
            "bytes": len(actual),
            "predictedSha256": hashlib.sha256(predicted).hexdigest(),
            "actualSha256": hashlib.sha256(actual).hexdigest(),
            "recordMismatchCount": record_mismatches,
            "wordMismatchCount": word_mismatches,
            "componentMismatchCounts": dict(sorted(component_mismatches.items())),
            "exact": record_mismatches == 0,
        },
        examples,
    )


def open_holdout(root: Path) -> JsonObject:
    preregistration, prediction_metadata = load_preregistration()
    predicted_combined, predicted = model.prediction_streams()
    validation, actual = actual_streams(root)
    actual_combined = b"".join(actual.values())
    cases: list[JsonObject] = []
    examples: list[JsonObject] = []
    for capture_case in capture.CASES:
        if capture_case.role != "sealed-holdout":
            continue
        comparison, case_examples = case_comparison(
            capture_case,
            actual[capture_case.name],
            predicted[capture_case.name],
        )
        cases.append(comparison)
        examples.extend(case_examples[: MAX_MISMATCH_EXAMPLES - len(examples)])
    record_mismatches = sum(int(case["recordMismatchCount"]) for case in cases)
    word_mismatches = sum(int(case["wordMismatchCount"]) for case in cases)
    exact = (
        hashlib.sha256(predicted_combined).hexdigest()
        == preregistration["predictedTruthStream"]["sha256"]
        and len(actual_combined) == prediction_metadata["bytes"]
        and record_mismatches == 0
        and word_mismatches == 0
    )
    return {
        "rasterTileSelectorHoldoutOpeningSchemaVersion": 1,
        "source": str(root),
        "sourceManifestSha256": validation["manifestSha256"],
        "sourceRawSha256": validation["rawSha256"],
        "sourceCiCommit": json.loads(
            (root / "manifest.json").read_text(encoding="utf-8")
        )["ciCommit"],
        "preregistrationSha256": PREREGISTRATION_SHA256,
        "predictionSha256": hashlib.sha256(predicted_combined).hexdigest(),
        "actualSha256": hashlib.sha256(actual_combined).hexdigest(),
        "recordCount": len(actual_combined) // capture.RECORD.size,
        "wordCount": len(actual_combined) // 4,
        "recordMismatchCount": record_mismatches,
        "wordMismatchCount": word_mismatches,
        "cases": cases,
        "mismatchExamples": examples,
        "exact": exact,
        "productionShaderAuthorized": False,
        "remainingGates": [
            "unchanged schema-3 repeat",
            "fresh Walle geometry and scale image holdout",
            "unchanged Walle image repeat",
            "dynamic-transition holdout and repeat",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    report = open_holdout(arguments.root)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not report["exact"]:
        raise SystemExit("tile-selector sealed holdout differs")


if __name__ == "__main__":
    main()
