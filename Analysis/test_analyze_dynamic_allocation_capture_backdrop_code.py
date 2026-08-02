#!/usr/bin/env python3
"""Tests for the capture_backdrop code-evidence analyzer."""

import unittest

import analyze_dynamic_allocation_capture_backdrop_code as analyzer


class CaptureBackdropCodeAnalyzerTests(unittest.TestCase):
    def test_sign_extend_preserves_positive_and_negative_values(self) -> None:
        self.assertEqual(analyzer.sign_extend(1, 26), 1)
        self.assertEqual(analyzer.sign_extend((1 << 26) - 1, 26), -1)

    def test_control_flow_decodes_direct_and_conditional_branches(self) -> None:
        self.assertEqual(
            analyzer.control_flow_instruction(0x9400_0001, 0x100),
            {
                "kind": "bl",
                "offset": 0x100,
                "instruction": "94000001",
                "targetOffset": 0x104,
            },
        )
        self.assertEqual(
            analyzer.control_flow_instruction(0x54FF_FFE1, 0x100)["kind"],
            "b.cond",
        )
        self.assertIsNone(analyzer.control_flow_instruction(0xD503_201F, 0x100))

    def test_direct_call_groups_preserve_every_source_offset(self) -> None:
        target_code = {"sha256": "a" * 64}
        groups = analyzer.direct_call_groups(
            [
                {
                    "targetImageOffset": "0x100",
                    "targetSymbol": "helper",
                    "targetSymbolOffset": "0x0",
                    "targetCode": target_code,
                    "sourceInstructionOffset": 0x20,
                },
                {
                    "targetImageOffset": "0x100",
                    "targetSymbol": "helper",
                    "targetSymbolOffset": "0x0",
                    "targetCode": target_code,
                    "sourceInstructionOffset": 0x40,
                },
            ]
        )
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["sourceInstructionOffsets"], [0x20, 0x40])

    def test_classification_denies_a_recovered_policy(self) -> None:
        self.assertIn("not-a-recovered-producer-mesh-policy", analyzer.CLASSIFICATION)

    def test_retrospective_status_is_not_a_prospective_pass(self) -> None:
        self.assertIn(
            "retrospective-validator-correction-after-failed-ci-gate",
            analyzer.EVIDENCE_STATUSES,
        )


if __name__ == "__main__":
    unittest.main()
