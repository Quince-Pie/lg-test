#!/usr/bin/env python3
"""Validate Darwin/CoreGraphics candidates for dynamic inputClamp arithmetic."""

from __future__ import annotations

import argparse
import json
import struct
from collections import Counter
from pathlib import Path
from typing import Any

import validate_dynamic_allocation_holdout as holdout


ENCODED_CANDIDATES = (
    "double-multiply-add-cast-float",
    "float-fma",
    "float-multiply-add",
    "float-weighted-mix",
)
DECODED_CANDIDATES = (
    "coregraphics-extended-srgb-to-linear",
    "double-base-darwin-pow-cast-float",
    "float-base-darwin-pow-cast-float",
    "float-base-darwin-powf",
    "mixed-base-darwin-powf",
    "mixed-base-vforce-vvpowf",
)
EXPECTED_CANDIDATE_NAMES = tuple(
    f"{encoded}/{decoded}"
    for encoded in ENCODED_CANDIDATES
    for decoded in DECODED_CANDIDATES
)
EXPECTED_SAMPLE_INDICES = tuple(range(1, 33))
CLASSIFICATION = (
    "prospective-platform-arithmetic-candidate-measurement; "
    "candidate-selection-is-not-an-unseen-rendering-transfer"
)


def float32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def float32_bits(value: float) -> str:
    return struct.pack("<f", value)[::-1].hex()


def float_evidence(value: object, name: str) -> tuple[float, str]:
    evidence = holdout.mapping(value, name)
    number = holdout.numeric(evidence.get("value"), f"{name} value")
    bits = evidence.get("bits")
    if not isinstance(bits, str) or len(bits) != 8:
        raise ValueError(f"{name} bits differ")
    normalized = float32(number)
    if float32_bits(normalized) != bits:
        raise ValueError(f"{name} value and bits differ")
    return normalized, bits


def validate(path: Path) -> dict[str, Any]:
    report = holdout.mapping(
        json.loads(path.read_text(encoding="utf-8")), "transition report"
    )
    uniforms = holdout.mapping(
        report.get("dynamicBackgroundUniforms"), "dynamic background uniforms"
    )
    probe = holdout.mapping(
        uniforms.get("inputClampArithmeticProbe"), "inputClamp arithmetic probe"
    )
    untyped_records = probe.get("records")
    if (
        probe.get("schemaVersion") != 1
        or probe.get("requested") is not True
        or probe.get("executed") is not True
        or probe.get("sampleCount") != len(EXPECTED_SAMPLE_INDICES)
        or probe.get("executedSampleCount") != len(EXPECTED_SAMPLE_INDICES)
        or not isinstance(untyped_records, list)
        or len(untyped_records) != len(EXPECTED_SAMPLE_INDICES)
    ):
        raise ValueError("inputClamp arithmetic probe is incomplete")
    normal_records = uniforms.get("records")
    if not isinstance(normal_records, list) or len(normal_records) != len(
        EXPECTED_SAMPLE_INDICES
    ):
        raise ValueError("normal dynamic records are incomplete")
    normal_by_sample = {
        int(holdout.mapping(value, "normal record")["sampleIndex"]): holdout.mapping(
            value, "normal record"
        )
        for value in normal_records
    }

    match_counts: Counter[str] = Counter()
    records: list[dict[str, Any]] = []
    for sample_index, untyped_record in zip(
        EXPECTED_SAMPLE_INDICES, untyped_records, strict=True
    ):
        record = holdout.mapping(untyped_record, "inputClamp record")
        if (
            record.get("sampleIndex") != sample_index
            or record.get("executed") is not True
        ):
            raise ValueError(f"inputClamp record differs at sample {sample_index}")
        remaining, remaining_bits = float_evidence(record.get("remaining"), "remaining")
        observed, observed_bits = float_evidence(
            record.get("observedInputClamp"), "observed inputClamp"
        )
        normal = normal_by_sample[sample_index]
        normal_remaining = holdout.numeric(normal.get("remaining"), "normal remaining")
        normal_inputs = holdout.mapping(
            holdout.mapping(normal.get("filter"), "normal filter").get("inputValues"),
            "normal filter inputs",
        )
        normal_clamp = holdout.numeric(
            normal_inputs.get("inputClamp"), "normal inputClamp"
        )
        if remaining_bits != float32_bits(
            normal_remaining
        ) or observed_bits != float32_bits(normal_clamp):
            raise ValueError("inputClamp probe and captured filter differ")

        candidates = holdout.mapping(record.get("candidates"), "inputClamp candidates")
        if record.get("candidateCount") != len(EXPECTED_CANDIDATE_NAMES) or set(
            candidates
        ) != set(EXPECTED_CANDIDATE_NAMES):
            raise ValueError("inputClamp candidate set differs")
        computed_exact: list[str] = []
        candidate_bits: dict[str, str] = {}
        for name in EXPECTED_CANDIDATE_NAMES:
            candidate = holdout.mapping(candidates.get(name), f"candidate {name}")
            float_evidence(candidate.get("encoded"), f"encoded {name}")
            _, decoded_bits = float_evidence(
                candidate.get("decoded"), f"decoded {name}"
            )
            candidate_bits[name] = decoded_bits
            if decoded_bits == observed_bits:
                computed_exact.append(name)
                match_counts[name] += 1
        if record.get("exactCandidateNames") != computed_exact:
            raise ValueError("inputClamp exact candidate list differs")
        records.append(
            {
                "sampleIndex": sample_index,
                "remaining": remaining,
                "remainingBits": remaining_bits,
                "observedInputClamp": observed,
                "observedInputClampBits": observed_bits,
                "exactCandidateNames": computed_exact,
                "candidateDecodedBits": candidate_bits,
            }
        )

    exact_every_state = [
        name
        for name in EXPECTED_CANDIDATE_NAMES
        if match_counts[name] == len(EXPECTED_SAMPLE_INDICES)
    ]
    return {
        "transitionInputClampProbeResultSchemaVersion": 1,
        "classification": CLASSIFICATION,
        "timeline": str(path),
        "timelineSHA256": holdout.sha256_file(path),
        "sampleIndices": list(EXPECTED_SAMPLE_INDICES),
        "candidateNames": list(EXPECTED_CANDIDATE_NAMES),
        "aggregate": {
            "sampleCount": len(records),
            "candidateCount": len(EXPECTED_CANDIDATE_NAMES),
            "exactMatchCounts": {
                name: match_counts[name] for name in EXPECTED_CANDIDATE_NAMES
            },
            "exactEveryStateCandidateNames": exact_every_state,
        },
        "records": records,
        "conclusion": {
            "captureIntegrityPassed": True,
            "platformArithmeticCandidateRecovered": bool(exact_every_state),
            "candidateSelectionOnly": True,
            "requiresUnseenTemporalTransfer": True,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = validate(arguments.report)
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")
        print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
