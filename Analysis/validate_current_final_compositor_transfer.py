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
SOURCE_BASE_PIXELS = 768
SOURCE_MIP_COUNT = 6
FINITE_SOURCE_SALT = 0x6D2B79F5
QUARTZCORE_LIBRARY_PATH = (
    "/System/Library/Frameworks/QuartzCore.framework/Versions/A/"
    "Resources/default.metallib"
)
QUARTZCORE_LIBRARY_BYTES = 160_220_928
QUARTZCORE_LIBRARY_SHA256 = (
    "eb32770f9a595d777a040dee7454fe30d668ccacaa803f35ddb2f97646193ca7"
)
QUARTZCORE_G13G_SLICE_SHA256 = (
    "5566617c9a00a05fb768d3e659308288e17e6b21c3dc8df903e99a7c914ef119"
)
CAPTURED_VERTEX_STREAM_SHA256 = (
    "9c11e428af9990dc729caa8936f17e25f53a488e5ad8e38dda11550b3d081d3b"
)
WIDENED_IRSD_VERTEX_STREAM_SHA256 = (
    "736890b297ce90ad499ca3e6c010d3667cd09db70806d1f044d9c6314f258afd"
)
IMAGE_FUNCTION = {"Iscd": 21, "Irsd": 20}
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
    mipmap_level: int | None = None,
    mipmap_level_count: int | None = None,
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
    if mipmap_level is not None:
        require(
            snapshot.get("mipmapLevel") == mipmap_level,
            f"{label} mipmapLevel differs",
        )
    if mipmap_level_count is not None:
        require(
            snapshot.get("mipmapLevelCount") == mipmap_level_count,
            f"{label} mipmapLevelCount differs",
        )
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


def expected_finite_source_mips() -> tuple[bytes, ...]:
    payloads: list[bytes] = []
    for level in range(SOURCE_MIP_COUNT):
        width = max(1, SOURCE_BASE_PIXELS >> level)
        height = max(1, SOURCE_BASE_PIXELS >> level)
        payload = bytearray(width * height * 4)
        for y in range(height):
            for x in range(width):
                word = (
                    x * 0x045D9F3B ^ y * 0x0119DE1F ^ level * 0x9E3779B9
                ) & 0xFFFF_FFFF
                word ^= FINITE_SOURCE_SALT
                offset = (y * width + x) * 4
                payload[offset] = word & 0xFF
                payload[offset + 1] = (word >> 8) & 0xFF
                payload[offset + 2] = (word >> 16) & 0xFF
                payload[offset + 3] = 0xFF
        payloads.append(bytes(payload))
    return tuple(payloads)


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


def validate_system_specialization(
    untyped: object,
    *,
    role: str,
) -> None:
    specialization = mapping(untyped, f"{role} system specialization")
    expected = {
        "schemaVersion": 1,
        "role": role,
        "libraryPath": QUARTZCORE_LIBRARY_PATH,
        "libraryByteCount": QUARTZCORE_LIBRARY_BYTES,
        "librarySHA256": QUARTZCORE_LIBRARY_SHA256,
        "g13gSliceSHA256": QUARTZCORE_G13G_SLICE_SHA256,
        "baseFunction": "fixed_frag_lph_cpf",
        "functionConstantCount": 60,
        "generic": False,
        "vertexLayout": 0,
        "framebufferFetch": True,
        "attachmentCount": 2,
        "textureFunction": 66,
        "blendFunction": 43,
        "imageCount": 1,
        "destinationCount": 1,
        "extendedRange": False,
        "imageFunction0": IMAGE_FUNCTION[role],
        "texcoordCount0": 1,
        "allUnlistedConstantsZero": True,
        "specializedFunctionRuntimeName": "fixed_frag_lph_cpf",
    }
    for field, value in expected.items():
        require(
            specialization.get(field) == value,
            f"{role} system specialization {field} differs",
        )


def validate_geometry_activity_control(
    untyped: object,
    *,
    role: str,
) -> None:
    control = mapping(untyped, f"{role} geometry activity control")
    common = {
        "schemaVersion": 1,
        "vertexCount": 16,
        "vertexStride": 48,
        "positionOffsets": [0, 4],
        "capturedVertexStreamSHA256": CAPTURED_VERTEX_STREAM_SHA256,
        "capturedApplePipelineMutated": False,
        "liveAppleFrameMutated": False,
    }
    for field, value in common.items():
        require(
            control.get(field) == value,
            f"{role} geometry activity {field} differs",
        )
    if role == "Iscd":
        expected = {
            "method": "captured-Iscd-geometry",
            "vertexStreamMutated": False,
        }
    else:
        expected = {
            "method": "widen-Irsd-center-seams-v1",
            "halfExpansionPixels": 32,
            "capturedColumnXFloat32Bits": [
                "436212e0",
                "43f10a76",
                "43f10a75",
                "443885be",
            ],
            "capturedRowYFloat32Bits": [
                "44477b48",
                "44077ac5",
                "44077ac6",
                "438ef485",
            ],
            "widenedColumnXFloat32Bits": [
                "436212e0",
                "43e10a76",
                "4400853b",
                "443885be",
            ],
            "widenedRowYFloat32Bits": [
                "44477b48",
                "440f7ac6",
                "43fef58c",
                "438ef485",
            ],
            "widenedVertexStreamSHA256": WIDENED_IRSD_VERTEX_STREAM_SHA256,
            "vertexStreamMutated": True,
        }
    for field, value in expected.items():
        require(
            control.get(field) == value,
            f"{role} geometry activity {field} differs",
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
            live_element.get("bounds") == [0, 0, 494.0159606933594, 494.0159606933594]
            and live_element.get("position") == [-217.0079803466797, -217.0079803466797]
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
        "schemaVersion": 2,
        "bindingIndex": 3,
        "method": (
            "isolated replay binding override immediately before the selected draw"
        ),
        "finiteSourceEncoding": "opaque-bgra8-six-mip-coordinate-hash-v1",
        "finiteSourceFormula": (
            "word=u32(x*0x045d9f3b ^ y*0x0119de1f ^ level*0x9e3779b9) "
            "^ 0x6d2b79f5; bgra=(word[7:0],word[15:8],word[23:16],0xff)"
        ),
        "finiteSourceSalt": "0x6d2b79f5",
        "basePixels": [SOURCE_BASE_PIXELS, SOURCE_BASE_PIXELS],
        "mipmapLevelCount": SOURCE_MIP_COUNT,
        "capturedAndFiniteSourceDiffer": True,
    }
    for field, value in expected.items():
        require(
            intervention.get(field) == value,
            f"{role} source intervention {field} differs",
        )
    captured_snapshots = sequence(
        intervention.get("capturedSourceMips"),
        f"{role} captured source mips",
    )
    finite_snapshots = sequence(
        intervention.get("finiteSourceMips"),
        f"{role} finite source mips",
    )
    require(
        len(captured_snapshots) == SOURCE_MIP_COUNT
        and len(finite_snapshots) == SOURCE_MIP_COUNT,
        f"{role} source mip count differs",
    )
    expected_mips = expected_finite_source_mips()
    captured_mips: list[bytes] = []
    finite_mips: list[bytes] = []
    for level, expected_mip in enumerate(expected_mips):
        width = max(1, SOURCE_BASE_PIXELS >> level)
        height = max(1, SOURCE_BASE_PIXELS >> level)
        captured_mips.append(
            snapshot_payload(
                capture_directory,
                captured_snapshots[level],
                label=f"{role} captured source mip {level}",
                pixel_format=80,
                byte_count=width * height * 4,
                width=width,
                height=height,
                mipmap_level=level,
                mipmap_level_count=SOURCE_MIP_COUNT,
            )
        )
        finite_mip = snapshot_payload(
            capture_directory,
            finite_snapshots[level],
            label=f"{role} finite source mip {level}",
            pixel_format=80,
            byte_count=width * height * 4,
            width=width,
            height=height,
            mipmap_level=level,
            mipmap_level_count=SOURCE_MIP_COUNT,
        )
        require(
            finite_mip == expected_mip,
            f"{role} finite source mip {level} bytes differ",
        )
        finite_mips.append(finite_mip)
    require(
        captured_mips != finite_mips,
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
        f"{role} texture-3 path-sensitivity control is inactive",
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
        "capturedSourceSHA256": sha256_bytes(b"".join(captured_mips)),
        "finiteSourceSHA256": sha256_bytes(b"".join(finite_mips)),
        "mipmapLevelCount": SOURCE_MIP_COUNT,
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
        "schemaVersion": 4,
        "executed": True,
        "role": role,
        "pipelineLabel": PIPELINES[role],
        "capturedAppleFunctionUnmodified": True,
        "capturedAppleResourceMutated": False,
        "liveAppleFrameMutated": False,
        "alphaOracleHalfWords": list(ALPHA_ORACLE_WORDS),
        "matrixCaseCount": len(MATRIX_CASES),
        "casesExecuted": True,
        "positiveControlsPassed": True,
        "systemSpecializationExact": True,
        "candidatesExact": True,
    }
    for field, value in expected_scalars.items():
        require(record.get(field) == value, f"{role} {field} differs")
    uses_auxiliary = record.get("usesAuxiliaryAttachment")
    require(
        type(uses_auxiliary) is bool and (role != "Irsd" or uses_auxiliary is True),
        f"{role} auxiliary attachment topology differs",
    )
    draw_index = record.get("drawIndex")
    require(type(draw_index) is int and draw_index >= 0, f"{role} drawIndex differs")
    validate_system_specialization(
        record.get("systemSpecialization"),
        role=role,
    )
    validate_geometry_activity_control(
        record.get("geometryActivityControl"),
        role=role,
    )
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
    total_system_comparison_bytes = 0
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
                isinstance(word, str) and len(word) == 6 and word.startswith("0x")
                for word in matrix_words
            ),
            f"{role} {name} matrix words differ",
        )
        combined = mapping(
            case.get("uniformIntervention"),
            f"{role} {name} intervention",
        )
        require(
            combined.get("name") == name, f"{role} {name} intervention name differs"
        )
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
        system_specialized_apple = output_payload(
            capture_directory,
            case.get("systemSpecializedApple"),
            label=f"{role} {name} system-specialized Apple",
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
        system_comparison = mismatch_metrics(apple, system_specialized_apple)
        require(
            system_comparison["exactByteMatch"] is True,
            f"{role} {name} system specialization bytes differ",
        )
        validate_reported_comparison(
            case.get("capturedVsSystemSpecializationComparison"),
            system_comparison,
            label=f"{role} {name} system specialization comparison",
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
        total_system_comparison_bytes += len(apple)
        output_hashes[name] = sha256_bytes(apple)
    return {
        "role": role,
        "pipelineLabel": PIPELINES[role],
        "drawIndex": draw_index,
        "nonzeroAlphaPixels": nonzero_alpha,
        "matrixCaseCount": len(MATRIX_CASES),
        "positiveControlUnequalBytes": total_activity_bytes,
        "positiveControlUnequalPixels": total_activity_pixels,
        "comparedSystemSpecializationBytes": total_system_comparison_bytes,
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
        preregistration.get(
            "currentFinalCompositorTransferPreregistrationSchemaVersion"
        )
        == 4,
        "preregistration schema differs",
    )
    descriptor_capture = mapping(
        preregistration.get("descriptorCapture"),
        "descriptorCapture",
    )
    require(
        descriptor_capture.get("installationBoundary") == "before NSApplication.shared"
        and descriptor_capture.get("selectors")
        == [
            "newRenderPipelineStateWithDescriptor:error:",
            "newRenderPipelineStateWithDescriptor:options:reflection:error:",
            "newRenderPipelineStateWithDescriptor:completionHandler:",
            "newRenderPipelineStateWithDescriptor:options:completionHandler:",
            "newPrecompiledRenderPipelineStateWithDescriptor:options:"
            "pipelineCache:completionHandler:",
        ],
        "descriptor-capture preregistration differs",
    )
    superseded = mapping(
        preregistration.get("supersedesFailedRun"),
        "supersedesFailedRun",
    )
    require(
        superseded.get("captureCommit") == "b838af32b291561b362bd1dc0243ac0213359978"
        and superseded.get("timelineSHA256")
        == "52e523f76997426348b6ce83c9f3dcae08e5fe05936b6c6dd1ccc0195e0b1464"
        and superseded.get("frozenValidatorExitStatus") == 1
        and superseded.get("promotedEvidence") is False
        and superseded.get("arithmeticCasesChanged") is False
        and superseded.get("candidateChanged") is False
        and superseded.get("toleranceChanged") is False,
        "failed-run amendment differs",
    )
    superseded_v2 = mapping(
        preregistration.get("supersedesFailedV2Run"),
        "supersedesFailedV2Run",
    )
    observed_v2 = mapping(
        superseded_v2.get("observedTopology"),
        "v2 observed topology",
    )
    inherited_texture = mapping(
        observed_v2.get("inheritedTexture3"),
        "v2 inherited texture 3",
    )
    require(
        superseded_v2.get("captureCommit") == "8c7dd82ebe0c0abbb3d04aa005adfd2ddc79848b"
        and superseded_v2.get("timelineSHA256")
        == "105832a92ff8211ffbcb55492ac2c09a4bd16964c592a8f58a66aaa333c20ef1"
        and superseded_v2.get("nativeCaptureExitStatus") == 0
        and superseded_v2.get("frozenValidatorExitStatus") == 1
        and superseded_v2.get("promotedEvidence") is False
        and superseded_v2.get("arithmeticCasesChanged") is False
        and superseded_v2.get("candidateChanged") is False
        and superseded_v2.get("toleranceChanged") is False
        and observed_v2.get("IscdDescriptorAvailable") is False
        and observed_v2.get("IrsdDescriptorAvailable") is True
        and observed_v2.get("texture4BoundAtEitherCurrentDraw") is False
        and inherited_texture
        == {
            "bindingSequence": 37,
            "width": 768,
            "height": 768,
            "pixelFormat": 80,
            "mipmapLevelCount": 6,
            "sampleCount": 1,
            "textureType": 2,
        },
        "failed-v2 amendment differs",
    )
    superseded_v3 = mapping(
        preregistration.get("supersedesFailedV3Run"),
        "supersedesFailedV3Run",
    )
    observed_v3 = mapping(
        superseded_v3.get("observedTransport"),
        "v3 observed transport",
    )
    require(
        superseded_v3.get("captureCommit") == "2e41aba0275a5e829c43f283071b462d8ac675b3"
        and superseded_v3.get("timelineSHA256")
        == "22296e449db47aff8bbd142e2b4ef6b33b0a68a31bdfc6fc053d0f91bd457cec"
        and superseded_v3.get("nativeCaptureExitStatus") == 0
        and superseded_v3.get("frozenValidatorExitStatus") == 1
        and superseded_v3.get("promotedEvidence") is False
        and superseded_v3.get("arithmeticCasesChanged") is False
        and superseded_v3.get("candidateChanged") is False
        and superseded_v3.get("toleranceChanged") is False
        and observed_v3.get("IscdPrivateBitcodeRebuildFailed") is True
        and observed_v3.get("IrsdPixelSampleCoverage") == 0
        and observed_v3.get("IrsdPositiveMatrixCaseCount") == 0
        and observed_v3.get("capturedVertexStreamSHA256")
        == CAPTURED_VERTEX_STREAM_SHA256,
        "failed-v3 amendment differs",
    )
    specialization = mapping(
        preregistration.get("systemSpecialization"),
        "systemSpecialization",
    )
    require(
        specialization.get("libraryPath") == QUARTZCORE_LIBRARY_PATH
        and specialization.get("libraryByteCount") == QUARTZCORE_LIBRARY_BYTES
        and specialization.get("librarySHA256") == QUARTZCORE_LIBRARY_SHA256
        and specialization.get("g13gSliceSHA256") == QUARTZCORE_G13G_SLICE_SHA256
        and specialization.get("baseFunction") == "fixed_frag_lph_cpf"
        and specialization.get("functionConstantCount") == 60
        and specialization.get("extendedRange") is False
        and specialization.get("imageFunctionByRole") == IMAGE_FUNCTION
        and specialization.get("capturedComparisonRequirement")
        == (
            "each reconstructed system specialization must equal its captured "
            "Apple pipeline byte-for-byte in all seven matrix cases"
        ),
        "system-specialization preregistration differs",
    )
    nonvacuity = mapping(preregistration.get("nonvacuity"), "nonvacuity")
    expected_source_mips = expected_finite_source_mips()
    require(
        nonvacuity.get("finiteSourceSHA256")
        == sha256_bytes(b"".join(expected_source_mips))
        and nonvacuity.get("finiteSourceMipSHA256")
        == [sha256_bytes(payload) for payload in expected_source_mips]
        and nonvacuity.get("finiteSourceFormula")
        == (
            "word=u32(x*0x045d9f3b ^ y*0x0119de1f ^ level*0x9e3779b9) "
            "^ 0x6d2b79f5; bgra=(word[7:0],word[15:8],word[23:16],0xff)"
        )
        and nonvacuity.get("sourcePathSensitivityRequirement")
        == (
            "the captured-source and finite-source RGBA16Float alpha-oracle "
            "outputs must differ by at least one byte and one 8-byte pixel for "
            "each current function"
        ),
        "finite-source preregistration differs",
    )
    geometry_activity = mapping(
        nonvacuity.get("geometryActivity"),
        "geometry activity",
    )
    require(
        geometry_activity.get("IscdMethod") == "captured-Iscd-geometry"
        and geometry_activity.get("IrsdMethod") == "widen-Irsd-center-seams-v1"
        and geometry_activity.get("IrsdHalfExpansionPixels") == 32
        and geometry_activity.get("capturedVertexStreamSHA256")
        == CAPTURED_VERTEX_STREAM_SHA256
        and geometry_activity.get("widenedIrsdVertexStreamSHA256")
        == WIDENED_IRSD_VERTEX_STREAM_SHA256
        and geometry_activity.get("capturedApplePipelineChanged") is False
        and geometry_activity.get("liveAppleFrameChanged") is False,
        "geometry-activity preregistration differs",
    )
    validate_sources(preregistration)
    candidate_source_sha256 = preregistration.get("candidateMetalSourceSHA256")
    require(
        isinstance(candidate_source_sha256, str) and len(candidate_source_sha256) == 64,
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
        "schemaVersion": 4,
        "executed": True,
        "selectionPolicy": (
            "exactly one current Iscd and one immediately later current Irsd draw "
            "in the frozen sample"
        ),
        "activityPolicy": (
            "replace only inherited texture 3 in each isolated replay with "
            "the frozen opaque six-mip 768x768 BGRA8 pattern; retain captured "
            "Iscd geometry and widen only the Irsd center seams by 32 pixels "
            "per side in its isolated replay"
        ),
        "systemSpecializationPolicy": (
            "instantiate QuartzCore fixed_frag_lph_cpf from the pinned system "
            "default.metallib with the statically decoded non-extended Iscd/"
            "Irsd constants and require exact BGRA8 equality to each captured "
            "Apple pipeline"
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
        "currentFinalCompositorTransferResultSchemaVersion": 4,
        "accepted": True,
        "captureDirectory": capture_directory.name,
        "sampleIndex": SAMPLE,
        "physicalRetina": True,
        "candidateMetalSourceSHA256": candidate_source_sha256,
        "roles": summaries,
        "matrixCasesPerRole": len(MATRIX_CASES),
        "positiveControlCount": len(PIPELINES) * len(MATRIX_CASES),
        "exactSystemSpecializationComparisonCount": (
            len(PIPELINES) * len(MATRIX_CASES)
        ),
        "comparedSystemSpecializationBytes": (
            len(PIPELINES) * len(MATRIX_CASES) * BGRA_BYTES
        ),
        "unequalSystemSpecializationBytes": 0,
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
