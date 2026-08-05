#!/usr/bin/env python3
"""Integrity tests for the prospective exact crop-union operand capture."""

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
REGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_crop_union_operand_preregistration.json"
)
REGISTRATION = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))
TOPOLOGY_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_crop_transfer_topology_preregistration.json"
)
MATRIX_ANALYSIS_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_crop_transfer_matrix_analysis.json"
)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerCropUnionOperandPreregistrationTests(unittest.TestCase):
    def test_registration_is_prospective_and_chained_to_opened_matrix(self):
        registration = REGISTRATION
        antecedent = registration["antecedentEvidence"]
        opened = registration["openedMatrixAnalysis"]
        self.assertEqual(
            registration[
                "prepareLayerCropUnionOperandPreregistrationSchemaVersion"
            ],
            1,
        )
        self.assertIn("prospective", registration["classification"])
        self.assertIsNone(registration["runtimeOutcomeFrozenBeforeDispatch"])
        self.assertEqual(sha256(TOPOLOGY_PATH), antecedent["topologyPreregistrationSHA256"])
        self.assertEqual(antecedent["successfulRunID"], 31055266553)
        self.assertEqual(antecedent["successfulJobCount"], 8)
        self.assertEqual(len(antecedent["artifactInventory"]), 8)
        self.assertEqual(
            len({record["artifactID"] for record in antecedent["artifactInventory"]}),
            8,
        )
        self.assertEqual(sha256(MATRIX_ANALYSIS_PATH), opened["analysisSHA256"])
        self.assertEqual(opened["recordCount"], 256)
        self.assertEqual(opened["componentCount"], 1024)
        self.assertEqual(opened["exactComponentCount"], 1015)
        self.assertEqual(opened["mismatchedComponentCount"], 9)
        self.assertEqual(opened["mismatchedRecordCount"], 6)

    def test_capture_targets_only_the_opened_exact_union_sites(self):
        sites = REGISTRATION["openedInstructionSites"]
        design = REGISTRATION["captureDesign"]
        self.assertEqual(sites["callOffset"], 0x85DC)
        self.assertEqual(sites["callRawLittleEndianHex"], "e1dbff97")
        self.assertEqual(sites["returnOffset"], 0x85E0)
        self.assertEqual(sites["returnRawLittleEndianHex"], "686241f9")
        self.assertEqual(sites["destinationLoadOffset"], 0x85D4)
        self.assertEqual(sites["inputRoleOffset"], 0x620)
        self.assertEqual(sites["destinationRoleOffset"], 0x290)
        self.assertIn("caller chain", design["callSelection"])
        self.assertIn("destination", design["markerCorrelation"])
        self.assertFalse(design["cropValuesUsedForSelection"])
        self.assertFalse(design["aggregateValuesUsedForSelection"])
        self.assertFalse(design["hardwareWatchpoints"])
        self.assertFalse(design["instructionStepping"])
        self.assertFalse(design["appleCaptureProgramChanged"])
        self.assertFalse(design["productionShaderChanged"])

    def test_frozen_implementation_hashes_match(self):
        frozen = REGISTRATION["frozenImplementation"]
        pairs = (
            (frozen["baseCaptureHarness"], frozen["baseCaptureHarnessSHA256"]),
            (frozen["baseValidator"], frozen["baseValidatorSHA256"]),
            (frozen["captureHarness"], frozen["captureHarnessSHA256"]),
            (frozen["captureHarnessTest"], frozen["captureHarnessTestSHA256"]),
            (frozen["validator"], frozen["validatorSHA256"]),
            (frozen["validatorTest"], frozen["validatorTestSHA256"]),
            (frozen["workflow"], frozen["workflowSHA256"]),
            (frozen["matrixAnalyzer"], frozen["matrixAnalyzerSHA256"]),
            (frozen["matrixAnalyzerTest"], frozen["matrixAnalyzerTestSHA256"]),
            (frozen["matrixAnalysis"], frozen["matrixAnalysisSHA256"]),
        )
        for relative, expected in pairs:
            self.assertEqual(sha256(REPOSITORY_ROOT / relative), expected)

    def test_acceptance_remains_discovery_only_and_fail_closed(self):
        acceptance = REGISTRATION["acceptance"]
        self.assertEqual(acceptance["geometryCount"], 8)
        self.assertEqual(acceptance["normalMarkerCountPerGeometry"], 32)
        self.assertEqual(acceptance["linkedOperandCountPerGeometry"], 32)
        self.assertTrue(acceptance["allCallReturnPairsMustBeComplete"])
        self.assertTrue(acceptance["oneDestinationMatchPerMarkerRequired"])
        self.assertTrue(acceptance["zeroTrailingQualifiedUnionRecordsRequired"])
        self.assertTrue(acceptance["allSelectedUnionsMustReplayBitForBit"])
        self.assertTrue(acceptance["allFinalAggregatesMustReplayBitForBit"])
        self.assertFalse(acceptance["generalCropPolicyMayBeClaimedByThisRunAlone"])
        self.assertFalse(acceptance["unseenTransferMayBeClaimedByThisRunAlone"])
        self.assertFalse(acceptance["productionShaderMayChange"])
        self.assertFalse(acceptance["liquidGlassParityMayBeClaimed"])


if __name__ == "__main__":
    unittest.main()
