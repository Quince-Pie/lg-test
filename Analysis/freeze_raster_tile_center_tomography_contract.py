#!/usr/bin/env python3
"""Materialize the schema-11 dense tile-center tomography preregistration."""

import json

import validate_raster_tile_center_tomography as capture


def contract() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "role": "preregistered-center-dense-tomography",
        "createdAt": "2026-08-01T22:00:00Z",
        "appleOutputsObservedAtPreregistration": False,
        "scientificQuestion": (
            "Which input-derived coefficient, tile-constant, and evaluation law "
            "reproduces Apple's interpolate_at_center path below the formerly "
            "observable p27 lattice, without geometry-name or captured-value "
            "selectors?"
        ),
        "derivationEvidence": {
            "schema10CiRun": 30_706_923_035,
            "schema10CiCommit": (
                "d9ac507478e2a35430d735b127fd647ffe03eb93"
            ),
            "schema10RawSha256": (
                "9d08f9ab5b9660ab7870213a532c952adb389125cca69071af4a8bd9125379c5"
            ),
            "schema10FrozenRecordMismatchCount": 3_288,
            "schema10FrozenWordMismatchCount": 6_036,
            "schema10PostOpeningResidualRecordCount": 108,
            "schema10PostOpeningResidualWordCount": 216,
            "schema10ResidualScope": (
                "center and axis derivative only, effective extent 252, opposite "
                "extent 647, n15 forward family, final partial tile"
            ),
            "prospectiveEvidenceForRecoveredSubP27Law": False,
        },
        "capture": capture.capture_metadata(),
        "hypotheses": [
            "one global center coefficient plus one tile constant per setup",
            "independent center and explicit-offset pull setup paths",
            "determinant-dependent sub-p27 coefficient residue",
            "sub-binary32 tile-constant residue",
            "center evaluation precision or double-rounding boundary",
        ],
        "designRationale": (
            "Every integer pixel on the effective axis is recorded for both "
            "triangle primitives, both axis orientations, three determinant "
            "classes, and two tile alignments. This turns the previous 108 "
            "boundary-only residual records into a dense bit sequence capable of "
            "separating coefficient, constant, primitive, tile, and evaluator laws."
        ),
        "acceptance": {
            "structuralValidationRequired": True,
            "allDeclaredRecordsFinite": True,
            "zeroEndpointPullControlsExact": True,
            "tolerance": 0,
            "discoveryCapture": True,
            "prospectiveParityClaim": False,
            "productionShaderAuthorizedByThisCapture": False,
        },
        "nextGate": (
            "Recover one input-only arithmetic law from this preregistered discovery "
            "matrix, replay it with zero mismatches over every opened schema-5 "
            "through schema-11 word, then freeze its complete prediction bytes for "
            "a fresh prospective holdout and unchanged repeat."
        ),
    }


def main() -> None:
    capture.PREREGISTRATION_PATH.write_text(
        json.dumps(contract(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
