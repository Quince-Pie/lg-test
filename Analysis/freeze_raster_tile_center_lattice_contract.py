#!/usr/bin/env python3
"""Materialize the schema-8 preregistration and prediction archive."""

import argparse
import hashlib
import json
import zlib
from pathlib import Path

import raster_tile_selector_model as v1
import raster_tile_selector_model_v2 as v2
import raster_tile_selector_model_v4 as v4
import raster_tile_selector_model_v5 as v5
import raster_tile_selector_model_v6 as model
import validate_raster_tile_center_lattice_holdout as capture


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def prediction_bytes() -> tuple[bytes, bytes]:
    raw, _ = model.prediction_streams()
    return raw, zlib.compress(raw, level=9)


def prediction_hashes() -> dict[str, str | int]:
    raw, compressed = prediction_bytes()
    return {
        "rawBytes": len(raw),
        "rawSha256": hashlib.sha256(raw).hexdigest(),
        "archiveBytes": len(compressed),
        "archiveSha256": hashlib.sha256(compressed).hexdigest(),
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
        "role": "prospective-center-p27-lattice-holdout",
        "createdAt": "2026-08-01T15:00:00Z",
        "sealedHoldoutOpenedAtPreregistration": False,
        "scientificQuestion": (
            "Does Apple's translated tile-center path use a signed 27-bit "
            "coefficient lattice with forward phase actions -1 below 3/32, "
            "0 from 3/32 through 9/16, and +1 at or above 9/16, while reverse "
            "ramps use the signed numerical floor?"
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
            "openedRecordCount": 819_480,
            "openedWordCount": 14_750_640,
            "openedV6MismatchCount": 0,
            "prospectiveEvidenceForV6": False,
        },
        "capture": capture.capture_metadata(),
        "model": {
            "file": "Analysis/raster_tile_selector_model_v6.py",
            "sourceSha256": sha256_path(Path(model.__file__)),
            "baseFile": "Analysis/raster_tile_selector_model.py",
            "baseSourceSha256": sha256_path(Path(v1.__file__)),
            "v2File": "Analysis/raster_tile_selector_model_v2.py",
            "v2SourceSha256": sha256_path(Path(v2.__file__)),
            "v4File": "Analysis/raster_tile_selector_model_v4.py",
            "v4SourceSha256": sha256_path(Path(v4.__file__)),
            "v5File": "Analysis/raster_tile_selector_model_v5.py",
            "v5SourceSha256": sha256_path(Path(v5.__file__)),
            "selectorTableSha256": v1.SELECTOR_TABLE_COMPRESSED_SHA256,
            "pullCoefficientLaw": (
                "two-stage determinant coefficient rounded to binary32 nearest-even"
            ),
            "translatedCenterLattice": (
                "exact endpoint delta divided by axis extent on a signed p27 lattice"
            ),
            "translatedForwardPhaseLaw": (
                "signed floor - 1 step below 3/32; signed floor through 9/16; "
                "signed floor + 1 step at or above 9/16"
            ),
            "translatedReversePhaseLaw": "signed numerical p27 floor",
            "zeroEndpointCenterLaw": "use the determinant-rounded binary32 coefficient",
            "constantLaw": (
                "schema-6 physical/exact composite, 28-bit nearest-even then "
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
            "Open every schema-8 sealed word only after this preregistration, "
            "executable model, compressed prediction stream, and probe layout are "
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
        raise ValueError("freeze model hashes before materializing schema 8")
    model.PREDICTION_ARCHIVE_PATH.write_bytes(compressed)
    capture.PREREGISTRATION_PATH.write_text(
        json.dumps(contract(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
