#!/usr/bin/env python3
"""Unit tests for the strict presentation-lifetime validator."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import validate_transition_presentation_lifetime_holdout as validator


ANALYSIS = Path(__file__).parent
PREREGISTRATION = ANALYSIS / (
    "transition_presentation_lifetime_holdout_preregistration.json"
)


def glass_filter(kind: str, face_opacity: float | None = None) -> dict:
    inputs = {} if face_opacity is None else {"inputFaceOpacity": face_opacity}
    return {
        "description": kind,
        "knownValues": {"type": kind},
        "inputValues": inputs,
    }


def state(direction: str, sample_index: int, face_opacity: float | None) -> dict:
    background, foreground, layer_count = validator.expected_topology(
        direction, sample_index
    )
    records = [
        {
            "path": validator.BACKGROUND_PATH,
            "class": "CABackdropLayer",
            "filters": (
                [glass_filter("glassBackground", face_opacity)] if background else []
            ),
        },
        {
            "path": validator.FOREGROUND_PATH,
            "class": "SyntheticSDFPortalLayer",
            "filters": [glass_filter("glassForeground")] if foreground else [],
        },
    ]
    records.extend(
        {
            "path": [100 + index],
            "class": "SyntheticLayer",
            "filters": [],
        }
        for index in range(layer_count - len(records))
    )
    return {"layerCount": layer_count, "records": records}


def preflight() -> dict:
    return {
        "localRetinaCaptureSessionPreflightSchemaVersion": 2,
        "passed": True,
        "displayActive": True,
        "displayAsleep": False,
        "sessionLocked": False,
        "sessionLoginDone": True,
        "sessionOnConsole": True,
        "backingScaleFactor": 2,
        "physicalPixels": [3456, 2234],
        "logicalPoints": [1728, 1117],
    }


def write_fixture(
    directory: Path,
    material: str,
    appearance: str,
    direction: str,
    geometry: str,
) -> Path:
    (directory / "capture-session-preflight.json").write_text(
        json.dumps(preflight()), encoding="utf-8"
    )
    (directory / "capture-context.txt").write_text(
        "\n".join(
            (
                "CAPTURE_COMMIT=" + "a" * 40,
                "NATIVE_CAPTURE_DEBUGGER_USED=0",
                "LG_TRANSITION_UNIFORMS=0",
                "LG_TRANSITION_TIMELINE=1",
                "LG_TRANSITION_CONTROLLED_BACKDROP=0",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    samples = []
    for sample_index in range(validator.SAMPLE_COUNT):
        requested = sample_index / (validator.SAMPLE_COUNT - 1)
        background, _, _ = validator.expected_topology(direction, sample_index)
        if not background:
            face_opacity = None
        elif sample_index in validator.DYNAMIC_INDICES:
            face_opacity = requested if direction == "materialize" else 1.0 - requested
        else:
            face_opacity = 1.0
        png_name = f"transition-{direction}-{sample_index:02d}-rgba8.png"
        png_payload = f"synthetic-png-{direction}-{sample_index}".encode()
        (directory / png_name).write_bytes(png_payload)
        png_sha256 = hashlib.sha256(png_payload).hexdigest()
        pixel_sha256 = hashlib.sha256(
            f"synthetic-pixels-{direction}-{sample_index}".encode()
        ).hexdigest()
        sample = {
            "executed": True,
            "progress": requested,
            "actualProgress": requested,
            "targetMediaTime": 1000.0 + sample_index,
            "stateBracketSeconds": 0.001,
            "presentationStateBeforeCapture": state(
                direction, sample_index, face_opacity
            ),
            "presentationStateAfterCapture": state(
                direction, sample_index, face_opacity
            ),
            "windowCapture": {
                "backend": "CGWindowListCreateImage",
                "width": 2048,
                "height": 2048,
                "bytesPerRow": 8192,
                "pixelBytes": 2048 * 2048 * 4,
                "pixelFormat": "RGBA8 premultiplied-last sRGB top-left",
                "pngFile": png_name,
                "pngBytes": len(png_payload),
                "pngSHA256": png_sha256,
                "pixelSHA256": pixel_sha256,
                "captureDurationSeconds": 0.001,
            },
        }
        if sample_index == validator.SAMPLE_COUNT - 1:
            sample.update(
                {
                    "endpointTopologyExpectedGlassBackground": (
                        direction == "materialize"
                    ),
                    "endpointTopologyMatchedBeforeCapture": True,
                    "endpointTopologyObservedFaceOpacity": (
                        1 if direction == "materialize" else None
                    ),
                }
            )
        samples.append(sample)
    timeline = {
        "schemaVersion": 5,
        "probe": "paced-presentation-state-window-timeline",
        "material": material,
        "appearance": appearance,
        "direction": direction,
        "geometry": {"name": geometry},
        "animationCurve": "linear",
        "animationDurationSeconds": 60,
        "sampleCount": 33,
        "sampleProgressRule": "index/(sampleCount-1)",
        "captureBackend": "CGWindowListCreateImage",
        "windowBackingScaleFactor": 2,
        "expectedWindowPixels": [2048, 2048],
        "failedSamples": 0,
        "dynamicBackgroundUniforms": {
            "schemaVersion": 9,
            "requested": False,
            "executed": False,
            "evidenceMode": "disabled",
            "presentationLayerReplayed": False,
        },
        "samples": samples,
    }
    path = directory / "transition-timeline.json"
    path.write_text(json.dumps(timeline), encoding="utf-8")
    return path


class TransitionPresentationLifetimeValidatorTests(unittest.TestCase):
    def validate_fixture(
        self,
        material: str,
        appearance: str,
        direction: str,
        geometry: str,
    ) -> dict:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = write_fixture(
            Path(temporary.name), material, appearance, direction, geometry
        )
        return validator.validate(
            path,
            PREREGISTRATION,
            material,
            appearance,
            direction,
            geometry,
        )

    def test_materialize_and_dematerialize_contracts_pass(self) -> None:
        for identity in (
            ("clear", "light", "materialize", "circle-452-center"),
            ("regular", "dark", "dematerialize", "circle-477-center"),
        ):
            with self.subTest(identity=identity):
                result = self.validate_fixture(*identity)
                self.assertEqual(result["status"], "passed")
                self.assertEqual(result["capture"]["sampleCount"], 33)
                self.assertEqual(result["capture"]["glassBackgroundPresenceCount"], 64)
                self.assertTrue(
                    result["sealedConclusion"][
                        "observerIndependentPresentationLifetimeTransferPassedForCase"
                    ]
                )
                self.assertFalse(
                    result["sealedConclusion"]["liquidGlassParityEstablished"]
                )

    def test_missing_dynamic_foreground_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = write_fixture(
                directory,
                "clear",
                "light",
                "materialize",
                "circle-452-center",
            )
            timeline = json.loads(path.read_text(encoding="utf-8"))
            records = timeline["samples"][30]["presentationStateAfterCapture"][
                "records"
            ]
            records[1]["filters"] = []
            path.write_text(json.dumps(timeline), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "glassForeground lifetime"):
                validator.validate(
                    path,
                    PREREGISTRATION,
                    "clear",
                    "light",
                    "materialize",
                    "circle-452-center",
                )

    def test_debugger_context_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = write_fixture(
                directory,
                "clear",
                "dark",
                "materialize",
                "circle-460-center",
            )
            context = directory / "capture-context.txt"
            context.write_text(
                context.read_text(encoding="utf-8").replace(
                    "NATIVE_CAPTURE_DEBUGGER_USED=0",
                    "NATIVE_CAPTURE_DEBUGGER_USED=1",
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "observer-independent"):
                validator.validate(
                    path,
                    PREREGISTRATION,
                    "clear",
                    "dark",
                    "materialize",
                    "circle-460-center",
                )


if __name__ == "__main__":
    unittest.main()
