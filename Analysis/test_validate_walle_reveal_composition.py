#!/usr/bin/env python3

from __future__ import annotations

import unittest

import numpy as np

from validate_walle_reveal_composition import compare_frame, reveal_mask


class RevealCompositionTests(unittest.TestCase):
    def test_pixel_center_circle_selects_sources_exactly(self) -> None:
        outgoing = np.zeros((5, 7, 4), dtype=np.uint8)
        incoming = np.full((5, 7, 4), 211, dtype=np.uint8)
        mask = reveal_mask(7, 5, 3.5, 2.5, 2.0)
        actual = np.where(mask[:, :, None], incoming, outgoing)
        result = compare_frame(actual, outgoing, incoming, mask)
        self.assertEqual(result["mismatchedBytes"], 0)
        self.assertEqual(result["mismatchedPixels"], 0)
        self.assertEqual(result["neitherSourcePixels"], 0)

    def test_one_wrong_source_pixel_is_rejected(self) -> None:
        outgoing = np.zeros((3, 3, 4), dtype=np.uint8)
        incoming = np.full((3, 3, 4), 255, dtype=np.uint8)
        mask = reveal_mask(3, 3, 1.5, 1.5, 0.75)
        actual = np.where(mask[:, :, None], incoming, outgoing)
        actual[0, 0] = incoming[0, 0]
        result = compare_frame(actual, outgoing, incoming, mask)
        self.assertEqual(result["mismatchedBytes"], 4)
        self.assertEqual(result["mismatchedPixels"], 1)
        self.assertEqual(result["neitherSourcePixels"], 0)

    def test_blended_boundary_pixel_is_not_a_source(self) -> None:
        outgoing = np.zeros((3, 3, 4), dtype=np.uint8)
        incoming = np.full((3, 3, 4), 200, dtype=np.uint8)
        mask = reveal_mask(3, 3, 1.5, 1.5, 0.75)
        actual = np.where(mask[:, :, None], incoming, outgoing)
        actual[0, 0] = 100
        result = compare_frame(actual, outgoing, incoming, mask)
        self.assertEqual(result["mismatchedPixels"], 1)
        self.assertEqual(result["neitherSourcePixels"], 1)


if __name__ == "__main__":
    unittest.main()
