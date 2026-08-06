#!/usr/bin/env python3
"""Portable source tests for the prospective crop-policy holdout probe."""

from __future__ import annotations

import importlib.util
import inspect
import sys
import types
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
MODULE_PATH = ANALYSIS_ROOT / "capture_prepare_layer_crop_policy_holdout_lldb.py"
MODULE_NAMES = (
    "capture_prepare_layer_crop_policy_holdout_lldb",
    "capture_prepare_layer_crop_union_operand_lldb",
    "capture_prepare_layer_crop_transfer_lldb",
    "capture_prepare_layer_full_path_trace_lldb",
)


def load_with_stub_lldb():
    module_name = "capture_prepare_layer_crop_policy_holdout_source_test"
    specification = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError("crop-policy holdout LLDB module spec is unavailable")
    module = importlib.util.module_from_spec(specification)
    previous_lldb = sys.modules.get("lldb")
    previous_modules = {name: sys.modules.pop(name, None) for name in MODULE_NAMES}
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


class PrepareLayerCropPolicyHoldoutSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_with_stub_lldb()

    def setUp(self):
        self.module._reset_state()

    def test_only_the_opened_pre_store_instruction_is_added(self):
        self.assertEqual(self.module.STORE_OFFSET, 0x55C0)
        self.assertEqual(
            self.module.STORE_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX,
            "802f803d",
        )
        source = inspect.getsource(self.module._install_extension)
        self.assertIn("nested crop store instruction", source)
        self.assertIn("STORE_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX", source)

    def test_both_inherited_entry_and_marker_gates_run_first(self):
        entry = inspect.getsource(self.module.prepare_layer_entry)
        marker = inspect.getsource(self.module.crop_transfer_marker)
        self.assertLess(
            entry.index("union_base.prepare_layer_entry"),
            entry.index("_install_extension"),
        )
        self.assertLess(
            marker.index("union_base.crop_transfer_marker"),
            marker.index('marker["cropPolicyStoreWindow"]'),
        )

    def test_store_selection_reads_no_crop_value(self):
        source = inspect.getsource(self.module.nested_crop_store)
        caller = source.index("_direct_timeline_caller")
        registers = source.index("_register_snapshot")
        role = source.index('"roleState": _snapshot')
        destination = source.index('"destinationBefore": _snapshot')
        self.assertLess(caller, registers)
        self.assertLess(registers, role)
        self.assertLess(registers, destination)
        prefix = source[:registers]
        self.assertNotIn("struct.", prefix)
        self.assertNotIn("unpack", prefix)
        self.assertNotIn("ROLE_WORKING_CROP_OFFSET", prefix)
        self.assertNotIn("ROLE_FLOAT_INPUT_OFFSET", prefix)
        self.assertNotIn("_snapshot(", prefix)

    def test_marker_link_is_order_and_pointer_only(self):
        source = inspect.getsource(self.module.crop_transfer_marker)
        self.assertIn("union_indices[-1]", source)
        self.assertIn('record["frameIdentity"]["layerShapesBase"]', source)
        self.assertIn("selected_layer_shapes", source)
        self.assertNotIn("struct", source)
        self.assertNotIn("unpack", source)
        self.assertNotIn("aggregateF64", source)
        self.assertNotIn("workingCrop", source)

    def test_exact_producer_ranges_and_simd_source_are_retained(self):
        self.assertEqual(self.module.ROLE_WORKING_CROP_OFFSET, 0x270)
        self.assertEqual(self.module.ROLE_FLOAT_INPUT_OFFSET, 0x290)
        self.assertEqual(self.module.LAYER_SHAPES_NESTED_OFFSET, 0xB0)
        self.assertEqual(self.module.WORKING_CROP_BYTE_COUNT, 16)
        self.assertEqual(self.module.FLOAT_INPUT_BYTE_COUNT, 32)
        self.assertEqual(self.module.STORE_SIMD_REGISTER_NAMES, ("v0",))
        source = inspect.getsource(self.module.nested_crop_store)
        self.assertIn("STORE_SIMD_REGISTER_NAMES", source)
        self.assertIn("ROLE_STATE_BYTE_COUNT", source)

    def test_no_watchpoint_or_instruction_stepping_is_present(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("WatchAddress", source)
        self.assertNotIn("DeleteWatchpoint", source)
        self.assertNotIn("StepInstruction", source)
        self.assertNotIn("StepOut", source)


if __name__ == "__main__":
    unittest.main()
