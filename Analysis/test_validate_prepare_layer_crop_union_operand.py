#!/usr/bin/env python3
"""Tests for the destination-correlated crop-union operand validator."""

import copy
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

import test_validate_prepare_layer_crop_transfer as base_fixtures
import validate_prepare_layer_crop_union_operand as validator


def write_documents(trace, timeline, directory):
    trace_path = directory / "trace.json"
    timeline_path = directory / "timeline.json"
    trace_path.write_text(json.dumps(trace), encoding="utf-8")
    timeline_path.write_text(json.dumps(timeline), encoding="utf-8")
    return trace_path, timeline_path


def valid_inputs():
    trace, timeline = base_fixtures.valid_inputs()
    prepare_start = trace["prepareLayer"]["symbolStart"]
    extension = {
        "cropUnionOperandExtensionSchemaVersion": 1,
        "classification": "prospective synthetic fixture",
        "status": "finalized",
        "statusBeforeFinalization": "crop-union-breakpoints-active",
        "configuration": validator.EXPECTED_EXTENSION_CONFIGURATION,
        "prepareLayerSymbolStart": prepare_start,
        "unionCallBreakpointID": 2,
        "unionReturnBreakpointID": 3,
        "unionCallInstructionSHA256": hashlib.sha256(
            bytes.fromhex(validator.UNION_CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX)
        ).hexdigest(),
        "unionReturnInstructionSHA256": hashlib.sha256(
            bytes.fromhex(validator.UNION_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX)
        ).hexdigest(),
        "unionRecords": [],
        "markerLinks": [],
        "rejectionGroups": [],
    }
    uniform_records = timeline["dynamicBackgroundUniforms"]["records"]
    for index, (marker, uniform) in enumerate(
        zip(trace["qualifiedRecords"], uniform_records, strict=True)
    ):
        position = uniform["capturedLayerStates"][0]["position"]
        child = (0.0, -0.0, 640.0, 648.0)
        transformed = (
            position[0],
            (1024.0 - position[1]) - (child[1] + child[3]),
            child[2],
            child[3],
        )
        nested = (
            int(transformed[0]) - 1,
            int(transformed[1]) - 1,
            642,
            650,
        )
        observed = tuple(float(value) for value in nested)

        role = bytearray.fromhex(marker["roleState"]["hex"])
        struct.pack_into("<4d", role, validator.crop_validator.ROLE_AGGREGATE_OFFSET, *observed)
        struct.pack_into("<4d", role, validator.crop_validator.ROLE_RECURSIVE_CHILD_OFFSET, *child)
        role_snapshot = base_fixtures.snapshot(
            marker["roleState"]["address"], bytes(role)
        )
        marker["roleState"] = role_snapshot
        marker["prepareFrames"][0]["roleState"] = role_snapshot

        destination = marker["frameIdentity"]["roleBase"] + 0x290
        union_role_address = marker["frameIdentity"]["roleBase"] + 0x10_0000
        layer_shapes_address = marker["frameIdentity"]["source"] + 0x20_0000
        union_role = bytearray(role)
        struct.pack_into(
            "<4d",
            union_role,
            validator.UNION_INPUT_ROLE_OFFSET,
            *(float(value) for value in nested),
        )
        layer_window = bytearray(validator.LAYER_SHAPES_WINDOW_BYTE_COUNT)
        struct.pack_into("<4i", layer_window, 16, *nested)
        struct.pack_into("<4i", layer_window, 32, *nested)
        values = {
            "x0": destination,
            "x1": union_role_address + validator.UNION_INPUT_ROLE_OFFSET,
            "x2": 0,
            "x19": union_role_address,
            "x28": layer_shapes_address,
            "x29": union_role_address + 0x9000,
            "sp": union_role_address + 0x8000,
            "pc": prepare_start + validator.UNION_CALL_OFFSET,
            "cpsr": 0x1000,
        }
        backtrace = copy.deepcopy(marker["backtrace"])
        union_depth = sum(
            (record.get("function") or "")
            == validator.crop_validator.PREPARE_LAYER_FUNCTION
            for record in backtrace
        )
        union_record = {
            "recordIndex": index,
            "callEventSequence": index * 2 + 1,
            "returnEventSequence": index * 2 + 2,
            "callHitIndex": index + 1,
            "returnHitIndex": index + 1,
            "threadID": marker["threadID"],
            "prepareRecursionDepth": union_depth,
            "frame": {
                "frameIndex": 0,
                "pc": prepare_start + validator.UNION_CALL_OFFSET,
                "function": validator.crop_validator.PREPARE_LAYER_FUNCTION,
                "symbolStart": prepare_start,
                "symbolEnd": prepare_start
                + validator.crop_validator.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
                "symbolOffset": validator.UNION_CALL_OFFSET,
                "module": {"valid": True},
            },
            "backtrace": backtrace,
            "registers": base_fixtures.registers(
                validator.UNION_REGISTER_NAMES, values
            ),
            "frameIdentity": {
                "threadID": marker["threadID"],
                "roleBase": union_role_address,
                "framePointer": values["x29"],
                "layerShapesBase": layer_shapes_address,
                "destination": destination,
                "input": values["x1"],
            },
            "roleState": base_fixtures.snapshot(
                union_role_address, bytes(union_role)
            ),
            "layerShapesState": base_fixtures.snapshot(
                layer_shapes_address + validator.LAYER_SHAPES_WINDOW_OFFSET,
                bytes(layer_window),
            ),
            "inputState": base_fixtures.snapshot(
                values["x1"],
                struct.pack("<4d", *(float(value) for value in nested)),
            ),
            "targetBefore": base_fixtures.snapshot(
                destination, struct.pack("<4d", *transformed)
            ),
            "targetAfter": base_fixtures.snapshot(
                destination, struct.pack("<4d", *observed)
            ),
            "returnPC": prepare_start + validator.UNION_RETURN_OFFSET,
            "complete": True,
        }
        extension["unionRecords"].append(union_record)
        marker["cropUnionOperandWindow"] = {
            "startRecordIndex": index,
            "endRecordIndexExclusive": index + 1,
            "destinationAddress": destination,
            "matchingRecordIndices": [index],
        }
        extension["markerLinks"].append(
            {
                "markerRecordIndex": index,
                "markerCallbackSequence": marker["callbackSequence"],
                "startUnionRecordIndex": index,
                "endUnionRecordIndexExclusive": index + 1,
                "destinationAddress": destination,
                "matchingUnionRecordIndices": [index],
            }
        )
    extension.update(
        {
            "finalEventSequence": 64,
            "finalUnionCallHitCount": 32,
            "finalUnionReturnHitCount": 32,
            "finalQualifiedUnionRecordCount": 32,
            "finalCompleteUnionRecordCount": 32,
            "finalRejectedUnionCallCount": 0,
            "finalRejectedUnionReturnCount": 0,
            "finalMarkerLinkCount": 32,
            "finalLinkedUnionRecordCount": 32,
            "finalTrailingUnionRecordCount": 0,
        }
    )
    trace["cropUnionOperandExtension"] = extension
    return trace, timeline


class PrepareLayerCropUnionOperandValidatorTests(unittest.TestCase):
    def validate(self, trace, timeline):
        with tempfile.TemporaryDirectory() as temporary:
            trace_path, timeline_path = write_documents(
                trace, timeline, Path(temporary)
            )
            return validator.validate(
                trace_path, timeline_path, "circle-640-center"
            )

    def test_complete_destination_correlated_capture_passes(self):
        trace, timeline = valid_inputs()
        result = self.validate(trace, timeline)
        self.assertEqual(result["conclusion"], "success")
        self.assertEqual(result["recordCount"], 32)
        self.assertEqual(result["componentCount"], 128)
        self.assertEqual(result["unionRecordCount"], 32)
        self.assertEqual(result["records"][0]["nestedInputI32"], [510, -136, 642, 650])
        sealed = result["sealedConclusion"]
        self.assertTrue(sealed["destinationOnlyMarkerCorrelationPassed"])
        self.assertTrue(sealed["allSelectedFloatingUnionsReplayedBitForBit"])
        self.assertTrue(sealed["allFinalAggregateComponentsReplayedBitForBit"])
        self.assertFalse(sealed["generalCropPolicyRecovered"])
        self.assertFalse(sealed["productionShaderAuthorized"])
        self.assertFalse(sealed["liquidGlassParityEstablished"])

    def test_changed_integer_operand_bytes_fail(self):
        trace, timeline = valid_inputs()
        record = trace["cropUnionOperandExtension"]["unionRecords"][0]
        payload = bytearray.fromhex(record["layerShapesState"]["hex"])
        payload[16] ^= 1
        record["layerShapesState"] = base_fixtures.snapshot(
            record["layerShapesState"]["address"], bytes(payload)
        )
        with self.assertRaisesRegex(ValueError, "signed-int conversion differs"):
            self.validate(trace, timeline)

    def test_value_based_destination_substitution_fails(self):
        trace, timeline = valid_inputs()
        link = trace["cropUnionOperandExtension"]["markerLinks"][0]
        link["destinationAddress"] += 16
        with self.assertRaisesRegex(ValueError, "destination correlation differs"):
            self.validate(trace, timeline)

    def test_non_bit_exact_union_result_fails(self):
        trace, timeline = valid_inputs()
        record = trace["cropUnionOperandExtension"]["unionRecords"][0]
        payload = bytearray.fromhex(record["targetAfter"]["hex"])
        payload[0] ^= 1
        record["targetAfter"] = base_fixtures.snapshot(
            record["targetAfter"]["address"], bytes(payload)
        )
        with self.assertRaisesRegex(ValueError, "semantic replay differs"):
            self.validate(trace, timeline)


if __name__ == "__main__":
    unittest.main()
