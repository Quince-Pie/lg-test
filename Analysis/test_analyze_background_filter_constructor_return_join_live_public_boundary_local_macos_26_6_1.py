#!/usr/bin/env python3
"""Regression tests for the accepted-return live/public boundary analysis."""

import hashlib
import json
import unittest
from pathlib import Path

import analyze_background_filter_constructor_return_join_live_public_boundary_local_macos_26_6_1 as analysis


ANALYSIS = Path(__file__).resolve().parent
SOURCE = Path(analysis.__file__).resolve()
PREREGISTRATION = ANALYSIS / analysis.PREREGISTRATION_NAME
EXPECTED_SOURCE_SHA256 = (
    "d9f899b92b3fdead7712ea32d2a24b8002a6e4c7d7d8780c39b6e7108f091bee"
)
EXPECTED_PREREGISTRATION_SHA256 = (
    "4989483973cb9bbed473796102b59589616b6ab1d84ad80a189d5a6288248c1e"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReturnJoinLivePublicBoundaryAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preregistration = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))

    def test_source_preregistration_and_dependencies_are_frozen(self) -> None:
        self.assertEqual(sha256(SOURCE), EXPECTED_SOURCE_SHA256)
        self.assertEqual(sha256(PREREGISTRATION), EXPECTED_PREREGISTRATION_SHA256)
        self.assertEqual(
            analysis.normalized_source_sha256(SOURCE),
            self.preregistration["sourceIdentity"]["analysisSourceNormalizedSHA256"],
        )
        frozen = analysis.validate_frozen_inputs(ANALYSIS, SOURCE)
        self.assertEqual(
            frozen["preregistration"]["sha256"], EXPECTED_PREREGISTRATION_SHA256
        )

    def test_outcomes_are_unknown_and_mapping_predates_capture(self) -> None:
        self.assertEqual(self.preregistration["caseCount"], analysis.CASE_COUNT)
        self.assertEqual(
            self.preregistration["mappedFieldCount"], analysis.MAPPED_FIELD_COUNT
        )
        self.assertEqual(
            self.preregistration["mappedComponentCount"],
            analysis.MAPPED_COMPONENT_COUNT,
        )
        self.assertTrue(
            self.preregistration["mappingContract"]["mappingWasFrozenBeforeCapture"]
        )
        self.assertFalse(
            self.preregistration["capturedValuesUsedForSampleOrChainSelection"]
        )
        self.assertTrue(
            all(
                value is None
                for value in self.preregistration["unknownBeforeAnalysis"].values()
            )
        )

    def test_live_parameters_uses_only_prospectively_selected_chain_indices(self) -> None:
        payloads = [
            bytes([sample_index]) + bytes(analysis.basis.PARAMETERS_BYTE_COUNT - 1)
            for sample_index in range(1, analysis.CASE_COUNT + 1)
        ]
        validation = {
            "publicJoins": {
                "selectedChains": [
                    {
                        "sampleIndex": sample_index,
                        "structurallySelectedChainIndex": sample_index - 1,
                        "parametersSHA256": analysis.legacy.digest_bytes(payload),
                    }
                    for sample_index, payload in enumerate(payloads, start=1)
                ]
            }
        }
        trace = {
            "chains": [
                {
                    "chainIndex": chain_index,
                    "stage": "complete",
                    "builderOutputAtReturn": {
                        "hex": payload.hex(),
                        "sha256": analysis.legacy.digest_bytes(payload),
                    },
                }
                for chain_index, payload in enumerate(payloads)
            ]
        }
        extracted, records = analysis.live_parameters(validation, trace)
        self.assertEqual(extracted, payloads)
        self.assertEqual(
            [record["structurallySelectedChainIndex"] for record in records],
            list(range(analysis.CASE_COUNT)),
        )

    def test_duplicate_selected_chain_is_rejected(self) -> None:
        payload = bytes(analysis.basis.PARAMETERS_BYTE_COUNT)
        digest = analysis.legacy.digest_bytes(payload)
        validation = {
            "publicJoins": {
                "selectedChains": [
                    {
                        "sampleIndex": sample_index,
                        "structurallySelectedChainIndex": 0,
                        "parametersSHA256": digest,
                    }
                    for sample_index in range(1, analysis.CASE_COUNT + 1)
                ]
            }
        }
        trace = {
            "chains": [
                {
                    "chainIndex": 0,
                    "stage": "complete",
                    "builderOutputAtReturn": {
                        "hex": payload.hex(),
                        "sha256": digest,
                    },
                }
            ]
        }
        with self.assertRaisesRegex(analysis.AnalysisError, "not distinct"):
            analysis.live_parameters(validation, trace)


if __name__ == "__main__":
    unittest.main()
