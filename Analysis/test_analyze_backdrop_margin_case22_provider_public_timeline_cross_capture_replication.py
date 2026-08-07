#!/usr/bin/env python3
"""Tests for the retrospective cross-capture public/provider replication."""

from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
SOURCE_PATH = (
    ANALYSIS
    / "analyze_backdrop_margin_case22_provider_public_timeline_cross_capture_replication.py"
)
RESULT_PATH = (
    ANALYSIS
    / "backdrop_margin_case22_provider_public_timeline_cross_capture_replication_retrospective_result.json"
)
RESULT = json.loads(RESULT_PATH.read_text(encoding="utf-8"))


class PublicTimelineCrossCaptureReplicationTests(unittest.TestCase):
    def test_source_remains_python_3_9_parseable(self) -> None:
        ast.parse(SOURCE_PATH.read_text(encoding="utf-8"), feature_version=(3, 9))

    def test_result_is_canonical_and_source_bound(self) -> None:
        self.assertEqual(
            RESULT_PATH.read_text(encoding="utf-8"),
            json.dumps(RESULT, indent=2, sort_keys=True) + "\n",
        )
        self.assertEqual(
            RESULT["inputs"]["analysisSource"]["sha256"],
            hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest(),
        )

    def test_both_raw_capture_identities_and_modes_are_frozen(self) -> None:
        allocation = RESULT["inputs"]["allocationCapture"]
        normal = RESULT["inputs"]["normalCapture"]
        self.assertEqual(
            allocation["providerTraceSHA256"],
            "0e83312d2535ad6601b6bcae178e939e13a9ebae95d15efcc166ffde013e6d72",
        )
        self.assertEqual(
            normal["providerTraceSHA256"],
            "32f82fab6a209831347bd2673a6c83fb304cdc72fb04045f37ed23c1ea0be614",
        )
        self.assertEqual(allocation["evidenceMode"], "allocation-metadata-v1")
        self.assertEqual(normal["evidenceMode"], "controlled-replay-v1")
        self.assertNotEqual(allocation["sourceCommit"], normal["sourceCommit"])

    def test_normal_capture_replication_is_unique_collision_free_and_monotonic(
        self,
    ) -> None:
        replication = RESULT["replication"]
        self.assertEqual(replication["independentCaptureCount"], 2)
        self.assertEqual(replication["allocationProviderCallCount"], 1228)
        self.assertEqual(replication["normalProviderCallCount"], 1232)
        self.assertEqual(replication["allocationUniqueNonEndpointJoinCount"], 31)
        self.assertEqual(replication["normalUniqueNonEndpointJoinCount"], 8)
        self.assertEqual(
            replication["normalMatchedProviderCallIndices"],
            [70, 177, 331, 497, 657, 817, 964, 1091],
        )
        self.assertTrue(replication["allUniqueJoinsHaveZeroPartialCollisions"])
        self.assertTrue(replication["allUniqueJoinsStrictlyIncreasingWithinCapture"])

    def test_every_overlapping_input_changes_while_relations_transfer_exactly(
        self,
    ) -> None:
        replication = RESULT["replication"]
        self.assertEqual(replication["overlappingNonEndpointSampleCount"], 8)
        self.assertEqual(replication["changedSignatureWordComparisonCount"], 32)
        self.assertEqual(replication["equalConstantLoadedFieldComparisonCount"], 112)
        self.assertEqual(replication["changedVaryingLoadedFieldComparisonCount"], 32)
        for record in replication["crossCapturePairs"]:
            self.assertEqual(record["changedSignatureWordCount"], 4)
            self.assertEqual(record["equalConstantLoadedFieldCount"], 14)
            self.assertEqual(record["changedVaryingLoadedFieldCount"], 4)
            self.assertNotEqual(
                record["allocationProviderObjectSHA256"],
                record["normalProviderObjectSHA256"],
            )

    def test_endpoint_ambiguity_shape_replicates_exactly(self) -> None:
        replication = RESULT["replication"]
        self.assertTrue(
            replication["endpointPatternReplicatedAsInitialPlusTwoTerminalCalls"]
        )
        self.assertEqual(
            replication["allocationEndpoint"]["fullMatchCallIndices"],
            [0, 1226, 1227],
        )
        self.assertEqual(
            replication["normalEndpoint"]["fullMatchCallIndices"],
            [0, 1230, 1231],
        )
        self.assertEqual(replication["allocationEndpoint"]["partialMatchCallCount"], 0)
        self.assertEqual(replication["normalEndpoint"]["partialMatchCallCount"], 0)

    def test_normal_provider_execution_and_all_loaded_fields_replay_exactly(
        self,
    ) -> None:
        execution = RESULT["normalProviderExecution"]
        self.assertEqual(execution["matchingReplayReturnCount"], 8)
        self.assertEqual(execution["distinctExecutedPathCount"], 1)
        self.assertEqual(execution["loadedFieldCount"], 18)
        self.assertTrue(execution["allEightReturnsReplayedBitwise"])
        self.assertTrue(execution["allEightReturnsExactZero"])
        observations = {
            record["providerObjectOffset"]: record
            for record in execution["loadedFieldObservations"]
        }
        self.assertEqual(len(observations), 18)
        for offset in (0x018, 0x098, 0x0E8, 0x160):
            self.assertGreater(observations[offset]["distinctRawWordCount"], 1)

    def test_original_failed_gate_is_not_relabelled_or_promoted(self) -> None:
        normal = RESULT["inputs"]["normalCapture"]
        self.assertFalse(normal["originalProspectiveContractPassed"])
        self.assertEqual(
            normal["originalFailedRequirementsPreserved"],
            [
                "requireAtLeastTwoDistinctProviderReturnWords",
                "requireAtLeastOneFinitePositiveProviderReturn",
            ],
        )
        authority = RESULT["authority"]
        self.assertTrue(authority["retrospectiveCrossCaptureReplicationEstablished"])
        self.assertFalse(authority["normalOriginalProspectiveFailureRelabelledAsPass"])
        self.assertFalse(authority["authenticatedPerCallbackTemporalJoinEstablished"])
        self.assertFalse(
            authority["prospectivePublicInputToProviderConstructionTransferEstablished"]
        )
        self.assertFalse(authority["liquidGlassParityEstablished"])
        self.assertFalse(authority["productionShaderAuthorized"])


if __name__ == "__main__":
    unittest.main()
