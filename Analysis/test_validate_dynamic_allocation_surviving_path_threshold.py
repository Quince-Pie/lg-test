#!/usr/bin/env python3
"""Tests for the reduced surviving-path threshold validator."""

import hashlib
import unittest
from pathlib import Path

import validate_dynamic_allocation_surviving_path_threshold as surviving


class SurvivingPathThresholdValidatorTests(unittest.TestCase):
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
        frame.update(
            {
                "symbol": surviving.CAPTURE_BACKDROP_SYMBOL,
                "symbolAddress": f"0x{symbol_address:016x}",
                "imageBase": f"0x{image_base:016x}",
                "imageOffset": "0x1000",
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

    def test_swift_uses_schema_four_only_for_the_sample31_repeat_scan(self) -> None:
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
        self.assertIn('"schemaVersion": 4', path_block)
        self.assertNotIn('"schemaVersion": 3', path_block)
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
