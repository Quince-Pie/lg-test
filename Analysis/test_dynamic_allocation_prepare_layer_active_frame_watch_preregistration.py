import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
WALLE_ROOT = REPOSITORY_ROOT.parent
PREREGISTRATION_PATH = ANALYSIS_ROOT / (
    "dynamic_allocation_prepare_layer_active_frame_watch_preregistration.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ActiveFrameWatchPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = json.loads(
            PREREGISTRATION_PATH.read_text(encoding="utf-8")
        )

    def test_opened_boundary_is_exact_and_does_not_overclaim(self) -> None:
        boundary = self.document["openedEvidenceBoundary"]
        self.assertEqual(boundary["runID"], 31022198697)
        self.assertEqual(boundary["selectedPrepareLayerRecursionDepth"], 4)
        self.assertTrue(boundary["sameInvocationFrameCorrelationProved"])
        self.assertTrue(boundary["selectedAggregateChainClosedAtMarker"])
        self.assertFalse(boundary["completeCausalWriterListProved"])

    def test_four_watch_lanes_cover_exactly_thirty_two_bytes(self) -> None:
        acceptance = self.document["acceptance"]
        offsets = acceptance["watchLaneOffsets"]
        byte_count = acceptance["watchLaneByteCount"]
        covered = {
            byte for offset in offsets for byte in range(offset, offset + byte_count)
        }
        self.assertEqual(offsets, [0, 8, 16, 24])
        self.assertEqual(covered, set(range(32)))
        self.assertTrue(acceptance["allFourHardwareWatchpointsRequired"])
        self.assertTrue(acceptance["fullThirtyTwoByteCoverageRequired"])

    def test_early_identity_excludes_future_x28(self) -> None:
        acceptance = self.document["acceptance"]
        self.assertEqual(acceptance["earlyIdentityFields"], ["threadID", "x19", "x29"])
        self.assertTrue(acceptance["futureX28IdentityForbiddenAtEpoch"])
        self.assertTrue(acceptance["watchRetirementWithLiveFrameRequired"])

    def test_sealed_acceptance_requires_new_contiguous_writer_evidence(self) -> None:
        acceptance = self.document["acceptance"]
        self.assertTrue(acceptance["zeroIgnoredWatchpointHitsRequired"])
        self.assertTrue(acceptance["contiguousFullAggregateChainRequired"])
        self.assertEqual(acceptance["minimumSelectedChangedTransitionCount"], 3)
        self.assertEqual(acceptance["minimumSelectedDistinctAggregateCount"], 4)
        self.assertTrue(acceptance["newChangedWriterOutsideSampledSitesRequired"])
        self.assertTrue(acceptance["lastAggregateMustBitMatchBothMarkers"])
        self.assertFalse(acceptance["writerInstructionSemanticsMayBeClaimed"])
        self.assertFalse(acceptance["productionShaderMayChange"])

    def test_input_program_hashes_are_frozen(self) -> None:
        integrity = self.document["inputProgramIntegrity"]
        paths = (
            (WALLE_ROOT / "shaders/frag.glsl", "productionShaderSHA256"),
            (
                REPOSITORY_ROOT
                / "Analysis/dynamic_allocation_prepare_layer_frame_writer_result.json",
                "openedFrameWriterResultSHA256",
            ),
            (
                REPOSITORY_ROOT
                / "Analysis/capture_prepare_layer_active_frame_watch_trace_lldb.py",
                "captureProgramSHA256",
            ),
            (
                REPOSITORY_ROOT
                / "Analysis/validate_prepare_layer_active_frame_watch_trace.py",
                "validatorSHA256",
            ),
            (
                REPOSITORY_ROOT
                / "Analysis/test_capture_prepare_layer_active_frame_watch_trace_lldb_source.py",
                "captureSourceTestSHA256",
            ),
            (
                REPOSITORY_ROOT
                / "Analysis/test_validate_prepare_layer_active_frame_watch_trace.py",
                "validatorTestSHA256",
            ),
            (
                REPOSITORY_ROOT
                / ".github/workflows/prepare-layer-active-frame-watch-introspect.yml",
                "workflowSHA256",
            ),
        )
        for path, field in paths:
            with self.subTest(path=path):
                self.assertEqual(sha256(path), integrity[field])
        self.assertFalse(integrity["productionShaderModifiedByExperiment"])

    def test_runtime_outcome_is_null_and_product_claims_remain_forbidden(self) -> None:
        self.assertIsNone(self.document["runtimeOutcomeFrozenBeforeRun"])
        forbidden = "\n".join(self.document["notAuthorizedBeforeAcceptance"])
        self.assertIn("production shader", forbidden)
        self.assertIn("parity", forbidden)
        self.assertIn("fixed number", forbidden)


if __name__ == "__main__":
    unittest.main()
