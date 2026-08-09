#!/usr/bin/env python3
"""Authenticate the physical-Retina reveal coverage discovery corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image


class ValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class SampleBlock:
    x: int
    y: int
    width: int
    height: int
    pixels: bytes


@dataclass(frozen=True)
class SourceSamples:
    width: int
    height: int
    bytes_per_row: int
    center_x: float
    center_y: float
    radius: float
    blocks: tuple[SampleBlock, ...]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"{path}: expected a JSON object")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def parse_source_samples(path: Path) -> SourceSamples:
    data = path.read_bytes()
    require(data[:8] == b"LGRSMP01", f"{path}: sample magic differs")
    header_format = "<IIIIQQQI"
    header_size = struct.calcsize(header_format)
    require(len(data) >= 8 + header_size, f"{path}: truncated sample header")
    (
        schema,
        width,
        height,
        bytes_per_row,
        center_x_bits,
        center_y_bits,
        radius_bits,
        block_count,
    ) = struct.unpack_from(header_format, data, 8)
    require(schema == 1, f"{path}: sample schema differs")
    require(block_count == 65, f"{path}: sample block count differs")
    offset = 8 + header_size
    blocks: list[SampleBlock] = []
    for index in range(block_count):
        require(len(data) >= offset + 16, f"{path}: block {index} header truncated")
        x, y, block_width, block_height = struct.unpack_from("<iiII", data, offset)
        offset += 16
        require(block_width > 0 and block_height > 0, f"{path}: empty block")
        require(x >= 0 and y >= 0, f"{path}: negative block origin")
        require(x + block_width <= width, f"{path}: block exceeds width")
        require(y + block_height <= height, f"{path}: block exceeds height")
        byte_count = block_width * block_height * 4
        require(len(data) >= offset + byte_count, f"{path}: block payload truncated")
        blocks.append(
            SampleBlock(
                x=x,
                y=y,
                width=block_width,
                height=block_height,
                pixels=data[offset : offset + byte_count],
            )
        )
        offset += byte_count
    require(offset == len(data), f"{path}: trailing sample bytes")
    require(
        (blocks[0].x, blocks[0].y, blocks[0].width, blocks[0].height)
        == (0, 0, min(384, width), min(384, height)),
        f"{path}: fixed top-left block differs",
    )
    require(
        all(block.width == 16 and block.height == 16 for block in blocks[1:]),
        f"{path}: radial patch dimensions differ",
    )
    return SourceSamples(
        width=width,
        height=height,
        bytes_per_row=bytes_per_row,
        center_x=struct.unpack("<d", struct.pack("<Q", center_x_bits))[0],
        center_y=struct.unpack("<d", struct.pack("<Q", center_y_bits))[0],
        radius=struct.unpack("<d", struct.pack("<Q", radius_bits))[0],
        blocks=tuple(blocks),
    )


def sample_path(capture_root: Path, frame_file: str) -> Path:
    return capture_root / Path(frame_file).with_suffix(".source-samples")


def image_dimensions(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def expected_radius(
    index: int,
    frame_count: int,
    width_points: float,
    height_points: float,
    scale: float,
    origin_x: float,
    origin_y: float,
) -> float:
    center_x = width_points * origin_x * scale
    center_y = height_points * origin_y * scale
    right = width_points * scale - center_x
    bottom = height_points * scale - center_y
    farthest = max(
        math.hypot(center_x, center_y),
        math.hypot(right, center_y),
        math.hypot(center_x, bottom),
        math.hypot(right, bottom),
    )
    unsnapped = farthest * 1.03 * index / (frame_count - 1)
    return math.floor(2.0 * unsnapped) / 2.0


def select_sequence(manifest: dict[str, Any]) -> dict[str, Any]:
    matches = [
        item
        for item in manifest.get("sweepSequences", [])
        if isinstance(item, dict)
        and item.get("id") == "sweep__wallpaper-reveal__regular__dark"
    ]
    require(len(matches) == 1, f"expected one coverage sweep; found {len(matches)}")
    return matches[0]


def validate(
    capture_root: Path,
    preregistration_path: Path,
    preflight_path: Path,
) -> dict[str, Any]:
    preregistration = load_object(preregistration_path)
    expected = preregistration["capture"]
    manifest_path = capture_root / "manifest.json"
    manifest = load_object(manifest_path)
    preflight = load_object(preflight_path)

    require(preflight.get("passed") is True, "physical Retina preflight failed")
    require(preflight.get("backingScaleFactor") == 2, "preflight is not 2x")
    require(preflight.get("sessionOnConsole") is True, "session is not on-console")
    require(preflight.get("sessionLocked") is False, "session is locked")
    require(preflight.get("displayActive") is True, "display is inactive")
    require(preflight.get("displayAsleep") is False, "display is asleep")
    require(manifest.get("osBuild") == expected["macOSBuild"], "OS build differs")
    require(
        manifest.get("backingScaleFactor") == expected["backingScaleFactor"],
        "backing scale differs",
    )
    require(manifest.get("windowPoints") == expected["windowPoints"], "size differs")
    require(
        manifest.get("transitionOriginNormalized")
        == expected["transitionOriginNormalized"],
        "origin differs",
    )
    require(
        manifest.get("requestedDynamicModes") == ["wallpaper-reveal"],
        "capture is not the isolated reveal mode",
    )
    require(manifest.get("exactSweepsRequested") is True, "exact sweeps absent")

    repository = preregistration_path.parent.parent
    for relative, expected_hash in preregistration["frozenSources"].items():
        require(
            sha256(repository / relative) == expected_hash,
            f"{relative} SHA-256 differs",
        )

    sequence = select_sequence(manifest)
    require(
        sequence.get("outgoingBackground") == "reveal-coverage-black",
        "outgoing coverage source differs",
    )
    require(
        sequence.get("incomingBackground") == "reveal-coverage-white",
        "incoming coverage source differs",
    )
    require(
        sequence.get("probeRole") == "walle-two-wallpaper-reveal-oracle",
        "probe role differs",
    )

    frame_count = expected["sweepFrameCount"]
    traversal_names = ("frames", "reverseFrames", "repeatFrames")
    width_points, height_points = expected["windowPoints"]
    scale = float(expected["backingScaleFactor"])
    origin_x, origin_y = expected["transitionOriginNormalized"]
    pixel_width = int(width_points * scale)
    pixel_height = int(height_points * scale)
    canonical_hashes: dict[str, list[str]] = {}
    sample_hashes: dict[str, list[str]] = {}
    sample_payload_bytes = 0
    distinct_sample_words: set[bytes] = set()

    for traversal in traversal_names:
        records = sequence.get(traversal)
        require(isinstance(records, list), f"{traversal} is absent")
        require(len(records) == frame_count, f"{traversal} count differs")
        ordered = sorted(records, key=lambda item: item["index"])
        require(
            [item["index"] for item in ordered] == list(range(frame_count)),
            f"{traversal} indices differ",
        )
        canonical_hashes[traversal] = []
        sample_hashes[traversal] = []
        for record in ordered:
            index = record["index"]
            progress = index / (frame_count - 1)
            require(record.get("progress") == progress, "progress differs")
            require(record.get("stable") is True, "unstable sweep frame")
            frame_path = capture_root / record["file"]
            require(sha256(frame_path) == record["fileSha256"], "PNG hash differs")
            require(
                image_dimensions(frame_path) == (pixel_width, pixel_height),
                "PNG dimensions differ",
            )
            canonical_hashes[traversal].append(record["pixelSha256"])
            source_image = record["sourceImage"]
            require(source_image["bitsPerComponent"] == 8, "source depth differs")
            require(source_image["bitsPerPixel"] == 32, "source pixel size differs")
            require(
                source_image["bytesPerRow"] == pixel_width * 4,
                "source row stride differs",
            )
            require(source_image["alphaInfo"] == 2, "source alpha layout differs")
            require(source_image["bitmapInfo"] == 8194, "source bitmap layout differs")
            require("Color LCD" in source_image["colorSpace"], "source profile differs")

            raw_path = sample_path(capture_root, record["file"])
            raw_hash = sha256(raw_path)
            sample_hashes[traversal].append(raw_hash)
            parsed = parse_source_samples(raw_path)
            require(
                (parsed.width, parsed.height, parsed.bytes_per_row)
                == (pixel_width, pixel_height, pixel_width * 4),
                "raw sample geometry differs",
            )
            require(parsed.center_x == width_points * origin_x * scale, "center X differs")
            require(parsed.center_y == height_points * origin_y * scale, "center Y differs")
            require(
                parsed.radius
                == expected_radius(
                    index,
                    frame_count,
                    width_points,
                    height_points,
                    scale,
                    origin_x,
                    origin_y,
                ),
                "effective radius differs",
            )
            for block in parsed.blocks:
                sample_payload_bytes += len(block.pixels)
                if traversal == "frames":
                    words = memoryview(block.pixels).cast("B")
                    distinct_sample_words.update(
                        bytes(words[offset : offset + 4])
                        for offset in range(0, len(words), 4)
                    )

    for traversal in traversal_names[1:]:
        require(
            canonical_hashes[traversal] == canonical_hashes["frames"],
            f"{traversal} canonical pixels differ from forward",
        )
        require(
            sample_hashes[traversal] == sample_hashes["frames"],
            f"{traversal} source samples differ from forward",
        )
    require(len(distinct_sample_words) >= 16, "coverage samples are degenerate")

    combined = hashlib.sha256()
    for traversal in traversal_names:
        for digest in sample_hashes[traversal]:
            combined.update(bytes.fromhex(digest))
    return {
        "schemaVersion": 1,
        "status": "accepted-reveal-coverage-discovery-corpus",
        "accepted": True,
        "claimBoundary": {
            "promotes": "complete deterministic coverage-discovery input corpus only",
            "doesNotPromote": [
                "a coverage formula",
                "a color-compositing formula",
                "ordinary Walle integration",
                "production parity",
            ],
        },
        "capture": {
            "manifestSHA256": sha256(manifest_path),
            "preflightSHA256": sha256(preflight_path),
            "physicalRetina": True,
        },
        "traversalCount": len(traversal_names),
        "frameCount": frame_count * len(traversal_names),
        "rawSampleFileCount": frame_count * len(traversal_names),
        "rawSamplePayloadBytes": sample_payload_bytes,
        "distinctRawBGRAWords": len(distinct_sample_words),
        "combinedRawSampleSHA256": combined.hexdigest(),
        "repeatMismatchedCanonicalFrames": 0,
        "repeatMismatchedRawSampleFiles": 0,
        "comparisonTolerance": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        result = validate(
            arguments.capture_root,
            arguments.preregistration,
            arguments.preflight,
        )
    except (OSError, KeyError, TypeError, ValueError, ValidationError) as error:
        result = {
            "schemaVersion": 1,
            "status": "rejected",
            "error": str(error),
            "accepted": False,
        }
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("accepted") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
