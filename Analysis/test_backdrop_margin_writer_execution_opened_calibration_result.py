"""Integrity tests for the opened two-profile writer calibration."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import validate_backdrop_margin_writer_execution_retry as retry


RESULT = Path(__file__).with_name(
    "backdrop_margin_writer_execution_opened_calibration_result.json"
)


class BackdropMarginWriterExecutionOpenedCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_artifact_identity_and_undispatched_supersession_are_immutable(
        self,
    ) -> None:
        self.assertEqual(
            self.value[
                "backdropMarginWriterExecutionOpenedCalibrationResultSchemaVersion"
            ],
            1,
        )
        self.assertEqual(self.value["run"]["runID"], 31109847952)
        self.assertEqual(
            {artifact["artifactID"] for artifact in self.value["artifacts"]},
            {8971372675, 8971354085},
        )
        audit = self.value["retrySupersessionAudit"]
        self.assertEqual(audit["initialRetryCommit"], "c7e1a3f")
        self.assertEqual(audit["workflowDispatchCountBeforeSupersession"], 0)
        self.assertFalse(audit["prospectiveCaseAppleOutputAvailable"])

    def test_clear_and_regular_select_distinct_exact_laws(self) -> None:
        profiles = self.value["profiles"]
        clear = profiles["clear-light-materialize-circle-347-center"]
        self.assertEqual(clear["marginSetterEventCount"], 154)
        self.assertEqual(clear["copyMarginStoreEventCount"], 277)
        self.assertEqual(clear["backdropBoundsEventCount"], 288)
        self.assertEqual(clear["allMarginSetterF64RawLittleEndianHex"], "0" * 16)
        self.assertEqual(clear["allCopyStoreF32RawLittleEndianHex"], "0" * 8)
        self.assertEqual(clear["allGetBoundsF32RawLittleEndianHex"], "0" * 8)
        self.assertEqual(clear["capturedInputTransitionMaximumF64"], 83.0)
        self.assertEqual(clear["structurallyCompleteChainCount"], 32)
        self.assertEqual(clear["exactZeroChainCount"], 32)

        regular = profiles["regular-dark-materialize-circle-896-center"]
        self.assertEqual(regular["marginSetterEventCount"], 138)
        self.assertEqual(regular["copyMarginStoreEventCount"], 250)
        self.assertEqual(regular["backdropBoundsEventCount"], 320)
        self.assertEqual(
            regular["capturedInputTransitionMaximumF64RawLittleEndianHex"],
            "9999999999997340",
        )
        self.assertEqual(
            regular["capturedInputTransitionMaximumF32RawLittleEndianHex"],
            "cdcc9c43",
        )
        self.assertEqual(regular["transitionMaximumBitExactChainCount"], 32)
        self.assertEqual(regular["transitionMaximumGetBoundsEventCount"], 320)

    def test_shared_caller_call_site_decodes_to_frozen_relative_targets(
        self,
    ) -> None:
        caller = self.value["sharedCaller"]
        self.assertEqual(caller["moduleUUID"], retry.SWIFTUICORE_UUID)
        self.assertEqual(caller["symbolByteCount"], retry.CALLER_BYTE_COUNT)
        self.assertEqual(caller["codeSHA256"], retry.CALLER_CODE_SHA256)
        self.assertEqual(
            caller["setterReturnSymbolOffset"],
            retry.CALLER_RETURN_SYMBOL_OFFSET,
        )
        by_offset = {
            instruction["symbolOffset"]: instruction
            for instruction in caller["callSiteInstructions"]
        }
        symbol_start = 0x100000000
        producer_address = symbol_start + 5760
        setter_address = symbol_start + 5768
        producer_target = retry.decode_bl_target(
            by_offset[5760]["instructionHex"], producer_address
        )
        setter_target = retry.decode_bl_target(
            by_offset[5768]["instructionHex"], setter_address
        )
        module_load = symbol_start - caller["symbolStartModuleOffset"]
        self.assertEqual(
            producer_target - module_load,
            by_offset[5760]["targetModuleOffset"],
        )
        self.assertEqual(
            setter_target - module_load,
            by_offset[5768]["targetModuleOffset"],
        )
        self.assertEqual(
            by_offset[5764]["instructionHex"],
            retry.PRODUCER_BRIDGE_INSTRUCTION_HEX,
        )

    def test_calibration_grants_no_product_authority(self) -> None:
        sealed = self.value["sealedConclusion"]
        self.assertTrue(sealed["universalTransitionMaximumLawDisproved"])
        self.assertTrue(sealed["clearExactZeroLawCalibrated"])
        self.assertTrue(sealed["regularTransitionMaximumLawCalibrated"])
        self.assertFalse(sealed["materialSpecificLawProspectivelyValidated"])
        self.assertFalse(sealed["adjacentProducerArithmeticDecoded"])
        self.assertFalse(sealed["productionShaderAuthorized"])
        self.assertFalse(sealed["liquidGlassParityEstablished"])


if __name__ == "__main__":
    unittest.main()
