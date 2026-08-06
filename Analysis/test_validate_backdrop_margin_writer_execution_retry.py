"""Tests for the output-blind Objective-C ABI correction."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import test_validate_backdrop_margin_writer_execution as fixture
import validate_backdrop_margin_writer_execution as frozen
import validate_backdrop_margin_writer_execution_retry as retry


class BackdropMarginWriterExecutionRetryValidatorTests(unittest.TestCase):
    def paths(self, root: Path) -> tuple[Path, Path, Path]:
        trace = fixture.trace()
        copy_entry = trace["events"][1]
        copy_store = trace["events"][2]
        assert isinstance(copy_entry, dict)
        assert isinstance(copy_store, dict)
        opaque_argument = 0x500000000
        copy_entry["renderArgument"] = opaque_argument
        copy_store["entryRenderArgument"] = opaque_argument
        copy_store["entryRenderArgumentMatched"] = False
        values = (
            (root / "trace.json", trace),
            (root / "timeline.json", fixture.timeline()),
            (root / "preregistration.json", fixture.preregistration()),
        )
        for path, value in values:
            path.write_text(json.dumps(value), encoding="utf-8")
        return values[0][0], values[1][0], values[2][0]

    def test_frozen_accidental_x2_assertion_rejects_the_real_abi(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.paths(Path(directory))
            with self.assertRaisesRegex(ValueError, "copy entry/store"):
                frozen.validate(
                    *paths,
                    "regular",
                    "light",
                    "materialize",
                    "circle-347-center",
                )

    def test_retry_keeps_model_and_render_joins_without_x2_assumption(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.paths(Path(directory))
            result = retry.validate(
                *paths,
                "regular",
                "light",
                "materialize",
                "circle-347-center",
            )
        self.assertEqual(result["conclusion"], "success")
        self.assertEqual(
            result["backdropMarginWriterExecutionRetryValidationSchemaVersion"], 1
        )
        discovery = result["writerExecution"]["opaqueEntryArgumentDiscovery"]
        self.assertFalse(discovery["isRenderObject"])
        self.assertEqual(
            discovery["copyStoreEventCountValidatedWithoutX2RenderAssumption"], 1
        )
        self.assertFalse(discovery["capturedValueUsedForCorrection"])
        self.assertTrue(result["sealedConclusion"]["opaqueCopyArgumentABIResolved"])

    def test_retry_still_rejects_a_model_pointer_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.paths(root)
            trace = json.loads(paths[0].read_text(encoding="utf-8"))
            trace["events"][2]["entryModelMatched"] = False
            paths[0].write_text(json.dumps(trace), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "model entry/store"):
                retry.validate(
                    *paths,
                    "regular",
                    "light",
                    "materialize",
                    "circle-347-center",
                )


if __name__ == "__main__":
    unittest.main()
