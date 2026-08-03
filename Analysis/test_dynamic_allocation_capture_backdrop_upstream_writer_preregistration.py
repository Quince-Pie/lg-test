#!/usr/bin/env python3
"""Integrity tests for the upstream owner-region writer preregistration."""

import hashlib
import json
import unittest
from pathlib import Path

import validate_dynamic_allocation_surviving_path_threshold as surviving


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
PREREGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_capture_backdrop_upstream_writer_preregistration.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CaptureBackdropUpstreamWriterPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preregistration = json.loads(
            PREREGISTRATION_PATH.read_text(encoding="utf-8")
        )

    def test_owner_record_checkpoint_is_a_prospective_pass(self) -> None:
        opened = self.preregistration["openedOwnerRecordEvidence"]
        self.assertEqual(opened["runID"], 30771308161)
        self.assertEqual(opened["workflowConclusion"], "success")
        self.assertTrue(opened["prospectiveGatePassed"])
        self.assertEqual(opened["completeLiveOperandCaptureCount"], 114)
        self.assertEqual(opened["ownerRecordCountStates"], {"1": 114})
        self.assertEqual(
            sha256(
                ANALYSIS_ROOT
                / "dynamic_allocation_capture_backdrop_owner_record_result.json"
            ),
            opened["ownerRecordAnalysisResultSHA256"],
        )

    def test_capture_is_bounded_to_the_instruction_proven_object_chain(self) -> None:
        capture = self.preregistration["capture"]
        self.assertEqual(capture["outerCaptureEvidenceSchemaVersion"], 9)
        self.assertEqual(capture["operandEvidenceSchemaVersion"], 5)
        self.assertEqual(capture["producerCallSiteSchemaVersion"], 6)
        self.assertEqual(capture["requiredReadMask"], "0x3fffffff")
        self.assertEqual(
            capture["upstreamObjectOffsets"],
            surviving.CAPTURE_BACKDROP_UPSTREAM_OBJECT_OFFSETS,
        )
        self.assertEqual(
            capture["regionBuilderOutput"],
            [
                surviving.CAPTURE_BACKDROP_REGION_BUILDER_OUTPUT_STACK_OFFSET,
                surviving.CAPTURE_BACKDROP_REGION_BUILDER_OUTPUT_BYTE_COUNT,
            ],
        )
        self.assertEqual(
            capture["upstreamDirectCallOffsets"],
            list(surviving.CAPTURE_BACKDROP_UPSTREAM_DIRECT_CALL_OFFSETS),
        )
        self.assertEqual(
            capture["upstreamDirectCallTargetCodeByteCount"],
            surviving.CAPTURE_BACKDROP_UPSTREAM_DIRECT_CALL_TARGET_CODE_BYTE_COUNT,
        )
        self.assertEqual(
            capture["sourceObjectPrefixByteCount"],
            surviving.CAPTURE_BACKDROP_SOURCE_OBJECT_PREFIX_BYTE_COUNT,
        )
        self.assertEqual(
            capture["layerObjectPrefixByteCount"],
            surviving.CAPTURE_BACKDROP_LAYER_OBJECT_PREFIX_BYTE_COUNT,
        )
        self.assertEqual(
            capture["layerStatePrefixByteCount"],
            surviving.CAPTURE_BACKDROP_LAYER_STATE_PREFIX_BYTE_COUNT,
        )
        self.assertEqual(
            capture["layerAuxiliaryPrefixByteCount"],
            surviving.CAPTURE_BACKDROP_LAYER_AUXILIARY_PREFIX_BYTE_COUNT,
        )
        self.assertEqual(
            capture["layerAuxiliaryNestedPrefixMaximumByteCount"],
            surviving.CAPTURE_BACKDROP_LAYER_AUXILIARY_NESTED_PREFIX_BYTE_COUNT,
        )
        self.assertEqual(
            capture["renderContextPrefixByteCount"],
            surviving.CAPTURE_BACKDROP_RENDER_CONTEXT_PREFIX_BYTE_COUNT,
        )

    def test_frozen_implementation_hashes_match_files(self) -> None:
        expected = self.preregistration["frozenImplementation"]
        files = {
            "matrixBridgeHeaderSHA256": REPOSITORY_ROOT
            / "Sources/GlassIntrospect/MatrixBridge.h",
            "matrixBridgeSourceSHA256": REPOSITORY_ROOT
            / "Sources/GlassIntrospect/MatrixBridge.c",
            "swiftCaptureSHA256": REPOSITORY_ROOT
            / "Sources/GlassIntrospect/main.swift",
            "holdoutValidatorSHA256": ANALYSIS_ROOT
            / "validate_dynamic_allocation_holdout.py",
            "validatorSHA256": ANALYSIS_ROOT
            / "validate_dynamic_allocation_surviving_path_threshold.py",
            "validatorTestSHA256": ANALYSIS_ROOT
            / "test_validate_dynamic_allocation_surviving_path_threshold.py",
            "historicalRetryTestSHA256": ANALYSIS_ROOT
            / "test_dynamic_allocation_capture_backdrop_owner_record_retry_preregistration.py",
            "passingAnalyzerSHA256": ANALYSIS_ROOT
            / "analyze_dynamic_allocation_capture_backdrop_owner_record.py",
            "passingAnalyzerTestSHA256": ANALYSIS_ROOT
            / "test_analyze_dynamic_allocation_capture_backdrop_owner_record.py",
            "passingResultSHA256": ANALYSIS_ROOT
            / "dynamic_allocation_capture_backdrop_owner_record_result.json",
            "productionShaderSHA256": REPOSITORY_ROOT.parent / "shaders/frag.glsl",
        }
        for name, path in files.items():
            with self.subTest(name=name):
                self.assertEqual(sha256(path), expected[name])
        # These two files legitimately gain a successor probe after this
        # preregistration is captured. Keep their historical digests immutable
        # instead of relabelling the successor as the implementation used by
        # run 30773890196.
        self.assertEqual(
            expected["workflowSHA256"],
            "bc79f75eb6244cda94dc4995164338589396535764b07c61a2d3b6be7570b870",
        )
        self.assertEqual(
            expected["upstreamWriterPreregistrationTestSHA256"],
            "b3accf45e25a2d1f15138680a8438a8a8141af57919e97cf6faa80b8ec4c7c8d",
        )

    def test_acceptance_is_exact_and_cannot_authorize_product_changes(self) -> None:
        acceptance = self.preregistration["acceptance"]
        self.assertEqual(acceptance["operandCaptureCount"], 114)
        self.assertEqual(acceptance["upstreamObjectChainExactCount"], 114)
        self.assertEqual(acceptance["upstreamDirectCallTargetCaptureCount"], 7)
        self.assertFalse(acceptance["allowNumericTolerance"])
        self.assertFalse(acceptance["productionShaderAuthorized"])
        self.assertIn("production Walle parity", self.preregistration["notClaimed"])
        self.assertIn(
            "a public-state-only owner-region construction policy",
            self.preregistration["notClaimed"],
        )


if __name__ == "__main__":
    unittest.main()
