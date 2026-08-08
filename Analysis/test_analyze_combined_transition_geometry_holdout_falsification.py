#!/usr/bin/env python3
"""Tests for the immutable combined-geometry falsification record."""

import json
from pathlib import Path
import unittest

import analyze_combined_transition_geometry_holdout_falsification as analysis


RESULT = Path(__file__).with_name(
    "combined_transition_geometry_holdout_7432ffa_falsification_result.json"
)


class CombinedTransitionGeometryFalsificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_retina_center_snap_preserves_measured_quarter_phases(self) -> None:
        expected = {
            11.25: 11.5,
            151.5: 151.5,
            211.75: 212.0,
            243.125: 243.0,
            689.625: 689.5,
            772.75: 773.0,
            850.875: 851.0,
            1002.75: 1003.0,
        }
        self.assertEqual(
            {value: analysis.retina_snap(value) for value in expected}, expected
        )

    def test_live_carrier_is_local_but_endpoint_carrier_is_placed(self) -> None:
        geometry = {
            "name": "unit-test",
            "shape": "circle",
            "width": 541,
            "height": 541,
            "centerX": 772.75,
            "centerY": 296.5,
            "windowWidth": 1024,
            "windowHeight": 1024,
            "extendsBeyondWindow": False,
        }
        live = analysis.retrospective_layer_candidate(geometry, 0.25)
        self.assertEqual(live["carrierPosition"], (444.375, 444.375))
        endpoint = analysis.retrospective_layer_candidate(geometry, 1.0)
        self.assertEqual(endpoint["carrierPosition"], (502.5, 26.0))

    def test_red_gate_and_residuals_cannot_be_relabelled(self) -> None:
        self.assertEqual(self.result["status"], "prospectively-falsified")
        self.assertFalse(self.result["prospectiveGatePassed"])
        self.assertFalse(
            self.result["retrospectiveCalibrationHasProspectiveAuthority"]
        )
        self.assertEqual(
            self.result["firstFrozenFailure"], analysis.FROZEN_FAILURE
        )
        metrics = self.result["metrics"]
        self.assertEqual(
            metrics["dynamicElementBoundsCandidate"]["mismatchedComponents"], 78
        )
        self.assertEqual(
            metrics["dynamicElementPositionCandidate"]["mismatchedComponents"],
            76,
        )
        self.assertFalse(metrics["dynamicElementBoundsCandidate"]["exact"])
        self.assertFalse(metrics["dynamicElementPositionCandidate"]["exact"])

    def test_opened_policy_is_exact_without_overclaiming_branches(self) -> None:
        metrics = self.result["metrics"]
        exact_names = {
            "backdropScale",
            "dynamicCarrierBounds",
            "dynamicCarrierPosition",
            "producerActiveExtent",
            "producerCropOrigin",
            "producerStorageExtent",
            "selectedRegionOrigin",
            "selectedRegionAllocation",
            "copyBaseOriginComposition",
            "destinationMipCount",
        }
        self.assertTrue(all(metrics[name]["exact"] for name in exact_names))
        branches = self.result["pipelineBranchInventory"]
        self.assertEqual(
            sum(branches[name] for name in (
                "current-clear-background",
                "current-regular-background",
                "small-clear-background",
                "clear-without-primary-Tgh-draw",
            )),
            252,
        )
        self.assertEqual(
            branches["current-final-highlight"]
            + branches["small-clear-final-highlight"],
            252,
        )
        self.assertFalse(self.result["productionParityAuthorized"])
        self.assertFalse(self.result["productionShaderChanged"])

    def test_result_pins_every_timeline(self) -> None:
        pinned = {
            case["caseId"]: case["timelineSHA256"]
            for case in self.result["cases"]
        }
        self.assertEqual(pinned, analysis.TIMELINE_SHA256)
        self.assertEqual(self.result["stateCount"], 252)


if __name__ == "__main__":
    unittest.main()
