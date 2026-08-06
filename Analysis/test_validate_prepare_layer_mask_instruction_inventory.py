#!/usr/bin/env python3
"""Tests for output-blind helper inventory selection and fresh trace gating."""

from __future__ import annotations

import inspect
import unittest

import validate_prepare_layer_mask_inventory_selected_trace as selected_validator
import validate_prepare_layer_mask_instruction_inventory as inventory_validator
import validate_prepare_layer_mask_instruction_trace as trace_validator


class PrepareLayerMaskInstructionInventoryValidatorTests(unittest.TestCase):
    def test_inventory_configuration_only_replaces_unreachable_ordinal(self) -> None:
        expected = dict(trace_validator.EXPECTED_CONFIGURATION)
        observed = inventory_validator.expected_configuration()
        self.assertEqual(observed["targetQualifiedOrdinal"], 4_097)
        self.assertIn("ordinal 4097", observed["entrySelectionRule"])
        expected["targetQualifiedOrdinal"] = 4_097
        expected["entrySelectionRule"] = inventory_validator.selection_rule(4_097)
        self.assertEqual(observed, expected)

    def test_last_prior_structural_identity_is_deterministic(self) -> None:
        opened = [
            {
                "sampleIndex": 2,
                "structuralProducerStoreIndex": 14,
                "producerRoleBase": 100,
                "producerPrepareRecursionDepth": 7,
            }
        ]
        helpers = [
            {
                "eventIndex": 1,
                "markerIntervalIndex": 2,
                "callerRoleBase": 100,
                "prepareRecursionDepth": 7,
                "qualifiedOrdinalWithinMarkerInterval": 8,
                "helperRecordIndex": 19,
            },
            {
                "eventIndex": 3,
                "markerIntervalIndex": 2,
                "callerRoleBase": 100,
                "prepareRecursionDepth": 7,
                "qualifiedOrdinalWithinMarkerInterval": 11,
                "helperRecordIndex": 22,
            },
            {
                "eventIndex": 2,
                "markerIntervalIndex": 2,
                "callerRoleBase": 101,
                "prepareRecursionDepth": 7,
                "qualifiedOrdinalWithinMarkerInterval": 9,
                "helperRecordIndex": 20,
            },
        ]
        stores = {
            14: {
                "eventIndex": 4,
                "markerIntervalIndex": 2,
                "callerRoleBase": 100,
                "prepareRecursionDepth": 7,
            }
        }
        result = inventory_validator.structural_mappings(opened, helpers, stores)[0]
        self.assertEqual(result["matchingPriorHelperOrdinals"], [8, 11])
        self.assertEqual(result["selectedQualifiedOrdinal"], 11)
        self.assertEqual(
            result["selectedByLastPriorStructuralIdentityHelperRecordIndex"], 22
        )
        self.assertFalse(result["cropOrOutputValuesUsedForSelection"])

    def test_future_and_wrong_depth_helpers_cannot_match(self) -> None:
        opened = [
            {
                "sampleIndex": 2,
                "structuralProducerStoreIndex": 14,
                "producerRoleBase": 100,
                "producerPrepareRecursionDepth": 7,
            }
        ]
        helpers = [
            {
                "eventIndex": 5,
                "markerIntervalIndex": 2,
                "callerRoleBase": 100,
                "prepareRecursionDepth": 7,
                "qualifiedOrdinalWithinMarkerInterval": 11,
                "helperRecordIndex": 22,
            },
            {
                "eventIndex": 3,
                "markerIntervalIndex": 2,
                "callerRoleBase": 100,
                "prepareRecursionDepth": 6,
                "qualifiedOrdinalWithinMarkerInterval": 10,
                "helperRecordIndex": 21,
            },
        ]
        stores = {
            14: {
                "eventIndex": 4,
                "markerIntervalIndex": 2,
                "callerRoleBase": 100,
                "prepareRecursionDepth": 7,
            }
        }
        with self.assertRaisesRegex(ValueError, "producer helper is absent"):
            inventory_validator.structural_mappings(opened, helpers, stores)

    def test_selected_configuration_changes_only_ordinal_rule(self) -> None:
        expected = dict(trace_validator.EXPECTED_CONFIGURATION)
        observed = selected_validator.selected_configuration(11)
        expected["targetQualifiedOrdinal"] = 11
        expected["entrySelectionRule"] = inventory_validator.selection_rule(11)
        self.assertEqual(observed, expected)

    def test_selection_implementations_do_not_decode_render_values(self) -> None:
        source = inspect.getsource(inventory_validator.structural_mappings)
        self.assertIn("callerRoleBase", source)
        self.assertIn("prepareRecursionDepth", source)
        self.assertIn("eventIndex", source)
        self.assertNotIn("producerHex", source)
        self.assertNotIn("floatingInput", source)
        self.assertNotIn("struct.unpack", source)
        selected_source = inspect.getsource(selected_validator.load_inventory)
        self.assertNotIn("producerHex", selected_source)
        self.assertNotIn("outputLayerShapes", selected_source)


if __name__ == "__main__":
    unittest.main()
