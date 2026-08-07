#!/usr/bin/env python3
"""Regression tests for the frozen live Parameters/public boundary analysis."""

import hashlib
import json
import unittest
from pathlib import Path

import analyze_background_filter_constructor_live_public_boundary_local_macos_26_6_1 as analysis
import analyze_designlibrary_material_context_weighted_live_public_boundary as boundary


ANALYSIS = Path(__file__).resolve().parent
SOURCE = Path(analysis.__file__).resolve()
PREREGISTRATION = ANALYSIS / analysis.PREREGISTRATION_NAME
WEIGHTED_RESULT = (
    ANALYSIS / "designlibrary_material_context_weighted_live_timeline_parameters_"
    "local_macos_26_6_1_result.json"
)
PUBLIC_PROJECTION = ANALYSIS / boundary.PUBLIC_PROJECTION_NAME
BOUNDARY_RESULT = (
    ANALYSIS
    / "designlibrary_material_context_weighted_live_public_boundary_analysis_result.json"
)
EXPECTED_SOURCE_SHA256 = (
    "6329a734fb875ceb140559fabb539c14fef69b0768f886525453d7867da9052e"
)
EXPECTED_PREREGISTRATION_SHA256 = (
    "f634ac687b0b86f614fef18e6f4929d56cf31cd0b77d5a4b14034a03cb0a6030"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LivePublicBoundaryAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preregistration = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
        cls.weighted = json.loads(WEIGHTED_RESULT.read_text(encoding="utf-8"))
        cls.projection = json.loads(PUBLIC_PROJECTION.read_text(encoding="utf-8"))
        cls.boundary_result = json.loads(BOUNDARY_RESULT.read_text(encoding="utf-8"))

    def test_source_and_preregistration_are_frozen(self) -> None:
        self.assertEqual(sha256(SOURCE), EXPECTED_SOURCE_SHA256)
        self.assertEqual(sha256(PREREGISTRATION), EXPECTED_PREREGISTRATION_SHA256)
        self.assertEqual(
            analysis.normalized_source_sha256(SOURCE),
            self.preregistration["sourceIdentity"]["analysisSourceNormalizedSHA256"],
        )
        self.assertEqual(
            analysis.validate_frozen_inputs(ANALYSIS, SOURCE)["preregistration"][
                "sha256"
            ],
            EXPECTED_PREREGISTRATION_SHA256,
        )

    def test_preregistration_leaves_every_result_count_unknown(self) -> None:
        self.assertEqual(
            self.preregistration["artifactDirectoryName"],
            analysis.EXPECTED_ARTIFACT_DIRECTORY_NAME,
        )
        self.assertEqual(self.preregistration["caseCount"], 32)
        self.assertFalse(self.preregistration["capturedValuesUsedForAnalysisSelection"])
        self.assertTrue(
            all(
                value is None
                for value in self.preregistration["unknownBeforeCapture"].values()
            )
        )

    def test_frozen_mapper_reproduces_the_existing_canonical_boundary(self) -> None:
        cases, unique = boundary.validate_weighted_result(self.weighted)
        payloads = [
            boundary.weighted_payload(
                boundary.object_value(case, "weighted case"),
                unique,
            )
            for case in cases
        ]
        samples = [
            boundary.object_value(sample, "public sample")
            for sample in self.projection["samples"]
        ]
        self.assertEqual(
            analysis.mapped_field_results(payloads, samples),
            self.boundary_result["mappedFields"],
        )

    def test_live_parameters_uses_only_validator_selected_builder_calls(self) -> None:
        cases, unique = boundary.validate_weighted_result(self.weighted)
        payloads = [
            boundary.weighted_payload(
                boundary.object_value(case, "weighted case"),
                unique,
            )
            for case in cases
        ]
        validation = {
            "constructorProviderJoin": {
                "joins": [
                    {
                        "sampleIndex": sample_index,
                        "parametersBuilderCallIndices": [sample_index - 1],
                        "parametersSHA256": analysis.digest_bytes(payload),
                    }
                    for sample_index, payload in enumerate(payloads, start=1)
                ]
            }
        }
        trace = {
            "parametersBuilderCalls": [
                {
                    "assignedSampleIndex": sample_index,
                    "outputParametersAtReturn": {"hex": payload.hex()},
                }
                for sample_index, payload in enumerate(payloads, start=1)
            ]
        }
        extracted, records = analysis.live_parameters(validation, trace)
        self.assertEqual(extracted, payloads)
        self.assertEqual(
            [record["rawParametersSHA256"] for record in records],
            [analysis.digest_bytes(payload) for payload in payloads],
        )


if __name__ == "__main__":
    unittest.main()
