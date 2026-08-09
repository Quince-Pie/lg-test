#!/usr/bin/env python3
"""Compare native AGX border interpolants with the frozen independent axis."""

import argparse
import base64
import hashlib
import json
import re
import zlib
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np


type JsonObject = dict[str, Any]

SCHEMA_VERSION = 1
RIG_VERSION = "metal-raster-border-interpolant-transfer-1.0.0"
TARGET_SIZE = 1_024
PRIMITIVE_COUNT = 8
ACTIVE_BOUNDS = (256, 256, 768, 768)
ACTIVE_PIXEL_COUNT = 512 * 512
SENTINEL = np.uint32(0xFFFF_FFFF)
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")

PREREGISTRATION = Path(__file__).with_name(
    "natural_sample28_border_interpolant_transport_preregistration.json"
)
PREREGISTRATION_REPOSITORY_PATH = (
    "Analysis/natural_sample28_border_interpolant_transport_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "b90598ad886cf2b2ad6034e6008b23928c6d46252012466597ceb01ec1768d96"
)
AXIS_ARCHIVE = Path(__file__).with_name("natural_sample28_border_axis_u32le.zlib.b64")
AXIS_ARCHIVE_REPOSITORY_PATH = "Analysis/natural_sample28_border_axis_u32le.zlib.b64"
AXIS_ARCHIVE_FILE_SHA256 = (
    "bca0ca6db1c8570bfc54956527f1f67e2ff553bf959e30e04271ed45051b1035"
)
AXIS_COMPRESSED_SHA256 = (
    "72311e605a756b12a14b45adcd4f4a9a1bbce4800161254478c9b575ad732cd6"
)
AXIS_SHA256 = "e73c03674f15f0301581d48c67419bb1324e2b417735817a7ed489024d03faf1"
AXIS_BYTES = PRIMITIVE_COUNT * TARGET_SIZE * 4 * 4
VERTEX_SHA256 = "fce89df436fd7a0ec9b00d171c40be676023facfaf49e76366b1ec9f0cac3c62"
INDEX_SHA256 = "3fdf4e60209c103fbcf42515c4f2bda4613dae912e198abe0c58097a0106e572"
TIMELINE_SHA256 = "c028e232c0eb06ade31f826578c7209ea2e19f69b65a65cdc723187bc34adc44"

CENTER_FILE = "center-interpolants.rgba32ui.raw"
DERIVATIVE_X_FILE = "derivative-x.rgba32ui.raw"
DERIVATIVE_Y_FILE = "derivative-y.rgba32ui.raw"
PRIMITIVE_FILE = "primitive.r32ui.raw"
OUTPUT_LAYOUT = (
    (CENTER_FILE, 4),
    (DERIVATIVE_X_FILE, 4),
    (DERIVATIVE_Y_FILE, 4),
    (PRIMITIVE_FILE, 1),
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def load_frozen_axis() -> np.ndarray:
    preregistration_raw = PREREGISTRATION.read_bytes()
    preregistration: JsonObject = json.loads(preregistration_raw)
    correction = preregistration.get("preAnalysisCorrection", {})
    axis_record = preregistration.get("frozenEvidence", {}).get("independentAxis", {})
    archive_record = axis_record.get("archive", {})
    if (
        sha256_bytes(preregistration_raw) != PREREGISTRATION_SHA256
        or preregistration.get("schemaVersion") != SCHEMA_VERSION
        or correction.get("rejectedCommit") != "421dce8"
        or correction.get("outputComparedAgainstCandidate") is not False
        or axis_record.get("byteCount") != AXIS_BYTES
        or axis_record.get("sha256") != AXIS_SHA256
        or axis_record.get("comparedComponents") != ["sdf-x", "sdf-y"]
        or archive_record.get("file") != AXIS_ARCHIVE_REPOSITORY_PATH
        or archive_record.get("compressedByteCount") != 6_769
        or archive_record.get("compressedSha256") != AXIS_COMPRESSED_SHA256
    ):
        raise ValueError("border-interpolant preregistration differs")

    archive_raw = AXIS_ARCHIVE.read_bytes()
    if sha256_bytes(archive_raw) != AXIS_ARCHIVE_FILE_SHA256:
        raise ValueError("border-interpolant axis archive file differs")
    compressed = base64.b64decode(b"".join(archive_raw.split()), validate=True)
    if len(compressed) != 6_769 or sha256_bytes(compressed) != AXIS_COMPRESSED_SHA256:
        raise ValueError("border-interpolant compressed axis differs")
    axis_raw = zlib.decompress(compressed)
    if len(axis_raw) != AXIS_BYTES or sha256_bytes(axis_raw) != AXIS_SHA256:
        raise ValueError("border-interpolant independent axis differs")
    return np.frombuffer(axis_raw, dtype="<u4").reshape(
        PRIMITIVE_COUNT,
        TARGET_SIZE,
        4,
    )


def validate_manifest(root: Path, *, expected_commit: str) -> JsonObject:
    if COMMIT_PATTERN.fullmatch(expected_commit) is None:
        raise ValueError("expected capture commit is not a full SHA-1")
    manifest: JsonObject = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    device = manifest.get("device", {})
    compile_record = manifest.get("compile", {})
    evidence = manifest.get("borderInterpolantTransfer", {})
    outputs = evidence.get("outputs", [])
    if (
        manifest.get("schemaVersion") != SCHEMA_VERSION
        or manifest.get("rigVersion") != RIG_VERSION
        or manifest.get("ciCommit") != expected_commit
        or device.get("name") != "Apple M1 Max"
        or compile_record.get("interpolation") != "perspective"
        or compile_record.get("centerPull") != "interpolate_at_center"
        or compile_record.get("derivatives") != ["dfdx", "dfdy"]
        or compile_record.get("cullMode") != "none"
        or evidence.get("preregistrationFile") != PREREGISTRATION_REPOSITORY_PATH
        or evidence.get("preregistrationSha256") != PREREGISTRATION_SHA256
        or evidence.get("captureTimelineSha256") != TIMELINE_SHA256
        or evidence.get("vertexPayloadSha256") != VERTEX_SHA256
        or evidence.get("vertexCount") != 16
        or evidence.get("vertexStride") != 32
        or evidence.get("indexPayloadSha256") != INDEX_SHA256
        or evidence.get("indexCount") != 24
        or evidence.get("independentAxisSha256") != AXIS_SHA256
        or evidence.get("independentAxisArchiveFile") != AXIS_ARCHIVE_REPOSITORY_PATH
        or evidence.get("independentAxisArchiveFileSha256") != AXIS_ARCHIVE_FILE_SHA256
        or evidence.get("targetSize") != [TARGET_SIZE, TARGET_SIZE]
        or evidence.get("activePixels") != ACTIVE_PIXEL_COUNT
        or not isinstance(outputs, list)
        or len(outputs) != len(OUTPUT_LAYOUT)
    ):
        raise ValueError("border-interpolant manifest differs")

    for output, (filename, components) in zip(outputs, OUTPUT_LAYOUT, strict=True):
        path = root / filename
        expected_bytes = TARGET_SIZE * TARGET_SIZE * components * 4
        if (
            output.get("file") != filename
            or output.get("components") != components
            or output.get("bytes") != expected_bytes
            or not path.is_file()
            or path.stat().st_size != expected_bytes
            or output.get("sha256") != sha256_path(path)
        ):
            raise ValueError(f"border-interpolant output differs: {filename}")
    return manifest


def float_record(word: int) -> JsonObject:
    value = np.asarray([word], dtype=np.uint32).view(np.float32)[0]
    return {"bits": f"0x{word:08x}", "value": float(value)}


def finite_word_count(words: np.ndarray) -> int:
    return int(np.count_nonzero((words & 0x7F80_0000) != 0x7F80_0000))


def compare(
    root: Path,
    *,
    expected_commit: str,
) -> JsonObject:
    axis = load_frozen_axis()
    manifest = validate_manifest(root, expected_commit=expected_commit)
    center = np.memmap(
        root / CENTER_FILE,
        mode="r",
        dtype="<u4",
        shape=(TARGET_SIZE, TARGET_SIZE, 4),
    )
    derivative_x = np.memmap(
        root / DERIVATIVE_X_FILE,
        mode="r",
        dtype="<u4",
        shape=(TARGET_SIZE, TARGET_SIZE, 4),
    )
    derivative_y = np.memmap(
        root / DERIVATIVE_Y_FILE,
        mode="r",
        dtype="<u4",
        shape=(TARGET_SIZE, TARGET_SIZE, 4),
    )
    primitive = np.memmap(
        root / PRIMITIVE_FILE,
        mode="r",
        dtype="<u4",
        shape=(TARGET_SIZE, TARGET_SIZE),
    )

    active = primitive != SENTINEL
    expected_active = np.zeros((TARGET_SIZE, TARGET_SIZE), dtype=np.bool_)
    left, top, right, bottom = ACTIVE_BOUNDS
    expected_active[top:bottom, left:right] = True
    coverage_mismatch = active != expected_active
    active_y, active_x = np.nonzero(active)
    active_primitive = primitive[active_y, active_x].astype(np.intp)
    if np.any(active_primitive >= PRIMITIVE_COUNT):
        raise ValueError("native primitive ID lies outside the frozen topology")

    expected = np.empty((len(active_x), 2), dtype=np.uint32)
    expected[:, 0] = axis[active_primitive, active_x, 0]
    expected[:, 1] = axis[active_primitive, active_y, 1]
    actual = center[active_y, active_x, :2]
    unequal = actual != expected
    unequal_pixels = np.any(unequal, axis=1)
    primitive_counts = Counter(map(int, active_primitive))
    unequal_by_primitive = Counter(map(int, active_primitive[unequal_pixels]))

    first_mismatches: list[JsonObject] = []
    for index in np.flatnonzero(unequal_pixels)[:32]:
        components: list[JsonObject] = []
        for component, name in enumerate(("sdf-x", "sdf-y")):
            if not unequal[index, component]:
                continue
            components.append(
                {
                    "component": name,
                    "expected": float_record(int(expected[index, component])),
                    "actual": float_record(int(actual[index, component])),
                    "derivativeX": float_record(
                        int(derivative_x[active_y[index], active_x[index], component])
                    ),
                    "derivativeY": float_record(
                        int(derivative_y[active_y[index], active_x[index], component])
                    ),
                }
            )
        first_mismatches.append(
            {
                "x": int(active_x[index]),
                "yTopLeft": int(active_y[index]),
                "primitive": int(active_primitive[index]),
                "components": components,
            }
        )

    source = center[active_y, active_x, 2:]
    derivatives = np.concatenate(
        (
            derivative_x[active_y, active_x],
            derivative_y[active_y, active_x],
        ),
        axis=0,
    )
    coverage_exact = not np.any(coverage_mismatch)
    center_exact = not np.any(unequal)
    classification = (
        "center-exact; residual is downstream of center interpolation"
        if center_exact and coverage_exact
        else "center-interpolant-or-coverage-residual"
    )
    evidence = manifest["borderInterpolantTransfer"]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "executed": True,
        "accepted": center_exact and coverage_exact,
        "classification": classification,
        "captureCommit": expected_commit,
        "captureManifestSha256": sha256_path(root / "manifest.json"),
        "captureTimelineSha256": TIMELINE_SHA256,
        "frozenInputs": {
            "preregistrationSha256": PREREGISTRATION_SHA256,
            "vertexPayloadSha256": VERTEX_SHA256,
            "indexPayloadSha256": INDEX_SHA256,
            "independentAxisSha256": AXIS_SHA256,
        },
        "coverage": {
            "expectedBoundsTopLeft": list(ACTIVE_BOUNDS),
            "expectedPixels": ACTIVE_PIXEL_COUNT,
            "activePixels": int(np.count_nonzero(active)),
            "mismatchedPixels": int(np.count_nonzero(coverage_mismatch)),
            "exact": coverage_exact,
            "primitivePixelCounts": {
                str(key): value for key, value in sorted(primitive_counts.items())
            },
            "manifestPrimitivePixelCounts": evidence["primitivePixelCounts"],
        },
        "centerSdf": {
            "checkedWords": int(actual.size),
            "mismatchedWords": int(np.count_nonzero(unequal)),
            "mismatchedPixels": int(np.count_nonzero(unequal_pixels)),
            "mismatchedWordsByComponent": [
                int(value) for value in np.count_nonzero(unequal, axis=0)
            ],
            "mismatchedPixelsByPrimitive": {
                str(key): value for key, value in sorted(unequal_by_primitive.items())
            },
            "exact": center_exact,
            "firstMismatches": first_mismatches,
        },
        "controls": {
            "activeSourceWords": int(source.size),
            "finiteSourceWords": finite_word_count(source),
            "nonzeroSourceWords": int(np.count_nonzero(source & 0x7FFF_FFFF)),
            "activeDerivativeWords": int(derivatives.size),
            "finiteDerivativeWords": finite_word_count(derivatives),
        },
        "promotion": {
            "traceMayBeWalleInput": False,
            "frameTolerance": 0,
            "requiresIndependentRule": True,
            "requiresUnseenRetinaCapture": True,
            "requiresEightStateAmdZeroByteGate": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = compare(
        arguments.capture,
        expected_commit=arguments.expected_commit,
    )
    serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(serialized, end="")
    else:
        arguments.output.write_text(serialized, encoding="utf-8")
    if not result["accepted"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
