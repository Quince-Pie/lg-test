#!/usr/bin/env python3
"""Decode live backdrop state, its copy writer, and retrospective allocation data."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_prepare_layer_backdrop_state_writer_discovery as validator


ANALYSIS_SCHEMA_VERSION = 1
RUN_ID = 31090638908
HEAD_SHA = "a27444af9bf97ccaf0c03568f91a962d0170f051"
ARTIFACT_ID = 8963467627
ARTIFACT_DIGEST = (
    "sha256:196864e4082c96b00373d99108d506120ca7772fcbfd6633713d29e33ea9f426"
)
TRACE_SHA256 = "d77b3d4bf59940765bd3d7c20adfd484ded247e76d086c715e9cccfa2a2753b4"
TIMELINE_SHA256 = "672b639cf56070ade9b664ae58e7255ecfac6cba11f8565595b028eff217f4df"
VALIDATION_SHA256 = "420fb76aed6e13fd53177ae497f595dba300a1c68bac50781f6e762c91262f68"
INDEPENDENT_VALIDATION_SHA256 = (
    "47789f0cf0fbb49f5af6f80d6ddd63a6e4f67d6612531e5b2e2b3413794997ca"
)
EXPECTED_CORPUS_NAMES = (
    "circle-1023-center-light-materialize",
    "circle-1024-center-light-dematerialize",
    "circle-127-center-dark-dematerialize",
    "circle-127-center-dark-materialize",
    "circle-127-center-light-dematerialize",
    "circle-127-center-light-materialize",
    "circle-128-center-dark-dematerialize",
    "circle-128-center-dark-materialize",
    "circle-128-center-light-dematerialize",
    "circle-128-center-light-materialize",
    "circle-255-center-light-materialize",
    "circle-257-center-light-dematerialize",
    "circle-257-center-light-materialize",
    "circle-511-center-dark-materialize",
    "circle-512-center-light-dematerialize",
)
RECORDS_PER_DATASET = 32
ROLE_STATE_BYTE_COUNT = 2048
ROLE_RECURSIVE_CHILD_OFFSET = 0x620
COPY_RENDER_LAYER = "-[CABackdropLayer _copyRenderLayer:layerFlags:commitFlags:]"
MARGIN_GETTER = "-[CABackdropLayer marginWidth]"
MARGIN_SETTER = "-[CABackdropLayer setMarginWidth:]"
RENDER_SET_PROPERTY = (
    "CA::Render::BackdropLayer::set_property(unsigned long, unsigned int const*, "
    "bool, unsigned long, double const*)"
)
EXPECTED_SYMBOLS = {
    COPY_RENDER_LAYER: {
        "relativeStart": 221640,
        "byteCount": 1640,
        "codeSHA256": (
            "6547059b681d624b57e2996cfe4ebec262759a7e11be3f43cdd56e6b5794d838"
        ),
    },
    MARGIN_GETTER: {
        "relativeStart": 225540,
        "byteCount": 100,
        "codeSHA256": (
            "d78ead8020178d1f5220e9f3f602fd79e69152d7b5972360c92714161445e9d1"
        ),
    },
    MARGIN_SETTER: {
        "relativeStart": 3270856,
        "byteCount": 96,
        "codeSHA256": (
            "b7c5020620b41d7d8f3107e525521ad6c381b5f26dac500449838e813c2f2901"
        ),
    },
    RENDER_SET_PROPERTY: {
        "relativeStart": 2152744,
        "byteCount": 468,
        "codeSHA256": (
            "79e63b0075fa6ae3929961540990f9f2452c4b9bf9c2c251b2aa1fad2f74ecf3"
        ),
    },
}
EXPECTED_INSTRUCTIONS = {
    COPY_RENDER_LAYER: {
        936: ("e00314aa", "mov", "x0, x20"),
        940: ("ab630f94", "bl", "0x196913420"),
        944: ("0040621e", "fcvt", "s0, d0"),
        948: ("a02600bd", "str", "s0, [x21, #0x24]"),
    },
    MARGIN_GETTER: {
        32: ("000840f9", "ldr", "x0, [x0, #0x10]"),
        44: ("c13e8052", "mov", "w1, #0x1f6"),
        48: ("42028052", "mov", "w2, #0x12"),
        52: ("1252ff97", "bl", "0x19650f980"),
        56: ("e00340fd", "ldr", "d0, [sp]"),
    },
    MARGIN_SETTER: {
        32: ("000840f9", "ldr", "x0, [x0, #0x10]"),
        36: ("e00300fd", "str", "d0, [sp]"),
        44: ("c13e8052", "mov", "w1, #0x1f6"),
        48: ("42028052", "mov", "w2, #0x12"),
        52: ("c6a8f397", "bl", "0x19650cc14"),
    },
    RENDER_SET_PROPERTY: {
        300: ("1fd90771", "cmp", "w8, #0x1f6"),
        308: ("44fbffb4", "cbz", "x4, 0x1967119c4"),
        312: ("a00040fd", "ldr", "d0, [x5]"),
        316: ("0040621e", "fcvt", "s0, d0"),
        320: ("602600bd", "str", "s0, [x19, #0x24]"),
    },
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


def integer(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} is not an integer")
    return value


def binary32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def f32_hex(value: float) -> str:
    return struct.pack("<f", value).hex()


def normalized_validation(value: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(value))
    inputs = dict(mapping(result.get("inputs"), "validation inputs"))
    inputs.pop("trace", None)
    inputs.pop("timeline", None)
    result["inputs"] = inputs
    return result


def offset_components(value: Any, label: str) -> tuple[float, float]:
    record = mapping(value, label)
    try:
        payload = bytes.fromhex(str(record.get("hex")))
    except ValueError as error:
        raise ValueError(f"{label} is not hexadecimal") from error
    if len(payload) != 16 or record.get("lengthBytes") != 16:
        raise ValueError(f"{label} byte count differs")
    result = struct.unpack("<2d", payload)
    if not all(math.isfinite(component) for component in result):
        raise ValueError(f"{label} contains a non-finite component")
    return result


def required_margin(input_values: Any) -> float:
    values = mapping(input_values, "background-filter inputs")
    bleed = float(values.get("inputBleedAmount"))
    shadow = float(values.get("inputShadowAmount"))
    offset = offset_components(values.get("inputShadowOffset"), "shadow offset")
    if not all(math.isfinite(value) for value in (bleed, shadow, *offset)):
        raise ValueError("margin operands are not finite")
    return max(bleed, shadow + max(abs(offset[0]), abs(offset[1])))


def role_margin(value: Any, label: str) -> tuple[float, tuple[float, ...]]:
    snapshot = mapping(value, label)
    try:
        payload = bytes.fromhex(str(snapshot.get("hex")))
    except ValueError as error:
        raise ValueError(f"{label} is not hexadecimal") from error
    if len(payload) != ROLE_STATE_BYTE_COUNT or snapshot.get("byteCount") != len(
        payload
    ):
        raise ValueError(f"{label} byte count differs")
    child = struct.unpack_from("<4d", payload, ROLE_RECURSIVE_CHILD_OFFSET)
    if not all(math.isfinite(value) for value in child):
        raise ValueError(f"{label} recursive child is not finite")
    margin = -child[0]
    if margin < 0.0 or child[1] != -margin or binary32(margin) != margin:
        raise ValueError(f"{label} recursive-child margin differs")
    return margin, child


def topology_runs(depths: Sequence[int]) -> list[dict[str, int]]:
    result: list[dict[str, int]] = []
    for depth in depths:
        if result and result[-1]["depth"] == depth:
            result[-1]["count"] += 1
        else:
            result.append({"depth": depth, "count": 1})
    return result


def carrier_width(record: Any) -> float:
    matches = [
        mapping(item, "captured layer state")
        for item in sequence(
            mapping(record, "dynamic record").get("capturedLayerStates"),
            "captured layer states",
        )
        if mapping(item, "captured layer state").get("path") == [1]
    ]
    if len(matches) != 1:
        raise ValueError("animated carrier path [1] is not unique")
    bounds = sequence(matches[0].get("bounds"), "animated carrier bounds")
    if len(bounds) != 4:
        raise ValueError("animated carrier bounds differ")
    width = float(bounds[2])
    if not math.isfinite(width) or width < 0.0:
        raise ValueError("animated carrier width differs")
    return width


def symbol(trace: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    extension = mapping(
        trace.get("prepareLayerBackdropStateWriterDiscoveryExtension"),
        "backdrop-state extension",
    )
    inventory = mapping(extension.get("symbolInventory"), "symbol inventory")
    matches = [
        mapping(item, "symbol range")
        for item in sequence(inventory.get("ranges"), "symbol ranges")
        if name in sequence(mapping(item, "symbol range").get("names"), "symbol names")
    ]
    if len(matches) != 1:
        raise ValueError(f"{name} symbol range is not unique")
    return matches[0]


def decode_symbols(trace: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, expected in EXPECTED_SYMBOLS.items():
        item = symbol(trace, name)
        if (
            item.get("moduleRelativeStart") != expected["relativeStart"]
            or item.get("symbolByteCount") != expected["byteCount"]
            or item.get("observedCodeSHA256") != expected["codeSHA256"]
        ):
            raise ValueError(f"{name} code identity differs")
        instructions = {
            integer(
                mapping(raw, "instruction").get("offset"), "instruction offset"
            ): mapping(raw, "instruction")
            for raw in sequence(item.get("instructions"), "instructions")
        }
        selected: list[dict[str, Any]] = []
        for offset, (raw_hex, mnemonic, operands) in EXPECTED_INSTRUCTIONS[
            name
        ].items():
            instruction = mapping(instructions.get(offset), f"{name}+{offset:#x}")
            if (
                instruction.get("rawLittleEndianHex") != raw_hex
                or instruction.get("mnemonic") != mnemonic
                or instruction.get("operands") != operands
            ):
                raise ValueError(f"{name}+{offset:#x} differs")
            selected.append(
                {
                    "offset": offset,
                    "rawLittleEndianHex": raw_hex,
                    "mnemonic": mnemonic,
                    "operands": operands,
                    "comment": instruction.get("comment"),
                }
            )
        result[name] = {
            **expected,
            "selectedInstructions": selected,
        }
    return result


def analyze_corpus(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    names = tuple(sorted(path.name for path in root.iterdir() if path.is_dir()))
    if names != EXPECTED_CORPUS_NAMES:
        raise ValueError("retrospective corpus dataset set differs")

    datasets: list[dict[str, Any]] = []
    all_preterminal_dematerialize: list[tuple[float, int]] = []
    exact_records = 0
    for name in names:
        directory = root / name
        trace_path = directory / "prepare-layer-crop-policy-holdout-trace.json"
        timeline_path = directory / "transition-timeline.json"
        trace = mapping(load_json(trace_path, f"{name} trace"), f"{name} trace")
        timeline = mapping(
            load_json(timeline_path, f"{name} timeline"), f"{name} timeline"
        )
        if (
            trace.get("status") != "finalized"
            or trace.get("finalFailureCount") != 0
            or trace.get("failures") != []
        ):
            raise ValueError(f"{name} trace did not finalize cleanly")
        qualified = sequence(trace.get("qualifiedRecords"), f"{name} records")
        dynamic = mapping(
            timeline.get("dynamicBackgroundUniforms"), f"{name} dynamic uniforms"
        )
        records = sequence(dynamic.get("records"), f"{name} dynamic records")
        if len(qualified) != RECORDS_PER_DATASET or len(records) != len(qualified):
            raise ValueError(f"{name} record count differs")

        requirements: list[float] = []
        margins: list[float] = []
        children: list[tuple[float, ...]] = []
        depths: list[int] = []
        widths: list[float] = []
        for index, (raw_qualified, raw_dynamic) in enumerate(
            zip(qualified, records, strict=True), start=1
        ):
            qualified_record = mapping(raw_qualified, f"{name} qualified {index}")
            dynamic_record = mapping(raw_dynamic, f"{name} dynamic {index}")
            if (
                qualified_record.get("normalRenderOrdinal") != index
                or dynamic_record.get("sampleIndex") != index
            ):
                raise ValueError(f"{name} ordinal {index} differs")
            filter_record = mapping(
                dynamic_record.get("filter"), f"{name} filter {index}"
            )
            requirements.append(required_margin(filter_record.get("inputValues")))
            margin, child = role_margin(
                qualified_record.get("roleState"), f"{name} role {index}"
            )
            margins.append(margin)
            children.append(child)
            depth = integer(
                qualified_record.get("prepareRecursionDepth"),
                f"{name} recursion depth {index}",
            )
            if depth not in (3, 4):
                raise ValueError(f"{name} recursion depth {index} differs")
            depths.append(depth)
            widths.append(carrier_width(dynamic_record))

        candidate_unrounded = max(requirements)
        candidate = binary32(candidate_unrounded)
        if any(margin != candidate for margin in margins):
            raise ValueError(f"{name} captured-transition maximum margin differs")
        exact_records += len(margins)
        maximum_index = requirements.index(candidate_unrounded) + 1
        direction = str(timeline.get("direction"))
        if direction == "dematerialize":
            all_preterminal_dematerialize.extend(
                (width, depth)
                for index, (width, depth) in enumerate(
                    zip(widths, depths, strict=True), start=1
                )
                if index < RECORDS_PER_DATASET
            )
        datasets.append(
            {
                "name": name,
                "material": timeline.get("material"),
                "appearance": timeline.get("appearance"),
                "direction": direction,
                "geometry": timeline.get("geometry"),
                "traceSHA256": sha256(trace_path),
                "timelineSHA256": sha256(timeline_path),
                "recordCount": len(margins),
                "uniqueObservedMarginF32": sorted(set(margins)),
                "candidateUnroundedF64": candidate_unrounded,
                "candidateMaximumSampleIndex": maximum_index,
                "candidateMarginF32": candidate,
                "candidateMarginF32Hex": f32_hex(candidate),
                "allRecordMarginsMatchCandidate": True,
                "topologyRuns": topology_runs(depths),
                "carrierWidths": widths,
                "recursiveChildFirstF64": list(children[0]),
                "recursiveChildLastF64": list(children[-1]),
            }
        )

    depth_three_widths = [
        width for width, depth in all_preterminal_dematerialize if depth == 3
    ]
    depth_four_widths = [
        width for width, depth in all_preterminal_dematerialize if depth == 4
    ]
    lower = max(depth_four_widths)
    upper = min(depth_three_widths)
    if not lower < upper:
        raise ValueError("dematerialize topology bracket is empty")
    allocation = {
        "classification": (
            "retrospective candidate discovered after opening all fifteen datasets; "
            "not a prospective transfer gate"
        ),
        "datasetCount": len(datasets),
        "recordCount": exact_records,
        "exactMatchCount": exact_records,
        "candidateLaw": (
            "margin_f32 = float32(max over retained transition records of "
            "max(inputBleedAmount, inputShadowAmount + "
            "max(abs(inputShadowOffset.x), abs(inputShadowOffset.y))))"
        ),
        "importantTemporalSemantics": (
            "the selected allocation margin is constant across all 32 records; "
            "it is the captured-transition maximum, not each frame's current value"
        ),
        "maximumULPDistanceF32": 0,
        "maximumAbsoluteError": 0.0,
        "datasets": datasets,
        "prospectiveAuthority": False,
    }
    topology = {
        "datasetCount": len(datasets),
        "topologyRuns": [
            {"name": item["name"], "runs": item["topologyRuns"]} for item in datasets
        ],
        "materializeObservedPattern": [
            {"depth": 3, "count": 1},
            {"depth": 4, "count": 31},
        ],
        "dematerializePreterminalWidthBracketForSimpleThreshold": {
            "largestDepthFourWidth": lower,
            "smallestDepthThreeWidth": upper,
            "candidateThresholdWouldNeedToBeGreaterThan": lower,
            "candidateThresholdWouldNeedToBeLessThanOrEqualTo": upper,
        },
        "simpleWidthThresholdIsNotGeneral": True,
        "reason": (
            "materialize sample 1 has a small carrier at depth 3, and terminal "
            "dematerialize records return full carrier width while remaining at depth 4"
        ),
        "dynamicTopologyLawDecoded": False,
    }
    return allocation, topology


def analyze(
    trace_path: Path,
    timeline_path: Path,
    inventory_path: Path,
    validation_path: Path,
    corpus_root: Path,
) -> dict[str, Any]:
    for path, expected, label in (
        (trace_path, TRACE_SHA256, "trace"),
        (timeline_path, TIMELINE_SHA256, "timeline"),
        (validation_path, VALIDATION_SHA256, "CI validation"),
    ):
        if sha256(path) != expected:
            raise ValueError(f"{label} SHA-256 differs")

    trace = mapping(load_json(trace_path, "trace"), "trace")
    timeline = mapping(load_json(timeline_path, "timeline"), "timeline")
    ci_validation = mapping(
        load_json(validation_path, "CI validation"), "CI validation"
    )
    independent = validator.validate(trace_path, timeline_path, inventory_path)
    if normalized_validation(ci_validation) != normalized_validation(independent):
        raise ValueError("independent validation differs from CI validation")

    state = mapping(ci_validation.get("liveBackdropState"), "live backdrop state")
    if (
        state.get("selfMinusLayer") != 160
        or state.get("marginF32") != 83.0
        or state.get("marginRawLittleEndianHex") != "0000a642"
        or state.get("backdropRectF64") != [0.0, 0.0, 0.0, 0.0]
        or state.get("layerRectF64") != [0.0, 0.0, 127.0, 127.0]
        or state.get("selectedBaseSource") != "layer"
        or state.get("primaryRectBeforeF64") != [0.0, 0.0, 127.0, 127.0]
        or state.get("primaryRectAfterF64") != [-83.0, -83.0, 293.0, 293.0]
        or state.get("replayF64") != state.get("primaryRectAfterF64")
        or state.get("bitExact") is not True
        or state.get("inputObjectsUnchanged") is not True
    ):
        raise ValueError("selected live backdrop state differs")
    inventory = mapping(
        ci_validation.get("backdropLayerSymbolInventory"), "symbol inventory"
    )
    if (
        inventory.get("matchedNameCount") != 117
        or inventory.get("uniqueRangeCount") != 117
        or inventory.get("totalCodeByteCount") != 36312
        or inventory.get("canonicalSHA256")
        != "312130349720126c7a94164313bed05a08afbfe945c10d5b7fe97ff22d08660c"
    ):
        raise ValueError("symbol inventory summary differs")

    symbols = decode_symbols(trace)
    allocation, topology = analyze_corpus(corpus_root)
    current_records = sequence(
        mapping(
            timeline.get("dynamicBackgroundUniforms"), "current dynamic uniforms"
        ).get("records"),
        "current dynamic records",
    )
    current_required = max(
        required_margin(
            mapping(raw, "current dynamic record").get("filter", {}).get("inputValues")
        )
        for raw in current_records
    )
    if binary32(current_required) != 83.0:
        raise ValueError("current captured-transition maximum differs")

    return {
        "prepareLayerBackdropStateWriterDiscoveryAnalysisSchemaVersion": (
            ANALYSIS_SCHEMA_VERSION
        ),
        "classification": (
            "retrospective exact decode of a prospective live-state capture and "
            "class-scoped code inventory, plus retrospective allocation-corpus "
            "analysis; selected state replay is proved while upstream allocation "
            "transfer, dynamic topology, and product parity remain closed"
        ),
        "run": {
            "id": RUN_ID,
            "headSHA": HEAD_SHA,
            "artifactID": ARTIFACT_ID,
            "artifactDigest": ARTIFACT_DIGEST,
            "traceSHA256": TRACE_SHA256,
            "timelineSHA256": TIMELINE_SHA256,
            "ciValidationSHA256": VALIDATION_SHA256,
            "independentValidationSHA256": INDEPENDENT_VALIDATION_SHA256,
            "independentValidationEqualExceptCallerPaths": True,
        },
        "liveSelectedState": dict(state),
        "symbolInventory": {
            "matchedNameCount": 117,
            "uniqueRangeCount": 117,
            "totalCodeByteCount": 36312,
            "canonicalSHA256": inventory.get("canonicalSHA256"),
        },
        "writerCode": {
            "symbols": symbols,
            "propertyKey": 502,
            "propertyValueType": 18,
            "renderCopySemantics": (
                "_copyRenderLayer sends marginWidth to the CABackdropLayer, "
                "converts the returned binary64 value to binary32, and stores it "
                "at Render::BackdropLayer+0x24"
            ),
            "renderSetPropertySemantics": (
                "property key 502 loads one binary64 value, converts it to "
                "binary32, and stores it at Render::BackdropLayer+0x24"
            ),
            "copyPathSemanticsDecoded": True,
            "selectedCopyInvocationExecutionAuthenticated": False,
            "upstreamPropertyArithmeticDecodedProspectively": False,
        },
        "currentAllocationCandidateReplay": {
            "maximumRequiredMarginF64": current_required,
            "maximumRequiredMarginF32": binary32(current_required),
            "directlyCapturedMarginF32": state.get("marginF32"),
            "bitExact": True,
            "retrospective": True,
        },
        "retrospectiveAllocationCorpus": allocation,
        "dynamicTopology": topology,
        "conclusion": {
            "liveBackdropBaseAndMarginFieldsCaptured": True,
            "selectedBackdropBoundsReplayBitExact": True,
            "classScopedBackdropWriterCodeInventoryOpened": True,
            "renderMarginCopyPathSemanticsDecoded": True,
            "selectedRenderMarginWriterExecutionAuthenticated": False,
            "upstreamMarginAllocationPolicyProspectivelyPassed": False,
            "dynamicTopologyLawDecoded": False,
            "prospectiveUnseenGeometryTransferPassed": False,
            "capturedInputOpticalParityPassedAcrossDeclaredDomain": False,
            "independentPrivateInputGenerationPassed": False,
            "physicalOutputTransferPassed": False,
            "independentWalleZeroByteFrameParityPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
        "nextExactGate": {
            "capture": [
                "authenticate the selected marginWidth copy/setter invocation and caller",
                "freeze the retrospective transition-maximum margin candidate before unseen profiles",
                "densely bracket and instruction-decode the direction-dependent recursion-topology switch",
            ],
            "acceptance": [
                "every unseen allocation margin matches at zero ULP",
                "every unseen recursion depth and recursive child matches exactly",
                "no captured target value participates in selection or prediction",
            ],
            "requiresNewAppleCapture": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("validation", type=Path)
    parser.add_argument("corpus_root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = analyze(
        arguments.trace,
        arguments.timeline,
        arguments.inventory,
        arguments.validation,
        arguments.corpus_root,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
