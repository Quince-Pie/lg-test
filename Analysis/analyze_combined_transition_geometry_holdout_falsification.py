#!/usr/bin/env python3
"""Preserve and open the failed combined transition-geometry holdout."""

import argparse
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
import hashlib
import json
import math
from pathlib import Path
import struct
from typing import Any

import analyze_transition_geometry_corpus_local_macos_26_6_1 as model
import validate_combined_transition_geometry_holdout_local_macos_26_6_1 as frozen
import validate_variable_blur_selected_region_origin as selected


type JsonObject = dict[str, Any]

RESULT_SCHEMA_VERSION = 1
CAPTURE_COMMIT = "7432ffa54d530acf98ffc827c4588df94a1a5419"
CAPTURE_BINARY_SHA256 = (
    "9f48afc4c7ee44417db3ed1f6f733b742d9df2e69d8500c082ccc2026294ed0c"
)
PREREGISTRATION_SHA256 = (
    "b942bb532449998d8bca2c9be6a61397d73edcd221f244c73ca96d108745c2aa"
)
FROZEN_FAILURE = "expected one current background profile binding; found 0"
EXTRA_PRODUCER_FRAGMENTS = frozenset(
    {
        "TkfhA2Xhfc_Irsd",
        "TmuaA2Xhfc_Isrc_Isqr",
    }
)
TIMELINE_SHA256 = {
    "clear-dark-dematerialize-06": (
        "0fb1572ce1822fa3a00da0cf37357ba7d923d60d21da85b6a14207bf20c3fe31"
    ),
    "clear-dark-materialize-02": (
        "af9ba643aa1572bdd39fb55b7f7484ae5317a70509321086638bf3176ceefe9d"
    ),
    "clear-light-dematerialize-05": (
        "bb6ab00d00712abe3e3e3016387f268c77581ef52beb5ebc480dfb4258c90c46"
    ),
    "clear-light-materialize-01": (
        "85dc1f54a54f86852ee46b1c611f8968b470c0551a4647c0f7b8a59030ccb016"
    ),
    "regular-dark-dematerialize-08": (
        "9c2c56d949dd7fff27e7583a2cf4b91e0d574033682275b553bcc8c60df0e58f"
    ),
    "regular-dark-materialize-04": (
        "9e712a68193876937fa6001137a649d48802700d91b1afd955fc38625c759ded"
    ),
    "regular-light-dematerialize-07": (
        "1a4129540e0e2c495a506de25e488d6b76479d9e4804beb8595158b2c75fe45b"
    ),
    "regular-light-materialize-03": (
        "f5f8065c97375f2c545838d3bd28eab1f256c96330c5d1646f172cfa99b37068"
    ),
}

CURRENT_CLEAR_BACKGROUND = "PBGRABsovXm_TghzA2Xhf_Isrc"
CURRENT_REGULAR_BACKGROUND = "PBGRABsovXm_TghsA2Xhf_Isrc"
SMALL_CLEAR_BACKGROUND = "PBGRABsovXm_TghnA2Xhf_Isrc_Isrc"
CURRENT_FINAL_HIGHLIGHT = "PBGRAXm_TkfhBvcmA2Xhfc_Iscd"
SMALL_CLEAR_FINAL_HIGHLIGHT = "PBGRAXm_TkfhA2Xhfc_Iscd"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def load_object(path: Path, name: str) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{name} is not an object")
    return value


def exact_status(path: Path, expected: str) -> None:
    require(path.read_text(encoding="utf-8") == expected + "\n", f"{path} differs")


def retina_snap(value: float) -> float:
    """Reproduce the observed 2x placement snap, including quarter phases."""
    return math.floor(2.0 * value + 0.5) / 2.0


def retrospective_layer_candidate(
    geometry: Mapping[str, Any], remaining: float
) -> dict[str, tuple[float, ...]]:
    """Apply the coordinate-space split exposed by the opened holdout.

    This deliberately remains a calibration candidate.  Its residual element
    ULPs are reported rather than rounded away or promoted to transfer authority.
    """
    window_width = model.finite(geometry.get("windowWidth"), "window width")
    window_height = model.finite(geometry.get("windowHeight"), "window height")
    center_x = model.finite(geometry.get("centerX"), "geometry center x")
    center_y = model.finite(geometry.get("centerY"), "geometry center y")
    snapped_x = retina_snap(center_x)
    snapped_y = retina_snap(center_y)
    if remaining == 1.0:
        endpoint_geometry = dict(geometry)
        endpoint_geometry["centerX"] = snapped_x
        endpoint_geometry["centerY"] = snapped_y
        return model.expected_dynamic_layer_state(endpoint_geometry, remaining)

    local_geometry = dict(geometry)
    local_geometry["centerX"] = window_width / 2.0
    local_geometry["centerY"] = window_height / 2.0
    result = model.expected_dynamic_layer_state(local_geometry, remaining)
    position = result["elementPosition"]
    result["elementPosition"] = (
        position[0] + snapped_x - window_width / 2.0,
        position[1] + snapped_y - window_height / 2.0,
    )
    return result


def add_binary64_metric(
    metrics: dict[str, Counter[str]],
    name: str,
    observed: Sequence[float],
    predicted: Sequence[float],
) -> None:
    require(len(observed) == len(predicted), f"{name} component count differs")
    metric = metrics.setdefault(name, Counter())
    metric["componentCount"] += len(observed)
    metric["mismatchedComponents"] += sum(
        model.float64_bits(left) != model.float64_bits(right)
        for left, right in zip(observed, predicted, strict=True)
    )


def add_binary32_metric(
    metrics: dict[str, Counter[str]],
    name: str,
    observed: Sequence[float],
    predicted: Sequence[float],
) -> None:
    require(len(observed) == len(predicted), f"{name} component count differs")
    metric = metrics.setdefault(name, Counter())
    metric["componentCount"] += len(observed)
    metric["mismatchedComponents"] += sum(
        model.float32_bits(left) != model.float32_bits(right)
        for left, right in zip(observed, predicted, strict=True)
    )


def add_integer_metric(
    metrics: dict[str, Counter[str]],
    name: str,
    observed: Sequence[int],
    predicted: Sequence[int],
) -> None:
    require(len(observed) == len(predicted), f"{name} component count differs")
    metric = metrics.setdefault(name, Counter())
    metric["componentCount"] += len(observed)
    metric["mismatchedComponents"] += sum(
        left != right for left, right in zip(observed, predicted, strict=True)
    )


def metric_results(metrics: Mapping[str, Counter[str]]) -> JsonObject:
    return {
        name: {
            "componentCount": counter["componentCount"],
            "mismatchedComponents": counter["mismatchedComponents"],
            "exact": (
                counter["componentCount"] > 0
                and counter["mismatchedComponents"] == 0
            ),
        }
        for name, counter in sorted(metrics.items())
    }


def pipeline_tokens(record: Mapping[str, Any]) -> set[str]:
    render = model.mapping(record.get("render"), "dynamic render")
    probe = model.mapping(render.get("metalUniformProbe"), "Metal uniform probe")
    records = model.sequence(probe.get("records"), "Metal records")
    result: set[str] = set()
    for untyped in records:
        item = model.mapping(untyped, "Metal record")
        label = model.pipeline_label(item)
        if label:
            result.add(label.rsplit(".", 1)[-1])
    return result


@contextmanager
def opened_producer_fragments() -> Iterator[None]:
    original = selected.allocation.PRODUCER_FRAGMENTS
    selected.allocation.PRODUCER_FRAGMENTS = frozenset(
        set(original) | set(EXTRA_PRODUCER_FRAGMENTS)
    )
    try:
        yield
    finally:
        selected.allocation.PRODUCER_FRAGMENTS = original


def expected_case(case_id: str) -> Mapping[str, Any]:
    matches = [case for case in frozen.EXPECTED_CASES if case.get("caseId") == case_id]
    require(len(matches) == 1, f"case matrix has no unique {case_id}")
    case = matches[0]
    geometry = model.mapping(case.get("geometry"), "expected geometry")
    return {
        "sha256": TIMELINE_SHA256[case_id],
        "material": case["material"],
        "appearance": case["appearance"],
        "direction": case["direction"],
        "geometry": geometry["name"],
        "records": case["records"],
    }


def validate_capture_transport(root: Path) -> None:
    for case_id in TIMELINE_SHA256:
        directory = root / case_id
        exact_status(directory / "preflight-exit-status.txt", "0")
        exact_status(directory / "capture-exit-status.txt", "0")
        preflight = load_object(
            directory / "capture-session-preflight.json", "Retina preflight"
        )
        require(
            preflight.get("localRetinaCaptureSessionPreflightSchemaVersion") == 2
            and preflight.get("passed") is True
            and preflight.get("displayActive") is True
            and preflight.get("displayAsleep") is False
            and preflight.get("sessionLocked") is False
            and preflight.get("sessionLoginDone") is True
            and preflight.get("sessionOnConsole") is True
            and preflight.get("physicalPixels") == [3456, 2234]
            and preflight.get("logicalPoints") == [1728, 1117]
            and preflight.get("backingScaleFactor") == 2,
            f"{case_id} Retina preflight differs",
        )
        context = (directory / "capture-context.txt").read_text(encoding="utf-8")
        for line in (
            f"CAPTURE_COMMIT={CAPTURE_COMMIT}",
            f"CAPTURE_BINARY_SHA256={CAPTURE_BINARY_SHA256}",
            "NATIVE_CAPTURE_DEBUGGER_USED=0",
            "GITHUB_ACTIONS_USED=0",
            "TRACKED_DIRTY_STATE=0",
            "MTL_CAPTURE_ENABLED=0",
            "NATIVE_SDK_PATH=/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk",
            "NATIVE_SDK_VERSION=26.5",
            "NATIVE_DECLARED_SDK_VERSION=26.5",
            "ProductVersion:\t\t26.6.1",
            "BuildVersion:\t\t25G76",
            "Resolution: 3456 x 2234 Retina",
            f"{PREREGISTRATION_SHA256}  Analysis/combined_transition_geometry_holdout_preregistration.json",
        ):
            require(line in context, f"{case_id} capture context lacks {line!r}")
    exact_status(root / "validation-exit-status.txt", "1")


def frozen_failure(root: Path, preregistration: Path) -> str:
    try:
        frozen.validate(root, preregistration)
    except ValueError as error:
        message = str(error)
        require(message == FROZEN_FAILURE, "frozen validator failed differently")
        return message
    raise ValueError("frozen prospective validator unexpectedly passed")


def analyze(root: Path, preregistration: Path) -> JsonObject:
    require(root.is_dir(), "capture root is not a directory")
    require(
        sha256_file(preregistration) == PREREGISTRATION_SHA256,
        "frozen preregistration SHA-256 differs",
    )
    validate_capture_transport(root)
    failure = frozen_failure(root, preregistration)

    metrics: dict[str, Counter[str]] = {}
    branch_inventory: Counter[str] = Counter()
    producer_fragments: Counter[str] = Counter()
    final_topologies: Counter[str] = Counter()
    case_results: list[JsonObject] = []
    state_count = 0

    with opened_producer_fragments():
        for case_id, timeline_sha256 in sorted(TIMELINE_SHA256.items()):
            path = root / case_id / "transition-timeline.json"
            require(path.is_file(), f"missing timeline: {case_id}")
            require(
                sha256_file(path) == timeline_sha256,
                f"timeline SHA-256 differs: {case_id}",
            )
            timeline = load_object(path, "transition timeline")
            expected = expected_case(case_id)
            geometry = model.mapping(timeline.get("geometry"), "timeline geometry")
            records = model.validate_envelope(timeline, expected)
            case_branches: Counter[str] = Counter()

            for record in records:
                remaining = model.finite(record.get("remaining"), "remaining")
                predicted_layer = retrospective_layer_candidate(geometry, remaining)
                states = model.layer_states(record)
                carrier = model.mapping(states.get((1,)), "carrier layer state")
                element = model.mapping(
                    states.get((1, 0, 1, 0, 0, 0, 0)), "element layer state"
                )
                add_binary64_metric(
                    metrics,
                    "dynamicCarrierBounds",
                    model.vector(carrier.get("bounds"), "carrier bounds", 4),
                    predicted_layer["carrierBounds"],
                )
                add_binary64_metric(
                    metrics,
                    "dynamicCarrierPosition",
                    model.vector(carrier.get("position"), "carrier position", 2),
                    predicted_layer["carrierPosition"],
                )
                add_binary64_metric(
                    metrics,
                    "dynamicElementBoundsCandidate",
                    model.vector(element.get("bounds"), "element bounds", 4),
                    predicted_layer["elementBounds"],
                )
                add_binary64_metric(
                    metrics,
                    "dynamicElementPositionCandidate",
                    model.vector(element.get("position"), "element position", 2),
                    predicted_layer["elementPosition"],
                )

                observed_scale, _ = selected.allocation.captured_scale(record)
                predicted_scale = model.expected_backdrop_scale(
                    str(expected["material"]), remaining
                )
                add_binary32_metric(
                    metrics, "backdropScale", [observed_scale], [predicted_scale]
                )
                policy = selected.observed_policy(record, scale=observed_scale)
                mesh = model.mapping(policy.get("producerMesh"), "producer mesh")
                producer_fragment = mesh.get("fragmentFunction")
                require(
                    isinstance(producer_fragment, str) and producer_fragment,
                    "producer fragment is missing",
                )
                producer_fragments[producer_fragment] += 1
                crop_origin = [
                    model.integer(value, "crop origin")
                    for value in model.sequence(policy.get("cropOrigin"), "crop origin")
                ]
                clamp = [
                    model.integer(value, "copy clamp")
                    for value in model.sequence(
                        policy.get("textureCoordinateClamp"), "copy clamp"
                    )
                ]
                active_extent = [clamp[2] + 1, clamp[3] + 1]
                producer_extent = [
                    model.integer(value, "producer extent")
                    for value in model.sequence(
                        policy.get("producerExtent"), "producer extent"
                    )
                ]
                destination_extent = [
                    model.integer(value, "destination extent")
                    for value in model.sequence(
                        policy.get("destinationExtent"), "destination extent"
                    )
                ]
                copy_offset = [
                    model.integer(value, "copy offset")
                    for value in model.sequence(policy.get("copyOffset"), "copy offset")
                ]
                effective_origin = [
                    model.integer(value, "effective origin")
                    for value in model.sequence(
                        policy.get("effectiveOrigin"), "effective origin"
                    )
                ]
                predicted_producer = model.expected_producer_crop(
                    geometry,
                    material=str(expected["material"]),
                    carrier_position=predicted_layer["carrierPosition"],
                    backdrop_scale=predicted_scale,
                )
                add_integer_metric(
                    metrics,
                    "producerCropOrigin",
                    crop_origin,
                    predicted_producer["cropOrigin"],
                )
                add_integer_metric(
                    metrics,
                    "producerActiveExtent",
                    active_extent,
                    predicted_producer["activeExtent"],
                )
                add_integer_metric(
                    metrics,
                    "producerStorageExtent",
                    producer_extent,
                    predicted_producer["storageExtent"],
                )

                filter_record = model.mapping(record.get("filter"), "background filter")
                inputs = model.mapping(filter_record.get("inputValues"), "filter inputs")
                radius1 = selected.predict_radius1(
                    blur_radius=model.finite(
                        inputs.get("inputBlurRadius"), "blur radius"
                    ),
                    bleed_blur_radius=model.finite(
                        inputs.get("inputBleedBlurRadius"), "bleed blur radius"
                    ),
                    backdrop_scale=observed_scale,
                )
                mip = selected.predict_mip_policy(
                    radius1=radius1, source_extent=active_extent
                )
                helper_bounds = selected.predict_integer_bounds(
                    bounds=[*crop_origin, *active_extent],
                    radius1=radius1,
                    alignment_scale=model.integer(
                        mip.get("alignmentScale"), "alignment scale"
                    ),
                )
                add_integer_metric(
                    metrics,
                    "selectedRegionOrigin",
                    effective_origin,
                    helper_bounds[:2],
                )
                add_integer_metric(
                    metrics,
                    "selectedRegionAllocation",
                    destination_extent,
                    [selected.align_up(value) for value in helper_bounds[2:]],
                )
                add_integer_metric(
                    metrics,
                    "copyBaseOriginComposition",
                    effective_origin,
                    [
                        crop_origin[0] + copy_offset[0],
                        crop_origin[1] + copy_offset[1],
                    ],
                )
                add_integer_metric(
                    metrics,
                    "destinationMipCount",
                    [selected.copy_destination_mipmap_count(record)],
                    [model.integer(mip.get("levelCount"), "mip count")],
                )

                labels = pipeline_tokens(record)
                if CURRENT_CLEAR_BACKGROUND in labels:
                    background_family = "current-clear-background"
                elif CURRENT_REGULAR_BACKGROUND in labels:
                    background_family = "current-regular-background"
                elif SMALL_CLEAR_BACKGROUND in labels:
                    background_family = "small-clear-background"
                else:
                    require(
                        expected["material"] == "clear",
                        "regular state has no admitted background family",
                    )
                    background_family = "clear-without-primary-Tgh-draw"
                branch_inventory[background_family] += 1
                case_branches[background_family] += 1

                if CURRENT_FINAL_HIGHLIGHT in labels:
                    final_family = "current-final-highlight"
                elif SMALL_CLEAR_FINAL_HIGHLIGHT in labels:
                    final_family = "small-clear-final-highlight"
                else:
                    raise ValueError("state has no admitted final-highlight family")
                branch_inventory[final_family] += 1
                case_branches[final_family] += 1
                try:
                    final = model.final_highlight_inventory(record)
                except ValueError:
                    final_topologies["unparsed-small-clear"] += 1
                else:
                    final_topologies[
                        f"{final['indexCount']}-indices/{final['vertexCount']}-vertices"
                    ] += 1
                state_count += 1

            case_results.append(
                {
                    "caseId": case_id,
                    "timelineSHA256": timeline_sha256,
                    "stateCount": len(records),
                    "branchInventory": dict(sorted(case_branches.items())),
                }
            )

    results = metric_results(metrics)
    for name in (
        "backdropScale",
        "dynamicCarrierBounds",
        "dynamicCarrierPosition",
        "producerCropOrigin",
        "producerActiveExtent",
        "producerStorageExtent",
        "selectedRegionOrigin",
        "selectedRegionAllocation",
        "copyBaseOriginComposition",
        "destinationMipCount",
    ):
        require(results[name]["exact"] is True, f"opened exact metric differs: {name}")
    require(state_count == 252, "opened state count differs")
    require(
        branch_inventory
        == Counter(
            {
                "current-clear-background": 37,
                "current-regular-background": 126,
                "small-clear-background": 60,
                "clear-without-primary-Tgh-draw": 29,
                "current-final-highlight": 191,
                "small-clear-final-highlight": 61,
            }
        ),
        "opened branch inventory differs",
    )
    require(
        final_topologies
        == Counter(
            {
                "6-indices/4-vertices": 186,
                "24-indices/16-vertices": 5,
                "unparsed-small-clear": 61,
            }
        ),
        "opened final topology inventory differs",
    )

    return {
        "combinedTransitionGeometryHoldoutFalsificationSchemaVersion": (
            RESULT_SCHEMA_VERSION
        ),
        "classification": (
            "immutable prospective falsification followed by explicitly "
            "retrospective exact branch census"
        ),
        "status": "prospectively-falsified",
        "captureCommit": CAPTURE_COMMIT,
        "captureBinarySHA256": CAPTURE_BINARY_SHA256,
        "preregistrationSHA256": PREREGISTRATION_SHA256,
        "timelineCount": len(TIMELINE_SHA256),
        "stateCount": state_count,
        "frozenValidatorExitStatus": 1,
        "firstFrozenFailure": failure,
        "prospectiveGatePassed": False,
        "retrospectiveCalibrationHasProspectiveAuthority": False,
        "cases": case_results,
        "metrics": results,
        "pipelineBranchInventory": dict(sorted(branch_inventory.items())),
        "producerFragmentInventory": dict(sorted(producer_fragments.items())),
        "finalTopologyInventory": dict(sorted(final_topologies.items())),
        "openedFindings": {
            "coordinateSpaceSplit": (
                "for live k<1 the carrier remains centered in the 1024-point "
                "window while the requested center, snapped to the nearest "
                "Retina half point, moves into the element; the k=1 endpoint "
                "moves the carrier to that snapped requested center"
            ),
            "producerPolicy": (
                "the corrected local carrier coordinate makes crop, active and "
                "storage extent, selected region, copy composition, and mip "
                "count exact in all 252 opened states"
            ),
            "alternateFamilies": (
                "small clear geometry selects Tghn/Tkfh without Bvcm, while "
                "29 clear states have no ordinary Tgh primary draw"
            ),
        },
        "remainingAlgorithmBoundaries": [
            "exact binary64 off-center element extent and position staging",
            "window clipping and alternate 24-vertex/96-index topology construction",
            "small-clear Tghn/Tmua/Tkfh/A2Xghfc construction and pixels",
        ],
        "walleIntegrationMayBeginBehindGates": True,
        "productionParityAuthorized": False,
        "productionShaderChanged": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-root", required=True, type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = analyze(arguments.capture_root, arguments.preregistration)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
