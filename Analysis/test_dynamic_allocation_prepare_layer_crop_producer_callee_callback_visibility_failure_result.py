#!/usr/bin/env python3
"""Integrity checks for the producer-callee callback transport failure."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
RESULT_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_crop_producer_callee_callback_visibility_failure_result.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerCropProducerCalleeCallbackFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_run_and_raw_failure_are_frozen(self) -> None:
        run = self.result["run"]
        evidence = self.result["rawEvidence"]
        self.assertEqual(run["runID"], 31068004888)
        self.assertEqual(run["headSHA"], "f92d6dd734a85e4ee2443ecaa83c28152aa3e91f")
        self.assertEqual(run["workflowConclusion"], "failure")
        self.assertEqual(evidence["captureCommandExitStatus"], 0)
        self.assertEqual(evidence["validatorCommandExitStatus"], 1)
        self.assertIn(
            "crop transfer trace did not remain active", evidence["validatorFailure"]
        )

    def test_failure_precedes_every_scientific_selection_or_step(self) -> None:
        failure = self.result["openedFailure"]
        self.assertEqual(failure["stopReason"], "breakpoint 1.1")
        self.assertEqual(failure["stopSymbolOffset"], 0)
        self.assertEqual(failure["qualifiedCropRecordCount"], 0)
        self.assertEqual(failure["qualifiedHelperEntryCount"], 0)
        self.assertFalse(failure["helperSelectionReached"])
        self.assertFalse(failure["manualTraceStarted"])
        self.assertEqual(failure["callerContinuationInstructionCount"], 0)
        self.assertEqual(failure["calleeInstructionCount"], 0)
        self.assertFalse(failure["producerOwnershipOutcomeAvailable"])

    def test_retry_is_transport_only(self) -> None:
        retry = self.result["transportRetryBoundary"]
        self.assertTrue(retry["sameBreakpointAddressesRequired"])
        self.assertTrue(retry["sameSelectorRequired"])
        self.assertTrue(retry["sameMemoryReadsRequired"])
        self.assertTrue(retry["sameInstructionSteppingRequired"])
        self.assertTrue(retry["sameValidatorRequired"])
        self.assertEqual(retry["newBreakpointCount"], 0)
        self.assertEqual(retry["newMemoryReadCount"], 0)
        self.assertEqual(retry["newValueBasedSelectorCount"], 0)

    def test_no_parity_or_shader_claim_is_opened(self) -> None:
        for key, value in self.result["sealedConclusion"].items():
            self.assertFalse(value, key)
        shader = REPOSITORY_ROOT.parent / "shaders" / "frag.glsl"
        if shader.is_file():
            self.assertEqual(
                sha256(shader),
                "6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d",
            )


if __name__ == "__main__":
    unittest.main()
