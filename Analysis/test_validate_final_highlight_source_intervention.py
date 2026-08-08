#!/usr/bin/env python3
"""Tests for the current-highlight source pixel-influence gate."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

import validate_final_highlight_source_intervention as gate


RESULT = Path(__file__).with_name(
    "final_highlight_source_intervention_local_macos_26_6_1_result.json"
)
PREREGISTRATION = Path(__file__).with_name(
    "final_highlight_source_intervention_preregistration.json"
)


class FinalHighlightSourceInterventionTests(unittest.TestCase):
    def test_frozen_preregistration_is_still_valid(self) -> None:
        value = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
        gate.validate_preregistration_value(value)

    def test_acceptance_mutation_fails_closed(self) -> None:
        value = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
        mutated = copy.deepcopy(value)
        mutated["acceptance"]["tolerance"] = 1
        with self.assertRaisesRegex(ValueError, "frozen acceptance differs"):
            gate.validate_preregistration_value(mutated)

    def test_replacement_stream_mutation_fails_closed(self) -> None:
        value = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
        mutated = copy.deepcopy(value)
        mutated["interventions"][1]["littleEndianHex"] = "00" * 32
        with self.assertRaisesRegex(ValueError, "intervention streams differ"):
            gate.validate_preregistration_value(mutated)

    def test_comparison_requires_literal_zero_difference(self) -> None:
        exact = {
            "byteCount": gate.RAW_BYTE_COUNT,
            "compared": True,
            "exactByteMatch": True,
            "firstMismatchedByte": -1,
            "matchingPixelFraction": 1,
            "maximumChannelDelta": 0,
            "meanAbsoluteChannelDelta": 0,
            "mismatchedByteCount": 0,
            "mismatchedPixelCount": 0,
            "rootMeanSquareChannelDelta": 0,
        }
        gate.validate_comparison(exact)
        mutated = dict(exact)
        mutated["mismatchedByteCount"] = 1
        with self.assertRaisesRegex(ValueError, "comparison differs"):
            gate.validate_comparison(mutated)

    def test_macho_parser_rejects_non_macho_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "probe"
            path.write_bytes(b"not a Mach-O binary" + b"\0" * 64)
            with self.assertRaisesRegex(ValueError, "not little-endian Mach-O"):
                gate.macho_build_version(path)

    def test_result_closes_only_pixel_influence_boundary(self) -> None:
        result = json.loads(RESULT.read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "exact-pixel-noninfluence")
        self.assertEqual(result["selection"]["selectedSampleIndex"], 1)
        self.assertEqual(result["selection"]["candidateSampleCount"], 31)
        self.assertEqual(result["selection"]["eligibleSampleCount"], 27)
        self.assertEqual(result["selection"]["ineligibleSampleCount"], 4)
        self.assertEqual(result["totalComparedBytes"], 8_388_608)
        self.assertEqual(result["totalUnequalBytes"], 0)
        self.assertEqual(result["totalUnequalPixels"], 0)
        self.assertEqual(result["maximumChannelDelta"], 0)
        self.assertEqual(len(result["remainingAppleAlgorithmBoundaries"]), 1)
        self.assertFalse(result["productionParityAuthorized"])
        self.assertFalse(result["productionShaderChanged"])


if __name__ == "__main__":
    unittest.main()
