#!/usr/bin/env python3
"""Tests for the corrected frozen v2 uniform-transfer matrix."""

import json
import tempfile
import unittest
from pathlib import Path

import aggregate_transition_uniform_profile_holdout_v2 as aggregate
import validate_transition_uniform_profile_holdout as v1
import validate_transition_uniform_profile_holdout_v2 as validator


ANALYSIS = Path(__file__).parent
PREREGISTRATION = (
    ANALYSIS / "transition_uniform_profile_holdout_v2_preregistration.json"
)
RUNNER = ANALYSIS / "run_transition_uniform_profile_holdout_v2_local_macos_26_6_1.sh"


class TransitionUniformProfileHoldoutV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preregistration = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))

    def test_v2_cases_are_unopened(self) -> None:
        cases = self.preregistration["caseMatrix"]
        self.assertEqual(len(cases), 4)
        self.assertEqual(
            {
                (case["material"], case["appearance"], case["geometry"])
                for case in cases
            },
            set(validator.EXPECTED_CASES),
        )
        for case in cases:
            self.assertIs(case["appleOutputAvailableAtFreeze"], False)
            self.assertIsNone(case["timelineSHA256"])
            self.assertIsNone(case["numericFieldWords"])
            self.assertIsNone(case["inputClampWords"])
        for identity, (case_id, diameter) in validator.EXPECTED_CASES.items():
            _, observed_id, observed_diameter = validator.validate_preregistration(
                PREREGISTRATION, identity
            )
            self.assertEqual((observed_id, observed_diameter), (case_id, diameter))

    def test_v2_correction_is_structurally_frozen(self) -> None:
        correction = self.preregistration["correctionBasis"]
        acceptance = self.preregistration["acceptance"]
        self.assertEqual(correction["expectedFrameCount"], 132)
        self.assertEqual(correction["expectedDistinctFrameCount"], 129)
        self.assertEqual(correction["expectedDuplicateClasses"], 1)
        self.assertEqual(correction["expectedDuplicateClassOccurrences"], 4)
        self.assertEqual(
            correction["expectedDuplicateFrameName"],
            "transition-materialize-00-rgba8.png",
        )
        self.assertIs(correction["allOtherFramesMustBeGloballyDistinct"], True)
        self.assertEqual(acceptance["numericComparisonCountAcrossMatrix"], 6_016)
        self.assertEqual(acceptance["requiredNumericMismatchCount"], 0)

    def test_v1_failure_and_frozen_sources_are_hash_locked(self) -> None:
        failure = self.preregistration["v1FailureEvidence"]
        self.assertEqual(
            v1.sha256_file(ANALYSIS / Path(failure["path"]).name),
            failure["sha256"],
        )
        implementation = self.preregistration["frozenImplementation"]
        for path_key, hash_key in (
            ("model", "modelSHA256"),
            ("nativeClamp", "nativeClampSHA256"),
            ("validator", "validatorSHA256"),
            ("aggregator", "aggregatorSHA256"),
            ("preflight", "preflightSHA256"),
        ):
            path = ANALYSIS.parent / implementation[path_key]
            self.assertEqual(v1.sha256_file(path), implementation[hash_key])

    def test_runner_is_direct_and_allows_only_v2_cases(self) -> None:
        source = RUNNER.read_text(encoding="utf-8")
        self.assertNotIn("lldb", source.lower())
        self.assertNotIn("github", source.lower())
        self.assertIn("NATIVE_CAPTURE_DEBUGGER_USED=0", source)
        for profile in (
            "clear:light:circle-455-center",
            "clear:dark:circle-463-center",
            "regular:light:circle-471-center",
            "regular:dark:circle-479-center",
        ):
            self.assertIn(profile, source)

    @staticmethod
    def synthetic_results(directory: Path) -> list[Path]:
        paths = []
        for case_index, (identity, (case_id, _)) in enumerate(
            sorted(validator.EXPECTED_CASES.items())
        ):
            material, appearance, geometry = identity
            frame_hashes = {aggregate.ABSENT_FRAME_NAME: "f" * 64}
            frame_hashes.update(
                {
                    f"transition-materialize-{frame:02d}-rgba8.png": (
                        f"{case_index * 32 + frame:064x}"
                    )
                    for frame in range(1, 33)
                }
            )
            value = {
                "transitionUniformProfileHoldoutV2ValidationSchemaVersion": 1,
                "classification": (
                    "corrected prospective direct-Retina v2 materialize numeric "
                    "uniform transfer; one case of the frozen four-profile matrix"
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
                    "sha256": frame_hashes,
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

    def test_corrected_129_frame_relation_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = aggregate.aggregate(self.synthetic_results(Path(temporary)))
        totals = result["aggregate"]
        self.assertEqual(totals["windowServerFrameCount"], 132)
        self.assertEqual(totals["distinctWindowServerFrameCount"], 129)
        self.assertEqual(totals["duplicateFrameClassCount"], 1)
        self.assertEqual(totals["numericExactMatchCount"], 6_016)

    def test_any_second_duplicate_class_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.synthetic_results(Path(temporary))
            first = json.loads(paths[0].read_text(encoding="utf-8"))
            second = json.loads(paths[1].read_text(encoding="utf-8"))
            second["windowServerFrames"]["sha256"][
                "transition-materialize-01-rgba8.png"
            ] = first["windowServerFrames"]["sha256"][
                "transition-materialize-01-rgba8.png"
            ]
            paths[1].write_text(json.dumps(second), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "distinct frame count"):
                aggregate.aggregate(paths)


if __name__ == "__main__":
    unittest.main()
