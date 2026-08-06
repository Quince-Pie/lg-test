#!/usr/bin/env python3
"""Portable source tests for the bounded prepare_layer_mask LLDB trace."""

from __future__ import annotations

import importlib.util
import inspect
import sys
import types
import unittest
from pathlib import Path

import validate_prepare_layer_mask_instruction_trace as validator


ANALYSIS_ROOT = Path(__file__).resolve().parent
MODULE_PATH = ANALYSIS_ROOT / "capture_prepare_layer_mask_instruction_trace_lldb.py"
MODULE_NAMES = (
    "capture_prepare_layer_mask_instruction_trace_lldb",
    "capture_prepare_layer_crop_policy_holdout_callback_retry_lldb",
    "capture_prepare_layer_crop_policy_holdout_lldb",
    "capture_prepare_layer_crop_union_operand_lldb",
    "capture_prepare_layer_crop_transfer_lldb",
    "capture_prepare_layer_full_path_trace_lldb",
)


def load_with_stub_lldb():
    module_name = "capture_prepare_layer_mask_instruction_source_test"
    specification = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError("prepare_layer_mask LLDB module spec is unavailable")
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


class PrepareLayerMaskInstructionTraceSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_with_stub_lldb()

    def test_configuration_is_byte_for_byte_aligned_with_validator(self) -> None:
        self.assertEqual(
            self.module._new_extension_trace()["configuration"],
            validator.EXPECTED_CONFIGURATION,
        )

    def test_target_is_the_preopened_bounded_helper(self) -> None:
        module = self.module
        self.assertEqual(module.HELPER_FUNCTION, validator.HELPER_FUNCTION)
        self.assertEqual(module.HELPER_RELATIVE_TO_PREPARE_LAYER, -1_209_388)
        self.assertEqual(module.HELPER_SYMBOL_BYTE_COUNT, 2_176)
        self.assertEqual(module.CALL_OFFSET, 0xD90)
        self.assertEqual(module.CALL_RETURN_OFFSET, 0xD94)
        self.assertEqual(module.CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX, "915ffb97")

    def test_selection_is_frozen_before_any_output_snapshot(self) -> None:
        source = inspect.getsource(self.module.prepare_layer_mask_entry)
        self.assertIn("TARGET_MARKER_INTERVAL", source)
        self.assertIn("TARGET_QUALIFIED_ORDINAL", source)
        self.assertIn("selected_by_ordinal", source)
        self.assertIn("role_offsets_match", source)
        self.assertIn("selectedByFrozenRule", source)
        self.assertLess(
            source.index("selected_by_ordinal ="),
            source.index('"entryStack": _snapshot'),
        )
        prefix = source[: source.index("if selected_by_ordinal:")]
        self.assertNotIn("roleState", prefix)
        self.assertNotIn("outputLayerShapesAtEntry", prefix)
        self.assertNotIn("struct.unpack", source)
        self.assertNotIn("fromhex", source)

    def test_every_dynamic_breakpoint_callback_is_top_level_visible(self) -> None:
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

    def test_helper_code_is_captured_before_breakpoint_installation(self) -> None:
        source = inspect.getsource(self.module._install_extension)
        self.assertIn("HELPER_SYMBOL_BYTE_COUNT", source)
        self.assertIn("hashlib.sha256(code)", source)
        self.assertIn('"hex": code.hex()', source)
        self.assertLess(
            source.index('"prepare_layer_mask complete code"'),
            source.index("_address_breakpoint("),
        )

    def test_instruction_trace_is_complete_and_watchpoint_free(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn("SetAsync(False)", source)
        self.assertIn("DisableAllBreakpoints", source)
        self.assertIn("StepInstruction(False, error)", source)
        self.assertIn("StepOut(error)", source)
        self.assertIn("_full_register_snapshot", source)
        self.assertIn('"stackBefore"', source)
        self.assertIn('"outputBefore"', source)
        self.assertIn('"outputAfter"', source)
        self.assertNotIn("WatchAddress", source)
        self.assertNotIn("DeleteWatchpoint", source)

    def test_helper_breakpoint_stays_disabled_after_base_breakpoints_restore(self) -> None:
        source = inspect.getsource(self.module._restore_breakpoints)
        self.assertIn("identifier != helper_id", source)
        self.assertIn('"helperEntryDeliberatelyDisabled"', source)
        self.assertIn('"enabledAfterRestore"', source)

    def test_qword_change_detection_is_bit_exact(self) -> None:
        before = bytes(32)
        after = bytearray(before)
        after[7] = 1
        after[16] = 1
        self.assertEqual(
            self.module._changed_qword_offsets(before, bytes(after)), [0, 16]
        )

    def test_finalize_seals_extension_before_inherited_finalizer(self) -> None:
        source = inspect.getsource(self.module.finalize)
        self.assertLess(
            source.index('extension["status"] = "finalized"'),
            source.index("holdout_retry.finalize()"),
        )
        self.assertIn('extension["finalFailureCount"]', source)


if __name__ == "__main__":
    unittest.main()
