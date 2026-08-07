#!/usr/bin/env python3
"""Integrity tests for the live producer-census preregistration."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
REPOSITORY = ANALYSIS.parent
PREREGISTRATION_PATH = (
    ANALYSIS
    / "background_filter_constructor_timeline_marker_census_local_macos_26_6_1_preregistration.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ConstructorTimelineMarkerCensusPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))

    def test_runtime_outcome_is_unknown_before_dispatch(self) -> None:
        self.assertIsNone(self.value["runtimeOutcomeFrozenBeforeDispatch"])

    def test_every_frozen_file_hash_matches(self) -> None:
        for record in self.value["frozenImplementation"]["files"]:
            path = REPOSITORY / record["path"]
            self.assertTrue(path.is_file(), record["path"])
            self.assertEqual(sha256(path), record["sha256"], record["path"])

    def test_selection_is_control_flow_only(self) -> None:
        selection = self.value["selectionPolicy"]
        self.assertFalse(selection["capturedValuesMaySelectCalls"])
        self.assertIsNone(selection["minimumObservedCallCount"])
        self.assertTrue(selection["selectionFrozenBeforeDispatch"])
        contract = self.value["captureContract"]
        self.assertTrue(contract["noParametersOrBackgroundFilterBytesRead"])
        self.assertTrue(contract["noRegisterArgumentsRead"])
        self.assertTrue(contract["noObservedCallCountPredicted"])

    def test_parent_provider_gate_is_exact_and_passed(self) -> None:
        parent = self.value["parentProviderGate"]
        self.assertEqual(
            parent["resultSHA256"],
            "9ce1e32be073ef9ff0684fe8537d7fd44870f4b6566ac55498a25772bad7bc2e",
        )
        self.assertTrue(parent["prospectiveValidationPassed"])

    def test_authority_is_only_a_temporal_census(self) -> None:
        authority = self.value["productAuthority"]
        self.assertTrue(
            authority["liveProducerTemporalTopologyMeasuredOnPass"]
        )
        for key in (
            "parametersBytesJoinedToConstructorOnPass",
            "constructorOutputJoinedToProviderOnPass",
            "upstreamCropAllocationPolicyEstablishedOnPass",
            "physicalRetinaColorPixelCompositorTransferEstablishedOnPass",
            "independentWalleZeroByteFrameParityEstablishedOnPass",
            "liquidGlassParityEstablishedOnPass",
            "productionShaderAuthorizedOnPass",
        ):
            self.assertFalse(authority[key])


if __name__ == "__main__":
    unittest.main()
