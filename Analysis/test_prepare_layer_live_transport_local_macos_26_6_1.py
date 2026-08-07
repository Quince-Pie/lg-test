#!/usr/bin/env python3
"""Tests for the value-blind active-M1 ``prepare_layer`` mapping."""

import unittest
from types import SimpleNamespace

import prepare_layer_live_transport_local_macos_26_6_1 as live


class PrepareLayerLiveTransportTests(unittest.TestCase):
    def test_live_code_and_semantic_sites_are_exact(self) -> None:
        self.assertEqual(live.PREPARE_LAYER_SYMBOL_BYTE_COUNT, 39_880)
        self.assertEqual(
            live.PREPARE_LAYER_FULL_CODE_SHA256,
            "6949daed1a86b3153cf90afc4d7c6a83f99cb6e5435d6331fc93066caeb337a8",
        )
        self.assertEqual(
            (
                live.MARKER_OFFSET,
                live.STORE_OFFSET,
                live.UNION_CALL_OFFSET,
                live.UNION_RETURN_OFFSET,
            ),
            (0x3EF0, 0x54E0, 0x84E0, 0x84E4),
        )
        self.assertEqual(live.UNION_HELPER_RELATIVE_OFFSET, -0xAA0)

    def test_transport_has_no_algorithm_or_product_authority(self) -> None:
        record = live.transport_record()
        self.assertEqual(record["quartzCoreUUID"], live.QUARTZCORE_UUID)
        self.assertTrue(record["authority"]["captureTransportMayBeClaimed"])
        for key in (
            "cropPolicyMayBeClaimed",
            "selectedRegionOriginTransferMayBeClaimed",
            "productionShaderAuthorized",
            "liquidGlassParityEstablished",
        ):
            self.assertFalse(record["authority"][key], key)
        serialized = repr(record).lower()
        self.assertNotIn("tolerance", serialized)
        self.assertNotIn("rectanglef64", serialized)

    def test_capture_patch_changes_only_code_transport_constants(self) -> None:
        full_path = SimpleNamespace(
            PREPARE_LAYER_SYMBOL_BYTE_COUNT=1,
            KNOWN_PREPARE_LAYER_WINDOWS=(),
        )
        crop = SimpleNamespace(
            capture_base=full_path,
            PREPARE_LAYER_FULL_CODE_SHA256="old",
            MARKER_OFFSET=1,
            MARKER_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX="old",
        )
        union = SimpleNamespace(
            crop_base=crop,
            UNION_CALL_OFFSET=1,
            UNION_CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX="old",
            UNION_RETURN_OFFSET=2,
            UNION_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX="old",
        )
        holdout = SimpleNamespace(
            union_base=union,
            STORE_OFFSET=1,
            STORE_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX="old",
        )
        live.patch_capture_modules(holdout)
        self.assertEqual(
            full_path.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            live.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
        )
        self.assertEqual(crop.MARKER_OFFSET, live.MARKER_OFFSET)
        self.assertEqual(union.UNION_CALL_OFFSET, live.UNION_CALL_OFFSET)
        self.assertEqual(holdout.STORE_OFFSET, live.STORE_OFFSET)


if __name__ == "__main__":
    unittest.main()
