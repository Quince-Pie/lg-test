#!/usr/bin/env python3
"""Integrity checks for the opened ordinal-fourteen ownership failure."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
RESULT_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_mask_inventory_selected_trace_result.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerMaskInventorySelectedTraceResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_run_identity_and_original_failure_are_frozen(self) -> None:
        run = self.result["run"]
        self.assertEqual(run["runID"], 31065907932)
        self.assertEqual(run["headSHA"], "5fc325cef3db62f5ff769e403e30f5053a53cd9c")
        self.assertEqual(run["workflowConclusion"], "failure")
        self.assertEqual(
            run["originalStrictFailure"],
            "helper output does not match structural producer",
        )

    def test_selector_passes_by_role_and_depth_without_output(self) -> None:
        selection = self.result["prospectiveSelectionRevalidated"]
        self.assertEqual(selection["markerInterval"], 2)
        self.assertEqual(selection["qualifiedHelperOrdinal"], 14)
        self.assertEqual(selection["callerRoleBase"], 6171882864)
        self.assertEqual(selection["callerRoleDelta"], 0)
        self.assertEqual(selection["prepareRecursionDepth"], 7)
        self.assertEqual(selection["independentProducerPrepareRecursionDepth"], 7)
        self.assertFalse(selection["cropValueUsedForSelection"])
        self.assertFalse(selection["outputValueUsedForSelection"])
        self.assertTrue(selection["structuralMappingPassed"])

    def test_complete_helper_execution_falsifies_first_rectangle_owner(self) -> None:
        helper = self.result["helperExecution"]
        zero = "00" * 32
        self.assertEqual(helper["instructionStateCount"], 52)
        self.assertEqual(helper["opaqueCalleeBoundaryCount"], 0)
        self.assertEqual(helper["failureCount"], 0)
        self.assertEqual(helper["firstRectangleAtEntryHex"], zero)
        self.assertEqual(helper["firstRectangleAtReturnHex"], zero)
        self.assertNotEqual(
            helper["firstRectangleAtReturnHex"], helper["independentProducerHex"]
        )
        self.assertFalse(helper["returnMatchesIndependentProducerBitForBit"])
        self.assertFalse(helper["firstRectangleOwner"])
        self.assertEqual(
            [
                record["changedOutputQwordOffsets"]
                for record in helper["changedOutputInstructions"]
            ],
            [[112, 120], [136]],
        )

    def test_next_gate_is_the_exact_static_second_call(self) -> None:
        gate = self.result["nextStructuralGate"]
        self.assertEqual(
            gate["prepareLayerFullCodeSHA256"],
            "fe58001369708e0276599f26865be03fdf1dd2348524f92a72c1427be8d1817c",
        )
        self.assertEqual(gate["globalStateByte49AtSelectedEntry"], 0)
        self.assertEqual(gate["calleeCallOffset"], 0xF5C)
        self.assertEqual(gate["calleeReturnOffset"], 0xF60)
        self.assertEqual(gate["calleeEntryRelativeToPrepareLayer"], -1_206_100)
        self.assertEqual(gate["calleeCallRawLittleEndianHex"], "5462fb97")
        self.assertTrue(gate["prospectiveOutputBlindTraceRequired"])

    def test_no_downstream_parity_claim_is_opened(self) -> None:
        sealed = self.result["sealedConclusion"]
        self.assertTrue(sealed["prepareLayerMaskFirstRectangleOwnershipFalsified"])
        for key, value in sealed.items():
            if key not in (
                "ordinalFourteenStructuralMappingPassed",
                "prepareLayerMaskFirstRectangleOwnershipFalsified",
            ):
                self.assertFalse(value, key)
        shader = REPOSITORY_ROOT.parent / "shaders" / "frag.glsl"
        if shader.is_file():
            self.assertEqual(
                sha256(shader),
                "6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d",
            )


if __name__ == "__main__":
    unittest.main()
