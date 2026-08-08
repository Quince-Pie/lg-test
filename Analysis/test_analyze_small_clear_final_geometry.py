#!/usr/bin/env python3
"""Tests for exact small-clear final-highlight geometry."""

import json
from pathlib import Path
import unittest

import analyze_small_clear_final_geometry as analysis
import analyze_transition_geometry_corpus_local_macos_26_6_1 as model


RESULT = Path(__file__).with_name("small_clear_final_geometry_result.json")


class SmallClearFinalGeometryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_radius_expands_in_binary64_before_binary32_half(self) -> None:
        extent = 53.870121574401765
        half, outer, radius, inner_outer = analysis.small_axis_terms(extent)
        naive = model.float32(
            model.float32(model.float32(half + 9.0) - 9.0)
        )
        self.assertEqual(model.float32_bits(outer), 0x420FBD81)
        self.assertEqual(model.float32_bits(radius), 0x41D77B02)
        self.assertEqual(model.float32_bits(half), 0x41D77B01)
        self.assertEqual(model.float32_bits(naive), 0x41D77B00)
        self.assertEqual(model.float32_bits(inner_outer), 0x420FBD80)
        self.assertGreater(radius, half)

    def test_border_placement_uses_inner_outer_and_two_positive_zeros(self) -> None:
        positions, coordinates = analysis.border_axis(
            967.7190170288086,
            1038.328525543213,
            52.6095085144043,
        )
        self.assertEqual(
            tuple(model.float32_bits(value) for value in positions),
            (0x4471EE04, 0x447AC186, 0x447AC185, 0x4481CA83),
        )
        self.assertEqual(
            tuple(model.float32_bits(value) for value in coordinates),
            (0xC20D3812, 0x00000000, 0x00000000, 0x420D3812),
        )

    def test_quad_clipping_keeps_binary64_edges_until_fraction(self) -> None:
        low = 977.2800777435302 - 9.0
        high = (977.2800777435302 + 51.64003887176517) + 9.0
        _, outer, _, _ = analysis.small_axis_terms(51.64003887176517)
        clipped = analysis.current.clip_axis(
            low, high, -outer, outer, 0, 1024
        )
        self.assertEqual(
            tuple(model.float32_bits(value) for value in clipped),
            (0x447211ED, 0x44800000, 0xC20B47B3, 0x41A73300),
        )

    def test_result_closes_all_position_sdf_and_index_components(self) -> None:
        self.assertEqual(
            self.result["status"], "exact-small-clear-final-geometry-closure"
        )
        self.assertEqual(self.result["stateCount"], 123)
        self.assertEqual(self.result["topology"]["quadStateCount"], 89)
        self.assertEqual(self.result["topology"]["borderStateCount"], 34)
        self.assertEqual(self.result["topology"]["predicateMismatches"], 0)
        self.assertEqual(
            self.result["metrics"]["positionAndSDFGeometry"]["componentCount"],
            5400,
        )
        self.assertEqual(
            self.result["metrics"]["positionAndSDFGeometry"][
                "mismatchedComponents"
            ],
            0,
        )
        self.assertEqual(self.result["metrics"]["indices"]["componentCount"], 1350)
        self.assertEqual(
            self.result["metrics"]["indices"]["mismatchedComponents"], 0
        )
        self.assertEqual(
            self.result["radiusDiscrimination"],
            {
                "directHalfMatchCount": 60,
                "exactLaw": "binary32(binary32((extent+18)/2)-9)",
                "expandedBeforeHalfMatchCount": 123,
                "halfBeforeExpandMatchCount": 91,
                "stateCount": 123,
            },
        )

    def test_identity_transform_witness_is_exact(self) -> None:
        witness = self.result["identityTransformWitness"]
        self.assertEqual(witness["recordCount"], 64)
        self.assertEqual(witness["finalCallCount"], 32)
        self.assertEqual(witness["backgroundCallCount"], 32)
        self.assertEqual(witness["nullTransformCount"], 64)
        self.assertEqual(witness["shapeHalfExtentComponents"], 32)
        self.assertEqual(witness["shapeHalfExtentMismatches"], 0)
        self.assertTrue(witness["exact"])

    def test_active_half4_stays_open_until_pixel_influence_is_proved(self) -> None:
        layout = self.result["vertexLayout"]
        self.assertEqual(layout["strideBytes"], 48)
        self.assertEqual(layout["activeColorHalf4Offset"], 32)
        self.assertEqual(layout["activeColorHalfComponentCount"], 3600)
        self.assertEqual(layout["quadAllZeroColorStateCount"], 89)
        self.assertFalse(layout["activeColorPixelSemanticsClosed"])
        self.assertTrue(self.result["geometryFamilyClosed"])
        self.assertFalse(self.result["smallClearFamilyClosed"])

    def test_status_allows_gated_walle_work_without_claiming_parity(self) -> None:
        self.assertEqual(self.result["appleUnknownsBlockingGatedWalleIntegration"], 0)
        self.assertEqual(len(self.result["remainingAppleAlgorithmFamilies"]), 1)
        self.assertEqual(len(self.result["remainingSmallClearSubBoundaries"]), 3)
        self.assertEqual(len(self.result["remainingProductProofs"]), 2)
        self.assertTrue(self.result["walleIntegrationMayBeginBehindGates"])
        self.assertFalse(self.result["universalCircleDomainParity"])
        self.assertFalse(self.result["productionParityAuthorized"])
        self.assertFalse(self.result["productionShaderChanged"])
        self.assertFalse(self.result["productionFlakeChanged"])


if __name__ == "__main__":
    unittest.main()
