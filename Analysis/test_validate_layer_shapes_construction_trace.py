#!/usr/bin/env python3
"""Tests for the sealed two-branch LayerShapes construction validator."""

import copy
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import validate_layer_shapes_construction_trace as validator


PREPARE_START = 0x19428653C
MODULE = {
    "valid": True,
    "path": "/System/Library/Frameworks/QuartzCore.framework/QuartzCore",
    "loadAddress": 0x1940D0000,
}


def memory_snapshot(address, payload):
    return {
        "address": address,
        "byteCount": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "hex": payload.hex(),
    }


def register_snapshot(values, names=validator.GENERAL_REGISTER_NAMES):
    records = []
    for name in names:
        byte_count = 16 if name.startswith("v") else 8
        value = values[name]
        payload = value if isinstance(value, bytes) else value.to_bytes(8, "little")
        record = {
            "name": name,
            "byteCount": byte_count,
            "hex": payload.hex(),
            "valueString": "0x" + payload[::-1].hex(),
        }
        if byte_count <= 8:
            record["unsignedValue"] = int.from_bytes(payload, "little")
        records.append(record)
    return records


def frame(pc):
    return {
        "frameIndex": 0,
        "pc": pc,
        "function": validator.base.PREPARE_LAYER_FUNCTION,
        "symbolStart": PREPARE_START,
        "symbolEnd": PREPARE_START + validator.base.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
        "symbolOffset": pc - PREPARE_START,
        "module": MODULE,
    }


def role_state(aggregate, source, source_offset):
    payload = bytearray(validator.ROLE_STATE_BYTE_COUNT)
    payload[656:688] = aggregate
    payload[source_offset : source_offset + 32] = source
    return bytes(payload)


def direct_record(source):
    x19 = 0x1_7000_0000
    aggregate_address = x19 + 656
    child_address = x19 + 1568
    aggregate_before = struct.pack("<4d", 500.0, 0.0, 524.0, 524.0)
    child = struct.pack("<4d", 491.5, -107.5, 640.0, 640.0)
    aggregate_after = struct.pack("<4d", 490.0, -115.5, 641.5, 649.5)
    before_role = role_state(aggregate_before, child, 1568)
    after_role = role_state(aggregate_after, child, 1568)
    call_pc = PREPARE_START + validator.DIRECT_CALL_OFFSET
    return_pc = PREPARE_START + validator.DIRECT_RETURN_OFFSET
    before_values = {
        "x0": aggregate_address,
        "x1": child_address,
        "x2": 1,
        "x19": x19,
        "x28": source,
        "x30": 0x1_8000_0000,
        "sp": x19 - 96,
        "pc": call_pc,
    }
    after_values = dict(before_values)
    after_values.update({"x0": 1, "x30": return_pc, "pc": return_pc})
    return {
        "recordIndex": 0,
        "complete": True,
        "selectedSource": True,
        "sourceKnownAtCall": False,
        "threadID": 71,
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
        "recursiveChildBefore": memory_snapshot(child_address, child),
        "roleStateBefore": memory_snapshot(x19, before_role),
        "returnPC": return_pc,
        "returnFrame": frame(return_pc),
        "returnBacktrace": [frame(return_pc)],
        "registersAfter": register_snapshot(after_values),
        "aggregateAfter": memory_snapshot(aggregate_address, aggregate_after),
        "recursiveChildAfter": memory_snapshot(child_address, child),
        "roleStateAfter": memory_snapshot(x19, after_role),
        "aggregateChanged": True,
        "recursiveChildChanged": False,
        "roleStateChanged": True,
    }


def alternate_record(index, source):
    x19 = 0x1_7100_0000 + index * 0x2000
    aggregate_address = x19 + 656
    alternate_address = x19 + 1312
    aggregate_before = struct.pack("<4d", 500.0 - index, 0.0, 524.0, 524.0)
    alternate = struct.pack(
        "<4d", 490.0 - index, -115.5 + index, 641.5 + index, 649.5 + index
    )
    role_before = role_state(aggregate_before, alternate, 1312)
    role_after = role_state(alternate, alternate, 1312)
    store_pc = PREPARE_START + validator.ALTERNATE_STORE_OFFSET
    after_pc = PREPARE_START + validator.ALTERNATE_AFTER_OFFSET
    before_values = {
        "x0": 0,
        "x1": 0,
        "x2": 0,
        "x19": x19,
        "x28": source,
        "x30": 0x1_8200_0000 + index,
        "sp": x19 - 96,
        "pc": store_pc,
    }
    after_values = dict(before_values)
    after_values["pc"] = after_pc
    return {
        "recordIndex": index,
        "complete": True,
        "selectedSource": True,
        "sourceKnownAtStore": True,
        "threadID": 100 + index,
        "storePC": store_pc,
        "storeFrame": frame(store_pc),
        "storeBacktrace": [frame(store_pc)],
        "registersBefore": register_snapshot(before_values),
        "simdSourceRegisters": register_snapshot(
            {"v0": alternate[:16], "v1": alternate[16:]},
            validator.ALTERNATE_SIMD_REGISTER_NAMES,
        ),
        "addresses": {
            "x19": x19,
            "aggregate": aggregate_address,
            "alternateSource": alternate_address,
            "source": source,
        },
        "aggregateBefore": memory_snapshot(aggregate_address, aggregate_before),
        "alternateSourceBefore": memory_snapshot(alternate_address, alternate),
        "roleStateBefore": memory_snapshot(x19, role_before),
        "afterPC": after_pc,
        "afterFrame": frame(after_pc),
        "afterBacktrace": [frame(after_pc)],
        "registersAfter": register_snapshot(after_values),
        "aggregateAfter": memory_snapshot(aggregate_address, alternate),
        "alternateSourceAfter": memory_snapshot(alternate_address, alternate),
        "roleStateAfter": memory_snapshot(x19, role_after),
        "aggregateChanged": aggregate_before != alternate,
        "alternateSourceChanged": False,
        "roleStateChanged": role_before != role_after,
    }


def passing_trace():
    prepare_payload = bytearray(validator.base.PREPARE_LAYER_CODE_WINDOW_BYTE_COUNT)
    direct_index = (
        validator.DIRECT_CALL_OFFSET - validator.base.PREPARE_LAYER_CODE_WINDOW_OFFSET
    )
    alternate_index = (
        validator.ALTERNATE_STORE_OFFSET
        - validator.base.PREPARE_LAYER_CODE_WINDOW_OFFSET
    )
    prepare_payload[direct_index : direct_index + 4] = bytes.fromhex(
        validator.DIRECT_CALL_RAW_LITTLE_ENDIAN_HEX
    )
    prepare_payload[alternate_index : alternate_index + 4] = bytes.fromhex(
        validator.ALTERNATE_STORE_RAW_LITTLE_ENDIAN_HEX
    )
    helper_payload = bytes(
        index & 0xFF for index in range(validator.UNION_HELPER_CODE_WINDOW_BYTE_COUNT)
    )
    prepare_sha256 = hashlib.sha256(prepare_payload).hexdigest()
    helper_sha256 = hashlib.sha256(helper_payload).hexdigest()
    symbol_sha256 = hashlib.sha256(
        helper_payload[: validator.UNION_HELPER_SYMBOL_BYTE_COUNT]
    ).hexdigest()
    source = 0x1_A000_0000
    owner = 0x1_B000_0000
    layer = 0x1_C000_0000
    layer_state = 0x1_D000_0000
    source_rectangle = [500, -128, 644, 652]
    layer_state_rectangle = [500, 0, 524, 524]
    owner_rectangle = [500.0, 0.0, 524.0, 524.0]
    alternate_records = [
        alternate_record(index, source)
        for index in range(validator.MINIMUM_SELECTED_ALTERNATE_RECORD_COUNT)
    ]
    configuration = copy.deepcopy(validator.EXPECTED_CONFIGURATION)
    configuration.update(
        {
            "prepareLayerCodeWindowSHA256": prepare_sha256,
            "unionHelperCodeWindowSHA256": helper_sha256,
            "unionHelperSymbolSHA256": symbol_sha256,
        }
    )
    helper_address = PREPARE_START + validator.UNION_HELPER_RELATIVE_TO_PREPARE_LAYER
    trace = {
        "layerShapesConstructionTraceSchemaVersion": (
            validator.EXPECTED_TRACE_SCHEMA_VERSION
        ),
        "classification": validator.EXPECTED_CLASSIFICATION,
        "status": "finalized",
        "statusBeforeFinalization": "source-selected-construction-active",
        "configuration": configuration,
        "captureBackdrop": {
            "symbolAddress": 0x194400000,
            "codeByteCount": 0x4000,
            "codeSHA256": validator.base.CAPTURE_BACKDROP_CODE_SHA256,
            "module": MODULE,
        },
        "prepareLayer": {
            "function": validator.base.PREPARE_LAYER_FUNCTION,
            "symbolStart": PREPARE_START,
            "symbolEnd": PREPARE_START
            + validator.base.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            "symbolByteCount": validator.base.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            "module": MODULE,
            "constructionCodeWindow": {
                **memory_snapshot(
                    PREPARE_START + validator.base.PREPARE_LAYER_CODE_WINDOW_OFFSET,
                    bytes(prepare_payload),
                ),
                "symbolOffset": validator.base.PREPARE_LAYER_CODE_WINDOW_OFFSET,
            },
            "directCallAddress": PREPARE_START + validator.DIRECT_CALL_OFFSET,
            "directReturnAddress": PREPARE_START + validator.DIRECT_RETURN_OFFSET,
            "directCallRawLittleEndianHex": (
                validator.DIRECT_CALL_RAW_LITTLE_ENDIAN_HEX
            ),
            "directCallWord": validator.DIRECT_CALL_WORD,
            "directCallDisplacement": validator.DIRECT_CALL_DISPLACEMENT,
            "alternateStoreAddress": PREPARE_START
            + validator.ALTERNATE_STORE_OFFSET,
            "alternateAfterAddress": PREPARE_START
            + validator.ALTERNATE_AFTER_OFFSET,
            "alternateStoreRawLittleEndianHex": (
                validator.ALTERNATE_STORE_RAW_LITTLE_ENDIAN_HEX
            ),
            "directCallBreakpointID": 3,
            "directReturnBreakpointID": 4,
            "alternateStoreBreakpointID": 5,
            "alternateAfterBreakpointID": 6,
        },
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
            "codeWindow": memory_snapshot(helper_address, helper_payload),
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
        "directRecords": [direct_record(source)],
        "alternateRecords": alternate_records,
        "failures": [],
        "finalFailureCount": 0,
        "directCallSiteHitCount": 1,
        "alternateStoreHitCount": len(alternate_records),
        "rejectedAlternateStoreCount": 0,
        "rejectedAlternateAfterCount": 0,
        "finalDirectRecordCount": 1,
        "finalCompleteDirectRecordCount": 1,
        "finalSelectedDirectRecordCount": 1,
        "finalPendingDirectRecordCount": 0,
        "finalAlternateRecordCount": len(alternate_records),
        "finalCompleteAlternateRecordCount": len(alternate_records),
        "finalSelectedAlternateRecordCount": len(alternate_records),
        "finalPendingAlternateRecordCount": 0,
    }
    return trace, prepare_sha256, helper_sha256, symbol_sha256


class LayerShapesConstructionTraceValidatorTests(unittest.TestCase):
    def validate_document(self, document, prepare_hash, helper_hash, symbol_hash):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "layer-shapes-construction-trace.json"
            path.write_text(
                json.dumps(document, sort_keys=True, allow_nan=False) + "\n",
                encoding="utf-8",
            )
            with (
                mock.patch.object(
                    validator.base,
                    "PREPARE_LAYER_CODE_WINDOW_SHA256",
                    prepare_hash,
                ),
                mock.patch.object(
                    validator, "UNION_HELPER_CODE_WINDOW_SHA256", helper_hash
                ),
                mock.patch.object(
                    validator, "UNION_HELPER_SYMBOL_SHA256", symbol_hash
                ),
                mock.patch.dict(
                    validator.EXPECTED_CONFIGURATION,
                    {
                        "prepareLayerCodeWindowSHA256": prepare_hash,
                        "unionHelperCodeWindowSHA256": helper_hash,
                        "unionHelperSymbolSHA256": symbol_hash,
                    },
                ),
            ):
                return validator.validate(path)

    def test_passing_trace_retains_only_sealed_integrity_claims(self):
        document, prepare_hash, helper_hash, symbol_hash = passing_trace()
        result = self.validate_document(
            document, prepare_hash, helper_hash, symbol_hash
        )
        self.assertEqual(result["conclusion"], "success")
        self.assertEqual(result["aggregate"]["selectedDirectRecordCount"], 1)
        self.assertEqual(
            result["aggregate"]["selectedAlternateRecordCount"],
            validator.MINIMUM_SELECTED_ALTERNATE_RECORD_COUNT,
        )
        self.assertFalse(result["sealedConclusion"]["alternateProducerSemanticsOpened"])
        self.assertFalse(result["sealedConclusion"]["productionShaderAuthorized"])

    def test_simd_to_store_tampering_fails_closed(self):
        document, prepare_hash, helper_hash, symbol_hash = passing_trace()
        record = document["alternateRecords"][0]
        record["simdSourceRegisters"][0]["hex"] = "00" * 16
        with self.assertRaisesRegex(ValueError, "exact store replay"):
            self.validate_document(document, prepare_hash, helper_hash, symbol_hash)

    def test_missing_selected_direct_pair_fails_closed(self):
        document, prepare_hash, helper_hash, symbol_hash = passing_trace()
        document["directRecords"][0]["addresses"]["source"] += 8
        document["directRecords"][0]["selectedSource"] = False
        before = document["directRecords"][0]["registersBefore"]
        after = document["directRecords"][0]["registersAfter"]
        for records in (before, after):
            x28 = next(item for item in records if item["name"] == "x28")
            value = document["directRecords"][0]["addresses"]["source"]
            x28["hex"] = value.to_bytes(8, "little").hex()
            x28["unsignedValue"] = value
        document["finalSelectedDirectRecordCount"] = 0
        with self.assertRaisesRegex(ValueError, "selected direct record coverage"):
            self.validate_document(document, prepare_hash, helper_hash, symbol_hash)

    def test_insufficient_dynamic_diversity_fails_closed(self):
        document, prepare_hash, helper_hash, symbol_hash = passing_trace()
        common = document["alternateRecords"][0]["alternateSourceBefore"]
        common_aggregate = document["alternateRecords"][0]["aggregateAfter"]
        common_simd = document["alternateRecords"][0]["simdSourceRegisters"]
        for record in document["alternateRecords"][1:]:
            address = record["addresses"]["alternateSource"]
            payload = bytes.fromhex(common["hex"])
            record["alternateSourceBefore"] = memory_snapshot(address, payload)
            record["alternateSourceAfter"] = memory_snapshot(address, payload)
            record["aggregateAfter"] = memory_snapshot(
                record["addresses"]["aggregate"],
                bytes.fromhex(common_aggregate["hex"]),
            )
            record["simdSourceRegisters"] = copy.deepcopy(common_simd)
            before_role = bytearray.fromhex(record["roleStateBefore"]["hex"])
            after_role = bytearray.fromhex(record["roleStateAfter"]["hex"])
            before_role[1312:1344] = payload
            after_role[1312:1344] = payload
            after_role[656:688] = payload
            record["roleStateBefore"] = memory_snapshot(
                record["addresses"]["x19"], bytes(before_role)
            )
            record["roleStateAfter"] = memory_snapshot(
                record["addresses"]["x19"], bytes(after_role)
            )
            record["aggregateChanged"] = (
                record["aggregateBefore"]["hex"] != payload.hex()
            )
            record["roleStateChanged"] = before_role != after_role
        with self.assertRaisesRegex(ValueError, "selected alternate record coverage"):
            self.validate_document(document, prepare_hash, helper_hash, symbol_hash)


if __name__ == "__main__":
    unittest.main()
