#!/usr/bin/env python3
"""Fail-closed validation for preregistered exact source holdouts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REQUIRED_PATTERNS = {
    "constant-opaque",
    "opaque-coordinate-hash",
    "premultiplied-alpha-field",
    "discordant-mips",
    "sampler-basis-level-zero",
    "sampler-basis-level-one",
    "prospective-opaque-seeded-v1",
    "prospective-premultiplied-seeded-v1",
}
PROSPECTIVE_PATTERNS = {
    "prospective-opaque-seeded-v1",
    "prospective-premultiplied-seeded-v1",
}
PRODUCTION_ORACLE_PATTERNS = {
    "opaque-coordinate-hash",
    "sampler-basis-level-zero",
    "sampler-basis-level-one",
    "prospective-opaque-seeded-v1",
}
PRODUCTION_ORACLE_EDITS = {
    "production-edge-sample": {
        "face_matrix_0": (128, "0000000000000000"),
        "face_matrix_1": (136, "0000000000000000"),
        "face_matrix_2": (144, "0000000000000000"),
        "bleed_matrix_0": (152, "003c000000000000"),
        "bleed_matrix_1": (160, "0000003c00000000"),
        "bleed_matrix_2": (168, "00000000003c0000"),
        "edge_bleed_distance": (224, "fffbfefb"),
        "edge_bleed_opacity": (228, "003c"),
        "face_opacity": (230, "003c"),
        "bleed_darken": (232, "0000003c"),
        "shadow_opacity": (238, "0000"),
        "holding_tone_opacity": (242, "0000"),
        "clamp_limit": (248, "0000"),
    },
    "production-shadow-sample": {
        "shadow_inverse_radius": (124, "00000000"),
        "face_matrix_0": (128, "0000000000000000"),
        "face_matrix_1": (136, "0000000000000000"),
        "face_matrix_2": (144, "0000000000000000"),
        "shadow_matrix_0": (176, "003c000000000000"),
        "shadow_matrix_1": (184, "0000003c00000000"),
        "shadow_matrix_2": (192, "00000000003c0000"),
        "shadow_contribution": (200, "0000803f"),
        "shadow_face_opacity": (204, "0000803f"),
        "edge_bleed_opacity": (228, "0000"),
        "face_opacity": (230, "003c"),
        "shadow_opacity": (238, "0040"),
        "holding_tone_opacity": (242, "0000"),
        "clamp_limit": (248, "0000"),
    },
}
REGULAR_DIAGNOSTIC_TRACES = {
    "edgeSampleTrace": ("edge-sample", 115, 8),
    "shadowSampleTrace": ("shadow-sample", 115, 8),
    "shadowLayerTrace": ("shadow-layer", 115, 8),
    "bleedTrace": ("bleed", 115, 8),
    "colorStagesATrace": ("color-stages-a", 123, 16),
    "colorStagesBTrace": ("color-stages-b", 123, 16),
    "finalColorTrace": ("final-color", 115, 8),
}
MASK64 = (1 << 64) - 1


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def fnv1a64_file(path: Path) -> str:
    result = 0xCBF29CE484222325
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            for byte in block:
                result ^= byte
                result = (result * 0x100000001B3) & MASK64
    return f"{result:016x}"


def raw_file(root: Path, record: dict[str, Any]) -> Path:
    filename = record.get("rawFile")
    require(isinstance(filename, str) and filename, "raw file is missing")
    path = root / filename
    require(path.parent == root, f"raw file escapes artifact root: {filename}")
    require(path.is_file(), f"raw file does not exist: {path}")
    return path


def validate_record_file(
    root: Path,
    record: dict[str, Any],
    *,
    description: str,
) -> Path:
    path = raw_file(root, record)
    require(
        path.stat().st_size == record.get("rawBytes"),
        f"{description} byte count differs: {path}",
    )
    require(
        fnv1a64_file(path) == record.get("fnv1a64"),
        f"{description} FNV-1a differs: {path}",
    )
    return path


def validate_exact_comparison(
    record: dict[str, Any],
    *,
    pattern: str,
) -> None:
    construction = record.get("construction", {})
    comparison = record.get("comparison", {})
    reference = record.get("reference", {})
    candidate = record.get("candidate", {})
    sample_trace = record.get("sampleTrace", {})
    require(record.get("executed") is True, f"{pattern} did not execute")
    require(
        construction.get("created") is True,
        f"{pattern} source construction failed",
    )
    require(
        reference.get("executed") is True,
        f"{pattern} Apple replay failed",
    )
    require(
        candidate.get("executed") is True,
        f"{pattern} independent replay failed",
    )
    require(
        sample_trace.get("executed") is True,
        f"{pattern} source trace failed",
    )
    require(
        comparison.get("compared") is True
        and comparison.get("exactByteMatch") is True
        and comparison.get("mismatchedByteCount") == 0
        and comparison.get("mismatchedPixelCount") == 0
        and comparison.get("maximumChannelDelta") == 0,
        f"{pattern} Apple/independent comparison is not byte-exact",
    )


def validate_production_oracle(
    root: Path,
    oracle: dict[str, Any],
    *,
    pattern: str,
) -> dict[str, str]:
    name = oracle.get("name")
    require(
        isinstance(name, str) and name in PRODUCTION_ORACLE_EDITS,
        f"{pattern} production sampler oracle name differs",
    )
    require(
        oracle.get("executed") is True,
        f"{pattern} {name} oracle did not execute",
    )
    edits = oracle.get("edits", [])
    actual_edits = {
        edit.get("field"): (edit.get("recordOffset"), edit.get("hex"))
        for edit in edits
        if isinstance(edit, dict)
    }
    require(
        len(actual_edits) == len(edits)
        and actual_edits == PRODUCTION_ORACLE_EDITS[name],
        f"{pattern} {name} oracle uniform edits differ",
    )
    comparison = oracle.get("comparison", {})
    require(
        comparison.get("compared") is True
        and comparison.get("exactByteMatch") is True
        and comparison.get("mismatchedByteCount") == 0
        and comparison.get("mismatchedPixelCount") == 0
        and comparison.get("maximumChannelDelta") == 0,
        f"{pattern} {name} Apple/independent output is not byte-exact",
    )
    hashes: dict[str, str] = {}
    for implementation in ("reference", "candidate"):
        replay = oracle.get(implementation, {})
        require(
            replay.get("executed") is True,
            f"{pattern} {name} {implementation} replay failed",
        )
        output = replay.get("output", {})
        width = output.get("width")
        height = output.get("height")
        require(
            isinstance(width, int)
            and width > 0
            and isinstance(height, int)
            and height > 0
            and output.get("pixelFormat") == 80
            and output.get("rawBytes") == width * height * 4,
            f"{pattern} {name} {implementation} output metadata differs",
        )
        path = validate_record_file(
            root,
            output,
            description=f"{pattern} {name} {implementation} output",
        )
        hashes[implementation] = sha256_file(path)
    require(
        hashes["reference"] == hashes["candidate"],
        f"{pattern} {name} output SHA-256 differs",
    )
    return hashes


def validate(
    capture_root: Path,
    preregistration_path: Path,
    *,
    material: str,
    appearance: str,
) -> dict[str, Any]:
    runtime_path = capture_root / "runtime.json"
    require(runtime_path.is_file(), f"runtime evidence is missing: {runtime_path}")
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    preregistration = json.loads(
        preregistration_path.read_text(encoding="utf-8")
    )
    profile = runtime.get("materialProfileEvidence", {})
    require(profile.get("material") == material, "material differs")
    require(
        profile.get("requestedAppearance") == appearance,
        "appearance differs",
    )
    require(
        preregistration.get("liquidGlassUnseenSourceHoldoutSchemaVersion")
        == 1,
        "preregistration schema differs",
    )
    require(
        preregistration.get("status")
        == "preregistered-before-apple-capture",
        "preregistration is not sealed",
    )
    require(
        preregistration.get("scope", {}).get(
            "appleOutputAvailableDuringPrediction"
        )
        is False,
        "preregistration does not exclude Apple output",
    )

    source_differential = (
        runtime.get("carendererEvidence", {})
        .get("exactPassReplay", {})
        .get("independentGlassReplay", {})
        .get("sourceTextureDifferential", {})
    )
    records = {
        record.get("name"): record
        for record in source_differential.get("records", [])
        if isinstance(record, dict)
    }
    prospective = source_differential.get("prospectiveHoldout", {})
    require(source_differential.get("schemaVersion") == 4, "schema differs")
    require(source_differential.get("executed") is True, "probe did not execute")
    require(
        source_differential.get("fragmentTextureIndex") == 3,
        "source texture index differs",
    )
    require(set(records) == REQUIRED_PATTERNS, "source inventory differs")
    require(
        prospective.get("status") == "preregistered-before-apple-capture",
        "runtime holdout status differs",
    )
    require(
        set(prospective.get("patterns", [])) == PROSPECTIVE_PATTERNS,
        "runtime prospective inventory differs",
    )
    require(
        set(prospective.get("regularDiagnosticTraces", []))
        == {
            specification[0]
            for specification in REGULAR_DIAGNOSTIC_TRACES.values()
        },
        "runtime regular diagnostic inventory differs",
    )
    require(
        set(prospective.get("regularProductionSamplerOraclePatterns", []))
        == PRODUCTION_ORACLE_PATTERNS,
        "runtime production sampler oracle pattern inventory differs",
    )
    require(
        set(prospective.get("regularProductionSamplerOracles", []))
        == set(PRODUCTION_ORACLE_EDITS),
        "runtime production sampler oracle inventory differs",
    )

    diagnostic_hashes: dict[str, dict[str, str]] = {}
    production_oracle_hashes: dict[str, dict[str, dict[str, str]]] = {}
    for pattern, record in records.items():
        validate_exact_comparison(record, pattern=pattern)
        construction = record["construction"]
        levels = construction.get("levels", [])
        require(bool(levels), f"{pattern} has no source mips")
        for level in levels:
            require(
                level.get("rawWritten") is True,
                f"{pattern} source mip was not written",
            )
            validate_record_file(
                capture_root,
                level,
                description=f"{pattern} source mip {level.get('level')}",
            )
        for implementation in ("reference", "candidate"):
            validate_record_file(
                capture_root,
                record[implementation]["output"],
                description=f"{pattern} {implementation} output",
            )
        if material == "regular" and pattern in PROSPECTIVE_PATTERNS:
            diagnostic_hashes[pattern] = {}
            for field, (
                trace_name,
                pixel_format,
                bytes_per_pixel,
            ) in REGULAR_DIAGNOSTIC_TRACES.items():
                trace = record.get(field, {})
                require(
                    trace.get("executed") is True,
                    f"{pattern} {trace_name} diagnostic did not execute",
                )
                output = trace.get("output", {})
                width = output.get("width")
                height = output.get("height")
                require(
                    isinstance(width, int)
                    and width > 0
                    and isinstance(height, int)
                    and height > 0
                    and output.get("pixelFormat") == pixel_format
                    and output.get("rawBytes")
                    == width * height * bytes_per_pixel,
                    f"{pattern} {trace_name} diagnostic metadata differs",
                )
                path = validate_record_file(
                    capture_root,
                    output,
                    description=f"{pattern} {trace_name} diagnostic",
                )
                diagnostic_hashes[pattern][trace_name] = sha256_file(path)
        if material == "regular" and pattern in PRODUCTION_ORACLE_PATTERNS:
            oracle_records = record.get("productionSamplerOracles", [])
            oracles = {
                oracle.get("name"): oracle
                for oracle in oracle_records
                if isinstance(oracle, dict)
            }
            require(
                len(oracles) == len(oracle_records)
                and set(oracles) == set(PRODUCTION_ORACLE_EDITS),
                f"{pattern} production sampler oracle inventory differs",
            )
            production_oracle_hashes[pattern] = {
                name: validate_production_oracle(
                    capture_root,
                    oracles[name],
                    pattern=pattern,
                )
                for name in sorted(oracles)
            }

    profile_name = f"{material}-{appearance}"
    prospective_results: dict[str, Any] = {}
    for pattern in sorted(PROSPECTIVE_PATTERNS):
        record = records[pattern]
        expected_levels = preregistration["sources"][pattern][material]
        actual_levels = {
            level.get("level"): level
            for level in record["construction"]["levels"]
        }
        require(
            set(actual_levels)
            == {expected["level"] for expected in expected_levels},
            f"{pattern} prospective mip inventory differs",
        )
        source_hashes = []
        for expected in expected_levels:
            actual = actual_levels[expected["level"]]
            path = raw_file(capture_root, actual)
            require(
                actual.get("width") == expected["width"]
                and actual.get("height") == expected["height"]
                and actual.get("rawBytes") == expected["bytes"]
                and actual.get("fnv1a64") == expected["fnv1a64"],
                f"{pattern} prospective mip metadata differs",
            )
            actual_sha256 = sha256_file(path)
            require(
                actual_sha256 == expected["sha256"],
                f"{pattern} prospective mip SHA-256 differs",
            )
            source_hashes.append(actual_sha256)

        expected_output = preregistration["predictions"][profile_name][
            pattern
        ]["output"]
        output_hashes = {}
        for implementation in ("reference", "candidate"):
            output = record[implementation]["output"]
            path = raw_file(capture_root, output)
            require(
                output.get("width") == expected_output["width"]
                and output.get("height") == expected_output["height"]
                and output.get("rawBytes") == expected_output["bytes"]
                and output.get("fnv1a64") == expected_output["fnv1a64"],
                f"{pattern} {implementation} output metadata differs",
            )
            actual_sha256 = sha256_file(path)
            require(
                actual_sha256 == expected_output["sha256"],
                f"{pattern} {implementation} output SHA-256 differs",
            )
            output_hashes[implementation] = actual_sha256
        prospective_results[pattern] = {
            "sourceMipSha256": source_hashes,
            "expectedOutputSha256": expected_output["sha256"],
            "outputSha256": output_hashes,
            "regularDiagnosticTraceSha256": diagnostic_hashes.get(
                pattern, {}
            ),
            "productionSamplerOracleSha256": production_oracle_hashes.get(
                pattern, {}
            ),
            "exact": True,
        }

    return {
        "liquidGlassExactSourceHoldoutValidationSchemaVersion": 1,
        "profile": profile_name,
        "patternCount": len(records),
        "prospectivePatternCount": len(PROSPECTIVE_PATTERNS),
        "preregistrationSha256": sha256_file(preregistration_path),
        "runtimeSha256": sha256_file(runtime_path),
        "prospective": prospective_results,
        "productionSamplerOracleSha256": production_oracle_hashes,
        "allAppleMetalAndFrozenGlslOutputsExact": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("preregistration", type=Path)
    parser.add_argument("--material", choices=("clear", "regular"), required=True)
    parser.add_argument("--appearance", choices=("light", "dark"), required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = validate(
        arguments.capture_root,
        arguments.preregistration,
        material=arguments.material,
        appearance=arguments.appearance,
    )
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")
        print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
