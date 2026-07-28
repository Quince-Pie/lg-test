import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageCms

from validate import (
    Findings,
    pixel_diff,
    source_diff_is_within_tolerance,
    validate,
    validate_dynamic,
    validate_environment,
    validate_sweeps,
)


SRGB_PROFILE = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


class ValidatorTests(unittest.TestCase):
    def test_pixel_diff_ignores_alpha(self) -> None:
        reference = bytes((10, 20, 30, 0, 40, 50, 60, 255))
        capture = bytes((10, 20, 30, 255, 43, 45, 67, 0))
        self.assertEqual(pixel_diff(reference, capture), (1, 7, 15 / 6))

    def test_source_round_trip_tolerance_is_tight(self) -> None:
        tolerance = {
            "maximumChangedPixelFraction": 0.005,
            "maximumChannelDelta": 1,
            "maximumMeanAbsoluteChannelDelta": 0.002,
        }
        self.assertTrue(
            source_diff_is_within_tolerance((20_287, 1, 0.0011), 6_400_000, tolerance)
        )
        self.assertFalse(
            source_diff_is_within_tolerance((32_001, 1, 0.0011), 6_400_000, tolerance)
        )
        self.assertFalse(
            source_diff_is_within_tolerance((1, 2, 0.0001), 6_400_000, tolerance)
        )

    def test_missing_manifest_produces_actionable_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            findings, report = validate(Path(temporary))

            self.assertFalse(report["valid"])
            self.assertEqual(report["summary"]["errors"], 1)
            self.assertIn("cannot read manifest.json", findings.errors[0])

    def test_minimal_static_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "reference").mkdir()
            (root / "shots").mkdir()
            pixels = bytes((17, 33, 65, 255)) * 4
            shot_paths = [
                f"shots/probe__circle-0500-center__{overlay}__{appearance}.png"
                for appearance in ("light", "dark")
                for overlay in ("none", "regular", "clear")
            ]
            for relative in ["reference/probe.png", *shot_paths]:
                Image.frombytes("RGBA", (2, 2), pixels).save(
                    root / relative, icc_profile=SRGB_PROFILE
                )

            def file_hash(relative: str) -> str:
                return hashlib.sha256((root / relative).read_bytes()).hexdigest()

            pixel_hash = hashlib.sha256(pixels).hexdigest()
            image_metadata = {
                "bitsPerComponent": 8,
                "bitsPerPixel": 32,
                "bytesPerRow": 8,
                "colorSpace": "sRGB IEC61966-2.1",
                "alphaInfo": 1,
                "bitmapInfo": 16385,
            }
            manifest = {
                "schemaVersion": 3,
                "rigVersion": "2.1.0",
                "requestedSuite": "static",
                "osVersion": "Version 26.4",
                "osBuild": "25E246",
                "architecture": "arm64",
                "ciCommit": "test",
                "backingScaleFactor": 1,
                "canonicalPixelEncoding": "sRGB RGBA8 top-left opaque-alpha",
                "sourceRoundTripTolerance": {
                    "maximumChangedPixelFraction": 0.005,
                    "maximumChannelDelta": 1,
                    "maximumMeanAbsoluteChannelDelta": 0.002,
                },
                "reduceTransparency": False,
                "increaseContrast": False,
                "reduceMotion": False,
                "applicationActive": True,
                "windowKey": True,
                "preflightErrors": [],
                "references": [
                    {
                        "file": "reference/probe.png",
                        "background": "probe",
                        "family": "tone",
                        "fileSha256": file_hash("reference/probe.png"),
                        "pixelSha256": pixel_hash,
                        "pixelWidth": 2,
                        "pixelHeight": 2,
                        "image": image_metadata,
                    }
                ],
                "captures": [
                    {
                        "file": relative,
                        "referenceFile": "reference/probe.png",
                        "controlFile": (
                            f"shots/probe__circle-0500-center__none__{appearance}.png"
                        ),
                        "background": "probe",
                        "family": "tone",
                        "overlay": overlay,
                        "appearance": appearance,
                        "scene": "circle-0500-center",
                        "sha256": file_hash(relative),
                        "pixelSha256": pixel_hash,
                        "pixelWidth": 2,
                        "pixelHeight": 2,
                        "stable": True,
                        "stabilitySamples": 2,
                        "sourceDiff": {
                            "changedPixels": 0,
                            "maxChannelDelta": 0,
                            "meanAbsoluteChannelDelta": 0,
                        }
                        if overlay == "none"
                        else None,
                        "sourceImage": image_metadata,
                        "savedImage": image_metadata,
                    }
                    for appearance in ("light", "dark")
                    for overlay in ("none", "regular", "clear")
                    for relative in [
                        f"shots/probe__circle-0500-center__{overlay}__{appearance}.png"
                    ]
                ],
                "dynamicSequences": [],
            }
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            findings, report = validate(root)

            self.assertEqual(findings.errors, [])
            self.assertTrue(report["valid"])

    def test_dynamic_grid_accepts_deadline_skips(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "reference").mkdir()
            (root / "dynamic").mkdir()

            image_metadata = {
                "bitsPerComponent": 8,
                "bitsPerPixel": 32,
                "bytesPerRow": 8,
                "colorSpace": "sRGB IEC61966-2.1",
                "alphaInfo": 1,
                "bitmapInfo": 16385,
            }
            source_pixels = bytes((0, 0, 0, 255)) * 4
            reference = root / "reference/dynamic-coded-field.png"
            Image.frombytes("RGBA", (2, 2), source_pixels).save(
                reference, icc_profile=SRGB_PROFILE
            )

            def file_hash(path: Path) -> str:
                return hashlib.sha256(path.read_bytes()).hexdigest()

            grid_indices = [0, 7, 14, 21, 28, 35, 42, 49, 56, 60]
            sequences = []
            for mode in (
                "materialize",
                "resize",
                "translate",
                "morph",
                "wallpaper-wipe",
            ):
                for overlay in ("regular", "clear"):
                    for appearance in ("light", "dark"):
                        sequence_id = f"{mode}__{overlay}__{appearance}"
                        sequence_dir = root / "dynamic" / sequence_id
                        sequence_dir.mkdir()
                        frames = []
                        for position, grid_index in enumerate(grid_indices):
                            value = position
                            pixels = bytes((value, value * 2, value * 3, 255)) * 4
                            relative = (
                                f"dynamic/{sequence_id}/frame-{grid_index:04d}.png"
                            )
                            path = root / relative
                            Image.frombytes("RGBA", (2, 2), pixels).save(
                                path, icc_profile=SRGB_PROFILE
                            )
                            target = grid_index / 60
                            frames.append(
                                {
                                    "file": relative,
                                    "index": grid_index,
                                    "targetSeconds": target,
                                    "actualSeconds": target,
                                    "timingErrorSeconds": 0,
                                    "captureDurationSeconds": 0.005,
                                    "fileSha256": file_hash(path),
                                    "pixelSha256": hashlib.sha256(pixels).hexdigest(),
                                    "pixelWidth": 2,
                                    "pixelHeight": 2,
                                    "captureBackend": "unit-test",
                                    "sourceImage": image_metadata,
                                    "savedImage": image_metadata,
                                }
                            )
                        sequences.append(
                            {
                                "id": sequence_id,
                                "mode": mode,
                                "overlay": overlay,
                                "appearance": appearance,
                                "background": "dynamic-coded-field",
                                "durationSeconds": 1,
                                "animationCurve": "linear",
                                "cropPixels": {
                                    "x": 0,
                                    "y": 0,
                                    "width": 2,
                                    "height": 2,
                                },
                                "frames": frames,
                            }
                        )

            manifest = {
                "schemaVersion": 3,
                "rigVersion": "2.1.0",
                "requestedSuite": "dynamic",
                "osVersion": "Version 26.4",
                "osBuild": "25E246",
                "architecture": "arm64",
                "ciCommit": "test",
                "backingScaleFactor": 1,
                "canonicalPixelEncoding": "sRGB RGBA8 top-left opaque-alpha",
                "sourceRoundTripTolerance": {
                    "maximumChangedPixelFraction": 0.005,
                    "maximumChannelDelta": 1,
                    "maximumMeanAbsoluteChannelDelta": 0.002,
                },
                "reduceTransparency": False,
                "increaseContrast": False,
                "reduceMotion": False,
                "applicationActive": True,
                "windowKey": True,
                "preflightErrors": [],
                "dynamicFrameCount": 61,
                "dynamicDurationSeconds": 1,
                "references": [
                    {
                        "file": "reference/dynamic-coded-field.png",
                        "background": "dynamic-coded-field",
                        "family": "dynamic",
                        "fileSha256": file_hash(reference),
                        "pixelSha256": hashlib.sha256(source_pixels).hexdigest(),
                        "pixelWidth": 2,
                        "pixelHeight": 2,
                        "image": image_metadata,
                    }
                ],
                "captures": [],
                "dynamicSequences": sequences,
            }
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            findings, report = validate(root)

            self.assertEqual(findings.errors, [])
            self.assertTrue(report["valid"])
            self.assertEqual(
                {timing["droppedTargets"] for timing in report["dynamicTiming"]},
                {51},
            )

    def test_exact_state_sweep_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "sweeps").mkdir()
            image_metadata = {
                "bitsPerComponent": 8,
                "bitsPerPixel": 32,
                "bytesPerRow": 8,
                "colorSpace": "sRGB IEC61966-2.1",
                "alphaInfo": 1,
                "bitmapInfo": 16385,
            }

            sequences = []
            for mode in ("resize", "translate", "morph", "wallpaper-wipe"):
                for overlay in ("regular", "clear"):
                    for appearance in ("light", "dark"):
                        sequence_id = f"sweep__{mode}__{overlay}__{appearance}"
                        sequence_dir = root / "sweeps" / sequence_id
                        sequence_dir.mkdir()
                        frames = []
                        for index in range(17):
                            pixels = bytes((index, index * 2, index * 3, 255)) * 4
                            relative = f"sweeps/{sequence_id}/frame-{index:04d}.png"
                            path = root / relative
                            Image.frombytes("RGBA", (2, 2), pixels).save(
                                path, icc_profile=SRGB_PROFILE
                            )
                            frames.append(
                                {
                                    "file": relative,
                                    "index": index,
                                    "progress": index / 16,
                                    "fileSha256": hashlib.sha256(
                                        path.read_bytes()
                                    ).hexdigest(),
                                    "pixelSha256": hashlib.sha256(pixels).hexdigest(),
                                    "pixelWidth": 2,
                                    "pixelHeight": 2,
                                    "captureBackend": "unit-test",
                                    "stable": True,
                                    "stabilitySamples": 2,
                                    "sourceImage": image_metadata,
                                    "savedImage": image_metadata,
                                }
                            )
                        sequences.append(
                            {
                                "id": sequence_id,
                                "mode": mode,
                                "overlay": overlay,
                                "appearance": appearance,
                                "background": "dynamic-coded-field",
                                "cropPixels": {
                                    "x": 0,
                                    "y": 0,
                                    "width": 2,
                                    "height": 2,
                                },
                                "frames": frames,
                            }
                        )

            findings = Findings()
            summary = validate_sweeps(
                root,
                {
                    "schemaVersion": 4,
                    "requestedSuite": "dynamic",
                    "sweepSequences": sequences,
                },
                {"dynamic-coded-field": {}},
                findings,
            )

            self.assertEqual(findings.errors, [])
            self.assertEqual(summary, {"sequences": 16, "frames": 272})

    def test_static_suite_does_not_require_dynamic_sweeps(self) -> None:
        findings = Findings()
        summary = validate_sweeps(
            Path("."),
            {
                "schemaVersion": 4,
                "requestedSuite": "static",
                "sweepSequences": [],
            },
            {},
            findings,
        )

        self.assertEqual(findings.errors, [])
        self.assertEqual(summary, {"sequences": 0, "frames": 0})

    def test_v25_requires_measured_raster_clock_preflight(self) -> None:
        manifest = {
            "schemaVersion": 4,
            "rigVersion": "2.5.0",
            "requestedSuite": "dynamic",
            "canonicalPixelEncoding": "sRGB RGBA8 top-left opaque-alpha",
            "osVersion": "Version 26.4",
            "reduceTransparency": False,
            "increaseContrast": False,
            "reduceMotion": False,
            "applicationActive": True,
            "windowKey": True,
            "preflightErrors": [],
            "presentationClockPreflight": {
                "backend": "appkit-raster-monotonic",
                "staticQuarterProgress": 0.25,
                "staticThreeQuarterProgress": 0.75,
                "liveMidpointProgress": 0.51,
                "liveEndpointProgress": 1.0,
            },
            "sourceRoundTripTolerance": {
                "maximumChangedPixelFraction": 0.005,
                "maximumChannelDelta": 1,
                "maximumMeanAbsoluteChannelDelta": 0.002,
            },
            "backingScaleFactor": 1,
        }

        valid = Findings()
        validate_environment(manifest, valid)
        self.assertEqual(valid.errors, [])

        manifest["presentationClockPreflight"]["liveMidpointProgress"] = 0
        invalid = Findings()
        validate_environment(manifest, invalid)
        self.assertTrue(
            any("liveMidpointProgress" in error for error in invalid.errors)
        )

        manifest.update(
            {
                "schemaVersion": 5,
                "rigVersion": "2.6.0",
                "requestedDynamicModes": [
                    "materialize",
                    "dematerialize",
                    "wallpaper-transition",
                ],
                "transitionOriginNormalized": [0.25, 0.30],
                "exactSweepsRequested": False,
            }
        )
        manifest["presentationClockPreflight"]["liveMidpointProgress"] = 0.51
        v26 = Findings()
        validate_environment(manifest, v26)
        self.assertEqual(v26.errors, [])

        manifest["rigVersion"] = "2.7.0"
        v27 = Findings()
        validate_environment(manifest, v27)
        self.assertEqual(v27.errors, [])

    def test_schema4_presentation_clock_and_exclusion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "reference").mkdir()
            sequence_id = "wallpaper-wipe__regular__light"
            sequence_dir = root / "dynamic" / sequence_id
            sequence_dir.mkdir(parents=True)
            image_metadata = {
                "bitsPerComponent": 8,
                "bitsPerPixel": 32,
                "bytesPerRow": 8,
                "colorSpace": "sRGB IEC61966-2.1",
                "alphaInfo": 1,
                "bitmapInfo": 16385,
            }
            reference_path = root / "reference/dynamic-coded-field.png"
            reference_pixels = bytes((0, 0, 0, 255)) * 4
            Image.frombytes("RGBA", (2, 2), reference_pixels).save(
                reference_path, icc_profile=SRGB_PROFILE
            )
            frames = []
            for index in range(10):
                pixels = bytes((index, index * 2, index * 3, 255)) * 4
                relative = f"dynamic/{sequence_id}/frame-{index:04d}.png"
                path = root / relative
                Image.frombytes("RGBA", (2, 2), pixels).save(
                    path, icc_profile=SRGB_PROFILE
                )
                progress = index / 9
                frames.append(
                    {
                        "file": relative,
                        "index": index,
                        "targetSeconds": progress,
                        "actualSeconds": progress,
                        "timingErrorSeconds": 0,
                        "captureDurationSeconds": 0.005,
                        "presentationProgress": progress,
                        "fileSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "pixelSha256": hashlib.sha256(pixels).hexdigest(),
                        "pixelWidth": 2,
                        "pixelHeight": 2,
                        "captureBackend": "unit-test",
                        "sourceImage": image_metadata,
                        "savedImage": image_metadata,
                    }
                )
            sequence = {
                "id": sequence_id,
                "mode": "wallpaper-wipe",
                "overlay": "regular",
                "appearance": "light",
                "background": "dynamic-coded-field",
                "durationSeconds": 1,
                "animationCurve": "linear",
                "presentationClock": "swiftui-animatable-frame",
                "samplingMethod": "continuous-off-main-presentation-binned",
                "captureAttempts": 20,
                "decodedSamples": 19,
                "transientFailures": 1,
                "cropPixels": {
                    "x": 0,
                    "y": 0,
                    "width": 2,
                    "height": 2,
                },
                "analysisExclusionPixels": [{"x": 0, "y": 0, "width": 2, "height": 2}],
                "frames": frames,
            }
            manifest = {
                "schemaVersion": 4,
                "rigVersion": "2.4.0",
                "requestedSuite": "static",
                "backingScaleFactor": 1,
                "dynamicFrameCount": 10,
                "dynamicDurationSeconds": 1,
                "sourceRoundTripTolerance": {
                    "maximumChangedPixelFraction": 0.005,
                    "maximumChannelDelta": 1,
                    "maximumMeanAbsoluteChannelDelta": 0.002,
                },
                "dynamicSequences": [sequence],
            }
            references = {
                "dynamic-coded-field": {"file": "reference/dynamic-coded-field.png"}
            }

            findings = Findings()
            summary, _ = validate_dynamic(root, manifest, references, findings)

            self.assertEqual(findings.errors, [])
            self.assertEqual(summary, {"sequences": 1, "frames": 10})

            sequence["analysisExclusionPixels"] = []
            invalid = Findings()
            validate_dynamic(root, manifest, references, invalid)
            self.assertTrue(
                any("analysisExclusionPixels" in error for error in invalid.errors)
            )

            sequence["analysisExclusionPixels"] = [
                {"x": 0, "y": 0, "width": 2, "height": 2}
            ]
            sequence["presentationClock"] = "core-animation-layer"
            wrong_clock = Findings()
            validate_dynamic(root, manifest, references, wrong_clock)
            self.assertTrue(
                any("presentationClock" in error for error in wrong_clock.errors)
            )

            manifest["rigVersion"] = "2.5.0"
            sequence.update(
                {
                    "id": "materialize__regular__light",
                    "mode": "materialize",
                    "analysisExclusionPixels": [],
                    "presentationClock": "appkit-raster-monotonic",
                }
            )
            raster_clock = Findings()
            validate_dynamic(root, manifest, references, raster_clock)
            self.assertEqual(raster_clock.errors, [])

            sequence["presentationClock"] = "core-animation-layer"
            obsolete_clock = Findings()
            validate_dynamic(root, manifest, references, obsolete_clock)
            self.assertTrue(
                any("presentationClock" in error for error in obsolete_clock.errors)
            )

    def test_schema5_two_source_transition_and_post_settle_control(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "reference").mkdir()
            sequence_id = "wallpaper-transition__regular__light"
            sequence_dir = root / "dynamic" / sequence_id
            sequence_dir.mkdir(parents=True)
            image_metadata = {
                "bitsPerComponent": 8,
                "bitsPerPixel": 32,
                "bytesPerRow": 8,
                "colorSpace": "sRGB IEC61966-2.1",
                "alphaInfo": 1,
                "bitmapInfo": 16385,
            }
            outgoing_pixels = bytes((0, 0, 0, 255)) * 10
            incoming_pixels = bytes((200, 100, 50, 255)) * 10

            def save(relative: str, pixels: bytes) -> Path:
                path = root / relative
                Image.frombytes("RGBA", (2, 5), pixels).save(
                    path, icc_profile=SRGB_PROFILE
                )
                return path

            outgoing_path = save("reference/dynamic-coded-field.png", outgoing_pixels)
            incoming_path = save(
                "reference/dynamic-coded-field-incoming.png", incoming_pixels
            )

            def reference_record(
                path: Path, name: str, pixels: bytes
            ) -> dict[str, object]:
                return {
                    "file": str(path.relative_to(root)),
                    "background": name,
                    "family": "dynamic",
                    "fileSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "pixelSha256": hashlib.sha256(pixels).hexdigest(),
                    "pixelWidth": 2,
                    "pixelHeight": 5,
                    "image": image_metadata,
                }

            frames = []
            for index in range(10):
                pixels = (
                    outgoing_pixels
                    if index == 0
                    else bytes((index, index * 2, index * 3, 255)) * 10
                )
                relative = f"dynamic/{sequence_id}/frame-{index:04d}.png"
                path = save(relative, pixels)
                progress = index / 9
                frames.append(
                    {
                        "file": relative,
                        "index": index,
                        "targetSeconds": progress,
                        "actualSeconds": progress,
                        "timingErrorSeconds": 0,
                        "captureDurationSeconds": 0.005,
                        "presentationProgress": progress,
                        "fileSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "pixelSha256": hashlib.sha256(pixels).hexdigest(),
                        "pixelWidth": 2,
                        "pixelHeight": 5,
                        "captureBackend": "unit-test",
                        "sourceImage": image_metadata,
                        "savedImage": image_metadata,
                    }
                )
            post_relative = f"dynamic/{sequence_id}/post-settle.png"
            post_path = save(post_relative, incoming_pixels)
            sequence = {
                "id": sequence_id,
                "mode": "wallpaper-transition",
                "overlay": "regular",
                "appearance": "light",
                "background": "dynamic-coded-field",
                "outgoingBackground": "dynamic-coded-field",
                "incomingBackground": "dynamic-coded-field-incoming",
                "probeRole": "walle-two-wallpaper-reference",
                "stateIsolation": "fresh-swiftui-dynamic-subtree-per-sequence",
                "durationSeconds": 1,
                "animationCurve": "linear",
                "phaseSchedule": {
                    "expansionEnd": 0.62,
                    "dematerializeStart": 0.66,
                    "dematerializeEnd": 1.0,
                },
                "presentationClock": "appkit-raster-monotonic",
                "samplingMethod": "continuous-off-main-presentation-binned",
                "captureAttempts": 20,
                "decodedSamples": 19,
                "transientFailures": 1,
                "cropPixels": {"x": 0, "y": 0, "width": 2, "height": 5},
                "analysisExclusionPixels": [{"x": 0, "y": 0, "width": 2, "height": 4}],
                "frames": frames,
                "postSettleDelaySeconds": 0.9,
                "postSettleFrame": {
                    "file": post_relative,
                    "fileSha256": hashlib.sha256(post_path.read_bytes()).hexdigest(),
                    "pixelSha256": hashlib.sha256(incoming_pixels).hexdigest(),
                    "pixelWidth": 2,
                    "pixelHeight": 5,
                    "captureBackend": "unit-test",
                    "stable": True,
                    "stabilitySamples": 3,
                    "sourceImage": image_metadata,
                    "savedImage": image_metadata,
                },
            }
            references = {
                "dynamic-coded-field": reference_record(
                    outgoing_path, "dynamic-coded-field", outgoing_pixels
                ),
                "dynamic-coded-field-incoming": reference_record(
                    incoming_path,
                    "dynamic-coded-field-incoming",
                    incoming_pixels,
                ),
            }
            manifest = {
                "schemaVersion": 5,
                "rigVersion": "2.6.0",
                "requestedSuite": "static",
                "backingScaleFactor": 1,
                "settleSeconds": 0.45,
                "dynamicFrameCount": 10,
                "dynamicDurationSeconds": 1,
                "sourceRoundTripTolerance": {
                    "maximumChangedPixelFraction": 0.005,
                    "maximumChannelDelta": 1,
                    "maximumMeanAbsoluteChannelDelta": 0.002,
                },
                "dynamicSequences": [sequence],
            }

            findings = Findings()
            summary, timing = validate_dynamic(root, manifest, references, findings)

            self.assertEqual(findings.errors, [])
            self.assertEqual(
                summary,
                {"sequences": 1, "frames": 10, "postSettleFrames": 1},
            )
            self.assertTrue(timing[0]["initialControlWithinTolerance"])
            self.assertTrue(timing[0]["postSettleControlWithinTolerance"])

    def test_schema5_sweeps_measure_repeatability_and_hysteresis(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sequence_id = "sweep__wallpaper-transition__regular__light"
            sequence_dir = root / "sweeps" / sequence_id
            sequence_dir.mkdir(parents=True)
            image_metadata = {
                "bitsPerComponent": 8,
                "bitsPerPixel": 32,
                "bytesPerRow": 8,
                "colorSpace": "sRGB IEC61966-2.1",
                "alphaInfo": 1,
                "bitmapInfo": 16385,
            }

            def traversal(key: str, indices: list[int]) -> list[dict[str, object]]:
                records = []
                for index in indices:
                    pixels = bytes((index, index * 2, index * 3, 255)) * 4
                    relative = f"sweeps/{sequence_id}/{key}-{index:04d}.png"
                    path = root / relative
                    Image.frombytes("RGBA", (2, 2), pixels).save(
                        path, icc_profile=SRGB_PROFILE
                    )
                    records.append(
                        {
                            "file": relative,
                            "index": index,
                            "progress": index / 16,
                            "fileSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "pixelSha256": hashlib.sha256(pixels).hexdigest(),
                            "pixelWidth": 2,
                            "pixelHeight": 2,
                            "captureBackend": "unit-test",
                            "stable": True,
                            "stabilitySamples": 3,
                            "sourceImage": image_metadata,
                            "savedImage": image_metadata,
                        }
                    )
                return records

            sequence = {
                "id": sequence_id,
                "mode": "wallpaper-transition",
                "overlay": "regular",
                "appearance": "light",
                "background": "dynamic-coded-field",
                "outgoingBackground": "dynamic-coded-field",
                "incomingBackground": "dynamic-coded-field-incoming",
                "probeRole": "walle-two-wallpaper-expansion",
                "stateIsolation": "cold-forward/warm-reverse/cold-repeat",
                "traversals": [
                    "forward-cold",
                    "reverse-warm",
                    "forward-cold-repeat",
                ],
                "stabilityConfirmationSeconds": 0.1,
                "cropPixels": {"x": 0, "y": 0, "width": 2, "height": 2},
                "frames": traversal("frame", list(range(17))),
                "reverseFrames": traversal("reverse-frame", list(reversed(range(17)))),
                "repeatFrames": traversal("repeat-frame", list(range(17))),
            }
            findings = Findings()
            summary = validate_sweeps(
                root,
                {
                    "schemaVersion": 5,
                    "requestedSuite": "static",
                    "exactSweepsRequested": True,
                    "sweepSequences": [sequence],
                },
                {
                    "dynamic-coded-field": {},
                    "dynamic-coded-field-incoming": {},
                },
                findings,
            )

            self.assertEqual(findings.errors, [])
            self.assertEqual(findings.warnings, [])
            self.assertEqual(summary["sequences"], 1)
            self.assertEqual(summary["frames"], 51)
            self.assertEqual(summary["coldRepeatDifferingStates"], 0)
            self.assertEqual(summary["warmReverseDifferingStates"], 0)


if __name__ == "__main__":
    unittest.main()
