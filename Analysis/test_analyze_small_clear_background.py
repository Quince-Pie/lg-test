#!/usr/bin/env python3
"""Tests for retained exact small-clear Tghn construction."""

import json
import math
from pathlib import Path
import unittest

import analyze_small_clear_background as analysis
import analyze_transition_geometry_corpus_local_macos_26_6_1 as model


RESULT = Path(__file__).with_name("small_clear_background_result.json")


class SmallClearBackgroundTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_quad_stages_reciprocal_products_before_edge_addition(self) -> None:
        scale = model.float32(0.9682064056396484)
        positions, backdrop = analysis.predicted_position_and_backdrop_uv(
            scale=scale, bounds=(492, 444, 56, 56)
        )
        self.assertEqual(
            tuple(model.float32_bits(value) for value in positions[0]),
            (0x43FE13FC, 0x43E14A3A),
        )
        self.assertEqual(
            tuple(model.float32_bits(value) for value in positions[2]),
            (0x440D7FAF, 0x44011ACE),
        )
        self.assertEqual(
            tuple(model.float32_bits(value) for value in backdrop[0]),
            (0x37685E9A, 0xC0F7DC79),
        )
        self.assertEqual(
            tuple(model.float32_bits(value) for value in backdrop[2]),
            (0x42600003, 0x425FFFFC),
        )

    def test_backdrop_uv_uses_binary64_fma_not_plain_multiply(self) -> None:
        reciprocal = model.float32(1.8845384120941162)
        base = model.multiply32(256.0, reciprocal)
        fused = model.float32(math.fma(base, 1.0 / reciprocal, -256.0))
        plain = model.float32(base * (1.0 / reciprocal) - 256.0)
        self.assertEqual(model.float32_bits(fused), 0xA8BF458C)
        self.assertEqual(model.float32_bits(plain), 0xA9000000)

    def test_halfway_detector_distinguishes_exact_midpoint(self) -> None:
        lower = analysis.f32_from_bits(0x42832ECB)
        upper = analysis.f32_from_bits(0x42832ECC)
        midpoint = (float(lower) + float(upper)) / 2.0
        self.assertTrue(analysis.binary32_halfway(midpoint))
        self.assertFalse(analysis.binary32_halfway(math.nextafter(midpoint, upper)))

    def test_exact_retained_metrics_and_open_tie_boundary(self) -> None:
        self.assertEqual(self.result["stateCount"], 60)
        self.assertEqual(self.result["publicProfileNumericWordCount"], 2_760)
        exact_counts = {
            "activeColorHalf4": 960,
            "backdropUV": 480,
            "dynamicResamplingScale": 60,
            "positionXY": 480,
            "positionZW": 480,
            "profileDisplacementMatrix": 240,
            "publicProfileNumericFields": 2_760,
            "scissor": 240,
        }
        for name, count in exact_counts.items():
            metric = self.result["metrics"][name]
            self.assertEqual(metric["componentCount"], count)
            self.assertEqual(metric["mismatchedComponents"], 0)
            self.assertTrue(metric["exact"])
            self.assertEqual(metric["observedSHA256"], metric["predictedSHA256"])

        secondary = self.result["metrics"][
            "secondaryUVRetrospectiveCandidate"
        ]
        self.assertEqual(secondary["componentCount"], 480)
        self.assertEqual(secondary["mismatchedComponents"], 24)
        self.assertFalse(secondary["exact"])
        ties = self.result["secondaryUVTieBoundary"]
        self.assertEqual(ties["componentCount"], 120)
        self.assertEqual(ties["halfwayComponentCount"], 31)
        self.assertEqual(ties["mismatchedHalfwayDecisions"], 12)
        self.assertEqual(ties["mismatchedNonHalfwayComponents"], 0)
        self.assertFalse(ties["exactPolicyClosed"])

    def test_binding_topology_excludes_unclassified_tail_bytes(self) -> None:
        topology = self.result["bindingTopology"]
        self.assertEqual(topology["recordCountPerState"], 13)
        self.assertEqual(topology["fragmentProfileMeaningfulBytesPerState"], 210)
        self.assertEqual(topology["fragmentProfileMeaningfulByteCount"], 12_600)
        self.assertEqual(topology["excludedUnclassifiedVertexBytesPerVertex"], 8)
        self.assertEqual(
            topology["excludedUnclassifiedVertexByteCount"], 1_920
        )

    def test_status_does_not_promote_retrospective_ties_or_pixels(self) -> None:
        self.assertTrue(self.result["publicProfileNumericLawClosed"])
        self.assertTrue(self.result["TghnGeometryAndBackdropUVClosed"])
        self.assertFalse(self.result["fragmentPayloadByteConstructorClosed"])
        self.assertFalse(self.result["TghnSecondaryUVClosed"])
        self.assertFalse(self.result["TghnPixelSemanticsClosed"])
        self.assertFalse(self.result["TghnBoundaryClosed"])
        self.assertEqual(
            self.result["appleUnknownsBlockingGatedWalleIntegration"], 0
        )
        self.assertTrue(self.result["walleIntegrationMayBeginBehindGates"])
        self.assertFalse(self.result["productionParityAuthorized"])
        self.assertFalse(self.result["productionShaderChanged"])
        self.assertFalse(self.result["productionFlakeChanged"])


if __name__ == "__main__":
    unittest.main()
