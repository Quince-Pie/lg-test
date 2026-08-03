#!/usr/bin/env python3
"""Open the passing upstream-object capture from run 30773890196."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_dynamic_allocation_surviving_path_threshold as surviving


EXPECTED_RUN_ID = 30_773_890_196
EXPECTED_HEAD_SHA = "c90825a4c2302ca9af98749c3a9ffc24342edeac"
EXPECTED_TIMELINE_SHA256 = (
    "d9001c6b9b99988a5932755e40a2ca30e4cf089e9a204994a9d399d05963df82"
)
EXPECTED_CAPTURE_BACKDROP_SHA256 = (
    "14f25960556bec9e88ba8ade176ee7f1d39b84726226ade3eb1b0f1be00b70d2"
)
EXPECTED_RECORD_COUNT = 114
EXPECTED_REQUIRED_READ_MASK = 0x3FFF_FFFF
EXPECTED_DIRECT_CALLS = {
    0x0100: {
        "instruction": "94001021",
        "imageOffset": "0xa939c",
        "symbol": "_ZN2CA6Render13BackdropGroup10layer_itemEPNS0_13BackdropStateEj",
        "codeSHA256": (
            "cd11ac525009b9695b6193c363a4dabf8f9407934f33329a6b937a0b40790934"
        ),
    },
    0x0BDC: {
        "instruction": "9409b094",
        "imageOffset": "0x312044",
        "symbol": (
            "_ZN2CA3OGL12_GLOBAL__N_116collect_surfacesEPNS0_7SurfaceEPS3_"
            "PNS_6BoundsEbRb"
        ),
        "codeSHA256": (
            "4b2b191d2626a787cbc695b88321819cf7b4ed4ef4f8ab134e90554dd6a264fd"
        ),
    },
    0x0C74: {
        "instruction": "9409b0be",
        "imageOffset": "0x312184",
        "symbol": (
            "_ZN2CA3OGL12_GLOBAL__N_128desired_src_edge_replicationEPKNS_"
            "6Render13BackdropGroupEPKNS0_5LayerERNS0_7ContextEPNS_4RectE"
            "PNS_4Vec2IfEEPbSG_SG_SG_"
        ),
        "codeSHA256": (
            "192a97ee95eb6d82a5f67cc2cd21439fc838ef989fdb2f6f32d0dca3dd8b2be9"
        ),
    },
    0x17F8: {
        "instruction": "97feb156",
        "imageOffset": "0x52f68",
        "symbol": "_ZN2CA6Bounds12set_exteriorERKNS_4RectE",
        "codeSHA256": (
            "dcd3839424f0d2dfef75e2d6a805744af7f73fbfaaab59529433eaea3c001468"
        ),
    },
    0x1804: {
        "instruction": "97ffa31b",
        "imageOffset": "0x8f688",
        "symbol": "_ZNK2CA5Shape9intersectERKNS_6BoundsE",
        "codeSHA256": (
            "4c67a83ab7e9cac50ab6a3823f99678c2a36ee5d44af02be56f83f594f726f46"
        ),
    },
    0x1830: {
        "instruction": "9408bc71",
        "imageOffset": "0x2d5c0c",
        "symbol": "_ZN2CA11shape_scaleEPPNS_5ShapeEii",
        "codeSHA256": (
            "2452f1b2740fd32d4f8e1a741bc54a7db54f4143dbf4ec9a0dd178996fc65e92"
        ),
    },
    0x183C: {
        "instruction": "9408bbd1",
        "imageOffset": "0x2d5998",
        "symbol": "_ZNK2CA5Shape9translateEii",
        "codeSHA256": (
            "cdd6f255674004721e41e6541d5b03b66b11b396e6b2f32c358db8d2a3c9bd4c"
        ),
    },
}
EXPECTED_FIRST_WORD_SYMBOLS = {
    "source": "_ZTVN2CA6Render13BackdropStateE",
    "owner": "_ZTVN2CA6Render13BackdropGroupE",
    "renderContext": "_ZTVN2CA3OGL12MetalContextE",
    "layerAuxiliary": "_ZTVN2CA6Render5LayerE",
}
EXPECTED_CAPTURE_BACKDROP_WORDS = {
    0x0140: 0xF941_3A80,  # ldr x0, [x20, #0x270]
    0x014C: 0xF901_3A9F,  # str xzr, [x20, #0x270]
    0x01C8: 0xF941_3A80,
    0x01D4: 0xF901_3A9F,
    0x17A4: 0x5280_4E08,  # mov w8, #0x270
    0x17A8: 0x5280_4909,  # mov w9, #0x248
    0x17AC: 0x9A88_1128,  # csel x8, x9, x8, ne
    0x17BC: 0xF868_6A80,  # ldr x0, [x20, x8]
    0x17C0: 0xF901_53E0,  # str x0, [sp, #0x2a0]
    0x3B80: 0xF941_3A80,
    0x3B8C: 0xF901_3A9F,
}
EXPECTED_EDGE_REPLICATION_WORDS = {
    0x0050: 0xF941_4C09,  # ldr x9, [x0, #0x298]
    0x0080: 0xA945_2009,  # ldp x9, x8, [x0, #0x50]
    0x0088: 0xF103_411F,  # cmp x8, #0xd0
    0x0090: 0xF940_46A8,  # ldr x8, [x21, #0x88]
    0x0098: 0xF940_3109,  # ldr x9, [x8, #0x60]
    0x01E4: 0x3900_02E0,  # strb w0, [x23]
    0x0204: 0x3900_02C8,  # strb w8, [x22]
    0x029C: 0xFD00_0260,  # str d0, [x19]
    0x02D4: 0xD65F_0FFF,  # retab
}
CLASSIFICATION = (
    "post-opening-analysis-of-prospectively-passing-upstream-object-capture;"
    " private-field-map-and-writer-exclusion-not-a-public-crop-policy-unseen-"
    "transfer-or-product-parity-claim"
)


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} differs")
    return value


def sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{label} differs")
    return value


def record_operand_payload(record: Mapping[str, Any]) -> Mapping[str, Any]:
    render = mapping(record.get("render"), "path-isolation render")
    retained = mapping(render.get("metalBufferSnapshots"), "retained Metal buffers")
    payloads = [
        mapping(snapshot, "retained snapshot")["captureBackdropOperands"]
        for snapshot in sequence(retained.get("snapshots"), "retained snapshots")
        if "captureBackdropOperands" in mapping(snapshot, "retained snapshot")
    ]
    if len(payloads) != 1:
        raise ValueError("upstream-writer operand inventory differs")
    return mapping(payloads[0], "upstream-writer operands")


def capture_backdrop_frame(record: Mapping[str, Any]) -> Mapping[str, Any]:
    render = mapping(record.get("render"), "code render")
    retained = mapping(render.get("metalBufferSnapshots"), "code buffers")
    call_sites = [
        mapping(snapshot, "code snapshot")["producerGeometryCallSite"]
        for snapshot in sequence(retained.get("snapshots"), "code snapshots")
        if "producerGeometryCallSite" in mapping(snapshot, "code snapshot")
    ]
    if len(call_sites) != 1:
        raise ValueError("producer call-site inventory differs")
    frames = sequence(
        mapping(call_sites[0], "producer call site").get("frames"),
        "producer call-site frames",
    )
    matching = [
        mapping(frame, "producer frame")
        for frame in frames
        if mapping(frame, "producer frame").get("symbol")
        == surviving.CAPTURE_BACKDROP_SYMBOL
    ]
    if len(matching) != 1:
        raise ValueError("capture_backdrop frame inventory differs")
    return matching[0]


def code_bytes(value: Any, label: str, expected_sha256: str) -> bytes:
    code = mapping(value, label)
    raw = surviving.hexadecimal_bytes(code, label)
    if (
        code.get("lengthBytes") != len(raw)
        or code.get("sha256") != expected_sha256
        or hashlib.sha256(raw).hexdigest() != expected_sha256
    ):
        raise ValueError(f"{label} differs")
    return raw


def opened_code(record: Mapping[str, Any]) -> tuple[bytes, dict[int, bytes]]:
    frame = capture_backdrop_frame(record)
    capture = mapping(frame.get("captureBackdropCode"), "capture_backdrop code")
    body = code_bytes(
        capture,
        "capture_backdrop code",
        EXPECTED_CAPTURE_BACKDROP_SHA256,
    )
    if len(body) != 0x4000:
        raise ValueError("capture_backdrop byte count differs")
    calls = sequence(capture.get("upstreamDirectCalls"), "upstream direct calls")
    if len(calls) != len(EXPECTED_DIRECT_CALLS):
        raise ValueError("upstream direct-call count differs")
    targets: dict[int, bytes] = {}
    for raw_call in calls:
        call = mapping(raw_call, "upstream direct call")
        offset = call.get("sourceInstructionOffset")
        if not isinstance(offset, int) or offset not in EXPECTED_DIRECT_CALLS:
            raise ValueError("upstream direct-call offset differs")
        expected = EXPECTED_DIRECT_CALLS[offset]
        target = code_bytes(
            call.get("targetCode"),
            f"upstream target at {offset:#x}",
            str(expected["codeSHA256"]),
        )
        if (
            len(target) != 0x1000
            or call.get("sourceInstruction") != expected["instruction"]
            or call.get("targetImageOffset") != expected["imageOffset"]
            or call.get("targetSymbol") != expected["symbol"]
            or call.get("targetSymbolOffset") != "0x0"
        ):
            raise ValueError(f"upstream target metadata at {offset:#x} differs")
        targets[offset] = target
    return body, targets


def unpack_rect_i32(prefix: bytes, offset: int) -> tuple[int, int, int, int]:
    return struct.unpack_from("<4i", prefix, offset)


def unpack_rect_f64(prefix: bytes, offset: int) -> tuple[float, float, float, float]:
    return struct.unpack_from("<4d", prefix, offset)


def analyze(timeline_path: Path, *, run_id: int, head_sha: str) -> dict[str, Any]:
    if run_id != EXPECTED_RUN_ID or head_sha != EXPECTED_HEAD_SHA:
        raise ValueError("upstream-writer run identity differs")
    timeline_sha = surviving.holdout.sha256_file(timeline_path)
    if timeline_sha != EXPECTED_TIMELINE_SHA256:
        raise ValueError("upstream-writer timeline digest differs")

    validated = surviving.validate(timeline_path)
    aggregate = mapping(validated.get("aggregate"), "validated aggregate")
    upstream = mapping(
        aggregate.get("captureBackdropUpstreamWriterReplay"),
        "upstream-writer replay",
    )
    owner_record = mapping(
        aggregate.get("captureBackdropOwnerRecordReplay"), "owner-record replay"
    )
    owner_region = mapping(
        aggregate.get("captureBackdropOwnerRegionReplay"), "owner-region replay"
    )
    operands = mapping(aggregate.get("captureBackdropOperandReplay"), "operand replay")
    consumed = mapping(
        aggregate.get("captureBackdropConsumedRegionReplay"), "consumed replay"
    )
    q_replay = mapping(
        aggregate.get("primaryProducerSourceQ"), "primary source-q replay"
    )
    allocation = mapping(aggregate.get("allocationInvariants"), "allocation replay")
    if (
        upstream.get("captureCount") != EXPECTED_RECORD_COUNT
        or upstream.get("expectedCaptureCount") != EXPECTED_RECORD_COUNT
        or upstream.get("objectChainExact") is not True
        or upstream.get("distinctSourceObjectPrefixCount") != 114
        or upstream.get("distinctLayerObjectPrefixCount") != 14
        or upstream.get("distinctLayerStatePrefixCount") != 110
        or upstream.get("distinctLayerAuxiliaryPrefixCount") != 114
        or upstream.get("distinctLayerAuxiliaryNestedPrefixCount") != 1
        or upstream.get("distinctRenderContextPrefixCount") != 114
        or upstream.get("distinctRegionBuilderOutputCount") != 1
        or owner_record.get("ownerRecordCountStates") != {"1": 114}
        or owner_record.get("sourceRecordMatchCountStates") != {"1": 114}
        or owner_region.get("selectedEqualsOwner248Count") != 114
        or owner_region.get("selectedEqualsOwner270Count") != 111
        or operands.get("primaryPositionMismatchedComponents") != 0
        or operands.get("primarySourceMismatchedComponents") != 0
        or consumed.get("consumedRegionRectExact") is not True
        or q_replay
        != {
            "componentCount": 912,
            "exact": True,
            "mismatchedComponents": 0,
        }
        or allocation
        != {"componentCount": 1596, "exact": True, "mismatchedComponents": 0}
    ):
        raise ValueError("prospective upstream-writer gate differs")

    with timeline_path.open(encoding="utf-8") as stream:
        report = json.load(stream)
    uniforms = mapping(report.get("dynamicBackgroundUniforms"), "uniform evidence")
    evidence = mapping(
        uniforms.get("pathIsolationInterventions"), "path-isolation evidence"
    )
    raw_records = [
        mapping(value, "path-isolation record")
        for value in sequence(evidence.get("records"), "path-isolation records")
    ]
    if evidence.get("schemaVersion") != 9 or len(raw_records) != EXPECTED_RECORD_COUNT:
        raise ValueError("upstream-writer record inventory differs")
    body, targets = opened_code(raw_records[0])

    rect_frequency: Counter[tuple[int, ...]] = Counter()
    input_frequency: Counter[tuple[int, ...]] = Counter()
    input_to_outputs: defaultdict[tuple[int, ...], set[tuple[int, ...]]] = defaultdict(
        set
    )
    source_addresses: set[int] = set()
    owner_addresses: set[int] = set()
    layer_addresses: set[int] = set()
    context_addresses: set[int] = set()
    layer_state_addresses: set[int] = set()
    nested_addresses: set[int] = set()
    exact_field_count = 0
    symbol_counts: Counter[tuple[str, str]] = Counter()
    region_builder_hashes: set[str] = set()
    nested_hashes: set[str] = set()

    for record_index, raw_record in enumerate(raw_records):
        if raw_record.get("recordIndex") != record_index:
            raise ValueError("upstream-writer record order differs")
        payload = record_operand_payload(raw_record)
        decoded = surviving.validate_capture_backdrop_operands(payload)
        if (
            payload.get("schemaVersion") != 5
            or payload.get("completeRead") is not True
            or int(str(payload.get("readMask")), 16) != EXPECTED_REQUIRED_READ_MASK
            or int(str(payload.get("requiredReadMask")), 16)
            != EXPECTED_REQUIRED_READ_MASK
        ):
            raise ValueError("upstream-writer live operand mask differs")

        pointers = mapping(payload.get("upstreamObjectPointers"), "object pointers")
        source_addresses.add(
            surviving.hexadecimal_address(pointers.get("source"), "source pointer")
        )
        owner_addresses.add(
            surviving.hexadecimal_address(pointers.get("owner"), "owner pointer")
        )
        layer_addresses.add(
            surviving.hexadecimal_address(pointers.get("layer"), "layer pointer")
        )
        context_addresses.add(
            surviving.hexadecimal_address(
                pointers.get("renderContext"), "render-context pointer"
            )
        )
        layer_state_addresses.add(
            surviving.hexadecimal_address(
                pointers.get("layerState"), "layer-state pointer"
            )
        )
        nested_pointer = surviving.hexadecimal_address(
            pointers.get("layerAuxiliaryNested"), "nested pointer"
        )
        nested_addresses.add(nested_pointer)

        source_prefix = surviving.capture_backdrop_operand_bytes(
            payload, "sourceObjectPrefix"
        )
        owner_prefix = surviving.capture_backdrop_operand_bytes(
            payload, "ownerObjectPrefix"
        )
        layer_state_prefix = surviving.capture_backdrop_operand_bytes(
            payload, "layerStatePrefix"
        )
        record_vector = surviving.capture_backdrop_owner_record_vector_bytes(payload)
        nested_prefix = surviving.capture_backdrop_optional_prefix_bytes(
            payload,
            field="layerAuxiliaryNestedPrefix",
            class_name="bounded nested layer-auxiliary prefix bytes",
            pointer=nested_pointer,
            pointer_byte_count=0x60,
        )
        region_builder = surviving.capture_backdrop_operand_bytes(
            payload, "regionBuilderOutput"
        )
        selected = tuple(int(value) for value in decoded["selectedRegionRect"])
        input_bounds = unpack_rect_i32(layer_state_prefix, 0xA0)
        source_rect = unpack_rect_i32(source_prefix, 0x50)
        state_rect = unpack_rect_i32(layer_state_prefix, 0xB0)
        owner_rect = unpack_rect_f64(owner_prefix, 0xE0)
        record_rect = unpack_rect_f64(record_vector, 0x70)
        if (
            source_rect != selected
            or state_rect != selected
            or owner_rect != tuple(float(value) for value in selected)
            or record_rect != tuple(float(value) for value in selected)
        ):
            raise ValueError("cross-object selected rectangle differs")
        exact_field_count += 1
        rect_frequency[selected] += 1
        input_frequency[input_bounds] += 1
        input_to_outputs[input_bounds].add(selected)
        nested_hashes.add(hashlib.sha256(nested_prefix).hexdigest())
        region_builder_hashes.add(hashlib.sha256(region_builder).hexdigest())

        symbols = mapping(
            payload.get("upstreamObjectFirstWordSymbols"), "first-word symbols"
        )
        for name, expected_symbol in EXPECTED_FIRST_WORD_SYMBOLS.items():
            item = mapping(symbols.get(name), f"{name} first-word symbol")
            if (
                item.get("resolved") is not True
                or item.get("symbol") != expected_symbol
                or item.get("symbolOffset") != "0x10"
            ):
                raise ValueError(f"{name} first-word symbol differs")
            symbol_counts[(name, expected_symbol)] += 1
        for name in {"layer", "layerState", "layerAuxiliaryNested"}:
            if mapping(symbols.get(name), f"{name} first word").get("resolved"):
                raise ValueError(f"{name} unexpectedly acquired a symbol")

    if (
        exact_field_count != EXPECTED_RECORD_COUNT
        or len(source_addresses) != 1
        or len(owner_addresses) != 1
        or len(layer_addresses) != 1
        or len(context_addresses) != 1
        or len(layer_state_addresses) != 14
        or len(nested_addresses) != 73
        or len(rect_frequency) != 9
        or len(input_frequency) != 83
        or len(nested_hashes) != 1
        or len(region_builder_hashes) != 1
        or any(count != EXPECTED_RECORD_COUNT for count in symbol_counts.values())
    ):
        raise ValueError("opened upstream-object inventory differs")

    observed_capture_words = {
        offset: int.from_bytes(body[offset : offset + 4], "little")
        for offset in EXPECTED_CAPTURE_BACKDROP_WORDS
    }
    edge_code = targets[0x0C74]
    observed_edge_words = {
        offset: int.from_bytes(edge_code[offset : offset + 4], "little")
        for offset in EXPECTED_EDGE_REPLICATION_WORDS
    }
    if (
        observed_capture_words != EXPECTED_CAPTURE_BACKDROP_WORDS
        or observed_edge_words != EXPECTED_EDGE_REPLICATION_WORDS
    ):
        raise ValueError("opened upstream instruction words differ")

    ambiguous_input_count = sum(
        len(outputs) > 1 for outputs in input_to_outputs.values()
    )
    return {
        "dynamicAllocationCaptureBackdropUpstreamWriterAnalysisSchemaVersion": 1,
        "classification": CLASSIFICATION,
        "runID": run_id,
        "headSHA": head_sha,
        "workflowConclusion": "success",
        "prospectiveGatePassed": True,
        "inputTimelineArtifact": timeline_path.parent.name + "/" + timeline_path.name,
        "inputTimelineSHA256": timeline_sha,
        "aggregate": {
            "recordCount": EXPECTED_RECORD_COUNT,
            "completeLiveOperandCaptureCount": EXPECTED_RECORD_COUNT,
            "completeReadMask": f"0x{EXPECTED_REQUIRED_READ_MASK:08x}",
            "primaryPositionReplay": {
                "componentCount": operands["primaryPositionComponentCount"],
                "mismatchedComponents": 0,
                "allowNumericTolerance": False,
            },
            "primarySourceReplay": {
                "componentCount": operands["primarySourceComponentCount"],
                "mismatchedComponents": 0,
                "allowNumericTolerance": False,
            },
            "primarySourceQ": dict(q_replay),
            "allocationInvariants": dict(allocation),
            "selectedRegionConsumedRectangleExactCount": consumed["captureCount"],
            "selectedEqualsOwner248Count": 114,
            "selectedEqualsOwner270Count": 111,
        },
        "openedObjectChain": {
            "sourceClass": "CA::Render::BackdropState",
            "ownerClass": "CA::Render::BackdropGroup",
            "renderContextClass": "CA::OGL::MetalContext",
            "layerAuxiliaryClass": "CA::Render::Layer",
            "distinctSourceAddressCount": len(source_addresses),
            "distinctOwnerAddressCount": len(owner_addresses),
            "distinctLayerAddressCount": len(layer_addresses),
            "distinctRenderContextAddressCount": len(context_addresses),
            "distinctLayerStateAddressCount": len(layer_state_addresses),
            "distinctNestedAuxiliaryAddressCount": len(nested_addresses),
            "firstWordSymbolExactCountPerResolvedClass": EXPECTED_RECORD_COUNT,
        },
        "openedPrivateRectangleIdentity": {
            "encodingMap": [
                {
                    "object": "CA::Render::BackdropState",
                    "offset": 0x50,
                    "encoding": "four little-endian signed int32 words",
                },
                {
                    "object": "layer state",
                    "offset": 0xB0,
                    "encoding": "four little-endian signed int32 words",
                },
                {
                    "object": "CA::Render::BackdropGroup",
                    "offset": 0xE0,
                    "encoding": "four little-endian binary64 words",
                },
                {
                    "object": "single owner record",
                    "offset": 0x70,
                    "encoding": "four little-endian binary64 words",
                },
                {
                    "object": "CA::Render::BackdropGroup",
                    "offset": 0x248,
                    "encoding": "packed Shape handle consumed as the same rectangle",
                },
            ],
            "exactCrossObjectCount": exact_field_count,
            "distinctSelectedRectangleCount": len(rect_frequency),
            "selectedRectangleFrequency": [
                {"rect": list(rect), "count": count}
                for rect, count in sorted(rect_frequency.items())
            ],
            "layerStateInputBoundsOffset": 0xA0,
            "distinctLayerStateInputBoundsCount": len(input_frequency),
            "inputBoundsWithMultipleObservedOutputsCount": ambiguous_input_count,
            "publicConstructionRuleRecovered": False,
        },
        "openedTargetCode": {
            "captureBackdropSymbolPrefixSHA256": EXPECTED_CAPTURE_BACKDROP_SHA256,
            "captureBackdropRetainedByteCount": len(body),
            "captureBackdropCompleteFunctionSizeKnown": False,
            "directCalls": [
                {
                    "sourceInstructionOffset": offset,
                    "targetImageOffset": expected["imageOffset"],
                    "targetSymbol": expected["symbol"],
                    "targetCodeByteCount": len(targets[offset]),
                    "targetCodeSHA256": expected["codeSHA256"],
                }
                for offset, expected in sorted(EXPECTED_DIRECT_CALLS.items())
            ],
            "captureBackdropByteGatedWords": [
                {"offset": offset, "word": f"0x{word:08x}"}
                for offset, word in sorted(observed_capture_words.items())
            ],
            "desiredSourceEdgeReplication": {
                "targetImageOffset": "0x312184",
                "functionBodyEndOffset": 0x2D4,
                "byteGatedWords": [
                    {"offset": offset, "word": f"0x{word:08x}"}
                    for offset, word in sorted(observed_edge_words.items())
                ],
                "role": (
                    "scans owner surfaces and the one-record vector, dispatches "
                    "surface virtual methods, and writes edge-replication outputs"
                ),
                "constructsOwnerRegion": False,
                "nestedAuxiliaryReadOffset": 0x60,
                "capturedNestedAuxiliaryByteCount": 0x60,
                "nestedReadCoveredByCapture": False,
            },
            "lateRegionSelection": {
                "instructionRange": [0x17A4, 0x17C4],
                "candidateOwnerOffsets": [0x248, 0x270],
                "operation": "select and load an already-constructed Shape handle",
                "constructsSelectedRegion": False,
            },
            "owner270DirectClearPaths": [
                [0x140, 0x14C],
                [0x1C8, 0x1D4],
                [0x3B80, 0x3B8C],
            ],
        },
        "conclusion": {
            "frozenUpstreamObjectGatePassed": True,
            "privateSelectedRectangleMappedAcrossFiveLocations": True,
            "desiredSourceEdgeReplicationIsRegionWriter": False,
            "lateCaptureBackdropPathConsumesPrebuiltRegion": True,
            "layerStateA0ToB0ConstructionRuleRecovered": False,
            "requiresEarlierWriterTrace": True,
            "requiresUnseenGeometryTransfer": True,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = analyze(
        arguments.timeline,
        run_id=arguments.run_id,
        head_sha=arguments.head_sha,
    )
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        arguments.output.write_text(encoded, encoding="utf-8")
        print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
