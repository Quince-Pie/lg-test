#!/usr/bin/env python3
"""Tests for matched numerator/determinant factorization tomography."""

import unittest

import validate_raster_general_height_factorization as factorization


def float_components(bits: int) -> tuple[int, int]:
    exponent = (bits >> 23) & 0xFF
    significand = (1 << 23) | (bits & 0x7F_FFFF)
    return significand, exponent - 150


class RasterGeneralHeightFactorizationTests(unittest.TestCase):
    def test_preregistration_and_layout_are_frozen(self) -> None:
        factorization.load_preregistration()
        self.assertEqual(
            factorization.uint32_sha256(
                [value for pair in factorization.bridge_pairs() for value in pair]
            ),
            "284a1566ea432994831a277612ce19bfaf7d382e845f224feb7a63813bae198b",
        )
        self.assertEqual(
            factorization.layout_metadata(),
            {
                "baseCaseCount": 64,
                "baseCaseWordsSha256": factorization.BASE_CASE_WORDS_SHA256,
                "caseCount": 192,
                "caseWordsSha256": factorization.CASE_WORDS_SHA256,
                "fineInputCount": 4_096,
                "exactInputCount": 4_096,
                "inputCount": 8_192,
                "significandsSha256": factorization.SIGNIFICANDS_SHA256,
                "caseDeltaBitsCount": 1_572_864,
                "caseDeltaBitsSha256": factorization.CASE_DELTA_BITS_SHA256,
                "recordCount": 4_718_592,
                "rawBytes": 37_748_736,
            },
        )

    def test_every_capture_pair_has_the_same_exact_determinant(self) -> None:
        cases = factorization.capture_cases()
        significands = factorization.generate_significands()
        for base_index, base in enumerate(factorization.base_cases()):
            selected = cases[
                base_index * factorization.VARIANT_COUNT : (base_index + 1)
                * factorization.VARIANT_COUNT
            ]
            determinants = {
                int(case["width"]) * int(case["height"]) for case in selected
            }
            self.assertEqual(determinants, {int(base["area"])})
            self.assertEqual(
                [case["variant"] for case in selected],
                list(factorization.VARIANTS),
            )
            for case in selected:
                for sample_index in range(factorization.SAMPLE_POSITION_COUNT):
                    factorization.sample_position(case, sample_index)
            odd_deltas = factorization.case_delta_bits(selected[0], significands)
            width_index = int(base["oddWidth"]) - 8_192
            old_shift = factorization.top_left.factorized.delta_exponent_shift_bits()[
                width_index
            ]
            for input_index, witness_index in factorization.bridge_pairs():
                self.assertEqual(
                    odd_deltas[input_index],
                    factorization.top_left.arithmetic.witness_delta_bits()[
                        witness_index
                    ]
                    - old_shift,
                )

    def test_exact_bank_has_the_same_mathematical_plane_numerator(self) -> None:
        significands = factorization.generate_significands()
        self.assertEqual(len(set(significands)), factorization.INPUT_COUNT)
        self.assertEqual(
            len(
                set(significands[: factorization.FINE_INPUT_COUNT])
                & set(factorization.top_left.arithmetic.WITNESS_SIGNIFICANDS)
            ),
            8,
        )
        exact_significands = significands[factorization.FINE_INPUT_COUNT :]
        self.assertTrue(
            set(exact_significands).isdisjoint(
                factorization.top_left.arithmetic.WITNESS_SIGNIFICANDS
            )
        )
        fine_same_count = 0
        exact_same_count = 0
        for base in factorization.base_cases():
            height = int(base["height"])
            area_shift = int(base["areaShift"])
            delta_exponent_shift = int(base["deltaExponentShift"])
            for input_index, significand in enumerate(significands):
                floor_bits = factorization.rounded_product_delta_bits(
                    significand,
                    height=height,
                    area_shift=area_shift,
                    delta_exponent_shift=delta_exponent_shift,
                    upward=False,
                )
                ceil_bits = factorization.rounded_product_delta_bits(
                    significand,
                    height=height,
                    area_shift=area_shift,
                    delta_exponent_shift=delta_exponent_shift,
                    upward=True,
                )
                if floor_bits == ceil_bits:
                    if input_index < factorization.FINE_INPUT_COUNT:
                        fine_same_count += 1
                    else:
                        exact_same_count += 1
            power_height = int(base["powerHeight"])
            for significand in exact_significands:
                control_bits = factorization.rounded_product_delta_bits(
                    significand,
                    height=height,
                    area_shift=area_shift,
                    delta_exponent_shift=delta_exponent_shift,
                    upward=False,
                )
                control_significand, control_exponent = float_components(control_bits)
                left = significand * height
                right = control_significand * power_height
                odd_exponent = -24 - delta_exponent_shift
                if control_exponent >= odd_exponent:
                    right <<= control_exponent - odd_exponent
                else:
                    left <<= odd_exponent - control_exponent
                self.assertEqual(left, right)
        self.assertEqual(fine_same_count, 3_936)
        self.assertEqual(exact_same_count, 262_144)

    def test_raw_layout_size_is_frozen(self) -> None:
        self.assertEqual(factorization.RECORD.size, 8)
        self.assertEqual(factorization.RECORD_COUNT, 4_718_592)
        self.assertEqual(factorization.RAW_BYTES, 37_748_736)


if __name__ == "__main__":
    unittest.main()
