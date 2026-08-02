#!/usr/bin/env python3
"""Integrity checks for the immutable sample-31 repeat-scan result."""

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
RESULT_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_primary_mesh_sample31_repeat_scan_result.json"
)
RESULT_SHA256 = "c59bc25ea4e778fe775cc81cc0ab2f71f18ad2f989f19f43826ac711af3f1de4"
RESULT = json.loads(RESULT_PATH.read_text(encoding="utf-8"))


class PrimaryMeshSample31RepeatScanResultTests(unittest.TestCase):
    def test_canonical_result_hash_is_immutable(self) -> None:
        self.assertEqual(
            hashlib.sha256(RESULT_PATH.read_bytes()).hexdigest(), RESULT_SHA256
        )

    def test_opened_result_preserves_the_preregistered_scope(self) -> None:
        self.assertEqual(RESULT["runID"], 30760175468)
        self.assertEqual(RESULT["sourceTargetCenterResidualULPs"], [0.0, 0.0])
        self.assertEqual(RESULT["aggregate"]["recordCount"], 114)
        self.assertEqual(RESULT["aggregate"]["unitScanRecordCount"], 90)
        self.assertEqual(RESULT["aggregate"]["repeatEquivalenceGroupCount"], 23)
        self.assertEqual(
            RESULT["aggregate"]["exactDecodedDrawConsumedRepeatGroupCount"], 23
        )
        self.assertTrue(
            RESULT["conclusion"][
                "sample31SameStateResponseDeterministicAcrossRecordedOrder"
            ]
        )
        self.assertTrue(
            RESULT["conclusion"]["everyReportedTransitionBracketHasUnitWidth"]
        )

    def test_opened_result_does_not_claim_a_complete_policy(self) -> None:
        conclusion = RESULT["conclusion"]
        self.assertFalse(conclusion["independentProducerMeshPolicyRecovered"])
        self.assertFalse(conclusion["productionShaderAuthorized"])
        self.assertTrue(conclusion["requiresUnseenGeometryTransfer"])


if __name__ == "__main__":
    unittest.main()
