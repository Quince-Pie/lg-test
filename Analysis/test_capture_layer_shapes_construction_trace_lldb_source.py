#!/usr/bin/env python3
"""Portable source tests for the early/dynamic LayerShapes LLDB probe."""

import importlib.util
import inspect
import sys
import types
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
MODULE_PATH = ANALYSIS_ROOT / "capture_layer_shapes_construction_trace_lldb.py"


def load_with_stub_lldb():
    module_name = "capture_layer_shapes_construction_trace_lldb_source_test"
    specification = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError("LLDB construction module spec is unavailable")
    module = importlib.util.module_from_spec(specification)
    previous = sys.modules.get("lldb")
    stub = types.ModuleType("lldb")
    stub.LLDB_INVALID_ADDRESS = (1 << 64) - 1
    sys.modules["lldb"] = stub
    try:
        specification.loader.exec_module(module)
    finally:
        if previous is None:
            del sys.modules["lldb"]
        else:
            sys.modules["lldb"] = previous
    return module


class LayerShapesConstructionLLDBSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_with_stub_lldb()

    def setUp(self):
        self.module._state["objectAddresses"] = {}
        self.module._state["trace"] = {
            "directRecords": [],
            "alternateRecords": [],
        }

    def test_opened_direct_helper_and_alternate_store_are_frozen(self):
        module = self.module
        self.assertEqual(module.TRACE_SCHEMA_VERSION, 1)
        self.assertEqual(module.DIRECT_CALL_OFFSET, 0x32C0)
        self.assertEqual(module.DIRECT_RETURN_OFFSET, 0x32C4)
        self.assertEqual(module.UNION_HELPER_RELATIVE_TO_PREPARE_LAYER, -0xAA0)
        self.assertEqual(module.UNION_HELPER_SYMBOL_BYTE_COUNT, 404)
        self.assertEqual(
            module.UNION_HELPER_SYMBOL_NAME,
            "CA::Render::Updater::LayerShapes::union_bounds(CA::Rect const&, bool)",
        )
        self.assertEqual(module.ALTERNATE_STORE_OFFSET, 0x33F0)
        self.assertEqual(module.ALTERNATE_AFTER_OFFSET, 0x33F4)
        self.assertEqual(module.ALTERNATE_STORE_RAW_LITTLE_ENDIAN.hex(), "608614ad")
        self.assertEqual(module.MAXIMUM_DIRECT_RECORD_COUNT, 64)
        self.assertEqual(module.MAXIMUM_ALTERNATE_RECORD_COUNT, 96)

    def test_direct_bl_decodes_to_opened_union_bounds_target(self):
        module = self.module
        prepare_start = 0x19428653C
        word, displacement, target = module._decode_bl_target(
            prepare_start + module.DIRECT_CALL_OFFSET,
            module.DIRECT_CALL_RAW_LITTLE_ENDIAN,
        )
        self.assertEqual(word, 0x97FFF0A8)
        self.assertEqual(displacement, -0x3D60)
        self.assertEqual(target, prepare_start - 0xAA0)

    def test_record_classification_is_retrospective_and_exact(self):
        source = 0x1_A000_0000
        self.module._state["trace"] = {
            "directRecords": [
                {"addresses": {"source": source}, "selectedSource": None},
                {"addresses": {"source": source + 8}, "selectedSource": None},
            ],
            "alternateRecords": [
                {"addresses": {"source": source}, "selectedSource": None}
            ],
        }
        self.module._state["objectAddresses"] = {"source": source}
        self.module._classify_records()
        self.assertEqual(
            [item["selectedSource"] for item in self.module._state["trace"]["directRecords"]],
            [True, False],
        )
        self.assertTrue(
            self.module._state["trace"]["alternateRecords"][0]["selectedSource"]
        )

    def test_callback_signatures_match_apple_lldb(self):
        for name in (
            "capture_backdrop_entry",
            "capture_backdrop_late",
            "prepare_layer_entry",
            "direct_union_call",
            "direct_union_return",
            "alternate_store_before",
            "alternate_store_after",
        ):
            with self.subTest(callback=name):
                self.assertEqual(
                    list(inspect.signature(getattr(self.module, name)).parameters),
                    ["frame", "_breakpoint_location", "_internal_dict"],
                )

    def test_decoder_rejects_non_bl_payloads(self):
        with self.assertRaisesRegex(ValueError, "not an AArch64 BL"):
            self.module._decode_bl_target(0x1000, bytes.fromhex("1f2003d5"))


if __name__ == "__main__":
    unittest.main()
