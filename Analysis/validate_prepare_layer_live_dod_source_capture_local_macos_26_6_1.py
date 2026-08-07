#!/usr/bin/env python3
"""Validate and decode the retrospective live DOD source inventory."""

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any


VALIDATION_SCHEMA_VERSION = 1
EXTENSION_SCHEMA_VERSION = 1
DOD_FUNCTION = (
    "CA::OGL::GlassBackgroundFilter::DOD(CA::Render::Filter const*, "
    "CA::Render::Layer const*, CA::Rect&) const"
)
DOD_RELATIVE_TO_PREPARE_LAYER = -0x16220
DOD_SYMBOL_BYTE_COUNT = 1136
DOD_CODE_SHA256 = "d44b226f8edbfcb8fd37bc0f15a48b583df08063dc812e28cd06b1398d2f1678"
SOURCE_REGISTERS_OFFSET = 0x200
SOURCE_REGISTERS_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = "e00703ad"
QUARTZCORE_UUID = "F1BA3189-E95A-3ECA-B59A-5A6872754484"


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


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} is not an integer")
    return value


def _registers(raw: Any) -> dict[str, dict[str, Any]]:
    records = _sequence(raw, "registers")
    result = {}
    for raw_record in records:
        record = _mapping(raw_record, "register")
        name = record.get("name")
        if not isinstance(name, str) or name in result:
            raise ValueError("register name differs")
        result[name] = record
    if set(result) != {"x19", "x21", "pc", "v0", "v1"}:
        raise ValueError("register inventory differs")
    return result


def _simd_pair(record: dict[str, Any], label: str) -> tuple[float, float]:
    payload = bytes.fromhex(str(record.get("hex")))
    if record.get("byteCount") != 16 or len(payload) != 16:
        raise ValueError(f"{label} byte count differs")
    values = struct.unpack("<2d", payload)
    if not all(math.isfinite(value) for value in values):
        raise ValueError(f"{label} contains a nonfinite value")
    return values


def validate(
    trace_path: Path,
    timeline_path: Path,
    expected_geometry: str,
    expected_material: str,
    expected_appearance: str,
    expected_direction: str,
) -> dict[str, Any]:
    trace = _mapping(json.loads(trace_path.read_text(encoding="utf-8")), "trace")
    timeline = _mapping(
        json.loads(timeline_path.read_text(encoding="utf-8")), "timeline"
    )
    extension = _mapping(
        trace.get("liveDODSourceBoundsExtension"), "DOD extension"
    )
    configuration = _mapping(extension.get("configuration"), "configuration")
    identity = _mapping(extension.get("codeIdentity"), "code identity")
    if (
        trace.get("status") != "finalized"
        or _sequence(trace.get("failures"), "trace failures")
        or len(_sequence(trace.get("qualifiedRecords"), "qualified records")) != 32
        or extension.get("liveDODSourceBoundsExtensionSchemaVersion")
        != EXTENSION_SCHEMA_VERSION
        or extension.get("status") != "finalized"
        or _sequence(extension.get("failures"), "DOD failures")
        or configuration.get("function") != DOD_FUNCTION
        or configuration.get("relativeToPrepareLayer")
        != DOD_RELATIVE_TO_PREPARE_LAYER
        or configuration.get("symbolByteCount") != DOD_SYMBOL_BYTE_COUNT
        or configuration.get("codeSHA256") != DOD_CODE_SHA256
        or configuration.get("sourceRegistersOffset") != SOURCE_REGISTERS_OFFSET
        or configuration.get("sourceRegistersInstructionRawLittleEndianHex")
        != SOURCE_REGISTERS_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
        or configuration.get("sourceValuesUsedForSelection") is not False
        or configuration.get("cropOrProducerValuesUsedForSelection") is not False
        or configuration.get("hardwareWatchpointsUsed") is not False
        or configuration.get("instructionSteppingUsed") is not False
        or identity.get("function") != DOD_FUNCTION
        or identity.get("relativeToPrepareLayer") != DOD_RELATIVE_TO_PREPARE_LAYER
        or identity.get("symbolByteCount") != DOD_SYMBOL_BYTE_COUNT
        or identity.get("codeSHA256") != DOD_CODE_SHA256
        or identity.get("sourceRegistersOffset") != SOURCE_REGISTERS_OFFSET
        or identity.get("sourceRegistersInstructionRawLittleEndianHex")
        != SOURCE_REGISTERS_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
        or identity.get("quartzCoreUUID") != QUARTZCORE_UUID
    ):
        raise ValueError("live DOD capture identity differs")
    if (
        timeline.get("geometry", {}).get("name") != expected_geometry
        or timeline.get("material") != expected_material
        or timeline.get("appearance") != expected_appearance
        or timeline.get("direction") != expected_direction
        or timeline.get("windowBackingScaleFactor") != 2
        or timeline.get("sampleCount") != 33
        or timeline.get("failedSamples") != 0
    ):
        raise ValueError("live DOD timeline metadata differs")

    events = _sequence(extension.get("events"), "events")
    records = _sequence(extension.get("records"), "records")
    if (
        extension.get("finalEventSequence") != len(events)
        or extension.get("finalDODHitCount") != len(records)
        or extension.get("finalRecordCount") != len(records)
        or extension.get("finalFailureCount") != 0
        or len(records) < 32
    ):
        raise ValueError("live DOD final accounting differs")
    if [event.get("sequence") for event in events] != list(
        range(1, len(events) + 1)
    ):
        raise ValueError("live DOD event order differs")
    marker_events = [
        event for event in events if event.get("kind") == "qualified-marker-callback"
    ]
    if (
        len(marker_events) != 32
        or [event.get("qualifiedMarkerCountAfterCallback") for event in marker_events]
        != list(range(1, 33))
    ):
        raise ValueError("live DOD marker event order differs")

    decoded = []
    for index, raw_record in enumerate(records):
        record = _mapping(raw_record, f"DOD record {index}")
        registers = _registers(record.get("registers"))
        event_sequence = _integer(record.get("eventSequence"), "event sequence")
        matching_events = [
            event
            for event in events
            if event.get("sequence") == event_sequence
            and event.get("kind") == "dod-source-registers"
            and event.get("recordIndex") == index
        ]
        if (
            record.get("recordIndex") != index
            or record.get("hitIndex") != index + 1
            or len(matching_events) != 1
            or record.get("pc") != identity.get("sourceRegistersAddress")
            or not _sequence(record.get("backtrace"), "backtrace")
        ):
            raise ValueError(f"live DOD record {index} differs")
        origin = _simd_pair(registers["v0"], "source origin")
        size = _simd_pair(registers["v1"], "source size")
        decoded.append(
            {
                "recordIndex": index,
                "hitIndex": record["hitIndex"],
                "eventSequence": event_sequence,
                "threadID": record["threadID"],
                "sourceOriginF64": list(origin),
                "sourceSizeF64": list(size),
                "sourceBoundsHex": struct.pack("<4d", *origin, *size).hex(),
                "backtraceFunctions": [
                    _mapping(frame, "backtrace frame").get("function")
                    for frame in record["backtrace"]
                ],
            }
        )

    return {
        "prepareLayerLiveDODSourceCaptureLocalMacOS2661ValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "classification": (
            "retrospective value-blind structural inventory of every live DOD "
            "source rectangle; selection and algorithm remain unopened"
        ),
        "conclusion": "success",
        "inputs": {
            "traceSHA256": _sha256(trace_path),
            "timelineSHA256": _sha256(timeline_path),
        },
        "profile": {
            "geometry": expected_geometry,
            "material": expected_material,
            "appearance": expected_appearance,
            "direction": expected_direction,
            "backingScaleFactor": 2,
        },
        "eventCount": len(events),
        "markerEventCount": len(marker_events),
        "sourceRecordCount": len(decoded),
        "sourceValuesUsedForSelection": False,
        "cropOrProducerValuesUsedForSelection": False,
        "records": decoded,
        "sealedConclusion": {
            "captureTransportPassed": True,
            "sourceRecordSelectionPassed": False,
            "sourceBoundsAlgorithmPassed": False,
            "selectedRegionOriginTransferPassed": False,
            "physicalRetinaColorTransferPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }


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
