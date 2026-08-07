#!/usr/bin/env python3
"""Tests for the prospective public-render/provider validator."""

from __future__ import annotations

import ast
import struct
import unittest
from pathlib import Path

import validate_backdrop_margin_case22_provider_public_render_interval_transfer_local_macos_26_6_1 as validator


SOURCE_PATH = (
    Path(__file__).resolve().parent
    / "validate_backdrop_margin_case22_provider_public_render_interval_transfer_local_macos_26_6_1.py"
)
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


class PublicRenderIntervalValidatorTests(unittest.TestCase):
    def test_source_remains_python_3_9_parseable(self) -> None:
        ast.parse(SOURCE, feature_version=(3, 9))

    def test_exact_render_boundary_is_revalidated(self) -> None:
        for value in (
            "F8B0B6E3-3270-3C94-817F-B4914852D04C",
            "1ca54720d237eb6970b65dd2ecc88b8372b64667f4ea2d28ef4bc8414668e2fd",
            "0c661f1010199a56e6730d897079fda69fc4a267f7f48d1e2054b14ff9270e0c",
            'RENDER_CALL_INSTRUCTION_HEX = "dfcfff97"',
        ):
            self.assertIn(value, SOURCE)

    def test_demangled_presentation_is_diagnostic_not_identity(self) -> None:
        self.assertNotIn('record.get("function") == function', SOURCE)
        self.assertIn('f"{label} function presentation is absent"', SOURCE)
        self.assertIn('record.get("codeSHA256") == digest', SOURCE)

    def test_direct_branch_target_is_independently_decoded(self) -> None:
        call_address = 0x100000000 + validator.BACKGROUND_MODULE_OFFSET + 0x1000
        expected = 0x100000000 + validator.RENDER_MODULE_OFFSET
        self.assertEqual(
            validator.decode_arm64_bl_target(bytes.fromhex("dfcfff97"), call_address),
            expected,
        )
        with self.assertRaisesRegex(ValueError, "not ARM64 BL"):
            validator.decode_arm64_bl_target(b"\x00\x00\x00\x00", call_address)

    def test_all_opened_loaded_field_predictions_are_bit_exact(self) -> None:
        raw = bytearray(384)
        shadow_offset = struct.pack("<dd", -3.0, 5.0)
        shadow = 13.5
        blur = 3.25
        inner = shadow * -0.8
        bleed = 11.25
        raw[0x008:0x018] = shadow_offset
        raw[0x018:0x020] = struct.pack("<d", shadow)
        raw[0x098:0x0A0] = struct.pack("<d", 2.0 * blur)
        raw[0x0E8:0x0F0] = struct.pack("<d", inner)
        raw[0x160:0x168] = struct.pack("<d", bleed)
        inputs = {
            "inputShadowOffset": {"hex": shadow_offset.hex()},
            "inputShadowAmount": shadow,
            "inputBlurRadius": blur,
            "inputInnerRefractionAmount": inner,
            "inputBleedAmount": bleed,
            "inputBleedHeight": bleed,
        }
        validator.validate_loaded_field_predictions(bytes(raw), inputs, 1)
        raw[0x098] ^= 1
        with self.assertRaisesRegex(ValueError, "blur field differs"):
            validator.validate_loaded_field_predictions(bytes(raw), inputs, 1)

    def test_gate_requires_one_match_then_two_for_repeated_endpoint(self) -> None:
        self.assertIn(
            "expected_full_count = 2 if sample_index == 32 else 1",
            SOURCE,
        )
        self.assertIn("partial == 0", SOURCE)
        self.assertIn('== "0000000000000000"', SOURCE)

    def test_every_event_is_partitioned_inside_its_render_interval(self) -> None:
        for value in (
            'f"provider call {index} escaped its render interval"',
            "sorted(referenced_events) == list(range(len(events)))",
            "len(events) == 2 * len(intervals) + 2 * len(calls)",
            'set(breakpoints) == {"bootstrap", *expected_breakpoint_addresses}',
        ):
            self.assertIn(value, SOURCE)

    def test_product_authority_stays_closed_after_narrow_pass(self) -> None:
        for field in (
            "constantAndCovaryingSemanticSourcesDisambiguated",
            "freshMaterialAppearanceGeometryProfileTransferEstablished",
            "generalPublicInputObjectConstructionLawEstablished",
            "upstreamCropAllocationPolicyEstablished",
            "physicalRetinaColorPixelCompositorTransferEstablished",
            "independentWalleZeroByteFrameParityEstablished",
            "liquidGlassParityEstablished",
            "productionShaderAuthorized",
        ):
            self.assertIn(f'"{field}": False', SOURCE)


if __name__ == "__main__":
    unittest.main()
