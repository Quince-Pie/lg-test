#!/usr/bin/env python3
"""Portable source tests for the multi-state crop-transfer LLDB probe."""

import importlib.util
import inspect
import sys
import types
import unittest
from pathlib import Path

import validate_prepare_layer_crop_transfer as validator


ANALYSIS_ROOT = Path(__file__).resolve().parent
MODULE_PATH = ANALYSIS_ROOT / "capture_prepare_layer_crop_transfer_lldb.py"
BASE_MODULE_NAME = "capture_prepare_layer_full_path_trace_lldb"


def load_with_stub_lldb():
    module_name = "capture_prepare_layer_crop_transfer_source_test"
    specification = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError("crop-transfer LLDB module spec is unavailable")
    module = importlib.util.module_from_spec(specification)
    previous_lldb = sys.modules.get("lldb")
    previous_base = sys.modules.pop(BASE_MODULE_NAME, None)
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
        if previous_base is None:
            sys.modules.pop(BASE_MODULE_NAME, None)
        else:
            sys.modules[BASE_MODULE_NAME] = previous_base
    return module


class PrepareLayerCropTransferSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_with_stub_lldb()

    def setUp(self):
        self.module._reset_state()
        self.module._state["trace"] = self.module._new_trace()

    def test_configuration_is_byte_for_byte_aligned_with_validator(self):
        self.assertEqual(
            self.module._new_trace()["configuration"],
            validator.EXPECTED_CONFIGURATION,
        )

    def test_only_the_opened_exact_marker_is_installed(self):
        source = inspect.getsource(self.module.prepare_layer_entry)
        self.assertEqual(self.module.MARKER_OFFSET, 0x3EF0)
        self.assertEqual(
            self.module.MARKER_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX,
            "28330b91",
        )
        self.assertIn("PREPARE_LAYER_FULL_CODE_SHA256", source)
        self.assertIn("KNOWN_PREPARE_LAYER_WINDOWS", source)
        self.assertIn("MARKER_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX", source)
        self.assertIn('"crop_transfer_marker"', source)
        self.assertNotIn("capture_backdrop", source)

    def test_selection_is_structural_and_crop_value_independent(self):
        source = inspect.getsource(self.module.crop_transfer_marker)
        caller_index = source.index("_direct_timeline_caller")
        depth_index = source.index("depth != REQUIRED_PREPARE_RECURSION_DEPTH")
        role_index = source.index('role_base = values["x19"]')
        self.assertLess(caller_index, role_index)
        self.assertLess(depth_index, role_index)
        prefix = source[:role_index]
        self.assertNotIn("ROLE_AGGREGATE", prefix)
        self.assertNotIn("struct.unpack", prefix)
        self.assertNotIn("ROLE_WORKING_CROP_OFFSET", prefix)

    def test_direct_timeline_caller_excludes_all_interventions(self):
        direct = [
            "main.carendererUniformEvidence(",
            "main.localTransitionCARendererEvidence(",
            "main.transitionBackgroundUniformEvidence(",
        ]
        self.assertTrue(self.module._direct_timeline_caller(direct))
        for excluded in self.module.EXCLUDED_CALLER_FRAGMENTS:
            self.assertFalse(
                self.module._direct_timeline_caller(direct + [excluded])
            )
        self.assertFalse(
            self.module._direct_timeline_caller(direct[:-1])
        )

    def test_structural_depth_does_not_read_register_or_role_state(self):
        source = inspect.getsource(self.module._exact_prepare_frames)
        self.assertIn("candidate.GetFunctionName()", source)
        self.assertIn("candidate.GetSymbol()", source)
        self.assertIn("candidate.GetFP()", source)
        self.assertNotIn("_register", source)
        self.assertNotIn("ReadMemory", source)

    def test_unavailable_x30_is_excluded_without_removing_crop_inputs(self):
        expected_general = tuple("x%d" % index for index in range(30)) + (
            "sp",
            "pc",
            "cpsr",
        )
        self.assertEqual(
            self.module.GENERAL_REGISTER_NAMES,
            expected_general,
        )
        self.assertEqual(
            self.module.PREPARE_FRAME_REGISTER_NAMES,
            ("x19", "x28", "x29", "sp", "pc"),
        )
        self.assertNotIn("x30", self.module.GENERAL_REGISTER_NAMES)
        self.assertNotIn("x30", self.module.PREPARE_FRAME_REGISTER_NAMES)
        self.assertTrue(
            {"x19", "x28", "x29", "sp", "pc"}.issubset(
                self.module.GENERAL_REGISTER_NAMES
            )
        )
        self.assertFalse(hasattr(self.module, "_register_record"))

    def test_hardware_watchpoints_and_instruction_stepping_are_absent(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("WatchAddress", source)
        self.assertNotIn("DeleteWatchpoint", source)
        self.assertNotIn("StepInstruction", source)
        self.assertNotIn("StepOut", source)

    def test_every_qualified_record_keeps_all_four_role_snapshots(self):
        source = inspect.getsource(self.module.crop_transfer_marker)
        frame_source = inspect.getsource(self.module._prepare_frame_snapshot)
        self.assertIn("for item in exact", source)
        self.assertIn('"prepareFrames": prepare_frames', source)
        self.assertIn("ROLE_STATE_BYTE_COUNT", frame_source)
        self.assertIn("PREPARE_FRAME_REGISTER_NAMES", frame_source)

    def test_finalize_preserves_fail_closed_accounting(self):
        source = inspect.getsource(self.module.finalize)
        for token in (
            "finalMarkerHitCount",
            "finalQualifiedRecordCount",
            "finalRejectedMarkerCount",
            "finalDiscardedQualifiedRecordCount",
            "finalUnretainedRejectionCount",
            "finalFailureCount",
            "terminalProcess",
        ):
            self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main()
