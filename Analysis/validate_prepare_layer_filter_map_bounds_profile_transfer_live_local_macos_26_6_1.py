#!/usr/bin/env python3
"""Validate a crop-profile replay through the active M1 QuartzCore code.

The numerical and structural gate remains the frozen profile-transfer
validator.  This adapter authenticates the value-blind live code record and
translates only the three moved instruction sites plus the complete function
identity.  It runs under ``nix develop`` Python, never LLDB's Python 3.9.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import prepare_layer_live_transport_local_macos_26_6_1 as live
import validate_prepare_layer_filter_map_bounds_profile_transfer_retry as profile


VALIDATION_SCHEMA_VERSION = 1


def _configure_live_validators() -> None:
    crop = profile.crop_validator
    union = profile.union_validator
    store = profile.store_validator

    crop.PREPARE_LAYER_SYMBOL_BYTE_COUNT = live.PREPARE_LAYER_SYMBOL_BYTE_COUNT
    crop.PREPARE_LAYER_FULL_CODE_SHA256 = live.PREPARE_LAYER_FULL_CODE_SHA256
    crop.KNOWN_PREPARE_LAYER_WINDOWS = live.PREPARE_LAYER_WINDOWS
    crop.EXPECTED_CONFIGURATION = {
        **crop.EXPECTED_CONFIGURATION,
        "prepareLayerSymbolByteCount": live.PREPARE_LAYER_SYMBOL_BYTE_COUNT,
        "prepareLayerFullCodeSHA256": live.PREPARE_LAYER_FULL_CODE_SHA256,
        "knownPrepareLayerWindows": [
            {"offset": offset, "byteCount": count, "sha256": digest}
            for offset, count, digest in live.PREPARE_LAYER_WINDOWS
        ],
        "markerOffset": live.MARKER_OFFSET,
        "markerInstructionRawLittleEndianHex": (
            live.MARKER_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
        ),
    }

    union.UNION_CALL_OFFSET = live.UNION_CALL_OFFSET
    union.UNION_CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = (
        live.UNION_CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
    )
    union.UNION_RETURN_OFFSET = live.UNION_RETURN_OFFSET
    union.UNION_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = (
        live.UNION_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
    )
    union.EXPECTED_EXTENSION_CONFIGURATION = {
        **union.EXPECTED_EXTENSION_CONFIGURATION,
        "unionCallOffset": live.UNION_CALL_OFFSET,
        "unionCallInstructionRawLittleEndianHex": (
            live.UNION_CALL_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
        ),
        "unionReturnOffset": live.UNION_RETURN_OFFSET,
        "unionReturnInstructionRawLittleEndianHex": (
            live.UNION_RETURN_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
        ),
        "callSelectionRule": live.union_call_selection_rule(),
    }

    store.STORE_OFFSET = live.STORE_OFFSET
    store.STORE_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = (
        live.STORE_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
    )
    store.EXPECTED_EXTENSION_CONFIGURATION = {
        **store.EXPECTED_EXTENSION_CONFIGURATION,
        "storeOffset": live.STORE_OFFSET,
        "storeInstructionRawLittleEndianHex": (
            live.STORE_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
        ),
        "storeSelectionRule": live.store_selection_rule(),
    }


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    return value


def _authenticate_transport(trace_path: Path) -> dict[str, Any]:
    trace = _mapping(profile.crop_validator.load_json(trace_path, "trace"), "trace")
    observed = _mapping(
        trace.get("livePrepareLayerTransport"), "live prepare_layer transport"
    )
    expected = live.transport_record()
    if observed != expected:
        raise ValueError("live prepare_layer transport record differs")
    prepare = _mapping(trace.get("prepareLayer"), "prepare layer")
    if (
        prepare.get("function") != live.PREPARE_LAYER_FUNCTION
        or prepare.get("symbolByteCount") != live.PREPARE_LAYER_SYMBOL_BYTE_COUNT
        or prepare.get("fullCodeSHA256") != live.PREPARE_LAYER_FULL_CODE_SHA256
    ):
        raise ValueError("live prepare_layer capture identity differs")
    return observed


def validate(
    trace_path: Path,
    timeline_path: Path,
    expected_geometry: str,
    expected_material: str,
    expected_appearance: str,
    expected_direction: str,
) -> dict[str, Any]:
    _configure_live_validators()
    transport = _authenticate_transport(trace_path)
    result = profile.validate(
        trace_path,
        timeline_path,
        expected_geometry,
        expected_material,
        expected_appearance,
        expected_direction,
    )
    result[
        "prepareLayerFilterMapBoundsLiveLocalMacOS2661ValidationSchemaVersion"
    ] = VALIDATION_SCHEMA_VERSION
    result["classification"] = (
        "exact frozen profile replay through authenticated active-M1 "
        "QuartzCore code transport; numerical authority is unchanged"
    )
    result["livePrepareLayerTransport"] = transport
    sealed = _mapping(result.get("sealedConclusion"), "sealed conclusion")
    sealed["activeM1CropCaptureTransportPassed"] = True
    sealed["selectedRegionOriginTransferPassed"] = False
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
