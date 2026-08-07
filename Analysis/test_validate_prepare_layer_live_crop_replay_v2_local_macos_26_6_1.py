#!/usr/bin/env python3
"""Exact arithmetic tests for the live crop replay v2 candidate."""

import unittest

import analyze_prepare_layer_filter_map_bounds_exact_replay as exact
import validate_prepare_layer_filter_map_bounds_profile_transfer_retry as profile
import validate_prepare_layer_live_crop_replay_v2_local_macos_26_6_1 as validator


class PrepareLayerLiveCropReplayV2Tests(unittest.TestCase):
    def test_rare_sdf_rounding_case_matches_live_retina_bytes(self) -> None:
        transformed = (
            261.8149008750915,
            262.18706750869745,
            499.998031616211,
            499.998031616211,
        )
        parameters = (42.46388244628906, 0.0, 0.0, 0.0)
        carrier = (-496.813916683197, 527.186083316803)
        entry = validator.ExactSDFEntry(transformed, parameters, 0.0)

        self.assertEqual(
            exact.f64_hex(entry.resolve(carrier)),
            ("feffff8a3b6b6b400000005524776b4000000008684782400000000868478240"),
        )
        replay = validator.exact_filter_replay(
            entry,
            carrier,
            (-169.75, -169.75, 824.5, 824.5),
            8.0,
            5.0098419189453125,
        )
        self.assertEqual(
            exact.f64_hex(replay),
            ("000080cd057174400000009542b66940ffffffe7d8b37e40000000e8d8b37e40"),
        )

    def test_algebraically_simplified_sdf_y_is_observably_wrong(self) -> None:
        simplified = profile.sdf_entry(
            (
                261.8149008750915,
                262.18706750869745,
                499.998031616211,
                499.998031616211,
            ),
            (42.46388244628906, 0.0, 0.0, 0.0),
            0.0,
        )
        exact_entry = validator.ExactSDFEntry(
            (
                261.8149008750915,
                262.18706750869745,
                499.998031616211,
                499.998031616211,
            ),
            (42.46388244628906, 0.0, 0.0, 0.0),
            0.0,
        ).resolve((-496.813916683197, 527.186083316803))
        self.assertNotEqual(exact.f64_hex(simplified), exact.f64_hex(exact_entry))
        self.assertEqual(simplified[1], 219.7231850624084)
        self.assertEqual(exact_entry[1], 219.72318506240845)

    def test_static_inventory_is_frozen_and_value_blind(self) -> None:
        result = validator._validate_static_inventory()
        self.assertFalse(result["embeddedInTrace"])
        self.assertTrue(result["retrospectiveStaticInventory"])
        self.assertEqual(result["recordCount"], 6)

    def test_candidate_patch_restores_historical_functions(self) -> None:
        model = validator.RegularGeometryModel(
            width=485.0,
            height=485.0,
            terminal_bleed=169.75,
            source_bounds=(-169.75, -169.75, 824.5, 824.5),
            recursive_child=(0.0, 0.0, 824.5, 824.5),
        )
        original_sdf = profile.sdf_entry
        original_replay = exact.replay
        with self.assertRaisesRegex(RuntimeError, "deliberate"):
            with validator._candidate_patch(model):
                self.assertIs(profile.sdf_entry, validator.exact_sdf_entry)
                self.assertIs(exact.replay, validator.exact_filter_replay)
                raise RuntimeError("deliberate")
        self.assertIs(profile.sdf_entry, original_sdf)
        self.assertIs(exact.replay, original_replay)


if __name__ == "__main__":
    unittest.main()
