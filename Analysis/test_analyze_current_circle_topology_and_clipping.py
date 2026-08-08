#!/usr/bin/env python3
"""Tests for exact current-circle topology and clipping."""

import json
from pathlib import Path
import unittest

import analyze_current_circle_topology_and_clipping as analysis
import analyze_transition_geometry_corpus_local_macos_26_6_1 as model


RESULT = Path(__file__).with_name("current_circle_topology_and_clipping_result.json")


class CurrentCircleTopologyAndClippingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_clip_fraction_uses_binary64_positions(self) -> None:
        arguments = (
            -57.182475566864014,
            360.3112530708313,
            -208.74685668945312,
            208.74685668945312,
            0,
            1024,
        )
        exact = analysis.clip_axis(*arguments)
        self.assertEqual(
            tuple(model.float32_bits(value) for value in exact),
            (0x00000000, 0x43B427D7, 0xC317907C, 0x4350BF32),
        )

        low, high, low_value, high_value, clip_low, _ = arguments
        rounded_fraction = model.float32(
            (float(clip_low) - model.float32(low))
            / (model.float32(high) - model.float32(low))
        )
        rounded_position_result = analysis.fmaf32(
            model.float32(high_value - low_value),
            rounded_fraction,
            low_value,
        )
        self.assertEqual(model.float32_bits(rounded_position_result), 0xC317907B)
        self.assertNotEqual(
            model.float32_bits(rounded_position_result),
            model.float32_bits(exact[2]),
        )

    def test_upper_clip_consumes_updated_lower_edge(self) -> None:
        result = analysis.clip_axis(-10.0, 110.0, -1.0, 1.0, 0, 100)
        self.assertEqual(
            tuple(model.float32_bits(value) for value in result),
            (0x00000000, 0x42C80000, 0xBF555555, 0x3F555555),
        )

    def test_result_closes_every_current_stream(self) -> None:
        self.assertEqual(self.result["status"], "exact-current-family-closure")
        background = self.result["currentBackgroundTopology"]
        self.assertEqual(background["stateCount"], 163)
        self.assertEqual(background["ordinarySixVertexStateCount"], 161)
        self.assertEqual(background["splitTwentyFourVertexStateCount"], 2)
        self.assertTrue(background["exact"])
        final = self.result["currentFinalTopology"]
        self.assertEqual(final["stateCount"], 191)
        self.assertEqual(final["quadStateCount"], 186)
        self.assertEqual(final["borderStateCount"], 5)
        self.assertTrue(final["exact"])
        expected_components = {
            "splitBackgroundVertices": 1440,
            "splitBackgroundIndices": 192,
            "finalIndices": 1236,
            "finalGeometry": 4944,
            "finalPixelInfluentialSource": 1344,
        }
        self.assertEqual(
            {
                name: metric["componentCount"]
                for name, metric in self.result["metrics"].items()
            },
            expected_components,
        )
        self.assertTrue(
            all(metric["exact"] for metric in self.result["metrics"].values())
        )

    def test_live_general_transform_trace_is_bitwise_exact(self) -> None:
        live = self.result["liveGeneralTransformTrace"]
        self.assertEqual(live["recordCount"], 32)
        self.assertEqual(live["geometryComponents"], 768)
        self.assertEqual(live["geometryMismatches"], 0)
        self.assertEqual(live["publicRawComponents"], 128)
        self.assertEqual(live["publicRawMismatches"], 0)
        self.assertEqual(live["publicOuterComponents"], 64)
        self.assertEqual(live["publicOuterMismatches"], 0)
        self.assertTrue(live["exact"])

    def test_no_background_source_exclusion_is_prospectively_anchored(self) -> None:
        excluded = self.result["excludedNoBackgroundSource"]
        self.assertEqual(excluded["componentCount"], 304)
        self.assertEqual(
            excluded["interventionResultSHA256"],
            analysis.SOURCE_INTERVENTION_RESULT_SHA256,
        )
        prerequisite = self.result["prerequisites"]["sourcePixelInfluence"]
        self.assertEqual(prerequisite["status"], "exact-pixel-noninfluence")

    def test_result_allows_gated_work_without_claiming_parity(self) -> None:
        self.assertEqual(self.result["appleUnknownsBlockingGatedWalleIntegration"], 0)
        self.assertEqual(len(self.result["remainingAppleAlgorithmBoundaries"]), 1)
        self.assertEqual(len(self.result["remainingProductProofs"]), 2)
        self.assertTrue(self.result["walleIntegrationMayBeginBehindGates"])
        self.assertFalse(self.result["productionParityAuthorized"])
        self.assertFalse(self.result["productionShaderChanged"])
        self.assertFalse(self.result["productionFlakeChanged"])


if __name__ == "__main__":
    unittest.main()
