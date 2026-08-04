#!/usr/bin/env python3
"""Tests for the preregistered Apple crop-writer operand trace."""

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
PREREGISTRATION = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_capture_backdrop_writer_operands_preregistration.json"
    ).read_text(encoding="utf-8")
)
OPENED_RESULT = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_capture_backdrop_writer_trace_preconvergence_result.json"
    ).read_text(encoding="utf-8")
)


class CaptureBackdropWriterOperandsPreregistrationTests(unittest.TestCase):
    def test_opened_failure_and_useful_writer_sites_are_both_retained(self):
        opened = PREREGISTRATION["openedInput"]
        aggregate = OPENED_RESULT["rawTraceAggregate"]
        sites = OPENED_RESULT["openedWriterSites"]
        self.assertEqual(opened["runID"], 30780736839)
        self.assertEqual(opened["workflowConclusion"], "failure")
        self.assertEqual(opened["writerTraceValidatorOutcome"], "failure")
        self.assertTrue(opened["captureTargetExitedNormally"])
        self.assertEqual(aggregate["eventCount"], 24)
        self.assertEqual(aggregate["changedWatchedByteEventCount"], 19)
        self.assertEqual(aggregate["unchangedWatchedByteEventCount"], 5)
        self.assertEqual(aggregate["prepareLayerEventCount"], 9)
        self.assertEqual(aggregate["prepareLayerEventWindowContainsStopPCCount"], 0)
        self.assertEqual(sites["symbolByteCount"], 40128)
        self.assertFalse(
            OPENED_RESULT["nextEvidenceBoundary"]["publicCropConstructionRuleRecovered"]
        )

    def test_prepare_layer_sites_are_exact_prospective_targets(self):
        contract = PREREGISTRATION["traceContract"]
        self.assertEqual(
            contract["expectedChangedPrepareLayerOffsets"],
            {
                "sourceSelectedRectI32": [21260, 21264],
                "ownerSelectedRectF64": [19992],
                "ownerRegion248Handle": [16112],
                "layerStateSelectedRectI32": [21956],
            },
        )
        self.assertEqual(contract["rawTraceSchemaVersion"], 4)
        self.assertEqual(contract["sealedValidatorSchemaVersion"], 3)
        self.assertEqual(contract["maximumTotalEventCount"], 24)
        self.assertEqual(contract["pcCenteredCodeWindowByteCount"], 4096)
        self.assertEqual(contract["pcCenteredCodeWindowBacktrack"], 2048)
        self.assertEqual(contract["generalRegisterCount"], 34)
        self.assertEqual(contract["simdRegisterCount"], 34)

    def test_falsified_assumptions_are_replaced_without_changing_apple_input(self):
        delta = PREREGISTRATION["frozenDelta"]
        capture = PREREGISTRATION["capture"]
        self.assertTrue(delta["unchangedByteHardwareStopsRejectedBefore"])
        self.assertTrue(delta["unchangedByteHardwareStopsRetainedAfter"])
        self.assertTrue(delta["registerOperandCaptureAdded"])
        self.assertTrue(delta["stackOperandCaptureAdded"])
        self.assertTrue(delta["objectOperandCaptureAdded"])
        self.assertTrue(delta["boundedRegisterPointerProbesAdded"])
        self.assertTrue(delta["openedPrepareLayerSiteGateAdded"])
        self.assertFalse(delta["captureBackdropCodeGateChanged"])
        self.assertFalse(delta["lateCandidateRuleChanged"])
        self.assertFalse(delta["watchpointAddressesOrSizesChanged"])
        self.assertFalse(delta["eventCountBoundsChanged"])
        self.assertFalse(delta["AppleCaptureMatrixChanged"])
        self.assertFalse(delta["workflowChanged"])
        self.assertFalse(delta["productionShaderChanged"])
        self.assertEqual(
            capture["workflowInput"]["capture_mode"], "allocation-path-isolation"
        )
        self.assertEqual(capture["sampleCount"], 33)

    def test_preregistered_implementation_hashes_match_current_files(self):
        frozen = PREREGISTRATION["frozenImplementation"]
        historical = {
            "lldbTraceHarnessSHA256": (
                "077427cf687849f87bc082ce81714a58af75e434777b09438698adea98b13264"
            ),
            "lldbTraceHarnessSourceTestSHA256": (
                "5a5106aeab58063e6ef059811d45f9f174c674c1998f461e1c5c28508a35f0c7"
            ),
            "sealedTraceValidatorSHA256": (
                "32fbf6f9a66018127a60115b86fc6d159cf1a5d96915bffff8484463bff80fef"
            ),
            "sealedTraceValidatorTestSHA256": (
                "fba029c002321a59870f36228894d55302d048802afa7488d39aaf738e888ada"
            ),
            "registrationTestSHA256": (
                "2f7a7f08ebf34b4a0cc7dd630aaadc7559263f6ca924b36d756e414b23f9efb1"
            ),
        }
        for name, digest in historical.items():
            with self.subTest(name=name):
                self.assertEqual(frozen[name], digest)
        files = {
            "openedResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_capture_backdrop_writer_trace_preconvergence_result.json",
            "workflowSHA256": REPOSITORY_ROOT
            / ".github/workflows/transition-introspect.yml",
            "developmentFlakeSHA256": REPOSITORY_ROOT / "flake.nix",
            "productionShaderSHA256": REPOSITORY_ROOT.parent / "shaders/frag.glsl",
        }
        for name, path in files.items():
            with self.subTest(name=name):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(), frozen[name]
                )

    def test_crop_law_and_product_parity_remain_unclaimed(self):
        unclaimed = PREREGISTRATION["notClaimed"]
        self.assertIn(
            "that the public crop-construction rule is recovered",
            unclaimed,
        )
        self.assertIn(
            "that Walle may change its production shader",
            unclaimed,
        )
        self.assertIn(
            "that Apple Liquid Glass parity has been achieved",
            unclaimed,
        )


if __name__ == "__main__":
    unittest.main()
