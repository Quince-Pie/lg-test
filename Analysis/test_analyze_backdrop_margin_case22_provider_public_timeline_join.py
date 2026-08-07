#!/usr/bin/env python3
"""Tests for the retrospective public/provider timeline join."""

from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path

import analyze_backdrop_margin_case22_provider_public_timeline_join as analysis


ANALYSIS = Path(__file__).resolve().parent
SOURCE_PATH = (
    ANALYSIS / "analyze_backdrop_margin_case22_provider_public_timeline_join.py"
)
RESULT_PATH = (
    ANALYSIS
    / "backdrop_margin_case22_provider_public_timeline_join_retrospective_result.json"
)
RESULT = json.loads(RESULT_PATH.read_text(encoding="utf-8"))


class PublicTimelineProviderJoinAnalysisTests(unittest.TestCase):
    def test_source_remains_python_3_9_parseable(self) -> None:
        ast.parse(SOURCE_PATH.read_text(encoding="utf-8"), feature_version=(3, 9))

    def test_signature_matching_is_raw_and_requires_all_four_words(self) -> None:
        raw = bytearray(384)
        words = tuple(bytes([index + 1]) * 8 for index in range(4))
        for (offset, _key, _scale), word in zip(analysis.SIGNATURE, words):
            raw[offset : offset + 8] = word
        self.assertEqual(analysis.signature_match_count(bytes(raw), words), 4)
        raw[analysis.SIGNATURE[2][0]] ^= 0x01
        self.assertEqual(analysis.signature_match_count(bytes(raw), words), 3)

    def test_result_is_canonical_and_source_bound(self) -> None:
        self.assertEqual(
            RESULT_PATH.read_text(encoding="utf-8"),
            json.dumps(RESULT, indent=2, sort_keys=True) + "\n",
        )
        self.assertEqual(
            RESULT["inputs"]["analysisSource"]["sha256"],
            hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest(),
        )

    def test_join_is_exact_unique_and_monotonic_for_samples_1_through_31(self) -> None:
        selector = RESULT["selector"]
        expected = [
            50,
            87,
            134,
            163,
            213,
            254,
            297,
            330,
            365,
            421,
            450,
            482,
            520,
            568,
            600,
            642,
            675,
            721,
            753,
            790,
            832,
            866,
            934,
            948,
            977,
            1018,
            1059,
            1102,
            1120,
            1166,
            1190,
        ]
        self.assertEqual(selector["matchedProviderCallIndices"], expected)
        self.assertEqual(selector["uniqueNonEndpointJoinCount"], 31)
        self.assertTrue(selector["allNonEndpointOtherCallsMatchedZeroSignatureWords"])
        self.assertTrue(selector["allNonEndpointJoinsStrictlyIncreasing"])
        for sample in selector["joinedSamples"]:
            self.assertEqual(sample["partialMatchCallCount"], 0)
            self.assertEqual(
                sample["providerCallMatchHistogram"],
                [
                    {"matchingSignatureWordCount": 0, "providerCallCount": 1227},
                    {"matchingSignatureWordCount": 4, "providerCallCount": 1},
                ],
            )

    def test_repeated_endpoint_is_reported_as_ambiguous(self) -> None:
        endpoint = RESULT["selector"]["endpoint"]
        self.assertEqual(endpoint["sampleIndex"], 32)
        self.assertEqual(endpoint["fullMatchCallIndices"], [0, 1226, 1227])
        self.assertEqual(endpoint["partialMatchCallCount"], 0)
        self.assertIn("ambiguous", endpoint["classification"])

    def test_every_loaded_field_on_the_joined_path_is_accounted_for(self) -> None:
        execution = RESULT["providerExecution"]
        self.assertEqual(execution["joinedSampleCount"], 31)
        self.assertEqual(execution["matchingInstructionReplayReturnCount"], 31)
        self.assertTrue(execution["allJoinedReturnsReplayedBitwise"])
        self.assertEqual(execution["distinctExecutedPathCount"], 1)
        self.assertEqual(execution["loadedFieldCount"], 18)
        self.assertEqual(execution["varyingLoadedFieldCount"], 4)
        self.assertEqual(execution["constantLoadedFieldCount"], 14)
        observations = {
            record["providerObjectOffset"]: record
            for record in execution["loadedFieldObservations"]
        }
        self.assertEqual(set(observations), {
            0x008, 0x010, 0x018, 0x028, 0x038, 0x088,
            0x090, 0x098, 0x0A0, 0x0A8, 0x0B0, 0x0B8,
            0x0C0, 0x0E8, 0x0F8, 0x110, 0x160, 0x178,
        })
        self.assertEqual(observations[0x018]["distinctRawWordCount"], 31)
        self.assertEqual(observations[0x098]["distinctRawWordCount"], 31)
        self.assertEqual(observations[0x0E8]["distinctRawWordCount"], 31)
        self.assertEqual(observations[0x160]["distinctRawWordCount"], 31)

    def test_authority_does_not_promote_retrospective_covariance(self) -> None:
        authority = RESULT["authority"]
        self.assertTrue(authority["retrospectiveUniqueCrossArtifactValueJoinEstablished"])
        self.assertTrue(authority["allProviderLoadedFieldsCharacterizedForJoinedOpenedPath"])
        self.assertFalse(authority["authenticatedPerCallbackTemporalJoinEstablished"])
        self.assertFalse(
            authority["prospectivePublicInputToProviderConstructionTransferEstablished"]
        )
        self.assertFalse(authority["generalPublicInputObjectConstructionLawEstablished"])
        self.assertFalse(authority["liquidGlassParityEstablished"])
        self.assertFalse(authority["productionShaderAuthorized"])


if __name__ == "__main__":
    unittest.main()
