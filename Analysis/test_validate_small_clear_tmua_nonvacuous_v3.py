#!/usr/bin/env python3
"""Tests for the finite-source-positive-control validator."""

import json
from pathlib import Path
import tempfile
import unittest

import validate_small_clear_tmua_nonvacuous_v3 as subject


class SmallClearTmuaNonvacuousV3ValidatorTests(unittest.TestCase):
    def test_finite_source_payload_has_frozen_half_words(self) -> None:
        self.assertEqual(
            subject.finite_source_payload(2, 2),
            bytes.fromhex(
                "0034003c0030003c 003c003c003a003c 00340038003a003c 003c00380030003c"
            ),
        )

    def test_finite_source_payload_is_finite_and_opaque(self) -> None:
        payload = subject.finite_source_payload(4, 3)
        self.assertEqual(len(payload), 4 * 3 * 8)
        words = [
            int.from_bytes(payload[index : index + 2], "little")
            for index in range(0, len(payload), 2)
        ]
        self.assertTrue(
            all(word in {0x3000, 0x3400, 0x3800, 0x3A00, 0x3C00} for word in words)
        )
        self.assertEqual(words[3::4], [0x3C00] * 12)

    def test_finite_source_hash_is_deterministic_for_both_layouts(self) -> None:
        hashes = {
            width: subject.v2.sha256_bytes(subject.finite_source_payload(width, 128))
            for width in (64, 128)
        }
        self.assertEqual(len(set(hashes.values())), 2)
        self.assertEqual(
            hashes,
            {
                64: "b666b1596ea83c07a2eff81bca339446af7a8377e475a00458ce35c71fd56419",
                128: "fd3ff58e12b11badb18b4ddac67b98bbf88006c3f76d8fbddb436dd8c8013689",
            },
        )

    def test_candidate_grid_is_unchanged_from_v2(self) -> None:
        self.assertEqual(subject.SAMPLES, tuple(range(2, 32)))
        self.assertEqual(subject.TARGET_BYTES, 4_194_304)

    def test_source_hash_validation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preregistration.json"
            path.write_text(json.dumps({}), encoding="utf-8")
            relative = path.relative_to(path.anchor)
            preregistration = {"sourceSHA256": {str(relative): "0" * 64}}
            with self.assertRaisesRegex(ValueError, "pinned source"):
                subject.v2.validate_sources(preregistration)


if __name__ == "__main__":
    unittest.main()
