#!/usr/bin/env python3
"""Integrity checks for the opened caller trace and FilterOp ownership."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ANALYSIS_ROOT.parent
RESULT_PATH = (
    ANALYSIS_ROOT
    / "dynamic_allocation_prepare_layer_crop_producer_callee_callback_retry_result.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PrepareLayerCropProducerCalleeCallbackRetryResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    def test_run_and_raw_evidence_are_frozen(self) -> None:
        run = self.result["run"]
        evidence = self.result["rawEvidence"]
        self.assertEqual(run["runID"], 31068498526)
        self.assertEqual(run["headSHA"], "428a350df0d5d029fe9623e61f52079356861261")
        self.assertEqual(run["workflowConclusion"], "failure")
        self.assertEqual(
            evidence["traceSHA256"],
            "e74ba953b239682118c91f5c9ed1b6d45ceef013b7690d3facfb202b386d9b71",
        )
        self.assertEqual(
            evidence["rootFailure"], "crop producer call site was not reached"
        )

    def test_same_frame_skips_falsified_static_call(self) -> None:
        selection = self.result["transportAndSelection"]
        rejected = self.result["falsifiedStaticCalleeHypothesis"]
        self.assertTrue(selection["topLevelCallbackTransportRepaired"])
        self.assertEqual(selection["qualifiedHelperOrdinal"], 14)
        self.assertTrue(selection["callerFramePointerConstantAcrossAllStates"])
        self.assertEqual(rejected["x23AfterLoad"], 0)
        self.assertFalse(rejected["hypothesizedCallExecuted"])
        self.assertFalse(rejected["wrongRecursiveFrameEntered"])

    def test_dynamic_dispatch_chain_is_structural_and_exact(self) -> None:
        chain = self.result["openedDynamicDispatchChain"]
        dispatches = chain["dispatches"]
        self.assertEqual(chain["callerCallOffset"], 0x2864)
        self.assertEqual(chain["callRawLittleEndianHex"], "10093fd7")
        self.assertEqual(
            [item["ordinalAtCallSite"] for item in dispatches], [1, 2, 3, 4, 5]
        )
        self.assertEqual(
            [
                item["function"]
                .split("::map_bounds", maxsplit=1)[0]
                .rsplit("::", maxsplit=1)[-1]
                for item in dispatches
            ],
            ["FlattenZOp", "SDFOp", "FlattenZOp", "FilterOp", "FlattenZOp"],
        )
        self.assertFalse(chain["outputValuesUsedToChooseDispatch"])

    def test_filter_map_bounds_owns_exact_floating_producer(self) -> None:
        owner = self.result["filterMapBoundsOwnership"]
        self.assertEqual(owner["symbolRelativeToPrepareLayer"], -61056)
        self.assertEqual(owner["symbolByteCount"], 788)
        self.assertEqual(
            owner["codeSHA256FromPriorFrozenCompleteSymbol"],
            "e8766dcefdadc0074f7bb4e2bf62955072891858009dca6c72a7eef1c96789d0",
        )
        self.assertNotEqual(
            owner["firstRectangleBeforeHex"], owner["firstRectangleAfterHex"]
        )
        self.assertEqual(owner["changedFirstRectangleQwordOffsets"], [0, 8, 16, 24])
        self.assertEqual(owner["packedIntegerWorkingCropI32"], [478, 0, 546, 546])
        self.assertTrue(owner["floatingFirstRectangleOwnerEstablished"])
        self.assertFalse(owner["exactInternalArithmeticDecoded"])

    def test_only_opened_claims_are_true(self) -> None:
        sealed = self.result["sealedConclusion"]
        opened = {
            "callbackTransportRepaired",
            "staticPlusF5CCalleeHypothesisFalsified",
            "filterMapBoundsFloatingProducerOwnershipEstablished",
        }
        for key in opened:
            self.assertTrue(sealed[key], key)
        for key, value in sealed.items():
            if key not in opened:
                self.assertFalse(value, key)
        shader = REPOSITORY_ROOT.parent / "shaders" / "frag.glsl"
        if shader.is_file():
            self.assertEqual(
                sha256(shader),
                "6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d",
            )


if __name__ == "__main__":
    unittest.main()
