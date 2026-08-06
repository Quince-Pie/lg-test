#!/usr/bin/env python3
"""Integrity checks for the 513 callback-transport retry."""

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_filter_map_bounds_513_callback_retry_preregistration.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerFilterMapBounds513CallbackRetryPreregistrationTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registration = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))

    def test_retry_is_prospective_transport_only(self) -> None:
        registration = self.registration
        self.assertEqual(
            registration[
                "prepareLayerFilterMapBounds513CallbackRetryPreregistrationSchemaVersion"
            ],
            1,
        )
        self.assertIn("callback-transport-only", registration["classification"])
        self.assertIsNone(registration["runtimeOutcomeFrozenBeforeDispatch"])

    def test_antecedent_contains_no_filter_evidence(self) -> None:
        antecedent = self.registration["antecedentFailure"]
        self.assertEqual(antecedent["runID"], 31071398653)
        self.assertTrue(antecedent["geometryGuardRebound"])
        self.assertFalse(antecedent["callbackTransportRepaired"])
        self.assertEqual(antecedent["filterInstructionStateCount"], 0)
        self.assertIsNone(antecedent["appleArithmeticOutcome"])
        self.assertEqual(
            sha256(REPOSITORY_ROOT / antecedent["path"]), antecedent["sha256"]
        )

    def test_all_callbacks_are_exposed_without_capture_changes(self) -> None:
        delta = self.registration["transportDelta"]
        self.assertEqual(len(delta["topLevelCallbacks"]), 6)
        for key in (
            "geometryAdapterChanged",
            "captureSelectorChanged",
            "breakpointChanged",
            "memoryReadChanged",
            "instructionTraceChanged",
            "validatorSemanticChecksChanged",
            "acceptanceChanged",
        ):
            self.assertFalse(delta[key], key)

    def test_retry_cannot_claim_parity(self) -> None:
        acceptance = self.registration["acceptance"]
        self.assertTrue(acceptance["filterReturnMustMatchIndependentProducerBitForBit"])
        self.assertFalse(acceptance["unchangedBlindRepeatMayBeClaimed"])
        self.assertFalse(acceptance["allCropHoldoutsMayBeClaimed"])
        self.assertFalse(acceptance["productionShaderMayChange"])
        self.assertFalse(acceptance["liquidGlassParityMayBeClaimed"])

    def test_frozen_hashes_match(self) -> None:
        for record in self.registration["frozenImplementation"]["files"]:
            self.assertEqual(sha256(REPOSITORY_ROOT / record["path"]), record["sha256"])
        shader = self.registration["frozenImplementation"]["productionShader"]
        self.assertFalse(shader["changed"])
        local_shader = REPOSITORY_ROOT.parent / "shaders" / "frag.glsl"
        if local_shader.is_file():
            self.assertEqual(sha256(local_shader), shader["sha256"])


if __name__ == "__main__":
    unittest.main()
