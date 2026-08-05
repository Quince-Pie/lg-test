#!/usr/bin/env python3
"""Integrity tests for the frame-correlated writer preregistration."""

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
PREREGISTRATION = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_prepare_layer_frame_writer_preregistration.json"
    ).read_text(encoding="utf-8")
)
OPENED_RESULT = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_prepare_layer_live_writer_x28_timing_result.json"
    ).read_text(encoding="utf-8")
)


class PrepareLayerFrameWriterPreregistrationTests(unittest.TestCase):
    def test_failed_live_writer_run_is_the_exact_antecedent(self):
        opened = PREREGISTRATION["openedEvidenceBoundary"]
        self.assertEqual(opened["runID"], 30960697537)
        self.assertEqual(opened["jobID"], 92163765090)
        self.assertEqual(
            opened["headSHA"],
            "65bc6a5d56f80fa65032a0b68524039c4e9bf5cc",
        )
        self.assertEqual(opened["workflowConclusion"], "failure")
        self.assertTrue(opened["captureTargetExitedNormally"])
        self.assertEqual(opened["ignoredPrepareFrameSeenCount"], 196)
        self.assertEqual(opened["qualifiedWatchpointHitCount"], 0)
        self.assertFalse(opened["selectedWriterDependencySliceCaptured"])
        self.assertEqual(
            opened["runID"], OPENED_RESULT["run"]["runID"]
        )

    def test_contract_freezes_exact_writer_sites_and_frame_identity(self):
        contract = PREREGISTRATION["traceContract"]
        self.assertEqual(contract["prepareLayerSymbolByteCount"], 40128)
        self.assertEqual(contract["liveSelectionMarkerOffset"], 0x3EF0)
        self.assertEqual(contract["aggregateOffset"], 656)
        self.assertEqual(contract["maximumRecordCountPerWriterSite"], 512)
        self.assertEqual(
            contract["frameIdentity"], ["threadID", "x19", "x29"]
        )
        sites = {item["name"]: item for item in contract["writerSites"]}
        self.assertEqual(len(sites), 9)
        self.assertEqual(sites["unionBoundsStoreAfter"]["relativeToPrepareLayer"], -2588)
        self.assertEqual(sites["zeroInitializationAfter"]["relativeToPrepareLayer"], 0xB60)
        self.assertTrue(sites["zeroInitializationAfter"]["epochStart"])
        self.assertEqual(sites["rangeClampStoreAfter"]["relativeToPrepareLayer"], 0x3974)

    def test_acceptance_rejects_every_known_false_positive(self):
        acceptance = PREREGISTRATION["acceptance"]
        for name in (
            "completePrepareLayerCodeRequired",
            "writerSitesMustBeInstalledBeforeFirstResume",
            "longLivedHardwareWatchpointForbidden",
            "nearestExactPrepareFrameRequired",
            "exactThreadRoleAndFramePointerCorrelationRequired",
            "latestZeroEpochBoundaryRequired",
            "allSameFrameSuffixEventsRequired",
            "lastAggregateMustBitMatchMarker",
            "minimumTwoDistinctSelectedAggregatesRequired",
            "minimumOneChangingSelectedTransitionRequired",
            "zeroDiscardedRecordsRequired",
            "zeroTraceFailuresRequired",
            "existingPathIsolationGateMustPass",
            "existingInputClampGateMustPass",
            "targetMustExitNormally",
        ):
            with self.subTest(name=name):
                self.assertTrue(acceptance[name])
        self.assertFalse(acceptance["writerSemanticsMayBeClaimed"])
        self.assertFalse(acceptance["productionShaderMayChange"])

    def test_frozen_implementation_hashes_match_current_files(self):
        frozen = PREREGISTRATION["frozenImplementation"]
        files = {
            "openedTimingResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_prepare_layer_live_writer_x28_timing_result.json",
            "openedTimingResultTestSHA256": ANALYSIS_ROOT
            / "test_dynamic_allocation_prepare_layer_live_writer_x28_timing_result.py",
            "lldbFrameWriterHarnessSHA256": ANALYSIS_ROOT
            / "capture_prepare_layer_frame_correlated_writer_trace_lldb.py",
            "lldbFullPathBaseHarnessSHA256": ANALYSIS_ROOT
            / "capture_prepare_layer_full_path_trace_lldb.py",
            "lldbFrameWriterHarnessSourceTestSHA256": ANALYSIS_ROOT
            / "test_capture_prepare_layer_frame_correlated_writer_trace_lldb_source.py",
            "sealedFrameWriterValidatorSHA256": ANALYSIS_ROOT
            / "validate_prepare_layer_frame_correlated_writer_trace.py",
            "sealedFrameWriterValidatorTestSHA256": ANALYSIS_ROOT
            / "test_validate_prepare_layer_frame_correlated_writer_trace.py",
            "workflowSHA256": REPOSITORY_ROOT
            / ".github/workflows/prepare-layer-frame-writer-introspect.yml",
            "developmentFlakeSHA256": REPOSITORY_ROOT / "flake.nix",
            "registrationTestSHA256": ANALYSIS_ROOT
            / "test_dynamic_allocation_prepare_layer_frame_writer_preregistration.py",
            "productionShaderSHA256": REPOSITORY_ROOT.parent
            / "shaders/frag.glsl",
        }
        for name, path in files.items():
            with self.subTest(name=name):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(), frozen[name]
                )

    def test_frozen_capture_program_and_validator_dependencies_match(self):
        for section in ("frozenCaptureProgram", "frozenValidatorDependencies"):
            for item in PREREGISTRATION[section]:
                with self.subTest(section=section, path=item["path"]):
                    path = REPOSITORY_ROOT / item["path"]
                    self.assertEqual(
                        hashlib.sha256(path.read_bytes()).hexdigest(),
                        item["sha256"],
                    )

    def test_existing_evidence_and_product_files_are_unchanged_by_probe(self):
        delta = PREREGISTRATION["frozenDelta"]
        self.assertTrue(delta["separateFrameWriterWorkflowAdded"])
        self.assertTrue(delta["separateFrameWriterHarnessAdded"])
        self.assertTrue(delta["separateFrameWriterValidatorAdded"])
        self.assertTrue(delta["openedTimingResultAdded"])
        for name, changed in delta.items():
            if name.endswith("Changed"):
                with self.subTest(name=name):
                    self.assertFalse(changed)

    def test_parity_shader_authority_and_run_count_remain_unclaimed(self):
        nonclaims = PREREGISTRATION["notClaimed"]
        self.assertIn(
            "that the selected writer dependency slice is already captured",
            nonclaims,
        )
        self.assertIn(
            "that the complete public crop-construction rule is recovered",
            nonclaims,
        )
        self.assertIn("that Walle may change its production shader", nonclaims)
        self.assertIn("that Apple Liquid Glass parity has been achieved", nonclaims)
        self.assertIn(
            "that a fixed number of later CI runs will be sufficient",
            nonclaims,
        )


if __name__ == "__main__":
    unittest.main()
