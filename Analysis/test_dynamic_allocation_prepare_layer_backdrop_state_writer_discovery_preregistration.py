#!/usr/bin/env python3
"""Checks for the frozen backdrop-state writer-discovery preregistration."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREREGISTRATION_PATH = (
    ROOT
    / "Analysis"
    / "dynamic_allocation_prepare_layer_backdrop_state_writer_discovery_preregistration.json"
)


class BackdropStateWriterDiscoveryPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))

    def test_runtime_outcome_and_all_discovery_values_are_unknown(self) -> None:
        document = self.document
        self.assertIsNone(document["runtimeOutcomeFrozenBeforeDispatch"])
        target = document["liveBoundaryTarget"]
        for key in (
            "expectedSelfAddress",
            "expectedLayerAddress",
            "expectedOutputAddress",
            "expectedSelfMinusLayer",
            "expectedBackdropObjectBytes",
            "expectedLayerObjectBytes",
            "expectedPrimaryRectBeforeBytes",
            "expectedPrimaryRectAfterBytes",
            "expectedMarginF32",
            "expectedBackdropRectF64",
            "expectedLayerRectF64",
            "expectedSelectedBaseSource",
        ):
            self.assertIsNone(target[key])
        discovery = document["writerDiscoveryTarget"]
        for key in (
            "expectedMatchedNameCount",
            "expectedUniqueRangeCount",
            "expectedTotalCodeByteCount",
            "expectedSymbolNames",
            "expectedSymbolAddresses",
            "expectedCodeBytes",
            "expectedCodeSHA256",
            "expectedWriterIdentity",
            "expectedWriterArithmetic",
        ):
            self.assertIsNone(discovery[key])

    def test_capture_reuses_only_the_existing_dynamic_mechanism(self) -> None:
        contract = self.document["captureContract"]
        self.assertTrue(contract["reuseExistingOpaqueBoundaryStep"])
        self.assertEqual(contract["newBreakpointsAdded"], 0)
        self.assertEqual(contract["newInstructionStepsAdded"], 0)
        self.assertFalse(contract["fieldValueAcceptedBeforeCapture"])
        self.assertFalse(contract["pointerRelationshipAcceptedBeforeCapture"])
        self.assertFalse(contract["outputValueAcceptedBeforeCapture"])
        self.assertFalse(contract["symbolInventoryAcceptedBeforeCapture"])
        self.assertFalse(contract["writerCandidateAcceptedBeforeCapture"])
        self.assertFalse(contract["cropOrOutputValueUsedForSelection"])

    def test_claims_remain_fail_closed(self) -> None:
        authority = self.document["productAuthority"]
        self.assertTrue(authority["liveBackdropFieldCaptureMayBeOpened"])
        self.assertTrue(authority["selectedBackdropBoundsReplayMayBeOpened"])
        self.assertTrue(authority["classScopedBackdropWriterCodeInventoryMayBeOpened"])
        for key in (
            "backdropMarginWriterMayBeDeclaredDecoded",
            "dynamicTopologyLawMayBeDeclaredDecoded",
            "completeRegularCropLawMayBeClaimed",
            "capturedInputOpticalParityMayBeClaimed",
            "independentPrivateInputGenerationMayBeClaimed",
            "physicalOutputTransferMayBeClaimed",
            "independentWalleZeroByteParityMayBeClaimed",
            "productionShaderMayChange",
            "liquidGlassParityMayBeClaimed",
        ):
            self.assertFalse(authority[key])

    def test_frozen_file_hashes_match(self) -> None:
        for record in self.document["frozenImplementation"]["files"]:
            path = ROOT / record["path"]
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(digest, record["sha256"], record["path"])

    def test_production_shader_quality_lock_is_unchanged(self) -> None:
        shader = self.document["frozenImplementation"]["productionShader"]
        path = (ROOT / shader["externalPath"]).resolve()
        self.assertFalse(shader["changed"])
        self.assertEqual(
            shader["sha256"],
            "6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d",
        )
        if path.is_file():
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(), shader["sha256"]
            )


if __name__ == "__main__":
    unittest.main()
