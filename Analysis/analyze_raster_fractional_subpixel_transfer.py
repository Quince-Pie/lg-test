#!/usr/bin/env python3
"""Resolve fractional-width selectors after measured raster-grid snapping."""

import argparse
import hashlib
import json
import zlib
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

import build_raster_fractional_selector_witness_map as witness_map
import validate_raster_fractional_selector_sweep as sweep


type JsonObject = dict[str, Any]

CI_RUN_ID = 30_672_604_597
CI_COMMIT = "0bee7c342ad3c3ab85a0d9ccb98df7f3867de0af"
MANIFEST_SHA256 = "c96f6f295dc3924b35462483f34cbe68401d5d28db67c1f683f8d10afcfcd9f9"
RAW_SHA256 = "254b4d81c29a462c19193bee6491566ecb0662f747269003d28adc1faaea283e"
SELECTOR_TABLE_SHA256 = (
    "b0990c2ce17fff5ebf06124497a38d38c9cf22e7e9210ccb6f95adb2c6834d53"
)
SELECTOR_COMPRESSED_SHA256 = (
    "2b49309da4283726cc894f7aada3c25db41cf8ca71a4c278c952407e9e1eedd3"
)
CASE_SLOPE_TABLE_SHA256 = (
    "c31c0618ed4bc26c4dc8d482f452b25db3b879f2e2e4f00cc0a82e6fe4160567"
)
SCHEMA_VERSION = 1
ROLE = "post-capture-exhaustive-fractional-width-subpixel-transfer"
SELECTED_QUANTUM_MANTISSA_ULPS = 4
SELECTED_ROUNDING_BIAS = 2
POLICY_QUANTA = (1, 2, 4, 8, 16)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def counter_json(counter: Counter[int]) -> JsonObject:
    return {str(key): value for key, value in sorted(counter.items())}


def quantized_mantissas(*, quantum: int, bias: int) -> np.ndarray:
    if quantum <= 0 or quantum & (quantum - 1) or not 0 <= bias < quantum:
        raise ValueError("fractional selector grid policy differs")
    mantissas = np.arange(witness_map.MANTISSA_COUNT, dtype=np.uint64)
    return ((mantissas + np.uint64(bias)) // quantum) * quantum


def class_starts() -> np.ndarray:
    starts = np.concatenate(
        (
            np.asarray([0], dtype=np.int64),
            np.arange(
                2,
                witness_map.MANTISSA_COUNT,
                SELECTED_QUANTUM_MANTISSA_ULPS,
                dtype=np.int64,
            ),
        )
    )
    expected_count = (
        witness_map.MANTISSA_COUNT // SELECTED_QUANTUM_MANTISSA_ULPS + 1
    )
    if (
        len(starts) != expected_count
        or starts[0] != 0
        or starts[1] != 2
        or starts[-1] != witness_map.MANTISSA_COUNT - 2
    ):
        raise ValueError("fractional selector class boundaries differ")
    return starts


def candidate_tables(
    assignments: np.ndarray,
    quantized: np.ndarray,
) -> tuple[np.ndarray, ...]:
    normalized_inputs = (
        np.uint64(witness_map.NORMALIZED_INPUT_LOWER) + quantized
    )
    lower_reciprocals = (
        np.uint64(witness_map.RECIPROCAL_NUMERATOR) // normalized_inputs
    )
    remainders = (
        np.uint64(witness_map.RECIPROCAL_NUMERATOR) % normalized_inputs
    )
    upper_reciprocals = lower_reciprocals + (remainders != 0)
    lower_slopes = np.empty(witness_map.MANTISSA_COUNT, dtype=np.uint32)
    upper_slopes = np.empty_like(lower_slopes)
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
    return (
        normalized_inputs,
        lower_reciprocals,
        upper_reciprocals,
        remainders,
        lower_slopes,
        upper_slopes,
    )


def policy_matching_case_count(
    observations: np.ndarray,
    assignments: np.ndarray,
    *,
    quantum: int,
    bias: int,
) -> int:
    quantized = quantized_mantissas(quantum=quantum, bias=bias)
    _, _, _, _, lower_slopes, upper_slopes = candidate_tables(
        assignments,
        quantized,
    )
    accepted = sweep.accepts_candidate(
        observations,
        lower_slopes,
    ) | sweep.accepts_candidate(observations, upper_slopes)
    return int(np.count_nonzero(accepted))


def identify_grid_policy(
    observations: np.ndarray,
    assignments: np.ndarray,
) -> JsonObject:
    matching_counts: JsonObject = {}
    full_domain: list[JsonObject] = []
    for quantum in POLICY_QUANTA:
        for bias in range(quantum):
            count = policy_matching_case_count(
                observations,
                assignments,
                quantum=quantum,
                bias=bias,
            )
            matching_counts[f"quantum-{quantum}-bias-{bias}"] = count
            if count == witness_map.MANTISSA_COUNT:
                full_domain.append(
                    {
                        "quantumMantissaUlps": quantum,
                        "roundingBias": bias,
                    }
                )
    expected = [
        {
            "quantumMantissaUlps": SELECTED_QUANTUM_MANTISSA_ULPS,
            "roundingBias": SELECTED_ROUNDING_BIAS,
        }
    ]
    if full_domain != expected:
        raise ValueError("fractional selector grid policy is not unique")
    return {
        "candidatePolicyMatchingCaseCount": matching_counts,
        "fullDomainMatchingPolicies": full_domain,
    }


def control_match_counts(selector_table: np.ndarray) -> tuple[int, int]:
    controls = sweep.sealed_controls()
    canonical_mantissas = np.arange(0, witness_map.MANTISSA_COUNT, 1_024)
    canonical_quantized = (
        (canonical_mantissas + SELECTED_ROUNDING_BIAS)
        // SELECTED_QUANTUM_MANTISSA_ULPS
        * SELECTED_QUANTUM_MANTISSA_ULPS
    )
    canonical_actual = selector_table[
        canonical_quantized // SELECTED_QUANTUM_MANTISSA_ULPS
    ]
    canonical_expected = np.asarray(controls["canonical"], dtype=np.uint32)
    canonical_matches = int(
        np.count_nonzero(canonical_actual == canonical_expected)
    )

    general_matches = 0
    for case_index, expected in enumerate(controls["generalValues"]):
        width_index, height_index = divmod(
            case_index,
            sweep.general_selector.HEIGHT_COUNT,
        )
        determinant = (
            sweep.general_selector.WIDTHS[width_index]
            * sweep.general_selector.HEIGHTS[height_index]
        )
        mantissa = sweep.general_mantissa_index(determinant)
        quantized = (
            (mantissa + SELECTED_ROUNDING_BIAS)
            // SELECTED_QUANTUM_MANTISSA_ULPS
            * SELECTED_QUANTUM_MANTISSA_ULPS
        )
        general_matches += int(
            selector_table[quantized // SELECTED_QUANTUM_MANTISSA_ULPS]
            == expected
        )
    return canonical_matches, general_matches


def analyze(root: Path) -> tuple[bytes, JsonObject]:
    sweep.load_preregistration()
    manifest, raw_path = sweep.validate_manifest(root)
    manifest_sha256 = sweep.sha256_path(root / "manifest.json")
    raw_sha256 = sweep.sha256_path(raw_path)
    if (
        manifest.get("ciCommit") != CI_COMMIT
        or manifest_sha256 != MANIFEST_SHA256
        or raw_sha256 != RAW_SHA256
    ):
        raise ValueError("fractional selector capture identity differs")
    _, prospective = sweep.validate(root)
    _, index_bytes = sweep.load_witness_inputs()
    assignments = np.frombuffer(index_bytes, dtype=np.uint8)
    records = np.memmap(raw_path, mode="r", dtype="<u4").reshape(
        witness_map.MANTISSA_COUNT,
        len(witness_map.SAMPLE_XS),
        2,
    )
    observations = records.reshape(witness_map.MANTISSA_COUNT, -1)
    policy = identify_grid_policy(observations, assignments)

    quantized = quantized_mantissas(
        quantum=SELECTED_QUANTUM_MANTISSA_ULPS,
        bias=SELECTED_ROUNDING_BIAS,
    )
    (
        normalized_inputs,
        lower_reciprocals,
        upper_reciprocals,
        remainders,
        lower_slopes,
        upper_slopes,
    ) = candidate_tables(assignments, quantized)
    lower_accepted = sweep.accepts_candidate(observations, lower_slopes)
    upper_accepted = sweep.accepts_candidate(observations, upper_slopes)
    individual_multiplicity = (
        lower_accepted.astype(np.uint8) + upper_accepted.astype(np.uint8)
    )
    if np.any(individual_multiplicity == 0):
        raise ValueError("selected grid policy does not explain every record")

    starts = class_starts()
    class_indices = (
        quantized // SELECTED_QUANTUM_MANTISSA_ULPS
    ).astype(np.int64)
    group_lower_accepted = np.logical_and.reduceat(lower_accepted, starts)
    group_upper_accepted = np.logical_and.reduceat(upper_accepted, starts)
    group_lower = lower_reciprocals[starts]
    group_upper = upper_reciprocals[starts]
    exact_candidate = group_lower == group_upper
    group_unique = (
        exact_candidate & (group_lower_accepted | group_upper_accepted)
    ) | (
        ~exact_candidate & (group_lower_accepted ^ group_upper_accepted)
    )
    if not np.all(group_unique):
        raise ValueError("pooled fractional selector witnesses are not unique")

    selected_physical = np.where(
        group_lower_accepted,
        group_lower,
        group_upper,
    )
    selected_lower_path = group_lower_accepted | exact_candidate
    selected_case_lower_path = selected_lower_path[class_indices]
    selected_case_slopes = np.where(
        selected_case_lower_path,
        lower_slopes,
        upper_slopes,
    ).astype(np.uint32)
    selected_case_accepted = np.where(
        selected_case_lower_path,
        lower_accepted,
        upper_accepted,
    )
    if not np.all(selected_case_accepted):
        raise ValueError("pooled selector does not reproduce every observation")

    selector_table = selected_physical.astype(np.uint32)
    if selector_table[0] != 1 << 25:
        raise ValueError("lower exponent-boundary selector differs")
    selector_table[0] = 1 << 24
    canonical_matches, general_matches = control_match_counts(selector_table)
    if canonical_matches != 8_192 or general_matches != 32_768:
        raise ValueError("fractional selector sealed controls do not transfer")

    group_normalized_inputs = normalized_inputs[starts]
    group_remainders = remainders[starts]
    nearest = group_lower + (
        (2 * group_remainders > group_normalized_inputs)
        | (
            (2 * group_remainders == group_normalized_inputs)
            & ((group_lower & 1) == 1)
        )
    )
    endpoint_distribution = Counter(
        (selected_physical.astype(np.int64) - group_lower.astype(np.int64)).tolist()
    )
    nearest_distribution = Counter(
        (selected_physical.astype(np.int64) - nearest.astype(np.int64)).tolist()
    )
    if set(endpoint_distribution) - {0, 1}:
        raise ValueError("fractional selector is not an exact endpoint")

    selector_bytes = selector_table.astype("<u4", copy=False).tobytes()
    selected_slope_bytes = selected_case_slopes.astype(
        "<u4", copy=False
    ).tobytes()
    if (
        sha256_bytes(selector_bytes) != SELECTOR_TABLE_SHA256
        or sha256_bytes(selected_slope_bytes) != CASE_SLOPE_TABLE_SHA256
    ):
        raise ValueError("resolved fractional selector evidence differs")
    prospective_measurement = prospective["measurement"]
    report: JsonObject = {
        "rasterFractionalSubpixelTransferAnalysisSchemaVersion": SCHEMA_VERSION,
        "classification": ROLE,
        "ciRunId": CI_RUN_ID,
        "ciCommit": manifest.get("ciCommit"),
        "manifestSha256": manifest_sha256,
        "rawSha256": raw_sha256,
        "preregistrationSha256": sweep.PREREGISTRATION_SHA256,
        "prospectiveHypothesis": {
            "exactFloatingWidthHypothesisFalsified": True,
            "candidateMultiplicity": prospective_measurement[
                "selectorCandidateMultiplicity"
            ],
            "canonicalIntegerWidthExactMatchCount": prospective_measurement[
                "canonicalIntegerWidthExactMatchCount"
            ],
            "generalHeightExactMatchCount": prospective_measurement[
                "generalHeightExactMatchCount"
            ],
        },
        "quantizerIdentification": {
            "inputCoordinateMantissaUlpPixels": "1/1024",
            "selectedQuantumMantissaUlps": SELECTED_QUANTUM_MANTISSA_ULPS,
            "selectedQuantumPixels": "1/256",
            "selectedRoundingBias": SELECTED_ROUNDING_BIAS,
            "selectedRounding": "nearest with half-step ties toward positive infinity",
            "selectedFormula": "((mantissa + 2) // 4) * 4",
            **policy,
        },
        "measurement": {
            "inputMantissaCount": witness_map.MANTISSA_COUNT,
            "inputRecordCount": int(records.shape[0] * records.shape[1]),
            "allInputRecordsExplained": True,
            "individualCandidateMultiplicity": counter_json(
                Counter(individual_multiplicity.tolist())
            ),
            "quantizedClassCount": len(starts),
            "quantizedClassMemberCountDistribution": {
                "2": 2,
                "4": len(starts) - 2,
            },
            "exactReciprocalClassCount": int(np.count_nonzero(exact_candidate)),
            "jointLowerOnlyClassCount": int(
                np.count_nonzero(
                    group_lower_accepted & ~group_upper_accepted
                )
            ),
            "jointUpperOnlyClassCount": int(
                np.count_nonzero(
                    ~group_lower_accepted & group_upper_accepted
                )
            ),
            "jointExactClassCount": int(np.count_nonzero(exact_candidate)),
            "jointSelectorUniqueClassCount": int(np.count_nonzero(group_unique)),
            "resolvedSelectorEndpointFromFloorDistribution": counter_json(
                endpoint_distribution
            ),
            "resolvedSelectorOffsetFromNearestDistribution": counter_json(
                nearest_distribution
            ),
            "resolvedSelectorTableBytes": len(selector_bytes),
            "resolvedSelectorTableSha256": sha256_bytes(selector_bytes),
            "resolvedCaseSlopeTableSha256": sha256_bytes(selected_slope_bytes),
            "canonicalIntegerWidthExactMatchCount": canonical_matches,
            "canonicalIntegerWidthCount": 8_192,
            "generalHeightExactMatchCount": general_matches,
            "generalHeightCount": 32_768,
            "sealedControlGate": True,
            "exhaustiveQuantizedClassGate": True,
        },
        "conclusions": {
            "fractionalCoordinatesQuantizedToOneOver256Pixels": True,
            "positiveNormalMantissaInputDomainComplete": True,
            "quantizedCoordinateSelectorClassDomainComplete": True,
            "priorSelectorCorporaTransferredExactly": True,
            "portableClosedFormSelectorLawEstablished": False,
            "clippedSetupEstablished": False,
            "endToEndLiquidGlassParityEstablished": False,
        },
    }
    return selector_bytes, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--selector-output", type=Path)
    parser.add_argument("--report", type=Path)
    arguments = parser.parse_args()
    selectors, report = analyze(arguments.root)
    compressed = zlib.compress(selectors, level=9)
    if sha256_bytes(compressed) != SELECTOR_COMPRESSED_SHA256:
        raise ValueError("compressed fractional selector evidence differs")
    report["measurement"]["compressedSelectorTableBytes"] = len(compressed)
    report["measurement"]["compressedSelectorTableSha256"] = sha256_bytes(
        compressed
    )
    if arguments.selector_output is not None:
        arguments.selector_output.write_bytes(compressed)
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.report is not None:
        arguments.report.write_text(serialized, encoding="utf-8")
    print(serialized, end="")


if __name__ == "__main__":
    main()
