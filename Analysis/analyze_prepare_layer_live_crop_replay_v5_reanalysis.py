#!/usr/bin/env python3
"""Reanalyze every direct-Mac regular crop capture under the v5 model."""

import argparse
import json
from pathlib import Path
from typing import Any

import validate_prepare_layer_live_crop_replay_v5_local_macos_26_6_1 as v5


ANALYSIS_SCHEMA_VERSION = 1
EXPECTED_INPUTS = {
    "failed485": (
        "018e870a730042f24fc5d06957ef693e39d63b01d9481c2f694b8abf8c3e6ef0",
        "c549bafa4ae350818ba062ff834ec726e9c8ca42797ab1a0c30b850a9fe49012",
        "circle-485-center",
    ),
    "dod485": (
        "691cffb51557a9fb63596534bb09d8e5497bd8c06163e77071d656561bfce2d7",
        "f4a5180d646e088f5aaa5dda7b5a65d98754a4dfcffcaa6a494dfb54118deedc",
        "circle-485-center",
    ),
    "failed487": (
        "537e2f7068009f6873ffb63e788c41965d4902de96b246fe4adcef0ac6288927",
        "fea52975827939fd5bce84dd8451c16676d8d16b5408905e4d7c48311816637c",
        "circle-487-center",
    ),
    "arithmetic496": (
        "8ff22c95a3c8614e17a1060578bfd34d4a5e1a9ccf5ce40b6fe76a39023cc201",
        "992035fc474a151c27d22a727ede99e76c365d1aebbf6ee82a91b48290fad95c",
        "circle-496-center",
    ),
    "failed497": (
        "b40239659cd4f53054c232fb42b603c82450ccdd55c9c28061ecbfb793f666e5",
        "36e7f816610b45b6c382241eb7991d542ca28ad0e9efb69817132e1d62416fb0",
        "circle-497-center",
    ),
    "failed498": (
        "6a39a28ca2c60aa549bfab6f0c044ad4b36744ec5f9a51b468be944c660e4382",
        "eb2f1c5eeff2be1489da0bde7e19cc9f2afc7dbdc60a294596dd7e5e9f380561",
        "circle-498-center",
    ),
    "stage498a": (
        "27b8aa31ce31b90f56e70dde258ff251fc2ba27ccc56e3ffb8bb066f44361b6c",
        "c7c2665c3370d64fc4d3203c550c196ce41f3f3a78a14ab66bb05bf1ca6f85c3",
        "circle-498-center",
    ),
    "stage498b": (
        "9983046bf7e25db8c0c29404b140b224517cbb7d115dbf0a23b5c374baa9d28b",
        "e1e3690a922dede630d8b1862cf6133ec8cb1b753ff7c9fa5522d32bcab1bf35",
        "circle-498-center",
    ),
    "known800a": (
        "271871e797714fae80052bcd8a3f280baa6c50653fabd26c35a88e876fe2c8f5",
        "5bbadf2e5da0f5038ffe665540281da84107c2a6ee1857515e546b7160db0abc",
        "circle-800-center",
    ),
    "known800b": (
        "1217f5228b39a394bf3a9e32fe91f6f8ed0abe2a9054528c860ec2bb8c37f890",
        "02f3d95599bf63573dcca2673e08af4afb642b426a78320f1346f8cf2dcf45ad",
        "circle-800-center",
    ),
}


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    return value


def _opened_replay(
    trace_path: Path,
    timeline_path: Path,
    specification: tuple[str, str, str],
) -> dict[str, Any]:
    trace_sha, timeline_sha, geometry = specification
    if (
        v5.v2._sha256(trace_path) != trace_sha
        or v5.v2._sha256(timeline_path) != timeline_sha
    ):
        raise ValueError("v5 opened input hash differs")
    result = v5.validate(
        trace_path,
        timeline_path,
        geometry,
        "regular",
        "dark",
        "materialize",
        require_embedded_code_identity=False,
    )
    replay = _mapping(result.get("floatingReplay"), "floating replay")
    model = _mapping(result.get("regularGeometryModel"), "geometry model")
    shadow = _mapping(result.get("filterShadowArithmetic"), "shadow arithmetic")
    endpoint = _mapping(result.get("endpointYOffset"), "endpoint witness")
    return {
        "geometry": geometry,
        "traceSHA256": trace_sha,
        "timelineSHA256": timeline_sha,
        "publicBackdropBoundsF64": model["publicBackdropBoundsF64"],
        "publicBackdropBoundsHex": model["publicBackdropBoundsHex"],
        "sourceBoundsF64": model["sourceBoundsF64"],
        "sourceBoundsHex": model["sourceBoundsHex"],
        "positiveShadowExpansionRecordCount": shadow["positiveExpansionRecordCount"],
        "legacyEndpointBranchRecordCount": endpoint["appliedRecordCount"],
        "legacyEndpointArithmeticOffsetApplied": endpoint["arithmeticOffsetApplied"],
        "rectangleCount": replay["rectangleCount"],
        "exactRectangleCount": replay["exactRectangleCount"],
        "componentCount": replay["componentCount"],
        "exactComponentCount": replay["exactComponentCount"],
        "maximumAbsoluteErrorsXYWH": replay["maximumAbsoluteErrorsXYWH"],
        "maximumULPDistancesXYWH": replay["maximumULPDistancesXYWH"],
    }


def analyze(inputs: dict[str, tuple[Path, Path]]) -> dict[str, Any]:
    if set(inputs) != set(EXPECTED_INPUTS):
        raise ValueError("v5 opened input inventory differs")
    replays = {
        label: _opened_replay(*inputs[label], specification)
        for label, specification in EXPECTED_INPUTS.items()
    }
    rectangles = sum(record["rectangleCount"] for record in replays.values())
    exact_rectangles = sum(record["exactRectangleCount"] for record in replays.values())
    components = sum(record["componentCount"] for record in replays.values())
    exact_components = sum(record["exactComponentCount"] for record in replays.values())
    positive_shadows = sum(
        record["positiveShadowExpansionRecordCount"] for record in replays.values()
    )
    endpoint_branches = sum(
        record["legacyEndpointBranchRecordCount"] for record in replays.values()
    )
    if (
        rectangles != 320
        or exact_rectangles != rectangles
        or components != 1280
        or exact_components != components
        or positive_shadows != 320
        or endpoint_branches != 10
        or any(
            record["legacyEndpointArithmeticOffsetApplied"] is not False
            for record in replays.values()
        )
    ):
        raise ValueError("opened v5 aggregate replay differs")
    return {
        "prepareLayerLiveCropReplayV5ReanalysisSchemaVersion": (
            ANALYSIS_SCHEMA_VERSION
        ),
        "classification": (
            "retrospective exact reanalysis of all ten retained direct-Mac "
            "regular-crop captures after opening the failed v4 target and live "
            "Filter/DOD stages; this calibrates v5 but supplies no unseen "
            "transfer authority"
        ),
        "conclusion": "success",
        "v4Falsification": {
            "geometry": "circle-498-center",
            "originalValidationExitStatus": 1,
            "v4UnseenGeometryTransferPassed": False,
            "negatedMarginSourceOriginAssumptionFalsified": True,
            "endpointSDFTranslationFalsified": True,
        },
        "v5Rules": {
            "sourceBounds": (
                "select the unique stable public CABackdropLayer bounds; let "
                "m=binary64(binary32(terminal inputBleedAmount)) and n=-m; "
                "return [b.x+n,b.y+n,b.w-(n+n),fma(n,-2,b.h)]"
            ),
            "shadow": (
                "s=gaussian_expansion_factor(inputShadowOpacity)*"
                "inputShadowRadius; expand origin by -s and size with "
                "fma(s,2,size), add inputShadowOffset, then union with the "
                "main 2.8-radius rectangle"
            ),
            "endpoint": (
                "retain the formerly correlated branch as a structural witness "
                "but apply no endpoint-derived SDF translation"
            ),
            "cropOrProducerValuesUsed": False,
            "toleranceUsed": False,
        },
        "openedReplays": replays,
        "aggregate": {
            "captureCount": len(replays),
            "rectangleCount": rectangles,
            "exactRectangleCount": exact_rectangles,
            "componentCount": components,
            "exactComponentCount": exact_components,
            "positiveShadowExpansionRecordCount": positive_shadows,
            "legacyEndpointBranchRecordCount": endpoint_branches,
            "legacyEndpointArithmeticOffsetAppliedCount": 0,
            "maximumAbsoluteErrorsXYWH": [0.0, 0.0, 0.0, 0.0],
            "maximumULPDistancesXYWH": [0, 0, 0, 0],
            "toleranceUsed": False,
        },
        "sealedConclusion": {
            "v4UnseenGeometryTransferPassed": False,
            "v4UnseenGeometryTransferFalsified": True,
            "v5OpenedEvidenceReplayPassed": True,
            "v5UnseenGeometryTransferPassed": False,
            "selectedRegionOriginTransferPassed": False,
            "opticalTransferPassed": False,
            "physicalRetinaColorCompositorTransferPassed": False,
            "independentWalleZeroByteFrameParityPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    for label in EXPECTED_INPUTS:
        parser.add_argument(f"--{label}-trace", required=True, type=Path)
        parser.add_argument(f"--{label}-timeline", required=True, type=Path)
    arguments = parser.parse_args()
    inputs = {
        label: (
            getattr(arguments, f"{label}_trace"),
            getattr(arguments, f"{label}_timeline"),
        )
        for label in EXPECTED_INPUTS
    }
    print(json.dumps(analyze(inputs), indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
