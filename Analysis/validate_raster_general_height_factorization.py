#!/usr/bin/env python3
"""Validate matched numerator/determinant factorization tomography."""

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path
from typing import Any

import validate_raster_general_height_top_left as top_left
import validate_raster_low_exponent_power2 as low_exponent


type JsonObject = dict[str, Any]

SCHEMA_VERSION = 6
RIG_VERSION = "metal-raster-general-height-factorization-6.0.0"
ROLE = "discovery-with-prospective-exact-factorization-control"
TARGET_WIDTH = 64
TARGET_HEIGHT = 256
VIEWPORT_WIDTH = 32_768
ORIGIN_Y = 11
SAMPLE_XS = (0, 15, 31)
SAMPLE_TILE_LOCAL_XS = SAMPLE_XS
SAMPLE_POSITION_COUNT = len(SAMPLE_XS)
CANDIDATE_RADIUS = 8
FINE_INPUT_COUNT = 4_096
EXACT_INPUT_COUNT = 4_096
INPUT_COUNT = FINE_INPUT_COUNT + EXACT_INPUT_COUNT
VARIANTS = ("odd", "power-floor", "power-ceil")
VARIANT_COUNT = len(VARIANTS)
ODD_WIDTHS: tuple[tuple[int, tuple[int, ...]], ...] = (
    (
        47,
        (
            8_192,
            8_576,
            8_928,
            9_312,
            9_664,
            10_048,
            10_400,
            10_784,
            11_136,
            11_904,
            12_608,
            13_376,
            14_080,
            14_848,
            15_552,
            16_320,
        ),
    ),
    (
        61,
        (
            8_192,
            8_480,
            8_960,
            9_536,
            10_048,
            10_624,
            11_200,
            11_776,
            12_352,
            12_928,
            13_504,
            14_080,
            14_592,
            15_168,
            15_744,
            16_320,
        ),
    ),
    (
        79,
        (
            8_192,
            8_640,
            9_088,
            9_536,
            9_920,
            10_368,
            10_816,
            11_264,
            11_712,
            12_160,
            12_608,
            13_056,
            13_568,
            14_464,
            15_360,
            16_256,
        ),
    ),
    (
        113,
        (
            8_192,
            8_512,
            8_768,
            9_088,
            9_600,
            10_240,
            10_752,
            11_392,
            12_032,
            12_672,
            13_184,
            13_824,
            14_464,
            15_104,
            15_616,
            16_256,
        ),
    ),
)
BASE_CASE_COUNT = sum(len(widths) for _, widths in ODD_WIDTHS)
CASE_COUNT = BASE_CASE_COUNT * VARIANT_COUNT
RECORD = struct.Struct("<2I")
RECORD_COUNT = CASE_COUNT * INPUT_COUNT * SAMPLE_POSITION_COUNT
RAW_BYTES = RECORD_COUNT * RECORD.size
SENTINEL = (0xFFFF_FFFF, 0xFFFF_FFFF)
PREREGISTRATION_PATH = Path(__file__).with_name(
    "raster_general_height_factorization_preregistration.json"
)
EXACT_ANALYSIS_SCRIPT_PATH = Path(__file__).with_name(
    "explore_exact_general_height_numerator.py"
)
EXACT_ANALYSIS_PATH = Path(__file__).with_name(
    "exact_general_height_numerator_analysis.json"
)
PREREGISTRATION_SHA256 = (
    "adfee23de593f8b34a1070f745159e80ce115e371e9419c1034bbb7fccd4cba4"
)
BASE_CASE_WORDS_SHA256 = (
    "e073bea9809b1fed485418902638baa006fce2b43258bf17d2983f3aa3473f89"
)
CASE_WORDS_SHA256 = "68f90846f919bd6f00a413a4e8061b6412e24567b1b4e1626c8d54a85efdf32c"
SIGNIFICANDS_SHA256 = "d91eafe4caba7e38c40decd5a03e6d8b966c5a4586ee213279fd1118b35be55a"
CASE_DELTA_BITS_SHA256 = (
    "814c61befbfcbcbbd55c48019ba02c40a659dd4fd37a7b6b5ee776227a302976"
)
SAMPLE_XS_SHA256 = "036f6670f2f5a456953f3bad012b7876e2df65e3cd18a439d79966046cb6477e"


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def uint32_sha256(values: list[int]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(struct.pack("<I", value))
    return digest.hexdigest()


def generate_significands() -> list[int]:
    result: list[int] = []
    for bank in range(16):
        numerator = 32_768 + 2_048 * bank + ((73 * bank + 19) & 255)
        result.extend((numerator << 8) | phase for phase in range(256))
    seen = set(result)
    sequence_index = 0
    while len(result) < INPUT_COUNT:
        exact_index = (40_503 * sequence_index + 12_345) & 0xFFFF
        significand = 0x80_0000 | (exact_index << 7)
        sequence_index += 1
        if significand not in seen:
            seen.add(significand)
            result.append(significand)
    if (
        len(result) != INPUT_COUNT
        or len(seen) != INPUT_COUNT
        or any(not 1 << 23 <= value < 1 << 24 for value in result)
        or any(value & 0x7F != 0 for value in result[FINE_INPUT_COUNT:])
    ):
        raise ValueError("factorization significand generator differs")
    return result


def bridge_pairs() -> list[tuple[int, int]]:
    input_indices = {
        significand: index for index, significand in enumerate(generate_significands())
    }
    result = [
        (input_indices[significand], witness_index)
        for witness_index, significand in enumerate(
            top_left.arithmetic.WITNESS_SIGNIFICANDS
        )
        if significand in input_indices
    ]
    if len(result) != 8 or any(
        input_index >= FINE_INPUT_COUNT for input_index, _ in result
    ):
        raise ValueError("factorization bridge inputs differ")
    return result


def odd_delta_bits(significand: int, *, delta_exponent_shift: int) -> int:
    return (0x3F00_0000 | (significand & 0x7F_FFFF)) - (
        delta_exponent_shift * 0x0080_0000
    )


def base_cases() -> list[JsonObject]:
    result: list[JsonObject] = []
    for height, widths in ODD_WIDTHS:
        for width in widths:
            area = width * height
            area_shift = area.bit_length() - 14
            normalized_width, remainder = divmod(area, 1 << area_shift)
            if remainder or not 8_192 <= normalized_width <= 16_383:
                raise ValueError("factorization determinant is not exact-normalized")
            result.append(
                {
                    "height": height,
                    "oddWidth": width,
                    "area": area,
                    "areaShift": area_shift,
                    "normalizedWidth": normalized_width,
                    "powerHeight": 1 << area_shift,
                    "deltaExponentShift": 2 if width == 8_192 else 1,
                }
            )
    if len(result) != BASE_CASE_COUNT:
        raise ValueError("factorization base-case count differs")
    return result


def capture_cases() -> list[JsonObject]:
    result: list[JsonObject] = []
    for base_index, base in enumerate(base_cases()):
        for variant in VARIANTS:
            odd = variant == "odd"
            result.append(
                {
                    "baseIndex": base_index,
                    "variant": variant,
                    "width": base["oddWidth"] if odd else base["normalizedWidth"],
                    "height": base["height"] if odd else base["powerHeight"],
                    "oddHeight": base["height"],
                    "area": base["area"],
                    "areaShift": base["areaShift"],
                    "deltaExponentShift": base["deltaExponentShift"],
                }
            )
    if len(result) != CASE_COUNT:
        raise ValueError("factorization capture-case count differs")
    return result


def rounded_product_delta_bits(
    significand: int,
    *,
    height: int,
    area_shift: int,
    delta_exponent_shift: int,
    upward: bool,
) -> int:
    product = significand * height
    product_shift = product.bit_length() - 24
    rounded, remainder = divmod(product, 1 << product_shift)
    rounded += upward and remainder != 0
    exponent = 126 + product_shift - area_shift - delta_exponent_shift
    if rounded == 1 << 24:
        rounded >>= 1
        exponent += 1
    if not 1 << 23 <= rounded < 1 << 24 or not 1 <= exponent < 255:
        raise ValueError("factorization control delta is not a normal binary32")
    return (exponent << 23) | (rounded & 0x7F_FFFF)


def case_delta_bits(case: JsonObject, significands: list[int]) -> list[int]:
    variant = str(case["variant"])
    if variant == "odd":
        return [
            odd_delta_bits(
                significand,
                delta_exponent_shift=int(case["deltaExponentShift"]),
            )
            for significand in significands
        ]
    return [
        rounded_product_delta_bits(
            significand,
            height=int(case["oddHeight"]),
            area_shift=int(case["areaShift"]),
            delta_exponent_shift=int(case["deltaExponentShift"]),
            upward=variant == "power-ceil",
        )
        for significand in significands
    ]


def all_delta_bits() -> list[int]:
    significands = generate_significands()
    return [
        bits for case in capture_cases() for bits in case_delta_bits(case, significands)
    ]


def layout_metadata() -> JsonObject:
    significands = generate_significands()
    bases = base_cases()
    cases = capture_cases()
    deltas = all_delta_bits()
    base_words = [
        value
        for case in bases
        for value in (
            int(case["height"]),
            int(case["oddWidth"]),
            int(case["area"]),
            int(case["areaShift"]),
            int(case["normalizedWidth"]),
            int(case["powerHeight"]),
            int(case["deltaExponentShift"]),
        )
    ]
    case_words = [
        value
        for case in cases
        for value in (
            int(case["baseIndex"]),
            VARIANTS.index(str(case["variant"])),
            int(case["width"]),
            int(case["height"]),
            int(case["oddHeight"]),
            int(case["area"]),
            int(case["areaShift"]),
            int(case["deltaExponentShift"]),
        )
    ]
    return {
        "baseCaseCount": len(bases),
        "baseCaseWordsSha256": uint32_sha256(base_words),
        "caseCount": len(cases),
        "caseWordsSha256": uint32_sha256(case_words),
        "fineInputCount": FINE_INPUT_COUNT,
        "exactInputCount": EXACT_INPUT_COUNT,
        "inputCount": len(significands),
        "significandsSha256": uint32_sha256(significands),
        "caseDeltaBitsCount": len(deltas),
        "caseDeltaBitsSha256": uint32_sha256(deltas),
        "recordCount": RECORD_COUNT,
        "rawBytes": RAW_BYTES,
    }


def load_preregistration() -> JsonObject:
    preregistration: JsonObject = json.loads(
        PREREGISTRATION_PATH.read_text(encoding="utf-8")
    )
    source = preregistration.get("sourceEvidence", {})
    base = preregistration.get("baseCases", {})
    inputs = preregistration.get("inputs", {})
    capture = preregistration.get("capture", {})
    recovery = preregistration.get("slopeRecovery", {})
    control = preregistration.get("prospectiveControl", {})
    bridge = preregistration.get("crossRunControl", {})
    acceptance = preregistration.get("acceptance", {})
    metadata = layout_metadata()
    if (
        sha256_path(PREREGISTRATION_PATH) != PREREGISTRATION_SHA256
        or preregistration.get("schemaVersion") != 1
        or preregistration.get("role") != ROLE
        or preregistration.get("observedAtPreregistration") is not False
        or source.get("generalHeightTopLeftRunId") != 30_663_719_233
        or source.get("lowExponentRunId") != 30_666_092_410
        or source.get("lowExponentPredictedExactMatchCount") != 458_752
        or source.get("exactNumeratorAnalysisSha256")
        != "56851d72d40df3e9777778ad7eaaed271b9ba132b5b37610855c44aa7d6453ae"
        or sha256_path(EXACT_ANALYSIS_SCRIPT_PATH)
        != "e291f89446ea595ea1cf7a89051a5b7c8ee126f7df7a92bd6dfb6216d1d9a647"
        or sha256_path(EXACT_ANALYSIS_PATH)
        != "56851d72d40df3e9777778ad7eaaed271b9ba132b5b37610855c44aa7d6453ae"
        or source.get("simpleModelBestExactNormalizedMatchCount") != 6_452
        or source.get("numeratorModelBestExactNormalizedMatchCount") != 6_450
        or source.get("simpleModelExactNormalizedCoefficientCount") != 6_776
        or source.get("singleNumeratorValueImpossibleGroupCount") != 48
        or source.get("singleNumeratorValueGroupCount") != 56
        or base.get("heightOrder") != [height for height, _ in ODD_WIDTHS]
        or base.get("oddWidthsByHeight") != [list(widths) for _, widths in ODD_WIDTHS]
        or base.get("baseCaseCount") != BASE_CASE_COUNT
        or base.get("baseCaseWordsSha256") != BASE_CASE_WORDS_SHA256
        or inputs.get("fineInputCount") != FINE_INPUT_COUNT
        or inputs.get("fineGeneralHeightWitnessBridgeCount") != 8
        or inputs.get("fineOddHeightUnobservedCount") != 4_088
        or inputs.get("exactInputCount") != EXACT_INPUT_COUNT
        or inputs.get("exactInputsDisjointFromGeneralHeightWitnesses") is not True
        or inputs.get("inputCount") != INPUT_COUNT
        or inputs.get("allInputsUnique") is not True
        or inputs.get("significandsSha256") != SIGNIFICANDS_SHA256
        or bridge.get("bridgePairCount") != 8
        or bridge.get("bridgePairsSha256")
        != "284a1566ea432994831a277612ce19bfaf7d382e845f224feb7a63813bae198b"
        or bridge.get("comparisonCount") != BASE_CASE_COUNT * 8
        or bridge.get("mustMatchFrozenTopLeftSlopes") is not True
        or capture.get("variantsInOrder") != list(VARIANTS)
        or capture.get("fineFloorEqualsCeilCount") != 3_936
        or capture.get("fineFloorDiffersFromCeilCount") != 258_208
        or capture.get("exactFloorEqualsCeilCount") != 262_144
        or capture.get("exactFloorDiffersFromCeilCount") != 0
        or capture.get("caseCount") != CASE_COUNT
        or capture.get("caseWordsSha256") != CASE_WORDS_SHA256
        or capture.get("caseDeltaBitsCount") != CASE_COUNT * INPUT_COUNT
        or capture.get("caseDeltaBitsSha256") != CASE_DELTA_BITS_SHA256
        or capture.get("targetWidth") != TARGET_WIDTH
        or capture.get("targetHeight") != TARGET_HEIGHT
        or capture.get("viewportWidth") != VIEWPORT_WIDTH
        or capture.get("originY") != ORIGIN_Y
        or capture.get("sampleXs") != list(SAMPLE_XS)
        or capture.get("sampleXsSha256") != SAMPLE_XS_SHA256
        or capture.get("recordComponents") != ["pull@0,0.5", "pull@15/16,0.5"]
        or capture.get("recordBytes") != RECORD.size
        or capture.get("recordCount") != RECORD_COUNT
        or capture.get("rawBytes") != RAW_BYTES
        or recovery.get("syntheticPreflightCoefficientCount")
        != CASE_COUNT * INPUT_COUNT
        or recovery.get("syntheticPreflightUniqueCoefficientCount")
        != CASE_COUNT * INPUT_COUNT
        or recovery.get("syntheticPreflightUniqueSlopeBitsCount") != 425_876
        or control.get("exactComparisonCount") != BASE_CASE_COUNT * EXACT_INPUT_COUNT
        or control.get("equalDeterminant") is not True
        or control.get("equalMathematicalPlaneNumerator") is not True
        or acceptance
        != {
            "allRecordsWrittenAndFinite": True,
            "allSamplesSafelyInsideTopLeftPrimitive": True,
            "everyCoefficientHasExactlyOneRecoveredSlope": True,
            "allFrozenTopLeftBridgeSlopesMatch": True,
            "exactFactorizationControlResultMustBeReported": True,
            "fineFloorAndCeilRelationsMustBeReported": True,
            "captureValidityDoesNotDependOnWhichFactorizationHypothesisWins": True,
        }
        or metadata
        != {
            "baseCaseCount": BASE_CASE_COUNT,
            "baseCaseWordsSha256": BASE_CASE_WORDS_SHA256,
            "caseCount": CASE_COUNT,
            "caseWordsSha256": CASE_WORDS_SHA256,
            "fineInputCount": FINE_INPUT_COUNT,
            "exactInputCount": EXACT_INPUT_COUNT,
            "inputCount": INPUT_COUNT,
            "significandsSha256": SIGNIFICANDS_SHA256,
            "caseDeltaBitsCount": CASE_COUNT * INPUT_COUNT,
            "caseDeltaBitsSha256": CASE_DELTA_BITS_SHA256,
            "recordCount": RECORD_COUNT,
            "rawBytes": RAW_BYTES,
        }
    ):
        raise ValueError("factorization preregistration differs")
    return preregistration


def validate_manifest(root: Path) -> tuple[JsonObject, Path]:
    manifest: JsonObject = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    evidence = manifest.get("rasterGeneralHeightFactorization", {})
    path = root / str(evidence.get("file", ""))
    if (
        manifest.get("schemaVersion") != SCHEMA_VERSION
        or manifest.get("rigVersion") != RIG_VERSION
        or not isinstance(manifest.get("ciCommit"), str)
        or len(manifest.get("ciCommit", "")) != 40
        or evidence.get("role") != ROLE
        or evidence.get("preregistrationFile")
        != "Analysis/raster_general_height_factorization_preregistration.json"
        or evidence.get("preregistrationSha256") != PREREGISTRATION_SHA256
        or evidence.get("baseCases") != base_cases()
        or evidence.get("variantsInOrder") != list(VARIANTS)
        or evidence.get("baseCaseCount") != BASE_CASE_COUNT
        or evidence.get("baseCaseWordsSha256") != BASE_CASE_WORDS_SHA256
        or evidence.get("caseCount") != CASE_COUNT
        or evidence.get("caseWordsSha256") != CASE_WORDS_SHA256
        or evidence.get("fineInputCount") != FINE_INPUT_COUNT
        or evidence.get("exactInputCount") != EXACT_INPUT_COUNT
        or evidence.get("inputCount") != INPUT_COUNT
        or evidence.get("significandsSha256") != SIGNIFICANDS_SHA256
        or evidence.get("caseDeltaBitsCount") != CASE_COUNT * INPUT_COUNT
        or evidence.get("caseDeltaBitsSha256") != CASE_DELTA_BITS_SHA256
        or evidence.get("bridgePairCount") != len(bridge_pairs())
        or evidence.get("bridgePairsSha256")
        != "284a1566ea432994831a277612ce19bfaf7d382e845f224feb7a63813bae198b"
        or evidence.get("syntheticPreflightUniqueCoefficientCount")
        != CASE_COUNT * INPUT_COUNT
        or evidence.get("syntheticPreflightUniqueSlopeBitsCount") != 425_876
        or evidence.get("targetWidth") != TARGET_WIDTH
        or evidence.get("targetHeight") != TARGET_HEIGHT
        or evidence.get("viewportWidth") != VIEWPORT_WIDTH
        or evidence.get("originY") != ORIGIN_Y
        or evidence.get("sampleXs") != list(SAMPLE_XS)
        or evidence.get("sampleXsSha256") != SAMPLE_XS_SHA256
        or evidence.get("candidateRadiusFloatUlps") != CANDIDATE_RADIUS
        or evidence.get("ordering") != "case-major,input-major,sample-position-major"
        or evidence.get("recordBytes") != RECORD.size
        or evidence.get("recordComponents") != ["pull@0,0.5", "pull@15/16,0.5"]
        or evidence.get("uncoveredRecordSentinel") != "0xffffffffffffffff"
        or evidence.get("bytes") != RAW_BYTES
        or not path.is_file()
        or path.stat().st_size != RAW_BYTES
        or sha256_path(path) != evidence.get("sha256")
    ):
        raise ValueError("factorization manifest differs")
    return manifest, path


def finite_float_bits(bits: int) -> bool:
    return bits & 0x7F80_0000 != 0x7F80_0000


def accepted_slopes(
    direct_bits: int,
    records: list[tuple[int, int]],
) -> tuple[int, ...]:
    accepted: list[int] = []
    observations = [
        observation
        for sample_index, position in enumerate(SAMPLE_TILE_LOCAL_XS)
        for observation in (
            (float(position), records[sample_index][0]),
            (float(position) + 0.9375, records[sample_index][1]),
        )
    ]
    for offset in range(-CANDIDATE_RADIUS, CANDIDATE_RADIUS + 1):
        slope_bits = direct_bits + offset
        if top_left.factorized.shared_plane_accepts_slope(
            slope_bits,
            observations=observations,
        ):
            accepted.append(slope_bits)
    return tuple(accepted)


def counter_json(counter: Counter[int | str]) -> JsonObject:
    return {
        str(key): value
        for key, value in sorted(counter.items(), key=lambda item: str(item[0]))
    }


def validate(root: Path) -> JsonObject:
    load_preregistration()
    manifest, path = validate_manifest(root)
    data = path.read_bytes()
    cases = capture_cases()
    deltas = all_delta_bits()
    multiplicity: Counter[int] = Counter()
    direct_offsets: Counter[int] = Counter()
    fine_relations: Counter[str] = Counter()
    fine_odd_minus_floor: Counter[int] = Counter()
    fine_odd_minus_ceil: Counter[int] = Counter()
    fine_ceil_minus_floor: Counter[int] = Counter()
    exact_relations: Counter[str] = Counter()
    exact_odd_minus_power: Counter[int] = Counter()
    bridge_mismatches: Counter[int] = Counter()
    first_failures: list[JsonObject] = []
    unique_count = 0
    bridge_match_count = 0
    recovered_digest = hashlib.sha256()
    bridge_digest = hashlib.sha256()
    frozen_offsets = low_exponent.load_top_left_slope_offsets()
    bridges = bridge_pairs()
    bases = base_cases()

    def records_at(case_index: int, input_index: int) -> list[tuple[int, int]]:
        return [
            RECORD.unpack_from(
                data,
                (
                    (case_index * INPUT_COUNT + input_index) * SAMPLE_POSITION_COUNT
                    + sample_index
                )
                * RECORD.size,
            )
            for sample_index in range(SAMPLE_POSITION_COUNT)
        ]

    for base_index in range(BASE_CASE_COUNT):
        recovered_by_variant: list[list[int]] = []
        delta_by_variant: list[list[int]] = []
        for variant_index in range(VARIANT_COUNT):
            case_index = base_index * VARIANT_COUNT + variant_index
            case = cases[case_index]
            for sample_index in range(SAMPLE_POSITION_COUNT):
                sample_position(case, sample_index)
            case_recovered: list[int] = []
            case_deltas = deltas[
                case_index * INPUT_COUNT : (case_index + 1) * INPUT_COUNT
            ]
            delta_by_variant.append(case_deltas)
            for input_index, delta_bits in enumerate(case_deltas):
                records = records_at(case_index, input_index)
                if any(
                    record == SENTINEL
                    or not all(finite_float_bits(bits) for bits in record)
                    for record in records
                ):
                    raise ValueError("factorization capture has missing records")
                delta = top_left.arithmetic.float32_value(delta_bits)
                direct_bits = top_left.arithmetic.float32_bits(
                    delta / int(case["width"])
                )
                accepted = accepted_slopes(direct_bits, records)
                multiplicity[len(accepted)] += 1
                recovered = accepted[0] if len(accepted) == 1 else 0xFFFF_FFFF
                recovered_digest.update(struct.pack("<I", recovered))
                case_recovered.append(recovered)
                if len(accepted) == 1:
                    unique_count += 1
                    direct_offsets[recovered - direct_bits] += 1
                elif len(first_failures) < 32:
                    first_failures.append(
                        {
                            "baseIndex": base_index,
                            "variant": case["variant"],
                            "inputIndex": input_index,
                            "acceptedOffsets": [
                                candidate - direct_bits for candidate in accepted
                            ],
                        }
                    )
            recovered_by_variant.append(case_recovered)

        odd, floor, ceil = recovered_by_variant
        odd_delta, floor_delta, ceil_delta = delta_by_variant
        base = bases[base_index]
        width_index = int(base["oddWidth"]) - 8_192
        geometry_index = [height for height, _ in ODD_WIDTHS].index(int(base["height"]))
        old_shift = top_left.factorized.delta_exponent_shift_bits()[width_index]
        for input_index, witness_index in bridges:
            old_delta_bits = (
                top_left.arithmetic.witness_delta_bits()[witness_index] - old_shift
            )
            old_delta = top_left.arithmetic.float32_value(old_delta_bits)
            old_direct = top_left.arithmetic.float32_bits(
                old_delta / int(base["oddWidth"])
            )
            offset_index = (
                width_index * len(top_left.arithmetic.WITNESS_SIGNIFICANDS)
                + witness_index
            ) * len(ODD_WIDTHS) + geometry_index
            encoded_offset = frozen_offsets[offset_index]
            signed_offset = (
                encoded_offset if encoded_offset < 128 else encoded_offset - 256
            )
            expected = old_direct + signed_offset
            actual = odd[input_index]
            bridge_digest.update(struct.pack("<I", actual))
            bridge_match_count += actual == expected
            bridge_mismatches[actual - expected] += 1
            if actual != expected and len(first_failures) < 32:
                first_failures.append(
                    {
                        "baseIndex": base_index,
                        "inputIndex": input_index,
                        "witnessIndex": witness_index,
                        "reason": "frozen top-left bridge slope differs",
                        "expectedBits": f"0x{expected:08x}",
                        "actualBits": f"0x{actual:08x}",
                    }
                )
        for input_index in range(INPUT_COUNT):
            slopes = odd[input_index], floor[input_index], ceil[input_index]
            if input_index < FINE_INPUT_COUNT:
                if slopes[0] == slopes[1] == slopes[2]:
                    relation = "odd-equals-floor-equals-ceil"
                elif slopes[0] == slopes[1]:
                    relation = "odd-equals-floor"
                elif slopes[0] == slopes[2]:
                    relation = "odd-equals-ceil"
                elif slopes[1] < slopes[0] < slopes[2]:
                    relation = "floor-less-than-odd-less-than-ceil"
                elif slopes[0] < slopes[1]:
                    relation = "odd-less-than-floor"
                elif slopes[0] > slopes[2]:
                    relation = "odd-greater-than-ceil"
                else:
                    relation = "other"
                fine_relations[relation] += 1
                fine_odd_minus_floor[slopes[0] - slopes[1]] += 1
                fine_odd_minus_ceil[slopes[0] - slopes[2]] += 1
                fine_ceil_minus_floor[slopes[2] - slopes[1]] += 1
            else:
                equal_delta = floor_delta[input_index] == ceil_delta[input_index]
                equal_slopes = slopes[0] == slopes[1] == slopes[2]
                relation = (
                    "all-equal"
                    if equal_slopes
                    else "odd-differs-from-equal-power-controls"
                )
                exact_relations[relation] += 1
                exact_odd_minus_power[slopes[0] - slopes[1]] += 1
                if (
                    not equal_delta
                    or odd_delta[input_index] == floor_delta[input_index]
                    or not equal_slopes
                ) and len(first_failures) < 32:
                    reason = (
                        "exact factorization input invariant differs"
                        if not equal_delta
                        or odd_delta[input_index] == floor_delta[input_index]
                        else "exact factorization slopes differ"
                    )
                    first_failures.append(
                        {
                            "baseIndex": base_index,
                            "inputIndex": input_index,
                            "reason": reason,
                            "slopeBits": [f"0x{bits:08x}" for bits in slopes],
                        }
                    )

    structurally_valid = unique_count == CASE_COUNT * INPUT_COUNT
    bridge_comparison_count = BASE_CASE_COUNT * len(bridges)
    bridge_gate = bridge_match_count == bridge_comparison_count
    valid_for_comparison = structurally_valid and bridge_gate
    exact_comparison_count = BASE_CASE_COUNT * EXACT_INPUT_COUNT
    exact_equal_count = exact_relations["all-equal"]
    exact_gate = valid_for_comparison and exact_equal_count == exact_comparison_count
    return {
        "liquidGlassRasterGeneralHeightFactorizationValidationSchemaVersion": 1,
        "classification": ROLE,
        "probe": str(root),
        "ciCommit": manifest.get("ciCommit"),
        "manifestSha256": sha256_path(root / "manifest.json"),
        "rawSha256": sha256_path(path),
        "preregistrationSha256": PREREGISTRATION_SHA256,
        "measurement": {
            "recordCount": RECORD_COUNT,
            "coefficientCount": CASE_COUNT * INPUT_COUNT,
            "candidateMultiplicity": counter_json(multiplicity),
            "recoveredDirectDivisionOffsetDistribution": counter_json(direct_offsets),
            "uniqueCoefficientCount": unique_count,
            "recoveredSlopeTableSha256": recovered_digest.hexdigest(),
            "bridgeComparisonCount": bridge_comparison_count,
            "bridgeExactMatchCount": bridge_match_count,
            "bridgeMismatchFloatUlpDistribution": counter_json(bridge_mismatches),
            "bridgeRecoveredSlopeTableSha256": bridge_digest.hexdigest(),
            "frozenTopLeftBridgeControlGate": bridge_gate,
            "fineComparisonCount": BASE_CASE_COUNT * FINE_INPUT_COUNT,
            "fineRelations": counter_json(fine_relations),
            "fineOddMinusFloorFloatUlpDistribution": counter_json(fine_odd_minus_floor),
            "fineOddMinusCeilFloatUlpDistribution": counter_json(fine_odd_minus_ceil),
            "fineCeilMinusFloorFloatUlpDistribution": counter_json(
                fine_ceil_minus_floor
            ),
            "exactComparisonCount": exact_comparison_count,
            "exactRelations": counter_json(exact_relations),
            "exactOddMinusPowerFloatUlpDistribution": counter_json(
                exact_odd_minus_power
            ),
            "exactFactorizationControlGate": exact_gate,
            "firstFailures": first_failures,
            "allRecordsFinite": True,
            "allSamplesSafelyInsideTopLeftPrimitive": True,
            "structurallyValid": structurally_valid,
            "captureValidForComparison": valid_for_comparison,
        },
        "conclusions": {
            "setupDependsOnlyOnNumericalNumeratorAndDeterminantForExactBank": (
                exact_gate
            ),
            "factorizationDependentSetupObserved": valid_for_comparison
            and not exact_gate,
            "completeOddHeightArithmeticEstablished": False,
            "nonExactDeterminantSelectorEstablished": False,
            "clippedSetupEstablished": False,
            "endToEndLiquidGlassParityEstablished": False,
        },
    }


def sample_position(case: JsonObject, sample_index: int) -> JsonObject:
    if sample_index not in range(SAMPLE_POSITION_COUNT):
        raise ValueError("factorization sample index differs")
    x = SAMPLE_XS[sample_index]
    width = int(case["width"])
    height = int(case["height"])
    signed_interior = width * (2 * height - 1) - height * (2 * x + 1)
    if (
        not 0 <= x < TARGET_WIDTH
        or ORIGIN_Y + height > TARGET_HEIGHT
        or width > VIEWPORT_WIDTH
        or signed_interior <= 1_024
    ):
        raise ValueError("factorization sample is not safely interior")
    return {
        "x": x,
        "y": ORIGIN_Y,
        "tileLocalX": x,
        "signedInteriorArea": signed_interior,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.root is None:
        print(json.dumps(layout_metadata(), indent=2, sort_keys=True))
        return
    if arguments.output is None:
        raise SystemExit("--output is required with a capture root")
    report = validate(arguments.root)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    raise SystemExit(0 if report["measurement"]["captureValidForComparison"] else 1)


if __name__ == "__main__":
    main()
