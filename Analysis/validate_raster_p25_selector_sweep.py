#!/usr/bin/env python3
"""Validate and materialize the exhaustive normalized-P25 selector sweep."""

import argparse
import hashlib
import json
import re
import struct
import zlib
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np

import generate_raster_p25_selector_witnesses as witness
import validate_raster_near_square_selector_sweep as near_square


type JsonObject = dict[str, Any]

SCHEMA_VERSION = 1
RIG_VERSION = "metal-raster-p25-selector-sweep-1.0.0"
ROLE = (
    "prospective-exhaustive-normalized-p25-fixed-grid-reciprocal-selector-calibration"
)
PREREGISTRATION = Path(__file__).with_name(
    "raster_p25_selector_sweep_preregistration.json"
)
PREREGISTRATION_REPOSITORY_PATH = (
    "Analysis/raster_p25_selector_sweep_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "5ca58f828876270cbe9a7f269269d8a9b1ce247775bb09c0d86f4c49b44503b2"
)
PREFLIGHT = Path(__file__).with_name(
    "raster_p25_selector_witness_preflight.json"
)
PREFLIGHT_SHA256 = (
    "b3674247ebc7c92f024f1b09dbd50cecee10851b6d672f7d63c6031823464ebd"
)
CASE_GENERATOR = Path(__file__).with_name("generate_raster_p25_selector_cases.py")
CASE_GENERATOR_SHA256 = (
    "c60bb59c0ce94552b0c448f57f906621ffe7f7e1b28b3e727057bbe7682590f2"
)
WITNESS_GENERATOR = Path(__file__).with_name(
    "generate_raster_p25_selector_witnesses.py"
)
WITNESS_GENERATOR_SHA256 = (
    "5d8b4fa592520c8a3c110b6313e5825075fa8aaef61a8bd302130b5e31931760"
)
CASE_REPOSITORY_PATH = "Analysis/raster_p25_selector_cases_u32le.bin"
RAW_FILE = "raster-p25-selector-sweep.raw"
SELECTOR_BITS_FILE = "raster-p25-selector-ceil-bits.bin"
SELECTOR_BITS_ARCHIVE = "raster-p25-selector-ceil-bits.zlib"
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")

SMALL_SQUARE_ARCHIVE = Path(__file__).with_name(
    "raster_small_square_selectors_u32le.zlib"
)
SMALL_SQUARE_ARCHIVE_SHA256 = (
    "4a701a9868484ec6580026b6328ac99ec38d14d1d4747cd2066964e46498989e"
)
SMALL_SQUARE_RAW_SHA256 = (
    "9cb148ec4996e77243c397c97f01163ea0a08502239adc8aeecd3e8e64fe6d10"
)
SMALL_SQUARE_WIDTH_LOWER = 114_688
SMALL_SQUARE_WIDTH_UPPER = 147_456

SMALL_NEAR_SQUARE_ARCHIVE = Path(__file__).with_name(
    "raster_small_near_square_selectors_u32le.zlib"
)
SMALL_NEAR_SQUARE_ARCHIVE_SHA256 = (
    "7d0f0743a894c47518139456d5e7d9d805526126f760650239babde35388bba6"
)
SMALL_NEAR_SQUARE_RAW_SHA256 = (
    "424fd9e815520c1f6f77840a6b976bf41d2907aecb1d4c82d1ea43fbc152633f"
)

NATURAL_CASES = Path(__file__).with_name(
    "raster_natural_shadow_selector_cases_u32le.bin"
)
NATURAL_CASES_SHA256 = (
    "94a4e83307b5b5ba0020fb7ff6f4838acde2f959a9d3a8a2d6bf250af1a6893d"
)
NATURAL_SELECTOR_ARCHIVE = Path(__file__).with_name(
    "raster_natural_shadow_selectors_u32le.zlib"
)
NATURAL_SELECTOR_ARCHIVE_SHA256 = (
    "b063a9a84afb062a8f54e006dac387f0c65c09cfc003405d7fa69218969e922d"
)
NATURAL_SELECTOR_RAW_SHA256 = (
    "90edc4baf626f8a6b90aa3a874465f3a004d9c8a8cbeac282663d24161aa8ef8"
)
CONTROL_PAIR_SHA256 = (
    "05894bd31f6ebceacd27369f4d984543d32e155484de13c505c9abfee1ce67bf"
)
CONTROL_CASE_COUNT = 761_872
CONTROL_UNIQUE_KEY_COUNT = 278_412


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> JsonObject:
    return json.loads(path.read_text(encoding="utf-8"))


def load_preregistered_inputs() -> tuple[JsonObject, JsonObject]:
    preregistration = load_json(PREREGISTRATION)
    preflight = load_json(PREFLIGHT)
    capture = preregistration.get("capture", {})
    domain = preregistration.get("finiteDomain", {})
    frozen_preflight = preregistration.get("witnessPreflight", {})
    if (
        sha256_path(PREREGISTRATION) != PREREGISTRATION_SHA256
        or sha256_path(PREFLIGHT) != PREFLIGHT_SHA256
        or sha256_path(CASE_GENERATOR) != CASE_GENERATOR_SHA256
        or sha256_path(WITNESS_GENERATOR) != WITNESS_GENERATOR_SHA256
        or preregistration.get("schemaVersion") != SCHEMA_VERSION
        or preregistration.get("role") != ROLE
        or preregistration.get("observedAtPreregistration") is not False
        or domain.get("keyLowerInclusive") != witness.KEY_LOWER
        or domain.get("keyUpperExclusive") != witness.KEY_UPPER
        or domain.get("caseCount") != witness.KEY_COUNT
        or domain.get("caseGeneratorSha256") != CASE_GENERATOR_SHA256
        or capture.get("rigVersion") != RIG_VERSION
        or capture.get("caseFileSha256") != witness.CASE_SHA256
        or capture.get("recordCount") != witness.KEY_COUNT
        or capture.get("recordBytes") != 4
        or capture.get("rawBytes") != witness.KEY_COUNT * 4
        or frozen_preflight.get("sha256") != PREFLIGHT_SHA256
        or frozen_preflight.get("generatorSha256") != WITNESS_GENERATOR_SHA256
        or frozen_preflight.get("candidateConstantPairSha256")
        != preflight.get("witness", {}).get("candidateConstantPairSha256")
        or preflight.get("capturedAppleOutputUsed") is not False
        or preflight.get("witness", {}).get("everyNonBoundaryCandidateMultiplicity")
        != 1
    ):
        raise ValueError("normalized-P25 preregistration differs")
    return preregistration, preflight


def validate_manifest(
    root: Path,
    *,
    expected_commit: str,
) -> tuple[JsonObject, Path]:
    if COMMIT_PATTERN.fullmatch(expected_commit) is None:
        raise ValueError("expected capture commit is not a full SHA-1")
    manifest_path = root / "manifest.json"
    manifest = load_json(manifest_path)
    evidence = manifest.get("rasterP25SelectorSweep", {})
    device = manifest.get("device", {})
    compile_record = manifest.get("compile", {})
    raw_path = root / RAW_FILE
    if (
        manifest.get("schemaVersion") != SCHEMA_VERSION
        or manifest.get("rigVersion") != RIG_VERSION
        or manifest.get("ciCommit") != expected_commit
        or not isinstance(device, dict)
        or device.get("name") != "Apple M1 Max"
        or not isinstance(compile_record, dict)
        or compile_record.get("fastMathEnabled") is not True
        or compile_record.get("interpolation") != "perspective"
        or compile_record.get("boundedBatchOutputBytes")
        != witness.BATCH_CASE_COUNT * 4
        or not isinstance(evidence, dict)
        or evidence.get("role") != ROLE
        or evidence.get("preregistrationFile")
        != PREREGISTRATION_REPOSITORY_PATH
        or evidence.get("preregistrationSha256") != PREREGISTRATION_SHA256
        or evidence.get("caseFile") != CASE_REPOSITORY_PATH
        or evidence.get("caseSha256") != witness.CASE_SHA256
        or evidence.get("caseCount") != witness.KEY_COUNT
        or evidence.get("keyLowerInclusive") != witness.KEY_LOWER
        or evidence.get("keyUpperExclusive") != witness.KEY_UPPER
        or evidence.get("fixedUnitsPerPixel") != witness.FIXED_UNITS_PER_PIXEL
        or evidence.get("targetSize") != [1_024, 1_024]
        or evidence.get("samplePixel") != [witness.SAMPLE_X, witness.SAMPLE_Y]
        or evidence.get("pullOffset") != list(witness.PULL_OFFSET)
        or evidence.get("endpointRamp") != "[-width/2,+width/2]"
        or evidence.get("batchCaseCount") != witness.BATCH_CASE_COUNT
        or evidence.get("batchCount")
        != witness.KEY_COUNT // witness.BATCH_CASE_COUNT
        or evidence.get("ordering") != "ascending normalized-P25 key"
        or evidence.get("recordBytes") != 4
        or evidence.get("recordCount") != witness.KEY_COUNT
        or evidence.get("file") != RAW_FILE
        or evidence.get("bytes") != witness.KEY_COUNT * 4
        or not raw_path.is_file()
        or raw_path.stat().st_size != witness.KEY_COUNT * 4
        or evidence.get("sha256") != sha256_path(raw_path)
    ):
        raise ValueError("normalized-P25 selector manifest differs")
    return manifest, raw_path


def normalized_p25_key(determinant: int) -> int:
    if determinant <= 0:
        raise ValueError("determinant must be positive")
    shift = determinant.bit_length() - 1 - 24
    if shift <= 0:
        return determinant << -shift
    quotient, remainder = divmod(determinant, 1 << shift)
    return quotient + (remainder >= (1 << (shift - 1)))


def selector_candidates_for_determinant(
    determinant: int,
    key: int,
) -> tuple[int, int]:
    if determinant & (determinant - 1) == 0 or key == witness.KEY_UPPER:
        return 1 << 24, 1 << 24
    if not witness.KEY_LOWER <= key < witness.KEY_UPPER:
        raise ValueError("normalized determinant key is outside P25")
    lower = witness.RECIPROCAL_NUMERATOR // key
    upper = lower + (witness.RECIPROCAL_NUMERATOR % key != 0)
    return lower, upper


def selector_from_bitmap(determinant: int, bitmap: bytes) -> tuple[int, int, int]:
    key = normalized_p25_key(determinant)
    lower, upper = selector_candidates_for_determinant(determinant, key)
    if lower == upper:
        return key, lower, 0
    bit_index = key - witness.KEY_LOWER
    choice = (bitmap[bit_index >> 3] >> (bit_index & 7)) & 1
    return key, upper if choice else lower, choice


def load_selector_archive(
    path: Path,
    *,
    archive_sha256: str,
    raw_sha256: str,
) -> np.ndarray:
    compressed = path.read_bytes()
    raw = zlib.decompress(compressed)
    if (
        sha256_bytes(compressed) != archive_sha256
        or sha256_bytes(raw) != raw_sha256
        or len(raw) % 4
    ):
        raise ValueError(f"frozen selector archive differs: {path.name}")
    return np.frombuffer(raw, dtype="<u4")


def frozen_control_records() -> Iterable[tuple[str, int, int, int]]:
    square = load_selector_archive(
        SMALL_SQUARE_ARCHIVE,
        archive_sha256=SMALL_SQUARE_ARCHIVE_SHA256,
        raw_sha256=SMALL_SQUARE_RAW_SHA256,
    )
    expected_square_count = SMALL_SQUARE_WIDTH_UPPER - SMALL_SQUARE_WIDTH_LOWER + 1
    if len(square) != expected_square_count:
        raise ValueError("small-square control count differs")
    for index, selector in enumerate(square):
        width = SMALL_SQUARE_WIDTH_LOWER + index
        yield "small-square", width, width, int(selector)

    near = load_selector_archive(
        SMALL_NEAR_SQUARE_ARCHIVE,
        archive_sha256=SMALL_NEAR_SQUARE_ARCHIVE_SHA256,
        raw_sha256=SMALL_NEAR_SQUARE_RAW_SHA256,
    )
    expected_near_count = expected_square_count * len(near_square.HEIGHT_DELTAS)
    if len(near) != expected_near_count:
        raise ValueError("small-near-square control count differs")
    index = 0
    for height_delta in near_square.HEIGHT_DELTAS:
        for width in range(SMALL_SQUARE_WIDTH_LOWER, SMALL_SQUARE_WIDTH_UPPER + 1):
            yield "small-near-square", width, width + height_delta, int(near[index])
            index += 1

    natural_case_bytes = NATURAL_CASES.read_bytes()
    if sha256_bytes(natural_case_bytes) != NATURAL_CASES_SHA256:
        raise ValueError("natural-shadow control cases differ")
    natural_cases = np.frombuffer(natural_case_bytes, dtype="<u4").reshape(-1, 2)
    natural = load_selector_archive(
        NATURAL_SELECTOR_ARCHIVE,
        archive_sha256=NATURAL_SELECTOR_ARCHIVE_SHA256,
        raw_sha256=NATURAL_SELECTOR_RAW_SHA256,
    )
    if len(natural_cases) != len(natural) or len(natural) != 139_261:
        raise ValueError("natural-shadow control count differs")
    for (width, height), selector in zip(natural_cases, natural, strict=True):
        yield "natural-shadow", int(width), int(height), int(selector)


def validate_controls(bitmap: bytes) -> JsonObject:
    role_counts: Counter[str] = Counter()
    role_matches: Counter[str] = Counter()
    endpoint_counts: Counter[int] = Counter()
    unique: dict[int, int] = {}
    conflict_count = 0
    invalid_candidate_count = 0
    mismatch_examples: list[JsonObject] = []
    pair_digest = hashlib.sha256()
    for role, width, height, measured in frozen_control_records():
        determinant = width * height
        key = normalized_p25_key(determinant)
        lower, upper = selector_candidates_for_determinant(determinant, key)
        if measured not in (lower, upper):
            invalid_candidate_count += 1
        _, predicted, predicted_choice = selector_from_bitmap(determinant, bitmap)
        measured_choice = int(measured == upper and upper != lower)
        role_counts[role] += 1
        role_matches[role] += predicted == measured
        endpoint_counts[predicted_choice] += 1
        if key < witness.KEY_UPPER:
            prior = unique.get(key)
            conflict_count += prior is not None and prior != measured_choice
            unique[key] = measured_choice
        if predicted != measured and len(mismatch_examples) < 32:
            mismatch_examples.append(
                {
                    "role": role,
                    "widthFixed": width,
                    "heightFixed": height,
                    "key": key,
                    "measuredSelector": measured,
                    "predictedSelector": predicted,
                    "candidateSelectors": [lower, upper],
                }
            )
    for key, choice in sorted(unique.items()):
        pair_digest.update(struct.pack("<IB", key, choice))
    matched = sum(role_matches.values())
    if (
        sum(role_counts.values()) != CONTROL_CASE_COUNT
        or len(unique) != CONTROL_UNIQUE_KEY_COUNT
        or pair_digest.hexdigest() != CONTROL_PAIR_SHA256
    ):
        raise ValueError("frozen normalized-P25 control corpus differs")
    return {
        "caseCount": CONTROL_CASE_COUNT,
        "matchedCaseCount": matched,
        "mismatchedCaseCount": CONTROL_CASE_COUNT - matched,
        "invalidCandidateCount": invalid_candidate_count,
        "uniqueNormalizedKeyCount": len(unique),
        "conflictingNormalizedKeyCount": conflict_count,
        "endpointChoiceCounts": {
            str(key): value for key, value in sorted(endpoint_counts.items())
        },
        "roleCaseCounts": dict(sorted(role_counts.items())),
        "roleMatchCounts": dict(sorted(role_matches.items())),
        "keyChoicePairSha256": pair_digest.hexdigest(),
        "mismatchExamples": mismatch_examples,
        "passed": (
            matched == CONTROL_CASE_COUNT
            and invalid_candidate_count == 0
            and conflict_count == 0
            and not mismatch_examples
        ),
    }


def validate(
    root: Path,
    *,
    cases_path: Path,
    expected_commit: str,
) -> tuple[JsonObject, bytes | None, bytes | None]:
    _, preflight = load_preregistered_inputs()
    cases = witness.load_cases(cases_path)
    manifest, raw_path = validate_manifest(root, expected_commit=expected_commit)
    observations = np.memmap(raw_path, mode="r", dtype="<u4")
    bitmap = bytearray()
    reciprocal_pair_digest = hashlib.sha256()
    constant_pair_digest = hashlib.sha256()
    lower_constant_digest = hashlib.sha256()
    upper_constant_digest = hashlib.sha256()
    floor_match_count = 0
    ceil_match_count = 0
    boundary_match_count = 0
    finite_word_count = 0
    missing_record_count = 0
    zero_match_count = 0
    ambiguous_match_count = 0
    failure_examples: list[JsonObject] = []

    for start in range(0, witness.KEY_COUNT, witness.BATCH_CASE_COUNT):
        stop = min(start + witness.BATCH_CASE_COUNT, witness.KEY_COUNT)
        keys = np.arange(
            witness.KEY_LOWER + start,
            witness.KEY_LOWER + stop,
            dtype=np.uint64,
        )
        widths = np.asarray(cases[start:stop, 0], dtype=np.uint64)
        heights = np.asarray(cases[start:stop, 1], dtype=np.uint64)
        lower, upper = witness.reciprocal_candidates(keys)
        lower_bits = witness.candidate_constant_bits(widths, heights, lower)
        upper_bits = witness.candidate_constant_bits(widths, heights, upper)
        observed = np.asarray(observations[start:stop], dtype=np.uint32)
        finite = (observed & 0x7F80_0000) != 0x7F80_0000
        missing = observed == 0xFFFF_FFFF
        lower_match = observed == lower_bits
        upper_match = observed == upper_bits
        exact_boundary = lower == upper
        upper_match[exact_boundary] = False
        multiplicity = lower_match.astype(np.uint8) + upper_match.astype(np.uint8)
        invalid = multiplicity != 1
        finite_word_count += int(np.count_nonzero(finite))
        missing_record_count += int(np.count_nonzero(missing))
        zero_match_count += int(np.count_nonzero(multiplicity == 0))
        ambiguous_match_count += int(np.count_nonzero(multiplicity > 1))
        floor_match_count += int(np.count_nonzero(lower_match & (~exact_boundary)))
        ceil_match_count += int(np.count_nonzero(upper_match))
        boundary_match_count += int(np.count_nonzero(lower_match & exact_boundary))
        if np.any(invalid) and len(failure_examples) < 32:
            for local_index in np.flatnonzero(invalid)[
                : 32 - len(failure_examples)
            ]:
                failure_examples.append(
                    {
                        "key": int(keys[local_index]),
                        "widthFixed": int(widths[local_index]),
                        "heightFixed": int(heights[local_index]),
                        "observedBits": f"0x{int(observed[local_index]):08x}",
                        "candidateConstantBits": [
                            f"0x{int(lower_bits[local_index]):08x}",
                            f"0x{int(upper_bits[local_index]):08x}",
                        ],
                        "candidateReciprocals": [
                            int(lower[local_index]),
                            int(upper[local_index]),
                        ],
                        "matchMultiplicity": int(multiplicity[local_index]),
                    }
                )
        bitmap.extend(np.packbits(upper_match, bitorder="little").tobytes())
        reciprocal_pair_digest.update(
            np.column_stack((lower, upper)).astype("<u4", copy=False).tobytes()
        )
        constant_pair_digest.update(
            np.column_stack((lower_bits, upper_bits))
            .astype("<u4", copy=False)
            .tobytes()
        )
        lower_constant_digest.update(lower_bits.astype("<u4", copy=False).tobytes())
        upper_constant_digest.update(upper_bits.astype("<u4", copy=False).tobytes())

    bitmap_bytes = bytes(bitmap)
    witness_record = preflight["witness"]
    domain_record = preflight["domain"]
    candidate_streams_match = (
        reciprocal_pair_digest.hexdigest()
        == domain_record["candidateReciprocalPairSha256"]
        and constant_pair_digest.hexdigest()
        == witness_record["candidateConstantPairSha256"]
        and lower_constant_digest.hexdigest()
        == witness_record["lowerCandidateConstantSha256"]
        and upper_constant_digest.hexdigest()
        == witness_record["upperCandidateConstantSha256"]
    )
    exhaustive_opening_passed = (
        len(bitmap_bytes) == witness.KEY_COUNT // 8
        and finite_word_count == witness.KEY_COUNT
        and missing_record_count == 0
        and zero_match_count == 0
        and ambiguous_match_count == 0
        and floor_match_count + ceil_match_count == witness.KEY_COUNT - 1
        and boundary_match_count == 1
        and not failure_examples
        and candidate_streams_match
    )
    controls = validate_controls(bitmap_bytes) if exhaustive_opening_passed else None
    complete = exhaustive_opening_passed and bool(controls and controls["passed"])
    archive = zlib.compress(bitmap_bytes, level=9) if complete else None
    report: JsonObject = {
        "rasterP25SelectorValidationSchemaVersion": SCHEMA_VERSION,
        "classification": (
            "preregistered exhaustive normalized-P25 fixed-grid reciprocal "
            "selector calibration"
        ),
        "manifest": str(root / "manifest.json"),
        "captureCommit": manifest.get("ciCommit"),
        "domain": {
            "keyLowerInclusive": witness.KEY_LOWER,
            "keyUpperExclusive": witness.KEY_UPPER,
            "keyCount": witness.KEY_COUNT,
            "caseFileSha256": witness.CASE_SHA256,
        },
        "input": {
            "raw": str(raw_path),
            "rawBytes": witness.KEY_COUNT * 4,
            "rawSha256": sha256_path(raw_path),
            "finiteWordCount": finite_word_count,
            "missingRecordCount": missing_record_count,
        },
        "predeclaredRecovery": {
            "candidateReciprocalPairSha256": reciprocal_pair_digest.hexdigest(),
            "candidateConstantPairSha256": constant_pair_digest.hexdigest(),
            "candidateStreamsMatchPreregistration": candidate_streams_match,
            "floorMatchCount": floor_match_count,
            "ceilMatchCount": ceil_match_count,
            "exactPowerBoundaryMatchCount": boundary_match_count,
            "zeroMatchCount": zero_match_count,
            "ambiguousMatchCount": ambiguous_match_count,
            "failureExamples": failure_examples,
        },
        "frozenControls": controls,
        "selectorBitmap": (
            {
                "file": SELECTOR_BITS_FILE,
                "bytes": len(bitmap_bytes),
                "sha256": sha256_bytes(bitmap_bytes),
                "bitOrdering": "ascending key, least-significant bit first",
                "zeroMeaning": "floor endpoint",
                "oneMeaning": "ceil endpoint",
                "archiveFile": SELECTOR_BITS_ARCHIVE,
                "archiveBytes": len(archive),
                "archiveSha256": sha256_bytes(archive),
            }
            if complete and archive is not None
            else None
        ),
        "measurement": {
            "exhaustiveOpeningPassed": exhaustive_opening_passed,
            "frozenControlsPassed": bool(controls and controls["passed"]),
            "calibrationComplete": complete,
        },
        "gate": {
            "portableNormalizedP25SelectorEstablished": complete,
            "productionSelectorUseAuthorized": complete,
            "productionParityAuthorized": False,
            "remainingProductionGate": (
                "continuously resizing, clipped reveal/crop geometry and final "
                "physical-Retina output"
            ),
            "qualityTolerance": 0,
        },
    }
    return report, bitmap_bytes if complete else None, archive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    report, bitmap, archive = validate(
        arguments.root,
        cases_path=arguments.cases,
        expected_commit=arguments.expected_commit,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    if bitmap is not None and archive is not None:
        (arguments.output.parent / SELECTOR_BITS_FILE).write_bytes(bitmap)
        (arguments.output.parent / SELECTOR_BITS_ARCHIVE).write_bytes(archive)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["measurement"], sort_keys=True))
    return 0 if report["gate"]["portableNormalizedP25SelectorEstablished"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
