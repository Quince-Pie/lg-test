#!/usr/bin/env python3
"""Exact endpoint-grouping tests for live crop replay v4."""

import unittest

import validate_prepare_layer_live_crop_replay_v3_local_macos_26_6_1 as v3
import validate_prepare_layer_live_crop_replay_v4_local_macos_26_6_1 as validator


class PrepareLayerLiveCropReplayV4Tests(unittest.TestCase):
    def test_circle_497_endpoint_discriminator_matches_apple_bits(self) -> None:
        entry = validator.ExactSDFEntry(
            (
                255.7866678237915,
                255.72648525238037,
                512.4868469238281,
                512.4868469238281,
            ),
            (42.46388244628906, 0.0, 0.0, 0.0),
            -0.09005647907832781,
        )
        carrier = (-504.03009128570557, 519.9699087142944)
        replay = v3.v2.exact_filter_replay(
            entry,
            carrier,
            (
                -173.9499969482422,
                -173.9499969482422,
                844.8999938964844,
                844.8999938964844,
            ),
            8.0,
            2.565765380859375,
        )
        self.assertEqual(
            v3.v2.exact.f64_hex(replay),
            "0000001148a1744018f2df7f85a5694000000090767d7e40f406102ff58b7e40",
        )

    def test_v3_left_association_is_observably_wrong(self) -> None:
        entry = v3.v2.ExactSDFEntry(
            (
                255.7866678237915,
                255.72648525238037,
                512.4868469238281,
                512.4868469238281,
            ),
            (42.46388244628906, 0.0, 0.0, 0.0),
            -0.09005647907832781,
        )
        replay = v3.v2.exact_filter_replay(
            entry,
            (-504.03009128570557, 519.9699087142944),
            (
                -173.9499969482422,
                -173.9499969482422,
                844.8999938964844,
                844.8999938964844,
            ),
            8.0,
            2.565765380859375,
        )
        self.assertEqual(
            v3.v2.exact.f64_hex(replay),
            "0000001148a174401af2df7f85a5694000000090767d7e40f306102ff58b7e40",
        )

    def test_endpoint_patch_restores_v3_factory_after_exception(self) -> None:
        original = v3.v2.exact_sdf_entry
        with self.assertRaisesRegex(RuntimeError, "deliberate"):
            with validator._endpoint_grouping_patch():
                self.assertIs(v3.v2.exact_sdf_entry, validator.exact_sdf_entry)
                raise RuntimeError("deliberate")
        self.assertIs(v3.v2.exact_sdf_entry, original)


if __name__ == "__main__":
    unittest.main()
