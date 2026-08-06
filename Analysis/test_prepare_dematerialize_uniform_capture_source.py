#!/usr/bin/env python3
"""Checks for the byte-frozen reverse-direction Swift source adapter."""

import hashlib
import unittest
from pathlib import Path

import prepare_dematerialize_uniform_capture_source as adapter


ANALYSIS_ROOT = Path(__file__).resolve().parent
SOURCE_PATH = ANALYSIS_ROOT.parent / "Sources" / "GlassIntrospect" / "main.swift"


class PrepareDematerializeUniformCaptureSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_bytes()
        cls.transformed = adapter.transform(cls.source)

    def test_input_and_output_hashes_are_frozen(self) -> None:
        self.assertEqual(hashlib.sha256(self.source).hexdigest(), adapter.SOURCE_SHA256)
        self.assertEqual(
            hashlib.sha256(self.transformed).hexdigest(), adapter.TRANSFORMED_SHA256
        )

    def test_only_the_materialize_only_guard_is_removed(self) -> None:
        self.assertEqual(self.source.count(adapter.MATERIALIZE_ONLY_GUARD), 1)
        self.assertNotIn(adapter.MATERIALIZE_ONLY_GUARD, self.transformed)
        self.assertEqual(
            self.transformed,
            self.source.replace(adapter.MATERIALIZE_ONLY_GUARD, b""),
        )
        self.assertEqual(
            len(self.source) - len(self.transformed),
            len(adapter.MATERIALIZE_ONLY_GUARD),
        )

    def test_filter_and_render_logic_are_not_rewritten(self) -> None:
        for marker in (
            b"transitionBackgroundUniformEvidence(",
            b"localTransitionCARendererEvidence(",
            b"copiedTransitionFilter(snapshot.filter)",
            b"transitionBackgroundFilterSnapshot(",
        ):
            self.assertEqual(self.source.count(marker), self.transformed.count(marker))


if __name__ == "__main__":
    unittest.main()
