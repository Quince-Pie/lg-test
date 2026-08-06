#!/usr/bin/env python3
"""Checks for the exact FilterOp profile-transfer validator."""

import ast
import unittest
from pathlib import Path
from unittest import mock

import validate_prepare_layer_filter_map_bounds_profile_transfer as profile


SOURCE_PATH = (
    Path(__file__).resolve().parent
    / "validate_prepare_layer_filter_map_bounds_profile_transfer.py"
)


class PrepareLayerFilterMapBoundsProfileTransferValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_profile_is_authenticated_before_normalization(self) -> None:
        self.assertLess(
            self.source.index("require_profile("),
            self.source.index('normalized["material"]'),
        )
        self.assertIn(
            '"actualProfileAuthenticatedBeforeNormalization": True', self.source
        )
        self.assertIn('"traceBytesChanged": False', self.source)
        self.assertIn('"timelineBytesChanged": False', self.source)
        self.assertIn('"cropOrProducerValuesInspected": False', self.source)

    def test_only_profile_metadata_is_adapted(self) -> None:
        assignments = {
            node.targets[0].slice.value
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Subscript)
            and isinstance(node.targets[0].value, ast.Name)
            and node.targets[0].value.id == "normalized"
            and isinstance(node.targets[0].slice, ast.Constant)
        }
        self.assertEqual(assignments, {"material", "appearance", "direction"})

    def test_validator_restores_the_frozen_base_function(self) -> None:
        original = profile.crop_validator.validate_timeline

        def base_timeline(timeline, geometry):
            self.assertEqual(timeline["material"], "clear")
            self.assertEqual(timeline["appearance"], "light")
            self.assertEqual(timeline["direction"], "materialize")
            return {"name": geometry}, []

        def blind_validate(_trace, _timeline, geometry):
            profile.crop_validator.validate_timeline(
                {
                    "material": "regular",
                    "appearance": "dark",
                    "direction": "dematerialize",
                },
                geometry,
            )
            return {"sealedConclusion": {}}

        with (
            mock.patch.object(
                profile.crop_validator, "validate_timeline", base_timeline
            ),
            mock.patch.object(profile.blind_validator, "validate", blind_validate),
        ):
            installed = profile.crop_validator.validate_timeline
            result = profile.validate(
                Path("trace"),
                Path("timeline"),
                "circle-800-center",
                "regular",
                "dark",
                "dematerialize",
            )
            self.assertIs(profile.crop_validator.validate_timeline, installed)
        self.assertIs(profile.crop_validator.validate_timeline, original)
        self.assertTrue(
            result["sealedConclusion"]["singleProfileExactCropReplayPassed"]
        )
        self.assertFalse(result["sealedConclusion"]["completeProfileMatrixPassed"])

    def test_mismatched_profile_fails_before_base_validation(self) -> None:
        with self.assertRaisesRegex(ValueError, "timeline profile metadata differs"):
            profile.require_profile(
                {
                    "material": "clear",
                    "appearance": "light",
                    "direction": "materialize",
                },
                "regular",
                "light",
                "materialize",
            )

    def test_single_job_does_not_claim_complete_product_parity(self) -> None:
        self.assertIn(
            'result["sealedConclusion"]["completeProfileMatrixPassed"] = False',
            self.source,
        )
        self.assertNotIn('"liquidGlassParityEstablished": True', self.source)


if __name__ == "__main__":
    unittest.main()
