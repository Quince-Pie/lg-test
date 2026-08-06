#!/usr/bin/env python3
"""Validate the complete local allocation-profile provider-object matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


RESULT_SCHEMA_VERSION = 1
EXPECTED_SHA256 = {
    "preregistration": "2e4b4bc919d90fb7abed939641cfce37bd0d3c48acd89b5dfb1c50623d35c918",
    "captureContext": "87801d05b664f5f5d9c3fba7e4b26deea02c7ca71e6245c528972b6ed1274b8e",
    "lldbExitStatus": "9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa",
    "lldbLog": "d45f23eee3e9e853fe5ebe317f8944eec04e668cd254c26a64583b025553863b",
    "trace": "0e83312d2535ad6601b6bcae178e939e13a9ebae95d15efcc166ffde013e6d72",
    "timeline": "1dd73cfa4e696c43a0612c107e9a5edcb78c72b14ba80e67a53e4e99b06d931f",
    "progress": "cb4986842de21454883ea6481555fb85df79f390f0556b2df08fed236b3c0246",
    "runtimeStdout": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "runtimeStderr": "faf8b47bd80acd915f14efbaefd92d02ab1c0ba1a9ff23b24383a927d7730773",
}
EXPECTED_COMMIT = "b694a919a7dd2e6c3a06b24fd1705a1bcb6646f3"
EXPECTED_BINARY_SHA256 = (
    "b9cb4068e77a61ff87794fa20a5c273e007f3ee20dd74503b1ab78839104e8dd"
)
EXPECTED_CAPTURE_SHA256 = (
    "3796c5791462c30a971b2ab1063e7e3dc5a30ede1a82d7fa0a452a469d1306d4"
)
EXPECTED_PREREGISTRATION_SHA256 = EXPECTED_SHA256["preregistration"]
EXPECTED_ENVIRONMENT = {
    "LG_GEOMETRY_POLICY": "0",
    "LG_GLASS_APPEARANCE": "light",
    "LG_GLASS_GEOMETRY": "circle-127-center",
    "LG_GLASS_MATERIAL": "regular",
    "LG_TRANSITION_ALLOCATION_DENSE": "1",
    "LG_TRANSITION_ALLOCATION_FIXED_STATE": "0",
    "LG_TRANSITION_ALLOCATION_ONLY": "1",
    "LG_TRANSITION_ALLOCATION_PATH_ISOLATION": "0",
    "LG_TRANSITION_CONTROLLED_BACKDROP": "0",
    "LG_TRANSITION_DIRECTION": "materialize",
    "LG_TRANSITION_HIGHLIGHT_TRACE": "0",
    "LG_TRANSITION_MATRIX_BASIS": "0",
    "LG_TRANSITION_TIMELINE": "1",
    "LG_TRANSITION_UNIFORMS": "1",
}
EXPECTED_SYMBOLS = {
    "caller": {
        "function": (
            "SwiftUI.SDFLayer.updateSDFEffects(for: SwiftUI.SDFStyle, at: "
            "inout Swift.Int, in: SwiftUI.DisplayList.ViewRenderer.Environment, "
            "backdropGroupID: Swift.Optional<SwiftUI.BackdropGroupID>, blend: "
            "SwiftUI.Material.Layer.SDFLayer.GroupLayer.Blend, opacity: Swift.Float, "
            "options: SwiftUI.Material.Layer.SDFLayer.GroupLayer.Options, gain: "
            "Swift.Float, maxColorComponent: Swift.Float) -> ()"
        ),
        "byteCount": 6844,
        "moduleOffset": 0x9265FC,
        "codeSHA256": "d60a0510382f913b937ceb2c20111c4dcf1b4dd9d6d49388c2fe5c4d2683168c",
    },
    "group": {
        "function": "SwiftUI.SDFStyle.Group.margin.getter : CoreGraphics.CGFloat",
        "byteCount": 732,
        "moduleOffset": 0x3715D0,
        "codeSHA256": "5414dac1e2dce7753af9afe072ceb3b7f938ec894df81bd621866f50d03b015d",
    },
    "wrapper": {
        "function": "SwiftUI._AnyCAFilterProvider.sdfBackdropMargin.getter : CoreGraphics.CGFloat",
        "byteCount": 116,
        "moduleOffset": 0x76BC54,
        "codeSHA256": "922147f9c8b9cecdc273065e6677312965449069e4cf076e65daa1aba0a9d0ee",
    },
    "provider": {
        "function": "___lldb_unnamed_symbol_2409180b4",
        "byteCount": 984,
        "moduleOffset": 0xB70B4,
        "codeSHA256": "a76c6f0b03cc6b64c6b040220f495c5f22d7e1e5322efb3cb139554dd397c10b",
    },
}
SWIFTUICORE_UUID = "99606D45-C40A-3C69-AE51-5F0C4E32E531"
DESIGN_LIBRARY_UUID = "1E980802-69F5-3E69-89EF-50088297FCF5"
OBJECT_BYTE_COUNT = 384
MAXIMUM_CALL_COUNT = 4096


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is unreadable: {error}") from error


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} is not an object")
    return value


def sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{label} is not an array")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_symbol(
    record_value: Any,
    contract: Mapping[str, Any],
    expected_uuid: str,
    label: str,
) -> Mapping[str, Any]:
    record = mapping(record_value, label)
    module = mapping(record.get("module"), f"{label} module")
    code = bytes.fromhex(str(record.get("hex", "")))
    require(module.get("valid") is True, f"{label} module is invalid")
    require(module.get("uuid") == expected_uuid, f"{label} module UUID differs")
    require(record.get("function") == contract["function"], f"{label} function differs")
    require(record.get("symbolByteCount") == contract["byteCount"], f"{label} byte count differs")
    require(record.get("symbolStart") - module.get("loadAddress") == contract["moduleOffset"], f"{label} module offset differs")
    require(len(code) == contract["byteCount"], f"{label} code payload length differs")
    require(hashlib.sha256(code).hexdigest() == contract["codeSHA256"], f"{label} code hash differs")
    require(record.get("codeSHA256") == contract["codeSHA256"], f"{label} recorded code hash differs")
    return record


def validate_frame(
    frame_value: Any,
    symbol: Mapping[str, Any],
    offset: int,
    label: str,
) -> None:
    frame = mapping(frame_value, label)
    require(frame.get("function") == symbol["function"], f"{label} function differs")
    require(frame.get("symbolStart") == symbol["symbolStart"], f"{label} symbol start differs")
    require(frame.get("symbolOffset") == offset, f"{label} symbol offset differs")
    require(frame.get("pc") == symbol["symbolStart"] + offset, f"{label} PC differs")
    require(mapping(frame.get("module"), f"{label} module").get("uuid") == symbol["module"]["uuid"], f"{label} module differs")


def validate_snapshot(
    snapshot_value: Any,
    address: int,
    label: str,
) -> bytes:
    snapshot = mapping(snapshot_value, label)
    payload = bytes.fromhex(str(snapshot.get("hex", "")))
    require(snapshot.get("address") == address, f"{label} address differs")
    require(snapshot.get("byteCount") == OBJECT_BYTE_COUNT, f"{label} byte count differs")
    require(len(payload) == OBJECT_BYTE_COUNT, f"{label} payload length differs")
    require(snapshot.get("sha256") == hashlib.sha256(payload).hexdigest(), f"{label} SHA-256 differs")
    return payload


def png_dimensions(path: Path) -> tuple[int, int]:
    payload = path.read_bytes()[:24]
    require(payload[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not PNG")
    require(payload[12:16] == b"IHDR", f"{path.name} lacks IHDR")
    return struct.unpack(">II", payload[16:24])


def validate_context(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    require(lines[0] == EXPECTED_COMMIT, "capture commit differs")
    require(lines[1].startswith(EXPECTED_BINARY_SHA256 + "  "), "binary context hash differs")
    require(lines[2].startswith(EXPECTED_CAPTURE_SHA256 + "  "), "capture source context hash differs")
    require(lines[3].startswith(EXPECTED_PREREGISTRATION_SHA256 + "  "), "preregistration context hash differs")
    environment = dict(line.split("=", 1) for line in lines[4:])
    trace_output = environment.pop("LG_CASE22_PROVIDER_OBJECT_MATRIX_MINIMAL_TRACE_OUTPUT", None)
    require(trace_output is not None and trace_output.endswith("/provider-object-matrix-trace.json"), "trace output environment differs")
    require(environment == EXPECTED_ENVIRONMENT, "capture environment differs")
    return environment


def validate_timeline(timeline_value: Any, artifact_directory: Path) -> dict[str, Any]:
    timeline = mapping(timeline_value, "timeline")
    require(timeline.get("schemaVersion") == 5, "timeline schema differs")
    require(timeline.get("material") == "regular", "timeline material differs")
    require(timeline.get("appearance") == "light", "timeline appearance differs")
    require(mapping(timeline.get("geometry"), "timeline geometry").get("name") == "circle-127-center", "timeline geometry differs")
    require(timeline.get("direction") == "materialize", "timeline direction differs")
    require(timeline.get("windowBackingScaleFactor") == 2, "timeline is not Retina 2x")
    require(timeline.get("sampleCount") == 33, "timeline sample count differs")
    require(timeline.get("failedSamples") == 0, "timeline has failed samples")
    require("error" not in timeline, "timeline contains an error")
    samples = sequence(timeline.get("samples"), "timeline samples")
    require(len(samples) == 33, "timeline sample length differs")
    expected_names = {f"transition-materialize-{index:02d}-rgba8.png" for index in range(33)}
    observed_names = {path.name for path in artifact_directory.glob("transition-materialize-*-rgba8.png")}
    require(observed_names == expected_names, "canonical image file set differs")
    image_hashes: list[str] = []
    for index, sample_value in enumerate(samples):
        sample = mapping(sample_value, f"timeline sample {index}")
        require(sample.get("executed") is True, f"timeline sample {index} did not execute")
        capture = mapping(sample.get("windowCapture"), f"timeline sample {index} capture")
        name = f"transition-materialize-{index:02d}-rgba8.png"
        require(capture.get("pngFile") == name, f"timeline sample {index} image name differs")
        image_path = artifact_directory / name
        digest = sha256(image_path)
        require(capture.get("pngSHA256") == digest, f"timeline sample {index} image hash differs")
        width, height = png_dimensions(image_path)
        require((width, height) == (capture.get("width"), capture.get("height")), f"timeline sample {index} dimensions differ")
        image_hashes.append(digest)
    dynamic = mapping(timeline.get("dynamicBackgroundUniforms"), "dynamic background uniforms")
    require(dynamic.get("requested") is True and dynamic.get("executed") is True, "dynamic background capture did not execute")
    require(dynamic.get("evidenceMode") == "allocation-metadata-v1", "dynamic evidence mode differs")
    require(dynamic.get("executedSampleCount") == 32, "dynamic sample count differs")
    return {
        "schemaVersion": 5,
        "sampleCount": 33,
        "failedSamples": 0,
        "canonicalImageCount": len(image_hashes),
        "distinctCanonicalImageSHA256Count": len(set(image_hashes)),
        "windowBackingScaleFactor": 2,
        "dynamicEvidenceMode": dynamic["evidenceMode"],
    }


def validate_trace(trace_value: Any) -> dict[str, Any]:
    trace = mapping(trace_value, "trace")
    configuration = mapping(trace.get("configuration"), "trace configuration")
    require(trace.get("case22ProviderObjectMatrixMinimalLocalMacOSLldbTraceSchemaVersion") == 1, "trace schema differs")
    require(configuration.get("maximumCallCount") == MAXIMUM_CALL_COUNT, "trace call bound differs")
    require(configuration.get("previousMaximumCallCount") == 512, "trace previous bound differs")
    require(configuration.get("boundChangeOnly") is True, "trace is not bound-only")
    require(configuration.get("activeBreakpointCountPerSelectedCall") == 6, "active breakpoint count differs")
    require(configuration.get("perSelectedCallMaximumStopCount") == 6, "selected stop bound differs")
    require(configuration.get("unrelatedWrapperOrProviderCallbacksArmed") is False, "unrelated callbacks were armed")
    for key in (
        "capturedObjectUsedForSelection",
        "capturedReturnUsedForSelection",
        "capturedMarginUsedForSelection",
        "capturedCropUsedForSelection",
        "capturedImageUsedForSelection",
        "capturedPixelUsedForSelection",
        "capturedValueUsedToSelectNewBound",
    ):
        require(configuration.get(key) is False, f"trace {key} differs")

    modules = mapping(trace.get("modules"), "trace modules")
    require(mapping(modules.get("swiftUICore"), "SwiftUICore module").get("uuid") == SWIFTUICORE_UUID, "SwiftUICore UUID differs")
    require(mapping(modules.get("designLibrary"), "DesignLibrary module").get("uuid") == DESIGN_LIBRARY_UUID, "DesignLibrary UUID differs")
    caller = validate_symbol(trace.get("caller"), EXPECTED_SYMBOLS["caller"], SWIFTUICORE_UUID, "caller")
    group = validate_symbol(trace.get("group"), EXPECTED_SYMBOLS["group"], SWIFTUICORE_UUID, "Group")
    wrapper = validate_symbol(trace.get("wrapper"), EXPECTED_SYMBOLS["wrapper"], SWIFTUICORE_UUID, "wrapper")
    provider = validate_symbol(trace.get("provider"), EXPECTED_SYMBOLS["provider"], DESIGN_LIBRARY_UUID, "provider")
    require(caller.get("symbolOffset") == 5760, "caller selected offset differs")
    caller_code = bytes.fromhex(caller["hex"])
    require(caller_code[5760:5764].hex() == "5526e997", "caller Group call instruction differs")

    breakpoints = sequence(trace.get("breakpoints"), "trace breakpoints")
    require(len(breakpoints) == 6, "trace breakpoint count differs")
    require(
        {mapping(value, "breakpoint").get("name") for value in breakpoints}
        == {
            "selected_callsite",
            "wrapper_entry",
            "provider_entry",
            "provider_return",
            "group_return",
            "selected_caller_return",
        },
        "trace breakpoint names differ",
    )
    calls = sequence(trace.get("calls"), "provider calls")
    require(2 <= len(calls) < MAXIMUM_CALL_COUNT, "provider call count violates the frozen bound")
    object_payloads: list[bytes] = []
    return_words: list[str] = []
    thread_ids: set[int] = set()
    for index, call_value in enumerate(calls):
        call = mapping(call_value, f"provider call {index}")
        require(call.get("callIndex") == index, f"provider call {index} index differs")
        wrapper_address = call.get("wrapperObjectAddress")
        provider_address = call.get("providerObjectAddress")
        require(isinstance(wrapper_address, int) and isinstance(provider_address, int), f"provider call {index} address differs")
        require(provider_address == wrapper_address + 16, f"provider call {index} object offset differs")
        require(call.get("providerObjectOffsetFromWrapper") == 16, f"provider call {index} recorded object offset differs")
        wrapper_payload = validate_snapshot(call.get("wrapperEntryObject"), provider_address, f"provider call {index} wrapper snapshot")
        entry_payload = validate_snapshot(call.get("providerEntryObject"), provider_address, f"provider call {index} entry snapshot")
        return_payload = validate_snapshot(call.get("returnObject"), provider_address, f"provider call {index} return snapshot")
        require(wrapper_payload == entry_payload == return_payload, f"provider call {index} object changed")
        require(call.get("providerEntryMatchesWrapperObjectBitwise") is True, f"provider call {index} entry join differs")
        require(call.get("objectChanged") is False, f"provider call {index} mutation flag differs")
        raw_v0 = str(call.get("returnV0RawLittleEndianHex", ""))
        raw_f64 = str(call.get("returnF64RawLittleEndianHex", ""))
        group_v0 = str(call.get("groupReturnV0RawLittleEndianHex", ""))
        require(len(bytes.fromhex(raw_v0)) == 16, f"provider call {index} return width differs")
        require(raw_v0[:16] == raw_f64 and raw_v0 == group_v0, f"provider call {index} return join differs")
        require(call.get("providerReturnMatchesGroupBitwise") is True, f"provider call {index} Group join flag differs")
        validate_frame(call.get("wrapperEntryFrame"), wrapper, 0, f"provider call {index} wrapper entry")
        validate_frame(call.get("providerEntryFrame"), provider, 0, f"provider call {index} provider entry")
        validate_frame(call.get("wrapperReturnFrame"), wrapper, 104, f"provider call {index} wrapper return")
        validate_frame(call.get("groupCallerFrame"), group, 620, f"provider call {index} Group caller")
        validate_frame(call.get("groupReturnFrame"), group, 620, f"provider call {index} Group return")
        require(isinstance(call.get("threadID"), int), f"provider call {index} thread differs")
        thread_ids.add(call["threadID"])
        object_payloads.append(entry_payload)
        return_words.append(raw_f64)

    require(trace.get("status") == "finalized", "trace did not finalize")
    require(trace.get("statusBeforeFinalization") == "between-selected-calls", "trace did not finish between calls")
    require(not sequence(trace.get("failures"), "trace failures"), "trace contains failures")
    for key in (
        "finalCallCount",
        "finalSelectedCallerCount",
        "finalProviderEnteredCallCount",
        "finalReturnedCallCount",
        "finalGroupLinkedCallCount",
        "finalUnchangedObjectCount",
    ):
        require(trace.get(key) == len(calls), f"trace {key} differs")
    require(trace.get("finalPendingThreadCount") == 0, "trace has a pending provider call")
    require(trace.get("finalActiveSelectedCallerCount") == 0, "trace has an active selected caller")
    require(trace.get("finalFailureCount") == 0, "trace failure count differs")

    varying_byte_offsets = [
        offset
        for offset in range(OBJECT_BYTE_COUNT)
        if len({payload[offset] for payload in object_payloads}) > 1
    ]
    distinct_objects = len(set(object_payloads))
    distinct_returns = len(set(return_words))
    require(distinct_objects >= 2 or distinct_returns >= 2, "provider matrix lacks distinct objects or returns")
    require(set(return_words) == {"0000000000000000"}, "allocation-profile return is not exact zero")

    nonzero_scaled_matches = 0
    for payload in object_payloads:
        shape = struct.unpack_from("<d", payload, 24)[0]
        secondary = struct.unpack_from("<d", payload, 232)[0]
        if shape != 0.0:
            require(struct.pack("<d", secondary) == struct.pack("<d", shape * -0.8), "offset 232 scaling relation differs")
            nonzero_scaled_matches += 1
    require(nonzero_scaled_matches > 1, "offset 232 scaling relation lacks coverage")
    return {
        "callCount": len(calls),
        "threadCount": len(thread_ids),
        "distinctProviderObjectCount": distinct_objects,
        "distinctProviderReturnCount": distinct_returns,
        "providerReturnWords": sorted(set(return_words)),
        "unchangedProviderObjectCount": len(calls),
        "providerGroupLinkedCallCount": len(calls),
        "varyingProviderObjectByteCount": len(varying_byte_offsets),
        "varyingProviderObjectByteOffsets": varying_byte_offsets,
        "nonzeroOffset232EqualsOffset24TimesNegativePoint8Count": nonzero_scaled_matches,
        "failureCount": 0,
        "pendingCallCount": 0,
    }


def validate_endpoint_candidates(
    trace_value: Any,
    timeline_value: Any,
) -> list[dict[str, Any]]:
    calls = sequence(mapping(trace_value, "trace").get("calls"), "provider calls")
    first_object = bytes.fromhex(mapping(mapping(calls[0], "first provider call").get("providerEntryObject"), "first provider object")["hex"])
    dynamic = mapping(mapping(timeline_value, "timeline").get("dynamicBackgroundUniforms"), "dynamic background uniforms")
    records = sequence(dynamic.get("records"), "dynamic records")
    endpoint_inputs = mapping(mapping(mapping(records[-1], "endpoint dynamic record").get("filter"), "endpoint filter").get("inputValues"), "endpoint inputs")
    specifications = (
        (24, "inputShadowAmount", 1.0),
        (152, "inputBlurRadius", 2.0),
        (232, "inputInnerRefractionAmount", 1.0),
        (352, "inputBleedAmount", 1.0),
    )
    results = []
    for offset, key, scale in specifications:
        provider_word = first_object[offset : offset + 8]
        public_word = struct.pack("<d", float(endpoint_inputs[key]) * scale)
        require(provider_word == public_word, f"endpoint candidate {key} word differs")
        results.append(
            {
                "providerObjectOffset": offset,
                "candidateInput": key,
                "scale": scale,
                "rawLittleEndianHex": provider_word.hex(),
                "wordEqual": True,
                "authenticatedTemporalJoin": False,
                "publicInputMappingAuthority": False,
            }
        )
    return results


def validate(preregistration_path: Path, artifact_directory: Path) -> dict[str, Any]:
    paths = {
        "preregistration": preregistration_path,
        "captureContext": artifact_directory / "capture-context.txt",
        "lldbExitStatus": artifact_directory / "lldb-exit-status.txt",
        "lldbLog": artifact_directory / "lldb.log",
        "trace": artifact_directory / "provider-object-matrix-trace.json",
        "timeline": artifact_directory / "transition-timeline.json",
        "progress": artifact_directory / "transition-progress.json",
        "runtimeStdout": artifact_directory / "runtime-stdout.log",
        "runtimeStderr": artifact_directory / "runtime-stderr.log",
    }
    observed_hashes = {name: sha256(path) for name, path in paths.items()}
    require(observed_hashes == EXPECTED_SHA256, "input SHA-256 identity differs")
    preregistration = mapping(load_json(preregistration_path, "preregistration"), "preregistration")
    require(preregistration.get("runtimeOutcomeFrozenBeforeDispatch") is None, "outcome was not sealed before dispatch")
    require(preregistration["retry2Overlay"]["maximumCallCount"] == MAXIMUM_CALL_COUNT, "preregistered bound differs")
    validate_context(paths["captureContext"])
    require(paths["lldbExitStatus"].read_text(encoding="utf-8") == "0\n", "LLDB exit status differs")
    lldb_log = paths["lldbLog"].read_text(encoding="utf-8")
    require("Process 7794 exited with status = 0" in lldb_log, "application process did not exit zero")
    require("minimal_retry2_local_macos_26_6_1_lldb.selected_callsite" in lldb_log, "direct callback namespace differs")
    require("Traceback" not in lldb_log, "LLDB log contains a traceback")
    trace = load_json(paths["trace"], "trace")
    timeline = load_json(paths["timeline"], "timeline")
    trace_result = validate_trace(trace)
    timeline_result = validate_timeline(timeline, artifact_directory)
    endpoint_candidates = validate_endpoint_candidates(trace, timeline)
    return {
        "backdropMarginCase22ProviderObjectMatrixMinimalRetry2LocalMacOSValidationSchemaVersion": RESULT_SCHEMA_VERSION,
        "classification": "exact all-live provider-object matrix for the opened regular/light circle-127 allocation-only materialize profile; narrow object-layout authority only",
        "inputs": {name: {"path": str(path), "sha256": observed_hashes[name]} for name, path in paths.items()},
        "application": {
            "processExitStatus": 0,
            **timeline_result,
        },
        "trace": trace_result,
        "retrospectiveEndpointCandidateSemantics": endpoint_candidates,
        "captureContractPassed": True,
        "exactAllLiveProviderObjectsForOpenedAllocationProfile": True,
        "exactObjectOffsetAndReturnCovarianceForOpenedAllocationProfile": True,
        "completeFiniteProviderLaw": False,
        "publicInputMappingAuthority": False,
        "freshProfileTransfer": False,
        "physicalOutputTransfer": False,
        "independentWalleZeroByteFrameParity": False,
        "productionShaderAuthorized": False,
        "liquidGlassParityEstablished": False,
        "nextExactGate": "repeat the same exact call/object/return capture on a prospectively frozen normal live transition so nonzero provider gates and returns open, then intervene on candidate public inputs upstream of provider construction",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--artifact-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        result = validate(arguments.preregistration, arguments.artifact_directory)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(payload, end="")
    else:
        arguments.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
