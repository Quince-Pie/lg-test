#!/usr/bin/env python3
"""Unit contracts for the live DOD source decoder."""

import struct
import unittest

import validate_prepare_layer_live_dod_source_capture_local_macos_26_6_1 as validator


class PrepareLayerLiveDODSourceValidatorTests(unittest.TestCase):
    def test_simd_pair_is_bit_exact(self) -> None:
        payload = struct.pack("<2d", -169.74999999999997, 824.5)
        self.assertEqual(
            validator._simd_pair(
                {"byteCount": 16, "hex": payload.hex()}, "synthetic pair"
            ),
            (-169.74999999999997, 824.5),
        )

    def test_no_product_authority_is_granted(self) -> None:
        source = validator.Path(validator.__file__).read_text(encoding="utf-8")
        for forbidden in (
            '"sourceBoundsAlgorithmPassed": True',
            '"selectedRegionOriginTransferPassed": True',
            '"physicalRetinaColorTransferPassed": True',
            '"productionShaderAuthorized": True',
            '"liquidGlassParityEstablished": True',
            "isclose(",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
