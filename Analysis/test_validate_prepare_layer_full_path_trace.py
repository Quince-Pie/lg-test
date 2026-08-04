#!/usr/bin/env python3
"""Tests for the sealed full-code/path/aggregate-writer validator."""

import copy
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import test_validate_capture_backdrop_writer_trace as writer_fixture
import test_validate_layer_shapes_construction_trace as construction_fixture
import validate_prepare_layer_full_path_trace as validator


PREPARE_START = construction_fixture.PREPARE_START
MODULE = construction_fixture.MODULE


def memory_snapshot(address, payload):
    return {
        "address": address,
        "byteCount": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "hex": payload.hex(),
    }


def marker_registers(x19, source, pc):
    values = {name: 0 for name in validator.MARKER_REGISTER_NAMES}
    values.update(
        {
            "x19": x19,
            "x28": source,
            "x29": x19 - 0x100,
            "x30": pc + 0x100,
            "sp": x19 - 0x200,
            "pc": pc,
        }
    )
    return [
        writer_fixture.raw_register(name, 8, values[name])
        for name in validator.MARKER_REGISTER_NAMES
    ]


def role_state(aggregate):
    payload = bytearray(validator.ROLE_STATE_BYTE_COUNT)
    payload[
        validator.AGGREGATE_OFFSET : validator.AGGREGATE_OFFSET
        + validator.AGGREGATE_BYTE_COUNT
    ] = aggregate
    return bytes(payload)


def passing_trace():
    base_document, _prepare_hash, _helper_hash, _symbol_hash = (
        construction_fixture.passing_trace()
    )
    chain = copy.deepcopy(base_document["objectChain"])
    chain["callbackSequence"] = 3
    addresses = chain["addresses"]
    source = addresses["source"]

    full_code = bytearray(validator.PREPARE_LAYER_SYMBOL_BYTE_COUNT)
    known_windows = tuple(
        (
            offset,
            count,
            hashlib.sha256(full_code[offset : offset + count]).hexdigest(),
        )
        for offset, count, _digest in validator.KNOWN_PREPARE_LAYER_WINDOWS
    )
    configuration = copy.deepcopy(validator.EXPECTED_CONFIGURATION)
    configuration["knownPrepareLayerWindows"] = [
        {"offset": offset, "byteCount": count, "sha256": digest}
        for offset, count, digest in known_windows
    ]
    marker_static = []
    for index, (name, offset, watch_arm) in enumerate(
        validator.PATH_MARKERS, start=3
    ):
        marker_static.append(
            {
                "name": name,
                "offset": offset,
                "address": PREPARE_START + offset,
                "breakpointID": index,
                "watchArmCandidate": watch_arm,
                "instructionRawLittleEndianHex": bytes(
                    full_code[offset : offset + 4]
                ).hex(),
            }
        )

    aggregates = [
        struct.pack("<4d", 490.0, -115.0, 642.0, 650.0),
        struct.pack("<4d", 480.0, -105.0, 642.0, 650.0),
        struct.pack("<4d", 460.0, -85.0, 642.0, 650.0),
        struct.pack("<4d", 460.0, -85.0, 642.0, 650.0),
    ]
    marker_records = []
    marker_sequences = [4, 6, 7, 8]
    marker_names = list(validator.LATER_SELECTED_MARKER_NAMES)
    role_base = 0x71_0000_0000
    for index, (name, aggregate, callback_sequence) in enumerate(
        zip(marker_names, aggregates, marker_sequences, strict=True)
    ):
        offset = validator.MARKER_BY_NAME[name]["offset"]
        pc = PREPARE_START + offset
        role = role_state(aggregate)
        marker_records.append(
            {
                "recordIndex": index,
                "callbackSequence": callback_sequence,
                "markerName": name,
                "markerOffset": offset,
                "watchArmCandidate": True,
                "selectedSource": True,
                "sourceKnownAtHit": True,
                "threadID": 71,
                "pc": pc,
                "frame": construction_fixture.frame(pc),
                "backtrace": [construction_fixture.frame(pc)],
                "registers": marker_registers(role_base, source, pc),
                "addresses": {
                    "x19": role_base,
                    "source": source,
                    "aggregate": role_base + validator.AGGREGATE_OFFSET,
                    "alternateSource": role_base
                    + validator.ALTERNATE_SOURCE_OFFSET,
                    "recursiveChild": role_base
                    + validator.RECURSIVE_CHILD_OFFSET,
                },
                "roleState": memory_snapshot(role_base, role),
                "aggregateHex": aggregate.hex(),
                "alternateSourceHex": "00" * validator.AGGREGATE_BYTE_COUNT,
                "recursiveChildHex": "00" * validator.AGGREGATE_BYTE_COUNT,
            }
        )

    initial_role = role_state(aggregates[0])
    after_role = role_state(aggregates[1])
    initial = aggregates[0][: validator.WATCHPOINT_BYTE_COUNT]
    after = aggregates[1][: validator.WATCHPOINT_BYTE_COUNT]
    writer_pc = PREPARE_START + 0x3000
    writer_frame = writer_fixture.frame(
        writer_pc,
        validator.merge_base.PREPARE_LAYER_FUNCTION,
        symbol_offset=0x3000,
    )
    code = bytes([0xA5]) * validator.PC_CENTERED_CODE_WINDOW_BYTE_COUNT
    callback_order = [
        {"sequence": 1, "kind": "prepare-layer-entry"},
        {"sequence": 2, "kind": "capture-backdrop-entry"},
        {"sequence": 3, "kind": "source-selected"},
        {"sequence": 4, "kind": "marker:sourceLaterHandle"},
        {"sequence": 5, "kind": "aggregate-watchpoint-armed"},
        {"sequence": 6, "kind": "marker:sourceLaterOwnerRectangle"},
        {"sequence": 7, "kind": "marker:sourceLaterIntegerOrigin"},
        {"sequence": 8, "kind": "marker:sourceLaterIntegerTail"},
        {"sequence": 9, "kind": "aggregate-watchpoint-hit"},
    ]
    hit_counts = {name: 0 for name in validator.MARKER_BY_NAME}
    for name in marker_names:
        hit_counts[name] = 1
    helper_address = PREPARE_START + validator.UNION_HELPER_RELATIVE_TO_PREPARE_LAYER
    trace = {
        "prepareLayerFullPathTraceSchemaVersion": (
            validator.EXPECTED_TRACE_SCHEMA_VERSION
        ),
        "classification": validator.EXPECTED_CLASSIFICATION,
        "status": "finalized",
        "statusBeforeFinalization": "source-selected-path-trace-active",
        "configuration": configuration,
        "callbackOrder": callback_order,
        "captureBackdropEntryBreakpointID": 1,
        "prepareLayerEntryBreakpointID": 2,
        "captureBackdrop": {
            "callbackSequence": 2,
            "symbolAddress": 0x194400000,
            "codeByteCount": validator.CAPTURE_BACKDROP_CODE_BYTE_COUNT,
            "codeSHA256": validator.merge_base.CAPTURE_BACKDROP_CODE_SHA256,
            "module": MODULE,
            "lateBreakpointID": 16,
        },
        "prepareLayer": {
            "callbackSequence": 1,
            "callbackPC": PREPARE_START,
            "callbackLocationAddress": PREPARE_START,
            "entryBreakpointID": 2,
            "entryBreakpointLocationAddresses": [PREPARE_START],
            "function": validator.merge_base.PREPARE_LAYER_FUNCTION,
            "symbolStart": PREPARE_START,
            "symbolEnd": PREPARE_START + validator.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            "symbolByteCount": validator.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            "module": MODULE,
            "fullCode": memory_snapshot(PREPARE_START, bytes(full_code)),
            "knownWindows": [
                {"offset": offset, "byteCount": count, "sha256": digest}
                for offset, count, digest in known_windows
            ],
            "unionHelper": {
                "address": helper_address,
                "relativeToPrepareLayer": (
                    validator.UNION_HELPER_RELATIVE_TO_PREPARE_LAYER
                ),
                "module": MODULE,
                "symbol": {
                    "valid": True,
                    "name": validator.UNION_HELPER_SYMBOL_NAME,
                    "startAddress": helper_address,
                    "endAddress": helper_address
                    + validator.UNION_HELPER_SYMBOL_BYTE_COUNT,
                },
                "symbolCodeSHA256": validator.UNION_HELPER_SYMBOL_SHA256,
            },
            "markers": marker_static,
        },
        "lateCandidateCount": 1,
        "lateCandidateDiagnostics": [],
        "objectChain": chain,
        "markerRecords": marker_records,
        "aggregateWatchpoint": {
            "callbackSequence": 5,
            "id": 17,
            "deprecatedHardwareIndex": -1,
            "markerName": marker_names[0],
            "markerRecordIndex": 0,
            "armMode": "live-selected-marker",
            "selectedSource": source,
            "roleBase": role_base,
            "address": role_base + validator.AGGREGATE_OFFSET,
            "byteCount": validator.WATCHPOINT_BYTE_COUNT,
            "initialHex": initial.hex(),
            "initialRoleStateSHA256": hashlib.sha256(initial_role).hexdigest(),
            "initialRoleStateHex": initial_role.hex(),
        },
        "codeWindows": [
            {
                "startAddress": writer_pc
                - validator.PC_CENTERED_CODE_WINDOW_BACKTRACK,
                "byteCount": len(code),
                "source": "pc-centered",
                "stopPCOffset": validator.PC_CENTERED_CODE_WINDOW_BACKTRACK,
                "containsStopPC": True,
                "sha256": hashlib.sha256(code).hexdigest(),
                "hex": code.hex(),
            }
        ],
        "watchpointEvents": [
            {
                "eventIndex": 0,
                "callbackSequence": 9,
                "watchpointID": 17,
                "watchpointHitIndex": 1,
                "threadID": 71,
                "stopPC": writer_pc,
                "watchedAddress": role_base + validator.AGGREGATE_OFFSET,
                "beforeHex": initial.hex(),
                "afterHex": after.hex(),
                "valueChanged": True,
                "frame": writer_frame,
                "backtrace": [writer_frame],
                "codeWindowIndex": 0,
                "roleStateAfter": memory_snapshot(role_base, after_role),
                "privateFieldsAfter": writer_fixture.private_fields(),
                "operandSnapshot": writer_fixture.operand_snapshot(
                    addresses, writer_pc, is_prepare_layer=True
                ),
            }
        ],
        "failures": [],
        "finalFailureCount": 0,
        "finalCallbackSequence": 9,
        "markerHitCounts": hit_counts,
        "rejectedMarkerCounts": {name: 0 for name in validator.MARKER_BY_NAME},
        "discardedMarkerCounts": {name: 0 for name in validator.MARKER_BY_NAME},
        "finalMarkerRecordCount": len(marker_records),
        "finalSelectedMarkerRecordCount": len(marker_records),
        "finalSelectedLaterMarkerRecordCount": len(marker_records),
        "finalWatchpointEventCount": 1,
        "finalChangedWatchpointEventCount": 1,
        "watchpointHitCount": 1,
    }
    return trace, known_windows


class PrepareLayerFullPathTraceValidatorTests(unittest.TestCase):
    def validate_document(self, document, known_windows):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prepare-layer-full-path-trace.json"
            path.write_text(
                json.dumps(document, sort_keys=True, allow_nan=False) + "\n",
                encoding="utf-8",
            )
            with (
                mock.patch.object(
                    validator, "KNOWN_PREPARE_LAYER_WINDOWS", known_windows
                ),
                mock.patch.dict(
                    validator.EXPECTED_CONFIGURATION,
                    {
                        "knownPrepareLayerWindows": [
                            {
                                "offset": offset,
                                "byteCount": count,
                                "sha256": digest,
                            }
                            for offset, count, digest in known_windows
                        ]
                    },
                ),
            ):
                return validator.validate(path)

    def test_passing_trace_retains_only_sealed_claims(self):
        document, known_windows = passing_trace()
        result = self.validate_document(document, known_windows)
        self.assertEqual(result["conclusion"], "success")
        self.assertEqual(result["aggregate"]["watchpointEventCount"], 1)
        self.assertTrue(
            result["sealedConclusion"]["selectedAggregateWriterEventCaptured"]
        )
        self.assertFalse(
            result["sealedConclusion"]["writerInstructionSemanticsOpened"]
        )
        self.assertFalse(result["sealedConclusion"]["productionShaderAuthorized"])

    def test_retrospective_source_selection_arm_passes_exact_provenance(self):
        document, known_windows = passing_trace()
        document["callbackOrder"] = [
            {"sequence": 1, "kind": "prepare-layer-entry"},
            {"sequence": 2, "kind": "marker:sourceLaterHandle"},
            {"sequence": 3, "kind": "capture-backdrop-entry"},
            {"sequence": 4, "kind": "source-selected"},
            {"sequence": 5, "kind": "aggregate-watchpoint-armed"},
            {"sequence": 6, "kind": "marker:sourceLaterOwnerRectangle"},
            {"sequence": 7, "kind": "marker:sourceLaterIntegerOrigin"},
            {"sequence": 8, "kind": "marker:sourceLaterIntegerTail"},
            {"sequence": 9, "kind": "aggregate-watchpoint-hit"},
        ]
        document["captureBackdrop"]["callbackSequence"] = 3
        document["objectChain"]["callbackSequence"] = 4
        document["markerRecords"][0]["callbackSequence"] = 2
        document["markerRecords"][0]["sourceKnownAtHit"] = False
        document["aggregateWatchpoint"]["armMode"] = (
            "retrospective-source-selection"
        )
        result = self.validate_document(document, known_windows)
        self.assertTrue(result["prospectiveGatePassed"])

    def test_nonentry_prepare_callback_fails_closed(self):
        document, known_windows = passing_trace()
        document["prepareLayer"]["callbackPC"] += 4
        with self.assertRaisesRegex(ValueError, "exact entry"):
            self.validate_document(document, known_windows)

    def test_missing_selected_later_marker_fails_closed(self):
        document, known_windows = passing_trace()
        removed = document["markerRecords"].pop()
        document["finalMarkerRecordCount"] -= 1
        document["finalSelectedMarkerRecordCount"] -= 1
        document["finalSelectedLaterMarkerRecordCount"] -= 1
        document["markerHitCounts"][removed["markerName"]] = 0
        with self.assertRaisesRegex(ValueError, "selected later marker coverage"):
            self.validate_document(document, known_windows)

    def test_watchpoint_role_alias_tampering_fails_closed(self):
        document, known_windows = passing_trace()
        role = bytearray.fromhex(
            document["watchpointEvents"][0]["roleStateAfter"]["hex"]
        )
        role[validator.AGGREGATE_OFFSET] ^= 0x01
        document["watchpointEvents"][0]["roleStateAfter"] = memory_snapshot(
            document["aggregateWatchpoint"]["roleBase"], bytes(role)
        )
        with self.assertRaisesRegex(ValueError, "watched role alias"):
            self.validate_document(document, known_windows)

    def test_watchpoint_before_chain_tampering_fails_closed(self):
        document, known_windows = passing_trace()
        document["watchpointEvents"][0]["beforeHex"] = "00" * 8
        with self.assertRaisesRegex(ValueError, "watchpoint event 0 identity"):
            self.validate_document(document, known_windows)

    def test_marker_accounting_tampering_fails_closed(self):
        document, known_windows = passing_trace()
        document["markerHitCounts"]["sourceLaterHandle"] += 1
        with self.assertRaisesRegex(ValueError, "marker accounting"):
            self.validate_document(document, known_windows)


if __name__ == "__main__":
    unittest.main()
