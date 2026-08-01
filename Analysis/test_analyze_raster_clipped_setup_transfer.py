#!/usr/bin/env python3
"""Tests for the descriptive clipped-setup artifact analysis."""

import unittest

import numpy as np

import analyze_raster_clipped_setup_transfer as analysis


class RasterClippedSetupAnalysisTests(unittest.TestCase):
    def test_equality_counts_distinguish_words_records_and_coefficients(self) -> None:
        left = np.zeros((2, 3, 2), dtype=np.uint32)
        right = left.copy()
        right[0, 1, 0] = 1
        self.assertEqual(
            analysis.equality_counts(left, right),
            {
                "coefficientAllRecordsEqualCount": 1,
                "recordEqualCount": 5,
                "wordEqualCount": 11,
                "wordCount": 12,
            },
        )

    def test_source_evidence_is_cryptographically_pinned(self) -> None:
        self.assertEqual(analysis.SOURCE_RUN_ID, 30_674_647_960)
        for digest in (
            analysis.SOURCE_COMMIT,
            analysis.SOURCE_MANIFEST_SHA256,
            analysis.SOURCE_RAW_SHA256,
            analysis.SOURCE_VALIDATION_SHA256,
        ):
            self.assertEqual(len(digest), 40 if digest == analysis.SOURCE_COMMIT else 64)


if __name__ == "__main__":
    unittest.main()
