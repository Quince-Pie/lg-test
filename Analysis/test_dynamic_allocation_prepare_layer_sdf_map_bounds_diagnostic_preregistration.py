#!/usr/bin/env python3
"""Integrity tests for the prospective SDF map-bounds diagnostic."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_sdf_map_bounds_diagnostic_preregistration.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerSDFMapBoundsDiagnosticPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registration = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))

    def test_discovery_run_is_prospective_and_output_blind(self) -> None:
        registration = self.registration
        self.assertEqual(
            registration[
                "prepareLayerSDFMapBoundsDiagnosticPreregistrationSchemaVersion"
            ],
            1,
        )
        self.assertIn("prospective", registration["classification"])
        self.assertIn("output-blind", registration["classification"])
        self.assertIsNone(registration["runtimeOutcomeFrozenBeforeDispatch"])

    def test_residual_is_recorded_without_overclaim(self) -> None:
        prior = self.registration["priorEvidence"]
        self.assertEqual(prior["retrospectiveRegularExactRectangleCount"], 124)
        self.assertEqual(prior["retrospectiveRegularRectangleCount"], 128)
        self.assertEqual(prior["retrospectiveRegularExactComponentCount"], 504)
        self.assertEqual(prior["retrospectiveRegularComponentCount"], 512)
        self.assertFalse(prior["retainedRoleSnapshotsContainExactMissingEntryY"])
        self.assertFalse(prior["completeProfileMatrixPassed"])
        self.assertFalse(prior["liquidGlassParityEstablished"])

    def test_selector_is_frozen_while_code_hash_is_discovery_output(self) -> None:
        diagnostic = self.registration["frozenDiagnostic"]
        self.assertEqual(diagnostic["dynamicDispatchOrdinal"], 2)
        self.assertEqual(diagnostic["sdfRelativeToPrepareLayer"], -56012)
        self.assertEqual(diagnostic["sdfSymbolByteCount"], 160)
        self.assertEqual(diagnostic["maximumOpaqueCalleeCount"], 64)
        self.assertIsNone(diagnostic["sdfCodeSHA256"])
        self.assertFalse(diagnostic["captureReadsCropOrOutputForSelection"])
        self.assertFalse(diagnostic["filterSelectorChanged"])
        self.assertFalse(diagnostic["filterInstructionCaptureChanged"])

    def test_acceptance_and_product_authority_stay_narrow(self) -> None:
        acceptance = self.registration["acceptance"]
        authority = self.registration["productAuthority"]
        self.assertTrue(acceptance["completeExecutedSDFInstructionChainRequired"])
        self.assertTrue(
            acceptance[
                "everyExecutedOpaqueCalleeMustRetainCompleteInternallyHashedSymbolBytes"
            ]
        )
        self.assertTrue(
            acceptance["syntheticOpaqueBoundaryMustMatchTraceEndpointsBitForBit"]
        )
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
