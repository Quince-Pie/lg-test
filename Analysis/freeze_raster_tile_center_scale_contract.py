#!/usr/bin/env python3
"""Materialize the schema-9 preregistration and prediction archive."""

import argparse
import hashlib
import json
import zlib
from pathlib import Path

import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v6 as v6
import raster_tile_selector_model_v7 as model
import validate_raster_tile_center_scale_holdout as capture


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def prediction_bytes() -> tuple[bytes, bytes]:
    raw, _ = model.prediction_streams()
    return raw, zlib.compress(raw, level=9)


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
        "role": "prospective-center-scale-switch-holdout",
        "createdAt": "2026-08-01T16:00:00Z",
        "sealedHoldoutOpenedAtPreregistration": False,
        "scientificQuestion": (
            "Does Apple select the signed-p27 center coefficient when two nonzero "
            "endpoints retain at least 16 bits of cancellation, and otherwise use "
            "the determinant coefficient rounded to binary32?"
        ),
        "derivationEvidence": {
            "schema5RawSha256": (
                "3cd6a35830a3d71af0252b87bce94e97917fdd68234805216d432b0bedbc1cc3"
            ),
            "schema6RawSha256": (
                "3b84d1376edc4d354672ff6367a9a66437ba23425342218f3c87952537e92665"
            ),
            "schema7RawSha256": (
                "0e20ff958ea6ce7326adb8dc0f9d3945bfb984dea010a0ff23a707a16c4d826c"
            ),
            "schema8RawSha256": (
                "7550032284d1570684efa2201de8a8bfabfb0254a8d130774b6e781ddde7d395"
            ),
            "schema8NearEqualRecordCount": 303_448,
            "schema8NearEqualWordCount": 5_462_064,
            "schema8NearEqualV6MismatchCount": 0,
            "schema8BroadRecordCount": 21_936,
            "schema8BroadWordCount": 394_848,
            "schema8BroadDeterminantPhysicalMismatchCount": 0,
            "openedRecordCount": 1_144_864,
            "openedWordCount": 20_607_552,
            "openedV7MismatchCount": 0,
            "prospectiveEvidenceForV7": False,
        },
        "capture": capture.capture_metadata(),
        "model": {
            "file": "Analysis/raster_tile_selector_model_v7.py",
            "sourceSha256": sha256_path(Path(model.__file__)),
            "baseFile": "Analysis/raster_tile_selector_model.py",
            "baseSourceSha256": sha256_path(Path(v1.__file__)),
            "v2File": "Analysis/raster_tile_selector_model_v2.py",
            "v2SourceSha256": sha256_path(Path(v2.__file__)),
            "v4File": "Analysis/raster_tile_selector_model_v4.py",
            "v4SourceSha256": sha256_path(Path(v4.__file__)),
            "v6File": "Analysis/raster_tile_selector_model_v6.py",
            "v6SourceSha256": sha256_path(Path(v6.__file__)),
            "selectorTableSha256": v1.SELECTOR_TABLE_COMPRESSED_SHA256,
            "pullCoefficientLaw": (
                "two-stage determinant coefficient rounded to binary32 nearest-even"
            ),
            "centerScaleFeature": (
                "maximum endpoint exponent minus exact endpoint-delta exponent"
            ),
            "centerScaleThreshold": capture.CANDIDATE_CANCELLATION_BITS,
            "highCancellationCenterLaw": (
                "schema-8 signed-p27 forward-phase selector and reverse floor"
            ),
            "ordinaryCenterLaw": "determinant coefficient rounded to binary32",
            "constantLaw": (
                "physical primitive-anchor composite, 28-bit nearest-even then "
                "binary32 nearest-even"
            ),
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
            "Open every schema-9 sealed word only after this preregistration, "
            "executable model, compressed prediction stream, and scale sweep are "
            "committed; require zero mismatched words and an unchanged bit-identical "
            "repeat before using this arithmetic in a fresh Walle image holdout."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-hashes", action="store_true")
    arguments = parser.parse_args()
    raw, compressed = prediction_bytes()
    hashes = {
        "rawBytes": len(raw),
        "rawSha256": hashlib.sha256(raw).hexdigest(),
        "archiveBytes": len(compressed),
        "archiveSha256": hashlib.sha256(compressed).hexdigest(),
    }
    if arguments.print_hashes:
        print(json.dumps(hashes, indent=2, sort_keys=True))
        return
    if (
        hashes["rawSha256"] != model.PREDICTION_RAW_SHA256
        or hashes["archiveSha256"] != model.PREDICTION_ARCHIVE_SHA256
    ):
        raise ValueError("freeze model hashes before materializing schema 9")
    model.PREDICTION_ARCHIVE_PATH.write_bytes(compressed)
    capture.PREREGISTRATION_PATH.write_text(
        json.dumps(contract(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
