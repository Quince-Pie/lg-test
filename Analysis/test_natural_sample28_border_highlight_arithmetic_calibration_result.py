#!/usr/bin/env python3
"""Contracts for the exact sample-28 arithmetic calibration."""

import base64
import hashlib
import json
from pathlib import Path
import re
import struct
import unittest


ANALYSIS = Path(__file__).resolve().parent
RESULT_PATH = ANALYSIS / (
    "natural_sample28_border_highlight_arithmetic_calibration_result.json"
)
PREREGISTRATION_PATH = ANALYSIS / (
    "natural_sample28_border_highlight_arithmetic_preregistration.json"
)
MAIN_SWIFT_PATH = ANALYSIS.parent / "Sources/GlassIntrospect/main.swift"


class Sample28BorderHighlightArithmeticCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
        cls.preregistration = json.loads(
            PREREGISTRATION_PATH.read_text(encoding="utf-8")
        )

    def test_result_is_the_record_frozen_by_the_preregistration(self) -> None:
        expected = self.preregistration["frozenCalibrationEvidence"][
            "analysisResult"
        ]["sha256"]
        actual = hashlib.sha256(RESULT_PATH.read_bytes()).hexdigest()
        self.assertEqual(actual, expected)

    def test_wrong_pass_uniform_reproduces_the_historical_residual(self) -> None:
        ownership = self.result["passUniformOwnership"]
        self.assertEqual(
            ownership["backgroundHalfSizeBits"],
            ["0x43770167", "0x43770167"],
        )
        self.assertEqual(
            ownership["finalHighlightHalfSizeBits"],
            ["0x43770168", "0x43770168"],
        )
        self.assertEqual(ownership["ulpDelta"], [1, 1])
        control = ownership["wrongPassUniformPositiveControl"]
        self.assertEqual(control["mismatchedHalfWords"], 148)
        self.assertEqual(control["maximumHalfBitDistance"], 24)
        self.assertEqual(control["appleActivePixels"], 2_520)
        self.assertEqual(control["candidateActivePixels"], 2_520)

    def test_prior_radial_order_is_a_nonvacuous_negative_control(self) -> None:
        baseline = self.result["baseline"]
        self.assertEqual(baseline["firstDivergentStage"], "radial-input-y")
        self.assertEqual(baseline["mismatchedStageWords"], 633_382)
        self.assertEqual(baseline["tomographyMismatchedHalfWords"], 47)
        self.assertEqual(baseline["tomographyExactCaseCount"], 3)

    def test_recovered_rule_is_exact_at_every_calibration_boundary(self) -> None:
        candidate = self.result["candidate"]
        self.assertEqual(candidate["stageCaseCount"], 40)
        self.assertEqual(candidate["checkedStageWords"], 41_943_040)
        self.assertEqual(candidate["mismatchedStageWords"], 0)
        self.assertEqual(candidate["checkedSdfWords"], 786_432)
        self.assertEqual(candidate["mismatchedSdfWords"], 0)
        self.assertEqual(candidate["checkedNaturalAlphaHalfWords"], 1_048_576)
        self.assertEqual(candidate["mismatchedNaturalAlphaHalfWords"], 0)
        self.assertEqual(candidate["tomographyCaseCount"], 10)
        self.assertEqual(candidate["tomographyCheckedHalfWords"], 10_485_760)
        self.assertEqual(candidate["tomographyMismatchedHalfWords"], 0)
        self.assertEqual(candidate["totalCheckedWords"], 54_263_808)
        self.assertEqual(candidate["totalMismatchedWords"], 0)
        self.assertEqual(candidate["maximumBitDistance"], 0)

    def test_calibration_does_not_claim_prospective_or_product_parity(self) -> None:
        gate = self.result["gate"]
        self.assertTrue(gate["calibrationExact"])
        self.assertTrue(gate["positiveControlsPassed"])
        self.assertTrue(gate["prospectiveUnseenRetinaHoldoutRequired"])
        self.assertTrue(gate["eightStateAmdFrameGateRequired"])
        self.assertFalse(gate["productionWalleParityEstablished"])
        self.assertFalse(gate["productionShaderModified"])
        self.assertFalse(gate["shaderQualityReductionAllowed"])

    def test_prospective_sdf_inputs_are_frozen_and_source_authenticated(self) -> None:
        source = MAIN_SWIFT_PATH.read_text(encoding="utf-8")
        preregistration_sha256 = hashlib.sha256(
            PREREGISTRATION_PATH.read_bytes()
        ).hexdigest()
        self.assertIn(preregistration_sha256, source)
        match = re.search(
            r'naturalSample28BorderUniformPrefixBase64 = """\n(.*?)\n"""',
            source,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        base = base64.b64decode(match.group(1))
        self.assertEqual(len(base), 248)
        holdout = self.preregistration["prospectiveHoldout"]
        self.assertEqual(
            hashlib.sha256(base).hexdigest(),
            holdout["baseUniformPrefixSha256"],
        )
        cases = holdout["sdfInputInterventions"]
        self.assertEqual(len(cases), 4)
        self.assertEqual(
            {case["name"] for case in cases},
            {"wide-coarse", "tall-coarse", "wide-ulp", "tall-ulp"},
        )
        alpha_oracle_words = [0] * 15 + [0x3C00] * 4 + [0] * 5
        for case in cases:
            natural = bytearray(base)
            for edit in case["edits"]:
                payload = bytes.fromhex(edit["hex"])
                self.assertEqual(
                    struct.unpack("<I", payload)[0],
                    int(edit["float32Bits"], 16),
                )
                offset = edit["recordOffset"]
                natural[offset : offset + len(payload)] = payload
            self.assertEqual(
                hashlib.sha256(natural).hexdigest(),
                case["naturalUniformPrefixSha256"],
            )
            alpha_oracle = bytearray(natural)
            alpha_oracle[0x60:0x90] = struct.pack(
                "<24H", *alpha_oracle_words
            )
            self.assertEqual(
                hashlib.sha256(alpha_oracle).hexdigest(),
                case["alphaOracleUniformPrefixSha256"],
            )
            self.assertEqual(
                hashlib.sha256(alpha_oracle[:48]).hexdigest(),
                case["sdfRecordSha256"],
            )


if __name__ == "__main__":
    unittest.main()
