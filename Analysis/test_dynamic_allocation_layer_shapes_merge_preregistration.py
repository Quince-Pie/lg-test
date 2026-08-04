#!/usr/bin/env python3
"""Tests for the preregistered selected-source LayerShapes merge capture."""

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
PREREGISTRATION = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_layer_shapes_merge_preregistration.json"
    ).read_text(encoding="utf-8")
)
OPENED_RESULT = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_capture_backdrop_writer_role_state_result.json"
    ).read_text(encoding="utf-8")
)


class LayerShapesMergePreregistrationTests(unittest.TestCase):
    def test_opened_three_sample_identity_and_remaining_gap_are_retained(self):
        opened = PREREGISTRATION["openedEvidenceBoundary"]
        result_join = OPENED_RESULT["openedPublicPrivateJoin"]["threeSampleRule"]
        self.assertEqual(opened["openedPublicPrivateSampleIndices"], [2, 3, 5])
        self.assertEqual(
            opened["openedBinary64AggregateMatchCount"],
            result_join["binary64AggregateMatchCount"],
        )
        self.assertEqual(opened["directMergeCallOffset"], 0x32C0)
        self.assertEqual(opened["directMergeCallRawLittleEndianHex"], "a8f0ff97")
        self.assertEqual(opened["directMergeTargetRelativeToPrepareLayer"], -0xAA0)
        self.assertFalse(opened["helperTargetCodeCaptured"])
        self.assertFalse(opened["helperPreAndPostOperandsCaptured"])
        self.assertFalse(opened["completePublicCropConstructionRuleRecovered"])

    def test_capture_contract_is_bounded_and_requires_diverse_complete_pairs(self):
        contract = PREREGISTRATION["traceContract"]
        self.assertEqual(contract["rawTraceSchemaVersion"], 1)
        self.assertEqual(contract["sealedValidatorSchemaVersion"], 1)
        self.assertEqual(contract["layerShapesByteCount"], 32)
        self.assertEqual(contract["roleStateByteCount"], 2048)
        self.assertEqual(contract["sourceObjectByteCount"], 384)
        self.assertEqual(contract["minimumCompleteRecordCount"], 16)
        self.assertEqual(contract["maximumCompleteRecordCount"], 64)
        self.assertEqual(contract["minimumDistinctInputPairCount"], 8)
        self.assertEqual(contract["maximumMergeCallSiteHitCount"], 4096)

    def test_successful_schema5_contract_and_product_shader_are_unchanged(self):
        delta = PREREGISTRATION["frozenDelta"]
        self.assertTrue(delta["separateWorkflowAdded"])
        self.assertTrue(delta["separateLLDBHarnessAdded"])
        self.assertTrue(delta["separateSealedValidatorAdded"])
        for name, changed in delta.items():
            if name.endswith("Changed"):
                with self.subTest(name=name):
                    self.assertFalse(changed)
        self.assertEqual(PREREGISTRATION["capture"]["sampleCount"], 33)
        self.assertEqual(
            PREREGISTRATION["capture"]["geometry"], "circle-640-center"
        )

    def test_preregistered_implementation_hashes_match_current_files(self):
        frozen = PREREGISTRATION["frozenImplementation"]
        files = {
            "openedResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_capture_backdrop_writer_role_state_result.json",
            "openedResultTestSHA256": ANALYSIS_ROOT
            / "test_dynamic_allocation_capture_backdrop_writer_role_state_result.py",
            "lldbMergeHarnessSHA256": ANALYSIS_ROOT
            / "capture_layer_shapes_merge_trace_lldb.py",
            "lldbMergeHarnessSourceTestSHA256": ANALYSIS_ROOT
            / "test_capture_layer_shapes_merge_trace_lldb_source.py",
            "sealedMergeValidatorSHA256": ANALYSIS_ROOT
            / "validate_layer_shapes_merge_trace.py",
            "sealedMergeValidatorTestSHA256": ANALYSIS_ROOT
            / "test_validate_layer_shapes_merge_trace.py",
            "workflowSHA256": REPOSITORY_ROOT
            / ".github/workflows/layer-shapes-merge-introspect.yml",
            "developmentFlakeSHA256": REPOSITORY_ROOT / "flake.nix",
            "registrationTestSHA256": ANALYSIS_ROOT
            / "test_dynamic_allocation_layer_shapes_merge_preregistration.py",
            "productionShaderSHA256": REPOSITORY_ROOT.parent
            / "shaders/frag.glsl",
        }
        for name, path in files.items():
            with self.subTest(name=name):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(), frozen[name]
                )

    def test_helper_semantics_and_product_parity_remain_sealed(self):
        not_claimed = PREREGISTRATION["notClaimed"]
        self.assertIn(
            "that the unseen helper-code SHA-256 or symbol name is known before capture",
            not_claimed,
        )
        self.assertIn("that Walle may change its production shader", not_claimed)
        self.assertIn(
            "that Apple Liquid Glass parity has been achieved",
            not_claimed,
        )


if __name__ == "__main__":
    unittest.main()
