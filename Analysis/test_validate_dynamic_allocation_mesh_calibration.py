#!/usr/bin/env python3
"""Tests for producer-mesh center-phase calibration metadata."""

import unittest

import validate_dynamic_allocation_mesh_calibration as calibration


class MeshCalibrationContractTests(unittest.TestCase):
    def test_every_nonzero_timeline_sample_is_requested(self) -> None:
        self.assertEqual(calibration.EXPECTED_SAMPLE_INDICES, tuple(range(1, 33)))

    def test_same_diameter_center_phases_are_frozen(self) -> None:
        self.assertEqual(
            calibration.EXPECTED_GEOMETRIES,
            {
                "circle-640-center",
                "circle-640-integer",
                "circle-640-phase-0500-even",
                "circle-640-phase-0500-signed",
            },
        )

    def test_calibration_is_not_classified_as_a_holdout(self) -> None:
        self.assertIn("post-opening", calibration.CLASSIFICATION)
        self.assertNotIn("unseen", calibration.CLASSIFICATION)


if __name__ == "__main__":
    unittest.main()
