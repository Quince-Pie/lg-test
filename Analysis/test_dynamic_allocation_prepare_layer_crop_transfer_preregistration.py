#!/usr/bin/env python3
"""Integrity tests for the prospective crop-transfer registration."""

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
WORKSPACE_ROOT = REPOSITORY_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_crop_transfer_preregistration.json"
)
REGISTRATION = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerCropTransferPreregistrationTests(unittest.TestCase):
    def test_registration_is_prospective_and_has_no_observed_outcome(self):
        self.assertEqual(
            REGISTRATION["prepareLayerCropTransferPreregistrationSchemaVersion"],
            1,
        )
        self.assertIn("prospective", REGISTRATION["classification"])
        self.assertNotIn("result", REGISTRATION)
        self.assertNotIn("workflowConclusion", REGISTRATION)
        self.assertFalse(
            REGISTRATION["acceptance"]["generalCropPolicyMayBeClaimedByThisCaptureAlone"]
        )
        self.assertFalse(
            REGISTRATION["acceptance"]["productionShaderMayChange"]
        )
        self.assertFalse(
            REGISTRATION["acceptance"]["liquidGlassParityMayBeClaimed"]
        )

    def test_discovery_matrix_is_dense_and_phase_discriminating(self):
        matrix = REGISTRATION["frozenDiscoveryMatrix"]
        self.assertEqual(matrix["geometryCount"], 8)
        self.assertEqual(matrix["normalReplayRecordCountPerGeometry"], 32)
        self.assertEqual(matrix["prospectivePrivateRecordCount"], 256)
        self.assertTrue(matrix["denseAllocationEvidence"])
        self.assertEqual(
            set(matrix["geometries"]),
            {
                "circle-640-center",
                "circle-640-integer",
                "circle-640-phase-0500-even",
                "circle-640-phase-0500-signed",
                "circle-256-center",
                "circle-512-offset",
                "circle-640-fractional",
                "circle-1536-center",
            },
        )

    def test_selection_is_crop_independent_and_fails_closed(self):
        design = REGISTRATION["captureDesign"]
        acceptance = REGISTRATION["acceptance"]
        self.assertIn("Crop and aggregate bytes are not read", design["selection"])
        self.assertIn("missing or duplicate", design["join"])
        self.assertFalse(design["hardwareWatchpoints"])
        self.assertFalse(design["instructionStepping"])
        self.assertFalse(design["productionShaderChanged"])
        self.assertTrue(acceptance["cropIndependentSelectionRequired"])
        self.assertTrue(acceptance["oneQualifiedRecordPerNormalReplayRequired"])
        self.assertTrue(acceptance["zeroTraceFailuresRequired"])
        self.assertTrue(acceptance["zeroDiscardedQualifiedRecordsRequired"])
        self.assertTrue(acceptance["zeroUnretainedRejectionsRequired"])

    def test_frozen_implementation_hashes_match(self):
        frozen = REGISTRATION["frozenImplementation"]
        pairs = (
            (frozen["captureHarness"], frozen["captureHarnessSHA256"]),
            (frozen["validator"], frozen["validatorSHA256"]),
            (frozen["captureHarnessTest"], frozen["captureHarnessTestSHA256"]),
            (frozen["validatorTest"], frozen["validatorTestSHA256"]),
            (frozen["workflow"], frozen["workflowSHA256"]),
        )
        for relative, expected in pairs:
            self.assertEqual(sha256(REPOSITORY_ROOT / relative), expected)
        self.assertEqual(
            sha256(WORKSPACE_ROOT / "shaders" / "frag.glsl"),
            frozen["productionShaderSHA256"],
        )
        self.assertEqual(
            sha256(WORKSPACE_ROOT / "flake.nix"),
            frozen["developmentFlakeSHA256"],
        )

    def test_capture_program_is_unchanged_and_fully_hashed(self):
        records = REGISTRATION["frozenCaptureProgram"]
        self.assertEqual(len(records), 7)
        for record in records:
            self.assertEqual(
                sha256(REPOSITORY_ROOT / record["path"]),
                record["sha256"],
            )

    def test_opened_semantic_results_are_pinned(self):
        opened = REGISTRATION["openedEvidenceBoundary"]
        self.assertEqual(
            sha256(
                ANALYSIS_ROOT
                / "dynamic_allocation_prepare_layer_crop_writer_semantics_result.json"
            ),
            opened["cropWriterSemanticsResultSHA256"],
        )
        self.assertEqual(
            sha256(
                ANALYSIS_ROOT
                / "dynamic_allocation_prepare_layer_dod_semantics_result.json"
            ),
            opened["dodSemanticsResultSHA256"],
        )

    def test_diagnostic_hypotheses_are_explicitly_not_acceptance(self):
        hypotheses = REGISTRATION["frozenDiagnosticHypotheses"]
        self.assertIn("not accepted prospectively", hypotheses["baselineOnly"]["status"])
        self.assertIn("diagnostic candidates only", hypotheses["genericComposition"]["status"])
        self.assertFalse(
            REGISTRATION["acceptance"]["formulaFitRequiredForCaptureIntegrity"]
        )


if __name__ == "__main__":
    unittest.main()
