#!/usr/bin/env python3
"""Regression tests for exact observed-timeline Material.Context laws."""

from __future__ import annotations

import ast
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import analyze_designlibrary_material_context_live_timeline_laws as analysis


ANALYSIS = Path(__file__).resolve().parent
SOURCE_PATH = Path(analysis.__file__).resolve()
RESULT_PATH = (
    ANALYSIS / "designlibrary_material_context_live_timeline_law_analysis_result.json"
)
EXPECTED_SOURCE_SHA256 = (
    "852ee9b3de2788cbb131ffaed244cab49a17d34f54856330948918e537757b96"
)
EXPECTED_RESULT_SHA256 = (
    "e3520a6819728117646fa2e4bb53801fa50cf1546e4901061f4e7c2d05e18c6e"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MaterialContextLiveTimelineLawAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_source_result_and_inputs_are_frozen(self) -> None:
        ast.parse(SOURCE_PATH.read_text(encoding="utf-8"), feature_version=(3, 9))
        self.assertEqual(sha256(SOURCE_PATH), EXPECTED_SOURCE_SHA256)
        self.assertEqual(sha256(RESULT_PATH), EXPECTED_RESULT_SHA256)
        self.assertEqual(
            self.result["inputs"],
            {
                "analysisSource": {
                    "path": "Analysis/" + SOURCE_PATH.name,
                    "sha256": EXPECTED_SOURCE_SHA256,
                },
                "zeroFlagsTransfer": {
                    "path": "Analysis/" + analysis.ZERO_FLAGS_RESULT_NAME,
                    "sha256": analysis.EXPECTED_ZERO_FLAGS_RESULT_SHA256,
                },
                "flagsProducedTransfer": {
                    "path": "Analysis/" + analysis.FLAGS_RESULT_NAME,
                    "sha256": analysis.EXPECTED_FLAGS_RESULT_SHA256,
                },
            },
        )

    def test_analysis_reproduces_the_canonical_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            regenerated = analysis.analyze(output)
            self.assertEqual(regenerated, self.result)
            self.assertEqual(output.read_bytes(), RESULT_PATH.read_bytes())

    def test_all_63_parameters_payloads_are_reconstructed_bitwise(self) -> None:
        invariants = self.result["measuredInvariants"]
        self.assertEqual(invariants["profileCount"], 2)
        self.assertEqual(invariants["capturedCaseCount"], 63)
        self.assertEqual(
            invariants["fullNormalizedParametersReconstructionMatchCount"], 63
        )
        self.assertEqual(invariants["retainedLiveTransferPredictionCount"], 252)
        self.assertEqual(invariants["retainedLiveTransferMatchCount"], 252)
        self.assertFalse(invariants["capturedValuesUsedForRuntimeSelection"])
        for profile in self.result["profiles"]:
            self.assertEqual(
                profile["fullNormalizedParametersReconstructionMatchCount"],
                profile["caseCount"],
            )
            for record in profile["reconstructions"]:
                self.assertTrue(record["dimensionLawMatchedBitwise"])
                self.assertTrue(record["fullNormalizedParametersMatchedBitwise"])
                self.assertEqual(
                    record["observedNormalizedParametersSHA256"],
                    record["reconstructedNormalizedParametersSHA256"],
                )

    def test_exact_profile_specific_varying_fields_are_pinned(self) -> None:
        profiles = {profile["name"]: profile for profile in self.result["profiles"]}
        self.assertEqual(
            [
                field["field"]
                for field in profiles["zeroFlagsRegularLight"]["varyingScalarFields"]
            ],
            [
                "shadow.height",
                "blur.radius",
                "edgeBleed.amount",
                "edgeBleed.height",
            ],
        )
        self.assertEqual(
            [
                field["field"]
                for field in profiles["flagsProducedRegularLight"][
                    "varyingScalarFields"
                ]
            ],
            [
                "shadow.height",
                "shadow.opacity",
                "shadow.vibrancyContribution",
                "blur.radius",
                "blur.distances.0",
                "refraction.outerHeight",
                "refraction.outerAmount",
                "edgeBleed.amount",
                "edgeBleed.height",
                "edgeBleed.blurRadius",
                "edgeBleed.opacity",
                "sdrAdjustment.shadowOpacityShift",
            ],
        )
        for profile in profiles.values():
            self.assertEqual(
                profile["dimensionLaw"],
                {
                    "expressionWithOperationOrder": "x = 143 - 16 * k",
                    "bitwiseMatchCount": profile["caseCount"],
                },
            )
            for field in profile["varyingScalarFields"]:
                self.assertEqual(field["bitwiseMatchCount"], profile["caseCount"])
                self.assertTrue(
                    all(item["matchedBitwise"] for item in field["observations"])
                )

    def test_claim_boundary_separates_observed_law_from_parity(self) -> None:
        claims = self.result["claims"]
        self.assertTrue(claims["exactObservedTimelineContextValueLawEstablished"])
        self.assertTrue(claims["allCapturedNormalizedParametersReconstructedBitwise"])
        self.assertTrue(claims["allOpenedLiveFieldsReplayedBitwise"])
        for name in (
            "completeLiveParametersTransferEstablished",
            "generalContextToParametersValueLawEstablished",
            "liveContextCallbackProductionEstablished",
            "generalIntegerCropAllocationPolicyEstablished",
            "retinaCompositorColorLawEstablished",
            "independentWalleZeroByteFrameParityEstablished",
            "liquidGlassParityEstablished",
            "productionShaderChangeAuthorized",
        ):
            self.assertFalse(claims[name])


if __name__ == "__main__":
    unittest.main()
