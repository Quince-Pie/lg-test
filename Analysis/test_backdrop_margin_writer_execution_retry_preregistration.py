"""Integrity tests for the superseding material-specific fresh holdout."""

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

    def test_v1_was_superseded_before_any_dispatch(self) -> None:
        self.assertEqual(
            self.value[
                "backdropMarginWriterExecutionRetryPreregistrationSchemaVersion"
            ],
            2,
        )
        supersession = self.value["supersedesUndispatchedVersion"]
        self.assertEqual(supersession["commit"], "c7e1a3f")
        self.assertEqual(supersession["workflowDispatchCountBeforeSupersession"], 0)
        self.assertFalse(supersession["appleOutputForProspectiveCasesAvailable"])

    def test_opened_calibration_selects_a_material_specific_law(self) -> None:
        calibration = self.value["openedCalibration"]
        result_path = ROOT / calibration["result"]
        self.assertTrue(result_path.is_file())
        self.assertEqual(
            hashlib.sha256(result_path.read_bytes()).hexdigest(),
            calibration["resultSHA256"],
        )
        self.assertTrue(calibration["openedAppleWriterValuesUsedToChooseCandidate"])
        self.assertFalse(calibration["prospectiveCaseOutputUsedToChooseCandidate"])
        self.assertTrue(calibration["universalTransitionMaximumLawDisproved"])
        self.assertEqual(calibration["clearAllSetterEventCount"], 154)
        self.assertEqual(calibration["clearAllSetterF64RawLittleEndianHex"], "0" * 16)
        candidate = self.value["frozenCandidate"]
        self.assertEqual(
            candidate["materialSelector"],
            {
                "clear": "exact binary64 +0.0",
                "regular": ("maximum over all 32 retained per-record required margins"),
            },
        )
        self.assertTrue(candidate["candidateCalibratedFromOpenedAppleWriterValues"])
        self.assertFalse(candidate["prospectiveCaseOutputUsedToChooseCandidate"])

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
            self.assertIsNone(case["expectedProducerIdentity"])
        self.assertIsNone(self.value["runtimeOutcomeFrozenBeforeDispatch"])

    def test_abi_join_and_producer_selection_are_structural(self) -> None:
        correction = self.value["abiCorrection"]
        self.assertFalse(correction["candidateMarginValueUsed"])
        self.assertFalse(correction["cropValueUsed"])
        self.assertFalse(correction["imageValueUsed"])
        self.assertTrue(correction["opaqueX2RetainedAsEvidence"])
        contract = self.value["captureContract"]
        self.assertTrue(contract["captureAdapterChangedFromFirstDispatch"])
        self.assertTrue(contract["frozenBaseCaptureAdapterUnchanged"])
        self.assertFalse(contract["breakpointSelectionChangedFromFirstDispatch"])
        self.assertFalse(contract["exactCodeHashesChangedFromFirstDispatch"])
        self.assertFalse(contract["eventBoundChangedFromFirstDispatch"])
        self.assertFalse(contract["producerSelectedByCapturedMargin"])
        self.assertEqual(contract["producerSelfOffsetFromStackPointer"], 0x160)
        self.assertEqual(contract["producerSelfSnapshotByteCount"], 0x60)
        caller = contract["openedSetterCaller"]
        self.assertEqual(caller["returnSymbolOffset"], 5772)
        self.assertEqual(caller["producerCallSymbolOffset"], 5760)
        self.assertEqual(caller["bridgeInstructionHex"], "e0031caa")
        self.assertEqual(caller["setterCallSymbolOffset"], 5768)

    def test_every_frozen_implementation_hash_is_current(self) -> None:
        entries = self.value["frozenImplementation"]["files"]
        self.assertGreaterEqual(len(entries), 10)
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
