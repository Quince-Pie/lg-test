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
            1,
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
            "c1bfabda9338a7f574ababbeccf3d18ca3abc12d",
        )
        self.assertTrue(predecessor["captureContractMustPass"])
        self.assertEqual(
            predecessor["artifactDirectory"],
            "local-case22-provider-public-render-interval-c1bfabd-run1",
        )

    def test_captured_values_cannot_select_runtime_capture(self) -> None:
        self.assertFalse(self.value["selectionPolicy"]["runtimeByteOrValueSelection"])
        self.assertTrue(
            self.value["captureContract"][
                "noCapturedValueMaySelectRuntimeCapture"
            ]
        )

    def test_authority_remains_closed_beyond_same_profile_join(self) -> None:
        authority = self.value["productAuthority"]
        self.assertTrue(
            authority["sameProfilePublicParametersConstructionJoinEstablishedOnPass"]
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
