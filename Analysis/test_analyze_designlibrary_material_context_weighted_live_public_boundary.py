#!/usr/bin/env python3
"""Regression tests for the weighted/live public presentation boundary."""

import ast
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import analyze_designlibrary_material_context_weighted_live_public_boundary as analysis


ANALYSIS = Path(__file__).resolve().parent
SOURCE_PATH = Path(analysis.__file__).resolve()
PROJECTION_PATH = ANALYSIS / analysis.PUBLIC_PROJECTION_NAME
RESULT_PATH = (
    ANALYSIS
    / "designlibrary_material_context_weighted_live_public_boundary_analysis_result.json"
)
EXPECTED_SOURCE_SHA256 = (
    "d9406c8d9390d58ed9c399426b8a1fee1436de49e6198bd9c0b7c5bcddf24e7f"
)
EXPECTED_PROJECTION_SHA256 = (
    "d4d8471355e0cbba4578d2b3786951116a372f5fcc94798ed9384687008d4573"
)
EXPECTED_RESULT_SHA256 = (
    "308943d6d5cb16166cd7a1a3f63a824a2b4e47f93bab18e13f7fccac51b94767"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WeightedLivePublicBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.projection = json.loads(PROJECTION_PATH.read_text(encoding="utf-8"))
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_sources_and_results_are_frozen(self) -> None:
        ast.parse(SOURCE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(sha256(SOURCE_PATH), EXPECTED_SOURCE_SHA256)
        self.assertEqual(sha256(PROJECTION_PATH), EXPECTED_PROJECTION_SHA256)
        self.assertEqual(sha256(RESULT_PATH), EXPECTED_RESULT_SHA256)
        self.assertEqual(
            analysis.EXPECTED_PUBLIC_PROJECTION_SHA256,
            EXPECTED_PROJECTION_SHA256,
        )

    def test_projection_preserves_the_frozen_public_scalar_domain(self) -> None:
        self.assertEqual(
            self.projection["sourceTimeline"],
            {
                "artifact": analysis.SOURCE_TIMELINE_ARTIFACT,
                "sha256": analysis.EXPECTED_SOURCE_TIMELINE_SHA256,
            },
        )
        self.assertEqual(len(self.projection["numericInputNames"]), 47)
        self.assertEqual(len(self.projection["samples"]), 32)
        self.assertEqual(
            [sample["sampleIndex"] for sample in self.projection["samples"]],
            list(range(1, 33)),
        )

    def test_analysis_reproduces_the_canonical_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            regenerated = analysis.analyze(output)
            self.assertEqual(regenerated, self.result)
            self.assertEqual(output.read_bytes(), RESULT_PATH.read_bytes())

    def test_complete_candidate_is_rejected_by_exact_counts(self) -> None:
        invariants = self.result["measuredInvariants"]
        self.assertEqual(invariants["caseCount"], 32)
        self.assertEqual(invariants["frozenOpenedPublicFieldPredictionCount"], 128)
        self.assertEqual(invariants["frozenOpenedPublicFieldPredictionMatchCount"], 128)
        self.assertEqual(invariants["mappedFieldCount"], 49)
        self.assertEqual(invariants["mappedComponentCount"], 1_568)
        self.assertEqual(invariants["mappedComponentBitwiseMatchCount"], 1_087)
        self.assertEqual(invariants["mappedComponentBitwiseMismatchCount"], 481)
        self.assertEqual(invariants["fullyExactMappedFieldCount"], 33)
        self.assertEqual(invariants["rejectedMappedFieldCount"], 16)
        self.assertEqual(invariants["endpointMappedFieldBitwiseMatchCount"], 48)
        self.assertFalse(invariants["capturedValuesUsedForRuntimeSelection"])

    def test_comparison_applies_the_authenticated_exporter_operations(self) -> None:
        exporter = self.result["inputs"]["authenticatedBackgroundFilterExporter"]
        self.assertEqual(
            exporter["sha256"],
            analysis.EXPECTED_BACKGROUND_FILTER_METADATA_RESULT_SHA256,
        )
        self.assertEqual(
            exporter["constructor"],
            analysis.EXPECTED_BACKGROUND_FILTER_CONSTRUCTOR,
        )
        self.assertEqual(
            exporter["filterArrayGetter"], analysis.EXPECTED_FILTER_ARRAY_GETTER
        )
        transforms = {
            field["parametersField"]: field["candidateToPublicTransform"]
            for field in self.result["mappedFields"]
        }
        self.assertEqual(transforms["blur.radius"], "multiply-by-binary64-0.5")
        self.assertEqual(
            transforms["filterArrayGetter.inputBlurDistance4.constantZero"],
            "constant-binary64-positive-zero",
        )
        constant = next(
            field
            for field in self.result["mappedFields"]
            if field["publicInput"] == "inputBlurDistance4"
        )
        self.assertIsNone(constant["sourceParametersField"])
        for index in range(5):
            self.assertEqual(
                transforms[f"blur.opacities.{index}"],
                "binary32-multiply-by-blur-opacity",
            )

    def test_rejected_fields_are_exactly_pinned(self) -> None:
        self.assertEqual(
            self.result["measuredInvariants"]["rejectedMappedFields"],
            [
                "edgeBleed.ycc.saturation",
                "edgeBleed.ycc.white",
                "filterArrayGetter.inputBlurDistance4.constantZero",
                "blur.opacities.0",
                "blur.opacities.1",
                "blur.opacities.2",
                "blur.opacities.3",
                "blur.opacities.4",
                "faceEffects.ycc.saturation",
                "faceEffects.ycc.white",
                "sdrAdjustment.faceDimming.whitePointShift",
                "sdrAdjustment.headroomTransitionPoint",
                "shadow.ycc.saturation",
                "shadow.ycc.white",
                "shadow.offset.height",
                "edgeBleed.useDarkenBlending",
            ],
        )

    def test_first_state_contains_concrete_nonzero_baseline_counterexamples(
        self,
    ) -> None:
        fields = {
            field["parametersField"]: field for field in self.result["mappedFields"]
        }
        expected = {
            "filterArrayGetter.inputBlurDistance4.constantZero": (
                None,
                0.0,
                3.67435648732062,
            ),
            "shadow.offset.height": (1.0430068969726562, 1.0430068969726562, 8.0),
            "blur.opacities.0": (
                0.13037586212158203,
                0.016997866332530975,
                0.13037586212158203,
            ),
            "blur.opacities.1": (
                0.06518793106079102,
                0.008498933166265488,
                0.03117453306913376,
            ),
            "sdrAdjustment.headroomTransitionPoint": (
                1303.6282958984375,
                1303.6282958984375,
                1304.671875,
            ),
            "sdrAdjustment.faceDimming.whitePointShift": (
                0.1264645904302597,
                0.1264645904302597,
                0.9960887432098389,
            ),
        }
        for name, (candidate, predicted, public) in expected.items():
            observation = fields[name]["observations"][0]
            self.assertEqual(observation["candidateValue"], candidate)
            self.assertEqual(observation["predictedPublicValue"], predicted)
            self.assertEqual(observation["publicValue"], public)
            self.assertFalse(observation["matchedBitwise"])
        constant = fields["filterArrayGetter.inputBlurDistance4.constantZero"]
        self.assertIsNone(
            constant["observations"][0]["candidateRawLittleEndianHex"]
        )
        self.assertEqual(
            constant["observations"][0]["predictedPublicRawLittleEndianHex"],
            "0000000000000000",
        )
        self.assertNotIn("backdropScale", fields)
        darken = fields["edgeBleed.useDarkenBlending"]["observations"][0]
        self.assertEqual(darken["candidateValue"], "false")
        self.assertIs(darken["predictedPublicValue"], False)
        self.assertIs(darken["publicValue"], True)
        self.assertFalse(darken["matchedBitwise"])

    def test_claims_preserve_the_formal_parity_boundary(self) -> None:
        claims = self.result["claims"]
        self.assertTrue(
            claims["controlledCompleteWeightedParametersCandidateEstablished"]
        )
        self.assertTrue(claims["allFrozenOpenedZeroBaselinePublicFieldsReplayBitwise"])
        self.assertTrue(
            claims["controlledCandidateRejectedAsCompleteLivePresentationState"]
        )
        self.assertTrue(claims["distinctLivePresentationTransformationRequired"])
        for name in (
            "controlledCandidateMatchesCompleteMappedPublicState",
            "actualLiveCallbackCompleteParametersObserved",
            "completeLiveParametersTransferEstablished",
            "generalIntegerCropAllocationPolicyEstablished",
            "retinaCompositorColorLawEstablished",
            "independentWalleZeroByteFrameParityEstablished",
            "liquidGlassParityEstablished",
            "productionShaderChangeAuthorized",
        ):
            self.assertFalse(claims[name])


if __name__ == "__main__":
    unittest.main()
