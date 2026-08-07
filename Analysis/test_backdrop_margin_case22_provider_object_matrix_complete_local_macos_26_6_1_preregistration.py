#!/usr/bin/env python3
"""Integrity checks for the complete unlocked provider-matrix preregistration."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
REPOSITORY = ANALYSIS.parent
PATH = (
    ANALYSIS
    / "backdrop_margin_case22_provider_object_matrix_complete_local_macos_26_6_1_preregistration.json"
)
VALUE = json.loads(PATH.read_text(encoding="utf-8"))


class CompleteProviderObjectMatrixPreregistrationTests(unittest.TestCase):
    def test_requires_unlocked_awake_exact_retina_session(self) -> None:
        preflight = VALUE["nativeSessionPreflight"]
        self.assertFalse(preflight["requireSessionLocked"])
        self.assertTrue(preflight["requireSessionOnConsole"])
        self.assertTrue(preflight["requireDisplayActive"])
        self.assertFalse(preflight["requireDisplayAsleep"])
        self.assertEqual(preflight["requirePhysicalPixels"], [3456, 2234])
        self.assertEqual(preflight["requireLogicalPoints"], [1728, 1117])
        self.assertEqual(preflight["requireBackingScaleFactor"], 2)
        self.assertTrue(preflight["failClosedBeforeAppLaunch"])

    def test_native_debugger_is_not_wrapped_by_nix(self) -> None:
        transport = VALUE["nativeDebuggerTransport"]
        self.assertEqual(
            transport["lldb"],
            "/Library/Developer/CommandLineTools/usr/bin/lldb",
        )
        self.assertEqual(
            transport["python"],
            "/Library/Developer/CommandLineTools/usr/bin/python3",
        )
        self.assertFalse(transport["runInsideNixDevelop"])
        self.assertFalse(transport["hardCodedNixStorePath"])
        self.assertTrue(transport["importCaptureBeforeRun"])
        self.assertFalse(transport["stopAtExecutableMain"])

    def test_two_stages_are_unconditional_and_output_blind(self) -> None:
        stages = VALUE["unconditionalTwoStageDispatch"]
        self.assertEqual(
            [stage["stage"] for stage in stages],
            [
                "fixed-selected-reproduction",
                "complete-provider-matrix",
            ],
        )
        self.assertTrue(stages[0]["dispatchRegardlessOfExpectedReturn"])
        self.assertEqual(
            stages[0]["expectedReturnRawLittleEndianHex"],
            "0000006002a22a40",
        )
        self.assertTrue(stages[1]["dispatchRegardlessOfFirstStageOutcome"])
        self.assertFalse(
            VALUE["completeCapture"][
                "capturedObjectReturnMarginCropImageOrPixelUsedForSelection"
            ]
        )

    def test_frozen_sources_match(self) -> None:
        for section in ("nativeSessionPreflight", "completeCapture"):
            item = VALUE[section]
            self.assertEqual(
                hashlib.sha256((REPOSITORY / item["path"]).read_bytes()).hexdigest(),
                item["sha256"],
            )
        validator = VALUE["prospectiveValidator"]
        for path_key, hash_key in (
            ("path", "sha256"),
            ("sourceTestPath", "sourceTestSHA256"),
        ):
            self.assertEqual(
                hashlib.sha256(
                    (REPOSITORY / validator[path_key]).read_bytes()
                ).hexdigest(),
                validator[hash_key],
            )
        self.assertFalse(validator["capturedOutputMayChangeStructuralAcceptance"])
        self.assertTrue(validator["valueHypothesesReportedAsResults"])
        runner = VALUE["nativeRunner"]
        self.assertEqual(
            hashlib.sha256((REPOSITORY / runner["path"]).read_bytes()).hexdigest(),
            runner["sha256"],
        )
        self.assertEqual(
            hashlib.sha256(
                (REPOSITORY / runner["sourceTestPath"]).read_bytes()
            ).hexdigest(),
            runner["sourceTestSHA256"],
        )
        self.assertTrue(runner["directNativeCommandLineTools"])
        self.assertTrue(runner["preflightImmediatelyBeforeEachStage"])
        self.assertTrue(runner["prospectiveValidatorRunsAfterBothStages"])
        self.assertTrue(runner["secondStageIndependentOfFirstStageValue"])
        self.assertTrue(runner["validatorExitStatusRecorded"])
        self.assertTrue(runner["validatorOutputInsideCompleteStage"])
        self.assertEqual(
            runner["directNativePython"],
            "/Library/Developer/CommandLineTools/usr/bin/python3",
        )
        self.assertFalse(runner["usesNixStorePath"])

    def test_outcome_unknown_and_authority_remains_narrow(self) -> None:
        self.assertIsNone(VALUE["runtimeOutcomeFrozenBeforeDispatch"])
        self.assertTrue(
            all(value is None for value in VALUE["unknownBeforeDispatch"].values())
        )
        authority = VALUE["authorityOnPass"]
        allowed = {
            "exactCompleteProcessProviderObjectsForThisOpenedProfile",
            "exactAllCase22IterationsForEachSelectedCaller",
            "exactObjectOffsetAndReturnCovarianceForThisOpenedProfile",
            "unlockedSessionTransferForSelectedInvocation",
        }
        for key, value in authority.items():
            self.assertIs(value, key in allowed, key)

    def test_preregistration_is_canonical_json(self) -> None:
        self.assertEqual(
            PATH.read_text(encoding="utf-8"),
            json.dumps(VALUE, indent=2, sort_keys=True) + "\n",
        )


if __name__ == "__main__":
    unittest.main()
