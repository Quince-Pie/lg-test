import json
import math
import unittest
from pathlib import Path


RESULT_PATH = Path(__file__).with_name(
    "dynamic_allocation_prepare_layer_frame_writer_result.json"
)


class PrepareLayerFrameWriterResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_successful_prospective_gate_is_frozen(self) -> None:
        self.assertEqual(self.result["run"]["runID"], 31022198697)
        self.assertEqual(
            self.result["inputArtifacts"]["rawFrameWriterTraceSHA256"],
            "2429aea6ea9e7afd6b2516de7ab623b9e785b7c71b53070c25483f6665fe4019",
        )
        gate = self.result["prospectiveGate"]
        self.assertEqual(gate["conclusion"], "success")
        self.assertEqual(gate["selectedWriterEventCount"], 7)
        self.assertEqual(gate["selectedDistinctAggregateCount"], 4)
        self.assertEqual(gate["selectedChangingTransitionCount"], 3)
        self.assertTrue(gate["sameInvocationFrameCorrelationProved"])
        self.assertTrue(gate["selectedAggregateChainClosedAtMarker"])

    def test_identity_and_fourth_exact_rule_sample_are_frozen(self) -> None:
        identity = self.result["selectedIdentity"]
        self.assertEqual(identity["aggregateAddress"], identity["roleBase"] + 656)
        self.assertEqual(identity["prepareLayerRecursionDepth"], 4)
        sample = self.result["fourthExactPublicRuleSample"]
        carrier = sample["publicCarrierP"]
        origin = math.floor(carrier) - 1
        expected = [
            float(origin),
            1024.0 - carrier - 640.0 - 8.0,
            carrier + 640.0 - origin,
            carrier + 640.0 + 8.0 - origin,
        ]
        self.assertEqual(sample["integerOriginL"], origin)
        self.assertEqual(sample["expectedAggregateF64"], expected)
        self.assertEqual(sample["observedAggregateF64"], expected)
        self.assertTrue(sample["bitExact"])

    def test_sampled_helpers_are_not_misclassified_as_causal_writers(self) -> None:
        audit = self.result["causalAddressAudit"]
        aggregate = audit["aggregateAddress"]
        self.assertEqual(audit["firstUnionDestination"], aggregate)
        self.assertEqual(audit["secondUnionDestination"], aggregate)
        self.assertNotEqual(audit["firstApplyDestination"], aggregate)
        self.assertNotEqual(audit["secondApplyDestination"], aggregate)
        self.assertNotEqual(audit["sampledUnapplyDestination"], aggregate)
        self.assertTrue(audit["unionCallbacksCausallyTargetAggregate"])
        self.assertFalse(audit["sampledTransformCallbacksCausallyTargetAggregate"])
        self.assertTrue(audit["hiddenMutationProved"])

    def test_result_keeps_semantics_and_product_claims_closed(self) -> None:
        self.assertFalse(self.result["prospectiveGate"]["writerInstructionSemanticsOpened"])
        self.assertFalse(self.result["prospectiveGate"]["productionShaderAuthorized"])
        self.assertFalse(self.result["nextEvidenceBoundary"]["productionShaderAuthorized"])
        claims = "\n".join(self.result["notClaimed"])
        self.assertIn("complete crop-allocation producer", claims)
        self.assertIn("parity", claims)


if __name__ == "__main__":
    unittest.main()
