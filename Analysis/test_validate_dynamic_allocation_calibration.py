#!/usr/bin/env python3
"""Tests for dense dynamic-allocation calibration metadata."""

import unittest

import validate_dynamic_allocation_calibration as calibration


class CalibrationContractTests(unittest.TestCase):
    def test_every_nonzero_timeline_sample_is_requested(self) -> None:
        self.assertEqual(calibration.EXPECTED_SAMPLE_INDICES, tuple(range(1, 33)))

    def test_calibration_is_not_classified_as_a_holdout(self) -> None:
        self.assertIn("post-opening", calibration.CLASSIFICATION)
        self.assertNotIn("unseen", calibration.CLASSIFICATION)


if __name__ == "__main__":
    unittest.main()
