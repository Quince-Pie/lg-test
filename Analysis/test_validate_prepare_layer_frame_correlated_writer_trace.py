#!/usr/bin/env python3
"""Adversarial tests for the frame-correlated writer integrity gate."""

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
import validate_prepare_layer_frame_correlated_writer_trace as validator


PREPARE_START = construction_fixture.PREPARE_START
MODULE = construction_fixture.MODULE
ROLE_BASE = 0x1_7000_1000
FRAME_POINTER = 0x1_7000_1A00
THREAD_ID = 71


def memory_snapshot(address, payload):
    return {
        "address": address,
        "byteCount": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "hex": payload.hex(),
    }


def role_state(aggregate):
    payload = bytearray(validator.full_base.ROLE_STATE_BYTE_COUNT)
    offset = validator.full_base.AGGREGATE_OFFSET
    payload[offset : offset + len(aggregate)] = aggregate
    return bytes(payload)


def prepare_registers(role_base, source_register, frame_pointer, pc):
    values = {name: 0 for name in validator.PREPARE_FRAME_REGISTER_NAMES}
    values.update(
        {
            "x19": role_base,
            "x28": source_register,
            "x29": frame_pointer,
            "x30": pc + 0x100,
            "sp": role_base - 0x100,
            "pc": pc,
        }
    )
    return [
        writer_fixture.raw_register(name, 8, values[name])
        for name in validator.PREPARE_FRAME_REGISTER_NAMES
    ]


def top_operands(pc, role_base, frame_pointer, addresses):
    values = {name: 0 for name in validator.full_base.GENERAL_REGISTER_NAMES}
    values.update(
        {
            "x0": addresses["source"],
            "x1": addresses["owner"],
            "x2": addresses["layer"],
            "x3": addresses["layerState"],
            "x19": role_base,
            "x28": 0x1_E000_0000,
            "x29": frame_pointer,
            "sp": role_base - 0x100,
            "pc": pc,
        }
    )
    general = [
        writer_fixture.raw_register(name, 4 if name == "cpsr" else 8, values[name])
        for name in validator.full_base.GENERAL_REGISTER_NAMES
    ]
    simd = [
        writer_fixture.raw_register(
            name,
            4 if name in {"fpsr", "fpcr"} else 16,
            index,
        )
        for index, name in enumerate(validator.full_base.SIMD_REGISTER_NAMES)
    ]
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
    probes = []
    for index, (start, names) in enumerate(sorted(pointer_groups.items()), start=1):
        probe = writer_fixture.raw_snapshot(
            start,
            validator.full_base.REGISTER_POINTER_SNAPSHOT_BYTE_COUNT,
            index,
        )
        probe.update(
            {
                "registerNames": names,
                "registerValue": (
                    start + validator.full_base.REGISTER_POINTER_SNAPSHOT_BACKTRACK
                ),
            }
        )
        probes.append(probe)
    return {
        "registers": {"general": general, "simd": simd},
        "stack": writer_fixture.raw_snapshot(
            values["sp"], validator.full_base.STACK_SNAPSHOT_BYTE_COUNT, 0x55
        ),
        "registerPointerProbeCount": len(probes),
        "registerPointerProbes": probes,
        "registerPointerProbeFailures": [],
    }


def prepare_frame(pc, *, frame_index=0):
    frame = construction_fixture.frame(pc)
    frame["frameIndex"] = frame_index
    return frame


def helper_frame(pc):
    helper_start = PREPARE_START + validator.full_base.UNION_HELPER_RELATIVE_TO_PREPARE_LAYER
    return {
        "frameIndex": 0,
        "pc": pc,
        "function": validator.full_base.UNION_HELPER_SYMBOL_NAME,
        "symbolStart": helper_start,
        "symbolEnd": helper_start + validator.full_base.UNION_HELPER_SYMBOL_BYTE_COUNT,
        "symbolOffset": pc - helper_start,
        "module": MODULE,
    }


def code_window(pc, preceding_raw, fill):
    payload = bytearray(
        [fill] * validator.full_base.PC_CENTERED_CODE_WINDOW_BYTE_COUNT
    )
    offset = validator.full_base.PC_CENTERED_CODE_WINDOW_BACKTRACK
    payload[offset - 4 : offset] = bytes.fromhex(preceding_raw)
    return {
        "startAddress": pc - offset,
        "byteCount": len(payload),
        "source": "pc-centered",
        "stopPCOffset": offset,
        "containsStopPC": True,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "hex": payload.hex(),
    }


def candidate_event(
    index,
    callback,
    site,
    aggregate,
    addresses,
    *,
    source_known,
    previous_index,
    previous_aggregate,
    window_index,
):
    stop_pc = PREPARE_START + site["relativeToPrepareLayer"]
    direct = site["function"] == validator.merge_base.PREPARE_LAYER_FUNCTION
    if direct:
        top = prepare_frame(stop_pc)
        parent = top
        backtrace = [top]
        prepare_index = 0
        prepare_pc = stop_pc
    else:
        top = helper_frame(stop_pc)
        prepare_pc = PREPARE_START + 0x2500
        parent = prepare_frame(prepare_pc, frame_index=1)
        backtrace = [top, parent]
        prepare_index = 1
    role = role_state(aggregate)
    return {
        "eventIndex": index,
        "callbackSequence": callback,
        "siteName": site["name"],
        "siteRelativeToPrepareLayer": site["relativeToPrepareLayer"],
        "epochStart": site["epochStart"],
        "sourceKnownAtHit": source_known,
        "threadID": THREAD_ID,
        "stopPC": stop_pc,
        "frame": top,
        "backtrace": backtrace,
        "prepareFrameIndex": prepare_index,
        "prepareFrame": parent,
        "prepareFrameRegisters": prepare_registers(
            ROLE_BASE, 0x1_E000_0000, FRAME_POINTER, prepare_pc
        ),
        "frameIdentity": {
            "threadID": THREAD_ID,
            "roleBase": ROLE_BASE,
            "framePointer": FRAME_POINTER,
        },
        "previousSameFrameCandidateEventIndex": previous_index,
        "aggregateChangedFromPreviousSameFrameCandidate": (
            None if previous_aggregate is None else aggregate != previous_aggregate
        ),
        "roleStateAfter": memory_snapshot(ROLE_BASE, role),
        "aggregateAfterHex": aggregate.hex(),
        "codeWindowIndex": window_index,
        "topOperandSnapshot": top_operands(
            stop_pc, ROLE_BASE, FRAME_POINTER, addresses
        ),
    }


def passing_trace():
    base, _prepare_hash, _helper_hash, _symbol_hash = (
        construction_fixture.passing_trace()
    )
    chain = copy.deepcopy(base["objectChain"])
    chain["callbackSequence"] = 5
    addresses = chain["addresses"]
    selected_source = addresses["source"]

    full_code = bytearray(validator.full_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT)
    for site in validator.WRITER_SITES:
        relative = site["relativeToPrepareLayer"]
        raw = site.get("precedingInstructionRawLittleEndianHex")
        if relative >= 4 and raw is not None:
            full_code[relative - 4 : relative] = bytes.fromhex(raw)
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

    site_records = []
    breakpoint_id = 3
    raw_by_name = {}
    for index, site in enumerate(validator.WRITER_SITES, start=1):
        address = PREPARE_START + site["relativeToPrepareLayer"]
        if site["function"] == validator.merge_base.PREPARE_LAYER_FUNCTION:
            symbol_start = PREPARE_START
            symbol_end = PREPARE_START + validator.full_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT
        elif site["function"] == validator.full_base.UNION_HELPER_SYMBOL_NAME:
            symbol_start = PREPARE_START + validator.full_base.UNION_HELPER_RELATIVE_TO_PREPARE_LAYER
            symbol_end = symbol_start + validator.full_base.UNION_HELPER_SYMBOL_BYTE_COUNT
        else:
            symbol_start = address - 0x100
            symbol_end = address + 0x100
        raw = site.get("precedingInstructionRawLittleEndianHex")
        if raw is None:
            raw = bytes([index, index + 1, index + 2, index + 3]).hex()
        raw_by_name[site["name"]] = raw
        site_records.append(
            {
                **site,
                "address": address,
                "breakpointID": breakpoint_id,
                "module": MODULE,
                "symbol": {
                    "valid": True,
                    "name": site["function"],
                    "startAddress": symbol_start,
                    "endAddress": symbol_end,
                },
                "precedingInstructionRawLittleEndianHex": raw,
            }
        )
        breakpoint_id += 1

    stale = struct.pack("<4d", 501.0, -126.0, 644.0, 652.0)
    zero = bytes(validator.full_base.AGGREGATE_BYTE_COUNT)
    final = struct.pack("<4d", 490.0, -115.0, 642.0, 650.0)
    helper_site = validator.WRITER_SITE_BY_NAME["unionBoundsStoreAfter"]
    zero_site = validator.WRITER_SITE_BY_NAME["zeroInitializationAfter"]
    windows = [
        code_window(
            PREPARE_START + helper_site["relativeToPrepareLayer"],
            raw_by_name[helper_site["name"]],
            0x5A,
        ),
        code_window(
            PREPARE_START + zero_site["relativeToPrepareLayer"],
            raw_by_name[zero_site["name"]],
            0xA5,
        ),
    ]
    events = [
        candidate_event(
            0,
            2,
            helper_site,
            stale,
            addresses,
            source_known=False,
            previous_index=None,
            previous_aggregate=None,
            window_index=0,
        ),
        candidate_event(
            1,
            3,
            zero_site,
            zero,
            addresses,
            source_known=False,
            previous_index=None,
            previous_aggregate=None,
            window_index=1,
        ),
        candidate_event(
            2,
            6,
            helper_site,
            final,
            addresses,
            source_known=True,
            previous_index=1,
            previous_aggregate=zero,
            window_index=0,
        ),
    ]
    marker_pc = PREPARE_START + validator.LIVE_SELECTION_MARKER_OFFSET
    marker_role = role_state(final)
    helper_address = PREPARE_START + validator.full_base.UNION_HELPER_RELATIVE_TO_PREPARE_LAYER
    hit_counts = {name: 0 for name in validator.WRITER_SITE_BY_NAME}
    hit_counts[helper_site["name"]] = 2
    hit_counts[zero_site["name"]] = 1
    zero_counts = {name: 0 for name in validator.WRITER_SITE_BY_NAME}
    trace = {
        "prepareLayerFrameWriterTraceSchemaVersion": validator.EXPECTED_TRACE_SCHEMA_VERSION,
        "classification": validator.EXPECTED_CLASSIFICATION,
        "status": "finalized",
        "statusBeforeFinalization": "live-selected-frame-correlated",
        "configuration": configuration,
        "callbackOrder": [
            {"sequence": 1, "kind": "prepare-layer-entry"},
            {"sequence": 2, "kind": "writer-site:unionBoundsStoreAfter"},
            {"sequence": 3, "kind": "writer-site:zeroInitializationAfter"},
            {"sequence": 4, "kind": "capture-backdrop-entry"},
            {"sequence": 5, "kind": "source-selected"},
            {"sequence": 6, "kind": "writer-site:unionBoundsStoreAfter"},
            {"sequence": 7, "kind": "live-selected-frame-correlated"},
        ],
        "captureBackdropEntryBreakpointID": 1,
        "prepareLayerEntryBreakpointID": 2,
        "captureBackdrop": {
            "callbackSequence": 4,
            "symbolAddress": 0x1944_0000_0,
            "codeByteCount": validator.full_base.CAPTURE_BACKDROP_CODE_BYTE_COUNT,
            "codeSHA256": validator.merge_base.CAPTURE_BACKDROP_CODE_SHA256,
            "module": MODULE,
            "lateBreakpointID": 13,
        },
        "prepareLayer": {
            "callbackSequence": 1,
            "callbackPC": PREPARE_START,
            "callbackLocationAddress": PREPARE_START,
            "entryBreakpointID": 2,
            "entryBreakpointLocationAddresses": [PREPARE_START],
            "function": validator.merge_base.PREPARE_LAYER_FUNCTION,
            "symbolStart": PREPARE_START,
            "symbolEnd": PREPARE_START + validator.full_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            "symbolByteCount": validator.full_base.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            "module": MODULE,
            "fullCode": memory_snapshot(PREPARE_START, bytes(full_code)),
            "knownWindows": [
                {"offset": offset, "byteCount": count, "sha256": digest}
                for offset, count, digest in known_windows
            ],
            "unionHelper": {
                "address": helper_address,
                "relativeToPrepareLayer": validator.full_base.UNION_HELPER_RELATIVE_TO_PREPARE_LAYER,
                "module": MODULE,
                "symbol": {
                    "valid": True,
                    "name": validator.full_base.UNION_HELPER_SYMBOL_NAME,
                    "startAddress": helper_address,
                    "endAddress": helper_address + validator.full_base.UNION_HELPER_SYMBOL_BYTE_COUNT,
                },
                "symbolCodeSHA256": validator.full_base.UNION_HELPER_SYMBOL_SHA256,
            },
            "writerSites": site_records,
            "liveSelectionMarker": {
                "name": validator.LIVE_SELECTION_MARKER_NAME,
                "offset": validator.LIVE_SELECTION_MARKER_OFFSET,
                "address": marker_pc,
                "breakpointID": 12,
                "instructionRawLittleEndianHex": bytes(
                    full_code[
                        validator.LIVE_SELECTION_MARKER_OFFSET : validator.LIVE_SELECTION_MARKER_OFFSET + 4
                    ]
                ).hex(),
            },
        },
        "lateCandidateCount": 1,
        "lateCandidateDiagnostics": [],
        "objectChain": chain,
        "writerCandidateEvents": events,
        "rejectedWriterDiagnostics": [],
        "preselectionMarkerDiagnostics": [
            {
                "markerHitIndex": 1,
                "threadID": THREAD_ID,
                "roleBase": ROLE_BASE + 0x2000,
                "sourceRegister": selected_source,
                "framePointer": FRAME_POINTER + 0x2000,
            }
        ],
        "selectedFrame": {
            "callbackSequence": 7,
            "markerHitIndex": 2,
            "threadID": THREAD_ID,
            "pc": marker_pc,
            "frame": prepare_frame(marker_pc),
            "backtrace": [prepare_frame(marker_pc)],
            "registers": prepare_registers(
                ROLE_BASE, selected_source, FRAME_POINTER, marker_pc
            ),
            "frameIdentity": {
                "threadID": THREAD_ID,
                "roleBase": ROLE_BASE,
                "framePointer": FRAME_POINTER,
            },
            "selectedSource": selected_source,
            "epochStartEventIndex": 1,
            "selectedWriterEventCount": 2,
            "roleStateAtMarker": memory_snapshot(ROLE_BASE, marker_role),
            "aggregateAtMarkerHex": final.hex(),
            "privateFieldsAtMarker": writer_fixture.private_fields(),
            "selectedObjectsAtMarker": {
                base: writer_fixture.raw_snapshot(addresses[base], byte_count, index)
                for index, (base, byte_count) in enumerate(
                    validator.full_base.OBJECT_SNAPSHOT_SPECS, start=1
                )
            },
        },
        "selectedWriterEventIndices": [1, 2],
        "codeWindows": windows,
        "failures": [],
        "finalFailureCount": 0,
        "finalCallbackSequence": 7,
        "writerSiteHitCounts": hit_counts,
        "rejectedWriterSiteHitCounts": copy.deepcopy(zero_counts),
        "discardedWriterSiteHitCounts": copy.deepcopy(zero_counts),
        "unretainedRejectedWriterHitCount": 0,
        "finalWriterCandidateEventCount": 3,
        "selectionMarkerHitCount": 2,
        "rejectedSelectionMarkerHitCount": 0,
        "discardedSelectionMarkerHitCount": 0,
        "finalSelectedWriterEventCount": 2,
        "finalSelectedDistinctAggregateCount": 2,
        "finalSelectedChangingTransitionCount": 1,
    }
    return trace, full_hash, known_windows, configuration


class PrepareLayerFrameCorrelatedWriterValidatorTests(unittest.TestCase):
    def validate_document(self, document, full_hash, known_windows, configuration):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prepare-layer-frame-writer-trace.json"
            path.write_text(
                json.dumps(document, sort_keys=True, allow_nan=False) + "\n",
                encoding="utf-8",
            )
            with (
                mock.patch.object(
                    validator, "PREPARE_LAYER_FULL_CODE_SHA256", full_hash
                ),
                mock.patch.object(
                    validator.full_base,
                    "KNOWN_PREPARE_LAYER_WINDOWS",
                    known_windows,
                ),
                mock.patch.object(
                    validator, "EXPECTED_CONFIGURATION", configuration
                ),
            ):
                return validator.validate(path)

    def test_passing_trace_opens_only_same_frame_suffix_integrity(self):
        document, full_hash, windows, configuration = passing_trace()
        result = self.validate_document(document, full_hash, windows, configuration)
        self.assertEqual(result["conclusion"], "success")
        self.assertEqual(result["aggregate"]["writerCandidateEventCount"], 3)
        self.assertEqual(result["aggregate"]["selectedWriterEventCount"], 2)
        sealed = result["sealedConclusion"]
        self.assertTrue(sealed["sameInvocationFrameCorrelationProved"])
        self.assertTrue(sealed["selectedAggregateChainClosedAtMarker"])
        self.assertFalse(sealed["writerInstructionSemanticsOpened"])
        self.assertFalse(sealed["productionShaderAuthorized"])

    def test_stale_same_address_epoch_cannot_enter_selected_suffix(self):
        document, full_hash, windows, configuration = passing_trace()
        document["selectedWriterEventIndices"] = [0, 1, 2]
        document["selectedFrame"]["selectedWriterEventCount"] = 3
        document["finalSelectedWriterEventCount"] = 3
        document["finalSelectedDistinctAggregateCount"] = 3
        with self.assertRaisesRegex(ValueError, "selected writer suffix"):
            self.validate_document(document, full_hash, windows, configuration)

    def test_wrong_selected_frame_pointer_fails_closed(self):
        document, full_hash, windows, configuration = passing_trace()
        identity = document["selectedFrame"]["frameIdentity"]
        identity["framePointer"] += 8
        with self.assertRaisesRegex(ValueError, "selected frame correlation"):
            self.validate_document(document, full_hash, windows, configuration)

    def test_omitted_same_frame_writer_event_fails_closed(self):
        document, full_hash, windows, configuration = passing_trace()
        document["selectedWriterEventIndices"] = [1]
        document["selectedFrame"]["selectedWriterEventCount"] = 1
        document["finalSelectedWriterEventCount"] = 1
        document["finalSelectedDistinctAggregateCount"] = 1
        document["finalSelectedChangingTransitionCount"] = 0
        with self.assertRaisesRegex(ValueError, "selected writer suffix"):
            self.validate_document(document, full_hash, windows, configuration)

    def test_last_writer_must_bit_match_marker_aggregate(self):
        document, full_hash, windows, configuration = passing_trace()
        aggregate = struct.pack("<4d", 491.0, -115.0, 642.0, 650.0)
        document["selectedFrame"]["aggregateAtMarkerHex"] = aggregate.hex()
        document["selectedFrame"]["roleStateAtMarker"] = memory_snapshot(
            ROLE_BASE, role_state(aggregate)
        )
        with self.assertRaisesRegex(ValueError, "selected writer suffix"):
            self.validate_document(document, full_hash, windows, configuration)

    def test_nonchanging_selected_chain_fails_closed(self):
        document, full_hash, windows, configuration = passing_trace()
        zero = bytes(validator.full_base.AGGREGATE_BYTE_COUNT)
        event = document["writerCandidateEvents"][2]
        event["aggregateAfterHex"] = zero.hex()
        event["aggregateChangedFromPreviousSameFrameCandidate"] = False
        event["roleStateAfter"] = memory_snapshot(ROLE_BASE, role_state(zero))
        selected = document["selectedFrame"]
        selected["aggregateAtMarkerHex"] = zero.hex()
        selected["roleStateAtMarker"] = memory_snapshot(ROLE_BASE, role_state(zero))
        document["finalSelectedDistinctAggregateCount"] = 1
        document["finalSelectedChangingTransitionCount"] = 0
        with self.assertRaisesRegex(ValueError, "selected writer suffix"):
            self.validate_document(document, full_hash, windows, configuration)

    def test_writer_code_tampering_fails_closed(self):
        document, full_hash, windows, configuration = passing_trace()
        payload = bytearray.fromhex(document["codeWindows"][1]["hex"])
        offset = validator.full_base.PC_CENTERED_CODE_WINDOW_BACKTRACK
        payload[offset - 4] ^= 0xFF
        document["codeWindows"][1]["hex"] = payload.hex()
        document["codeWindows"][1]["sha256"] = hashlib.sha256(payload).hexdigest()
        with self.assertRaisesRegex(ValueError, "code containment"):
            self.validate_document(document, full_hash, windows, configuration)

    def test_unaccounted_rejected_writer_hit_fails_closed(self):
        document, full_hash, windows, configuration = passing_trace()
        name = "glassDODAfter0"
        document["writerSiteHitCounts"][name] = 1
        document["rejectedWriterSiteHitCounts"][name] = 1
        with self.assertRaisesRegex(ValueError, "diagnostic accounting"):
            self.validate_document(document, full_hash, windows, configuration)

    def test_trace_failure_never_passes(self):
        document, full_hash, windows, configuration = passing_trace()
        document["failures"] = [{"stage": "writer-site", "message": "failure"}]
        document["finalFailureCount"] = 1
        with self.assertRaisesRegex(ValueError, "trace envelope"):
            self.validate_document(document, full_hash, windows, configuration)


if __name__ == "__main__":
    unittest.main()
