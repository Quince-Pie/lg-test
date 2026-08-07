"""Integrity checks for the frozen direct-Retina clear-removal gate."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
ROOT = ANALYSIS.parent
PREREGISTRATION = (
    ANALYSIS
    / "backdrop_margin_writer_clear_presentation_removal_local_macos_26_6_1_"
    "preregistration.json"
)


class BackdropMarginWriterClearPresentationRemovalPreregistrationTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))

    def test_calibration_and_unseen_dark_holdout_are_distinct(self) -> None:
        self.assertEqual(
            self.value[
                "backdropMarginWriterClearPresentationRemovalPreregistrationSchemaVersion"
            ],
            1,
        )
        cases = self.value["caseMatrix"]
        self.assertEqual(len(cases), 2)
        light = next(case for case in cases if case["appearance"] == "light")
        dark = next(case for case in cases if case["appearance"] == "dark")
        self.assertEqual(light["role"], "calibration-removal")
        self.assertTrue(light["appleOutputAvailableAtFreeze"])
        self.assertEqual(light["observedRemovalSamples"], [30, 30])
        self.assertEqual(dark["role"], "prospective-holdout")
        self.assertFalse(dark["appleOutputAvailableAtFreeze"])
        self.assertIsNone(dark["expectedRemovalSample"])
        self.assertIsNone(dark["expectedEventCounts"])

    def test_candidate_is_bitwise_zero_and_bounds_absence_is_explicit(self) -> None:
        candidate = self.value["frozenCandidate"]
        self.assertEqual(
            candidate["groupMarginF64RawLittleEndianHex"], "0000000000000000"
        )
        self.assertEqual(
            candidate["setterInputF64RawLittleEndianHex"], "0000000000000000"
        )
        self.assertEqual(candidate["copyStoreF32RawLittleEndianHex"], "00000000")
        self.assertFalse(candidate["regularBoundsConsumerExpected"])
        self.assertTrue(candidate["presentationBackdropRemovalExpected"])
        self.assertEqual(candidate["minimumRemovalSample"], 24)
        self.assertEqual(candidate["maximumRemovalSample"], 32)
        self.assertIn("images 00 through N", candidate["retainedImageSequence"])
        self.assertFalse(candidate["prospectiveHoldoutOutputUsedToChooseCandidate"])

    def test_v6_partial_clear_runs_are_not_relabelled_as_passes(self) -> None:
        supersession = self.value["supersedesRegularStyleClearConsumerContract"]
        self.assertTrue(supersession["regularDarkCorrectedCompositionProspectivelyPassed"])
        self.assertEqual(supersession["clearLightCaptureCount"], 2)
        self.assertFalse(supersession["v6ClearCompleteChainAcceptancePassed"])
        self.assertFalse(supersession["partialCapturesPromotedToProspectivePass"])
        self.assertFalse(supersession["clearDarkOutputAvailableWhenNewContractFrozen"])
        result = ROOT / supersession["result"]
        self.assertEqual(
            hashlib.sha256(result.read_bytes()).hexdigest(),
            supersession["resultSHA256"],
        )

    def test_frozen_evidence_and_implementation_hashes_match(self) -> None:
        entries = self.value["frozenEvidence"] + self.value["frozenImplementation"]
        self.assertGreaterEqual(len(entries), 10)
        seen: set[str] = set()
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

    def test_host_quality_and_product_authority_fail_closed(self) -> None:
        capture = self.value["captureContract"]
        self.assertTrue(capture["directPhysicalMacOnly"])
        self.assertTrue(capture["githubActionsForbidden"])
        self.assertTrue(capture["nativeAppleCommandLineToolsOnly"])
        self.assertTrue(capture["nixStorePathInNativeBuildOrDebugForbidden"])
        locks = self.value["qualityLocks"]
        self.assertFalse(locks["shaderQualityRegressionPermitted"])
        for name in ("productionShader", "walleFlake"):
            lock = locks[name]
            path = ROOT / lock["path"]
            self.assertFalse(lock["changed"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), lock["sha256"])
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
