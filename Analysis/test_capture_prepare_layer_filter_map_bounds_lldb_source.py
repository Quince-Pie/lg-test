#!/usr/bin/env python3
"""Source contracts for the output-blind FilterOp map-bounds trace."""

from __future__ import annotations

import importlib.util
import inspect
import sys
import types
import unittest
from pathlib import Path

import validate_prepare_layer_filter_map_bounds as validator


ANALYSIS_ROOT = Path(__file__).resolve().parent
MODULE_PATH = ANALYSIS_ROOT / "capture_prepare_layer_filter_map_bounds_lldb.py"
MODULE_NAMES = (
    "capture_prepare_layer_filter_map_bounds_lldb",
    "capture_prepare_layer_crop_producer_callee_lldb",
    "capture_prepare_layer_mask_inventory_calibration_lldb",
    "capture_prepare_layer_mask_instruction_trace_lldb",
    "capture_prepare_layer_crop_policy_holdout_callback_retry_lldb",
    "capture_prepare_layer_crop_policy_holdout_lldb",
    "capture_prepare_layer_crop_union_operand_lldb",
    "capture_prepare_layer_crop_transfer_lldb",
    "capture_prepare_layer_full_path_trace_lldb",
)


def load_with_stub_lldb():
    module_name = "capture_prepare_layer_filter_map_bounds_source_test"
    specification = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError("FilterOp LLDB module spec is unavailable")
    module = importlib.util.module_from_spec(specification)
    previous_lldb = sys.modules.get("lldb")
    previous_modules = {name: sys.modules.pop(name, None) for name in MODULE_NAMES}
    stub = types.ModuleType("lldb")
    stub.LLDB_INVALID_ADDRESS = (1 << 64) - 1
    stub.eStateStopped = 5
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


class PrepareLayerFilterMapBoundsSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_with_stub_lldb()
        cls.module.selected_base._target_ordinal = 14

    def test_capture_and_validator_freeze_the_same_configuration(self):
        extension = self.module._new_extension_trace()
        self.assertEqual(extension["configuration"], validator.EXPECTED_CONFIGURATION)

    def test_structural_target_is_the_fourth_authenticated_dispatch(self):
        self.assertEqual(self.module.DYNAMIC_CALL_OFFSET, 0x2864)
        self.assertEqual(self.module.DYNAMIC_RETURN_OFFSET, 0x2868)
        self.assertEqual(self.module.DYNAMIC_CALL_RAW_LITTLE_ENDIAN_HEX, "10093fd7")
        self.assertEqual(self.module.TARGET_DISPATCH_ORDINAL, 4)
        self.assertEqual(
            list(self.module.EXPECTED_DISPATCH_FUNCTIONS),
            validator.EXPECTED_DISPATCH_FUNCTIONS,
        )

    def test_filter_identity_is_frozen_before_dispatch(self):
        self.assertEqual(self.module.FILTER_RELATIVE_TO_PREPARE_LAYER, -61056)
        self.assertEqual(self.module.FILTER_SYMBOL_BYTE_COUNT, 788)
        self.assertEqual(
            self.module.FILTER_CODE_SHA256,
            "e8766dcefdadc0074f7bb4e2bf62955072891858009dca6c72a7eef1c96789d0",
        )
        source = inspect.getsource(self.module._capture_filter_identity)
        self.assertIn("observed_sha != FILTER_CODE_SHA256", source)
        self.assertIn('"expectedSHA256": FILTER_CODE_SHA256', source)

    def test_dispatch_selector_never_reads_crop_or_output_values(self):
        source = inspect.getsource(self.module._record_dispatch)
        for forbidden in (
            "outputBefore",
            "outputAfter",
            "callerRoleBefore",
            "callerRoleAfter",
            "struct.unpack",
        ):
            self.assertNotIn(forbidden, source)
        configuration = self.module._new_extension_trace()["configuration"]
        self.assertFalse(configuration["cropValuesUsedForSelection"])
        self.assertFalse(configuration["outputValuesUsedForSelection"])

    def test_trace_opens_every_filter_instruction_and_other_callee_boundary(self):
        source = inspect.getsource(self.module.trace_selected_filter_map_bounds)
        opened = inspect.getsource(self.module._trace_opened_scope_instruction)
        self.assertIn('"producerCallee"', opened)
        self.assertIn("producer_base._trace_instruction", opened)
        self.assertIn("_trace_opened_scope_instruction", source)
        self.assertIn("producer_base._trace_opaque_callee", source)
        self.assertIn("FILTER_OBJECT_BYTE_COUNT", source)
        self.assertIn("MAXIMUM_FILTER_INSTRUCTION_COUNT", source)

    def test_extension_adds_no_breakpoint_or_watchpoint(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        for forbidden in ("BreakpointCreate", "WatchAddress"):
            self.assertNotIn(forbidden, source)
        self.assertIn("_install_callback_proxies", source)

    def test_every_dynamic_callback_is_top_level_visible(self):
        source = inspect.getsource(self.module._install_callback_proxies)
        for callback in (
            "prepare_layer_entry",
            "crop_transfer_marker",
            "crop_union_call",
            "crop_union_return",
            "nested_crop_store",
            "prepare_layer_mask_entry",
        ):
            self.assertIn(callback, source)
        entry = inspect.getsource(self.module.prepare_layer_entry)
        self.assertLess(
            entry.index("selected_base.prepare_layer_entry"),
            entry.index("_install_callback_proxies"),
        )

    def test_finalization_seals_extension_before_inherited_trace(self):
        source = inspect.getsource(self.module.finalize)
        self.assertLess(
            source.index('extension["status"] = "finalized"'),
            source.index("selected_base.finalize()"),
        )


if __name__ == "__main__":
    unittest.main()
