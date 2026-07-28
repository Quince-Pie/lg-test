import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from measure import Artifact, COLOR_BACKGROUNDS, GRAY_LEVELS, Measurements


class MeasurementTests(unittest.TestCase):
    def test_phase_cycle_fit_recovers_complex_transfer(self) -> None:
        height = width = 300
        y, x = np.indices((height, width))
        source = np.exp(1j * (2 * np.pi * x / 256)).astype(np.complex128)
        expected_amplitude = 0.245
        expected_displacement = 3.75
        transfer = expected_amplitude * np.exp(
            1j * 2 * np.pi * expected_displacement / 256
        )
        output = source * transfer

        result = Measurements.phase_cycle_fit(
            source,
            output,
            axis="x",
            period=256,
            center_x=150,
            center_y=150,
            radius=250,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertAlmostEqual(result["amplitudeRatio"], expected_amplitude)
        self.assertAlmostEqual(
            result["apparentDisplacementPixels"],
            expected_displacement,
        )
        self.assertAlmostEqual(result["normalizedComplexResidual"], 0)
        self.assertIsNone(
            Measurements.phase_cycle_fit(
                source,
                output,
                axis="x",
                period=256,
                center_x=150,
                center_y=150,
                radius=100,
            )
        )

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
            permuted_indices = (indices * 257 + 113) % 729
            permuted_cube = np.stack(
                (
                    levels[permuted_indices % 9],
                    levels[(permuted_indices // 9) % 9],
                    levels[(permuted_indices // 81) % 9],
                ),
                axis=2,
            )
            shuffled_indices = (indices * 365 + 271) % 729
            shuffled_cube = np.stack(
                (
                    levels[shuffled_indices % 9],
                    levels[(shuffled_indices // 9) % 9],
                    levels[(shuffled_indices // 81) % 9],
                ),
                axis=2,
            )
            holdout_levels = np.arange(16, 241, 32, dtype=np.uint8)
            holdout_columns = np.minimum(31, np.arange(width) * 32 // width)
            holdout_rows = np.minimum(15, np.arange(height) * 16 // height)
            holdout_indices = holdout_rows[:, None] * 32 + holdout_columns
            holdout_cube = np.stack(
                (
                    holdout_levels[holdout_indices % 8],
                    holdout_levels[(holdout_indices // 8) % 8],
                    holdout_levels[(holdout_indices // 64) % 8],
                ),
                axis=2,
            )
            shuffled_holdout_indices = (holdout_indices * 257 + 97) % 512
            shuffled_holdout = np.stack(
                (
                    holdout_levels[shuffled_holdout_indices % 8],
                    holdout_levels[(shuffled_holdout_indices // 8) % 8],
                    holdout_levels[(shuffled_holdout_indices // 64) % 8],
                ),
                axis=2,
            )
            sources = {
                "ramp-x": np.repeat(ramp_x[:, :, None], 3, axis=2).astype(np.uint8),
                "ramp-y": np.repeat(ramp_y[:, :, None], 3, axis=2).astype(np.uint8),
                "color-cube-9": cube,
                "color-cube-9-permuted": permuted_cube,
                "color-cube-9-shuffled": shuffled_cube,
                "color-cube-holdout-8": holdout_cube,
                "color-cube-holdout-8-shuffled": shuffled_holdout,
            }

            references = []
            for background, pixels in sources.items():
                relative = f"reference/{background}.png"
                Image.fromarray(pixels).save(root / relative)
                references.append({"background": background, "file": relative})

            captures = []
            for appearance in ("light", "dark"):
                for background, source in sources.items():
                    relative = (
                        f"shots/{background}__circle-0500-center__"
                        f"none__{appearance}.png"
                    )
                    Image.fromarray(source).save(root / relative)
                    captures.append(
                        {
                            "background": background,
                            "scene": "circle-0500-center",
                            "overlay": "none",
                            "appearance": appearance,
                            "file": relative,
                        }
                    )
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
                        "scenes": [
                            {
                                "name": "circle-4000-center",
                                "shapes": [
                                    {
                                        "centerX": width / 2,
                                        "centerY": height / 2,
                                        "width": 4000,
                                        "height": 4000,
                                    }
                                ],
                            }
                        ],
                    },
                )
            )
            tone = measurements.dense_tone_transfer()
            color = measurements.dense_color_transfer()
            holdout = measurements.dense_color_holdout()
            context_repeat = measurements.dense_color_context_repeat()
            context_holdout = measurements.dense_color_context_holdout()
            holdout_context_repeat = measurements.dense_color_holdout_context_repeat()

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
            self.assertEqual(len(color["sampleGeometry"]), 729)
            self.assertGreater(
                min(
                    sample["depthInsideShapePixels"]
                    for sample in color["sampleGeometry"]
                ),
                0,
            )
            self.assertEqual(
                color["light/regular"]["outputCodes"][0],
                [1.0, 2.0, 3.0],
            )
            self.assertEqual(
                color["capturedControlInputCodes"]["light"][0],
                [0.0, 0.0, 0.0],
            )
            self.assertEqual(
                color["light/regular"]["outputCodes"][-1],
                [255.0, 255.0, 255.0],
            )
            self.assertTrue(holdout["available"])
            self.assertEqual(holdout["sampleCount"], 512)
            self.assertEqual(holdout["inputCodes"][0], [16.0, 16.0, 16.0])
            self.assertEqual(holdout["inputCodes"][-1], [240.0, 240.0, 240.0])
            self.assertEqual(
                holdout["light/regular"]["outputCodes"][0],
                [17.0, 18.0, 19.0],
            )
            self.assertTrue(context_repeat["available"])
            self.assertEqual(context_repeat["sampleCount"], 729)
            self.assertEqual(
                sorted(context_repeat["inputCodes"]),
                sorted(color["inputCodes"]),
            )
            self.assertTrue(context_holdout["available"])
            self.assertEqual(context_holdout["sampleCount"], 729)
            self.assertEqual(
                sorted(context_holdout["inputCodes"]),
                sorted(color["inputCodes"]),
            )
            self.assertTrue(holdout_context_repeat["available"])
            self.assertEqual(holdout_context_repeat["sampleCount"], 512)
            self.assertEqual(
                sorted(holdout_context_repeat["inputCodes"]),
                sorted(holdout["inputCodes"]),
            )

    def test_sparse_transfer_preserves_holdout_samples(self) -> None:
        color_inputs = {
            name: np.asarray(
                [
                    (index * 47 + 13) % 256,
                    (index * 83 + 29) % 256,
                    (index * 131 + 7) % 256,
                ],
                dtype=np.float64,
            )
            for index, name in enumerate(COLOR_BACKGROUNDS)
        }

        def sample(
            _measurements: Measurements,
            background: str,
            overlay: str,
            _appearance: str,
        ) -> np.ndarray:
            if background.startswith("gray-"):
                code = float(background.removeprefix("gray-"))
                source = np.full(3, code)
            else:
                source = color_inputs[background]
            if overlay == "none":
                return source
            return np.clip(source * 0.75 + [11, 17, 23], 0, 255)

        measurements = Measurements(
            Artifact(
                path=Path("."),
                manifest={
                    "references": [],
                    "captures": [],
                    "scenes": [],
                },
            )
        )
        with patch.object(Measurements, "deep_median", sample):
            result = measurements.sparse_color_transfer()

        record = result["dark/regular"]
        expected_samples = len(GRAY_LEVELS) + len(COLOR_BACKGROUNDS)
        self.assertEqual(record["sampleCount"], expected_samples)
        self.assertEqual(len(record["backgrounds"]), expected_samples)
        self.assertEqual(len(record["inputCodes"]), expected_samples)
        self.assertEqual(len(record["outputCodes"]), expected_samples)
        self.assertEqual(record["backgrounds"][0], "gray-000")
        self.assertEqual(record["inputCodes"][0], [0.0, 0.0, 0.0])
        self.assertEqual(record["outputCodes"][0], [11.0, 17.0, 23.0])


if __name__ == "__main__":
    unittest.main()
