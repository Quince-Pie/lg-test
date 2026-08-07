#!/usr/bin/env python3
"""Tests for the frozen four-profile uniform holdout aggregator."""

import json
import tempfile
import unittest
from pathlib import Path

import aggregate_transition_uniform_profile_holdout as aggregate
import validate_transition_uniform_profile_holdout as validator


class TransitionUniformProfileHoldoutAggregateTests(unittest.TestCase):
    def make_results(self, directory: Path) -> list[Path]:
        paths = []
        for case_index, (identity, (case_id, _)) in enumerate(
            sorted(validator.EXPECTED_CASES.items())
        ):
            material, appearance, geometry = identity
            value = {
                "transitionUniformProfileHoldoutValidationSchemaVersion": 1,
                "classification": (
                    "prospective direct-Retina materialize numeric uniform "
                    "transfer; one case of the frozen four-profile matrix"
                ),
                "caseId": case_id,
                "profile": {
                    "material": material,
                    "appearance": appearance,
                    "direction": "materialize",
                    "geometry": geometry,
                },
                "captureCommit": "a" * 40,
                "openedCalibrationSHA256": "b" * 64,
                "inputs": {
                    "timelineSHA256": f"{case_index + 1:064x}",
                    "nativeClampResultSHA256": f"{case_index + 5:064x}",
                },
                "uniformAnalysis": {
                    "numericComparisonCount": 1_504,
                    "numericExactMatchCount": 1_504,
                    "structuredRecordCount": 32,
                },
                "windowServerFrames": {
                    "count": 33,
                    "distinctSHA256Count": 33,
                    "sha256": {
                        f"frame-{frame:02d}.png": f"{case_index * 33 + frame + 100:064x}"
                        for frame in range(33)
                    },
                },
                "conclusion": {
                    "captureIntegrityPassed": True,
                    "numericMaterializeTransferPassedForCase": True,
                    "allNumericWordsExact": True,
                    "numericMismatchCount": 0,
                    "fourProfileMatrixComplete": False,
                    "productionShaderChangeAuthorized": False,
                },
            }
            path = directory / f"{case_id}.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            paths.append(path)
        return paths

    def test_complete_exact_matrix_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = aggregate.aggregate(self.make_results(Path(temporary)))
        totals = result["aggregate"]
        self.assertEqual(totals["profileCount"], 4)
        self.assertEqual(totals["dynamicStateCount"], 128)
        self.assertEqual(totals["numericComparisonCount"], 6_016)
        self.assertEqual(totals["numericExactMatchCount"], 6_016)
        self.assertEqual(totals["numericMismatchCount"], 0)
        self.assertEqual(totals["distinctWindowServerFrameCount"], 132)
        self.assertIs(
            result["conclusion"]["fourProfileNumericMaterializeTransferEstablished"],
            True,
        )

    def test_mixed_capture_commits_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.make_results(Path(temporary))
            changed = json.loads(paths[0].read_text(encoding="utf-8"))
            changed["captureCommit"] = "c" * 40
            paths[0].write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "one frozen commit"):
                aggregate.aggregate(paths)

    def test_duplicate_frame_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.make_results(Path(temporary))
            first = json.loads(paths[0].read_text(encoding="utf-8"))
            second = json.loads(paths[1].read_text(encoding="utf-8"))
            first_hash = next(iter(first["windowServerFrames"]["sha256"].values()))
            second_key = next(iter(second["windowServerFrames"]["sha256"]))
            second["windowServerFrames"]["sha256"][second_key] = first_hash
            paths[1].write_text(json.dumps(second), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not all distinct"):
                aggregate.aggregate(paths)


if __name__ == "__main__":
    unittest.main()
