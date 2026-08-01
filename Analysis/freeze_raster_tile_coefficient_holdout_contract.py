#!/usr/bin/env python3
"""Materialize the schema-13 prediction archive and preregistration."""

import argparse
import hashlib
import json
import zlib
from dataclasses import asdict
from pathlib import Path

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


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def prediction_bytes() -> tuple[bytes, bytes]:
    raw, _ = model.prediction_streams()
    return raw, zlib.compress(raw, level=9)


def write_archive() -> dict[str, str | int]:
    raw, compressed = prediction_bytes()
    model.PREDICTION_ARCHIVE_PATH.write_bytes(compressed)
    return {
        "rawBytes": len(raw),
        "rawSha256": hashlib.sha256(raw).hexdigest(),
        "archiveBytes": len(compressed),
        "archiveSha256": hashlib.sha256(compressed).hexdigest(),
    }


def model_source_hashes() -> dict[str, str]:
    return {
        "sourceSha256": sha256_path(Path(model.__file__)),
        "coefficientSourceSha256": sha256_path(Path(coefficients.__file__)),
        "iteratorSourceSha256": sha256_path(Path(iterator.__file__)),
        "baseSourceSha256": sha256_path(Path(v1.__file__)),
        "v2SourceSha256": sha256_path(Path(v2.__file__)),
        "v4SourceSha256": sha256_path(Path(v4.__file__)),
        "v6SourceSha256": sha256_path(Path(v6.__file__)),
        "v7SourceSha256": sha256_path(Path(v7.__file__)),
        "v8SourceSha256": sha256_path(Path(v8.__file__)),
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
        "role": "prospective-complete-raster-coefficient-holdout",
        "createdAt": "2026-08-01T23:30:00Z",
        "appleOutputsObservedAtPreregistration": False,
        "scientificQuestion": (
            "Does one input-only AGX model predict every pull, center, and "
            "derivative word for novel geometry and endpoints that distinguish "
            "aggregate tile-product truncation, all measured stage biases, and "
            "the broad-endpoint constant path?"
        ),
        "derivationEvidence": {
            "openedSchemas": list(range(3, 13)),
            "recordCount": 4_914_544,
            "wordCount": 88_461_792,
            "wordMismatchCount": 0,
            "retrospectiveExact": True,
            "prospectiveAtDerivation": False,
            "schema3RawSha256": (
                "c260075c6865c8d95749a6b6db51e441a37f9e2448ca4a4c1cfea8baac78c99b"
            ),
            "schema12RawSha256": (
                "dde09692cb490155cd2100552043115c4dce59f9244e22127e6857b2ca5f7477"
            ),
        },
        "capture": capture.capture_metadata(),
        "model": {
            **model_source_hashes(),
            "parameters": asdict(coefficients.MEASURED_POLICY),
            "centerPrecisionBits": iterator.CENTER_PRECISION_BITS,
            "constantPathSelector": (
                "positive lower endpoint below 0.5, upper endpoint at least "
                "0.5, and non-power-of-two exact endpoint delta"
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
            "Require zero mismatched words on the first unseen Apple capture, "
            "then require an unchanged independent capture with the same raw "
            "SHA-256 before treating this raster-coefficient domain as "
            "prospectively validated."
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
