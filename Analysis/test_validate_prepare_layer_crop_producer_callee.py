#!/usr/bin/env python3
"""Unit contracts for the post-mask crop-producer callee validator."""

from __future__ import annotations

import inspect
import unittest

import validate_prepare_layer_crop_producer_callee as validator


class PrepareLayerCropProducerCalleeValidatorTests(unittest.TestCase):
    def test_changed_qwords_reports_exact_byte_offsets(self):
        before = bytes(32)
        after = bytearray(before)
        after[8] = 1
        after[31] = 1
        self.assertEqual(validator.changed_qwords(before, bytes(after)), [8, 24])

    def test_changed_qwords_rejects_non_qword_or_different_lengths(self):
        with self.assertRaisesRegex(ValueError, "qword comparison byte count"):
            validator.changed_qwords(bytes(8), bytes(16))
        with self.assertRaisesRegex(ValueError, "qword comparison byte count"):
            validator.changed_qwords(bytes(7), bytes(7))

    def test_antecedent_requires_the_frozen_ownership_falsification(self):
        self.assertEqual(
            validator.EXPECTED_HELPER_MISMATCH,
            "helper output does not match structural producer",
        )
        source = inspect.getsource(validator.validate_antecedent)
        self.assertIn("selected helper unexpectedly produced the crop", source)
        self.assertIn("selected_validator.validate", source)

    def test_execution_requires_a_complete_bitwise_chain(self):
        source = inspect.getsource(validator.validate_execution)
        for required in (
            'record["outputBefore"] != previous_output',
            'record["roleBefore"] != previous_role',
            'record["pc"] != previous_result_pc',
            "producer callee event coverage differs",
            "PRODUCER_CALLEE_RETURN_OFFSET",
        ):
            self.assertIn(required, source)

    def test_success_still_seals_every_downstream_parity_claim(self):
        source = inspect.getsource(validator.validate)
        for required_false in (
            '"exactCalleeSemanticsDecoded": False',
            '"unchangedRepeatPassed": False',
            '"allCropHoldoutsBitExact": False',
            '"materialAppearanceDirectionTransferPassed": False',
            '"physicalRetina2xAndColorTransferPassed": False',
            '"independentWalleZeroByteFrameParityPassed": False',
            '"productionShaderAuthorized": False',
            '"liquidGlassParityEstablished": False',
        ):
            self.assertIn(required_false, source)


if __name__ == "__main__":
    unittest.main()
