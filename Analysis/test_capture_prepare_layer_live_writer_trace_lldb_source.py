#!/usr/bin/env python3
"""Portable source tests for the live-qualified writer LLDB probe."""

import importlib.util
import inspect
import sys
import types
import unittest
from pathlib import Path

import validate_prepare_layer_live_writer_trace as validator


ANALYSIS_ROOT = Path(__file__).resolve().parent
MODULE_PATH = ANALYSIS_ROOT / "capture_prepare_layer_live_writer_trace_lldb.py"
BASE_MODULE_NAME = "capture_prepare_layer_full_path_trace_lldb"


def load_with_stub_lldb():
    module_name = "capture_prepare_layer_live_writer_trace_lldb_source_test"
    specification = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError("LLDB live-writer module spec is unavailable")
    module = importlib.util.module_from_spec(specification)
    previous_lldb = sys.modules.get("lldb")
    previous_base = sys.modules.pop(BASE_MODULE_NAME, None)
    stub = types.ModuleType("lldb")
    stub.LLDB_INVALID_ADDRESS = (1 << 64) - 1
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


class FakeAddress:
    def __init__(self, value):
        self.value = value

    def GetLoadAddress(self, _target):
        return self.value


class FakeSymbol:
    def __init__(self, start, end, *, valid=True):
        self.start = start
        self.end = end
        self.valid = valid

    def IsValid(self):
        return self.valid

    def GetStartAddress(self):
        return FakeAddress(self.start)

    def GetEndAddress(self):
        return FakeAddress(self.end)


class FakeRegister:
    def __init__(self, value, *, valid=True):
        self.value = value
        self.valid = valid

    def IsValid(self):
        return self.valid

    def GetValueAsUnsigned(self, _default):
        return self.value


class FakeFrame:
    def __init__(self, function, start, end, registers):
        self.function = function
        self.symbol = FakeSymbol(start, end)
        self.registers = registers

    def GetFunctionName(self):
        return self.function

    def GetSymbol(self):
        return self.symbol

    def FindRegister(self, name):
        value = self.registers.get(name)
        return FakeRegister(0, valid=False) if value is None else FakeRegister(value)


class FakeProcess:
    def __init__(self):
        self.target = object()

    def GetTarget(self):
        return self.target


class FakeThread:
    def __init__(self, frames):
        self.frames = frames
        self.process = FakeProcess()

    def GetProcess(self):
        return self.process

    def GetNumFrames(self):
        return len(self.frames)

    def GetFrameAtIndex(self, index):
        return self.frames[index]


class PrepareLayerLiveWriterLLDBSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_with_stub_lldb()

    def setUp(self):
        module = self.module
        module._state["objectAddresses"] = {}
        module._state["prepareLayer"] = None
        module._state["callbackSequence"] = 0
        module._state["markerHitCount"] = 0
        module._state["rejectedMarkerHitCount"] = 0
        module._state["discardedMarkerHitCount"] = 0
        module._state["rawWatchpointHitCount"] = 0
        module._state["ignoredWatchpointHitCount"] = 0
        module._state["ignoredPrepareFrameSeenCount"] = 0
        module._state["unretainedIgnoredWatchpointHitCount"] = 0
        module._state["qualifiedWatchpointHitCount"] = 0
        module._state["ignoredWatchpointGroups"] = {}
        module._state["trace"] = module._new_trace()

    def test_complete_code_and_live_marker_are_frozen(self):
        module = self.module
        self.assertEqual(module.TRACE_SCHEMA_VERSION, 1)
        self.assertEqual(module.PREPARE_LAYER_FULL_CODE_SHA256, validator.PREPARE_LAYER_FULL_CODE_SHA256)
        self.assertEqual(module.LIVE_ARM_MARKER_NAME, "sourceLaterHandle")
        self.assertEqual(module.LIVE_ARM_MARKER_OFFSET, 0x3EF0)
        self.assertEqual(module.MAXIMUM_PRESELECTION_MARKER_RECORD_COUNT, 32)

    def test_watchpoint_limits_leave_unrelated_hits_diagnostic_only(self):
        module = self.module
        self.assertEqual(module.MAXIMUM_RAW_WATCHPOINT_HIT_COUNT, 8192)
        self.assertEqual(module.MAXIMUM_IGNORED_WATCHPOINT_DIAGNOSTIC_COUNT, 64)
        self.assertEqual(module.MAXIMUM_QUALIFIED_WATCHPOINT_EVENT_COUNT, 24)
        self.assertEqual(module.PREPARE_FRAME_REGISTER_NAMES, ("x19", "x28", "x29", "x30", "sp", "pc"))

    def test_harness_and_validator_configuration_are_byte_for_byte_aligned(self):
        self.assertEqual(
            self.module._new_trace()["configuration"],
            validator.EXPECTED_CONFIGURATION,
        )

    def test_source_selection_never_arms_retrospectively(self):
        late_source = inspect.getsource(self.module.capture_backdrop_late)
        marker_source = inspect.getsource(self.module.prepare_layer_live_arm_marker)
        self.assertNotIn("_install_live_watchpoint", late_source)
        self.assertIn("_install_live_watchpoint", marker_source)
        self.assertFalse(hasattr(self.module, "_retrospective_watchpoint_candidate"))

    def test_matching_frame_requires_both_live_unwound_roles(self):
        module = self.module
        start = 0x1_9000_0000
        end = start + module.capture_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT
        role = 0x1_7000_1000
        source = 0x9_8000_0000
        helper = FakeFrame("helper", start - 0x1000, start, {})
        wrong = FakeFrame(
            module.capture_base.PREPARE_LAYER_FUNCTION,
            start,
            end,
            {"x19": role + 0x800, "x28": source},
        )
        exact = FakeFrame(
            module.capture_base.PREPARE_LAYER_FUNCTION,
            start,
            end,
            {"x19": role, "x28": source},
        )
        module._state["prepareLayer"] = {"symbolStart": start, "symbolEnd": end}
        frame, index, saw_exact = module._matching_prepare_frame(
            FakeThread([helper, wrong, exact]),
            {"roleBase": role, "selectedSource": source},
        )
        self.assertIs(frame, exact)
        self.assertEqual(index, 2)
        self.assertTrue(saw_exact)

    def test_stale_prepare_frame_is_seen_but_not_qualified(self):
        module = self.module
        start = 0x1_9000_0000
        end = start + module.capture_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT
        stale = FakeFrame(
            module.capture_base.PREPARE_LAYER_FUNCTION,
            start,
            end,
            {"x19": 0x1_7000_2000, "x28": 0x9_8000_0000},
        )
        module._state["prepareLayer"] = {"symbolStart": start, "symbolEnd": end}
        frame, index, saw_exact = module._matching_prepare_frame(
            FakeThread([stale]),
            {"roleBase": 0x1_7000_1000, "selectedSource": 0x9_8000_0000},
        )
        self.assertIsNone(frame)
        self.assertIsNone(index)
        self.assertTrue(saw_exact)

    def test_callback_sequence_is_explicit_and_monotonic(self):
        self.assertEqual(self.module._next_sequence("first"), 1)
        self.assertEqual(self.module._next_sequence("second"), 2)
        self.assertEqual(
            self.module._state["trace"]["callbackOrder"],
            [
                {"sequence": 1, "kind": "first"},
                {"sequence": 2, "kind": "second"},
            ],
        )

    def test_callback_signatures_match_apple_lldb(self):
        expected = {
            "capture_backdrop_entry": [
                "frame",
                "_breakpoint_location",
                "_internal_dict",
            ],
            "capture_backdrop_late": [
                "frame",
                "_breakpoint_location",
                "_internal_dict",
            ],
            "prepare_layer_entry": [
                "frame",
                "breakpoint_location",
                "_internal_dict",
            ],
            "prepare_layer_live_arm_marker": [
                "frame",
                "_breakpoint_location",
                "_internal_dict",
            ],
            "aggregate_origin_watchpoint": [
                "frame",
                "watchpoint",
                "_internal_dict",
            ],
        }
        for name, parameters in expected.items():
            with self.subTest(callback=name):
                self.assertEqual(
                    list(inspect.signature(getattr(self.module, name)).parameters),
                    parameters,
                )


if __name__ == "__main__":
    unittest.main()
