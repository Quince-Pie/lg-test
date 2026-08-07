"""Static integrity tests for the live-UUID writer capture overlay."""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
SOURCE = ANALYSIS / "capture_backdrop_margin_writer_provider_composition_lldb.py"
BASE = ANALYSIS / "capture_backdrop_margin_writer_execution_lldb.py"
PRODUCER = ANALYSIS / "capture_backdrop_margin_writer_producer_lldb.py"


class BackdropMarginWriterProviderCompositionCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE.read_text(encoding="utf-8")

    def test_frozen_adapters_remain_byte_identical(self) -> None:
        self.assertEqual(
            hashlib.sha256(BASE.read_bytes()).hexdigest(),
            "f91ba6afb61b491d949ea5dc9d4fc1c82c165e0016aefa84db00a0b15d435ecd",
        )
        self.assertEqual(
            hashlib.sha256(PRODUCER.read_bytes()).hexdigest(),
            "4e5620a157021578a0bb79f3b8cbf49eed2d754e960ecc076a046ae13d575d76",
        )

    def test_overlay_changes_only_structural_module_identity(self) -> None:
        self.assertIn("F1BA3189-E95A-3ECA-B59A-5A6872754484", self.source)
        self.assertIn("writer.QUARTZCORE_UUID = LIVE_QUARTZCORE_UUID", self.source)
        self.assertIn("producer.__lldb_init_module", self.source)
        self.assertIn("producer.finalize", self.source)
        self.assertIn("_install_direct_callback_proxies()", self.source)
        for callback in (
            "margin_setter",
            "copy_entry",
            "copy_margin_store",
            "backdrop_bounds",
        ):
            self.assertIn(f"def {callback}(", self.source)
        for forbidden in (
            "marginF64",
            "marginF32",
            "inputShadow",
            "inputBleed",
            "transition-timeline",
            "rgba8",
        ):
            self.assertNotIn(forbidden, self.source)


if __name__ == "__main__":
    unittest.main()
