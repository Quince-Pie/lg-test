import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from compare_runs import RunComparator
from measure import Artifact


class RunComparatorTests(unittest.TestCase):
    def test_reports_exact_and_measured_differences(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left_root = root / "left"
            right_root = root / "right"
            left_root.mkdir()
            right_root.mkdir()

            base = np.zeros((2, 2, 3), dtype=np.uint8)
            changed = base.copy()
            changed[1, 1] = [3, 0, 0]
            Image.fromarray(base).save(left_root / "exact.png")
            Image.fromarray(base).save(right_root / "exact.png")
            Image.fromarray(base).save(left_root / "changed.png")
            Image.fromarray(changed).save(right_root / "changed.png")

            def manifest() -> dict[str, object]:
                return {
                    "references": [
                        {
                            "background": "exact",
                            "file": "exact.png",
                            "pixelSha256": "same",
                        },
                        {
                            "background": "changed",
                            "file": "changed.png",
                            "pixelSha256": "left",
                        },
                    ],
                    "captures": [],
                    "dynamicSequences": [],
                    "sweepSequences": [],
                }

            left_manifest = manifest()
            right_manifest = manifest()
            right_manifest["references"][1]["pixelSha256"] = "right"
            comparator = RunComparator(
                Artifact(path=left_root, manifest=left_manifest),
                Artifact(path=right_root, manifest=right_manifest),
            )

            result = comparator.run()["references"]

            self.assertEqual(result["sharedCases"], 2)
            self.assertEqual(result["exactCases"], 1)
            self.assertEqual(result["differingCases"], 1)
            self.assertEqual(result["changedPixels"]["maximum"], 1)
            self.assertEqual(result["maximumChannelDelta"], 3)


if __name__ == "__main__":
    unittest.main()
