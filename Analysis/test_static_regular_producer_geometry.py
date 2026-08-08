#!/usr/bin/env python3
"""Tests for the frozen static regular producer-geometry model."""

import unittest

import static_regular_producer_geometry as model


def geometry(name: str, width: float, x: float, y: float) -> dict[str, object]:
    return {
        "name": name,
        "shape": "circle",
        "width": width,
        "height": width,
        "centerX": x,
        "centerY": y,
        "windowWidth": 1_024,
        "windowHeight": 1_024,
    }


class OpenedCorpusTests(unittest.TestCase):
    def test_all_five_opened_geometries_share_one_exact_policy(self) -> None:
        cases = (
            (
                geometry("circle-256-center", 256, 512, 512),
                [74, 74],
                [108, 108],
                [128, 128],
                [256, 256],
                [-74, -74],
            ),
            (
                geometry("circle-512-offset", 512, 337, 419),
                [0, 43],
                [193, 213],
                [256, 256],
                [320, 384],
                [-64, -107],
            ),
            (
                geometry("circle-640-fractional", 640, 602.25, 377.75),
                [15, 26],
                [241, 230],
                [256, 256],
                [384, 384],
                [-79, -90],
            ),
            (
                geometry("circle-896-center", 896, 512, 512),
                [0, 0],
                [256, 256],
                [256, 256],
                [384, 384],
                [-64, -64],
            ),
            (
                geometry("circle-1536-center", 1_536, 512, 512),
                [0, 0],
                [256, 256],
                [256, 256],
                [384, 384],
                [-64, -64],
            ),
        )
        for source, crop, active, producer, destination, offset in cases:
            with self.subTest(name=source["name"]):
                result = model.predict(source)
                self.assertEqual(result["cropOrigin"], crop)
                self.assertEqual(result["activeExtent"], active)
                self.assertEqual(result["producerExtent"], producer)
                self.assertEqual(result["destinationExtent"], destination)
                self.assertEqual(result["copyOffset"], offset)
                self.assertEqual(result["effectiveOrigin"], result["selectedRegion"][:2])


class ProspectiveHoldoutTests(unittest.TestCase):
    def test_fractional_clipped_holdout_prediction_is_frozen(self) -> None:
        result = model.predict(
            geometry(
                "circle-377-fractional-holdout",
                377,
                301.25,
                699.75,
            )
        )
        self.assertEqual(result["inputBleedAmount"], 131.9499969482422)
        self.assertEqual(result["cropOrigin"], [0, 1])
        self.assertEqual(result["activeExtent"], [155, 160])
        self.assertEqual(result["textureCoordinateClamp"], [0, 0, 154, 159])
        self.assertEqual(result["producerExtent"], [192, 192])
        self.assertEqual(result["radius1"], 20.0)
        self.assertEqual(result["mipPolicy"]["maximumLevelCount"], 8)
        self.assertEqual(result["mipPolicy"]["levelCount"], 6)
        self.assertEqual(result["mipPolicy"]["alignmentScale"], 64)
        self.assertEqual(result["selectedRegion"], [-64, -64, 320, 320])
        self.assertEqual(result["destinationExtent"], [320, 320])
        self.assertEqual(result["copyOffset"], [-64, -65])
        self.assertEqual(result["effectiveOrigin"], [-64, -64])

    def test_non_circle_is_outside_the_model(self) -> None:
        source = geometry("square", 377, 301.25, 699.75)
        source["shape"] = "square"
        with self.assertRaisesRegex(ValueError, "circle"):
            model.predict(source)


if __name__ == "__main__":
    unittest.main()
