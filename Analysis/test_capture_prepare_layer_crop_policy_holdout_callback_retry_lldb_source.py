#!/usr/bin/env python3
"""Source tests for the crop-policy LLDB callback-visibility retry."""

from __future__ import annotations

import importlib.util
import inspect
import sys
import types
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
MODULE_PATH = (
    ANALYSIS_ROOT / "capture_prepare_layer_crop_policy_holdout_callback_retry_lldb.py"
)
MODULE_NAMES = (
    "capture_prepare_layer_crop_policy_holdout_callback_retry_lldb",
    "capture_prepare_layer_crop_policy_holdout_lldb",
    "capture_prepare_layer_crop_union_operand_lldb",
    "capture_prepare_layer_crop_transfer_lldb",
    "capture_prepare_layer_full_path_trace_lldb",
)


def load_with_stub_lldb():
    module_name = "capture_crop_policy_callback_retry_source_test"
    specification = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError("callback-retry LLDB module spec is unavailable")
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


class PrepareLayerCropPolicyCallbackRetrySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_with_stub_lldb()

    def test_every_dynamically_installed_breakpoint_is_proxied(self):
        source = inspect.getsource(self.module._install_callback_proxies)
        for state_name, callback in (
            ("prepareEntryBreakpoint", "prepare_layer_entry"),
            ("markerBreakpoint", "crop_transfer_marker"),
            ("unionCallBreakpoint", "crop_union_call"),
            ("unionReturnBreakpoint", "crop_union_return"),
            ("storeBreakpoint", "nested_crop_store"),
        ):
            self.assertIn(state_name, source)
            self.assertIn(callback, source)

    def test_entry_installs_proxies_after_the_immutable_base_entry(self):
        source = inspect.getsource(self.module.prepare_layer_entry)
        self.assertLess(
            source.index("holdout_base.prepare_layer_entry"),
            source.index("_install_callback_proxies"),
        )

    def test_proxy_callbacks_forward_without_inspecting_values(self):
        forwarding = (
            ("crop_union_call", "holdout_base.union_base.crop_union_call"),
            ("crop_union_return", "holdout_base.union_base.crop_union_return"),
            ("nested_crop_store", "holdout_base.nested_crop_store"),
            ("crop_transfer_marker", "holdout_base.crop_transfer_marker"),
        )
        for name, target in forwarding:
            source = inspect.getsource(getattr(self.module, name))
            self.assertIn(target, source)
            self.assertNotIn("struct", source)
            self.assertNotIn("unpack", source)
            self.assertNotIn("roleState", source)

    def test_retry_contains_no_capture_policy_or_new_breakpoint(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("BreakpointCreate", source)
        self.assertNotIn("ReadMemory", source)
        self.assertNotIn("_memory_snapshot", source)
        self.assertNotIn("WatchAddress", source)
        self.assertNotIn("StepInstruction", source)

    def test_finalize_delegates_unchanged(self):
        source = inspect.getsource(self.module.finalize)
        self.assertIn("holdout_base.finalize()", source)


if __name__ == "__main__":
    unittest.main()
