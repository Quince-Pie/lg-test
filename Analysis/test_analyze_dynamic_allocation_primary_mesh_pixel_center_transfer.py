#!/usr/bin/env python3
"""Tests for the primary-mesh pixel-center transfer analyzer."""

import unittest

import analyze_dynamic_allocation_primary_mesh_pixel_center_transfer as analyzer


class PrimaryMeshPixelCenterTransferTests(unittest.TestCase):
    def test_nested_unit_bracket_is_accepted(self) -> None:
        self.assertTrue(analyzer.bracket_contains((330, 338), (335, 336)))

    def test_non_nested_bracket_is_rejected(self) -> None:
        self.assertFalse(analyzer.bracket_contains((330, 335), (335, 336)))

    def test_classification_denies_complete_policy(self) -> None:
        self.assertIn("not-a-complete-mesh-policy", analyzer.CLASSIFICATION)


if __name__ == "__main__":
    unittest.main()
