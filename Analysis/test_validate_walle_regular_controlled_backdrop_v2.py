#!/usr/bin/env python3
"""Discriminators for the schema-only backdrop-validator correction."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import validate_walle_regular_controlled_backdrop as frozen
import validate_walle_regular_controlled_backdrop_v2 as corrected


def timeline(schema_version: int) -> dict[str, object]:
    return {
        "material": "regular",
        "appearance": "dark",
        "direction": "dematerialize",
        "geometry": {"name": "circle-480-center"},
        "dynamicBackgroundUniforms": {
            "schemaVersion": schema_version,
            "records": [
                {"sampleIndex": sample, "ordinal": ordinal}
                for ordinal, sample in enumerate(frozen.EXPECTED_SAMPLES)
            ],
        },
    }


class CorrectedValidatorTests(unittest.TestCase):
    def test_only_schema_nine_is_admitted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "transition-timeline.json").write_text(
                json.dumps(timeline(8)),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "requires.*schema 9"):
                corrected.validate(root)

    def test_all_frozen_state_checks_are_delegated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "transition-timeline.json").write_text(
                json.dumps(timeline(9)),
                encoding="utf-8",
            )

            def validate_state(
                _root: Path,
                record: frozen.JSONObject,
                _expected_input: bytes,
            ) -> frozen.JSONObject:
                fragment = (
                    "downsample_4_frag_lph"
                    if record["ordinal"] < 3
                    else "TimgA2Xhfc_Isrc"
                )
                return {
                    "sampleIndex": record["sampleIndex"],
                    "producerFragment": fragment,
                }

            with patch.object(
                frozen, "validate_state", side_effect=validate_state
            ) as call:
                result = corrected.validate(root)
            self.assertEqual(call.call_count, len(frozen.EXPECTED_SAMPLES))
            self.assertEqual(result["stateCount"], 8)
            self.assertEqual(
                result["producerFragmentCounts"],
                {"TimgA2Xhfc_Isrc": 5, "downsample_4_frag_lph": 3},
            )
            self.assertEqual(
                result["transportCorrection"],
                {
                    "field": "dynamicBackgroundUniforms.schemaVersion",
                    "frozenValue": 7,
                    "correctedValue": 9,
                    "answerBytesReadBeforeFrozenFailure": 0,
                    "stateSelectionChanged": False,
                    "pixelSelectionChanged": False,
                    "acceptanceThresholdChanged": False,
                    "toleranceChanged": False,
                },
            )


if __name__ == "__main__":
    unittest.main()
