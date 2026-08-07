#!/usr/bin/env python3
"""Exact precision-boundary tests for live crop replay v3."""

from pathlib import Path
import unittest

import validate_prepare_layer_live_crop_replay_v2_local_macos_26_6_1 as v2
import validate_prepare_layer_live_crop_replay_v3_local_macos_26_6_1 as validator


class PrepareLayerLiveCropReplayV3Tests(unittest.TestCase):
    def test_opened_487_precision_discriminator(self) -> None:
        public = v2.RegularGeometryModel(
            width=487.0,
            height=487.0,
            terminal_bleed=170.45,
            source_bounds=(-170.45, -170.45, 827.9, 827.9),
            recursive_child=(0.0, 0.0, 827.9, 827.9),
        )
        internal = validator._internal_geometry_model(public)
        self.assertEqual(internal.terminal_bleed, 170.4499969482422)
        self.assertEqual(
            internal.source_bounds,
            (
                -170.4499969482422,
                -170.4499969482422,
                827.8999938964844,
                827.8999938964844,
            ),
        )
        self.assertEqual(
            v2.exact.f64_hex(internal.source_bounds),
            "00000060664e65c000000060664e65c00000003033df89400000003033df8940",
        )

    def test_binary32_exact_inputs_remain_unchanged(self) -> None:
        for public in (169.75, 280.0):
            self.assertEqual(validator._binary32_promoted(public), public)

    def test_geometry_patch_restores_v2_model_after_exception(self) -> None:
        original = v2._regular_geometry_model
        model = v2.RegularGeometryModel(
            width=487.0,
            height=487.0,
            terminal_bleed=170.4499969482422,
            source_bounds=(
                -170.4499969482422,
                -170.4499969482422,
                827.8999938964844,
                827.8999938964844,
            ),
            recursive_child=(0.0, 0.0, 827.8999938964844, 827.8999938964844),
        )
        path = Path("timeline.json")
        with self.assertRaisesRegex(RuntimeError, "deliberate"):
            with validator._geometry_model_patch(model, path, "circle-487-center"):
                self.assertIs(
                    v2._regular_geometry_model(path, "circle-487-center"), model
                )
                raise RuntimeError("deliberate")
        self.assertIs(v2._regular_geometry_model, original)


if __name__ == "__main__":
    unittest.main()
