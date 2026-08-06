#!/usr/bin/env python3
"""Source tests for the two-pass helper-role calibration transport."""

from __future__ import annotations

import importlib.util
import inspect
import sys
import types
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
MODULE_PATH = ANALYSIS_ROOT / "capture_prepare_layer_mask_inventory_calibration_lldb.py"
MODULE_NAMES = (
    "capture_prepare_layer_mask_inventory_calibration_lldb",
    "capture_prepare_layer_mask_instruction_trace_lldb",
    "capture_prepare_layer_crop_policy_holdout_callback_retry_lldb",
    "capture_prepare_layer_crop_policy_holdout_lldb",
    "capture_prepare_layer_crop_union_operand_lldb",
    "capture_prepare_layer_crop_transfer_lldb",
    "capture_prepare_layer_full_path_trace_lldb",
)


def load_with_stub_lldb():
    module_name = "capture_prepare_layer_mask_inventory_source_test"
    specification = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError("inventory calibration LLDB module spec is unavailable")
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


class PrepareLayerMaskInventoryCalibrationSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_with_stub_lldb()

    def test_inventory_sentinel_cannot_select_a_bounded_entry(self):
        self.assertEqual(self.module.INVENTORY_SENTINEL_ORDINAL, 4097)
        self.assertGreater(
            self.module.INVENTORY_SENTINEL_ORDINAL,
            self.module.base.MAXIMUM_QUALIFIED_HELPER_ENTRY_COUNT,
        )

    def test_selected_mode_reads_only_validated_structural_ordinal_metadata(self):
        source = inspect.getsource(self.module._load_configuration)
        self.assertIn("sample2TargetQualifiedOrdinal", source)
        self.assertIn("allHelperEntriesRetainedWithoutSelection", source)
        self.assertIn("sample2ProducerRoleMappedByLastPriorHelper", source)
        self.assertIn("cropOrOutputValuesUsedForSelection", source)
        self.assertNotIn("producerHex", source)
        self.assertNotIn("outputLayerShapes", source)
        self.assertNotIn("struct.unpack", source)

    def test_constant_and_target_are_installed_before_base_initialization(self):
        source = inspect.getsource(getattr(self.module, "__lldb_init_module"))
        self.assertLess(
            source.index("base.crop_base.PREPARE_LAYER_FUNCTION"),
            source.index("base.__lldb_init_module"),
        )
        self.assertLess(
            source.index("base.TARGET_QUALIFIED_ORDINAL"),
            source.index("base.__lldb_init_module"),
        )

    def test_every_dynamic_breakpoint_callback_is_proxied(self):
        source = inspect.getsource(self.module._install_callback_proxies)
        for state_name, callback in (
            ("prepareEntryBreakpoint", "prepare_layer_entry"),
            ("markerBreakpoint", "crop_transfer_marker"),
            ("unionCallBreakpoint", "crop_union_call"),
            ("unionReturnBreakpoint", "crop_union_return"),
            ("storeBreakpoint", "nested_crop_store"),
            ("helperBreakpoint", "prepare_layer_mask_entry"),
        ):
            self.assertIn(state_name, source)
            self.assertIn(callback, source)

    def test_transport_adds_no_capture_or_stepping_mechanism(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "BreakpointCreate",
            "ReadMemory",
            "_memory_snapshot",
            "WatchAddress",
            "StepInstruction",
            "StepOut",
        ):
            self.assertNotIn(forbidden, source)

    def test_cross_callback_order_uses_only_record_identity(self):
        source = "\n".join(
            inspect.getsource(getattr(self.module, name))
            for name in (
                "_append_callback_event",
                "nested_crop_store",
                "crop_transfer_marker",
                "prepare_layer_mask_entry",
            )
        )
        self.assertIn("storeRecordIndex", source)
        self.assertIn("helperRecordIndex", source)
        self.assertIn("callerRoleBase", source)
        self.assertIn("prepareRecursionDepth", source)
        self.assertNotIn("roleState", source)
        self.assertNotIn("floatingInput", source)
        self.assertNotIn("outputLayerShapesAt", source)
        self.assertNotIn("struct.unpack", source)

    def test_manual_trace_is_rejected_in_inventory_mode(self):
        source = inspect.getsource(self.module.trace_selected_helper)
        self.assertIn("_mode != SELECTED_MODE", source)
        self.assertIn("base.trace_selected_helper()", source)


if __name__ == "__main__":
    unittest.main()
