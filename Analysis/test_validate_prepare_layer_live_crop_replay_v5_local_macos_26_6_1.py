#!/usr/bin/env python3
"""Contracts for public-backdrop-bound crop replay v5."""

import json
import struct
import tempfile
import unittest
from pathlib import Path

import validate_prepare_layer_live_crop_replay_v5_local_macos_26_6_1 as validator


class PrepareLayerLiveCropReplayV5Tests(unittest.TestCase):
    def test_gaussian_shadow_expansion_matches_live_stage_word(self) -> None:
        opacity = 0.0082786083221435547
        radius = 0.79474639892578125
        factor = validator.gaussian_expansion_factor(opacity)
        expansion = factor * radius
        self.assertEqual(factor.hex(), "0x1.227ebb1e6fdafp-3")
        self.assertEqual(struct.pack("<d", expansion).hex(), "9041a921d6dbbc3f")

    def test_shadow_union_replaces_endpoint_translation_compensation(self) -> None:
        timeline_record = {
            "filter": {
                "inputValues": {
                    "inputBlurRadius": 0.13245773315429688,
                    "inputBleedBlurRadius": 5.298309326171875,
                    "inputShadowOpacity": 0.0082786083221435547,
                    "inputShadowRadius": 0.79474639892578125,
                    "inputShadowOffset": {
                        "lengthBytes": 16,
                        "hex": "00000000000000000000000000002040",
                    },
                }
            }
        }
        radius = validator.shadow_aware_filter_radius(timeline_record, "regular")
        replay = validator.exact_filter_replay(
            (
                212.55553913116455,
                213.0465269088745,
                598.3979339599609,
                598.3979339599609,
            ),
            (-503.754506111145, 520.245493888855),
            (
                -174.30000305175776,
                -174.30000305175776,
                846.6000061035156,
                846.6000061035156,
            ),
            8.0,
            radius,
        )
        self.assertEqual(
            replay,
            (
                329.45450305938726,
                204.9337974708385,
                488.91660308837885,
                489.61169946977424,
            ),
        )

    def test_backdrop_bounds_replay_uses_exact_observed_order(self) -> None:
        public = validator.v2.RegularGeometryModel(
            width=498.0,
            height=498.0,
            terminal_bleed=174.29999999999998,
            source_bounds=(0.0, 0.0, 0.0, 0.0),
            recursive_child=(0.0, 0.0, 0.0, 0.0),
        )
        raw = (
            2.0**-44,
            2.0**-44,
            498.0 - 2.0**-44,
            498.0 - 2.0**-44,
        )
        model = validator.backdrop_geometry_model(public, raw)
        self.assertEqual(model.terminal_bleed, 174.3000030517578)
        self.assertEqual(
            model.source_bounds,
            (
                -174.30000305175776,
                -174.30000305175776,
                846.6000061035156,
                846.6000061035156,
            ),
        )
        self.assertEqual(
            model.recursive_child,
            (0.0, 0.0, 846.6000061035156, 846.6000061035156),
        )

    def test_public_bounds_select_unique_stable_backdrop_layer(self) -> None:
        bounds = [2.0**-44, 2.0**-44, 498.0 - 2.0**-44, 498.0 - 2.0**-44]
        records = []
        for sample in range(1, validator.EXPECTED_RECORD_COUNT + 1):
            state = {
                "class": validator.BACKDROP_LAYER_CLASS,
                "path": [1, 0, 1, 0],
                "bounds": bounds,
            }
            records.append(
                {
                    "sampleIndex": sample,
                    "render": {
                        "liveRenderBoundaryBefore": {"layerStates": [state]},
                        "liveRenderBoundaryAfter": {"layerStates": [state]},
                    },
                }
            )
        payload = {
            "material": "regular",
            "geometry": {"name": "circle-498-center"},
            "dynamicBackgroundUniforms": {"records": records},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "timeline.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            selected, layer_path = validator.public_backdrop_bounds(
                path, "circle-498-center"
            )
        self.assertEqual(selected, tuple(bounds))
        self.assertEqual(layer_path, [1, 0, 1, 0])

    def test_source_declares_no_crop_or_producer_selection(self) -> None:
        source = Path(validator.__file__).read_text(encoding="utf-8")
        self.assertIn('model["cropOrProducerValuesUsed"] = False', source)
        self.assertIn('metadata["cropOrProducerValuesUsedByV5Model"] = False', source)
        self.assertIn('metadata["toleranceUsedByV5Model"] = False', source)
        self.assertIn('endpoint["legacyEndpointTranslationFalsified"] = True', source)
        self.assertNotIn("isclose(", source)

    def test_binary32_margin_round_trip_is_explicit(self) -> None:
        public = 174.29999999999998
        expected = struct.unpack("<f", struct.pack("<f", public))[0]
        self.assertEqual(expected, validator.v3._binary32_promoted(public))


if __name__ == "__main__":
    unittest.main()
