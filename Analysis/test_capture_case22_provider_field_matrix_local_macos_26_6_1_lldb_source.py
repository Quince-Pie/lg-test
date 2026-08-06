#!/usr/bin/env python3
"""Source-contract checks for the local case-22 provider field matrix."""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
CAPTURE = ANALYSIS / "capture_case22_provider_field_matrix_local_macos_26_6_1_lldb.py"
APP = ANALYSIS.parent / "Sources/GlassIntrospect/main.swift"

EXPECTED_NAMES = (
    "baseline",
    "blur-radius-3_25",
    "bleed-amount-11_25",
    "bleed-height-0_375",
    "bleed-blur-radius-4_5",
    "bleed-distance0-0_25",
    "bleed-distance1-0_75",
    "shadow-offset-neg3-pos5",
    "shadow-amount-13_5",
    "shadow-height-0_4375",
    "shadow-opacity-0_625",
    "shadow-distance-offset-2_25",
    "shadow-blur-radius-6_5",
    "shadow-radius-7_25",
    "inner-refraction-amount-0_3125",
    "inner-refraction-height-0_5625",
    "outer-refraction-amount-0_6875",
    "outer-refraction-height-0_8125",
    "refraction-distance0-0_1875",
    "refraction-distance1-0_9375",
    "refraction-opacity-0_40625",
    "face-opacity-0_5",
    "sdr-shadow-opacity-0_34375",
)


def assigned_literal(tree: ast.Module, name: str):
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            if any(
                isinstance(target, ast.Name) and target.id == name
                for target in statement.targets
            ):
                return ast.literal_eval(statement.value)
    raise AssertionError(f"{name} assignment is absent")


class Case22ProviderFieldMatrixSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.capture_source = CAPTURE.read_text(encoding="utf-8")
        cls.capture_tree = ast.parse(cls.capture_source)
        cls.app_source = APP.read_text(encoding="utf-8")

    def test_intervention_order_is_identical_in_app_and_capture(self) -> None:
        self.assertEqual(
            assigned_literal(self.capture_tree, "INTERVENTION_NAMES"),
            EXPECTED_NAMES,
        )
        app_names = tuple(
            re.findall(
                r'Case22ProviderFieldIntervention\(\s*name: "([^"]+)"',
                self.app_source,
            )
        )
        self.assertEqual(app_names, EXPECTED_NAMES)

    def test_marker_is_exported_and_arguments_are_retained(self) -> None:
        for needle in (
            '@_cdecl("lg_case22_provider_probe_marker")',
            "@_optimize(none)",
            "public func lgCase22ProviderProbeMarker(",
            "lgCase22ProviderProbeMarkerState =",
            "lgCase22ProviderProbeMarker(Int32(index), 0)",
            "lgCase22ProviderProbeMarker(Int32(index), 1)",
        ):
            self.assertIn(needle, self.app_source)

    def test_capture_is_bounded_and_output_blind(self) -> None:
        self.assertIn("MAXIMUM_CALLS_PER_INTERVENTION = 128", self.capture_source)
        self.assertIn('"capturedObjectUsedForSelection": False', self.capture_source)
        self.assertIn('"capturedReturnUsedForSelection": False', self.capture_source)
        self.assertIn('"capturedMarginUsedForSelection": False', self.capture_source)
        self.assertIn('"capturedCropUsedForSelection": False', self.capture_source)
        self.assertIn('"capturedImageUsedForSelection": False', self.capture_source)
        self.assertIn('"capturedPixelUsedForSelection": False', self.capture_source)
        self.assertNotIn("provider_return ==", self.capture_source)
        self.assertNotIn("margin ==", self.capture_source)

    def test_exact_local_symbol_identities_are_frozen(self) -> None:
        for needle in (
            'SWIFTUICORE_UUID = "99606D45-C40A-3C69-AE51-5F0C4E32E531"',
            "WRAPPER_MODULE_OFFSET = 0x76BC54",
            "PROVIDER_MODULE_OFFSET = opened.PROVIDER_MODULE_OFFSET",
            '"922147f9c8b9cecdc273065e6677312965449069e4cf076e65daa1aba0a9d0ee"',
        ):
            self.assertIn(needle, self.capture_source)


if __name__ == "__main__":
    unittest.main()
