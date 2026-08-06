#!/usr/bin/env python3
"""Checks for the exact FilterOp replay decoder and frozen result."""

import json
import struct
import unittest
from pathlib import Path

import analyze_prepare_layer_filter_map_bounds_exact_replay as analysis


ANALYSIS_ROOT = Path(__file__).resolve().parent
RESULT_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_filter_map_bounds_exact_replay_result.json"
)


def f64_hex(values: tuple[float, ...]) -> str:
    return struct.pack(f"<{len(values)}d", *values).hex()


class PrepareLayerFilterMapBoundsExactReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_live_513_replay_is_bit_exact(self) -> None:
        observed = (
            496.01806640625,
            230.48136901855457,
            289.85016937255864,
            297.5005645751954,
        )
        replayed = analysis.replay(
            (
                239.5175018310547,
                238.4813690185547,
                546.0011291503906,
                546.0011291503906,
            ),
            (-496.01806640625, 527.98193359375),
            (
                -2.842170943040401e-14,
                -2.842170943040401e-14,
                512.9999999999999,
                512.9999999999999,
            ),
            8.0,
            0.12485885620117188,
        )
        self.assertEqual(f64_hex(replayed), f64_hex(observed))

    def test_every_archived_holdout_component_is_exact(self) -> None:
        replay = self.result["holdoutReplay"]
        self.assertEqual(replay["rectangleCount"], 256)
        self.assertEqual(replay["exactRectangleCount"], 256)
        self.assertEqual(replay["componentCount"], 1024)
        self.assertEqual(replay["exactComponentCount"], 1024)
        self.assertEqual(replay["maximumAbsoluteErrorsXYWH"], [0.0] * 4)
        self.assertEqual(replay["maximumULPDistancesXYWH"], [0] * 4)
        self.assertTrue(all(record["exact"] for record in replay["records"]))

    def test_each_geometry_has_32_exact_rectangles(self) -> None:
        geometry_results = self.result["holdoutReplay"]["geometryResults"]
        self.assertEqual(len(geometry_results), 8)
        for geometry in geometry_results:
            self.assertEqual(geometry["recordCount"], 32)
            self.assertEqual(geometry["exactRectangleCount"], 32)

    def test_live_traces_supply_the_two_residual_bounds(self) -> None:
        by_geometry = {
            record["geometry"]: record for record in self.result["liveFilterResults"]
        }
        self.assertEqual(
            by_geometry["circle-1025-center"]["sourceBoundsF64"],
            [-5.684341886080802e-14, -5.684341886080802e-14, 1025.0, 1025.0],
        )
        self.assertEqual(
            by_geometry["circle-513-center"]["sourceBoundsF64"],
            [
                -2.842170943040401e-14,
                -2.842170943040401e-14,
                512.9999999999999,
                512.9999999999999,
            ],
        )
        self.assertTrue(
            all(record["liveReplayExact"] for record in by_geometry.values())
        )

    def test_source_bounds_use_one_crop_blind_terminal_rule(self) -> None:
        policy = self.result["sourceBoundsPolicy"]
        self.assertEqual(policy["terminalSampleIndex"], 32)
        self.assertFalse(policy["cropOrProducerValuesUsed"])
        self.assertEqual(policy["geometryCount"], 8)
        self.assertEqual(policy["liveInstructionTraceConfirmationCount"], 2)
        self.assertTrue(policy["liveInstructionTraceConfirmationsExact"])

    def test_retrospective_result_does_not_claim_blind_or_product_parity(self) -> None:
        conclusion = self.result["conclusion"]
        self.assertTrue(conclusion["archivedHoldoutFloatingReplayExact"])
        self.assertFalse(conclusion["unchangedBlindRepeatPassed"])
        self.assertFalse(conclusion["generalUnseenGeometryPolicyEstablished"])
        self.assertFalse(conclusion["materialAppearanceDirectionTransferPassed"])
        self.assertFalse(conclusion["physicalRetina2xAndColorTransferPassed"])
        self.assertFalse(conclusion["independentWalleZeroByteFrameParityPassed"])
        self.assertFalse(conclusion["productionShaderAuthorized"])
        self.assertFalse(conclusion["liquidGlassParityEstablished"])


if __name__ == "__main__":
    unittest.main()
