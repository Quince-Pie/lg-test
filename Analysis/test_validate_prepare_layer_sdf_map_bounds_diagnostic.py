#!/usr/bin/env python3
"""Checks for the SDF map-bounds diagnostic validator."""

import unittest
from pathlib import Path

import validate_prepare_layer_sdf_map_bounds_diagnostic as diagnostic


SOURCE_PATH = (
    Path(__file__).resolve().parent
    / "validate_prepare_layer_sdf_map_bounds_diagnostic.py"
)


class PrepareLayerSDFMapBoundsDiagnosticValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")

    def test_discovery_boundary_is_explicit(self) -> None:
        self.assertEqual(diagnostic.SDF_RELATIVE_TO_PREPARE_LAYER, -56012)
        self.assertEqual(diagnostic.SDF_SYMBOL_BYTE_COUNT, 160)
        self.assertEqual(diagnostic.SDF_DISPATCH_ORDINAL, 2)
        self.assertIsNone(diagnostic.EXPECTED_CONFIGURATION["expectedCodeSHA256"])
        self.assertFalse(
            diagnostic.EXPECTED_CONFIGURATION["cropValuesUsedForSelection"]
        )
        self.assertFalse(
            diagnostic.EXPECTED_CONFIGURATION["outputValuesUsedForSelection"]
        )

    def test_complete_code_instruction_and_boundary_chains_are_checked(self) -> None:
        self.assertIn("hashlib.sha256(code).hexdigest()", self.source)
        self.assertIn("producer.validate_instruction_state", self.source)
        self.assertIn("producer.validate_opaque_boundary", self.source)
        self.assertIn("validate_opaque_identity", self.source)
        self.assertIn("SDF instruction chain differs", self.source)
        self.assertIn("SDF synthetic opaque boundary differs", self.source)

    def test_product_authority_remains_closed(self) -> None:
        self.assertIn('sealed["sdfCodeHashProspectivelyFrozen"] = False', self.source)
        self.assertIn('sealed["completeProfileMatrixPassed"] = False', self.source)
        self.assertIn('sealed["productionShaderAuthorized"] = False', self.source)
        self.assertIn('sealed["liquidGlassParityEstablished"] = False', self.source)
        self.assertNotIn('"liquidGlassParityEstablished"] = True', self.source)


if __name__ == "__main__":
    unittest.main()
