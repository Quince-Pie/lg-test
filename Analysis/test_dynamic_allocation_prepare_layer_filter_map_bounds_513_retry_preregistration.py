#!/usr/bin/env python3
"""Integrity checks for the geometry-only 513 retry."""

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_filter_map_bounds_513_retry_preregistration.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerFilterMapBounds513RetryPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registration = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))

    def test_retry_has_no_runtime_outcome(self) -> None:
        registration = self.registration
        self.assertEqual(
            registration[
                "prepareLayerFilterMapBounds513RetryPreregistrationSchemaVersion"
            ],
            1,
        )
        self.assertIn("transport-only retry", registration["classification"])
        self.assertIsNone(registration["runtimeOutcomeFrozenBeforeDispatch"])

    def test_antecedent_is_an_exact_null_result(self) -> None:
        antecedent = self.registration["antecedentFailure"]
        self.assertEqual(antecedent["runID"], 31070965886)
        self.assertEqual(antecedent["filterInstructionStateCount"], 0)
        self.assertIsNone(antecedent["appleArithmeticOutcome"])
        self.assertEqual(
            sha256(REPOSITORY_ROOT / antecedent["path"]), antecedent["sha256"]
        )

    def test_only_geometry_transport_changes(self) -> None:
        delta = self.registration["transportDelta"]
        for key in (
            "captureSelectorChanged",
            "breakpointChanged",
            "memoryReadChanged",
            "instructionTraceChanged",
            "validatorSemanticChecksChanged",
            "acceptanceChanged",
        ):
            self.assertFalse(delta[key], key)

    def test_retry_cannot_claim_general_parity(self) -> None:
        acceptance = self.registration["acceptance"]
        self.assertTrue(acceptance["zeroCaptureFailuresRequired"])
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
