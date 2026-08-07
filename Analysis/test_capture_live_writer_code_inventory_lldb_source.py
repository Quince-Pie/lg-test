"""Static tests for the value-blind live writer code inventory."""

from __future__ import annotations

import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parent / "capture_live_writer_code_inventory_lldb.py"


class LiveWriterCodeInventorySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE.read_text(encoding="utf-8")

    def test_inventory_reads_symbols_but_no_application_values(self) -> None:
        self.assertIn("BreakpointCreateByName", self.source)
        self.assertIn("GetStartAddress", self.source)
        self.assertIn("GetEndAddress", self.source)
        self.assertIn("ReadMemory", self.source)
        for forbidden in (
            "GetRegisters",
            "FindRegister",
            "marginF64",
            "marginF32",
            "inputShadow",
            "inputBleed",
            "transition-timeline",
            "rgba8",
        ):
            self.assertNotIn(forbidden, self.source)

    def test_all_four_structural_symbols_are_frozen(self) -> None:
        for key in ('"key": "copy"', '"key": "setter"', '"key": "bounds"', '"key": "caller"'):
            self.assertIn(key, self.source)
        self.assertIn("processContinuedAfterMain", self.source)


if __name__ == "__main__":
    unittest.main()
