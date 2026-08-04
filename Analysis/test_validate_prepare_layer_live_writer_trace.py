#!/usr/bin/env python3
"""Tests for the sealed live-frame-qualified writer validator."""

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
import validate_prepare_layer_live_writer_trace as validator


PREPARE_START = construction_fixture.PREPARE_START
MODULE = construction_fixture.MODULE


def memory_snapshot(address, payload):
    return {
        "address": address,
        "byteCount": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "hex": payload.hex(),
    }


def prepare_registers(role_base, source, pc):
    values = {name: 0 for name in validator.PREPARE_FRAME_REGISTER_NAMES}
    values.update(
        {
            "x19": role_base,
            "x28": source,
            "x29": role_base + 0x700,
            "x30": pc + 0x100,
            "sp": role_base - 0x100,
            "pc": pc,
        }
    )
    return [
        writer_fixture.raw_register(name, 8, values[name])
        for name in validator.PREPARE_FRAME_REGISTER_NAMES
    ]


def role_state(aggregate):
    payload = bytearray(validator.full_base.ROLE_STATE_BYTE_COUNT)
    payload[
        validator.full_base.AGGREGATE_OFFSET : validator.full_base.AGGREGATE_OFFSET
        + validator.full_base.AGGREGATE_BYTE_COUNT
    ] = aggregate
    return bytes(payload)


def direct_operand_snapshot(addresses, pc, role_base):
    snapshot = writer_fixture.operand_snapshot(
        addresses, pc, is_prepare_layer=True
    )
    general = snapshot["registers"]["general"]
    x19_index = next(
        index for index, record in enumerate(general) if record["name"] == "x19"
    )
    general[x19_index] = writer_fixture.raw_register("x19", 8, role_base)
    values = {record["name"]: record["unsignedValue"] for record in general}

    pointer_groups = {}
    for name in validator.full_base.POINTER_PROBE_REGISTER_NAMES:
        address = values[name]
        if not (
            validator.full_base.MINIMUM_POINTER_PROBE_ADDRESS
            <= address
            <= validator.full_base.MAXIMUM_POINTER_PROBE_ADDRESS
        ):
            continue
        start = address - validator.full_base.REGISTER_POINTER_SNAPSHOT_BACKTRACK
        pointer_groups.setdefault(start, []).append(name)
    pointer_probes = []
    for index, (start, names) in enumerate(sorted(pointer_groups.items()), start=1):
        probe = writer_fixture.raw_snapshot(
            start,
            validator.full_base.REGISTER_POINTER_SNAPSHOT_BYTE_COUNT,
            index,
        )
        probe.update(
            {
                "registerNames": names,
                "registerValue": start
                + validator.full_base.REGISTER_POINTER_SNAPSHOT_BACKTRACK,
            }
        )
        pointer_probes.append(probe)
    snapshot["registerPointerProbeCount"] = len(pointer_probes)
    snapshot["registerPointerProbes"] = pointer_probes
    snapshot["registerPointerProbeFailures"] = []

    role_groups = {}
    for name in validator.full_base.PREPARE_LAYER_ROLE_REGISTER_NAMES:
        role_groups.setdefault(values[name], []).append(name)
    role_probes = []
    for index, (address, names) in enumerate(sorted(role_groups.items()), start=1):
        probe = writer_fixture.raw_snapshot(
            address, validator.full_base.ROLE_STATE_BYTE_COUNT, index + 16
        )
        probe.update({"registerNames": names, "registerValue": address})
        role_probes.append(probe)
    snapshot["prepareLayerRoleProbeCount"] = len(role_probes)
    snapshot["prepareLayerRoleProbes"] = role_probes
    snapshot["prepareLayerRoleProbeFailures"] = []
    return snapshot


def marker_record(index, callback, role_base, source, aggregate, *, source_known):
    pc = PREPARE_START + validator.LIVE_ARM_MARKER_OFFSET
    role = role_state(aggregate)
    return {
        "recordIndex": index,
        "callbackSequence": callback,
        "sourceKnownAtHit": source_known,
        "selectedSource": True,
        "threadID": 71,
        "pc": pc,
        "frame": construction_fixture.frame(pc),
        "backtrace": [construction_fixture.frame(pc)],
        "roleBase": role_base,
        "source": source,
        "registers": prepare_registers(role_base, source, pc),
        "roleState": memory_snapshot(role_base, role),
        "aggregateHex": aggregate.hex(),
    }


def passing_trace():
    base_document, _prepare_hash, _helper_hash, _symbol_hash = (
        construction_fixture.passing_trace()
    )
    chain = copy.deepcopy(base_document["objectChain"])
    chain["callbackSequence"] = 4
    addresses = chain["addresses"]
    source = addresses["source"]

    full_code = bytearray(validator.full_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT)
    full_hash = hashlib.sha256(full_code).hexdigest()
    known_windows = tuple(
        (
            offset,
            count,
            hashlib.sha256(full_code[offset : offset + count]).hexdigest(),
        )
        for offset, count, _digest in validator.full_base.KNOWN_PREPARE_LAYER_WINDOWS
    )
    configuration = copy.deepcopy(validator.EXPECTED_CONFIGURATION)
    configuration["prepareLayerFullCodeSHA256"] = full_hash
    configuration["knownPrepareLayerWindows"] = [
        {"offset": offset, "byteCount": count, "sha256": digest}
        for offset, count, digest in known_windows
    ]

    stale_role_base = 0x71_0000_1800
    role_base = 0x71_0000_1000
    preselection_aggregate = struct.pack("<4d", 501.0, -126.0, 644.0, 652.0)
    initial_aggregate = struct.pack("<4d", 490.0, -115.0, 642.0, 650.0)
    intermediate_aggregate = struct.pack("<4d", 489.0, -114.0, 642.0, 650.0)
    after_aggregate = struct.pack("<4d", 480.0, -105.0, 642.0, 650.0)
    marker_records = [
        marker_record(
            0,
            2,
            stale_role_base,
            source,
            preselection_aggregate,
            source_known=False,
        ),
        marker_record(
            1,
            5,
            role_base,
            source,
            initial_aggregate,
            source_known=True,
        ),
    ]

    writer_pc = PREPARE_START + 0xB60
    writer_frame = construction_fixture.frame(writer_pc)
    code = bytes([0xA5]) * validator.full_base.PC_CENTERED_CODE_WINDOW_BYTE_COUNT
    helper_address = (
        PREPARE_START + validator.full_base.UNION_HELPER_RELATIVE_TO_PREPARE_LAYER
    )
    trace = {
        "prepareLayerLiveWriterTraceSchemaVersion": (
            validator.EXPECTED_TRACE_SCHEMA_VERSION
        ),
        "classification": validator.EXPECTED_CLASSIFICATION,
        "status": "finalized",
        "statusBeforeFinalization": "qualified-live-writer-captured",
        "configuration": configuration,
        "callbackOrder": [
            {"sequence": 1, "kind": "prepare-layer-entry"},
            {"sequence": 2, "kind": "live-arm-marker"},
            {"sequence": 3, "kind": "capture-backdrop-entry"},
            {"sequence": 4, "kind": "source-selected"},
            {"sequence": 5, "kind": "live-arm-marker"},
            {"sequence": 6, "kind": "live-aggregate-watchpoint-armed"},
            {
                "sequence": 7,
                "kind": "qualified-live-aggregate-watchpoint-hit",
            },
        ],
        "captureBackdropEntryBreakpointID": 1,
        "prepareLayerEntryBreakpointID": 2,
        "captureBackdrop": {
            "callbackSequence": 3,
            "symbolAddress": 0x1944_0000_0,
            "codeByteCount": validator.full_base.CAPTURE_BACKDROP_CODE_BYTE_COUNT,
            "codeSHA256": validator.merge_base.CAPTURE_BACKDROP_CODE_SHA256,
            "module": MODULE,
            "lateBreakpointID": 4,
        },
        "prepareLayer": {
            "callbackSequence": 1,
            "callbackPC": PREPARE_START,
            "callbackLocationAddress": PREPARE_START,
            "entryBreakpointID": 2,
            "entryBreakpointLocationAddresses": [PREPARE_START],
            "function": validator.merge_base.PREPARE_LAYER_FUNCTION,
            "symbolStart": PREPARE_START,
            "symbolEnd": (
                PREPARE_START + validator.full_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT
            ),
            "symbolByteCount": validator.full_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            "module": MODULE,
            "fullCode": memory_snapshot(PREPARE_START, bytes(full_code)),
            "knownWindows": [
                {"offset": offset, "byteCount": count, "sha256": digest}
                for offset, count, digest in known_windows
            ],
            "unionHelper": {
                "address": helper_address,
                "relativeToPrepareLayer": (
                    validator.full_base.UNION_HELPER_RELATIVE_TO_PREPARE_LAYER
                ),
                "module": MODULE,
                "symbol": {
                    "valid": True,
                    "name": validator.full_base.UNION_HELPER_SYMBOL_NAME,
                    "startAddress": helper_address,
                    "endAddress": (
                        helper_address
                        + validator.full_base.UNION_HELPER_SYMBOL_BYTE_COUNT
                    ),
                },
                "symbolCodeSHA256": (
                    validator.full_base.UNION_HELPER_SYMBOL_SHA256
                ),
            },
            "liveArmMarker": {
                "name": validator.LIVE_ARM_MARKER_NAME,
                "offset": validator.LIVE_ARM_MARKER_OFFSET,
                "address": PREPARE_START + validator.LIVE_ARM_MARKER_OFFSET,
                "breakpointID": 3,
                "instructionRawLittleEndianHex": bytes(
                    full_code[
                        validator.LIVE_ARM_MARKER_OFFSET : validator.LIVE_ARM_MARKER_OFFSET
                        + 4
                    ]
                ).hex(),
            },
        },
        "lateCandidateCount": 1,
        "lateCandidateDiagnostics": [],
        "objectChain": chain,
        "liveArmMarkerRecords": marker_records,
        "aggregateWatchpoint": {
            "callbackSequence": 6,
            "id": 1,
            "deprecatedHardwareIndex": -1,
            "markerRecordIndex": 1,
            "markerCallbackSequence": 5,
            "roleBase": role_base,
            "selectedSource": source,
            "address": role_base + validator.full_base.AGGREGATE_OFFSET,
            "byteCount": validator.full_base.WATCHPOINT_BYTE_COUNT,
            "initialHex": initial_aggregate[
                : validator.full_base.WATCHPOINT_BYTE_COUNT
            ].hex(),
            "initialRoleStateSHA256": hashlib.sha256(
                role_state(initial_aggregate)
            ).hexdigest(),
            "initialRoleStateHex": role_state(initial_aggregate).hex(),
        },
        "ignoredWatchpointDiagnostics": [
            {
                "stopPC": 0x1800_0010_0,
                "function": "_os_log_fmt_flatten_object_impl",
                "module": {
                    "valid": True,
                    "path": "/usr/lib/system/libsystem_trace.dylib",
                    "loadAddress": 0x1800_0000_0,
                },
                "exactPrepareFrameSeen": False,
                "hitCount": 1,
                "changedCount": 1,
                "firstBeforeHex": initial_aggregate[
                    : validator.full_base.WATCHPOINT_BYTE_COUNT
                ].hex(),
                "lastAfterHex": intermediate_aggregate[
                    : validator.full_base.WATCHPOINT_BYTE_COUNT
                ].hex(),
            }
        ],
        "codeWindows": [
            {
                "startAddress": (
                    writer_pc - validator.full_base.PC_CENTERED_CODE_WINDOW_BACKTRACK
                ),
                "byteCount": len(code),
                "source": "pc-centered",
                "stopPCOffset": validator.full_base.PC_CENTERED_CODE_WINDOW_BACKTRACK,
                "containsStopPC": True,
                "sha256": hashlib.sha256(code).hexdigest(),
                "hex": code.hex(),
            }
        ],
        "qualifiedWatchpointEvents": [
            {
                "eventIndex": 0,
                "callbackSequence": 7,
                "watchpointID": 1,
                "rawWatchpointHitIndex": 2,
                "qualifiedWatchpointHitIndex": 1,
                "threadID": 71,
                "stopPC": writer_pc,
                "watchedAddress": role_base + validator.full_base.AGGREGATE_OFFSET,
                "beforeHex": intermediate_aggregate[
                    : validator.full_base.WATCHPOINT_BYTE_COUNT
                ].hex(),
                "afterHex": after_aggregate[
                    : validator.full_base.WATCHPOINT_BYTE_COUNT
                ].hex(),
                "valueChanged": True,
                "frame": writer_frame,
                "backtrace": [writer_frame],
                "prepareFrameIndex": 0,
                "prepareFrame": writer_frame,
                "prepareFrameRegisters": prepare_registers(
                    role_base, source, writer_pc
                ),
                "codeWindowIndex": 0,
                "roleStateAfter": memory_snapshot(
                    role_base, role_state(after_aggregate)
                ),
                "privateFieldsAfter": writer_fixture.private_fields(),
                "operandSnapshot": direct_operand_snapshot(
                    addresses, writer_pc, role_base
                ),
            }
        ],
        "failures": [],
        "finalFailureCount": 0,
        "finalCallbackSequence": 7,
        "markerHitCount": 2,
        "rejectedMarkerHitCount": 0,
        "discardedMarkerHitCount": 0,
        "finalMarkerRecordCount": 2,
        "finalSelectedMarkerRecordCount": 2,
        "rawWatchpointHitCount": 2,
        "ignoredWatchpointHitCount": 1,
        "ignoredPrepareFrameSeenCount": 0,
        "unretainedIgnoredWatchpointHitCount": 0,
        "qualifiedWatchpointHitCount": 1,
        "finalQualifiedWatchpointEventCount": 1,
        "finalChangedQualifiedWatchpointEventCount": 1,
    }
    return trace, known_windows, full_hash


def convert_event_to_helper(document):
    event = document["qualifiedWatchpointEvents"][0]
    role_base = document["aggregateWatchpoint"]["roleBase"]
    source = document["aggregateWatchpoint"]["selectedSource"]
    addresses = document["objectChain"]["addresses"]
    helper_pc = PREPARE_START - 0xA00
    prepare_pc = PREPARE_START + 0x32C4
    helper_frame = writer_fixture.frame(
        helper_pc,
        validator.full_base.UNION_HELPER_SYMBOL_NAME,
        symbol_offset=0xA0,
    )
    prepare_frame = construction_fixture.frame(prepare_pc)
    prepare_frame["frameIndex"] = 1
    event["stopPC"] = helper_pc
    event["frame"] = helper_frame
    event["backtrace"] = [helper_frame, prepare_frame]
    event["prepareFrameIndex"] = 1
    event["prepareFrame"] = prepare_frame
    event["prepareFrameRegisters"] = prepare_registers(
        role_base, source, prepare_pc
    )
    event["operandSnapshot"] = writer_fixture.operand_snapshot(
        addresses, helper_pc, is_prepare_layer=False
    )
    code = bytes([0x5A]) * validator.full_base.PC_CENTERED_CODE_WINDOW_BYTE_COUNT
    document["codeWindows"] = [
        {
            "startAddress": (
                helper_pc - validator.full_base.PC_CENTERED_CODE_WINDOW_BACKTRACK
            ),
            "byteCount": len(code),
            "source": "pc-centered",
            "stopPCOffset": validator.full_base.PC_CENTERED_CODE_WINDOW_BACKTRACK,
            "containsStopPC": True,
            "sha256": hashlib.sha256(code).hexdigest(),
            "hex": code.hex(),
        }
    ]


class PrepareLayerLiveWriterTraceValidatorTests(unittest.TestCase):
    def validate_document(self, document, known_windows, full_hash):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prepare-layer-live-writer-trace.json"
            path.write_text(
                json.dumps(document, sort_keys=True, allow_nan=False) + "\n",
                encoding="utf-8",
            )
            with (
                mock.patch.object(
                    validator,
                    "PREPARE_LAYER_FULL_CODE_SHA256",
                    full_hash,
                ),
                mock.patch.object(
                    validator.full_base,
                    "KNOWN_PREPARE_LAYER_WINDOWS",
                    known_windows,
                ),
                mock.patch.dict(
                    validator.EXPECTED_CONFIGURATION,
                    {
                        "prepareLayerFullCodeSHA256": full_hash,
                        "knownPrepareLayerWindows": [
                            {
                                "offset": offset,
                                "byteCount": count,
                                "sha256": digest,
                            }
                            for offset, count, digest in known_windows
                        ],
                    },
                ),
            ):
                return validator.validate(path)

    def test_direct_writer_passes_but_semantics_and_parity_remain_sealed(self):
        document, known_windows, full_hash = passing_trace()
        result = self.validate_document(document, known_windows, full_hash)
        self.assertEqual(result["conclusion"], "success")
        self.assertEqual(result["aggregate"]["ignoredWatchpointHitCount"], 1)
        self.assertEqual(result["aggregate"]["qualifiedWatchpointEventCount"], 1)
        self.assertTrue(
            result["sealedConclusion"]["qualifiedSelectedWriterEventCaptured"]
        )
        self.assertFalse(
            result["sealedConclusion"]["writerInstructionSemanticsOpened"]
        )
        self.assertFalse(result["sealedConclusion"]["productionShaderAuthorized"])

    def test_helper_writer_with_exact_parent_prepare_frame_passes(self):
        document, known_windows, full_hash = passing_trace()
        convert_event_to_helper(document)
        result = self.validate_document(document, known_windows, full_hash)
        self.assertTrue(result["prospectiveGatePassed"])
        self.assertEqual(result["aggregate"]["prepareLayerFrameOffsets"], [0x32C4])

    def test_unrelated_stale_stack_event_cannot_be_qualified(self):
        document, known_windows, full_hash = passing_trace()
        event = document["qualifiedWatchpointEvents"][0]
        unrelated = writer_fixture.frame(event["stopPC"], "mach_get_times")
        event["frame"] = unrelated
        event["backtrace"] = [unrelated]
        event["prepareFrame"] = unrelated
        with self.assertRaisesRegex(ValueError, "exact prepare frame"):
            self.validate_document(document, known_windows, full_hash)

    def test_wrong_unwound_role_or_source_fails_closed(self):
        for register_index, register_name, field in (
            (0, "x19", "roleBase"),
            (1, "x28", "selectedSource"),
        ):
            with self.subTest(register=register_name):
                document, known_windows, full_hash = passing_trace()
                registers = document["qualifiedWatchpointEvents"][0][
                    "prepareFrameRegisters"
                ]
                registers[register_index] = writer_fixture.raw_register(
                    register_name,
                    8,
                    document["aggregateWatchpoint"][field] + 0x800,
                )
                with self.assertRaisesRegex(
                    ValueError, "live ancestry qualification"
                ):
                    self.validate_document(document, known_windows, full_hash)

    def test_retrospective_arm_fails_closed(self):
        document, known_windows, full_hash = passing_trace()
        arm_record = document["liveArmMarkerRecords"][1]
        arm_record["sourceKnownAtHit"] = False
        with self.assertRaisesRegex(ValueError, "live marker record 1 identity"):
            self.validate_document(document, known_windows, full_hash)

    def test_marker_initial_mismatch_fails_closed(self):
        document, known_windows, full_hash = passing_trace()
        initial = bytearray.fromhex(document["aggregateWatchpoint"]["initialRoleStateHex"])
        initial[validator.full_base.AGGREGATE_OFFSET] ^= 1
        document["aggregateWatchpoint"]["initialRoleStateHex"] = initial.hex()
        document["aggregateWatchpoint"]["initialRoleStateSHA256"] = hashlib.sha256(
            initial
        ).hexdigest()
        with self.assertRaisesRegex(ValueError, "watchpoint arm provenance"):
            self.validate_document(document, known_windows, full_hash)

    def test_raw_ignored_qualified_accounting_tampering_fails_closed(self):
        document, known_windows, full_hash = passing_trace()
        document["rawWatchpointHitCount"] += 1
        with self.assertRaisesRegex(ValueError, "raw watchpoint accounting"):
            self.validate_document(document, known_windows, full_hash)

    def test_unretained_ignored_hits_require_full_diagnostic_inventory(self):
        document, known_windows, full_hash = passing_trace()
        document["unretainedIgnoredWatchpointHitCount"] = 1
        document["ignoredWatchpointHitCount"] = 2
        document["rawWatchpointHitCount"] = 3
        document["qualifiedWatchpointEvents"][0]["rawWatchpointHitIndex"] = 3
        with self.assertRaisesRegex(ValueError, "ignored watchpoint accounting"):
            self.validate_document(document, known_windows, full_hash)


if __name__ == "__main__":
    unittest.main()
