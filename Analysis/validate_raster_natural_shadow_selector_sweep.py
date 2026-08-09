#!/usr/bin/env python3
"""Validate and materialize the finite natural shadow selector sweep."""

import argparse
import hashlib
import json
import re
import struct
import zlib
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np

import generate_raster_natural_shadow_selector_witnesses as witnesses
import raster_tile_selector_model as arithmetic
import validate_raster_near_square_selector_sweep as near_square


type JsonObject = dict[str, Any]

SCHEMA_VERSION = 1
RIG_VERSION = "metal-raster-natural-shadow-selector-sweep-1.0.0"
ROLE = "finite-natural-circle480-shadow-fixed-grid-reciprocal-selector-calibration"
PREREGISTRATION = Path(__file__).with_name(
    "raster_natural_shadow_selector_sweep_preregistration.json"
)
PREREGISTRATION_REPOSITORY_PATH = (
    "Analysis/raster_natural_shadow_selector_sweep_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "05658e2229623ac241789af414899345ad21823061bf91d9ff63880e4769440a"
)
CASE_PATH = Path(__file__).with_name("raster_natural_shadow_selector_cases_u32le.bin")
CASE_REPOSITORY_PATH = "Analysis/raster_natural_shadow_selector_cases_u32le.bin"
CASE_SHA256 = "94a4e83307b5b5ba0020fb7ff6f4838acde2f959a9d3a8a2d6bf250af1a6893d"
WITNESS_PATH = Path(__file__).with_name(
    "raster_natural_shadow_selector_witness_indices_u8.bin"
)
WITNESS_REPOSITORY_PATH = (
    "Analysis/raster_natural_shadow_selector_witness_indices_u8.bin"
)
WITNESS_SHA256 = "f49b80510bc6de0baadefaf654b44f4a967bdeb7cea17ead7e9ab8017601a18f"
MULTIPLIER_PATH = Path(__file__).with_name(
    "raster_natural_shadow_selector_multiplier_bits_u32le.bin"
)
MULTIPLIER_REPOSITORY_PATH = (
    "Analysis/raster_natural_shadow_selector_multiplier_bits_u32le.bin"
)
MULTIPLIER_SHA256 = "b5e16e3ecdd55a9b816d2b8cb9dbfbea0a08910fcab362958693a71bf49d8573"
RAW_FILE = "raster-natural-shadow-selector-sweep.raw"
SELECTOR_FILE = "raster-natural-shadow-selectors-u32le.zlib"
OFFSET_FILE = "raster-natural-shadow-selector-offsets-i8.bin"
CASE_COUNT = 139_261
WITNESS_SLOT_COUNT = 8
WITNESS_POOL_COUNT = 65
SAMPLE_XS = (512, 527, 543)
SAMPLE_Y = 512
SAMPLE_POSITION_COUNT = len(SAMPLE_XS)
TARGET_SIZE = 1_024
INSTANCE_COUNT = CASE_COUNT * WITNESS_SLOT_COUNT
RECORD = struct.Struct("<2I")
RECORD_COUNT = INSTANCE_COUNT * SAMPLE_POSITION_COUNT
RAW_BYTES = RECORD_COUNT * RECORD.size
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def counter_json(counter: Counter[int]) -> JsonObject:
    return {str(key): value for key, value in sorted(counter.items())}


def load_frozen_inputs() -> tuple[np.ndarray, bytes, tuple[int, ...]]:
    case_bytes = CASE_PATH.read_bytes()
    witness_bytes = WITNESS_PATH.read_bytes()
    multiplier_bytes = MULTIPLIER_PATH.read_bytes()
    multipliers = tuple(
        value for (value,) in struct.iter_unpack("<I", multiplier_bytes)
    )
    if (
        sha256_bytes(case_bytes) != CASE_SHA256
        or len(case_bytes) != CASE_COUNT * 8
        or sha256_bytes(witness_bytes) != WITNESS_SHA256
        or len(witness_bytes) != INSTANCE_COUNT
        or sha256_bytes(multiplier_bytes) != MULTIPLIER_SHA256
        or len(multiplier_bytes) != WITNESS_POOL_COUNT * 4
        or multipliers != witnesses.multiplier_bits()
        or any(index >= WITNESS_POOL_COUNT for index in witness_bytes)
    ):
        raise ValueError("frozen natural-shadow selector inputs differ")
    cases = np.frombuffer(case_bytes, dtype="<u4").reshape(-1, 2)
    return cases, witness_bytes, multipliers


def load_preregistration() -> JsonObject:
    raw = PREREGISTRATION.read_bytes()
    preregistration: JsonObject = json.loads(raw)
    finite_domain = preregistration.get("finiteDomain", {})
    recovery = preregistration.get("predeclaredRecovery", {})
    witness = preregistration.get("inputOnlyWitnesses", {})
    capture = preregistration.get("capture", {})
    if (
        sha256_bytes(raw) != PREREGISTRATION_SHA256
        or preregistration.get("schemaVersion") != SCHEMA_VERSION
        or preregistration.get("role") != ROLE
        or preregistration.get("observedAtPreregistration") is not False
        or finite_domain.get("caseCount") != CASE_COUNT
        or finite_domain.get("caseFileSha256") != CASE_SHA256
        or recovery.get("selectorOffsetsFromExactFloor")
        != list(witnesses.RECOVERY_OFFSETS)
        or witness.get("assignmentFileSha256") != WITNESS_SHA256
        or witness.get("multiplierFileSha256") != MULTIPLIER_SHA256
        or witness.get("witnessSlotCount") != WITNESS_SLOT_COUNT
        or witness.get("samplePixels")
        != [[sample_x, SAMPLE_Y] for sample_x in SAMPLE_XS]
        or witness.get("candidateStreamSha256")
        != "fafc17687af9e87cae8cdfbee285cfef5721186d096021c24946fc4c0a07b5fb"
        or witness.get("everyCaseCandidateMultiplicity") != 1
        or capture.get("rigVersion") != RIG_VERSION
        or capture.get("recordCount") != RECORD_COUNT
        or capture.get("rawBytes") != RAW_BYTES
    ):
        raise ValueError("natural-shadow selector preregistration differs")
    return preregistration


def validate_manifest(
    root: Path,
    *,
    expected_commit: str,
) -> tuple[JsonObject, Path]:
    if COMMIT_PATTERN.fullmatch(expected_commit) is None:
        raise ValueError("expected capture commit is not a full SHA-1")
    manifest_path = root / "manifest.json"
    manifest: JsonObject = json.loads(manifest_path.read_text(encoding="utf-8"))
    evidence = manifest.get("rasterNaturalShadowSelectorSweep", {})
    device = manifest.get("device", {})
    raw_path = root / RAW_FILE
    if (
        manifest.get("schemaVersion") != SCHEMA_VERSION
        or manifest.get("rigVersion") != RIG_VERSION
        or manifest.get("ciCommit") != expected_commit
        or not isinstance(device, dict)
        or device.get("name") != "Apple M1 Max"
        or not isinstance(evidence, dict)
        or evidence.get("role") != ROLE
        or evidence.get("preregistrationFile") != PREREGISTRATION_REPOSITORY_PATH
        or evidence.get("preregistrationSha256") != PREREGISTRATION_SHA256
        or evidence.get("caseFile") != CASE_REPOSITORY_PATH
        or evidence.get("caseSha256") != CASE_SHA256
        or evidence.get("caseCount") != CASE_COUNT
        or evidence.get("witnessFile") != WITNESS_REPOSITORY_PATH
        or evidence.get("witnessSha256") != WITNESS_SHA256
        or evidence.get("witnessSlotCount") != WITNESS_SLOT_COUNT
        or evidence.get("multiplierFile") != MULTIPLIER_REPOSITORY_PATH
        or evidence.get("multiplierSha256") != MULTIPLIER_SHA256
        or evidence.get("witnessPoolCount") != WITNESS_POOL_COUNT
        or evidence.get("fixedUnitsPerPixel") != 256
        or evidence.get("targetSize") != [TARGET_SIZE, TARGET_SIZE]
        or evidence.get("samplePixels")
        != [[sample_x, SAMPLE_Y] for sample_x in SAMPLE_XS]
        or evidence.get("pullOffsets") != [[0.0, 0.5], [0.9375, 0.5]]
        or evidence.get("ordering")
        != "case-major,witness-slot-minor,sample-position-minor"
        or evidence.get("instanceCountPerSample") != INSTANCE_COUNT
        or evidence.get("coverage") != [INSTANCE_COUNT] * SAMPLE_POSITION_COUNT
        or evidence.get("recordBytes") != RECORD.size
        or evidence.get("recordCount") != RECORD_COUNT
        or evidence.get("file") != RAW_FILE
        or evidence.get("bytes") != RAW_BYTES
        or not raw_path.is_file()
        or raw_path.stat().st_size != RAW_BYTES
        or evidence.get("sha256") != sha256_path(raw_path)
    ):
        raise ValueError("natural-shadow selector manifest differs")
    return manifest, raw_path


def normalized_fallback_selector(
    width_fixed: int,
    height_fixed: int,
    table: tuple[int, ...],
) -> int:
    determinant = width_fixed * height_fixed
    exponent = determinant.bit_length() - 1
    if exponent <= 23:
        normalized = determinant << (23 - exponent)
    else:
        normalized = arithmetic.round_fraction_to_integer_nearest_even(
            Fraction(determinant, 1 << (exponent - 23))
        )
    if normalized == 1 << 24:
        normalized >>= 1
    mantissa = normalized - (1 << 23)
    index = (mantissa + 2) // 4
    return table[index]


def validate(
    root: Path,
    *,
    expected_commit: str,
) -> tuple[JsonObject, bytes | None, bytes | None]:
    preregistration = load_preregistration()
    cases, assignment_bytes, multipliers = load_frozen_inputs()
    manifest, raw_path = validate_manifest(
        root,
        expected_commit=expected_commit,
    )
    records = np.memmap(raw_path, mode="r", dtype="<u4").reshape(
        CASE_COUNT,
        WITNESS_SLOT_COUNT,
        SAMPLE_POSITION_COUNT,
        2,
    )
    finite = (records & 0x7F80_0000) != 0x7F80_0000
    finite_word_count = int(np.count_nonzero(finite))
    missing_record_count = int(np.count_nonzero(np.all(records == 0xFFFF_FFFF, axis=3)))
    assignments = np.frombuffer(assignment_bytes, dtype=np.uint8).reshape(
        CASE_COUNT,
        WITNESS_SLOT_COUNT,
    )
    selector_table = arithmetic.load_selector_table()
    candidate_digest = hashlib.sha256()
    selectors: list[int] = []
    offsets: list[int] = []
    offset_counts: Counter[int] = Counter()
    floor_match_count = 0
    fallback_match_count = 0
    ambiguous_case_count = 0
    failures: list[JsonObject] = []
    for case_index, (width_value, height_value) in enumerate(cases):
        width_fixed = int(width_value)
        height_fixed = int(height_value)
        case_assignments = assignments[case_index]
        predictions: dict[int, tuple[tuple[int, ...], ...]] = {}
        for witness_index in set(map(int, case_assignments)):
            predictions[witness_index] = witnesses.candidate_records(
                width_fixed,
                height_fixed,
                multipliers[witness_index],
            )
        for slot, witness_index_value in enumerate(case_assignments):
            witness_index = int(witness_index_value)
            for candidate in predictions[witness_index]:
                for position in range(SAMPLE_POSITION_COUNT):
                    start = position * 2
                    candidate_digest.update(RECORD.pack(*candidate[start : start + 2]))
        observed = records[case_index].reshape(WITNESS_SLOT_COUNT, -1)
        matches: list[int] = []
        for candidate_index, offset in enumerate(witnesses.RECOVERY_OFFSETS):
            if all(
                np.array_equal(
                    observed[slot],
                    predictions[int(witness_index)][candidate_index],
                )
                for slot, witness_index in enumerate(case_assignments)
            ):
                matches.append(offset)
        floor = near_square.exact_floor_selector(width_fixed, height_fixed)
        fallback = normalized_fallback_selector(
            width_fixed,
            height_fixed,
            selector_table,
        )
        if len(matches) == 1:
            offset = matches[0]
            selector = floor + offset
            selectors.append(selector)
            offsets.append(offset)
            offset_counts[offset] += 1
            floor_match_count += offset == 0
            fallback_match_count += selector == fallback
            continue
        ambiguous_case_count += len(matches) > 1
        if len(failures) < 32:
            failures.append(
                {
                    "caseIndex": case_index,
                    "widthFixed": width_fixed,
                    "heightFixed": height_fixed,
                    "matchingOffsets": matches,
                    "witnessIndices": list(map(int, case_assignments)),
                    "observed": [
                        [f"0x{int(word):08x}" for word in row] for row in observed
                    ],
                }
            )

    candidate_stream_sha256 = candidate_digest.hexdigest()
    expected_candidate_sha256 = preregistration["inputOnlyWitnesses"][
        "candidateStreamSha256"
    ]
    if candidate_stream_sha256 != expected_candidate_sha256:
        raise ValueError("natural-shadow selector candidate stream differs")
    complete = (
        len(selectors) == CASE_COUNT
        and not failures
        and ambiguous_case_count == 0
        and missing_record_count == 0
        and finite_word_count == RECORD_COUNT * 2
    )
    selector_raw = struct.pack(f"<{len(selectors)}I", *selectors) if complete else None
    offset_raw = struct.pack(f"<{len(offsets)}b", *offsets) if complete else None
    selector_archive = (
        zlib.compress(selector_raw, level=9) if selector_raw is not None else None
    )
    report: JsonObject = {
        "rasterNaturalShadowSelectorValidationSchemaVersion": 1,
        "classification": (
            "preregistered finite natural shadow calibration; not a portable "
            "reciprocal-selector law"
        ),
        "manifest": str(root / "manifest.json"),
        "captureCommit": manifest.get("ciCommit"),
        "domain": {
            "caseCount": CASE_COUNT,
            "fixedUnitsPerPixel": 256,
            "caseFileSha256": CASE_SHA256,
        },
        "input": {
            "raw": str(raw_path),
            "rawBytes": RAW_BYTES,
            "rawSha256": sha256_path(raw_path),
            "recordCount": RECORD_COUNT,
            "finiteWordCount": finite_word_count,
            "missingRecordCount": missing_record_count,
        },
        "predeclaredRecovery": {
            "selectorOffsetsFromExactFloor": list(witnesses.RECOVERY_OFFSETS),
            "candidateStreamSha256": candidate_stream_sha256,
            "matchedCaseCount": len(selectors),
            "mismatchedCaseCount": CASE_COUNT - len(selectors),
            "ambiguousCaseCount": ambiguous_case_count,
            "selectorOffsetCounts": counter_json(offset_counts),
            "failureExamples": failures,
        },
        "controls": {
            "exactFloorMatchCount": floor_match_count,
            "exactFloorMismatchCount": CASE_COUNT - floor_match_count,
            "normalizedFallbackMatchCount": fallback_match_count,
            "normalizedFallbackMismatchCount": CASE_COUNT - fallback_match_count,
        },
        "selectors": (
            {
                "file": SELECTOR_FILE,
                "rawBytes": len(selector_raw),
                "rawSha256": sha256_bytes(selector_raw),
                "compressedBytes": len(selector_archive),
                "compressedSha256": sha256_bytes(selector_archive),
                "dtype": "little-endian uint32",
                "ordering": "ascending widthFixed,heightFixed",
                "offsetFile": OFFSET_FILE,
                "offsetBytes": len(offset_raw),
                "offsetSha256": sha256_bytes(offset_raw),
                "offsetDtype": "signed int8 relative to exact floor",
            }
            if selector_raw is not None
            and selector_archive is not None
            and offset_raw is not None
            else None
        ),
        "measurement": {
            "caseCount": CASE_COUNT,
            "matchedCaseCount": len(selectors),
            "mismatchedCaseCount": CASE_COUNT - len(selectors),
            "ambiguousCaseCount": ambiguous_case_count,
            "calibrationComplete": complete,
        },
        "gate": {
            "calibrationComplete": complete,
            "portableClosedFormEstablished": False,
            "prospectiveNaturalHoldoutPassed": False,
            "productionParityAuthorized": False,
            "qualityTolerance": 0,
        },
    }
    return report, selector_archive, offset_raw


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    report, selectors, offsets = validate(
        arguments.root,
        expected_commit=arguments.expected_commit,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    if selectors is not None and offsets is not None:
        (arguments.output.parent / SELECTOR_FILE).write_bytes(selectors)
        (arguments.output.parent / OFFSET_FILE).write_bytes(offsets)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["measurement"], sort_keys=True))
    return 0 if report["gate"]["calibrationComplete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
