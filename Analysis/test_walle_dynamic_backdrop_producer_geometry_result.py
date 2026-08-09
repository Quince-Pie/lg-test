#!/usr/bin/env python3
"""Integrity checks for the exact dynamic producer-geometry result."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent.parent
ANALYZER = ROOT / "Analysis/analyze_walle_dynamic_backdrop_producer_geometry.py"
RESULT = ROOT / "Analysis/walle_dynamic_backdrop_producer_geometry_result.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DynamicBackdropProducerGeometryResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_frozen_files_are_exact(self) -> None:
        self.assertEqual(
            sha256_file(ANALYZER),
            "f2527065b60f57a4c57df184e5ffe7eb1ee0ff2c0d2edb0d51ddeb85d04e2edc",
        )
        self.assertEqual(
            sha256_file(RESULT),
            "b3b48d6abaf09804d22e6e267dcf636701ddafd22f35dc6f3c46490f514cfe62",
        )

    def test_all_geometry_metrics_are_zero_tolerance(self) -> None:
        self.assertTrue(self.result["exact"])
        self.assertEqual(self.result["model"]["tolerance"], 0)
        for name, metric in self.result["metrics"].items():
            with self.subTest(name=name):
                self.assertTrue(metric["exact"])
                self.assertEqual(metric["mismatchCount"], 0)

    def test_both_producer_branches_are_covered_twice(self) -> None:
        expected = {"TimgA2Xhfc_Isrc": 5, "downsample_4_frag_lph": 3}
        self.assertEqual(
            self.result["producerFragmentInventory"],
            {"natural": expected, "controlled": expected},
        )

    def test_result_does_not_overclaim_production_parity(self) -> None:
        self.assertFalse(self.result["productionParityEstablished"])


if __name__ == "__main__":
    unittest.main()
