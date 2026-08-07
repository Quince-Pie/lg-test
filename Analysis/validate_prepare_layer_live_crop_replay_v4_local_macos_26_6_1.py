#!/usr/bin/env python3
"""Replay live crop arithmetic with Apple's endpoint-translation grouping."""

import argparse
from collections.abc import Iterator
from contextlib import contextmanager
import json
from pathlib import Path
from typing import Any

import validate_prepare_layer_live_crop_replay_v3_local_macos_26_6_1 as v3


VALIDATION_SCHEMA_VERSION = 1


class ExactSDFEntry(v3.v2.ExactSDFEntry):
    """Preserve Apple's grouping of the endpoint offset into Y translation."""

    __slots__ = ()

    def resolve(self, carrier: v3.v2.Pair) -> v3.v2.Rect:
        if self._resolved is not None:
            if self._carrier is None or v3.v2.exact.f64_hex(
                self._carrier
            ) != v3.v2.exact.f64_hex(carrier):
                raise ValueError("SDF entry was resolved with a different carrier")
            return self._resolved

        radius, offset_x, offset_y, _padding = self.parameters
        transform_x = -carrier[0]
        transform_y = carrier[1]
        local_origin = (
            self.transformed[0] - transform_x,
            -((self.transformed[1] - transform_y) + self.transformed[3]),
        )
        local_size = self.transformed[2:4]
        negative_radius = -radius
        expanded_origin = (
            local_origin[0] + negative_radius,
            local_origin[1] + negative_radius,
        )
        expanded_size = (
            local_size[0] - (negative_radius + negative_radius),
            v3.v2.exact.binary64_fma(negative_radius, -2.0, local_size[1]),
        )
        expanded_origin = (
            expanded_origin[0] + offset_x,
            expanded_origin[1] + offset_y,
        )
        local_union = v3.v2._rect_union(
            (*local_origin, *local_size),
            (*expanded_origin, *expanded_size),
        )
        self._resolved = (
            local_union[0] + transform_x,
            -(local_union[3] + local_union[1]) + (transform_y + self.extra_y_offset),
            local_union[2],
            local_union[3],
        )
        self._carrier = carrier
        return self._resolved


def exact_sdf_entry(
    transformed: v3.v2.Rect,
    parameters: v3.v2.Rect,
    extra_y_offset: float,
) -> ExactSDFEntry:
    return ExactSDFEntry(transformed, parameters, extra_y_offset)


@contextmanager
def _endpoint_grouping_patch() -> Iterator[None]:
    original = v3.v2.exact_sdf_entry
    v3.v2.exact_sdf_entry = exact_sdf_entry
    try:
        yield
    finally:
        v3.v2.exact_sdf_entry = original


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    return value


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
    with _endpoint_grouping_patch():
        result = v3.validate(
            trace_path,
            timeline_path,
            expected_geometry,
            expected_material,
            expected_appearance,
            expected_direction,
            require_embedded_code_identity=require_embedded_code_identity,
        )

    result.pop(
        "prepareLayerLiveCropReplayV3LocalMacOS2661ValidationSchemaVersion", None
    )
    result["prepareLayerLiveCropReplayV4LocalMacOS2661ValidationSchemaVersion"] = (
        VALIDATION_SCHEMA_VERSION
    )
    result["classification"] = (
        "exact regular-glass crop replay with endpoint offset grouped into the "
        "Y translation before the final binary64 add; public-to-internal bleed, "
        "SDF, Filter, DOD, and last-store rules otherwise remain v3-identical"
    )
    sdf = _mapping(result.get("sdfState"), "SDF state")
    sdf["endpointApplyOrder"] = (
        "-(local union height + local union origin Y) + (carrier Y + endpoint offset)"
    )
    sdf["endpointOffsetGroupedIntoYTranslation"] = True
    endpoint = _mapping(result.get("endpointYOffset"), "endpoint offset")
    endpoint["applyOrder"] = sdf["endpointApplyOrder"]
    metadata = _mapping(result.get("metadataAdapter"), "metadata adapter")
    metadata["cropOrProducerValuesUsedByV4Model"] = False
    metadata["toleranceUsedByV4Model"] = False
    sealed = _mapping(result.get("sealedConclusion"), "sealed conclusion")
    sealed["v3UnseenGeometryTransferPassed"] = False
    sealed["v3UnseenGeometryTransferFalsified"] = True
    sealed["v4OpenedGeometryReplayPassed"] = True
    sealed["v4UnseenGeometryTransferPassed"] = False
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
