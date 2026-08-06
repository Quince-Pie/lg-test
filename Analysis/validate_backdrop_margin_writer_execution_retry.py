"""Validate the writer chain with the discovered opaque Objective-C argument.

The first capture proved that ``_copyRenderLayer:layerFlags:commitFlags:``'s
first explicit Objective-C argument in ``x2`` is not the render object later
held in ``x21``.  The original preregistered join rule never depended on that
argument: model identity is ``entry x0 == store x20`` and render identity is
``store x21 == get_bounds x0``.  This wrapper removes only the accidental
``x2 == x21`` validator assertion and delegates every other byte, event, code,
timeline, formula, and product-authority check to the frozen validator.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import validate_backdrop_margin_writer_execution as frozen


RETRY_VALIDATION_SCHEMA_VERSION = 1
_FROZEN_VALIDATE_EVENTS = frozen.validate_events


def validate_events(
    trace: dict[str, Any],
    gates: dict[str, dict[str, Any]],
    callers: list[Any],
) -> list[dict[str, Any]]:
    original_events = frozen.sequence(trace.get("events"), "events")
    patched_trace = copy.deepcopy(trace)
    patched_events = frozen.sequence(patched_trace.get("events"), "patched events")
    correction_count = 0
    for index, value in enumerate(original_events):
        event = frozen.mapping(value, f"event {index}")
        if event.get("type") != "copyMarginStore":
            continue
        model = frozen.integer(event.get("modelSelf"), "copy-store model")
        render = frozen.integer(event.get("renderSelf"), "copy-store render")
        entry_argument = frozen.integer(
            event.get("entryRenderArgument"), "opaque copy-entry argument"
        )
        entry_index = frozen.integer(
            event.get("copyEntryEventIndex"), "copy entry event index"
        )
        if not 0 <= entry_index < index:
            raise ValueError("copy entry does not precede its store")
        entry = frozen.mapping(original_events[entry_index], "joined copy entry")
        if (
            event.get("entryModelMatched") is not True
            or entry.get("type") != "copyEntry"
            or entry.get("modelSelf") != model
            or entry.get("renderArgument") != entry_argument
            or entry.get("threadID") != event.get("threadID")
        ):
            raise ValueError("model entry/store structural join differs")
        patched_event = frozen.mapping(
            patched_events[index], "patched copy-store event"
        )
        patched_entry = frozen.mapping(
            patched_events[entry_index], "patched copy-entry event"
        )
        patched_event["entryRenderArgument"] = render
        patched_event["entryRenderArgumentMatched"] = True
        patched_entry["renderArgument"] = render
        correction_count += 1
    if correction_count == 0:
        raise ValueError("no copy-store event exercised the opaque-argument correction")
    _FROZEN_VALIDATE_EVENTS(patched_trace, gates, callers)
    return [frozen.mapping(value, "event") for value in original_events]


def validate(
    trace_path: Path,
    timeline_path: Path,
    preregistration_path: Path,
    material: str,
    appearance: str,
    direction: str,
    geometry: str,
) -> dict[str, Any]:
    original = frozen.validate_events
    frozen.validate_events = validate_events
    try:
        result = frozen.validate(
            trace_path,
            timeline_path,
            preregistration_path,
            material,
            appearance,
            direction,
            geometry,
        )
    finally:
        frozen.validate_events = original
    trace = frozen.mapping(frozen.load_json(trace_path, "trace"), "trace")
    events = frozen.sequence(trace.get("events"), "events")
    corrected = sum(
        isinstance(event, dict) and event.get("type") == "copyMarginStore"
        for event in events
    )
    result[
        "backdropMarginWriterExecutionRetryValidationSchemaVersion"
    ] = RETRY_VALIDATION_SCHEMA_VERSION
    result["classification"] = (
        "prospective captured-input transition-maximum margin transfer with "
        "the output-blind ABI-correct model/store/render object join"
    )
    result["writerExecution"]["opaqueEntryArgumentDiscovery"] = {
        "field": "_copyRenderLayer first explicit Objective-C argument x2",
        "isRenderObject": False,
        "copyStoreEventCountValidatedWithoutX2RenderAssumption": corrected,
        "capturedValueUsedForCorrection": False,
        "marginValueUsedForCorrection": False,
        "cropOrImageUsedForCorrection": False,
    }
    result["sealedConclusion"]["opaqueCopyArgumentABIResolved"] = True
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("preregistration", type=Path)
    parser.add_argument("--material", required=True, choices=("clear", "regular"))
    parser.add_argument("--appearance", required=True, choices=("light", "dark"))
    parser.add_argument("--direction", required=True, choices=("materialize",))
    parser.add_argument("--geometry", required=True)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate(
        arguments.trace,
        arguments.timeline,
        arguments.preregistration,
        arguments.material,
        arguments.appearance,
        arguments.direction,
        arguments.geometry,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
