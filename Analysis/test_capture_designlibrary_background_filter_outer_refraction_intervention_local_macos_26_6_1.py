#!/usr/bin/env python3
"""Regression tests for the prospective outer-refraction intervention."""

import hashlib
import json
import unittest
from pathlib import Path

import capture_designlibrary_background_filter_outer_refraction_intervention_local_macos_26_6_1 as capture


ANALYSIS = Path(__file__).resolve().parent
PREREGISTRATION = ANALYSIS / capture.PREREGISTRATION_NAME
WEIGHTED_RESULT = ANALYSIS / capture.WEIGHTED_RESULT_NAME
CORRECTED_EXPORT_RESULT = ANALYSIS / capture.CORRECTED_EXPORT_RESULT_NAME
CORRECTED_EXPORT_PREREGISTRATION = (
    ANALYSIS
    / "designlibrary_weighted_parameters_background_filter_export_"
    "local_macos_26_6_1_preregistration.json"
)
RESULT = (
    ANALYSIS
    / "designlibrary_background_filter_outer_refraction_intervention_"
    "local_macos_26_6_1_result.json"
)
EXPECTED_HASHES = {
    "capture": "a01ff57947bc8e50ac3a60b9c45d7bb190dad9b51c656e827f15dc42c5f35635",
    "preregistration": "7e73960ba18e9f265b5cf1ad07fa0ec6758c41abf049630b81f1e909975cdb4f",
    "result": "8fc39c0a79ca020467beadba8f51d850833b390d23f87c7ae3abd6d77308ce1e",
    "probe": "f855d88dddc59b58bcd26cd7d86c804cae2e3446a92ec677180cde35559d900c",
    "bridge": "d8d4e4de79a989a9e47e98a2a63fc033ede618ddedc9c8fa223bd265f40e6f3d",
    "context": "bb3640cd849ecfe0b450e0979f7e1ef2d584b25853f8d1d717686f4ea5bac1af",
    "correctedExporter": "d080175c56e380685d43c54e9712a56576ae8f54f5fddfd6650ecbf82beef19f",
    "correctedExporterPreregistration": "8ef67f6b6106097162cdfb998f81a765da2a8b71b8ba86dafa79f4a5c505bba5",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class OuterRefractionInterventionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preregistration = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
        cls.weighted = json.loads(WEIGHTED_RESULT.read_text(encoding="utf-8"))
        cls.corrected = json.loads(
            CORRECTED_EXPORT_RESULT.read_text(encoding="utf-8")
        )
        cls.corrected_preregistration = json.loads(
            CORRECTED_EXPORT_PREREGISTRATION.read_text(encoding="utf-8")
        )
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_sources_preregistration_and_result_are_frozen(self) -> None:
        self.assertEqual(sha256(Path(capture.__file__)), EXPECTED_HASHES["capture"])
        self.assertEqual(
            sha256(PREREGISTRATION), EXPECTED_HASHES["preregistration"]
        )
        self.assertEqual(sha256(RESULT), EXPECTED_HASHES["result"])
        self.assertEqual(
            sha256(ANALYSIS / capture.PROBE_SOURCE_NAME), EXPECTED_HASHES["probe"]
        )
        self.assertEqual(
            sha256(ANALYSIS / capture.BRIDGE_SOURCE_NAME), EXPECTED_HASHES["bridge"]
        )
        self.assertEqual(
            sha256(ANALYSIS / capture.CONTEXT_SOURCE_NAME), EXPECTED_HASHES["context"]
        )
        self.assertEqual(
            sha256(CORRECTED_EXPORT_RESULT), EXPECTED_HASHES["correctedExporter"]
        )
        self.assertEqual(
            sha256(CORRECTED_EXPORT_PREREGISTRATION),
            EXPECTED_HASHES["correctedExporterPreregistration"],
        )
        self.assertEqual(
            capture.normalized_capture_source_sha256(Path(capture.__file__)),
            self.preregistration["sourceIdentity"][
                "captureSourceNormalizedSHA256"
            ],
        )

    def test_all_interventions_are_unseen_and_reproduce_frozen_payloads(self) -> None:
        payloads, cases = capture.intervention_payloads(
            self.preregistration,
            self.weighted,
        )
        self.assertEqual(len(payloads), 9)
        self.assertEqual(
            [capture.digest_bytes(payload) for payload in payloads],
            [case["syntheticParametersSHA256"] for case in cases],
        )
        self.assertEqual(
            [case["outerAmountBits"] for case in cases],
            [
                "0xc030000000000000",
                "0xbff0000000000000",
                "0x8000000000000000",
                "0x0000000000000000",
                "0x0000000000000001",
                "0x3fc0000000000000",
                "0x3ff0000000000000",
                "0x400c000000000000",
                "0x4030000000000000",
            ],
        )

    def test_corrected_reopened_export_is_exact_and_disclosed(self) -> None:
        invariants = self.corrected["measuredInvariants"]
        self.assertEqual(invariants["mappedComponentCount"], 1_519)
        self.assertEqual(
            invariants["mappedComponentExporterPredictionMatchCount"], 1_519
        )
        self.assertEqual(
            invariants["mappedComponentExporterPredictionMismatchCount"], 0
        )
        self.assertEqual(invariants["mappedComponentRetainedPublicMatchCount"], 1_054)
        self.assertEqual(
            invariants["mappedComponentRetainedPublicMismatchCount"], 465
        )
        correction = self.corrected_preregistration["failedRunCorrection3"]
        self.assertTrue(correction["genuineModelFalsification"])
        self.assertTrue(correction["predictionChangedAfterFalsification"])
        self.assertIn("retrospective", correction["rerunClassification"])

    def test_prospective_intervention_matches_every_raw_prediction(self) -> None:
        invariants = self.result["measuredInvariants"]
        self.assertEqual(invariants["caseCount"], 9)
        self.assertEqual(invariants["previouslyUnseenInterventionCount"], 9)
        self.assertEqual(invariants["freshProcessSemanticMatchCount"], 3)
        self.assertEqual(invariants["constructorOutputExactCount"], 9)
        self.assertEqual(invariants["outerAmountIdentityBitwiseMatchCount"], 9)
        self.assertEqual(
            invariants["blurDistance4PositiveZeroBitwiseMatchCount"], 9
        )
        self.assertFalse(invariants["capturedValuesUsedForRuntimeSelection"])
        for frozen, observed in zip(
            self.preregistration["interventionCases"],
            self.result["cases"],
            strict=True,
        ):
            self.assertEqual(
                observed["inputOuterRefractionAmountRawLittleEndianHex"],
                frozen["outerAmountRawLittleEndianHex"],
            )
            self.assertEqual(
                observed["inputBlurDistance4RawLittleEndianHex"],
                "0000000000000000",
            )

    def test_claims_preserve_the_remaining_parity_boundary(self) -> None:
        claims = self.result["claims"]
        self.assertTrue(claims["outerRefractionGetterSeparationEstablishedProspectively"])
        for name in (
            "actualLiveCallbackCompleteParametersObserved",
            "completeLiveParametersTransferEstablished",
            "generalIntegerCropAllocationPolicyEstablished",
            "retinaCompositorColorLawEstablished",
            "independentWalleZeroByteFrameParityEstablished",
            "liquidGlassParityEstablished",
            "productionShaderChangeAuthorized",
        ):
            self.assertFalse(claims[name])


if __name__ == "__main__":
    unittest.main()
