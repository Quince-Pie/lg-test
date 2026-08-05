#!/usr/bin/env python3
"""Validate and join multi-state public/private ``prepare_layer`` crop evidence."""

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path


TRACE_SCHEMA_VERSION = 1
VALIDATION_SCHEMA_VERSION = 1
TIMELINE_SCHEMA_VERSION = 5
UNIFORM_EVIDENCE_SCHEMA_VERSION = 9
PREPARE_LAYER_FUNCTION = (
    "CA::Render::Updater::prepare_layer(CA::Render::Updater::GlobalState&, "
    "CA::Render::Updater::LocalState&, CA::Render::LayerNode*, "
    "CA::Render::Updater::LayerShapes&, unsigned long long&)"
)
PREPARE_LAYER_SYMBOL_BYTE_COUNT = 40128
PREPARE_LAYER_FULL_CODE_SHA256 = (
    "fe58001369708e0276599f26865be03fdf1dd2348524f92a72c1427be8d1817c"
)
KNOWN_PREPARE_LAYER_WINDOWS = (
    (12764, 0x1000, "91fbe43da3533d7cd4578195b77c5a1aa0844105493c70635687e76adb7af768"),
    (14064, 0x1000, "9f67889b8a095f620d078f0c5c61eb0dca92e76916301a4ada40cf3b63eff9df"),
    (17944, 0x1000, "6472a0a0dbbb1fcdcbc75dcea63f28f2645cb58770ab0dc00ea17464db597c7f"),
    (19212, 0x1000, "756da544c0ac96badc07fc651b127e7eb8dcb244f98801335748e27feed2b5fa"),
    (19216, 0x1000, "e28e801599441f3aaf171ccc7ca5df86a0dc4c32a0d18062ab9a8c4627e9bc37"),
)
MARKER_NAME = "sourceLaterHandle"
MARKER_OFFSET = 0x3EF0
MARKER_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX = "28330b91"
REQUIRED_PREPARE_RECURSION_DEPTH = 4
MAXIMUM_MARKER_HIT_COUNT = 4096
MAXIMUM_QUALIFIED_RECORD_COUNT = 128
MAXIMUM_REJECTION_GROUP_COUNT = 64
MAXIMUM_BACKTRACE_FRAME_COUNT = 24
ROLE_STATE_BYTE_COUNT = 0x800
SOURCE_STATE_BYTE_COUNT = 0x180
STACK_STATE_BYTE_COUNT = 0x800
POINTER_STATE_BYTE_COUNT = 0x200
MINIMUM_POINTER_ADDRESS = 0x1_0000_0000
MAXIMUM_POINTER_ADDRESS = 0x0000_FFFF_FFFF_FFFF
GENERAL_REGISTER_NAMES = tuple("x%d" % index for index in range(30)) + (
    "sp",
    "pc",
    "cpsr",
)
POINTER_REGISTER_NAMES = (
    "x0",
    "x1",
    "x2",
    "x3",
    "x4",
    "x5",
    "x19",
    "x23",
    "x24",
    "x27",
    "x28",
)
PREPARE_FRAME_REGISTER_NAMES = ("x19", "x28", "x29", "sp", "pc")
DIRECT_TIMELINE_CALLER_FRAGMENT = "transitionBackgroundUniformEvidence("
REQUIRED_CALLER_FRAGMENTS = (
    "carendererUniformEvidence(",
    "localTransitionCARendererEvidence(",
    DIRECT_TIMELINE_CALLER_FRAGMENT,
)
EXCLUDED_CALLER_FRAGMENTS = (
    "transitionFixedStateAllocationEvidence(",
    "transitionPathIsolationAllocationEvidence(",
    "transitionMatrixUniformBasisEvidence(",
)
ROLE_VISIBLE_CROP_OFFSET = 0x260
ROLE_WORKING_CROP_OFFSET = 0x270
ROLE_AGGREGATE_OFFSET = 0x290
ROLE_VIEWPORT_OFFSET = 0x2F0
ROLE_ALTERNATE_OFFSET = 0x520
ROLE_RECURSIVE_CHILD_OFFSET = 0x620
EXPECTED_NORMAL_RECORD_COUNT = 32
EXPECTED_TIMELINE_SAMPLE_COUNT = 33


EXPECTED_CONFIGURATION = {
    "prepareLayerFunction": PREPARE_LAYER_FUNCTION,
    "prepareLayerSymbolByteCount": PREPARE_LAYER_SYMBOL_BYTE_COUNT,
    "prepareLayerFullCodeSHA256": PREPARE_LAYER_FULL_CODE_SHA256,
    "knownPrepareLayerWindows": [
        {"offset": offset, "byteCount": count, "sha256": digest}
        for offset, count, digest in KNOWN_PREPARE_LAYER_WINDOWS
    ],
    "markerName": MARKER_NAME,
    "markerOffset": MARKER_OFFSET,
    "markerInstructionRawLittleEndianHex": (
        MARKER_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
    ),
    "requiredPrepareRecursionDepth": REQUIRED_PREPARE_RECURSION_DEPTH,
    "maximumMarkerHitCount": MAXIMUM_MARKER_HIT_COUNT,
    "maximumQualifiedRecordCount": MAXIMUM_QUALIFIED_RECORD_COUNT,
    "maximumRejectionGroupCount": MAXIMUM_REJECTION_GROUP_COUNT,
    "maximumBacktraceFrameCount": MAXIMUM_BACKTRACE_FRAME_COUNT,
    "roleStateByteCount": ROLE_STATE_BYTE_COUNT,
    "sourceStateByteCount": SOURCE_STATE_BYTE_COUNT,
    "stackStateByteCount": STACK_STATE_BYTE_COUNT,
    "pointerStateByteCount": POINTER_STATE_BYTE_COUNT,
    "pointerAddressRange": [MINIMUM_POINTER_ADDRESS, MAXIMUM_POINTER_ADDRESS],
    "generalRegisterNames": list(GENERAL_REGISTER_NAMES),
    "pointerRegisterNames": list(POINTER_REGISTER_NAMES),
    "prepareFrameRegisterNames": list(PREPARE_FRAME_REGISTER_NAMES),
    "requiredCallerFragments": list(REQUIRED_CALLER_FRAGMENTS),
    "excludedCallerFragments": list(EXCLUDED_CALLER_FRAGMENTS),
    "selectionRule": (
        "retain every exact prepare_layer+0x3ef0 stop whose backtrace has "
        "exactly four structural prepare_layer frames and the direct normal "
        "transitionBackgroundUniformEvidence -> localTransitionCARendererEvidence "
        "-> carendererUniformEvidence caller chain, excluding every matrix, "
        "fixed-state, and path-isolation intervention caller; never inspect "
        "crop bytes when selecting"
    ),
    "ordinalJoinRule": (
        "qualified marker records in callback order join one-to-one to "
        "dynamicBackgroundUniforms.records in array order; duplicate or "
        "missing records fail validation"
    ),
    "hardwareWatchpointsUsed": False,
}


def mapping(value, label):
    if not isinstance(value, dict):
        raise ValueError(label + " is not an object")
    return value


def sequence(value, label):
    if not isinstance(value, list):
        raise ValueError(label + " is not an array")
    return value


def integer(value, label):
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(label + " is not an integer")
    return value


def number(value, label):
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
    ):
        raise ValueError(label + " is not a finite number")
    return float(value)


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path, label):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(label + " is unreadable: " + str(error)) from error


def hexadecimal_payload(value, byte_count, label):
    if not isinstance(value, str) or len(value) != byte_count * 2:
        raise ValueError(label + " hex length differs")
    try:
        payload = bytes.fromhex(value)
    except ValueError as error:
        raise ValueError(label + " is not hexadecimal") from error
    if len(payload) != byte_count:
        raise ValueError(label + " payload length differs")
    return payload


def memory_snapshot(value, expected_byte_count, label, expected_address=None):
    record = mapping(value, label)
    address = integer(record.get("address"), label + " address")
    byte_count = integer(record.get("byteCount"), label + " byte count")
    if byte_count != expected_byte_count:
        raise ValueError(label + " byte count differs")
    if expected_address is not None and address != expected_address:
        raise ValueError(label + " address differs")
    payload = hexadecimal_payload(record.get("hex"), byte_count, label)
    if record.get("sha256") != hashlib.sha256(payload).hexdigest():
        raise ValueError(label + " SHA-256 differs")
    return address, payload


def register_values(value, names, label):
    records = sequence(value, label)
    if len(records) != len(names):
        raise ValueError(label + " inventory differs")
    result = {}
    for expected_name, raw in zip(names, records):
        record = mapping(raw, label + " " + expected_name)
        if record.get("name") != expected_name:
            raise ValueError(label + " register order differs")
        byte_count = integer(record.get("byteCount"), label + " byte count")
        expected_bytes = 4 if expected_name in ("cpsr",) else 8
        if byte_count != expected_bytes:
            raise ValueError(label + " register byte count differs")
        payload = hexadecimal_payload(
            record.get("hex"), byte_count, label + " " + expected_name
        )
        unsigned = integer(
            record.get("unsignedValue"), label + " unsigned value"
        )
        if unsigned != int.from_bytes(payload, "little"):
            raise ValueError(label + " register value differs from bytes")
        result[expected_name] = unsigned
    return result


def frame_record(value, label):
    record = mapping(value, label)
    integer(record.get("frameIndex"), label + " frame index")
    integer(record.get("pc"), label + " PC")
    function = record.get("function")
    if function is not None and not isinstance(function, str):
        raise ValueError(label + " function differs")
    return record


def decode_role(payload):
    if len(payload) != ROLE_STATE_BYTE_COUNT:
        raise ValueError("role payload size differs")
    aggregate = struct.unpack_from("<4d", payload, ROLE_AGGREGATE_OFFSET)
    viewport = struct.unpack_from("<4d", payload, ROLE_VIEWPORT_OFFSET)
    alternate = struct.unpack_from("<4d", payload, ROLE_ALTERNATE_OFFSET)
    recursive_child = struct.unpack_from(
        "<4d", payload, ROLE_RECURSIVE_CHILD_OFFSET
    )
    for label, values in (
        ("aggregate", aggregate),
        ("viewport", viewport),
        ("alternate", alternate),
        ("recursive child", recursive_child),
    ):
        if not all(math.isfinite(value) for value in values):
            raise ValueError(label + " contains a non-finite binary64 value")
    if aggregate[2] < 0 or aggregate[3] < 0:
        raise ValueError("aggregate has negative extent")
    return {
        "visibleCropI32": list(
            struct.unpack_from("<4i", payload, ROLE_VISIBLE_CROP_OFFSET)
        ),
        "workingCropI32": list(
            struct.unpack_from("<4i", payload, ROLE_WORKING_CROP_OFFSET)
        ),
        "aggregateF64": list(aggregate),
        "aggregateF64Hex": payload[
            ROLE_AGGREGATE_OFFSET : ROLE_AGGREGATE_OFFSET + 32
        ].hex(),
        "viewportF64": list(viewport),
        "alternateF64": list(alternate),
        "recursiveChildF64": list(recursive_child),
    }


def layer_state(records, path):
    matches = [
        mapping(record, "captured layer state")
        for record in sequence(records, "captured layer states")
        if mapping(record, "captured layer state").get("path") == path
    ]
    if len(matches) != 1:
        raise ValueError("captured layer path %r is not unique" % (path,))
    return matches[0]


def validate_trace(trace):
    if trace.get("prepareLayerCropTransferTraceSchemaVersion") != TRACE_SCHEMA_VERSION:
        raise ValueError("crop transfer trace schema differs")
    if trace.get("status") != "finalized":
        raise ValueError("crop transfer trace was not finalized")
    if trace.get("statusBeforeFinalization") != "crop-transfer-marker-active":
        raise ValueError("crop transfer trace did not remain active to exit")
    if trace.get("configuration") != EXPECTED_CONFIGURATION:
        raise ValueError("crop transfer trace configuration differs")
    if sequence(trace.get("failures"), "trace failures"):
        raise ValueError("crop transfer trace contains failures")
    if integer(trace.get("finalFailureCount"), "final failure count") != 0:
        raise ValueError("final failure count differs")
    if integer(
        trace.get("finalDiscardedQualifiedRecordCount"),
        "discarded qualified record count",
    ) != 0:
        raise ValueError("qualified records were discarded")
    if integer(
        trace.get("finalUnretainedRejectionCount"),
        "unretained rejection count",
    ) != 0:
        raise ValueError("marker rejections were not retained")
    terminal = mapping(trace.get("terminalProcess"), "terminal process")
    if terminal.get("exited") is not True or terminal.get("exitStatus") != 0:
        raise ValueError("capture target did not exit normally")
    prepare = mapping(trace.get("prepareLayer"), "prepare layer")
    start = integer(prepare.get("symbolStart"), "prepare symbol start")
    end = integer(prepare.get("symbolEnd"), "prepare symbol end")
    if (
        prepare.get("function") != PREPARE_LAYER_FUNCTION
        or end - start != PREPARE_LAYER_SYMBOL_BYTE_COUNT
        or prepare.get("symbolByteCount") != PREPARE_LAYER_SYMBOL_BYTE_COUNT
        or prepare.get("fullCodeSHA256") != PREPARE_LAYER_FULL_CODE_SHA256
    ):
        raise ValueError("prepare_layer identity differs")
    marker = mapping(prepare.get("marker"), "prepare marker")
    if (
        marker.get("name") != MARKER_NAME
        or marker.get("offset") != MARKER_OFFSET
        or marker.get("address") != start + MARKER_OFFSET
        or marker.get("instructionRawLittleEndianHex")
        != MARKER_INSTRUCTION_RAW_LITTLE_ENDIAN_HEX
    ):
        raise ValueError("prepare_layer marker identity differs")
    callbacks = sequence(trace.get("callbackOrder"), "callback order")
    final_sequence = integer(
        trace.get("finalCallbackSequence"), "final callback sequence"
    )
    if final_sequence != len(callbacks):
        raise ValueError("callback sequence count differs")
    for expected, raw in enumerate(callbacks, start=1):
        callback = mapping(raw, "callback %d" % expected)
        if callback.get("sequence") != expected:
            raise ValueError("callback sequence is not contiguous")
    records = sequence(trace.get("qualifiedRecords"), "qualified records")
    if (
        len(records) != EXPECTED_NORMAL_RECORD_COUNT
        or trace.get("finalQualifiedRecordCount") != len(records)
    ):
        raise ValueError("qualified normal-render record count differs")
    marker_hit_count = integer(trace.get("finalMarkerHitCount"), "marker hit count")
    rejected_count = integer(
        trace.get("finalRejectedMarkerCount"), "rejected marker count"
    )
    rejection_groups = sequence(trace.get("rejectionGroups"), "rejection groups")
    if len(rejection_groups) > MAXIMUM_REJECTION_GROUP_COUNT:
        raise ValueError("rejection group count exceeds its bound")
    grouped_rejection_count = 0
    for index, raw_group in enumerate(rejection_groups):
        group = mapping(raw_group, "rejection group %d" % index)
        if not isinstance(group.get("reason"), str) or not group["reason"]:
            raise ValueError("rejection group reason differs")
        integer(group.get("prepareRecursionDepth"), "rejection group depth")
        hit_count = integer(group.get("hitCount"), "rejection group hit count")
        if hit_count <= 0:
            raise ValueError("rejection group hit count is not positive")
        grouped_rejection_count += hit_count
    if grouped_rejection_count != rejected_count:
        raise ValueError("rejected marker accounting differs")
    if marker_hit_count != len(records) + rejected_count:
        raise ValueError("marker hit accounting differs")
    if marker_hit_count > MAXIMUM_MARKER_HIT_COUNT:
        raise ValueError("marker hit count exceeds its bound")
    return start, records


def validate_timeline(timeline, expected_geometry):
    if (
        timeline.get("schemaVersion") != TIMELINE_SCHEMA_VERSION
        or timeline.get("material") != "clear"
        or timeline.get("appearance") != "light"
        or timeline.get("direction") != "materialize"
        or timeline.get("animationCurve") != "linear"
        or timeline.get("sampleCount") != EXPECTED_TIMELINE_SAMPLE_COUNT
        or timeline.get("failedSamples") != 0
        or timeline.get("windowBackingScaleFactor") != 1
    ):
        raise ValueError("timeline metadata differs")
    geometry = mapping(timeline.get("geometry"), "timeline geometry")
    if geometry.get("name") != expected_geometry:
        raise ValueError("timeline geometry differs")
    samples = sequence(timeline.get("samples"), "timeline samples")
    if len(samples) != EXPECTED_TIMELINE_SAMPLE_COUNT:
        raise ValueError("timeline sample inventory differs")
    uniforms = mapping(
        timeline.get("dynamicBackgroundUniforms"),
        "dynamic background uniforms",
    )
    if (
        uniforms.get("schemaVersion") != UNIFORM_EVIDENCE_SCHEMA_VERSION
        or uniforms.get("executed") is not True
        or uniforms.get("evidenceMode") != "allocation-metadata-v1"
        or uniforms.get("sampleCount") != EXPECTED_NORMAL_RECORD_COUNT
        or uniforms.get("executedSampleCount") != EXPECTED_NORMAL_RECORD_COUNT
        or uniforms.get("fixedStateInterventions", {}).get("requested") is True
        or uniforms.get("pathIsolationInterventions", {}).get("requested") is True
    ):
        raise ValueError("dynamic background uniform metadata differs")
    records = sequence(uniforms.get("records"), "uniform records")
    if len(records) != EXPECTED_NORMAL_RECORD_COUNT:
        raise ValueError("uniform record inventory differs")
    if [record.get("sampleIndex") for record in records] != list(range(1, 33)):
        raise ValueError("uniform sample order differs")
    return geometry, records


def validate_record(raw, ordinal, start):
    record = mapping(raw, "qualified record %d" % ordinal)
    if (
        record.get("recordIndex") != ordinal - 1
        or record.get("normalRenderOrdinal") != ordinal
        or record.get("prepareRecursionDepth") != REQUIRED_PREPARE_RECURSION_DEPTH
        or record.get("pc") != start + MARKER_OFFSET
    ):
        raise ValueError("qualified record ordinal or marker differs")
    backtrace = [
        frame_record(value, "backtrace frame")
        for value in sequence(record.get("backtrace"), "backtrace")
    ]
    functions = "\n".join((frame.get("function") or "") for frame in backtrace)
    if (
        not all(fragment in functions for fragment in REQUIRED_CALLER_FRAGMENTS)
        or any(fragment in functions for fragment in EXCLUDED_CALLER_FRAGMENTS)
    ):
        raise ValueError("qualified record caller chain differs")
    registers = register_values(
        record.get("registers"), GENERAL_REGISTER_NAMES, "marker registers"
    )
    identity = mapping(record.get("frameIdentity"), "frame identity")
    if (
        identity.get("threadID") != record.get("threadID")
        or identity.get("roleBase") != registers["x19"]
        or identity.get("source") != registers["x28"]
        or identity.get("framePointer") != registers["x29"]
    ):
        raise ValueError("qualified frame identity differs")
    _role_address, role = memory_snapshot(
        record.get("roleState"),
        ROLE_STATE_BYTE_COUNT,
        "qualified role state",
        expected_address=registers["x19"],
    )
    memory_snapshot(
        record.get("sourceState"),
        SOURCE_STATE_BYTE_COUNT,
        "qualified source state",
        expected_address=registers["x28"],
    )
    memory_snapshot(
        record.get("stackState"),
        STACK_STATE_BYTE_COUNT,
        "qualified stack state",
        expected_address=registers["sp"],
    )
    pointer_states = sequence(record.get("pointerStates"), "pointer states")
    seen_addresses = set()
    for index, raw_pointer in enumerate(pointer_states):
        pointer = mapping(raw_pointer, "pointer state %d" % index)
        name = pointer.get("register")
        if name not in POINTER_REGISTER_NAMES:
            raise ValueError("pointer state register differs")
        address = integer(pointer.get("address"), "pointer state address")
        if address != registers[name] or address in seen_addresses:
            raise ValueError("pointer state address differs or repeats")
        seen_addresses.add(address)
        if pointer.get("readable") is True:
            memory_snapshot(
                pointer,
                POINTER_STATE_BYTE_COUNT,
                "readable pointer state",
                expected_address=address,
            )
        elif pointer.get("readable") is not False:
            raise ValueError("pointer state readability differs")
    prepare_frames = sequence(record.get("prepareFrames"), "prepare frames")
    if len(prepare_frames) != REQUIRED_PREPARE_RECURSION_DEPTH:
        raise ValueError("prepare frame inventory differs")
    for index, raw_frame in enumerate(prepare_frames):
        prepared = mapping(raw_frame, "prepare frame %d" % index)
        if prepared.get("frameIndex") != index:
            raise ValueError("prepare frame order differs")
        frame = frame_record(prepared.get("frame"), "prepare frame")
        if frame.get("function") != PREPARE_LAYER_FUNCTION:
            raise ValueError("prepare frame function differs")
        frame_registers = register_values(
            prepared.get("registers"),
            PREPARE_FRAME_REGISTER_NAMES,
            "prepare frame registers",
        )
        _address, frame_role = memory_snapshot(
            prepared.get("roleState"),
            ROLE_STATE_BYTE_COUNT,
            "prepare frame role",
            expected_address=frame_registers["x19"],
        )
        if index == 0 and (
            frame_registers["x19"] != registers["x19"]
            or frame_registers["x28"] != registers["x28"]
            or frame_registers["x29"] != registers["x29"]
            or frame_role != role
        ):
            raise ValueError("top prepare frame does not match marker state")
    return decode_role(role)


def validate(trace_path, timeline_path, expected_geometry):
    trace = mapping(load_json(trace_path, "trace"), "trace")
    timeline = mapping(load_json(timeline_path, "timeline"), "timeline")
    start, trace_records = validate_trace(trace)
    geometry, uniform_records = validate_timeline(timeline, expected_geometry)
    joined = []
    for ordinal, (raw_trace, raw_uniform) in enumerate(
        zip(trace_records, uniform_records), start=1
    ):
        private = validate_record(raw_trace, ordinal, start)
        uniform = mapping(raw_uniform, "uniform record %d" % ordinal)
        render = mapping(uniform.get("render"), "uniform render")
        if render.get("executed") is not True:
            raise ValueError("uniform render did not execute")
        expected_capture = "transition-background-uniform-%02d" % ordinal
        if render.get("capture") != expected_capture:
            raise ValueError("uniform capture ordinal differs")
        carrier = layer_state(uniform.get("capturedLayerStates"), [1])
        carrier_position = [
            number(value, "carrier position")
            for value in sequence(carrier.get("position"), "carrier position")
        ]
        carrier_bounds = [
            number(value, "carrier bounds")
            for value in sequence(carrier.get("bounds"), "carrier bounds")
        ]
        if len(carrier_position) != 2 or len(carrier_bounds) != 4:
            raise ValueError("carrier geometry inventory differs")
        viewport = private["viewportF64"]
        expected_viewport = [
            0.0,
            0.0,
            number(geometry.get("windowWidth"), "window width"),
            number(geometry.get("windowHeight"), "window height"),
        ]
        if [struct.pack("<d", value) for value in viewport] != [
            struct.pack("<d", value) for value in expected_viewport
        ]:
            raise ValueError("private viewport does not bit-match public window")
        joined.append(
            {
                "normalRenderOrdinal": ordinal,
                "sampleIndex": uniform.get("sampleIndex"),
                "capture": render.get("capture"),
                "remaining": number(uniform.get("remaining"), "remaining"),
                "carrierPosition": carrier_position,
                "carrierBounds": carrier_bounds,
                "private": private,
                "traceRecordIndex": raw_trace.get("recordIndex"),
                "traceCallbackSequence": raw_trace.get("callbackSequence"),
            }
        )
    return {
        "prepareLayerCropTransferValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "classification": (
            "prospective-structural-multi-state-public-private-crop-join; "
            "discovery-only-general-law-and-product-parity-remain-sealed"
        ),
        "conclusion": "success",
        "prospectiveCaptureIntegrityGatePassed": True,
        "inputs": {
            "trace": str(trace_path),
            "traceSHA256": sha256_file(trace_path),
            "timeline": str(timeline_path),
            "timelineSHA256": sha256_file(timeline_path),
        },
        "geometry": geometry,
        "recordCount": len(joined),
        "records": joined,
        "sealedConclusion": {
            "exactPrepareLayerCodePassed": True,
            "cropIndependentStructuralSelectionPassed": True,
            "oneQualifiedRecordPerNormalRenderPassed": True,
            "publicPrivateOrdinalJoinPassed": True,
            "completeRoleBytesCaptured": True,
            "allAncestorRoleBytesCaptured": True,
            "hardwareWatchpointsUsed": False,
            "generalCropPolicyRecovered": False,
            "unseenGeometryHoldoutPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate multi-state prepare_layer crop-transfer evidence"
    )
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("--expected-geometry", required=True)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        result = validate(
            arguments.trace,
            arguments.timeline,
            arguments.expected_geometry,
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
