#!/usr/bin/env python3
"""Open callback-retry run 31059860458 without relabelling its red gate.

The frozen holdout predicted the binary64 rectangle found at the one
LayerShapes-pointer-correlated store.  That store is a downstream integer
mirror, so the prospective validator correctly rejected the run.  The same
capture also retained the actual floating producer two structural store
records earlier.  This analyzer validates all inherited evidence, opens that
producer by event/role/depth relationships only, and measures candidate
arithmetic without tolerances or value-based selection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import analyze_prepare_layer_crop_union_operand_matrix as crop_analysis
import validate_prepare_layer_crop_policy_holdout as holdout_validator
import validate_prepare_layer_crop_transfer as crop_validator


ANALYSIS_SCHEMA_VERSION = 1
RUN_ID = 31_059_860_458
HEAD_SHA = "6ff54c6bd01e6dea04002ca8c11fd1c0f7e4852c"
WORKFLOW_PATH = (
    ".github/workflows/prepare-layer-crop-policy-holdout-callback-retry.yml"
)
TRACE_FILE_NAME = "prepare-layer-crop-policy-holdout-trace.json"
TIMELINE_FILE_NAME = "transition-timeline.json"
ORIGINAL_PROSPECTIVE_FLOAT_ERROR = "public crop producer replay differs"
ORIGINAL_PROSPECTIVE_TOPOLOGY_ERROR = (
    "qualified normal-render recursion topology differs"
)
OPENED_OVERSIZED_TOPOLOGY = (3,) * 32
TRUE_PRODUCER_STORE_INDEX_DELTA = 2
TRUE_PRODUCER_ROLE_DELTA = 0xFB0
TRUE_PRODUCER_DEPTH_DELTA = 2
PRODUCTION_SHADER_SHA256 = (
    "6489828f12de599da9633d6183266a81b71ed846a1b03c03cb4eb9c23639352d"
)

ROLE_TRANSFORM_OFFSET = 0x330
ROLE_TRANSFORM_COMPONENT_COUNT = 16
ROLE_TRANSFORMED_DYNAMIC_BOUNDS_OFFSET = 0x580
ROLE_SHADOW_OFFSET_OFFSET = 0x5E0
ROLE_CARRIER_TRANSLATION_OFFSET = 0x5F0
ROLE_NOMINAL_SHAPE_OFFSET = 0x600
ROLE_DYNAMIC_LOCAL_BOUNDS_OFFSET = 0x620
ROLE_RECURSIVE_CHILD_OFFSET = 0x640

type RectF64 = tuple[float, float, float, float]
type RectI32 = tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class ArtifactSpec:
    geometry: str
    artifact_id: int
    artifact_name: str
    artifact_size: int
    artifact_digest: str
    trace_sha256: str
    timeline_sha256: str
    opened_topology: tuple[int, ...] | None = None


EXPECTED_ARTIFACTS: dict[str, ArtifactSpec] = {
    "holdout-065-center": ArtifactSpec(
        "circle-065-center",
        8_951_719_063,
        "liquid-glass-prepare-layer-crop-policy-callback-retry-"
        "holdout-065-center-31059860458",
        87_263_763,
        "sha256:f0cd63e27937306a3c5158bdf466ab9c979c68bae29f9d02340fc99a3ec55e39",
        "5c70a3ab7fe96c5952776d1ba51b68da0974bd297f2e743a31de0deb6af9cea7",
        "9aa0455c960abcfc6c66c42625c195dc593dfc63196d715028e3e837f86a5f24",
    ),
    "holdout-096-padx-453": ArtifactSpec(
        "circle-096-padx-453",
        8_951_801_447,
        "liquid-glass-prepare-layer-crop-policy-callback-retry-"
        "holdout-096-padx-453-31059860458",
        87_358_221,
        "sha256:c479d967a74a4024bad126dd4a3b7555289bf1300455c9b7043928cd51ad1e0f",
        "57d9206150e9656c4702576e721b2272508da2e5b21643134cd1ba3e2b6a7dba",
        "845b566d2f29df17c8fcd858052e16b7137398336744a85206ce630573a9a936",
    ),
    "holdout-1025-center": ArtifactSpec(
        "circle-1025-center",
        8_951_806_341,
        "liquid-glass-prepare-layer-crop-policy-callback-retry-"
        "holdout-1025-center-31059860458",
        103_635_380,
        "sha256:b9fd004c6f893e1f00dfc3e751c6da7b2ac104622ea905ca01ee72787ac35aa6",
        "f9dd25cf5a4ee8902b7b544843d74e60aff5eb8a8ce0f0b1d177c8cfad979030",
        "5443a588472cc36ef279c2c9355452b185a667012e630114ee675d2be3051a71",
    ),
    "holdout-2048-center": ArtifactSpec(
        "circle-2048-center",
        8_951_736_947,
        "liquid-glass-prepare-layer-crop-policy-callback-retry-"
        "holdout-2048-center-31059860458",
        101_546_167,
        "sha256:952d05be9f745d08f4affaf4a7da7fc5e3eb3e2bab5a283c6a31088ed2074b16",
        "9e1e75956f0c0f57ca852c821c5f4ddf20c0d6b946c22e3c70302fed4d24f33f",
        "6522b63a65d23af765ad51e067fb09fb736c7c348fe24b900b5f74670087361d",
        OPENED_OVERSIZED_TOPOLOGY,
    ),
    "holdout-256-crop-d": ArtifactSpec(
        "circle-256-crop-d",
        8_951_804_974,
        "liquid-glass-prepare-layer-crop-policy-callback-retry-"
        "holdout-256-crop-d-31059860458",
        89_011_872,
        "sha256:6bbb956cfc15c92d076f1f2b05b62cf2dccd567197266992d03cbdf11f39bff4",
        "95acf6ddeba60aa19a6ed73dde8e36df88f6a342fab02284911cf198bf1b5b3f",
        "bedf32451f63ad3d9a9ebddd75bbe24955dbd372ac3397aec13540fed921ccc3",
    ),
    "holdout-343-center": ArtifactSpec(
        "circle-343-center",
        8_951_739_015,
        "liquid-glass-prepare-layer-crop-policy-callback-retry-"
        "holdout-343-center-31059860458",
        89_995_537,
        "sha256:8f1fb5ce1936f232623a22fb7f794e4e7f571bb6bee138ed13f459e7e6e1a65c",
        "7b3de26b11840ed79528ca576ff55bc8da3cd1334bd2d63cce0699f9109b9932",
        "67aad095d5f92d5456ece7f18e3d18f32a798ca54230cf29781c33e3988099c9",
    ),
    "holdout-513-center": ArtifactSpec(
        "circle-513-center",
        8_951_718_689,
        "liquid-glass-prepare-layer-crop-policy-callback-retry-"
        "holdout-513-center-31059860458",
        93_101_176,
        "sha256:473bb9ed0cab758b0932045f33712c6c2a64c51ca53185b90ea50b23a4647c2d",
        "6a11a7c44b30a3097d9c3eaeee4633b9de4253e557511acd6ee5ccf45faed663",
        "fbc698a3a4aaabb96593a235b2e367b31d95f83f587358bfc0acfe47cab5af70",
    ),
    "holdout-769-center": ArtifactSpec(
        "circle-769-center",
        8_951_727_258,
        "liquid-glass-prepare-layer-crop-policy-callback-retry-"
        "holdout-769-center-31059860458",
        98_408_881,
        "sha256:b37429c3e2fa5c8b54595e275f90574389b148da1947c4b817e258f27c724751",
        "adf2f75972dcbd9bb810b77c317eead05abe958668ac902af34cf73ef2fe8e4a",
        "9c10c80d40c19712cd26b28a967e1db3d805a0049b8f3745b32315d5bd10c7dd",
    ),
}


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} is not an object")
    return value


def sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{label} is not an array")
    return value


def integer(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} is not an integer")
    return value


def finite(value: Any, label: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(result := float(value))
    ):
        raise ValueError(f"{label} is not finite")
    return result


def finite_rect(value: Any, label: str) -> RectF64:
    raw = sequence(value, label)
    if len(raw) != 4:
        raise ValueError(f"{label} component count differs")
    result = tuple(finite(component, label) for component in raw)
    return result  # type: ignore[return-value]


def f64_hex(values: Sequence[float]) -> str:
    return struct.pack(f"<{len(values)}d", *values).hex()


def same_f64(left: Sequence[float], right: Sequence[float]) -> bool:
    return f64_hex(left) == f64_hex(right)


def f64_bits(value: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", value))[0]


def ordered_f64_bits(value: float) -> int:
    bits = f64_bits(value)
    if bits >> 63:
        return (~bits) & ((1 << 64) - 1)
    return bits | (1 << 63)


@dataclass(slots=True)
class ExactMetric:
    rectangle_count: int = 0
    exact_rectangle_count: int = 0
    exact_component_counts: list[int] = field(default_factory=lambda: [0] * 4)
    maximum_absolute_errors: list[float] = field(default_factory=lambda: [0.0] * 4)
    maximum_ulp_distances: list[int] = field(default_factory=lambda: [0] * 4)

    def add(self, observed: RectF64, candidate: RectF64) -> bool:
        self.rectangle_count += 1
        exact = same_f64(observed, candidate)
        self.exact_rectangle_count += int(exact)
        for index, (actual, predicted) in enumerate(
            zip(observed, candidate, strict=True)
        ):
            if f64_bits(actual) == f64_bits(predicted):
                self.exact_component_counts[index] += 1
                continue
            self.maximum_absolute_errors[index] = max(
                self.maximum_absolute_errors[index], abs(actual - predicted)
            )
            self.maximum_ulp_distances[index] = max(
                self.maximum_ulp_distances[index],
                abs(ordered_f64_bits(actual) - ordered_f64_bits(predicted)),
            )
        return exact

    def result(self) -> dict[str, Any]:
        component_count = self.rectangle_count * 4
        exact_components = sum(self.exact_component_counts)
        return {
            "rectangleCount": self.rectangle_count,
            "exactRectangleCount": self.exact_rectangle_count,
            "mismatchedRectangleCount": (
                self.rectangle_count - self.exact_rectangle_count
            ),
            "componentCount": component_count,
            "exactComponentCount": exact_components,
            "mismatchedComponentCount": component_count - exact_components,
            "exactComponentCountsXYWH": self.exact_component_counts,
            "maximumAbsoluteErrorsXYWH": self.maximum_absolute_errors,
            "maximumULPDistancesXYWH": self.maximum_ulp_distances,
            "toleranceUsed": False,
        }


def local_coordinate_candidate(
    carrier_position: Sequence[Any],
    public_bounds: RectF64,
    recursive_child: RectF64,
    canvas_height: float,
    blur_radius: float,
    bleed_blur_radius: float,
) -> RectF64:
    """Evaluate the simplified candidate in LayerShapes local coordinates."""
    if len(carrier_position) != 2:
        raise ValueError("carrier position component count differs")
    position_x = finite(carrier_position[0], "carrier x")
    position_y = finite(carrier_position[1], "carrier y")
    expansion = 2.8 * max(2.0 * blur_radius, bleed_blur_radius)
    support = 9.0 + expansion

    query_x = public_bounds[0] - support
    query_width = public_bounds[2] + 2.0 * support
    lower_x = max(recursive_child[0], query_x)
    far_x = min(
        recursive_child[0] + recursive_child[2], query_x + query_width
    )

    query_y = public_bounds[1] - 9.0 - expansion
    query_height = public_bounds[3] + 26.0 + expansion
    lower_y = max(recursive_child[1], query_y)
    far_y = min(
        recursive_child[1] + recursive_child[3], query_y + query_height
    )
    return (
        position_x + lower_x,
        (canvas_height - position_y) - far_y,
        far_x - lower_x,
        far_y - lower_y,
    )


def require_original_prospective_failure(
    trace_path: Path, timeline_path: Path, spec: ArtifactSpec
) -> str:
    expected = (
        ORIGINAL_PROSPECTIVE_TOPOLOGY_ERROR
        if spec.opened_topology is not None
        else ORIGINAL_PROSPECTIVE_FLOAT_ERROR
    )
    try:
        holdout_validator.validate(trace_path, timeline_path, spec.geometry)
    except ValueError as error:
        if str(error) != expected:
            raise ValueError(
                f"{spec.geometry} prospective failure differs: {error}"
            ) from error
        return expected
    raise ValueError(f"{spec.geometry} unexpectedly passed its prospective gate")


def validate_base(
    trace_path: Path, timeline_path: Path, spec: ArtifactSpec
) -> Mapping[str, Any]:
    if spec.opened_topology is None:
        return crop_validator.validate(trace_path, timeline_path, spec.geometry)

    original = crop_validator.EXPECTED_NORMAL_PREPARE_RECURSION_DEPTHS
    if original != (3,) + (4,) * 31:
        raise ValueError("frozen normal topology constant differs")
    crop_validator.EXPECTED_NORMAL_PREPARE_RECURSION_DEPTHS = spec.opened_topology
    try:
        result = crop_validator.validate(trace_path, timeline_path, spec.geometry)
    finally:
        crop_validator.EXPECTED_NORMAL_PREPARE_RECURSION_DEPTHS = original
    return result


def role_payload(raw_store: Any, expected_address: int) -> bytes:
    store = mapping(raw_store, "raw producer store")
    address, payload = crop_validator.memory_snapshot(
        store.get("roleState"),
        crop_validator.ROLE_STATE_BYTE_COUNT,
        "producer role state",
        expected_address,
    )
    if address != expected_address:
        raise ValueError("producer role address differs")
    return payload


def role_intermediates(payload: bytes) -> dict[str, Any]:
    transform = struct.unpack_from(
        f"<{ROLE_TRANSFORM_COMPONENT_COUNT}d", payload, ROLE_TRANSFORM_OFFSET
    )
    transformed_dynamic = struct.unpack_from(
        "<4d", payload, ROLE_TRANSFORMED_DYNAMIC_BOUNDS_OFFSET
    )
    shadow_offset = struct.unpack_from("<d", payload, ROLE_SHADOW_OFFSET_OFFSET)[0]
    carrier_translation = struct.unpack_from(
        "<2d", payload, ROLE_CARRIER_TRANSLATION_OFFSET
    )
    nominal_shape = struct.unpack_from("<4d", payload, ROLE_NOMINAL_SHAPE_OFFSET)
    dynamic_local = struct.unpack_from(
        "<4d", payload, ROLE_DYNAMIC_LOCAL_BOUNDS_OFFSET
    )
    recursive_child = struct.unpack_from(
        "<4d", payload, ROLE_RECURSIVE_CHILD_OFFSET
    )
    values = (
        *transform,
        *transformed_dynamic,
        shadow_offset,
        *carrier_translation,
        *nominal_shape,
        *dynamic_local,
        *recursive_child,
    )
    if not all(math.isfinite(value) for value in values):
        raise ValueError("producer role intermediates are not finite")
    return {
        "transformF64": list(transform),
        "transformHex": f64_hex(transform),
        "transformedDynamicBoundsF64": list(transformed_dynamic),
        "transformedDynamicBoundsHex": f64_hex(transformed_dynamic),
        "shadowOffsetF64": shadow_offset,
        "shadowOffsetHex": f64_hex((shadow_offset,)),
        "carrierTranslationF64": list(carrier_translation),
        "carrierTranslationHex": f64_hex(carrier_translation),
        "nominalShapeF64": list(nominal_shape),
        "nominalShapeHex": f64_hex(nominal_shape),
        "dynamicLocalBoundsF64": list(dynamic_local),
        "dynamicLocalBoundsHex": f64_hex(dynamic_local),
        "recursiveChildF64": list(recursive_child),
        "recursiveChildHex": f64_hex(recursive_child),
    }


def validate_store_extension(
    trace: Mapping[str, Any],
    base_result: Mapping[str, Any],
    timeline: Mapping[str, Any],
    crop_records: Sequence[Any],
    label: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    extension = mapping(trace.get("cropPolicyHoldoutExtension"), "crop extension")
    if (
        extension.get("cropPolicyHoldoutExtensionSchemaVersion")
        != holdout_validator.EXTENSION_SCHEMA_VERSION
        or extension.get("configuration")
        != holdout_validator.EXPECTED_EXTENSION_CONFIGURATION
        or extension.get("status") != "finalized"
        or extension.get("statusBeforeFinalization") != "crop-policy-store-active"
    ):
        raise ValueError(f"{label} crop extension identity differs")

    prepare_start = integer(
        mapping(trace.get("prepareLayer"), "prepare layer").get("symbolStart"),
        "prepare start",
    )
    instruction_digest = hashlib.sha256(
        bytes.fromhex(holdout_validator.STORE_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX)
    ).hexdigest()
    if (
        extension.get("prepareLayerSymbolStart") != prepare_start
        or integer(extension.get("storeBreakpointID"), "store breakpoint") <= 0
        or extension.get("storeInstructionSHA256") != instruction_digest
    ):
        raise ValueError(f"{label} crop store instruction identity differs")

    raw_stores = sequence(extension.get("storeRecords"), "store records")
    if not 32 <= len(raw_stores) <= holdout_validator.MAXIMUM_QUALIFIED_STORE_RECORD_COUNT:
        raise ValueError(f"{label} qualified store bounds differ")
    stores = [
        holdout_validator.validate_store_record(raw, index, prepare_start)
        for index, raw in enumerate(raw_stores)
    ]
    hit_indices = [record["storeHitIndex"] for record in stores]
    if hit_indices != sorted(hit_indices) or len(set(hit_indices)) != len(hit_indices):
        raise ValueError(f"{label} qualified store hit order differs")

    rejected = integer(extension.get("finalRejectedStoreCount"), "rejected stores")
    grouped_rejections = 0
    for raw_group in sequence(extension.get("rejectionGroups"), "store rejections"):
        group = mapping(raw_group, "store rejection group")
        if group.get("reason") != "caller-chain-excluded":
            raise ValueError(f"{label} store rejection reason differs")
        integer(group.get("prepareRecursionDepth"), "store rejection depth")
        grouped_rejections += integer(group.get("hitCount"), "store rejection count")
    if (
        rejected != grouped_rejections
        or extension.get("finalQualifiedStoreRecordCount") != len(stores)
        or extension.get("finalStoreHitCount") != len(stores) + rejected
    ):
        raise ValueError(f"{label} store accounting differs")

    links = sequence(extension.get("markerLinks"), "store links")
    marker_records = sequence(trace.get("qualifiedRecords"), "marker records")
    union_extension = mapping(
        trace.get("cropUnionOperandExtension"), "union extension"
    )
    raw_union_records = sequence(union_extension.get("unionRecords"), "union records")
    union_links = sequence(union_extension.get("markerLinks"), "union links")
    public_records = sequence(base_result.get("records"), "base public records")
    timeline_records = sequence(
        mapping(timeline.get("dynamicBackgroundUniforms"), "timeline uniforms").get(
            "records"
        ),
        "timeline records",
    )
    if not (
        len(links)
        == len(marker_records)
        == len(union_links)
        == len(public_records)
        == len(timeline_records)
        == len(crop_records)
        == 32
    ) or extension.get("finalMarkerLinkCount") != 32:
        raise ValueError(f"{label} marker-link inventory differs")

    joined: list[dict[str, Any]] = []
    previous_end = 0
    canvas_height = finite(
        mapping(base_result.get("geometry"), "geometry").get("windowHeight"),
        "canvas height",
    )
    geometry_width = finite(
        mapping(base_result.get("geometry"), "geometry").get("width"),
        "geometry width",
    )
    geometry_height = finite(
        mapping(base_result.get("geometry"), "geometry").get("height"),
        "geometry height",
    )
    for index, (
        raw_link,
        raw_marker,
        raw_union_link,
        raw_crop,
        raw_public,
        raw_timeline,
    ) in enumerate(
        zip(
            links,
            marker_records,
            union_links,
            crop_records,
            public_records,
            timeline_records,
            strict=True,
        )
    ):
        link = mapping(raw_link, f"{label} store link {index + 1}")
        marker = mapping(raw_marker, f"{label} marker {index + 1}")
        union_link = mapping(raw_union_link, f"{label} union link {index + 1}")
        crop = mapping(raw_crop, f"{label} crop record {index + 1}")
        public = mapping(raw_public, f"{label} public record {index + 1}")
        timeline_record = mapping(
            raw_timeline, f"{label} timeline record {index + 1}"
        )
        start = integer(link.get("startStoreRecordIndex"), "store link start")
        end = integer(link.get("endStoreRecordIndexExclusive"), "store link end")
        union_indices = list(
            sequence(
                union_link.get("matchingUnionRecordIndices"), "matching unions"
            )
        )
        if len(union_indices) != 2:
            raise ValueError(f"{label} sample {index + 1} union topology differs")
        selected_union_index = integer(union_indices[-1], "selected union index")
        selected_union = mapping(
            raw_union_records[selected_union_index], "selected union"
        )
        selected_layer_shapes = integer(
            mapping(
                selected_union.get("frameIdentity"), "selected union identity"
            ).get("layerShapesBase"),
            "selected union LayerShapes base",
        )
        matching = list(
            sequence(link.get("matchingStoreRecordIndices"), "matching stores")
        )
        recomputed = [
            store["recordIndex"]
            for store in stores[start:end]
            if store["layerShapesBase"] == selected_layer_shapes
        ]
        embedded = mapping(marker.get("cropPolicyStoreWindow"), "store window")
        if (
            start != previous_end
            or not start < end <= len(stores)
            or link.get("selectedUnionRecordIndex") != selected_union_index
            or link.get("selectedLayerShapesBase") != selected_layer_shapes
            or matching != recomputed
            or len(matching) != 1
            or embedded.get("startRecordIndex") != start
            or embedded.get("endRecordIndexExclusive") != end
            or embedded.get("selectedUnionRecordIndex") != selected_union_index
            or embedded.get("selectedLayerShapesBase") != selected_layer_shapes
            or embedded.get("matchingStoreRecordIndices") != matching
        ):
            raise ValueError(f"{label} sample {index + 1} pointer link differs")

        mirror_index = integer(matching[0], "mirror store index")
        producer_index = mirror_index - TRUE_PRODUCER_STORE_INDEX_DELTA
        if producer_index < start:
            raise ValueError(f"{label} sample {index + 1} producer leaves window")
        mirror = stores[mirror_index]
        producer = stores[producer_index]
        if (
            producer["recordIndex"] + TRUE_PRODUCER_STORE_INDEX_DELTA
            != mirror["recordIndex"]
            or producer["roleBase"] + TRUE_PRODUCER_ROLE_DELTA
            != mirror["roleBase"]
            or producer["prepareRecursionDepth"]
            != mirror["prepareRecursionDepth"] + TRUE_PRODUCER_DEPTH_DELTA
        ):
            raise ValueError(
                f"{label} sample {index + 1} structural producer differs"
            )

        observed_crop = tuple(integer(value, "observed crop") for value in sequence(
            crop.get("observedNestedInputI32"), "observed crop"
        ))
        if len(observed_crop) != 4:
            raise ValueError(f"{label} sample {index + 1} crop size differs")
        producer_working = tuple(producer["workingCropI32"])
        mirror_working = tuple(mirror["workingCropI32"])
        mirror_float = finite_rect(mirror["floatingInputF64"], "mirror float")
        producer_float = finite_rect(
            producer["floatingInputF64"], "producer float"
        )
        integer_mirror = tuple(float(value) for value in observed_crop)
        if (
            producer_working != observed_crop
            or mirror_working != observed_crop
            or not same_f64(mirror_float, integer_mirror)
        ):
            raise ValueError(f"{label} sample {index + 1} integer mirror differs")
        viewport = tuple(
            integer(value, "viewport component")
            for value in sequence(crop.get("viewportI32"), "viewport")
        )
        producer_enclosure = crop_analysis.integer_crop(producer_float)
        producer_crop = crop_analysis.intersect_i32(
            producer_enclosure, viewport  # type: ignore[arg-type]
        )
        if producer_crop != observed_crop:
            raise ValueError(
                f"{label} sample {index + 1} producer integerization differs"
            )

        layer = crop_analysis.public_layer(timeline_record)
        bounds = finite_rect(layer.get("bounds"), "public bounds")
        filter_values = mapping(
            mapping(timeline_record.get("filter"), "background filter").get(
                "inputValues"
            ),
            "filter inputs",
        )
        blur = finite(filter_values.get("inputBlurRadius"), "blur radius")
        bleed_blur = finite(
            filter_values.get("inputBleedBlurRadius"), "bleed blur radius"
        )
        recursive_child = finite_rect(
            mapping(public.get("private"), "private record").get(
                "recursiveChildF64"
            ),
            "recursive child",
        )
        carrier_position = sequence(public.get("carrierPosition"), "carrier position")
        global_candidate = finite_rect(
            crop.get("candidateIntersectionF64"), "global candidate"
        )
        local_candidate = local_coordinate_candidate(
            carrier_position,
            bounds,
            recursive_child,
            canvas_height,
            blur,
            bleed_blur,
        )

        payload = role_payload(raw_stores[producer_index], producer["roleBase"])
        intermediates = role_intermediates(payload)
        transform = tuple(intermediates["transformF64"])
        transformed_dynamic = tuple(intermediates["transformedDynamicBoundsF64"])
        shadow_offset = finite(intermediates["shadowOffsetF64"], "shadow offset")
        carrier_translation = tuple(intermediates["carrierTranslationF64"])
        nominal_shape = tuple(intermediates["nominalShapeF64"])
        dynamic_local = tuple(intermediates["dynamicLocalBoundsF64"])
        role_child = tuple(intermediates["recursiveChildF64"])
        position_x = finite(carrier_position[0], "carrier x")
        position_y = finite(carrier_position[1], "carrier y")
        public_transformed_dynamic = (
            position_x + bounds[0],
            (canvas_height - position_y) - (bounds[1] + bounds[3]),
            bounds[2],
            bounds[3],
        )
        public_translation = (-position_x, canvas_height - position_y)
        expected_dynamic_local = (0.0, -0.0, bounds[2], bounds[3])
        expected_role_child = (
            nominal_shape[0],
            nominal_shape[1],
            nominal_shape[2],
            nominal_shape[3] + shadow_offset,
        )
        expected_nominal_shape = (
            0.0,
            0.0,
            geometry_width,
            geometry_height,
        )
        relation_flags = {
            "matrixTranslationMatchesPublicBoundsBitwise": same_f64(
                transform[12:14], bounds[:2]
            ),
            "transformedDynamicMatchesCollapsedPublicTransformBitwise": same_f64(
                transformed_dynamic, public_transformed_dynamic
            ),
            "shadowOffsetIsEightBitwise": same_f64((shadow_offset,), (8.0,)),
            "carrierTranslationMatchesPublicBitwise": same_f64(
                carrier_translation, public_translation
            ),
            "nominalShapeMatchesPublicGeometryBitwise": same_f64(
                nominal_shape, expected_nominal_shape
            ),
            "dynamicLocalMatchesPublicBoundsBitwise": same_f64(
                dynamic_local, expected_dynamic_local
            ),
            "recursiveChildIsNominalPlusShadowBitwise": same_f64(
                role_child, expected_role_child
            ),
        }
        joined.append(
            {
                "label": label,
                "geometry": mapping(base_result.get("geometry"), "geometry").get(
                    "name"
                ),
                "sampleIndex": index + 1,
                "storeWindow": [start, end],
                "pointerCorrelatedMirrorStoreIndex": mirror_index,
                "structuralProducerStoreIndex": producer_index,
                "mirrorRoleBase": mirror["roleBase"],
                "producerRoleBase": producer["roleBase"],
                "mirrorPrepareRecursionDepth": mirror["prepareRecursionDepth"],
                "producerPrepareRecursionDepth": producer["prepareRecursionDepth"],
                "observedProducerF64": list(producer_float),
                "observedProducerHex": f64_hex(producer_float),
                "globalCandidateF64": list(global_candidate),
                "globalCandidateHex": f64_hex(global_candidate),
                "globalCandidateExact": same_f64(producer_float, global_candidate),
                "localCandidateF64": list(local_candidate),
                "localCandidateHex": f64_hex(local_candidate),
                "localCandidateExact": same_f64(producer_float, local_candidate),
                "producerEnclosureI32": list(producer_enclosure),
                "viewportI32": list(viewport),
                "observedCropI32": list(observed_crop),
                "roleIntermediates": intermediates,
                "roleIntermediateRelations": relation_flags,
            }
        )
        previous_end = end

    trailing = len(stores) - previous_end
    if (
        extension.get("finalLinkedStoreRecordCount") != 32
        or extension.get("finalTrailingStoreRecordCount") != trailing
    ):
        raise ValueError(f"{label} trailing store accounting differs")
    return joined, {
        "storeRecordCount": len(stores),
        "rejectedStoreCount": rejected,
        "trailingStoreRecordCount": trailing,
    }


def relation_count(records: Sequence[Mapping[str, Any]], name: str) -> int:
    return sum(
        mapping(record.get("roleIntermediateRelations"), "role relations").get(name)
        is True
        for record in records
    )


def analyze(root: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    geometries: list[dict[str, Any]] = []
    prospective_failures: dict[str, str] = {}
    for label, spec in EXPECTED_ARTIFACTS.items():
        directory = root / label
        if not directory.is_dir():
            raise ValueError(f"{label} artifact directory is missing")
        trace_path = directory / TRACE_FILE_NAME
        timeline_path = directory / TIMELINE_FILE_NAME
        trace_digest = crop_analysis.sha256_file(trace_path)
        timeline_digest = crop_analysis.sha256_file(timeline_path)
        if (
            trace_digest != spec.trace_sha256
            or timeline_digest != spec.timeline_sha256
        ):
            raise ValueError(f"{label} frozen input hash differs")

        prospective_failures[label] = require_original_prospective_failure(
            trace_path, timeline_path, spec
        )
        base_result = validate_base(trace_path, timeline_path, spec)
        trace = mapping(crop_validator.load_json(trace_path, "trace"), "trace")
        timeline = mapping(
            crop_validator.load_json(timeline_path, "timeline"), "timeline"
        )
        observed_topology = tuple(
            integer(
                mapping(raw, "qualified marker").get("prepareRecursionDepth"),
                "marker depth",
            )
            for raw in sequence(trace.get("qualifiedRecords"), "qualified markers")
        )
        expected_opened = spec.opened_topology or (3,) + (4,) * 31
        if observed_topology != expected_opened:
            raise ValueError(f"{label} opened topology differs")
        crop_records, union_accounting = crop_analysis.validate_extension(
            trace, base_result, timeline, label
        )
        geometry_records, store_accounting = validate_store_extension(
            trace, base_result, timeline, crop_records, label
        )
        records.extend(geometry_records)
        geometries.append(
            {
                "label": label,
                "geometry": spec.geometry,
                "artifactID": spec.artifact_id,
                "artifactName": spec.artifact_name,
                "artifactSize": spec.artifact_size,
                "artifactDigest": spec.artifact_digest,
                "traceSHA256": trace_digest,
                "timelineSHA256": timeline_digest,
                "recordCount": len(geometry_records),
                "observedPrepareRecursionDepths": list(observed_topology),
                "openedTopologyVariant": spec.opened_topology is not None,
                "originalProspectiveFailure": prospective_failures[label],
                **union_accounting,
                **store_accounting,
            }
        )

    global_metric = ExactMetric()
    local_metric = ExactMetric()
    for record in records:
        observed = finite_rect(record["observedProducerF64"], "observed producer")
        global_metric.add(
            observed, finite_rect(record["globalCandidateF64"], "global candidate")
        )
        local_metric.add(
            observed, finite_rect(record["localCandidateF64"], "local candidate")
        )

    relation_names = (
        "matrixTranslationMatchesPublicBoundsBitwise",
        "transformedDynamicMatchesCollapsedPublicTransformBitwise",
        "shadowOffsetIsEightBitwise",
        "carrierTranslationMatchesPublicBitwise",
        "nominalShapeMatchesPublicGeometryBitwise",
        "dynamicLocalMatchesPublicBoundsBitwise",
        "recursiveChildIsNominalPlusShadowBitwise",
    )
    role_counts = {
        name: relation_count(records, name) for name in relation_names
    }
    return {
        "prepareLayerCropPolicyHoldoutCallbackRetryAnalysisSchemaVersion": (
            ANALYSIS_SCHEMA_VERSION
        ),
        "classification": (
            "retrospective opening of a prospectively failed callback-retry "
            "holdout; the original red gate is preserved, the upstream "
            "producer is selected only by store order, role delta, recursion "
            "depth, and marker interval, and every comparison is bitwise"
        ),
        "run": {
            "id": RUN_ID,
            "headSHA": HEAD_SHA,
            "workflowPath": WORKFLOW_PATH,
            "event": "workflow_dispatch",
            "runAttempt": 1,
            "status": "completed",
            "conclusion": "failure",
        },
        "prospectiveGatePassed": False,
        "originalProspectiveFailures": prospective_failures,
        "artifactCount": len(geometries),
        "geometryCount": len(geometries),
        "recordCount": len(records),
        "capturedProducerComponentCount": len(records) * 4,
        "geometryResults": geometries,
        "openedProducerSelection": {
            "pointerCorrelatedStoreMeaning": (
                "downstream binary64 mirror of the signed integer crop"
            ),
            "producerStoreIndex": (
                "pointer-correlated mirror store index minus 2"
            ),
            "producerRoleRelationship": (
                "producer role base + 0xfb0 equals mirror role base"
            ),
            "producerDepthRelationship": (
                "producer prepare recursion depth equals mirror depth + 2"
            ),
            "selectionUsesCropValues": False,
            "allStructuralSelectionsPassed": len(records) == 256,
        },
        "downstreamBoundary": {
            "pointerCorrelatedIntegerMirrorCount": len(records),
            "producerIntegerizationAndViewportIntersectionExactCount": len(records),
            "mismatchedIntegerCropCount": 0,
            "calibrationAndHoldoutIntegerCropCount": 512,
            "calibrationAndHoldoutMismatchedIntegerCropCount": 0,
        },
        "floatingProducerModels": {
            "originalCollapsedCanvasCandidate": {
                **global_metric.result(),
                "status": "prospectively falsified for exact floating replay",
            },
            "retrospectiveLocalCoordinateCandidate": {
                **local_metric.result(),
                "status": (
                    "diagnostic only; substantially narrows operation-order "
                    "error but is not exact and has no production authority"
                ),
            },
        },
        "producerRoleIntermediateExactCounts": {
            "recordCount": len(records),
            **role_counts,
        },
        "producerRoleLayout": {
            "transformOffset": ROLE_TRANSFORM_OFFSET,
            "transformTranslationIndices": [12, 13],
            "transformedDynamicBoundsOffset": ROLE_TRANSFORMED_DYNAMIC_BOUNDS_OFFSET,
            "shadowOffsetOffset": ROLE_SHADOW_OFFSET_OFFSET,
            "carrierTranslationOffset": ROLE_CARRIER_TRANSLATION_OFFSET,
            "nominalShapeOffset": ROLE_NOMINAL_SHAPE_OFFSET,
            "dynamicLocalBoundsOffset": ROLE_DYNAMIC_LOCAL_BOUNDS_OFFSET,
            "recursiveChildOffset": ROLE_RECURSIVE_CHILD_OFFSET,
        },
        "records": records,
        "conclusion": {
            "callbackTransportRecovered": True,
            "allRetainedCaptureHashesAndSnapshotsRevalidated": True,
            "originalProspectiveFailurePreserved": True,
            "oversizedDepthThreeTopologyOpenedWithoutChangingFrozenValidator": True,
            "actualPreIntegerProducerOpenedStructurally": True,
            "allCapturedProducerFloatsRetainedBitForBit": True,
            "allCapturedFinalIntegerCropsExact": True,
            "exactBinary64ProducerArithmeticRecovered": False,
            "prepareLayerMaskInstructionOrderCaptured": False,
            "materialAppearanceDirectionTransferPassed": False,
            "physicalRetina2xAndColorTransferPassed": False,
            "independentWalleZeroByteFrameParityPassed": False,
            "productionShaderExpectedSHA256": PRODUCTION_SHADER_SHA256,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
        "nextExactGate": {
            "target": "CA::Render::Updater::prepare_layer_mask",
            "reason": (
                "the existing prepare_layer instruction trace calls this "
                "helper with destination role+0x290; tracing its retained "
                "body is the shortest evidence path to Apple's exact "
                "binary64 construction, transform, union, and intersection order"
            ),
            "requiresNewAppleCapture": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact_root", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = analyze(arguments.artifact_root)
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")


if __name__ == "__main__":
    main()
