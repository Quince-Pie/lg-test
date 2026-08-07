#!/usr/bin/env python3
"""Recover the complete BackgroundFilter payload from the retained wrapper."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple


EXPECTED_TRACE_SHA256 = (
    "e6c1075ae00dc9fb98a0768c72ed7155b9461bf6c643ba34bb26285c4439f040"
)
EXPECTED_METADATA_RESULT_SHA256 = (
    "dc2202be02d3831126866236661173c92bf492498a4cc2d2717931ba296b0757"
)
EXPECTED_PROVIDER_PREFIX_SHA256 = (
    "c70501b12b2c3e5003ae9ed96416816832b26b10741845ca23f6e10e990e23d1"
)
EXPECTED_WRAPPER_HEADER_BYTE_COUNT = 16
EXPECTED_PROVIDER_PREFIX_BYTE_COUNT = 384
EXPECTED_COMPLETE_PAYLOAD_BYTE_COUNT = 504

SCALARS: Tuple[Tuple[str, int, str], ...] = (
    ("layerIndex", 0x000, "q"),
    ("shadow.offset.width", 0x008, "d"),
    ("shadow.offset.height", 0x010, "d"),
    ("shadow.amount", 0x018, "d"),
    ("shadow.height", 0x020, "d"),
    ("shadow.inset", 0x028, "d"),
    ("shadow.blurRadius", 0x030, "d"),
    ("shadow.shadowRadius", 0x038, "d"),
    ("shadow.ycc.black", 0x040, "f"),
    ("shadow.ycc.white", 0x044, "f"),
    ("shadow.ycc.saturation", 0x048, "f"),
    ("shadow.opacity", 0x088, "f"),
    ("shadow.vibrancyContribution", 0x090, "d"),
    ("blur.radius", 0x098, "d"),
    ("blur.distances[0]", 0x0A0, "d"),
    ("blur.distances[1]", 0x0A8, "d"),
    ("blur.distances[2]", 0x0B0, "d"),
    ("blur.distances[3]", 0x0B8, "d"),
    ("blur.distances[4]", 0x0C0, "d"),
    ("blur.opacities[0]", 0x0C8, "f"),
    ("blur.opacities[1]", 0x0CC, "f"),
    ("blur.opacities[2]", 0x0D0, "f"),
    ("blur.opacities[3]", 0x0D4, "f"),
    ("blur.opacities[4]", 0x0D8, "f"),
    ("blur.opacity", 0x0DC, "f"),
    ("refraction.innerHeight", 0x0E0, "d"),
    ("refraction.innerAmount", 0x0E8, "d"),
    ("refraction.outerHeight", 0x0F0, "d"),
    ("refraction.outerAmount", 0x0F8, "d"),
    ("refraction.outerDistances[0]", 0x100, "d"),
    ("refraction.outerDistances[1]", 0x108, "d"),
    ("refraction.outerOpacity", 0x110, "f"),
    ("face.opacity", 0x114, "f"),
    ("face.ycc.black", 0x118, "f"),
    ("face.ycc.white", 0x11C, "f"),
    ("face.ycc.saturation", 0x120, "f"),
    ("bleed.amount", 0x160, "d"),
    ("bleed.height", 0x168, "d"),
    ("bleed.blurRadius", 0x170, "d"),
    ("bleed.opacity", 0x178, "f"),
    ("bleed.distances[0]", 0x17C, "f"),
    ("bleed.distances[1]", 0x180, "f"),
    ("bleed.ycc.black", 0x184, "f"),
    ("bleed.ycc.white", 0x188, "f"),
    ("bleed.ycc.saturation", 0x18C, "f"),
    ("bleed.useDarkenBlending", 0x1C9, "?"),
    ("sdrAdjustment.headroomTransitionPoint", 0x1D0, "f"),
    ("sdrAdjustment.shadowOpacityShift", 0x1D4, "f"),
    ("sdrAdjustment.faceDimming.whitePointShift", 0x1D8, "f"),
    ("sdrAdjustment.faceDimming.distances[0]", 0x1E0, "d"),
    ("sdrAdjustment.faceDimming.distances[1]", 0x1E8, "d"),
    ("flags.rawValue", 0x1F0, "Q"),
)

RAW_OPTIONAL_COLOR_FIELDS: Tuple[Tuple[str, int, int], ...] = (
    ("shadow.ycc.normalFill", 0x04C, 20),
    ("shadow.ycc.dodgeFill", 0x060, 20),
    ("shadow.ycc.burnFill", 0x074, 20),
    ("face.ycc.normalFill", 0x124, 20),
    ("face.ycc.dodgeFill", 0x138, 20),
    ("face.ycc.burnFill", 0x14C, 20),
    ("bleed.ycc.normalFill", 0x190, 20),
    ("bleed.ycc.dodgeFill", 0x1A4, 20),
    ("bleed.ycc.burnFill", 0x1B8, 20),
)


class AnalysisError(RuntimeError):
    """Raised when retained evidence differs from the frozen contract."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def general_register(entry: Mapping[str, object], name: str) -> int:
    registers = entry["registers"]
    if not isinstance(registers, dict):
        raise AnalysisError("register payload is not an object")
    general = registers["general"]
    if not isinstance(general, list):
        raise AnalysisError("general-register payload is not an array")
    matches = [record for record in general if record.get("name") == name]
    if len(matches) != 1:
        raise AnalysisError("expected one register " + name)
    value = matches[0].get("unsignedValue")
    if not isinstance(value, int):
        raise AnalysisError("register has no unsigned integer value: " + name)
    return value


def snapshot_bytes(snapshot: Mapping[str, object], label: str) -> bytes:
    hexadecimal = snapshot.get("hex")
    byte_count = snapshot.get("byteCount")
    if not isinstance(hexadecimal, str) or not isinstance(byte_count, int):
        raise AnalysisError(label + " snapshot is incomplete")
    try:
        decoded = bytes.fromhex(hexadecimal)
    except ValueError as error:
        raise AnalysisError(label + " snapshot is not hexadecimal") from error
    if len(decoded) != byte_count:
        raise AnalysisError(label + " byte count differs")
    return decoded


def scalar_record(payload: bytes, name: str, offset: int, code: str) -> Mapping[str, object]:
    byte_count = struct.calcsize("<" + code)
    raw = payload[offset : offset + byte_count]
    if len(raw) != byte_count:
        raise AnalysisError("scalar exceeds complete payload: " + name)
    value = struct.unpack("<" + code, raw)[0]
    if isinstance(value, float) and not math.isfinite(value):
        raise AnalysisError("non-finite scalar: " + name)
    return {
        "name": name,
        "offset": "0x{:03x}".format(offset),
        "byteCount": byte_count,
        "hex": raw.hex(),
        "value": value,
    }


def validate_metadata(metadata: Mapping[str, object]) -> None:
    background_filter = metadata.get("backgroundFilter")
    if not isinstance(background_filter, dict):
        raise AnalysisError("metadata result has no BackgroundFilter")
    value_metadata = background_filter.get("metadata")
    if not isinstance(value_metadata, dict):
        raise AnalysisError("BackgroundFilter metadata is absent")
    if value_metadata.get("size") != EXPECTED_COMPLETE_PAYLOAD_BYTE_COUNT:
        raise AnalysisError("BackgroundFilter size differs")
    if value_metadata.get("fieldOffsets") != [
        0,
        8,
        0x98,
        0xE0,
        0x114,
        0x160,
        0x1D0,
        0x1F0,
    ]:
        raise AnalysisError("BackgroundFilter top-level offsets differ")


def analyze(trace_path: Path, metadata_path: Path) -> Mapping[str, object]:
    if sha256_file(trace_path) != EXPECTED_TRACE_SHA256:
        raise AnalysisError("retained trace SHA-256 differs")
    if sha256_file(metadata_path) != EXPECTED_METADATA_RESULT_SHA256:
        raise AnalysisError("metadata result SHA-256 differs")
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(trace, dict) or not isinstance(metadata, dict):
        raise AnalysisError("input root must be an object")
    validate_metadata(metadata)

    callee_trace = trace.get("case22CalleeTrace")
    provider_trace = trace.get("case22ProviderTrace")
    if not isinstance(callee_trace, dict) or not isinstance(provider_trace, dict):
        raise AnalysisError("nested case-22 traces are absent")
    callee_entry = callee_trace.get("entry")
    provider_entry = provider_trace.get("entry")
    if not isinstance(callee_entry, dict) or not isinstance(provider_entry, dict):
        raise AnalysisError("nested case-22 entries are absent")
    wrapper_snapshot = callee_entry.get("object")
    provider_snapshot = provider_entry.get("object")
    if not isinstance(wrapper_snapshot, dict) or not isinstance(provider_snapshot, dict):
        raise AnalysisError("object snapshots are absent")

    wrapper = snapshot_bytes(wrapper_snapshot, "wrapper")
    provider_prefix = snapshot_bytes(provider_snapshot, "provider prefix")
    wrapper_address = general_register(callee_entry, "x0")
    provider_address = general_register(provider_entry, "x20")
    header_byte_count = provider_address - wrapper_address
    if header_byte_count != EXPECTED_WRAPPER_HEADER_BYTE_COUNT:
        raise AnalysisError("wrapper payload offset differs from 16")
    if wrapper_snapshot.get("address") != wrapper_address:
        raise AnalysisError("wrapper snapshot address differs from entry x0")
    if provider_snapshot.get("address") != provider_address:
        raise AnalysisError("provider snapshot address differs from entry x20")
    if len(provider_prefix) != EXPECTED_PROVIDER_PREFIX_BYTE_COUNT:
        raise AnalysisError("provider prefix byte count differs from 384")
    if sha256_bytes(provider_prefix) != EXPECTED_PROVIDER_PREFIX_SHA256:
        raise AnalysisError("provider prefix SHA-256 differs")

    payload_end = header_byte_count + EXPECTED_COMPLETE_PAYLOAD_BYTE_COUNT
    complete_payload = wrapper[header_byte_count:payload_end]
    if len(complete_payload) != EXPECTED_COMPLETE_PAYLOAD_BYTE_COUNT:
        raise AnalysisError("wrapper does not retain the complete payload")
    if complete_payload[: len(provider_prefix)] != provider_prefix:
        raise AnalysisError("provider prefix differs from the wrapper payload")

    decoded_scalars = [
        scalar_record(complete_payload, name, offset, code)
        for name, offset, code in SCALARS
    ]
    raw_optional_colors = []
    for name, offset, byte_count in RAW_OPTIONAL_COLOR_FIELDS:
        raw = complete_payload[offset : offset + byte_count]
        if len(raw) != byte_count:
            raise AnalysisError("optional color exceeds payload: " + name)
        raw_optional_colors.append(
            {
                "name": name,
                "offset": "0x{:03x}".format(offset),
                "byteCount": byte_count,
                "hex": raw.hex(),
            }
        )

    tail = complete_payload[EXPECTED_PROVIDER_PREFIX_BYTE_COUNT:]
    source_path = Path(__file__).resolve()
    return {
        "designLibraryBackgroundFilterRetainedPayloadAnalysisSchemaVersion": 1,
        "classification": (
            "retrospective recovery of the complete provider value from the retained "
            "value-blind 4096-byte wrapper snapshot; no new Apple process was launched"
        ),
        "inputs": {
            "trace": str(trace_path),
            "traceSHA256": EXPECTED_TRACE_SHA256,
            "metadataResult": str(metadata_path),
            "metadataResultSHA256": EXPECTED_METADATA_RESULT_SHA256,
        },
        "source": {
            "path": "Analysis/analyze_designlibrary_background_filter_retained_payload.py",
            "sha256": sha256_file(source_path),
            "python": sys.version.split()[0],
        },
        "wrapper": {
            "address": wrapper_address,
            "snapshotByteCount": len(wrapper),
            "headerByteCount": header_byte_count,
            "headerHex": wrapper[:header_byte_count].hex(),
        },
        "payload": {
            "address": provider_address,
            "byteCount": len(complete_payload),
            "hex": complete_payload.hex(),
            "sha256": sha256_bytes(complete_payload),
            "providerPrefixByteCount": len(provider_prefix),
            "providerPrefixSHA256": sha256_bytes(provider_prefix),
            "recoveredTailByteCount": len(tail),
            "recoveredTailHex": tail.hex(),
            "recoveredTailSHA256": sha256_bytes(tail),
        },
        "decodedScalars": decoded_scalars,
        "rawOptionalResolvedColors": raw_optional_colors,
        "claims": {
            "completeRetainedPayloadRecovered": True,
            "capturedProviderPrefixWasCompleteValue": False,
            "publicInputConstructionRecovered": False,
            "cropAllocationPolicyRecovered": False,
            "liquidGlassParityEstablished": False,
            "productionShaderChangeAuthorized": False,
        },
    }


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument(
        "--metadata-result",
        type=Path,
        default=Path(
            "Analysis/designlibrary_background_filter_metadata_local_macos_26_6_1_result.json"
        ),
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    try:
        result = analyze(arguments.trace, arguments.metadata_result)
    except (AnalysisError, OSError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        sys.stdout.write(encoded)
    else:
        arguments.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
