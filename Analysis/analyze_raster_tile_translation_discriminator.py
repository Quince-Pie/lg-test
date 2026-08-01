#!/usr/bin/env python3
"""Fit and verify schema-5 using only the four readable discovery cases."""

import argparse
import hashlib
import json
import mmap
from collections import Counter
from pathlib import Path
from typing import Any

import raster_tile_selector_model as v1
import raster_tile_selector_model_v3 as model
import validate_raster_tile_translation_discriminator as capture


type JsonObject = dict[str, Any]

EXPECTED_RAW_SHA256 = (
    "3cd6a35830a3d71af0252b87bce94e97917fdd68234805216d432b0bedbc1cc3"
)
MAX_MISMATCH_EXAMPLES = 64
COMPONENT_NAMES = (
    *(f"pull@{numerator}/16" for numerator in capture.PULL_NUMERATORS),
    "center",
    "axis-derivative(center)",
)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


class DiscoveryRecords:
    """A raw accessor that refuses every non-discovery case before reading."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.discovery_reads = 0
        self.sealed_reads = 0
        self._stream = None
        self._raw = None

    def __enter__(self) -> "DiscoveryRecords":
        self._stream = self.path.open("rb")
        self._raw = mmap.mmap(self._stream.fileno(), 0, access=mmap.ACCESS_READ)
        return self

    def __exit__(self, *_: object) -> None:
        if self._raw is not None:
            self._raw.close()
        if self._stream is not None:
            self._stream.close()

    def record(
        self,
        case_index: int,
        endpoint_index: int,
        sample: capture.SamplePosition,
    ) -> tuple[int, ...]:
        capture_case = capture.CASES[case_index]
        if capture_case.role != "discovery":
            self.sealed_reads += capture_case.role == "sealed-holdout"
            raise PermissionError(
                f"discovery analysis cannot read {capture_case.role} case "
                f"{capture_case.name}"
            )
        if self._raw is None:
            raise RuntimeError("discovery records are not open")
        record_index = (
            case_index * len(capture.ENDPOINTS) + endpoint_index
        ) * capture.SLOT_COUNT + sample.slot
        self.discovery_reads += 1
        return capture.RECORD.unpack_from(
            self._raw,
            record_index * capture.RECORD.size,
        )


def capture_paths(root: Path) -> tuple[JsonObject, Path]:
    manifest: JsonObject = json.loads(
        (root / "manifest.json").read_text(encoding="utf-8")
    )
    evidence = manifest.get("rasterTileNumerator", {})
    raw_path = root / str(evidence.get("file", ""))
    if (
        manifest.get("schemaVersion") != capture.SCHEMA_VERSION
        or manifest.get("rigVersion") != capture.RIG_VERSION
        or evidence.get("role") != capture.ROLE
        or evidence.get("layout") != capture.layout_metadata()
        or evidence.get("sha256") != EXPECTED_RAW_SHA256
        or not raw_path.is_file()
        or raw_path.stat().st_size != capture.raw_bytes()
    ):
        raise ValueError("schema-5 discovery manifest differs")
    return manifest, raw_path


def analyze(root: Path) -> JsonObject:
    manifest, raw_path = capture_paths(root)
    selector_table = v1.load_selector_table()
    mismatch_examples: list[JsonObject] = []
    component_mismatches: Counter[str] = Counter()
    slope_selectors: Counter[str] = Counter()
    constant_selectors: Counter[str] = Counter()
    selected_constant_groups: set[tuple[str, str, int, int, int, str]] = set()
    record_count = 0
    mismatched_records = 0
    mismatched_words = 0
    with DiscoveryRecords(raw_path) as records:
        for case_index, capture_case in enumerate(capture.CASES):
            if capture_case.role != "discovery":
                continue
            samples = capture.sample_positions(capture_case)
            for endpoint_index, endpoint in enumerate(capture.ENDPOINTS):
                slopes = {
                    axis: model.selected_slope(
                        capture_case,
                        endpoint,
                        axis=axis,
                        selector_table=selector_table,
                    )
                    for axis in range(capture.AXIS_COUNT)
                }
                for sample in samples:
                    slope_name, slope, setup_phase, setup_internal = slopes[
                        sample.axis
                    ]
                    constant_name, constant_bits, constant_phase = (
                        model.selected_constant_bits(
                            capture_case,
                            endpoint,
                            sample,
                            setup_phase=setup_phase,
                            setup_internal=setup_internal,
                            selector_table=selector_table,
                        )
                    )
                    slope_selectors[slope_name] += 1
                    constant_selectors[constant_name] += 1
                    selected_constant_groups.add(
                        (
                            capture_case.name,
                            endpoint.name,
                            sample.axis,
                            sample.primitive,
                            sample.tile,
                            constant_name,
                        )
                    )
                    actual = records.record(case_index, endpoint_index, sample)
                    if (
                        actual == capture.SENTINEL
                        or not all(capture.base.finite(bits) for bits in actual)
                    ):
                        raise ValueError("discovery record is absent or nonfinite")
                    predicted = model.v2.predict_record_with_setup(
                        sample,
                        slope=slope,
                        constant=v1.bits_float32(constant_bits),
                    )
                    differing = [
                        index
                        for index, (predicted_word, actual_word) in enumerate(
                            zip(predicted, actual, strict=True)
                        )
                        if predicted_word != actual_word
                    ]
                    record_count += 1
                    if not differing:
                        continue
                    mismatched_records += 1
                    mismatched_words += len(differing)
                    component_mismatches.update(
                        COMPONENT_NAMES[index] for index in differing
                    )
                    if len(mismatch_examples) < MAX_MISMATCH_EXAMPLES:
                        mismatch_examples.append(
                            {
                                "case": capture_case.name,
                                "endpoint": endpoint.name,
                                "axis": "x" if sample.axis == 0 else "y",
                                "primitive": sample.primitive,
                                "tile": sample.tile,
                                "edge": sample.edge,
                                "slopeSelector": slope_name,
                                "constantSelector": constant_name,
                                "setupPhase": str(setup_phase),
                                "constantPhase": (
                                    None
                                    if constant_phase is None
                                    else str(constant_phase)
                                ),
                                "components": [
                                    {
                                        "name": COMPONENT_NAMES[index],
                                        "predictedBits": f"0x{predicted[index]:08x}",
                                        "actualBits": f"0x{actual[index]:08x}",
                                    }
                                    for index in differing
                                ],
                            }
                        )
        discovery_reads = records.discovery_reads
        sealed_reads = records.sealed_reads

    discovery_case_count = sum(
        capture_case.role == "discovery" for capture_case in capture.CASES
    )
    expected_records = sum(
        len(capture.sample_positions(capture_case)) * len(capture.ENDPOINTS)
        for capture_case in capture.CASES
        if capture_case.role == "discovery"
    )
    exact = (
        record_count == expected_records == discovery_reads == 35_168
        and sealed_reads == 0
        and mismatched_records == 0
        and mismatched_words == 0
    )
    return {
        "rasterTileTranslationDiscoveryAnalysisSchemaVersion": 1,
        "source": str(root),
        "sourceManifestSha256": sha256_path(root / "manifest.json"),
        "sourceRawManifestSha256": manifest["rasterTileNumerator"]["sha256"],
        "sourceCiCommit": manifest["ciCommit"],
        "discoveryCaseCount": discovery_case_count,
        "sealedCaseCount": sum(
            capture_case.role == "sealed-holdout"
            for capture_case in capture.CASES
        ),
        "discoveryRecordReadCount": discovery_reads,
        "sealedRecordReadCount": sealed_reads,
        "recordCount": record_count,
        "wordCount": record_count * capture.RECORD_COMPONENT_COUNT,
        "mismatchedRecordCount": mismatched_records,
        "mismatchedWordCount": mismatched_words,
        "componentMismatchCounts": dict(sorted(component_mismatches.items())),
        "slopeSelectorRecordCounts": dict(sorted(slope_selectors.items())),
        "constantSelectorRecordCounts": dict(sorted(constant_selectors.items())),
        "constantSelectorGroupCounts": dict(
            sorted(Counter(group[-1] for group in selected_constant_groups).items())
        ),
        "mismatchExamples": mismatch_examples,
        "exact": exact,
        "sealedHoldoutOpened": False,
        "productionShaderAuthorized": False,
        "nextGate": (
            "Commit this executable model, its compressed sealed prediction bytes, "
            "and all prediction hashes before opening any sealed record."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    report = analyze(arguments.root)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not report["exact"]:
        raise SystemExit("schema-5 discovery model differs")


if __name__ == "__main__":
    main()
