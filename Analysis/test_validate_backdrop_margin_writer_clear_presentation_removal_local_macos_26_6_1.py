"""Unit tests for the clear positive-zero writer/removal validator."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import test_validate_backdrop_margin_writer_execution as fixture
import validate_backdrop_margin_writer_clear_presentation_removal_local_macos_26_6_1 as validator


class BackdropMarginWriterClearPresentationRemovalTests(unittest.TestCase):
    def test_late_removal_requires_contiguous_pre_removal_images(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            removal_sample = 30
            for index in range(removal_sample + 1):
                (directory / f"transition-materialize-{index:02d}-rgba8.png").touch()
            (directory / "transition-progress.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 5,
                        "phase": "complete",
                        "capture": "transition-materialize-30",
                    }
                ),
                encoding="utf-8",
            )
            timeline = {
                "schemaVersion": 5,
                "probe": "paced-presentation-state-window-timeline",
                "material": "clear",
                "appearance": "light",
                "direction": "materialize",
                "error": (
                    "presentation glassBackground snapshot unavailable at sample 30"
                ),
            }
            self.assertEqual(
                validator.validate_removal_timeline(timeline, directory), 30
            )
            (directory / "transition-materialize-30-rgba8.png").unlink()
            with self.assertRaisesRegex(ValueError, "image sequence"):
                validator.validate_removal_timeline(timeline, directory)

    def clear_trace(self) -> dict[str, object]:
        trace = copy.deepcopy(fixture.trace())
        events = trace["events"]
        events.pop()
        setter = events[0]
        setter["marginF64"] = 0.0
        setter["marginF64RawLittleEndianHex"] = validator.ZERO_F64_RAW
        copy_store = events[2]
        copy_store["marginF32"] = 0.0
        copy_store["marginF32RawLittleEndianHex"] = validator.ZERO_F32_RAW
        copy_store["entryRenderArgumentMatched"] = False
        trace["finalEventCount"] = len(events)
        trace["eventTypeCounts"] = {
            "marginSetter": 1,
            "copyEntry": 1,
            "copyMarginStore": 1,
            "backdropBounds": 0,
        }
        del trace["codeGates"]["bounds"]
        for name, expected in validator.CODE_GATES.items():
            gate = trace["codeGates"][name]
            gate["function"] = expected["function"]
            gate["symbolByteCount"] = expected["byteCount"]
            gate["symbolEnd"] = gate["symbolStart"] + expected["byteCount"]
            gate["codeSHA256"] = expected["sha256"]
            gate["module"]["uuid"] = validator.LIVE_QUARTZCORE_UUID
        return trace

    def test_clear_events_accept_only_positive_zero_without_bounds(self) -> None:
        trace = self.clear_trace()
        gates = validator.validate_code_gates(trace)
        callers = fixture.validator.validate_callers(trace)
        events, joined = validator.validate_events(trace, gates, callers)
        self.assertEqual(len(events), 3)
        self.assertEqual(joined, 1)
        trace["events"][0]["marginF64RawLittleEndianHex"] = "0000000000000080"
        with self.assertRaisesRegex(ValueError, "positive zero"):
            validator.validate_events(trace, gates, callers)

    def test_removal_sample_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            timeline = {
                "schemaVersion": 5,
                "probe": "paced-presentation-state-window-timeline",
                "material": "clear",
                "direction": "materialize",
                "error": (
                    "presentation glassBackground snapshot unavailable at sample 1"
                ),
            }
            with self.assertRaisesRegex(ValueError, "was not late"):
                validator.validate_removal_timeline(timeline, directory)


if __name__ == "__main__":
    unittest.main()
