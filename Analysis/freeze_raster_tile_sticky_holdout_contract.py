#!/usr/bin/env python3
"""Materialize the schema-14 prediction archive and preregistration."""

import argparse
import hashlib
import json
import zlib
from dataclasses import asdict
from pathlib import Path

import raster_tile_coefficient_model as coefficient_base
import raster_tile_coefficient_model_v2 as coefficients
import raster_tile_iterator_model as iterator_base
import raster_tile_iterator_model_v2 as iterator
import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v6 as v6
import raster_tile_selector_model_v7 as v7
import raster_tile_selector_model_v8 as v8
import raster_tile_sticky_holdout_model as model
import validate_raster_tile_sticky_holdout as capture


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def write_archive() -> dict[str, str | int]:
    raw, _ = model.prediction_streams()
    compressed = zlib.compress(raw, level=9)
    model.PREDICTION_ARCHIVE_PATH.write_bytes(compressed)
    return {
        "rawBytes": len(raw),
        "rawSha256": hashlib.sha256(raw).hexdigest(),
        "archiveBytes": len(compressed),
        "archiveSha256": hashlib.sha256(compressed).hexdigest(),
    }


def model_source_hashes() -> dict[str, str]:
    modules = {
        "sourceSha256": model,
        "coefficientSourceSha256": coefficients,
        "coefficientBaseSourceSha256": coefficient_base,
        "iteratorSourceSha256": iterator,
        "iteratorBaseSourceSha256": iterator_base,
        "baseSourceSha256": v1,
        "v2SourceSha256": v2,
        "v4SourceSha256": v4,
        "v6SourceSha256": v6,
        "v7SourceSha256": v7,
        "v8SourceSha256": v8,
    }
    return {
        **{
            key: sha256_path(Path(module.__file__))
            for key, module in modules.items()
        },
        "selectorTableSha256": v1.SELECTOR_TABLE_COMPRESSED_SHA256,
    }


def contract() -> dict[str, object]:
    prediction = model.prediction_metadata()
    prediction["archive"] = {
        "file": model.PREDICTION_ARCHIVE_PATH.name,
        "bytes": model.PREDICTION_ARCHIVE_PATH.stat().st_size,
        "sha256": model.PREDICTION_ARCHIVE_SHA256,
        "rawSha256": model.PREDICTION_RAW_SHA256,
    }
    return {
        "schemaVersion": 1,
        "role": capture.ROLE,
        "createdAt": "2026-08-01T20:38:17Z",
        "appleOutputsObservedAtPreregistration": False,
        "scientificQuestion": (
            "Does the calibrated AGX tile multiplier retain exactly one "
            "discarded-column carry, use the factorized coefficient path for "
            "every endpoint domain, and predict every pull, center, and "
            "derivative word for wholly novel geometry and endpoint bits?"
        ),
        "derivationEvidence": {
            "openedSchemas": list(range(3, 14)),
            "recordCount": 4_938_472,
            "wordCount": 88_892_496,
            "wordMismatchCount": 0,
            "retrospectiveExactAfterSchema13Calibration": True,
            "prospectiveAtDerivation": False,
            "schema13WasFailedProspectiveEvidence": True,
            "schema13RawSha256": (
                "2551aa03106d055322f810b3cc68b9106aec13784dbb85de180891da1cd9e6c8"
            ),
            "schema13OriginalPredictionWordMismatchCount": 6_411,
            "schema13CalibratedPredictionWordMismatchCount": 0,
        },
        "capture": capture.capture_metadata(),
        "model": {
            **model_source_hashes(),
            "parameters": asdict(coefficients.MEASURED_POLICY),
            "centerPrecisionBits": iterator_base.CENTER_PRECISION_BITS,
            "constantPath": "universal factorized coefficient setup",
            "tileProduct": (
                "truncated binary partial products plus at most one carry "
                "unit when any discarded column contributes"
            ),
        },
        "predictedTruthStream": prediction,
        "preflightDiscrimination": model.preflight_discrimination_metadata(),
        "acceptance": {
            "allDeclaredRecordsFinite": True,
            "recordMismatchCount": 0,
            "wordMismatchCount": 0,
            "tolerance": 0,
            "failureIsEvidence": True,
            "unchangedBitIdenticalRepeatRequired": True,
            "productionShaderAuthorizedByThisCapture": False,
        },
        "nextGate": (
            "Require zero mismatched words on this first unseen schema-14 "
            "capture, then require an unchanged independent capture with the "
            "same raw SHA-256 before treating the raster-coefficient domain "
            "as prospectively validated."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-only", action="store_true")
    arguments = parser.parse_args()
    if arguments.archive_only:
        print(json.dumps(write_archive(), indent=2, sort_keys=True))
        return
    capture.PREREGISTRATION_PATH.write_text(
        json.dumps(contract(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
