#!/usr/bin/env python3
"""Tests for the multi-state public/private crop-transfer validator."""

import hashlib
import json
import math
import struct
import tempfile
import unittest
from pathlib import Path

import validate_prepare_layer_crop_transfer as validator


def snapshot(address, payload):
    return {
        "address": address,
        "byteCount": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "hex": payload.hex(),
    }


def registers(names, values):
    records = []
    for name in names:
        byte_count = 4 if name == "cpsr" else 8
        value = values.get(name, 0)
        records.append(
            {
                "name": name,
                "byteCount": byte_count,
                "hex": value.to_bytes(byte_count, "little").hex(),
                "unsignedValue": value,
                "valueString": hex(value),
            }
        )
    return records


def role_payload(ordinal):
    payload = bytearray(validator.ROLE_STATE_BYTE_COUNT)
    struct.pack_into("<4i", payload, validator.ROLE_VISIBLE_CROP_OFFSET, 1, 2, 3, 4)
    struct.pack_into(
        "<4i",
        payload,
        validator.ROLE_WORKING_CROP_OFFSET,
        ordinal,
        -ordinal,
        640,
        648,
    )
    struct.pack_into(
        "<4d",
        payload,
        validator.ROLE_AGGREGATE_OFFSET,
        500.0 - ordinal,
        -100.0 + ordinal,
        641.0,
        649.0,
    )
    struct.pack_into(
        "<4d", payload, validator.ROLE_VIEWPORT_OFFSET, 0.0, 0.0, 1024.0, 1024.0
    )
    return bytes(payload)


def frame_record(index, pc):
    return {
        "frameIndex": index,
        "pc": pc,
        "function": validator.PREPARE_LAYER_FUNCTION,
        "symbolStart": pc - validator.MARKER_OFFSET,
        "symbolEnd": pc - validator.MARKER_OFFSET
        + validator.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
        "symbolOffset": validator.MARKER_OFFSET,
        "module": {"valid": True},
    }


def valid_inputs():
    start = 0x1_9700_0000
    marker = start + validator.MARKER_OFFSET
    callbacks = [{"sequence": 1, "kind": "prepare-layer-entry"}]
    trace_records = []
    uniform_records = []
    for ordinal in range(1, 33):
        role_address = 0x1_6000_0000 + ordinal * 0x10_000
        source_address = 0x9_0000_0000 + ordinal * 0x10_000
        stack_address = role_address + 0x8000
        values = {
            "x19": role_address,
            "x28": source_address,
            "x29": stack_address + 0x1000,
            "sp": stack_address,
            "pc": marker,
            "cpsr": 0x1000,
        }
        role = role_payload(ordinal)
        prepare_frames = []
        prepare_depth = 3 if ordinal == 1 else 4
        for index in range(prepare_depth):
            frame_role_address = role_address + index * 0x3000
            frame_values = {
                "x19": frame_role_address,
                "x28": source_address if index == 0 else source_address + index,
                "x29": values["x29"] + index * 0x1000,
                "sp": stack_address + index * 0x1000,
                "pc": marker if index == 0 else start + 0x2A68,
            }
            frame_role = role if index == 0 else bytes(validator.ROLE_STATE_BYTE_COUNT)
            prepare_frames.append(
                {
                    "frameIndex": index,
                    "unwindFramePointer": frame_values["x29"],
                    "frame": frame_record(index, frame_values["pc"]),
                    "registers": registers(
                        validator.PREPARE_FRAME_REGISTER_NAMES, frame_values
                    ),
                    "roleState": snapshot(frame_role_address, frame_role),
                }
            )
        callbacks.append(
            {"sequence": ordinal + 1, "kind": "qualified-crop-transfer-marker"}
        )
        trace_records.append(
            {
                "recordIndex": ordinal - 1,
                "normalRenderOrdinal": ordinal,
                "callbackSequence": ordinal + 1,
                "markerHitIndex": ordinal * 4,
                "threadID": 42,
                "pc": marker,
                "prepareRecursionDepth": prepare_depth,
                "frame": frame_record(0, marker),
                "backtrace": [
                    frame_record(0, marker),
                    {
                        "frameIndex": 4,
                        "pc": 1,
                        "function": "main.carendererUniformEvidence(",
                    },
                    {
                        "frameIndex": 5,
                        "pc": 2,
                        "function": "main.localTransitionCARendererEvidence(",
                    },
                    {
                        "frameIndex": 6,
                        "pc": 3,
                        "function": "main.transitionBackgroundUniformEvidence(",
                    },
                ],
                "registers": registers(validator.GENERAL_REGISTER_NAMES, values),
                "frameIdentity": {
                    "threadID": 42,
                    "roleBase": role_address,
                    "source": source_address,
                    "framePointer": values["x29"],
                },
                "roleState": snapshot(role_address, role),
                "sourceState": snapshot(
                    source_address, bytes(validator.SOURCE_STATE_BYTE_COUNT)
                ),
                "stackState": snapshot(
                    stack_address, bytes(validator.STACK_STATE_BYTE_COUNT)
                ),
                "pointerStates": [],
                "prepareFrames": prepare_frames,
            }
        )
        uniform_records.append(
            {
                "sampleIndex": ordinal,
                "remaining": ordinal / 32,
                "capturedLayerStates": [
                    {
                        "path": [1],
                        "position": [512.0 - ordinal, 512.0 - ordinal],
                        "bounds": [0.0, 0.0, ordinal * 20.0, ordinal * 20.0],
                    }
                ],
                "render": {
                    "executed": True,
                    "capture": "transition-background-uniform-%02d" % ordinal,
                },
            }
        )
    trace = {
        "prepareLayerCropTransferTraceSchemaVersion": 1,
        "status": "finalized",
        "statusBeforeFinalization": "crop-transfer-marker-active",
        "configuration": validator.EXPECTED_CONFIGURATION,
        "prepareLayer": {
            "function": validator.PREPARE_LAYER_FUNCTION,
            "symbolStart": start,
            "symbolEnd": start + validator.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            "symbolByteCount": validator.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            "fullCodeSHA256": validator.PREPARE_LAYER_FULL_CODE_SHA256,
            "marker": {
                "name": validator.MARKER_NAME,
                "offset": validator.MARKER_OFFSET,
                "address": marker,
                "instructionRawLittleEndianHex": (
                    validator.MARKER_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
                ),
            },
        },
        "callbackOrder": callbacks,
        "qualifiedRecords": trace_records,
        "failures": [],
        "finalFailureCount": 0,
        "finalDiscardedQualifiedRecordCount": 0,
        "finalUnretainedRejectionCount": 0,
        "finalCallbackSequence": len(callbacks),
        "finalQualifiedRecordCount": 32,
        "finalMarkerHitCount": 128,
        "finalRejectedMarkerCount": 96,
        "rejectionGroups": [
            {
                "reason": "prepare-recursion-depth-differs",
                "prepareRecursionDepth": 1,
                "hitCount": 96,
            }
        ],
        "terminalProcess": {"exited": True, "exitStatus": 0},
    }
    timeline = {
        "schemaVersion": 5,
        "material": "clear",
        "appearance": "light",
        "direction": "materialize",
        "animationCurve": "linear",
        "sampleCount": 33,
        "failedSamples": 0,
        "windowBackingScaleFactor": 1,
        "geometry": {
            "name": "circle-640-center",
            "windowWidth": 1024,
            "windowHeight": 1024,
        },
        "samples": [{} for _ in range(33)],
        "dynamicBackgroundUniforms": {
            "schemaVersion": 9,
            "executed": True,
            "evidenceMode": "allocation-metadata-v1",
            "sampleCount": 32,
            "executedSampleCount": 32,
            "fixedStateInterventions": {"requested": False},
            "pathIsolationInterventions": {"requested": False},
            "records": uniform_records,
        },
    }
    return trace, timeline


class PrepareLayerCropTransferValidatorTests(unittest.TestCase):
    def test_role_decoder_is_bit_exact(self):
        payload = role_payload(7)
        decoded = validator.decode_role(payload)
        self.assertEqual(decoded["workingCropI32"], [7, -7, 640, 648])
        self.assertEqual(decoded["viewportF64"], [0.0, 0.0, 1024.0, 1024.0])
        self.assertEqual(
            decoded["aggregateF64Hex"],
            payload[
                validator.ROLE_AGGREGATE_OFFSET :
                validator.ROLE_AGGREGATE_OFFSET + 32
            ].hex(),
        )

    def test_role_decoder_rejects_nonfinite_aggregate(self):
        payload = bytearray(role_payload(1))
        struct.pack_into(
            "<d", payload, validator.ROLE_AGGREGATE_OFFSET, math.nan
        )
        with self.assertRaisesRegex(ValueError, "non-finite"):
            validator.decode_role(bytes(payload))

    def test_complete_synthetic_join_passes(self):
        trace, timeline = valid_inputs()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trace_path = root / "trace.json"
            timeline_path = root / "timeline.json"
            trace_path.write_text(json.dumps(trace), encoding="utf-8")
            timeline_path.write_text(json.dumps(timeline), encoding="utf-8")
            result = validator.validate(
                trace_path, timeline_path, "circle-640-center"
            )
        self.assertEqual(result["conclusion"], "success")
        self.assertEqual(result["recordCount"], 32)
        self.assertTrue(result["prospectiveCaptureIntegrityGatePassed"])
        self.assertFalse(
            result["sealedConclusion"]["generalCropPolicyRecovered"]
        )
        self.assertFalse(
            result["sealedConclusion"]["productionShaderAuthorized"]
        )

    def test_normal_recursion_topology_mismatch_fails_closed(self):
        trace, _timeline = valid_inputs()
        record = trace["qualifiedRecords"][0]
        record["prepareRecursionDepth"] = 4
        with self.assertRaisesRegex(ValueError, "recursion topology differs"):
            validator.validate_trace(trace)

    def test_missing_structural_record_fails_closed(self):
        trace, timeline = valid_inputs()
        trace["qualifiedRecords"].pop()
        trace["finalQualifiedRecordCount"] = 31
        with self.assertRaisesRegex(ValueError, "record count differs"):
            validator.validate_trace(trace)

    def test_crop_bytes_cannot_change_selection_acceptance(self):
        trace, _timeline = valid_inputs()
        original = trace["qualifiedRecords"][0]["roleState"]
        payload = bytearray(bytes.fromhex(original["hex"]))
        struct.pack_into(
            "<4i", payload, validator.ROLE_WORKING_CROP_OFFSET, -9, 8, 7, 6
        )
        trace["qualifiedRecords"][0]["roleState"] = snapshot(
            original["address"], bytes(payload)
        )
        trace["qualifiedRecords"][0]["prepareFrames"][0]["roleState"] = snapshot(
            original["address"], bytes(payload)
        )
        start, records = validator.validate_trace(trace)
        decoded = validator.validate_record(records[0], 1, start)
        self.assertEqual(decoded["workingCropI32"], [-9, 8, 7, 6])

    def test_intervention_caller_fails_closed(self):
        trace, _timeline = valid_inputs()
        trace["qualifiedRecords"][0]["backtrace"].append(
            {
                "frameIndex": 7,
                "pc": 4,
                "function": "main.transitionPathIsolationAllocationEvidence(",
            }
        )
        start, records = validator.validate_trace(trace)
        with self.assertRaisesRegex(ValueError, "caller chain differs"):
            validator.validate_record(records[0], 1, start)


if __name__ == "__main__":
    unittest.main()
