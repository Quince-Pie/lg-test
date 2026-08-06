#!/usr/bin/env python3
"""Tests for the exact FilterOp profile-transfer retry validator."""

from __future__ import annotations

import ast
import struct
import unittest
from pathlib import Path
from unittest import mock

import analyze_prepare_layer_filter_map_bounds_exact_replay as exact
import validate_prepare_layer_filter_map_bounds_profile_transfer_retry as retry


SOURCE_PATH = (
    Path(__file__).resolve().parent
    / "validate_prepare_layer_filter_map_bounds_profile_transfer_retry.py"
)


def timeline_record(
    blur: float,
    bleed: float,
    *,
    foreground_present: bool | None = None,
) -> dict:
    foreground = {}
    if foreground_present is not None:
        foreground["filterPresent"] = foreground_present
    return {
        "filter": {
            "inputValues": {
                "inputBlurRadius": blur,
                "inputBleedBlurRadius": bleed,
            }
        },
        "foregroundFilter": foreground,
    }


class PrepareLayerFilterMapBoundsProfileTransferRetryValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_sdf_parameters_are_frozen_as_exact_float32_bytes(self) -> None:
        self.assertEqual(
            struct.unpack(
                "<4f", bytes.fromhex(retry.EXPECTED_SDF_PARAMETERS_HEX["clear"])
            ),
            (9.0, 0.0, 0.0, 0.0),
        )
        self.assertEqual(
            struct.unpack(
                "<4f", bytes.fromhex(retry.EXPECTED_SDF_PARAMETERS_HEX["regular"])
            ),
            (42.46388244628906, 0.0, 0.0, 0.0),
        )
        self.assertEqual(retry.SDF_PARAMETERS_OFFSET, 0x7F0)
        self.assertEqual(retry.SDF_STATE_STORE_INDEX_DELTA_FROM_MIRROR, -1)
        self.assertEqual(retry.SDF_STATE_ROLE_DELTA_FROM_MIRROR, -0x800)
        self.assertEqual(retry.SDF_STATE_DEPTH_DELTA_FROM_MIRROR, 1)

    def test_regular_filter_radius_uses_half_bleed(self) -> None:
        record = timeline_record(0.2500572204589844, 10.002288818359375)
        self.assertEqual(retry.filter_radius(record, "regular"), 5.0011444091796875)
        self.assertEqual(retry.filter_radius(record, "clear"), 10.002288818359375)

    def test_regular_materialize_endpoint_vector_is_bit_exact(self) -> None:
        transformed = (
            104.67859649658203,
            103.8243179321289,
            815.4970855712891,
            815.4970855712891,
        )
        carrier = (-499.42713928222656, 524.5728607177734)
        mirror_nominal = (8.0, 0.0, -280.0759336749057, -280.0759336749057)
        record = timeline_record(0.12572860717773438, 5.029144287109375)
        offset, applied = retry.endpoint_y_offset(
            "regular", "materialize", 6, record, mirror_nominal
        )
        self.assertTrue(applied)
        self.assertEqual(offset, -0.07593367490568426)
        parameters = struct.unpack(
            "<4f", bytes.fromhex(retry.EXPECTED_SDF_PARAMETERS_HEX["regular"])
        )
        entry = retry.sdf_entry(transformed, parameters, offset)
        candidate = exact.replay(
            entry,
            carrier,
            retry.REGULAR_SOURCE_BOUNDS,
            8.0,
            retry.filter_radius(record, "regular"),
        )
        self.assertEqual(
            exact.f64_hex(candidate),
            "00000020ab6d6b40c0ce2a8e6aa44a400000009c0672874014531d8f4e7a8740",
        )

    def test_endpoint_selector_uses_only_live_state_direction_and_depth(self) -> None:
        nominal = (8.0, 0.0, -280.0528221121284, -280.0528221121284)
        live = timeline_record(1.0, 2.0)
        static = timeline_record(1.0, 2.0, foreground_present=False)
        self.assertEqual(
            retry.endpoint_y_offset("regular", "dematerialize", 7, live, nominal),
            (-0.05282211212841048, True),
        )
        self.assertEqual(
            retry.endpoint_y_offset("regular", "dematerialize", 6, live, nominal),
            (0.0, False),
        )
        self.assertEqual(
            retry.endpoint_y_offset("regular", "dematerialize", 7, static, nominal),
            (0.0, False),
        )
        self.assertEqual(
            retry.endpoint_y_offset("clear", "dematerialize", 7, live, nominal),
            (0.0, False),
        )

    def test_profile_and_reverse_topology_are_authenticated_then_restored(self) -> None:
        actual_timeline = {
            "material": "regular",
            "appearance": "dark",
            "direction": "dematerialize",
        }
        original_topology = (
            retry.crop_validator.EXPECTED_NORMAL_PREPARE_RECURSION_DEPTHS
        )

        def base_timeline(timeline, geometry):
            self.assertEqual(timeline["material"], "clear")
            self.assertEqual(timeline["appearance"], "light")
            self.assertEqual(timeline["direction"], "materialize")
            return {"name": geometry}, []

        def base_validate(_trace, _timeline, geometry):
            self.assertEqual(
                retry.crop_validator.EXPECTED_NORMAL_PREPARE_RECURSION_DEPTHS,
                retry.DEMATERIALIZE_NORMAL_PREPARE_RECURSION_DEPTHS,
            )
            retry.crop_validator.validate_timeline(actual_timeline, geometry)
            return {"geometry": {"name": geometry}}

        def load_json(_path, label):
            return actual_timeline if label == "timeline" else {}

        with (
            mock.patch.object(retry.crop_validator, "validate_timeline", base_timeline),
            mock.patch.object(retry.crop_validator, "validate", base_validate),
            mock.patch.object(retry.crop_validator, "load_json", load_json),
        ):
            installed = retry.crop_validator.validate_timeline
            retry.validate_base(
                Path("trace"),
                Path("timeline"),
                "circle-800-center",
                "regular",
                "dark",
                "dematerialize",
            )
            self.assertIs(retry.crop_validator.validate_timeline, installed)
            self.assertEqual(
                retry.crop_validator.EXPECTED_NORMAL_PREPARE_RECURSION_DEPTHS,
                original_topology,
            )

    def test_no_tolerance_or_product_parity_authority_is_present(self) -> None:
        self.assertNotIn('"liquidGlassParityEstablished": True', self.source)
        self.assertNotIn('"productionShaderAuthorized": True', self.source)
        self.assertNotIn("isclose(", self.source)
        self.assertNotIn("approx", self.source.lower())
        self.assertIn('"toleranceUsed": False', self.source)
        self.assertIn("cropOrProducerValuesUsedForSelection", self.source)


if __name__ == "__main__":
    unittest.main()
