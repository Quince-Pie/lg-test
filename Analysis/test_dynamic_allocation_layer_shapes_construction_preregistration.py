#!/usr/bin/env python3
"""Integrity tests for the early LayerShapes construction preregistration."""

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
PREREGISTRATION = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_layer_shapes_construction_preregistration.json"
    ).read_text(encoding="utf-8")
)
OPENED_FAILURE = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_layer_shapes_merge_late_arm_result.json"
    ).read_text(encoding="utf-8")
)


class LayerShapesConstructionPreregistrationTests(unittest.TestCase):
    def test_failed_late_arm_result_and_opened_helper_are_the_antecedent(self):
        opened = PREREGISTRATION["openedEvidenceBoundary"]
        helper = OPENED_FAILURE["openedMergeHelper"]
        self.assertEqual(opened["runID"], 30950358261)
        self.assertEqual(opened["lateArmMergeCallSiteHitCount"], 0)
        self.assertEqual(opened["lateArmRawFailureCount"], 0)
        self.assertEqual(
            opened["unionHelperSymbolName"], helper["resolvedName"]
        )
        self.assertEqual(
            opened["unionHelperSymbolByteCount"], helper["symbolByteCount"]
        )
        self.assertEqual(
            opened["unionHelperSymbolSHA256"], helper["symbolCodeSHA256"]
        )
        self.assertFalse(opened["selectedSourcePreAndPostReplayAvailable"])

    def test_contract_arms_early_and_covers_both_exact_branch_sites(self):
        contract = PREREGISTRATION["traceContract"]
        self.assertEqual(contract["rawTraceSchemaVersion"], 1)
        self.assertEqual(contract["sealedValidatorSchemaVersion"], 1)
        self.assertEqual(contract["directCallOffset"], 0x32C0)
        self.assertEqual(contract["directReturnOffset"], 0x32C4)
        self.assertEqual(contract["alternateStoreOffset"], 0x33F0)
        self.assertEqual(contract["alternateAfterOffset"], 0x33F4)
        self.assertEqual(
            contract["alternateStoreRawLittleEndianHex"], "608614ad"
        )
        self.assertEqual(contract["layerShapesByteCount"], 32)
        self.assertEqual(contract["roleStateByteCount"], 2048)
        self.assertEqual(contract["maximumDirectRecordCount"], 64)
        self.assertEqual(contract["maximumAlternateRecordCount"], 96)
        self.assertEqual(contract["minimumSelectedDirectRecordCount"], 1)
        self.assertEqual(contract["minimumSelectedAlternateRecordCount"], 8)
        self.assertEqual(
            contract["minimumDistinctSelectedAlternateSourceCount"], 8
        )

    def test_acceptance_requires_exact_aliases_and_store_replay(self):
        acceptance = PREREGISTRATION["acceptance"]
        self.assertTrue(acceptance["armAtFirstPrepareLayerEntry"])
        self.assertTrue(acceptance["retrospectiveExactX28Classification"])
        self.assertTrue(acceptance["selectedDirectAggregateMustChange"])
        self.assertTrue(acceptance["alternateSIMDSourceMustEqualX19Plus1312"])
        self.assertTrue(acceptance["alternateAggregateAfterMustEqualSource"])
        self.assertTrue(acceptance["allPairsMustComplete"])
        self.assertTrue(acceptance["zeroTraceFailuresRequired"])

    def test_previous_successful_harnesses_and_product_shader_are_unchanged(self):
        delta = PREREGISTRATION["frozenDelta"]
        self.assertTrue(delta["separateAmendmentWorkflowAdded"])
        self.assertTrue(delta["separateAmendmentHarnessAdded"])
        self.assertTrue(delta["separateAmendmentValidatorAdded"])
        for name, changed in delta.items():
            if name.endswith("Changed"):
                with self.subTest(name=name):
                    self.assertFalse(changed)

    def test_preregistered_implementation_hashes_match_current_files(self):
        frozen = PREREGISTRATION["frozenImplementation"]
        files = {
            "openedLateArmResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_layer_shapes_merge_late_arm_result.json",
            "openedLateArmResultTestSHA256": ANALYSIS_ROOT
            / "test_dynamic_allocation_layer_shapes_merge_late_arm_result.py",
            "lldbConstructionHarnessSHA256": ANALYSIS_ROOT
            / "capture_layer_shapes_construction_trace_lldb.py",
            "lldbConstructionHarnessSourceTestSHA256": ANALYSIS_ROOT
            / "test_capture_layer_shapes_construction_trace_lldb_source.py",
            "sealedConstructionValidatorSHA256": ANALYSIS_ROOT
            / "validate_layer_shapes_construction_trace.py",
            "sealedConstructionValidatorTestSHA256": ANALYSIS_ROOT
            / "test_validate_layer_shapes_construction_trace.py",
            "workflowSHA256": REPOSITORY_ROOT
            / ".github/workflows/layer-shapes-construction-introspect.yml",
            "developmentFlakeSHA256": REPOSITORY_ROOT / "flake.nix",
            "registrationTestSHA256": ANALYSIS_ROOT
            / "test_dynamic_allocation_layer_shapes_construction_preregistration.py",
            "productionShaderSHA256": REPOSITORY_ROOT.parent
            / "shaders/frag.glsl",
        }
        for name, path in files.items():
            with self.subTest(name=name):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(), frozen[name]
                )

    def test_semantics_transfer_and_product_parity_remain_sealed(self):
        not_claimed = PREREGISTRATION["notClaimed"]
        self.assertIn(
            "that the alternate x19+1312 producer algorithm is known",
            not_claimed,
        )
        self.assertIn("that Walle may change its production shader", not_claimed)
        self.assertIn(
            "that Apple Liquid Glass parity has been achieved",
            not_claimed,
        )


if __name__ == "__main__":
    unittest.main()
