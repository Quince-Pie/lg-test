#!/usr/bin/env python3
"""Tests for the constructor/public-render validator."""

from __future__ import annotations

import ast
import hashlib
import unittest
from pathlib import Path

import validate_background_filter_constructor_public_render_interval_local_macos_26_6_1 as validator


SOURCE_PATH = Path(validator.__file__).resolve()
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


class BackgroundFilterConstructorValidatorTests(unittest.TestCase):
    def test_framework_identity_correction_is_mandatory(self) -> None:
        self.assertIn("frameworkSymbolIdentityOperationalAmendment", SOURCE)
        self.assertIn("public.FRAMEWORK_IDENTITY_CORRECTION_PATH", SOURCE)
        self.assertIn("public.FRAMEWORK_IDENTITY_CORRECTION_SHA256", SOURCE)

    def test_source_remains_python_3_9_parseable(self) -> None:
        ast.parse(SOURCE, feature_version=(3, 9))

    def test_snapshot_requires_exact_address_width_and_digest(self) -> None:
        payload = b"abc"
        snapshot = {
            "address": 0x1234,
            "byteCount": len(payload),
            "hex": payload.hex(),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        self.assertEqual(
            validator.validate_snapshot(snapshot, 0x1234, 3, "snapshot"),
            payload,
        )
        for key, value in (
            ("address", 0x1235),
            ("byteCount", 4),
            ("sha256", "0" * 64),
        ):
            changed = dict(snapshot)
            changed[key] = value
            with self.assertRaises(ValueError):
                validator.validate_snapshot(changed, 0x1234, 3, "snapshot")

    def test_register_record_requires_exact_raw_f64_width(self) -> None:
        record = {
            "name": "d12",
            "byteCount": 8,
            "hex": validator.F64_ONE_RAW_LITTLE_ENDIAN_HEX,
            "valueString": "1",
        }
        self.assertEqual(
            validator.validate_register_record(record, "d12", "unity").hex(),
            validator.F64_ONE_RAW_LITTLE_ENDIAN_HEX,
        )
        for key, value in (
            ("name", "d9"),
            ("byteCount", 16),
            ("hex", "00"),
            ("valueString", None),
        ):
            changed = dict(record)
            changed[key] = value
            with self.assertRaises(ValueError):
                validator.validate_register_record(changed, "d12", "unity")

    def test_public_projection_remaps_interleaved_constructor_events(self) -> None:
        configuration = {key: key for key in validator.PUBLIC_CONFIGURATION_KEYS}
        configuration["extension"] = True
        trace = {
            "configuration": configuration,
            "breakpoints": {
                "bootstrap": {},
                "renderCall": {},
                "renderReturn": {},
                "providerEntry": {},
                "providerReturn": {},
                "constructorEntry": {},
                "constructorReturn": {},
                "parametersBuilderEntry": {},
                "parametersBlendDecision": {},
                "parametersBlendFinal": {},
                "parametersBlendResolved": {},
                "parametersBuilderReturn": {},
            },
            "events": [
                {
                    "eventIndex": 0,
                    "kind": "parameters-builder-entry",
                    "recordIndex": 0,
                },
                {
                    "eventIndex": 1,
                    "kind": "parameters-blend-decision",
                    "recordIndex": 0,
                },
                {
                    "eventIndex": 2,
                    "kind": "parameters-blend-final",
                    "recordIndex": 0,
                },
                {
                    "eventIndex": 3,
                    "kind": "parameters-blend-resolved",
                    "recordIndex": 0,
                },
                {
                    "eventIndex": 4,
                    "kind": "parameters-builder-return",
                    "recordIndex": 0,
                },
                {"eventIndex": 5, "kind": "constructor-entry", "recordIndex": 0},
                {"eventIndex": 6, "kind": "constructor-return", "recordIndex": 0},
                {"eventIndex": 7, "kind": "render-call", "recordIndex": 0},
                {"eventIndex": 8, "kind": "provider-entry", "recordIndex": 0},
                {"eventIndex": 9, "kind": "provider-return", "recordIndex": 0},
                {"eventIndex": 10, "kind": "render-return", "recordIndex": 0},
            ],
            "intervals": [
                {
                    "entryEventIndex": 7,
                    "returnEventIndex": 10,
                    "preRenderConstructorCallIndices": [0],
                    "inRenderConstructorCallIndices": [],
                    "preRenderParametersBuilderCallIndices": [0],
                    "inRenderParametersBuilderCallIndices": [],
                }
            ],
            "calls": [
                {
                    "entryEventIndex": 8,
                    "returnEventIndex": 9,
                    "providerObjectComplete": {},
                    "returnObjectComplete": {},
                    "completeObjectChanged": False,
                }
            ],
            "finalEventCount": 11,
        }
        projected = validator.public_projection(trace)
        self.assertEqual(
            [event["kind"] for event in projected["events"]],
            ["render-call", "provider-entry", "provider-return", "render-return"],
        )
        self.assertEqual(projected["intervals"][0]["entryEventIndex"], 0)
        self.assertEqual(projected["intervals"][0]["returnEventIndex"], 3)
        self.assertEqual(projected["calls"][0]["entryEventIndex"], 1)
        self.assertEqual(projected["calls"][0]["returnEventIndex"], 2)
        self.assertEqual(projected["finalEventCount"], 4)
        self.assertNotIn("extension", projected["configuration"])
        self.assertNotIn("constructorEntry", projected["breakpoints"])
        self.assertNotIn(
            "preRenderParametersBuilderCallIndices", projected["intervals"][0]
        )

    def test_initialized_projection_excludes_only_constructor_unwritten_padding(
        self,
    ) -> None:
        payload = bytes(index & 0xFF for index in range(504))
        projected = validator.initialized_background_filter_bytes(payload)
        self.assertEqual(len(projected), 491)
        expected = b"".join(
            payload[start:end]
            for start, end in validator.BACKGROUND_FILTER_INITIALIZED_RANGES
        )
        self.assertEqual(projected, expected)
        excluded = {
            index
            for start, end in validator.BACKGROUND_FILTER_PADDING_RANGES
            for index in range(start, end)
        }
        self.assertEqual(len(excluded), 13)

    def test_validator_requires_exact_same_sample_output_join(self) -> None:
        for needle in (
            "has no same-sample initialized constructor output",
            "has ambiguous Parameters values",
            'call.get("layerIndex") == 0',
            "Parameters changed",
            "complete event partition differs",
            "has no same-sample Parameters builder output",
            "resolved working/output bytes differ",
        ):
            self.assertIn(needle, SOURCE)

    def test_validator_authenticates_blend_boundary_and_unity_fast_path(self) -> None:
        for needle in (
            "RESOLVED_RECIPE_BUILDER_MODULE_OFFSET = 0x120B4C",
            "RESOLVED_RECIPE_BUILDER_CALLER_MODULE_OFFSET = 0x11F1BC",
            "BLEND_DECISION_OFFSET_IN_BUILDER = 0xFB8",
            "BLEND_FINAL_GATE_OFFSET_IN_BUILDER = 0x1174",
            "BLEND_RESOLVED_OFFSET_IN_BUILDER = 0x118C",
            'F64_ONE_RAW_LITTLE_ENDIAN_HEX = "000000000000f03f"',
            'decision.get("factorD9")',
            'decision.get("unityD12")',
            "direct-copy collection count differs",
            "direct-copy factor differs",
            "direct-copy source bytes differ",
            "direct-copy convergence bytes differ",
        ):
            self.assertIn(needle, SOURCE)

    def test_result_does_not_overclaim_from_same_profile_blend_join(self) -> None:
        self.assertIn(
            '"sameProfilePublicParametersBlendProvenanceEstablished": True',
            SOURCE,
        )

    def test_authority_remains_fail_closed_beyond_this_gate(self) -> None:
        for claim in (
            '"freshMaterialAppearanceGeometryProfileTransferEstablished": False',
            '"generalPublicInputConstructionLawEstablished": False',
            '"physicalRetinaColorPixelCompositorTransferEstablished": False',
            '"independentWalleZeroByteFrameParityEstablished": False',
            '"liquidGlassParityEstablished": False',
            '"productionShaderAuthorized": False',
        ):
            self.assertIn(claim, SOURCE)


if __name__ == "__main__":
    unittest.main()
