#!/usr/bin/env python3
"""Tests for the exact local case-22 provider validator."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import validate_backdrop_margin_case22_provider_local_macos_26_6_1 as validator


ANALYSIS = Path(__file__).parent
PREREGISTRATION = (
    ANALYSIS / "backdrop_margin_case22_provider_local_macos_26_6_1_preregistration.json"
)
EVIDENCE = (
    ANALYSIS.parent.parent
    / "artifacts/mac-quince-macos-26.6.1-case22-provider-passed-42f9413"
    / "backdrop-margin-writer-trace.json"
)


class LocalMacOSCase22ProviderValidatorTests(unittest.TestCase):
    def test_preregistration_is_exact_and_fail_closed(self) -> None:
        value = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
        validator.validate_preregistration(value, ANALYSIS.parent)
        value["selection"]["capturedMarginUsedForRuntimeSelection"] = True
        with self.assertRaisesRegex(ValueError, "selection field"):
            validator.validate_preregistration(value, ANALYSIS.parent)

    def test_dispatch_branch_decodes_exactly(self) -> None:
        address = 0x2493B4F4C
        target = validator.decode_b_target("5afcff17", address)
        self.assertEqual(target, address - 3736)
        with self.assertRaisesRegex(ValueError, "not B"):
            validator.decode_b_target("00000000", address)

    @unittest.skipUnless(EVIDENCE.exists(), "local Mac evidence is external")
    def test_opened_trace_passes_without_product_authority(self) -> None:
        result = validator.validate(EVIDENCE, PREREGISTRATION)
        self.assertEqual(result["conclusion"], "success")
        self.assertEqual(result["providerExecution"]["instructionStateCount"], 74)
        self.assertEqual(result["providerExecution"]["helperCalleeCount"], 1)
        self.assertTrue(
            result["sealedConclusion"]["selectedProviderArithmeticMayBeDecoded"]
        )
        for key in (
            "publicInputMarginLawDecoded",
            "unobservedProviderBranchesMapped",
            "capturedInputOpticalParityPassed",
            "physicalOutputTransferPassed",
            "independentWalleZeroByteFrameParityPassed",
            "productionShaderAuthorized",
            "liquidGlassParityEstablished",
        ):
            self.assertFalse(result["sealedConclusion"][key])


if __name__ == "__main__":
    unittest.main()
