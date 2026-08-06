#!/usr/bin/env python3
"""Source checks for the SDF map-bounds diagnostic adapter."""

import hashlib
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
SOURCE_PATH = ANALYSIS_ROOT / "capture_prepare_layer_sdf_map_bounds_diagnostic_lldb.py"
REGULAR_PATH = ANALYSIS_ROOT / "capture_prepare_layer_filter_map_bounds_regular_lldb.py"
FROZEN_PATH = ANALYSIS_ROOT / "capture_prepare_layer_filter_map_bounds_lldb.py"
REGULAR_SHA256 = "0366d6233e1260014d8a7e2ea1c509b0e7e5d8aa46c38bfda2f201746110249b"
FROZEN_SHA256 = "0755924cd34936f6cc433d1efe322989229f94423a832107a73ae087da0c1320"


class PrepareLayerSDFMapBoundsDiagnosticSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")

    def test_inherited_filter_captures_remain_unchanged(self) -> None:
        self.assertEqual(
            hashlib.sha256(REGULAR_PATH.read_bytes()).hexdigest(), REGULAR_SHA256
        )
        self.assertEqual(
            hashlib.sha256(FROZEN_PATH.read_bytes()).hexdigest(), FROZEN_SHA256
        )

    def test_sdf_identity_and_output_blind_dispatch_are_frozen(self) -> None:
        self.assertIn("SDF_RELATIVE_TO_PREPARE_LAYER = -56012", self.source)
        self.assertIn("SDF_SYMBOL_BYTE_COUNT = 160", self.source)
        self.assertIn("SDF_DISPATCH_ORDINAL = 2", self.source)
        self.assertIn('"cropValuesUsedForSelection": False', self.source)
        self.assertIn('"outputValuesUsedForSelection": False', self.source)
        self.assertIn('"expectedCodeSHA256": None', self.source)

    def test_only_sdf_boundary_is_opened(self) -> None:
        self.assertIn("frame.GetFunctionName() == SDF_FUNCTION", self.source)
        self.assertIn("_trace_sdf_instruction", self.source)
        self.assertIn("_trace_sdf_opaque_callee", self.source)
        self.assertIn("_capture_opaque_identity", self.source)
        self.assertIn(
            "return original(thread, frame, expected_return_function)", self.source
        )
        self.assertIn("producer_base._trace_opaque_callee = original", self.source)

    def test_filter_boundary_accounting_is_preserved(self) -> None:
        self.assertIn(
            'extension["opaqueCalleeBoundaries"].append(boundary)', self.source
        )
        self.assertIn('{"kind": "opaque-callee", "recordIndex":', self.source)
        self.assertNotIn("BreakpointCreate", self.source)
        self.assertNotIn("WatchAddress", self.source)


if __name__ == "__main__":
    unittest.main()
