#!/usr/bin/env python3
"""Regression gates for the finite case-22 branch-universe proof."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import prove_backdrop_margin_case22_provider_finite_branch_universe as proof


ANALYSIS = Path(__file__).resolve().parent
SOURCE = ANALYSIS / "prove_backdrop_margin_case22_provider_finite_branch_universe.py"
RESULT = json.loads(
    (
        ANALYSIS / "backdrop_margin_case22_provider_finite_branch_universe_result.json"
    ).read_text(encoding="utf-8")
)


class FiniteBranchUniverseProofTests(unittest.TestCase):
    def test_vector_alias_writes_are_recognized(self) -> None:
        self.assertEqual(proof.written_vector_indices("ldr\td4, [x20, #248]"), {4})
        self.assertEqual(
            proof.written_vector_indices("movi\tv4.2d, #0000000000000000"),
            {4},
        )
        self.assertEqual(
            proof.written_vector_indices("ldp\td5, d4, [x20, #168]"),
            {4, 5},
        )
        self.assertEqual(proof.written_vector_indices("fcmp\td4, #0.0"), set())

    def test_missing_outcome_partition_is_exact(self) -> None:
        universe = RESULT["finiteBranchUniverse"]
        self.assertEqual(universe["conditionalBranchCount"], 41)
        self.assertEqual(universe["totalOutcomeCount"], 82)
        self.assertEqual(universe["prospectivelyTransferredOutcomeCount"], 75)
        self.assertEqual(universe["provedInfeasibleOutcomeCount"], 7)
        self.assertTrue(universe["partitionIsExact"])
        self.assertEqual(
            set(universe["provedInfeasibleOutcomes"]),
            {
                proof.outcome_label(value)
                for value in proof.EXPECTED_INFEASIBLE_OUTCOMES
            },
        )

    def test_result_is_bound_to_the_current_proof_source(self) -> None:
        observed = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
        self.assertEqual(RESULT["inputs"]["proofSource"]["sha256"], observed)

    def test_product_authority_remains_closed(self) -> None:
        authority = RESULT["authority"]
        self.assertTrue(authority["finiteConditionalBranchOutcomeUniverseClosed"])
        self.assertTrue(
            authority["allFeasibleFiniteBranchOutcomesProspectivelyTransferred"]
        )
        self.assertFalse(authority["completeFiniteProviderLaw"])
        self.assertFalse(authority["publicInputFieldMappingEstablished"])
        self.assertFalse(authority["liquidGlassParityEstablished"])
        self.assertFalse(authority["productionShaderAuthorized"])


if __name__ == "__main__":
    unittest.main()
