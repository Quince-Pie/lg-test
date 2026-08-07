#!/usr/bin/env python3
"""Replay live regular-glass crop arithmetic across Apple's binary32 bleed boundary."""

import argparse
from collections.abc import Iterator
from contextlib import contextmanager
import json
from pathlib import Path
import struct
from typing import Any

import validate_prepare_layer_live_crop_replay_v2_local_macos_26_6_1 as v2


VALIDATION_SCHEMA_VERSION = 1


def _binary32_promoted(value: float) -> float:
    """Round once to binary32, then expose the exact promoted binary64 value."""

    return struct.unpack("<f", struct.pack("<f", value))[0]


def _internal_geometry_model(
    public_model: v2.RegularGeometryModel,
) -> v2.RegularGeometryModel:
    bleed = _binary32_promoted(public_model.terminal_bleed)
    source_bounds = (
        -bleed,
        -bleed,
        public_model.width + 2.0 * bleed,
        public_model.height + 2.0 * bleed,
    )
    return v2.RegularGeometryModel(
        width=public_model.width,
        height=public_model.height,
        terminal_bleed=bleed,
        source_bounds=source_bounds,
        recursive_child=(0.0, 0.0, source_bounds[2], source_bounds[3]),
    )


@contextmanager
def _geometry_model_patch(
    model: v2.RegularGeometryModel,
    timeline_path: Path,
    expected_geometry: str,
) -> Iterator[None]:
    original = v2._regular_geometry_model

    def frozen_model(path: Path, geometry: str) -> v2.RegularGeometryModel:
        if path != timeline_path or geometry != expected_geometry:
            raise ValueError("v3 geometry-model patch inputs differ")
        return model

    v2._regular_geometry_model = frozen_model
    try:
        yield
    finally:
        v2._regular_geometry_model = original


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
    if expected_material != "regular":
        raise ValueError("v3 exact crop replay currently requires regular material")
    public_model = v2._regular_geometry_model(timeline_path, expected_geometry)
    internal_model = _internal_geometry_model(public_model)
    with _geometry_model_patch(internal_model, timeline_path, expected_geometry):
        result = v2.validate(
            trace_path,
            timeline_path,
            expected_geometry,
            expected_material,
            expected_appearance,
            expected_direction,
            require_embedded_code_identity=require_embedded_code_identity,
        )

    result.pop(
        "prepareLayerLiveCropReplayV2LocalMacOS2661ValidationSchemaVersion", None
    )
    result["prepareLayerLiveCropReplayV3LocalMacOS2661ValidationSchemaVersion"] = (
        VALIDATION_SCHEMA_VERSION
    )
    result["classification"] = (
        "exact regular-glass crop replay using one public-binary64 to "
        "internal-binary32 bleed conversion before source-DOD, recursive-child, "
        "and endpoint arithmetic; all later SDF and Filter operations retain the "
        "live-code-authenticated v2 operation order and use no tolerance"
    )
    result["regularGeometryModel"] = {
        "geometryWidthF64": public_model.width,
        "geometryHeightF64": public_model.height,
        "terminalPublicInputBleedAmountF64": public_model.terminal_bleed,
        "terminalPublicInputBleedAmountF64Hex": v2.exact.f64_hex(
            (public_model.terminal_bleed,)
        ),
        "internalInputBleedAmountF32": internal_model.terminal_bleed,
        "internalInputBleedAmountF32RawLittleEndianHex": struct.pack(
            "<f", internal_model.terminal_bleed
        ).hex(),
        "internalInputBleedAmountPromotedF64Hex": v2.exact.f64_hex(
            (internal_model.terminal_bleed,)
        ),
        "sourceBoundsF64": list(internal_model.source_bounds),
        "sourceBoundsHex": v2.exact.f64_hex(internal_model.source_bounds),
        "recursiveChildF64": list(internal_model.recursive_child),
        "recursiveChildHex": v2.exact.f64_hex(internal_model.recursive_child),
        "binary32ConversionCount": 1,
        "cropOrProducerValuesUsed": False,
    }
    source = _mapping(result.get("sourceBounds"), "source bounds")
    source["rule"] = (
        "e = binary64(binary32(terminal public inputBleedAmount)); "
        "[-e, -e, geometry width + 2e, geometry height + 2e]"
    )
    source["publicBleedConvertedToBinary32ExactlyOnce"] = True
    endpoint = _mapping(result.get("endpointYOffset"), "endpoint offset")
    endpoint["rule"] = (
        "regular live-foreground endpoint depth uses mirror nominal width plus "
        "binary64(binary32(terminal public inputBleedAmount))"
    )
    metadata = _mapping(result.get("metadataAdapter"), "metadata adapter")
    metadata["cropOrProducerValuesUsedByV3Model"] = False
    metadata["toleranceUsedByV3Model"] = False
    sealed = _mapping(result.get("sealedConclusion"), "sealed conclusion")
    sealed["v2UnseenGeometryTransferPassed"] = False
    sealed["v2UnseenGeometryTransferFalsified"] = True
    sealed["v3OpenedGeometryReplayPassed"] = True
    sealed["v3UnseenGeometryTransferPassed"] = False
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
