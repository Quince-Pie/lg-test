#!/usr/bin/env python3
"""Validate the preregistered LLDB crop-writer trace without opening semantics."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


EXPECTED_TRACE_SCHEMA_VERSION = 4
EXPECTED_CAPTURE_BACKDROP_SYMBOL = (
    "_ZN2CA3OGL16capture_backdropERNS0_8RendererEPKNS0_5LayerE"
)
EXPECTED_CAPTURE_BACKDROP_CODE_SHA256 = (
    "14f25960556bec9e88ba8ade176ee7f1d39b84726226ade3eb1b0f1be00b70d2"
)
EXPECTED_WATCH_SPECS = {
    "sourceSelectedRectI32": ("source", 0x50),
    "ownerSelectedRectF64": ("owner", 0xE0),
    "ownerRegion248Handle": ("owner", 0x248),
    "layerStateSelectedRectI32": ("layerState", 0xB0),
}
EXPECTED_CLASSIFICATION = (
    "preregistered-bounded-lldb-hardware-watchpoint-trace-of-private-crop-"
    "writers; not-a-public-crop-law-unseen-transfer-or-product-parity-claim"
)
EXPECTED_WATCHPOINT_IDENTITY_RULE = (
    "distinct SBWatchpoint IDs and exact addresses; deprecated "
    "GetHardwareIndex returns -1"
)
MAXIMUM_EVENT_COUNT = 24
MAXIMUM_HITS_PER_WATCHPOINT = 6
MAXIMUM_BACKTRACE_FRAME_COUNT = 32
MAXIMUM_LATE_CANDIDATE_COUNT = 512
MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT = 16
PC_CENTERED_CODE_WINDOW_BYTE_COUNT = 0x1000
PC_CENTERED_CODE_WINDOW_BACKTRACK = 0x800
STACK_SNAPSHOT_BYTE_COUNT = 0x800
REGISTER_POINTER_SNAPSHOT_BYTE_COUNT = 0x100
REGISTER_POINTER_SNAPSHOT_BACKTRACK = 0x40
GENERAL_REGISTER_NAMES = tuple(f"x{index}" for index in range(31)) + (
    "sp",
    "pc",
    "cpsr",
)
SIMD_REGISTER_NAMES = tuple(f"v{index}" for index in range(32)) + (
    "fpsr",
    "fpcr",
)
POINTER_PROBE_REGISTER_NAMES = tuple(f"x{index}" for index in range(29))
MINIMUM_POINTER_PROBE_ADDRESS = 0x1_0000_0000
MAXIMUM_POINTER_PROBE_ADDRESS = 0x0000_FFFF_FFFF_FFFF
OBJECT_SNAPSHOT_SPECS = {
    "source": 0x180,
    "owner": 0x300,
    "layer": 0x200,
    "layerState": 0x180,
}
EXPECTED_PREPARE_LAYER_FUNCTION = (
    "CA::Render::Updater::prepare_layer(CA::Render::Updater::GlobalState&, "
    "CA::Render::Updater::LocalState&, CA::Render::LayerNode*, "
    "CA::Render::Updater::LayerShapes&, unsigned long long&)"
)
EXPECTED_CHANGED_PREPARE_LAYER_OFFSETS = {
    "sourceSelectedRectI32": {0x530C, 0x5310},
    "ownerSelectedRectF64": {0x4E18},
    "ownerRegion248Handle": {0x3EF0},
    "layerStateSelectedRectI32": {0x55C4},
}
QUARTZ_CORE_PATH_FRAGMENT = "/QuartzCore.framework/"


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} differs")
    return value


def sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{label} differs")
    return value


def integer(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} differs")
    return value


def hexadecimal_payload(value: Any, byte_count: int, label: str) -> bytes:
    if not isinstance(value, str):
        raise ValueError(f"{label} differs")
    try:
        payload = bytes.fromhex(value)
    except ValueError as error:
        raise ValueError(f"{label} differs") from error
    if len(payload) != byte_count:
        raise ValueError(f"{label} differs")
    return payload


def memory_snapshot(
    value: Any,
    label: str,
    *,
    expected_address: int | None = None,
    expected_byte_count: int,
) -> Mapping[str, Any]:
    snapshot = mapping(value, label)
    address = integer(snapshot.get("address"), f"{label} address")
    byte_count = integer(snapshot.get("byteCount"), f"{label} byte count")
    if (
        address == 0
        or byte_count != expected_byte_count
        or (expected_address is not None and address != expected_address)
    ):
        raise ValueError(f"{label} bounds differ")
    payload = hexadecimal_payload(snapshot.get("hex"), byte_count, label)
    if snapshot.get("sha256") != hashlib.sha256(payload).hexdigest():
        raise ValueError(f"{label} identity differs")
    return snapshot


def register_record(
    value: Any,
    expected_name: str,
    expected_byte_count: int,
    label: str,
) -> Mapping[str, Any]:
    record = mapping(value, label)
    if (
        record.get("name") != expected_name
        or record.get("byteCount") != expected_byte_count
        or record.get("valueString") is not None
        and not isinstance(record.get("valueString"), str)
    ):
        raise ValueError(f"{label} identity differs")
    payload = hexadecimal_payload(record.get("hex"), expected_byte_count, label)
    if expected_byte_count <= 8:
        unsigned = integer(record.get("unsignedValue"), f"{label} unsigned value")
        if unsigned != int.from_bytes(payload, "little"):
            raise ValueError(f"{label} raw value differs")
    elif "unsignedValue" in record:
        raise ValueError(f"{label} oversized unsigned value differs")
    return record


def operand_snapshot(
    value: Any,
    label: str,
    addresses: Mapping[str, Any],
) -> Mapping[str, Any]:
    snapshot = mapping(value, label)
    registers = mapping(snapshot.get("registers"), f"{label} registers")
    general_values = list(sequence(registers.get("general"), f"{label} general"))
    simd_values = list(sequence(registers.get("simd"), f"{label} SIMD"))
    if len(general_values) != len(GENERAL_REGISTER_NAMES) or len(simd_values) != len(
        SIMD_REGISTER_NAMES
    ):
        raise ValueError(f"{label} register inventory differs")
    general = {}
    for name, record_value in zip(GENERAL_REGISTER_NAMES, general_values, strict=True):
        byte_count = 4 if name == "cpsr" else 8
        general[name] = register_record(
            record_value,
            name,
            byte_count,
            f"{label} register {name}",
        )
    for name, record_value in zip(SIMD_REGISTER_NAMES, simd_values, strict=True):
        byte_count = 4 if name in {"fpsr", "fpcr"} else 16
        register_record(
            record_value,
            name,
            byte_count,
            f"{label} register {name}",
        )

    memory_snapshot(
        snapshot.get("stack"),
        f"{label} stack",
        expected_address=general["sp"]["unsignedValue"],
        expected_byte_count=STACK_SNAPSHOT_BYTE_COUNT,
    )
    objects = mapping(snapshot.get("objects"), f"{label} objects")
    if set(objects) != set(OBJECT_SNAPSHOT_SPECS):
        raise ValueError(f"{label} object inventory differs")
    for base, byte_count in OBJECT_SNAPSHOT_SPECS.items():
        memory_snapshot(
            objects.get(base),
            f"{label} object {base}",
            expected_address=integer(addresses.get(base), f"{base} address"),
            expected_byte_count=byte_count,
        )

    pointer_probes = [
        mapping(item, f"{label} pointer probe")
        for item in sequence(
            snapshot.get("registerPointerProbes"), f"{label} pointer probes"
        )
    ]
    pointer_failures = [
        mapping(item, f"{label} pointer failure")
        for item in sequence(
            snapshot.get("registerPointerProbeFailures"),
            f"{label} pointer failures",
        )
    ]
    probe_count = integer(
        snapshot.get("registerPointerProbeCount"), f"{label} pointer probe count"
    )
    if probe_count != len(pointer_probes) + len(pointer_failures):
        raise ValueError(f"{label} pointer probe count differs")

    expected_groups: defaultdict[int, list[str]] = defaultdict(list)
    for name in POINTER_PROBE_REGISTER_NAMES:
        address = general[name]["unsignedValue"]
        if MINIMUM_POINTER_PROBE_ADDRESS <= address <= MAXIMUM_POINTER_PROBE_ADDRESS:
            expected_groups[address - REGISTER_POINTER_SNAPSHOT_BACKTRACK].append(name)
    observed_groups = {}
    for item, succeeded in [
        *((probe, True) for probe in pointer_probes),
        *((failure, False) for failure in pointer_failures),
    ]:
        start = integer(item.get("address"), f"{label} pointer start")
        register_value = integer(
            item.get("registerValue"), f"{label} pointer register value"
        )
        names = list(sequence(item.get("registerNames"), f"{label} pointer registers"))
        if (
            start in observed_groups
            or register_value != start + REGISTER_POINTER_SNAPSHOT_BACKTRACK
            or names != expected_groups.get(start)
        ):
            raise ValueError(f"{label} pointer identity differs")
        observed_groups[start] = names
        if succeeded:
            memory_snapshot(
                item,
                f"{label} pointer memory",
                expected_address=start,
                expected_byte_count=REGISTER_POINTER_SNAPSHOT_BYTE_COUNT,
            )
        elif not isinstance(item.get("message"), str) or not item["message"]:
            raise ValueError(f"{label} pointer failure differs")
    if observed_groups != dict(expected_groups):
        raise ValueError(f"{label} pointer inventory differs")
    return snapshot


def numeric_vector(
    value: Any,
    count: int,
    label: str,
    *,
    integral: bool,
) -> list[int | float]:
    values = list(sequence(value, label))
    if len(values) != count:
        raise ValueError(f"{label} differs")
    for item in values:
        if integral:
            integer(item, label)
        elif (
            not isinstance(item, (int, float))
            or isinstance(item, bool)
            or not math.isfinite(float(item))
        ):
            raise ValueError(f"{label} differs")
    return values


def private_fields(value: Any, label: str) -> Mapping[str, Any]:
    fields = mapping(value, label)
    numeric_vector(
        fields.get("layerStateInputBoundsI32"),
        4,
        f"{label} layer-state input bounds",
        integral=True,
    )
    numeric_vector(
        fields.get("layerStateSelectedRectI32"),
        4,
        f"{label} layer-state selected rectangle",
        integral=True,
    )
    numeric_vector(
        fields.get("sourceSelectedRectI32"),
        4,
        f"{label} source selected rectangle",
        integral=True,
    )
    numeric_vector(
        fields.get("ownerSelectedRectF64"),
        4,
        f"{label} owner selected rectangle",
        integral=False,
    )
    integer(fields.get("ownerRegion248Handle"), f"{label} owner +0x248")
    integer(fields.get("ownerRegion270Handle"), f"{label} owner +0x270")
    return fields


def frame_record(value: Any, label: str) -> Mapping[str, Any]:
    frame = mapping(value, label)
    integer(frame.get("pc"), f"{label} PC")
    module = mapping(frame.get("module"), f"{label} module")
    if module.get("valid") is not True or not isinstance(module.get("path"), str):
        raise ValueError(f"{label} module differs")
    start = frame.get("symbolStart")
    offset = frame.get("symbolOffset")
    if start is not None:
        start = integer(start, f"{label} symbol start")
        if offset != frame["pc"] - start:
            raise ValueError(f"{label} symbol offset differs")
    elif offset is not None:
        raise ValueError(f"{label} unresolved symbol offset differs")
    return frame


def validate(trace_path: Path) -> dict[str, Any]:
    trace_sha256 = hashlib.sha256(trace_path.read_bytes()).hexdigest()
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    trace = mapping(trace, "writer trace")
    configuration = mapping(trace.get("configuration"), "trace configuration")
    expected_watch_specs = [
        {"name": name, "base": base, "offset": offset}
        for name, (base, offset) in EXPECTED_WATCH_SPECS.items()
    ]
    if (
        trace.get("captureBackdropWriterTraceSchemaVersion")
        != EXPECTED_TRACE_SCHEMA_VERSION
        or trace.get("classification") != EXPECTED_CLASSIFICATION
        or trace.get("status") != "finalized"
        or trace.get("statusBeforeFinalization")
        not in {"watchpoints-armed", "bounded-event-limit-reached"}
        or trace.get("finalFailureCount") != 0
        or sequence(trace.get("failures"), "trace failures") != []
        or configuration.get("captureBackdropSymbol")
        != EXPECTED_CAPTURE_BACKDROP_SYMBOL
        or configuration.get("captureBackdropCodeByteCount") != 0x4000
        or configuration.get("captureBackdropCodeSHA256")
        != EXPECTED_CAPTURE_BACKDROP_CODE_SHA256
        or configuration.get("lateInstructionOffset") != 0x2B58
        or configuration.get("watchpointByteCount") != 8
        or configuration.get("watchpointIdentityRule")
        != EXPECTED_WATCHPOINT_IDENTITY_RULE
        or configuration.get("maximumHitsPerWatchpoint") != MAXIMUM_HITS_PER_WATCHPOINT
        or configuration.get("maximumTotalHits") != MAXIMUM_EVENT_COUNT
        or configuration.get("maximumBacktraceFrameCount")
        != MAXIMUM_BACKTRACE_FRAME_COUNT
        or configuration.get("maximumLateCandidateCount")
        != MAXIMUM_LATE_CANDIDATE_COUNT
        or configuration.get("maximumLateCandidateDiagnosticCount")
        != MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT
        or configuration.get("pcCenteredCodeWindowByteCount")
        != PC_CENTERED_CODE_WINDOW_BYTE_COUNT
        or configuration.get("pcCenteredCodeWindowBacktrack")
        != PC_CENTERED_CODE_WINDOW_BACKTRACK
        or configuration.get("stackSnapshotByteCount") != STACK_SNAPSHOT_BYTE_COUNT
        or configuration.get("registerPointerSnapshotByteCount")
        != REGISTER_POINTER_SNAPSHOT_BYTE_COUNT
        or configuration.get("registerPointerSnapshotBacktrack")
        != REGISTER_POINTER_SNAPSHOT_BACKTRACK
        or configuration.get("generalRegisterNames") != list(GENERAL_REGISTER_NAMES)
        or configuration.get("simdRegisterNames") != list(SIMD_REGISTER_NAMES)
        or configuration.get("pointerProbeRegisterNames")
        != list(POINTER_PROBE_REGISTER_NAMES)
        or configuration.get("pointerProbeAddressRange")
        != [MINIMUM_POINTER_PROBE_ADDRESS, MAXIMUM_POINTER_PROBE_ADDRESS]
        or configuration.get("objectSnapshotSpecs")
        != [
            {"base": base, "byteCount": byte_count}
            for base, byte_count in OBJECT_SNAPSHOT_SPECS.items()
        ]
        or configuration.get("watchSpecs") != expected_watch_specs
    ):
        raise ValueError("writer-trace prospective configuration differs")

    capture = mapping(trace.get("captureBackdrop"), "capture_backdrop gate")
    if (
        capture.get("codeByteCount") != 0x4000
        or capture.get("codeSHA256") != EXPECTED_CAPTURE_BACKDROP_CODE_SHA256
        or integer(capture.get("symbolAddress"), "capture_backdrop address") == 0
        or QUARTZ_CORE_PATH_FRAGMENT
        not in str(mapping(capture.get("module"), "capture module").get("path"))
    ):
        raise ValueError("capture_backdrop byte gate differs")

    late_candidate_count = integer(
        trace.get("lateCandidateCount"), "late candidate count"
    )
    late_candidate_diagnostics = [
        mapping(value, "late candidate diagnostic")
        for value in sequence(
            trace.get("lateCandidateDiagnostics"), "late candidate diagnostics"
        )
    ]
    if (
        not 1 <= late_candidate_count <= MAXIMUM_LATE_CANDIDATE_COUNT
        or len(late_candidate_diagnostics) > MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT
    ):
        raise ValueError("late candidate bounds differ")
    for expected_index, diagnostic in enumerate(late_candidate_diagnostics, start=1):
        if (
            diagnostic.get("lateCandidateIndex") != expected_index
            or not isinstance(diagnostic.get("rejection"), str)
            or not diagnostic["rejection"]
            or not isinstance(diagnostic.get("pointerChainExact"), bool)
        ):
            raise ValueError("late candidate diagnostic identity differs")
        for name in ("source", "owner", "layer"):
            integer(diagnostic.get(name), f"late candidate {name}")
        if diagnostic["pointerChainExact"]:
            layer_state = integer(
                diagnostic.get("layerState"), "late candidate layer state"
            )
            if (
                0
                in (
                    diagnostic["source"],
                    diagnostic["owner"],
                    diagnostic["layer"],
                )
                or layer_state == 0
                or diagnostic.get("sourceOwner") != diagnostic["owner"]
                or diagnostic.get("layerStateSource") != diagnostic["source"]
            ):
                raise ValueError("late candidate pointer chain differs")
            rectangles = mapping(
                diagnostic.get("mirroredRectangles"),
                "late candidate mirrored rectangles",
            )
            source_rectangle = numeric_vector(
                rectangles.get("sourceSelectedRectI32"),
                4,
                "late candidate source rectangle",
                integral=True,
            )
            layer_state_rectangle = numeric_vector(
                rectangles.get("layerStateSelectedRectI32"),
                4,
                "late candidate layer-state rectangle",
                integral=True,
            )
            if (
                list(
                    struct.unpack(
                        "<4i",
                        hexadecimal_payload(
                            rectangles.get("sourceSelectedRectI32Hex"),
                            16,
                            "late candidate source rectangle bytes",
                        ),
                    )
                )
                != source_rectangle
                or list(
                    struct.unpack(
                        "<4i",
                        hexadecimal_payload(
                            rectangles.get("layerStateSelectedRectI32Hex"),
                            16,
                            "late candidate layer-state rectangle bytes",
                        ),
                    )
                )
                != layer_state_rectangle
            ):
                raise ValueError("late candidate rectangle bytes differ")
            owner_rectangle = list(
                struct.unpack(
                    "<4d",
                    hexadecimal_payload(
                        rectangles.get("ownerSelectedRectF64Hex"),
                        32,
                        "late candidate owner rectangle bytes",
                    ),
                )
            )
            source_equals_layer_state = source_rectangle == layer_state_rectangle
            owner_equals_layer_state = owner_rectangle == [
                float(value) for value in layer_state_rectangle
            ]
            mirrored_identity_exact = (
                source_equals_layer_state and owner_equals_layer_state
            )
            preconvergence_exact = (
                owner_equals_layer_state and not source_equals_layer_state
            )
            if (
                diagnostic.get("sourceEqualsLayerStateRectangle")
                is not source_equals_layer_state
                or diagnostic.get("ownerEqualsLayerStateRectangle")
                is not owner_equals_layer_state
                or diagnostic.get("mirroredRectangleIdentityExact")
                is not mirrored_identity_exact
                or diagnostic.get("preconvergenceExact") is not preconvergence_exact
                or preconvergence_exact
            ):
                raise ValueError("late candidate rectangle classification differs")

    object_chain = mapping(trace.get("objectChain"), "object chain")
    addresses = mapping(object_chain.get("addresses"), "object addresses")
    if object_chain.get("exact") is not True or set(addresses) != {
        "source",
        "owner",
        "layer",
        "layerState",
    }:
        raise ValueError("writer-trace object chain differs")
    for name, address in addresses.items():
        if integer(address, f"{name} address") == 0:
            raise ValueError("writer-trace object address differs")
    selected_late_candidate_index = integer(
        object_chain.get("selectedLateCandidateIndex"),
        "selected late candidate index",
    )
    if selected_late_candidate_index != late_candidate_count or len(
        late_candidate_diagnostics
    ) != min(
        selected_late_candidate_index - 1, MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT
    ):
        raise ValueError("selected late candidate differs")
    initial = private_fields(
        object_chain.get("initialPrivateFields"), "initial private fields"
    )
    source_selected = initial["sourceSelectedRectI32"]
    layer_state_selected = initial["layerStateSelectedRectI32"]
    owner_selected = initial["ownerSelectedRectF64"]
    source_equals_layer_state = source_selected == layer_state_selected
    owner_equals_layer_state = owner_selected == [
        float(value) for value in layer_state_selected
    ]
    selected_rectangles = mapping(
        object_chain.get("selectedMirroredRectangles"),
        "selected mirrored rectangles",
    )
    selected_source_bytes = hexadecimal_payload(
        selected_rectangles.get("sourceSelectedRectI32Hex"),
        16,
        "selected source rectangle bytes",
    )
    selected_layer_state_bytes = hexadecimal_payload(
        selected_rectangles.get("layerStateSelectedRectI32Hex"),
        16,
        "selected layer-state rectangle bytes",
    )
    selected_owner_bytes = hexadecimal_payload(
        selected_rectangles.get("ownerSelectedRectF64Hex"),
        32,
        "selected owner rectangle bytes",
    )
    if (
        object_chain.get("pointerChainExact") is not True
        or object_chain.get("selectedMirroredRectangleIdentityExact") is not False
        or object_chain.get("selectedOwnerEqualsLayerStateRectangle") is not True
        or object_chain.get("selectedSourceEqualsLayerStateRectangle") is not False
        or object_chain.get("selectedPreconvergenceExact") is not True
        or source_equals_layer_state
        or not owner_equals_layer_state
        or list(struct.unpack("<4i", selected_source_bytes)) != source_selected
        or list(struct.unpack("<4i", selected_layer_state_bytes))
        != layer_state_selected
        or list(struct.unpack("<4d", selected_owner_bytes)) != owner_selected
        or selected_rectangles.get("sourceSelectedRectI32") != source_selected
        or selected_rectangles.get("layerStateSelectedRectI32") != layer_state_selected
    ):
        raise ValueError("initial preconvergence rectangle state differs")

    watchpoints = [
        mapping(value, "watchpoint")
        for value in sequence(trace.get("watchpoints"), "watchpoints")
    ]
    if len(watchpoints) != len(EXPECTED_WATCH_SPECS):
        raise ValueError("writer watchpoint count differs")
    watchpoint_by_id: dict[int, Mapping[str, Any]] = {}
    for watchpoint in watchpoints:
        identifier = integer(watchpoint.get("id"), "watchpoint ID")
        deprecated_hardware_index = integer(
            watchpoint.get("deprecatedHardwareIndex"),
            "deprecated watchpoint hardware index",
        )
        name = watchpoint.get("name")
        if (
            identifier <= 0
            or identifier in watchpoint_by_id
            or deprecated_hardware_index != -1
            or name not in EXPECTED_WATCH_SPECS
            or watchpoint.get("byteCount") != 8
        ):
            raise ValueError("writer watchpoint identity differs")
        base, offset = EXPECTED_WATCH_SPECS[str(name)]
        if watchpoint.get("address") != addresses[base] + offset:
            raise ValueError("writer watchpoint address differs")
        hexadecimal_payload(watchpoint.get("initialHex"), 8, "initial watch value")
        watchpoint_by_id[identifier] = watchpoint
    if {item["name"] for item in watchpoints} != set(EXPECTED_WATCH_SPECS):
        raise ValueError("writer watchpoint name inventory differs")

    code_windows = [
        mapping(value, "code window")
        for value in sequence(trace.get("codeWindows"), "code windows")
    ]
    if not code_windows:
        raise ValueError("writer code-window inventory is empty")
    code_window_keys: set[tuple[int, str]] = set()
    for window in code_windows:
        start = integer(window.get("startAddress"), "code-window start")
        byte_count = integer(window.get("byteCount"), "code-window byte count")
        stop_pc_offset = integer(
            window.get("stopPCOffset"), "code-window stop-PC offset"
        )
        if (
            start == 0
            or byte_count != PC_CENTERED_CODE_WINDOW_BYTE_COUNT
            or window.get("source") != "pc-centered"
            or window.get("containsStopPC") is not True
            or stop_pc_offset != PC_CENTERED_CODE_WINDOW_BACKTRACK
        ):
            raise ValueError("writer code-window bounds differ")
        payload = hexadecimal_payload(window.get("hex"), byte_count, "code window")
        digest = hashlib.sha256(payload).hexdigest()
        if window.get("sha256") != digest or (start, digest) in code_window_keys:
            raise ValueError("writer code-window identity differs")
        code_window_keys.add((start, digest))

    events = [
        mapping(value, "watchpoint event")
        for value in sequence(trace.get("events"), "watchpoint events")
    ]
    if not 1 <= len(events) <= MAXIMUM_EVENT_COUNT or trace.get(
        "finalEventCount"
    ) != len(events):
        raise ValueError("writer event count differs")
    hit_counts: Counter[str] = Counter()
    hit_indices: defaultdict[str, list[int]] = defaultdict(list)
    quartz_core_events: Counter[str] = Counter()
    changed_events: Counter[str] = Counter()
    changed_quartz_core_events: Counter[str] = Counter()
    changed_prepare_layer_offsets: defaultdict[str, set[int]] = defaultdict(set)
    writer_sites: Counter[tuple[str | None, int | None, int]] = Counter()
    for event_index, event in enumerate(events):
        if event.get("eventIndex") != event_index:
            raise ValueError("writer event order differs")
        identifier = integer(event.get("watchpointID"), "event watchpoint ID")
        if identifier not in watchpoint_by_id:
            raise ValueError("event watchpoint identity differs")
        name = str(event.get("watchpointName"))
        if name != watchpoint_by_id[identifier]["name"]:
            raise ValueError("event watchpoint name differs")
        hit_index = integer(event.get("watchpointHitIndex"), "event hit index")
        integer(event.get("threadID"), "event thread ID")
        stop_pc = integer(event.get("stopPC"), "event stop PC")
        value_changed = event.get("valueChanged")
        if (
            hit_index < 1
            or hit_index > MAXIMUM_HITS_PER_WATCHPOINT
            or stop_pc == 0
            or not isinstance(value_changed, bool)
            or event.get("hardwareStopKind")
            != ("watched-bytes-changed" if value_changed else "watched-bytes-unchanged")
        ):
            raise ValueError("writer event bounds differ")
        before = hexadecimal_payload(event.get("beforeHex"), 8, "event before value")
        after = hexadecimal_payload(event.get("afterHex"), 8, "event after value")
        if (before != after) is not value_changed:
            raise ValueError("writer event value-change classification differs")
        frame = frame_record(event.get("frame"), "event frame")
        if frame["pc"] != stop_pc:
            raise ValueError("writer stop PC differs")
        backtrace = [
            frame_record(value, "backtrace frame")
            for value in sequence(event.get("backtrace"), "event backtrace")
        ]
        if (
            not 1 <= len(backtrace) <= MAXIMUM_BACKTRACE_FRAME_COUNT
            or backtrace[0]["pc"] != stop_pc
        ):
            raise ValueError("writer backtrace differs")
        code_window_index = integer(
            event.get("codeWindowIndex"), "event code-window index"
        )
        if not 0 <= code_window_index < len(code_windows):
            raise ValueError("event code-window reference differs")
        code_window = code_windows[code_window_index]
        if (
            stop_pc != code_window["startAddress"] + code_window["stopPCOffset"]
            or not code_window["startAddress"]
            <= stop_pc
            < code_window["startAddress"] + code_window["byteCount"]
        ):
            raise ValueError("event code window does not contain stop PC")
        private_fields(event.get("privateFieldsAfter"), "event private fields")
        operand_snapshot(event.get("operandSnapshot"), "event operands", addresses)
        hit_counts[name] += 1
        hit_indices[name].append(hit_index)
        module_path = str(mapping(frame["module"], "event module")["path"])
        if QUARTZ_CORE_PATH_FRAGMENT in module_path:
            quartz_core_events[name] += 1
        if value_changed:
            changed_events[name] += 1
            if QUARTZ_CORE_PATH_FRAGMENT in module_path:
                changed_quartz_core_events[name] += 1
            if frame.get("function") == EXPECTED_PREPARE_LAYER_FUNCTION:
                changed_prepare_layer_offsets[name].add(
                    integer(frame.get("symbolOffset"), "prepare_layer symbol offset")
                )
        writer_sites[(frame.get("function"), frame.get("symbolOffset"), stop_pc)] += 1

    final_hit_counts = mapping(trace.get("watchpointHitCounts"), "final hit counts")
    for name in EXPECTED_WATCH_SPECS:
        if (
            hit_counts[name] < 1
            or quartz_core_events[name] < 1
            or changed_events[name] < 1
            or changed_quartz_core_events[name] < 1
            or not EXPECTED_CHANGED_PREPARE_LAYER_OFFSETS[name].issubset(
                changed_prepare_layer_offsets[name]
            )
            or hit_indices[name] != list(range(1, hit_counts[name] + 1))
            or final_hit_counts.get(name) != hit_counts[name]
        ):
            raise ValueError(f"{name} prospective writer evidence differs")

    return {
        "captureBackdropWriterTraceValidationSchemaVersion": 3,
        "classification": (
            "prospective-integrity-gate-for-bounded-private-writer-trace; "
            "semantics-remain-sealed"
        ),
        "conclusion": "success",
        "prospectiveGatePassed": True,
        "inputTrace": trace_path.name,
        "inputTraceSHA256": trace_sha256,
        "aggregate": {
            "watchpointCount": len(watchpoints),
            "distinctWatchpointIDCount": len(watchpoint_by_id),
            "deprecatedHardwareIndexValues": sorted(
                {item["deprecatedHardwareIndex"] for item in watchpoints}
            ),
            "eventCount": len(events),
            "codeWindowCount": len(code_windows),
            "eventCountsByWatchpoint": dict(sorted(hit_counts.items())),
            "changedEventCountsByWatchpoint": dict(sorted(changed_events.items())),
            "unchangedEventCountsByWatchpoint": {
                name: hit_counts[name] - changed_events[name]
                for name in sorted(hit_counts)
            },
            "quartzCoreEventCountsByWatchpoint": dict(
                sorted(quartz_core_events.items())
            ),
            "changedQuartzCoreEventCountsByWatchpoint": dict(
                sorted(changed_quartz_core_events.items())
            ),
            "changedPrepareLayerOffsetsByWatchpoint": {
                name: sorted(changed_prepare_layer_offsets[name])
                for name in sorted(changed_prepare_layer_offsets)
            },
            "distinctWriterSiteCount": len(writer_sites),
            "writerSites": [
                {
                    "function": function,
                    "symbolOffset": symbol_offset,
                    "stopPC": stop_pc,
                    "eventCount": count,
                }
                for (function, symbol_offset, stop_pc), count in sorted(
                    writer_sites.items(), key=lambda item: item[0][2]
                )
            ],
        },
        "sealedConclusion": {
            "privateWriterPCsCaptured": True,
            "writerInstructionsAndOperandsCaptured": True,
            "writerSemanticsOpened": False,
            "publicLayerStateCropRuleRecovered": False,
            "unseenGeometryTransferPassed": False,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = validate(arguments.trace)
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")
        print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
