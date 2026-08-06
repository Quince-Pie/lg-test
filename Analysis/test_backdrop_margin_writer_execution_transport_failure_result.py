"""Integrity tests for the first writer-execution transport failure."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


RESULT = Path(__file__).with_name(
    "backdrop_margin_writer_execution_transport_failure_result.json"
)


class BackdropMarginWriterExecutionTransportFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = json.loads(RESULT.read_text(encoding="utf-8"))

    def test_run_and_artifacts_are_immutable(self) -> None:
        self.assertEqual(
            self.value[
                "backdropMarginWriterExecutionTransportFailureResultSchemaVersion"
            ],
            1,
        )
        self.assertEqual(self.value["run"]["runID"], 31109847952)
        self.assertEqual(
            self.value["run"]["headSHA"],
            "7a0abe0857da5ab1bf63cad256ab2038ed326300",
        )
        artifacts = self.value["artifacts"]
        self.assertEqual(len(artifacts), 4)
        self.assertEqual(
            {artifact["artifactID"] for artifact in artifacts},
            {8971372675, 8971228953, 8971235301, 8971354085},
        )
        for artifact in artifacts:
            self.assertRegex(artifact["artifactDigest"], r"^sha256:[0-9a-f]{64}$")
            self.assertRegex(artifact["traceSHA256"], r"^[0-9a-f]{64}$")
            self.assertRegex(artifact["timelineSHA256"], r"^[0-9a-f]{64}$")
            self.assertFalse(artifact["validatorReachedCandidateComputation"])
            self.assertFalse(artifact["validationOutputExists"])

    def test_diagnosis_uses_structure_not_target_values(self) -> None:
        diagnosis = self.value["diagnosis"]
        self.assertEqual(diagnosis["materializeCopyStoreEventCount"], 527)
        self.assertEqual(diagnosis["materializeModelEntryStorePointerMatchCount"], 527)
        self.assertEqual(diagnosis["materializeOpaqueX2EqualsRenderX21Count"], 0)
        self.assertFalse(diagnosis["candidateMarginValuesReadForDiagnosis"])
        self.assertFalse(diagnosis["cropOrImageValuesReadForDiagnosis"])
        self.assertFalse(diagnosis["candidateFormulaChanged"])

    def test_failure_grants_no_product_authority(self) -> None:
        sealed = self.value["sealedConclusion"]
        self.assertTrue(sealed["transportOrContractFailureOnly"])
        self.assertFalse(sealed["candidateTested"])
        self.assertFalse(sealed["prospectiveTransferPassed"])
        self.assertFalse(sealed["productionShaderAuthorized"])
        self.assertFalse(sealed["liquidGlassParityEstablished"])


if __name__ == "__main__":
    unittest.main()
