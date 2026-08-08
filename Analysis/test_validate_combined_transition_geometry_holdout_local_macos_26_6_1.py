#!/usr/bin/env python3
"""Tests for the prospective combined transition-geometry holdout gate."""

import copy
import tempfile
import unittest
from pathlib import Path

import validate_combined_transition_geometry_holdout_local_macos_26_6_1 as gate


class PreregistrationTests(unittest.TestCase):
    @staticmethod
    def value() -> dict[str, object]:
        return {
            "combinedTransitionGeometryHoldoutPreregistrationSchemaVersion": 1,
            "authority": (
                "prospective output-blind combined transition geometry transfer"
            ),
            "appleOutputsObservedAtFreeze": False,
            "caseMatrix": list(copy.deepcopy(gate.EXPECTED_CASES)),
            "captureContract": {
                "host": "quince@10.0.41.19",
                "githubActionsPermitted": False,
                "debuggerPermitted": False,
                "metalCaptureEnvironmentPermitted": False,
                "nativeCaptureMayContainNixStorePath": False,
                "sourceBuiltProbeRequired": True,
                "declaredSDKVersion": "26.5",
                "dynamicUniformEvidenceMode": "allocation-metadata-v1",
                "denseStateCapture": True,
                "sampleCountPerTimeline": 33,
            },
            "acceptance": {
                "timelineCount": 8,
                "dynamicStateCount": 252,
                "requiredMismatchCountPerMetric": 0,
                "comparisonMode": (
                    "exact integer, binary32, binary64, and byte-stream equality"
                ),
                "requireAllCasesRegardlessOfEarlierOutcome": True,
                "requireOneCaptureCommitAndBinary": True,
                "requireDirectActiveRetinaSessionPerCase": True,
                "requireNoCapturedValueInPrediction": True,
                "productionShaderMutationPermitted": False,
            },
            "sealedOutputs": {
                "timelineSHA256": None,
                "streamSHA256": None,
                "metricMismatchCounts": None,
                "finalHighlightTopologies": None,
                "prospectiveGatePassed": None,
            },
            "sourceSHA256": {
                path: "0" * 64 for path in gate.EXPECTED_SOURCE_PATHS
            },
        }

    def test_matrix_is_complete_and_output_blind(self) -> None:
        value = self.value()
        gate.validate_preregistration_value(value)
        cases = gate.EXPECTED_CASES
        self.assertEqual(len(cases), 8)
        self.assertEqual(sum(int(case["records"]) for case in cases), 252)
        self.assertEqual(
            {
                (
                    str(case["material"]),
                    str(case["appearance"]),
                    str(case["direction"]),
                )
                for case in cases
            },
            {
                (material, appearance, direction)
                for material in ("clear", "regular")
                for appearance in ("light", "dark")
                for direction in ("materialize", "dematerialize")
            },
        )

    def test_geometry_mutation_fails_closed(self) -> None:
        value = self.value()
        cases = value["caseMatrix"]
        assert isinstance(cases, list)
        geometry = cases[0]["geometry"]
        assert isinstance(geometry, dict)
        geometry["centerX"] = 11.5
        with self.assertRaisesRegex(ValueError, "case matrix differs"):
            gate.validate_preregistration_value(value)

    def test_opened_output_field_fails_closed(self) -> None:
        value = self.value()
        outputs = value["sealedOutputs"]
        assert isinstance(outputs, dict)
        outputs["timelineSHA256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "sealed output fields differ"):
            gate.validate_preregistration_value(value)


class CaptureContextTests(unittest.TestCase):
    def test_nix_store_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture-context.txt"
            path.write_text(
                "CAPTURE_COMMIT=" + "0" * 40 + "\nPATH=/nix/store/example\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Nix store path"):
                gate.context_fields(path)


if __name__ == "__main__":
    unittest.main()
