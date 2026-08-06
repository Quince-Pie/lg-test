#!/usr/bin/env python3
"""Integrity tests for the prospective FilterOp profile-transfer result."""

from __future__ import annotations

import hashlib
import json
import unittest
from itertools import product
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
RESULT_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_filter_map_bounds_profile_transfer_retry_result.json"
)
PREREGISTRATION_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_filter_map_bounds_profile_transfer_retry_preregistration.json"
)
EXPECTED_PROFILES = set(
    product(
        ("clear", "regular"),
        ("light", "dark"),
        ("materialize", "dematerialize"),
    )
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerFilterMapBoundsProfileTransferRetryResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_result_is_a_prospective_unchanged_pass(self) -> None:
        self.assertEqual(
            self.result[
                "prepareLayerFilterMapBoundsProfileTransferRetryResultSchemaVersion"
            ],
            1,
        )
        self.assertIn("prospective", self.result["classification"])
        preregistration = self.result["preregistration"]
        self.assertTrue(preregistration["committedBeforeDispatch"])
        self.assertTrue(preregistration["runtimeOutcomeUnopenedAtFreeze"])
        self.assertFalse(preregistration["candidateChangedAfterOpening"])
        self.assertEqual(sha256(PREREGISTRATION_PATH), preregistration["sha256"])

    def test_authoritative_run_and_artifacts_are_authenticated(self) -> None:
        run = self.result["run"]
        self.assertEqual(run["id"], 31080971042)
        self.assertEqual(run["headSHA"], "05bff66e698615597f284408a0c77584061bb717")
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["conclusion"], "success")
        self.assertEqual(run["successfulMacOSProfileJobCount"], 8)
        self.assertEqual(run["aggregateJobConclusion"], "success")

        inventory = self.result["artifactInventory"]
        self.assertEqual(inventory["artifactCount"], 17)
        self.assertEqual(inventory["totalArchiveBytes"], 761351808)
        self.assertTrue(inventory["allArtifactsDownloadedAndAudited"])
        self.assertEqual(
            inventory["matrix"]["jsonSHA256"],
            "cd4a9883548d57095b54320205ce9ee0536f5382ce541129fb8a3ae232a6fb19",
        )
        self.assertEqual(len(inventory["profiles"]), 8)
        self.assertEqual(
            {
                (item["material"], item["appearance"], item["direction"])
                for item in inventory["profiles"]
            },
            EXPECTED_PROFILES,
        )
        self.assertEqual(
            len({item["traceSHA256"] for item in inventory["profiles"]}), 8
        )
        self.assertEqual(
            len({item["timelineSHA256"] for item in inventory["profiles"]}), 8
        )
        self.assertEqual(
            len({item["validationSHA256"] for item in inventory["profiles"]}),
            8,
        )

        audit = self.result["independentArtifactAudit"]
        self.assertTrue(audit["allAggregateTraceHashesMatchDownloadedBytes"])
        self.assertTrue(audit["allAggregateTimelineHashesMatchDownloadedBytes"])
        self.assertTrue(audit["allAggregateValidationHashesMatchDownloadedResultBytes"])
        self.assertTrue(audit["allFullEvidenceValidationDuplicatesMatchResultBytes"])
        self.assertEqual(audit["hashMismatchCount"], 0)

    def test_complete_fixed_geometry_profile_product_is_bit_exact(self) -> None:
        replay = self.result["prospectiveReplay"]
        self.assertEqual(replay["profileCount"], 8)
        self.assertEqual(replay["rectangleCount"], 256)
        self.assertEqual(replay["exactRectangleCount"], 256)
        self.assertEqual(replay["componentCount"], 1024)
        self.assertEqual(replay["exactComponentCount"], 1024)
        self.assertEqual(replay["sdfStateRecordCount"], 256)
        self.assertEqual(replay["structurallyAuthenticatedSDFStateRecordCount"], 256)
        self.assertEqual(replay["endpointYOffsetAppliedRecordCount"], 4)
        self.assertEqual(replay["maximumULPDistance"], 0)
        self.assertEqual(replay["maximumAbsoluteError"], 0.0)
        self.assertFalse(replay["toleranceUsed"])
        self.assertFalse(replay["cropOrProducerValuesUsedForSelection"])
        self.assertTrue(replay["allDownstreamIntegerCropsExact"])
        self.assertTrue(replay["allEightProfilesAndAggregatePassed"])

    def test_fresh_endpoint_values_are_witnesses_not_fitted_constants(self) -> None:
        witnesses = self.result["freshEndpointBranchWitnesses"]
        self.assertEqual(len(witnesses), 4)
        self.assertEqual(
            {(item["appearance"], item["direction"]) for item in witnesses},
            set(product(("light", "dark"), ("materialize", "dematerialize"))),
        )
        self.assertEqual(
            {
                (
                    item["direction"],
                    item["sampleIndex"],
                    item["producerPrepareRecursionDepth"],
                )
                for item in witnesses
            },
            {("materialize", 1, 6), ("dematerialize", 31, 7)},
        )
        self.assertEqual(len({item["endpointYOffsetHex"] for item in witnesses}), 4)

    def test_crop_authority_opens_while_product_parity_stays_closed(self) -> None:
        conclusion = self.result["conclusion"]
        self.assertTrue(conclusion["fixedGeometryFilterOpCropProfileTransferPassed"])
        self.assertTrue(
            conclusion[
                "clearRegularLightDarkMaterializeDematerializeCropTransferPassed"
            ]
        )
        self.assertTrue(conclusion["unchangedProspectiveRepeatPassed"])
        for sealed in (
            "regularUnseenGeometryTransferPassed",
            "currentShaderCapturedInputOpticalTransferPassed",
            "independentPrivateUniformGenerationPassed",
            "independentBackdropPyramidGenerationPassed",
            "independentCompleteGeometryGenerationPassed",
            "opticalMaterialAppearanceDirectionTransferPassed",
            "physicalRetina2xAndColorTransferPassed",
            "independentWalleZeroByteFrameParityPassed",
            "productionShaderAuthorized",
            "liquidGlassParityEstablished",
        ):
            self.assertFalse(conclusion[sealed])

        shader = REPOSITORY_ROOT.parent / "shaders" / "frag.glsl"
        if shader.is_file():
            self.assertEqual(
                sha256(shader), conclusion["productionShaderExpectedSHA256"]
            )


if __name__ == "__main__":
    unittest.main()
