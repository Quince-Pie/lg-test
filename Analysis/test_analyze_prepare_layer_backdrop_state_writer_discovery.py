#!/usr/bin/env python3
"""Checks for the live backdrop-state and writer-code analysis."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import analyze_prepare_layer_backdrop_state_writer_discovery as analysis


RESULT_PATH = (
    Path(__file__).resolve().parent
    / "dynamic_allocation_prepare_layer_backdrop_state_writer_discovery_analysis.json"
)
RESULT = json.loads(RESULT_PATH.read_text(encoding="utf-8"))


class BackdropStateWriterDiscoveryAnalysisTests(unittest.TestCase):
    def test_required_margin_keeps_shadow_offset_and_binary32_boundary(self) -> None:
        inputs = {
            "inputBleedAmount": 44.45,
            "inputShadowAmount": 75.0,
            "inputShadowOffset": {
                "hex": "00000000000000000000000000002040",
                "lengthBytes": 16,
            },
        }
        self.assertEqual(analysis.required_margin(inputs), 83.0)
        self.assertEqual(analysis.binary32(358.05), 358.04998779296875)

    def test_live_base_margin_and_return_are_direct_and_bit_exact(self) -> None:
        state = RESULT["liveSelectedState"]
        self.assertEqual(state["selectedBaseSource"], "layer")
        self.assertEqual(state["backdropRectF64"], [0.0, 0.0, 0.0, 0.0])
        self.assertEqual(state["layerRectF64"], [0.0, 0.0, 127.0, 127.0])
        self.assertEqual(state["marginF32"], 83.0)
        self.assertEqual(state["marginRawLittleEndianHex"], "0000a642")
        self.assertEqual(state["replayF64"], [-83.0, -83.0, 293.0, 293.0])
        self.assertTrue(state["bitExact"])

    def test_copy_writer_and_property_transport_are_exactly_retained(self) -> None:
        writer = RESULT["writerCode"]
        copy_symbol = writer["symbols"][analysis.COPY_RENDER_LAYER]
        self.assertEqual(copy_symbol["relativeStart"], 221640)
        self.assertEqual(copy_symbol["byteCount"], 1640)
        self.assertEqual(
            copy_symbol["codeSHA256"],
            "6547059b681d624b57e2996cfe4ebec262759a7e11be3f43cdd56e6b5794d838",
        )
        self.assertEqual(writer["propertyKey"], 502)
        self.assertEqual(writer["propertyValueType"], 18)
        self.assertTrue(writer["copyPathSemanticsDecoded"])
        self.assertFalse(writer["selectedCopyInvocationExecutionAuthenticated"])

    def test_allocation_corpus_is_exact_but_retrospective(self) -> None:
        corpus = RESULT["retrospectiveAllocationCorpus"]
        self.assertEqual(corpus["datasetCount"], 15)
        self.assertEqual(corpus["recordCount"], 480)
        self.assertEqual(corpus["exactMatchCount"], 480)
        self.assertEqual(corpus["maximumULPDistanceF32"], 0)
        self.assertEqual(corpus["maximumAbsoluteError"], 0.0)
        self.assertFalse(corpus["prospectiveAuthority"])
        self.assertIn(
            "constant across all 32 records", corpus["importantTemporalSemantics"]
        )

    def test_dynamic_topology_remains_open(self) -> None:
        topology = RESULT["dynamicTopology"]
        bracket = topology["dematerializePreterminalWidthBracketForSimpleThreshold"]
        self.assertEqual(bracket["largestDepthFourWidth"], 40.17463207244873)
        self.assertEqual(bracket["smallestDepthThreeWidth"], 43.40578079223633)
        self.assertTrue(topology["simpleWidthThresholdIsNotGeneral"])
        self.assertFalse(topology["dynamicTopologyLawDecoded"])

    def test_parity_authority_is_fail_closed(self) -> None:
        conclusion = RESULT["conclusion"]
        self.assertTrue(conclusion["liveBackdropBaseAndMarginFieldsCaptured"])
        self.assertTrue(conclusion["selectedBackdropBoundsReplayBitExact"])
        self.assertTrue(conclusion["renderMarginCopyPathSemanticsDecoded"])
        for key in (
            "selectedRenderMarginWriterExecutionAuthenticated",
            "upstreamMarginAllocationPolicyProspectivelyPassed",
            "dynamicTopologyLawDecoded",
            "prospectiveUnseenGeometryTransferPassed",
            "capturedInputOpticalParityPassedAcrossDeclaredDomain",
            "independentPrivateInputGenerationPassed",
            "physicalOutputTransferPassed",
            "independentWalleZeroByteFrameParityPassed",
            "productionShaderAuthorized",
            "liquidGlassParityEstablished",
        ):
            self.assertFalse(conclusion[key], key)


if __name__ == "__main__":
    unittest.main()
