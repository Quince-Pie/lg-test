#!/usr/bin/env python3
"""Derive the frozen bottom-right candidate masks from Apple evidence."""

import argparse
import hashlib
import struct
import zlib
from pathlib import Path

import validate_raster_general_height_multitile as multitile


EXPECTED_COMMIT = "5923a6c9269762fe64e49b4a49e8ad42afc91a2f"
EXPECTED_RAW_SHA256 = "be36b115fccdbefcc24cee952d295f5e4c9a27d157e23f8b27712359668a0c46"
MASK = struct.Struct("<I")
MASK_COUNT = 458_752
RAW_BYTES = MASK_COUNT * MASK.size
RAW_SHA256 = "04a36598ae156769b59d22630d8a7279803bb354a66007cfe4ba8742ce1214f8"
COMPRESSED_BYTES = 175_503
COMPRESSED_SHA256 = "1a9c3bf01109f9c9c3d724215dee623af7275a294536b7618ab7938946c4781c"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def candidate_mask(
    direct_bits: int,
    records: list[tuple[int, int, int, int]],
) -> int:
    result = 0
    for offset in range(
        -multitile.CANDIDATE_RADIUS,
        multitile.CANDIDATE_RADIUS + 1,
    ):
        slope_bits = direct_bits + offset
        if all(
            multitile.factorized.shared_plane_accepts_slope(
                slope_bits,
                observations=[
                    observation
                    for sample_index in group
                    for observation in (
                        (
                            float(multitile.SAMPLE_TILE_LOCAL_XS[sample_index]),
                            records[sample_index][0],
                        ),
                        (
                            float(multitile.SAMPLE_TILE_LOCAL_XS[sample_index])
                            + 0.9375,
                            records[sample_index][1],
                        ),
                    )
                ],
            )
            for group in multitile.SHARED_TILE_GROUPS
        ):
            result |= 1 << (offset + multitile.CANDIDATE_RADIUS)
    return result


def build_candidate_masks(root: Path) -> bytes:
    manifest, path = multitile.validate_manifest(root)
    if (
        manifest.get("ciCommit") != EXPECTED_COMMIT
        or multitile.sha256_path(path) != EXPECTED_RAW_SHA256
    ):
        raise ValueError("bottom-right source artifact differs")

    data = path.read_bytes()
    widths = multitile.factorized.geometry_widths()
    shifts = multitile.factorized.delta_exponent_shift_bits()
    witnesses = multitile.arithmetic.witness_delta_bits()
    masks = bytearray(RAW_BYTES)
    mask_index = 0

    def record_at(
        width_index: int,
        witness_index: int,
        geometry_index: int,
        sample_index: int,
    ) -> tuple[int, int, int, int]:
        record_index = (
            (width_index * len(witnesses) + witness_index)
            * multitile.GEOMETRY_COUNT
            * multitile.SAMPLE_POSITION_COUNT
            + geometry_index * multitile.SAMPLE_POSITION_COUNT
            + sample_index
        )
        return multitile.RECORD.unpack_from(
            data,
            record_index * multitile.RECORD.size,
        )

    for width_index, width in enumerate(widths):
        for witness_index, delta_bits in enumerate(witnesses):
            scaled_value = multitile.arithmetic.float32_value(
                delta_bits - shifts[width_index]
            )
            direct_bits = multitile.arithmetic.float32_bits(scaled_value / width)
            for geometry_index in range(multitile.GEOMETRY_COUNT):
                records = [
                    record_at(
                        width_index,
                        witness_index,
                        geometry_index,
                        sample_index,
                    )
                    for sample_index in range(multitile.SAMPLE_POSITION_COUNT)
                ]
                mask = candidate_mask(direct_bits, records)
                if mask == 0:
                    raise ValueError(
                        "bottom-right control contains an empty candidate mask"
                    )
                MASK.pack_into(masks, mask_index * MASK.size, mask)
                mask_index += 1

    result = bytes(masks)
    if (
        mask_index != MASK_COUNT
        or len(result) != RAW_BYTES
        or sha256(result) != RAW_SHA256
    ):
        raise ValueError("bottom-right candidate-mask table differs")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    compressed = zlib.compress(build_candidate_masks(arguments.artifact), 9)
    if len(compressed) != COMPRESSED_BYTES or sha256(compressed) != COMPRESSED_SHA256:
        raise ValueError("compressed bottom-right candidate masks differ")
    arguments.output.write_bytes(compressed)


if __name__ == "__main__":
    main()
