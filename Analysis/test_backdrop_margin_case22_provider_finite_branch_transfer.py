#!/usr/bin/env python3
"""Source and deterministic-generator gates for the finite branch transfer."""

from __future__ import annotations

import hashlib
import json
import math
import struct
import unittest
from pathlib import Path

import generate_backdrop_margin_case22_provider_finite_branch_corpus as corpus


ANALYSIS = Path(__file__).resolve().parent
GENERATOR_SOURCE = (
    ANALYSIS / "generate_backdrop_margin_case22_provider_finite_branch_corpus.py"
).read_text(encoding="utf-8")
CAPTURE_SOURCE = (
    ANALYSIS
    / "capture_backdrop_margin_case22_provider_finite_branch_transfer_over_ssh.py"
).read_text(encoding="utf-8")
VALIDATOR_SOURCE = (
    ANALYSIS / "validate_backdrop_margin_case22_provider_finite_branch_transfer.py"
).read_text(encoding="utf-8")
C_SOURCE = (
    ANALYSIS / "invoke_backdrop_margin_case22_provider_local_macos_26_6_1.c"
).read_text(encoding="utf-8")
ASSEMBLY_SOURCE = (
    ANALYSIS / "invoke_backdrop_margin_case22_provider_local_macos_26_6_1_arm64.s"
).read_text(encoding="utf-8")
PREREGISTRATION = json.loads(
    (
        ANALYSIS
        / "backdrop_margin_case22_provider_finite_branch_transfer_preregistration.json"
    ).read_text(encoding="utf-8")
)


class FiniteBranchCorpusTests(unittest.TestCase):
    def test_splitmix64_stream_is_fully_specified(self) -> None:
        generator = corpus.SplitMix64(0xCACE22)
        self.assertEqual(
            [generator.next_u64() for _ in range(5)],
            [
                0x2861E05753AECDB7,
                0x4585F28A7AE3BEE7,
                0x1E9F504D9F62F8B7,
                0x0ED26A1751C8E0EB,
                0x5F2339FE8642A586,
            ],
        )

    def test_candidate_loaded_fields_are_finite(self) -> None:
        generator = corpus.SplitMix64(corpus.DEFAULT_SEED)
        for _ in range(128):
            raw = corpus.candidate_object(generator)
            self.assertEqual(len(raw), 384)
            values = [
                struct.unpack_from("<d", raw, offset)[0]
                for offset in corpus.F64_OFFSETS
            ]
            values.extend(
                struct.unpack_from("<f", raw, offset)[0]
                for offset in corpus.F32_OFFSETS
            )
            self.assertTrue(all(math.isfinite(value) for value in values))

    def test_generator_is_output_blind_and_cardinalities_are_frozen(self) -> None:
        self.assertNotIn("appleReturn", GENERATOR_SOURCE)
        self.assertNotIn("ssh", GENERATOR_SOURCE)
        self.assertEqual(corpus.DEFAULT_CANDIDATE_COUNT, 200_000)
        self.assertEqual(corpus.EXPECTED_STATIC_CONDITIONAL_BRANCH_COUNT, 41)
        self.assertEqual(corpus.EXPECTED_OBSERVED_CONDITIONAL_BRANCH_COUNT, 39)
        self.assertEqual(corpus.EXPECTED_BOTH_OUTCOME_CONDITIONAL_BRANCH_COUNT, 36)
        self.assertEqual(corpus.EXPECTED_OBSERVED_BRANCH_OUTCOME_COUNT, 75)
        self.assertEqual(corpus.EXPECTED_DISTINCT_PATH_COUNT, 348)
        self.assertEqual(corpus.EXPECTED_CORPUS_COUNT, 22)

    def test_native_invoker_authenticates_exact_code_before_input(self) -> None:
        self.assertIn("provider_module_offset = 0xB70B4", C_SOURCE)
        self.assertIn("provider_code_byte_count = 984", C_SOURCE)
        self.assertIn("provider_object_byte_count = 384", C_SOURCE)
        self.assertLess(C_SOURCE.index("PROVIDER_CODE="), C_SOURCE.index("fgets("))
        self.assertLess(C_SOURCE.index("memcmp(uuid"), C_SOURCE.index("fgets("))
        self.assertIn("mov x20, x0", ASSEMBLY_SOURCE)
        self.assertIn("blr x1", ASSEMBLY_SOURCE)
        self.assertIn("stp x20, x30", ASSEMBLY_SOURCE)
        self.assertIn("ldp x20, x30", ASSEMBLY_SOURCE)

    def test_capture_dispatches_every_frozen_object_before_classification(self) -> None:
        write_loop = CAPTURE_SOURCE.index("for record in records:")
        close_input = CAPTURE_SOURCE.index("process.stdin.close()", write_loop)
        read_loop = CAPTURE_SOURCE.index("for ordinal, record in enumerate(records):")
        comparison = CAPTURE_SOURCE.index("returnMatchedBitwise", read_loop)
        self.assertLess(write_loop, close_input)
        self.assertLess(close_input, read_loop)
        self.assertLess(read_loop, comparison)
        self.assertIn('REMOTE_HOST = "quince@10.0.41.19"', CAPTURE_SOURCE)
        self.assertIn('git", "status", "--porcelain', CAPTURE_SOURCE)
        self.assertNotIn("/nix/store/", CAPTURE_SOURCE)

    def test_product_authority_stays_closed(self) -> None:
        self.assertIn('"completeFiniteProviderLaw": False', VALIDATOR_SOURCE)
        self.assertIn('"publicInputFieldMappingEstablished": False', VALIDATOR_SOURCE)
        self.assertIn('"liquidGlassParityEstablished": False', VALIDATOR_SOURCE)
        self.assertIn('"productionShaderAuthorized": False', VALIDATOR_SOURCE)

    def test_preregistration_is_frozen_and_outcomes_are_unknown(self) -> None:
        frozen = PREREGISTRATION["frozenCorpus"]
        self.assertEqual(frozen["recordCount"], 22)
        self.assertEqual(frozen["coverage"]["observedBranchOutcomeCount"], 75)
        self.assertEqual(
            frozen["rawObjectsAndPredictionsSHA256"],
            "4ad66c334d3b9d2bddca232594ae9537b42a8e198091e7f4beee2b31c7613970",
        )
        self.assertIsNone(PREREGISTRATION["runtimeOutcomeFrozenBeforeDispatch"])
        self.assertTrue(
            all(
                value is None
                for value in PREREGISTRATION["unknownBeforeDispatch"].values()
            )
        )
        for record in PREREGISTRATION["frozenFiles"]:
            observed = hashlib.sha256(
                (ANALYSIS.parent / record["path"]).read_bytes()
            ).hexdigest()
            self.assertEqual(observed, record["sha256"], record["path"])


if __name__ == "__main__":
    unittest.main()
