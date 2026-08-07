#!/usr/bin/env python3
"""Tests for the instruction-level case-22 provider replay."""

from __future__ import annotations

import hashlib
import json
import math
import struct
import unittest
from pathlib import Path

import analyze_backdrop_margin_case22_provider_complete_semantics as analysis


ANALYSIS = Path(__file__).resolve().parent
SOURCE = ANALYSIS / "analyze_backdrop_margin_case22_provider_complete_semantics.py"
RESULT_PATH = (
    ANALYSIS
    / "backdrop_margin_case22_provider_complete_semantics_retrospective_result.json"
)
RESULT = json.loads(RESULT_PATH.read_text(encoding="utf-8"))


class CompleteProviderSemanticsAnalysisTests(unittest.TestCase):
    def test_fcmp_conditions_include_unordered_arm64_behavior(self) -> None:
        unordered = analysis.floating_compare(math.nan, 0.0)
        self.assertFalse(analysis.condition_passed("ge", unordered))
        self.assertFalse(analysis.condition_passed("gt", unordered))
        self.assertTrue(analysis.condition_passed("hi", unordered))
        self.assertTrue(analysis.condition_passed("le", unordered))
        self.assertFalse(analysis.condition_passed("ls", unordered))
        self.assertTrue(analysis.condition_passed("lt", unordered))

    def test_fcmp_treats_signed_zero_as_equal(self) -> None:
        equal = analysis.floating_compare(-0.0, 0.0)
        self.assertTrue(analysis.condition_passed("ge", equal))
        self.assertFalse(analysis.condition_passed("gt", equal))
        self.assertTrue(analysis.condition_passed("le", equal))
        self.assertTrue(analysis.condition_passed("ls", equal))

    def test_synthetic_control_flow_selects_the_greater_raw_value(self) -> None:
        instructions = (
            "ldr\td0, [x20, #0]",
            "ldr\td1, [x20, #8]",
            "fcmp\td0, d1",
            "b.ge\t#8",
            "mov\tv0.16b, v1.16b",
            "retab",
        )
        provider_object = bytearray(384)
        struct.pack_into("<dd", provider_object, 0, 1.25, 2.5)
        replay = analysis.replay(instructions, bytes(provider_object))
        self.assertEqual(
            replay["returnRawLittleEndianHex"], struct.pack("<d", 2.5).hex()
        )
        self.assertEqual(replay["branchOutcomes"], [(12, False)])

        struct.pack_into("<dd", provider_object, 0, 4.0, -3.0)
        replay = analysis.replay(instructions, bytes(provider_object))
        self.assertEqual(
            replay["returnRawLittleEndianHex"], struct.pack("<d", 4.0).hex()
        )
        self.assertEqual(replay["branchOutcomes"], [(12, True)])

    def test_retrospective_result_is_canonical_and_source_bound(self) -> None:
        self.assertEqual(
            RESULT_PATH.read_text(encoding="utf-8"),
            json.dumps(RESULT, indent=2, sort_keys=True) + "\n",
        )
        self.assertEqual(
            RESULT["inputs"]["analysisSource"]["sha256"],
            hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        )

    def test_retrospective_authority_is_exact_and_narrow(self) -> None:
        replay = RESULT["replay"]
        self.assertEqual(replay["sampleCount"], 3683)
        self.assertEqual(replay["matchingReturnCount"], 3683)
        self.assertEqual(replay["finiteLoadedObjectSampleCount"], 3683)
        self.assertTrue(replay["allReturnWordsMatchedBitwise"])
        self.assertEqual(replay["distinctExecutionPathCount"], 3)
        self.assertEqual(replay["executedInstructionCount"], 101)
        self.assertEqual(replay["staticConditionalBranchCount"], 41)
        self.assertEqual(replay["observedConditionalBranchCount"], 13)
        self.assertEqual(replay["bothOutcomeConditionalBranchCount"], 5)
        authority = RESULT["authority"]
        self.assertTrue(authority["retainedFiniteObjectReturnsReplayedBitwise"])
        self.assertFalse(authority["everyStaticBranchOutcomeObserved"])
        self.assertFalse(authority["publicInputFieldMappingEstablished"])
        self.assertFalse(authority["unseenObjectTransferEstablished"])
        self.assertFalse(authority["liquidGlassParityEstablished"])
        self.assertFalse(authority["productionShaderAuthorized"])


if __name__ == "__main__":
    unittest.main()
