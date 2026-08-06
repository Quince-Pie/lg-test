"""Integrity tests for the fresh all-materialize retry holdout."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
ROOT = ANALYSIS.parent
PREREGISTRATION = (
    ANALYSIS / "backdrop_margin_writer_execution_retry_preregistration.json"
)


class BackdropMarginWriterExecutionRetryPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))

    def test_retry_changes_only_the_output_blind_abi_assertion(self) -> None:
        self.assertEqual(
            self.value[
                "backdropMarginWriterExecutionRetryPreregistrationSchemaVersion"
            ],
            1,
        )
        correction = self.value["abiCorrection"]
        self.assertFalse(correction["candidateMarginValueUsed"])
        self.assertFalse(correction["cropValueUsed"])
        self.assertFalse(correction["imageValueUsed"])
        self.assertTrue(correction["opaqueX2RetainedAsEvidence"])
        self.assertFalse(correction["otherValidatorRuleChanged"])
        contract = self.value["captureContract"]
        self.assertFalse(contract["captureAdapterChangedFromFirstDispatch"])
        self.assertFalse(contract["breakpointSelectionChangedFromFirstDispatch"])
        self.assertFalse(contract["exactCodeHashesChangedFromFirstDispatch"])
        self.assertFalse(contract["eventBoundChangedFromFirstDispatch"])

    def test_four_exact_configurations_are_fresh_and_materialize_only(self) -> None:
        cases = self.value["prospectiveCases"]
        self.assertEqual(len(cases), 4)
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
                ("clear", "light", "materialize", "circle-408-center"),
                ("clear", "dark", "materialize", "circle-640-phase-0501"),
                ("regular", "light", "materialize", "circle-768-center"),
                ("regular", "dark", "materialize", "circle-1535-center"),
            },
        )
        for case in cases:
            self.assertFalse(case["exactConfigurationPreviouslyCaptured"])
            self.assertFalse(case["appleOutputAvailableAtFreeze"])
            self.assertIsNone(case["expectedMarginF64"])
            self.assertIsNone(case["expectedMarginF32"])
            self.assertIsNone(case["expectedWriterPointers"])
            self.assertIsNone(case["expectedCallerIdentity"])
        self.assertIsNone(self.value["runtimeOutcomeFrozenBeforeDispatch"])

    def test_failure_antecedent_did_not_open_the_candidate(self) -> None:
        antecedent = self.value["antecedentFailure"]
        self.assertEqual(antecedent["runID"], 31109847952)
        self.assertFalse(antecedent["candidateTested"])
        self.assertFalse(antecedent["candidateMarginValuesReadForDiagnosis"])
        self.assertEqual(antecedent["modelEntryStorePointerMatchCount"], 527)
        self.assertEqual(antecedent["opaqueX2EqualsRenderX21Count"], 0)

    def test_every_frozen_implementation_hash_is_current(self) -> None:
        entries = self.value["frozenImplementation"]["files"]
        self.assertGreaterEqual(len(entries), 6)
        paths = set()
        for entry in entries:
            path = ROOT / entry["path"]
            self.assertTrue(path.is_file(), entry["path"])
            self.assertNotIn(entry["path"], paths)
            paths.add(entry["path"])
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                entry["sha256"],
                entry["path"],
            )

    def test_quality_locks_and_non_authority_remain_exact(self) -> None:
        implementation = self.value["frozenImplementation"]
        expected = {
            "productionShader": (
                "../shaders/frag.glsl",
                "6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d",
            ),
            "walleFlake": (
                "../flake.nix",
                "b166e3c3ca8cca1e9e83544ab30d47c62b1b25fdef37783dcc2183e46669fa01",
            ),
        }
        for key, (external, digest) in expected.items():
            lock = implementation[key]
            self.assertEqual(lock["externalPath"], external)
            self.assertEqual(lock["sha256"], digest)
            self.assertFalse(lock["changed"])
            path = ROOT / external
            if path.is_file():
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
        authority = self.value["productAuthority"]
        for key in (
            "setterCallerArithmeticMayBeDeclaredDecoded",
            "independentTemporalInputGenerationMayBeClaimed",
            "capturedInputOpticalParityMayBeClaimedByThisGate",
            "physicalOutputTransferMayBeClaimed",
            "independentWalleZeroByteParityMayBeClaimed",
            "productionShaderMayChange",
            "liquidGlassParityMayBeClaimed",
        ):
            self.assertFalse(authority[key], key)


if __name__ == "__main__":
    unittest.main()
