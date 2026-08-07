#!/usr/bin/env python3
"""Regression checks for the frozen Material.Context metadata result."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_DIRECTORY = Path(__file__).resolve().parent
SOURCE = (
    ANALYSIS_DIRECTORY
    / "analyze_swiftuicore_material_context_metadata_local_macos_26_6_1.py"
)
RESULT = (
    ANALYSIS_DIRECTORY
    / "swiftuicore_material_context_metadata_local_macos_26_6_1_result.json"
)
EXPECTED_SOURCE_SHA256 = (
    "c5283cac21b80e4639fbea74710f141ca7966283887e4ee8df931ef7c63d1560"
)


class MaterialContextMetadataResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_source_identity_is_embedded(self) -> None:
        observed = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
        self.assertEqual(observed, EXPECTED_SOURCE_SHA256)
        self.assertEqual(self.result["tool"]["sourceSHA256"], EXPECTED_SOURCE_SHA256)

    def test_exact_material_context_layout(self) -> None:
        context = self.result["materialContext"]
        self.assertEqual(
            [field["name"] for field in context["fields"]],
            [
                "environment",
                "role",
                "substrate",
                "shapeDimensions",
                "shapeMetrics",
            ],
        )
        self.assertEqual(context["metadata"]["fieldOffsets"], [0, 16, 17, 24, 48])
        self.assertEqual(context["metadata"]["size"], 73)
        self.assertEqual(context["metadata"]["stride"], 80)

    def test_exact_shape_metrics_layout(self) -> None:
        metrics = self.result["shapeMetrics"]
        self.assertEqual(
            [field["name"] for field in metrics["fields"]],
            [
                "minimumDistance",
                "minimumDistanceOfLargestArea",
                "maximumDistance",
            ],
        )
        self.assertEqual(metrics["metadata"]["fieldOffsets"], [0, 8, 16])
        self.assertEqual(metrics["metadata"]["size"], 24)
        self.assertEqual(metrics["metadata"]["stride"], 24)

    def test_authority_remains_fail_closed(self) -> None:
        claims = self.result["claims"]
        self.assertTrue(claims["materialContextLayoutEstablished"])
        self.assertTrue(claims["shapeMetricsLayoutEstablished"])
        self.assertFalse(claims["liveContextValueProductionEstablished"])
        self.assertFalse(claims["contextToParametersValueLawEstablished"])
        self.assertFalse(claims["independentWalleZeroByteFrameParityEstablished"])
        self.assertFalse(claims["liquidGlassParityEstablished"])
        self.assertFalse(claims["productionShaderChangeAuthorized"])


if __name__ == "__main__":
    unittest.main()
