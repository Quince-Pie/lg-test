#!/usr/bin/env python3
"""Contracts for the frozen dematerialize uniform holdout."""

import json
import tempfile
import unittest
from pathlib import Path

import aggregate_transition_uniform_dematerialize_holdout as aggregate
import validate_transition_uniform_dematerialize_holdout as validator


ANALYSIS = Path(__file__).parent
PREREGISTRATION = (
    ANALYSIS / "transition_uniform_dematerialize_holdout_preregistration.json"
)
RUNNER = (
    ANALYSIS
    / "run_transition_uniform_dematerialize_holdout_local_macos_26_6_1.sh"
).read_text(encoding="utf-8")
NATIVE = (
    ANALYSIS
    / "analyze_transition_uniform_dematerialize_clamp_holdout_local_macos_26_6_1.swift"
).read_text(encoding="utf-8")
FROZEN = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))


class DematerializeHoldoutPreregistrationTests(unittest.TestCase):
    def test_all_four_runtime_profiles_validate_against_frozen_sources(self) -> None:
        for identity, (case_name, diameter) in validator.EXPECTED_CASES.items():
            _, observed_name, observed_diameter = validator.validate_preregistration(
                PREREGISTRATION, identity
            )
            self.assertEqual(observed_name, case_name)
            self.assertEqual(observed_diameter, diameter)

    def test_every_apple_output_is_unknown_at_freeze(self) -> None:
        self.assertIsNone(FROZEN["runtimeOutcomeFrozenBeforeDispatch"])
        self.assertEqual(FROZEN["sourceStateBeforeFreeze"]["githubActionsUsedForThisGate"], False)
        for case in FROZEN["caseMatrix"]:
            self.assertFalse(case["appleOutputAvailableAtFreeze"])
            self.assertIsNone(case["timelineSHA256"])
            self.assertIsNone(case["numericFieldWords"])
            self.assertIsNone(case["inputClampWords"])
            self.assertIsNone(case["windowServerFrameWords"])

    def test_real_record_and_absent_endpoint_topology_is_frozen(self) -> None:
        acceptance = FROZEN["acceptance"]
        self.assertEqual(acceptance["dynamicStateCountPerCase"], 31)
        self.assertTrue(acceptance["requireRealRecordsWithoutSyntheticEndpoint"])
        self.assertEqual(
            acceptance["commonAbsentEndpointFrame"],
            "transition-dematerialize-32-rgba8.png",
        )
        self.assertEqual(acceptance["expectedDistinctMatrixFrameCount"], 129)
        self.assertIn('let expectedIndices = Array(1...31)', NATIVE)
        self.assertNotIn("dynamic record count == 32", NATIVE)

    def test_direct_retina_runner_forbids_github_and_native_nix_paths(self) -> None:
        self.assertIn("GITHUB_ACTIONS_USED=0", RUNNER)
        self.assertIn("LG_TRANSITION_DIRECTION=\"$direction\"", RUNNER)
        self.assertIn("native capture environment contains a Nix store path", RUNNER)
        self.assertIn("glass-transition-introspect-9b5c502", RUNNER)
        self.assertIn("check_local_retina_capture_session_v2.swift", RUNNER)

    def test_pass_grants_only_numeric_dematerialize_transfer(self) -> None:
        authority = FROZEN["productAuthority"]
        self.assertTrue(
            authority["fourProfileNumericDematerializeTransferEstablishedOnCompletePass"]
        )
        self.assertFalse(authority["productionShaderAuthorizedOnPass"])
        self.assertFalse(authority["liquidGlassParityEstablishedOnPass"])
        self.assertFalse(
            authority["independentWalleZeroByteFrameParityEstablishedOnPass"]
        )

    @staticmethod
    def synthetic_results(directory: Path) -> list[Path]:
        paths = []
        for case_index, (identity, (case_id, _)) in enumerate(
            sorted(validator.EXPECTED_CASES.items())
        ):
            material, appearance, geometry = identity
            frame_hashes = {
                aggregate.ABSENT_FRAME_NAME: aggregate.ABSENT_FRAME_SHA256
            }
            frame_hashes.update(
                {
                    f"transition-dematerialize-{frame:02d}-rgba8.png": (
                        f"{case_index * 32 + frame:064x}"
                    )
                    for frame in range(32)
                }
            )
            value = {
                "transitionUniformDematerializeHoldoutValidationSchemaVersion": 1,
                "classification": (
                    "prospective direct-Retina dematerialize numeric uniform "
                    "transfer; one case of the frozen four-profile matrix"
                ),
                "caseId": case_id,
                "profile": {
                    "material": material,
                    "appearance": appearance,
                    "direction": "dematerialize",
                    "geometry": geometry,
                },
                "captureCommit": "a" * 40,
                "openedCalibrationSHA256": "b" * 64,
                "inputs": {
                    "timelineSHA256": f"{case_index + 1:064x}",
                    "nativeClampResultSHA256": f"{case_index + 5:064x}",
                },
                "uniformAnalysis": {
                    "numericComparisonCount": 1_457,
                    "numericExactMatchCount": 1_457,
                    "structuredRecordCount": 31,
                },
                "windowServerFrames": {
                    "count": 33,
                    "distinctSHA256Count": 33,
                    "sha256": frame_hashes,
                },
                "conclusion": {
                    "captureIntegrityPassed": True,
                    "numericDematerializeTransferPassedForCase": True,
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

    def test_frozen_129_frame_relation_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = aggregate.aggregate(self.synthetic_results(Path(temporary)))
        totals = result["aggregate"]
        self.assertEqual(totals["windowServerFrameCount"], 132)
        self.assertEqual(totals["distinctWindowServerFrameCount"], 129)
        self.assertEqual(totals["duplicateFrameClassCount"], 1)
        self.assertEqual(totals["numericExactMatchCount"], 5_828)

    def test_any_second_duplicate_class_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.synthetic_results(Path(temporary))
            first = json.loads(paths[0].read_text(encoding="utf-8"))
            second = json.loads(paths[1].read_text(encoding="utf-8"))
            frame = "transition-dematerialize-01-rgba8.png"
            second["windowServerFrames"]["sha256"][frame] = first[
                "windowServerFrames"
            ]["sha256"][frame]
            paths[1].write_text(json.dumps(second), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "distinct frame count"):
                aggregate.aggregate(paths)


if __name__ == "__main__":
    unittest.main()
