#!/usr/bin/env python3
"""Replay crop arithmetic from the public CABackdropLayer input bounds."""

import argparse
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
import json
import math
from pathlib import Path
import struct
from typing import Any

import validate_prepare_layer_live_crop_replay_v4_local_macos_26_6_1 as v4


VALIDATION_SCHEMA_VERSION = 1
EXPECTED_RECORD_COUNT = 32
BACKDROP_LAYER_CLASS = "CABackdropLayer"

v3 = v4.v3
v2 = v3.v2
Rect = v2.Rect


class ShadowAwareFilterRadius(float):
    """Carry public shadow inputs through the inherited replay interface."""

    shadow_opacity: float
    gaussian_factor: float
    shadow_radius: float
    shadow_expansion: float
    shadow_offset: tuple[float, float]

    def __new__(
        cls,
        radius: float,
        *,
        shadow_opacity: float,
        gaussian_factor: float,
        shadow_radius: float,
        shadow_expansion: float,
        shadow_offset: tuple[float, float],
    ) -> "ShadowAwareFilterRadius":
        value = super().__new__(cls, radius)
        value.shadow_opacity = shadow_opacity
        value.gaussian_factor = gaussian_factor
        value.shadow_radius = shadow_radius
        value.shadow_expansion = shadow_expansion
        value.shadow_offset = shadow_offset
        return value


def gaussian_expansion_factor(opacity: float) -> float:
    """Replay the authenticated 200-byte Apple helper in executed order."""

    value = v2.exact.finite(opacity, "shadow opacity")
    if value <= 0.005:
        return 0.0
    if value < 0.505:
        shifted = max(0.0, value + -0.005)
        logarithm = math.log(shifted + shifted)
        candidate = math.fma(logarithm, 0.3, 1.65)
        return max(0.0, candidate) if math.isfinite(candidate) else 0.0
    return math.fma(value, 0.10101010101010102, 1.598989898989899)


def _shadow_offset(value: Any) -> tuple[float, float]:
    payload = _mapping(value, "input shadow offset")
    raw_hex = payload.get("hex")
    if payload.get("lengthBytes") != 16 or not isinstance(raw_hex, str):
        raise ValueError("input shadow offset representation differs")
    try:
        raw = bytes.fromhex(raw_hex)
    except ValueError as error:
        raise ValueError("input shadow offset hex differs") from error
    if len(raw) != 16:
        raise ValueError("input shadow offset byte count differs")
    offset = struct.unpack("<2d", raw)
    return (
        v2.exact.finite(offset[0], "shadow offset x"),
        v2.exact.finite(offset[1], "shadow offset y"),
    )


def shadow_aware_filter_radius(
    timeline_record: dict[str, Any], material: str
) -> ShadowAwareFilterRadius:
    """Attach the public shadow state to the inherited Filter radius value."""

    radius = v4.v3.v2.profile.filter_radius(timeline_record, material)
    inputs = _mapping(
        _mapping(timeline_record.get("filter"), "background filter").get("inputValues"),
        "background filter inputs",
    )
    opacity = v2.exact.finite(inputs.get("inputShadowOpacity"), "shadow opacity")
    shadow_radius = v2.exact.finite(inputs.get("inputShadowRadius"), "shadow radius")
    if opacity < 0.0 or shadow_radius < 0.0:
        raise ValueError("negative shadow input differs")
    factor = gaussian_expansion_factor(opacity)
    expansion = factor * shadow_radius
    return ShadowAwareFilterRadius(
        radius,
        shadow_opacity=opacity,
        gaussian_factor=factor,
        shadow_radius=shadow_radius,
        shadow_expansion=expansion,
        shadow_offset=_shadow_offset(inputs.get("inputShadowOffset")),
    )


def exact_filter_replay(
    entry: Sequence[float],
    carrier: v2.Pair,
    source_bounds: Rect,
    shadow_y: float,
    radius: float,
) -> Rect:
    """Replay Glass DOD including its Gaussian-expanded shadow rectangle."""

    if not isinstance(radius, ShadowAwareFilterRadius):
        raise ValueError("shadow-aware Filter radius was not supplied")
    if isinstance(entry, v2.ExactSDFEntry):
        resolved_entry = entry.resolve(carrier)
    else:
        resolved_entry = v2.exact.rect(entry, "Filter entry")

    transform_x = -carrier[0]
    transform_y = carrier[1]
    local_origin = (
        resolved_entry[0] - transform_x,
        -((resolved_entry[1] - transform_y) + resolved_entry[3]),
    )
    local_size = resolved_entry[2:4]

    negative_expansion = float(radius) * -2.8
    expanded_origin = (
        local_origin[0] + negative_expansion,
        local_origin[1] + negative_expansion,
    )
    expanded_size = (
        v2.exact.binary64_fma(float(radius), 5.6, local_size[0]),
        v2.exact.binary64_fma(float(radius), 5.6, local_size[1]),
    )

    shadow_expansion = radius.shadow_expansion
    shadow_origin = (
        local_origin[0] - shadow_expansion,
        local_origin[1] - shadow_expansion,
    )
    shadow_size = (
        v2.exact.binary64_fma(shadow_expansion, 2.0, local_size[0]),
        v2.exact.binary64_fma(shadow_expansion, 2.0, local_size[1]),
    )
    offset_x, offset_y = radius.shadow_offset
    if v2.exact.f64_hex((offset_y,)) != v2.exact.f64_hex((shadow_y,)):
        raise ValueError("public and structurally retained shadow offsets differ")
    shifted_shadow_origin = (
        shadow_origin[0] + offset_x,
        shadow_origin[1] + offset_y,
    )
    dod_union = v2._rect_union(
        (*expanded_origin, *expanded_size),
        (*shifted_shadow_origin, *shadow_size),
    )

    dod_far = (dod_union[0] + dod_union[2], dod_union[1] + dod_union[3])
    source_far = (
        source_bounds[0] + source_bounds[2],
        source_bounds[1] + source_bounds[3],
    )
    intersection_origin = (
        max(dod_union[0], source_bounds[0]),
        max(dod_union[1], source_bounds[1]),
    )
    intersection_far = (
        min(dod_far[0], source_far[0]),
        min(dod_far[1], source_far[1]),
    )
    intersection_size = (
        intersection_far[0] - intersection_origin[0],
        intersection_far[1] - intersection_origin[1],
    )
    return (
        intersection_origin[0] + transform_x,
        -(intersection_origin[1] + intersection_size[1]) + transform_y,
        intersection_size[0],
        intersection_size[1],
    )


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    return value


def _sequence(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} is not an array")
    return value


def _backdrop_layer_state(
    boundary: dict[str, Any], label: str
) -> tuple[list[int], Rect]:
    states = _sequence(boundary.get("layerStates"), f"{label} layer states")
    matches = [
        _mapping(state, f"{label} layer state")
        for state in states
        if isinstance(state, dict) and state.get("class") == BACKDROP_LAYER_CLASS
    ]
    if len(matches) != 1:
        raise ValueError(f"{label} CABackdropLayer count differs")
    state = matches[0]
    raw_path = _sequence(state.get("path"), f"{label} CABackdropLayer path")
    path = [
        v2.profile.holdout.integer(component, f"{label} path component")
        for component in raw_path
    ]
    bounds = v2.exact.rect(state.get("bounds"), f"{label} CABackdropLayer bounds")
    if not path or bounds[2] <= 0.0 or bounds[3] <= 0.0:
        raise ValueError(f"{label} CABackdropLayer state differs")
    return path, bounds


def public_backdrop_bounds(
    timeline_path: Path, expected_geometry: str
) -> tuple[Rect, list[int]]:
    """Select the unique public CABackdropLayer bounds without crop outputs."""

    timeline = _mapping(
        json.loads(timeline_path.read_text(encoding="utf-8")), "timeline"
    )
    geometry = _mapping(timeline.get("geometry"), "geometry")
    records = _sequence(
        _mapping(timeline.get("dynamicBackgroundUniforms"), "dynamic uniforms").get(
            "records"
        ),
        "timeline records",
    )
    if (
        geometry.get("name") != expected_geometry
        or timeline.get("material") != "regular"
        or len(records) != EXPECTED_RECORD_COUNT
    ):
        raise ValueError("public backdrop-bound inputs differ")

    selected_bounds: list[Rect] = []
    selected_paths: list[list[int]] = []
    for expected_sample, raw_record in enumerate(records, start=1):
        record = _mapping(raw_record, "timeline record")
        render = _mapping(record.get("render"), "timeline render")
        before = _mapping(
            render.get("liveRenderBoundaryBefore"), "live render boundary before"
        )
        after = _mapping(
            render.get("liveRenderBoundaryAfter"), "live render boundary after"
        )
        before_path, before_bounds = _backdrop_layer_state(
            before, "live render boundary before"
        )
        after_path, after_bounds = _backdrop_layer_state(
            after, "live render boundary after"
        )
        if (
            record.get("sampleIndex") != expected_sample
            or before_path != after_path
            or v2.exact.f64_hex(before_bounds) != v2.exact.f64_hex(after_bounds)
        ):
            raise ValueError("public CABackdropLayer boundary changed")
        selected_paths.append(before_path)
        selected_bounds.append(before_bounds)

    first_path = selected_paths[0]
    first_bounds = selected_bounds[0]
    first_hex = v2.exact.f64_hex(first_bounds)
    if any(path != first_path for path in selected_paths) or any(
        v2.exact.f64_hex(bounds) != first_hex for bounds in selected_bounds
    ):
        raise ValueError("public CABackdropLayer state varies across transition")
    return first_bounds, first_path


def backdrop_geometry_model(
    public_model: v2.RegularGeometryModel,
    backdrop_bounds: Sequence[float],
) -> v2.RegularGeometryModel:
    """Replay BackdropLayer::get_backdrop_bounds in exact ARM64 order."""

    raw = v2.exact.rect(backdrop_bounds, "public CABackdropLayer bounds")
    margin = v3._binary32_promoted(public_model.terminal_bleed)
    negative_margin = -margin
    source_bounds = (
        raw[0] + negative_margin,
        raw[1] + negative_margin,
        raw[2] - (negative_margin + negative_margin),
        v2.exact.binary64_fma(negative_margin, -2.0, raw[3]),
    )
    return v2.RegularGeometryModel(
        width=public_model.width,
        height=public_model.height,
        terminal_bleed=margin,
        source_bounds=source_bounds,
        recursive_child=(0.0, 0.0, source_bounds[2], source_bounds[3]),
    )


@contextmanager
def _backdrop_geometry_patch(
    model: v2.RegularGeometryModel,
) -> Iterator[None]:
    original = v3._internal_geometry_model

    def frozen_model(
        _public_model: v2.RegularGeometryModel,
    ) -> v2.RegularGeometryModel:
        return model

    v3._internal_geometry_model = frozen_model
    try:
        yield
    finally:
        v3._internal_geometry_model = original


@contextmanager
def _shadow_arithmetic_patch() -> Iterator[None]:
    profile = v4.v3.v2.profile
    original_filter_radius = profile.filter_radius
    original_endpoint = profile.endpoint_y_offset
    original_replay = v2.exact_filter_replay

    def filter_radius(
        timeline_record: dict[str, Any], material: str
    ) -> ShadowAwareFilterRadius:
        # Avoid recursion through the patched module attribute.
        radius = original_filter_radius(timeline_record, material)
        inputs = _mapping(
            _mapping(timeline_record.get("filter"), "background filter").get(
                "inputValues"
            ),
            "background filter inputs",
        )
        opacity = v2.exact.finite(inputs.get("inputShadowOpacity"), "shadow opacity")
        shadow_radius = v2.exact.finite(
            inputs.get("inputShadowRadius"), "shadow radius"
        )
        if opacity < 0.0 or shadow_radius < 0.0:
            raise ValueError("negative shadow input differs")
        factor = gaussian_expansion_factor(opacity)
        return ShadowAwareFilterRadius(
            radius,
            shadow_opacity=opacity,
            gaussian_factor=factor,
            shadow_radius=shadow_radius,
            shadow_expansion=factor * shadow_radius,
            shadow_offset=_shadow_offset(inputs.get("inputShadowOffset")),
        )

    def endpoint_y_offset(*args: Any, **kwargs: Any) -> tuple[float, bool]:
        _legacy_offset, branch_applied = original_endpoint(*args, **kwargs)
        return 0.0, branch_applied

    profile.filter_radius = filter_radius
    profile.endpoint_y_offset = endpoint_y_offset
    v2.exact_filter_replay = exact_filter_replay
    try:
        yield
    finally:
        profile.filter_radius = original_filter_radius
        profile.endpoint_y_offset = original_endpoint
        v2.exact_filter_replay = original_replay


def _shadow_records(timeline_path: Path) -> list[dict[str, Any]]:
    timeline = _mapping(
        json.loads(timeline_path.read_text(encoding="utf-8")), "timeline"
    )
    raw_records = _sequence(
        _mapping(timeline.get("dynamicBackgroundUniforms"), "dynamic uniforms").get(
            "records"
        ),
        "timeline records",
    )
    if len(raw_records) != EXPECTED_RECORD_COUNT:
        raise ValueError("shadow timeline record count differs")
    records: list[dict[str, Any]] = []
    for expected_sample, raw_record in enumerate(raw_records, start=1):
        record = _mapping(raw_record, "timeline record")
        if record.get("sampleIndex") != expected_sample:
            raise ValueError("shadow timeline sample order differs")
        radius = shadow_aware_filter_radius(record, "regular")
        records.append(
            {
                "sampleIndex": expected_sample,
                "inputShadowOpacityF64": radius.shadow_opacity,
                "inputShadowOpacityHex": v2.exact.f64_hex((radius.shadow_opacity,)),
                "gaussianExpansionFactorF64": radius.gaussian_factor,
                "gaussianExpansionFactorHex": v2.exact.f64_hex(
                    (radius.gaussian_factor,)
                ),
                "inputShadowRadiusF64": radius.shadow_radius,
                "inputShadowRadiusHex": v2.exact.f64_hex((radius.shadow_radius,)),
                "shadowExpansionF64": radius.shadow_expansion,
                "shadowExpansionHex": v2.exact.f64_hex((radius.shadow_expansion,)),
                "inputShadowOffsetF64": list(radius.shadow_offset),
                "inputShadowOffsetHex": v2.exact.f64_hex(radius.shadow_offset),
            }
        )
    return records


def validate(
    trace_path: Path,
    timeline_path: Path,
    expected_geometry: str,
    expected_material: str,
    expected_appearance: str,
    expected_direction: str,
    *,
    require_embedded_code_identity: bool = True,
) -> dict[str, Any]:
    if expected_material != "regular":
        raise ValueError("v5 exact crop replay currently requires regular material")
    backdrop_bounds, backdrop_path = public_backdrop_bounds(
        timeline_path, expected_geometry
    )
    public_model = v2._regular_geometry_model(timeline_path, expected_geometry)
    internal_model = backdrop_geometry_model(public_model, backdrop_bounds)
    with _backdrop_geometry_patch(internal_model), _shadow_arithmetic_patch():
        result = v4.validate(
            trace_path,
            timeline_path,
            expected_geometry,
            expected_material,
            expected_appearance,
            expected_direction,
            require_embedded_code_identity=require_embedded_code_identity,
        )

    result.pop(
        "prepareLayerLiveCropReplayV4LocalMacOS2661ValidationSchemaVersion", None
    )
    result["prepareLayerLiveCropReplayV5LocalMacOS2661ValidationSchemaVersion"] = (
        VALIDATION_SCHEMA_VERSION
    )
    result["classification"] = (
        "exact regular-glass crop replay using the unique public CABackdropLayer "
        "input bounds, authenticated get_backdrop_bounds operation order, and "
        "the public-input Gaussian shadow expansion; no crop or producer value "
        "and no tolerance is used"
    )
    model = _mapping(result.get("regularGeometryModel"), "geometry model")
    model["publicBackdropLayerClass"] = BACKDROP_LAYER_CLASS
    model["publicBackdropLayerPath"] = backdrop_path
    model["publicBackdropBoundsF64"] = list(backdrop_bounds)
    model["publicBackdropBoundsHex"] = v2.exact.f64_hex(backdrop_bounds)
    model["sourceBoundsF64"] = list(internal_model.source_bounds)
    model["sourceBoundsHex"] = v2.exact.f64_hex(internal_model.source_bounds)
    model["recursiveChildF64"] = list(internal_model.recursive_child)
    model["recursiveChildHex"] = v2.exact.f64_hex(internal_model.recursive_child)
    model["backdropBoundsRecordCount"] = EXPECTED_RECORD_COUNT
    model["backdropBoundsUsedAsPublicInput"] = True
    model["cropOrProducerValuesUsed"] = False
    source = _mapping(result.get("sourceBounds"), "source bounds")
    source["rule"] = (
        "let m = binary64(binary32(terminal public inputBleedAmount)), n = -m, "
        "and b = the unique public CABackdropLayer bounds; return "
        "[b.x+n, b.y+n, b.w-(n+n), fma(n,-2,b.h)]"
    )
    source["publicBackdropBoundsUsed"] = True
    source["directNominalGeometryOriginAssumptionFalsified"] = True
    sdf = _mapping(result.get("sdfState"), "SDF state")
    sdf["endpointApplyOrder"] = "no endpoint-derived SDF translation is applied"
    sdf["endpointOffsetGroupedIntoYTranslation"] = False
    endpoint = _mapping(result.get("endpointYOffset"), "endpoint offset")
    endpoint["rule"] = (
        "the formerly correlated endpoint branch is retained as a structural "
        "witness but contributes exact positive zero to SDF translation"
    )
    endpoint["applyOrder"] = "no endpoint-derived SDF translation is applied"
    endpoint["legacyEndpointTranslationFalsified"] = True
    endpoint["arithmeticOffsetApplied"] = False
    shadow_records = _shadow_records(timeline_path)
    result["filterShadowArithmetic"] = {
        "rule": (
            "s = gaussian_expansion_factor(inputShadowOpacity) * "
            "inputShadowRadius; shadow origin = local origin - s; shadow size = "
            "fma(s,2,local size); then add inputShadowOffset before unioning "
            "with the main 2.8-radius expansion"
        ),
        "gaussianHelperCodeSHA256": (
            "7834bbb95f84915a6544d34b4148f7f267fcc94d2ae730888644535ffc57c0dd"
        ),
        "recordCount": len(shadow_records),
        "positiveExpansionRecordCount": sum(
            record["shadowExpansionF64"] > 0.0 for record in shadow_records
        ),
        "publicTimelineInputsUsed": True,
        "cropOrProducerValuesUsed": False,
        "toleranceUsed": False,
        "records": shadow_records,
    }
    metadata = _mapping(result.get("metadataAdapter"), "metadata adapter")
    metadata["cropOrProducerValuesUsedByV5Model"] = False
    metadata["publicLayerTreeInputUsedByV5Model"] = True
    metadata["toleranceUsedByV5Model"] = False
    sealed = _mapping(result.get("sealedConclusion"), "sealed conclusion")
    sealed["v4UnseenGeometryTransferPassed"] = False
    sealed["v4UnseenGeometryTransferFalsified"] = True
    sealed["v4EndpointTranslationModelFalsified"] = True
    sealed["v5OpenedGeometryReplayPassed"] = True
    sealed["v5UnseenGeometryTransferPassed"] = False
    sealed["selectedRegionOriginTransferPassed"] = False
    sealed["physicalRetina2xAndColorTransferPassed"] = False
    sealed["independentWalleZeroByteFrameParityPassed"] = False
    sealed["productionShaderAuthorized"] = False
    sealed["liquidGlassParityEstablished"] = False
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("--expected-geometry", required=True)
    parser.add_argument("--expected-material", required=True)
    parser.add_argument("--expected-appearance", required=True)
    parser.add_argument("--expected-direction", required=True)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate(
        arguments.trace,
        arguments.timeline,
        arguments.expected_geometry,
        arguments.expected_material,
        arguments.expected_appearance,
        arguments.expected_direction,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
