"""Integrity checks for the frozen direct-M1 provider/writer composition gate."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
ROOT = ANALYSIS.parent
PREREGISTRATION = (
    ANALYSIS
    / "backdrop_margin_writer_provider_composition_local_macos_26_6_1_"
    "v6_preregistration.json"
)


class BackdropMarginWriterProviderCompositionPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))

    def test_three_unseen_holdouts_and_one_calibration_case_are_frozen(self) -> None:
        self.assertEqual(
            self.value[
                "backdropMarginWriterProviderCompositionPreregistrationSchemaVersion"
            ],
            6,
        )
        cases = self.value["caseMatrix"]
        self.assertEqual(
            {
                (
                    case["material"],
                    case["appearance"],
                    case["direction"],
                    case["geometry"],
                )
                for case in cases
            },
            {
                ("clear", "light", "materialize", "circle-451-center"),
                ("clear", "dark", "materialize", "circle-459-center"),
                ("regular", "light", "materialize", "circle-467-center"),
                ("regular", "dark", "materialize", "circle-475-center"),
            },
        )
        self.assertEqual(len(cases), 4)
        for case in cases:
            self.assertIsNone(case["expectedWriterPointers"])
            self.assertIsNone(case["expectedCrop"])
            self.assertIsNone(case["expectedImageDigest"])
            opened = case["geometry"] == "circle-467-center"
            if opened:
                self.assertEqual(case["role"], "calibration-falsification")
                self.assertTrue(case["exactConfigurationPreviouslyCaptured"])
                self.assertTrue(case["appleInputAvailableAtFreeze"])
                self.assertTrue(case["appleTargetWriterOutputAvailableAtFreeze"])
                self.assertEqual(case["expectedGroupMarginF64"], 163.45)
                self.assertEqual(
                    case["expectedGroupMarginF64RawLittleEndianHex"],
                    "66666666666e6440",
                )
                self.assertEqual(
                    case["expectedRenderMarginF32"], 163.4499969482422
                )
                self.assertEqual(
                    case["expectedRenderMarginF32RawLittleEndianHex"], "33732343"
                )
            else:
                self.assertEqual(case["role"], "prospective-holdout")
                self.assertFalse(case["exactConfigurationPreviouslyCaptured"])
                self.assertFalse(case["appleInputAvailableAtFreeze"])
                self.assertFalse(case["appleTargetWriterOutputAvailableAtFreeze"])
                self.assertIsNone(case["expectedGroupMarginF64"])
                self.assertIsNone(case["expectedRenderMarginF32"])
        self.assertIsNone(self.value["runtimeOutcomeFrozenBeforeDispatch"])

    def test_v1_failed_before_launch_and_consumed_no_case(self) -> None:
        failure = self.value["supersedesBuildTransportVersion"]
        self.assertFalse(failure["applicationBuilt"])
        self.assertFalse(failure["applicationLaunched"])
        self.assertFalse(failure["lldbStarted"])
        self.assertFalse(failure["appleMarginCropImageOrPixelObserved"])
        self.assertFalse(failure["candidateTested"])
        self.assertEqual(failure["prospectiveCasesConsumed"], 0)
        result = ROOT / failure["result"]
        self.assertEqual(
            hashlib.sha256(result.read_bytes()).hexdigest(), failure["resultSHA256"]
        )

    def test_v2_retained_no_candidate_input_or_writer_event(self) -> None:
        failure = self.value["supersedesStructuralTransportVersion"]
        self.assertFalse(failure["completeTimelineCreated"])
        self.assertEqual(failure["dynamicPublicRecordCount"], 0)
        self.assertEqual(failure["writerEventCount"], 0)
        self.assertFalse(failure["appleMarginOrCropObserved"])
        self.assertFalse(failure["candidateTested"])
        self.assertFalse(failure["caseAcceptedAsProspectiveEvidence"])
        self.assertFalse(failure["candidateCaseMatrixSelectionOrAcceptanceChanged"])
        result = ROOT / failure["result"]
        self.assertEqual(
            hashlib.sha256(result.read_bytes()).hexdigest(), failure["resultSHA256"]
        )

    def test_v3_pins_stable_binary_and_live_module_identities(self) -> None:
        capture = self.value["captureContract"]
        self.assertEqual(
            capture["stablePresentationBinarySHA256"],
            "b9cb4068e77a61ff87794fa20a5c273e007f3ee20dd74503b1ab78839104e8dd",
        )
        self.assertEqual(
            capture["liveQuartzCoreUUID"],
            "F1BA3189-E95A-3ECA-B59A-5A6872754484",
        )
        self.assertEqual(
            capture["liveSwiftUICoreUUID"],
            "99606D45-C40A-3C69-AE51-5F0C4E32E531",
        )
        self.assertEqual(
            capture["liveSwiftUICoreCallerSHA256"],
            "d60a0510382f913b937ceb2c20111c4dcf1b4dd9d6d49388c2fe5c4d2683168c",
        )

    def test_v3_callback_namespace_failure_opened_no_value(self) -> None:
        failure = self.value["supersedesCallbackTransportVersion"]
        self.assertFalse(failure["applicationCompleted"])
        self.assertFalse(failure["timelineCreated"])
        self.assertEqual(failure["dynamicPublicRecordCount"], 0)
        self.assertEqual(failure["writerEventCount"], 0)
        self.assertFalse(failure["candidateTested"])
        self.assertFalse(failure["caseAcceptedAsProspectiveEvidence"])
        self.assertFalse(failure["candidateCaseMatrixSelectionOrAcceptanceChanged"])
        result = ROOT / failure["result"]
        self.assertEqual(
            hashlib.sha256(result.read_bytes()).hexdigest(), failure["resultSHA256"]
        )

    def test_v4_opened_input_but_not_target_writer_output(self) -> None:
        failure = self.value["supersedesHistoricalWriterCodeVersion"]
        self.assertTrue(failure["retinaTimelineComplete"])
        self.assertEqual(failure["dynamicPublicRecordCount"], 32)
        self.assertEqual(failure["frozenPredictionFromOpenedInputF64"], 83.0)
        self.assertEqual(failure["writerSetterEventCount"], 0)
        self.assertEqual(failure["writerCopyStoreEventCount"], 0)
        self.assertFalse(failure["targetWriterMarginObserved"])
        self.assertFalse(failure["candidateTestedAgainstTarget"])
        self.assertFalse(failure["candidateFormulaChanged"])
        self.assertFalse(failure["remainingThreeUnseenCasesChanged"])
        result = ROOT / failure["result"]
        self.assertEqual(
            hashlib.sha256(result.read_bytes()).hexdigest(), failure["resultSHA256"]
        )

    def test_provider_only_candidate_is_preserved_as_a_clean_falsification(self) -> None:
        falsification = self.value["supersedesProviderOnlyCompositionVersion"]
        self.assertTrue(falsification["captureCompleted"])
        self.assertTrue(falsification["providerOnlyCandidateFalsifiedBitwise"])
        self.assertEqual(falsification["frozenProviderOnlyPredictionF64"], 83.0)
        self.assertEqual(falsification["observedWriterTargetF64"], 163.45)
        self.assertEqual(
            falsification["observedWriterTargetF64RawLittleEndianHex"],
            "66666666666e6440",
        )
        self.assertEqual(
            falsification["maximumInputBleedF64RawLittleEndianHex"],
            falsification["observedWriterTargetF64RawLittleEndianHex"],
        )
        result = ROOT / falsification["result"]
        self.assertEqual(
            hashlib.sha256(result.read_bytes()).hexdigest(),
            falsification["resultSHA256"],
        )

    def test_corrected_candidate_discloses_calibration_and_preserves_holdouts(self) -> None:
        candidate = self.value["frozenCandidate"]
        self.assertEqual(
            candidate["perRecordProviderReturn"],
            "max(abs(inputShadowOffset.x), abs(inputShadowOffset.y)) + "
            "abs(inputShadowAmount)",
        )
        self.assertEqual(
            candidate["perRecordRegularGroupContribution"],
            "max(inputBleedAmount, authenticated per-record provider return)",
        )
        self.assertTrue(candidate["capturedTargetValueUsedToChooseCandidate"])
        self.assertFalse(candidate["prospectiveFreshCaseOutputUsedToChooseCandidate"])
        self.assertFalse(candidate["cropOrImageUsedToChooseCandidate"])

    def test_frozen_evidence_and_implementation_hashes_are_current(self) -> None:
        entries = self.value["frozenEvidence"] + self.value["frozenImplementation"]
        self.assertGreaterEqual(len(entries), 15)
        seen = set()
        for entry in entries:
            self.assertNotIn(entry["path"], seen)
            seen.add(entry["path"])
            path = ROOT / entry["path"]
            self.assertTrue(path.is_file(), entry["path"])
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                entry["sha256"],
                entry["path"],
            )

    def test_direct_retina_host_and_quality_locks_are_fail_closed(self) -> None:
        capture = self.value["captureContract"]
        self.assertTrue(capture["directPhysicalMacOnly"])
        self.assertTrue(capture["githubActionsForbidden"])
        self.assertTrue(capture["activeRetinaSessionPreflightRequired"])
        self.assertTrue(capture["nativeAppleCommandLineToolsOnly"])
        self.assertTrue(capture["nixStorePathInNativeBuildOrDebugForbidden"])
        locks = self.value["qualityLocks"]
        self.assertFalse(locks["shaderQualityRegressionPermitted"])
        for name in ("productionShader", "walleFlake"):
            lock = locks[name]
            self.assertFalse(lock["changed"])
            path = ROOT / lock["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), lock["sha256"])

    def test_gate_cannot_claim_pixel_or_product_parity(self) -> None:
        authority = self.value["productAuthority"]
        for key in (
            "generalSelectedRegionPolicyEstablishedOnPass",
            "physicalRetinaColorPixelCompositorTransferEstablishedOnPass",
            "independentWalleZeroByteFrameParityEstablishedOnPass",
            "productionShaderAuthorizedOnPass",
            "liquidGlassParityEstablishedOnPass",
        ):
            self.assertFalse(authority[key], key)


if __name__ == "__main__":
    unittest.main()
