#!/usr/bin/env python3
"""Source contracts for the output-blind post-mask callee trace."""

from __future__ import annotations

import importlib.util
import inspect
import sys
import types
import unittest
from pathlib import Path

import validate_prepare_layer_crop_producer_callee as validator


ANALYSIS_ROOT = Path(__file__).resolve().parent
MODULE_PATH = ANALYSIS_ROOT / "capture_prepare_layer_crop_producer_callee_lldb.py"
MODULE_NAMES = (
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
    module_name = "capture_prepare_layer_crop_producer_callee_source_test"
    specification = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError("crop producer callee LLDB module spec is unavailable")
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


class PrepareLayerCropProducerCalleeSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_with_stub_lldb()
        cls.module.selected_base._target_ordinal = 14

    def test_capture_and_validator_freeze_the_same_configuration(self):
        extension = self.module._new_extension_trace()
        self.assertEqual(extension["configuration"], validator.EXPECTED_CONFIGURATION)
        self.assertIsNone(extension["configuration"]["calleeExpectedSHA256"])

    def test_target_is_the_static_second_post_mask_call(self):
        self.assertEqual(self.module.CALLER_CONTINUATION_START_OFFSET, 0xD94)
        self.assertEqual(self.module.PRODUCER_CALLEE_CALL_OFFSET, 0xF5C)
        self.assertEqual(self.module.PRODUCER_CALLEE_RETURN_OFFSET, 0xF60)
        self.assertEqual(
            self.module.PRODUCER_CALLEE_RELATIVE_TO_PREPARE_LAYER,
            -1_206_100,
        )
        self.assertEqual(
            self.module.PRODUCER_CALLEE_CALL_RAW_LITTLE_ENDIAN_HEX,
            "5462fb97",
        )

    def test_extension_adds_no_breakpoint_or_watchpoint(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        for forbidden in ("BreakpointCreate", "WatchAddress"):
            self.assertNotIn(forbidden, source)
        configuration = self.module._new_extension_trace()["configuration"]
        self.assertFalse(configuration["hardwareWatchpointsUsed"])
        self.assertFalse(configuration["cropValuesUsedForSelection"])

    def test_instruction_trace_keeps_register_stack_and_memory_pairs(self):
        source = inspect.getsource(self.module._trace_instruction)
        for required in (
            "_full_register_snapshot(frame)",
            '"stackBefore"',
            '"registersAfter"',
            '"stackAfter"',
            '"outputBefore"',
            '"outputAfter"',
            '"callerRoleBefore"',
            '"callerRoleAfter"',
            "StepInstruction(False, error)",
        ):
            self.assertIn(required, source)

    def test_every_other_callee_is_an_explicit_boundary(self):
        source = inspect.getsource(self.module._trace_opaque_callee)
        for required in (
            "StepOut(error)",
            '"entryFrame"',
            '"returnFrame"',
            '"registersAtEntry"',
            '"registersAtReturn"',
            '"stackAtEntry"',
            '"stackAtReturn"',
        ):
            self.assertIn(required, source)

    def test_trace_checkpoints_are_bounded_not_mutation_driven(self):
        instruction = inspect.getsource(self.module._trace_instruction)
        boundary = inspect.getsource(self.module._trace_opaque_callee)
        self.assertIn("TRACE_CHECKPOINT_INSTRUCTION_INTERVAL", instruction)
        self.assertIn("TRACE_CHECKPOINT_BOUNDARY_INTERVAL", boundary)
        self.assertNotIn('state["outputChanged"] or', instruction)

    def test_call_arguments_are_structural_and_output_blind(self):
        source = inspect.getsource(self.module.trace_selected_producer_callee)
        self.assertIn(
            "raw_call.hex() != PRODUCER_CALLEE_CALL_RAW_LITTLE_ENDIAN_HEX", source
        )
        self.assertIn('call_values["x1"]', source)
        self.assertIn('call_values["x19"] + CALLER_LOCAL_STATE_OFFSET', source)
        self.assertIn(
            'call_values["x3"] != base._state["selected"]["outputAddress"]', source
        )
        self.assertIn('"cropValuesUsedForSelection": False', source)

    def test_first_run_captures_complete_unknown_callee_code(self):
        source = inspect.getsource(self.module._capture_callee_identity)
        self.assertIn("symbol.GetStartAddress()", source)
        self.assertIn("symbol.GetEndAddress()", source)
        self.assertIn('"crop producer callee complete code"', source)
        self.assertIn('"expectedSHA256": None', source)
        self.assertIn("hashlib.sha256(code).hexdigest()", source)

    def test_finalization_seals_extension_before_inherited_trace(self):
        source = inspect.getsource(self.module.finalize)
        self.assertLess(
            source.index('extension["status"] = "finalized"'),
            source.index("selected_base.finalize()"),
        )


if __name__ == "__main__":
    unittest.main()
