#!/usr/bin/env python3
"""Summarize the first real clipped-setup capture without fitting a model."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

import validate_raster_clipped_setup_transfer as clipped


type JsonObject = dict[str, Any]
type WordArray = NDArray[np.uint32]

SOURCE_RUN_ID = 30_674_647_960
SOURCE_COMMIT = "a9dd81713ffcdaf21f3447d0efd15a44d329447d"
SOURCE_MANIFEST_SHA256 = (
    "ed317bd8992b3359f0b25fa2c9d1d7f9e6ce05511837f21a1569a7e874c0113d"
)
SOURCE_RAW_SHA256 = (
    "c89b0d39d1c022fad863007e996e701ffa3b2e1c128b2b08fe7d28511fa4f590"
)
SOURCE_VALIDATION_SHA256 = (
    "204057a4e1287b24a2ba6faf642b82d020220ba917a871e41a0ee9e8202db768"
)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def load_words(raw_path: Path) -> WordArray:
    words = np.memmap(raw_path, dtype="<u4", mode="r")
    expected_word_count = clipped.RAW_BYTES // np.dtype("<u4").itemsize
    if words.size != expected_word_count:
        raise ValueError("clipped-setup raw word count differs")
    return words.reshape(
        clipped.WIDTH_COUNT,
        clipped.HEIGHT_COUNT,
        clipped.WITNESS_COUNT,
        clipped.VARIANT_COUNT,
        clipped.SAMPLE_POSITION_COUNT,
        2,
    )


def equality_counts(left: WordArray, right: WordArray) -> JsonObject:
    equal = left == right
    return {
        "coefficientAllRecordsEqualCount": int(equal.all(axis=(-2, -1)).sum()),
        "recordEqualCount": int(equal.all(axis=-1).sum()),
        "wordEqualCount": int(equal.sum()),
        "wordCount": int(equal.size),
    }


def equality_by_height(
    words: WordArray,
    *,
    left_variant: int,
    right_variant: int,
) -> JsonObject:
    return {
        str(height): equality_counts(
            words[:, height_index, :, left_variant, :, :],
            words[:, height_index, :, right_variant, :, :],
        )
        for height_index, height in enumerate(clipped.HEIGHTS)
    }


def validate_source(root: Path) -> tuple[JsonObject, Path, JsonObject]:
    manifest, raw_path = clipped.validate_manifest(root)
    validation_path = root / "validation.json"
    validation: JsonObject = json.loads(
        validation_path.read_text(encoding="utf-8")
    )
    if (
        manifest.get("ciCommit") != SOURCE_COMMIT
        or sha256_path(root / "manifest.json") != SOURCE_MANIFEST_SHA256
        or sha256_path(raw_path) != SOURCE_RAW_SHA256
        or sha256_path(validation_path) != SOURCE_VALIDATION_SHA256
        or validation.get("ciCommit") != SOURCE_COMMIT
        or validation.get("rawSha256") != SOURCE_RAW_SHA256
    ):
        raise ValueError("clipped-setup source evidence differs")
    return manifest, raw_path, validation


def analyze(root: Path) -> JsonObject:
    manifest, raw_path, validation = validate_source(root)
    words = load_words(raw_path)
    centered_index = 1
    variant_equality = {
        str(variant["name"]): equality_by_height(
            words,
            left_variant=variant_index,
            right_variant=centered_index,
        )
        for variant_index, variant in enumerate(clipped.VARIANTS)
        if variant_index != centered_index
    }
    x_xy_equality = equality_by_height(
        words,
        left_variant=2,
        right_variant=4,
    )
    measurement = validation["measurement"]
    y_equality = variant_equality["y-clipped-centered"]
    height_47 = y_equality["47"]
    changed_height_counts = {
        height: clipped.COEFFICIENT_COUNT // clipped.HEIGHT_COUNT
        - int(y_equality[height]["coefficientAllRecordsEqualCount"])
        for height in ("61", "79", "113")
    }
    return {
        "liquidGlassRasterClippedSetupAnalysisSchemaVersion": 1,
        "classification": "post-capture descriptive analysis; no fitted clip law",
        "sourceEvidence": {
            "runId": SOURCE_RUN_ID,
            "ciCommit": manifest["ciCommit"],
            "manifestSha256": SOURCE_MANIFEST_SHA256,
            "rawSha256": SOURCE_RAW_SHA256,
            "validationSha256": SOURCE_VALIDATION_SHA256,
            "rawBytes": clipped.RAW_BYTES,
        },
        "measurement": {
            "coefficientCountPerVariant": clipped.COEFFICIENT_COUNT,
            "variantEqualityAgainstUnclippedCenteredByHeight": variant_equality,
            "xVersusXYEqualityByHeight": x_xy_equality,
            "prospectiveCandidateMultiplicityByVariant": measurement[
                "candidateMultiplicityByVariant"
            ],
            "prospectiveExpectedSlopeAcceptedCountByVariant": measurement[
                "expectedSlopeAcceptedCountByVariant"
            ],
            "prospectiveFailureCountByVariant": measurement[
                "failureCountByVariant"
            ],
        },
        "conclusions": {
            "unclippedCenteredControlExact": bool(
                measurement["centeredVaryingControlGate"]
            ),
            "clippedTransferFalsified": not bool(
                measurement["axisIsolatedClippedSetupGate"]
            ),
            "height376YVariantBitIdenticalToUnclipped": (
                height_47["coefficientAllRecordsEqualCount"]
                == clipped.COEFFICIENT_COUNT // clipped.HEIGHT_COUNT
            ),
            "height488AndAboveChangeEveryCoefficient": all(
                count == clipped.COEFFICIENT_COUNT // clipped.HEIGHT_COUNT
                for count in changed_height_counts.values()
            ),
            "screenSpaceYExtentWithNoObservedClipEffect": {
                "heightPixels": 376,
                "minimumY": -60.5,
                "maximumY": 315.5,
            },
            "smallestMeasuredYExtentWithUniversalClipEffect": {
                "heightPixels": 488,
                "minimumY": -116.5,
                "maximumY": 371.5,
            },
            "guardBoundaryEstablished": False,
            "clipGeneratedTopologyEstablished": False,
            "endToEndLiquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    report = analyze(arguments.root)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
