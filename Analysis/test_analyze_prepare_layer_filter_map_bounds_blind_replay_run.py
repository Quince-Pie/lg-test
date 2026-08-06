#!/usr/bin/env python3
"""Checks for the opened exact FilterOp blind-matrix result."""

import ast
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
RESULT_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_filter_map_bounds_blind_replay_result.json"
)
ANALYZER_PATH = (
    ANALYSIS_ROOT / "analyze_prepare_layer_filter_map_bounds_blind_replay_run.py"
)
EXPECTED_ARTIFACTS = {
    "circle-127-center": (
        8956379064,
        "sha256:64cb8bf3493704fad30876fed337c746d708e235092bc6f479269ace29827f77",
    ),
    "circle-128-center": (
        8956450473,
        "sha256:1c8d5e67490801f826cc35b5ee4f1433086df799aab765e12ae59bf143dd8206",
    ),
    "circle-255-center": (
        8956451236,
        "sha256:8c9b5347b4c83264097644fdb628d2beb4dc42ba91e175757d109e6f12ca19c9",
    ),
    "circle-257-center": (
        8956379903,
        "sha256:8806fe9bfdea736e14d980ba5da838070db662a45f3a8c0bb735066d5a56faec",
    ),
    "circle-511-center": (
        8956379840,
        "sha256:8f58f94a419c1832684c8f1be2ad0e01be75f686d9d94e79e9e79c3d31812d44",
    ),
    "circle-512-center": (
        8956361754,
        "sha256:c1738dfbe873c57785e06a9f65f8dc6dbbbe9d7dd2361b04b7233d3d189d65fa",
    ),
    "circle-1023-center": (
        8956372358,
        "sha256:ad188e2eeeba434418c50c93d3e65215bf25c82d5d86969cb8808865209392e9",
    ),
    "circle-1024-center": (
        8956447826,
        "sha256:79e2072826f2eca63a958effe7e35055efb28a1eaccc51dac90591d6eaeff496",
    ),
}


class PrepareLayerFilterMapBoundsBlindReplayRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
        cls.source = ANALYZER_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_run_identity_and_prospective_chain_are_exact(self) -> None:
        run = self.result["run"]
        self.assertEqual(
            self.result["prepareLayerFilterMapBoundsBlindReplayResultSchemaVersion"],
            1,
        )
        self.assertIn(
            "opened prospective target-output-blind", self.result["classification"]
        )
        self.assertEqual(run["runID"], 31072896015)
        self.assertEqual(run["headSHA"], "cf40cfdfe2f2fefc2b539f932048df5c434f6e26")
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["conclusion"], "success")
        self.assertEqual(
            run["preregistrationSHA256"],
            "fa4324d854ac1ee95a100269dd734260720b119dc2255932ab2ab2d5903eb251",
        )

    def test_all_blind_rectangles_and_components_are_bit_exact(self) -> None:
        replay = self.result["blindReplay"]
        self.assertEqual(replay["jobCount"], 8)
        self.assertEqual(replay["passedJobCount"], 8)
        self.assertEqual(replay["rectangleCount"], 256)
        self.assertEqual(replay["exactRectangleCount"], 256)
        self.assertEqual(replay["componentCount"], 1024)
        self.assertEqual(replay["exactComponentCount"], 1024)
        self.assertEqual(replay["mismatchedRectangleCount"], 0)
        self.assertEqual(replay["mismatchedComponentCount"], 0)
        self.assertEqual(replay["maximumAbsoluteErrorsXYWH"], [0.0] * 4)
        self.assertEqual(replay["maximumULPDistancesXYWH"], [0] * 4)
        self.assertFalse(replay["toleranceUsed"])

    def test_every_artifact_and_local_replay_is_authenticated(self) -> None:
        jobs = self.result["blindReplay"]["jobs"]
        self.assertEqual(len(jobs), 8)
        for job in jobs:
            artifact_id, digest = EXPECTED_ARTIFACTS[job["geometry"]]
            self.assertEqual(job["artifact"]["artifactID"], artifact_id)
            self.assertEqual(job["artifact"]["digest"], digest)
            self.assertFalse(job["artifact"]["expired"])
            self.assertTrue(job["allRequiredStepsPassed"])
            self.assertTrue(job["localSemanticReplayByteIdenticalToCI"])
            self.assertEqual(job["exactRectangleCount"], 32)
            self.assertEqual(job["exactComponentCount"], 128)
            self.assertEqual(job["maximumAbsoluteErrorsXYWH"], [0.0] * 4)
            self.assertEqual(job["maximumULPDistancesXYWH"], [0] * 4)
            self.assertEqual(job["sourceBounds"]["sampleIndex"], 32)
            self.assertFalse(job["sourceBounds"]["cropOrProducerValuesUsed"])
            for digest_value in job["files"].values():
                self.assertRegex(digest_value, r"^[0-9a-f]{64}$")

    def test_combined_crop_boundary_is_closed(self) -> None:
        combined = self.result["combinedCropEvidence"]
        self.assertEqual(combined["totalExactFloatingRectangleCount"], 512)
        self.assertEqual(combined["totalExactFloatingComponentCount"], 2048)
        self.assertEqual(combined["totalExactIntegerCropCount"], 768)
        conclusion = self.result["conclusion"]
        self.assertTrue(conclusion["filterMapBoundsOwnerEstablished"])
        self.assertTrue(conclusion["exactFilterMapBoundsArithmeticEstablished"])
        self.assertTrue(conclusion["uniformCropBlindSourceBoundsRuleEstablished"])
        self.assertTrue(conclusion["unchangedBlindRepeatPassed"])
        self.assertTrue(
            conclusion["clearLightMaterializeOneXGeometryCropTransferPassed"]
        )

    def test_product_parity_and_shader_authority_remain_closed(self) -> None:
        conclusion = self.result["conclusion"]
        for key in (
            "materialAppearanceDirectionTransferPassed",
            "physicalRetina2xAndColorTransferPassed",
            "independentWalleZeroByteFrameParityPassed",
            "productionShaderAuthorized",
            "liquidGlassParityEstablished",
        ):
            self.assertFalse(conclusion[key])
        self.assertEqual(len(self.result["remainingExactGates"]), 5)
        self.assertFalse(self.result["productionShader"]["changed"])
        self.assertEqual(
            self.result["productionShader"]["sha256"],
            "6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d",
        )

    def test_analyzer_reruns_the_semantic_validator_without_tolerance(self) -> None:
        self.assertIn("blind_validator.validate(", self.source)
        self.assertIn("local_validation == ci_validation", self.source)
        self.assertNotIn("isclose", self.source)
        self.assertIn('replay.get("toleranceUsed") is False', self.source)


if __name__ == "__main__":
    unittest.main()
