#!/usr/bin/env python3
"""Integrity tests for the prospective crop-transfer registration."""

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
WORKSPACE_ROOT = REPOSITORY_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_crop_transfer_preregistration.json"
)
REGISTRATION = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))
RETRY_REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_crop_transfer_retry_preregistration.json"
)
RETRY_REGISTRATION = json.loads(
    RETRY_REGISTRATION_PATH.read_text(encoding="utf-8")
)
ERROR_CHECKED_RETRY_REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_crop_transfer_error_checked_retry_preregistration.json"
)
ERROR_CHECKED_RETRY_REGISTRATION = json.loads(
    ERROR_CHECKED_RETRY_REGISTRATION_PATH.read_text(encoding="utf-8")
)
AVAILABLE_REGISTER_REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_crop_transfer_available_register_preregistration.json"
)
AVAILABLE_REGISTER_REGISTRATION = json.loads(
    AVAILABLE_REGISTER_REGISTRATION_PATH.read_text(encoding="utf-8")
)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_sha256(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


class PrepareLayerCropTransferPreregistrationTests(unittest.TestCase):
    def test_registration_is_prospective_and_has_no_observed_outcome(self):
        self.assertEqual(
            REGISTRATION["prepareLayerCropTransferPreregistrationSchemaVersion"],
            1,
        )
        self.assertIn("prospective", REGISTRATION["classification"])
        self.assertNotIn("result", REGISTRATION)
        self.assertNotIn("workflowConclusion", REGISTRATION)
        self.assertFalse(
            REGISTRATION["acceptance"]["generalCropPolicyMayBeClaimedByThisCaptureAlone"]
        )
        self.assertFalse(
            REGISTRATION["acceptance"]["productionShaderMayChange"]
        )
        self.assertFalse(
            REGISTRATION["acceptance"]["liquidGlassParityMayBeClaimed"]
        )

    def test_discovery_matrix_is_dense_and_phase_discriminating(self):
        matrix = REGISTRATION["frozenDiscoveryMatrix"]
        self.assertEqual(matrix["geometryCount"], 8)
        self.assertEqual(matrix["normalReplayRecordCountPerGeometry"], 32)
        self.assertEqual(matrix["prospectivePrivateRecordCount"], 256)
        self.assertTrue(matrix["denseAllocationEvidence"])
        self.assertEqual(
            set(matrix["geometries"]),
            {
                "circle-640-center",
                "circle-640-integer",
                "circle-640-phase-0500-even",
                "circle-640-phase-0500-signed",
                "circle-256-center",
                "circle-512-offset",
                "circle-640-fractional",
                "circle-1536-center",
            },
        )

    def test_selection_is_crop_independent_and_fails_closed(self):
        design = REGISTRATION["captureDesign"]
        acceptance = REGISTRATION["acceptance"]
        self.assertIn("Crop and aggregate bytes are not read", design["selection"])
        self.assertIn("missing or duplicate", design["join"])
        self.assertFalse(design["hardwareWatchpoints"])
        self.assertFalse(design["instructionStepping"])
        self.assertFalse(design["productionShaderChanged"])
        self.assertTrue(acceptance["cropIndependentSelectionRequired"])
        self.assertTrue(acceptance["oneQualifiedRecordPerNormalReplayRequired"])
        self.assertTrue(acceptance["zeroTraceFailuresRequired"])
        self.assertTrue(acceptance["zeroDiscardedQualifiedRecordsRequired"])
        self.assertTrue(acceptance["zeroUnretainedRejectionsRequired"])

    def test_frozen_implementation_hashes_match(self):
        frozen = REGISTRATION["frozenImplementation"]
        retry = AVAILABLE_REGISTER_REGISTRATION["frozenImplementation"]
        pairs = (
            (frozen["workflow"], frozen["workflowSHA256"]),
            (retry["captureHarness"], retry["captureHarnessSHA256"]),
            (retry["captureHarnessTest"], retry["captureHarnessTestSHA256"]),
            (retry["validator"], retry["validatorSHA256"]),
            (retry["validatorTest"], retry["validatorTestSHA256"]),
        )
        for relative, expected in pairs:
            self.assertEqual(sha256(REPOSITORY_ROOT / relative), expected)

    def test_retry_is_chained_to_the_immutable_failed_attempt(self):
        retry = RETRY_REGISTRATION
        original = retry["originalPreregistration"]
        failed = retry["failedAttempt"]
        correction = retry["retryCorrection"]
        acceptance = retry["acceptance"]
        self.assertEqual(
            retry["prepareLayerCropTransferRetryPreregistrationSchemaVersion"],
            1,
        )
        self.assertEqual(sha256(REGISTRATION_PATH), original["sha256"])
        self.assertEqual(
            original["captureHarnessSHA256"],
            REGISTRATION["frozenImplementation"]["captureHarnessSHA256"],
        )
        self.assertEqual(
            original["captureHarnessTestSHA256"],
            REGISTRATION["frozenImplementation"]["captureHarnessTestSHA256"],
        )
        self.assertEqual(failed["runID"], 31052255187)
        self.assertEqual(failed["failedJobCount"], 8)
        self.assertEqual(len(failed["artifactInventory"]), 8)
        self.assertEqual(
            len({record["artifactID"] for record in failed["artifactInventory"]}),
            8,
        )
        self.assertTrue(
            all(
                record["digest"].startswith("sha256:")
                and is_sha256(record["digest"].removeprefix("sha256:"))
                for record in failed["artifactInventory"]
            )
        )
        self.assertFalse(
            failed["openedFailureFixture"]["privateCropOutcomeObserved"]
        )
        self.assertEqual(
            failed["openedFailureFixture"]["failureMessage"],
            "register x30 data is unavailable",
        )
        self.assertEqual(correction["affectedArchitecturalRegister"], "x30")
        self.assertFalse(correction["selectionChanged"])
        self.assertFalse(correction["cropBytesReadDuringSelection"])
        self.assertFalse(correction["ordinalJoinChanged"])
        self.assertFalse(correction["appleCaptureProgramChanged"])
        self.assertTrue(
            acceptance["allOriginalProspectiveCaptureRequirementsRemainRequired"]
        )
        self.assertTrue(acceptance["x30ScalarViewsMustAgreeWhenFallbackIsUsed"])
        self.assertFalse(acceptance["generalCropPolicyMayBeClaimedByRetryAlone"])
        self.assertFalse(acceptance["productionShaderMayChange"])
        self.assertIsNone(retry["retryRuntimeOutcomeFrozenBeforeDispatch"])

    def test_available_register_amendment_removes_only_unused_x30(self):
        registration = AVAILABLE_REGISTER_REGISTRATION
        antecedent = registration["antecedentRetryPreregistration"]
        failed = registration["failedAttempt"]
        amendment = registration["amendment"]
        acceptance = registration["acceptance"]
        self.assertEqual(
            registration[
                "prepareLayerCropTransferAvailableRegisterPreregistrationSchemaVersion"
            ],
            1,
        )
        self.assertEqual(
            sha256(ERROR_CHECKED_RETRY_REGISTRATION_PATH), antecedent["sha256"]
        )
        previous = ERROR_CHECKED_RETRY_REGISTRATION["frozenRetryImplementation"]
        self.assertEqual(
            antecedent["captureHarnessSHA256"], previous["captureHarnessSHA256"]
        )
        self.assertEqual(
            antecedent["captureHarnessTestSHA256"],
            previous["captureHarnessTestSHA256"],
        )
        self.assertEqual(antecedent["validatorSHA256"], previous["validatorSHA256"])
        self.assertEqual(failed["runID"], 31053754016)
        self.assertEqual(
            failed["headSHA"], "75c8fb8dd693ecc4a07f9d1f56dded6aaf95bb14"
        )
        self.assertEqual(failed["failedJobCount"], 8)
        self.assertEqual(len(failed["artifactInventory"]), 8)
        self.assertEqual(
            len({record["artifactID"] for record in failed["artifactInventory"]}),
            8,
        )
        self.assertTrue(
            all(
                record["digest"].startswith("sha256:")
                and is_sha256(record["digest"].removeprefix("sha256:"))
                for record in failed["artifactInventory"]
            )
        )
        self.assertEqual(failed["openedFailureFixture"]["qualifiedRecordCount"], 0)
        self.assertFalse(
            failed["openedFailureFixture"]["privateCropOutcomeObserved"]
        )
        self.assertEqual(amendment["removedUnavailableField"], "x30")
        self.assertEqual(
            amendment["markerRegisterNames"],
            ["x%d" % index for index in range(30)] + ["sp", "pc", "cpsr"],
        )
        self.assertEqual(
            amendment["prepareFrameRegisterNames"],
            ["x19", "x28", "x29", "sp", "pc"],
        )
        self.assertNotIn("x30", amendment["markerRegisterNames"])
        self.assertNotIn("x30", amendment["prepareFrameRegisterNames"])
        for predicate in (
            "x30UsedByStructuralSelection",
            "x30UsedByCropDecoding",
            "x30UsedByMemoryAddressing",
            "x30UsedByOrdinalJoin",
            "x30UsedByAnyAcceptancePredicate",
        ):
            self.assertFalse(amendment[predicate])
        self.assertTrue(amendment["allRetainedRegistersRequireExactSBData"])
        self.assertFalse(amendment["syntheticRegisterFallbackRetained"])
        self.assertFalse(amendment["selectionChanged"])
        self.assertFalse(amendment["cropBytesReadDuringSelection"])
        self.assertFalse(amendment["ordinalJoinChanged"])
        self.assertFalse(amendment["appleCaptureProgramChanged"])
        self.assertTrue(
            acceptance[
                "allOriginalProspectiveRequirementsExceptUnavailableUnusedX30RemainRequired"
            ]
        )
        self.assertTrue(acceptance["exactSBDataRequiredForEveryRetainedRegister"])
        self.assertTrue(acceptance["allCropBearingMemoryRangesRemainRequired"])
        self.assertFalse(acceptance["generalCropPolicyMayBeClaimedByThisRunAlone"])
        self.assertFalse(acceptance["productionShaderMayChange"])
        self.assertIsNone(registration["runtimeOutcomeFrozenBeforeDispatch"])

    def test_error_checked_retry_is_chained_to_the_second_failed_attempt(self):
        retry = ERROR_CHECKED_RETRY_REGISTRATION
        antecedent = retry["antecedentRetryPreregistration"]
        failed = retry["failedAttempt"]
        api = retry["apiEvidence"]
        correction = retry["retryCorrection"]
        acceptance = retry["acceptance"]
        self.assertEqual(
            retry[
                "prepareLayerCropTransferErrorCheckedRetryPreregistrationSchemaVersion"
            ],
            1,
        )
        self.assertEqual(sha256(RETRY_REGISTRATION_PATH), antecedent["sha256"])
        self.assertEqual(
            antecedent["captureHarnessSHA256"],
            RETRY_REGISTRATION["frozenRetryImplementation"][
                "captureHarnessSHA256"
            ],
        )
        self.assertEqual(
            antecedent["captureHarnessTestSHA256"],
            RETRY_REGISTRATION["frozenRetryImplementation"][
                "captureHarnessTestSHA256"
            ],
        )
        self.assertEqual(failed["runID"], 31053097928)
        self.assertEqual(failed["headSHA"], "0faf942e552bd04131ae78af46d52c5797968792")
        self.assertEqual(failed["failedJobCount"], 8)
        self.assertEqual(len(failed["artifactInventory"]), 8)
        self.assertEqual(
            len({record["artifactID"] for record in failed["artifactInventory"]}),
            8,
        )
        self.assertTrue(
            all(
                record["digest"].startswith("sha256:")
                and is_sha256(record["digest"].removeprefix("sha256:"))
                for record in failed["artifactInventory"]
            )
        )
        opened = failed["openedFailureFixture"]
        self.assertEqual(opened["qualifiedRecordCount"], 0)
        self.assertFalse(opened["privateCropOutcomeObserved"])
        self.assertEqual(
            opened["failureMessage"],
            "register x30 has neither exact SBData nor a self-consistent scalar value",
        )
        self.assertIn("GetValueAsUnsigned", api["requiredOverload"])
        self.assertIn("SBError", api["requiredOverload"])
        self.assertEqual(correction["affectedArchitecturalRegister"], "x30")
        self.assertFalse(correction["selectionChanged"])
        self.assertFalse(correction["cropBytesReadDuringSelection"])
        self.assertFalse(correction["ordinalJoinChanged"])
        self.assertFalse(correction["appleCaptureProgramChanged"])
        self.assertFalse(correction["validatorChanged"])
        self.assertTrue(
            acceptance["allOriginalProspectiveCaptureRequirementsRemainRequired"]
        )
        self.assertTrue(acceptance["x30ExplicitScalarErrorMustReportSuccess"])
        self.assertTrue(acceptance["x30PresentFormattedTextMustAgree"])
        self.assertTrue(
            acceptance["x30MissingFormattedTextMayNotRejectAnErrorCheckedValue"]
        )
        self.assertFalse(acceptance["generalCropPolicyMayBeClaimedByRetryAlone"])
        self.assertFalse(acceptance["productionShaderMayChange"])
        self.assertIsNone(retry["retryRuntimeOutcomeFrozenBeforeDispatch"])

    def test_external_walle_companion_hashes_are_frozen_and_match_when_present(self):
        frozen = REGISTRATION["frozenImplementation"]
        companions = (
            (
                WORKSPACE_ROOT / "shaders" / "frag.glsl",
                frozen["productionShaderSHA256"],
            ),
            (WORKSPACE_ROOT / "flake.nix", frozen["developmentFlakeSHA256"]),
        )
        for path, expected in companions:
            with self.subTest(path=path):
                self.assertTrue(is_sha256(expected))
                if path.is_file():
                    self.assertEqual(sha256(path), expected)

    def test_capture_program_is_unchanged_and_fully_hashed(self):
        records = REGISTRATION["frozenCaptureProgram"]
        self.assertEqual(len(records), 7)
        for record in records:
            self.assertEqual(
                sha256(REPOSITORY_ROOT / record["path"]),
                record["sha256"],
            )

    def test_opened_semantic_results_are_pinned(self):
        opened = REGISTRATION["openedEvidenceBoundary"]
        self.assertEqual(
            sha256(
                ANALYSIS_ROOT
                / "dynamic_allocation_prepare_layer_crop_writer_semantics_result.json"
            ),
            opened["cropWriterSemanticsResultSHA256"],
        )
        self.assertEqual(
            sha256(
                ANALYSIS_ROOT
                / "dynamic_allocation_prepare_layer_dod_semantics_result.json"
            ),
            opened["dodSemanticsResultSHA256"],
        )

    def test_diagnostic_hypotheses_are_explicitly_not_acceptance(self):
        hypotheses = REGISTRATION["frozenDiagnosticHypotheses"]
        self.assertIn("not accepted prospectively", hypotheses["baselineOnly"]["status"])
        self.assertIn("diagnostic candidates only", hypotheses["genericComposition"]["status"])
        self.assertFalse(
            REGISTRATION["acceptance"]["formulaFitRequiredForCaptureIntegrity"]
        )


if __name__ == "__main__":
    unittest.main()
