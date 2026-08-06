#!/usr/bin/env python3
"""Integrity checks for the retrospective profile-transfer reanalysis."""

from __future__ import annotations

import hashlib
import json
import unittest
from itertools import product
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
RESULT_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_filter_map_bounds_profile_transfer_reanalysis_result.json"
)
EXPECTED_PROFILES = set(
    product(
        ("clear", "regular"),
        ("light", "dark"),
        ("materialize", "dematerialize"),
    )
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerFilterMapBoundsProfileTransferReanalysisResultTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_result_is_explicitly_retrospective(self) -> None:
        self.assertEqual(
            self.result[
                "prepareLayerFilterMapBoundsProfileTransferReanalysisResultSchemaVersion"
            ],
            1,
        )
        self.assertIn("retrospective", self.result["classification"])
        run = self.result["calibrationRun"]
        self.assertTrue(run["targetOutputsOpenedBeforeRuleFrozen"])
        self.assertFalse(run["prospectiveTransferEstablished"])
        self.assertEqual(run["workflowConclusion"], "failure")

    def test_complete_calibration_matrix_is_bit_exact(self) -> None:
        replay = self.result["retrospectiveReplay"]
        profiles = replay["profiles"]
        observed = {
            (record["material"], record["appearance"], record["direction"])
            for record in profiles
        }
        self.assertEqual(observed, EXPECTED_PROFILES)
        self.assertEqual(replay["profileCount"], 8)
        self.assertEqual(replay["exactRectangleCount"], 256)
        self.assertEqual(replay["exactComponentCount"], 1024)
        self.assertEqual(replay["mismatchedRectangleCount"], 0)
        self.assertEqual(replay["mismatchedComponentCount"], 0)
        self.assertEqual(replay["maximumULPDistance"], 0)
        self.assertEqual(replay["maximumAbsoluteError"], 0.0)
        self.assertEqual(sum(item["exactRectangleCount"] for item in profiles), 256)
        self.assertEqual(sum(item["exactComponentCount"] for item in profiles), 1024)
        self.assertEqual(sum(len(item["endpointRecords"]) for item in profiles), 4)

    def test_decoded_constants_and_structural_selectors_are_exact(self) -> None:
        candidate = self.result["decodedCandidate"]
        self.assertEqual(
            candidate["producerSelector"],
            {
                "storeIndexDeltaFromPointerCorrelatedMirror": -2,
                "roleBaseDeltaFromPointerCorrelatedMirror": -4016,
                "prepareDepthDeltaFromPointerCorrelatedMirror": 2,
                "cropOrProducerValuesUsedForSelection": False,
            },
        )
        self.assertEqual(candidate["sdfStateSelector"]["parametersRoleOffset"], 0x7F0)
        self.assertEqual(candidate["clear"]["sdfRadiusF32"], 9.0)
        self.assertEqual(candidate["regular"]["sdfRadiusF32"], 42.46388244628906)
        self.assertEqual(
            candidate["regular"]["sourceBoundsF64"],
            [-280.0, -280.0, 1360.0, 1360.0],
        )
        self.assertTrue(candidate["binary64FMARequired"])
        self.assertFalse(candidate["toleranceUsed"])
        self.assertFalse(candidate["exceptionFitUsed"])

    def test_product_authority_remains_closed(self) -> None:
        conclusion = self.result["conclusion"]
        self.assertTrue(conclusion["archivedCompleteProfileMatrixReplaysBitForBit"])
        self.assertFalse(conclusion["prospectiveUnchangedRepeatPassed"])
        self.assertFalse(conclusion["filterOpCropProfileTransferPassed"])
        self.assertFalse(conclusion["productionShaderAuthorized"])
        self.assertFalse(conclusion["liquidGlassParityEstablished"])
        shader = REPOSITORY_ROOT.parent / "shaders" / "frag.glsl"
        if shader.is_file():
            self.assertEqual(
                sha256(shader), conclusion["productionShaderExpectedSHA256"]
            )


if __name__ == "__main__":
    unittest.main()
