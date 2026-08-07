#!/usr/bin/env python3
"""Source-contract tests for the variable-blur LLDB calibration trace."""

from pathlib import Path
import unittest


SOURCE = Path(__file__).with_name("capture_variable_blur_parameter_trace_lldb.py")


class VariableBlurParameterTraceSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE.read_text(encoding="utf-8")

    def test_selection_is_stack_structural(self) -> None:
        self.assertIn("CAPTURE_BACKDROP_NAME", self.source)
        self.assertIn("_contains_capture_backdrop", self.source)
        self.assertIn('"capturedResultUsedForSelection": False', self.source)

    def test_complete_code_and_operands_are_retained(self) -> None:
        for token in (
            "GetStartAddress",
            "GetEndAddress",
            "complete helper code",
            '"sourceExtent"',
            '"boundsHex"',
            '"integerBounds"',
            '"floatingBounds"',
        ):
            self.assertIn(token, self.source)

    def test_no_image_or_pixel_read_is_present(self) -> None:
        self.assertNotIn("CGImage", self.source)
        self.assertNotIn("MTLTexture", self.source)
        self.assertIn(
            '"capturedImageOrPixelUsedForSelection": False',
            self.source,
        )


if __name__ == "__main__":
    unittest.main()
