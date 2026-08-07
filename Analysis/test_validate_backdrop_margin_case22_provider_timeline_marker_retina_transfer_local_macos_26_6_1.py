#!/usr/bin/env python3
"""Tests for the active-Retina timeline-marker/provider validator."""

from __future__ import annotations

import ast
import struct
import unittest
from pathlib import Path

import validate_backdrop_margin_case22_provider_timeline_marker_retina_transfer_local_macos_26_6_1 as validator


SOURCE = Path(validator.__file__).resolve().read_text(encoding="utf-8")


class RetinaTimelineMarkerValidatorTests(unittest.TestCase):
    def test_source_remains_python_3_9_parseable(self) -> None:
        ast.parse(SOURCE, feature_version=(3, 9))

    def test_all_18_loaded_fields_are_bitwise_gated(self) -> None:
        shadow_offset = struct.pack("<dd", 0.0, 8.0)
        inputs = {
            "inputShadowOffset": {"hex": shadow_offset.hex()},
            "inputShadowAmount": 2.5,
            "inputShadowRadius": 0.75,
            "inputShadowOpacity": 0.1,
            "inputShadowVibrancyContribution": 0.2,
            "inputBlurRadius": 3.25,
            "inputBlurDistance0": -1.0,
            "inputBlurDistance1": -0.5,
            "inputBlurDistance4": 4.0,
            "inputOuterRefractionAmount": 4.0,
            "inputShadowHeight": 8.0,
            "inputInnerRefractionAmount": -2.0,
            "inputRefractionOpacity": 0.25,
            "inputBleedAmount": 1.5,
            "inputBleedHeight": 1.5,
            "inputBleedBlurRadius": 3.0,
            "inputBleedOpacity": 0.3,
        }
        raw = bytearray(384)
        raw[0x008:0x018] = shadow_offset
        for offset, key, scale in validator.F64_PUBLIC_FIELDS:
            raw[offset : offset + 8] = struct.pack("<d", inputs[key] * scale)
        for offset, key in validator.F32_PUBLIC_FIELDS:
            raw[offset : offset + 4] = struct.pack("<f", inputs[key])
        validator.provider_loaded_fields_match(bytes(raw), inputs)
        self.assertEqual(
            validator.expected_public_return(inputs), struct.pack("<d", 10.5)
        )
        raw[0x178] ^= 1
        with self.assertRaises(ValueError):
            validator.provider_loaded_fields_match(bytes(raw), inputs)

    def test_selection_is_structural_and_includes_endpoint(self) -> None:
        self.assertIn("for sample_index in range(1, 33):", SOURCE)
        self.assertIn("call_index = end - 1", SOURCE)
        self.assertIn("global_matches == [call_index]", SOURCE)
        self.assertIn('"selectionUsesCapturedValues": False', SOURCE)
        self.assertIn('"all32SamplesAcceptanceGated": True', SOURCE)

    def test_initial_and_noninitial_object_return_laws_are_exact(self) -> None:
        self.assertIn("returns[0] == ZERO_F64", SOURCE)
        self.assertIn("zip(objects[1:], returns[1:])", SOURCE)
        self.assertIn("max(abs(axis_x), abs(axis_y)) + abs(shape_radius)", SOURCE)

    def test_product_authority_remains_narrow(self) -> None:
        for statement in (
            '"upstreamCropAllocationPolicyEstablished": False',
            '"physicalRetinaColorPixelCompositorTransferEstablished": False',
            '"independentWalleZeroByteFrameParityEstablished": False',
            '"liquidGlassParityEstablished": False',
            '"productionShaderAuthorized": False',
        ):
            self.assertIn(statement, SOURCE)


if __name__ == "__main__":
    unittest.main()
