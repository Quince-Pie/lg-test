#!/usr/bin/env python3
"""Source contracts for the live DOD source calibration overlay."""

import unittest
from pathlib import Path


SOURCE_PATH = Path(__file__).with_name(
    "capture_prepare_layer_live_dod_source_bounds_local_macos_26_6_1_lldb.py"
)
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


class PrepareLayerLiveDODSourceCaptureTests(unittest.TestCase):
    def test_exact_live_code_identity_is_frozen(self) -> None:
        for fragment in (
            "DOD_RELATIVE_TO_PREPARE_LAYER = -0x16220",
            "DOD_SYMBOL_BYTE_COUNT = 1136",
            "d44b226f8edbfcb8fd37bc0f15a48b583df08063dc812e28cd06b1398d2f1678",
            "SOURCE_REGISTERS_OFFSET = 0x200",
            'SOURCE_REGISTERS_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = "e00703ad"',
        ):
            self.assertIn(fragment, SOURCE)

    def test_selection_is_value_blind_and_nonintervening(self) -> None:
        self.assertIn('"sourceValuesUsedForSelection": False', SOURCE)
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

    def test_q_registers_are_retained_only_after_structural_stop(self) -> None:
        self.assertIn('frame, ("x19", "x21", "pc", "v0", "v1")', SOURCE)
        self.assertLess(
            SOURCE.index("BreakpointCreateByAddress"),
            SOURCE.index("def dod_source_bounds"),
        )
        callback = SOURCE[SOURCE.index("def dod_source_bounds") :]
        self.assertNotIn("sourceOrigin", callback)
        self.assertNotIn("sourceSize", callback)


if __name__ == "__main__":
    unittest.main()
