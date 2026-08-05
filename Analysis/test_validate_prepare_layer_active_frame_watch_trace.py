#!/usr/bin/env python3
"""Adversarial tests for the four-lane active-frame writer gate."""

import copy
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import test_validate_capture_backdrop_writer_trace as writer_fixture
import test_validate_prepare_layer_frame_correlated_writer_trace as frame_fixture
import validate_prepare_layer_active_frame_watch_trace as validator


PREPARE_START = frame_fixture.PREPARE_START
MODULE = frame_fixture.MODULE
ROLE_BASE = frame_fixture.ROLE_BASE
FRAME_POINTER = frame_fixture.FRAME_POINTER
THREAD_ID = frame_fixture.THREAD_ID


def identity(role_base=ROLE_BASE, frame_pointer=FRAME_POINTER):
    return {
        "threadID": THREAD_ID,
        "roleBase": role_base,
        "framePointer": frame_pointer,
    }


def active_registers(names, role_base, source, frame_pointer, pc):
    available = {
        item["name"]: item
        for item in frame_fixture.prepare_registers(
            role_base, source, frame_pointer, pc
        )
    }
    return [available[name] for name in names]


def prepare_frames(pc):
    result = []
    for ordinal in range(validator.TARGET_PREPARE_RECURSION_DEPTH):
        item_identity = identity(
            ROLE_BASE + ordinal * 0x2000,
            FRAME_POINTER + ordinal * 0x2000,
        )
        item_pc = pc if ordinal == 0 else PREPARE_START + validator.RETURN_MARKER_OFFSET
        result.append(
            {
                "frameIndex": ordinal,
                "frame": frame_fixture.prepare_frame(item_pc, frame_index=ordinal),
                "unwindFramePointer": item_identity["framePointer"],
            }
        )
    return result


def active_event(index, callback, stop_offset, before, after, addresses, lane):
    stop_pc = PREPARE_START + stop_offset
    top = frame_fixture.prepare_frame(stop_pc)
    structural = prepare_frames(stop_pc)
    changed_lanes = [
        offset
        for offset in validator.WATCH_LANE_OFFSETS
        if before[offset : offset + validator.WATCH_LANE_BYTE_COUNT]
        != after[offset : offset + validator.WATCH_LANE_BYTE_COUNT]
    ]
    return {
        "eventIndex": index,
        "callbackSequence": callback,
        "groupIndex": 0,
        "epochRecordIndex": 0,
        "watchpointID": 10 + validator.WATCH_LANE_OFFSETS.index(lane),
        "triggeredLaneOffset": lane,
        "threadID": THREAD_ID,
        "stopPC": stop_pc,
        "watchedAddress": ROLE_BASE + validator.full_base.AGGREGATE_OFFSET + lane,
        "aggregateAddress": ROLE_BASE + validator.full_base.AGGREGATE_OFFSET,
        "beforeHex": before.hex(),
        "afterHex": after.hex(),
        "valueChanged": before != after,
        "changedLaneOffsets": changed_lanes,
        "frame": top,
        "backtrace": [item["frame"] for item in structural],
        "prepareFrameOrdinal": 0,
        "prepareFrameCount": validator.TARGET_PREPARE_RECURSION_DEPTH,
        "prepareFrameIndex": 0,
        "prepareFrame": top,
        "prepareFramePointer": FRAME_POINTER,
        "frameIdentity": identity(),
        "roleStateAfter": frame_fixture.memory_snapshot(
            ROLE_BASE, frame_fixture.role_state(after)
        ),
        "codeWindowIndex": index,
        "privateFieldsAfter": writer_fixture.private_fields(),
        "operandSnapshot": frame_fixture.top_operands(
            stop_pc, ROLE_BASE, FRAME_POINTER, addresses
        ),
    }


def passing_documents():
    base, _full_hash, _known_windows, _configuration = frame_fixture.passing_trace()
    base_selected = base["selectedFrame"]
    addresses = base["objectChain"]["addresses"]
    source = addresses["source"]
    zero = bytes(validator.full_base.AGGREGATE_BYTE_COUNT)
    state_one = struct.pack("<4d", 481.25, -97.25, 640.0, 640.0)
    state_two = struct.pack("<4d", 481.25, -105.25, 640.0, 648.0)
    final = struct.pack("<4d", 480.0, -105.25, 641.25, 649.25)
    base_selected["aggregateAtMarkerHex"] = final.hex()
    base_selected["roleStateAtMarker"] = frame_fixture.memory_snapshot(
        ROLE_BASE, frame_fixture.role_state(final)
    )
    offsets = [0x3974, 0x2504, 0x2604]
    states = [(zero, state_one), (state_one, state_two), (state_two, final)]
    lanes = [0, 8, 0]
    events = [
        active_event(
            index,
            5 + index,
            offsets[index],
            before,
            after,
            addresses,
            lanes[index],
        )
        for index, (before, after) in enumerate(states)
    ]
    windows = [
        frame_fixture.code_window(event["stopPC"], "01020304", 0x30 + index)
        for index, event in enumerate(events)
    ]
    epoch_pc = PREPARE_START + validator.EPOCH_MARKER_OFFSET
    marker_pc = PREPARE_START + validator.SELECTION_MARKER_OFFSET
    epoch_frame = frame_fixture.prepare_frame(epoch_pc)
    marker_frame = frame_fixture.prepare_frame(marker_pc)
    epoch_prepare_frames = prepare_frames(epoch_pc)
    marker_prepare_frames = prepare_frames(marker_pc)
    base_sites = {item["name"]: item for item in base["prepareLayer"]["writerSites"]}
    retired_breakpoints = [
        {
            "name": name,
            "breakpointID": base_sites[name]["breakpointID"],
            "enabledAfterRetirement": False,
        }
        for name in validator.RETIRED_INHERITED_WRITER_SITE_NAMES
    ]
    retained_breakpoints = [
        {
            "name": validator.EPOCH_MARKER_NAME,
            "breakpointID": base_sites[validator.EPOCH_MARKER_NAME]["breakpointID"],
            "enabledAfterRetirement": True,
        },
        {
            "name": validator.SELECTION_MARKER_NAME,
            "breakpointID": base["prepareLayer"]["liveSelectionMarker"]["breakpointID"],
            "enabledAfterRetirement": True,
        },
        {
            "name": validator.RETURN_MARKER_NAME,
            "breakpointID": 13,
            "enabledAfterRetirement": True,
        },
    ]
    group = {
        "groupIndex": 0,
        "callbackSequence": 4,
        "epochRecordIndex": 0,
        "identity": identity(),
        "initialAggregateHex": zero.hex(),
        "watchpoints": [
            {
                "id": 10 + index,
                "deprecatedHardwareIndex": index,
                "laneOffset": lane,
                "address": ROLE_BASE + validator.full_base.AGGREGATE_OFFSET + lane,
                "byteCount": validator.WATCH_LANE_BYTE_COUNT,
            }
            for index, lane in enumerate(validator.WATCH_LANE_OFFSETS)
        ],
        "retiredCallbackSequence": 9,
        "retirementReason": "selected-marker-closed",
        "lastAggregateHex": final.hex(),
    }
    document = {
        "prepareLayerActiveFrameWatchTraceSchemaVersion": (
            validator.EXPECTED_TRACE_SCHEMA_VERSION
        ),
        "classification": validator.EXPECTED_CLASSIFICATION,
        "status": "finalized",
        "statusBeforeFinalization": "live-selected-active-frame-watch-closed",
        "configuration": copy.deepcopy(validator.EXPECTED_CONFIGURATION),
        "callbackOrder": [
            {"sequence": 1, "kind": "prepare-layer-entry"},
            {"sequence": 2, "kind": "inherited-writer-breakpoints-retired"},
            {"sequence": 3, "kind": "depth-four-zero-epoch"},
            {"sequence": 4, "kind": "active-watch-group-armed"},
            *[
                {
                    "sequence": 5 + index,
                    "kind": "qualified-active-frame-watchpoint-hit",
                }
                for index in range(3)
            ],
            {"sequence": 8, "kind": "live-selected-active-frame-watch-closed"},
            {"sequence": 9, "kind": "active-watch-group-retired"},
        ],
        "prepareLayerEntryBreakpointID": 2,
        "prepareLayer": {
            "callbackSequence": 1,
            "callbackPC": PREPARE_START,
            "callbackLocationAddress": PREPARE_START,
            "function": validator.merge_base.PREPARE_LAYER_FUNCTION,
            "symbolStart": PREPARE_START,
            "symbolEnd": (
                PREPARE_START + validator.full_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT
            ),
            "symbolByteCount": validator.full_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            "fullCodeSHA256": validator.PREPARE_LAYER_FULL_CODE_SHA256,
            "module": MODULE,
            "epochMarker": {"address": epoch_pc, "breakpointID": 9},
            "returnMarker": {
                "address": PREPARE_START + validator.RETURN_MARKER_OFFSET,
                "breakpointID": retained_breakpoints[2]["breakpointID"],
            },
            "selectionMarker": {"address": marker_pc, "breakpointID": 12},
        },
        "epochRecords": [
            {
                "recordIndex": 0,
                "callbackSequence": 3,
                "markerHitIndex": 1,
                "threadID": THREAD_ID,
                "pc": epoch_pc,
                "frame": epoch_frame,
                "backtrace": [item["frame"] for item in epoch_prepare_frames],
                "prepareRecursionDepth": validator.TARGET_PREPARE_RECURSION_DEPTH,
                "prepareFrames": epoch_prepare_frames,
                "registers": active_registers(
                    validator.IDENTITY_FRAME_REGISTER_NAMES,
                    ROLE_BASE,
                    source,
                    FRAME_POINTER,
                    epoch_pc,
                ),
                "identity": identity(),
                "selectedSourceKnown": source,
                "roleStateAtEpoch": frame_fixture.memory_snapshot(
                    ROLE_BASE, frame_fixture.role_state(zero)
                ),
                "aggregateAtEpochHex": zero.hex(),
                "watchpointGroupIndex": 0,
            }
        ],
        "watchpointGroups": [group],
        "retirementRecords": [
            {
                "recordIndex": 0,
                "callbackSequence": 9,
                "groupIndex": 0,
                "epochRecordIndex": 0,
                "reason": "selected-marker-closed",
                "identity": identity(),
                "lastAggregateHex": final.hex(),
            }
        ],
        "qualifiedWatchpointEvents": events,
        "ignoredWatchpointDiagnostics": [],
        "rejectedMarkerDiagnostics": [],
        "inheritedWriterBreakpointRetirement": {
            "callbackSequence": 2,
            "threadID": THREAD_ID,
            "pc": base["captureBackdrop"]["symbolAddress"]
            + validator.full_base.CAPTURE_BACKDROP_LATE_OFFSET,
            "selectedSource": source,
            "retired": retired_breakpoints,
            "retainedControlBreakpoints": retained_breakpoints,
        },
        "codeWindows": windows,
        "selectedFrame": {
            "callbackSequence": 8,
            "markerHitIndex": 1,
            "threadID": THREAD_ID,
            "pc": marker_pc,
            "frame": marker_frame,
            "backtrace": [item["frame"] for item in marker_prepare_frames],
            "registers": active_registers(
                validator.SELECTION_FRAME_REGISTER_NAMES,
                ROLE_BASE,
                source,
                FRAME_POINTER,
                marker_pc,
            ),
            "prepareRecursionDepth": validator.TARGET_PREPARE_RECURSION_DEPTH,
            "frameIdentity": identity(),
            "selectedSource": source,
            "selectedEpochRecordIndex": 0,
            "selectedWatchpointGroupIndex": 0,
            "selectedWriterEventCount": 3,
            "roleStateAtMarker": frame_fixture.memory_snapshot(
                ROLE_BASE, frame_fixture.role_state(final)
            ),
            "aggregateAtMarkerHex": final.hex(),
            "objectChain": copy.deepcopy(base["objectChain"]),
        },
        "selectedWriterEventIndices": [0, 1, 2],
        "failures": [],
        "finalFailureCount": 0,
        "finalCallbackSequence": 9,
        "epochMarkerHitCount": 1,
        "rejectedEpochDepthCount": 0,
        "sourceUnknownEpochCount": 0,
        "discardedEpochRecordCount": 0,
        "finalEpochRecordCount": 1,
        "returnMarkerHitCount": 1,
        "selectionMarkerHitCount": 1,
        "rejectedSelectionMarkerHitCount": 0,
        "rawWatchpointHitCount": 3,
        "qualifiedWatchpointHitCount": 3,
        "ignoredWatchpointHitCount": 0,
        "unretainedIgnoredWatchpointHitCount": 0,
        "unretainedRejectedMarkerDiagnosticCount": 0,
        "finalRejectedMarkerDiagnosticCount": 0,
        "inheritedWriterBreakpointsRetired": True,
        "finalQualifiedWatchpointEventCount": 3,
        "finalChangedQualifiedWatchpointEventCount": 3,
        "finalSelectedWriterEventCount": 3,
        "finalSelectedChangedTransitionCount": 3,
        "finalSelectedDistinctAggregateCount": 4,
    }
    return document, base


class ActiveFrameWatchValidatorTests(unittest.TestCase):
    def validate_documents(self, document, base):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trace_path = root / "active-watch.json"
            base_path = root / "frame-writer.json"
            trace_path.write_text(
                json.dumps(document, sort_keys=True, allow_nan=False) + "\n",
                encoding="utf-8",
            )
            base_path.write_text(
                json.dumps(base, sort_keys=True, allow_nan=False) + "\n",
                encoding="utf-8",
            )
            full_code_hash = base["prepareLayer"]["fullCode"]["sha256"]
            known_windows = [
                (item["offset"], item["byteCount"], item["sha256"])
                for item in base["prepareLayer"]["knownWindows"]
            ]
            with (
                mock.patch.object(
                    validator.frame_validator,
                    "PREPARE_LAYER_FULL_CODE_SHA256",
                    full_code_hash,
                ),
                mock.patch.object(
                    validator.full_base,
                    "KNOWN_PREPARE_LAYER_WINDOWS",
                    known_windows,
                ),
                mock.patch.object(
                    validator.frame_validator,
                    "EXPECTED_CONFIGURATION",
                    base["configuration"],
                ),
            ):
                return validator.validate(trace_path, base_path)

    def test_passing_trace_opens_complete_PC_chain_only(self):
        document, base = passing_documents()
        result = self.validate_documents(document, base)
        self.assertEqual(result["conclusion"], "success")
        self.assertEqual(result["aggregate"]["selectedChangedTransitionCount"], 3)
        self.assertEqual(result["aggregate"]["selectedDistinctAggregateCount"], 4)
        self.assertEqual(
            result["aggregate"]["newlyOpenedChangedWriterOffsets"],
            [0x2504, 0x2604],
        )
        sealed = result["sealedConclusion"]
        self.assertTrue(sealed["completeCausalWriterPCSequenceCaptured"])
        self.assertTrue(sealed["knownAggregateStateTransferPassed"])
        self.assertFalse(sealed["writerInstructionSemanticsOpened"])
        self.assertFalse(sealed["productionShaderAuthorized"])

    def test_breakpoint_retirement_identity_is_exact(self):
        document, base = passing_documents()
        retirement = document["inheritedWriterBreakpointRetirement"]
        retirement["retired"][0]["breakpointID"] += 1
        with self.assertRaisesRegex(ValueError, "retired writer breakpoint"):
            self.validate_documents(document, base)

    def test_disabled_writer_state_is_observed_not_assumed(self):
        document, base = passing_documents()
        retirement = document["inheritedWriterBreakpointRetirement"]
        retirement["retired"][0]["enabledAfterRetirement"] = True
        with self.assertRaisesRegex(ValueError, "retired writer breakpoint"):
            self.validate_documents(document, base)

    def test_retirement_must_precede_first_hardware_epoch(self):
        document, base = passing_documents()
        document["callbackOrder"][1]["kind"] = "depth-four-zero-epoch"
        document["callbackOrder"][2]["kind"] = "inherited-writer-breakpoints-retired"
        document["inheritedWriterBreakpointRetirement"]["callbackSequence"] = 3
        document["epochRecords"][0]["callbackSequence"] = 2
        with self.assertRaisesRegex(ValueError, "retirement timing differs"):
            self.validate_documents(document, base)

    def test_retirement_pc_is_the_independent_source_selector(self):
        document, base = passing_documents()
        document["inheritedWriterBreakpointRetirement"]["pc"] += 4
        with self.assertRaisesRegex(ValueError, "breakpoint retirement differs"):
            self.validate_documents(document, base)

    def test_inherited_marker_context_cannot_be_replaced(self):
        document, base = passing_documents()
        base["selectedFrame"]["selectedSource"] += 8
        with self.assertRaisesRegex(ValueError, "selected marker identity differs"):
            self.validate_documents(document, base)

    def test_known_transfer_is_bit_exact_and_ordered(self):
        carrier = 481.25
        states = [
            bytes(32),
            struct.pack("<4d", carrier, -97.25, 640.0, 640.0),
            struct.pack("<4d", carrier, -105.25, 640.0, 648.0),
            struct.pack("<4d", 480.0, -105.25, 641.25, 649.25),
        ]
        result = validator._known_state_transfer(states, states[-1])
        self.assertEqual(result["carrierP"], carrier)
        self.assertEqual(result["integerOriginL"], 480)
        self.assertEqual(result["stateIndices"], [0, 1, 2, 3])

    def test_previous_collision_trace_still_fails_known_transfer(self):
        carrier = 491.9310302734375
        marker = struct.pack(
            "<4d", 490.0, -115.9310302734375, 641.9310302734375, 649.9310302734375
        )
        observed = [
            bytes(32),
            struct.pack("<4d", carrier, -107.9310302734375, 640.0, 640.0),
            struct.pack(
                "<4d",
                -0.3512069702148437,
                -0.3512069702148437,
                640.7024139404297,
                648.3512069702149,
            ),
            marker,
        ]
        with self.assertRaisesRegex(ValueError, "known aggregate state transfer"):
            validator._known_state_transfer(observed, marker)

    def test_missing_hardware_lane_fails_closed(self):
        document, base = passing_documents()
        document["watchpointGroups"][0]["watchpoints"].pop()
        with self.assertRaisesRegex(ValueError, "watchpoint group 0 differs"):
            self.validate_documents(document, base)

    def test_duplicate_shared_breakpoint_identity_fails_closed(self):
        document, base = passing_documents()
        document["prepareLayer"]["epochMarker"]["breakpointID"] = 14
        with self.assertRaisesRegex(ValueError, "breakpoint identities differ"):
            self.validate_documents(document, base)

    def test_discontinuous_full_aggregate_chain_fails_closed(self):
        document, base = passing_documents()
        document["qualifiedWatchpointEvents"][1]["beforeHex"] = bytes(32).hex()
        with self.assertRaisesRegex(ValueError, "event 1 chain differs"):
            self.validate_documents(document, base)

    def test_marker_must_match_last_hardware_state_bit_for_bit(self):
        document, base = passing_documents()
        altered = struct.pack("<4d", 491.0, -115.0, 642.0, 650.0)
        selected = document["selectedFrame"]
        selected["aggregateAtMarkerHex"] = altered.hex()
        selected["roleStateAtMarker"] = frame_fixture.memory_snapshot(
            ROLE_BASE, frame_fixture.role_state(altered)
        )
        with self.assertRaisesRegex(ValueError, "marker closure differs"):
            self.validate_documents(document, base)

    def test_any_ignored_watchpoint_hit_fails_closed(self):
        document, base = passing_documents()
        document["ignoredWatchpointHitCount"] = 1
        document["rawWatchpointHitCount"] = 4
        with self.assertRaisesRegex(ValueError, "bounded accounting differs"):
            self.validate_documents(document, base)

    def test_no_new_changed_writer_PC_fails_closed(self):
        document, base = passing_documents()
        with (
            mock.patch.object(
                validator,
                "KNOWN_SAMPLED_WRITER_AFTER_OFFSETS",
                (*validator.KNOWN_SAMPLED_WRITER_AFTER_OFFSETS, 0x2504, 0x2604),
            ),
            self.assertRaisesRegex(ValueError, "selected causal chain differs"),
        ):
            self.validate_documents(document, base)

    def test_wrong_selected_frame_pointer_fails_closed(self):
        document, base = passing_documents()
        document["selectedFrame"]["frameIdentity"]["framePointer"] += 8
        with self.assertRaisesRegex(ValueError, "selected identity differs"):
            self.validate_documents(document, base)

    def test_duplicate_structural_frame_pointer_fails_closed(self):
        document, base = passing_documents()
        frames = document["epochRecords"][0]["prepareFrames"]
        frames[1]["unwindFramePointer"] = frames[0]["unwindFramePointer"]
        with self.assertRaisesRegex(ValueError, "prepare frame pointers differ"):
            self.validate_documents(document, base)

    def test_event_must_match_armed_unwind_frame_pointer(self):
        document, base = passing_documents()
        document["qualifiedWatchpointEvents"][0]["prepareFramePointer"] += 8
        with self.assertRaisesRegex(ValueError, "prepare ancestry differs"):
            self.validate_documents(document, base)

    def test_rejection_counter_without_diagnostic_fails_closed(self):
        document, base = passing_documents()
        document["rejectedEpochDepthCount"] = 1
        with self.assertRaisesRegex(ValueError, "diagnostic accounting differs"):
            self.validate_documents(document, base)

    def test_source_unknown_rejection_is_retained_without_affecting_result(self):
        document, base = passing_documents()
        epoch_pc = PREPARE_START + validator.EPOCH_MARKER_OFFSET
        structural = prepare_frames(epoch_pc)[:3]
        document["sourceUnknownEpochCount"] = 1
        document["epochMarkerHitCount"] = 2
        document["rejectedMarkerDiagnostics"] = [
            {
                "diagnosticIndex": 0,
                "marker": "epoch",
                "reason": "source-unknown",
                "markerHitIndex": 1,
                "threadID": THREAD_ID,
                "pc": epoch_pc,
                "selectedSource": None,
                "observedX28": None,
                "structuralPrepareRecursionDepth": 3,
                "backtrace": [item["frame"] for item in structural],
                "prepareFrames": structural,
            }
        ]
        document["finalRejectedMarkerDiagnosticCount"] = 1
        result = self.validate_documents(document, base)
        self.assertEqual(result["conclusion"], "success")


if __name__ == "__main__":
    unittest.main()
