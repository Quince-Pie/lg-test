#!/usr/bin/env python3
"""Integrity checks for the small-geometry helper transport retry."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_small_geometry_helper_code_callback_retry_preregistration.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class SmallGeometryHelperCodeCallbackRetryPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registration = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))

    def test_retry_is_prospective_output_blind_and_transport_only(self) -> None:
        registration = self.registration
        self.assertEqual(
            registration[
                "prepareLayerSmallGeometryHelperCodeCallbackRetryPreregistrationSchemaVersion"
            ],
            1,
        )
        for token in ("prospective", "output-blind", "transport-only"):
            self.assertIn(token, registration["classification"])
        self.assertIsNone(registration["runtimeOutcomeFrozenBeforeDispatch"])

    def test_failed_run_is_preserved_without_acceptance(self) -> None:
        antecedent = self.registration["antecedentFailure"]
        self.assertEqual(antecedent["runID"], 31086167113)
        self.assertTrue(antecedent["traceWriterRouteFailed"])
        self.assertFalse(antecedent["inheritedExecutionTraceCompleted"])
        self.assertFalse(antecedent["validationPresent"])
        self.assertFalse(antecedent["helperCodeOpeningAccepted"])
        self.assertEqual(
            sha256(REPOSITORY_ROOT / antecedent["path"]),
            antecedent["sha256"],
        )

    def test_only_transport_changes(self) -> None:
        correction = self.registration["frozenCorrection"]
        self.assertTrue(correction["writerReboundBeforeFrozenInitialization"])
        self.assertEqual(len(correction["callbacksForwarded"]), 6)
        self.assertTrue(correction["dynamicCallbacksReboundAfterPrepareEntry"])
        for field in (
            "newStaticTargetAdded",
            "newBreakpointAdded",
            "newMemoryReadAdded",
            "newSteppingRuleAdded",
            "selectorChanged",
            "captureRuleChanged",
            "validatorChanged",
            "timelineChanged",
            "cropOrOutputValuesReadForSelection",
        ):
            self.assertFalse(correction[field], field)

    def test_failed_hashes_are_disclosed_but_not_accepted(self) -> None:
        evidence = self.registration["retainedButUnacceptedFailureEvidence"]
        self.assertFalse(evidence["codeHashesAcceptedAsRetryExpectations"])
        for target in evidence["targets"]:
            self.assertEqual(len(target["observedCodeSHA256"]), 64)
            self.assertIsNone(target["retryExpectedCodeSHA256"])
        for target in self.registration["unchangedCapture"]["targets"]:
            self.assertIsNone(target["expectedCodeSHA256"])

    def test_product_authority_remains_closed(self) -> None:
        acceptance = self.registration["acceptance"]
        authority = self.registration["productAuthority"]
        self.assertFalse(acceptance["helperCodeHashesMayBeAcceptedProspectively"])
        self.assertFalse(acceptance["gaussianGeneralSemanticsMayBeClaimed"])
        self.assertFalse(acceptance["regularGeometryTransferMayBeClaimed"])
        self.assertFalse(authority["productionShaderMayChange"])
        self.assertFalse(authority["liquidGlassParityMayBeClaimed"])

    def test_frozen_implementation_hashes_match(self) -> None:
        for record in self.registration["frozenImplementation"]["files"]:
            self.assertEqual(sha256(REPOSITORY_ROOT / record["path"]), record["sha256"])
        shader = self.registration["frozenImplementation"]["productionShader"]
        local_shader = REPOSITORY_ROOT.parent / "shaders" / "frag.glsl"
        self.assertFalse(shader["changed"])
        if local_shader.is_file():
            self.assertEqual(sha256(local_shader), shader["sha256"])


if __name__ == "__main__":
    unittest.main()
