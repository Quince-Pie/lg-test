#!/usr/bin/env python3
"""Unit contracts for the FilterOp map-bounds validator."""

from __future__ import annotations

import inspect
import unittest

import validate_prepare_layer_filter_map_bounds as validator


class PrepareLayerFilterMapBoundsValidatorTests(unittest.TestCase):
    def test_target_is_fixed_to_known_code_not_an_output(self):
        self.assertEqual(validator.DYNAMIC_CALL_OFFSET, 0x2864)
        self.assertEqual(validator.TARGET_DISPATCH_ORDINAL, 4)
        self.assertEqual(validator.FILTER_RELATIVE_TO_PREPARE_LAYER, -61056)
        self.assertEqual(validator.FILTER_SYMBOL_BYTE_COUNT, 788)
        self.assertEqual(
            validator.FILTER_CODE_SHA256,
            "e8766dcefdadc0074f7bb4e2bf62955072891858009dca6c72a7eef1c96789d0",
        )
        self.assertFalse(validator.EXPECTED_CONFIGURATION["cropValuesUsedForSelection"])
        self.assertFalse(
            validator.EXPECTED_CONFIGURATION["outputValuesUsedForSelection"]
        )

    def test_dispatch_validation_uses_structure_only(self):
        source = inspect.getsource(validator.validate_dispatches)
        for required in (
            'dispatch.get("dispatchOrdinal")',
            'dispatch.get("callerStateIndex")',
            'dispatch.get("function")',
            'instruction.get("scopeOffset")',
            'instruction.get("rawLittleEndianHex")',
            'dispatch.get("symbolRelativeToPrepareLayer")',
        ):
            self.assertIn(required, source)
        for forbidden in (
            'dispatch.get("outputBefore")',
            'dispatch.get("outputAfter")',
            "struct.unpack",
        ):
            self.assertNotIn(forbidden, source)

    def test_execution_requires_complete_pc_and_memory_chain(self):
        source = inspect.getsource(validator.validate_execution)
        for required in (
            'record["outputBefore"] != previous_output',
            'record["roleBefore"] != previous_role',
            'record["pc"] != previous_result_pc',
            "FilterOp event coverage differs",
            "DYNAMIC_RETURN_OFFSET",
        ):
            self.assertIn(required, source)

    def test_first_pass_still_seals_semantics_and_product_claims(self):
        source = inspect.getsource(validator.validate)
        for required_false in (
            '"exactFilterMapBoundsSemanticsDecoded": False',
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
