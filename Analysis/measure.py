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

from probe_catalog import ADAPTIVE_SPATIAL_PROBES, CLEAR_KERNEL_PROBES


type JsonObject = dict[str, Any]
type FloatImage = NDArray[np.float64]
type ComplexImage = NDArray[np.complex128]
type CodeImage = NDArray[np.uint8]

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
POSITION_SCENES = [
    "circle-0500-center",
    "circle-0500-upper-left",
    "circle-0500-upper-right",
    "circle-0500-lower-left",
    "circle-0500-lower-right",
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
CUBE_CONTEXT_TRAINING_BACKGROUNDS = [
    f"color-cube-9-context-train-{index:02d}" for index in range(4)
]
HOLDOUT_CONTEXT_TRAINING_BACKGROUNDS = [
    f"color-cube-holdout-8-context-train-{index:02d}" for index in range(4)
]
STOCHASTIC_BACKGROUNDS = [
    f"noise-{channel}-a{amplitude:03d}-{role}"
    for channel in ("gray", "rgb")
    for amplitude in (16, 64)
    for role in ("train", "holdout")
]
CLEAR_KERNEL_BACKGROUNDS = [
    "noise-rgb-a064-train",
    "noise-rgb-a064-holdout",
    *CLEAR_KERNEL_PROBES,
]
CLEAR_KERNEL_SCENES = [
    "circle-4000-center",
    "circle-6000-upper-left",
    "rect-6000x4000-r000-center",
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

    def code_image(self, relative: str) -> CodeImage:
        with Image.open(BytesIO(self.read_bytes(relative))) as source:
            return np.asarray(source.convert("RGB"), dtype=np.uint8)

    def image(self, relative: str) -> FloatImage:
        return self.code_image(relative).astype(np.float64)

    def image_channel(self, relative: str, channel: str = "R") -> FloatImage:
        with Image.open(BytesIO(self.read_bytes(relative))) as source:
            rgb = source.convert("RGB")
            return np.asarray(rgb.getchannel(channel), dtype=np.float64)


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

    def code_image(
        self, background: str, scene: str, overlay: str, appearance: str
    ) -> CodeImage:
        record = self.records[(background, scene, overlay, appearance)]
        return self.artifact.code_image(str(record["file"]))

    def image_channel(
        self, background: str, scene: str, overlay: str, appearance: str
    ) -> FloatImage:
        record = self.records[(background, scene, overlay, appearance)]
        return self.artifact.image_channel(str(record["file"]))

    def reference_image(self, background: str) -> FloatImage:
        return self.artifact.image(str(self.references[background]["file"]))

    def reference_code_image(self, background: str) -> CodeImage:
        return self.artifact.code_image(str(self.references[background]["file"]))

    def reference_channel(self, background: str) -> FloatImage:
        return self.artifact.image_channel(str(self.references[background]["file"]))

    def has_image(
        self, background: str, scene: str, overlay: str, appearance: str
    ) -> bool:
        return (background, scene, overlay, appearance) in self.records

    @property
    def backing_scale(self) -> float:
        return float(self.artifact.manifest.get("backingScaleFactor", 1))

    def shape_pixels(self, scene: str) -> tuple[float, float, float, float]:
        shape = self.scenes[scene]["shapes"][0]
        scale = self.backing_scale
        return (
            float(shape["centerX"]) * scale,
            float(shape["centerY"]) * scale,
            float(shape["width"]) * scale,
            float(shape["height"]) * scale,
        )

    @staticmethod
    def pixel_difference(
        reference: NDArray[Any],
        capture: NDArray[Any],
        exclusions: list[JsonObject] | None = None,
    ) -> JsonObject:
        if reference.shape != capture.shape:
            return {
                "shapeMismatch": {
                    "reference": list(reference.shape),
                    "capture": list(capture.shape),
                }
            }
        delta = np.abs(
            reference.astype(np.int16, copy=False)
            - capture.astype(np.int16, copy=False)
        )
        if exclusions:
            keep = np.ones(reference.shape[:2], dtype=np.bool_)
            for region in exclusions:
                x = int(region["x"])
                y = int(region["y"])
                width = int(region["width"])
                height = int(region["height"])
                keep[y : y + height, x : x + width] = False
            delta = delta[keep]
            changed = np.any(delta != 0, axis=1)
        else:
            changed = np.any(delta != 0, axis=2)
        changed_pixels = int(np.count_nonzero(changed))
        pixel_count = int(changed.size)
        return {
            "pixels": pixel_count,
            "changedPixels": changed_pixels,
            "changedFraction": changed_pixels / pixel_count if pixel_count else 0,
            "maximumChannelDelta": int(delta.max(initial=0)),
            "meanAbsoluteChannelDelta": float(delta.mean()) if delta.size else 0,
        }

    @staticmethod
    def phase_cycle_fit(
        source: ComplexImage,
        output: ComplexImage,
        *,
        axis: str,
        period: int,
        center_x: int,
        center_y: int,
        radius: float,
    ) -> JsonObject | None:
        """Fit one complete source cycle well inside a circular glass body."""
        if period <= 0 or period % 2 != 0 or source.shape != output.shape:
            return None
        half_axis = period // 2
        half_cross = 16
        if math.hypot(half_axis, half_cross) + 8 > radius:
            return None

        if axis == "x":
            region = (
                slice(center_y - half_cross, center_y + half_cross + 1),
                slice(center_x - half_axis, center_x + half_axis),
            )
        elif axis == "y":
            region = (
                slice(center_y - half_axis, center_y + half_axis),
                slice(center_x - half_cross, center_x + half_cross + 1),
            )
        else:
            return None

        source_region = source[region]
        output_region = output[region]
        expected_shape = (
            (2 * half_cross + 1, period)
            if axis == "x"
            else (period, 2 * half_cross + 1)
        )
        if (
            source_region.shape != expected_shape
            or output_region.shape != expected_shape
        ):
            return None

        source_vector = source_region.ravel()
        output_vector = output_region.ravel()
        source_energy = float(np.vdot(source_vector, source_vector).real)
        output_energy = float(np.vdot(output_vector, output_vector).real)
        if source_energy <= 0 or output_energy <= 0:
            return None

        transfer = np.vdot(source_vector, output_vector) / source_energy
        residual = output_vector - transfer * source_vector
        residual_energy = float(np.vdot(residual, residual).real)
        return {
            "axisSamples": period,
            "crossAxisSamples": 2 * half_cross + 1,
            "amplitudeRatio": float(abs(transfer)),
            "apparentDisplacementPixels": float(
                np.angle(transfer) * period / (2 * np.pi)
            ),
            "normalizedComplexResidual": math.sqrt(residual_energy / output_energy),
        }

    def deep_median(
        self, background: str, overlay: str, appearance: str
    ) -> NDArray[np.float64]:
        image = self.image(background, "circle-0500-center", overlay, appearance)
        center_x, center_y, _, _ = self.shape_pixels("circle-0500-center")
        half_width = max(1, round(32 * self.backing_scale))
        x = round(center_x)
        y = round(center_y)
        return np.median(
            image[
                y - half_width : y + half_width + 1,
                x - half_width : x + half_width + 1,
            ],
            axis=(0, 1),
        )

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

    def color_patch_samples(
        self,
        background: str,
        *,
        columns: int,
        rows: int,
    ) -> tuple[
        list[list[float]],
        list[tuple[slice, slice]],
        list[tuple[int, int]],
    ]:
        source = self.reference_image(background)
        height, width = source.shape[:2]
        input_codes: list[list[float]] = []
        patches: list[tuple[slice, slice]] = []
        centers: list[tuple[int, int]] = []
        for row in range(rows):
            y0 = math.ceil(row * height / rows)
            y1 = math.ceil((row + 1) * height / rows)
            for column in range(columns):
                x0 = math.ceil(column * width / columns)
                x1 = math.ceil((column + 1) * width / columns)
                center_x = (x0 + x1) // 2
                center_y = (y0 + y1) // 2
                half_size = min(8, (x1 - x0 - 1) // 2, (y1 - y0 - 1) // 2)
                if half_size < 1:
                    raise ValueError(
                        f"{background} tiles are too small for robust sampling"
                    )
                patch = (
                    slice(center_y - half_size, center_y + half_size + 1),
                    slice(center_x - half_size, center_x + half_size + 1),
                )
                patches.append(patch)
                centers.append((center_x, center_y))
                input_codes.append(np.median(source[patch], axis=(0, 1)).tolist())
        return input_codes, patches, centers

    def color_transfer_chart(
        self,
        background: str,
        *,
        columns: int,
        rows: int,
        scene: str = "circle-4000-center",
    ) -> JsonObject:
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
                "reason": (
                    f"requires {scene} {background} captures for both "
                    "materials and appearances"
                ),
            }

        input_codes, patches, centers = self.color_patch_samples(
            background,
            columns=columns,
            rows=rows,
        )
        center_x, center_y, shape_width, shape_height = self.shape_pixels(scene)
        radius_x = shape_width / 2
        radius_y = shape_height / 2
        sample_geometry = []
        for x, y in centers:
            normalized_radius = math.hypot(
                (x - center_x) / radius_x,
                (y - center_y) / radius_y,
            )
            sample_geometry.append(
                {
                    "x": x,
                    "y": y,
                    "depthInsideShapePixels": (
                        (1 - normalized_radius) * min(radius_x, radius_y)
                    ),
                }
            )

        result: JsonObject = {
            "available": True,
            "background": background,
            "scene": scene,
            "layout": {"columns": columns, "rows": rows},
            "sampleCount": len(patches),
            "inputCodes": input_codes,
            "sampleGeometry": sample_geometry,
        }
        control_codes: JsonObject = {}
        for appearance in ("light", "dark"):
            control_case = (
                background,
                "circle-0500-center",
                "none",
                appearance,
            )
            if control_case not in self.records:
                continue
            control = self.image(*control_case)
            control_codes[appearance] = [
                np.median(control[patch], axis=(0, 1)).tolist() for patch in patches
            ]
        if control_codes:
            result["capturedControlInputCodes"] = control_codes
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

    def dense_color_transfer(self) -> JsonObject:
        result = self.color_transfer_chart(
            "color-cube-9",
            columns=27,
            rows=27,
        )
        if result.get("available"):
            result["gridLevels"] = [0, 32, 64, 96, 128, 160, 192, 224, 255]
        return result

    def dense_color_holdout(self) -> JsonObject:
        result = self.color_transfer_chart(
            "color-cube-holdout-8",
            columns=32,
            rows=16,
        )
        if result.get("available"):
            result["gridLevels"] = [16, 48, 80, 112, 144, 176, 208, 240]
            result["relationship"] = (
                "strict midpoints between color-cube-9 fitting knots"
            )
        return result

    def dense_color_context_repeat(self) -> JsonObject:
        result = self.color_transfer_chart(
            "color-cube-9-permuted",
            columns=27,
            rows=27,
        )
        if result.get("available"):
            result["gridLevels"] = [0, 32, 64, 96, 128, 160, 192, 224, 255]
            result["relationship"] = (
                "same fitting colors in a bijectively permuted spatial order"
            )
        return result

    def dense_color_context_holdout(self) -> JsonObject:
        result = self.color_transfer_chart(
            "color-cube-9-shuffled",
            columns=27,
            rows=27,
        )
        if result.get("available"):
            result["gridLevels"] = [0, 32, 64, 96, 128, 160, 192, 224, 255]
            result["relationship"] = (
                "same fitting colors in an independently shuffled spatial order"
            )
        return result

    def dense_color_holdout_context_repeat(self) -> JsonObject:
        result = self.color_transfer_chart(
            "color-cube-holdout-8-shuffled",
            columns=32,
            rows=16,
        )
        if result.get("available"):
            result["gridLevels"] = [16, 48, 80, 112, 144, 176, 208, 240]
            result["relationship"] = (
                "same off-grid colors in an independently shuffled spatial order"
            )
        return result

    def color_context_training_charts(
        self,
        backgrounds: list[str],
        *,
        columns: int,
        rows: int,
        grid_levels: list[int],
        relationship: str,
    ) -> JsonObject:
        charts = {
            background: self.color_transfer_chart(
                background,
                columns=columns,
                rows=rows,
            )
            for background in backgrounds
        }
        for chart in charts.values():
            if chart.get("available"):
                chart["gridLevels"] = grid_levels
                chart["relationship"] = relationship
        available = [
            background for background, chart in charts.items() if chart.get("available")
        ]
        return {
            "available": len(available) == len(backgrounds),
            "requiredChartCount": len(backgrounds),
            "availableChartCount": len(available),
            "charts": charts,
        }

    def dense_color_context_training(self) -> JsonObject:
        return self.color_context_training_charts(
            CUBE_CONTEXT_TRAINING_BACKGROUNDS,
            columns=27,
            rows=27,
            grid_levels=[0, 32, 64, 96, 128, 160, 192, 224, 255],
            relationship=(
                "independently seeded fitting contexts; the legacy shuffled "
                "chart remains an untouched holdout"
            ),
        )

    def dense_color_holdout_context_training(self) -> JsonObject:
        return self.color_context_training_charts(
            HOLDOUT_CONTEXT_TRAINING_BACKGROUNDS,
            columns=32,
            rows=16,
            grid_levels=[16, 48, 80, 112, 144, 176, 208, 240],
            relationship=(
                "independently seeded off-grid fitting contexts; the legacy "
                "shuffled midpoint chart remains an untouched holdout"
            ),
        )

    @staticmethod
    def channel_statistics(image: FloatImage) -> JsonObject:
        flattened = image.reshape(-1, 3)
        return {
            "pixelCount": int(flattened.shape[0]),
            "meanCodes": flattened.mean(axis=0).tolist(),
            "standardDeviationCodes": flattened.std(axis=0).tolist(),
            "minimumCodes": flattened.min(axis=0).tolist(),
            "maximumCodes": flattened.max(axis=0).tolist(),
            "covarianceCodes": np.cov(
                flattened,
                rowvar=False,
                bias=True,
            ).tolist(),
        }

    def stochastic_probe_statistics(self) -> JsonObject:
        scene = "circle-4000-center"
        available = [
            background
            for background in STOCHASTIC_BACKGROUNDS
            if background in self.references
            and all(
                self.has_image(background, scene, "regular", appearance)
                for appearance in ("light", "dark")
            )
        ]
        if not available:
            return {
                "available": False,
                "reason": "requires v2.10 train/holdout stochastic probes",
            }

        records: JsonObject = {}
        margin = round(512 * self.backing_scale)
        for background in available:
            source = self.reference_image(background)
            region = (
                slice(margin, source.shape[0] - margin),
                slice(margin, source.shape[1] - margin),
            )
            record: JsonObject = {
                "source": self.channel_statistics(source[region]),
            }
            for appearance in ("light", "dark"):
                output = self.image(
                    background,
                    scene,
                    "regular",
                    appearance,
                )
                record[appearance] = self.channel_statistics(output[region])
            records[background] = record
        return {
            "available": len(available) == len(STOCHASTIC_BACKGROUNDS),
            "requiredProbeCount": len(STOCHASTIC_BACKGROUNDS),
            "availableProbeCount": len(available),
            "boundaryExclusionPixels": margin,
            "records": records,
        }

    def pixel_scale_giant_probe_statistics(self) -> JsonObject:
        scene = "circle-4000-center"
        available = [
            background
            for background in STOCHASTIC_BACKGROUNDS
            if background in self.references
            and all(
                self.has_image(background, scene, material, appearance)
                for material in ("regular", "clear")
                for appearance in ("light", "dark")
            )
        ]
        if not available:
            return {
                "available": False,
                "reason": (
                    "requires v2.12 boundary-free regular/clear pixel-scale "
                    "train/holdout probes"
                ),
            }

        margin = round(512 * self.backing_scale)
        records: JsonObject = {}
        for background in available:
            source = self.reference_image(background)
            region = (
                slice(margin, source.shape[0] - margin),
                slice(margin, source.shape[1] - margin),
            )
            records[background] = {
                "source": self.channel_statistics(source[region]),
                "outputs": {
                    material: {
                        appearance: self.channel_statistics(
                            self.image(
                                background,
                                scene,
                                material,
                                appearance,
                            )[region]
                        )
                        for appearance in ("light", "dark")
                    }
                    for material in ("regular", "clear")
                },
            }
        return {
            "available": len(available) == len(STOCHASTIC_BACKGROUNDS),
            "requiredProbeCount": len(STOCHASTIC_BACKGROUNDS),
            "availableProbeCount": len(available),
            "boundaryExclusionPixels": margin,
            "records": records,
        }

    def adaptive_spatial_probe_statistics(self) -> JsonObject:
        scene = "circle-4000-center"
        available = [
            background
            for background in ADAPTIVE_SPATIAL_PROBES
            if background in self.references
            and all(
                self.has_image(background, scene, material, appearance)
                for material in ("regular", "clear")
                for appearance in ("light", "dark")
            )
        ]
        if not available:
            return {
                "available": False,
                "reason": "requires v2.11 adaptive spatial probes",
            }

        margin = round(512 * self.backing_scale)
        records: JsonObject = {}
        for background in available:
            source = self.reference_image(background)
            region = (
                slice(margin, source.shape[0] - margin),
                slice(margin, source.shape[1] - margin),
            )
            record: JsonObject = {
                **ADAPTIVE_SPATIAL_PROBES[background],
                "source": self.channel_statistics(source[region]),
            }
            record["outputs"] = {
                material: {
                    appearance: self.channel_statistics(
                        self.image(
                            background,
                            scene,
                            material,
                            appearance,
                        )[region]
                    )
                    for appearance in ("light", "dark")
                }
                for material in ("regular", "clear")
            }
            records[background] = record

        translation: JsonObject = {"available": False}
        base_name = "context-rgb-grid-b0016-train"
        shifted_name = "context-rgb-grid-b0016-shifted-check"
        if base_name in available and shifted_name in available:
            shift_x = 37
            shift_y = 53

            def aligned_center(values: NDArray[Any]) -> NDArray[Any]:
                aligned = np.roll(
                    values,
                    shift=(shift_y, shift_x),
                    axis=(0, 1),
                )
                return aligned[
                    margin : aligned.shape[0] - margin,
                    margin : aligned.shape[1] - margin,
                ]

            base_source = self.reference_code_image(base_name)
            shifted_source = self.reference_code_image(shifted_name)
            center = (
                slice(margin, base_source.shape[0] - margin),
                slice(margin, base_source.shape[1] - margin),
            )
            translation = {
                "available": True,
                "baseBackground": base_name,
                "shiftedBackground": shifted_name,
                "sourceShiftPixels": [shift_x, shift_y],
                "sourceAfterAlignment": self.pixel_difference(
                    base_source[center],
                    aligned_center(shifted_source),
                ),
                "materialAfterAlignment": {
                    material: {
                        appearance: self.pixel_difference(
                            self.code_image(
                                base_name,
                                scene,
                                material,
                                appearance,
                            )[center],
                            aligned_center(
                                self.code_image(
                                    shifted_name,
                                    scene,
                                    material,
                                    appearance,
                                )
                            ),
                        )
                        for appearance in ("light", "dark")
                    }
                    for material in ("regular", "clear")
                },
            }

        return {
            "available": len(available) == len(ADAPTIVE_SPATIAL_PROBES),
            "requiredProbeCount": len(ADAPTIVE_SPATIAL_PROBES),
            "availableProbeCount": len(available),
            "boundaryExclusionPixels": margin,
            "records": records,
            "translationEquivariance": translation,
        }

    def clear_kernel_geometry_statistics(self) -> JsonObject:
        complete = [
            background
            for background in CLEAR_KERNEL_BACKGROUNDS
            if background in self.references
            and all(
                self.has_image(background, scene, "clear", appearance)
                for scene in CLEAR_KERNEL_SCENES
                for appearance in ("light", "dark")
            )
        ]
        if not complete:
            return {
                "available": False,
                "reason": (
                    "requires v2.13 independent clear-kernel probes across "
                    "centered-circle, translated-circle, and rectangle scenes"
                ),
            }

        margin = round(512 * self.backing_scale)
        records: JsonObject = {}

        def region_description(codes: CodeImage) -> JsonObject:
            contiguous = np.ascontiguousarray(codes)
            return {
                "rgbPixelSha256": hashlib.sha256(contiguous.tobytes()).hexdigest(),
                **self.channel_statistics(contiguous),
            }

        for background in complete:
            source = self.reference_code_image(background)
            region = (
                slice(margin, source.shape[0] - margin),
                slice(margin, source.shape[1] - margin),
            )
            outputs = {
                scene: {
                    appearance: self.code_image(
                        background,
                        scene,
                        "clear",
                        appearance,
                    )[region]
                    for appearance in ("light", "dark")
                }
                for scene in CLEAR_KERNEL_SCENES
            }
            metadata = CLEAR_KERNEL_PROBES.get(background)
            if metadata is None:
                metadata = {
                    "probeKind": "historical-independent-rgb-binary-pixels",
                    "role": (
                        "training" if background.endswith("-train") else "holdout"
                    ),
                    "blockSizePixels": 1,
                    "centerCode": 128,
                    "amplitudeCodes": 64,
                    "levels": [64, 192],
                    "seed": (
                        "0x31415926"
                        if background.endswith("-train")
                        else "0xa7f43c19"
                    ),
                }
            records[background] = {
                **metadata,
                "source": region_description(source[region]),
                "outputs": {
                    scene: {
                        appearance: region_description(codes)
                        for appearance, codes in appearances.items()
                    }
                    for scene, appearances in outputs.items()
                },
                "appearanceDifferences": {
                    scene: self.pixel_difference(
                        appearances["light"],
                        appearances["dark"],
                    )
                    for scene, appearances in outputs.items()
                },
                "geometryDifferencesFromCenteredCircle": {
                    scene: {
                        appearance: self.pixel_difference(
                            outputs["circle-4000-center"][appearance],
                            outputs[scene][appearance],
                        )
                        for appearance in ("light", "dark")
                    }
                    for scene in CLEAR_KERNEL_SCENES
                    if scene != "circle-4000-center"
                },
            }

        return {
            "available": len(complete) == len(CLEAR_KERNEL_BACKGROUNDS),
            "requiredProbeCount": len(CLEAR_KERNEL_BACKGROUNDS),
            "availableProbeCount": len(complete),
            "requiredOutputCount": (
                len(CLEAR_KERNEL_BACKGROUNDS) * len(CLEAR_KERNEL_SCENES) * 2
            ),
            "boundaryExclusionPixels": margin,
            "scenes": {
                scene: self.scenes.get(scene) for scene in CLEAR_KERNEL_SCENES
            },
            "records": records,
        }

    def base_color_charts(self) -> JsonObject:
        return {
            "fitting": self.color_transfer_chart(
                "color-cube-9",
                columns=27,
                rows=27,
                scene="circle-0500-center",
            ),
            "contextRepeat": self.color_transfer_chart(
                "color-cube-9-permuted",
                columns=27,
                rows=27,
                scene="circle-0500-center",
            ),
            "contextHoldout": self.color_transfer_chart(
                "color-cube-9-shuffled",
                columns=27,
                rows=27,
                scene="circle-0500-center",
            ),
            "offGridHoldout": self.color_transfer_chart(
                "color-cube-holdout-8",
                columns=32,
                rows=16,
                scene="circle-0500-center",
            ),
            "offGridContextRepeat": self.color_transfer_chart(
                "color-cube-holdout-8-shuffled",
                columns=32,
                rows=16,
                scene="circle-0500-center",
            ),
        }

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
                    "backgrounds": backgrounds,
                    "inputCodes": (inputs * 255).tolist(),
                    "outputCodes": (outputs * 255).tolist(),
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
        for scene_name in dict.fromkeys([*CIRCLE_SCENES, *POSITION_SCENES]):
            if ("checker-0128", scene_name, "regular", "light") not in self.records:
                continue
            center_x, center_y, width, height = self.shape_pixels(scene_name)
            radius_x = width / 2
            radius_y = height / 2
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
        for scene_name in dict.fromkeys([*CIRCLE_SCENES, *POSITION_SCENES]):
            if scene_name == "circle-4000-center":
                continue
            if not self.has_image("gray-128", scene_name, "regular", "light"):
                continue
            center_x, center_y, width, _ = self.shape_pixels(scene_name)
            radius = width / 2
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
        depths = [70, 50, 30, 20, 15, 10, 5, 2]
        center_x, center_y, width, _ = self.shape_pixels("circle-0500-center")
        radius = width / 2
        for appearance in ("light", "dark"):
            for overlay in ("regular", "clear"):
                source: list[FloatImage] = []
                output: list[FloatImage] = []
                for phase in range(4):
                    background = f"sine-x-p{period:04d}-ph{phase}"
                    source.append(
                        self.image_channel(
                            background,
                            "circle-0500-center",
                            "none",
                            appearance,
                        )
                    )
                    output.append(
                        self.image_channel(
                            background,
                            "circle-0500-center",
                            overlay,
                            appearance,
                        )
                    )
                source_complex = (source[0] - source[2]) + 1j * (source[1] - source[3])
                output_complex = (output[0] - output[2]) + 1j * (output[1] - output[3])
                response = output_complex / source_complex
                samples: JsonObject = {}
                for depth in depths:
                    x = round(center_x + radius - depth)
                    y = round(center_y)
                    values = response[y - 5 : y + 6, x]
                    unit = np.mean(values / np.maximum(np.abs(values), 1e-12))
                    samples[str(depth)] = {
                        "depthInsidePixels": depth,
                        "apparentOutwardDisplacementPixels": float(
                            np.angle(unit) * period / (2 * np.pi)
                        ),
                        "amplitudeRatio": float(np.median(np.abs(values))),
                    }
                result[f"{appearance}/{overlay}"] = samples
        return result

    def phase_response(self) -> JsonObject:
        periods = (32, 64, 128, 256, 512, 1024)
        candidate_scenes = (
            "circle-0256-center",
            "circle-0500-center",
            "circle-4000-center",
            "circle-0500-upper-left",
            "circle-0500-upper-right",
            "circle-0500-lower-left",
            "circle-0500-lower-right",
        )
        result: JsonObject = {}
        source_cache: dict[tuple[str, int], ComplexImage] = {}

        def source_complex(axis: str, period: int) -> ComplexImage:
            key = (axis, period)
            if key not in source_cache:
                phases = [
                    self.reference_channel(f"sine-{axis}-p{period:04d}-ph{phase}")
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
            center_x_value, center_y_value, width, _ = self.shape_pixels(scene_name)
            center_x = round(center_x_value)
            center_y = round(center_y_value)
            radius = width / 2
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
                                self.image_channel(
                                    background,
                                    scene_name,
                                    overlay,
                                    appearance,
                                )
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
                            cycle_fit = self.phase_cycle_fit(
                                source,
                                output_complex,
                                axis=axis,
                                period=period,
                                center_x=center_x,
                                center_y=center_y,
                                radius=radius,
                            )
                            if cycle_fit is not None:
                                period_result["cycleFit"] = cycle_fit

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

        spatial_variants: JsonObject = {}
        for appearance in ("light", "dark"):
            for overlay in ("regular", "clear"):
                variant = f"{appearance}/{overlay}"
                axes: JsonObject = {}
                for axis in ("x", "y"):
                    samples = {
                        scene: result.get(scene, {})
                        .get(variant, {})
                        .get(axis, {})
                        .get("256", {})
                        .get("cycleFit")
                        for scene in POSITION_SCENES
                    }
                    if not all(isinstance(sample, dict) for sample in samples.values()):
                        continue
                    amplitudes = [
                        float(sample["amplitudeRatio"]) for sample in samples.values()
                    ]
                    displacements = [
                        float(sample["apparentDisplacementPixels"])
                        for sample in samples.values()
                    ]
                    residuals = [
                        float(sample["normalizedComplexResidual"])
                        for sample in samples.values()
                    ]
                    axes[axis] = {
                        "periodPixels": 256,
                        "scenes": samples,
                        "amplitudeRange": max(amplitudes) - min(amplitudes),
                        "displacementRangePixels": max(displacements)
                        - min(displacements),
                        "normalizedResidualRange": max(residuals) - min(residuals),
                    }
                if axes:
                    spatial_variants[variant] = axes
        return {
            "available": bool(result),
            "phaseConvention": (
                "positive displacement is apparent motion toward the named "
                "outward edge; values are wrapped to +/- period/2"
            ),
            "spatialCycleConsistency": {
                "available": bool(spatial_variants),
                "method": (
                    "source-normalized complex least-squares fit over one complete "
                    "p256 cycle inside each 500-point circle"
                ),
                "variants": spatial_variants,
            },
            "scenes": result,
        }

    def spatial_consistency(self) -> JsonObject:
        required = [
            ("gray-128", scene, overlay, appearance)
            for scene in POSITION_SCENES
            for appearance in ("light", "dark")
            for overlay in ("regular", "clear")
        ]
        if not all(case in self.records for case in required):
            return {
                "available": False,
                "reason": "requires the v2.6 five-position gray-128 matrix",
            }

        result: JsonObject = {
            "available": True,
            "comparison": (
                "shape-aligned crops on uniform gray-128; all distances are "
                "physical capture pixels"
            ),
            "variants": {},
        }
        margin = max(1, round(100 * self.backing_scale))
        body_half_width = max(1, round(32 * self.backing_scale))
        for appearance in ("light", "dark"):
            for overlay in ("regular", "clear"):
                crops: dict[str, CodeImage] = {}
                body_medians: JsonObject = {}
                for scene in POSITION_SCENES:
                    image = self.code_image("gray-128", scene, overlay, appearance)
                    center_x, center_y, width, height = self.shape_pixels(scene)
                    half_width = round(width / 2) + margin
                    half_height = round(height / 2) + margin
                    x = round(center_x)
                    y = round(center_y)
                    crops[scene] = image[
                        y - half_height : y + half_height,
                        x - half_width : x + half_width,
                    ].copy()
                    body = image[
                        y - body_half_width : y + body_half_width + 1,
                        x - body_half_width : x + body_half_width + 1,
                    ]
                    body_medians[scene] = np.median(body, axis=(0, 1)).tolist()

                center = crops["circle-0500-center"]
                result["variants"][f"{appearance}/{overlay}"] = {
                    "bodyMedianRGB": body_medians,
                    "alignedCropVsCenter": {
                        scene: self.pixel_difference(center, crop)
                        for scene, crop in crops.items()
                        if scene != "circle-0500-center"
                    },
                }
        return result

    def dynamic_source_controls(self) -> JsonObject:
        sequences: JsonObject = {}
        for sequence in self.artifact.manifest.get("dynamicSequences", []):
            mode = str(sequence.get("mode"))
            crop = sequence.get("cropPixels")
            frames = sequence.get("frames")
            if not isinstance(crop, dict) or not isinstance(frames, list) or not frames:
                continue

            def reference_crop(background: str) -> CodeImage:
                source = self.reference_code_image(background)
                x = int(crop["x"])
                y = int(crop["y"])
                width = int(crop["width"])
                height = int(crop["height"])
                return source[y : y + height, x : x + width]

            controls: JsonObject = {}
            if mode in {
                "materialize",
                "wallpaper-transition",
                "wallpaper-transition-reverse",
            }:
                first = min(frames, key=lambda frame: int(frame["index"]))
                outgoing = str(
                    sequence.get(
                        "outgoingBackground",
                        sequence.get("background"),
                    )
                )
                controls["initialOutgoing"] = self.pixel_difference(
                    reference_crop(outgoing),
                    self.artifact.code_image(str(first["file"])),
                    sequence.get("analysisExclusionPixels", []),
                )

            post_settle = sequence.get("postSettleFrame")
            if mode in {
                "dematerialize",
                "wallpaper-transition",
                "wallpaper-transition-reverse",
            } and isinstance(post_settle, dict):
                expected = (
                    sequence.get("incomingBackground")
                    if mode
                    in {
                        "wallpaper-transition",
                        "wallpaper-transition-reverse",
                    }
                    else sequence.get(
                        "outgoingBackground",
                        sequence.get("background"),
                    )
                )
                controls["postSettleSource"] = self.pixel_difference(
                    reference_crop(str(expected)),
                    self.artifact.code_image(str(post_settle["file"])),
                )
            if controls:
                sequences[str(sequence["id"])] = controls
        return {
            "available": bool(sequences),
            "sequences": sequences,
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
            traversal_keys = {
                "forwardCold": "frames",
                "reverseWarm": "reverseFrames",
                "forwardColdRepeat": "repeatFrames",
            }
            traversals: JsonObject = {}
            hashes: dict[str, dict[int, str]] = {}
            for traversal, key in traversal_keys.items():
                frames = sequence.get(key, [])
                if not frames and key != "frames":
                    continue
                hashes[traversal] = {
                    int(frame["index"]): str(frame.get("pixelSha256"))
                    for frame in frames
                }
                traversals[traversal] = {
                    "frames": len(frames),
                    "uniqueFrames": len(
                        {str(frame.get("pixelSha256")) for frame in frames}
                    ),
                    "stableFrames": sum(
                        frame.get("stable") is True for frame in frames
                    ),
                    "progress": [frame.get("progress") for frame in frames],
                }
            forward = hashes.get("forwardCold", {})
            reverse = hashes.get("reverseWarm", {})
            repeat = hashes.get("forwardColdRepeat", {})
            records = {
                traversal: {
                    int(frame["index"]): frame for frame in sequence.get(key, [])
                }
                for traversal, key in traversal_keys.items()
            }

            def compare_traversal(name: str) -> JsonObject:
                candidate = records.get(name, {})
                differences: list[JsonObject] = []
                for index in sorted(records["forwardCold"].keys() & candidate.keys()):
                    left = records["forwardCold"][index]
                    right = candidate[index]
                    if left.get("pixelSha256") == right.get("pixelSha256"):
                        continue
                    difference = self.pixel_difference(
                        self.artifact.code_image(str(left["file"])),
                        self.artifact.code_image(str(right["file"])),
                    )
                    differences.append(
                        {
                            "index": index,
                            "progress": left.get("progress"),
                            **difference,
                        }
                    )
                return {
                    "differingStates": len(differences),
                    "differences": differences,
                    "maximumChangedPixels": max(
                        (
                            int(difference["changedPixels"])
                            for difference in differences
                        ),
                        default=0,
                    ),
                    "maximumChangedFraction": max(
                        (
                            float(difference["changedFraction"])
                            for difference in differences
                        ),
                        default=0,
                    ),
                    "maximumChannelDelta": max(
                        (
                            float(difference["maximumChannelDelta"])
                            for difference in differences
                        ),
                        default=0,
                    ),
                    "maximumMeanAbsoluteChannelDelta": max(
                        (
                            float(difference["meanAbsoluteChannelDelta"])
                            for difference in differences
                        ),
                        default=0,
                    ),
                }

            cold_comparison = (
                compare_traversal("forwardColdRepeat")
                if records.get("forwardColdRepeat")
                else None
            )
            reverse_comparison = (
                compare_traversal("reverseWarm") if records.get("reverseWarm") else None
            )
            result[str(sequence.get("id"))] = {
                "traversals": traversals,
                "coldRepeatDifferingStates": sum(
                    forward.get(index) != repeat.get(index)
                    for index in forward.keys() & repeat.keys()
                ),
                "warmReverseDifferingStates": sum(
                    forward.get(index) != reverse.get(index)
                    for index in forward.keys() & reverse.keys()
                ),
                "coldRepeatDifference": cold_comparison,
                "warmReverseDifference": reverse_comparison,
            }
        return {
            "available": bool(sequences),
            "sequences": result,
        }

    def run(self) -> JsonObject:
        manifest = self.artifact.manifest
        dynamic_sequences = manifest.get("dynamicSequences", [])
        sweep_sequences = manifest.get("sweepSequences", [])
        rig_version = manifest.get("rigVersion")
        analysis_schema_version = {
            "2.11.0": 8,
            "2.12.0": 9,
            "2.13.0": 10,
        }.get(str(rig_version), 7)
        result = {
            "analysisSchemaVersion": analysis_schema_version,
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
                "requestedDynamicModes": manifest.get("requestedDynamicModes"),
                "dynamicDurationSeconds": manifest.get("dynamicDurationSeconds"),
                "transitionOriginNormalized": manifest.get(
                    "transitionOriginNormalized"
                ),
                "exactSweepsRequested": manifest.get("exactSweepsRequested"),
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
                "dynamicPostSettleFrames": sum(
                    isinstance(sequence.get("postSettleFrame"), dict)
                    for sequence in dynamic_sequences
                ),
                "sweepSequences": len(sweep_sequences),
                "sweepFrames": sum(
                    sum(
                        len(sequence.get(key, []))
                        for key in ("frames", "reverseFrames", "repeatFrames")
                    )
                    for sequence in sweep_sequences
                ),
            },
            "toneTransfer": self.tone_transfer(),
            "denseToneTransfer": self.dense_tone_transfer(),
            "sparseColorTransfer": self.sparse_color_transfer(),
            "denseColorTransfer": self.dense_color_transfer(),
            "denseColorHoldout": self.dense_color_holdout(),
            "denseColorContextRepeat": self.dense_color_context_repeat(),
            "denseColorContextHoldout": self.dense_color_context_holdout(),
            "denseColorHoldoutContextRepeat": (
                self.dense_color_holdout_context_repeat()
            ),
            "denseColorContextTraining": self.dense_color_context_training(),
            "denseColorHoldoutContextTraining": (
                self.dense_color_holdout_context_training()
            ),
            "stochasticProbeStatistics": self.stochastic_probe_statistics(),
            "baseColorCharts": self.base_color_charts(),
            "checkerEdgeSpread": self.checker_blur(),
            "edgeGeometry": self.edge_geometry(),
            "phaseRefraction": self.phase_refraction(),
            "phaseResponse": self.phase_response(),
            "spatialConsistency": self.spatial_consistency(),
            "dynamicTiming": self.dynamic_timing(),
            "dynamicSourceControls": self.dynamic_source_controls(),
            "sweepStates": self.sweep_states(),
        }
        if rig_version in {"2.11.0", "2.12.0", "2.13.0"}:
            result["adaptiveSpatialProbeStatistics"] = (
                self.adaptive_spatial_probe_statistics()
            )
        if rig_version in {"2.12.0", "2.13.0"}:
            result["pixelScaleGiantProbeStatistics"] = (
                self.pixel_scale_giant_probe_statistics()
            )
        if rig_version == "2.13.0":
            result["clearKernelGeometryStatistics"] = (
                self.clear_kernel_geometry_statistics()
            )
        return result


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
