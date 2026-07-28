#!/usr/bin/env python3
"""Extract reproducible optical measurements from a GlassCapture artifact."""

import argparse
import hashlib
import json
import math
import platform
import statistics
from dataclasses import dataclass, field
from importlib.metadata import version as package_version
from io import BytesIO
from pathlib import Path
from typing import Any, Self
from zipfile import ZipFile

import numpy as np
from numpy.typing import NDArray
from PIL import Image
from scipy.ndimage import map_coordinates
from scipy.optimize import least_squares
from scipy.special import ndtr


type JsonObject = dict[str, Any]
type FloatImage = NDArray[np.float64]
type ComplexImage = NDArray[np.complex128]

LUMA = np.array([0.2126, 0.7152, 0.0722])
GRAY_LEVELS = [*range(0, 241, 16), 255]
CIRCLE_SCENES = [
    "circle-0128-center",
    "circle-0256-center",
    "circle-0500-center",
    "circle-1000-center",
    "circle-1600-center",
    "circle-4000-center",
]
COLOR_BACKGROUNDS = [
    "red-255",
    "green-255",
    "blue-255",
    "cyan-255",
    "magenta-255",
    "yellow-255",
    "red-128",
    "green-128",
    "blue-128",
    "cyan-128",
    "magenta-128",
    "yellow-128",
    "orange",
    "violet",
]


@dataclass(slots=True)
class Artifact:
    path: Path
    manifest: JsonObject
    prefix: str = ""
    archive: ZipFile | None = field(default=None, repr=False)

    @classmethod
    def open(cls, path: Path) -> Self:
        path = path.resolve()
        if path.is_dir():
            manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
            return cls(path=path, manifest=manifest)
        archive = ZipFile(path)
        names = [name for name in archive.namelist() if name.endswith("manifest.json")]
        if len(names) != 1:
            archive.close()
            raise ValueError(
                f"archive has {len(names)} manifest.json entries; expected one"
            )
        manifest_name = names[0]
        manifest = json.loads(archive.read(manifest_name))
        return cls(
            path=path,
            manifest=manifest,
            prefix=manifest_name.removesuffix("manifest.json"),
            archive=archive,
        )

    def close(self) -> None:
        if self.archive is not None:
            self.archive.close()

    def read_bytes(self, relative: str) -> bytes:
        if self.archive is not None:
            return self.archive.read(f"{self.prefix}{relative}")
        return (self.path / relative).read_bytes()

    def image(self, relative: str) -> FloatImage:
        with Image.open(BytesIO(self.read_bytes(relative))) as source:
            return np.asarray(source.convert("RGB"), dtype=np.float64)


@dataclass(slots=True)
class Measurements:
    artifact: Artifact
    records: dict[tuple[str, str, str, str], JsonObject] = field(init=False)
    scenes: dict[str, JsonObject] = field(init=False)
    references: dict[str, JsonObject] = field(init=False)

    def __post_init__(self) -> None:
        self.records = {
            (
                str(record["background"]),
                str(record["scene"]),
                str(record["overlay"]),
                str(record["appearance"]),
            ): record
            for record in self.artifact.manifest["captures"]
        }
        self.scenes = {
            str(scene["name"]): scene for scene in self.artifact.manifest["scenes"]
        }
        self.references = {
            str(reference["background"]): reference
            for reference in self.artifact.manifest["references"]
        }

    def image(
        self, background: str, scene: str, overlay: str, appearance: str
    ) -> FloatImage:
        record = self.records[(background, scene, overlay, appearance)]
        return self.artifact.image(str(record["file"]))

    def reference_image(self, background: str) -> FloatImage:
        return self.artifact.image(str(self.references[background]["file"]))

    def has_image(
        self, background: str, scene: str, overlay: str, appearance: str
    ) -> bool:
        return (background, scene, overlay, appearance) in self.records

    def deep_median(
        self, background: str, overlay: str, appearance: str
    ) -> NDArray[np.float64]:
        image = self.image(background, "circle-0500-center", overlay, appearance)
        shape = self.scenes["circle-0500-center"]["shapes"][0]
        x = round(float(shape["centerX"]))
        y = round(float(shape["centerY"]))
        return np.median(image[y - 32 : y + 33, x - 32 : x + 33], axis=(0, 1))

    def tone_transfer(self) -> JsonObject:
        source = np.asarray(GRAY_LEVELS, dtype=np.float64) / 255
        result: JsonObject = {}
        for appearance in ("light", "dark"):
            for overlay in ("regular", "clear"):
                values = np.asarray(
                    [
                        self.deep_median(
                            f"gray-{level:03d}", overlay, appearance
                        ).mean()
                        for level in GRAY_LEVELS
                    ]
                )
                if overlay == "clear":
                    fit = least_squares(
                        lambda parameters: (
                            np.clip(parameters[0] * source + parameters[1], 0, 1) * 255
                            - values
                        ),
                        [1, 0.05],
                    )
                    predicted = np.clip(fit.x[0] * source + fit.x[1], 0, 1) * 255
                    model = {
                        "kind": "clipped-affine-srgb",
                        "gain": float(fit.x[0]),
                        "offset": float(fit.x[1]),
                    }
                else:
                    coefficients = np.polyfit(source, values / 255, 2)
                    predicted = np.clip(np.polyval(coefficients, source), 0, 1) * 255
                    model = {
                        "kind": "quadratic-srgb",
                        "coefficientsDescending": coefficients.tolist(),
                    }
                error = np.abs(predicted - values)
                result[f"{appearance}/{overlay}"] = {
                    "inputCodes": GRAY_LEVELS,
                    "outputCodes": values.tolist(),
                    "model": model,
                    "fitErrorCodes": {
                        "meanAbsolute": float(error.mean()),
                        "maximum": float(error.max()),
                        "rmse": float(np.sqrt(np.mean(error**2))),
                    },
                }
        return result

    def dense_tone_transfer(self) -> JsonObject:
        scene = "circle-4000-center"
        required = [
            (background, scene, overlay, appearance)
            for background in ("ramp-x", "ramp-y")
            for appearance in ("light", "dark")
            for overlay in ("regular", "clear")
        ]
        if not all(case in self.records for case in required):
            return {
                "available": False,
                "reason": "requires v2.2 giant-circle ramp-x and ramp-y captures",
            }

        result: JsonObject = {"available": True, "samplesPerCurve": 256}
        source_images = {
            background: np.rint(self.reference_image(background)[:, :, 0]).astype(
                np.uint8
            )
            for background in ("ramp-x", "ramp-y")
        }
        for appearance in ("light", "dark"):
            for overlay in ("regular", "clear"):
                orientations: dict[str, NDArray[np.float64]] = {}
                for background, axis in (("ramp-x", "x"), ("ramp-y", "y")):
                    output = self.image(background, scene, overlay, appearance).mean(
                        axis=2
                    )
                    source = source_images[background]
                    height, width = source.shape
                    mask = np.zeros_like(source, dtype=bool)
                    if axis == "x":
                        mask[height // 4 : 3 * height // 4, :] = True
                    else:
                        mask[:, width // 4 : 3 * width // 4] = True
                    orientations[axis] = np.asarray(
                        [
                            np.median(output[mask & (source == code)])
                            for code in range(256)
                        ]
                    )

                combined = np.median(np.stack(list(orientations.values())), axis=0)
                disagreement = np.abs(orientations["x"] - orientations["y"])
                result[f"{appearance}/{overlay}"] = {
                    "inputCodes": list(range(256)),
                    "outputCodes": combined.tolist(),
                    "orientationOutputCodes": {
                        axis: values.tolist() for axis, values in orientations.items()
                    },
                    "orientationDisagreementCodes": {
                        "meanAbsolute": float(disagreement.mean()),
                        "maximum": float(disagreement.max()),
                    },
                    "monotonic": bool(np.all(np.diff(combined) >= 0)),
                }
        return result

    def dense_color_transfer(self) -> JsonObject:
        background = "color-cube-9"
        scene = "circle-4000-center"
        required = [
            (background, scene, overlay, appearance)
            for appearance in ("light", "dark")
            for overlay in ("regular", "clear")
        ]
        if background not in self.references or not all(
            case in self.records for case in required
        ):
            return {
                "available": False,
                "reason": "requires the v2.2 9x9x9 color-cube captures",
            }

        source = self.reference_image(background)
        height, width = source.shape[:2]
        input_codes: list[list[float]] = []
        patches: list[tuple[slice, slice]] = []
        for row in range(27):
            y0 = math.ceil(row * height / 27)
            y1 = math.ceil((row + 1) * height / 27)
            for column in range(27):
                x0 = math.ceil(column * width / 27)
                x1 = math.ceil((column + 1) * width / 27)
                center_x = (x0 + x1) // 2
                center_y = (y0 + y1) // 2
                half_size = min(8, (x1 - x0 - 1) // 2, (y1 - y0 - 1) // 2)
                patch = (
                    slice(center_y - half_size, center_y + half_size + 1),
                    slice(center_x - half_size, center_x + half_size + 1),
                )
                patches.append(patch)
                input_codes.append(np.median(source[patch], axis=(0, 1)).tolist())

        result: JsonObject = {
            "available": True,
            "gridLevels": [0, 32, 64, 96, 128, 160, 192, 224, 255],
            "sampleCount": len(patches),
            "inputCodes": input_codes,
        }
        for appearance in ("light", "dark"):
            for overlay in ("regular", "clear"):
                output = self.image(background, scene, overlay, appearance)
                result[f"{appearance}/{overlay}"] = {
                    "outputCodes": [
                        np.median(output[patch], axis=(0, 1)).tolist()
                        for patch in patches
                    ]
                }
        return result

    def sparse_color_transfer(self) -> JsonObject:
        backgrounds = [
            *(f"gray-{level:03d}" for level in GRAY_LEVELS),
            *COLOR_BACKGROUNDS,
        ]
        result: JsonObject = {}
        for appearance in ("light", "dark"):
            for overlay in ("regular", "clear"):
                inputs = (
                    np.asarray(
                        [
                            self.deep_median(background, "none", appearance)
                            for background in backgrounds
                        ]
                    )
                    / 255
                )
                outputs = (
                    np.asarray(
                        [
                            self.deep_median(background, overlay, appearance)
                            for background in backgrounds
                        ]
                    )
                    / 255
                )
                design = np.column_stack((inputs, np.ones(len(inputs))))
                coefficients: list[NDArray[np.float64]] = []
                for channel in range(3):
                    unclipped = (outputs[:, channel] > 1 / 255) & (
                        outputs[:, channel] < 254 / 255
                    )
                    coefficients.append(
                        np.linalg.lstsq(
                            design[unclipped],
                            outputs[unclipped, channel],
                            rcond=None,
                        )[0]
                    )
                transform = np.stack(coefficients, axis=1)
                predicted = np.clip(design @ transform, 0, 1)
                error = np.abs(predicted - outputs) * 255
                result[f"{appearance}/{overlay}"] = {
                    "model": "affine-srgb-diagnostic",
                    "sampleCount": len(backgrounds),
                    "matrixRowsAndOffset": np.column_stack(
                        (transform[:3].T, transform[3])
                    ).tolist(),
                    "fitErrorCodes": {
                        "meanAbsolute": float(error.mean()),
                        "p95": float(np.percentile(error, 95)),
                        "maximum": float(error.max()),
                    },
                }
        return result

    def checker_blur(self) -> JsonObject:
        result: JsonObject = {}
        for scene_name in CIRCLE_SCENES:
            if ("checker-0128", scene_name, "regular", "light") not in self.records:
                continue
            shape = self.scenes[scene_name]["shapes"][0]
            center_x = float(shape["centerX"])
            center_y = float(shape["centerY"])
            radius_x = float(shape["width"]) / 2
            radius_y = float(shape["height"]) / 2
            if min(radius_x, radius_y) <= 119:
                continue
            scene_result: JsonObject = {}
            for appearance in ("light", "dark"):
                for overlay in ("regular", "clear"):
                    image = (
                        self.image(
                            "checker-0128",
                            scene_name,
                            overlay,
                            appearance,
                        )
                        @ LUMA
                        / 255
                    )
                    x0 = max(0, math.floor(center_x - radius_x + 55))
                    x1 = min(image.shape[1], math.ceil(center_x + radius_x - 55))
                    y0 = max(0, math.floor(center_y - radius_y + 55))
                    y1 = min(image.shape[0], math.ceil(center_y + radius_y - 55))
                    yy, xx = np.mgrid[y0:y1:2, x0:x1:2]
                    ellipse = ((xx - center_x) / (radius_x - 55)) ** 2 + (
                        (yy - center_y) / (radius_y - 55)
                    ) ** 2 < 1
                    phase_y = yy % 128
                    far_from_horizontal = (
                        np.minimum(phase_y + 0.5, 127.5 - phase_y) > 40
                    )
                    phase_x = xx % 128
                    distance = np.minimum(phase_x + 0.5, 127.5 - phase_x)
                    white = ((xx // 128 + yy // 128) % 2) == 0
                    signed_distance = np.where(white, distance, -distance)
                    mask = ellipse & far_from_horizontal & (distance < 45)
                    sample_x = signed_distance[mask]
                    sample_y = image[yy[mask], xx[mask]]
                    if len(sample_x) > 200_000:
                        stride = math.ceil(len(sample_x) / 200_000)
                        sample_x = sample_x[::stride]
                        sample_y = sample_y[::stride]

                    def residual(parameters: NDArray[np.float64]) -> FloatImage:
                        sigma, low, high, shift = parameters
                        return (
                            low
                            + (high - low) * ndtr((sample_x - shift) / sigma)
                            - sample_y
                        )

                    fit = least_squares(
                        residual,
                        [
                            6,
                            float(np.percentile(sample_y, 2)),
                            float(np.percentile(sample_y, 98)),
                            0,
                        ],
                        bounds=([0.1, 0, 0, -3], [50, 1, 1, 3]),
                        loss="soft_l1",
                        f_scale=0.003,
                    )
                    fit_error = residual(fit.x)
                    scene_result[f"{appearance}/{overlay}"] = {
                        "sigmaPixels": float(fit.x[0]),
                        "lowCode": float(fit.x[1] * 255),
                        "highCode": float(fit.x[2] * 255),
                        "edgeShiftPixels": float(fit.x[3]),
                        "rmseCodes": float(np.sqrt(np.mean(fit_error**2)) * 255),
                        "samples": len(sample_x),
                    }
            result[scene_name] = scene_result
        return result

    def edge_geometry(self) -> JsonObject:
        control = (
            self.image("gray-128", "circle-0500-center", "none", "light") @ LUMA / 255
        )
        result: JsonObject = {}
        for scene_name in CIRCLE_SCENES:
            if scene_name == "circle-4000-center":
                continue
            shape = self.scenes[scene_name]["shapes"][0]
            center_x = float(shape["centerX"])
            center_y = float(shape["centerY"])
            radius = float(shape["width"]) / 2
            scene_result: JsonObject = {}
            for appearance in ("light", "dark"):
                for overlay in ("regular", "clear"):
                    difference = (
                        self.image("gray-128", scene_name, overlay, appearance)
                        @ LUMA
                        / 255
                        - control
                    )
                    body = float(difference[round(center_y), round(center_x)])
                    offsets = np.arange(-5, 5.25, 0.25)
                    angles = np.deg2rad(np.arange(360))
                    rim_values = np.asarray(
                        [
                            map_coordinates(
                                difference,
                                [
                                    center_y + (radius + offset) * np.sin(angles),
                                    center_x + (radius + offset) * np.cos(angles),
                                ],
                                order=1,
                            )
                            for offset in offsets
                        ]
                    )
                    peak_index = np.unravel_index(
                        np.argmax(rim_values), rim_values.shape
                    )
                    reaches: JsonObject = {}
                    for name, degrees in (
                        ("up", -90),
                        ("right", 0),
                        ("down", 90),
                        ("left", 180),
                    ):
                        theta = math.radians(degrees)
                        outside = np.arange(2, 61, 0.25)
                        radii = radius + outside
                        profile = map_coordinates(
                            difference,
                            [
                                center_y + radii * math.sin(theta),
                                center_x + radii * math.cos(theta),
                            ],
                            order=1,
                        )
                        nonzero = np.flatnonzero(np.abs(profile) > 1 / 255)
                        reaches[name] = (
                            float(outside[nonzero[-1]]) if len(nonzero) else 0
                        )
                    scene_result[f"{appearance}/{overlay}"] = {
                        "bodyDeltaSrgb": body,
                        "rimPeakDeltaSrgb": float(rim_values[peak_index]),
                        "rimPeakOffsetPixels": float(offsets[peak_index[0]]),
                        "oneCodeOuterReachPixels": reaches,
                    }
            result[scene_name] = scene_result
        return result

    def phase_refraction(self) -> JsonObject:
        result: JsonObject = {}
        period = 256
        offsets = [180, 200, 220, 230, 235, 240, 245, 248]
        for appearance in ("light", "dark"):
            for overlay in ("regular", "clear"):
                source: list[FloatImage] = []
                output: list[FloatImage] = []
                for phase in range(4):
                    background = f"sine-x-p{period:04d}-ph{phase}"
                    source.append(
                        self.image(
                            background,
                            "circle-0500-center",
                            "none",
                            appearance,
                        )[:, :, 0]
                    )
                    output.append(
                        self.image(
                            background,
                            "circle-0500-center",
                            overlay,
                            appearance,
                        )[:, :, 0]
                    )
                source_complex = (source[0] - source[2]) + 1j * (source[1] - source[3])
                output_complex = (output[0] - output[2]) + 1j * (output[1] - output[3])
                response = output_complex / source_complex
                samples: JsonObject = {}
                for offset in offsets:
                    values = response[995:1006, 1600 + offset]
                    unit = np.mean(values / np.maximum(np.abs(values), 1e-12))
                    samples[str(250 - offset)] = {
                        "depthInsidePixels": 250 - offset,
                        "apparentOutwardDisplacementPixels": float(
                            np.angle(unit) * period / (2 * np.pi)
                        ),
                        "amplitudeRatio": float(np.median(np.abs(values))),
                    }
                result[f"{appearance}/{overlay}"] = samples
        return result

    def phase_response(self) -> JsonObject:
        periods = (64, 256, 1024)
        candidate_scenes = (
            "circle-0256-center",
            "circle-0500-center",
            "circle-4000-center",
        )
        result: JsonObject = {}
        source_cache: dict[tuple[str, int], ComplexImage] = {}

        def source_complex(axis: str, period: int) -> ComplexImage:
            key = (axis, period)
            if key not in source_cache:
                phases = [
                    self.reference_image(f"sine-{axis}-p{period:04d}-ph{phase}")[
                        :, :, 0
                    ]
                    for phase in range(4)
                ]
                source_cache[key] = (phases[0] - phases[2]) + 1j * (
                    phases[1] - phases[3]
                )
            return source_cache[key]

        for scene_name in candidate_scenes:
            if scene_name not in self.scenes:
                continue
            scene_result: JsonObject = {}
            shape = self.scenes[scene_name]["shapes"][0]
            center_x = round(float(shape["centerX"]))
            center_y = round(float(shape["centerY"]))
            radius = float(shape["width"]) / 2
            for appearance in ("light", "dark"):
                for overlay in ("regular", "clear"):
                    variant_result: JsonObject = {}
                    for axis in ("x", "y"):
                        axis_result: JsonObject = {}
                        for period in periods:
                            backgrounds = [
                                f"sine-{axis}-p{period:04d}-ph{phase}"
                                for phase in range(4)
                            ]
                            if not all(
                                self.has_image(
                                    background,
                                    scene_name,
                                    overlay,
                                    appearance,
                                )
                                for background in backgrounds
                            ):
                                continue
                            phases = [
                                self.image(
                                    background,
                                    scene_name,
                                    overlay,
                                    appearance,
                                )[:, :, 0]
                                for background in backgrounds
                            ]
                            output_complex = (phases[0] - phases[2]) + 1j * (
                                phases[1] - phases[3]
                            )
                            source = source_complex(axis, period)
                            response = np.divide(
                                output_complex,
                                source,
                                out=np.zeros_like(output_complex),
                                where=np.abs(source) > 1e-12,
                            )
                            center_values = response[
                                center_y - 16 : center_y + 17,
                                center_x - 16 : center_x + 17,
                            ]
                            center_unit = np.mean(
                                center_values / np.maximum(np.abs(center_values), 1e-12)
                            )
                            period_result: JsonObject = {
                                "centerAmplitudeRatio": float(
                                    np.median(np.abs(center_values))
                                ),
                                "centerApparentDisplacementPixels": float(
                                    np.angle(center_unit) * period / (2 * np.pi)
                                ),
                            }

                            # The 4000-point circle's boundary is intentionally
                            # off-screen; it provides an edge-free interior MTF.
                            if radius < min(response.shape[0], response.shape[1]):
                                profiles: JsonObject = {}
                                directions = (
                                    (("right", 1), ("left", -1))
                                    if axis == "x"
                                    else (("down", 1), ("up", -1))
                                )
                                depths = [
                                    depth
                                    for depth in (2, 5, 10, 15, 20, 30, 50, 70)
                                    if depth < radius - 8
                                ]
                                for direction_name, sign in directions:
                                    samples: list[JsonObject] = []
                                    for depth in depths:
                                        if axis == "x":
                                            x = round(
                                                center_x + sign * (radius - depth)
                                            )
                                            values = response[
                                                center_y - 5 : center_y + 6, x
                                            ]
                                        else:
                                            y = round(
                                                center_y + sign * (radius - depth)
                                            )
                                            values = response[
                                                y, center_x - 5 : center_x + 6
                                            ]
                                        unit = np.mean(
                                            values / np.maximum(np.abs(values), 1e-12)
                                        )
                                        screen_displacement = (
                                            np.angle(unit) * period / (2 * np.pi)
                                        )
                                        samples.append(
                                            {
                                                "depthInsidePixels": depth,
                                                "wrappedApparentOutwardDisplacementPixels": float(
                                                    sign * screen_displacement
                                                ),
                                                "amplitudeRatio": float(
                                                    np.median(np.abs(values))
                                                ),
                                            }
                                        )
                                    profiles[direction_name] = samples
                                period_result["edgeProfiles"] = profiles
                            axis_result[str(period)] = period_result

                        reference_amplitude = axis_result.get("1024", {}).get(
                            "centerAmplitudeRatio"
                        )
                        if isinstance(reference_amplitude, (int, float)):
                            for period_result in axis_result.values():
                                amplitude = period_result.get("centerAmplitudeRatio")
                                if isinstance(amplitude, (int, float)):
                                    period_result["centerAmplitudeRelativeToP1024"] = (
                                        amplitude / reference_amplitude
                                        if reference_amplitude
                                        else None
                                    )
                        if axis_result:
                            variant_result[axis] = axis_result
                    if variant_result:
                        scene_result[f"{appearance}/{overlay}"] = variant_result
            if scene_result:
                result[scene_name] = scene_result
        return {
            "available": bool(result),
            "phaseConvention": (
                "positive displacement is apparent motion toward the named "
                "outward edge; values are wrapped to +/- period/2"
            ),
            "scenes": result,
        }

    def dynamic_timing(self) -> JsonObject:
        result: JsonObject = {}
        for sequence in self.artifact.manifest["dynamicSequences"]:
            frames = sequence["frames"]
            actual = [float(frame["actualSeconds"]) for frame in frames]
            target = [float(frame["targetSeconds"]) for frame in frames]
            capture = [float(frame["captureDurationSeconds"]) for frame in frames]
            gaps = [right - left for left, right in zip(actual, actual[1:])]
            errors = [abs(left - right) for left, right in zip(actual, target)]
            presented = [
                float(frame["presentationProgress"])
                for frame in frames
                if isinstance(frame.get("presentationProgress"), (int, float))
            ]
            presentation_gaps = [
                right - left for left, right in zip(presented, presented[1:])
            ]
            unique_frames = len({str(frame["pixelSha256"]) for frame in frames})
            maximum_gap = max(gaps, default=0)
            result[str(sequence["id"])] = {
                "capturedFrames": len(frames),
                "uniqueFrames": unique_frames,
                "presentationClock": sequence.get("presentationClock"),
                "samplingMethod": sequence.get("samplingMethod"),
                "captureAttempts": sequence.get("captureAttempts"),
                "decodedSamples": sequence.get("decodedSamples"),
                "transientFailures": sequence.get("transientFailures"),
                "acceptedForTemporalFit": (
                    unique_frames >= min(10, len(frames))
                    and maximum_gap <= 0.200
                    and (
                        not presented
                        or (
                            presented[0] <= 0.005
                            and presented[-1] >= 0.995
                            and all(
                                right >= left
                                for left, right in zip(presented, presented[1:])
                            )
                            and max(presentation_gaps, default=0) <= 0.200
                        )
                    )
                ),
                "actualStartSeconds": actual[0],
                "actualEndSeconds": actual[-1],
                "actualGapMilliseconds": {
                    "median": statistics.median(gaps) * 1000,
                    "p95": float(np.percentile(gaps, 95)) * 1000,
                    "maximum": maximum_gap * 1000,
                },
                "targetErrorMilliseconds": {
                    "median": statistics.median(errors) * 1000,
                    "p95": float(np.percentile(errors, 95)) * 1000,
                    "maximum": max(errors) * 1000,
                },
                "captureDurationMilliseconds": {
                    "median": statistics.median(capture) * 1000,
                    "p95": float(np.percentile(capture, 95)) * 1000,
                    "maximum": max(capture) * 1000,
                },
                "presentationProgress": {
                    "samples": len(presented),
                    "start": presented[0] if presented else None,
                    "end": presented[-1] if presented else None,
                    "maximumGap": max(presentation_gaps, default=None),
                },
                "analysisExclusionPixels": sequence.get("analysisExclusionPixels", []),
            }
        return result

    def sweep_states(self) -> JsonObject:
        sequences = self.artifact.manifest.get("sweepSequences", [])
        result: JsonObject = {}
        for sequence in sequences:
            frames = sequence.get("frames", [])
            result[str(sequence.get("id"))] = {
                "frames": len(frames),
                "uniqueFrames": len(
                    {str(frame.get("pixelSha256")) for frame in frames}
                ),
                "stableFrames": sum(frame.get("stable") is True for frame in frames),
                "progress": [frame.get("progress") for frame in frames],
            }
        return {
            "available": bool(sequences),
            "sequences": result,
        }

    def run(self) -> JsonObject:
        manifest = self.artifact.manifest
        dynamic_sequences = manifest.get("dynamicSequences", [])
        sweep_sequences = manifest.get("sweepSequences", [])
        return {
            "analysisSchemaVersion": 2,
            "analysisImplementation": {
                "file": "Analysis/measure.py",
                "sha256": file_sha256(Path(__file__).resolve()),
                "python": platform.python_version(),
                "numpy": np.__version__,
                "scipy": package_version("scipy"),
                "Pillow": package_version("Pillow"),
            },
            "artifact": {
                "file": self.artifact.path.name,
                "sha256": file_sha256(self.artifact.path)
                if self.artifact.path.is_file()
                else None,
                "schemaVersion": manifest.get("schemaVersion"),
                "rigVersion": manifest.get("rigVersion"),
                "osVersion": manifest.get("osVersion"),
                "osBuild": manifest.get("osBuild"),
                "architecture": manifest.get("architecture"),
                "hostModel": manifest.get("hostModel"),
                "xcodeVersion": manifest.get("xcodeVersion"),
                "ciCommit": manifest.get("ciCommit"),
                "runnerImageVersion": manifest.get("runnerImageVersion"),
                "presentationClockPreflight": manifest.get(
                    "presentationClockPreflight"
                ),
                "backingScaleFactor": manifest.get("backingScaleFactor"),
                "reduceTransparency": manifest.get("reduceTransparency"),
                "increaseContrast": manifest.get("increaseContrast"),
                "reduceMotion": manifest.get("reduceMotion"),
                "windowKey": manifest.get("windowKey"),
                "applicationActive": manifest.get("applicationActive"),
                "references": len(manifest.get("references", [])),
                "staticCaptures": len(manifest.get("captures", [])),
                "dynamicSequences": len(dynamic_sequences),
                "dynamicFrames": sum(
                    len(sequence.get("frames", [])) for sequence in dynamic_sequences
                ),
                "sweepSequences": len(sweep_sequences),
                "sweepFrames": sum(
                    len(sequence.get("frames", [])) for sequence in sweep_sequences
                ),
            },
            "toneTransfer": self.tone_transfer(),
            "denseToneTransfer": self.dense_tone_transfer(),
            "sparseColorTransfer": self.sparse_color_transfer(),
            "denseColorTransfer": self.dense_color_transfer(),
            "checkerEdgeSpread": self.checker_blur(),
            "edgeGeometry": self.edge_geometry(),
            "phaseRefraction": self.phase_refraction(),
            "phaseResponse": self.phase_response(),
            "dynamicTiming": self.dynamic_timing(),
            "sweepStates": self.sweep_states(),
        }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure a validated GlassCapture directory or ZIP."
    )
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifact = Artifact.open(args.artifact)
    try:
        report = Measurements(artifact).run()
    finally:
        artifact.close()
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report is None:
        print(encoded, end="")
    else:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded, encoding="utf-8")
        print(args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
