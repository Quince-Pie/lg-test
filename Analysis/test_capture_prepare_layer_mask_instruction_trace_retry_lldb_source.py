#!/usr/bin/env python3
"""Source tests for the namespace-only helper-body trace retry."""

from __future__ import annotations

import importlib.util
import inspect
import sys
import types
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
MODULE_PATH = (
    ANALYSIS_ROOT / "capture_prepare_layer_mask_instruction_trace_retry_lldb.py"
)
MODULE_NAMES = (
    "capture_prepare_layer_mask_instruction_trace_retry_lldb",
    "capture_prepare_layer_mask_instruction_trace_lldb",
    "capture_prepare_layer_crop_policy_holdout_callback_retry_lldb",
    "capture_prepare_layer_crop_policy_holdout_lldb",
    "capture_prepare_layer_crop_union_operand_lldb",
    "capture_prepare_layer_crop_transfer_lldb",
    "capture_prepare_layer_full_path_trace_lldb",
)


def load_with_stub_lldb():
    module_name = "capture_prepare_layer_mask_retry_source_test"
    specification = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError("prepare_layer_mask retry module spec is unavailable")
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


class PrepareLayerMaskInstructionTraceRetrySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_with_stub_lldb()

    def test_constant_alias_is_installed_before_the_immutable_base_init(self):
        source = inspect.getsource(getattr(self.module, "__lldb_init_module"))
        self.assertIn(
            "base.crop_base.PREPARE_LAYER_FUNCTION = "
            "base.capture_base.PREPARE_LAYER_FUNCTION",
            source,
        )
        self.assertLess(
            source.index("base.crop_base.PREPARE_LAYER_FUNCTION"),
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

    def test_entry_rebinds_callbacks_after_dynamic_base_installation(self):
        source = inspect.getsource(self.module.prepare_layer_entry)
        self.assertLess(
            source.index("base.prepare_layer_entry"),
            source.index("_install_callback_proxies"),
        )

    def test_proxy_callbacks_forward_without_inspecting_capture_values(self):
        forwarding = (
            ("crop_union_call", "base.crop_union_call"),
            ("crop_union_return", "base.crop_union_return"),
            ("nested_crop_store", "base.nested_crop_store"),
            ("crop_transfer_marker", "base.crop_transfer_marker"),
            ("prepare_layer_mask_entry", "base.prepare_layer_mask_entry"),
        )
        for name, target in forwarding:
            source = inspect.getsource(getattr(self.module, name))
            self.assertIn(target, source)
            self.assertNotIn("unpack", source)
            self.assertNotIn("roleState", source)
            self.assertNotIn("outputLayerShapes", source)

    def test_retry_adds_no_capture_or_stepping_mechanism(self):
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

    def test_manual_trace_and_finalize_delegate_unchanged(self):
        self.assertIn(
            "base.trace_selected_helper()",
            inspect.getsource(self.module.trace_selected_helper),
        )
        self.assertIn("base.finalize()", inspect.getsource(self.module.finalize))


if __name__ == "__main__":
    unittest.main()
