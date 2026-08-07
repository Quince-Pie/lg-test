#!/usr/bin/env python3
"""Prove the native ResolvedRecipe-to-BackgroundFilter provenance chain."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import struct
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

import analyze_designlibrary_background_filter_metadata_local_macos_26_6_1 as metadata


RESULT_SCHEMA_VERSION = 1
SOURCE_RELATIVE_PATH = (
    "Analysis/analyze_designlibrary_resolved_recipe_provenance_local_macos_26_6_1.py"
)
METADATA_ANALYZER_RELATIVE_PATH = (
    "Analysis/analyze_designlibrary_background_filter_metadata_local_macos_26_6_1.py"
)
METADATA_ANALYZER_SHA256 = (
    "a50569535c5452a4a4e3db0940be09968b4de38bc86aeda12c95ab3c0a653aff"
)
EXPECTED_UUID = metadata.EXPECTED_UUID
EXPECTED_MACOS_PRODUCT_VERSION = metadata.EXPECTED_MACOS_PRODUCT_VERSION
EXPECTED_MACOS_BUILD_VERSION = metadata.EXPECTED_MACOS_BUILD_VERSION
EXPECTED_HARDWARE_MODEL = "MacBookPro18,2"
PARAMETERS_BYTE_COUNT = 0x401
BYTE_COPY_STUB = 0x2409A5910
BYTE_COPY_STUB_END = 0x2409A5920
BYTE_COPY_STUB_SHA256 = (
    "6b5abc621f7b37a3403371e2107e0ceb2a9d9de358b781d172ce768c5d7772f6"
)
RESOLVED_RECIPE_DESCRIPTOR = 0x2409D2F1C
RESOLVED_RECIPE_METADATA_ACCESSOR = 0x240986060
DEFAULT_PARAMETERS_ONCE_TOKEN = 0x298F07D08
DEFAULT_PARAMETERS_STORAGE = 0x298F0E710

CODE_REGIONS = {
    "backgroundFilterProducer": (
        0x240918FA8,
        0x240919614,
        "0729f7b0f874c0fb9fb64fa3383a6f2ed328d1dc55fdce53b82038a188df6f97",
    ),
    "resolveLayersHelper": (
        0x240922488,
        0x240926268,
        "e929428281b6f7d9296b9ed290dc9ea3a9f91c18c331e1735391e11167709092",
    ),
    "defaultParametersInitializer": (
        0x24093C0F8,
        0x24093C638,
        "b1691f1577f440c764a86ccd1a1ddc32fbae80fff16aba6ea12e0542233faa75",
    ),
    "resolveLayers": (
        0x24097BC34,
        0x24097C040,
        "f66d0b6213c93d6fa532688faba56d529b8ba1b0ff8290a4c73d7c22c1a8ffdf",
    ),
    "resolvedRecipeIntermediateBuilder": (
        0x2409801BC,
        0x240980F38,
        "ba0ad1081cece802ccd1e148660a542145f95bf57a92de4407a3fad55f4679c6",
    ),
    "resolvedRecipeBuilder": (
        0x240981B4C,
        0x240982E80,
        "07d9b8571ca8fed42e1d8e71b312f00a9c9713ce19f406d6f2c15a9d2403fde4",
    ),
    "resolvedRecipeMetadataAccessor": (
        0x240986060,
        0x2409860AC,
        "31eda33fd9f60223ed013edefaed24c2a5009620fa7fdfefbd68b4edda782d99",
    ),
}

EXPECTED_DIRECT_CALLS = {
    "backgroundFilterProducer": (0x240923830,),
    "resolveLayersHelper": (0x24097BFD0,),
    "defaultParametersInitializer": (),
    "resolveLayers": (0x24097730C,),
    "resolvedRecipeIntermediateBuilder": (0x24091F9E0, 0x240923628),
    "resolvedRecipeBuilder": (0x240980EF0,),
    "resolvedRecipeMetadataAccessor": (
        0x24091F920,
        0x24091FF20,
        0x24091FF78,
        0x24091FFD0,
        0x2409226F8,
        0x240982D90,
    ),
}

RESOLVED_RECIPE_FIELDS = (
    (
        "parameters",
        "_____ 13DesignLibrary21GlassMaterialProviderV10ParametersV",
    ),
    ("layers", "_____ 13DesignLibrary21GlassMaterialProviderV6LayersV"),
    ("flags", "_____ 13DesignLibrary21GlassMaterialProviderV16EnvironmentFlagsV"),
    ("colorScheme", "_____ 7SwiftUI11ColorSchemeO"),
    (
        "optimizationLevel",
        "_____ 13DesignLibrary21GlassMaterialProviderV25ResolvedOptimizationLevelO",
    ),
    (
        "contentEffect",
        "_____ 13DesignLibrary21GlassMaterialProviderV21ResolvedContentEffectO",
    ),
)

CRITICAL_INSTRUCTIONS = {
    0x2409224BC: ("str", "x20, [x19, #0x298]"),
    0x2409226F8: ("bl", "0x240986060"),
    0x2409226FC: ("str", "x0, [x19, #0x258]"),
    0x2409235F0: ("ldr", "x8, [x22]"),
    0x240923628: ("bl", "0x2409801bc"),
    0x240923630: ("ldr", "x21, [x19, #0x258]"),
    0x24092369C: ("mov", "x0, x28"),
    0x2409236A0: ("ldr", "x22, [x19, #0x218]"),
    0x2409236AC: ("add", "x28, x19, #0x6d8"),
    0x2409236B0: ("add", "x0, x19, #0x6d8"),
    0x2409236B4: ("mov", "x1, x22"),
    0x2409236B8: ("mov", "w2, #0x401"),
    0x2409236C0: ("mov", "x11, x22"),
    0x2409236C4: ("ldr", "x22, [x22, #0x408]"),
    0x2409236C8: ("ldr", "x20, [x11, #0x410]"),
    0x24092381C: ("add", "x0, x19, #0x6d8"),
    0x240923824: ("mov", "x8, x21"),
    0x240923828: ("ldr", "x2, [x19, #0x218]"),
    0x240923830: ("bl", "0x240918fa8"),
    0x24093C4FC: ("adrp", "x19, 361938"),
    0x24093C500: ("add", "x19, x19, #0x710"),
    0x24093C538: ("str", "wzr, [x19]"),
    0x24093C5B4: ("add", "x0, x19, #0x205"),
    0x24093C5B8: ("add", "x1, sp, #0x5f0"),
    0x24093C5BC: ("mov", "w2, #0x104"),
    0x24093C618: ("strb", "w20, [x19, #0x400]"),
    0x24097BC58: ("mov", "x21, x20"),
    0x24097BE38: ("stp", "x19, x21, [x29, #-0x70]"),
    0x24097BFC4: ("mov", "x8, x23"),
    0x24097BFC8: ("ldur", "x0, [x29, #-0x58]"),
    0x24097BFCC: ("ldur", "x20, [x29, #-0x68]"),
    0x24097BFD0: ("bl", "0x240922488"),
    0x24098020C: ("mov", "x20, x0"),
    0x240980210: ("stur", "x8, [x29, #-0xe0]"),
    0x240980EE0: ("ldp", "x8, x2, [x29, #-0xe0]"),
    0x240980EE4: ("mov", "x0, x22"),
    0x240980EE8: ("ldur", "x1, [x29, #-0xa8]"),
    0x240980EEC: ("mov.16b", "v0, v8"),
    0x240980EF0: ("bl", "0x240981b4c"),
    0x240981BA0: ("str", "x2, [x19, #0x88]"),
    0x240981BA4: ("mov", "x25, x1"),
    0x240981BA8: ("mov", "x23, x0"),
    0x240981BAC: ("mov", "x27, x8"),
    0x240981E18: ("adrp", "x8, 361862"),
    0x240981E1C: ("ldr", "x8, [x8, #0xd08]"),
    0x240981E20: ("cmn", "x8, #0x1"),
    0x240981E24: ("b.ne", "0x240982e60"),
    0x240981E38: ("adrp", "x1, 361869"),
    0x240981E3C: ("add", "x1, x1, #0x710"),
    0x240981E40: ("add", "x0, x19, #0xc60"),
    0x240981E44: ("mov", "w2, #0x401"),
    0x240982B18: ("add", "x0, x19, #0xc60"),
    0x240982B1C: ("add", "x1, x19, #0x1, lsl #12"),
    0x240982B20: ("add", "x1, x1, #0x68"),
    0x240982B24: ("mov", "w2, #0x401"),
    0x240982D00: ("ldr", "x23, [x19]"),
    0x240982D90: ("bl", "0x240986060"),
    0x240982DFC: ("add", "x1, x19, #0xc60"),
    0x240982E00: ("mov", "x0, x23"),
    0x240982E04: ("mov", "w2, #0x401"),
    0x240982E0C: ("ldr", "x8, [x19, #0x460]"),
    0x240982E10: ("str", "x8, [x23, #0x408]"),
    0x240982E14: ("str", "x21, [x23, #0x410]"),
    0x240982E18: ("ldrsw", "x8, [x20, #0x20]"),
    0x240982E1C: ("strb", "w22, [x23, x8]"),
    0x240982E20: ("ldrsw", "x8, [x20, #0x24]"),
    0x240982E24: ("ldr", "w9, [x19, #0x46c]"),
    0x240982E28: ("strb", "w9, [x23, x8]"),
    0x240982E60: ("adrp", "x0, 361861"),
    0x240982E64: ("add", "x0, x0, #0xd08"),
    0x240982E68: ("adrp", "x16, -70"),
    0x240982E6C: ("add", "x16, x16, #0xf8"),
    0x240982E70: ("paciza", "x16"),
    0x240982E74: ("mov", "x1, x16"),
    0x240982E7C: ("b", "0x240981e28"),
    0x240986084: ("adrp", "x16, 76"),
    0x240986088: ("add", "x16, x16, #0xf1c"),
}

BYTE_COPY_CALLS = {
    "helperRecipePrefixToLocalParameters": 0x2409236BC,
    "builderDefaultSeedToWorkingParameters": 0x240981E48,
    "builderAlternateRecipeToWorkingParameters": 0x240982B28,
    "builderWorkingParametersToRecipePrefix": 0x240982E08,
    "defaultInitializerNestedValue": 0x24093C5C0,
}

INSTRUCTION_LINE = re.compile(r"^0x([0-9A-Fa-f]+)\s+([^\s]+)(?:\s+(.*?))?\s*$")
MEMORY_OPERAND = re.compile(r"\[(x[0-9]+)(?:,\s*#(-?0x[0-9A-Fa-f]+|-?[0-9]+))?\]")
REGISTER = re.compile(r"^([xwqdsbh])([0-9]+)$")


class AnalysisError(RuntimeError):
    """Raised when native evidence differs from the frozen contract."""


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


def parse_instructions(output: str) -> Mapping[int, tuple[str, str]]:
    result: dict[int, tuple[str, str]] = {}
    for line in output.splitlines():
        match = INSTRUCTION_LINE.match(line)
        if match is None:
            continue
        address = int(match.group(1), 16)
        if address in result:
            raise AnalysisError("duplicate instruction at {:#x}".format(address))
        result[address] = (
            match.group(2).lower(),
            (match.group(3) or "").split(";", 1)[0].strip(),
        )
    return result


def validate_instruction_contracts(
    instructions: Mapping[int, tuple[str, str]],
) -> list[Mapping[str, object]]:
    records: list[Mapping[str, object]] = []
    for address, expected in sorted(CRITICAL_INSTRUCTIONS.items()):
        observed = instructions.get(address)
        if observed != expected:
            raise AnalysisError(
                "instruction contract differs at {:#x}: {!r} != {!r}".format(
                    address, observed, expected
                )
            )
        records.append(
            {
                "address": "0x{:x}".format(address),
                "mnemonic": observed[0],
                "operands": observed[1],
            }
        )
    return records


def sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value & (sign - 1)) - (value & sign)


def direct_calls(
    text: metadata.Section,
) -> Mapping[str, tuple[int, ...]]:
    targets = {start: name for name, (start, _, _) in CODE_REGIONS.items()}
    result: dict[str, list[int]] = {name: [] for name in CODE_REGIONS}
    for address in range(text.start, text.end - 3, 4):
        instruction = struct.unpack("<I", metadata.read_bytes(text.memory, address, 4))[
            0
        ]
        if instruction & 0xFC000000 != 0x94000000:
            continue
        destination = address + sign_extend(instruction & 0x03FFFFFF, 26) * 4
        name = targets.get(destination)
        if name is not None:
            result[name].append(address)
    frozen = {name: tuple(values) for name, values in result.items()}
    if frozen != EXPECTED_DIRECT_CALLS:
        raise AnalysisError("direct call graph differs from the frozen contract")
    return frozen


def branch_destination(text: metadata.Section, address: int) -> int:
    instruction = struct.unpack("<I", metadata.read_bytes(text.memory, address, 4))[0]
    if instruction & 0xFC000000 != 0x94000000:
        raise AnalysisError("expected BL at {:#x}".format(address))
    return address + sign_extend(instruction & 0x03FFFFFF, 26) * 4


def validate_byte_copy_calls(text: metadata.Section) -> Mapping[str, str]:
    result = {
        name: "0x{:x}".format(branch_destination(text, address))
        for name, address in BYTE_COPY_CALLS.items()
    }
    if set(result.values()) != {"0x{:x}".format(BYTE_COPY_STUB)}:
        raise AnalysisError("byte-copy call targets differ")
    return result


def merge_ranges(ranges: Iterable[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    ordered = sorted(ranges)
    if not ordered:
        return ()
    result: list[tuple[int, int]] = []
    start, end = ordered[0]
    for next_start, next_end in ordered[1:]:
        if next_start > end:
            result.append((start, end))
            start, end = next_start, next_end
        else:
            end = max(end, next_end)
    result.append((start, end))
    return tuple(result)


def complement_ranges(
    ranges: Sequence[tuple[int, int]], end: int
) -> tuple[tuple[int, int], ...]:
    cursor = 0
    result: list[tuple[int, int]] = []
    for start, stop in ranges:
        if cursor < start:
            result.append((cursor, start))
        cursor = stop
    if cursor < end:
        result.append((cursor, end))
    return tuple(result)


def register_width(register: str) -> int:
    if register in ("xzr", "wzr"):
        return 8 if register == "xzr" else 4
    match = REGISTER.match(register)
    if match is None:
        raise AnalysisError("unsupported register " + register)
    return {
        "x": 8,
        "w": 4,
        "q": 16,
        "d": 8,
        "s": 4,
        "h": 2,
        "b": 1,
    }[match.group(1)]


def split_operands(value: str) -> list[str]:
    result: list[str] = []
    depth = 0
    start = 0
    for index, character in enumerate(value):
        if character == "[":
            depth += 1
        elif character == "]":
            depth -= 1
        elif character == "," and depth == 0:
            result.append(value[start:index].strip())
            start = index + 1
    result.append(value[start:].strip())
    return result


def default_initializer_write_coverage(
    instructions: Mapping[int, tuple[str, str]],
) -> tuple[tuple[int, int], ...]:
    pointers: dict[str, int] = {"x19": 0}
    ranges: list[tuple[int, int]] = []
    for address in range(0x24093C504, 0x24093C61C, 4):
        mnemonic, operands_text = instructions[address]
        operands = split_operands(operands_text)
        if mnemonic == "add" and len(operands) >= 3:
            destination, source, immediate = operands[:3]
            if source in pointers and immediate.startswith("#"):
                pointers[destination] = pointers[source] + int(immediate[1:], 0)
            else:
                pointers.pop(destination, None)
            continue
        if mnemonic in ("str", "stur", "strb", "sturb", "strh", "sturh", "stp"):
            memory = operands[-1]
            match = MEMORY_OPERAND.search(memory)
            if match is None or match.group(1) not in pointers:
                continue
            offset = int(match.group(2), 0) if match.group(2) else 0
            width = register_width(operands[0])
            if mnemonic in ("strb", "sturb"):
                width = 1
            elif mnemonic in ("strh", "sturh"):
                width = 2
            elif mnemonic == "stp":
                width *= 2
            start = pointers[match.group(1)] + offset
            ranges.append((start, start + width))
            continue
        if address == 0x24093C5C0:
            if pointers.get("x0") != 0x205:
                raise AnalysisError("nested default copy destination differs")
            ranges.append((0x205, 0x205 + 0x104))
            pointers.pop("x0", None)
            continue
        if mnemonic.startswith(("ldr", "ldur", "ldp", "adrp")) and operands:
            pointers.pop(operands[0], None)
            if mnemonic == "ldp" and len(operands) > 1:
                pointers.pop(operands[1], None)
    merged = merge_ranges(ranges)
    expected = (
        (0x000, 0x004),
        (0x008, 0x0A9),
        (0x0B0, 0x0F9),
        (0x100, 0x135),
        (0x138, 0x182),
        (0x188, 0x1F2),
        (0x1F4, 0x309),
        (0x310, 0x331),
        (0x338, 0x369),
        (0x370, 0x389),
        (0x390, 0x3A9),
        (0x3B0, 0x3C1),
        (0x3C8, 0x3D9),
        (0x3E0, 0x401),
    )
    if merged != expected:
        raise AnalysisError(
            "default Parameters write coverage differs: {!r}".format(merged)
        )
    return merged


def descriptor_evidence() -> Mapping[str, object]:
    specs = (
        ("__TEXT", "__const"),
        ("__TEXT", "__constg_swiftt"),
        ("__TEXT", "__swift5_reflstr"),
        ("__TEXT", "__swift5_typeref"),
        ("__TEXT", "__swift5_fieldmd"),
    )
    sections = {
        spec: metadata.parse_section_bytes(
            *spec, metadata.run_dyld_info(("-section_bytes", *spec))
        )
        for spec in specs
    }
    memory = metadata.merged_memory(sections.values())
    type_labels = metadata.parse_type_labels(
        metadata.run_dyld_info(("-section", "__TEXT", "__swift5_typeref"))
    )
    descriptors = metadata.scan_descriptors(
        sections[("__TEXT", "__constg_swiftt")],
        memory,
        sections[("__TEXT", "__swift5_fieldmd")],
        type_labels,
    )
    matches = [
        value for value in descriptors if value.address == RESOLVED_RECIPE_DESCRIPTOR
    ]
    if len(matches) != 1:
        raise AnalysisError("ResolvedRecipe descriptor identity differs")
    descriptor = matches[0]
    observed_fields = tuple(
        (field.name, field.type_reference) for field in descriptor.fields
    )
    if descriptor.name != "ResolvedRecipe" or observed_fields != RESOLVED_RECIPE_FIELDS:
        raise AnalysisError("ResolvedRecipe fields differ")
    return {
        "name": descriptor.name,
        "descriptorAddress": "0x{:x}".format(descriptor.address),
        "descriptorFlags": "0x{:08x}".format(descriptor.flags),
        "fieldDescriptorAddress": "0x{:x}".format(descriptor.field_descriptor_address),
        "fieldOffsetVectorWords": descriptor.field_offset_vector_words,
        "fields": [
            {
                "index": index,
                "name": field.name,
                "typeReference": field.type_reference,
                "flags": "0x{:08x}".format(field.flags),
            }
            for index, field in enumerate(descriptor.fields)
        ],
    }


def range_records(ranges: Sequence[tuple[int, int]]) -> list[Mapping[str, int]]:
    return [
        {"start": start, "endExclusive": end, "byteCount": end - start}
        for start, end in ranges
    ]


def analyze() -> Mapping[str, object]:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise AnalysisError("analysis requires native arm64 macOS")
    product_version = command_output(("/usr/bin/sw_vers", "-productVersion"))
    build_version = command_output(("/usr/bin/sw_vers", "-buildVersion"))
    hardware_model = command_output(("/usr/sbin/sysctl", "-n", "hw.model"))
    if (
        product_version != EXPECTED_MACOS_PRODUCT_VERSION
        or build_version != EXPECTED_MACOS_BUILD_VERSION
        or hardware_model != EXPECTED_HARDWARE_MODEL
    ):
        raise AnalysisError("host differs from the frozen native target")

    uuid_output = metadata.run_dyld_info(("-uuid",))
    if EXPECTED_UUID not in uuid_output:
        raise AnalysisError("DesignLibrary UUID differs")

    text = metadata.parse_section_bytes(
        "__TEXT",
        "__text",
        metadata.run_dyld_info(("-section_bytes", "__TEXT", "__text")),
    )
    auth_stubs = metadata.parse_section_bytes(
        "__TEXT",
        "__auth_stubs",
        metadata.run_dyld_info(("-section_bytes", "__TEXT", "__auth_stubs")),
    )
    byte_copy_code = metadata.read_bytes(
        auth_stubs.memory, BYTE_COPY_STUB, BYTE_COPY_STUB_END - BYTE_COPY_STUB
    )
    if hashlib.sha256(byte_copy_code).hexdigest() != BYTE_COPY_STUB_SHA256:
        raise AnalysisError("byte-copy stub differs")

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

    instructions = parse_instructions(metadata.run_dyld_info(("-disassemble",)))
    for name, (start, end, _) in CODE_REGIONS.items():
        expected_addresses = set(range(start, end, 4))
        if not expected_addresses.issubset(instructions):
            raise AnalysisError(name + " disassembly coverage differs")
    instruction_contracts = validate_instruction_contracts(instructions)
    calls = direct_calls(text)
    byte_copy_calls = validate_byte_copy_calls(text)

    common = metadata.parse_section_bytes(
        "__DATA_DIRTY",
        "__common",
        metadata.run_dyld_info(("-section_bytes", "__DATA_DIRTY", "__common")),
    )
    zero_seed = metadata.read_bytes(
        common.memory, DEFAULT_PARAMETERS_STORAGE, PARAMETERS_BYTE_COUNT
    )
    if set(zero_seed) != {0}:
        raise AnalysisError("default Parameters common storage is not zero-filled")
    data = metadata.parse_section_bytes(
        "__DATA_DIRTY",
        "__data",
        metadata.run_dyld_info(("-section_bytes", "__DATA_DIRTY", "__data")),
    )
    once_token = metadata.read_bytes(data.memory, DEFAULT_PARAMETERS_ONCE_TOKEN, 8)
    if once_token != bytes(8):
        raise AnalysisError("default Parameters once token initial value differs")

    initializer_ranges = default_initializer_write_coverage(instructions)
    initializer_gaps = complement_ranges(initializer_ranges, PARAMETERS_BYTE_COUNT)
    direct_write_count = sum(end - start for start, end in initializer_ranges)

    source_path = Path(__file__).resolve()
    metadata_analyzer_path = Path(metadata.__file__).resolve()
    metadata_analyzer_sha256 = sha256(metadata_analyzer_path)
    if metadata_analyzer_sha256 != METADATA_ANALYZER_SHA256:
        raise AnalysisError("metadata analyzer dependency differs")
    return {
        "designLibraryResolvedRecipeProvenanceAnalysisSchemaVersion": (
            RESULT_SCHEMA_VERSION
        ),
        "classification": (
            "native static type/code/data provenance; no Apple application, render, "
            "image, public sample value, crop, or provider return is read"
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
            "uuid": EXPECTED_UUID,
        },
        "tool": {
            "dyldInfo": str(metadata.DYLD_INFO),
            "python": sys.version.split()[0],
            "source": SOURCE_RELATIVE_PATH,
            "sourceSHA256": sha256(source_path),
            "metadataAnalyzerSource": METADATA_ANALYZER_RELATIVE_PATH,
            "metadataAnalyzerSHA256": metadata_analyzer_sha256,
        },
        "resolvedRecipe": descriptor_evidence(),
        "codeRegions": code_records,
        "directBLCallsites": {
            name: ["0x{:x}".format(address) for address in addresses]
            for name, addresses in calls.items()
        },
        "byteCopyStub": {
            "address": "0x{:x}".format(BYTE_COPY_STUB),
            "byteCount": len(byte_copy_code),
            "sha256": BYTE_COPY_STUB_SHA256,
            "callTargets": byte_copy_calls,
        },
        "instructionContracts": instruction_contracts,
        "defaultParametersSeed": {
            "onceTokenAddress": "0x{:x}".format(DEFAULT_PARAMETERS_ONCE_TOKEN),
            "onceTokenInitialBytesHex": once_token.hex(),
            "zeroFilledCommonStorageAddress": "0x{:x}".format(
                DEFAULT_PARAMETERS_STORAGE
            ),
            "byteCount": PARAMETERS_BYTE_COUNT,
            "initialSHA256": hashlib.sha256(zero_seed).hexdigest(),
            "initializerDirectWriteRanges": range_records(initializer_ranges),
            "initializerDirectWriteByteCount": direct_write_count,
            "zeroFillOnlyPaddingRanges": range_records(initializer_gaps),
            "zeroFillOnlyPaddingByteCount": PARAMETERS_BYTE_COUNT - direct_write_count,
        },
        "provenanceChain": [
            {
                "boundary": "Resolved.resolveLayers self to stripped helper",
                "source": "original Swift self in x20",
                "destination": "helper x20, stored at frame +0x298",
                "callsite": "0x24097bfd0",
            },
            {
                "boundary": "Resolved state to ResolvedRecipe",
                "source": "resolved state/context inputs",
                "destination": "ResolvedRecipe indirect result in x8",
                "callsite": "0x240923628",
                "builderCallsite": "0x240980ef0",
            },
            {
                "boundary": "default Parameters to recipe working Parameters",
                "source": "zero-filled once-initialized common storage 0x298f0e710",
                "destination": "recipe-builder stack +0xc60",
                "byteCount": PARAMETERS_BYTE_COUNT,
                "callsite": "0x240981e48",
            },
            {
                "boundary": "working Parameters to ResolvedRecipe.parameters",
                "source": "recipe-builder stack +0xc60",
                "destination": "ResolvedRecipe output byte 0",
                "byteCount": PARAMETERS_BYTE_COUNT,
                "callsite": "0x240982e08",
            },
            {
                "boundary": "ResolvedRecipe.parameters to local constructor input",
                "source": "ResolvedRecipe byte 0",
                "destination": "resolveLayers helper frame +0x6d8",
                "byteCount": PARAMETERS_BYTE_COUNT,
                "callsite": "0x2409236bc",
            },
            {
                "boundary": "local Parameters to BackgroundFilter producer",
                "source": "resolveLayers helper frame +0x6d8",
                "destination": "backgroundFilterProducer x0",
                "callsite": "0x240923830",
            },
        ],
        "claims": {
            "parametersAreResolvedRecipeFieldZero": True,
            "parametersFieldOffset": 0,
            "parametersFieldByteCount": PARAMETERS_BYTE_COUNT,
            "resolvedRecipeBuilderIsExactProducerBoundary": True,
            "resolveLayersHelperOnlyCopiesAlreadyProducedParameters": True,
            "constructorAndProducerAreDownstreamOfResolvedRecipeBuilder": True,
            "defaultSeedPaddingIsDeterministicZeroFill": True,
            "publicControlsToParametersLawEstablished": False,
            "opticalLawFullyDecoded": False,
            "remainingStaticLawRegion": "0x240981b4c..0x240982e80",
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
    except (AnalysisError, metadata.AnalysisError) as error:
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
