#!/usr/bin/env python3
"""Checks for the small-geometry Filter/SDF validator adapter."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

import validate_prepare_layer_filter_sdf_small_geometry as small


class PrepareLayerFilterSDFSmallGeometryValidatorTests(unittest.TestCase):
    def test_geometry_is_adapted_only_while_frozen_validator_runs(self) -> None:
        original_geometry = small.frozen.regular.EXPECTED_GEOMETRY
        original_configuration = small.frozen.EXPECTED_CONFIGURATION
        captured: dict[str, object] = {}

        def fake_validate(*_arguments: object) -> dict[str, object]:
            captured["geometry"] = small.frozen.regular.EXPECTED_GEOMETRY
            captured["configuration"] = small.frozen.EXPECTED_CONFIGURATION
            return {
                "profile": {"geometry": small.EXPECTED_GEOMETRY},
                "sealedConclusion": {},
            }

        with mock.patch.object(small.frozen, "validate", side_effect=fake_validate):
            result = small.validate(Path("trace"), Path("timeline"), Path("inventory"))

        self.assertEqual(captured["geometry"], small.EXPECTED_GEOMETRY)
        self.assertEqual(
            captured["configuration"]["geometry"], small.EXPECTED_GEOMETRY
        )
        self.assertEqual(small.frozen.regular.EXPECTED_GEOMETRY, original_geometry)
        self.assertIs(small.frozen.EXPECTED_CONFIGURATION, original_configuration)
        self.assertEqual(
            result["prepareLayerFilterSDFSmallGeometryValidationSchemaVersion"], 1
        )

    def test_product_authority_remains_closed(self) -> None:
        source = Path(small.__file__).read_text(encoding="utf-8")
        self.assertIn('sealed["regularGeometryTransferPassed"] = False', source)
        self.assertIn('sealed["productionShaderAuthorized"] = False', source)
        self.assertIn('sealed["liquidGlassParityEstablished"] = False', source)
        self.assertNotIn('sealed["liquidGlassParityEstablished"] = True', source)


if __name__ == "__main__":
    unittest.main()
