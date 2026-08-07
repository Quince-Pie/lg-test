#!/usr/bin/env python3
"""Source contracts for the exact live FilterOp/DOD stage overlay."""

import unittest
from pathlib import Path


SOURCE_PATH = Path(__file__).with_name(
    "capture_prepare_layer_filter_stage_arithmetic_local_macos_26_6_1_lldb.py"
)
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


class PrepareLayerFilterStageCaptureTests(unittest.TestCase):
    def test_complete_symbol_identities_are_frozen(self) -> None:
        for fragment in (
            "FILTER_RELATIVE_TO_PREPARE_LAYER = -61476",
            "FILTER_SYMBOL_BYTE_COUNT = 292",
            "4dba83cf41031189caf8813b9eed5e833ee13484d4fa2f98cb4010f6e357cada",
            "DOD_RELATIVE_TO_PREPARE_LAYER = -90656",
            "DOD_SYMBOL_BYTE_COUNT = 1136",
            "d44b226f8edbfcb8fd37bc0f15a48b583df08063dc812e28cd06b1398d2f1678",
        ):
            self.assertIn(fragment, SOURCE)

    def test_filter_stage_instructions_are_frozen(self) -> None:
        for fragment in (
            '("entry", 0, "7f2303d5", "filter_entry")',
            '("afterUnapply", 88, "810242a9", "filter_after_unapply")',
            '("afterApplyDOD", 100, "6006416d", "filter_after_apply_dod")',
            '("afterApplyTransform", 140, "75000037", "filter_after_apply_transform")',
            '("final", 268, "fd7b45a9", "filter_final")',
        ):
            self.assertIn(fragment, SOURCE)

    def test_dod_stage_instructions_are_frozen(self) -> None:
        for fragment in (
            '("beforePrimaryUnion", 408, "e50bc03d", "dod_before_primary_union")',
            '("afterPrimaryUnion", 504, "a082c43c", "dod_after_primary_union")',
            '("afterLayerSource", 592, "e51bc03d", "dod_after_layer_source")',
            '("afterBleedUnion", 940, "e002c03d", "dod_after_bleed_union")',
            '("beforeSourceIntersection", 988, "6202c03d", "dod_before_source_intersection")',
            '("final", 1072, "a88359f8", "dod_final")',
        ):
            self.assertIn(fragment, SOURCE)

    def test_selection_is_value_blind_and_nonintervening(self) -> None:
        self.assertIn('"rectangleValuesUsedForSelection": False', SOURCE)
        self.assertIn('"cropOrProducerValuesUsedForSelection": False', SOURCE)
        self.assertIn('"hardwareWatchpointsUsed": False', SOURCE)
        self.assertIn('"instructionSteppingUsed": False', SOURCE)
        for forbidden in (
            "WatchAddress",
            "StepInstruction",
            "isclose(",
            "productionShaderAuthorized",
            "liquidGlassParityEstablished",
        ):
            self.assertNotIn(forbidden, SOURCE)

    def test_every_inherited_callback_is_exported(self) -> None:
        for callback in (
            "prepare_layer_entry",
            "crop_transfer_marker",
            "crop_union_call",
            "crop_union_return",
            "nested_crop_store",
        ):
            self.assertIn("def " + callback + "(", SOURCE)
            self.assertIn('"' + callback + '"', SOURCE)


if __name__ == "__main__":
    unittest.main()
