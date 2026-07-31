#!/usr/bin/env python3
"""Validate the exhaustive fractional-width raster selector sweep."""

import argparse
import hashlib
import json
import struct
import zlib
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

import build_raster_fractional_selector_witness_map as witness_map
import validate_raster_general_height_selector_transfer as general_selector


type JsonObject = dict[str, Any]

SCHEMA_VERSION = 1
RIG_VERSION = "metal-raster-fractional-selector-sweep-1.0.0"
ROLE = "prospective-exhaustive-fractional-width-reciprocal-selector-calibration"
TARGET_WIDTH = 64
TARGET_HEIGHT = 128
VIEWPORT_WIDTH = 32_768
ORIGIN_Y = 11
BATCH_CASE_COUNT = 65_536
PREREGISTRATION_PATH = Path(__file__).with_name(
    "raster_fractional_selector_sweep_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "942a513d58181b89f857401c0e4341edeca90d07e664cae69e1a6c80679afe0a"
)
WITNESS_REPORT_PATH = Path(__file__).with_name(
    "raster_fractional_selector_witness_map.json"
)
WITNESS_REPORT_SHA256 = (
    "da6d9a67b1594df4ca6be304ed5b2a6060c9216555c98d052ceb2c7ecb2d6025"
)
WITNESS_INDEX_PATH = Path(__file__).with_name(
    "raster_fractional_selector_witness_indices.bin"
)
WITNESS_INDEX_SHA256 = (
    "c8562d881275af6178ee239262d047b4fb19d127b4ac7da9ea04648c75e82296"
)
GENERAL_SELECTOR_PATH = Path(__file__).with_name(
    "raster_general_height_resolved_selectors.zlib"
)
GENERAL_SELECTOR_COMPRESSED_SHA256 = (
    "ae266b7bc78ccf28549d376627e73819eefa0596135fca4709a85d1070e00eee"
)
GENERAL_SELECTOR_RAW_SHA256 = (
    "0b8ece5b7c2ea05475fd76120987670bf29cf69d16916372af5cf4734fd209af"
)
GENERAL_PAIR_SHA256 = (
    "6537e22d40814cfc72e5d0295821f610e77236db8624a67c3e81edc183dfa59c"
)
COMBINED_CONTROL_SHA256 = (
    "c24bb5b7ff96924e7c645f2d51291dbb76f45eff4eddb332b8abb685d0f2350c"
)
CANONICAL_SELECTOR_SHA256 = (
    "2c58cdd15e8db020f6a0f22716bf0fbcc4c33edda429724c23094eeb7e87a8fb"
)
RECORD = struct.Struct("<2I")
SENTINEL = (0xFFFF_FFFF, 0xFFFF_FFFF)
AMBIGUOUS_SELECTOR = 0xFFFF_FFFF


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def counter_json(counter: Counter[int]) -> JsonObject:
    return {str(key): value for key, value in sorted(counter.items())}


def load_witness_inputs() -> tuple[JsonObject, bytes]:
    report: JsonObject = json.loads(
        WITNESS_REPORT_PATH.read_text(encoding="utf-8")
    )
    indices = WITNESS_INDEX_PATH.read_bytes()
    if (
        sha256_path(WITNESS_REPORT_PATH) != WITNESS_REPORT_SHA256
        or sha256_path(WITNESS_INDEX_PATH) != WITNESS_INDEX_SHA256
        or len(indices) != witness_map.MANTISSA_COUNT
        or report.get("witnessIndexSha256") != WITNESS_INDEX_SHA256
        or report.get("candidateSlopePairSha256")
        != "785738882867b59709bfe125f8e32c1d9fc9d7debec8cef94d848dfe3b08a20f"
        or report.get("candidateSlopeDistinctCount")
        != witness_map.MANTISSA_COUNT - 1
        or report.get("rawBytes")
        != witness_map.MANTISSA_COUNT * len(witness_map.SAMPLE_XS) * RECORD.size
    ):
        raise ValueError("fractional selector witness inputs differ")
    return report, indices


def general_mantissa_index(determinant: int) -> int:
    exponent = (determinant - 1).bit_length()
    if determinant == 1 << exponent:
        return 0
    normalized_input = determinant << (24 - exponent)
    if not 1 << 23 < normalized_input < 1 << 24:
        raise ValueError("general-height determinant normalization differs")
    return normalized_input - (1 << 23)


def sealed_controls() -> JsonObject:
    canonical = (
        general_selector.factorization.low_exponent.factorized.canonical_reciprocals()
    )
    if general_selector.uint32_sha256(canonical) != CANONICAL_SELECTOR_SHA256:
        raise ValueError("canonical selector table differs")
    compressed = GENERAL_SELECTOR_PATH.read_bytes()
    general_bytes = zlib.decompress(compressed)
    if (
        sha256_bytes(compressed) != GENERAL_SELECTOR_COMPRESSED_SHA256
        or sha256_bytes(general_bytes) != GENERAL_SELECTOR_RAW_SHA256
    ):
        raise ValueError("general-height selector table differs")
    general_values = tuple(
        value for (value,) in struct.iter_unpack("<I", general_bytes)
    )
    general_pairs = bytearray()
    general_unique: dict[int, int] = {}
    conflicts = 0
    for case_index, reciprocal in enumerate(general_values):
        width_index, height_index = divmod(
            case_index,
            general_selector.HEIGHT_COUNT,
        )
        determinant = (
            general_selector.WIDTHS[width_index]
            * general_selector.HEIGHTS[height_index]
        )
        mantissa = general_mantissa_index(determinant)
        general_pairs.extend(struct.pack("<II", mantissa, reciprocal))
        conflicts += (
            mantissa in general_unique
            and general_unique[mantissa] != reciprocal
        )
        general_unique[mantissa] = reciprocal
    combined = {
        index * 1_024: reciprocal
        for index, reciprocal in enumerate(canonical)
    }
    overlap_count = 0
    for mantissa, reciprocal in general_unique.items():
        overlap_count += mantissa in combined
        conflicts += mantissa in combined and combined[mantissa] != reciprocal
        combined[mantissa] = reciprocal
    combined_bytes = b"".join(
        struct.pack("<II", mantissa, reciprocal)
        for mantissa, reciprocal in sorted(combined.items())
    )
    if (
        sha256_bytes(general_pairs) != GENERAL_PAIR_SHA256
        or sha256_bytes(combined_bytes) != COMBINED_CONTROL_SHA256
        or len(general_values) != 32_768
        or len(general_unique) != 32_215
        or overlap_count != 473
        or len(combined) != 39_934
        or conflicts != 0
    ):
        raise ValueError("sealed fractional selector controls differ")
    return {
        "canonical": canonical,
        "generalValues": general_values,
        "generalUnique": general_unique,
        "combined": combined,
    }


def load_preregistration() -> JsonObject:
    preregistration: JsonObject = json.loads(
        PREREGISTRATION_PATH.read_text(encoding="utf-8")
    )
    witness_report, _ = load_witness_inputs()
    controls = sealed_controls()
    domain = preregistration.get("domain", {})
    witness = preregistration.get("witnessSelection", {})
    sealed = preregistration.get("sealedControls", {})
    capture = preregistration.get("captureLayout", {})
    if (
        sha256_path(PREREGISTRATION_PATH) != PREREGISTRATION_SHA256
        or preregistration.get("schemaVersion") != 1
        or preregistration.get("role") != ROLE
        or preregistration.get("observedAtPreregistration") is not False
        or domain.get("caseCount") != witness_map.MANTISSA_COUNT
        or domain.get("oppositeEdge") != witness_map.OPPOSITE_EDGE
        or domain.get("reciprocalCandidateNumerator")
        != witness_map.RECIPROCAL_NUMERATOR
        or witness.get("reportSha256") != WITNESS_REPORT_SHA256
        or witness.get("mapSha256") != WITNESS_INDEX_SHA256
        or witness.get("candidateSlopePairSha256")
        != witness_report.get("candidateSlopePairSha256")
        or sealed.get("canonicalIntegerWidthCount") != len(controls["canonical"])
        or sealed.get("generalHeightPairCount")
        != len(controls["generalValues"])
        or sealed.get("combinedUniqueControlCount") != len(controls["combined"])
        or capture.get("targetWidth") != TARGET_WIDTH
        or capture.get("targetHeight") != TARGET_HEIGHT
        or capture.get("viewportWidth") != VIEWPORT_WIDTH
        or capture.get("originY") != ORIGIN_Y
        or capture.get("sampleXs") != list(witness_map.SAMPLE_XS)
        or capture.get("recordBytes") != RECORD.size
        or capture.get("rawBytes") != witness_report.get("rawBytes")
        or capture.get("batchCaseCount") != BATCH_CASE_COUNT
    ):
        raise ValueError("fractional selector preregistration differs")
    return preregistration


def validate_manifest(root: Path) -> tuple[JsonObject, Path]:
    manifest_path = root / "manifest.json"
    manifest: JsonObject = json.loads(manifest_path.read_text(encoding="utf-8"))
    evidence = manifest.get("rasterFractionalSelectorSweep", {})
    raw_path = root / str(evidence.get("file", ""))
    witness_report, _ = load_witness_inputs()
    if (
        manifest.get("schemaVersion") != SCHEMA_VERSION
        or manifest.get("rigVersion") != RIG_VERSION
        or not isinstance(manifest.get("ciCommit"), str)
        or len(str(manifest.get("ciCommit"))) != 40
        or evidence.get("role") != ROLE
        or evidence.get("preregistrationSha256") != PREREGISTRATION_SHA256
        or evidence.get("witnessMapSha256") != WITNESS_INDEX_SHA256
        or evidence.get("witnessPoolSha256")
        != witness_report.get("witnessSignificandsSha256")
        or evidence.get("caseCount") != witness_map.MANTISSA_COUNT
        or evidence.get("targetWidth") != TARGET_WIDTH
        or evidence.get("targetHeight") != TARGET_HEIGHT
        or evidence.get("viewportWidth") != VIEWPORT_WIDTH
        or evidence.get("originY") != ORIGIN_Y
        or evidence.get("oppositeEdge") != witness_map.OPPOSITE_EDGE
        or evidence.get("sampleXs") != list(witness_map.SAMPLE_XS)
        or evidence.get("batchCaseCount") != BATCH_CASE_COUNT
        or evidence.get("recordBytes") != RECORD.size
        or evidence.get("bytes") != witness_report.get("rawBytes")
        or not raw_path.is_file()
        or raw_path.stat().st_size != witness_report.get("rawBytes")
        or evidence.get("sha256") != sha256_path(raw_path)
    ):
        raise ValueError("fractional selector manifest differs")
    return manifest, raw_path


def candidate_tables(indices: bytes) -> tuple[np.ndarray, ...]:
    normalized_inputs = np.arange(
        witness_map.NORMALIZED_INPUT_LOWER,
        1 << 24,
        dtype=np.uint64,
    )
    lower_reciprocals = (
        np.uint64(witness_map.RECIPROCAL_NUMERATOR) // normalized_inputs
    )
    remainders = (
        np.uint64(witness_map.RECIPROCAL_NUMERATOR) % normalized_inputs
    )
    lower_reciprocals[0] = 1 << 24
    remainders[0] = 0
    upper_reciprocals = lower_reciprocals + (remainders != 0)
    assignments = np.frombuffer(indices, dtype=np.uint8)
    lower_slopes = np.empty(witness_map.MANTISSA_COUNT, dtype=np.uint32)
    upper_slopes = np.empty(witness_map.MANTISSA_COUNT, dtype=np.uint32)
    witnesses = witness_map.witness_significands()
    for witness_index in np.unique(assignments):
        selected = np.flatnonzero(assignments == witness_index)
        numerator_index, numerator_exponent = witness_map.first_stage(
            witnesses[int(witness_index)]
        )
        lower_slopes[selected] = witness_map.vector_slope_bits(
            lower_reciprocals[selected],
            numerator_index=numerator_index,
            numerator_lsb_exponent=numerator_exponent,
        )
        upper_slopes[selected] = witness_map.vector_slope_bits(
            upper_reciprocals[selected],
            numerator_index=numerator_index,
            numerator_lsb_exponent=numerator_exponent,
        )
    slope_pairs = np.column_stack((lower_slopes, upper_slopes))
    if sha256_bytes(slope_pairs.astype("<u4", copy=False).tobytes()) != (
        "785738882867b59709bfe125f8e32c1d9fc9d7debec8cef94d848dfe3b08a20f"
    ):
        raise ValueError("fractional selector candidate slopes differ")
    return (
        normalized_inputs,
        lower_reciprocals,
        upper_reciprocals,
        remainders,
        lower_slopes,
        upper_slopes,
    )


def accepts_candidate(
    observations: np.ndarray,
    slope_bits: np.ndarray,
) -> np.ndarray:
    constants = observations[:, 0].view(np.float32).astype(np.float64)
    slopes = slope_bits.view(np.float32).astype(np.float64)
    accepted = np.ones(len(slope_bits), dtype=np.bool_)
    for slot, position in enumerate(witness_map.SAMPLE_OFFSETS):
        predicted = (position * slopes + constants).astype(np.float32).view(
            np.uint32
        )
        accepted &= predicted == observations[:, slot]
    return accepted


def failure_records(
    failures: np.ndarray,
    *,
    observations: np.ndarray,
    assignments: np.ndarray,
    lower_reciprocals: np.ndarray,
    upper_reciprocals: np.ndarray,
    lower_slopes: np.ndarray,
    upper_slopes: np.ndarray,
    lower_accepted: np.ndarray,
    upper_accepted: np.ndarray,
) -> list[JsonObject]:
    result: list[JsonObject] = []
    for mantissa in failures[:32].tolist():
        result.append(
            {
                "mantissa": mantissa,
                "widthBits": f"0x{0x4600_0000 + mantissa:08x}",
                "witnessIndex": int(assignments[mantissa]),
                "candidateReciprocals": [
                    int(lower_reciprocals[mantissa]),
                    int(upper_reciprocals[mantissa]),
                ],
                "candidateSlopeBits": [
                    f"0x{int(lower_slopes[mantissa]):08x}",
                    f"0x{int(upper_slopes[mantissa]):08x}",
                ],
                "candidateAccepted": [
                    bool(lower_accepted[mantissa]),
                    bool(upper_accepted[mantissa]),
                ],
                "observationBits": [
                    f"0x{int(value):08x}"
                    for value in observations[mantissa].tolist()
                ],
            }
        )
    return result


def validate(root: Path) -> tuple[bytes, JsonObject]:
    load_preregistration()
    controls = sealed_controls()
    manifest, raw_path = validate_manifest(root)
    _, index_bytes = load_witness_inputs()
    assignments = np.frombuffer(index_bytes, dtype=np.uint8)
    (
        normalized_inputs,
        lower_reciprocals,
        upper_reciprocals,
        remainders,
        lower_slopes,
        upper_slopes,
    ) = candidate_tables(index_bytes)
    records = np.memmap(raw_path, mode="r", dtype="<u4").reshape(
        witness_map.MANTISSA_COUNT,
        len(witness_map.SAMPLE_XS),
        2,
    )
    observations = records.reshape(witness_map.MANTISSA_COUNT, -1)
    finite = (observations & 0x7F80_0000) != 0x7F80_0000
    all_records_finite = bool(np.all(finite))
    missing_record_count = int(
        np.count_nonzero(np.all(records == 0xFFFF_FFFF, axis=2))
    )
    lower_accepted = accepts_candidate(observations, lower_slopes)
    upper_accepted = accepts_candidate(observations, upper_slopes)
    upper_accepted[0] = False
    multiplicity = lower_accepted.astype(np.uint8) + upper_accepted.astype(np.uint8)
    valid_selector = multiplicity == 1
    selected = np.full(
        witness_map.MANTISSA_COUNT,
        AMBIGUOUS_SELECTOR,
        dtype=np.uint32,
    )
    selected[lower_accepted] = lower_reciprocals[lower_accepted].astype(np.uint32)
    selected[upper_accepted] = upper_reciprocals[upper_accepted].astype(np.uint32)
    selected_slopes = np.full_like(selected, AMBIGUOUS_SELECTOR)
    selected_slopes[lower_accepted] = lower_slopes[lower_accepted]
    selected_slopes[upper_accepted] = upper_slopes[upper_accepted]

    canonical_actual = selected[::1_024]
    canonical_expected = np.asarray(controls["canonical"], dtype=np.uint32)
    canonical_match_count = int(
        np.count_nonzero(canonical_actual == canonical_expected)
    )
    general_match_count = 0
    for case_index, expected in enumerate(controls["generalValues"]):
        width_index, height_index = divmod(
            case_index,
            general_selector.HEIGHT_COUNT,
        )
        determinant = (
            general_selector.WIDTHS[width_index]
            * general_selector.HEIGHTS[height_index]
        )
        general_match_count += int(
            selected[general_mantissa_index(determinant)] == expected
        )

    exact_nearest = lower_reciprocals + (
        (2 * remainders > normalized_inputs)
        | (
            (2 * remainders == normalized_inputs)
            & ((lower_reciprocals & 1) == 1)
        )
    )
    valid_selected = selected[valid_selector].astype(np.int64)
    endpoints = Counter(
        (
            valid_selected
            - lower_reciprocals[valid_selector].astype(np.int64)
        ).tolist()
    )
    nearest_offsets = Counter(
        (
            valid_selected
            - exact_nearest[valid_selector].astype(np.int64)
        ).tolist()
    )
    failures = np.flatnonzero(~valid_selector)
    selector_bytes = selected.astype("<u4", copy=False).tobytes()
    selector_gate = bool(np.all(valid_selector))
    sealed_gate = (
        canonical_match_count == 8_192 and general_match_count == 32_768
    )
    valid = (
        all_records_finite
        and missing_record_count == 0
        and selector_gate
        and sealed_gate
    )
    report: JsonObject = {
        "liquidGlassRasterFractionalSelectorValidationSchemaVersion": 1,
        "classification": ROLE,
        "probe": str(root),
        "ciCommit": manifest.get("ciCommit"),
        "manifestSha256": sha256_path(root / "manifest.json"),
        "rawSha256": sha256_path(raw_path),
        "preregistrationSha256": PREREGISTRATION_SHA256,
        "measurement": {
            "mantissaCount": witness_map.MANTISSA_COUNT,
            "allRecordsFinite": all_records_finite,
            "missingRecordCount": missing_record_count,
            "selectorCandidateMultiplicity": counter_json(
                Counter(multiplicity.tolist())
            ),
            "resolvedSelectorEndpointFromFloorDistribution": counter_json(
                endpoints
            ),
            "resolvedSelectorOffsetFromNearestDistribution": counter_json(
                nearest_offsets
            ),
            "resolvedSelectorTableSha256": sha256_bytes(selector_bytes),
            "resolvedSlopeTableSha256": sha256_bytes(
                selected_slopes.astype("<u4", copy=False).tobytes()
            ),
            "canonicalIntegerWidthExactMatchCount": canonical_match_count,
            "canonicalIntegerWidthCount": 8_192,
            "generalHeightExactMatchCount": general_match_count,
            "generalHeightCount": 32_768,
            "sealedControlGate": sealed_gate,
            "exhaustiveSelectorGate": selector_gate,
            "captureValidForComparison": valid,
            "firstFailures": failure_records(
                failures,
                observations=observations,
                assignments=assignments,
                lower_reciprocals=lower_reciprocals,
                upper_reciprocals=upper_reciprocals,
                lower_slopes=lower_slopes,
                upper_slopes=upper_slopes,
                lower_accepted=lower_accepted,
                upper_accepted=upper_accepted,
            ),
        },
        "conclusions": {
            "twoStageArithmeticTransferredToFractionalWidths": selector_gate,
            "priorSelectorCorporaTransferredExactly": sealed_gate,
            "positiveNormalMantissaSelectorDomainComplete": valid,
            "portableClosedFormSelectorLawEstablished": False,
            "clippedSetupEstablished": False,
            "endToEndLiquidGlassParityEstablished": False,
        },
    }
    return selector_bytes, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--selector-output", type=Path)
    arguments = parser.parse_args()
    selectors, report = validate(arguments.root)
    if arguments.selector_output is not None:
        arguments.selector_output.write_bytes(zlib.compress(selectors, level=9))
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    raise SystemExit(
        0 if report["measurement"]["captureValidForComparison"] else 1
    )


if __name__ == "__main__":
    main()
