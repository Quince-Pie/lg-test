#!/usr/bin/env python3
"""Tests for the active-M1 crop profile validator adapter."""

import unittest

import prepare_layer_live_transport_local_macos_26_6_1 as live
import validate_prepare_layer_filter_map_bounds_profile_transfer_live_local_macos_26_6_1 as validator


class PrepareLayerLiveProfileValidatorTests(unittest.TestCase):
    def test_configuration_uses_only_frozen_live_code_translation(self) -> None:
        validator._configure_live_validators()
        crop = validator.profile.crop_validator
        union = validator.profile.union_validator
        store = validator.profile.store_validator
        self.assertEqual(
            crop.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
            live.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
        )
        self.assertEqual(
            crop.PREPARE_LAYER_FULL_CODE_SHA256,
            live.PREPARE_LAYER_FULL_CODE_SHA256,
        )
        self.assertEqual(union.UNION_CALL_OFFSET, live.UNION_CALL_OFFSET)
        self.assertEqual(union.UNION_RETURN_OFFSET, live.UNION_RETURN_OFFSET)
        self.assertEqual(store.STORE_OFFSET, live.STORE_OFFSET)

    def test_adapter_grants_no_crop_or_product_authority(self) -> None:
        source = validator.Path(validator.__file__).read_text(encoding="utf-8")
        self.assertNotIn('"selectedRegionOriginTransferPassed"] = True', source)
        self.assertNotIn('"productionShaderAuthorized"] = True', source)
        self.assertNotIn('"liquidGlassParityEstablished"] = True', source)
        self.assertNotIn("isclose(", source)


if __name__ == "__main__":
    unittest.main()
