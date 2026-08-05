#!/usr/bin/env python3
"""Portable source tests for the frame-correlated LLDB probe."""

import importlib.util
import inspect
import json
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

import validate_prepare_layer_frame_correlated_writer_trace as validator


ANALYSIS_ROOT = Path(__file__).resolve().parent
MODULE_PATH = ANALYSIS_ROOT / "capture_prepare_layer_frame_correlated_writer_trace_lldb.py"
BASE_MODULE_NAME = "capture_prepare_layer_full_path_trace_lldb"
OPENED_RESULT = json.loads(
    (
        ANALYSIS_ROOT
        / "dynamic_allocation_prepare_layer_live_writer_x28_timing_result.json"
    ).read_text(encoding="utf-8")
)


def load_with_stub_lldb():
    module_name = "capture_prepare_layer_frame_correlated_writer_source_test"
    specification = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError("frame-correlated LLDB module spec is unavailable")
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


class FakeFrame:
    def __init__(self, function, start, end, registers):
        self.function = function
        self.symbol = FakeSymbol(start, end)
        self.registers = registers

    def GetFunctionName(self):
        return self.function

    def GetSymbol(self):
        return self.symbol


class FakeProcess:
    def GetTarget(self):
        return object()


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


def register_records(frame, names):
    return [
        {
            "name": name,
            "byteCount": 8,
            "hex": frame.registers[name].to_bytes(8, "little").hex(),
            "valueString": hex(frame.registers[name]),
            "unsignedValue": frame.registers[name],
        }
        for name in names
    ]


class PrepareLayerFrameCorrelatedWriterSourceTests(unittest.TestCase):
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

    def test_opened_writer_sites_and_instructions_are_frozen(self):
        sites = {site["name"]: site for site in self.module.WRITER_SITES}
        self.assertEqual(len(sites), 9)
        self.assertEqual(sites["rectApplyTransformAfter"]["relativeToPrepareLayer"], -1207012)
        self.assertEqual(sites["unionBoundsStoreAfter"]["relativeToPrepareLayer"], -2588)
        self.assertEqual(sites["unionBoundsStoreAfter"]["precedingInstructionRawLittleEndianHex"], "800600ad")
        self.assertEqual(sites["zeroInitializationAfter"]["relativeToPrepareLayer"], 0xB60)
        self.assertTrue(sites["zeroInitializationAfter"]["epochStart"])
        self.assertEqual(sites["zeroInitializationAfter"]["precedingInstructionRawLittleEndianHex"], "60a6803d")
        self.assertEqual(sites["alternateAggregateCopyAfter"]["relativeToPrepareLayer"], 0x33F4)
        self.assertEqual(sites["rangeClampStoreAfter"]["relativeToPrepareLayer"], 0x3974)
        self.assertEqual(sites["rangeClampStoreAfter"]["precedingInstructionRawLittleEndianHex"], "608614ad")

    def test_dynamic_sites_are_exactly_the_opened_watchpoint_groups(self):
        opened = {
            (group["function"], group["stopPCRelativeToPrepareLayer"])
            for group in OPENED_RESULT["openedPrepareAncestryWriterGroups"]
        }
        configured = {
            (site["function"], site["relativeToPrepareLayer"])
            for site in self.module.WRITER_SITES
            if site["openedByHardwareWatchpoint"]
        }
        self.assertEqual(configured, opened)

    def test_probe_uses_no_hardware_or_long_lived_watchpoint(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("WatchAddress", source)
        self.assertNotIn("BreakpointCreateByAddress(role", source)
        self.assertFalse(hasattr(self.module, "aggregate_watchpoint_hit"))
        self.assertFalse(hasattr(self.module, "_install_live_watchpoint"))

    def test_sites_are_installed_at_first_exact_prepare_entry(self):
        source = inspect.getsource(self.module.prepare_layer_entry)
        self.assertIn("for site in WRITER_SITES", source)
        self.assertIn('target, address, "writer_site"', source)
        self.assertIn("LIVE_SELECTION_MARKER_OFFSET", source)
        self.assertIn('SetEnabled(False)', source)

    def test_nearest_exact_prepare_frame_is_returned_without_x28_filter(self):
        module = self.module
        start = 0x1_9000_0000
        end = start + module.capture_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT
        helper = FakeFrame("helper", start - 0x1000, start, {})
        nearest = FakeFrame(
            module.capture_base.PREPARE_LAYER_FUNCTION,
            start,
            end,
            {"x19": 0x170001000, "x28": 0x111, "x29": 0x170001800, "x30": 3, "sp": 4, "pc": start + 0x100},
        )
        deeper = FakeFrame(
            module.capture_base.PREPARE_LAYER_FUNCTION,
            start,
            end,
            {"x19": 0x170002000, "x28": 0x222, "x29": 0x170002800, "x30": 5, "sp": 6, "pc": start + 0x200},
        )
        module._state["prepareLayer"] = {"symbolStart": start, "symbolEnd": end}
        with mock.patch.object(
            module.capture_base,
            "_register_snapshot",
            side_effect=register_records,
        ):
            frame, index, records, values = module._matching_prepare_frame(
                FakeThread([helper, nearest, deeper])
            )
        self.assertIs(frame, nearest)
        self.assertEqual(index, 1)
        self.assertEqual(values["x19"], nearest.registers["x19"])
        self.assertEqual(values["x28"], 0x111)
        self.assertEqual(values["x29"], nearest.registers["x29"])
        self.assertEqual(len(records), len(module.PREPARE_FRAME_REGISTER_NAMES))

    def test_correlation_uses_three_stable_identity_fields_and_latest_epoch(self):
        marker = inspect.getsource(self.module.live_selection_marker)
        writer = inspect.getsource(self.module.writer_site)
        self.assertIn('"threadID": thread_id', marker)
        self.assertIn('"roleBase": x19', marker)
        self.assertIn('"framePointer": x29', marker)
        self.assertIn('if site["epochStart"]', writer)
        self.assertIn('if event["frameIdentity"] == identity', marker)
        self.assertIn('max(epochs, key=lambda event: event["callbackSequence"])', marker)

    def test_finalize_preserves_complete_failure_and_accounting_state(self):
        source = inspect.getsource(self.module.finalize)
        self.assertIn('"unretainedRejectedWriterHitCount"', source)
        self.assertIn('"finalSelectedDistinctAggregateCount"', source)
        self.assertIn('"finalSelectedChangingTransitionCount"', source)


if __name__ == "__main__":
    unittest.main()
