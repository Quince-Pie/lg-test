#!/usr/bin/env python3
"""Checks for the prospectively reusable blind FilterOp validator."""

import ast
import unittest
from pathlib import Path


SOURCE_PATH = (
    Path(__file__).resolve().parent
    / "validate_prepare_layer_filter_map_bounds_blind_replay.py"
)


class PrepareLayerFilterMapBoundsBlindReplayValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_source_bound_rule_is_terminal_and_crop_blind(self) -> None:
        self.assertIn("transform[12]", self.source)
        self.assertIn("transform[13]", self.source)
        self.assertIn('int(record.get("sampleIndex")) == 32', self.source)
        self.assertIn('"cropOrProducerValuesUsed": False', self.source)

    def test_replay_uses_exact_decoder_not_tolerance(self) -> None:
        self.assertIn("exact.replay(", self.source)
        self.assertNotIn("isclose", self.source)
        self.assertNotIn("tolerance", self.source.lower())
        self.assertIn('raise ValueError("blind FilterOp replay differs")', self.source)

    def test_selection_reuses_structural_store_relationships(self) -> None:
        self.assertIn("holdout.validate_store_extension(", self.source)
        self.assertIn("holdout.TRUE_PRODUCER_STORE_INDEX_DELTA", self.source)
        self.assertIn("holdout.TRUE_PRODUCER_ROLE_DELTA", self.source)
        self.assertIn("holdout.TRUE_PRODUCER_DEPTH_DELTA", self.source)

    def test_validator_does_not_claim_product_parity(self) -> None:
        for key in (
            "materialAppearanceDirectionTransferPassed",
            "physicalRetina2xAndColorTransferPassed",
            "independentWalleZeroByteFrameParityPassed",
            "productionShaderAuthorized",
            "liquidGlassParityEstablished",
        ):
            self.assertIn(f'"{key}": False', self.source)


if __name__ == "__main__":
    unittest.main()
