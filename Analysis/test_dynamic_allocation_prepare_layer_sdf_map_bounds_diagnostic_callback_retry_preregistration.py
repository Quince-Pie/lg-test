#!/usr/bin/env python3
"""Integrity tests for the SDF callback-visibility retry."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_sdf_map_bounds_diagnostic_callback_retry_preregistration.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerSDFMapBoundsCallbackRetryPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registration = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))

    def test_retry_is_prospective_and_output_blind(self) -> None:
        registration = self.registration
        self.assertEqual(
            registration[
                "prepareLayerSDFMapBoundsDiagnosticCallbackRetryPreregistrationSchemaVersion"
            ],
            1,
        )
        self.assertIn("prospective", registration["classification"])
        self.assertIn("output-blind", registration["classification"])
        self.assertIsNone(registration["runtimeOutcomeFrozenBeforeDispatch"])

    def test_first_run_is_preserved_as_preselector_null(self) -> None:
        prior = self.registration["priorNullRun"]
        self.assertEqual(prior["runID"], 31077148370)
        self.assertEqual(prior["dynamicDispatchCount"], 0)
        self.assertEqual(prior["sdfInstructionStateCount"], 0)
        self.assertFalse(prior["sdfCodeCaptured"])
        self.assertFalse(prior["selectorReached"])
        self.assertFalse(prior["captureRuleExercised"])
        self.assertFalse(prior["scientificHypothesisTested"])

    def test_only_callback_visibility_changes(self) -> None:
        correction = self.registration["frozenCorrection"]
        self.assertEqual(len(correction["callbacksForwarded"]), 6)
        self.assertTrue(correction["dynamicCallbacksReboundAfterPrepareEntry"])
        for field in (
            "newBreakpointAdded",
            "newMemoryReadAdded",
            "newSteppingRuleAdded",
            "selectorChanged",
            "captureRuleChanged",
            "validatorChanged",
            "timelineChanged",
            "cropOrOutputValuesReadForSelection",
        ):
            self.assertFalse(correction[field])

    def test_product_authority_remains_closed(self) -> None:
        acceptance = self.registration["acceptance"]
        authority = self.registration["productAuthority"]
        self.assertFalse(acceptance["sdfCodeIdentityMayBeCalledProspectivelyFrozen"])
        self.assertFalse(acceptance["completeProfileTransferMayBeClaimed"])
        self.assertFalse(authority["productionShaderMayChange"])
        self.assertFalse(authority["liquidGlassParityMayBeClaimed"])

    def test_frozen_implementation_hashes_match(self) -> None:
        for record in self.registration["frozenImplementation"]["files"]:
            self.assertEqual(sha256(REPOSITORY_ROOT / record["path"]), record["sha256"])
        shader = self.registration["frozenImplementation"]["productionShader"]
        self.assertEqual(
            shader["sha256"],
            "6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d",
        )
        local_shader = REPOSITORY_ROOT.parent / "shaders" / "frag.glsl"
        if local_shader.is_file():
            self.assertEqual(sha256(local_shader), shader["sha256"])


if __name__ == "__main__":
    unittest.main()
