#!/usr/bin/env python3
"""Contracts for the immutable v2 unseen-crop falsification record."""

import hashlib
import json
from pathlib import Path
import struct
import unittest


ANALYSIS = Path(__file__).resolve().parent
RESULT = ANALYSIS / (
    "prepare_layer_live_crop_replay_v2_a311a12_holdout_falsification_result.json"
)


class PrepareLayerLiveCropReplayV2HoldoutFalsificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_frozen_tracked_inputs_still_match(self) -> None:
        inputs = self.result["inputs"]
        for prefix in ("preregistration", "holdoutValidator", "v2Model"):
            path = ANALYSIS.parent / inputs[f"{prefix}Path"]
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                inputs[f"{prefix}SHA256"],
            )

    def test_opened_precision_boundary_is_exactly_one_binary32_round_trip(self) -> None:
        frozen = self.result["frozenV2Prediction"]
        diagnosis = self.result["openedDiagnosis"]
        public_bleed = frozen["publicTerminalInputBleedAmountF64"]
        internal_bleed = struct.unpack("<f", struct.pack("<f", public_bleed))[0]
        self.assertEqual(internal_bleed, diagnosis["internalBleedF32"])
        self.assertEqual(struct.pack("<f", internal_bleed).hex(), "33732a43")
        self.assertEqual(
            struct.pack("<d", internal_bleed).hex(),
            diagnosis["internalBleedPromotedF64RawLittleEndianHex"],
        )
        corrected = (
            -internal_bleed,
            -internal_bleed,
            487.0 + 2.0 * internal_bleed,
            487.0 + 2.0 * internal_bleed,
        )
        self.assertEqual(list(corrected), diagnosis["correctedSourceBoundsF64"])
        self.assertEqual(
            "".join(struct.pack("<d", value).hex() for value in corrected),
            diagnosis["correctedSourceBoundsHex"],
        )

    def test_failed_holdout_is_never_relabelled_as_a_pass(self) -> None:
        self.assertEqual(self.result["conclusion"], "falsified")
        self.assertEqual(self.result["capture"]["v2ValidationExitStatus"], 1)
        self.assertFalse(
            self.result["observedAppleTarget"]["frozenV2RecursiveChildMatchedBitwise"]
        )
        self.assertTrue(
            self.result["openedDiagnosis"]["targetOutputsUsedToDeriveCorrection"]
        )
        self.assertFalse(
            self.result["openedDiagnosis"]["correctedCandidateProspectivelyEstablished"]
        )
        sealed = self.result["sealedConclusion"]
        self.assertTrue(sealed["v2UnseenGeometryTransferFalsified"])
        for key in (
            "v2UnseenGeometryTransferPassed",
            "v3UnseenGeometryTransferPassed",
            "selectedRegionOriginTransferPassed",
            "physicalRetinaColorTransferPassed",
            "independentWalleZeroByteFrameParityPassed",
            "productionShaderAuthorized",
            "liquidGlassParityEstablished",
        ):
            self.assertFalse(sealed[key], key)


if __name__ == "__main__":
    unittest.main()
