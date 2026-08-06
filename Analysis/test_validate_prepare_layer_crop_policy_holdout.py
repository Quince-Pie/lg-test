#!/usr/bin/env python3
"""Tests for the unseen exact crop-policy holdout validator."""

from __future__ import annotations

import copy
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

import test_validate_prepare_layer_crop_transfer as base_fixtures
import test_validate_prepare_layer_crop_union_operand as union_fixtures
import validate_prepare_layer_crop_policy_holdout as validator


def snapshot(address: int, payload: bytes):
    return base_fixtures.snapshot(address, payload)


def replace_register(records, name: str, value: int):
    for record in records:
        if record["name"] == name:
            byte_count = record["byteCount"]
            payload = value.to_bytes(byte_count, "little")
            record.update(
                {
                    "hex": payload.hex(),
                    "unsignedValue": value,
                    "valueString": f"0x{value:0{byte_count * 2}x}",
                }
            )
            return
    raise AssertionError(f"register {name} is absent")


def valid_inputs():
    trace, timeline = union_fixtures.valid_inputs()
    union_extension = trace["cropUnionOperandExtension"]
    original_records = union_extension["unionRecords"]
    new_union_records = []
    new_union_links = []
    store_records = []
    store_links = []
    prepare_start = trace["prepareLayer"]["symbolStart"]

    for index, (original, marker, timeline_record) in enumerate(
        zip(
            original_records,
            trace["qualifiedRecords"],
            timeline["dynamicBackgroundUniforms"]["records"],
            strict=True,
        )
    ):
        position = timeline_record["capturedLayerStates"][0]["position"]
        child = (0.0, -0.0, 640.0, 264.0)
        transformed = (
            position[0],
            1024.0 - position[1] - child[3],
            child[2],
            child[3],
        )
        working_crop = (
            int(transformed[0]) - 1,
            int(transformed[1]) - 1,
            1024 - (int(transformed[0]) - 1),
            266,
        )
        observed_aggregate = (
            float(working_crop[0]),
            float(working_crop[1]),
            max(
                transformed[0] + transformed[2],
                float(working_crop[0] + working_crop[2]),
            )
            - float(working_crop[0]),
            max(
                transformed[1] + transformed[3],
                float(working_crop[1] + working_crop[3]),
            )
            - float(working_crop[1]),
        )
        marker_role = bytearray.fromhex(marker["roleState"]["hex"])
        struct.pack_into(
            "<4d",
            marker_role,
            validator.crop_validator.ROLE_AGGREGATE_OFFSET,
            *observed_aggregate,
        )
        struct.pack_into(
            "<4d",
            marker_role,
            validator.crop_validator.ROLE_RECURSIVE_CHILD_OFFSET,
            *child,
        )
        marker["roleState"] = snapshot(
            marker["roleState"]["address"], bytes(marker_role)
        )
        marker["prepareFrames"][0]["roleState"] = copy.deepcopy(marker["roleState"])
        timeline_record["capturedLayerStates"].append(
            {
                "path": [1, 0, 1],
                "position": [0.0, 0.0],
                "bounds": [9.25, 9.25, 612.5, 238.5],
            }
        )
        timeline_record["filter"] = {
            "inputValues": {
                "inputBlurRadius": 0.0,
                "inputBleedBlurRadius": 0.0,
            }
        }

        original_role = bytearray.fromhex(original["roleState"]["hex"])
        struct.pack_into(
            "<4d",
            original_role,
            validator.union_validator.UNION_INPUT_ROLE_OFFSET,
            *(float(value) for value in working_crop),
        )
        original["roleState"] = snapshot(
            original["roleState"]["address"], bytes(original_role)
        )
        layer_window = bytearray.fromhex(original["layerShapesState"]["hex"])
        struct.pack_into("<4i", layer_window, 16, *working_crop)
        struct.pack_into("<4i", layer_window, 32, *working_crop)
        original["layerShapesState"] = snapshot(
            original["layerShapesState"]["address"], bytes(layer_window)
        )
        original["inputState"] = snapshot(
            original["frameIdentity"]["input"],
            struct.pack("<4d", *(float(value) for value in working_crop)),
        )
        original["targetBefore"] = snapshot(
            original["frameIdentity"]["destination"],
            struct.pack("<4d", *transformed),
        )
        original["targetAfter"] = snapshot(
            original["frameIdentity"]["destination"],
            struct.pack("<4d", *observed_aggregate),
        )

        selected = copy.deepcopy(original)
        selected_index = index * 2 + 1
        selected["recordIndex"] = selected_index
        selected["callEventSequence"] = index * 4 + 3
        selected["returnEventSequence"] = index * 4 + 4
        selected["callHitIndex"] = selected_index + 1
        selected["returnHitIndex"] = selected_index + 1

        first = copy.deepcopy(original)
        first_index = index * 2
        first["recordIndex"] = first_index
        first["callEventSequence"] = index * 4 + 1
        first["returnEventSequence"] = index * 4 + 2
        first["callHitIndex"] = first_index + 1
        first["returnHitIndex"] = first_index + 1
        first_role_base = selected["frameIdentity"]["roleBase"] - 48
        first_input = (
            first_role_base + validator.union_validator.UNION_INPUT_ROLE_OFFSET
        )
        first["frameIdentity"]["roleBase"] = first_role_base
        first["frameIdentity"]["input"] = first_input
        replace_register(first["registers"], "x19", first_role_base)
        replace_register(first["registers"], "x1", first_input)
        first["roleState"]["address"] = first_role_base
        first["inputState"]["address"] = first_input
        first["targetBefore"] = snapshot(
            first["frameIdentity"]["destination"], bytes(32)
        )
        first["targetAfter"] = copy.deepcopy(first["inputState"])
        first["targetAfter"]["address"] = first["frameIdentity"]["destination"]
        new_union_records.extend((first, selected))

        marker["cropUnionOperandWindow"] = {
            "startRecordIndex": first_index,
            "endRecordIndexExclusive": selected_index + 1,
            "destinationAddress": selected["frameIdentity"]["destination"],
            "matchingRecordIndices": [first_index, selected_index],
        }
        new_union_links.append(
            {
                "markerRecordIndex": index,
                "markerCallbackSequence": marker["callbackSequence"],
                "startUnionRecordIndex": first_index,
                "endUnionRecordIndexExclusive": selected_index + 1,
                "destinationAddress": selected["frameIdentity"]["destination"],
                "matchingUnionRecordIndices": [first_index, selected_index],
            }
        )

        candidate, _expansion, _roi = (
            validator.crop_analysis.public_crop_float_candidate(
                position,
                (9.25, 9.25, 612.5, 238.5),
                transformed,
                1024.0,
                0.0,
                0.0,
            )
        )
        store_role_base = selected["frameIdentity"]["roleBase"] + 0x40_0000
        layer_shapes = selected["frameIdentity"]["layerShapesBase"]
        role = bytearray(validator.crop_validator.ROLE_STATE_BYTE_COUNT)
        struct.pack_into("<4i", role, validator.ROLE_WORKING_CROP_OFFSET, *working_crop)
        struct.pack_into("<4d", role, validator.ROLE_FLOAT_INPUT_OFFSET, *candidate)
        register_values = {
            "x19": store_role_base,
            "x28": layer_shapes,
            "x29": store_role_base + 0x900,
            "sp": store_role_base + 0x800,
            "pc": prepare_start + validator.STORE_OFFSET,
            "cpsr": 0x1000,
        }
        store = {
            "recordIndex": index,
            "storeHitIndex": index + 1,
            "threadID": marker["threadID"],
            "prepareRecursionDepth": selected["prepareRecursionDepth"],
            "frame": {
                **selected["frame"],
                "pc": prepare_start + validator.STORE_OFFSET,
                "symbolOffset": validator.STORE_OFFSET,
            },
            "backtrace": copy.deepcopy(selected["backtrace"]),
            "registers": base_fixtures.registers(
                validator.STORE_REGISTER_NAMES, register_values
            ),
            "simdSourceRegisters": [
                {
                    "name": "v0",
                    "byteCount": 16,
                    "hex": struct.pack("<4i", *working_crop).hex(),
                    "valueString": None,
                }
            ],
            "frameIdentity": {
                "threadID": marker["threadID"],
                "roleBase": store_role_base,
                "framePointer": register_values["x29"],
                "layerShapesBase": layer_shapes,
                "destination": layer_shapes + validator.LAYER_SHAPES_NESTED_OFFSET,
            },
            "roleState": snapshot(store_role_base, bytes(role)),
            "destinationBefore": snapshot(
                layer_shapes + validator.LAYER_SHAPES_NESTED_OFFSET,
                bytes(16),
            ),
        }
        store_records.append(store)
        marker["cropPolicyStoreWindow"] = {
            "startRecordIndex": index,
            "endRecordIndexExclusive": index + 1,
            "selectedUnionRecordIndex": selected_index,
            "selectedLayerShapesBase": layer_shapes,
            "matchingStoreRecordIndices": [index],
        }
        store_links.append(
            {
                "markerRecordIndex": index,
                "markerCallbackSequence": marker["callbackSequence"],
                "startStoreRecordIndex": index,
                "endStoreRecordIndexExclusive": index + 1,
                "selectedUnionRecordIndex": selected_index,
                "selectedLayerShapesBase": layer_shapes,
                "matchingStoreRecordIndices": [index],
            }
        )

    union_extension["unionRecords"] = new_union_records
    union_extension["markerLinks"] = new_union_links
    union_extension.update(
        {
            "finalEventSequence": 128,
            "finalUnionCallHitCount": 64,
            "finalUnionReturnHitCount": 64,
            "finalQualifiedUnionRecordCount": 64,
            "finalCompleteUnionRecordCount": 64,
            "finalRejectedUnionCallCount": 0,
            "finalRejectedUnionReturnCount": 0,
            "finalMarkerLinkCount": 32,
            "finalLinkedUnionRecordCount": 64,
            "finalTrailingUnionRecordCount": 0,
        }
    )
    trace["cropPolicyHoldoutExtension"] = {
        "cropPolicyHoldoutExtensionSchemaVersion": 1,
        "classification": "prospective synthetic fixture",
        "status": "finalized",
        "statusBeforeFinalization": "crop-policy-store-active",
        "configuration": validator.EXPECTED_EXTENSION_CONFIGURATION,
        "prepareLayerSymbolStart": prepare_start,
        "storeBreakpointID": 4,
        "storeInstructionSHA256": hashlib.sha256(
            bytes.fromhex(validator.STORE_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX)
        ).hexdigest(),
        "storeRecords": store_records,
        "markerLinks": store_links,
        "rejectionGroups": [],
        "finalStoreHitCount": 32,
        "finalQualifiedStoreRecordCount": 32,
        "finalRejectedStoreCount": 0,
        "finalMarkerLinkCount": 32,
        "finalLinkedStoreRecordCount": 32,
        "finalTrailingStoreRecordCount": 0,
    }
    return trace, timeline


def write_documents(trace, timeline, directory: Path):
    trace_path = directory / "trace.json"
    timeline_path = directory / "timeline.json"
    trace_path.write_text(json.dumps(trace), encoding="utf-8")
    timeline_path.write_text(json.dumps(timeline), encoding="utf-8")
    return trace_path, timeline_path


class PrepareLayerCropPolicyHoldoutValidatorTests(unittest.TestCase):
    def validate(self, trace, timeline):
        with tempfile.TemporaryDirectory() as temporary:
            paths = write_documents(trace, timeline, Path(temporary))
            return validator.validate(*paths, "circle-640-center")

    def test_complete_unseen_crop_policy_fixture_passes(self):
        result = self.validate(*valid_inputs())
        self.assertEqual(result["conclusion"], "success")
        self.assertEqual(result["recordCount"], 32)
        self.assertEqual(result["componentCount"], 128)
        sealed = result["sealedConclusion"]
        self.assertTrue(sealed["allPreIntegerFloatingInputsReplayedBitForBit"])
        self.assertTrue(sealed["allSignedIntegerOperandsReplayedExactly"])
        self.assertTrue(sealed["unseenGeometryCropPolicyTransferPassed"])
        self.assertFalse(sealed["productionShaderAuthorized"])
        self.assertFalse(sealed["liquidGlassParityEstablished"])

    def test_changed_preinteger_float_fails(self):
        trace, timeline = valid_inputs()
        record = trace["cropPolicyHoldoutExtension"]["storeRecords"][0]
        role = bytearray.fromhex(record["roleState"]["hex"])
        role[validator.ROLE_FLOAT_INPUT_OFFSET] ^= 1
        record["roleState"] = snapshot(record["roleState"]["address"], bytes(role))
        with self.assertRaisesRegex(ValueError, "producer replay differs"):
            self.validate(trace, timeline)

    def test_changed_simd_store_source_fails(self):
        trace, timeline = valid_inputs()
        record = trace["cropPolicyHoldoutExtension"]["storeRecords"][0]
        payload = bytearray.fromhex(record["simdSourceRegisters"][0]["hex"])
        payload[0] ^= 1
        record["simdSourceRegisters"][0]["hex"] = payload.hex()
        with self.assertRaisesRegex(ValueError, "SIMD source differs"):
            self.validate(trace, timeline)

    def test_first_union_substitution_fails(self):
        trace, timeline = valid_inputs()
        link = trace["cropPolicyHoldoutExtension"]["markerLinks"][0]
        link["selectedUnionRecordIndex"] = 0
        with self.assertRaisesRegex(ValueError, "pointer correlation differs"):
            self.validate(trace, timeline)

    def test_public_formula_change_fails_before_store_comparison(self):
        trace, timeline = valid_inputs()
        layer = timeline["dynamicBackgroundUniforms"]["records"][0][
            "capturedLayerStates"
        ][1]
        layer["bounds"][0] += 2.0
        with self.assertRaisesRegex(ValueError, "public crop candidate differs"):
            self.validate(trace, timeline)


if __name__ == "__main__":
    unittest.main()
