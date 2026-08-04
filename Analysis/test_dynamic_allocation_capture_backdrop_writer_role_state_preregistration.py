#!/usr/bin/env python3
"""Tests for the preregistered Apple prepare_layer role-state trace."""

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
PREREGISTRATION = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_capture_backdrop_writer_role_state_preregistration.json"
    ).read_text(encoding="utf-8")
)
OPENED_RESULT = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_capture_backdrop_writer_operands_result.json"
    ).read_text(encoding="utf-8")
)


class CaptureBackdropWriterRoleStatePreregistrationTests(unittest.TestCase):
    def test_opened_success_and_measured_operand_gap_are_retained(self):
        opened = PREREGISTRATION["openedInput"]
        boundary = PREREGISTRATION["openedInstructionBoundary"]
        result_boundary = OPENED_RESULT["operandBoundary"]
        self.assertEqual(opened["runID"], 30881161586)
        self.assertEqual(opened["workflowConclusion"], "success")
        self.assertEqual(opened["writerTraceValidatorOutcome"], "success")
        self.assertTrue(opened["captureTargetExitedNormally"])
        self.assertEqual(boundary["workingRectangleOffset"], 624)
        self.assertEqual(boundary["floatingOriginOffset"], 752)
        self.assertEqual(boundary["floatingSizeOffset"], 768)
        self.assertEqual(boundary["helperScratchRectangleOffset"], 1568)
        self.assertEqual(
            boundary["priorGenericPointerProbeForwardCoverage"],
            result_boundary["genericForwardCoverageFromRegisterValue"],
        )
        self.assertFalse(boundary["publicCropConstructionRuleRecovered"])

    def test_role_capture_covers_every_opened_x19_range(self):
        contract = PREREGISTRATION["traceContract"]
        boundary = PREREGISTRATION["openedInstructionBoundary"]
        self.assertEqual(contract["rawTraceSchemaVersion"], 5)
        self.assertEqual(contract["sealedValidatorSchemaVersion"], 4)
        self.assertEqual(contract["prepareLayerRoleSnapshotByteCount"], 2048)
        self.assertEqual(contract["requiredSuccessfulRoleRegister"], "x19")
        self.assertEqual(
            contract["prepareLayerRoleRegisterNames"],
            [f"x{index}" for index in range(19, 29)],
        )
        for name in (
            "workingRectangleOffset",
            "floatingOriginOffset",
            "floatingSizeOffset",
            "helperScratchRectangleOffset",
        ):
            with self.subTest(name=name):
                self.assertLess(boundary[name] + 32, 2048)

    def test_successful_capture_contract_is_changed_only_by_role_state(self):
        delta = PREREGISTRATION["frozenDelta"]
        self.assertTrue(delta["prepareLayerRoleSnapshotsAdded"])
        self.assertTrue(delta["requiredX19RoleSnapshotGateAdded"])
        for name, changed in delta.items():
            if name.endswith("Changed"):
                with self.subTest(name=name):
                    self.assertFalse(changed)
        self.assertEqual(
            PREREGISTRATION["capture"]["workflowInput"]["capture_mode"],
            "allocation-path-isolation",
        )
        self.assertEqual(PREREGISTRATION["capture"]["sampleCount"], 33)

    def test_preregistered_implementation_hashes_match_current_files(self):
        frozen = PREREGISTRATION["frozenImplementation"]
        files = {
            "openedResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_capture_backdrop_writer_operands_result.json",
            "lldbTraceHarnessSHA256": ANALYSIS_ROOT
            / "capture_backdrop_writer_trace_lldb.py",
            "lldbTraceHarnessSourceTestSHA256": ANALYSIS_ROOT
            / "test_capture_backdrop_writer_trace_lldb_source.py",
            "sealedTraceValidatorSHA256": ANALYSIS_ROOT
            / "validate_capture_backdrop_writer_trace.py",
            "sealedTraceValidatorTestSHA256": ANALYSIS_ROOT
            / "test_validate_capture_backdrop_writer_trace.py",
            "openedResultTestSHA256": ANALYSIS_ROOT
            / "test_dynamic_allocation_capture_backdrop_writer_operands_result.py",
            "workflowSHA256": REPOSITORY_ROOT
            / ".github/workflows/transition-introspect.yml",
            "developmentFlakeSHA256": REPOSITORY_ROOT / "flake.nix",
            "registrationTestSHA256": ANALYSIS_ROOT
            / "test_dynamic_allocation_capture_backdrop_writer_role_state_preregistration.py",
            "productionShaderSHA256": REPOSITORY_ROOT.parent / "shaders/frag.glsl",
        }
        for name, path in files.items():
            with self.subTest(name=name):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(), frozen[name]
                )

    def test_public_policy_and_product_parity_remain_unclaimed(self):
        unclaimed = PREREGISTRATION["notClaimed"]
        self.assertIn(
            "that the complete public crop-construction rule is recovered",
            unclaimed,
        )
        self.assertIn("that Walle may change its production shader", unclaimed)
        self.assertIn(
            "that Apple Liquid Glass parity has been achieved",
            unclaimed,
        )


if __name__ == "__main__":
    unittest.main()
