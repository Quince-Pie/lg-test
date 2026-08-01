#!/usr/bin/env python3
"""Validate power-scaled raster coefficients across isolated clip axes."""

import argparse
import functools
import hashlib
import json
import struct
import zlib
from collections import Counter
from pathlib import Path
from typing import Any

import model_raster_general_height_arithmetic as two_stage
import validate_raster_general_height_factorization as factorization
import validate_raster_general_height_selector_transfer as selector


type JsonObject = dict[str, Any]

SCHEMA_VERSION = 1
RIG_VERSION = "metal-raster-clipped-setup-transfer-1.0.0"
ROLE = "prospective-power-scaled-axis-isolated-clipped-setup-transfer"
TARGET_WIDTH = 256
TARGET_HEIGHT = 256
VIEWPORT_WIDTH = 256
CENTER_X = 128.0
CENTER_Y = 127.5
SAMPLE_Y = 127
SAMPLE_XS = (96, 126, 128, 158)
SAMPLE_POSITION_COUNT = len(SAMPLE_XS)
PULL_OFFSETS = (0.0, 0.9375)
VARIANTS = (
    {
        "name": "unclipped-zero-origin-control",
        "xExponentShift": 6,
        "heightScale": 1,
        "centeredVarying": False,
        "xClipped": False,
        "yClipped": False,
    },
    {
        "name": "unclipped-centered-control",
        "xExponentShift": 6,
        "heightScale": 1,
        "centeredVarying": True,
        "xClipped": False,
        "yClipped": False,
    },
    {
        "name": "x-clipped-centered",
        "xExponentShift": 3,
        "heightScale": 1,
        "centeredVarying": True,
        "xClipped": True,
        "yClipped": False,
    },
    {
        "name": "y-clipped-centered",
        "xExponentShift": 6,
        "heightScale": 8,
        "centeredVarying": True,
        "xClipped": False,
        "yClipped": True,
    },
    {
        "name": "xy-clipped-centered",
        "xExponentShift": 3,
        "heightScale": 8,
        "centeredVarying": True,
        "xClipped": True,
        "yClipped": True,
    },
)
VARIANT_COUNT = len(VARIANTS)
WIDTHS = selector.WIDTHS
HEIGHTS = selector.HEIGHTS
WITNESS_SIGNIFICANDS = selector.WITNESS_SIGNIFICANDS
WIDTH_COUNT = len(WIDTHS)
HEIGHT_COUNT = len(HEIGHTS)
WITNESS_COUNT = len(WITNESS_SIGNIFICANDS)
CASE_COUNT = WIDTH_COUNT * HEIGHT_COUNT
COEFFICIENT_COUNT = CASE_COUNT * WITNESS_COUNT
COEFFICIENT_VARIANT_COUNT = COEFFICIENT_COUNT * VARIANT_COUNT
BATCH_WIDTH_COUNT = 128
CANDIDATE_RADIUS_FLOAT_ULPS = 8
RECORD = struct.Struct("<2I")
RECORD_COUNT = COEFFICIENT_VARIANT_COUNT * SAMPLE_POSITION_COUNT
RAW_BYTES = RECORD_COUNT * RECORD.size
SENTINEL = (0xFFFF_FFFF, 0xFFFF_FFFF)
SELECTOR_PATH = Path(__file__).with_name(
    "raster_general_height_resolved_selectors.zlib"
)
SELECTOR_RAW_BYTES = 131_072
SELECTOR_RAW_SHA256 = "0b8ece5b7c2ea05475fd76120987670bf29cf69d16916372af5cf4734fd209af"
SELECTOR_COMPRESSED_BYTES = 110_243
SELECTOR_COMPRESSED_SHA256 = (
    "ae266b7bc78ccf28549d376627e73819eefa0596135fca4709a85d1070e00eee"
)
EXPECTED_BASE_SLOPE_SHA256 = (
    "14f89787b189e382b313ae5406dd1a8519e536b96783f74fb29e7959926b3f8f"
)
PREREGISTRATION_PATH = Path(__file__).with_name(
    "raster_clipped_setup_transfer_preregistration.json"
)
PREREGISTRATION_SHA256 = (
    "d89f55a9ba81280bdb7be4b0a93f841c736e07da0fbdfcde0f9d5a8e5b557ad7"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def uint32_sha256(values: tuple[int, ...] | list[int]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(struct.pack("<I", value))
    return digest.hexdigest()


def float32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


@functools.cache
def load_selectors() -> tuple[int, ...]:
    compressed = SELECTOR_PATH.read_bytes()
    if (
        len(compressed) != SELECTOR_COMPRESSED_BYTES
        or sha256_bytes(compressed) != SELECTOR_COMPRESSED_SHA256
    ):
        raise ValueError("compressed resolved selector table differs")
    raw = zlib.decompress(compressed)
    if len(raw) != SELECTOR_RAW_BYTES or sha256_bytes(raw) != SELECTOR_RAW_SHA256:
        raise ValueError("resolved selector table differs")
    values = tuple(value for (value,) in struct.iter_unpack("<I", raw))
    if len(values) != CASE_COUNT:
        raise ValueError("resolved selector count differs")
    return values


def scaled_delta_bits(width_index: int, variant_index: int, significand: int) -> int:
    variant = VARIANTS[variant_index]
    return selector.scaled_delta_bits(width_index, significand) - (
        int(variant["xExponentShift"]) << 23
    )


def endpoint_bits(
    width_index: int,
    variant_index: int,
    significand: int,
) -> tuple[int, int]:
    delta_bits = scaled_delta_bits(width_index, variant_index, significand)
    if not bool(VARIANTS[variant_index]["centeredVarying"]):
        return 0, delta_bits
    half_bits = delta_bits - (1 << 23)
    return half_bits | 0x8000_0000, half_bits


def fixed_geometry(
    width: int,
    height: int,
    variant_index: int,
) -> tuple[int, int, int, int]:
    variant = VARIANTS[variant_index]
    width_fixed = width << (8 - int(variant["xExponentShift"]))
    height_fixed = height * int(variant["heightScale"]) * 256
    center_x_fixed = int(CENTER_X * 256)
    center_y_fixed = int(CENTER_Y * 256)
    return (
        center_x_fixed - width_fixed // 2,
        center_x_fixed + width_fixed // 2,
        center_y_fixed - height_fixed // 2,
        center_y_fixed + height_fixed // 2,
    )


def expected_slope_bits(
    selectors: tuple[int, ...],
    *,
    width_index: int,
    height_index: int,
    witness_index: int,
) -> int:
    width = WIDTHS[width_index]
    height = HEIGHTS[height_index]
    reciprocal = selectors[width_index * HEIGHT_COUNT + height_index]
    return two_stage.slope_bits(
        selector.scaled_delta_bits(
            width_index,
            WITNESS_SIGNIFICANDS[witness_index],
        ),
        opposite_edge=height,
        determinant=width * height,
        reciprocal_index=reciprocal,
        first_stage_bias_units=two_stage.FIRST_STAGE_BIAS_UNITS[0],
    )


@functools.cache
def predicted_layout() -> JsonObject:
    selectors = load_selectors()
    geometry_digest = hashlib.sha256()
    endpoint_digest = hashlib.sha256()
    base_slope_digest = hashlib.sha256()
    coefficient_variant_digest = hashlib.sha256()
    direct_offset_distribution: Counter[int] = Counter()
    extent_x = [1 << 30, -(1 << 30)]
    extent_y = [1 << 30, -(1 << 30)]
    minimum_sample_boundary_margin = 1 << 30
    clip_classification: Counter[str] = Counter()

    for width_index, width in enumerate(WIDTHS):
        for height in HEIGHTS:
            for variant_index, variant in enumerate(VARIANTS):
                left, right, top, bottom = fixed_geometry(
                    width,
                    height,
                    variant_index,
                )
                geometry_digest.update(struct.pack("<4i", left, right, top, bottom))
                extent_x[0] = min(extent_x[0], left)
                extent_x[1] = max(extent_x[1], right)
                extent_y[0] = min(extent_y[0], top)
                extent_y[1] = max(extent_y[1], bottom)
                x_clipped = left < 0 or right > TARGET_WIDTH * 256
                y_clipped = top < 0 or bottom > TARGET_HEIGHT * 256
                if x_clipped != bool(variant["xClipped"]) or y_clipped != bool(
                    variant["yClipped"]
                ):
                    raise ValueError("clip classification differs")
                clip_classification[f"x{int(x_clipped)}y{int(y_clipped)}"] += 1
                for sample_x in SAMPLE_XS:
                    sample_x_fixed = sample_x * 256 + 128
                    sample_y_fixed = SAMPLE_Y * 256 + 128
                    minimum_sample_boundary_margin = min(
                        minimum_sample_boundary_margin,
                        sample_x_fixed - left,
                        right - sample_x_fixed,
                        sample_y_fixed - top,
                        bottom - sample_y_fixed,
                    )
        for significand in WITNESS_SIGNIFICANDS:
            for variant_index in range(VARIANT_COUNT):
                endpoint_digest.update(
                    struct.pack(
                        "<2I",
                        *endpoint_bits(width_index, variant_index, significand),
                    )
                )
        for height_index, height in enumerate(HEIGHTS):
            for witness_index, significand in enumerate(WITNESS_SIGNIFICANDS):
                expected = expected_slope_bits(
                    selectors,
                    width_index=width_index,
                    height_index=height_index,
                    witness_index=witness_index,
                )
                base_slope_digest.update(struct.pack("<I", expected))
                for _variant in VARIANTS:
                    coefficient_variant_digest.update(struct.pack("<I", expected))
                direct = factorization.top_left.arithmetic.float32_bits(
                    factorization.top_left.arithmetic.float32_value(
                        selector.scaled_delta_bits(width_index, significand)
                    )
                    / width
                )
                direct_offset_distribution[expected - direct] += 1

    if base_slope_digest.hexdigest() != EXPECTED_BASE_SLOPE_SHA256:
        raise ValueError("base slope table differs")
    sample_words = [SAMPLE_Y, *SAMPLE_XS]
    variant_words = [
        value
        for variant in VARIANTS
        for value in (
            int(variant["xExponentShift"]),
            int(variant["heightScale"]),
            int(bool(variant["centeredVarying"])),
            int(bool(variant["xClipped"])),
            int(bool(variant["yClipped"])),
        )
    ]
    return {
        "widthCount": WIDTH_COUNT,
        "heightCount": HEIGHT_COUNT,
        "witnessCount": WITNESS_COUNT,
        "variantCount": VARIANT_COUNT,
        "caseCount": CASE_COUNT,
        "coefficientCount": COEFFICIENT_COUNT,
        "coefficientVariantCount": COEFFICIENT_VARIANT_COUNT,
        "samplePositionCount": SAMPLE_POSITION_COUNT,
        "recordCount": RECORD_COUNT,
        "rawBytes": RAW_BYTES,
        "widthsSha256": uint32_sha256(WIDTHS),
        "heightsSha256": uint32_sha256(list(HEIGHTS)),
        "witnessSignificandsSha256": uint32_sha256(list(WITNESS_SIGNIFICANDS)),
        "sampleCoordinatesSha256": uint32_sha256(sample_words),
        "variantWordsSha256": uint32_sha256(variant_words),
        "fixedGeometrySha256": geometry_digest.hexdigest(),
        "endpointBitsSha256": endpoint_digest.hexdigest(),
        "baseSlopeTableSha256": base_slope_digest.hexdigest(),
        "coefficientVariantPredictionSha256": (coefficient_variant_digest.hexdigest()),
        "resolvedSelectorTableSha256": SELECTOR_RAW_SHA256,
        "expectedSlopeOffsetFromDirectDistribution": {
            str(key): value for key, value in sorted(direct_offset_distribution.items())
        },
        "fixedCoordinateExtent": {
            "minimumX": extent_x[0],
            "maximumX": extent_x[1],
            "minimumY": extent_y[0],
            "maximumY": extent_y[1],
            "unitsPerPixel": 256,
        },
        "minimumSampleBoundaryMarginFixed": minimum_sample_boundary_margin,
        "clipClassification": {
            key: value for key, value in sorted(clip_classification.items())
        },
        "syntheticCenteredUniqueCoefficientCount": COEFFICIENT_COUNT,
    }


def load_preregistration() -> JsonObject:
    preregistration: JsonObject = json.loads(
        PREREGISTRATION_PATH.read_text(encoding="utf-8")
    )
    if (
        sha256_path(PREREGISTRATION_PATH) != PREREGISTRATION_SHA256
        or preregistration.get("schemaVersion") != 1
        or preregistration.get("role") != ROLE
        or preregistration.get("observedAtPreregistration") is not False
        or preregistration.get("frozenLayout") != predicted_layout()
    ):
        raise ValueError("clipped-setup preregistration differs")
    return preregistration


def validate_manifest(root: Path) -> tuple[JsonObject, Path]:
    manifest_path = root / "manifest.json"
    manifest: JsonObject = json.loads(manifest_path.read_text(encoding="utf-8"))
    evidence = manifest.get("rasterClippedSetupTransfer", {})
    raw_path = root / str(evidence.get("file", ""))
    if (
        manifest.get("schemaVersion") != SCHEMA_VERSION
        or manifest.get("rigVersion") != RIG_VERSION
        or not isinstance(manifest.get("ciCommit"), str)
        or len(str(manifest.get("ciCommit"))) != 40
        or evidence.get("role") != ROLE
        or evidence.get("preregistrationFile")
        != "Analysis/raster_clipped_setup_transfer_preregistration.json"
        or evidence.get("preregistrationSha256") != PREREGISTRATION_SHA256
        or evidence.get("layout") != predicted_layout()
        or evidence.get("targetWidth") != TARGET_WIDTH
        or evidence.get("targetHeight") != TARGET_HEIGHT
        or evidence.get("viewportWidth") != VIEWPORT_WIDTH
        or evidence.get("center") != [CENTER_X, CENTER_Y]
        or evidence.get("sampleY") != SAMPLE_Y
        or evidence.get("sampleXs") != list(SAMPLE_XS)
        or evidence.get("pullOffsets") != list(PULL_OFFSETS)
        or evidence.get("variants") != list(VARIANTS)
        or evidence.get("heights") != list(HEIGHTS)
        or evidence.get("witnessSignificands") != list(WITNESS_SIGNIFICANDS)
        or evidence.get("batchWidthCount") != BATCH_WIDTH_COUNT
        or evidence.get("recordBytes") != RECORD.size
        or evidence.get("bytes") != RAW_BYTES
        or not raw_path.is_file()
        or raw_path.stat().st_size != RAW_BYTES
        or evidence.get("sha256") != sha256_path(raw_path)
    ):
        raise ValueError("clipped-setup manifest differs")
    return manifest, raw_path


def finite_float_bits(bits: int) -> bool:
    return bits & 0x7F80_0000 != 0x7F80_0000


def coefficient_records(
    data: bytes,
    *,
    coefficient_index: int,
    variant_index: int,
) -> tuple[tuple[int, int], ...]:
    first = (coefficient_index * VARIANT_COUNT + variant_index) * (
        SAMPLE_POSITION_COUNT * RECORD.size
    )
    return tuple(
        RECORD.unpack_from(data, first + sample_index * RECORD.size)
        for sample_index in range(SAMPLE_POSITION_COUNT)
    )


def accepted_slopes(
    records: tuple[tuple[int, int], ...],
    *,
    expected_bits: int,
) -> tuple[int, ...]:
    if any(
        record == SENTINEL
        or not all(finite_float_bits(component) for component in record)
        for record in records
    ):
        return ()
    groups = (
        tuple(
            (position, pull)
            for sample_index, position in ((0, 0.0), (1, 30.0))
            for position, pull in (
                (position, records[sample_index][0]),
                (position + PULL_OFFSETS[1], records[sample_index][1]),
            )
        ),
        tuple(
            (position, pull)
            for sample_index, position in ((2, 0.0), (3, 30.0))
            for position, pull in (
                (position, records[sample_index][0]),
                (position + PULL_OFFSETS[1], records[sample_index][1]),
            )
        ),
    )
    return tuple(
        candidate
        for candidate in range(
            expected_bits - CANDIDATE_RADIUS_FLOAT_ULPS,
            expected_bits + CANDIDATE_RADIUS_FLOAT_ULPS + 1,
        )
        if all(
            factorization.top_left.factorized.shared_plane_accepts_slope(
                candidate,
                observations=list(group),
            )
            for group in groups
        )
    )


def counter_json(counter: Counter[int | str]) -> JsonObject:
    return {
        str(key): value
        for key, value in sorted(counter.items(), key=lambda item: str(item[0]))
    }


def validate(root: Path) -> JsonObject:
    load_preregistration()
    manifest, raw_path = validate_manifest(root)
    data = raw_path.read_bytes()
    selectors = load_selectors()
    multiplicity_by_variant = {str(variant["name"]): Counter() for variant in VARIANTS}
    exact_match_by_variant: Counter[str] = Counter()
    failure_count_by_variant: Counter[str] = Counter()
    recovered_digests = {str(variant["name"]): hashlib.sha256() for variant in VARIANTS}
    first_failures: list[JsonObject] = []

    for width_index, width in enumerate(WIDTHS):
        for height_index, height in enumerate(HEIGHTS):
            for witness_index, significand in enumerate(WITNESS_SIGNIFICANDS):
                coefficient_index = (
                    width_index * HEIGHT_COUNT + height_index
                ) * WITNESS_COUNT + witness_index
                expected = expected_slope_bits(
                    selectors,
                    width_index=width_index,
                    height_index=height_index,
                    witness_index=witness_index,
                )
                for variant_index, variant in enumerate(VARIANTS):
                    name = str(variant["name"])
                    records = coefficient_records(
                        data,
                        coefficient_index=coefficient_index,
                        variant_index=variant_index,
                    )
                    accepted = accepted_slopes(records, expected_bits=expected)
                    multiplicity_by_variant[name][len(accepted)] += 1
                    exact = expected in accepted
                    exact_match_by_variant[name] += exact
                    if bool(variant["centeredVarying"]) and len(accepted) == 1:
                        recovered_digests[name].update(struct.pack("<I", accepted[0]))
                    else:
                        recovered_digests[name].update(struct.pack("<I", 0xFFFF_FFFF))
                    if not exact or (
                        bool(variant["centeredVarying"]) and accepted != (expected,)
                    ):
                        failure_count_by_variant[name] += 1
                        if len(first_failures) < 64:
                            first_failures.append(
                                {
                                    "width": width,
                                    "height": height,
                                    "witnessIndex": witness_index,
                                    "significand": significand,
                                    "variant": name,
                                    "expectedSlopeBits": expected,
                                    "acceptedOffsets": [
                                        value - expected for value in accepted
                                    ],
                                    "records": [list(record) for record in records],
                                }
                            )

    baseline_name = str(VARIANTS[0]["name"])
    baseline_gate = (
        exact_match_by_variant[baseline_name] == COEFFICIENT_COUNT
        and failure_count_by_variant[baseline_name] == 0
    )
    centered_variant_names = [
        str(variant["name"]) for variant in VARIANTS if bool(variant["centeredVarying"])
    ]
    centered_gates = {
        name: (
            multiplicity_by_variant[name] == Counter({1: COEFFICIENT_COUNT})
            and exact_match_by_variant[name] == COEFFICIENT_COUNT
            and recovered_digests[name].hexdigest() == EXPECTED_BASE_SLOPE_SHA256
        )
        for name in centered_variant_names
    }
    control_gate = baseline_gate and centered_gates["unclipped-centered-control"]
    clipped_gate = control_gate and all(
        centered_gates[name]
        for name in (
            "x-clipped-centered",
            "y-clipped-centered",
            "xy-clipped-centered",
        )
    )
    valid = clipped_gate
    return {
        "liquidGlassRasterClippedSetupTransferValidationSchemaVersion": 1,
        "classification": ROLE,
        "probe": str(root),
        "ciCommit": manifest.get("ciCommit"),
        "manifestSha256": sha256_path(root / "manifest.json"),
        "rawSha256": sha256_path(raw_path),
        "preregistrationSha256": PREREGISTRATION_SHA256,
        "measurement": {
            "coefficientCountPerVariant": COEFFICIENT_COUNT,
            "coefficientVariantCount": COEFFICIENT_VARIANT_COUNT,
            "candidateMultiplicityByVariant": {
                name: counter_json(counter)
                for name, counter in multiplicity_by_variant.items()
            },
            "expectedSlopeAcceptedCountByVariant": dict(exact_match_by_variant),
            "failureCountByVariant": dict(failure_count_by_variant),
            "recoveredSlopeTableSha256ByCenteredVariant": {
                name: recovered_digests[name].hexdigest()
                for name in centered_variant_names
            },
            "zeroOriginPowerScaleControlGate": baseline_gate,
            "centeredVaryingControlGate": centered_gates["unclipped-centered-control"],
            "centeredVariantGates": centered_gates,
            "axisIsolatedClippedSetupGate": clipped_gate,
            "captureValidForComparison": valid,
            "firstFailures": first_failures,
        },
        "conclusions": {
            "powerScaledUnclippedArithmeticTransferred": baseline_gate,
            "varyingTranslationPreservesSetupCoefficient": centered_gates[
                "unclipped-centered-control"
            ],
            "xClippedSetupEstablished": centered_gates["x-clipped-centered"],
            "yClippedSetupEstablished": centered_gates["y-clipped-centered"],
            "xyClippedSetupEstablished": centered_gates["xy-clipped-centered"],
            "clippedSetupEstablished": clipped_gate,
            "portableCompactSelectorLawEstablished": False,
            "endToEndLiquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.root is None:
        print(json.dumps(predicted_layout(), indent=2, sort_keys=True))
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
