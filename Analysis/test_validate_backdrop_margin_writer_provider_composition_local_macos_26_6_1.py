"""Unit tests for the frozen public/provider/writer composition law."""

from __future__ import annotations

import copy
import struct
import unittest

import test_validate_backdrop_margin_writer_execution as fixture
import validate_backdrop_margin_writer_provider_composition_local_macos_26_6_1 as validator


class BackdropMarginWriterProviderCompositionTests(unittest.TestCase):
    def timeline(self, material: str = "regular") -> dict[str, object]:
        value = copy.deepcopy(fixture.timeline())
        value["material"] = material
        value["geometry"] = {"name": "circle-451-center"}
        return value

    def test_regular_candidate_uses_authenticated_provider_order(self) -> None:
        candidate = validator.provider_transition_candidate(
            self.timeline(),
            "regular",
            "light",
            "materialize",
            "circle-451-center",
        )
        self.assertEqual(candidate["recordCount"], 32)
        self.assertEqual(candidate["perRecordProviderLaw"], validator.PROVIDER_LAW)
        self.assertEqual(candidate["maximumRequiredMarginF64"], 83.0)
        self.assertEqual(
            candidate["maximumRequiredMarginF64RawLittleEndianHex"],
            struct.pack("<d", 83.0).hex(),
        )
        self.assertEqual(
            candidate["expectedRenderMarginF32RawLittleEndianHex"],
            struct.pack("<f", 83.0).hex(),
        )
        self.assertFalse(candidate["capturedWriterValueUsedToBuildCandidate"])

    def test_axis_max_and_absolute_shape_are_not_the_old_fitted_law(self) -> None:
        value = self.timeline()
        records = value["dynamicBackgroundUniforms"]["records"]
        endpoint = records[-1]["filter"]["inputValues"]
        endpoint["inputBleedAmount"] = 10_000.0
        endpoint["inputShadowAmount"] = -3.0
        endpoint["inputShadowOffset"] = {
            "hex": struct.pack("<2d", -11.0, 7.0).hex(),
            "lengthBytes": 16,
            "objCType": "{CGSize=dd}",
        }
        candidate = validator.provider_transition_candidate(
            value,
            "regular",
            "light",
            "materialize",
            "circle-451-center",
        )
        self.assertEqual(candidate["records"][-1]["axisF64"], 11.0)
        self.assertEqual(candidate["records"][-1]["shapeF64"], 3.0)
        self.assertEqual(candidate["records"][-1]["providerReturnF64"], 14.0)
        self.assertEqual(candidate["providerMaximumF64"], 80.65625)

    def test_clear_selects_positive_zero_after_provider_replay(self) -> None:
        candidate = validator.provider_transition_candidate(
            self.timeline("clear"),
            "clear",
            "light",
            "materialize",
            "circle-451-center",
        )
        self.assertEqual(candidate["providerMaximumF64"], 83.0)
        self.assertEqual(candidate["maximumRequiredMarginF64"], 0.0)
        self.assertEqual(
            candidate["maximumRequiredMarginF64RawLittleEndianHex"], "0" * 16
        )
        self.assertEqual(
            candidate["expectedRenderMarginF32RawLittleEndianHex"], "0" * 8
        )

    def test_incomplete_timeline_is_rejected_before_prediction(self) -> None:
        value = self.timeline()
        value["failedSamples"] = 1
        with self.assertRaisesRegex(ValueError, "timeline identity"):
            validator.provider_transition_candidate(
                value,
                "regular",
                "light",
                "materialize",
                "circle-451-center",
            )


if __name__ == "__main__":
    unittest.main()
