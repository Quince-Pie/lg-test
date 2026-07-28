import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from measure import Artifact, Measurements


class MeasurementTests(unittest.TestCase):
    def test_geometry_coordinates_honor_backing_scale(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "shots").mkdir()
            pixels = np.zeros((400, 400, 3), dtype=np.uint8)
            pixels[136:265, 136:265] = 77
            relative = "shots/scaled.png"
            Image.fromarray(pixels).save(root / relative)
            measurements = Measurements(
                Artifact(
                    path=root,
                    manifest={
                        "backingScaleFactor": 2,
                        "references": [],
                        "captures": [
                            {
                                "background": "probe",
                                "scene": "circle-0500-center",
                                "overlay": "regular",
                                "appearance": "light",
                                "file": relative,
                            }
                        ],
                        "scenes": [
                            {
                                "name": "circle-0500-center",
                                "shapes": [
                                    {
                                        "centerX": 100,
                                        "centerY": 100,
                                        "width": 100,
                                        "height": 100,
                                    }
                                ],
                            }
                        ],
                    },
                )
            )

            self.assertEqual(
                measurements.shape_pixels("circle-0500-center"),
                (200.0, 200.0, 200.0, 200.0),
            )
            np.testing.assert_array_equal(
                measurements.deep_median("probe", "regular", "light"),
                [77, 77, 77],
            )

    def test_sweep_differences_report_pixel_magnitude(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sweeps").mkdir()
            base = np.zeros((2, 2, 3), dtype=np.uint8)
            changed = base.copy()
            changed[1, 1] = [2, 0, 0]
            paths = {
                "frame": "sweeps/frame.png",
                "reverse": "sweeps/reverse.png",
                "repeat": "sweeps/repeat.png",
            }
            Image.fromarray(base).save(root / paths["frame"])
            Image.fromarray(base).save(root / paths["reverse"])
            Image.fromarray(changed).save(root / paths["repeat"])
            manifest = {
                "references": [],
                "captures": [],
                "scenes": [],
                "sweepSequences": [
                    {
                        "id": "sweep__probe",
                        "frames": [
                            {
                                "index": 0,
                                "progress": 0,
                                "file": paths["frame"],
                                "pixelSha256": "base",
                                "stable": True,
                            }
                        ],
                        "reverseFrames": [
                            {
                                "index": 0,
                                "progress": 0,
                                "file": paths["reverse"],
                                "pixelSha256": "base",
                                "stable": True,
                            }
                        ],
                        "repeatFrames": [
                            {
                                "index": 0,
                                "progress": 0,
                                "file": paths["repeat"],
                                "pixelSha256": "changed",
                                "stable": True,
                            }
                        ],
                    }
                ],
            }

            result = Measurements(Artifact(path=root, manifest=manifest)).sweep_states()
            sequence = result["sequences"]["sweep__probe"]

            self.assertEqual(sequence["coldRepeatDifferingStates"], 1)
            self.assertEqual(
                sequence["coldRepeatDifference"]["maximumChangedPixels"],
                1,
            )
            self.assertEqual(
                sequence["coldRepeatDifference"]["maximumChannelDelta"],
                2,
            )
            self.assertEqual(sequence["warmReverseDifferingStates"], 0)

    def test_dense_transfer_extracts_every_tone_and_color_knot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "reference").mkdir()
            (root / "shots").mkdir()
            width = height = 540

            x_codes = np.arange(width, dtype=np.uint32) * 255 // (width - 1)
            y_codes = np.arange(height, dtype=np.uint32) * 255 // (height - 1)
            ramp_x = np.broadcast_to(x_codes, (height, width))
            ramp_y = np.broadcast_to(y_codes[:, None], (height, width))
            levels = np.asarray(
                [0, 32, 64, 96, 128, 160, 192, 224, 255],
                dtype=np.uint8,
            )
            columns = np.minimum(26, np.arange(width) * 27 // width)
            rows = np.minimum(26, np.arange(height) * 27 // height)
            indices = rows[:, None] * 27 + columns
            cube = np.stack(
                (
                    levels[indices % 9],
                    levels[(indices // 9) % 9],
                    levels[(indices // 81) % 9],
                ),
                axis=2,
            )
            sources = {
                "ramp-x": np.repeat(ramp_x[:, :, None], 3, axis=2).astype(np.uint8),
                "ramp-y": np.repeat(ramp_y[:, :, None], 3, axis=2).astype(np.uint8),
                "color-cube-9": cube,
            }

            references = []
            for background, pixels in sources.items():
                relative = f"reference/{background}.png"
                Image.fromarray(pixels).save(root / relative)
                references.append({"background": background, "file": relative})

            captures = []
            for appearance in ("light", "dark"):
                for overlay in ("regular", "clear"):
                    for background, source in sources.items():
                        if background.startswith("ramp"):
                            output = np.minimum(
                                source.astype(np.uint16) + 5, 255
                            ).astype(np.uint8)
                        else:
                            output = np.minimum(
                                source.astype(np.uint16)
                                + np.asarray([1, 2, 3], dtype=np.uint16),
                                255,
                            ).astype(np.uint8)
                        relative = (
                            f"shots/{background}__circle-4000-center__"
                            f"{overlay}__{appearance}.png"
                        )
                        Image.fromarray(output).save(root / relative)
                        captures.append(
                            {
                                "background": background,
                                "scene": "circle-4000-center",
                                "overlay": overlay,
                                "appearance": appearance,
                                "file": relative,
                            }
                        )

            measurements = Measurements(
                Artifact(
                    path=root,
                    manifest={
                        "references": references,
                        "captures": captures,
                        "scenes": [],
                    },
                )
            )
            tone = measurements.dense_tone_transfer()
            color = measurements.dense_color_transfer()

            self.assertTrue(tone["available"])
            self.assertEqual(
                tone["light/regular"]["outputCodes"],
                [min(code + 5, 255) for code in range(256)],
            )
            self.assertEqual(
                tone["light/regular"]["orientationDisagreementCodes"],
                {"meanAbsolute": 0.0, "maximum": 0.0},
            )
            self.assertTrue(color["available"])
            self.assertEqual(color["sampleCount"], 729)
            self.assertEqual(color["inputCodes"][0], [0.0, 0.0, 0.0])
            self.assertEqual(color["inputCodes"][-1], [255.0, 255.0, 255.0])
            self.assertEqual(
                color["light/regular"]["outputCodes"][0],
                [1.0, 2.0, 3.0],
            )
            self.assertEqual(
                color["light/regular"]["outputCodes"][-1],
                [255.0, 255.0, 255.0],
            )


if __name__ == "__main__":
    unittest.main()
