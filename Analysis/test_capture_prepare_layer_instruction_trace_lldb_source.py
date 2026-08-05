#!/usr/bin/env python3
"""Portable source tests for the software-instruction LLDB probe."""

import importlib.util
import inspect
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

import test_capture_prepare_layer_frame_correlated_writer_trace_lldb_source as frame_source
import validate_prepare_layer_instruction_trace as validator


ANALYSIS_ROOT = Path(__file__).resolve().parent
MODULE_PATH = ANALYSIS_ROOT / "capture_prepare_layer_instruction_trace_lldb.py"
FRAME_MODULE_NAME = "capture_prepare_layer_frame_correlated_writer_trace_lldb"


def load_with_stub_lldb():
    frame_module = frame_source.load_with_stub_lldb()
    module_name = "capture_prepare_layer_instruction_trace_source_test"
    specification = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError("instruction-trace LLDB module spec is unavailable")
    module = importlib.util.module_from_spec(specification)
    previous_lldb = sys.modules.get("lldb")
    previous_frame = sys.modules.get(FRAME_MODULE_NAME)
    stub = types.ModuleType("lldb")
    stub.LLDB_INVALID_ADDRESS = (1 << 64) - 1
    stub.eStateStopped = 5
    stub.eStateExited = 10
    stub.eStateDetached = 9
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


class PrepareLayerInstructionTraceSourceTests(unittest.TestCase):
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

    def test_scope_inventory_is_prospective_and_complete(self):
        self.assertEqual(
            self.module.CHECKPOINT_SCOPE_SPECS,
            validator.CHECKPOINT_SCOPE_SPECS,
        )
        self.assertEqual(
            [item["name"] for item in self.module.CHECKPOINT_SCOPE_SPECS],
            [
                "prepareLayer",
                "rectApplyTransform",
                "rectUnapplyTransform",
                "glassBackgroundDOD",
                "filterApplyDOD",
                "filterApply",
                "filterMapBounds",
                "unionBounds",
            ],
        )
        for item in self.module.CHECKPOINT_SCOPE_SPECS:
            self.assertEqual(item["byteCount"] % 4, 0)
            self.assertEqual(item["relativeToPrepareLayer"] % 4, 0)

    def test_dual_source_link_epoch_is_observer_count_independent(self):
        self.assertEqual(
            self.module.SOURCE_LINK_CELL_SPECS,
            validator.SOURCE_LINK_CELL_SPECS,
        )
        source = inspect.getsource(self.module.prepare_layer_epoch_marker)
        self.assertIn("sourceKnownDepthFourEpochCount", source)
        self.assertIn("_source_link_cells", source)
        self.assertIn("source_linked", source)
        self.assertIn("prospectiveTraceTarget", source)
        self.assertIn("return True", source)
        self.assertNotIn("WatchAddress", source)
        self.assertIn(
            "x10+128 and x20-24 both equal",
            self.module._new_trace()["configuration"]["selectionRule"],
        )

    def test_dual_source_link_requires_both_exact_uint64_cells(self):
        module = self.module
        selected_source = 0xA_BEEF_0000
        registers = {"x10": 0x1_1000_0000, "x20": 0xA_2000_0000}

        def memory(_process, address, byte_count, label):
            self.assertEqual(byte_count, 8)
            expected = {
                registers["x10"] + 128: selected_source,
                registers["x20"] - 24: selected_source,
            }
            payload = expected[address].to_bytes(8, "little")
            return payload, {
                "address": address,
                "byteCount": 8,
                "sha256": "0" * 64,
                "hex": payload.hex(),
                "label": label,
            }

        with mock.patch.object(module, "_memory_payload", side_effect=memory):
            records, matched = module._source_link_cells(
                None, registers, selected_source
            )
        self.assertTrue(matched)
        self.assertEqual(
            [item["address"] for item in records],
            [registers["x10"] + 128, registers["x20"] - 24],
        )
        self.assertTrue(all(item["selectedSourceMatches"] for item in records))

        def one_mismatch(_process, address, _byte_count, _label):
            observed = selected_source if address == registers["x10"] + 128 else 0
            payload = observed.to_bytes(8, "little")
            return payload, {
                "address": address,
                "byteCount": 8,
                "sha256": "0" * 64,
                "hex": payload.hex(),
            }

        with mock.patch.object(module, "_memory_payload", side_effect=one_mismatch):
            records, matched = module._source_link_cells(
                None, registers, selected_source
            )
        self.assertFalse(matched)
        self.assertEqual(
            [item["selectedSourceMatches"] for item in records], [True, False]
        )

    def test_structural_depth_does_not_depend_on_unwound_registers(self):
        source = inspect.getsource(self.module._exact_prepare_frames)
        self.assertIn("candidate.GetFunctionName()", source)
        self.assertIn("candidate.GetSymbol()", source)
        self.assertIn("candidate.GetFP()", source)
        self.assertNotIn("_register", source)
        self.assertNotIn("except Exception", source)

    def test_hardware_watchpoints_are_absent_from_the_entire_module(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("WatchAddress", source)
        self.assertNotIn("DeleteWatchpoint", source)
        self.assertNotIn("watchpoint command", source)
        self.assertIn("StepInstruction(False, error)", source)
        self.assertIn("StepOut(error)", source)
        self.assertIn("DisableAllBreakpoints", source)
        self.assertIn("SetAsync(False)", source)

    def test_exact_source_marker_is_checked_after_manual_stepping(self):
        source = inspect.getsource(self.module._selected_marker)
        self.assertIn('x28 = capture_base._register(frame, "x28")', source)
        self.assertIn("x28 != source", source)
        self.assertIn('record["result"] = "selected"', source)
        self.assertIn('"source-register-differs-during-manual-trace"', source)
        self.assertIn('"manualSelectionMarkers"', source)
        self.assertIn("frame_base.live_selection_marker", source)
        self.assertLess(
            source.index("frame_base.live_selection_marker"),
            source.index('"selectedFrame"'),
        )

    def test_manual_marker_with_other_source_is_retained_and_tracing_continues(self):
        class FakeThread:
            def GetThreadID(self):
                return 0x1_7000_0042

        class FakeFrame:
            def GetThread(self):
                return FakeThread()

            def GetFP(self):
                return 0x1_7000_A000

            def GetPC(self):
                return 0x1_9000_3EF0

        module = self.module
        module._state["pendingCandidate"] = {
            "identity": {
                "threadID": 0x1_7000_0042,
                "roleBase": 0x1_7000_8000,
                "framePointer": 0x1_7000_A000,
            },
            "selectedSource": 0xA_BEEF_0000,
        }
        observed = {"x19": 0x1_7000_8000, "x28": 0xA_BAD_0000}
        with (
            mock.patch.object(
                module.capture_base,
                "_register",
                side_effect=lambda _frame, name: observed[name],
            ),
            mock.patch.object(module, "_record_marker_rejection") as rejection,
            mock.patch.object(module, "_write_trace"),
        ):
            self.assertFalse(module._selected_marker(FakeFrame(), [], bytes(32)))
        self.assertEqual(module._state["selectionMarkerHitCount"], 1)
        self.assertEqual(module._state["rejectedSelectionMarkerHitCount"], 1)
        self.assertEqual(
            module._state["trace"]["manualSelectionMarkers"][0]["result"],
            "rejected",
        )
        self.assertFalse(
            module._state["trace"]["manualSelectionMarkers"][0]["sourceRegisterMatches"]
        )
        rejection.assert_called_once()

    def test_changed_lane_detection_is_bit_exact(self):
        before = bytes(32)
        after = bytearray(before)
        after[0] = 1
        after[23] = 1
        self.assertEqual(
            self.module._changed_lane_offsets(before, bytes(after)), [0, 16]
        )

    def test_every_changed_step_requires_pre_execution_context(self):
        source = inspect.getsource(self.module._record_step)
        self.assertIn("if before_context is None", source)
        self.assertIn('"beforeContext": before_context', source)
        self.assertIn("_post_transition_context", source)
        instruction = inspect.getsource(self.module._trace_one_instruction)
        self.assertIn('instruction["potentialWriter"]', instruction)
        self.assertIn('instruction["potentialCall"]', instruction)
        self.assertIn("changed at an instruction not decoded", instruction)

    def test_opaque_callees_are_explicit_fail_closed_boundaries(self):
        source = inspect.getsource(self.module._trace_opaque_callee)
        self.assertIn("StepOut(error)", source)
        self.assertIn('"aggregateChanged": before != after', source)
        self.assertIn('"opaque-callee-step-out"', source)
        self.assertIn(
            "a passing trace permits no aggregate change",
            self.module._new_trace()["configuration"]["opaqueBoundaryRule"],
        )

    def test_semantic_dod_trace_is_selected_by_the_live_aggregate_pointer(self):
        module = self.module
        source = inspect.getsource(module._semantic_state_before)
        self.assertIn('identity"]["roleBase"]', source)
        self.assertIn("capture_base.AGGREGATE_OFFSET", source)
        self.assertIn('capture_base._register_snapshot(frame, ("x3",))', source)
        self.assertIn('"argumentMatchesTarget": matched', source)
        self.assertIn("semantic DOD target entry is not unique", source)
        configuration = module._new_trace()["configuration"]
        self.assertEqual(
            configuration["semanticGeneralRegisterNames"],
            list(module.capture_base.GENERAL_REGISTER_NAMES),
        )
        self.assertEqual(
            configuration["semanticSIMDRegisterNames"],
            list(module.capture_base.SIMD_REGISTER_NAMES),
        )
        self.assertEqual(
            configuration["semanticStackByteCount"],
            module.SEMANTIC_STACK_BYTE_COUNT,
        )

    def test_every_selected_dod_instruction_and_return_state_are_exact(self):
        module = self.module
        before = inspect.getsource(module._semantic_state_before)
        finish = inspect.getsource(module._finish_semantic_instruction)
        marker = inspect.getsource(module._selected_marker)
        self.assertIn(
            "capture_base._full_register_snapshot",
            inspect.getsource(module._semantic_register_and_stack_snapshot),
        )
        self.assertIn(
            "capture_base._memory_snapshot",
            inspect.getsource(module._semantic_register_and_stack_snapshot),
        )
        self.assertIn('"semanticDODInstructionStates"', before)
        self.assertIn('"instructionStatesSHA256"', finish)
        self.assertIn('"returnRegisters"', finish)
        self.assertIn('"returnStack"', finish)
        self.assertIn("semantic DOD return instruction differs", finish)
        self.assertIn("selected marker preceded semantic DOD closure", marker)

    def test_inherited_source_harness_is_reused_and_forwarded(self):
        initialization = inspect.getsource(getattr(self.module, "__lldb_init_module"))
        entry = inspect.getsource(self.module.multiplexed_prepare_layer_entry)
        capture = inspect.getsource(self.module.forwarded_capture_backdrop_entry)
        finalize = inspect.getsource(self.module.finalize)
        self.assertIn("frame_base.__lldb_init_module", initialization)
        self.assertNotIn("BreakpointCreateByName", initialization)
        self.assertLess(
            entry.index("frame_base.prepare_layer_entry"),
            entry.rindex("prepare_layer_entry(frame"),
        )
        self.assertIn('frame_base._state["captureLateBreakpoint"]', capture)
        self.assertIn("frame_base.finalize()", finalize)

    def test_non_epoch_samples_retire_before_the_prospective_epoch(self):
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
        with mock.patch.object(module, "_write_trace"):
            module._retire_inherited_writer_breakpoints(FakeFrame())
        for name in module.RETIRED_INHERITED_WRITER_SITE_NAMES:
            self.assertFalse(writer_breakpoints[name].IsEnabled(), name)
        self.assertTrue(writer_breakpoints[module.EPOCH_MARKER_NAME].IsEnabled())
        self.assertTrue(module._state["selectionBreakpoint"].IsEnabled())
        self.assertEqual(module._state["callbackSequence"], 2)


if __name__ == "__main__":
    unittest.main()
