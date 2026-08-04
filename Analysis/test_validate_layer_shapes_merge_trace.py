#!/usr/bin/env python3
"""Tests for the sealed LayerShapes merge trace validator."""

import copy
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import validate_layer_shapes_merge_trace as validator


PREPARE_START = 0x18E983A7C
MODULE = {
    "valid": True,
    "path": "/System/Library/Frameworks/QuartzCore.framework/QuartzCore",
    "loadAddress": 0x18E7D0000,
}


def memory_snapshot(address, payload):
    return {
        "address": address,
        "byteCount": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "hex": payload.hex(),
    }


def register_snapshot(values):
    return [
        {
            "name": name,
            "byteCount": 8,
            "hex": values[name].to_bytes(8, "little").hex(),
            "unsignedValue": values[name],
            "valueString": hex(values[name]),
        }
        for name in validator.REGISTER_NAMES
    ]


def frame(pc):
    return {
        "frameIndex": 0,
        "pc": pc,
        "function": validator.PREPARE_LAYER_FUNCTION,
        "symbolStart": PREPARE_START,
        "symbolEnd": PREPARE_START + validator.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
        "symbolOffset": pc - PREPARE_START,
        "module": MODULE,
    }


def merge_record(index, source):
    thread_id = 100 + index
    x19 = 0x1_7000_0000 + index * 0x2000
    aggregate_address = x19 + 656
    child_address = x19 + 1568
    aggregate_before = struct.pack(
        "<4d", float(index), float(-index), 640.0 + index, 648.0 + index
    )
    aggregate_after = struct.pack(
        "<4d", float(index - 1), float(-index - 8), 641.0 + index, 649.0 + index
    )
    child_before = struct.pack(
        "<4d", 500.0 - index, -100.0 + index, 640.0, 640.0
    )
    child_after = child_before
    role_before = bytearray(validator.ROLE_STATE_BYTE_COUNT)
    role_after = bytearray(validator.ROLE_STATE_BYTE_COUNT)
    role_before[656:688] = aggregate_before
    role_before[1568:1600] = child_before
    role_after[656:688] = aggregate_after
    role_after[1568:1600] = child_after
    source_before = bytes([index & 0xFF]) * validator.SOURCE_OBJECT_BYTE_COUNT
    source_after = source_before
    call_pc = PREPARE_START + validator.MERGE_CALL_OFFSET
    return_pc = PREPARE_START + validator.MERGE_RETURN_OFFSET
    before_values = {
        "x0": aggregate_address,
        "x1": child_address,
        "x2": 1,
        "x19": x19,
        "x28": source,
        "x30": 0x1_8000_0000 + index,
        "sp": x19 - 96,
        "pc": call_pc,
    }
    after_values = dict(before_values)
    after_values.update({"x0": 1, "x30": return_pc, "pc": return_pc})
    return {
        "recordIndex": index,
        "complete": True,
        "threadID": thread_id,
        "selectedSource": source,
        "callPC": call_pc,
        "callFrame": frame(call_pc),
        "callBacktrace": [frame(call_pc)],
        "registersBefore": register_snapshot(before_values),
        "addresses": {
            "x19": x19,
            "aggregate": aggregate_address,
            "recursiveChild": child_address,
            "source": source,
        },
        "aggregateBefore": memory_snapshot(aggregate_address, aggregate_before),
        "recursiveChildBefore": memory_snapshot(child_address, child_before),
        "roleStateBefore": memory_snapshot(x19, bytes(role_before)),
        "sourceObjectBefore": memory_snapshot(source, source_before),
        "returnPC": return_pc,
        "returnFrame": frame(return_pc),
        "returnBacktrace": [frame(return_pc)],
        "registersAfter": register_snapshot(after_values),
        "aggregateAfter": memory_snapshot(aggregate_address, aggregate_after),
        "recursiveChildAfter": memory_snapshot(child_address, child_after),
        "roleStateAfter": memory_snapshot(x19, bytes(role_after)),
        "sourceObjectAfter": memory_snapshot(source, source_after),
        "aggregateChanged": True,
        "recursiveChildChanged": False,
        "roleStateChanged": True,
        "sourceObjectChanged": False,
    }


def passing_trace():
    prepare_payload = bytearray(validator.PREPARE_LAYER_CODE_WINDOW_BYTE_COUNT)
    call_index = (
        validator.MERGE_CALL_OFFSET - validator.PREPARE_LAYER_CODE_WINDOW_OFFSET
    )
    prepare_payload[call_index : call_index + 4] = bytes.fromhex(
        validator.MERGE_CALL_RAW_LITTLE_ENDIAN_HEX
    )
    prepare_sha256 = hashlib.sha256(prepare_payload).hexdigest()
    helper_payload = bytes(
        index & 0xFF for index in range(validator.MERGE_TARGET_CODE_BYTE_COUNT)
    )
    source = 0x1_A000_0000
    owner = 0x1_B000_0000
    layer = 0x1_C000_0000
    layer_state = 0x1_D000_0000
    source_rectangle = [500, -128, 644, 652]
    layer_state_rectangle = [500, 0, 524, 524]
    owner_rectangle = [500.0, 0.0, 524.0, 524.0]
    records = [
        merge_record(index, source)
        for index in range(validator.MINIMUM_COMPLETE_RECORD_COUNT)
    ]
    configuration = copy.deepcopy(validator.EXPECTED_CONFIGURATION)
    configuration["prepareLayerCodeWindowSHA256"] = prepare_sha256
    return {
        "layerShapesMergeTraceSchemaVersion": validator.EXPECTED_TRACE_SCHEMA_VERSION,
        "classification": validator.EXPECTED_CLASSIFICATION,
        "status": "finalized",
        "statusBeforeFinalization": "merge-breakpoints-armed",
        "configuration": configuration,
        "captureBackdrop": {
            "symbolAddress": 0x18F000000,
            "codeByteCount": 0x4000,
            "codeSHA256": validator.CAPTURE_BACKDROP_CODE_SHA256,
            "module": MODULE,
        },
        "prepareLayer": {
            "function": validator.PREPARE_LAYER_FUNCTION,
            "symbolStart": PREPARE_START,
            "symbolEnd": PREPARE_START + validator.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            "symbolByteCount": validator.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            "module": MODULE,
            "constructionCodeWindow": {
                **memory_snapshot(
                    PREPARE_START + validator.PREPARE_LAYER_CODE_WINDOW_OFFSET,
                    bytes(prepare_payload),
                ),
                "symbolOffset": validator.PREPARE_LAYER_CODE_WINDOW_OFFSET,
            },
            "callAddress": PREPARE_START + validator.MERGE_CALL_OFFSET,
            "returnAddress": PREPARE_START + validator.MERGE_RETURN_OFFSET,
            "callInstructionRawLittleEndianHex": (
                validator.MERGE_CALL_RAW_LITTLE_ENDIAN_HEX
            ),
            "callInstructionWord": validator.MERGE_CALL_WORD,
            "callDisplacement": validator.MERGE_CALL_DISPLACEMENT,
            "decodedHelperAddress": (
                PREPARE_START + validator.MERGE_TARGET_RELATIVE_TO_PREPARE_LAYER
            ),
        },
        "mergeHelper": {
            "address": (
                PREPARE_START + validator.MERGE_TARGET_RELATIVE_TO_PREPARE_LAYER
            ),
            "relativeToPrepareLayer": (
                validator.MERGE_TARGET_RELATIVE_TO_PREPARE_LAYER
            ),
            "module": MODULE,
            "symbol": {"valid": False},
            "codeWindow": memory_snapshot(
                PREPARE_START + validator.MERGE_TARGET_RELATIVE_TO_PREPARE_LAYER,
                helper_payload,
            ),
            "callBreakpointID": 3,
            "returnBreakpointID": 4,
        },
        "lateCandidateCount": 1,
        "lateCandidateDiagnostics": [],
        "objectChain": {
            "addresses": {
                "source": source,
                "owner": owner,
                "layer": layer,
                "layerState": layer_state,
            },
            "exact": True,
            "pointerChainExact": True,
            "selectedLateCandidateIndex": 1,
            "ownerEqualsLayerStateRectangle": True,
            "sourceEqualsLayerStateRectangle": False,
            "preconvergenceExact": True,
            "sourceSelectedRectI32": source_rectangle,
            "sourceSelectedRectI32Hex": struct.pack(
                "<4i", *source_rectangle
            ).hex(),
            "layerStateSelectedRectI32": layer_state_rectangle,
            "layerStateSelectedRectI32Hex": struct.pack(
                "<4i", *layer_state_rectangle
            ).hex(),
            "ownerSelectedRectF64": owner_rectangle,
            "ownerSelectedRectF64Hex": struct.pack(
                "<4d", *owner_rectangle
            ).hex(),
        },
        "records": records,
        "failures": [],
        "finalFailureCount": 0,
        "finalRecordCount": len(records),
        "finalCompleteRecordCount": len(records),
        "finalPendingRecordCount": 0,
        "mergeCallSiteHitCount": len(records) + 2,
        "selectedSourceCallCount": len(records),
        "rejectedSourceCallCount": 2,
        "rejectedSourceReturnCount": 2,
    }, prepare_sha256


class LayerShapesMergeTraceValidatorTests(unittest.TestCase):
    def validate_document(self, document, prepare_sha256):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "layer-shapes-merge-trace.json"
            path.write_text(
                json.dumps(document, sort_keys=True, allow_nan=False) + "\n",
                encoding="utf-8",
            )
            with (
                mock.patch.object(
                    validator,
                    "PREPARE_LAYER_CODE_WINDOW_SHA256",
                    prepare_sha256,
                ),
                mock.patch.dict(
                    validator.EXPECTED_CONFIGURATION,
                    {"prepareLayerCodeWindowSHA256": prepare_sha256},
                ),
            ):
                return validator.validate(path)

    def test_passing_trace_retains_only_sealed_integrity_conclusions(self):
        document, prepare_sha256 = passing_trace()
        result = self.validate_document(document, prepare_sha256)
        self.assertEqual(result["conclusion"], "success")
        self.assertTrue(result["prospectiveGatePassed"])
        self.assertEqual(
            result["aggregate"]["completeRecordCount"],
            validator.MINIMUM_COMPLETE_RECORD_COUNT,
        )
        self.assertGreaterEqual(
            result["aggregate"]["distinctInputPairCount"],
            validator.MINIMUM_DISTINCT_INPUT_PAIR_COUNT,
        )
        self.assertTrue(result["sealedConclusion"]["helperTargetCodeCaptured"])
        self.assertFalse(result["sealedConclusion"]["helperSemanticsOpened"])
        self.assertFalse(
            result["sealedConclusion"]["completePublicCropRuleRecovered"]
        )
        self.assertFalse(result["sealedConclusion"]["productionShaderAuthorized"])

    def test_role_state_alias_tampering_fails_closed(self):
        document, prepare_sha256 = passing_trace()
        record = document["records"][0]
        payload = bytearray.fromhex(record["roleStateBefore"]["hex"])
        payload[656] ^= 1
        record["roleStateBefore"] = memory_snapshot(
            record["addresses"]["x19"], bytes(payload)
        )
        with self.assertRaisesRegex(ValueError, "role-state aliases"):
            self.validate_document(document, prepare_sha256)

    def test_register_alias_tampering_fails_closed(self):
        document, prepare_sha256 = passing_trace()
        x2 = next(
            item for item in document["records"][0]["registersBefore"]
            if item["name"] == "x2"
        )
        x2["hex"] = (2).to_bytes(8, "little").hex()
        x2["unsignedValue"] = 2
        with self.assertRaisesRegex(ValueError, "register aliases"):
            self.validate_document(document, prepare_sha256)

    def test_prepare_layer_code_tampering_fails_closed(self):
        document, prepare_sha256 = passing_trace()
        window = document["prepareLayer"]["constructionCodeWindow"]
        payload = bytearray.fromhex(window["hex"])
        payload[0] ^= 1
        window.update(memory_snapshot(window["address"], bytes(payload)))
        with self.assertRaisesRegex(ValueError, "construction code"):
            self.validate_document(document, prepare_sha256)

    def test_insufficient_complete_records_fail_closed(self):
        document, prepare_sha256 = passing_trace()
        document["records"] = document["records"][:-1]
        count = len(document["records"])
        document["finalRecordCount"] = count
        document["finalCompleteRecordCount"] = count
        document["selectedSourceCallCount"] = count
        document["mergeCallSiteHitCount"] = count + 2
        with self.assertRaisesRegex(ValueError, "record bounds"):
            self.validate_document(document, prepare_sha256)


if __name__ == "__main__":
    unittest.main()
