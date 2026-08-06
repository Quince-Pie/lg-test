#!/usr/bin/env python3
"""Integrity tests for the callback-only crop-policy holdout retry."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_crop_policy_holdout_callback_retry_preregistration.json"
)
ANTECEDENT_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_crop_policy_holdout_preregistration.json"
)
FAILURE_RESULT_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_crop_policy_holdout_callback_visibility_failure_result.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerCropPolicyHoldoutCallbackRetryPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registration = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))
        cls.antecedent = json.loads(ANTECEDENT_PATH.read_text(encoding="utf-8"))
        cls.failure = json.loads(FAILURE_RESULT_PATH.read_text(encoding="utf-8"))

    def test_retry_is_prospective_and_chained_to_the_failed_holdout(self):
        registration = self.registration
        previous = registration["openedFailedHoldout"]
        self.assertEqual(
            registration[
                "prepareLayerCropPolicyHoldoutCallbackRetryPreregistrationSchemaVersion"
            ],
            1,
        )
        self.assertIn("prospective", registration["classification"])
        self.assertIsNone(registration["runtimeOutcomeFrozenBeforeDispatch"])
        self.assertEqual(previous["runID"], 31059229769)
        self.assertEqual(previous["workflowConclusion"], "failure")
        self.assertFalse(previous["cropPolicyOutcomeAvailable"])
        self.assertIsNone(previous["formulaPassed"])
        self.assertEqual(
            sha256(ANTECEDENT_PATH), previous["antecedentPreregistrationSHA256"]
        )
        self.assertEqual(sha256(FAILURE_RESULT_PATH), previous["failureResultSHA256"])

    def test_amendment_changes_callback_visibility_only(self):
        amendment = self.registration["transportOnlyAmendment"]
        self.assertEqual(
            amendment["failureClass"], "LLDB script callback name visibility"
        )
        self.assertEqual(
            amendment["mechanism"],
            "top-level forwarding callbacks rebound after inherited dynamic breakpoint installation",
        )
        self.assertTrue(amendment["sameBreakpointAddresses"])
        self.assertTrue(amendment["sameMemoryReads"])
        self.assertTrue(amendment["sameStructuralSelection"])
        self.assertTrue(amendment["sameStoreUnionCorrelation"])
        self.assertTrue(amendment["sameCandidateFormula"])
        self.assertTrue(amendment["sameValidator"])
        self.assertTrue(amendment["sameHoldoutMatrix"])
        self.assertTrue(amendment["sameAcceptance"])
        self.assertTrue(amendment["sameProductionShader"])

    def test_candidate_matrix_and_acceptance_are_byte_for_byte_unchanged(self):
        registration = self.registration
        self.assertEqual(
            registration["frozenCandidate"], self.antecedent["frozenCandidate"]
        )
        self.assertEqual(
            registration["holdoutMatrix"], self.antecedent["holdoutMatrix"]
        )
        self.assertEqual(registration["acceptance"], self.antecedent["acceptance"])

    def test_failure_result_records_no_scientific_outcome(self):
        diagnosis = self.failure["diagnosis"]
        evidence = self.failure["openedRepresentativeEvidence"]
        self.assertFalse(diagnosis["cropPolicyOutcomeAvailable"])
        self.assertIsNone(diagnosis["formulaPassed"])
        self.assertIsNone(diagnosis["formulaFailed"])
        self.assertFalse(diagnosis["parityEstablished"])
        self.assertFalse(evidence["targetStop"]["exited"])
        self.assertEqual(evidence["targetStop"]["prepareLayerOffsetHex"], "0x85dc")
        self.assertEqual(evidence["trace"]["qualifiedMarkerCount"], 0)
        self.assertEqual(evidence["trace"]["qualifiedUnionRecordCount"], 0)
        self.assertEqual(evidence["trace"]["qualifiedStoreRecordCount"], 1)
        self.assertFalse(evidence["trace"]["timelinePresent"])
        self.assertFalse(evidence["trace"]["validationPresent"])

    def test_frozen_implementation_hashes_match(self):
        for record in self.registration["frozenImplementation"]["files"]:
            self.assertEqual(sha256(REPOSITORY_ROOT / record["path"]), record["sha256"])
        shader = self.registration["frozenImplementation"]["productionShader"]
        self.assertEqual(
            shader["sha256"],
            "6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d",
        )
        local_shader = REPOSITORY_ROOT.parent / "shaders" / "frag.glsl"
        if local_shader.is_file():
            self.assertEqual(sha256(local_shader), shader["sha256"])


if __name__ == "__main__":
    unittest.main()
