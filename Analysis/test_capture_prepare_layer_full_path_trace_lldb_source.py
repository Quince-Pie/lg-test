#!/usr/bin/env python3
"""Portable source tests for the full-code/path/watchpoint LLDB probe."""

import importlib.util
import inspect
import sys
import types
import unittest
from pathlib import Path

import validate_prepare_layer_full_path_trace as validator


ANALYSIS_ROOT = Path(__file__).resolve().parent
MODULE_PATH = ANALYSIS_ROOT / "capture_prepare_layer_full_path_trace_lldb.py"


def load_with_stub_lldb():
    module_name = "capture_prepare_layer_full_path_trace_lldb_source_test"
    specification = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError("LLDB full-path module spec is unavailable")
    module = importlib.util.module_from_spec(specification)
    previous = sys.modules.get("lldb")
    stub = types.ModuleType("lldb")
    stub.LLDB_INVALID_ADDRESS = (1 << 64) - 1
    sys.modules["lldb"] = stub
    try:
        specification.loader.exec_module(module)
    finally:
        if previous is None:
            del sys.modules["lldb"]
        else:
            sys.modules["lldb"] = previous
    return module


class PrepareLayerFullPathLLDBSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_with_stub_lldb()

    def setUp(self):
        module = self.module
        module._state["objectAddresses"] = {}
        module._state["callbackSequence"] = 0
        module._state["trace"] = {
            "callbackOrder": [],
            "markerRecords": [],
        }

    def test_complete_symbol_and_all_prior_code_windows_are_frozen(self):
        module = self.module
        self.assertEqual(module.TRACE_SCHEMA_VERSION, 1)
        self.assertEqual(module.PREPARE_LAYER_SYMBOL_BYTE_COUNT, 40128)
        self.assertEqual(
            [item[0] for item in module.KNOWN_PREPARE_LAYER_WINDOWS],
            [12764, 14064, 17944, 19212, 19216],
        )
        self.assertTrue(
            all(item[1] == 4096 for item in module.KNOWN_PREPARE_LAYER_WINDOWS)
        )
        self.assertEqual(module.UNION_HELPER_RELATIVE_TO_PREPARE_LAYER, -0xAA0)
        self.assertEqual(module.UNION_HELPER_SYMBOL_BYTE_COUNT, 404)

    def test_markers_cover_skipped_branches_join_and_later_source_sites(self):
        module = self.module
        markers = {name: (offset, arm) for name, offset, arm in module.PATH_MARKERS}
        self.assertEqual(markers["constructionWindowEntry"], (0x31DC, False))
        self.assertEqual(markers["directUnionCall"], (0x32C0, False))
        self.assertEqual(markers["alternateAggregateStore"], (0x33F0, False))
        self.assertEqual(markers["constructionJoin"], (0x3458, False))
        self.assertEqual(markers["sourceLaterHandle"], (0x3EF0, True))
        self.assertEqual(markers["sourceLaterOwnerRectangle"], (0x4E18, True))
        self.assertEqual(markers["sourceLaterIntegerOrigin"], (0x530C, True))
        self.assertEqual(markers["sourceLaterIntegerTail"], (0x5310, True))
        self.assertEqual(
            set(module.LATER_SELECTED_MARKER_NAMES),
            {name for name, (_offset, arm) in markers.items() if arm},
        )

    def test_watchpoint_is_exactly_the_first_aggregate_component(self):
        module = self.module
        self.assertEqual(module.ROLE_STATE_BYTE_COUNT, 2048)
        self.assertEqual(module.AGGREGATE_OFFSET, 656)
        self.assertEqual(module.AGGREGATE_BYTE_COUNT, 32)
        self.assertEqual(module.WATCHPOINT_BYTE_COUNT, 8)
        self.assertEqual(module.MAXIMUM_WATCHPOINT_HIT_COUNT, 24)

    def test_harness_and_validator_configuration_are_byte_for_byte_aligned(self):
        self.assertEqual(
            self.module._new_trace()["configuration"],
            validator.EXPECTED_CONFIGURATION,
        )

    def test_marker_classification_is_retrospective_and_exact(self):
        source = 0x1_A000_0000
        self.module._state["trace"]["markerRecords"] = [
            {"addresses": {"source": source}, "selectedSource": None},
            {"addresses": {"source": source + 8}, "selectedSource": None},
        ]
        self.module._state["objectAddresses"] = {"source": source}
        self.module._classify_marker_records()
        self.assertEqual(
            [
                record["selectedSource"]
                for record in self.module._state["trace"]["markerRecords"]
            ],
            [True, False],
        )

    def test_retrospective_arm_uses_most_recent_selected_watch_marker(self):
        source = 0x1_A000_0000
        self.module._state["trace"]["markerRecords"] = [
            {
                "recordIndex": 0,
                "callbackSequence": 3,
                "watchArmCandidate": True,
                "selectedSource": True,
            },
            {
                "recordIndex": 1,
                "callbackSequence": 8,
                "watchArmCandidate": True,
                "selectedSource": False,
            },
            {
                "recordIndex": 2,
                "callbackSequence": 7,
                "watchArmCandidate": True,
                "selectedSource": True,
            },
        ]
        self.module._state["objectAddresses"] = {"source": source}
        candidate = self.module._retrospective_watchpoint_candidate()
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["recordIndex"], 2)

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
        for name in (
            "capture_backdrop_entry",
            "capture_backdrop_late",
            "prepare_layer_entry",
            "prepare_layer_marker",
            "aggregate_origin_watchpoint",
        ):
            with self.subTest(callback=name):
                expected = ["frame", "_breakpoint_location", "_internal_dict"]
                if name == "prepare_layer_entry":
                    expected = ["frame", "breakpoint_location", "_internal_dict"]
                elif name == "aggregate_origin_watchpoint":
                    expected = ["frame", "watchpoint", "_internal_dict"]
                self.assertEqual(
                    list(inspect.signature(getattr(self.module, name)).parameters),
                    expected,
                )


if __name__ == "__main__":
    unittest.main()
