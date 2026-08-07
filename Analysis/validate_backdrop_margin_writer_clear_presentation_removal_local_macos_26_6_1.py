#!/usr/bin/env python3
"""Validate clear glass's zero-margin writer path and backdrop removal boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from collections import Counter
from pathlib import Path
from typing import Any

import validate_backdrop_margin_writer_execution as base
import validate_backdrop_margin_writer_execution_retry as retry


VALIDATION_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 1
LIVE_QUARTZCORE_UUID = "F1BA3189-E95A-3ECA-B59A-5A6872754484"
LIVE_SWIFTUICORE_UUID = "99606D45-C40A-3C69-AE51-5F0C4E32E531"
LIVE_CALLER_CODE_SHA256 = (
    "d60a0510382f913b937ceb2c20111c4dcf1b4dd9d6d49388c2fe5c4d2683168c"
)
ZERO_F64_RAW = "0000000000000000"
ZERO_F32_RAW = "00000000"
MINIMUM_REMOVAL_SAMPLE = 24
MAXIMUM_REMOVAL_SAMPLE = 32
CASES = {
    ("clear", "light", "materialize", "circle-451-center"),
    ("clear", "dark", "materialize", "circle-459-center"),
}
CALIBRATION_CASE = ("clear", "light", "materialize", "circle-451-center")
CODE_GATES = {
    "copy": {
        "function": "-[CABackdropLayer _copyRenderLayer:layerFlags:commitFlags:]",
        "byteCount": 1640,
        "sha256": (
            "5bdf866c13bfb00d9becada24ff9876f84515fa36acb4ee274785d5176593a1e"
        ),
    },
    "setter": {
        "function": "-[CABackdropLayer setMarginWidth:]",
        "byteCount": 96,
        "sha256": (
            "2421048e418c6cdcc7622dd65f881e514e0852687f7920e6c4bdaf75a301f6dd"
        ),
    },
}
REMOVAL_PATTERN = re.compile(
    r"presentation glassBackground snapshot unavailable at sample ([0-9]+)\Z"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_preregistration(
    value: Any,
    material: str,
    appearance: str,
    direction: str,
    geometry: str,
) -> tuple[dict[str, Any], str]:
    preregistration = base.mapping(value, "clear-removal preregistration")
    require(
        preregistration.get(
            "backdropMarginWriterClearPresentationRemovalPreregistrationSchemaVersion"
        )
        == PREREGISTRATION_SCHEMA_VERSION,
        "clear-removal preregistration schema differs",
    )
    candidate = base.mapping(preregistration.get("frozenCandidate"), "candidate")
    require(
        candidate.get("groupMarginF64RawLittleEndianHex") == ZERO_F64_RAW
        and candidate.get("setterInputF64RawLittleEndianHex") == ZERO_F64_RAW
        and candidate.get("copyStoreF32RawLittleEndianHex") == ZERO_F32_RAW
        and candidate.get("regularBoundsConsumerExpected") is False
        and candidate.get("presentationBackdropRemovalExpected") is True
        and candidate.get("minimumRemovalSample") == MINIMUM_REMOVAL_SAMPLE
        and candidate.get("maximumRemovalSample") == MAXIMUM_REMOVAL_SAMPLE
        and candidate.get("prospectiveHoldoutOutputUsedToChooseCandidate") is False,
        "clear-removal candidate differs",
    )
    cases = base.sequence(preregistration.get("caseMatrix"), "case matrix")
    identities = {
        (
            case.get("material"),
            case.get("appearance"),
            case.get("direction"),
            case.get("geometry"),
        )
        for case in cases
        if isinstance(case, dict)
    }
    require(identities == CASES and len(cases) == 2, "case matrix differs")
    identity = (material, appearance, direction, geometry)
    selected = [
        case
        for case in cases
        if isinstance(case, dict)
        and (
            case.get("material"),
            case.get("appearance"),
            case.get("direction"),
            case.get("geometry"),
        )
        == identity
    ]
    require(len(selected) == 1, "runtime profile is not one frozen clear case")
    role = str(selected[0].get("role"))
    if identity == CALIBRATION_CASE:
        require(
            role == "calibration-removal"
            and selected[0].get("appleOutputAvailableAtFreeze") is True,
            "clear calibration disclosure differs",
        )
    else:
        require(
            role == "prospective-holdout"
            and selected[0].get("appleOutputAvailableAtFreeze") is False
            and selected[0].get("expectedRemovalSample") is None
            and selected[0].get("expectedEventCounts") is None,
            "clear holdout was not sealed output-blind",
        )
    acceptance = base.mapping(preregistration.get("acceptance"), "acceptance")
    for key in (
        "requireExactCopyAndSetterCode",
        "requireNoBoundsCodeGateOrEvent",
        "requireAtLeastOneSetterAndCopyStore",
        "requireEveryProducerReturnAndSetterToBePositiveZeroBitwise",
        "requireEveryCopyStoreToBePositiveZeroBitwise",
        "requireEveryProducerReturnToEqualSetterInputBitwise",
        "requireExactOpenedSwiftUICoreCallerIdentity",
        "requireLatePresentationBackdropRemoval",
        "requireNoCapturedValueForCaptureSelection",
        "zeroTolerance",
    ):
        require(acceptance.get(key) is True, "clear-removal acceptance differs")
    root = Path(__file__).resolve().parent.parent
    for index, entry_value in enumerate(
        base.sequence(preregistration.get("frozenEvidence"), "frozen evidence")
    ):
        entry = base.mapping(entry_value, f"frozen evidence {index}")
        path = root / str(entry.get("path"))
        require(path.is_file(), f"frozen evidence is missing: {path}")
        require(sha256(path) == entry.get("sha256"), f"frozen evidence differs: {path}")
    return preregistration, role


def validate_module(value: Any, label: str) -> dict[str, Any]:
    module = base.mapping(value, label)
    require(
        module.get("valid") is True
        and module.get("uuid") == LIVE_QUARTZCORE_UUID
        and isinstance(module.get("path"), str)
        and module["path"].endswith("/QuartzCore")
        and base.integer(module.get("loadAddress"), f"{label} load address") > 0,
        f"{label} differs",
    )
    return module


def validate_code_gates(trace: dict[str, Any]) -> dict[str, dict[str, Any]]:
    gates = base.mapping(trace.get("codeGates"), "code gates")
    require(set(gates) == set(CODE_GATES), "clear code-gate set differs")
    result: dict[str, dict[str, Any]] = {}
    module_identity: tuple[str, int] | None = None
    for name, expected in CODE_GATES.items():
        gate = base.mapping(gates.get(name), f"{name} gate")
        start = base.integer(gate.get("symbolStart"), f"{name} start")
        end = base.integer(gate.get("symbolEnd"), f"{name} end")
        module = validate_module(gate.get("module"), f"{name} module")
        identity = (module["uuid"], module["loadAddress"])
        require(
            gate.get("function") == expected["function"]
            and gate.get("symbolByteCount") == expected["byteCount"]
            and end - start == expected["byteCount"]
            and gate.get("codeSHA256") == expected["sha256"],
            f"{name} exact code identity differs",
        )
        if module_identity is None:
            module_identity = identity
        else:
            require(identity == module_identity, "code-gate modules differ")
        result[name] = gate
    return result


def validate_removal_timeline(timeline: dict[str, Any], directory: Path) -> int:
    require(
        timeline.get("schemaVersion") == 5
        and timeline.get("probe") == "paced-presentation-state-window-timeline"
        and timeline.get("material") == "clear"
        and timeline.get("direction") == "materialize",
        "clear-removal timeline identity differs",
    )
    match = REMOVAL_PATTERN.fullmatch(str(timeline.get("error")))
    require(match is not None, "clear presentation removal error differs")
    removal_sample = int(match.group(1))
    require(
        MINIMUM_REMOVAL_SAMPLE <= removal_sample <= MAXIMUM_REMOVAL_SAMPLE,
        "clear presentation removal was not late",
    )
    images = sorted(directory.glob("transition-materialize-*-rgba8.png"))
    expected_names = [
        f"transition-materialize-{index:02d}-rgba8.png"
        for index in range(removal_sample + 1)
    ]
    require(
        [path.name for path in images] == expected_names,
        "clear pre-removal image sequence differs",
    )
    progress = base.mapping(
        base.load_json(directory / "transition-progress.json", "transition progress"),
        "transition progress",
    )
    require(
        progress.get("schemaVersion") == 5
        and progress.get("phase") == "complete"
        and progress.get("capture") == f"transition-materialize-{removal_sample:02d}",
        "clear removal progress differs",
    )
    return removal_sample


def validate_events(
    trace: dict[str, Any],
    gates: dict[str, dict[str, Any]],
    callers: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    values = base.sequence(trace.get("events"), "events")
    require(
        0 < len(values) <= 8192 and trace.get("finalEventCount") == len(values),
        "clear event count differs",
    )
    events = [base.mapping(value, f"event {index}") for index, value in enumerate(values)]
    counts: Counter[str] = Counter()
    for index, event in enumerate(events):
        event_type = event.get("type")
        require(
            event.get("eventIndex") == index
            and event_type in {"marginSetter", "copyEntry", "copyMarginStore"},
            f"clear event {index} identity differs",
        )
        counts[str(event_type)] += 1
        base.integer(event.get("threadID"), f"event {index} thread")
        pc = base.integer(event.get("pc"), f"event {index} PC")
        if event_type == "marginSetter":
            require(pc == gates["setter"]["symbolStart"], "setter PC differs")
            model = base.integer(event.get("modelSelf"), "setter model")
            require(
                event.get("marginF64RawLittleEndianHex") == ZERO_F64_RAW
                and struct.pack(
                    "<d", base.finite_number(event.get("marginF64"), "setter value")
                ).hex()
                == ZERO_F64_RAW,
                "clear setter is not positive zero",
            )
            base.validate_snapshot(event.get("modelPrefix"), model, "setter model")
            caller_index = base.integer(event.get("directCallerIndex"), "caller index")
            require(0 <= caller_index < len(callers), "setter caller index differs")
        elif event_type == "copyEntry":
            require(pc == gates["copy"]["symbolStart"], "copy-entry PC differs")
            model = base.integer(event.get("modelSelf"), "copy-entry model")
            base.integer(event.get("renderArgument"), "opaque render argument")
            base.validate_snapshot(event.get("modelPrefix"), model, "copy-entry model")
        else:
            require(
                pc == gates["copy"]["symbolStart"] + 948,
                "copy-store PC differs",
            )
            model = base.integer(event.get("modelSelf"), "copy-store model")
            render = base.integer(event.get("renderSelf"), "copy-store render")
            entry_index = base.integer(
                event.get("copyEntryEventIndex"), "copy entry event index"
            )
            require(0 <= entry_index < index, "copy entry does not precede store")
            entry = events[entry_index]
            require(
                event.get("entryModelMatched") is True
                and event.get("entryRenderArgumentMatched") is False
                and entry.get("type") == "copyEntry"
                and entry.get("modelSelf") == model
                and entry.get("threadID") == event.get("threadID"),
                "clear copy entry/store model join differs",
            )
            require(
                event.get("marginF32RawLittleEndianHex") == ZERO_F32_RAW
                and struct.pack(
                    "<f", base.finite_number(event.get("marginF32"), "copy value")
                ).hex()
                == ZERO_F32_RAW,
                "clear copy store is not positive zero",
            )
            base.exact_hex(
                event.get("renderMarginBeforeRawLittleEndianHex"),
                4,
                "pre-store render margin",
            )
            base.validate_snapshot(
                event.get("renderPrefixBeforeStore"), render, "pre-store render"
            )
    require(
        counts["marginSetter"] > 0
        and counts["copyEntry"] > 0
        and counts["copyMarginStore"] > 0
        and counts["backdropBounds"] == 0,
        "clear writer path event coverage differs",
    )
    require(
        trace.get("eventTypeCounts")
        == {
            "marginSetter": counts["marginSetter"],
            "copyEntry": counts["copyEntry"],
            "copyMarginStore": counts["copyMarginStore"],
            "backdropBounds": 0,
        },
        "clear event-type totals differ",
    )
    setters = [event for event in events if event["type"] == "marginSetter"]
    joined_copy_count = 0
    for copy in (event for event in events if event["type"] == "copyMarginStore"):
        if any(
            setter["modelSelf"] == copy["modelSelf"]
            and setter["eventIndex"] < copy["eventIndex"]
            for setter in setters
        ):
            joined_copy_count += 1
    require(joined_copy_count > 0, "no clear setter/copy model chain was observed")
    return events, joined_copy_count


def validate(
    trace_path: Path,
    timeline_path: Path,
    preregistration_path: Path,
    material: str,
    appearance: str,
    direction: str,
    geometry: str,
) -> dict[str, Any]:
    preregistration, role = validate_preregistration(
        base.load_json(preregistration_path, "preregistration"),
        material,
        appearance,
        direction,
        geometry,
    )
    trace = base.mapping(base.load_json(trace_path, "trace"), "trace")
    timeline = base.mapping(base.load_json(timeline_path, "timeline"), "timeline")
    configuration = base.mapping(trace.get("configuration"), "configuration")
    require(
        trace.get("backdropMarginWriterExecutionTraceSchemaVersion")
        == base.TRACE_SCHEMA_VERSION
        and trace.get("status") == "finalized"
        and trace.get("statusBeforeFinalization") == "breakpoints-armed"
        and trace.get("failures") == []
        and trace.get("finalFailureCount") == 0
        and configuration.get("material") == material == "clear"
        and configuration.get("appearance") == appearance
        and configuration.get("direction") == direction == "materialize"
        and configuration.get("geometry") == geometry
        and configuration.get("quartzCoreUUID") == LIVE_QUARTZCORE_UUID
        and configuration.get("boundsCodeSHA256")
        == "85a99558cc08c2a693969b55c804cd811e8ef710ac2d02460830f8bf9d6ec85a"
        and configuration.get("capturedMarginUsedForSelection") is False
        and configuration.get("capturedCropUsedForSelection") is False
        and configuration.get("capturedImageUsedForSelection") is False,
        "clear trace identity or output-blind contract differs",
    )
    require(timeline.get("appearance") == appearance, "timeline appearance differs")
    removal_sample = validate_removal_timeline(timeline, timeline_path.parent)
    gates = validate_code_gates(trace)
    callers = base.validate_callers(trace)
    events, joined_copy_count = validate_events(trace, gates, callers)
    original_uuid = retry.SWIFTUICORE_UUID
    original_caller_sha256 = retry.CALLER_CODE_SHA256
    retry.SWIFTUICORE_UUID = LIVE_SWIFTUICORE_UUID
    retry.CALLER_CODE_SHA256 = LIVE_CALLER_CODE_SHA256
    try:
        provenance = retry.validate_producer_provenance(trace, events, callers)
    finally:
        retry.SWIFTUICORE_UUID = original_uuid
        retry.CALLER_CODE_SHA256 = original_caller_sha256
    setter_count = sum(event["type"] == "marginSetter" for event in events)
    copy_count = sum(event["type"] == "copyMarginStore" for event in events)
    prospective = role == "prospective-holdout"
    return {
        "backdropMarginWriterClearPresentationRemovalValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "classification": (
            f"exact clear zero-margin writer and presentation-removal {role} "
            "transfer on the direct physical Retina M1"
        ),
        "conclusion": "success",
        "profile": {
            "material": material,
            "appearance": appearance,
            "direction": direction,
            "geometry": geometry,
            "caseRole": role,
        },
        "presentationRemoval": {
            "sampleIndex": removal_sample,
            "retainedImageCount": removal_sample + 1,
            "lastRetainedImageIndex": removal_sample,
            "regularBoundsCodeGatePresent": False,
            "regularBoundsEventCount": 0,
            "clearBackdropRemovedBeforeRegularBoundsConsumption": True,
        },
        "writerExecution": {
            "exactCodeGateCount": len(gates),
            "eventCount": len(events),
            "marginSetterCount": setter_count,
            "copyMarginStoreCount": copy_count,
            "setterCopyModelJoinCount": joined_copy_count,
            "allProducerReturnsF64PositiveZeroBitwise": True,
            "allSetterInputsF64PositiveZeroBitwise": True,
            "allCopyStoresF32PositiveZeroBitwise": True,
            "producerProvenance": provenance,
            "capturedValueUsedForSelection": False,
        },
        "sealedConclusion": {
            "clearZeroMarginProducerSetterCopyLawBitExactForThisCase": True,
            "clearPresentationRemovalBoundaryEstablishedForThisCase": True,
            "prospectiveClearPathTransferPassedForThisCase": prospective,
            "generalSelectedRegionPolicyEstablished": False,
            "physicalRetinaColorPixelCompositorTransferEstablished": False,
            "independentWalleZeroByteFrameParityEstablished": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
        "preregistrationClassification": preregistration["classification"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("preregistration", type=Path)
    parser.add_argument("--material", required=True, choices=("clear",))
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
