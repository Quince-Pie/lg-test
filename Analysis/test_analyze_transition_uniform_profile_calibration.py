#!/usr/bin/env python3
"""Tests for the exact four-profile transition-uniform model."""

import json
import tempfile
import unittest
from pathlib import Path

import analyze_transition_uniform_profile_calibration as model


class TransitionUniformProfileModelTests(unittest.TestCase):
    def test_complete_numeric_inventory_is_partitioned_once(self) -> None:
        self.assertEqual(len(model.NUMERIC_FIELDS), 47)
        self.assertEqual(len(set(model.NUMERIC_FIELDS)), 47)
        self.assertEqual(len(model.PREDICTED_PYTHON_FIELDS), 46)
        self.assertNotIn(model.CLAMP_FIELD, model.PREDICTED_PYTHON_FIELDS)
        self.assertEqual(
            set(model.NUMERIC_FIELDS),
            set(model.PREDICTED_PYTHON_FIELDS) | {model.CLAMP_FIELD},
        )

    def test_clear_light_nontrivial_state_matches_frozen_words(self) -> None:
        fraction = model.float32(0.032377243041992188)
        predicted = model.predict_numeric_fields(
            material="clear",
            appearance="light",
            diameter=451,
            fraction=fraction,
        )
        expected = {
            "inputBlurDistance0": "c0f1a787",
            "inputBlurOpacity1": "3bde7e19",
            "inputOuterRefractionAmount": "404152d2",
            "inputRefractionDistance1": "bc849e00",
            "inputSDRGradientDistance0": "bd049e00",
            "inputSDRGradientDistance1": "bc849e00",
            "inputMaxHeadroom": "43a2735a",
        }
        self.assertEqual(model.float32_bits(fraction), "3d049e00")
        self.assertEqual(
            {field: model.float32_bits(predicted[field]) for field in expected},
            expected,
        )

    def test_regular_dark_endpoint_keeps_profile_specific_words(self) -> None:
        predicted = model.predict_numeric_fields(
            material="regular",
            appearance="dark",
            diameter=475,
            fraction=1.0,
        )
        expected = {
            "inputBleedAmount": "43264000",
            "inputBlurDistance4": "42be0000",
            "inputBleedOpacity": "3f4ccccd",
            "inputFaceColorMatrixWhite": "3f19999a",
            "inputShadowHeight": "433e0000",
        }
        self.assertEqual(
            {field: model.float32_bits(predicted[field]) for field in expected},
            expected,
        )

    def test_scalar_mix_rounds_each_operation_separately(self) -> None:
        fraction = model.float32(0.032377243041992188)
        self.assertEqual(
            model.float32_bits(model.float32_mix(0.2, 0.5, fraction)),
            "3e56bf0d",
        )
        self.assertEqual(
            model.float32_bits(
                model.float32_multiply(fraction, model.float32_mix(0.2, 0.5, fraction))
            ),
            "3bde7e19",
        )

    def test_unknown_profile_and_invalid_diameter_fail_closed(self) -> None:
        with self.assertRaisesRegex(model.AnalysisError, "unsupported profile"):
            model.predict_numeric_fields(
                material="clear",
                appearance="unknown",
                diameter=451,
                fraction=0.5,
            )
        with self.assertRaisesRegex(model.AnalysisError, "must be positive"):
            model.predict_numeric_fields(
                material="clear",
                appearance="light",
                diameter=0,
                fraction=0.5,
            )

    def test_native_clamp_contract_rejects_nonexact_result(self) -> None:
        result = {
            "transitionUniformProfileClampAnalysisSchemaVersion": 1,
            "classification": "native Darwin.powf four-profile opened calibration",
            "allCandidateWordsExact": True,
        }
        result["allCandidateWordsExact"] = False
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "clamp.json"
            path.write_text(json.dumps(result), encoding="utf-8")
            with self.assertRaisesRegex(model.AnalysisError, "contract differs"):
                model.load_native_clamp_result(path)


if __name__ == "__main__":
    unittest.main()
