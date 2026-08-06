#!/usr/bin/env python3
"""Prospective contracts for the unlocked complete-matrix validator."""

from __future__ import annotations

import importlib
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
MODULE_NAME = (
    "validate_backdrop_margin_case22_provider_object_matrix_complete_local_macos_26_6_1"
)
SOURCE = (ANALYSIS / f"{MODULE_NAME}.py").read_text(encoding="utf-8")


class CompleteProviderObjectMatrixValidatorSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = importlib.import_module(MODULE_NAME)

    def test_requires_both_exact_unlocked_retina_preflights(self) -> None:
        report = {
            **self.module.EXPECTED_PREFLIGHT,
            "classification": (
                "fail-closed native macOS presentation-session preflight"
            ),
        }
        self.assertEqual(
            self.module.validate_preflight(report, "synthetic preflight")[
                "passed"
            ],
            True,
        )
        report["sessionLocked"] = True
        with self.assertRaisesRegex(ValueError, "sessionLocked"):
            self.module.validate_preflight(report, "synthetic preflight")

    def test_complete_domain_is_an_exact_partition(self) -> None:
        for needle in (
            'trace.get("selectedCallerCalls")',
            "owned_indices == list(range(len(calls)))",
            'call.get("selectedCallerIndex") == selected_index',
            'call.get("providerCallIndexWithinSelectedCaller") == call_offset',
            'trace.get("finalActiveSelectedCallerCount") == 0',
            'trace.get("finalBootstrapObserved") is True',
        ):
            self.assertIn(needle, SOURCE)

    def test_every_object_and_return_join_fails_closed(self) -> None:
        for needle in (
            "provider_address == wrapper_address + 16",
            "wrapper_payload == entry_payload == return_payload",
            "raw_v0[:16] == raw_f64",
            "raw_v0 == group_v0",
            'call.get("providerReturnMatchesGroupBitwise") is True',
            'caller_code[CALLER_CALL_OFFSET : CALLER_CALL_OFFSET + 4].hex()',
        ):
            self.assertIn(needle, SOURCE)

    def test_output_hypotheses_are_reported_without_changing_structure(self) -> None:
        for needle in (
            "selected_return == EXPECTED_SELECTED_RETURN",
            "distinct_returns >= 2",
            "positive_gate_count >= 1",
            "positive_return_count >= 1",
            '"captureContractPassed": capture_contract_passed',
            '"transportAndStructuralIntegrityPassed": True',
        ):
            self.assertIn(needle, SOURCE)

    def test_product_authority_remains_closed(self) -> None:
        for needle in (
            '"completeFiniteProviderLaw": False',
            '"publicInputMappingAuthority": False',
            '"upstreamIntegerCropAllocationPolicy": False',
            '"physicalRetinaColorPixelCompositorTransfer": False',
            '"independentWalleZeroByteFrameParity": False',
            '"productionShaderAuthorized": False',
            '"liquidGlassParityEstablished": False',
        ):
            self.assertIn(needle, SOURCE)


if __name__ == "__main__":
    unittest.main()
