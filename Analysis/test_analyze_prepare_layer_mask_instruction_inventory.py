#!/usr/bin/env python3
"""Tests for the opened output-blind helper inventory result."""

from __future__ import annotations

import inspect
import json
import unittest
from pathlib import Path

import analyze_prepare_layer_mask_instruction_inventory as analyzer
import validate_prepare_layer_mask_inventory_selected_trace as selected_validator


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
RESULT_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_mask_instruction_inventory_result.json"
)
ARTIFACT_ROOT = (
    REPOSITORY_ROOT.parent
    / "artifacts"
    / "gh-run-31065261980"
    / "liquid-glass-prepare-layer-mask-inventory-calibration-31065261980"
    / "transition-inventory"
)


class PrepareLayerMaskInstructionInventoryAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_original_red_gate_is_preserved(self) -> None:
        result = self.result
        self.assertEqual(result["runID"], 31065261980)
        self.assertFalse(result["originalProspectiveValidatorPassed"])
        self.assertEqual(
            result["originalProspectiveValidatorFailure"],
            analyzer.ORIGINAL_VALIDATOR_FAILURE,
        )
        self.assertEqual(
            result["inputs"]["traceSHA256"], analyzer.EXPECTED_TRACE_SHA256
        )
        self.assertEqual(
            result["inputs"]["timelineSHA256"],
            analyzer.EXPECTED_TIMELINE_SHA256,
        )

    def test_exact_trailing_topology_is_opened_without_using_it_for_selection(self) -> None:
        trailing = self.result["openedTrailingTopology"]
        self.assertEqual(trailing["markerIntervalIndex"], 33)
        self.assertEqual(trailing["helperEntryCount"], 1)
        self.assertEqual(trailing["storeEventCount"], 4)
        self.assertEqual(trailing["eventIndices"], [826, 827, 828, 829, 830])
        self.assertFalse(trailing["usedForSample2Selection"])
        self.assertEqual(self.result["helper"]["qualifiedEntryCount"], 447)
        self.assertEqual(self.result["helper"]["callbackEventCount"], 831)

    def test_sample_two_target_is_exactly_ordinal_fourteen(self) -> None:
        selection = self.result["structuralSelection"]
        self.assertEqual(selection["sampleIndex"], 2)
        self.assertEqual(selection["sample2TargetQualifiedOrdinal"], 14)
        self.assertEqual(selection["sample2MatchingPriorHelperCount"], 1)
        self.assertEqual(selection["sample2MatchingPriorHelperOrdinals"], [14])
        self.assertEqual(selection["sample2HelperEventIndex"], 40)
        self.assertEqual(selection["sample2ProducerStoreEventIndex"], 41)
        self.assertFalse(selection["cropOrOutputValuesUsedForSelection"])
        summary = self.result["mappingSummary"]
        self.assertEqual(summary["matchingPriorHelperCountOne"], 32)
        self.assertEqual(summary["sample2Through32TargetQualifiedOrdinal"], 14)

    def test_checked_result_is_accepted_as_selected_capture_input(self) -> None:
        document, _digest, ordinal = selected_validator.load_inventory(RESULT_PATH)
        self.assertEqual(document, self.result)
        self.assertEqual(ordinal, 14)

    def test_structural_mapping_code_does_not_read_render_values(self) -> None:
        source = inspect.getsource(analyzer.validate_opened_callback_events)
        source += inspect.getsource(
            selected_validator.inventory_validator.structural_mappings
        )
        self.assertNotIn("producerHex", source)
        self.assertNotIn("floatingInput", source)
        self.assertNotIn("outputLayerShapesAt", source)
        self.assertNotIn("struct.unpack", source)

    @unittest.skipUnless(ARTIFACT_ROOT.is_dir(), "frozen GitHub artifact is absent")
    def test_frozen_raw_artifact_replays_to_checked_result(self) -> None:
        actual = analyzer.analyze(
            ARTIFACT_ROOT / "prepare-layer-mask-instruction-trace.json",
            ARTIFACT_ROOT / "transition-timeline.json",
        )
        self.assertEqual(actual, self.result)


if __name__ == "__main__":
    unittest.main()
