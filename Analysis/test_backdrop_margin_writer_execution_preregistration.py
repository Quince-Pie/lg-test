"""Integrity tests for the frozen writer-execution holdout."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
ROOT = ANALYSIS.parent
PREREGISTRATION = ANALYSIS / "backdrop_margin_writer_execution_preregistration.json"


class BackdropMarginWriterExecutionPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))

    def test_candidate_and_matrix_are_frozen_before_apple_outputs(self) -> None:
        self.assertEqual(
            self.value[
                "backdropMarginWriterExecutionPreregistrationSchemaVersion"
            ],
            1,
        )
        candidate = self.value["frozenCandidate"]
        self.assertEqual(
            candidate["perRecordRequiredMargin"],
            "max(inputBleedAmount, inputShadowAmount + "
            "max(abs(inputShadowOffset.x), abs(inputShadowOffset.y)))",
        )
        self.assertFalse(candidate["capturedTargetValueUsedToChooseCandidate"])
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
                ("clear", "light", "materialize", "circle-347-center"),
                ("clear", "dark", "dematerialize", "circle-640-fractional"),
                ("regular", "light", "dematerialize", "circle-769-center"),
                ("regular", "dark", "materialize", "circle-896-center"),
            },
        )
        for case in cases:
            self.assertFalse(case["casePresentInAntecedentCorpus"])
            self.assertFalse(case["appleOutputAvailableAtFreeze"])
            self.assertIsNone(case["expectedMarginF64"])
            self.assertIsNone(case["expectedMarginF32"])
            self.assertIsNone(case["expectedWriterPointers"])
            self.assertIsNone(case["expectedCallerIdentity"])
        self.assertIsNone(self.value["runtimeOutcomeFrozenBeforeDispatch"])

    def test_antecedent_is_the_authenticated_opening_run(self) -> None:
        antecedent = self.value["antecedent"]
        self.assertEqual(antecedent["runID"], 31090638908)
        self.assertEqual(
            antecedent["headSHA"],
            "a27444af9bf97ccaf0c03568f91a962d0170f051",
        )
        self.assertEqual(antecedent["retrospectiveRecordCount"], 480)
        self.assertEqual(antecedent["retrospectiveCandidateMismatchCount"], 0)
        self.assertFalse(antecedent["selectedWriterExecutionAuthenticated"])
        self.assertFalse(antecedent["prospectiveUnseenTransferPassed"])

    def test_every_frozen_implementation_hash_is_current(self) -> None:
        entries = self.value["frozenImplementation"]["files"]
        self.assertGreaterEqual(len(entries), 7)
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

    def test_product_quality_locks_are_immutable(self) -> None:
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

    def test_gate_grants_no_shader_or_parity_authority(self) -> None:
        authority = self.value["productAuthority"]
        self.assertTrue(
            authority[
                "transitionMaximumCandidateMayBeAcceptedForCapturedInputsAfterAllFourPass"
            ]
        )
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
