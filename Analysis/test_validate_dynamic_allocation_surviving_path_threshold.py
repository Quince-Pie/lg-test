#!/usr/bin/env python3
"""Tests for the reduced surviving-path threshold validator."""

import hashlib
import struct
import unittest
from pathlib import Path

import validate_dynamic_allocation_surviving_path_threshold as surviving


class SurvivingPathThresholdValidatorTests(unittest.TestCase):
    @staticmethod
    def operand_bytes(payload: bytes, class_name: str) -> dict[str, object]:
        return {
            "class": class_name,
            "lengthBytes": len(payload),
            "hex": payload.hex(),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }

    @classmethod
    def capture_backdrop_operands(cls) -> dict[str, object]:
        symbol_address = 0x1000_0000
        frame_pointer = 0x2000
        stack_pointer = (
            frame_pointer - surviving.CAPTURE_BACKDROP_FRAME_POINTER_TO_STACK_POINTER
        )
        origin_pointer = 0x3000
        context_pointer = 0x4000
        registers = [0] * surviving.CAPTURE_BACKDROP_REGISTER_COUNT
        registers[26 - surviving.CAPTURE_BACKDROP_FIRST_REGISTER] = origin_pointer
        registers[27 - surviving.CAPTURE_BACKDROP_FIRST_REGISTER] = context_pointer
        registers[29 - surviving.CAPTURE_BACKDROP_FIRST_REGISTER] = frame_pointer
        return {
            "schemaVersion": 1,
            "executed": True,
            "class": "bounded live capture_backdrop unwind operands",
            "symbol": surviving.CAPTURE_BACKDROP_SYMBOL,
            "symbolAddress": f"0x{symbol_address:016x}",
            "instructionPointer": (
                f"0x{symbol_address + surviving.CAPTURE_BACKDROP_VERTEX_BINDING_RETURN_OFFSET:016x}"
            ),
            "returnSymbolOffset": (
                surviving.CAPTURE_BACKDROP_VERTEX_BINDING_RETURN_OFFSET
            ),
            "canonicalFrameAddress": f"0x{frame_pointer + 0x10:016x}",
            "framePointer": f"0x{frame_pointer:016x}",
            "stackPointer": f"0x{stack_pointer:016x}",
            "framePointerToStackPointerDelta": (
                surviving.CAPTURE_BACKDROP_FRAME_POINTER_TO_STACK_POINTER
            ),
            "visitedFrameCount": 6,
            "firstRegister": surviving.CAPTURE_BACKDROP_FIRST_REGISTER,
            "registerCount": surviving.CAPTURE_BACKDROP_REGISTER_COUNT,
            "registers": cls.operand_bytes(
                struct.pack(
                    f"<{surviving.CAPTURE_BACKDROP_REGISTER_COUNT}Q",
                    *registers,
                ),
                "little-endian x19-through-x29 words",
            ),
            "readMask": "0x000000ff",
            "requiredReadMask": "0x000000ff",
            "stackOffsets": surviving.CAPTURE_BACKDROP_V1_STACK_OFFSETS,
            "originPointer": f"0x{origin_pointer:016x}",
            "shapePointer": "0x0000000000005000",
            "transformPointer": "0x0000000000000000",
            "contextPointer": f"0x{context_pointer:016x}",
            "contextScaleOffset": (surviving.CAPTURE_BACKDROP_CONTEXT_SCALE_OFFSET),
            "rect": cls.operand_bytes(
                struct.pack("<4i", 1, 2, 3, 4),
                "four little-endian signed 32-bit rectangle words",
            ),
            "affine": cls.operand_bytes(
                struct.pack("<6d", 1, 0, 0, 1, 0, 0),
                "six little-endian binary64 affine words",
            ),
            "origin": cls.operand_bytes(
                struct.pack("<2i", 0, 0),
                "two little-endian signed 32-bit origin words",
            ),
            "scale": cls.operand_bytes(
                struct.pack("<f", 1),
                "one little-endian binary32 scale word",
            ),
        }

    @classmethod
    def capture_backdrop_region_operands(cls) -> dict[str, object]:
        operands = cls.capture_backdrop_operands()
        rect = (1, 2, 3, 4)
        region_handle = (
            ((rect[0] & 0xFFFF) << 48)
            | ((rect[1] & 0xFFFF) << 32)
            | (rect[2] << 17)
            | (rect[3] << 2)
            | 1
        )
        registers = list(
            struct.unpack(
                f"<{surviving.CAPTURE_BACKDROP_REGISTER_COUNT}Q",
                bytes.fromhex(operands["registers"]["hex"]),
            )
        )
        registers[20 - surviving.CAPTURE_BACKDROP_FIRST_REGISTER] = 0x6000
        registers[25 - surviving.CAPTURE_BACKDROP_FIRST_REGISTER] = 2
        operands.update(
            {
                "schemaVersion": 2,
                "readMask": "0x0001ffff",
                "requiredReadMask": "0x0001ffff",
                "stackOffsets": surviving.CAPTURE_BACKDROP_STACK_OFFSETS,
                "registers": cls.operand_bytes(
                    struct.pack(
                        f"<{surviving.CAPTURE_BACKDROP_REGISTER_COUNT}Q",
                        *registers,
                    ),
                    "little-endian x19-through-x29 words",
                ),
                "rendererPointer": "0x0000000000007000",
                "regionHandle": f"0x{region_handle:016x}",
                "ownerRegion248": f"0x{region_handle:016x}",
                "ownerRegion270": "0x0000000000000000",
                "regionOwnerOffsets": surviving.CAPTURE_BACKDROP_REGION_OWNER_OFFSETS,
                "rendererOffsets": (surviving.CAPTURE_BACKDROP_RENDERER_OFFSETS),
                "rendererScale": cls.operand_bytes(
                    struct.pack("<d", 1),
                    "one little-endian binary64 renderer scale word",
                ),
                "rendererRegionControl": cls.operand_bytes(
                    bytes(16),
                    "bounded renderer region-control bytes at offset d0",
                ),
                "originBounds": cls.operand_bytes(
                    struct.pack("<4i", 0, 0, 10, 10),
                    "four little-endian signed 32-bit origin-bound words",
                ),
                "regionIterator": cls.operand_bytes(
                    struct.pack("<3Q", region_handle, 1, 0),
                    "three little-endian region iterator words",
                ),
                "regionPrefix": cls.operand_bytes(
                    b"", "bounded selected-region prefix bytes"
                ),
            }
        )
        return operands

    @classmethod
    def capture_backdrop_owner_region_operands(cls) -> dict[str, object]:
        operands = cls.capture_backdrop_region_operands()
        region_handle = operands["regionHandle"]
        region_handle_value = int(region_handle, 16)
        owner_region_window = bytearray(
            surviving.CAPTURE_BACKDROP_REGION_PREFIX_BYTE_COUNT
        )
        struct.pack_into("<Q", owner_region_window, 0x48, region_handle_value)
        struct.pack_into("<Q", owner_region_window, 0x70, region_handle_value)
        operands.update(
            {
                "schemaVersion": 3,
                "completeRead": True,
                "memoryReadMaximumAttemptCount": (
                    surviving.CAPTURE_BACKDROP_MEMORY_READ_MAXIMUM_ATTEMPT_COUNT
                ),
                "readMask": "0x000fffff",
                "requiredReadMask": "0x000fffff",
                "ownerRegion270": region_handle,
                "ownerRegionWindowOffset": (
                    surviving.CAPTURE_BACKDROP_OWNER_REGION_WINDOW_OFFSET
                ),
                "ownerRegion248Prefix": cls.operand_bytes(
                    b"", "bounded owner +0x248 region prefix bytes"
                ),
                "ownerRegion270Prefix": cls.operand_bytes(
                    b"", "bounded owner +0x270 region prefix bytes"
                ),
                "ownerRegionWindow": cls.operand_bytes(
                    bytes(owner_region_window),
                    "bounded owner bytes at offsets 0x200 through 0x2ff",
                ),
            }
        )
        return operands

    @classmethod
    def capture_backdrop_owner_record_operands(cls) -> dict[str, object]:
        operands = cls.capture_backdrop_owner_region_operands()
        registers = list(
            struct.unpack(
                f"<{surviving.CAPTURE_BACKDROP_REGISTER_COUNT}Q",
                bytes.fromhex(operands["registers"]["hex"]),
            )
        )
        registers[19 - surviving.CAPTURE_BACKDROP_FIRST_REGISTER] = 0x8000
        source_key = bytes(
            range(surviving.CAPTURE_BACKDROP_SOURCE_STATE_WINDOW_BYTE_COUNT)
        )
        record_count = 1
        vector = bytearray(
            record_count * surviving.CAPTURE_BACKDROP_OWNER_RECORD_BYTE_COUNT
        )
        selected_index = 0
        selected_offset = (
            selected_index * surviving.CAPTURE_BACKDROP_OWNER_RECORD_BYTE_COUNT
        )
        vector[selected_offset : selected_offset + len(source_key)] = source_key
        vector[selected_offset + 0x30 : selected_offset + 0x50] = bytes(range(32))
        record_begin = 0x9000
        record_end = record_begin + len(vector)
        owner_prefix = bytearray(
            surviving.CAPTURE_BACKDROP_OWNER_OBJECT_PREFIX_BYTE_COUNT
        )
        struct.pack_into("<2Q", owner_prefix, 0x50, record_begin, record_end)
        owner_window = bytearray.fromhex(operands["ownerRegionWindow"]["hex"])
        struct.pack_into("<Q", owner_window, 0x20, selected_index)
        operands["ownerRegionWindow"] = cls.operand_bytes(
            bytes(owner_window),
            "bounded owner bytes at offsets 0x200 through 0x2ff",
        )
        owner_prefix[0x200:0x300] = owner_window
        operands.update(
            {
                "schemaVersion": 4,
                "readMask": "0x007fffff",
                "requiredReadMask": "0x007fffff",
                "registers": cls.operand_bytes(
                    struct.pack(
                        f"<{surviving.CAPTURE_BACKDROP_REGISTER_COUNT}Q",
                        *registers,
                    ),
                    "little-endian x19-through-x29 words",
                ),
                "ownerRecordOffsets": surviving.CAPTURE_BACKDROP_OWNER_RECORD_OFFSETS,
                "sourceStateWindowOffset": (
                    surviving.CAPTURE_BACKDROP_SOURCE_STATE_WINDOW_OFFSET
                ),
                "ownerObjectPrefix": cls.operand_bytes(
                    bytes(owner_prefix), "bounded owner object prefix bytes"
                ),
                "ownerRecordVector": cls.operand_bytes(
                    bytes(vector), "bounded owner 0xd0-byte record vector"
                ),
                "sourceStateWindow": cls.operand_bytes(
                    source_key, "five little-endian source-state key words"
                ),
            }
        )
        return operands

    @classmethod
    def capture_backdrop_upstream_writer_operands(cls) -> dict[str, object]:
        operands = cls.capture_backdrop_owner_record_operands()
        registers = list(
            struct.unpack(
                f"<{surviving.CAPTURE_BACKDROP_REGISTER_COUNT}Q",
                bytes.fromhex(operands["registers"]["hex"]),
            )
        )
        source_pointer = registers[19 - surviving.CAPTURE_BACKDROP_FIRST_REGISTER]
        owner_pointer = registers[20 - surviving.CAPTURE_BACKDROP_FIRST_REGISTER]
        render_context_pointer = 0xA000
        layer_pointer = 0xB000
        layer_state_pointer = 0xC000
        layer_auxiliary_pointer = 0xD000
        layer_auxiliary_nested_pointer = 0
        registers[22 - surviving.CAPTURE_BACKDROP_FIRST_REGISTER] = (
            render_context_pointer
        )
        registers[24 - surviving.CAPTURE_BACKDROP_FIRST_REGISTER] = layer_pointer

        source_prefix = bytearray(
            surviving.CAPTURE_BACKDROP_SOURCE_OBJECT_PREFIX_BYTE_COUNT
        )
        source_key = bytes.fromhex(operands["sourceStateWindow"]["hex"])
        source_prefix[0x18:0x40] = source_key
        struct.pack_into("<Q", source_prefix, 0x48, owner_pointer)
        layer_prefix = bytearray(
            surviving.CAPTURE_BACKDROP_LAYER_OBJECT_PREFIX_BYTE_COUNT
        )
        struct.pack_into(
            "<2Q", layer_prefix, 0x10, layer_state_pointer, layer_auxiliary_pointer
        )
        layer_state_prefix = bytearray(
            surviving.CAPTURE_BACKDROP_LAYER_STATE_PREFIX_BYTE_COUNT
        )
        struct.pack_into("<Q", layer_state_prefix, 0x120, source_pointer)
        layer_auxiliary_prefix = bytearray(
            surviving.CAPTURE_BACKDROP_LAYER_AUXILIARY_PREFIX_BYTE_COUNT
        )
        struct.pack_into(
            "<Q", layer_auxiliary_prefix, 0x88, layer_auxiliary_nested_pointer
        )
        render_context_prefix = bytes(
            surviving.CAPTURE_BACKDROP_RENDER_CONTEXT_PREFIX_BYTE_COUNT
        )
        region_builder_output = bytes(
            surviving.CAPTURE_BACKDROP_REGION_BUILDER_OUTPUT_BYTE_COUNT
        )
        first_word_symbols = {
            name: {"address": "0x0000000000000000", "resolved": False}
            for name in (
                "source",
                "owner",
                "layer",
                "renderContext",
                "layerState",
                "layerAuxiliary",
                "layerAuxiliaryNested",
            )
        }
        operands.update(
            {
                "schemaVersion": 5,
                "readMask": "0x3fffffff",
                "requiredReadMask": "0x3fffffff",
                "registers": cls.operand_bytes(
                    struct.pack(
                        f"<{surviving.CAPTURE_BACKDROP_REGISTER_COUNT}Q",
                        *registers,
                    ),
                    "little-endian x19-through-x29 words",
                ),
                "upstreamObjectOffsets": surviving.CAPTURE_BACKDROP_UPSTREAM_OBJECT_OFFSETS,
                "upstreamObjectPointers": {
                    "source": f"0x{source_pointer:016x}",
                    "owner": f"0x{owner_pointer:016x}",
                    "layer": f"0x{layer_pointer:016x}",
                    "renderContext": f"0x{render_context_pointer:016x}",
                    "layerState": f"0x{layer_state_pointer:016x}",
                    "layerAuxiliary": f"0x{layer_auxiliary_pointer:016x}",
                    "layerAuxiliaryNested": (
                        f"0x{layer_auxiliary_nested_pointer:016x}"
                    ),
                },
                "regionBuilderOutputStackOffset": (
                    surviving.CAPTURE_BACKDROP_REGION_BUILDER_OUTPUT_STACK_OFFSET
                ),
                "sourceObjectPrefix": cls.operand_bytes(
                    bytes(source_prefix), "bounded source-object prefix bytes"
                ),
                "layerObjectPrefix": cls.operand_bytes(
                    bytes(layer_prefix), "bounded layer-object prefix bytes"
                ),
                "layerStatePrefix": cls.operand_bytes(
                    bytes(layer_state_prefix), "bounded layer-state prefix bytes"
                ),
                "layerAuxiliaryPrefix": cls.operand_bytes(
                    bytes(layer_auxiliary_prefix),
                    "bounded layer-auxiliary prefix bytes",
                ),
                "layerAuxiliaryNestedPrefix": cls.operand_bytes(
                    b"", "bounded nested layer-auxiliary prefix bytes"
                ),
                "renderContextPrefix": cls.operand_bytes(
                    render_context_prefix,
                    "bounded capture_backdrop render-context prefix bytes",
                ),
                "regionBuilderOutput": cls.operand_bytes(
                    region_builder_output,
                    "bounded downstream capture_backdrop region-builder "
                    "stack-state bytes",
                ),
                "upstreamObjectFirstWordSymbols": first_word_symbols,
            }
        )
        return operands

    @staticmethod
    def producer_call_site() -> dict[str, object]:
        payload = bytes(0x800)
        digest = hashlib.sha256(payload).hexdigest()
        return {
            "schemaVersion": 4,
            "executed": True,
            "capture": "transition-path-isolation-31-000",
            "purpose": "producer-primary-mesh-vertex-buffer-binding",
            "frameCount": 1,
            "quartzCoreCodeWindowCount": 1,
            "glassBackgroundRenderCodeCaptureCount": 0,
            "glassMatrixConstructorCodeCaptureCount": 0,
            "glassMatrixConstructorConstantDataCaptureCount": 0,
            "frames": [
                {
                    "imagePath": (
                        "/System/Library/Frameworks/QuartzCore.framework/QuartzCore"
                    ),
                    "codeWindow": {
                        "class": "mapped arm64e call-site window",
                        "returnInstructionOffset": 0x400,
                        "lengthBytes": len(payload),
                        "hex": payload.hex(),
                        "sha256": digest,
                    },
                }
            ],
        }

    @classmethod
    def producer_call_site_with_capture_backdrop(cls) -> dict[str, object]:
        call_site = cls.producer_call_site()
        symbol_address = 0x1000_0000
        image_base = symbol_address - 0x1000
        call_offset = surviving.CAPTURE_BACKDROP_VERTEX_BINDING_CALL_OFFSET
        instruction = 0x9400_0001
        target_address = symbol_address + call_offset + 4
        symbol_payload = bytearray(surviving.CAPTURE_BACKDROP_CODE_BYTE_COUNT)
        symbol_payload[call_offset : call_offset + 4] = instruction.to_bytes(
            4, "little"
        )
        target_payload = bytes(
            surviving.CAPTURE_BACKDROP_DIRECT_CALL_TARGET_CODE_BYTE_COUNT
        )
        call_site.update(
            {
                "schemaVersion": 5,
                "captureBackdropCodeCaptureCount": 1,
                "captureBackdropDecisionDirectCallCount": 1,
                "captureBackdropDirectCallTargetCodeCaptureCount": 1,
            }
        )
        frame = call_site["frames"][0]
        return_address = (
            symbol_address + surviving.CAPTURE_BACKDROP_VERTEX_BINDING_CALL_OFFSET + 4
        )
        frame.update(
            {
                "symbol": surviving.CAPTURE_BACKDROP_SYMBOL,
                "symbolAddress": f"0x{symbol_address:016x}",
                "returnAddress": f"0x{return_address:016x}",
                "symbolOffset": (f"0x{return_address - symbol_address:x}"),
                "imageBase": f"0x{image_base:016x}",
                "imageOffset": f"0x{return_address - image_base:x}",
                "captureBackdropCode": {
                    "class": (
                        "mapped arm64e QuartzCore symbol prefix and direct calls"
                    ),
                    "symbol": surviving.CAPTURE_BACKDROP_SYMBOL,
                    "startAddress": f"0x{symbol_address:016x}",
                    "imageOffset": "0x1000",
                    "requestedByteCount": len(symbol_payload),
                    "lengthBytes": len(symbol_payload),
                    "hex": symbol_payload.hex(),
                    "sha256": hashlib.sha256(symbol_payload).hexdigest(),
                    "decisionDirectCallRange": list(
                        surviving.CAPTURE_BACKDROP_DECISION_CALL_RANGE
                    ),
                    "decisionDirectCallCount": 1,
                    "directCalls": [
                        {
                            "sourceInstructionOffset": call_offset,
                            "sourceInstruction": f"{instruction:08x}",
                            "sourceInstructionAddress": (
                                f"0x{symbol_address + call_offset:016x}"
                            ),
                            "targetAddress": f"0x{target_address:016x}",
                            "targetImageBase": f"0x{image_base:016x}",
                            "targetImageOffset": (f"0x{target_address - image_base:x}"),
                            "targetImagePath": (
                                "/System/Library/Frameworks/"
                                "QuartzCore.framework/QuartzCore"
                            ),
                            "targetCode": {
                                "class": (
                                    "mapped arm64e QuartzCore direct-call target prefix"
                                ),
                                "startAddress": f"0x{target_address:016x}",
                                "requestedByteCount": len(target_payload),
                                "lengthBytes": len(target_payload),
                                "hex": target_payload.hex(),
                                "sha256": hashlib.sha256(target_payload).hexdigest(),
                            },
                        }
                    ],
                },
            }
        )
        return call_site

    @classmethod
    def producer_call_site_with_upstream_targets(cls) -> dict[str, object]:
        call_site = cls.producer_call_site_with_capture_backdrop()
        call_site["schemaVersion"] = 6
        call_site["captureBackdropUpstreamDirectCallCount"] = len(
            surviving.CAPTURE_BACKDROP_UPSTREAM_DIRECT_CALL_OFFSETS
        )
        call_site["captureBackdropUpstreamDirectCallTargetCodeCaptureCount"] = len(
            surviving.CAPTURE_BACKDROP_UPSTREAM_DIRECT_CALL_OFFSETS
        )
        frame = call_site["frames"][0]
        capture = frame["captureBackdropCode"]
        symbol_address = int(capture["startAddress"], 16)
        image_base = int(frame["imageBase"], 16)
        symbol_payload = bytearray.fromhex(capture["hex"])
        instruction = 0x9400_0001
        upstream_calls = []
        for offset in surviving.CAPTURE_BACKDROP_UPSTREAM_DIRECT_CALL_OFFSETS:
            symbol_payload[offset : offset + 4] = instruction.to_bytes(4, "little")
            target_address = symbol_address + offset + 4
            target_payload = bytes(
                surviving.CAPTURE_BACKDROP_UPSTREAM_DIRECT_CALL_TARGET_CODE_BYTE_COUNT
            )
            upstream_calls.append(
                {
                    "sourceInstructionOffset": offset,
                    "sourceInstruction": f"{instruction:08x}",
                    "sourceInstructionAddress": (f"0x{symbol_address + offset:016x}"),
                    "targetAddress": f"0x{target_address:016x}",
                    "targetImageBase": f"0x{image_base:016x}",
                    "targetImageOffset": f"0x{target_address - image_base:x}",
                    "targetImagePath": (
                        "/System/Library/Frameworks/QuartzCore.framework/QuartzCore"
                    ),
                    "targetCode": {
                        "class": ("mapped arm64e QuartzCore direct-call target prefix"),
                        "startAddress": f"0x{target_address:016x}",
                        "requestedByteCount": len(target_payload),
                        "lengthBytes": len(target_payload),
                        "hex": target_payload.hex(),
                        "sha256": hashlib.sha256(target_payload).hexdigest(),
                    },
                }
            )
        capture.update(
            {
                "hex": symbol_payload.hex(),
                "sha256": hashlib.sha256(symbol_payload).hexdigest(),
                "upstreamDirectCallOffsets": list(
                    surviving.CAPTURE_BACKDROP_UPSTREAM_DIRECT_CALL_OFFSETS
                ),
                "upstreamDirectCallCount": len(upstream_calls),
                "upstreamDirectCallTargetCodeByteCount": (
                    surviving.CAPTURE_BACKDROP_UPSTREAM_DIRECT_CALL_TARGET_CODE_BYTE_COUNT
                ),
                "upstreamDirectCalls": upstream_calls,
            }
        )
        return call_site

    def test_matrix_stays_below_observed_capture_ceiling(self) -> None:
        self.assertEqual(len(surviving.expected_interventions(25)), 67)
        self.assertEqual(len(surviving.expected_interventions(31)), 5)
        self.assertEqual(
            sum(
                len(surviving.expected_interventions(sample))
                for sample in surviving.EXPECTED_SOURCE_SAMPLE_INDICES
            ),
            72,
        )
        self.assertLess(72, 114)

    def test_fine_scan_uses_the_measured_brackets_and_remaining_budget(self) -> None:
        self.assertEqual(surviving.FINE_X_VALUES, tuple(range(80, 89)))
        self.assertEqual(surviving.FINE_Y_VALUES, tuple(range(64, 97)))
        self.assertEqual(len(surviving.fine_scan_interventions(25)), 43)
        self.assertEqual(len(surviving.fine_scan_interventions(31)), 63)
        self.assertEqual(
            sum(
                len(surviving.fine_scan_interventions(sample))
                for sample in surviving.EXPECTED_SOURCE_SAMPLE_INDICES
            ),
            106,
        )
        self.assertLess(106, 114)

    def test_cross_axis_scan_repeats_all_four_strong_controls(self) -> None:
        deltas = {
            intervention["delta"]
            for intervention in surviving.fine_scan_interventions(31)
        }
        self.assertTrue(
            {delta for _, delta in surviving.STRONG_DELTAS}.issubset(deltas)
        )

    def test_sample31_unit_scan_uses_the_complete_process_budget(self) -> None:
        interventions = surviving.sample31_repeat_interventions(31)
        scan = [item for item in interventions if item["phase"] == "sample31-unit-scan"]
        x_count = len(surviving.SAMPLE31_UNIT_X_VALUES)
        self.assertEqual(surviving.SAMPLE31_UNIT_X_VALUES, tuple(range(-12, 37)))
        self.assertEqual(surviving.SAMPLE31_UNIT_Y_VALUES, tuple(range(-4, 37)))
        self.assertEqual(len(interventions), 114)
        self.assertEqual(
            [item["delta"][0] for item in scan[:x_count]],
            list(surviving.SAMPLE31_UNIT_X_VALUES),
        )
        self.assertEqual(
            [item["delta"][1] for item in scan[x_count:]],
            list(surviving.SAMPLE31_UNIT_Y_VALUES),
        )

    def test_sample31_late_repeat_controls_are_exactly_frozen(self) -> None:
        interventions = surviving.sample31_repeat_interventions(31)
        repeat = [
            intervention
            for intervention in interventions
            if intervention["phase"] == "repeat-control"
        ]
        self.assertEqual(repeat[0]["name"], "repeat-base")
        self.assertEqual(repeat[0]["mutation"], "base")
        self.assertEqual(repeat[0]["delta"], (0, 0))
        self.assertEqual(
            [item["delta"][0] for item in repeat[1:12]],
            list(surviving.SAMPLE31_REPEAT_X_VALUES),
        )
        self.assertEqual(
            [item["delta"][1] for item in repeat[12:]],
            list(surviving.SAMPLE31_REPEAT_Y_VALUES),
        )

    def test_swift_uses_schema_nine_for_the_upstream_writer_replay(self) -> None:
        source = (
            Path(__file__).parents[1] / "Sources" / "GlassIntrospect" / "main.swift"
        ).read_text(encoding="utf-8")
        fixed_block, path_block = source.split(
            "private func transitionFixedStateAllocationEvidence", maxsplit=1
        )[1].split("private func transitionPathIsolationAllocationEvidence", maxsplit=1)
        path_block = path_block.split(
            "private func transitionFloatEvidence", maxsplit=1
        )[0]
        self.assertIn('"schemaVersion": 2', fixed_block)
        self.assertNotIn('"schemaVersion": 3', fixed_block)
        self.assertNotIn('"schemaVersion": 4', fixed_block)
        self.assertIn('"schemaVersion": 9', path_block)
        self.assertNotIn('"schemaVersion": 3', path_block)
        self.assertNotIn('"schemaVersion": 4', path_block)
        self.assertIn('"scanXValues"', path_block)
        self.assertIn('"scanYValues"', path_block)
        self.assertIn('"repeatXValues"', path_block)
        self.assertIn('"repeatYValues"', path_block)

    def test_swift_captures_the_producer_geometry_call_site_once(self) -> None:
        source = (
            Path(__file__).parents[1] / "Sources" / "GlassIntrospect" / "main.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("producerGeometryCallSiteCaptured", source)
        self.assertIn('capture == "transition-path-isolation-31-000"', source)
        self.assertIn('fragment == "A2Xghfc"', source)
        self.assertIn('"producer-primary-mesh-vertex-buffer-binding"', source)
        self.assertIn("captureBackdropCodeByteCount = 0x4000", source)
        self.assertIn("captureBackdropDecisionCallLowerBound = 0x2000", source)
        self.assertIn("captureBackdropDecisionCallUpperBound = 0x2B58", source)
        self.assertIn("currentCallStackContainsCaptureBackdrop()", source)
        self.assertIn(
            'evidence["captureBackdropCodeCaptureCount"]\n                as? Int == 1',
            source,
        )

    def test_producer_geometry_call_site_payload_is_byte_validated(self) -> None:
        summary = surviving.validate_producer_geometry_call_site(
            self.producer_call_site()
        )
        self.assertTrue(summary["captured"])
        self.assertEqual(summary["frameCount"], 1)
        self.assertEqual(summary["quartzCoreCodeWindowCount"], 1)
        self.assertEqual(len(summary["quartzCoreCodeWindowSHA256"]), 1)

    def test_producer_geometry_call_site_rejects_a_bad_digest(self) -> None:
        call_site = self.producer_call_site()
        call_site["frames"][0]["codeWindow"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "metadata differs"):
            surviving.validate_producer_geometry_call_site(call_site)

    def test_capture_backdrop_symbol_and_direct_call_are_byte_validated(self) -> None:
        summary = surviving.validate_producer_geometry_call_site(
            self.producer_call_site_with_capture_backdrop()
        )
        capture = summary["captureBackdrop"]
        self.assertEqual(summary["schemaVersion"], 5)
        self.assertEqual(capture["symbolPrefixByteCount"], 0x4000)
        self.assertEqual(capture["decisionDirectCallCount"], 1)
        self.assertEqual(capture["decisionDirectCallOffsets"], [0x2B54])
        self.assertEqual(capture["directCallTargetCodeCaptureCount"], 1)

    def test_capture_backdrop_upstream_direct_calls_are_byte_validated(self) -> None:
        summary = surviving.validate_producer_geometry_call_site(
            self.producer_call_site_with_upstream_targets()
        )
        capture = summary["captureBackdrop"]
        self.assertEqual(summary["schemaVersion"], 6)
        self.assertEqual(
            capture["upstreamDirectCallOffsets"],
            list(surviving.CAPTURE_BACKDROP_UPSTREAM_DIRECT_CALL_OFFSETS),
        )
        self.assertEqual(capture["upstreamDirectCallCount"], 7)
        self.assertEqual(capture["upstreamDirectCallTargetCodeCaptureCount"], 7)

    def test_capture_backdrop_distinguishes_return_and_symbol_image_offsets(
        self,
    ) -> None:
        call_site = self.producer_call_site_with_capture_backdrop()
        frame = call_site["frames"][0]
        capture = frame["captureBackdropCode"]
        self.assertEqual(int(frame["imageOffset"], 16), 0x1000 + 0x2B58)
        self.assertEqual(int(capture["imageOffset"], 16), 0x1000)
        surviving.validate_producer_geometry_call_site(call_site)

    def test_capture_backdrop_rejects_a_bad_symbol_digest(self) -> None:
        call_site = self.producer_call_site_with_capture_backdrop()
        call_site["frames"][0]["captureBackdropCode"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "symbol-prefix metadata differs"):
            surviving.validate_producer_geometry_call_site(call_site)

    def test_capture_backdrop_requires_the_known_vertex_binding_call(self) -> None:
        call_site = self.producer_call_site_with_capture_backdrop()
        capture = call_site["frames"][0]["captureBackdropCode"]
        payload = bytearray.fromhex(capture["hex"])
        offset = surviving.CAPTURE_BACKDROP_VERTEX_BINDING_CALL_OFFSET
        payload[offset : offset + 4] = bytes(4)
        capture["hex"] = payload.hex()
        capture["sha256"] = hashlib.sha256(payload).hexdigest()
        with self.assertRaisesRegex(ValueError, "direct-call count differs"):
            surviving.validate_producer_geometry_call_site(call_site)

    def test_capture_backdrop_operand_replay_is_bit_exact(self) -> None:
        operands = surviving.validate_capture_backdrop_operands(
            self.capture_backdrop_operands()
        )
        expected = [
            1.0,
            2.0,
            4.0,
            2.0,
            4.0,
            6.0,
            1.0,
            6.0,
        ]
        self.assertEqual(
            operands["predictedPrimaryPositionBits"],
            [surviving.holdout.float32_bits(value) for value in expected],
        )
        self.assertEqual(
            operands["predictedPrimarySourceBits"],
            [surviving.holdout.float32_bits(value) for value in expected],
        )
        self.assertEqual(operands["transformBranch"], "identity")
        self.assertEqual(operands["rect"], [1, 2, 3, 4])
        self.assertEqual(operands["origin"], [0, 0])
        self.assertEqual(operands["scaleBits"], 0x3F80_0000)

    def test_capture_backdrop_operand_replay_preserves_affine_order(self) -> None:
        predicted = surviving.capture_backdrop_primary_source_bits(
            rect=(1, 2, 3, 4),
            affine=(2, 3, 4, 5, 6, 7),
            origin=(1, 2),
            scale=1,
            transform_branch=True,
        )
        expected = [15, 18, 21, 27, 37, 47, 31, 38]
        self.assertEqual(
            predicted,
            [surviving.holdout.float32_bits(value) for value in expected],
        )

    def test_capture_backdrop_operand_replay_uses_the_null_transform_branch(
        self,
    ) -> None:
        operands = self.capture_backdrop_operands()
        operands["transformPointer"] = "0x0000000000000000"
        validated = surviving.validate_capture_backdrop_operands(operands)
        self.assertEqual(validated["transformBranch"], "identity")

    def test_capture_backdrop_operand_replay_rejects_a_missing_shape(self) -> None:
        operands = self.capture_backdrop_operands()
        operands["shapePointer"] = "0x0000000000000000"
        with self.assertRaisesRegex(ValueError, "operand metadata differs"):
            surviving.validate_capture_backdrop_operands(operands)

    def test_capture_backdrop_primary_positions_use_floor_and_ceil(self) -> None:
        predicted = surviving.capture_backdrop_primary_position_bits(
            rect=(1, 2, 3, 4),
            scale=0.5,
        )
        expected = [0, 1, 2, 1, 2, 3, 0, 3]
        self.assertEqual(
            predicted,
            [surviving.holdout.float32_bits(value) for value in expected],
        )

    def test_capture_backdrop_packed_region_replays_the_selected_rect(self) -> None:
        validated = surviving.validate_capture_backdrop_operands(
            self.capture_backdrop_region_operands()
        )
        self.assertEqual(validated["schemaVersion"], 2)
        self.assertEqual(validated["regionHandleClass"], "packed")
        self.assertEqual(validated["selectedRegionRect"], [1, 2, 3, 4])
        self.assertEqual(validated["consumedRegionRect"], [1, 2, 3, 4])
        self.assertTrue(validated["consumedRegionRectExact"])

    def test_capture_backdrop_schema_three_replays_both_owner_regions(self) -> None:
        validated = surviving.validate_capture_backdrop_operands(
            self.capture_backdrop_owner_region_operands()
        )
        self.assertEqual(validated["schemaVersion"], 3)
        self.assertEqual(validated["ownerRegion248Class"], "packed")
        self.assertEqual(validated["ownerRegion270Class"], "packed")
        self.assertEqual(validated["ownerRegion248FirstRect"], [1, 2, 3, 4])
        self.assertEqual(validated["ownerRegion270FirstRect"], [1, 2, 3, 4])
        self.assertTrue(validated["selectedEqualsOwner248"])
        self.assertEqual(validated["ownerRegionWindowByteCount"], 256)

    def test_capture_backdrop_schema_three_cross_checks_the_owner_window(self) -> None:
        operands = self.capture_backdrop_owner_region_operands()
        owner_window = bytearray.fromhex(operands["ownerRegionWindow"]["hex"])
        owner_window[0x48] ^= 1
        operands["ownerRegionWindow"] = self.operand_bytes(
            bytes(owner_window),
            "bounded owner bytes at offsets 0x200 through 0x2ff",
        )
        with self.assertRaisesRegex(ValueError, "selected-region replay differs"):
            surviving.validate_capture_backdrop_operands(operands)

    def test_capture_backdrop_schema_three_requires_complete_owner_prefixes(
        self,
    ) -> None:
        operands = self.capture_backdrop_owner_region_operands()
        operands["ownerRegion270"] = "0x0000000000008000"
        owner_window = bytearray.fromhex(operands["ownerRegionWindow"]["hex"])
        struct.pack_into("<Q", owner_window, 0x70, 0x8000)
        operands["ownerRegionWindow"] = self.operand_bytes(
            bytes(owner_window),
            "bounded owner bytes at offsets 0x200 through 0x2ff",
        )
        with self.assertRaisesRegex(ValueError, "ownerRegion270Prefix"):
            surviving.validate_capture_backdrop_operands(operands)

    def test_capture_backdrop_schema_three_decodes_a_4k_owner_prefix(self) -> None:
        operands = self.capture_backdrop_owner_region_operands()
        owner_handle = 0x8000
        payload = bytearray(surviving.CAPTURE_BACKDROP_OWNER_REGION_PREFIX_BYTE_COUNT)
        struct.pack_into("<5i", payload, 12, 2, 4, 1, 4, 6)
        operands["ownerRegion270"] = f"0x{owner_handle:016x}"
        owner_window = bytearray.fromhex(operands["ownerRegionWindow"]["hex"])
        struct.pack_into("<Q", owner_window, 0x70, owner_handle)
        operands["ownerRegionWindow"] = self.operand_bytes(
            bytes(owner_window),
            "bounded owner bytes at offsets 0x200 through 0x2ff",
        )
        operands["ownerRegion270Prefix"] = self.operand_bytes(
            bytes(payload), "bounded owner +0x270 region prefix bytes"
        )
        validated = surviving.validate_capture_backdrop_operands(operands)
        self.assertEqual(validated["ownerRegion270Class"], "pointer")
        self.assertEqual(validated["ownerRegion270FirstRect"], [1, 2, 3, 4])
        self.assertEqual(validated["ownerRegion270PrefixByteCount"], 4096)

    def test_capture_backdrop_schema_three_accepts_a_checked_256b_owner_prefix(
        self,
    ) -> None:
        operands = self.capture_backdrop_owner_region_operands()
        owner_handle = 0x8000
        payload = bytearray(surviving.CAPTURE_BACKDROP_REGION_PREFIX_BYTE_COUNT)
        struct.pack_into("<5i", payload, 12, 2, 4, 1, 4, 6)
        operands["ownerRegion270"] = f"0x{owner_handle:016x}"
        owner_window = bytearray.fromhex(operands["ownerRegionWindow"]["hex"])
        struct.pack_into("<Q", owner_window, 0x70, owner_handle)
        operands["ownerRegionWindow"] = self.operand_bytes(
            bytes(owner_window),
            "bounded owner bytes at offsets 0x200 through 0x2ff",
        )
        operands["ownerRegion270Prefix"] = self.operand_bytes(
            bytes(payload), "bounded owner +0x270 region prefix bytes"
        )
        validated = surviving.validate_capture_backdrop_operands(operands)
        self.assertEqual(validated["ownerRegion270FirstRect"], [1, 2, 3, 4])
        self.assertEqual(validated["ownerRegion270PrefixByteCount"], 256)

    def test_capture_backdrop_schema_four_replays_the_owner_record_vector(
        self,
    ) -> None:
        validated = surviving.validate_capture_backdrop_operands(
            self.capture_backdrop_owner_record_operands()
        )
        self.assertEqual(validated["schemaVersion"], 4)
        self.assertEqual(validated["ownerObjectPrefixByteCount"], 768)
        self.assertEqual(validated["ownerRecordCount"], 1)
        self.assertEqual(validated["ownerRecordVectorByteCount"], 0xD0)
        self.assertEqual(validated["sourceStateWindowByteCount"], 40)
        self.assertEqual(validated["sourceRecordMatchIndices"], [0])
        self.assertEqual(validated["selectedOwnerRecordIndex"], 0)
        self.assertTrue(validated["ownerRegionWindowEmbeddedInPrefix"])

    def test_capture_backdrop_schema_four_cross_checks_the_embedded_window(
        self,
    ) -> None:
        operands = self.capture_backdrop_owner_record_operands()
        prefix = bytearray.fromhex(operands["ownerObjectPrefix"]["hex"])
        prefix[0x248] ^= 1
        operands["ownerObjectPrefix"] = self.operand_bytes(
            bytes(prefix), "bounded owner object prefix bytes"
        )
        with self.assertRaisesRegex(ValueError, "record-vector replay differs"):
            surviving.validate_capture_backdrop_operands(operands)

    def test_capture_backdrop_schema_four_requires_a_source_key_match(self) -> None:
        operands = self.capture_backdrop_owner_record_operands()
        operands["sourceStateWindow"] = self.operand_bytes(
            bytes([0xFF]) * surviving.CAPTURE_BACKDROP_SOURCE_STATE_WINDOW_BYTE_COUNT,
            "five little-endian source-state key words",
        )
        with self.assertRaisesRegex(ValueError, "record-vector replay differs"):
            surviving.validate_capture_backdrop_operands(operands)

    def test_capture_backdrop_schema_four_requires_the_observed_single_record(
        self,
    ) -> None:
        operands = self.capture_backdrop_owner_record_operands()
        vector = bytes.fromhex(operands["ownerRecordVector"]["hex"])
        doubled = vector + vector
        prefix = bytearray.fromhex(operands["ownerObjectPrefix"]["hex"])
        begin = struct.unpack_from("<Q", prefix, 0x50)[0]
        struct.pack_into("<Q", prefix, 0x58, begin + len(doubled))
        operands["ownerObjectPrefix"] = self.operand_bytes(
            bytes(prefix), "bounded owner object prefix bytes"
        )
        operands["ownerRecordVector"] = self.operand_bytes(
            doubled, "bounded owner 0xd0-byte record vector"
        )
        with self.assertRaisesRegex(ValueError, "record-vector replay differs"):
            surviving.validate_capture_backdrop_operands(operands)

    def test_capture_backdrop_schema_four_requires_the_cached_record_index(
        self,
    ) -> None:
        operands = self.capture_backdrop_owner_record_operands()
        prefix = bytearray.fromhex(operands["ownerObjectPrefix"]["hex"])
        struct.pack_into("<Q", prefix, 0x220, 1)
        operands["ownerObjectPrefix"] = self.operand_bytes(
            bytes(prefix), "bounded owner object prefix bytes"
        )
        with self.assertRaisesRegex(ValueError, "record-vector replay differs"):
            surviving.validate_capture_backdrop_operands(operands)

    def test_capture_backdrop_schema_four_rejects_a_partial_record(self) -> None:
        operands = self.capture_backdrop_owner_record_operands()
        vector = bytes.fromhex(operands["ownerRecordVector"]["hex"])[1:]
        operands["ownerRecordVector"] = self.operand_bytes(
            vector, "bounded owner 0xd0-byte record vector"
        )
        with self.assertRaisesRegex(ValueError, "ownerRecordVector"):
            surviving.validate_capture_backdrop_operands(operands)

    def test_capture_backdrop_schema_five_replays_the_upstream_chain(self) -> None:
        validated = surviving.validate_capture_backdrop_operands(
            self.capture_backdrop_upstream_writer_operands()
        )
        self.assertEqual(validated["schemaVersion"], 5)
        self.assertTrue(validated["upstreamObjectChainExact"])
        self.assertEqual(validated["sourcePointer"], 0x8000)
        self.assertEqual(validated["ownerPointer"], 0x6000)
        self.assertEqual(validated["layerPointer"], 0xB000)
        self.assertEqual(validated["renderContextPointer"], 0xA000)
        self.assertEqual(validated["layerStatePointer"], 0xC000)
        self.assertEqual(validated["layerAuxiliaryPointer"], 0xD000)
        self.assertEqual(validated["layerAuxiliaryNestedPointer"], 0)
        self.assertEqual(len(bytes.fromhex(validated["regionBuilderOutputHex"])), 64)

    def test_capture_backdrop_schema_five_rejects_a_broken_owner_link(self) -> None:
        operands = self.capture_backdrop_upstream_writer_operands()
        source_prefix = bytearray.fromhex(operands["sourceObjectPrefix"]["hex"])
        struct.pack_into("<Q", source_prefix, 0x48, 0xDEAD)
        operands["sourceObjectPrefix"] = self.operand_bytes(
            bytes(source_prefix), "bounded source-object prefix bytes"
        )
        with self.assertRaisesRegex(ValueError, "upstream object-chain replay differs"):
            surviving.validate_capture_backdrop_operands(operands)

    def test_callback_attempt_retains_bounded_symbol_offsets_without_addresses(
        self,
    ) -> None:
        attempt = {
            "schemaVersion": 1,
            "executed": True,
            "class": "bounded eligible producer callback stack provenance",
            "maximumFrameCount": 32,
            "frameCount": 2,
            "attemptIndex": 0,
            "fragmentFunction": "TimgA2Xhfc_Isrc",
            "captureBackdropSymbolOffsets": ["0x2410"],
            "frames": [
                {"index": 0, "image": "GlassIntrospect", "symbol": "callback"},
                {
                    "index": 3,
                    "image": "QuartzCore",
                    "symbol": surviving.CAPTURE_BACKDROP_SYMBOL,
                    "symbolOffset": "0x2410",
                },
            ],
        }
        validated = surviving.validate_capture_backdrop_operand_attempt(attempt)
        self.assertEqual(validated["captureBackdropSymbolOffsets"], ["0x2410"])
        self.assertEqual(validated["fragmentFunction"], "TimgA2Xhfc_Isrc")

    def test_callback_attempt_can_retain_a_failed_closed_partial_read(self) -> None:
        partial = self.capture_backdrop_owner_region_operands()
        partial["completeRead"] = False
        partial["readMask"] = "0x0007ffff"
        attempt = {
            "schemaVersion": 1,
            "executed": True,
            "class": "bounded eligible producer callback stack provenance",
            "maximumFrameCount": 32,
            "frameCount": 0,
            "attemptIndex": 0,
            "fragmentFunction": "A2Xghfc",
            "captureBackdropSymbolOffsets": [],
            "frames": [],
            "partialOperands": partial,
        }
        validated = surviving.validate_capture_backdrop_operand_attempt(attempt)
        self.assertEqual(validated["partialReadMask"], "0x0007ffff")
        self.assertEqual(validated["partialRequiredReadMask"], "0x000fffff")

    def test_capture_backdrop_pointer_region_decoder_matches_the_helper(self) -> None:
        payload = bytearray(surviving.CAPTURE_BACKDROP_REGION_PREFIX_BYTE_COUNT)
        struct.pack_into("<5i", payload, 12, 2, 4, 1, 4, 6)
        self.assertEqual(
            surviving.capture_backdrop_first_region_rect(0x1000, bytes(payload)),
            [1, 2, 3, 4],
        )

    def test_capture_backdrop_region_decoder_rejects_an_empty_immediate(self) -> None:
        with self.assertRaisesRegex(ValueError, "selected-region rectangle is empty"):
            surviving.capture_backdrop_first_region_rect(1 << 32 | 1, b"")

    def test_capture_backdrop_region_iterator_selects_the_emitted_interval(
        self,
    ) -> None:
        payload = bytearray(surviving.CAPTURE_BACKDROP_REGION_PREFIX_BYTE_COUNT)
        struct.pack_into("<7i", payload, 12, 2, 6, 1, 4, 5, 9, 8)
        self.assertEqual(
            surviving.capture_backdrop_region_rect_for_iterator(
                0x1000, bytes(payload), [0x1000, 9, 0]
            ),
            [5, 2, 4, 6],
        )

    def test_capture_backdrop_region_replay_applies_the_observed_intersection(
        self,
    ) -> None:
        self.assertEqual(
            surviving.capture_backdrop_consumed_region_rect(
                [0, 0, 10, 10],
                [2, 3, 5, 4],
                shape_pointer=1,
                transform_pointer=0,
            ),
            [2, 3, 5, 4],
        )

    def test_capture_backdrop_operand_replay_rejects_a_bad_payload_hash(
        self,
    ) -> None:
        operands = self.capture_backdrop_operands()
        operands["affine"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "affine operand metadata differs"):
            surviving.validate_capture_backdrop_operands(operands)

    def test_swift_captures_bounded_operands_for_every_sample31_record(
        self,
    ) -> None:
        source = (
            Path(__file__).parents[1] / "Sources" / "GlassIntrospect" / "main.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("captureProducerGeometryOperandsIfNeeded", source)
        self.assertIn('"transition-path-isolation-31-"', source)
        self.assertIn('record["captureBackdropOperands"]', source)
        self.assertIn("captureBackdropFramePointerToStackPointer = 0xA50", source)
        self.assertIn("captureBackdropRegionHandleStackOffset = 0x2A0", source)
        self.assertIn('"regionPrefix": serialized(', source)
        self.assertIn('"ownerRegion248Prefix": serialized(', source)
        self.assertIn('"ownerRegion270Prefix": serialized(', source)
        self.assertIn('"ownerObjectPrefix": serialized(', source)
        self.assertIn('"ownerRecordVector": serialized(', source)
        self.assertIn('"sourceStateWindow": serialized(', source)
        self.assertIn('"captureBackdropOperandAttempt"', source)
        self.assertIn('"TimgA2Xhfc_Isrc"', source)

    def test_live_baseline_changes_only_deepest_position(self) -> None:
        states = [
            {"path": [], "position": [0, 0], "bounds": [0, 0, 10, 10]},
            {
                "path": list(surviving.POSITION_PATH),
                "position": [3.5, -2.0],
                "bounds": [0, 0, 4, 4],
            },
        ]
        changed = surviving.live_baseline_states(states, (90, -134))
        self.assertEqual(changed[0], states[0])
        self.assertEqual(changed[1]["position"], [93.5, -136.0])
        self.assertEqual(changed[1]["bounds"], states[1]["bounds"])
        self.assertEqual(states[1]["position"], [3.5, -2.0])

    def test_every_nonbase_intervention_targets_only_position(self) -> None:
        matrices = (
            (
                surviving.expected_interventions,
                surviving.EXPECTED_SOURCE_SAMPLE_INDICES,
            ),
            (
                surviving.fine_scan_interventions,
                surviving.EXPECTED_SOURCE_SAMPLE_INDICES,
            ),
            (
                surviving.sample31_repeat_interventions,
                surviving.SAMPLE31_REPEAT_SOURCE_SAMPLE_INDICES,
            ),
        )
        for builder, samples in matrices:
            for sample in samples:
                for intervention in builder(sample):
                    if intervention["mutation"] == "base":
                        self.assertEqual(intervention["path"], ())
                        self.assertEqual(intervention["delta"], (0, 0))
                        continue
                    self.assertEqual(intervention["path"], surviving.POSITION_PATH)
                    self.assertEqual(intervention["mutation"], "position")

    def test_classification_denies_production_authority(self) -> None:
        self.assertIn("calibration", surviving.CLASSIFICATION)


if __name__ == "__main__":
    unittest.main()
