#!/usr/bin/env python3
"""Tests for selected Glass DOD semantic-state decoding."""

import copy
import unittest
from unittest import mock

import analyze_prepare_layer_dod_semantics as analyzer
from test_validate_prepare_layer_instruction_trace import semantic_fixture


def fixture():
    trace, _scopes = semantic_fixture()
    invocation = trace["semanticDODInvocation"]
    validation = {
        "semanticDODTrace": {
            "targetAggregateAddress": invocation["targetAggregateAddress"],
            "entryRecordIndex": invocation["entryRecordIndex"],
            "entryStepIndex": invocation["entryStepIndex"],
            "returnStepIndex": invocation["returnStepIndex"],
            "instructionStateCount": invocation["instructionStateCount"],
            "instructionStatesSHA256": invocation["instructionStatesSHA256"],
        }
    }
    return trace, validation


class PrepareLayerDODSemanticAnalysisTests(unittest.TestCase):
    def test_validated_instruction_effects_are_decoded(self):
        trace, validation = fixture()
        with mock.patch.object(
            analyzer.validator,
            "validate_documents",
            return_value=validation,
        ):
            result = analyzer.analyze_documents(trace, {}, validation)
        self.assertEqual(result["instructionEffectCount"], 2)
        self.assertEqual(result["opaqueHelperReturnCount"], 0)
        self.assertEqual(result["aggregateWriterCount"], 0)
        self.assertEqual(
            result["inputInstructionStateSHA256"],
            trace["semanticDODInvocation"]["instructionStatesSHA256"],
        )
        self.assertTrue(result["conclusion"]["composedValidatorRepassed"])
        self.assertFalse(result["conclusion"]["productionShaderAuthorized"])

    def test_stored_validation_must_equal_composed_revalidation(self):
        trace, validation = fixture()
        with mock.patch.object(
            analyzer.validator,
            "validate_documents",
            return_value={"semanticDODTrace": {}},
        ):
            with self.assertRaisesRegex(ValueError, "stored validation differs"):
                analyzer.analyze_documents(trace, {}, validation)

    def test_opaque_helper_arguments_and_returns_are_retained(self):
        trace, validation = fixture()
        opaque = {
            "stepIndex": 1,
            "kind": "opaque-callee-step-out",
            "opaqueBoundary": {
                "entryFrame": {
                    "function": (
                        "CA::Render::KeyValueArray::get_float_key(unsigned int, "
                        "double) const"
                    )
                }
            },
        }
        trace["instructionSteps"].insert(1, opaque)
        trace["instructionSteps"][2]["stepIndex"] = 2
        trace["semanticDODInstructionStates"][1]["stepIndex"] = 2
        trace["semanticDODInvocation"]["returnStepIndex"] = 2
        states = trace["semanticDODInstructionStates"]
        digest = analyzer.sha256_json(states)
        trace["semanticDODInvocation"]["instructionStatesSHA256"] = digest
        validation = copy.deepcopy(validation)
        validation["semanticDODTrace"]["returnStepIndex"] = 2
        validation["semanticDODTrace"]["instructionStatesSHA256"] = digest
        with mock.patch.object(
            analyzer.validator,
            "validate_documents",
            return_value=validation,
        ):
            result = analyzer.analyze_documents(trace, {}, validation)
        helper = result["opaqueHelperReturns"][0]
        self.assertEqual(result["opaqueHelperReturnCount"], 1)
        self.assertEqual(helper["keyID"], 0)
        self.assertIn("get_float_key", helper["function"])
        self.assertEqual(len(helper["argumentV0F64"]), 2)
        self.assertEqual(len(helper["returnV0F64"]), 2)


if __name__ == "__main__":
    unittest.main()
