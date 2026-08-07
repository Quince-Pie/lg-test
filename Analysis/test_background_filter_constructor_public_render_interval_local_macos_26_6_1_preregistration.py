#!/usr/bin/env python3
"""Integrity checks for the constructor/public-render preregistration."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
REPOSITORY = ANALYSIS.parent
PREREGISTRATION_PATH = (
    ANALYSIS
    / "background_filter_constructor_public_render_interval_local_macos_26_6_1_preregistration.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BackgroundFilterConstructorPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))

    def test_schema_profile_and_host_are_exact(self) -> None:
        self.assertEqual(
            self.value[
                "backgroundFilterConstructorPublicRenderIntervalLocalMacOSPreregistrationSchemaVersion"
            ],
            2,
        )
        self.assertEqual(self.value["profile"]["sampleIndices"], list(range(1, 33)))
        self.assertEqual(self.value["host"]["macOSBuildVersion"], "25G76")
        self.assertEqual(self.value["host"]["sshTarget"], "quince@10.0.41.19")

    def test_every_frozen_file_hash_matches(self) -> None:
        for record in self.value["frozenImplementation"]["files"]:
            path = REPOSITORY / record["path"]
            self.assertTrue(path.is_file(), record["path"])
            self.assertEqual(sha256(path), record["sha256"], record["path"])

    def test_constructor_boundary_is_exact(self) -> None:
        self.assertEqual(
            self.value["constructorBoundary"],
            {
                "backgroundFilterByteCount": 504,
                "initializedByteCount": 491,
                "initializedRanges": [[0, 349], [352, 458], [464, 476], [480, 504]],
                "paddingRanges": [[349, 352], [458, 464], [476, 480]],
                "callInstructionHex": "730a0094",
                "callOffsetInProducer": 0x38C,
                "constructorByteCount": 0x414,
                "constructorCodeSHA256": "71a592bc8a187fe8bcca0fa50c3f4d36ea3c2916dbd5d16f3fa1df05b86f131d",
                "constructorModuleOffset": 0xBAD00,
                "parametersByteCount": 0x401,
                "producerByteCount": 0x66C,
                "producerCodeSHA256": "0729f7b0f874c0fb9fb64fa3383a6f2ed328d1dc55fdce53b82038a188df6f97",
                "producerModuleOffset": 0xB7FA8,
                "returnOffsetInProducer": 0x390,
            },
        )

    def test_predecessor_is_frozen_and_mandatory(self) -> None:
        predecessor = self.value["requiredPredecessor"]
        self.assertEqual(
            predecessor["captureCommit"],
            "72a73594907c50710182515661f367fbf0d85542",
        )
        self.assertTrue(predecessor["captureContractMustPass"])
        self.assertEqual(
            predecessor["artifactDirectory"],
            "local-case22-provider-public-render-interval-72a7359-run1",
        )

    def test_preflight_correction_precedes_dispatch_and_preserves_predictions(self) -> None:
        amendment = self.value["operationalAmendment"]
        self.assertTrue(amendment["noAppleApplicationDispatchedBeforeCorrection"])
        self.assertTrue(amendment["prospectivePredictionsUnchanged"])
        self.assertTrue(amendment["runtimeOutcomeStillNull"])

    def test_symbol_presentation_correction_saw_no_optical_intervals(self) -> None:
        amendment = self.value["symbolIdentityOperationalAmendment"]
        self.assertEqual(amendment["failedCaptureFinalIntervalCount"], 0)
        self.assertEqual(amendment["failedCaptureFinalCallCount"], 0)
        self.assertFalse(amendment["opticalPredictionsEvaluatedBeforeCorrection"])
        self.assertTrue(amendment["prospectiveOpticalPredictionsUnchanged"])

    def test_parameters_blend_boundary_is_exact(self) -> None:
        self.assertEqual(
            self.value["parametersBlendBoundary"],
            {
                "accumulatorFrameOffset": 0x1900,
                "animatableDataByteCount": 0x481,
                "blendDecisionOffsetInBuilder": 0xFB8,
                "blendFinalGateOffsetInBuilder": 0x1174,
                "blendResolvedOffsetInBuilder": 0x118C,
                "builderByteCount": 0x1334,
                "builderCodeSHA256": "07d9b8571ca8fed42e1d8e71b312f00a9c9713ce19f406d6f2c15a9d2403fde4",
                "builderModuleOffset": 0x120B4C,
                "callInstructionHex": "17030094",
                "callOffsetInCaller": 0xD34,
                "callerByteCount": 0xD7C,
                "callerCodeSHA256": "ba0ad1081cece802ccd1e148660a542145f95bf57a92de4407a3fad55f4679c6",
                "callerModuleOffset": 0x11F1BC,
                "collectionCountFrameOffset": 0xB0,
                "currentParametersFrameOffset": 0x1068,
                "factorRegister": "d9",
                "maximumBlendDecisions": 16384,
                "maximumParametersBuilderCalls": 4096,
                "parametersByteCount": 0x401,
                "resolverFlagFrameOffset": 0x7C,
                "returnOffsetInCaller": 0xD38,
                "unityRawLittleEndianHex": "000000000000f03f",
                "unityRegister": "d12",
                "workingParametersFrameOffset": 0xC60,
            },
        )

    def test_captured_values_cannot_select_runtime_capture(self) -> None:
        self.assertFalse(self.value["selectionPolicy"]["runtimeByteOrValueSelection"])
        self.assertTrue(
            self.value["captureContract"]["noCapturedValueMaySelectRuntimeCapture"]
        )
        self.assertIn(
            "every execution", self.value["selectionPolicy"]["blendDecisions"]
        )
        self.assertIn(
            "every call", self.value["selectionPolicy"]["parametersBuilderCalls"]
        )

    def test_blend_predictions_are_prospectively_frozen(self) -> None:
        predictions = self.value["prospectivePredictions"]
        for key in (
            "allConstructorParametersHaveSameSampleBuilderOutput",
            "allParametersBuilderCallsHaveAtLeastOneBlendDecision",
            "allParametersBuilderCallsOnAuthenticatedFunctionThread",
            "allParametersBuilderCallsReachFinalGate",
            "allParametersBuilderCallsReachResolvedConvergence",
            "allParametersBuilderOutputsEqualResolvedWorkingParameters",
            "allSamplesHaveAtLeastOneParametersBuilderCall",
            "resolverFlagIsOneAtEveryDecision",
            "unityRegisterIsExactOneAtEveryDecision",
        ):
            self.assertTrue(predictions[key], key)

    def test_authority_remains_closed_beyond_same_profile_join(self) -> None:
        authority = self.value["productAuthority"]
        self.assertTrue(
            authority["sameProfilePublicParametersConstructionJoinEstablishedOnPass"]
        )
        self.assertTrue(
            authority["sameProfilePublicParametersBlendProvenanceEstablishedOnPass"]
        )
        self.assertTrue(
            authority["allInitializedBackgroundFilterProviderBytesJoinedBitwiseOnPass"]
        )
        self.assertFalse(
            authority[
                "completeBackgroundFilterProviderObjectJoinedBitwiseGuaranteedOnPass"
            ]
        )
        for key in (
            "freshMaterialAppearanceGeometryProfileTransferEstablishedOnPass",
            "generalPublicInputConstructionLawEstablishedOnPass",
            "independentWalleZeroByteFrameParityEstablishedOnPass",
            "liquidGlassParityEstablishedOnPass",
            "physicalRetinaColorPixelCompositorTransferEstablishedOnPass",
            "productionShaderAuthorizedOnPass",
            "upstreamCropAllocationPolicyEstablishedOnPass",
        ):
            self.assertFalse(authority[key], key)


if __name__ == "__main__":
    unittest.main()
