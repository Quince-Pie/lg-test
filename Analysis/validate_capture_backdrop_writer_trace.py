#!/usr/bin/env python3
"""Validate the preregistered LLDB crop-writer trace without opening semantics."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


EXPECTED_TRACE_SCHEMA_VERSION = 1
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
MAXIMUM_EVENT_COUNT = 24
MAXIMUM_HITS_PER_WATCHPOINT = 6
MAXIMUM_BACKTRACE_FRAME_COUNT = 32
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
        or configuration.get("maximumHitsPerWatchpoint") != MAXIMUM_HITS_PER_WATCHPOINT
        or configuration.get("maximumTotalHits") != MAXIMUM_EVENT_COUNT
        or configuration.get("maximumBacktraceFrameCount")
        != MAXIMUM_BACKTRACE_FRAME_COUNT
        or configuration.get("symbolCodeWindowByteCount") != 0x1000
        or configuration.get("fallbackCodeWindowByteCount") != 0x400
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
    initial = private_fields(
        object_chain.get("initialPrivateFields"), "initial private fields"
    )
    selected = initial["sourceSelectedRectI32"]
    if initial["layerStateSelectedRectI32"] != selected or initial[
        "ownerSelectedRectF64"
    ] != [float(value) for value in selected]:
        raise ValueError("initial selected rectangle identity differs")

    watchpoints = [
        mapping(value, "watchpoint")
        for value in sequence(trace.get("watchpoints"), "watchpoints")
    ]
    if len(watchpoints) != len(EXPECTED_WATCH_SPECS):
        raise ValueError("writer watchpoint count differs")
    watchpoint_by_id: dict[int, Mapping[str, Any]] = {}
    hardware_indices: set[int] = set()
    for watchpoint in watchpoints:
        identifier = integer(watchpoint.get("id"), "watchpoint ID")
        hardware_index = integer(
            watchpoint.get("hardwareIndex"), "watchpoint hardware index"
        )
        name = watchpoint.get("name")
        if (
            identifier <= 0
            or identifier in watchpoint_by_id
            or hardware_index < 0
            or hardware_index in hardware_indices
            or name not in EXPECTED_WATCH_SPECS
            or watchpoint.get("byteCount") != 8
        ):
            raise ValueError("writer watchpoint identity differs")
        base, offset = EXPECTED_WATCH_SPECS[str(name)]
        if watchpoint.get("address") != addresses[base] + offset:
            raise ValueError("writer watchpoint address differs")
        hexadecimal_payload(watchpoint.get("initialHex"), 8, "initial watch value")
        watchpoint_by_id[identifier] = watchpoint
        hardware_indices.add(hardware_index)
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
        if start == 0 or byte_count not in {0x400, 0x1000}:
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
        if (
            hit_index < 1
            or hit_index > MAXIMUM_HITS_PER_WATCHPOINT
            or stop_pc == 0
            or event.get("valueChanged") is not True
        ):
            raise ValueError("writer event bounds differ")
        hexadecimal_payload(event.get("beforeHex"), 8, "event before value")
        hexadecimal_payload(event.get("afterHex"), 8, "event after value")
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
        private_fields(event.get("privateFieldsAfter"), "event private fields")
        hit_counts[name] += 1
        hit_indices[name].append(hit_index)
        module_path = str(mapping(frame["module"], "event module")["path"])
        if QUARTZ_CORE_PATH_FRAGMENT in module_path:
            quartz_core_events[name] += 1
        writer_sites[(frame.get("function"), frame.get("symbolOffset"), stop_pc)] += 1

    final_hit_counts = mapping(trace.get("watchpointHitCounts"), "final hit counts")
    for name in EXPECTED_WATCH_SPECS:
        if (
            hit_counts[name] < 1
            or quartz_core_events[name] < 1
            or hit_indices[name] != list(range(1, hit_counts[name] + 1))
            or final_hit_counts.get(name) != hit_counts[name]
        ):
            raise ValueError(f"{name} prospective writer evidence differs")

    return {
        "captureBackdropWriterTraceValidationSchemaVersion": 1,
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
            "distinctHardwareWatchpointCount": len(hardware_indices),
            "eventCount": len(events),
            "codeWindowCount": len(code_windows),
            "eventCountsByWatchpoint": dict(sorted(hit_counts.items())),
            "quartzCoreEventCountsByWatchpoint": dict(
                sorted(quartz_core_events.items())
            ),
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
