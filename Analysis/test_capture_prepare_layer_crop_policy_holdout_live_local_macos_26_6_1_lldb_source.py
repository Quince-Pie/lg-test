#!/usr/bin/env python3
"""Source tests for the active-M1 crop callback overlay."""

import importlib.util
import inspect
import sys
import types
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
MODULE_PATH = (
    ANALYSIS_ROOT
    / "capture_prepare_layer_crop_policy_holdout_live_local_macos_26_6_1_lldb.py"
)
MODULE_NAMES = (
    "capture_prepare_layer_crop_policy_holdout_lldb",
    "capture_prepare_layer_crop_union_operand_lldb",
    "capture_prepare_layer_crop_transfer_lldb",
    "capture_prepare_layer_full_path_trace_lldb",
    "prepare_layer_live_transport_local_macos_26_6_1",
)


def load_with_stub_lldb():
    module_name = "capture_prepare_layer_live_source_test"
    specification = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError("active-M1 crop module spec is unavailable")
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


class PrepareLayerLiveCaptureSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_with_stub_lldb()

    def test_all_dynamic_callbacks_are_exported(self) -> None:
        source = inspect.getsource(self.module._install_callback_proxies)
        for callback in (
            "prepare_layer_entry",
            "crop_transfer_marker",
            "crop_union_call",
            "crop_union_return",
            "nested_crop_store",
        ):
            self.assertIn(callback, source)

    def test_uuid_is_checked_before_inherited_entry(self) -> None:
        source = inspect.getsource(self.module.prepare_layer_entry)
        self.assertLess(
            source.index("_record_live_identity"),
            source.index("holdout_base.prepare_layer_entry"),
        )

    def test_overlay_adds_no_breakpoint_or_memory_read(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("BreakpointCreate", source)
        self.assertNotIn("ReadMemory", source)
        self.assertNotIn("_memory_snapshot", source)
        self.assertNotIn("WatchAddress", source)
        self.assertNotIn("StepInstruction", source)

    def test_finalize_preserves_inherited_capture(self) -> None:
        source = inspect.getsource(self.module.finalize)
        self.assertLess(
            source.index("holdout_base.finalize()"),
            source.index("live.rewrite_capture_trace"),
        )


if __name__ == "__main__":
    unittest.main()
