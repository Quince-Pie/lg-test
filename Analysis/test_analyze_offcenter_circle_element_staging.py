#!/usr/bin/env python3
"""Tests for exact off-center circle element staging."""

import json
from pathlib import Path
import unittest

import analyze_offcenter_circle_element_staging as analysis
import analyze_transition_geometry_corpus_local_macos_26_6_1 as model


RESULT = Path(__file__).with_name("offcenter_circle_element_staging_result.json")


class OffcenterCircleElementStagingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_circle_fit_recomputes_extents_after_translation(self) -> None:
        rectangle = (-435.5, 172.5, 332.9999999999999, 333.0)
        observed = analysis.transformed_circle_rectangle(rectangle)
        self.assertEqual(
            tuple(model.float64_bits(value) for value in observed),
            (
                model.float64_bits(-435.5),
                model.float64_bits(172.50000000000006),
                model.float64_bits(332.9999999999999),
                model.float64_bits(332.9999999999999),
            ),
        )
        self.assertNotEqual(observed, rectangle)

    def test_regular_dark_half_ulp_discriminator_is_exact(self) -> None:
        geometry = {
            "name": "circle-combined-holdout-04",
            "shape": "circle",
            "width": 317,
            "height": 317,
            "centerX": 243.125,
            "centerY": 850.875,
            "windowWidth": 1024,
            "windowHeight": 1024,
            "extendsBeyondWindow": False,
        }
        predicted = analysis.expected_element(geometry, 0.28288745880126953)
        expected = (
            -388.23690032958984,
            219.76309967041018,
            328.47380065917963,
            328.4738006591797,
        )
        self.assertEqual(
            tuple(model.float64_bits(value) for value in predicted),
            tuple(model.float64_bits(value) for value in expected),
        )

    def test_result_closes_every_component_without_overclaiming(self) -> None:
        self.assertEqual(self.result["status"], "exact-retrospective-closure")
        self.assertEqual(self.result["stateCount"], 252)
        self.assertEqual(self.result["liveStateCount"], 248)
        self.assertEqual(self.result["endpointStateCount"], 4)
        metrics = self.result["metrics"]
        self.assertEqual(metrics["elementBinary64"]["componentCount"], 1008)
        self.assertEqual(metrics["liveElementBinary64"]["componentCount"], 992)
        self.assertTrue(all(item["exact"] for item in metrics.values()))
        self.assertFalse(self.result["productionParityAuthorized"])
        self.assertFalse(self.result["productionShaderChanged"])
        self.assertEqual(len(self.result["remainingAlgorithmBoundaries"]), 2)

    def test_all_observed_background_families_are_exact(self) -> None:
        families = self.result["familyMetrics"]
        self.assertEqual(
            {name: item["stateCount"] for name, item in families.items()},
            {
                "clear-without-primary": 29,
                "current-clear": 37,
                "current-regular": 126,
                "small-clear": 60,
            },
        )
        self.assertTrue(all(item["exact"] for item in families.values()))

    def test_result_pins_all_opened_timelines(self) -> None:
        self.assertEqual(
            {case["caseId"]: case["timelineSHA256"] for case in self.result["cases"]},
            analysis.opened.TIMELINE_SHA256,
        )
        self.assertTrue(all(case["exact"] for case in self.result["cases"]))


if __name__ == "__main__":
    unittest.main()
