from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from validate import pixel_diff, validate


class ValidatorTests(unittest.TestCase):
    def test_pixel_diff_ignores_alpha(self) -> None:
        reference = bytes((10, 20, 30, 0, 40, 50, 60, 255))
        capture = bytes((10, 20, 30, 255, 43, 45, 67, 0))
        self.assertEqual(pixel_diff(reference, capture), (1, 7, 15 / 6))

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
                f"shots/probe__{overlay}__{appearance}.png"
                for appearance in ("light", "dark")
                for overlay in ("none", "regular", "clear")
            ]
            for relative in ["reference/probe.png", *shot_paths]:
                Image.frombytes("RGBA", (2, 2), pixels).save(root / relative)

            def file_hash(relative: str) -> str:
                return hashlib.sha256((root / relative).read_bytes()).hexdigest()

            pixel_hash = hashlib.sha256(pixels).hexdigest()
            manifest = {
                "schemaVersion": 2,
                "rigVersion": "2.0.0",
                "requestedSuite": "static",
                "osVersion": "Version 26.4",
                "osBuild": "25E246",
                "architecture": "arm64",
                "ciCommit": "test",
                "backingScaleFactor": 1,
                "reduceTransparency": False,
                "increaseContrast": False,
                "reduceMotion": False,
                "applicationActive": True,
                "windowKey": True,
                "references": [
                    {
                        "file": "reference/probe.png",
                        "background": "probe",
                        "family": "tone",
                        "fileSha256": file_hash("reference/probe.png"),
                        "pixelSha256": pixel_hash,
                        "pixelWidth": 2,
                        "pixelHeight": 2,
                    }
                ],
                "captures": [
                    {
                        "file": relative,
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
                        "controlDiff": {
                            "changedPixels": 0,
                            "maxChannelDelta": 0,
                            "meanAbsoluteChannelDelta": 0,
                        }
                        if overlay == "none"
                        else None,
                    }
                    for appearance in ("light", "dark")
                    for overlay in ("none", "regular", "clear")
                    for relative in [f"shots/probe__{overlay}__{appearance}.png"]
                ],
                "dynamicSequences": [],
            }
            (root / "manifest.json").write_text(json.dumps(manifest))

            findings, report = validate(root)

            self.assertEqual(findings.errors, [])
            self.assertTrue(report["valid"])


if __name__ == "__main__":
    unittest.main()
