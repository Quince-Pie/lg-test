#!/usr/bin/env python3
"""Portable source-level tests for the LayerShapes LLDB callback module."""

import importlib.util
import inspect
import sys
import types
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
MODULE_PATH = ANALYSIS_ROOT / "capture_layer_shapes_merge_trace_lldb.py"


def load_with_stub_lldb():
    module_name = "capture_layer_shapes_merge_trace_lldb_source_test"
    specification = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError("LLDB merge module spec is unavailable")
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


class FileSpec:
    def __init__(self, directory, filename):
        self.directory = directory
        self.filename = filename

    def GetDirectory(self):
        return self.directory

    def GetFilename(self):
        return self.filename


class LayerShapesMergeLLDBSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_with_stub_lldb()

    def test_frozen_trace_bounds_and_offsets_are_exact(self):
        module = self.module
        self.assertEqual(module.TRACE_SCHEMA_VERSION, 1)
        self.assertEqual(module.PREPARE_LAYER_SYMBOL_BYTE_COUNT, 40128)
        self.assertEqual(module.PREPARE_LAYER_CODE_WINDOW_OFFSET, 12764)
        self.assertEqual(module.PREPARE_LAYER_CODE_WINDOW_BYTE_COUNT, 0x1000)
        self.assertEqual(module.MERGE_CALL_OFFSET, 0x32C0)
        self.assertEqual(module.MERGE_RETURN_OFFSET, 0x32C4)
        self.assertEqual(module.MERGE_TARGET_CODE_BYTE_COUNT, 0x1000)
        self.assertEqual(module.LAYER_SHAPES_BYTE_COUNT, 0x20)
        self.assertEqual(module.ROLE_STATE_BYTE_COUNT, 0x800)
        self.assertEqual(module.SOURCE_OBJECT_BYTE_COUNT, 0x180)
        self.assertEqual(module.MAXIMUM_COMPLETE_RECORD_COUNT, 64)

    def test_opened_bl_decodes_to_the_exact_relative_target(self):
        module = self.module
        prepare_start = 0x18E983A7C
        call_address = prepare_start + module.MERGE_CALL_OFFSET
        word, displacement, target = module._decode_bl_target(
            call_address, module.MERGE_CALL_RAW_LITTLE_ENDIAN
        )
        self.assertEqual(word, 0x97FFF0A8)
        self.assertEqual(displacement, -0x3D60)
        self.assertEqual(target, prepare_start - 0xAA0)

    def test_decoder_rejects_non_bl_and_wrong_payload_size(self):
        with self.assertRaisesRegex(ValueError, "four bytes"):
            self.module._decode_bl_target(0x1000, b"\0\0")
        with self.assertRaisesRegex(ValueError, "not an AArch64 BL"):
            self.module._decode_bl_target(0x1000, bytes.fromhex("1f2003d5"))

    def test_callback_signatures_match_apple_lldb(self):
        for name in (
            "capture_backdrop_entry",
            "capture_backdrop_late",
            "prepare_layer_entry",
            "merge_call",
            "merge_return",
        ):
            with self.subTest(callback=name):
                self.assertEqual(
                    list(inspect.signature(getattr(self.module, name)).parameters),
                    ["frame", "_breakpoint_location", "_internal_dict"],
                )

    def test_file_spec_path_uses_portable_accessors(self):
        self.assertEqual(
            self.module._file_spec_path(
                FileSpec(
                    "/System/Library/Frameworks/QuartzCore.framework/Versions/A",
                    "QuartzCore",
                )
            ),
            "/System/Library/Frameworks/QuartzCore.framework/Versions/A/QuartzCore",
        )
        self.assertEqual(self.module._file_spec_path(FileSpec(None, None)), "")


if __name__ == "__main__":
    unittest.main()
