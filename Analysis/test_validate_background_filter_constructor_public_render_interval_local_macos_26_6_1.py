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

    def test_public_projection_remaps_interleaved_constructor_events(self) -> None:
        configuration = {
            key: key for key in validator.PUBLIC_CONFIGURATION_KEYS
        }
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
            },
            "events": [
                {"eventIndex": 0, "kind": "constructor-entry", "recordIndex": 0},
                {"eventIndex": 1, "kind": "constructor-return", "recordIndex": 0},
                {"eventIndex": 2, "kind": "render-call", "recordIndex": 0},
                {"eventIndex": 3, "kind": "provider-entry", "recordIndex": 0},
                {"eventIndex": 4, "kind": "provider-return", "recordIndex": 0},
                {"eventIndex": 5, "kind": "render-return", "recordIndex": 0},
            ],
            "intervals": [
                {
                    "entryEventIndex": 2,
                    "returnEventIndex": 5,
                    "preRenderConstructorCallIndices": [0],
                    "inRenderConstructorCallIndices": [],
                }
            ],
            "calls": [
                {
                    "entryEventIndex": 3,
                    "returnEventIndex": 4,
                    "providerObjectComplete": {},
                    "returnObjectComplete": {},
                    "completeObjectChanged": False,
                }
            ],
            "finalEventCount": 6,
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

    def test_validator_requires_exact_same_sample_output_join(self) -> None:
        for needle in (
            "has no same-sample constructor output",
            "has ambiguous Parameters values",
            'call.get("layerIndex") == 0',
            "Parameters changed",
            "complete event partition differs",
        ):
            self.assertIn(needle, SOURCE)

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
