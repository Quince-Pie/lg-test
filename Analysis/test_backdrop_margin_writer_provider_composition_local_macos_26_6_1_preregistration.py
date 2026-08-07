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
    "preregistration.json"
)


class BackdropMarginWriterProviderCompositionPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))

    def test_four_output_blind_exact_cases_are_frozen(self) -> None:
        self.assertEqual(
            self.value[
                "backdropMarginWriterProviderCompositionPreregistrationSchemaVersion"
            ],
            2,
        )
        cases = self.value["prospectiveCases"]
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
            self.assertFalse(case["exactConfigurationPreviouslyCaptured"])
            self.assertFalse(case["appleOutputAvailableAtFreeze"])
            for key in (
                "expectedGroupMarginF64",
                "expectedRenderMarginF32",
                "expectedWriterPointers",
                "expectedCrop",
                "expectedImageDigest",
            ):
                self.assertIsNone(case[key])
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

    def test_candidate_comes_from_the_authenticated_provider(self) -> None:
        correction = self.value["antecedentCorrection"]
        self.assertTrue(correction["supersededResultPreservedUnchanged"])
        self.assertFalse(correction["newCandidateChosenFromCapturedWriterTargetValue"])
        self.assertFalse(correction["newCandidateChosenFromCropOrImage"])
        candidate = self.value["frozenCandidate"]
        self.assertEqual(
            candidate["perRecordProviderReturn"],
            "max(abs(inputShadowOffset.x), abs(inputShadowOffset.y)) + "
            "abs(inputShadowAmount)",
        )
        self.assertFalse(candidate["capturedTargetValueUsedToChooseCandidate"])
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
