#!/usr/bin/env python3
"""Materialize the schema-12 varied-extent tomography preregistration."""

import json

import validate_raster_tile_center_extent_tomography as capture


def contract() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "role": "preregistered-center-varied-extent-tomography",
        "createdAt": "2026-08-01T17:05:00Z",
        "appleOutputsObservedAtPreregistration": False,
        "scientificQuestion": (
            "Which input-derived selector chooses determinant, p27, or "
            "scale-relative p58 center coefficients across varied extents, "
            "endpoint scales, native significands, directions, and tile phases?"
        ),
        "derivationEvidence": {
            "schema11CiRun": 30_708_595_385,
            "schema11CiCommit": (
                "1c826a37bf53ca70105b041d669c3f87dd8ecaa8"
            ),
            "schema11RawSha256": (
                "024e4092886280e74856eda245cdf5cc862947afb5bbdadca9d2159562964ee1"
            ),
            "schema11RecordCount": 471_744,
            "schema11WordCount": 8_491_392,
            "schema11AllDeclaredWordsFinite": True,
            "schema11PreregisteredControlRecordMismatchCount": 9_915,
            "schema11PreregisteredControlWordMismatchCount": 141_339,
            "schema11FrozenModelWordMismatchCount": 8_460,
            "schema11RetrospectiveScaleCandidateWordMismatchCount": 0,
            "schema11RetrospectiveScaleCandidateProspective": False,
            "decisiveOpenedExtentClasses": {
                "198": "sparse samples do not identify a unique coefficient",
                "252": "scale-relative p58 candidate only",
                "256": "older coefficient path only",
            },
        },
        "capture": capture.capture_metadata(),
        "hypotheses": [
            "determinant-rounded binary32 coefficient",
            "signed-p27 coefficient selector",
            "scale-relative p58 nearest-minus-one coefficient",
            "extent denominator or factorization selector",
            "native-significand and cancellation-depth selector",
            "tile-origin or opposite-extent selector",
        ],
        "designRationale": (
            "Seventeen effective extents include primes, composites, neighboring "
            "values, the decisive 252/256 pair, and legacy 198. Three decisive "
            "extents receive a second tile phase and opposite determinant. Every "
            "integer effective-axis pixel is recorded for both primitives and "
            "both axis orientations. Endpoint families cross two scales, both "
            "directions, cancellation depths 7 through 17, and six odd native "
            "significands."
        ),
        "acceptance": {
            "structuralValidationRequired": True,
            "allDeclaredRecordsFinite": True,
            "determinantZeroEndpointPullControlsExact": True,
            "tolerance": 0,
            "discoveryCapture": True,
            "prospectiveParityClaim": False,
            "productionShaderAuthorizedByThisCapture": False,
        },
        "nextGate": (
            "Recover one input-only selector from this preregistered discovery "
            "matrix, replay every opened schema-5 through schema-12 word exactly, "
            "then freeze complete prediction bytes for a novel prospective "
            "holdout and require an unchanged bit-identical repeat."
        ),
    }


def main() -> None:
    capture.PREREGISTRATION_PATH.write_text(
        json.dumps(contract(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
