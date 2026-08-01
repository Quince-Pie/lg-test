#!/usr/bin/env python3
"""Materialize the schema-7 preregistration from its frozen capture and model."""

import hashlib
import json
from pathlib import Path

import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v5 as model
import validate_raster_tile_center_origin_holdout as capture


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


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
        "role": "prospective-center-origin-versus-quotient-holdout",
        "createdAt": "2026-07-31T00:00:00Z",
        "sealedHoldoutOpenedAtPreregistration": False,
        "scientificQuestion": (
            "Does Apple select the center coefficient from the 32-pixel tile-origin "
            "residue, rather than from the denominator-33 quotient family that was "
            "confounded with that residue in opened schema 6?"
        ),
        "derivationEvidence": {
            "schema5RawSha256": (
                "3cd6a35830a3d71af0252b87bce94e97917fdd68234805216d432b0bedbc1cc3"
            ),
            "schema6RawSha256": (
                "3b84d1376edc4d354672ff6367a9a66437ba23425342218f3c87952537e92665"
            ),
            "openedRecordCount": 574680,
            "openedWordCount": 10344240,
            "openedV5MismatchCount": 0,
            "prospectiveEvidenceForV5": False,
        },
        "capture": capture.capture_metadata(),
        "model": {
            "file": "Analysis/raster_tile_selector_model_v5.py",
            "sourceSha256": sha256_path(Path(model.__file__)),
            "baseFile": "Analysis/raster_tile_selector_model.py",
            "baseSourceSha256": sha256_path(Path(v1.__file__)),
            "v2File": "Analysis/raster_tile_selector_model_v2.py",
            "v2SourceSha256": sha256_path(Path(v2.__file__)),
            "v4File": "Analysis/raster_tile_selector_model_v4.py",
            "v4SourceSha256": sha256_path(Path(v4.__file__)),
            "selectorTableSha256": v1.SELECTOR_TABLE_COMPRESSED_SHA256,
            "pullCoefficientLaw": "two-stage determinant coefficient rounded to binary32 nearest-even",
            "translatedCenterDefaultLaw": "exact endpoint delta divided by axis extent and rounded to binary32 toward negative infinity",
            "translatedCenterHalfTileLaw": "when axis origin modulo 32 equals 16, use the determinant coefficient",
            "zeroEndpointCenterLaw": "use the determinant coefficient",
            "constantLaw": "schema-6 physical/exact composite, 28-bit nearest-even then binary32 nearest-even",
            "capturedValuesParticipateInSelection": False,
        },
        "preflightDiscrimination": model.preflight_discrimination_metadata(),
        "predictedTruthStream": prediction,
        "acceptance": {
            "sealedWordMismatchCount": 0,
            "tolerance": 0,
            "unchangedRepeatRequired": True,
            "failureIsEvidence": True,
            "productionShaderAuthorizedByThisCapture": False,
        },
        "nextGate": (
            "Open every schema-7 sealed word only after this preregistration, "
            "executable model, compressed prediction stream, and probe layout are "
            "committed; require zero mismatched words and an unchanged repeat before "
            "using this arithmetic in a fresh Walle image holdout."
        ),
    }


def main() -> None:
    capture.PREREGISTRATION_PATH.write_text(
        json.dumps(contract(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
