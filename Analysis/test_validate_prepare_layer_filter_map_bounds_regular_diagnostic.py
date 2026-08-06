#!/usr/bin/env python3
"""Checks for the regular-material FilterOp diagnostic validator."""

import unittest
from pathlib import Path
from unittest import mock

import validate_prepare_layer_filter_map_bounds_regular_diagnostic as diagnostic


SOURCE_PATH = (
    Path(__file__).resolve().parent
    / "validate_prepare_layer_filter_map_bounds_regular_diagnostic.py"
)


class PrepareLayerFilterMapBoundsRegularDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")

    def test_profile_and_structural_relation_are_frozen(self) -> None:
        self.assertEqual(diagnostic.EXPECTED_MATERIAL, "regular")
        self.assertEqual(diagnostic.EXPECTED_APPEARANCE, "light")
        self.assertEqual(diagnostic.EXPECTED_DIRECTION, "materialize")
        self.assertEqual(diagnostic.EXPECTED_GEOMETRY, "circle-800-center")
        self.assertIn("holdout.TRUE_PRODUCER_STORE_INDEX_DELTA", self.source)
        self.assertIn("holdout.TRUE_PRODUCER_ROLE_DELTA", self.source)
        self.assertIn("holdout.TRUE_PRODUCER_DEPTH_DELTA", self.source)

    def test_filter_validator_patch_is_scoped_and_restored(self) -> None:
        trace = {"prepareLayer": {"symbolStart": 123}}
        timeline = {"profile": "authenticated"}
        records = [
            {
                "sampleIndex": index,
                "producerRoleBase": 1000 + index,
                "observedProducerHex": "00" * 32,
            }
            for index in range(1, 33)
        ]
        inventory = {"inputs": {}}
        original_antecedent = diagnostic.producer_validator.validate_antecedent
        original_filter_geometry = diagnostic.frozen.EXPECTED_GEOMETRY
        original_mask_geometry = diagnostic.frozen_mask.EXPECTED_GEOMETRY

        def frozen_validate(trace_path, timeline_path, inventory_path, geometry):
            self.assertEqual(geometry, "circle-800-center")
            self.assertEqual(
                diagnostic.producer_validator.validate_antecedent(
                    trace_path, timeline_path, inventory_path, geometry
                ),
                (trace, timeline, records, inventory, 14, "inventory-sha"),
            )
            return {"sealedConclusion": {}}

        with (
            mock.patch.object(
                diagnostic,
                "validate_base",
                return_value=(trace, timeline),
            ),
            mock.patch.object(
                diagnostic,
                "structural_producer_records",
                return_value=records,
            ),
            mock.patch.object(
                diagnostic.producer_validator,
                "validate_inventory_transport",
                return_value=(inventory, 14, "inventory-sha"),
            ),
            mock.patch.object(diagnostic.frozen, "validate", frozen_validate),
        ):
            result = diagnostic.validate(
                Path("trace"), Path("timeline"), Path("inventory")
            )

        self.assertIs(
            diagnostic.producer_validator.validate_antecedent, original_antecedent
        )
        self.assertEqual(diagnostic.frozen.EXPECTED_GEOMETRY, original_filter_geometry)
        self.assertEqual(
            diagnostic.frozen_mask.EXPECTED_GEOMETRY, original_mask_geometry
        )
        self.assertTrue(
            result["sealedConclusion"]["regularMaterialDiagnosticPassed"]
        )
        self.assertFalse(result["sealedConclusion"]["completeProfileMatrixPassed"])
        self.assertFalse(result["sealedConclusion"]["liquidGlassParityEstablished"])

    def test_diagnostic_does_not_claim_product_parity(self) -> None:
        self.assertIn(
            'result["sealedConclusion"]["completeProfileMatrixPassed"] = False',
            self.source,
        )
        self.assertNotIn('"liquidGlassParityEstablished"] = True', self.source)


if __name__ == "__main__":
    unittest.main()
