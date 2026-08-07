#!/usr/bin/env python3
"""Tests for the presentation-lifetime matrix aggregator."""

import json
from pathlib import Path
import tempfile
import unittest

import aggregate_transition_presentation_lifetime_holdout as aggregator


ANALYSIS = Path(__file__).parent
PREREGISTRATION = ANALYSIS / (
    "transition_presentation_lifetime_holdout_preregistration.json"
)


def validation(identity: tuple[str, str, str, str], index: int) -> dict:
    material, appearance, direction, geometry = identity
    return {
        "transitionPresentationLifetimeHoldoutValidationSchemaVersion": 1,
        "status": "passed",
        "authority": "prospective-holdout",
        "caseId": f"case-{index}",
        "profile": {
            "material": material,
            "appearance": appearance,
            "direction": direction,
            "geometry": geometry,
        },
        "capture": {
            "debuggerUsed": False,
            "dynamicUniformReplayUsed": False,
            "sampleCount": 33,
            "presentationStateCount": 66,
            "glassBackgroundPresenceCount": 64,
            "glassForegroundPresenceCount": 62,
            "uniquePixelSHA256Count": 33,
            "uniquePngSHA256Count": 33,
            "pngTreeSHA256": f"{index + 16:064x}",
            "maximumStateBracketSeconds": 0.01 + index / 1000,
            "maximumWindowCaptureSeconds": 0.02 + index / 1000,
            "maximumAbsoluteRequestedProgressError": 0.001 + index / 10000,
        },
        "evidence": {
            "captureCommit": "a" * 40,
            "timelineSHA256": f"{index + 32:064x}",
        },
        "sealedConclusion": {
            "observerIndependentPresentationLifetimeTransferPassedForCase": True,
            "appearanceDependentRemovalObservedForCase": False,
            "productionShaderChanged": False,
            "liquidGlassParityEstablished": False,
        },
    }


class TransitionPresentationLifetimeAggregatorTests(unittest.TestCase):
    def write_matrix(self, directory: Path) -> list[Path]:
        paths = []
        for index, identity in enumerate(sorted(aggregator.CASES)):
            path = directory / f"validation-{index}.json"
            path.write_text(json.dumps(validation(identity, index)), encoding="utf-8")
            paths.append(path)
        return paths

    def test_complete_matrix_closes_only_lifetime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = self.write_matrix(Path(temporary))
            result = aggregator.aggregate(PREREGISTRATION, paths)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["caseCount"], 8)
        self.assertEqual(result["matrixTotals"]["windowServerFrameCount"], 264)
        self.assertEqual(result["matrixTotals"]["presentationStateCount"], 528)
        conclusion = result["sealedConclusion"]
        self.assertTrue(
            conclusion["observerIndependentPresentationLifetimeTransferPassed"]
        )
        self.assertTrue(conclusion["appearanceDependentPresentationRemovalLawRejected"])
        self.assertFalse(conclusion["physicalRetinaOutputTransferPassed"])
        self.assertFalse(conclusion["independentWalleZeroByteParityPassed"])
        self.assertFalse(conclusion["liquidGlassParityEstablished"])

    def test_mixed_capture_commits_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            paths = self.write_matrix(directory)
            changed = json.loads(paths[0].read_text(encoding="utf-8"))
            changed["evidence"]["captureCommit"] = "b" * 40
            paths[0].write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "one frozen commit"):
                aggregator.aggregate(PREREGISTRATION, paths)


if __name__ == "__main__":
    unittest.main()
