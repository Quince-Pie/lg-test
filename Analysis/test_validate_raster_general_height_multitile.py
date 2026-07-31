#!/usr/bin/env python3
"""Tests for the preregistered multitile slope-recovery gate."""

import unittest

import validate_raster_general_height_multitile as multitile


class GeneralHeightMultitileTests(unittest.TestCase):
    def test_preregistration_and_sample_hash_are_frozen(self) -> None:
        multitile.load_preregistration()
        self.assertEqual(
            multitile.uint32_sha256(multitile.SAMPLE_XS),
            multitile.SAMPLE_XS_SHA256,
        )

    def test_every_sample_is_interior_and_tile_groups_are_exact(self) -> None:
        for width in multitile.factorized.geometry_widths():
            for geometry in multitile.failed_general.GEOMETRY_CASES:
                positions = [
                    multitile.sample_position(width, geometry, sample_index)
                    for sample_index in range(multitile.SAMPLE_POSITION_COUNT)
                ]
                self.assertEqual(
                    [position["tile"] for position in positions],
                    list(multitile.SAMPLE_TILES),
                )
                self.assertEqual(
                    [position["tileLocalX"] for position in positions],
                    list(multitile.SAMPLE_TILE_LOCAL_XS),
                )
                for left, right in multitile.SHARED_TILE_GROUPS:
                    self.assertEqual(
                        positions[left]["tile"],
                        positions[right]["tile"],
                    )

    def test_tile_groups_partition_the_sample_layout(self) -> None:
        self.assertEqual(
            sorted(index for group in multitile.SHARED_TILE_GROUPS for index in group),
            list(range(multitile.SAMPLE_POSITION_COUNT)),
        )

    def test_raw_layout_size_is_frozen(self) -> None:
        self.assertEqual(multitile.RECORD.size, 16)
        self.assertEqual(multitile.RAW_BYTES, 44_040_192)


if __name__ == "__main__":
    unittest.main()
