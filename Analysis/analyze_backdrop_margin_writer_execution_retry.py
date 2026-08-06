#!/usr/bin/env python3
"""Open the four-case writer retry without upgrading failed transport to evidence."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import struct
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_backdrop_margin_writer_execution as base
import validate_backdrop_margin_writer_execution_retry as retry


ANALYSIS_SCHEMA_VERSION = 1
RUN_ID = 31113785381
HEAD_SHA = "16102867187c66f20b560bb9a36667bdd3ae6115"
SWIFTUICORE_UUID = "A8FC6D2D-DFE9-3557-A734-7F2B231F8C97"
PRODUCER_FUNCTION = "SwiftUI.SDFStyle.Group.margin.getter : CoreGraphics.CGFloat"
PRODUCER_MODULE_OFFSET = 0x3715D0
PRODUCER_BYTE_COUNT = 732
PRODUCER_CODE_SHA256 = (
    "5414dac1e2dce7753af9afe072ceb3b7f938ec894df81bd621866f50d03b015d"
)

CASES = {
    "clear-light": {
        "profile": ("clear", "light", "circle-408-center"),
        "artifactID": 8972897031,
        "artifactDigest": (
            "sha256:4f5e4154fa1677a4efd7f59a5ea1f8e0fcb4f3bc7de59f05a00cca7c7c91bd3e"
        ),
        "artifactSizeBytes": 67791256,
        "traceSHA256": (
            "4d1e3afef588459576d4ccc64fb40afddfacf0fa85e0375064e466ebf7d0465b"
        ),
        "timelineSHA256": (
            "7f7af5899c3d2a9580648757d25f1a26e40a6049c566efe89b154fd0e2daa522"
        ),
        "timelineError": "presentation glassBackground snapshot unavailable at sample 24",
        "eventTypeCounts": {
            "marginSetter": 131,
            "copyEntry": 266,
            "copyMarginStore": 136,
            "backdropBounds": 0,
        },
    },
    "clear-dark": {
        "profile": ("clear", "dark", "circle-640-phase-0501"),
        "artifactID": 8972898736,
        "artifactDigest": (
            "sha256:8157b13d353062132a86d179d618beaad2852a44529694defd71cb6f506921cf"
        ),
        "artifactSizeBytes": 90846621,
        "traceSHA256": (
            "5d3ef502922b03f077fb9144348220f275237b31c85493bd3f76f7ad21e3e364"
        ),
        "timelineSHA256": (
            "728b801ab3788d3311f42023177443a04fb66cb6bf522d5cd028bbdff0a5683b"
        ),
        "timelineError": "presentation glassBackground snapshot unavailable at sample 31",
        "eventTypeCounts": {
            "marginSetter": 124,
            "copyEntry": 252,
            "copyMarginStore": 129,
            "backdropBounds": 0,
        },
    },
    "regular-light": {
        "profile": ("regular", "light", "circle-768-center"),
        "artifactID": 8973005023,
        "artifactDigest": (
            "sha256:bb610cc16963e45aad8003b2cbe2bdc2ec35bb33ca0a8f776ed3d0daa4b126aa"
        ),
        "artifactSizeBytes": 88610815,
        "traceSHA256": (
            "a09f296f20bf805cee9277f1a976668b9c36fee28ddc4af69d04ddee14fef73d"
        ),
        "timelineSHA256": (
            "6b3de340f4dc1184bf59116d5d3f708b5325e69f74b75df7849c65aefdc9e35f"
        ),
        "validationSHA256": (
            "e0e52288e4a40e6b38f324ecdaecdca7cc6de0d053784f5188f4f0da311c4f8a"
        ),
        "eventTypeCounts": {
            "marginSetter": 100,
            "copyEntry": 368,
            "copyMarginStore": 212,
            "backdropBounds": 320,
        },
        "maximumF64Raw": "cccccccccccc7040",
        "maximumF32Raw": "66668643",
    },
    "regular-dark": {
        "profile": ("regular", "dark", "circle-1535-center"),
        "artifactID": 8973017885,
        "artifactDigest": (
            "sha256:74938ec9011dc77c0d61aa587740056e34d8e51112ae6459b330bca02e534adb"
        ),
        "artifactSizeBytes": 71935628,
        "traceSHA256": (
            "5cbc0ba5b3a155a5e6ad950b559f01284e998923f7c14476c95866b3115cf5b6"
        ),
        "timelineSHA256": (
            "068bad1a968b9cb1dc4b86bf38fb6c7891b6fa00607b14c47a2ac8f91352c4d7"
        ),
        "validationSHA256": (
            "6a2360eb6326731e3c5226be84b033362f0affd608c2cbef524f1c8581af24e4"
        ),
        "eventTypeCounts": {
            "marginSetter": 118,
            "copyEntry": 400,
            "copyMarginStore": 230,
            "backdropBounds": 320,
        },
        "maximumF64Raw": "0000000000ca8040",
        "maximumF32Raw": "00500644",
    },
}

# The code itself was opened prospectively.  These offsets are a retrospective
# decode gate: changing even one instruction invalidates the symbolic analysis.
KEY_INSTRUCTIONS = {
    0x02C: "88424039",  # ldrb w8, [x20,#0x10]
    0x030: "95da41a9",  # ldp x21,x22, [x20,#0x18]
    0x034: "097d0653",  # lsr w9,w8,#6
    0x044: "d70a40f9",  # ldr x23, [x22,#0x10]
    0x060: "481f188b",  # add x8,x26,x24,lsl #7
    0x0B8: "e74df797",  # BL discriminator
    0x0BC: "1f500071",  # cmp w0,#20
    0x0C4: "08080051",  # sub w8,w0,#2
    0x0C8: "1f090071",  # cmp w8,#2
    0x0D8: "000040fd",  # ldr d0,[x0]
    0x0E0: "0ac0601e",  # fabs d10,d0
    0x110: "09fd7cd3",  # lsr x9,x8,#60
    0x114: "3f1500f1",  # cmp x9,#5
    0x120: "000940fd",  # ldr d0,[x8,#0x10]
    0x124: "011940fd",  # ldr d1,[x8,#0x30]
    0x128: "2140611e",  # fneg d1,d1
    0x12C: "2038601e",  # fsub d0,d1,d0
    0x130: "0820601e",  # fcmp d0,#0
    0x134: "209d601e",  # fcsel d0,d9,d0,ls
    0x138: "4a29601e",  # fadd d10,d10,d0
    0x148: "00216a1e",  # fcmp d8,d10
    0x14C: "489d681e",  # fcsel d8,d10,d8,ls
    0x154: "1f580071",  # cmp w0,#22
    0x15C: "1f540071",  # cmp w0,#21
    0x16C: "080040fd",  # ldr d8,[x0]
    0x174: "1f040071",  # cmp w0,#1
    0x184: "087840b9",  # ldr w8,[x0,#0x78]
    0x1B8: "09fd7cd3",  # lsr x9,x8,#60
    0x1BC: "3f0900f1",  # cmp x9,#2
    0x1C8: "090d40f9",  # ldr x9,[x8,#0x18]
    0x1CC: "280940f9",  # ldr x8,[x9,#0x10]
    0x1D4: "201140fd",  # ldr d0,[x9,#0x20]
    0x1E4: "218540fc",  # ldr d1,[x9],#8
    0x1E8: "0020611e",  # fcmp d0,d1
    0x1EC: "204c601e",  # fcsel d0,d1,d0,mi
    0x1F8: "0021601e",  # fcmp d8,d0
    0x1FC: "089c681e",  # fcsel d8,d0,d8,ls
    0x20C: "140040f9",  # ldr x20,[x0]
    0x25C: "f9c92794",  # BL fixed nested helper
    0x268: "910b3fd7",  # authenticated indirect call
    0x26C: "081ca04e",  # mov v8.16b,v0.16b
    0x278: "18070091",  # add x24,x24,#1
    0x27C: "1f0317eb",  # cmp x24,x23
    0x294: "3f0d0071",  # cmp w9,#3
    0x29C: "8a2640a9",  # ldp x10,x9,[x20]
    0x2A0: "1f010271",  # cmp w8,#0x80
    0x2AC: "c0ecff54",  # b.eq back to collection loop
    0x2B0: "001da84e",  # mov v0.16b,v8.16b
}

EXPECTED_DIRECT_CALL_TARGET_OFFSETS = {
    0x0B8: 0x144E24,
    0x0D4: 0x4F38,
    0x144: 0xB6CD0,
    0x168: 0x4F38,
    0x180: 0x4F38,
    0x208: 0x4F38,
    0x254: 0x4F38,
    0x25C: 0xD64010,
    0x274: 0xB7F38,
}


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


def normalized_validation(value: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(value))
    inputs = dict(mapping(result.get("inputs"), "validation inputs"))
    inputs.pop("trace", None)
    inputs.pop("timeline", None)
    result["inputs"] = inputs
    return result


def decode_bl_target_offset(code: bytes, instruction_offset: int) -> int:
    word = struct.unpack_from("<I", code, instruction_offset)[0]
    if word & 0xFC000000 != 0x94000000:
        raise ValueError(f"producer +{instruction_offset:#x} is not BL")
    displacement = word & 0x03FFFFFF
    if displacement & 0x02000000:
        displacement -= 0x04000000
    return PRODUCER_MODULE_OFFSET + instruction_offset + displacement * 4


def validate_producer(trace: Mapping[str, Any]) -> bytes:
    producers = sequence(trace.get("producerCallees"), "producer callees")
    if len(producers) != 1:
        raise ValueError("producer callee count differs")
    producer = mapping(producers[0], "producer")
    module = mapping(producer.get("module"), "producer module")
    load_address = module.get("loadAddress")
    selected = producer.get("selectedTarget")
    if (
        module.get("uuid") != SWIFTUICORE_UUID
        or not isinstance(load_address, int)
        or isinstance(load_address, bool)
        or not isinstance(selected, int)
        or isinstance(selected, bool)
        or selected - load_address != PRODUCER_MODULE_OFFSET
        or producer.get("function") != PRODUCER_FUNCTION
        or producer.get("symbolByteCount") != PRODUCER_BYTE_COUNT
        or producer.get("codeSHA256") != PRODUCER_CODE_SHA256
        or producer.get("completeCodeCaptured") is not True
    ):
        raise ValueError("producer identity differs")
    code = base.exact_hex(producer.get("hex"), PRODUCER_BYTE_COUNT, "producer code")
    if hashlib.sha256(code).hexdigest() != PRODUCER_CODE_SHA256:
        raise ValueError("producer code bytes differ")
    for offset, expected in KEY_INSTRUCTIONS.items():
        if code[offset : offset + 4].hex() != expected:
            raise ValueError(f"producer instruction +{offset:#x} differs")
    observed_targets = {
        offset: decode_bl_target_offset(code, offset)
        for offset in EXPECTED_DIRECT_CALL_TARGET_OFFSETS
    }
    if observed_targets != EXPECTED_DIRECT_CALL_TARGET_OFFSETS:
        raise ValueError("producer direct-call targets differ")
    return code


def validate_trace_common(
    trace: Mapping[str, Any], expected: Mapping[str, Any]
) -> dict[str, Any]:
    if (
        trace.get("status") != "finalized"
        or trace.get("failures") != []
        or trace.get("eventTypeCounts") != expected["eventTypeCounts"]
        or trace.get("finalEventCount") != sum(expected["eventTypeCounts"].values())
    ):
        raise ValueError("trace completion or event counts differ")
    validate_producer(trace)
    callers = base.validate_callers(dict(trace))
    events = [
        base.mapping(value, "event")
        for value in base.sequence(trace.get("events"), "events")
    ]
    provenance = retry.validate_producer_provenance(dict(trace), events, callers)
    setter_events = [event for event in events if event.get("type") == "marginSetter"]
    returns = Counter(event["marginF64RawLittleEndianHex"] for event in setter_events)
    self_tags = {
        bytes.fromhex(event["producerInvocation"]["producerSelfSnapshot"]["hex"])[0x10]
        for event in setter_events
    }
    if self_tags != {0x40}:
        raise ValueError("producer self collection tag differs")
    numeric_returns = [struct.unpack("<d", bytes.fromhex(raw))[0] for raw in returns]
    if not numeric_returns or any(
        not math.isfinite(value) for value in numeric_returns
    ):
        raise ValueError("producer return domain differs")
    return {
        "eventTypeCounts": dict(expected["eventTypeCounts"]),
        "producerInvocationCount": len(setter_events),
        "distinctProducerReturnWordCount": len(returns),
        "minimumProducerReturnF64": min(numeric_returns),
        "maximumProducerReturnF64": max(numeric_returns),
        "maximumProducerReturnF64RawLittleEndianHex": max(
            returns, key=lambda raw: struct.unpack("<d", bytes.fromhex(raw))[0]
        ),
        "producerSelfCollectionTagByte": 0x40,
        "producerProvenance": provenance,
    }


def analyze_case(
    name: str,
    directory: Path,
    preregistration_path: Path,
) -> tuple[dict[str, Any], bytes]:
    expected = CASES[name]
    trace_path = directory / "backdrop-margin-writer-trace.json"
    timeline_path = directory / "transition-timeline.json"
    if sha256(trace_path) != expected["traceSHA256"]:
        raise ValueError(f"{name} trace SHA-256 differs")
    if sha256(timeline_path) != expected["timelineSHA256"]:
        raise ValueError(f"{name} timeline SHA-256 differs")
    trace = mapping(load_json(trace_path, f"{name} trace"), f"{name} trace")
    common = validate_trace_common(trace, expected)
    code = validate_producer(trace)
    material, appearance, geometry = expected["profile"]
    result: dict[str, Any] = {
        "case": f"{material}-{appearance}-materialize-{geometry}",
        "artifactID": expected["artifactID"],
        "artifactDigest": expected["artifactDigest"],
        "artifactSizeBytes": expected["artifactSizeBytes"],
        "traceSHA256": expected["traceSHA256"],
        "timelineSHA256": expected["timelineSHA256"],
        **common,
    }
    if material == "clear":
        timeline = mapping(load_json(timeline_path, f"{name} timeline"), "timeline")
        if timeline.get("error") != expected["timelineError"]:
            raise ValueError(f"{name} timeline failure differs")
        if common["distinctProducerReturnWordCount"] != 1 or (
            common["maximumProducerReturnF64RawLittleEndianHex"] != "0000000000000000"
        ):
            raise ValueError(f"{name} partial clear producer returns differ")
        result.update(
            {
                "jobConclusion": "failure",
                "captureFailure": expected["timelineError"],
                "validationOutputExists": False,
                "prospectiveMaterialLawResult": False,
                "partialProducerObservationMayCountAsTransfer": False,
            }
        )
        return result, code

    validation_path = directory / "backdrop-margin-writer-validation.json"
    if sha256(validation_path) != expected["validationSHA256"]:
        raise ValueError(f"{name} CI validation SHA-256 differs")
    ci_validation = mapping(
        load_json(validation_path, f"{name} CI validation"),
        f"{name} CI validation",
    )
    independent = retry.validate(
        trace_path,
        timeline_path,
        preregistration_path,
        material,
        appearance,
        "materialize",
        geometry,
    )
    if normalized_validation(ci_validation) != normalized_validation(independent):
        raise ValueError(f"{name} independent validation differs")
    candidate = mapping(ci_validation.get("candidate"), "candidate")
    writer = mapping(ci_validation.get("writerExecution"), "writer execution")
    if (
        ci_validation.get("conclusion") != "success"
        or candidate.get("maximumRequiredMarginF64RawLittleEndianHex")
        != expected["maximumF64Raw"]
        or candidate.get("expectedRenderMarginF32RawLittleEndianHex")
        != expected["maximumF32Raw"]
        or writer.get("completeChainCount") != 32
        or writer.get("allStructurallyJoinedChainsBitExact") is not True
    ):
        raise ValueError(f"{name} prospective validation differs")
    result.update(
        {
            "jobConclusion": "success",
            "validationSHA256": expected["validationSHA256"],
            "independentValidationEqualExceptCallerPaths": True,
            "completeBitExactChainCount": writer["completeChainCount"],
            "candidateMaximumF64": candidate["maximumRequiredMarginF64"],
            "candidateMaximumF64RawLittleEndianHex": expected["maximumF64Raw"],
            "renderMarginF32": candidate["expectedRenderMarginF32"],
            "renderMarginF32RawLittleEndianHex": expected["maximumF32Raw"],
            "prospectiveRegularBranchResult": True,
        }
    )
    return result, code


def analyze(
    directories: Mapping[str, Path],
    preregistration_path: Path,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    producer_codes: list[bytes] = []
    for name in CASES:
        result, code = analyze_case(name, directories[name], preregistration_path)
        results.append(result)
        producer_codes.append(code)
    if any(code != producer_codes[0] for code in producer_codes[1:]):
        raise ValueError("producer code differs between cases")
    return {
        "backdropMarginWriterExecutionRetryAnalysisSchemaVersion": (
            ANALYSIS_SCHEMA_VERSION
        ),
        "classification": (
            "immutable mixed retry result: two regular prospective jobs pass "
            "bitwise, two clear jobs preserve valid producer observations but fail "
            "before validation because the presentation snapshot disappears; the "
            "opened producer code receives retrospective symbolic decoding only"
        ),
        "run": {
            "runID": RUN_ID,
            "headSHA": HEAD_SHA,
            "conclusion": "failure",
            "createdAtUtc": "2026-08-06T15:01:10Z",
            "completedAtUtc": "2026-08-06T15:07:38Z",
            "url": "https://github.com/Quince-Pie/lg-test/actions/runs/31113785381",
        },
        "artifacts": results,
        "adjacentProducer": {
            "function": PRODUCER_FUNCTION,
            "swiftUICoreUUID": SWIFTUICORE_UUID,
            "moduleOffset": PRODUCER_MODULE_OFFSET,
            "symbolByteCount": PRODUCER_BYTE_COUNT,
            "instructionCount": PRODUCER_BYTE_COUNT // 4,
            "codeSHA256": PRODUCER_CODE_SHA256,
            "identicalCodeInAllFourArtifacts": True,
            "directCallTargetModuleOffsets": [
                {
                    "instructionOffset": offset,
                    "targetModuleOffset": target,
                }
                for offset, target in EXPECTED_DIRECT_CALL_TARGET_OFFSETS.items()
            ],
            "exactSymbolicControlFlow": [
                "initialize binary64 accumulator to +0.0",
                "iterate the Group collection count at storage +0x10 using 128-byte records",
                "dispatch each copied SDFStyle record through the exact case discriminator",
                "cases 2 and 3 contribute abs(projectedDouble) plus, for a tag-5 side payload, max(+0.0, -payload[+0x30] - payload[+0x10]); retain max(accumulator, contribution)",
                "case 1 takes the maximum binary64 member of a tag-2 side collection and retains max(accumulator, memberMaximum)",
                "case 21 replaces the accumulator with one projected binary64 value",
                "case 22 invokes a nested/dynamic margin provider and replaces the accumulator with its binary64 return",
                "other decoded case numbers contribute no margin",
                "return the accumulator in v0 without a floating-format conversion",
            ],
            "symbolicArithmeticDecoded": True,
            "publicOperandMappingDecoded": False,
            "unopenedOperands": [
                "the public SDFStyle names corresponding to discriminator values 1, 2, 3, 21, and 22",
                "the tag-2 and tag-5 pointed payload bytes referenced by the x21 side table",
                "the authenticated indirect case-22 callee at producer +0x268",
                "the per-branch operands and accumulator after each executed live record",
            ],
        },
        "diagnosis": {
            "regularProspectiveJobsPassed": 2,
            "clearProspectiveJobsPassed": 0,
            "allFourProspectiveCasesPassed": False,
            "clearFailureClass": "timeline/presentation-state transport",
            "clearTraceFailureCount": 0,
            "clearProducerCodeAndReturnCaptureCompleted": True,
            "clearValidationSkipped": True,
            "partialClearReturnsMayNotBePromotedToProspectiveTransfer": True,
            "producerSelfSnapshotLimitation": (
                "the 96-byte value contains collection headers and pointers, but "
                "the pointed 128-byte records and tagged payloads were not retained"
            ),
            "nextStructuralCapture": (
                "capture each producer discriminator, raw 128-byte record, x21 side "
                "table payload, branch operands, accumulator, and nested case-22 target"
            ),
        },
        "sealedConclusion": {
            "regularBranchProspectiveBitExactInTwoCases": True,
            "clearBranchProspectiveBitExact": False,
            "materialSpecificFourCaseGatePassed": False,
            "adjacentProducerCodeOpened": True,
            "adjacentProducerSymbolicArithmeticDecoded": True,
            "adjacentProducerPublicInputLawDecoded": False,
            "independentTemporalInputGenerationPassed": False,
            "physicalOutputTransferPassed": False,
            "independentWalleZeroByteFrameParityPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in CASES:
        parser.add_argument(f"--{name}-directory", required=True, type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    directories = {
        name: getattr(arguments, name.replace("-", "_") + "_directory")
        for name in CASES
    }
    result = analyze(directories, arguments.preregistration)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
