#!/usr/bin/env python3
"""Portable source tests for the active-frame four-lane LLDB probe."""

import importlib.util
import inspect
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

import test_capture_prepare_layer_frame_correlated_writer_trace_lldb_source as frame_source
import validate_prepare_layer_active_frame_watch_trace as validator


ANALYSIS_ROOT = Path(__file__).resolve().parent
MODULE_PATH = ANALYSIS_ROOT / "capture_prepare_layer_active_frame_watch_trace_lldb.py"
FRAME_MODULE_NAME = "capture_prepare_layer_frame_correlated_writer_trace_lldb"


def load_with_stub_lldb():
    frame_module = frame_source.load_with_stub_lldb()
    module_name = "capture_prepare_layer_active_frame_watch_source_test"
    specification = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError("active-frame watch LLDB module spec is unavailable")
    module = importlib.util.module_from_spec(specification)
    previous_lldb = sys.modules.get("lldb")
    previous_frame = sys.modules.get(FRAME_MODULE_NAME)
    stub = types.ModuleType("lldb")
    stub.LLDB_INVALID_ADDRESS = (1 << 64) - 1
    sys.modules["lldb"] = stub
    sys.modules[FRAME_MODULE_NAME] = frame_module
    try:
        specification.loader.exec_module(module)
    finally:
        if previous_lldb is None:
            del sys.modules["lldb"]
        else:
            sys.modules["lldb"] = previous_lldb
        if previous_frame is None:
            del sys.modules[FRAME_MODULE_NAME]
        else:
            sys.modules[FRAME_MODULE_NAME] = previous_frame
    return module


class ActiveFrameWatchSourceTests(unittest.TestCase):
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

    def test_four_aligned_lanes_cover_all_aggregate_bytes(self):
        self.assertEqual(self.module.WATCH_LANE_OFFSETS, (0, 8, 16, 24))
        self.assertEqual(self.module.WATCH_LANE_BYTE_COUNT, 8)
        covered = {
            byte
            for offset in self.module.WATCH_LANE_OFFSETS
            for byte in range(offset, offset + self.module.WATCH_LANE_BYTE_COUNT)
        }
        self.assertEqual(covered, set(range(32)))
        source = inspect.getsource(self.module._install_watch_group)
        self.assertIn("for lane_offset in WATCH_LANE_OFFSETS", source)
        self.assertIn("target.WatchAddress", source)

    def test_arm_rule_is_source_known_and_exact_depth_four(self):
        source = inspect.getsource(self.module.prepare_layer_epoch_marker)
        self.assertIn("source = _selected_source()", source)
        self.assertIn("source is None", source)
        self.assertIn("len(exact) != TARGET_PREPARE_RECURSION_DEPTH", source)
        self.assertEqual(self.module.TARGET_PREPARE_RECURSION_DEPTH, 4)

    def test_structural_depth_never_depends_on_unwound_register_reads(self):
        source = inspect.getsource(self.module._exact_prepare_frames)
        self.assertIn("candidate.GetFunctionName()", source)
        self.assertIn("candidate.GetSymbol()", source)
        self.assertIn("candidate.GetFP()", source)
        self.assertNotIn("_register", source)
        self.assertNotIn("except Exception", source)

    def test_live_membership_uses_thread_and_unwind_frame_pointer(self):
        source = inspect.getsource(self.module._matching_identity)
        self.assertIn('thread_id != identity["threadID"]', source)
        self.assertIn('item["framePointer"] == identity["framePointer"]', source)
        self.assertNotIn("x19", source)
        self.assertNotIn("x28", source)

    def test_identity_does_not_require_future_x28_value(self):
        identity_source = inspect.getsource(self.module._identity)
        epoch_source = inspect.getsource(self.module.prepare_layer_epoch_marker)
        self.assertNotIn("x28", identity_source)
        self.assertNotIn('values["x28"] == source', epoch_source)
        self.assertIn('"roleBase"', identity_source)
        self.assertIn('"framePointer"', identity_source)
        self.assertEqual(
            self.module.IDENTITY_FRAME_REGISTER_NAMES,
            ("x19", "x29", "pc"),
        )
        self.assertEqual(
            self.module.SELECTION_FRAME_REGISTER_NAMES,
            ("x19", "x28", "x29", "pc"),
        )

    def test_return_marker_deletes_watches_with_live_frame(self):
        retirement = inspect.getsource(self.module.prepare_layer_return_marker)
        deletion = inspect.getsource(self.module._delete_active_watchpoints)
        self.assertIn("_matching_identity", retirement)
        self.assertIn("watched-prepare-frame-returned", retirement)
        self.assertIn("DeleteWatchpoint", deletion)

    def test_changed_lane_detection_is_exact(self):
        before = bytes(32)
        after = bytearray(before)
        after[8] = 1
        after[31] = 1
        self.assertEqual(
            self.module._changed_lane_offsets(before, bytes(after)), [8, 24]
        )

    def test_selected_marker_requires_contiguous_active_group(self):
        source = inspect.getsource(self.module.prepare_layer_selection_marker)
        self.assertIn("x28 != source", source)
        self.assertIn('group["identity"] != identity', source)
        self.assertIn("selected active watch epoch has no qualified writes", source)
        self.assertIn("selected-marker-closed", source)

    def test_every_ordinary_marker_rejection_is_retained(self):
        epoch = inspect.getsource(self.module.prepare_layer_epoch_marker)
        selection = inspect.getsource(self.module.prepare_layer_selection_marker)
        diagnostics = inspect.getsource(self.module._record_marker_rejection)
        self.assertEqual(epoch.count("_record_marker_rejection("), 2)
        self.assertEqual(selection.count("_record_marker_rejection("), 2)
        self.assertIn('"prepareFrames"', diagnostics)
        self.assertIn("_public_prepare_frames", diagnostics)

    def test_immutable_sampled_harness_is_reused_not_rewritten(self):
        source = inspect.getsource(getattr(self.module, "__lldb_init_module"))
        finalize = inspect.getsource(self.module.finalize)
        self.assertIn("frame_base.__lldb_init_module", source)
        self.assertIn('frame_base._state["captureEntryBreakpoint"]', source)
        self.assertIn('frame_base._state["prepareEntryBreakpoint"]', source)
        self.assertNotIn("BreakpointCreateByName", source)
        self.assertIn("frame_base.finalize()", finalize)

    def test_shared_breakpoint_callbacks_are_multiplexed_base_first(self):
        pairs = (
            (
                self.module.multiplexed_prepare_layer_entry,
                "frame_base.prepare_layer_entry",
                "prepare_layer_entry(frame",
            ),
            (
                self.module.multiplexed_epoch_marker,
                "frame_base.writer_site",
                "prepare_layer_epoch_marker",
            ),
            (
                self.module.multiplexed_selection_marker,
                "frame_base.live_selection_marker",
                "prepare_layer_selection_marker",
            ),
        )
        for callback, inherited, active in pairs:
            with self.subTest(callback=callback.__name__):
                source = inspect.getsource(callback)
                self.assertLess(source.index(inherited), source.rindex(active))
        entry = inspect.getsource(self.module.prepare_layer_entry)
        self.assertIn('frame_base._state["writerBreakpoints"]', entry)
        self.assertIn('frame_base._state["selectionMarkerBreakpoint"]', entry)
        self.assertEqual(entry.count("_address_breakpoint("), 1)

    def test_all_nested_inherited_callbacks_are_exported_by_active_module(self):
        initialization = inspect.getsource(getattr(self.module, "__lldb_init_module"))
        capture_entry = inspect.getsource(self.module.forwarded_capture_backdrop_entry)
        capture_late = inspect.getsource(self.module.forwarded_capture_backdrop_late)
        writer = inspect.getsource(self.module.forwarded_writer_site)
        entry = inspect.getsource(self.module.prepare_layer_entry)
        self.assertIn('"forwarded_capture_backdrop_entry"', initialization)
        self.assertIn('frame_base._state["captureLateBreakpoint"]', capture_entry)
        self.assertIn('"forwarded_capture_backdrop_late"', capture_entry)
        self.assertIn("frame_base.capture_backdrop_late", capture_late)
        self.assertLess(
            capture_late.index("frame_base.capture_backdrop_late"),
            capture_late.index(
                "_retire_inherited_writer_breakpoints_for_hardware_watch"
            ),
        )
        self.assertIn("frame_base.writer_site", writer)
        self.assertIn('"forwarded_writer_site"', entry)
        self.assertIn("name != EPOCH_MARKER_NAME", entry)

    def test_non_epoch_sample_breakpoints_are_retired_before_hardware_watch(self):
        class FakeBreakpoint:
            def __init__(self, identifier):
                self.identifier = identifier
                self.enabled = True

            def GetID(self):
                return self.identifier

            def IsEnabled(self):
                return self.enabled

            def IsValid(self):
                return True

            def SetEnabled(self, enabled):
                self.enabled = enabled

        class FakeThread:
            def GetThreadID(self):
                return 0x1_7000_0042

        class FakeFrame:
            def GetThread(self):
                return FakeThread()

            def GetPC(self):
                return 0x1_9440_2B58

        module = self.module
        writer_breakpoints = {
            site["name"]: FakeBreakpoint(index + 10)
            for index, site in enumerate(module.frame_base.WRITER_SITES)
        }
        module.frame_base._state["writerBreakpoints"] = writer_breakpoints
        module.frame_base._state["objectAddresses"] = {"source": 0x9_BEEF_0000}
        module._state["prepareLayer"] = {"symbolStart": 0x1_9000_0000}
        module._state["callbackSequence"] = 1
        module._state["selectionBreakpoint"] = FakeBreakpoint(100)
        module._state["returnBreakpoint"] = FakeBreakpoint(101)
        with mock.patch.object(module, "_write_trace"):
            module._retire_inherited_writer_breakpoints_for_hardware_watch(FakeFrame())
        for name in module.RETIRED_INHERITED_WRITER_SITE_NAMES:
            self.assertFalse(writer_breakpoints[name].IsEnabled(), name)
        self.assertTrue(writer_breakpoints[module.EPOCH_MARKER_NAME].IsEnabled())
        self.assertTrue(module._state["selectionBreakpoint"].IsEnabled())
        self.assertTrue(module._state["returnBreakpoint"].IsEnabled())
        self.assertEqual(module._state["callbackSequence"], 2)
        record = module._state["trace"]["inheritedWriterBreakpointRetirement"]
        self.assertEqual(record["callbackSequence"], 2)
        self.assertTrue(
            all(item["enabledAfterRetirement"] is False for item in record["retired"])
        )
        self.assertTrue(
            all(
                item["enabledAfterRetirement"] is True
                for item in record["retainedControlBreakpoints"]
            )
        )


if __name__ == "__main__":
    unittest.main()
