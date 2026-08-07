#!/usr/bin/env python3
"""Replay live regular-glass crop arithmetic in exact Apple operation order."""

import argparse
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any

import analyze_prepare_layer_filter_map_bounds_exact_replay as exact
import prepare_layer_live_crop_arithmetic_local_macos_26_6_1 as arithmetic
import validate_prepare_layer_filter_map_bounds_profile_transfer_retry as profile
import validate_prepare_layer_filter_map_bounds_profile_transfer_live_local_macos_26_6_1 as live


VALIDATION_SCHEMA_VERSION = 1
EXPECTED_RECORD_COUNT = 32
STATIC_INVENTORY_PATH = Path(__file__).with_name(
    "prepare_layer_live_crop_arithmetic_code_inventory_a3ac528_result.json"
)
STATIC_INVENTORY_SHA256 = (
    "8f175031d4e5a011bc2c567c1aa6f47c9d884868a6efd6dea68496178bc30028"
)

type Pair = tuple[float, float]
type Rect = tuple[float, float, float, float]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    return value


def _sequence(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} is not an array")
    return value


def _rect_union(first: Rect, second: Rect) -> Rect:
    first_far = (first[0] + first[2], first[1] + first[3])
    second_far = (second[0] + second[2], second[1] + second[3])
    origin = (min(first[0], second[0]), min(first[1], second[1]))
    far = (max(first_far[0], second_far[0]), max(first_far[1], second_far[1]))
    return (origin[0], origin[1], far[0] - origin[0], far[1] - origin[1])


@dataclass(slots=True)
class ExactSDFEntry(Sequence[float]):
    """Delay SDF replay until the structurally selected carrier is known."""

    transformed: Rect
    parameters: Rect
    extra_y_offset: float
    _resolved: Rect | None = field(init=False, default=None)
    _carrier: Pair | None = field(init=False, default=None)

    def resolve(self, carrier: Pair) -> Rect:
        if self._resolved is not None:
            if self._carrier is None or exact.f64_hex(self._carrier) != exact.f64_hex(
                carrier
            ):
                raise ValueError("SDF entry was resolved with a different carrier")
            return self._resolved

        radius, offset_x, offset_y, _padding = self.parameters
        transform_x = -carrier[0]
        transform_y = carrier[1]

        # CA::Rect::unapply_transform: subtract translation, then flip Y by
        # adding height before negation.  The grouping is observable at 1 ULP.
        local_origin = (
            self.transformed[0] - transform_x,
            -((self.transformed[1] - transform_y) + self.transformed[3]),
        )
        local_size = self.transformed[2:4]

        # SDFOp::apply uses a binary32 radius promoted to binary64.  Width is
        # two additions/subtraction; height is one hardware FMA.
        negative_radius = -radius
        expanded_origin = (
            local_origin[0] + negative_radius,
            local_origin[1] + negative_radius,
        )
        expanded_size = (
            local_size[0] - (negative_radius + negative_radius),
            exact.binary64_fma(negative_radius, -2.0, local_size[1]),
        )
        expanded_origin = (
            expanded_origin[0] + offset_x,
            expanded_origin[1] + offset_y,
        )
        local_union = _rect_union(
            (*local_origin, *local_size),
            (*expanded_origin, *expanded_size),
        )

        # CA::Rect::apply_transform performs size + origin before negating Y.
        self._resolved = (
            local_union[0] + transform_x,
            -(local_union[3] + local_union[1]) + transform_y + self.extra_y_offset,
            local_union[2],
            local_union[3],
        )
        self._carrier = carrier
        return self._resolved

    def _value(self) -> Rect:
        if self._resolved is None:
            raise RuntimeError("SDF entry was consumed before carrier resolution")
        return self._resolved

    def __len__(self) -> int:
        return 4

    def __getitem__(self, index: int | slice) -> float | tuple[float, ...]:
        return self._value()[index]

    def __iter__(self) -> Iterator[float]:
        return iter(self._value())


def exact_sdf_entry(
    transformed: Rect,
    parameters: Rect,
    extra_y_offset: float,
) -> ExactSDFEntry:
    return ExactSDFEntry(transformed, parameters, extra_y_offset)


def exact_filter_replay(
    entry: Sequence[float],
    carrier: Pair,
    source_bounds: Rect,
    shadow_y: float,
    radius: float,
) -> Rect:
    """Replay FilterOp using the DOD rectangle directly as the source clip."""

    if isinstance(entry, ExactSDFEntry):
        resolved_entry = entry.resolve(carrier)
    else:
        resolved_entry = exact.rect(entry, "Filter entry")

    transform_x = -carrier[0]
    transform_y = carrier[1]
    local_origin = (
        resolved_entry[0] - transform_x,
        -((resolved_entry[1] - transform_y) + resolved_entry[3]),
    )
    local_size = resolved_entry[2:4]

    negative_expansion = radius * -2.8
    expanded_origin = (
        local_origin[0] + negative_expansion,
        local_origin[1] + negative_expansion,
    )
    expanded_size = (
        exact.binary64_fma(radius, 5.6, local_size[0]),
        exact.binary64_fma(radius, 5.6, local_size[1]),
    )
    shadow_origin = (local_origin[0], local_origin[1] + shadow_y)
    dod_union = _rect_union(
        (*expanded_origin, *expanded_size),
        (*shadow_origin, *local_size),
    )

    # GlassBackgroundFilter::DOD intersects against the already-expanded
    # source DOD.  Applying shadow offset to this source again was the
    # falsified v1 assumption.
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


@dataclass(frozen=True, slots=True, kw_only=True)
class RegularGeometryModel:
    width: float
    height: float
    terminal_bleed: float
    source_bounds: Rect
    recursive_child: Rect


def _regular_geometry_model(
    timeline_path: Path, expected_geometry: str
) -> RegularGeometryModel:
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
        raise ValueError("regular geometry-model inputs differ")
    terminal = _mapping(records[-1], "terminal timeline record")
    inputs = _mapping(
        _mapping(terminal.get("filter"), "terminal filter").get("inputValues"),
        "terminal filter inputs",
    )
    width = exact.finite(geometry.get("width"), "geometry width")
    height = exact.finite(geometry.get("height"), "geometry height")
    bleed = exact.finite(inputs.get("inputBleedAmount"), "terminal bleed")
    bleed_height = exact.finite(inputs.get("inputBleedHeight"), "terminal bleed height")
    if (
        terminal.get("sampleIndex") != EXPECTED_RECORD_COUNT
        or exact.f64_hex((bleed,)) != exact.f64_hex((bleed_height,))
        or width <= 0.0
        or height <= 0.0
        or bleed < 0.0
    ):
        raise ValueError("terminal regular source inputs differ")
    source_bounds = (
        -bleed,
        -bleed,
        width + 2.0 * bleed,
        height + 2.0 * bleed,
    )
    return RegularGeometryModel(
        width=width,
        height=height,
        terminal_bleed=bleed,
        source_bounds=source_bounds,
        recursive_child=(0.0, 0.0, source_bounds[2], source_bounds[3]),
    )


def _validate_static_inventory() -> dict[str, Any]:
    if _sha256(STATIC_INVENTORY_PATH) != STATIC_INVENTORY_SHA256:
        raise ValueError("static live arithmetic inventory hash differs")
    inventory = _mapping(
        json.loads(STATIC_INVENTORY_PATH.read_text(encoding="utf-8")),
        "static live arithmetic inventory",
    )
    host = _mapping(inventory.get("host"), "inventory host")
    selection = _mapping(inventory.get("selection"), "inventory selection")
    if (
        inventory.get("prepareLayerLiveCropArithmeticCodeInventorySchemaVersion")
        != arithmetic.IDENTITY_SCHEMA_VERSION
        or host.get("architecture") != "arm64"
        or host.get("macOSProductVersion") != "26.6.1"
        or host.get("macOSBuildVersion") != "25G76"
        or host.get("quartzCoreUUID") != arithmetic.QUARTZCORE_UUID
        or selection
        != {
            "cropOrProducerValuesUsed": False,
            "imageValuesUsed": False,
            "instructionSteppingUsed": False,
            "symbolNamesAndBoundsOnly": True,
        }
        or _sequence(inventory.get("records"), "inventory records")
        != arithmetic.frozen_code_records()
    ):
        raise ValueError("static live arithmetic inventory differs")
    return {
        "embeddedInTrace": False,
        "retrospectiveStaticInventory": True,
        "staticInventorySHA256": STATIC_INVENTORY_SHA256,
        "recordCount": len(arithmetic.ARITHMETIC_CODE_SPECS),
        "records": arithmetic.frozen_code_records(),
    }


def _validate_embedded_identity(trace_path: Path) -> dict[str, Any]:
    trace = _mapping(json.loads(trace_path.read_text(encoding="utf-8")), "trace")
    prepare = _mapping(trace.get("prepareLayer"), "prepare layer")
    prepare_start = profile.holdout.integer(
        prepare.get("symbolStart"), "prepare layer start"
    )
    extension = _mapping(
        trace.get("liveCropArithmeticCodeIdentity"),
        "live crop arithmetic identity",
    )
    selection = _mapping(extension.get("selection"), "identity selection")
    expected = arithmetic.frozen_code_records()
    records = _sequence(extension.get("records"), "identity records")
    if (
        extension.get("liveCropArithmeticCodeIdentitySchemaVersion")
        != arithmetic.IDENTITY_SCHEMA_VERSION
        or extension.get("status") != "finalized"
        or extension.get("authenticated") is not True
        or extension.get("recordCount") != len(expected)
        or extension.get("expectedRecords") != expected
        or selection
        != {
            "exactSymbolNamesAndBoundsOnly": True,
            "cropOrProducerValuesUsed": False,
            "imageValuesUsed": False,
            "hardwareWatchpointsUsed": False,
            "instructionSteppingUsed": False,
        }
        or len(records) != len(expected)
    ):
        raise ValueError("embedded live arithmetic identity differs")
    for observed, specification in zip(records, expected, strict=True):
        record = _mapping(observed, "identity record")
        start = profile.holdout.integer(record.get("symbolStart"), "symbol start")
        end = profile.holdout.integer(record.get("symbolEnd"), "symbol end")
        if (
            {key: record.get(key) for key in specification} != specification
            or start - prepare_start != specification["relativeToPrepareLayer"]
            or end - start != specification["symbolByteCount"]
            or record.get("quartzCoreUUID") != arithmetic.QUARTZCORE_UUID
            or not str(record.get("modulePath", "")).endswith("/QuartzCore")
        ):
            raise ValueError("embedded live arithmetic record differs")
    return {
        "embeddedInTrace": True,
        "retrospectiveStaticInventory": False,
        "recordCount": len(records),
        "records": records,
    }


@contextmanager
def _candidate_patch(model: RegularGeometryModel) -> Iterator[None]:
    original_source = profile.REGULAR_SOURCE_BOUNDS
    original_child = profile.REGULAR_RECURSIVE_CHILD
    original_endpoint = profile.REGULAR_ENDPOINT_SOURCE_ORIGIN
    original_sdf_entry = profile.sdf_entry
    original_replay = exact.replay
    profile.REGULAR_SOURCE_BOUNDS = model.source_bounds
    profile.REGULAR_RECURSIVE_CHILD = model.recursive_child
    profile.REGULAR_ENDPOINT_SOURCE_ORIGIN = model.terminal_bleed
    profile.sdf_entry = exact_sdf_entry
    exact.replay = exact_filter_replay
    try:
        yield
    finally:
        profile.REGULAR_SOURCE_BOUNDS = original_source
        profile.REGULAR_RECURSIVE_CHILD = original_child
        profile.REGULAR_ENDPOINT_SOURCE_ORIGIN = original_endpoint
        profile.sdf_entry = original_sdf_entry
        exact.replay = original_replay


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
        raise ValueError("v2 exact crop replay currently requires regular material")
    model = _regular_geometry_model(timeline_path, expected_geometry)
    code_identity = (
        _validate_embedded_identity(trace_path)
        if require_embedded_code_identity
        else _validate_static_inventory()
    )
    with _candidate_patch(model):
        result = live.validate(
            trace_path,
            timeline_path,
            expected_geometry,
            expected_material,
            expected_appearance,
            expected_direction,
        )

    replay = _mapping(result.get("floatingReplay"), "floating replay")
    source = _mapping(result.get("sourceBounds"), "source bounds")
    if (
        replay.get("rectangleCount") != EXPECTED_RECORD_COUNT
        or replay.get("exactRectangleCount") != EXPECTED_RECORD_COUNT
        or replay.get("componentCount") != EXPECTED_RECORD_COUNT * 4
        or replay.get("exactComponentCount") != EXPECTED_RECORD_COUNT * 4
        or replay.get("maximumULPDistancesXYWH") != [0, 0, 0, 0]
        or source.get("f64") != list(model.source_bounds)
        or source.get("hex") != exact.f64_hex(model.source_bounds)
    ):
        raise ValueError("v2 live exact crop replay differs")

    result["prepareLayerLiveCropReplayV2LocalMacOS2661ValidationSchemaVersion"] = (
        VALIDATION_SCHEMA_VERSION
    )
    result["classification"] = (
        "exact regular-glass crop replay using the public terminal bleed, "
        "live-code-authenticated SDF transform round-trip, direct DOD source "
        "intersection, and no tolerance; unseen transfer is a separate gate"
    )
    result["liveCropArithmeticCodeIdentity"] = code_identity
    result["regularGeometryModel"] = {
        "geometryWidthF64": model.width,
        "geometryHeightF64": model.height,
        "terminalInputBleedAmountF64": model.terminal_bleed,
        "sourceBoundsF64": list(model.source_bounds),
        "sourceBoundsHex": exact.f64_hex(model.source_bounds),
        "recursiveChildF64": list(model.recursive_child),
        "recursiveChildHex": exact.f64_hex(model.recursive_child),
        "cropOrProducerValuesUsed": False,
    }
    source["rule"] = (
        "[-terminal inputBleedAmount, -terminal inputBleedAmount, "
        "geometry width + 2 * terminal inputBleedAmount, geometry height + "
        "2 * terminal inputBleedAmount]"
    )
    source["directDODSourceUsedWithoutSecondShadowUnion"] = True
    sdf = _mapping(result.get("sdfState"), "SDF state")
    sdf["operationOrder"] = (
        "unapply translation; add height then negate Y; expand using promoted "
        "binary32 radius and exact binary64 FMA; union; add size to origin, "
        "negate Y, and reapply translation"
    )
    endpoint = _mapping(result.get("endpointYOffset"), "endpoint offset")
    endpoint["rule"] = (
        "regular live-foreground endpoint depth uses mirror nominal width plus "
        "terminal public inputBleedAmount"
    )
    arithmetic_result = _mapping(result.get("filterArithmetic"), "filter arithmetic")
    arithmetic_result["sourceDODShadowUnionApplied"] = False
    arithmetic_result["sdfTransformRoundTripAlgebraicallySimplified"] = False
    metadata = _mapping(result.get("metadataAdapter"), "metadata adapter")
    metadata["cropOrProducerValuesUsedByV2Model"] = False
    metadata["toleranceUsedByV2Model"] = False
    sealed = _mapping(result.get("sealedConclusion"), "sealed conclusion")
    sealed["v1Fixed1360SourceAssumptionFalsified"] = True
    sealed["v1SimplifiedSDFTransformArithmeticFalsified"] = True
    sealed["v2OpenedGeometryReplayPassed"] = True
    sealed["v2UnseenGeometryTransferPassed"] = False
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
