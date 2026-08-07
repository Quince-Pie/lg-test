#!/usr/bin/env python3
"""Prove the native Parameters.AnimatableData-to-Parameters field map."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import struct
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Optional

import analyze_designlibrary_background_filter_metadata_local_macos_26_6_1 as metadata
import analyze_designlibrary_resolved_recipe_provenance_local_macos_26_6_1 as provenance


RESULT_SCHEMA_VERSION = 1
SOURCE_RELATIVE_PATH = (
    "Analysis/"
    "analyze_designlibrary_parameters_animatable_resolver_local_macos_26_6_1.py"
)
METADATA_ANALYZER_SHA256 = provenance.METADATA_ANALYZER_SHA256
PROVENANCE_ANALYZER_SHA256 = (
    "7492526b9ce67f21eee811a5a7d0f5effc1348be97f3aa4c2429d13e7c497145"
)
EXPECTED_HARDWARE_MODEL = provenance.EXPECTED_HARDWARE_MODEL
PARAMETERS_BYTE_COUNT = 0x401
ANIMATABLE_DATA_BYTE_COUNT = 0x481
ANIMATABLE_DATA_DESCRIPTOR = 0x2409D249C
PARAMETERS_DESCRIPTOR = 0x2409D2878

CODE_REGIONS = {
    "parametersResolver": (
        0x2409323F4,
        0x240932888,
        "99b1fedd3f82ad68d73f6c3a94608544fa82625aa56237fac9b8316d1c7e92a0",
    ),
    "shadowResolver": (
        0x240932888,
        0x240932A70,
        "3a591e8062a9e9fee12ebe8a7ebbe69dabb9d4fe0afc95bf5a9cbc1db9f7d51a",
    ),
    "blurResolver": (
        0x240932A70,
        0x240932B20,
        "d2002d25e2a2987a38c820a64795da6949eb96aea87b4cdce951e59865f72349",
    ),
    "refractionResolver": (
        0x240932B20,
        0x240932BB8,
        "ca6e38a9865c83e7ad19c8a6c5c1fdfdd5264f7d2ad6ca13d2fbb93a9f88d3d2",
    ),
    "faceEffectsResolver": (
        0x240932BB8,
        0x240932CC8,
        "687495cda220ce0aa829e7add2a6a591dd5c187a986b12973c10d8a6d1dcc508",
    ),
    "edgeBleedResolver": (
        0x240932CC8,
        0x240932E3C,
        "9460cf85a263ea3cc080bad02ad46299a994755118963146ff424a0bb8ca40ad",
    ),
    "highlightsResolver": (
        0x240932E3C,
        0x240933134,
        "47e4235ea19b5b52304be74f933d17cf25978c40c7611e8c27b156b629ef226f",
    ),
    "lensingResolver": (
        0x240933134,
        0x2409331F0,
        "2a40b9b3a25e9af97fb78e39923221a868600a90454cee49c20600031ea71c40",
    ),
}

EXPECTED_DIRECT_CALLS = {
    "parametersResolver": (0x2409332E4, 0x240982CD4),
    "shadowResolver": (0x240932454,),
    "blurResolver": (0x240932478,),
    "refractionResolver": (0x24093249C,),
    "faceEffectsResolver": (0x2409324C8,),
    "edgeBleedResolver": (0x2409324FC,),
    "highlightsResolver": (0x240932588,),
    "lensingResolver": (0x240932648,),
}

ANIMATABLE_DATA_FIELDS = (
    ("backdropScale", "Sf"),
    ("contentOpacity", "Sf"),
    (
        "shadow",
        "_____Sg 13DesignLibrary21GlassMaterialProviderV10ParametersV6ShadowV14AnimatableDataV",
    ),
    (
        "blur",
        "_____Sg 13DesignLibrary21GlassMaterialProviderV10ParametersV4BlurV14AnimatableDataV",
    ),
    (
        "refraction",
        "_____Sg 13DesignLibrary21GlassMaterialProviderV10ParametersV10RefractionV14AnimatableDataV",
    ),
    (
        "faceEffects",
        "_____Sg 13DesignLibrary21GlassMaterialProviderV10ParametersV11FaceEffectsV14AnimatableDataV",
    ),
    (
        "edgeBleed",
        "_____Sg 13DesignLibrary21GlassMaterialProviderV10ParametersV9EdgeBleedV14AnimatableDataV",
    ),
    (
        "tinting",
        "_____Sg 13DesignLibrary21GlassMaterialProviderV10ParametersV7TintingV14AnimatableDataV",
    ),
    (
        "highlights",
        "_____Sg 13DesignLibrary21GlassMaterialProviderV10ParametersV10HighlightsV14AnimatableDataV",
    ),
    (
        "sdrAdjustment",
        "_____Sg 13DesignLibrary21GlassMaterialProviderV10ParametersV13SDRAdjustmentV14AnimatableDataV",
    ),
    (
        "lensing",
        "_____Sg 13DesignLibrary21GlassMaterialProviderV10ParametersV7LensingV14AnimatableDataV",
    ),
    (
        "controlContentLensing",
        "_____Sg 13DesignLibrary21GlassMaterialProviderV10ParametersV12DisplacementV14AnimatableDataV",
    ),
    (
        "controlDisplacement",
        "_____Sg 13DesignLibrary21GlassMaterialProviderV10ParametersV12DisplacementV14AnimatableDataV",
    ),
    (
        "contrastEdge",
        "_____Sg 13DesignLibrary21GlassMaterialProviderV10ParametersV12ContrastEdgeV14AnimatableDataV",
    ),
    (
        "innerGlow",
        "_____Sg 13DesignLibrary21GlassMaterialProviderV10ParametersV9InnerGlowV14AnimatableDataV",
    ),
    (
        "radiosity",
        "_____Sg 13DesignLibrary21GlassMaterialProviderV10ParametersV9RadiosityV14AnimatableDataV",
    ),
)
ANIMATABLE_DATA_OFFSETS = (
    0,
    4,
    16,
    160,
    240,
    304,
    400,
    528,
    560,
    832,
    880,
    960,
    1008,
    1056,
    1088,
    1120,
)
PARAMETERS_FIELDS = (
    "backdropScale",
    "updateRate",
    "contentOpacity",
    "_shadow",
    "_blur",
    "_refraction",
    "_faceEffects",
    "_edgeBleed",
    "_tinting",
    "_highlights",
    "_sdrAdjustment",
    "_lensing",
    "_controlContentLensing",
    "_controlDisplacement",
    "_contrastEdge",
    "_innerGlow",
    "_radiosity",
)
PARAMETERS_OFFSETS = (
    0,
    8,
    16,
    24,
    176,
    256,
    312,
    392,
    500,
    520,
    784,
    824,
    880,
    912,
    944,
    968,
    992,
)

HELPER_OUTPUT_RANGES = {
    "shadowResolver": ((0, 145),),
    "blurResolver": ((0, 73),),
    "refractionResolver": ((0, 53),),
    "faceEffectsResolver": ((0, 74),),
    "edgeBleedResolver": ((0, 106),),
    "highlightsResolver": ((0, 257),),
    "lensingResolver": ((0, 49),),
}

HELPER_CALL_WRITES = {
    0x240932454: "shadowResolver",
    0x240932478: "blurResolver",
    0x24093249C: "refractionResolver",
    0x2409324C8: "faceEffectsResolver",
    0x2409324FC: "edgeBleedResolver",
    0x240932588: "highlightsResolver",
    0x240932648: "lensingResolver",
}

EXPECTED_PARAMETER_WRITE_RANGES = (
    (0, 4),
    (16, 20),
    (24, 169),
    (176, 249),
    (256, 309),
    (312, 386),
    (392, 498),
    (500, 517),
    (520, 777),
    (784, 817),
    (824, 873),
    (880, 905),
    (912, 937),
    (944, 961),
    (968, 985),
    (992, 1025),
)

FIELD_MAP = (
    ("backdropScale", 0, 4, 0, 8, 0, 4, "direct", "0x24093241c"),
    ("updateRate", None, None, 8, 16, None, None, "seed-preserved", None),
    ("contentOpacity", 4, 16, 16, 24, 16, 20, "direct", "0x240932420"),
    ("shadow", 16, 160, 24, 176, 24, 169, "helper", "0x240932454"),
    ("blur", 160, 240, 176, 256, 176, 249, "helper", "0x240932478"),
    ("refraction", 240, 304, 256, 312, 256, 309, "helper", "0x24093249c"),
    ("faceEffects", 304, 400, 312, 392, 312, 386, "helper", "0x2409324c8"),
    ("edgeBleed", 400, 528, 392, 500, 392, 498, "helper", "0x2409324fc"),
    ("tinting", 528, 560, 500, 520, 500, 517, "inline", "0x240932568"),
    ("highlights", 560, 832, 520, 784, 520, 777, "helper", "0x240932588"),
    ("sdrAdjustment", 832, 880, 784, 824, 784, 817, "inline", "0x240932618"),
    ("lensing", 880, 960, 824, 880, 824, 873, "helper", "0x240932648"),
    (
        "controlContentLensing",
        960,
        1008,
        880,
        912,
        880,
        905,
        "inline",
        "0x2409326b0",
    ),
    (
        "controlDisplacement",
        1008,
        1056,
        912,
        944,
        912,
        937,
        "inline",
        "0x240932720",
    ),
    ("contrastEdge", 1056, 1088, 944, 968, 944, 961, "inline", "0x240932794"),
    ("innerGlow", 1088, 1120, 968, 992, 968, 985, "inline", "0x240932800"),
    ("radiosity", 1120, 1153, 992, 1025, 992, 1025, "inline", "0x24093286c"),
)

CRITICAL_INSTRUCTIONS = {
    0x24093240C: ("mov", "x19, x0"),
    0x240932414: ("ldp", "s0, s1, [x0]"),
    0x240932418: ("add", "x21, x20, #0x1f4"),
    0x24093241C: ("str", "s0, [x20]"),
    0x240932420: ("str", "s1, [x20, #0x10]"),
    0x24093244C: ("add", "x8, x20, #0x18"),
    0x240932454: ("bl", "0x240932888"),
    0x240932470: ("add", "x8, x20, #0xb0"),
    0x240932478: ("bl", "0x240932a70"),
    0x240932494: ("add", "x8, x20, #0x100"),
    0x24093249C: ("bl", "0x240932b20"),
    0x2409324C0: ("add", "x8, x20, #0x138"),
    0x2409324C8: ("bl", "0x240932bb8"),
    0x2409324F4: ("add", "x8, x20, #0x188"),
    0x2409324FC: ("bl", "0x240932cc8"),
    0x240932568: ("stp", "x8, x10, [x21]"),
    0x24093256C: ("strb", "w9, [x20, #0x204]"),
    0x240932580: ("add", "x8, x20, #0x208"),
    0x240932588: ("bl", "0x240932e3c"),
    0x240932618: ("str", "x9, [x20, #0x310]"),
    0x240932624: ("strb", "w8, [x20, #0x330]"),
    0x240932640: ("add", "x8, x20, #0x338"),
    0x240932648: ("bl", "0x240933134"),
    0x2409326B0: ("str", "q1, [x20, #0x370]"),
    0x2409326B8: ("strb", "w8, [x20, #0x388]"),
    0x240932720: ("str", "q0, [x20, #0x390]"),
    0x240932728: ("strb", "w8, [x20, #0x3a8]"),
    0x240932794: ("str", "x9, [x20, #0x3b0]"),
    0x24093279C: ("strb", "w8, [x20, #0x3c0]"),
    0x240932800: ("str", "x9, [x20, #0x3c8]"),
    0x240932808: ("strb", "w8, [x20, #0x3d8]"),
    0x24093286C: ("stp", "q0, q1, [x20, #0x3e0]"),
    0x240932870: ("strb", "w8, [x20, #0x400]"),
    0x240933110: ("mov", "x0, x19"),
    0x240933114: ("mov", "w2, #0x101"),
    0x2409332C4: ("ldr", "x20, [x19, #0xd18]"),
    0x2409332E0: ("mov", "x0, x21"),
    0x2409332E4: ("bl", "0x2409323f4"),
    0x240982CC8: ("add", "x0, x19, #0x1, lsl #12"),
    0x240982CCC: ("add", "x0, x0, #0x900"),
    0x240982CD0: ("add", "x20, x19, #0xc60"),
    0x240982CD4: ("bl", "0x2409323f4"),
}


class AnalysisError(RuntimeError):
    """Raised when the native resolver differs from the frozen contract."""


def command_output(arguments: Sequence[str]) -> str:
    completed = subprocess.run(
        list(arguments),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise AnalysisError("command failed: " + " ".join(arguments))
    return completed.stdout.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def direct_calls(text: metadata.Section) -> Mapping[str, tuple[int, ...]]:
    targets = {start: name for name, (start, _, _) in CODE_REGIONS.items()}
    result: dict[str, list[int]] = {name: [] for name in CODE_REGIONS}
    for address in range(text.start, text.end - 3, 4):
        instruction = struct.unpack("<I", metadata.read_bytes(text.memory, address, 4))[
            0
        ]
        if instruction & 0xFC000000 != 0x94000000:
            continue
        destination = address + provenance.sign_extend(instruction & 0x03FFFFFF, 26) * 4
        name = targets.get(destination)
        if name is not None:
            result[name].append(address)
    frozen = {name: tuple(values) for name, values in result.items()}
    if frozen != EXPECTED_DIRECT_CALLS:
        raise AnalysisError("resolver direct call graph differs")
    return frozen


def merge_ranges(ranges: Iterable[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    return provenance.merge_ranges(ranges)


def output_write_coverage(
    instructions: Mapping[int, tuple[str, str]],
    start: int,
    end: int,
    initial_pointers: Mapping[str, int],
    helper_call_writes: Optional[Mapping[int, str]] = None,
    byte_copy_calls: Optional[Mapping[int, int]] = None,
) -> tuple[tuple[int, int], ...]:
    pointers = dict(initial_pointers)
    ranges: list[tuple[int, int]] = []
    helper_call_writes = helper_call_writes or {}
    byte_copy_calls = byte_copy_calls or {}
    for address in range(start, end, 4):
        mnemonic, operands_text = instructions[address]
        operands = provenance.split_operands(operands_text)
        if mnemonic == "add" and len(operands) >= 3:
            destination, source, immediate = operands[:3]
            if source in pointers and immediate.startswith("#"):
                pointers[destination] = pointers[source] + int(immediate[1:], 0)
            else:
                pointers.pop(destination, None)
            continue
        if mnemonic == "mov" and len(operands) == 2:
            destination, source = operands
            if source in pointers:
                pointers[destination] = pointers[source]
            else:
                pointers.pop(destination, None)
            continue
        if mnemonic in (
            "str",
            "stur",
            "strb",
            "sturb",
            "strh",
            "sturh",
            "stp",
        ):
            match = provenance.MEMORY_OPERAND.search(operands[-1])
            if match is None or match.group(1) not in pointers:
                continue
            offset = int(match.group(2), 0) if match.group(2) else 0
            width = provenance.register_width(operands[0])
            if mnemonic in ("strb", "sturb"):
                width = 1
            elif mnemonic in ("strh", "sturh"):
                width = 2
            elif mnemonic == "stp":
                width *= 2
            write_start = pointers[match.group(1)] + offset
            ranges.append((write_start, write_start + width))
            continue
        if mnemonic == "bl":
            helper_name = helper_call_writes.get(address)
            if helper_name is not None:
                if "x8" not in pointers:
                    raise AnalysisError(
                        "helper output pointer is unknown at {:#x}".format(address)
                    )
                for helper_start, helper_end in HELPER_OUTPUT_RANGES[helper_name]:
                    ranges.append(
                        (
                            pointers["x8"] + helper_start,
                            pointers["x8"] + helper_end,
                        )
                    )
            copy_count = byte_copy_calls.get(address)
            if copy_count is not None:
                if "x0" not in pointers:
                    raise AnalysisError(
                        "byte-copy output pointer is unknown at {:#x}".format(address)
                    )
                ranges.append((pointers["x0"], pointers["x0"] + copy_count))
            for index in range(19):
                pointers.pop("x{}".format(index), None)
            continue
        if mnemonic.startswith(("ldr", "ldur", "ldp", "adrp")) and operands:
            pointers.pop(operands[0], None)
            if mnemonic == "ldp" and len(operands) > 1:
                pointers.pop(operands[1], None)
    return merge_ranges(ranges)


def descriptor_evidence() -> tuple[Mapping[str, object], Mapping[str, object]]:
    specs = (
        ("__TEXT", "__const"),
        ("__TEXT", "__constg_swiftt"),
        ("__TEXT", "__swift5_reflstr"),
        ("__TEXT", "__swift5_typeref"),
        ("__TEXT", "__swift5_fieldmd"),
        ("__AUTH_CONST", "__const"),
    )
    sections = {
        spec: metadata.parse_section_bytes(
            *spec, metadata.run_dyld_info(("-section_bytes", *spec))
        )
        for spec in specs
    }
    memory = metadata.merged_memory(sections.values())
    labels = metadata.parse_type_labels(
        metadata.run_dyld_info(("-section", "__TEXT", "__swift5_typeref"))
    )
    descriptors = metadata.scan_descriptors(
        sections[("__TEXT", "__constg_swiftt")],
        memory,
        sections[("__TEXT", "__swift5_fieldmd")],
        labels,
    )
    slide, _ = metadata.infer_shared_cache_slide(
        sections[("__AUTH_CONST", "__const")], memory, descriptors
    )

    def exact_descriptor(
        address: int,
    ) -> tuple[metadata.Descriptor, Mapping[str, object]]:
        matches = [value for value in descriptors if value.address == address]
        if len(matches) != 1:
            raise AnalysisError("descriptor identity differs at {:#x}".format(address))
        descriptor = matches[0]
        value_metadata = metadata.metadata_for_descriptor(
            sections[("__AUTH_CONST", "__const")], memory, descriptor, slide
        )
        if value_metadata is None:
            raise AnalysisError("descriptor has no static metadata")
        return descriptor, value_metadata

    animatable, animatable_metadata = exact_descriptor(ANIMATABLE_DATA_DESCRIPTOR)
    if (
        animatable.name != "AnimatableData"
        or tuple((field.name, field.type_reference) for field in animatable.fields)
        != ANIMATABLE_DATA_FIELDS
        or animatable_metadata["size"] != ANIMATABLE_DATA_BYTE_COUNT
        or animatable_metadata["stride"] != 0x490
        or tuple(animatable_metadata["fieldOffsets"]) != ANIMATABLE_DATA_OFFSETS
    ):
        raise AnalysisError("Parameters.AnimatableData metadata differs")

    parameters, parameters_metadata = exact_descriptor(PARAMETERS_DESCRIPTOR)
    if (
        parameters.name != "Parameters"
        or tuple(field.name for field in parameters.fields) != PARAMETERS_FIELDS
        or parameters_metadata["size"] != PARAMETERS_BYTE_COUNT
        or parameters_metadata["stride"] != 0x408
        or tuple(parameters_metadata["fieldOffsets"]) != PARAMETERS_OFFSETS
    ):
        raise AnalysisError("Parameters metadata differs")

    def record(
        descriptor: metadata.Descriptor, value_metadata: Mapping[str, object]
    ) -> Mapping[str, object]:
        return {
            "name": descriptor.name,
            "descriptorAddress": "0x{:x}".format(descriptor.address),
            "size": value_metadata["size"],
            "stride": value_metadata["stride"],
            "fieldOffsets": value_metadata["fieldOffsets"],
            "fields": [
                {
                    "index": index,
                    "name": field.name,
                    "typeReference": field.type_reference,
                }
                for index, field in enumerate(descriptor.fields)
            ],
        }

    return record(animatable, animatable_metadata), record(
        parameters, parameters_metadata
    )


def range_record(start: int, end: int) -> Mapping[str, int]:
    return {"start": start, "endExclusive": end, "byteCount": end - start}


def field_map_records() -> list[Mapping[str, object]]:
    result: list[Mapping[str, object]] = []
    for (
        field,
        source_start,
        source_end,
        storage_start,
        storage_end,
        write_start,
        write_end,
        mechanism,
        site,
    ) in FIELD_MAP:
        result.append(
            {
                "field": field,
                "animatableStorageRange": (
                    range_record(source_start, source_end)
                    if source_start is not None and source_end is not None
                    else None
                ),
                "parametersStorageRange": range_record(storage_start, storage_end),
                "resolverWriteRange": (
                    range_record(write_start, write_end)
                    if write_start is not None and write_end is not None
                    else None
                ),
                "mechanism": mechanism,
                "firstWriteOrHelperCallsite": site,
            }
        )
    return result


def analyze() -> Mapping[str, object]:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise AnalysisError("analysis requires native arm64 macOS")
    product_version = command_output(("/usr/bin/sw_vers", "-productVersion"))
    build_version = command_output(("/usr/bin/sw_vers", "-buildVersion"))
    hardware_model = command_output(("/usr/sbin/sysctl", "-n", "hw.model"))
    if (
        product_version != metadata.EXPECTED_MACOS_PRODUCT_VERSION
        or build_version != metadata.EXPECTED_MACOS_BUILD_VERSION
        or hardware_model != EXPECTED_HARDWARE_MODEL
    ):
        raise AnalysisError("host differs from the frozen target")
    if metadata.EXPECTED_UUID not in metadata.run_dyld_info(("-uuid",)):
        raise AnalysisError("DesignLibrary UUID differs")
    if sha256(Path(metadata.__file__).resolve()) != METADATA_ANALYZER_SHA256:
        raise AnalysisError("metadata analyzer dependency differs")
    if sha256(Path(provenance.__file__).resolve()) != PROVENANCE_ANALYZER_SHA256:
        raise AnalysisError("provenance analyzer dependency differs")

    text = metadata.parse_section_bytes(
        "__TEXT",
        "__text",
        metadata.run_dyld_info(("-section_bytes", "__TEXT", "__text")),
    )
    code_records: dict[str, Mapping[str, object]] = {}
    for name, (start, end, expected_sha256) in CODE_REGIONS.items():
        code = metadata.read_bytes(text.memory, start, end - start)
        observed_sha256 = hashlib.sha256(code).hexdigest()
        if observed_sha256 != expected_sha256:
            raise AnalysisError(name + " code differs")
        code_records[name] = {
            "start": "0x{:x}".format(start),
            "endExclusive": "0x{:x}".format(end),
            "byteCount": end - start,
            "instructionCount": (end - start) // 4,
            "sha256": observed_sha256,
        }

    instructions = provenance.parse_instructions(
        metadata.run_dyld_info(("-disassemble",))
    )
    for name, (start, end, _) in CODE_REGIONS.items():
        if not set(range(start, end, 4)).issubset(instructions):
            raise AnalysisError(name + " disassembly coverage differs")
    contracts: list[Mapping[str, object]] = []
    for address, expected in sorted(CRITICAL_INSTRUCTIONS.items()):
        observed = instructions.get(address)
        if observed != expected:
            raise AnalysisError(
                "instruction differs at {:#x}: {!r}".format(address, observed)
            )
        contracts.append(
            {
                "address": "0x{:x}".format(address),
                "mnemonic": observed[0],
                "operands": observed[1],
            }
        )

    helper_coverages: dict[str, tuple[tuple[int, int], ...]] = {}
    for name, expected_ranges in HELPER_OUTPUT_RANGES.items():
        start, end, _ = CODE_REGIONS[name]
        initial = {"x8": 0}
        byte_copies = {0x240933118: 0x101} if name == "highlightsResolver" else {}
        observed_ranges = output_write_coverage(
            instructions,
            start,
            end,
            initial,
            byte_copy_calls=byte_copies,
        )
        if observed_ranges != expected_ranges:
            raise AnalysisError(name + " output write coverage differs")
        helper_coverages[name] = observed_ranges

    resolver_start, resolver_end, _ = CODE_REGIONS["parametersResolver"]
    parameter_writes = output_write_coverage(
        instructions,
        resolver_start,
        resolver_end,
        {"x20": 0},
        helper_call_writes=HELPER_CALL_WRITES,
    )
    if parameter_writes != EXPECTED_PARAMETER_WRITE_RANGES:
        raise AnalysisError(
            "Parameters resolver write coverage differs: {!r}".format(parameter_writes)
        )
    preserved_ranges = provenance.complement_ranges(
        parameter_writes, PARAMETERS_BYTE_COUNT
    )
    written_byte_count = sum(end - start for start, end in parameter_writes)
    if written_byte_count != 932:
        raise AnalysisError("Parameters resolver written byte count differs")

    animatable_descriptor, parameters_descriptor = descriptor_evidence()
    source_path = Path(__file__).resolve()
    return {
        "designLibraryParametersAnimatableResolverAnalysisSchemaVersion": (
            RESULT_SCHEMA_VERSION
        ),
        "classification": (
            "native static metadata/code/write-coverage analysis; no Apple "
            "application, render, image, public value, crop, or provider return is read"
        ),
        "host": {
            "system": platform.system(),
            "machine": platform.machine(),
            "macOSProductVersion": product_version,
            "macOSBuildVersion": build_version,
            "hardwareModel": hardware_model,
        },
        "framework": {
            "path": str(metadata.FRAMEWORK),
            "uuid": metadata.EXPECTED_UUID,
        },
        "tool": {
            "dyldInfo": str(metadata.DYLD_INFO),
            "python": sys.version.split()[0],
            "source": SOURCE_RELATIVE_PATH,
            "sourceSHA256": sha256(source_path),
            "metadataAnalyzerSHA256": METADATA_ANALYZER_SHA256,
            "provenanceAnalyzerSHA256": PROVENANCE_ANALYZER_SHA256,
        },
        "parametersAnimatableData": animatable_descriptor,
        "parameters": parameters_descriptor,
        "resolverABI": {
            "source": "x0 -> Parameters.AnimatableData (1,153 bytes)",
            "output": "x20 -> pre-seeded Parameters (1,025 bytes)",
            "primaryRecipeBuilderCallsite": "0x240982cd4",
            "secondDirectCallsite": "0x2409332e4",
        },
        "codeRegions": code_records,
        "directBLCallsites": {
            name: ["0x{:x}".format(address) for address in addresses]
            for name, addresses in direct_calls(text).items()
        },
        "instructionContracts": contracts,
        "helperOutputWriteCoverage": {
            name: [range_record(start, end) for start, end in ranges]
            for name, ranges in helper_coverages.items()
        },
        "fieldMap": field_map_records(),
        "parametersWriteCoverage": {
            "writtenRanges": [
                range_record(start, end) for start, end in parameter_writes
            ],
            "writtenByteCount": written_byte_count,
            "seedPreservedRanges": [
                range_record(start, end) for start, end in preserved_ranges
            ],
            "seedPreservedByteCount": PARAMETERS_BYTE_COUNT - written_byte_count,
        },
        "claims": {
            "resolverSourceIsParametersAnimatableData": True,
            "allSixteenAnimatableFieldsMappedToParameters": True,
            "updateRateIsOnlyParametersFieldWithoutResolverWrite": True,
            "updateRatePreservedFromDeterministicDefaultSeed": True,
            "resolverWrittenByteCount": written_byte_count,
            "resolverSeedPreservedByteCount": PARAMETERS_BYTE_COUNT
            - written_byte_count,
            "allHelperOutputWriteRangesProved": True,
            "optionalZeroCanonicalizationPresent": True,
            "allOpticalArithmeticDecoded": False,
            "publicControlsToAnimatableDataLawEstablished": False,
            "cropAllocationPolicyEstablished": False,
            "retinaCompositorColorLawEstablished": False,
            "independentWalleZeroByteFrameParityEstablished": False,
            "liquidGlassParityEstablished": False,
            "productionShaderChangeAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        result = analyze()
    except (AnalysisError, metadata.AnalysisError, provenance.AnalysisError) as error:
        print("analysis failed: " + str(error), file=sys.stderr)
        return 1
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(payload, end="")
    else:
        arguments.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
