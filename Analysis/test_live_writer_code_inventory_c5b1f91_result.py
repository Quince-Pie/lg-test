"""Integrity checks for the value-blind live writer code inventory."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
ROOT = ANALYSIS.parent
RESULT = ANALYSIS / "live_writer_code_inventory_c5b1f91_result.json"


class LiveWriterCodeInventoryResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_inputs_match(self) -> None:
        for record in self.value["inputs"].values():
            path = ROOT / record["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record["sha256"])

    def test_critical_copy_sequence_is_exact(self) -> None:
        copy = self.value["quartzCore"]["copy"]
        self.assertEqual(copy["byteCount"], 1640)
        self.assertEqual(copy["binary64ToBinary32InstructionHex"], "0040621e")
        self.assertEqual(copy["marginStoreInstructionHex"], "a02600bd")
        self.assertEqual(copy["marginStoreDestination"], "render object +0x24")
        self.assertTrue(copy["historicalByteCountMatched"])
        self.assertFalse(copy["historicalSHA256Matched"])
        self.assertTrue(self.value["quartzCore"]["bounds"]["historicalSHA256Matched"])

    def test_inventory_has_only_structural_authority(self) -> None:
        contract = self.value["captureContract"]
        self.assertTrue(contract["processStoppedAtExecutableMain"])
        self.assertFalse(contract["processContinuedAfterMain"])
        self.assertFalse(contract["registerOrObjectRead"])
        self.assertFalse(contract["marginCropImageOrPixelRead"])
        authority = self.value["authority"]
        self.assertTrue(authority["liveQuartzCoreWriterCodeAuthenticated"])
        for key in (
            "allocationMarginCompositionEstablished",
            "selectedRegionPolicyEstablished",
            "physicalRetinaColorPixelCompositorTransferEstablished",
            "independentWalleZeroByteFrameParityEstablished",
            "productionShaderAuthorized",
            "liquidGlassParityEstablished",
        ):
            self.assertFalse(authority[key], key)


if __name__ == "__main__":
    unittest.main()
