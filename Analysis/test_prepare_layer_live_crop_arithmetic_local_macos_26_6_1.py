#!/usr/bin/env python3
"""Contracts for the frozen live crop-arithmetic code inventory."""

import json
from pathlib import Path
import unittest

import prepare_layer_live_crop_arithmetic_local_macos_26_6_1 as arithmetic


INVENTORY_PATH = Path(__file__).with_name(
    "prepare_layer_live_crop_arithmetic_code_inventory_a3ac528_result.json"
)


class PrepareLayerLiveCropArithmeticTests(unittest.TestCase):
    def test_inventory_and_shared_identity_are_identical(self) -> None:
        inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            inventory["prepareLayerLiveCropArithmeticCodeInventorySchemaVersion"],
            arithmetic.IDENTITY_SCHEMA_VERSION,
        )
        self.assertEqual(
            inventory["host"]["quartzCoreUUID"], arithmetic.QUARTZCORE_UUID
        )
        self.assertEqual(inventory["records"], arithmetic.frozen_code_records())

    def test_inventory_is_value_blind(self) -> None:
        selection = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))["selection"]
        self.assertEqual(
            selection,
            {
                "cropOrProducerValuesUsed": False,
                "imageValuesUsed": False,
                "instructionSteppingUsed": False,
                "symbolNamesAndBoundsOnly": True,
            },
        )


if __name__ == "__main__":
    unittest.main()
