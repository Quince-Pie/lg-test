#!/usr/bin/env python3
"""Recover exact slopes from the matched-factorization Apple capture."""

import argparse
import hashlib
import json
import struct
import zlib
from collections import Counter
from pathlib import Path
from typing import Any

import model_raster_general_height_arithmetic as two_stage
import validate_raster_general_height_factorization as factorization


type JsonObject = dict[str, Any]

OFFSET = struct.Struct("<b")


def recover(root: Path) -> tuple[bytes, JsonObject]:
    manifest, raw_path = factorization.validate_manifest(root)
    data = raw_path.read_bytes()
    cases = factorization.capture_cases()
    deltas = factorization.all_delta_bits()
    positions = tuple(
        position
        for x in factorization.SAMPLE_TILE_LOCAL_XS
        for position in (float(x), float(x) + 0.9375)
    )
    offsets = bytearray()
    multiplicity: Counter[int] = Counter()
    distribution: Counter[int] = Counter()
    slope_digest = hashlib.sha256()
    first_failures: list[JsonObject] = []
    model_matches: Counter[int] = Counter()
    model_errors: dict[int, Counter[int]] = {
        bias: Counter() for bias in two_stage.FIRST_STAGE_BIAS_UNITS
    }
    model_digests = {
        bias: hashlib.sha256() for bias in two_stage.FIRST_STAGE_BIAS_UNITS
    }
    bases = factorization.base_cases()
    canonical = factorization.low_exponent.factorized.canonical_reciprocals()

    for case_index, capture_case in enumerate(cases):
        width = int(capture_case["width"])
        for input_index in range(factorization.INPUT_COUNT):
            delta_bits = deltas[case_index * factorization.INPUT_COUNT + input_index]
            delta = factorization.top_left.arithmetic.float32_value(delta_bits)
            direct_bits = factorization.top_left.arithmetic.float32_bits(delta / width)
            record_offset = (
                (case_index * factorization.INPUT_COUNT + input_index)
                * factorization.SAMPLE_POSITION_COUNT
                * factorization.RECORD.size
            )
            records = [
                factorization.RECORD.unpack_from(
                    data,
                    record_offset
                    + sample_index * factorization.RECORD.size,
                )
                for sample_index in range(factorization.SAMPLE_POSITION_COUNT)
            ]
            expected = tuple(component for record in records for component in record)
            constant_bits = expected[0]
            constant = factorization.top_left.arithmetic.float32_value(constant_bits)
            accepted: list[int] = []
            for candidate_offset in range(
                -factorization.CANDIDATE_RADIUS,
                factorization.CANDIDATE_RADIUS + 1,
            ):
                slope_bits = direct_bits + candidate_offset
                slope = factorization.top_left.arithmetic.float32_value(slope_bits)
                if all(
                    factorization.top_left.arithmetic.float32_bits(
                        position * slope + constant
                    )
                    == observation
                    for position, observation in zip(positions, expected, strict=True)
                ):
                    accepted.append(slope_bits)
            multiplicity[len(accepted)] += 1
            if len(accepted) != 1:
                if len(first_failures) < 32:
                    first_failures.append(
                        {
                            "caseIndex": case_index,
                            "inputIndex": input_index,
                            "acceptedOffsets": [
                                slope_bits - direct_bits for slope_bits in accepted
                            ],
                        }
                    )
                offsets.extend(OFFSET.pack(-128))
                slope_digest.update(struct.pack("<I", 0xFFFF_FFFF))
                continue
            slope_bits = accepted[0]
            offset = slope_bits - direct_bits
            offsets.extend(OFFSET.pack(offset))
            slope_digest.update(struct.pack("<I", slope_bits))
            distribution[offset] += 1
            base = bases[int(capture_case["baseIndex"])]
            reciprocal = canonical[int(base["normalizedWidth"]) - 8_192]
            for bias in two_stage.FIRST_STAGE_BIAS_UNITS:
                predicted = two_stage.slope_bits(
                    delta_bits,
                    opposite_edge=int(capture_case["height"]),
                    determinant=int(capture_case["area"]),
                    reciprocal_index=reciprocal,
                    first_stage_bias_units=bias,
                )
                model_matches[bias] += predicted == slope_bits
                model_errors[bias][predicted - slope_bits] += 1
                model_digests[bias].update(struct.pack("<I", predicted))

    report: JsonObject = {
        "ciCommit": manifest.get("ciCommit"),
        "rawSha256": factorization.sha256_path(raw_path),
        "coefficientCount": factorization.CASE_COUNT * factorization.INPUT_COUNT,
        "candidateMultiplicity": {
            str(key): value for key, value in sorted(multiplicity.items())
        },
        "directDivisionOffsetDistribution": {
            str(key): value for key, value in sorted(distribution.items())
        },
        "recoveredSlopeTableSha256": slope_digest.hexdigest(),
        "offsetBytes": len(offsets),
        "offsetSha256": hashlib.sha256(offsets).hexdigest(),
        "twoStage27Model": {
            "firstStageBiasEquivalenceClass": list(
                two_stage.FIRST_STAGE_BIAS_UNITS
            ),
            "matchesByFirstStageBias": {
                str(bias): model_matches[bias]
                for bias in two_stage.FIRST_STAGE_BIAS_UNITS
            },
            "errorFloatUlpDistributionByFirstStageBias": {
                str(bias): {
                    str(error): count
                    for error, count in sorted(model_errors[bias].items())
                }
                for bias in two_stage.FIRST_STAGE_BIAS_UNITS
            },
            "predictedSlopeTableSha256ByFirstStageBias": {
                str(bias): model_digests[bias].hexdigest()
                for bias in two_stage.FIRST_STAGE_BIAS_UNITS
            },
        },
        "firstFailures": first_failures,
    }
    return bytes(offsets), report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    arguments = parser.parse_args()
    offsets, report = recover(arguments.root)
    compressed = zlib.compress(offsets, level=9)
    report["compressedBytes"] = len(compressed)
    report["compressedSha256"] = hashlib.sha256(compressed).hexdigest()
    if arguments.output is not None:
        arguments.output.write_bytes(compressed)
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.report is not None:
        arguments.report.write_text(serialized, encoding="utf-8")
    print(serialized, end="")


if __name__ == "__main__":
    main()
