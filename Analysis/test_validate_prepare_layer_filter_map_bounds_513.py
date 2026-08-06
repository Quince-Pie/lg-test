#!/usr/bin/env python3
"""Source-level checks for the geometry-only 513 validator adapter."""

import hashlib
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
ADAPTER_PATH = ANALYSIS_ROOT / "validate_prepare_layer_filter_map_bounds_513.py"
FROZEN_PATH = ANALYSIS_ROOT / "validate_prepare_layer_filter_map_bounds.py"
FROZEN_SHA256 = "24fd0d7df9912738e3914eb146f5c4959c7bf737fc69a52ff10577fba88a19cc"


class PrepareLayerFilterMapBounds513ValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = ADAPTER_PATH.read_text(encoding="utf-8")

    def test_frozen_validator_is_unchanged(self) -> None:
        self.assertEqual(
            hashlib.sha256(FROZEN_PATH.read_bytes()).hexdigest(), FROZEN_SHA256
        )

    def test_adapter_rebinds_only_the_two_geometry_guards(self) -> None:
        self.assertIn('EXPECTED_GEOMETRY = "circle-513-center"', self.source)
        self.assertIn("frozen.EXPECTED_GEOMETRY = EXPECTED_GEOMETRY", self.source)
        self.assertIn("frozen_mask.EXPECTED_GEOMETRY = EXPECTED_GEOMETRY", self.source)
        self.assertIn(
            "frozen.validate(trace, timeline, inventory, EXPECTED_GEOMETRY)",
            self.source,
        )

    def test_adapter_restores_frozen_module_state(self) -> None:
        self.assertIn("finally:", self.source)
        self.assertIn(
            "frozen.EXPECTED_GEOMETRY = original_filter_geometry", self.source
        )
        self.assertIn(
            "frozen_mask.EXPECTED_GEOMETRY = original_mask_geometry", self.source
        )


if __name__ == "__main__":
    unittest.main()
