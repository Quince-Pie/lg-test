#!/usr/bin/env python3
"""Validate the prospective current Iscd/Irsd compositor transfer gate."""

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Never


REPOSITORY = Path(__file__).resolve().parents[1]
WIDTH = 1024
HEIGHT = 1024
PIXELS = WIDTH * HEIGHT
BGRA_BYTES = PIXELS * 4
RGBA16_BYTES = PIXELS * 8
SAMPLE = 24
FINITE_SOURCE = bytes((0x40, 0x80, 0xC0, 0xFF))
PIPELINES = {
    "Iscd": "com.apple.coreanimation.PBGRAXm_TkfhBvcmA2Xhfc_Iscd",
    "Irsd": "com.apple.coreanimation.PBGRAXm_TkfhBvcmA2Xhfc_Irsd",
}
MATRIX_CASES = (
    "zero-rgb-unit-alpha",
    "unit-rgb-unit-alpha",
    "identity-rgb-unit-alpha",
    "permuted-rgb-unit-alpha",
    "identity-rgb-destination-alpha",
    "asymmetric-constant-unit-alpha",
    "natural-rgb-unit-alpha",
)
ALPHA_ORACLE_WORDS = (
    *("0x0000",) * 15,
    "0x3c00",
    "0x3c00",
    "0x3c00",
    "0x3c00",
    *("0x0000",) * 5,
)
FORCED_COVERAGE_EDITS = (
    ("key_compositing_parameter", 0xD4, "0000"),
    ("key_color", 0xE8, "003c003c003c003c"),
    ("fill_color", 0xF0, "0000000000000000"),
    ("key_width", 0xD0, "ff7b"),
    ("key_threshold", 0xD2, "0000"),
    ("key_direction", 0xD6, "003c0000"),
    ("fade_mix", 0xE4, "0000"),
    ("distance_offset", 0xE6, "00f4"),
)
TRANSPORT_CARRIER_OUTER_PATHS = (
    (1, 0, 1),
    (1, 0, 1, 0),
    (1, 0, 1, 0, 0),
    (1, 0, 1, 2),
)
TRANSPORT_ELEMENT_PATH = (1, 0, 1, 0, 0, 0, 0)

type JSONObject = dict[str, object]


def fail(message: str) -> Never:
    raise ValueError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def mapping(value: object, label: str) -> Mapping[str, object]:
    require(isinstance(value, Mapping), f"{label} is not an object")
    return value


def sequence(value: object, label: str) -> Sequence[object]:
    require(
        isinstance(value, Sequence) and not isinstance(value, (str, bytes)),
        f"{label} is not an array",
    )
    return value


def load_json(path: Path) -> JSONObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path} is not a JSON object")
    return value


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def validate_sources(preregistration: Mapping[str, object]) -> None:
    sources = mapping(preregistration.get("sourceSHA256"), "sourceSHA256")
    for relative, expected in sources.items():
        require(
            isinstance(relative, str) and isinstance(expected, str),
            "source hash entry is malformed",
        )
        source = REPOSITORY / relative
        require(source.is_file(), f"pinned source is absent: {relative}")
        require(
            sha256_file(source) == expected,
            f"pinned source differs: {relative}",
        )


def snapshot_payload(
    capture_directory: Path,
    untyped: object,
    *,
    label: str,
    pixel_format: int,
    byte_count: int,
    width: int = WIDTH,
    height: int = HEIGHT,
) -> bytes:
    snapshot = mapping(untyped, f"{label} snapshot")
    expected = {
        "width": width,
        "height": height,
        "pixelFormat": pixel_format,
        "rawBytes": byte_count,
        "rawCapture": True,
    }
    for field, value in expected.items():
        require(snapshot.get(field) == value, f"{label} {field} differs")
    relative = snapshot.get("rawFile")
    require(isinstance(relative, str), f"{label} rawFile is absent")
    root = capture_directory.resolve()
    path = (capture_directory / relative).resolve()
    require(path.is_relative_to(root), f"{label} rawFile escapes capture root")
    require(path.is_file(), f"{label} raw file is absent")
    payload = path.read_bytes()
    require(len(payload) == byte_count, f"{label} disk bytes differ")
    return payload


def output_payload(
    capture_directory: Path,
    untyped: object,
    *,
    label: str,
    pixel_format: int = 80,
    byte_count: int = BGRA_BYTES,
    width: int = WIDTH,
    height: int = HEIGHT,
) -> bytes:
    wrapper = mapping(untyped, label)
    require(wrapper.get("executed") is True, f"{label} did not execute")
    return snapshot_payload(
        capture_directory,
        wrapper.get("output"),
        label=label,
        pixel_format=pixel_format,
        byte_count=byte_count,
        width=width,
        height=height,
    )


def mismatch_metrics(
    reference: bytes,
    candidate: bytes,
    *,
    bytes_per_pixel: int = 4,
) -> JSONObject:
    require(len(reference) == len(candidate), "comparison byte lengths differ")
    require(
        bytes_per_pixel > 0 and len(reference) % bytes_per_pixel == 0,
        "comparison pixel stride differs",
    )
    mismatched_bytes = 0
    mismatched_pixels = 0
    maximum_delta = 0
    first = -1
    for offset in range(0, len(reference), bytes_per_pixel):
        pixel_differs = False
        for channel in range(bytes_per_pixel):
            index = offset + channel
            delta = abs(reference[index] - candidate[index])
            if delta:
                mismatched_bytes += 1
                pixel_differs = True
                if first < 0:
                    first = index
                maximum_delta = max(maximum_delta, delta)
        mismatched_pixels += pixel_differs
    return {
        "byteCount": len(reference),
        "mismatchedByteCount": mismatched_bytes,
        "mismatchedPixelCount": mismatched_pixels,
        "maximumChannelDelta": maximum_delta,
        "firstMismatchedByte": first,
        "exactByteMatch": mismatched_bytes == 0,
    }


def validate_reported_comparison(
    untyped: object,
    independent: Mapping[str, object],
    *,
    label: str,
) -> None:
    reported = mapping(untyped, label)
    require(reported.get("compared") is True, f"{label} was not compared")
    for field in (
        "byteCount",
        "mismatchedByteCount",
        "mismatchedPixelCount",
        "maximumChannelDelta",
        "firstMismatchedByte",
        "exactByteMatch",
    ):
        require(
            reported.get(field) == independent[field],
            f"{label} {field} differs",
        )


def expected_seed() -> bytes:
    payload = bytearray(BGRA_BYTES)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            offset = (y * WIDTH + x) * 4
            alpha = 64 + (x * 13 + y * 7 + 29) % 192
            payload[offset] = (x * 17 + y * 31 + 47) % (alpha + 1)
            payload[offset + 1] = (x * 43 + y * 11 + 83) % (alpha + 1)
            payload[offset + 2] = (x * 5 + y * 53 + 131) % (alpha + 1)
            payload[offset + 3] = alpha
    return bytes(payload)


def validate_intervention(untyped: object, *, label: str) -> None:
    intervention = mapping(untyped, label)
    require(
        intervention.get("name") == "positive-normal-x",
        f"{label} name differs",
    )
    edits = sequence(intervention.get("edits"), f"{label} edits")
    observed: list[tuple[object, object, object]] = []
    for edit in edits:
        record = mapping(edit, f"{label} edit")
        observed.append(
            (record.get("field"), record.get("recordOffset"), record.get("hex"))
        )
    require(
        tuple(observed) == FORCED_COVERAGE_EDITS,
        f"{label} edits differ",
    )


def indexed_layer_states(
    untyped: object,
    *,
    label: str,
) -> dict[tuple[int, ...], Mapping[str, object]]:
    states = sequence(untyped, label)
    result: dict[tuple[int, ...], Mapping[str, object]] = {}
    for untyped_state in states:
        state = mapping(untyped_state, f"{label} state")
        path = sequence(state.get("path"), f"{label} path")
        require(
            all(type(component) is int for component in path),
            f"{label} path component differs",
        )
        key = tuple(path)  # type: ignore[arg-type]
        require(key not in result, f"{label} path is duplicated")
        result[key] = state
    return result


def validate_geometry_transport(record: Mapping[str, object]) -> None:
    transport = mapping(
        record.get("finalHighlightVertexTailGeometryTransport"),
        "geometry transport",
    )
    expected = {
        "schemaVersion": 1,
        "requested": True,
        "source": "previously captured current-build Apple Irsd state",
        "sourceTimelineSHA256": (
            "17a69db193892e7e30c6069e88a63a4a3badfd23e93916d91b10b126a67c8e7c"
        ),
        "sourceSampleIndex": 28,
        "sourceRemainingFloat32Bits": "3dfdf500",
        "elementPositionFloat32Bits": ["c359020b", "c359020b"],
        "extentFloat32Bits": "43f7020b",
        "radiusFloat32Bits": "4377020b",
        "carrierOuterPaths": [list(path) for path in TRANSPORT_CARRIER_OUTER_PATHS],
        "carrierOuterBoundsFloat32Bits": [
            "00000000",
            "00000000",
            "43f00000",
            "43f00000",
        ],
        "elementPath": list(TRANSPORT_ELEMENT_PATH),
    }
    for field, value in expected.items():
        require(transport.get(field) == value, f"transport {field} differs")
    requested = indexed_layer_states(
        transport.get("requestedLayerStates"),
        label="requested transport",
    )
    require(
        set(requested) == {TRANSPORT_ELEMENT_PATH},
        "requested transport path differs",
    )
    element = requested[TRANSPORT_ELEMENT_PATH]
    require(
        element.get("bounds") == [0, 0, 494.0159606933594, 494.0159606933594]
        and element.get("position") == [-217.0079803466797, -217.0079803466797]
        and element.get("cornerRadius") == 247.0079803466797,
        "requested transport geometry differs",
    )

    render = mapping(record.get("render"), "render")
    before = mapping(render.get("liveRenderBoundaryBefore"), "live boundary before")
    after = mapping(render.get("liveRenderBoundaryAfter"), "live boundary after")
    require(
        before.get("executed") is True and after.get("executed") is True,
        "live geometry readback did not execute",
    )
    for name, boundary in (("before", before), ("after", after)):
        states = indexed_layer_states(
            boundary.get("layerStates"),
            label=f"live {name} states",
        )
        require(
            TRANSPORT_ELEMENT_PATH in states
            and set(TRANSPORT_CARRIER_OUTER_PATHS).issubset(states),
            f"live {name} topology differs",
        )
        live_element = states[TRANSPORT_ELEMENT_PATH]
        require(
            live_element.get("bounds")
            == [0, 0, 494.0159606933594, 494.0159606933594]
            and live_element.get("position")
            == [-217.0079803466797, -217.0079803466797]
            and live_element.get("cornerRadius") == 247.0079803466797,
            f"live {name} element geometry differs",
        )
        for path in TRANSPORT_CARRIER_OUTER_PATHS:
            state = states[path]
            require(
                state.get("bounds") == [0, 0, 480, 480]
                and state.get("position") == [0, 0],
                f"live {name} carrier geometry differs",
            )
    require(
        before.get("layerStatesSHA256") == after.get("layerStatesSHA256"),
        "live geometry changed during render",
    )
    require(
        before.get("backgroundFilterInputValuesSHA256")
        == after.get("backgroundFilterInputValuesSHA256"),
        "live filter changed during render",
    )


def validate_alpha_trace(
    capture_directory: Path,
    record: Mapping[str, object],
    *,
    role: str,
) -> tuple[bytes, int]:
    alpha = output_payload(
        capture_directory,
        record.get("alphaTrace"),
        label=f"{role} alpha trace",
        pixel_format=115,
        byte_count=RGBA16_BYTES,
    )
    require(sys.byteorder == "little", "validator host is not little-endian")
    words = memoryview(alpha).cast("H")
    nonzero = 0
    channel_mismatches = 0
    nonunit_output_alpha = 0
    for offset in range(0, len(words), 4):
        red, green, blue, output_alpha = words[offset : offset + 4]
        nonzero += (red & 0x7FFF) != 0
        channel_mismatches += red != green or red != blue
        nonunit_output_alpha += output_alpha != 0x3C00
    require(nonzero > 0, f"{role} forced alpha is inactive")
    require(channel_mismatches == 0, f"{role} alpha RGB channels differ")
    require(nonunit_output_alpha == 0, f"{role} alpha output alpha differs")
    require(
        record.get("alphaTraceNonzeroPixelCount") == nonzero
        and record.get("alphaTraceChannelMismatchPixelCount") == 0
        and record.get("alphaTraceNonUnitOutputAlphaPixelCount") == 0,
        f"{role} alpha counters differ",
    )
    return alpha, nonzero


def validate_source_intervention(
    capture_directory: Path,
    record: Mapping[str, object],
    *,
    role: str,
) -> JSONObject:
    intervention = mapping(
        record.get("sourceIntervention"),
        f"{role} source intervention",
    )
    expected = {
        "schemaVersion": 1,
        "bindingIndex": 4,
        "method": (
            "isolated replay binding override immediately before the selected draw"
        ),
        "finiteSourceEncoding": "opaque-bgra8",
        "finiteSourceHex": FINITE_SOURCE.hex(),
        "capturedAndFiniteSourceDiffer": True,
    }
    for field, value in expected.items():
        require(
            intervention.get(field) == value,
            f"{role} source intervention {field} differs",
        )
    captured_source = snapshot_payload(
        capture_directory,
        intervention.get("capturedSource"),
        label=f"{role} captured source",
        pixel_format=80,
        byte_count=4,
        width=1,
        height=1,
    )
    finite_source = snapshot_payload(
        capture_directory,
        intervention.get("finiteSource"),
        label=f"{role} finite source",
        pixel_format=80,
        byte_count=4,
        width=1,
        height=1,
    )
    require(finite_source == FINITE_SOURCE, f"{role} finite source bytes differ")
    require(
        captured_source != finite_source,
        f"{role} captured source equals finite control",
    )

    captured_alpha = output_payload(
        capture_directory,
        record.get("capturedSourceAlphaTrace"),
        label=f"{role} captured-source alpha trace",
        pixel_format=115,
        byte_count=RGBA16_BYTES,
    )
    finite_alpha = output_payload(
        capture_directory,
        record.get("alphaTrace"),
        label=f"{role} finite-source alpha trace",
        pixel_format=115,
        byte_count=RGBA16_BYTES,
    )
    comparison = mismatch_metrics(
        captured_alpha,
        finite_alpha,
        bytes_per_pixel=8,
    )
    require(
        comparison["mismatchedByteCount"] > 0
        and comparison["mismatchedPixelCount"] > 0,
        f"{role} texture-4 path-sensitivity control is inactive",
    )
    reported = mapping(
        record.get("sourcePathSensitivityComparison"),
        f"{role} source path comparison",
    )
    require(
        reported.get("bytesPerPixel") == 8,
        f"{role} source path pixel stride differs",
    )
    validate_reported_comparison(
        reported,
        comparison,
        label=f"{role} source path comparison",
    )
    require(
        record.get("sourcePathSensitive") is True,
        f"{role} sourcePathSensitive differs",
    )
    return {
        "capturedSourceSHA256": sha256_bytes(captured_source),
        "finiteSourceSHA256": sha256_bytes(finite_source),
        "pathSensitivityUnequalBytes": comparison["mismatchedByteCount"],
        "pathSensitivityUnequalPixels": comparison["mismatchedPixelCount"],
    }


def validate_role(
    capture_directory: Path,
    untyped: object,
    *,
    role: str,
    seed_expected: bytes,
    candidate_source_sha256: str,
) -> JSONObject:
    record = mapping(untyped, f"{role} record")
    expected_scalars = {
        "schemaVersion": 2,
        "executed": True,
        "role": role,
        "pipelineLabel": PIPELINES[role],
        "capturedAppleFunctionUnmodified": True,
        "capturedAppleResourceMutated": False,
        "liveAppleFrameMutated": False,
        "usesAuxiliaryAttachment": role == "Irsd",
        "alphaOracleHalfWords": list(ALPHA_ORACLE_WORDS),
        "matrixCaseCount": len(MATRIX_CASES),
        "casesExecuted": True,
        "positiveControlsPassed": True,
        "candidatesExact": True,
    }
    for field, value in expected_scalars.items():
        require(record.get(field) == value, f"{role} {field} differs")
    draw_index = record.get("drawIndex")
    require(type(draw_index) is int and draw_index >= 0, f"{role} drawIndex differs")
    validate_intervention(
        record.get("forcedCoverageIntervention"),
        label=f"{role} forced coverage",
    )
    source_summary = validate_source_intervention(
        capture_directory,
        record,
        role=role,
    )
    _, nonzero_alpha = validate_alpha_trace(
        capture_directory,
        record,
        role=role,
    )

    seed_record = mapping(record.get("seed"), f"{role} seed")
    require(
        seed_record.get("schemaVersion") == 1
        and seed_record.get("encoding") == "premultiplied-bgra8"
        and seed_record.get("formula")
        == (
            "a=64+(13x+7y+29)%192; b=(17x+31y+47)%(a+1); "
            "g=(43x+11y+83)%(a+1); r=(5x+53y+131)%(a+1)"
        ),
        f"{role} seed declaration differs",
    )
    seed = snapshot_payload(
        capture_directory,
        seed_record.get("output"),
        label=f"{role} seed",
        pixel_format=80,
        byte_count=BGRA_BYTES,
    )
    require(seed == seed_expected, f"{role} seed bytes differ")

    candidate = mapping(record.get("candidate"), f"{role} candidate")
    candidate_expected = {
        "classification": "independent recovered mode-9 binary16 compositor",
        "capturedAppleFunctionUnmodified": False,
        "fastMathEnabled": False,
        "sourceSHA256": candidate_source_sha256,
        "destinationDivisionMode": 0,
        "vibrantArithmeticMode": 9,
        "sourceConstructionMode": 1,
        "sourceDivisionMode": 0,
    }
    for field, value in candidate_expected.items():
        require(candidate.get(field) == value, f"{role} candidate {field} differs")
    descriptor = mapping(
        candidate.get("pipelineDescriptor"),
        f"{role} candidate descriptor",
    )
    require(
        descriptor.get("label") == "lg.current-compositor-independent-mode9"
        and descriptor.get("vertexFunction") == "current_compositor_vertex"
        and descriptor.get("fragmentFunction") == "current_compositor_fragment",
        f"{role} candidate pipeline differs",
    )

    cases = sequence(record.get("cases"), f"{role} cases")
    require(len(cases) == len(MATRIX_CASES), f"{role} case count differs")
    by_name = {
        mapping(case, f"{role} case").get("name"): mapping(
            case,
            f"{role} case",
        )
        for case in cases
    }
    require(set(by_name) == set(MATRIX_CASES), f"{role} case names differ")
    total_activity_bytes = 0
    total_activity_pixels = 0
    output_hashes: dict[str, str] = {}
    for name in MATRIX_CASES:
        case = by_name[name]
        matrix_words = sequence(
            case.get("matrixHalfWordsLittleEndian"),
            f"{role} {name} matrix words",
        )
        require(
            len(matrix_words) == 24
            and all(
                isinstance(word, str)
                and len(word) == 6
                and word.startswith("0x")
                for word in matrix_words
            ),
            f"{role} {name} matrix words differ",
        )
        combined = mapping(
            case.get("uniformIntervention"),
            f"{role} {name} intervention",
        )
        require(combined.get("name") == name, f"{role} {name} intervention name differs")
        combined_edits = sequence(
            combined.get("edits"),
            f"{role} {name} edits",
        )
        require(
            len(combined_edits) >= len(FORCED_COVERAGE_EDITS),
            f"{role} {name} edits are incomplete",
        )
        forced_prefix = {
            (
                mapping(edit, "combined edit").get("field"),
                mapping(edit, "combined edit").get("recordOffset"),
                mapping(edit, "combined edit").get("hex"),
            )
            for edit in combined_edits
        }
        require(
            set(FORCED_COVERAGE_EDITS).issubset(forced_prefix),
            f"{role} {name} forced edits differ",
        )

        apple = output_payload(
            capture_directory,
            case.get("apple"),
            label=f"{role} {name} Apple",
        )
        independent_candidate = output_payload(
            capture_directory,
            case.get("candidate"),
            label=f"{role} {name} candidate",
        )
        activity = mismatch_metrics(seed, apple)
        require(
            activity["mismatchedByteCount"] > 0
            and activity["mismatchedPixelCount"] > 0,
            f"{role} {name} Apple positive control is inactive",
        )
        validate_reported_comparison(
            case.get("activityComparison"),
            activity,
            label=f"{role} {name} activity comparison",
        )
        comparison = mismatch_metrics(apple, independent_candidate)
        require(
            comparison["exactByteMatch"] is True,
            f"{role} {name} candidate bytes differ",
        )
        validate_reported_comparison(
            case.get("candidateComparison"),
            comparison,
            label=f"{role} {name} candidate comparison",
        )
        total_activity_bytes += int(activity["mismatchedByteCount"])
        total_activity_pixels += int(activity["mismatchedPixelCount"])
        output_hashes[name] = sha256_bytes(apple)
    return {
        "role": role,
        "pipelineLabel": PIPELINES[role],
        "drawIndex": draw_index,
        "nonzeroAlphaPixels": nonzero_alpha,
        "matrixCaseCount": len(MATRIX_CASES),
        "positiveControlUnequalBytes": total_activity_bytes,
        "positiveControlUnequalPixels": total_activity_pixels,
        "comparedCandidateBytes": len(MATRIX_CASES) * BGRA_BYTES,
        "sourceIntervention": source_summary,
        "outputSHA256": output_hashes,
    }


def validate(
    capture_directory: Path,
    preregistration_path: Path,
    preflight_path: Path,
) -> JSONObject:
    preregistration = load_json(preregistration_path)
    require(
        preregistration.get("currentFinalCompositorTransferPreregistrationSchemaVersion")
        == 2,
        "preregistration schema differs",
    )
    superseded = mapping(
        preregistration.get("supersedesFailedRun"),
        "supersedesFailedRun",
    )
    require(
        superseded.get("captureCommit")
        == "b838af32b291561b362bd1dc0243ac0213359978"
        and superseded.get("timelineSHA256")
        == "52e523f76997426348b6ce83c9f3dcae08e5fe05936b6c6dd1ccc0195e0b1464"
        and superseded.get("frozenValidatorExitStatus") == 1
        and superseded.get("promotedEvidence") is False
        and superseded.get("arithmeticCasesChanged") is False
        and superseded.get("candidateChanged") is False
        and superseded.get("toleranceChanged") is False,
        "failed-run amendment differs",
    )
    nonvacuity = mapping(preregistration.get("nonvacuity"), "nonvacuity")
    require(
        nonvacuity.get("finiteSourceSHA256")
        == sha256_bytes(FINITE_SOURCE)
        and nonvacuity.get("sourcePathSensitivityRequirement")
        == (
            "the captured-source and finite-source RGBA16Float alpha-oracle "
            "outputs must differ by at least one byte and one 8-byte pixel for "
            "each current function"
        ),
        "finite-source preregistration differs",
    )
    validate_sources(preregistration)
    candidate_source_sha256 = preregistration.get("candidateMetalSourceSHA256")
    require(
        isinstance(candidate_source_sha256, str)
        and len(candidate_source_sha256) == 64,
        "candidate Metal source hash is malformed",
    )

    preflight = load_json(preflight_path)
    require(preflight.get("passed") is True, "Retina preflight did not pass")
    require(preflight.get("backingScaleFactor") == 2, "Retina scale differs")
    require(
        preflight.get("physicalPixels") == [3456, 2234],
        "physical Retina display differs",
    )

    runtime = load_json(capture_directory / "transition-timeline.json")
    expected_runtime = {
        "material": "regular",
        "appearance": "dark",
        "direction": "dematerialize",
        "sampleCount": 33,
        "windowBackingScaleFactor": 2,
        "failedSamples": 0,
        "expectedWindowPixels": [2048, 2048],
    }
    for field, value in expected_runtime.items():
        require(runtime.get(field) == value, f"runtime {field} differs")
    geometry = mapping(runtime.get("geometry"), "runtime geometry")
    require(
        geometry.get("name") == "circle-480-center"
        and geometry.get("width") == 480
        and geometry.get("height") == 480,
        "runtime geometry differs",
    )
    uniforms = mapping(
        runtime.get("dynamicBackgroundUniforms"),
        "dynamicBackgroundUniforms",
    )
    expected_uniforms = {
        "schemaVersion": 9,
        "requested": True,
        "executed": True,
        "evidenceMode": "controlled-replay-v1",
        "sampleIndices": [SAMPLE],
        "sampleCount": 1,
        "executedSampleCount": 1,
        "presentationLayerReplayed": True,
        "presentationLayerAssignedToCARenderer": False,
        "freshStaticCarrier": True,
        "detachedLayerTreeCopies": False,
    }
    for field, value in expected_uniforms.items():
        require(uniforms.get(field) == value, f"dynamic {field} differs")
    records = sequence(uniforms.get("records"), "dynamic records")
    require(len(records) == 1, "dynamic record count differs")
    record = mapping(records[0], "sample record")
    require(record.get("sampleIndex") == SAMPLE, "sample selection differs")
    validate_geometry_transport(record)
    render = mapping(record.get("render"), "sample render")
    exact = mapping(render.get("exactPassReplay"), "exactPassReplay")
    require(exact.get("executed") is True, "exact pass replay did not execute")
    transfer = mapping(
        exact.get("currentFinalCompositorTransfer"),
        "currentFinalCompositorTransfer",
    )
    expected_transfer = {
        "schemaVersion": 2,
        "executed": True,
        "selectionPolicy": (
            "exactly one current Iscd and one immediately later current Irsd draw "
            "in the frozen sample"
        ),
        "activityPolicy": (
            "replace only texture 4 in each isolated replay with the frozen "
            "opaque finite BGRA8 texel 4080c0ff"
        ),
        "capturedAppleFunctionsUnmodified": True,
        "capturedAppleResourcesMutated": False,
        "liveAppleFrameMutated": False,
        "pipelineLabels": list(PIPELINES.values()),
        "recordCount": 2,
    }
    for field, value in expected_transfer.items():
        require(transfer.get(field) == value, f"transfer {field} differs")
    role_records = sequence(transfer.get("records"), "transfer records")
    require(len(role_records) == 2, "transfer role count differs")
    by_role = {
        mapping(item, "transfer role").get("role"): item for item in role_records
    }
    require(set(by_role) == set(PIPELINES), "transfer roles differ")

    seed = expected_seed()
    summaries = [
        validate_role(
            capture_directory,
            by_role[role],
            role=role,
            seed_expected=seed,
            candidate_source_sha256=candidate_source_sha256,
        )
        for role in PIPELINES
    ]
    require(
        int(summaries[0]["drawIndex"]) < int(summaries[1]["drawIndex"]),
        "current Iscd/Irsd draw order differs",
    )
    return {
        "currentFinalCompositorTransferResultSchemaVersion": 2,
        "accepted": True,
        "captureDirectory": capture_directory.name,
        "sampleIndex": SAMPLE,
        "physicalRetina": True,
        "candidateMetalSourceSHA256": candidate_source_sha256,
        "roles": summaries,
        "matrixCasesPerRole": len(MATRIX_CASES),
        "positiveControlCount": len(PIPELINES) * len(MATRIX_CASES),
        "exactCandidateComparisonCount": len(PIPELINES) * len(MATRIX_CASES),
        "comparedCandidateBytes": len(PIPELINES) * len(MATRIX_CASES) * BGRA_BYTES,
        "unequalCandidateBytes": 0,
        "remainingAppleConstructionQuestions": 0,
        "remainingProductProofs": [
            "Walle-shaped physical Retina color/compositor transfer",
            "fresh production-Walle frame with zero unequal bytes",
        ],
        "productionParity": False,
        "shaderChangeAuthorized": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture_directory", type=Path)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = validate(
            args.capture_directory,
            args.preregistration,
            args.preflight,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"validation failed: {error}", file=sys.stderr)
        return 1
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
