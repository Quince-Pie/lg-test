"""Validate the prospective BackdropLayer margin writer-chain capture."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any


VALIDATION_SCHEMA_VERSION = 1
TRACE_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 1
TIMELINE_SCHEMA_VERSION = 5

QUARTZCORE_UUID = "4D34EB4E-2BBB-3751-A362-8E2EB74656E8"
CODE_GATES = {
    "copy": {
        "function": "-[CABackdropLayer _copyRenderLayer:layerFlags:commitFlags:]",
        "byteCount": 1640,
        "sha256": (
            "6547059b681d624b57e2996cfe4ebec262759a7e11be3f43cdd56e6b5794d838"
        ),
    },
    "setter": {
        "function": "-[CABackdropLayer setMarginWidth:]",
        "byteCount": 96,
        "sha256": (
            "b7c5020620b41d7d8f3107e525521ad6c381b5f26dac500449838e813c2f2901"
        ),
    },
    "bounds": {
        "function": (
            "CA::Render::BackdropLayer::get_bounds("
            "CA::Render::Layer const*, CA::Rect&, CA::Rect*) const"
        ),
        "byteCount": 80,
        "sha256": (
            "85a99558cc08c2a693969b55c804cd811e8ef710ac2d02460830f8bf9d6ec85a"
        ),
    },
}


def load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}: {path}: {error}") from error


def mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    return value


def sequence(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} is not an array")
    return value


def integer(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} is not an integer")
    return value


def finite_number(value: Any, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{label} is not numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} is not finite")
    return result


def exact_hex(value: Any, byte_count: int, label: str) -> bytes:
    if not isinstance(value, str) or len(value) != 2 * byte_count:
        raise ValueError(f"{label} has the wrong encoded length")
    try:
        payload = bytes.fromhex(value)
    except ValueError as error:
        raise ValueError(f"{label} is not hexadecimal") from error
    if len(payload) != byte_count:
        raise ValueError(f"{label} has the wrong byte length")
    return payload


def validate_snapshot(value: Any, address: int, label: str) -> bytes:
    snapshot = mapping(value, label)
    byte_count = integer(snapshot.get("byteCount"), f"{label} byte count")
    if snapshot.get("address") != address or byte_count != 64:
        raise ValueError(f"{label} metadata differs")
    payload = exact_hex(snapshot.get("hex"), byte_count, f"{label} bytes")
    if snapshot.get("sha256") != hashlib.sha256(payload).hexdigest():
        raise ValueError(f"{label} SHA-256 differs")
    return payload


def validate_module(value: Any, label: str) -> dict[str, Any]:
    module = mapping(value, label)
    if (
        module.get("valid") is not True
        or module.get("uuid") != QUARTZCORE_UUID
        or not isinstance(module.get("path"), str)
        or not module["path"].endswith("/QuartzCore")
        or integer(module.get("loadAddress"), f"{label} load address") <= 0
    ):
        raise ValueError(f"{label} differs")
    return module


def validate_code_gates(trace: dict[str, Any]) -> dict[str, dict[str, Any]]:
    gates = mapping(trace.get("codeGates"), "code gates")
    if set(gates) != set(CODE_GATES):
        raise ValueError("code-gate set differs")
    validated: dict[str, dict[str, Any]] = {}
    module_identity: tuple[str, int] | None = None
    for name, expected in CODE_GATES.items():
        gate = mapping(gates.get(name), f"{name} code gate")
        start = integer(gate.get("symbolStart"), f"{name} symbol start")
        end = integer(gate.get("symbolEnd"), f"{name} symbol end")
        module = validate_module(gate.get("module"), f"{name} module")
        identity = (module["uuid"], module["loadAddress"])
        if module_identity is None:
            module_identity = identity
        elif identity != module_identity:
            raise ValueError("code-gate QuartzCore modules differ")
        if (
            gate.get("function") != expected["function"]
            or gate.get("symbolByteCount") != expected["byteCount"]
            or end - start != expected["byteCount"]
            or gate.get("codeSHA256") != expected["sha256"]
        ):
            raise ValueError(f"{name} exact code identity differs")
        validated[name] = gate
    return validated


def validate_preregistration(
    value: Any, material: str, appearance: str, direction: str, geometry: str
) -> dict[str, Any]:
    prereg = mapping(value, "preregistration")
    if prereg.get("backdropMarginWriterExecutionPreregistrationSchemaVersion") != (
        PREREGISTRATION_SCHEMA_VERSION
    ):
        raise ValueError("preregistration schema differs")
    candidate = mapping(prereg.get("frozenCandidate"), "frozen candidate")
    if (
        candidate.get("perRecordRequiredMargin")
        != (
            "max(inputBleedAmount, inputShadowAmount + "
            "max(abs(inputShadowOffset.x), abs(inputShadowOffset.y)))"
        )
        or candidate.get("transitionMargin") != "max over all 32 retained records"
        or candidate.get("modelStorage") != "binary64"
        or candidate.get("renderStorage") != "round-to-nearest-even binary32"
        or candidate.get("capturedTargetValueUsedToChooseCandidate") is not False
    ):
        raise ValueError("frozen candidate differs")
    cases = sequence(prereg.get("prospectiveCases"), "prospective cases")
    matching = [
        case
        for case in cases
        if isinstance(case, dict)
        and case.get("material") == material
        and case.get("appearance") == appearance
        and case.get("direction") == direction
        and case.get("geometry") == geometry
    ]
    if len(matching) != 1:
        raise ValueError("runtime profile is not one unique frozen case")
    case = matching[0]
    if (
        case.get("appleOutputAvailableAtFreeze") is not False
        or case.get("expectedMarginF64") is not None
        or case.get("expectedMarginF32") is not None
        or case.get("expectedWriterPointers") is not None
        or case.get("expectedCallerIdentity") is not None
    ):
        raise ValueError("prospective case was not sealed output-blind")
    acceptance = mapping(prereg.get("acceptance"), "acceptance")
    required_true = (
        "requireAllExactCodeGates",
        "requireEveryEventWithinBound",
        "requireAtLeastOneCompleteSetterCopyBoundsChain",
        "requireEveryStructurallyJoinedChainToMatchCandidateBitwise",
        "requireNoCapturedValueForSelection",
    )
    if any(acceptance.get(key) is not True for key in required_true):
        raise ValueError("preregistered acceptance differs")
    return prereg


def decode_shadow_offset(value: Any, label: str) -> tuple[float, float]:
    record = mapping(value, label)
    raw = exact_hex(record.get("hex"), 16, f"{label} bytes")
    if (
        record.get("lengthBytes") != 16
        or record.get("objCType") != "{CGSize=dd}"
    ):
        raise ValueError(f"{label} NSValue metadata differs")
    x, y = struct.unpack("<2d", raw)
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError(f"{label} is non-finite")
    return x, y


def transition_candidate(
    timeline: dict[str, Any], material: str, appearance: str, direction: str, geometry: str
) -> dict[str, Any]:
    if (
        timeline.get("schemaVersion") != TIMELINE_SCHEMA_VERSION
        or timeline.get("material") != material
        or timeline.get("appearance") != appearance
        or timeline.get("direction") != direction
        or mapping(timeline.get("geometry"), "timeline geometry").get("name")
        != geometry
        or timeline.get("sampleCount") != 33
        or timeline.get("failedSamples") != 0
    ):
        raise ValueError("transition timeline identity or completion differs")
    dynamic = mapping(
        timeline.get("dynamicBackgroundUniforms"), "dynamic background uniforms"
    )
    records = sequence(dynamic.get("records"), "dynamic uniform records")
    if (
        dynamic.get("requested") is not True
        or dynamic.get("executed") is not True
        or dynamic.get("sampleCount") != 32
        or dynamic.get("executedSampleCount") != 32
        or len(records) != 32
    ):
        raise ValueError("dynamic uniform capture differs")
    decoded = []
    for expected_index, value in enumerate(records, 1):
        record = mapping(value, f"dynamic record {expected_index}")
        if record.get("sampleIndex") != expected_index:
            raise ValueError("dynamic record indices differ")
        inputs = mapping(
            mapping(record.get("filter"), "filter").get("inputValues"),
            "filter input values",
        )
        bleed = finite_number(inputs.get("inputBleedAmount"), "inputBleedAmount")
        shadow = finite_number(
            inputs.get("inputShadowAmount"), "inputShadowAmount"
        )
        offset_x, offset_y = decode_shadow_offset(
            inputs.get("inputShadowOffset"), "inputShadowOffset"
        )
        offset_extent = max(abs(offset_x), abs(offset_y))
        shadow_with_offset = shadow + offset_extent
        required = max(bleed, shadow_with_offset)
        decoded.append(
            {
                "sampleIndex": expected_index,
                "inputBleedAmountF64": bleed,
                "inputShadowAmountF64": shadow,
                "inputShadowOffsetF64": [offset_x, offset_y],
                "offsetExtentF64": offset_extent,
                "shadowWithOffsetF64": shadow_with_offset,
                "requiredMarginF64": required,
                "requiredMarginF64RawLittleEndianHex": struct.pack(
                    "<d", required
                ).hex(),
            }
        )
    maximum = max(record["requiredMarginF64"] for record in decoded)
    maximum_raw = struct.pack("<d", maximum)
    render_raw = struct.pack("<f", maximum)
    return {
        "recordCount": len(decoded),
        "records": decoded,
        "maximumRequiredMarginF64": maximum,
        "maximumRequiredMarginF64RawLittleEndianHex": maximum_raw.hex(),
        "expectedRenderMarginF32": struct.unpack("<f", render_raw)[0],
        "expectedRenderMarginF32RawLittleEndianHex": render_raw.hex(),
    }


def validate_callers(trace: dict[str, Any]) -> list[dict[str, Any]]:
    callers = sequence(trace.get("callers"), "setter callers")
    if len(callers) > 64:
        raise ValueError("setter caller count exceeds the frozen bound")
    total = 0
    validated = []
    for index, value in enumerate(callers):
        caller = mapping(value, f"setter caller {index}")
        if caller.get("completeCodeCaptured") is True:
            byte_count = integer(
                caller.get("symbolByteCount"), f"setter caller {index} byte count"
            )
            if not 0 < byte_count <= 131072:
                raise ValueError("setter caller byte count differs")
            payload = exact_hex(
                caller.get("hex"), byte_count, f"setter caller {index} code"
            )
            if caller.get("codeSHA256") != hashlib.sha256(payload).hexdigest():
                raise ValueError("setter caller code hash differs")
            total += byte_count
        elif not isinstance(caller.get("completeCodeFailure"), str):
            raise ValueError("uncaptured setter caller lacks a reason")
        validated.append(caller)
    if total > 2 * 1024 * 1024:
        raise ValueError("setter caller total code exceeds the frozen bound")
    if trace.get("finalCallerCount") != len(callers):
        raise ValueError("final setter caller count differs")
    if trace.get("finalCallerCodeByteCount") != total:
        raise ValueError("final setter caller byte total differs")
    return validated


def validate_events(
    trace: dict[str, Any], gates: dict[str, dict[str, Any]], callers: list[Any]
) -> list[dict[str, Any]]:
    events = sequence(trace.get("events"), "events")
    if not 0 < len(events) <= 8192 or trace.get("finalEventCount") != len(events):
        raise ValueError("event count differs")
    allowed_types = {
        "marginSetter",
        "copyEntry",
        "copyMarginStore",
        "backdropBounds",
    }
    counts = {name: 0 for name in allowed_types}
    for index, value in enumerate(events):
        event = mapping(value, f"event {index}")
        event_type = event.get("type")
        if event.get("eventIndex") != index or event_type not in allowed_types:
            raise ValueError(f"event {index} identity differs")
        counts[event_type] += 1
        integer(event.get("threadID"), f"event {index} thread")
        pc = integer(event.get("pc"), f"event {index} PC")
        if event_type == "marginSetter":
            if pc != gates["setter"]["symbolStart"]:
                raise ValueError("setter event PC differs")
            model = integer(event.get("modelSelf"), "setter model")
            raw = exact_hex(
                event.get("marginF64RawLittleEndianHex"), 8, "setter margin"
            )
            if struct.pack("<d", finite_number(event.get("marginF64"), "setter value")) != raw:
                raise ValueError("setter numeric value differs from its raw bytes")
            validate_snapshot(event.get("modelPrefix"), model, "setter model prefix")
            caller_index = event.get("directCallerIndex")
            if caller_index is not None and (
                not isinstance(caller_index, int)
                or isinstance(caller_index, bool)
                or not 0 <= caller_index < len(callers)
            ):
                raise ValueError("setter caller index differs")
        elif event_type == "copyEntry":
            if pc != gates["copy"]["symbolStart"]:
                raise ValueError("copy-entry PC differs")
            model = integer(event.get("modelSelf"), "copy-entry model")
            integer(event.get("renderArgument"), "copy-entry render argument")
            validate_snapshot(event.get("modelPrefix"), model, "copy-entry model prefix")
        elif event_type == "copyMarginStore":
            if pc != gates["copy"]["symbolStart"] + 948:
                raise ValueError("copy-store PC differs")
            model = integer(event.get("modelSelf"), "copy-store model")
            render = integer(event.get("renderSelf"), "copy-store render")
            if (
                event.get("entryModelMatched") is not True
                or event.get("entryRenderArgumentMatched") is not True
                or event.get("entryRenderArgument") != render
            ):
                raise ValueError("copy entry/store structural join differs")
            entry_index = integer(
                event.get("copyEntryEventIndex"), "copy entry event index"
            )
            if not 0 <= entry_index < index:
                raise ValueError("copy entry does not precede its store")
            entry = mapping(events[entry_index], "joined copy entry")
            if (
                entry.get("type") != "copyEntry"
                or entry.get("modelSelf") != model
                or entry.get("renderArgument") != render
                or entry.get("threadID") != event.get("threadID")
            ):
                raise ValueError("copy entry/store event identities differ")
            raw = exact_hex(
                event.get("marginF32RawLittleEndianHex"), 4, "copy margin"
            )
            if struct.pack("<f", finite_number(event.get("marginF32"), "copy value")) != raw:
                raise ValueError("copy numeric value differs from its raw bytes")
            exact_hex(
                event.get("renderMarginBeforeRawLittleEndianHex"),
                4,
                "pre-store render margin",
            )
            validate_snapshot(
                event.get("renderPrefixBeforeStore"), render, "pre-store render prefix"
            )
        else:
            if pc != gates["bounds"]["symbolStart"]:
                raise ValueError("get_bounds event PC differs")
            render = integer(event.get("renderSelf"), "get_bounds render")
            integer(event.get("layer"), "get_bounds layer")
            integer(event.get("output"), "get_bounds output")
            raw = exact_hex(
                event.get("marginF32RawLittleEndianHex"), 4, "get_bounds margin"
            )
            if struct.pack("<f", finite_number(event.get("marginF32"), "bounds value")) != raw:
                raise ValueError("get_bounds value differs from its raw bytes")
            prefix = validate_snapshot(
                event.get("renderPrefix"), render, "get_bounds render prefix"
            )
            if prefix[36:40] != raw:
                raise ValueError("get_bounds prefix margin differs")
    if trace.get("eventTypeCounts") != counts:
        raise ValueError("event-type counts differ")
    if any(counts[name] == 0 for name in allowed_types):
        raise ValueError("one or more writer-chain event types were not observed")
    return [mapping(event, "event") for event in events]


def join_chains(events: list[dict[str, Any]], candidate: dict[str, Any]) -> list[dict[str, Any]]:
    setters = [event for event in events if event["type"] == "marginSetter"]
    copies = [event for event in events if event["type"] == "copyMarginStore"]
    bounds = [event for event in events if event["type"] == "backdropBounds"]
    chains: dict[int, dict[str, Any]] = {}
    expected_f64_raw = candidate["maximumRequiredMarginF64RawLittleEndianHex"]
    expected_f32_raw = candidate["expectedRenderMarginF32RawLittleEndianHex"]
    for bound in bounds:
        preceding_copies = [
            event
            for event in copies
            if event["renderSelf"] == bound["renderSelf"]
            and event["eventIndex"] < bound["eventIndex"]
        ]
        if not preceding_copies:
            continue
        copy = max(preceding_copies, key=lambda event: event["eventIndex"])
        preceding_setters = [
            event
            for event in setters
            if event["modelSelf"] == copy["modelSelf"]
            and event["eventIndex"] < copy["eventIndex"]
        ]
        if not preceding_setters:
            continue
        setter = max(preceding_setters, key=lambda event: event["eventIndex"])
        chain = chains.setdefault(
            copy["eventIndex"],
            {
                "setterEventIndex": setter["eventIndex"],
                "copyStoreEventIndex": copy["eventIndex"],
                "boundsEventIndices": [],
                "modelSelf": copy["modelSelf"],
                "renderSelf": copy["renderSelf"],
                "setterCallerIndex": setter.get("directCallerIndex"),
                "setterMarginF64RawLittleEndianHex": setter[
                    "marginF64RawLittleEndianHex"
                ],
                "copyMarginF32RawLittleEndianHex": copy[
                    "marginF32RawLittleEndianHex"
                ],
                "boundsMarginF32RawLittleEndianHex": bound[
                    "marginF32RawLittleEndianHex"
                ],
            },
        )
        if (
            chain["setterEventIndex"] != setter["eventIndex"]
            or chain["modelSelf"] != copy["modelSelf"]
            or chain["renderSelf"] != copy["renderSelf"]
        ):
            raise ValueError("joined writer chain changed identity")
        chain["boundsEventIndices"].append(bound["eventIndex"])
        if bound["marginF32RawLittleEndianHex"] != chain[
            "boundsMarginF32RawLittleEndianHex"
        ]:
            raise ValueError("one render object consumed multiple margins")
    if not chains:
        raise ValueError("no complete setter/copy/get_bounds chain was observed")
    result = []
    for chain in sorted(chains.values(), key=lambda item: item["copyStoreEventIndex"]):
        if (
            chain["setterMarginF64RawLittleEndianHex"] != expected_f64_raw
            or chain["copyMarginF32RawLittleEndianHex"] != expected_f32_raw
            or chain["boundsMarginF32RawLittleEndianHex"] != expected_f32_raw
        ):
            raise ValueError(
                "a structurally joined writer chain differs from the frozen "
                "transition-maximum candidate"
            )
        chain["modelMarginBitExact"] = True
        chain["copyConversionBitExact"] = True
        chain["renderConsumptionBitExact"] = True
        result.append(chain)
    return result


def validate(
    trace_path: Path,
    timeline_path: Path,
    preregistration_path: Path,
    material: str,
    appearance: str,
    direction: str,
    geometry: str,
) -> dict[str, Any]:
    trace = mapping(load_json(trace_path, "trace"), "trace")
    timeline = mapping(load_json(timeline_path, "timeline"), "timeline")
    preregistration = validate_preregistration(
        load_json(preregistration_path, "preregistration"),
        material,
        appearance,
        direction,
        geometry,
    )
    configuration = mapping(trace.get("configuration"), "trace configuration")
    if (
        trace.get("backdropMarginWriterExecutionTraceSchemaVersion")
        != TRACE_SCHEMA_VERSION
        or trace.get("status") != "finalized"
        or trace.get("statusBeforeFinalization") != "breakpoints-armed"
        or trace.get("failures") != []
        or trace.get("finalFailureCount") != 0
        or configuration.get("material") != material
        or configuration.get("appearance") != appearance
        or configuration.get("direction") != direction
        or configuration.get("geometry") != geometry
        or configuration.get("quartzCoreUUID") != QUARTZCORE_UUID
        or configuration.get("copyMarginStoreOffset") != 948
        or configuration.get("copyMarginStoreInstructionHex") != "a02600bd"
        or configuration.get("renderMarginOffset") != 36
        or configuration.get("maximumEventCount") != 8192
        or configuration.get("capturedMarginUsedForSelection") is not False
        or configuration.get("capturedCropUsedForSelection") is not False
        or configuration.get("capturedImageUsedForSelection") is not False
    ):
        raise ValueError("trace identity, completion, or output-blind contract differs")
    gates = validate_code_gates(trace)
    callers = validate_callers(trace)
    events = validate_events(trace, gates, callers)
    candidate = transition_candidate(
        timeline, material, appearance, direction, geometry
    )
    chains = join_chains(events, candidate)
    return {
        "backdropMarginWriterExecutionValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "classification": (
            "prospective captured-input transition-maximum margin transfer with "
            "a live object-identity join from model setter through render consumption"
        ),
        "conclusion": "success",
        "inputs": {
            "trace": str(trace_path),
            "timeline": str(timeline_path),
            "preregistration": str(preregistration_path),
        },
        "profile": {
            "material": material,
            "appearance": appearance,
            "direction": direction,
            "geometry": geometry,
            "prospectivelyFrozen": True,
        },
        "candidate": candidate,
        "writerExecution": {
            "exactCodeGateCount": len(gates),
            "eventCount": len(events),
            "callerCount": len(callers),
            "completeChainCount": len(chains),
            "chains": chains,
            "allStructurallyJoinedChainsBitExact": True,
            "capturedValueUsedForSelection": False,
        },
        "sealedConclusion": {
            "selectedMarginSetterExecutionAuthenticated": True,
            "selectedRenderCopyExecutionAuthenticated": True,
            "selectedGetBoundsConsumptionAuthenticated": True,
            "transitionMaximumCandidateProspectiveBitExactForThisCase": True,
            "setterCallerCodeOpened": any(
                caller.get("completeCodeCaptured") is True for caller in callers
            ),
            "setterCallerArithmeticDecoded": False,
            "allFourProspectiveCasesPassed": False,
            "independentTemporalInputGenerationPassed": False,
            "physicalOutputTransferPassed": False,
            "independentWalleZeroByteFrameParityPassed": False,
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
    parser.add_argument("--material", required=True, choices=("clear", "regular"))
    parser.add_argument("--appearance", required=True, choices=("light", "dark"))
    parser.add_argument(
        "--direction", required=True, choices=("materialize", "dematerialize")
    )
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
