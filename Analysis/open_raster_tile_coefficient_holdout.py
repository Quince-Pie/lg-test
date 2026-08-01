#!/usr/bin/env python3
"""Open schema-13 Apple records against the committed prediction bytes."""

import argparse
import hashlib
import json
import mmap
from collections import Counter
from pathlib import Path
from typing import Any

import raster_tile_coefficient_holdout_model as model
import raster_tile_coefficient_model as coefficients
import raster_tile_iterator_model as iterator
import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v6 as v6
import raster_tile_selector_model_v7 as v7
import raster_tile_selector_model_v8 as v8
import validate_raster_tile_coefficient_holdout as capture


type JsonObject = dict[str, Any]

MAX_MISMATCH_EXAMPLES = 128
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


def load_frozen_contract() -> tuple[JsonObject, JsonObject, dict[str, bytes]]:
    preregistration = capture.load_preregistration()
    metadata = model.prediction_metadata()
    frozen_model = preregistration.get("model", {})
    prediction = preregistration.get("predictedTruthStream", {})
    archive = prediction.get("archive", {})
    expected_prediction = {
        key: metadata[key]
        for key in (
            "ordering",
            "caseRole",
            "endpointRole",
            "endpointCount",
            "recordComponentCount",
            "recordBytes",
            "recordCount",
            "bytes",
            "sha256",
            "cases",
        )
    }
    source_hashes = {
        "sourceSha256": model,
        "coefficientSourceSha256": coefficients,
        "iteratorSourceSha256": iterator,
        "baseSourceSha256": v1,
        "v2SourceSha256": v2,
        "v4SourceSha256": v4,
        "v6SourceSha256": v6,
        "v7SourceSha256": v7,
        "v8SourceSha256": v8,
    }
    if (
        preregistration.get("appleOutputsObservedAtPreregistration") is not False
        or any(
            frozen_model.get(key) != sha256_path(Path(module.__file__))
            for key, module in source_hashes.items()
        )
        or frozen_model.get("selectorTableSha256")
        != v1.SELECTOR_TABLE_COMPRESSED_SHA256
        or {key: prediction.get(key) for key in expected_prediction}
        != expected_prediction
        or preregistration.get("preflightDiscrimination")
        != model.preflight_discrimination_metadata()
        or archive.get("file") != model.PREDICTION_ARCHIVE_PATH.name
        or archive.get("sha256") != model.PREDICTION_ARCHIVE_SHA256
        or archive.get("rawSha256") != model.PREDICTION_RAW_SHA256
        or archive.get("bytes") != model.PREDICTION_ARCHIVE_PATH.stat().st_size
    ):
        raise ValueError("schema-13 model or prediction contract differs")

    combined = model.read_prediction_archive()
    streams: dict[str, bytes] = {}
    offset = 0
    for case_metadata in metadata["cases"]:
        name = str(case_metadata["name"])
        byte_count = int(case_metadata["bytes"])
        stream = combined[offset : offset + byte_count]
        if hashlib.sha256(stream).hexdigest() != case_metadata["sha256"]:
            raise ValueError(f"frozen schema-13 prediction differs for {name}")
        streams[name] = stream
        offset += byte_count
    if offset != len(combined):
        raise ValueError("frozen schema-13 prediction has trailing bytes")
    return preregistration, metadata, streams


def actual_case_streams(root: Path) -> tuple[JsonObject, dict[str, bytes]]:
    validation = capture.validate(root)
    manifest: JsonObject = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    evidence = manifest["rasterTileNumerator"]
    raw_path = root / str(evidence["file"])
    streams: dict[str, bytes] = {}
    with (
        raw_path.open("rb") as stream,
        mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as raw,
    ):
        for case_index, capture_case in enumerate(capture.CASES):
            case_stream = bytearray()
            for endpoint_index, _ in enumerate(capture.ENDPOINTS):
                for sample in capture.sample_positions(capture_case):
                    record_index = (
                        case_index * len(capture.ENDPOINTS) + endpoint_index
                    ) * capture.SLOT_COUNT + sample.slot
                    offset = record_index * capture.RECORD.size
                    case_stream.extend(raw[offset : offset + capture.RECORD.size])
            streams[capture_case.name] = bytes(case_stream)
    return validation, streams


def compare_case(
    capture_case: capture.CaptureCase,
    actual: bytes,
    predicted: bytes,
) -> tuple[JsonObject, list[JsonObject]]:
    if len(actual) != len(predicted) or len(actual) % capture.RECORD.size:
        raise ValueError(f"{capture_case.name} comparison stream length differs")
    record_mismatches = 0
    word_mismatches = 0
    component_mismatches: Counter[str] = Counter()
    endpoint_mismatches: Counter[str] = Counter()
    examples: list[JsonObject] = []
    offset = 0
    for endpoint in capture.ENDPOINTS:
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
                endpoint_mismatches[endpoint.name] += len(differing)
                component_mismatches.update(
                    COMPONENT_NAMES[index] for index in differing
                )
                if len(examples) < MAX_MISMATCH_EXAMPLES:
                    examples.append(
                        {
                            "case": capture_case.name,
                            "endpoint": endpoint.name,
                            "endpointRole": endpoint.role,
                            "factorizedPathPredicted": (
                                coefficients.uses_factorized_tile_path(endpoint)
                            ),
                            "axis": "x" if sample.axis == 0 else "y",
                            "primitive": sample.primitive,
                            "tile": sample.tile,
                            "edge": sample.edge,
                            "x": sample.x,
                            "y": sample.y,
                            "components": [
                                {
                                    "name": COMPONENT_NAMES[index],
                                    "predictedBits": (
                                        f"0x{predicted_record[index]:08x}"
                                    ),
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
            "endpointWordMismatchCounts": dict(sorted(endpoint_mismatches.items())),
            "exact": record_mismatches == 0,
        },
        examples,
    )


def open_holdout(root: Path) -> JsonObject:
    preregistration, metadata, predictions = load_frozen_contract()
    validation, actual = actual_case_streams(root)
    cases: list[JsonObject] = []
    examples: list[JsonObject] = []
    for capture_case in capture.CASES:
        comparison, case_examples = compare_case(
            capture_case,
            actual[capture_case.name],
            predictions[capture_case.name],
        )
        cases.append(comparison)
        examples.extend(case_examples[: MAX_MISMATCH_EXAMPLES - len(examples)])

    record_mismatches = sum(int(case["recordMismatchCount"]) for case in cases)
    word_mismatches = sum(int(case["wordMismatchCount"]) for case in cases)
    combined_actual = b"".join(
        actual[capture_case.name] for capture_case in capture.CASES
    )
    actual_sha256 = hashlib.sha256(combined_actual).hexdigest()
    return {
        "rasterTileCoefficientHoldoutOpeningSchemaVersion": 1,
        "source": str(root),
        "sourceManifestSha256": validation["manifestSha256"],
        "sourceRawSha256": validation["rawSha256"],
        "sourceCiCommit": json.loads(
            (root / "manifest.json").read_text(encoding="utf-8")
        )["ciCommit"],
        "preregistrationSha256": capture.PREREGISTRATION_SHA256,
        "predictionSha256": metadata["sha256"],
        "actualComparedStreamSha256": actual_sha256,
        "predictionHashExact": actual_sha256 == metadata["sha256"],
        "recordCount": sum(int(case["recordCount"]) for case in cases),
        "wordCount": sum(int(case["recordCount"]) for case in cases)
        * capture.RECORD_COMPONENT_COUNT,
        "recordMismatchCount": record_mismatches,
        "wordMismatchCount": word_mismatches,
        "cases": cases,
        "mismatchExamples": examples,
        "exact": record_mismatches == 0,
        "productionShaderAuthorized": False,
        "remainingGates": [
            "unchanged independent schema-13 repeat",
            "held-out Walle image and transition parity",
        ],
        "acceptance": preregistration["acceptance"],
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
        raise SystemExit("schema-13 holdout differs")


if __name__ == "__main__":
    main()
