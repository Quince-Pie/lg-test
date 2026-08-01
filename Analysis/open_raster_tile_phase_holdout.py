#!/usr/bin/env python3
"""Open schema-4 phase-boundary records against the frozen v2 model."""

import argparse
import hashlib
import json
import mmap
from collections import Counter
from pathlib import Path
from typing import Any

import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as model
import validate_raster_tile_phase_holdout as capture


type JsonObject = dict[str, Any]

MAX_MISMATCH_EXAMPLES = 64
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


def load_preregistration() -> tuple[JsonObject, JsonObject]:
    preregistration = capture.load_preregistration()
    metadata = model.prediction_metadata()
    frozen_model = preregistration.get("model", {})
    prediction = preregistration.get("predictedTruthStream", {})
    expected_prediction = {
        "ordering": metadata["ordering"],
        "caseRole": metadata["caseRole"],
        "endpointRole": metadata["endpointRole"],
        "endpointCount": metadata["endpointCount"],
        "recordComponentCount": metadata["recordComponentCount"],
        "recordBytes": metadata["recordBytes"],
        "recordCount": metadata["recordCount"],
        "bytes": metadata["bytes"],
        "sha256": metadata["sha256"],
        "cases": metadata["cases"],
    }
    if (
        frozen_model.get("sourceSha256") != sha256_path(Path(model.__file__))
        or frozen_model.get("baseSourceSha256") != sha256_path(Path(v1.__file__))
        or frozen_model.get("selectorTableSha256")
        != v1.SELECTOR_TABLE_COMPRESSED_SHA256
        or {key: prediction.get(key) for key in expected_prediction}
        != expected_prediction
    ):
        raise ValueError("tile-phase model or prediction differs")
    return preregistration, metadata


def actual_case_streams(root: Path) -> tuple[JsonObject, dict[str, bytes]]:
    validation = capture.validate(root)
    manifest: JsonObject = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    evidence = manifest["rasterTileNumerator"]
    raw_path = root / str(evidence["file"])
    endpoint_indices = [
        endpoint_index
        for endpoint_index, endpoint in enumerate(capture.ENDPOINTS)
        if endpoint.role == "selector-discovery"
    ]
    streams: dict[str, bytes] = {}
    with (
        raw_path.open("rb") as stream,
        mmap.mmap(
            stream.fileno(),
            0,
            access=mmap.ACCESS_READ,
        ) as raw,
    ):
        for case_index, capture_case in enumerate(capture.CASES):
            case_stream = bytearray()
            for endpoint_index in endpoint_indices:
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
                            "caseRole": capture_case.role,
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
            "role": capture_case.role,
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
    validation, actual = actual_case_streams(root)
    selector_table = v1.load_selector_table()
    predicted = {
        capture_case.name: model.case_stream(capture_case, selector_table)
        for capture_case in capture.CASES
    }
    cases: list[JsonObject] = []
    examples: list[JsonObject] = []
    for capture_case in capture.CASES:
        comparison, case_examples = compare_case(
            capture_case,
            actual[capture_case.name],
            predicted[capture_case.name],
        )
        cases.append(comparison)
        examples.extend(case_examples[: MAX_MISMATCH_EXAMPLES - len(examples)])
    record_mismatches = sum(int(case["recordMismatchCount"]) for case in cases)
    word_mismatches = sum(int(case["wordMismatchCount"]) for case in cases)
    records_by_role: dict[str, int] = {}
    mismatches_by_role: dict[str, int] = {}
    for case in cases:
        role = str(case["role"])
        records_by_role[role] = records_by_role.get(role, 0) + int(case["recordCount"])
        mismatches_by_role[role] = mismatches_by_role.get(role, 0) + int(
            case["wordMismatchCount"]
        )
    sealed_actual = b"".join(
        actual[capture_case.name]
        for capture_case in capture.CASES
        if capture_case.role == "sealed-holdout"
    )
    exact = record_mismatches == 0 and word_mismatches == 0
    return {
        "rasterTilePhaseHoldoutOpeningSchemaVersion": 1,
        "source": str(root),
        "sourceManifestSha256": validation["manifestSha256"],
        "sourceRawSha256": validation["rawSha256"],
        "sourceCiCommit": json.loads(
            (root / "manifest.json").read_text(encoding="utf-8")
        )["ciCommit"],
        "preregistrationSha256": capture.PREREGISTRATION_SHA256,
        "predictionSha256": prediction_metadata["sha256"],
        "sealedActualSha256": hashlib.sha256(sealed_actual).hexdigest(),
        "sealedPredictionHashExact": (
            hashlib.sha256(sealed_actual).hexdigest()
            == preregistration["predictedTruthStream"]["sha256"]
        ),
        "recordCount": sum(int(case["recordCount"]) for case in cases),
        "wordCount": sum(int(case["recordCount"]) for case in cases)
        * capture.RECORD_COMPONENT_COUNT,
        "recordsByCaseRole": dict(sorted(records_by_role.items())),
        "wordMismatchesByCaseRole": dict(sorted(mismatches_by_role.items())),
        "recordMismatchCount": record_mismatches,
        "wordMismatchCount": word_mismatches,
        "cases": cases,
        "mismatchExamples": examples,
        "exact": exact,
        "productionShaderAuthorized": False,
        "remainingGates": [
            "unchanged schema-4 repeat",
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
        raise SystemExit("tile-phase holdout differs")


if __name__ == "__main__":
    main()
