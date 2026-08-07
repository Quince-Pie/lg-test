#!/usr/bin/env python3
"""Tests for the prospective timeline-marker/provider validator."""

from __future__ import annotations

import ast
import struct
import unittest
from pathlib import Path

import validate_backdrop_margin_case22_provider_timeline_marker_transfer_local_macos_26_6_1 as validator


SOURCE_PATH = Path(validator.__file__).resolve()
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


class TimelineMarkerValidatorTests(unittest.TestCase):
    def test_source_remains_python_3_9_parseable(self) -> None:
        ast.parse(SOURCE, feature_version=(3, 9))

    def test_loaded_field_gate_is_bitwise(self) -> None:
        raw = bytearray(384)
        shadow_amount = 2.5
        blur_radius = 3.25
        inner_refraction = -2.0
        bleed_amount = 1.5
        shadow_offset = struct.pack("<dd", 0.0, 8.0)
        raw[0x008:0x018] = shadow_offset
        raw[0x018:0x020] = struct.pack("<d", shadow_amount)
        raw[0x098:0x0A0] = struct.pack("<d", 2.0 * blur_radius)
        raw[0x0E8:0x0F0] = struct.pack("<d", inner_refraction)
        raw[0x160:0x168] = struct.pack("<d", bleed_amount)
        inputs = {
            "inputShadowOffset": {"hex": shadow_offset.hex()},
            "inputShadowAmount": shadow_amount,
            "inputBlurRadius": blur_radius,
            "inputInnerRefractionAmount": inner_refraction,
            "inputBleedAmount": bleed_amount,
            "inputBleedHeight": bleed_amount,
        }
        validator.provider_loaded_fields_match(bytes(raw), inputs)
        raw[0x110] = 1
        with self.assertRaises(ValueError):
            validator.provider_loaded_fields_match(bytes(raw), inputs)

    def test_nonendpoint_predictions_are_strict_and_endpoint_is_exploratory(
        self,
    ) -> None:
        self.assertIn("for sample_index in range(1, 32):", SOURCE)
        self.assertIn("len(matches) == 1", SOURCE)
        self.assertIn("global_matches == matches", SOURCE)
        self.assertIn("provider_loaded_fields_match", SOURCE)
        self.assertIn('"usedAsAcceptanceGate": False', SOURCE)

    def test_exact_event_partition_is_mandatory(self) -> None:
        self.assertIn("TIMELINE_MARKER_COUNT + 2 * len(calls)", SOURCE)
        self.assertIn("previous_end == len(calls)", SOURCE)
        self.assertIn("entry < complete < event_index", SOURCE)
        self.assertIn('"selectedCallsiteEnabledAtFinalization"', SOURCE)

    def test_product_authority_remains_narrow(self) -> None:
        self.assertIn('"liquidGlassParityEstablished": False', SOURCE)
        self.assertIn('"productionShaderAuthorized": False', SOURCE)
        self.assertIn('"upstreamCropAllocationPolicyEstablished": False', SOURCE)

    def test_transport_correction_crossed_no_optical_boundary(self) -> None:
        self.assertIn("transportOperationalAmendment", SOURCE)
        self.assertIn("finalTimelineMarkerCount", SOURCE)
        self.assertIn("opticalPredictionsEvaluated", SOURCE)
        self.assertIn("importAtExactMainEntryAfterDyldLoad", SOURCE)


if __name__ == "__main__":
    unittest.main()
