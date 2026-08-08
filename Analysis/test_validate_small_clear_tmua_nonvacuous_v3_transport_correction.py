#!/usr/bin/env python3
"""Tests for the frozen v3 final-input dimension correction."""

from pathlib import Path
import unittest

import validate_small_clear_tmua_nonvacuous_v3_transport_correction as subject


class SmallClearTmuaV3TransportCorrectionTests(unittest.TestCase):
    def test_only_final_input_dimensions_are_corrected(self) -> None:
        calls: list[tuple[str, tuple[int, int], int]] = []

        def original(
            _directory: Path,
            _snapshot: dict[str, object],
            label: str,
            dimensions: tuple[int, int],
            salt: int,
        ) -> str:
            calls.append((label, dimensions, salt))
            return "digest"

        validate = subject.corrected_pattern_validator(original)
        self.assertEqual(
            validate(Path("capture"), {}, "sample 9 final input", (576, 448), 3),
            "digest",
        )
        self.assertEqual(
            validate(Path("capture"), {}, "sample 10 final input", (576, 448), 3),
            "digest",
        )
        self.assertEqual(
            validate(Path("capture"), {}, "sample 10 backdrop", (64, 64), 7),
            "digest",
        )
        self.assertEqual(
            calls,
            [
                ("sample 9 final input", (576, 448), 3),
                ("sample 10 final input", (576, 384), 3),
                ("sample 10 backdrop", (64, 64), 7),
            ],
        )

    def test_correction_rejects_nonfrozen_input_assumption(self) -> None:
        def original(
            _directory: Path,
            _snapshot: dict[str, object],
            _label: str,
            _dimensions: tuple[int, int],
            _salt: int,
        ) -> str:
            return "digest"

        validate = subject.corrected_pattern_validator(original)
        with self.assertRaisesRegex(ValueError, "frozen final-input assumption"):
            validate(
                Path("capture"),
                {},
                "sample 10 final input",
                (576, 384),
                3,
            )

    def test_correction_rejects_sample_outside_frozen_grid(self) -> None:
        def original(
            _directory: Path,
            _snapshot: dict[str, object],
            _label: str,
            _dimensions: tuple[int, int],
            _salt: int,
        ) -> str:
            return "digest"

        validate = subject.corrected_pattern_validator(original)
        with self.assertRaisesRegex(ValueError, "outside the frozen grid"):
            validate(
                Path("capture"),
                {},
                "sample 32 final input",
                (576, 448),
                3,
            )


if __name__ == "__main__":
    unittest.main()
