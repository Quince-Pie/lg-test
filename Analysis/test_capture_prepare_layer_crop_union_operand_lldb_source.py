#!/usr/bin/env python3
"""Portable source tests for the prospective crop-union operand probe."""

import importlib.util
import inspect
import sys
import types
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
MODULE_PATH = ANALYSIS_ROOT / "capture_prepare_layer_crop_union_operand_lldb.py"
BASE_MODULE_NAMES = (
    "capture_prepare_layer_crop_union_operand_lldb",
    "capture_prepare_layer_crop_transfer_lldb",
    "capture_prepare_layer_full_path_trace_lldb",
)


def load_with_stub_lldb():
    module_name = "capture_prepare_layer_crop_union_operand_source_test"
    specification = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError("crop-union operand LLDB module spec is unavailable")
    module = importlib.util.module_from_spec(specification)
    previous_lldb = sys.modules.get("lldb")
    previous_modules = {
        name: sys.modules.pop(name, None) for name in BASE_MODULE_NAMES
    }
    stub = types.ModuleType("lldb")
    stub.LLDB_INVALID_ADDRESS = (1 << 64) - 1
    stub.eStateExited = 10
    stub.eStateDetached = 9
    sys.modules["lldb"] = stub
    try:
        specification.loader.exec_module(module)
    finally:
        if previous_lldb is None:
            del sys.modules["lldb"]
        else:
            sys.modules["lldb"] = previous_lldb
        for name, previous in previous_modules.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous
    return module


class PrepareLayerCropUnionOperandSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_with_stub_lldb()

    def setUp(self):
        self.module._reset_state()

    def test_only_the_opened_call_and_return_sites_are_added(self):
        self.assertEqual(self.module.UNION_CALL_OFFSET, 0x85DC)
        self.assertEqual(
            self.module.UNION_CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX,
            "e1dbff97",
        )
        self.assertEqual(self.module.UNION_RETURN_OFFSET, 0x85E0)
        self.assertEqual(
            self.module.UNION_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX,
            "686241f9",
        )
        source = inspect.getsource(self.module._install_extension)
        self.assertIn("crop union call window", source)
        self.assertIn("UNION_CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX", source)
        self.assertIn("UNION_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX", source)

    def test_existing_entry_and_marker_gates_run_before_extension_logic(self):
        entry = inspect.getsource(self.module.prepare_layer_entry)
        marker = inspect.getsource(self.module.crop_transfer_marker)
        self.assertLess(
            entry.index("crop_base.prepare_layer_entry"),
            entry.index("_install_extension"),
        )
        self.assertLess(
            marker.index("crop_base.crop_transfer_marker"),
            marker.index('marker["cropUnionOperandWindow"]'),
        )

    def test_union_call_selection_is_value_independent(self):
        source = inspect.getsource(self.module.crop_union_call)
        caller_index = source.index("_direct_timeline_caller")
        register_index = source.index("registers = _registers")
        role_index = source.index('"roleState": _snapshot')
        layer_shapes_index = source.index('"layerShapesState": _snapshot')
        self.assertLess(caller_index, register_index)
        self.assertLess(register_index, role_index)
        self.assertLess(register_index, layer_shapes_index)
        prefix = source[:register_index]
        self.assertNotIn("unpack", prefix)
        self.assertNotIn("integer", prefix.lower())
        self.assertNotIn("rectangle", prefix.lower())

    def test_marker_link_uses_only_interval_and_destination_identity(self):
        source = inspect.getsource(self.module.crop_transfer_marker)
        self.assertIn("lastQualifiedMarkerUnionIndex", source)
        self.assertIn("UNION_DESTINATION_ROLE_OFFSET", source)
        self.assertIn('record["frameIdentity"]["destination"] == destination', source)
        self.assertNotIn("struct", source)
        self.assertNotIn("unpack", source)
        self.assertNotIn("aggregateF64", source)

    def test_call_and_return_are_paired_by_thread(self):
        call = inspect.getsource(self.module.crop_union_call)
        returned = inspect.getsource(self.module.crop_union_return)
        self.assertIn('pendingByThread"][thread_id] = record_index', call)
        self.assertIn('pendingByThread"].pop(thread_id)', returned)
        self.assertIn('record["targetAfter"]', returned)
        self.assertIn('record["complete"] = True', returned)

    def test_exact_crop_bearing_ranges_are_retained(self):
        self.assertEqual(self.module.UNION_INPUT_ROLE_OFFSET, 0x620)
        self.assertEqual(self.module.UNION_DESTINATION_ROLE_OFFSET, 0x290)
        self.assertEqual(self.module.LAYER_SHAPES_WINDOW_OFFSET, 0xA0)
        self.assertEqual(self.module.LAYER_SHAPES_WINDOW_BYTE_COUNT, 0x30)
        self.assertEqual(self.module.UNION_INPUT_BYTE_COUNT, 0x20)
        self.assertEqual(self.module.UNION_TARGET_BYTE_COUNT, 0x20)
        self.assertEqual(
            self.module.UNION_REGISTER_NAMES,
            ("x0", "x1", "x2", "x19", "x28", "x29", "sp", "pc", "cpsr"),
        )

    def test_no_watchpoints_or_instruction_stepping_are_present(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("WatchAddress", source)
        self.assertNotIn("DeleteWatchpoint", source)
        self.assertNotIn("StepInstruction", source)
        self.assertNotIn("StepOut", source)


if __name__ == "__main__":
    unittest.main()
