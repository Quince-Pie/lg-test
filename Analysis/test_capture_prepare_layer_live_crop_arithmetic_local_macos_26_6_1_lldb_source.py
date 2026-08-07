#!/usr/bin/env python3
"""Source contracts for the native live crop-arithmetic overlay."""

import ast
from pathlib import Path
import unittest


SOURCE_PATH = Path(__file__).with_name(
    "capture_prepare_layer_live_crop_arithmetic_local_macos_26_6_1_lldb.py"
)
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


class CapturePrepareLayerLiveCropArithmeticTests(unittest.TestCase):
    def test_native_adapter_remains_apple_python_39_compatible(self) -> None:
        ast.parse(SOURCE, filename=str(SOURCE_PATH), feature_version=(3, 9))

    def test_capture_reads_code_only(self) -> None:
        for fragment in (
            "target.FindFunctions",
            "symbol.GetStartAddress",
            "symbol.GetEndAddress",
            "_read_memory",
            "hashlib.sha256(code).hexdigest()",
            '"cropOrProducerValuesUsed": False',
            '"imageValuesUsed": False',
            '"hardwareWatchpointsUsed": False',
            '"instructionSteppingUsed": False',
        ):
            self.assertIn(fragment, SOURCE)
        for forbidden in (
            "WatchAddress",
            "StepInstruction",
            "isclose(",
            "outputBounds",
            "observedProducer",
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
            self.assertIn(f"def {callback}(", SOURCE)
            self.assertIn(f'"{callback}"', SOURCE)


if __name__ == "__main__":
    unittest.main()
