"""Validate the material-specific writer law and its immediate producer.

The first capture proved that ``_copyRenderLayer:layerFlags:commitFlags:``'s
first explicit Objective-C argument in ``x2`` is not the render object later
held in ``x21``.  The original preregistered join rule never depended on that
argument: model identity is ``entry x0 == store x20`` and render identity is
``store x21 == get_bounds x0``.  The opened materialize artifacts then showed
that regular glass uses the retained transition maximum while clear glass
writes exact zero.  Fresh holdouts must match that piecewise law bit for bit
and expose the structurally adjacent Double-returning Swift producer.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

import validate_backdrop_margin_writer_execution as frozen


RETRY_VALIDATION_SCHEMA_VERSION = 2
RETRY_PREREGISTRATION_SCHEMA_VERSION = 2
SWIFTUICORE_UUID = "A8FC6D2D-DFE9-3557-A734-7F2B231F8C97"
CALLER_FUNCTION = (
    "SwiftUI.SDFLayer.updateSDFEffects(for: SwiftUI.SDFStyle, at: inout "
    "Swift.Int, in: SwiftUI.DisplayList.ViewRenderer.Environment, "
    "backdropGroupID: Swift.Optional<SwiftUI.BackdropGroupID>, blend: "
    "SwiftUI.Material.Layer.SDFLayer.GroupLayer.Blend, opacity: Swift.Float, "
    "options: SwiftUI.Material.Layer.SDFLayer.GroupLayer.Options, gain: "
    "Swift.Float, maxColorComponent: Swift.Float) -> ()"
)
CALLER_BYTE_COUNT = 6844
CALLER_CODE_SHA256 = "65dff1ba1d4e0ae3376a6ad2e1946bb6ee8725c6380ff886e68111d92fff933e"
CALLER_RETURN_SYMBOL_OFFSET = 5772
SETTER_CALL_FROM_RETURN_PC = -4
PRODUCER_BRIDGE_FROM_RETURN_PC = -8
PRODUCER_CALL_FROM_RETURN_PC = -12
PRODUCER_BRIDGE_INSTRUCTION_HEX = "e0031caa"
PRODUCER_SELF_OFFSET_FROM_STACK_POINTER = 0x160
PRODUCER_SELF_SNAPSHOT_BYTE_COUNT = 0x60
SETTER_STUB_MODULE_OFFSET = 0xF5AC00
PRODUCER_TARGET_MODULE_OFFSET = 0x3715D0
BASE_CAPTURE_SHA256 = "f91ba6afb61b491d949ea5dc9d4fc1c82c165e0016aefa84db00a0b15d435ecd"
_FROZEN_VALIDATE_EVENTS = frozen.validate_events
_FROZEN_TRANSITION_CANDIDATE = frozen.transition_candidate


def decode_bl_target(instruction_hex: Any, instruction_address: int) -> int:
    payload = frozen.exact_hex(instruction_hex, 4, "ARM64 BL instruction")
    word = int.from_bytes(payload, "little")
    if word & 0xFC000000 != 0x94000000:
        raise ValueError("call-site instruction is not ARM64 BL")
    displacement = word & 0x03FFFFFF
    if displacement & 0x02000000:
        displacement -= 0x04000000
    return instruction_address + displacement * 4


def validate_retry_preregistration(
    value: Any,
    material: str,
    appearance: str,
    direction: str,
    geometry: str,
) -> dict[str, Any]:
    preregistration = frozen.mapping(value, "retry preregistration")
    if (
        preregistration.get(
            "backdropMarginWriterExecutionRetryPreregistrationSchemaVersion"
        )
        != RETRY_PREREGISTRATION_SCHEMA_VERSION
    ):
        raise ValueError("retry preregistration schema differs")
    supersession = frozen.mapping(
        preregistration.get("supersedesUndispatchedVersion"),
        "undispatched retry supersession",
    )
    if (
        supersession.get("commit") != "c7e1a3f"
        or supersession.get("workflowDispatchCountBeforeSupersession") != 0
        or supersession.get("appleOutputForProspectiveCasesAvailable") is not False
        or supersession.get("reason")
        != "opened antecedent materialize artifacts disproved a universal material law"
    ):
        raise ValueError("undispatched retry supersession differs")
    candidate = frozen.mapping(
        preregistration.get("frozenCandidate"), "retry frozen candidate"
    )
    material_law = frozen.mapping(
        candidate.get("materialSelector"), "material-specific margin law"
    )
    if (
        material_law.get("clear") != "exact binary64 +0.0"
        or material_law.get("regular")
        != "maximum over all 32 retained per-record required margins"
        or candidate.get("candidateCalibratedFromOpenedAppleWriterValues") is not True
        or candidate.get("prospectiveCaseOutputUsedToChooseCandidate") is not False
        or candidate.get("modelStorage") != "binary64"
        or candidate.get("renderStorage") != "round-to-nearest-even binary32"
    ):
        raise ValueError("retry material-specific candidate differs")
    cases = frozen.sequence(
        preregistration.get("prospectiveCases"), "retry prospective cases"
    )
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
        raise ValueError("runtime profile is not one unique retry case")
    case = matching[0]
    if (
        case.get("appleOutputAvailableAtFreeze") is not False
        or case.get("expectedMarginF64") is not None
        or case.get("expectedMarginF32") is not None
        or case.get("expectedWriterPointers") is not None
        or case.get("expectedProducerIdentity") is not None
    ):
        raise ValueError("retry case was not sealed output-blind")
    acceptance = frozen.mapping(preregistration.get("acceptance"), "retry acceptance")
    for key in (
        "requireEveryStructurallyJoinedChainToMatchMaterialLawBitwise",
        "requireEverySetterToExposeExactAdjacentProducer",
        "requireExactOpenedSwiftUICoreCallerIdentity",
        "requireProducerCompleteCode",
        "requireProducerSelfSnapshot",
        "zeroTolerance",
    ):
        if acceptance.get(key) is not True:
            raise ValueError("retry acceptance differs")
    return preregistration


def validate_swiftui_module(value: Any, label: str) -> dict[str, Any]:
    module = frozen.mapping(value, label)
    if (
        module.get("valid") is not True
        or module.get("uuid") != SWIFTUICORE_UUID
        or not isinstance(module.get("path"), str)
        or not module["path"].endswith("/SwiftUICore")
        or frozen.integer(module.get("loadAddress"), f"{label} load address") <= 0
    ):
        raise ValueError(f"{label} differs")
    return module


def validate_producer_provenance(
    trace: dict[str, Any],
    events: list[dict[str, Any]],
    callers: list[Any],
) -> dict[str, Any]:
    configuration = frozen.mapping(trace.get("configuration"), "configuration")
    expected_configuration = {
        "baseCaptureSHA256": BASE_CAPTURE_SHA256,
        "maximumProducerCount": 64,
        "maximumProducerByteCount": 131072,
        "maximumTotalProducerByteCount": 2 * 1024 * 1024,
        "producerSelfSnapshotByteCount": PRODUCER_SELF_SNAPSHOT_BYTE_COUNT,
        "setterCallFromReturnPC": SETTER_CALL_FROM_RETURN_PC,
        "producerBridgeFromReturnPC": PRODUCER_BRIDGE_FROM_RETURN_PC,
        "producerCallFromReturnPC": PRODUCER_CALL_FROM_RETURN_PC,
        "producerBridgeInstructionHex": PRODUCER_BRIDGE_INSTRUCTION_HEX,
        "producerSelectedByCapturedMargin": False,
    }
    if any(
        configuration.get(key) != value for key, value in expected_configuration.items()
    ):
        raise ValueError("producer capture configuration differs")

    producer_values = frozen.sequence(trace.get("producerCallees"), "producer callees")
    if not 0 < len(producer_values) <= 64:
        raise ValueError("producer callee count differs")
    producers: list[dict[str, Any]] = []
    total_bytes = 0
    for index, value in enumerate(producer_values):
        producer = frozen.mapping(value, f"producer callee {index}")
        start = frozen.integer(producer.get("symbolStart"), "producer start")
        end = frozen.integer(producer.get("symbolEnd"), "producer end")
        selected = frozen.integer(
            producer.get("selectedTarget"), "producer selected target"
        )
        byte_count = frozen.integer(
            producer.get("symbolByteCount"), "producer byte count"
        )
        payload = frozen.exact_hex(
            producer.get("hex"), byte_count, "producer complete code"
        )
        module = validate_swiftui_module(
            producer.get("module"), f"producer callee {index} module"
        )
        if (
            producer.get("completeCodeCaptured") is not True
            or not 0 < byte_count <= 131072
            or end - start != byte_count
            or not start <= selected < end
            or producer.get("symbolOffset") != selected - start
            or producer.get("codeSHA256") != hashlib.sha256(payload).hexdigest()
            or selected - module["loadAddress"] != PRODUCER_TARGET_MODULE_OFFSET
        ):
            raise ValueError("producer complete-code identity differs")
        total_bytes += byte_count
        producers.append(producer)
    if (
        total_bytes > 2 * 1024 * 1024
        or trace.get("finalProducerCalleeCount") != len(producers)
        or trace.get("finalProducerCalleeCodeByteCount") != total_bytes
    ):
        raise ValueError("producer finalization totals differ")

    setter_count = 0
    caller_indices: set[int] = set()
    for event in events:
        if event.get("type") != "marginSetter":
            continue
        setter_count += 1
        caller_index = frozen.integer(
            event.get("directCallerIndex"), "setter direct caller index"
        )
        if not 0 <= caller_index < len(callers):
            raise ValueError("setter direct caller index differs")
        caller = frozen.mapping(callers[caller_index], "setter direct caller")
        caller_module = validate_swiftui_module(
            caller.get("module"), "setter direct caller module"
        )
        if (
            caller.get("completeCodeCaptured") is not True
            or caller.get("function") != CALLER_FUNCTION
            or caller.get("symbolByteCount") != CALLER_BYTE_COUNT
            or caller.get("codeSHA256") != CALLER_CODE_SHA256
            or caller.get("symbolOffset") != CALLER_RETURN_SYMBOL_OFFSET
        ):
            raise ValueError("opened setter caller identity differs")
        caller_indices.add(caller_index)

        invocation = frozen.mapping(
            event.get("producerInvocation"), "setter producer invocation"
        )
        if (
            invocation.get("complete") is not True
            or invocation.get("capturedMarginUsedForSelection") is not False
        ):
            raise ValueError("setter producer invocation is incomplete")
        return_pc = frozen.integer(
            invocation.get("callerReturnPC"), "setter caller return PC"
        )
        backtrace = frozen.sequence(event.get("backtrace"), "setter backtrace")
        if (
            len(backtrace) < 2
            or frozen.mapping(backtrace[1], "setter caller frame").get("pc")
            != return_pc
            or caller.get("pc") != return_pc
            or return_pc - caller.get("symbolStart") != CALLER_RETURN_SYMBOL_OFFSET
        ):
            raise ValueError("setter caller return identity differs")

        setter_call = frozen.mapping(
            invocation.get("setterCall"), "setter dispatch call"
        )
        setter_call_address = return_pc + SETTER_CALL_FROM_RETURN_PC
        setter_target = decode_bl_target(
            setter_call.get("instructionHex"), setter_call_address
        )
        if (
            setter_call.get("address") != setter_call_address
            or setter_call.get("target") != setter_target
            or setter_target - caller_module["loadAddress"] != SETTER_STUB_MODULE_OFFSET
        ):
            raise ValueError("setter dispatch call differs")

        bridge = frozen.mapping(invocation.get("bridge"), "producer bridge")
        if (
            bridge.get("address") != return_pc + PRODUCER_BRIDGE_FROM_RETURN_PC
            or bridge.get("instructionHex") != PRODUCER_BRIDGE_INSTRUCTION_HEX
        ):
            raise ValueError("producer/setter bridge differs")

        producer_call = frozen.mapping(invocation.get("producerCall"), "producer call")
        producer_call_address = return_pc + PRODUCER_CALL_FROM_RETURN_PC
        producer_target = decode_bl_target(
            producer_call.get("instructionHex"), producer_call_address
        )
        producer_index = frozen.integer(
            invocation.get("producerCalleeIndex"), "producer callee index"
        )
        if (
            producer_call.get("address") != producer_call_address
            or producer_call.get("target") != producer_target
            or producer_target - caller_module["loadAddress"]
            != PRODUCER_TARGET_MODULE_OFFSET
            or not 0 <= producer_index < len(producers)
            or producers[producer_index].get("selectedTarget") != producer_target
        ):
            raise ValueError("producer call target differs")

        producer_self = frozen.integer(invocation.get("producerSelf"), "producer self")
        stack_pointer = frozen.integer(
            invocation.get("stackPointerAtSetterEntry"), "setter stack pointer"
        )
        if (
            invocation.get("producerSelfOffsetFromStackPointer")
            != PRODUCER_SELF_OFFSET_FROM_STACK_POINTER
            or producer_self - stack_pointer != PRODUCER_SELF_OFFSET_FROM_STACK_POINTER
        ):
            raise ValueError("producer self stack identity differs")
        snapshot = frozen.mapping(
            invocation.get("producerSelfSnapshot"), "producer self snapshot"
        )
        snapshot_payload = frozen.exact_hex(
            snapshot.get("hex"),
            PRODUCER_SELF_SNAPSHOT_BYTE_COUNT,
            "producer self snapshot bytes",
        )
        if (
            snapshot.get("address") != producer_self
            or snapshot.get("byteCount") != PRODUCER_SELF_SNAPSHOT_BYTE_COUNT
            or snapshot.get("sha256") != hashlib.sha256(snapshot_payload).hexdigest()
        ):
            raise ValueError("producer self snapshot byte count differs")

        return_raw = frozen.exact_hex(
            invocation.get("producerReturnF64RawLittleEndianHex"),
            8,
            "producer return",
        )
        if (
            return_raw.hex() != event.get("marginF64RawLittleEndianHex")
            or struct.pack(
                "<d",
                frozen.finite_number(
                    invocation.get("producerReturnF64"), "producer return value"
                ),
            )
            != return_raw
        ):
            raise ValueError("producer return differs from setter input")
    if setter_count == 0 or not caller_indices:
        raise ValueError("no setter producer invocation was validated")
    return {
        "producerCalleeCount": len(producers),
        "producerCalleeCodeByteCount": total_bytes,
        "setterInvocationCount": setter_count,
        "directCallerCount": len(caller_indices),
        "allSetterInvocationsExposeExactAdjacentProducer": True,
        "allProducerReturnsEqualSetterInputsBitwise": True,
        "capturedMarginUsedForProducerSelection": False,
    }


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


def transition_candidate(
    timeline: dict[str, Any],
    material: str,
    appearance: str,
    direction: str,
    geometry: str,
) -> dict[str, Any]:
    candidate = _FROZEN_TRANSITION_CANDIDATE(
        timeline, material, appearance, direction, geometry
    )
    candidate["capturedInputTransitionMaximumF64"] = candidate[
        "maximumRequiredMarginF64"
    ]
    candidate["capturedInputTransitionMaximumF64RawLittleEndianHex"] = candidate[
        "maximumRequiredMarginF64RawLittleEndianHex"
    ]
    candidate["capturedInputTransitionMaximumF32"] = candidate[
        "expectedRenderMarginF32"
    ]
    candidate["capturedInputTransitionMaximumF32RawLittleEndianHex"] = candidate[
        "expectedRenderMarginF32RawLittleEndianHex"
    ]
    if material == "clear":
        candidate["maximumRequiredMarginF64"] = 0.0
        candidate["maximumRequiredMarginF64RawLittleEndianHex"] = "0000000000000000"
        candidate["expectedRenderMarginF32"] = 0.0
        candidate["expectedRenderMarginF32RawLittleEndianHex"] = "00000000"
        candidate["selectedMaterialLaw"] = (
            "clear material stores exact zero marginWidth; its separate "
            "no-bleed backdrop path does not consume the regular transition maximum"
        )
    else:
        candidate["selectedMaterialLaw"] = (
            "regular material stores the binary64 transition maximum and rounds "
            "it once to binary32 in _copyRenderLayer"
        )
    return candidate


def validate(
    trace_path: Path,
    timeline_path: Path,
    preregistration_path: Path,
    material: str,
    appearance: str,
    direction: str,
    geometry: str,
) -> dict[str, Any]:
    validate_retry_preregistration(
        frozen.load_json(preregistration_path, "retry preregistration"),
        material,
        appearance,
        direction,
        geometry,
    )
    original = frozen.validate_events
    original_candidate = frozen.transition_candidate
    frozen.validate_events = validate_events
    frozen.transition_candidate = transition_candidate
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
        frozen.transition_candidate = original_candidate
    trace = frozen.mapping(frozen.load_json(trace_path, "trace"), "trace")
    events = [
        frozen.mapping(value, "event")
        for value in frozen.sequence(trace.get("events"), "events")
    ]
    callers = frozen.validate_callers(trace)
    producer_provenance = validate_producer_provenance(trace, events, callers)
    corrected = sum(event.get("type") == "copyMarginStore" for event in events)
    result["backdropMarginWriterExecutionRetryValidationSchemaVersion"] = (
        RETRY_VALIDATION_SCHEMA_VERSION
    )
    result["classification"] = (
        "prospective material-specific captured-input margin transfer with the "
        "ABI-correct model/store/render join and exact adjacent Swift producer"
    )
    result["writerExecution"]["opaqueEntryArgumentDiscovery"] = {
        "field": "_copyRenderLayer first explicit Objective-C argument x2",
        "isRenderObject": False,
        "copyStoreEventCountValidatedWithoutX2RenderAssumption": corrected,
        "capturedValueUsedForCorrection": False,
        "marginValueUsedForCorrection": False,
        "cropOrImageUsedForCorrection": False,
    }
    result["writerExecution"]["producerProvenance"] = producer_provenance
    result["sealedConclusion"]["opaqueCopyArgumentABIResolved"] = True
    result["sealedConclusion"]["materialSpecificMarginLawSelected"] = True
    result["sealedConclusion"][
        "materialSpecificMarginCandidateProspectiveBitExactForThisCase"
    ] = True
    result["sealedConclusion"]["clearZeroMarginLawProspectiveBitExactForThisCase"] = (
        material == "clear"
    )
    result["sealedConclusion"][
        "regularTransitionMaximumLawProspectiveBitExactForThisCase"
    ] = material == "regular"
    result["sealedConclusion"][
        "transitionMaximumCandidateProspectiveBitExactForThisCase"
    ] = material == "regular"
    result["sealedConclusion"]["adjacentMarginProducerCodeOpened"] = True
    result["sealedConclusion"]["adjacentMarginProducerArithmeticDecoded"] = False
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
