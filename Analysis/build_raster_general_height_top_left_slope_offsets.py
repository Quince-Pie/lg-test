#!/usr/bin/env python3
"""Extract exact top-left slope offsets from the Apple capture."""

import argparse
import hashlib
import struct
import zlib
from collections import Counter
from pathlib import Path

import validate_raster_general_height_top_left as top_left


EXPECTED_COMMIT = "e56bcd2e0fb6b6fa8ecee8dc5551e020df1fffac"
EXPECTED_MANIFEST_SHA256 = (
    "09ad9cedaa8d7cea955a31364c59e64825c20958f112c9cc2313918197adb6f7"
)
EXPECTED_RAW_SHA256 = "ccb76da172eceba1e9681b6fbcedb47767262964c7d7e423ec86e84fe213d6e0"
OFFSET = struct.Struct("<b")
OFFSET_COUNT = top_left.COEFFICIENT_COUNT
RAW_BYTES = 458_752
RAW_SHA256 = "e4cf23c08f3c080fa61a1ae56067ae4ad318c442a27712032a9314202e409e70"
COMPRESSED_BYTES = 50_115
COMPRESSED_SHA256 = "bd022b0b87c7f485092d28877231880f4d359057216418ee8e018cb30189bf42"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_offsets(root: Path) -> bytes:
    manifest, path = top_left.validate_manifest(root)
    if (
        manifest.get("ciCommit") != EXPECTED_COMMIT
        or top_left.sha256_path(root / "manifest.json") != EXPECTED_MANIFEST_SHA256
        or top_left.sha256_path(path) != EXPECTED_RAW_SHA256
    ):
        raise ValueError("top-left source artifact differs")

    data = path.read_bytes()
    widths = top_left.factorized.geometry_widths()
    shifts = top_left.factorized.delta_exponent_shift_bits()
    witnesses = top_left.arithmetic.witness_delta_bits()
    offsets = bytearray(OFFSET_COUNT * OFFSET.size)
    distribution: Counter[int] = Counter()
    coefficient_index = 0

    for width_index, width in enumerate(widths):
        for witness_index, delta_bits in enumerate(witnesses):
            scaled_value = top_left.arithmetic.float32_value(
                delta_bits - shifts[width_index]
            )
            direct_bits = top_left.arithmetic.float32_bits(scaled_value / width)
            for geometry_index in range(top_left.GEOMETRY_COUNT):
                records = []
                for sample_index in range(top_left.SAMPLE_POSITION_COUNT):
                    record_index = (
                        (width_index * len(witnesses) + witness_index)
                        * top_left.GEOMETRY_COUNT
                        * top_left.SAMPLE_POSITION_COUNT
                        + geometry_index * top_left.SAMPLE_POSITION_COUNT
                        + sample_index
                    )
                    records.append(
                        top_left.RECORD.unpack_from(
                            data,
                            record_index * top_left.RECORD.size,
                        )
                    )
                accepted = top_left.accepted_slopes(direct_bits, records)
                if len(accepted) != 1:
                    raise ValueError("top-left source does not have one exact slope")
                offset = accepted[0] - direct_bits
                if offset not in (-1, 0, 1):
                    raise ValueError("top-left slope offset is outside {-1,0,1}")
                OFFSET.pack_into(
                    offsets,
                    coefficient_index * OFFSET.size,
                    offset,
                )
                distribution[offset] += 1
                coefficient_index += 1

    if (
        coefficient_index != OFFSET_COUNT
        or len(offsets) != RAW_BYTES
        or distribution
        != {
            -1: 31_570,
            0: 391_258,
            1: 35_924,
        }
    ):
        raise ValueError("top-left slope-offset table differs")
    result = bytes(offsets)
    if sha256(result) != RAW_SHA256:
        raise ValueError("top-left slope-offset hash differs")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    offsets = build_offsets(arguments.artifact)
    compressed = zlib.compress(offsets, 9)
    if len(compressed) != COMPRESSED_BYTES or sha256(compressed) != COMPRESSED_SHA256:
        raise ValueError("compressed top-left slope offsets differ")
    arguments.output.write_bytes(compressed)
    print(f"rawBytes={len(offsets)} rawSha256={sha256(offsets)}")
    print(f"compressedBytes={len(compressed)} compressedSha256={sha256(compressed)}")


if __name__ == "__main__":
    main()
