#!/usr/bin/env python3
"""Decode DesignLibrary's BackgroundFilter metadata from the native dyld cache."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import struct
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


DYLD_INFO = Path("/Library/Developer/CommandLineTools/usr/bin/dyld_info")
FRAMEWORK = Path(
    "/System/Library/PrivateFrameworks/DesignLibrary.framework/Versions/A/DesignLibrary"
)
EXPECTED_UUID = "1E980802-69F5-3E69-89EF-50088297FCF5"
EXPECTED_MACOS_PRODUCT_VERSION = "26.6.1"
EXPECTED_MACOS_BUILD_VERSION = "25G76"
SOURCE_RELATIVE_PATH = (
    "Analysis/analyze_designlibrary_background_filter_metadata_local_macos_26_6_1.py"
)
TARGET_TYPE = "BackgroundFilter"
TARGET_FIELDS = (
    "layerIndex",
    "shadow",
    "blur",
    "refraction",
    "face",
    "bleed",
    "sdrAdjustment",
    "flags",
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
YCC_FIELDS = ("black", "white", "saturation", "normalFill", "dodgeFill", "burnFill")
FACE_EFFECT_DIMMING_FIELDS = ("whitePointShift", "distances")
NESTED_TYPES = (
    "Shadow",
    "Blur",
    "Refraction",
    "FaceEffects",
    "EdgeBleed",
    "SDRAdjustment",
    "EnvironmentFlags",
    "YCC",
    "FaceEffectDimming",
)
TOP_LEVEL_NESTED_TYPES = {
    "shadow": "Shadow",
    "blur": "Blur",
    "refraction": "Refraction",
    "face": "FaceEffects",
    "bleed": "EdgeBleed",
    "sdrAdjustment": "SDRAdjustment",
    "flags": "EnvironmentFlags",
}
STRUCT_METADATA_KIND = 0x200
STRUCT_CONTEXT_KIND = 17
CODE_REGIONS = {
    "sdfBackdropMarginGetter": (0x2409180B4, 0x24091848C),
    "filterArrayGetter": (0x24091848C, 0x240918EAC),
    "backgroundFilterProducer": (0x240918FA8, 0x240919614),
    "backgroundFilterConstructor": (0x24091BD00, 0x24091C114),
    "backgroundFilterMetadataAccessor": (0x24091C288, 0x24091C298),
    "parametersMetadataAccessor": (0x240945CC0, 0x240945CD0),
    "parametersProducerCaller": (0x240922488, 0x240926268),
}
BYTE_LINE = re.compile(r"^0x([0-9A-Fa-f]+):((?: [0-9A-Fa-f]{2})+)\s*$")
TYPE_LABEL = re.compile(r"^_symbolic (.*):$")
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class AnalysisError(RuntimeError):
    """Raised when native metadata does not satisfy the fail-closed contract."""


@dataclass(frozen=True)
class Section:
    segment: str
    name: str
    memory: Mapping[int, int]

    @cached_property
    def start(self) -> int:
        return min(self.memory)

    @cached_property
    def end(self) -> int:
        return max(self.memory) + 1


@dataclass(frozen=True)
class Field:
    name: str
    flags: int
    type_reference_address: int
    type_reference: Optional[str]


@dataclass(frozen=True)
class Descriptor:
    address: int
    name: str
    flags: int
    field_descriptor_address: int
    field_offset_vector_words: int
    fields: Tuple[Field, ...]


@dataclass(frozen=True)
class TextEvidence:
    code: Mapping[str, bytes]
    direct_bl_callsites: Mapping[int, Sequence[str]]
    section_start: int
    section_end: int


def run_dyld_info(arguments: Sequence[str]) -> str:
    completed = subprocess.run(
        [str(DYLD_INFO), *arguments, str(FRAMEWORK)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise AnalysisError(
            "dyld_info failed: "
            + " ".join(arguments)
            + "\n"
            + completed.stderr.strip()
        )
    return completed.stdout


def parse_section_bytes(segment: str, name: str, output: str) -> Section:
    memory: Dict[int, int] = {}
    for line in output.splitlines():
        match = BYTE_LINE.match(line)
        if match is None:
            continue
        address = int(match.group(1), 16)
        octets = bytes.fromhex(match.group(2))
        for index, value in enumerate(octets):
            byte_address = address + index
            if byte_address in memory:
                raise AnalysisError(
                    "duplicate byte in ({},{}) at {:#x}".format(
                        segment, name, byte_address
                    )
                )
            memory[byte_address] = value
    if not memory:
        raise AnalysisError("dyld_info returned no bytes for ({},{})".format(segment, name))
    expected = set(range(min(memory), max(memory) + 1))
    if set(memory) != expected:
        raise AnalysisError("non-contiguous ({},{}) section".format(segment, name))
    return Section(segment=segment, name=name, memory=memory)


def parse_type_labels(output: str) -> Mapping[int, str]:
    labels: Dict[int, str] = {}
    pending: Optional[str] = None
    for line in output.splitlines():
        label_match = TYPE_LABEL.match(line)
        if label_match is not None:
            pending = label_match.group(1)
            continue
        byte_match = BYTE_LINE.match(line)
        if byte_match is not None and pending is not None:
            labels[int(byte_match.group(1), 16)] = pending
            pending = None
    if not labels:
        raise AnalysisError("no symbolic type-reference labels were decoded")
    return labels


def merged_memory(sections: Iterable[Section]) -> Mapping[int, int]:
    result: Dict[int, int] = {}
    for section in sections:
        overlap = set(result).intersection(section.memory)
        if overlap:
            raise AnalysisError("section byte ranges overlap at {:#x}".format(min(overlap)))
        result.update(section.memory)
    return result


def read_bytes(memory: Mapping[int, int], address: int, count: int) -> bytes:
    try:
        return bytes(memory[address + index] for index in range(count))
    except KeyError as error:
        raise AnalysisError(
            "missing byte at {:#x} while reading {} bytes from {:#x}".format(
                int(error.args[0]), count, address
            )
        ) from error


def read_u16(memory: Mapping[int, int], address: int) -> int:
    return struct.unpack("<H", read_bytes(memory, address, 2))[0]


def read_u32(memory: Mapping[int, int], address: int) -> int:
    return struct.unpack("<I", read_bytes(memory, address, 4))[0]


def read_i32(memory: Mapping[int, int], address: int) -> int:
    return struct.unpack("<i", read_bytes(memory, address, 4))[0]


def read_u64(memory: Mapping[int, int], address: int) -> int:
    return struct.unpack("<Q", read_bytes(memory, address, 8))[0]


def relative_target(memory: Mapping[int, int], address: int) -> int:
    return address + read_i32(memory, address)


def read_c_string(memory: Mapping[int, int], address: int, limit: int = 256) -> str:
    values: List[int] = []
    for index in range(limit):
        value = memory.get(address + index)
        if value is None:
            raise AnalysisError("unterminated or unmapped string at {:#x}".format(address))
        if value == 0:
            try:
                return bytes(values).decode("utf-8")
            except UnicodeDecodeError as error:
                raise AnalysisError("non-UTF-8 string at {:#x}".format(address)) from error
        values.append(value)
    raise AnalysisError("overlong string at {:#x}".format(address))


def parse_descriptor(
    memory: Mapping[int, int],
    field_section: Section,
    type_labels: Mapping[int, str],
    address: int,
) -> Optional[Descriptor]:
    try:
        flags = read_u32(memory, address)
        if flags & 0x1F != STRUCT_CONTEXT_KIND:
            return None
        name = read_c_string(memory, relative_target(memory, address + 8))
        if IDENTIFIER.fullmatch(name) is None:
            return None
        field_descriptor_address = relative_target(memory, address + 16)
        field_count = read_u32(memory, address + 20)
        field_offset_vector_words = read_u32(memory, address + 24)
        if field_count > 128 or field_offset_vector_words > 128:
            return None
        if field_count == 0:
            return Descriptor(
                address=address,
                name=name,
                flags=flags,
                field_descriptor_address=field_descriptor_address,
                field_offset_vector_words=field_offset_vector_words,
                fields=(),
            )
        if not field_section.start <= field_descriptor_address < field_section.end:
            return None
        record_size = read_u16(memory, field_descriptor_address + 10)
        descriptor_field_count = read_u32(memory, field_descriptor_address + 12)
        if record_size < 12 or descriptor_field_count != field_count:
            return None
        fields: List[Field] = []
        record_address = field_descriptor_address + 16
        for _ in range(field_count):
            type_address = relative_target(memory, record_address + 4)
            field_name = read_c_string(memory, relative_target(memory, record_address + 8))
            if IDENTIFIER.fullmatch(field_name) is None:
                return None
            fields.append(
                Field(
                    name=field_name,
                    flags=read_u32(memory, record_address),
                    type_reference_address=type_address,
                    type_reference=type_labels.get(type_address),
                )
            )
            record_address += record_size
        return Descriptor(
            address=address,
            name=name,
            flags=flags,
            field_descriptor_address=field_descriptor_address,
            field_offset_vector_words=field_offset_vector_words,
            fields=tuple(fields),
        )
    except AnalysisError:
        return None


def scan_descriptors(
    constg_section: Section,
    memory: Mapping[int, int],
    field_section: Section,
    type_labels: Mapping[int, str],
) -> Tuple[Descriptor, ...]:
    descriptors: List[Descriptor] = []
    address = (constg_section.start + 3) & ~3
    while address + 28 <= constg_section.end:
        descriptor = parse_descriptor(memory, field_section, type_labels, address)
        if descriptor is not None:
            descriptors.append(descriptor)
        address += 4
    if not descriptors:
        raise AnalysisError("no Swift struct descriptors were decoded")
    return tuple(descriptors)


def infer_shared_cache_slide(
    auth_section: Section,
    memory: Mapping[int, int],
    descriptors: Sequence[Descriptor],
) -> Tuple[int, int]:
    descriptor_addresses = {descriptor.address for descriptor in descriptors}
    counts: Counter[int] = Counter()
    address = (auth_section.start + 7) & ~7
    while address + 16 <= auth_section.end:
        if read_u64(memory, address) == STRUCT_METADATA_KIND:
            runtime_descriptor = read_u64(memory, address + 8)
            for descriptor_address in descriptor_addresses:
                slide = runtime_descriptor - descriptor_address
                if 0 <= slide < 0x40000000 and slide & 0xFFF == 0:
                    counts[slide] += 1
        address += 8
    if not counts:
        raise AnalysisError("could not infer the dyld shared-cache slide")
    slide, match_count = counts.most_common(1)[0]
    if match_count < 2:
        raise AnalysisError("shared-cache slide has fewer than two metadata matches")
    return slide, match_count


def metadata_for_descriptor(
    auth_section: Section,
    memory: Mapping[int, int],
    descriptor: Descriptor,
    slide: int,
) -> Optional[Mapping[str, object]]:
    target = descriptor.address + slide
    matches: List[int] = []
    address = (auth_section.start + 7) & ~7
    while address + 16 <= auth_section.end:
        if (
            read_u64(memory, address) == STRUCT_METADATA_KIND
            and read_u64(memory, address + 8) == target
        ):
            matches.append(address)
        address += 8
    if not matches:
        return None
    if len(matches) != 1:
        raise AnalysisError(
            "descriptor {} has {} static metadata matches".format(
                descriptor.name, len(matches)
            )
        )
    metadata_address = matches[0]
    offsets_address = metadata_address + descriptor.field_offset_vector_words * 8
    field_offsets = [
        read_u32(memory, offsets_address + index * 4)
        for index in range(len(descriptor.fields))
    ]
    runtime_vwt_address = read_u64(memory, metadata_address - 8)
    vwt_address = runtime_vwt_address - slide
    if not auth_section.start <= vwt_address < auth_section.end:
        return {
            "metadataAddress": "0x{:x}".format(metadata_address),
            "metadataDescriptorRuntimeAddress": "0x{:x}".format(target),
            "valueWitnessTableAddress": "0x{:x}".format(vwt_address),
            "valueWitnessTableMapped": False,
            "size": None,
            "stride": None,
            "valueWitnessFlags": None,
            "extraInhabitantCount": None,
            "fieldOffsets": field_offsets,
        }
    size = read_u64(memory, vwt_address + 64)
    stride = read_u64(memory, vwt_address + 72)
    value_witness_flags = read_u32(memory, vwt_address + 80)
    extra_inhabitant_count = read_u32(memory, vwt_address + 84)
    if any(offset >= size for offset in field_offsets):
        raise AnalysisError("field offset exceeds value size for {}".format(descriptor.name))
    if field_offsets != sorted(field_offsets):
        raise AnalysisError("field offsets are not monotonic for {}".format(descriptor.name))
    return {
        "metadataAddress": "0x{:x}".format(metadata_address),
        "metadataDescriptorRuntimeAddress": "0x{:x}".format(target),
        "valueWitnessTableAddress": "0x{:x}".format(vwt_address),
        "valueWitnessTableMapped": True,
        "size": size,
        "stride": stride,
        "valueWitnessFlags": "0x{:08x}".format(value_witness_flags),
        "extraInhabitantCount": extra_inhabitant_count,
        "fieldOffsets": field_offsets,
    }


def descriptor_record(
    descriptor: Descriptor,
    metadata: Optional[Mapping[str, object]],
) -> Mapping[str, object]:
    offsets: Sequence[Optional[int]]
    if metadata is None:
        offsets = [None] * len(descriptor.fields)
    else:
        offsets = list(metadata["fieldOffsets"])  # type: ignore[arg-type]
    return {
        "name": descriptor.name,
        "descriptorAddress": "0x{:x}".format(descriptor.address),
        "descriptorFlags": "0x{:08x}".format(descriptor.flags),
        "fieldDescriptorAddress": "0x{:x}".format(
            descriptor.field_descriptor_address
        ),
        "fieldOffsetVectorWords": descriptor.field_offset_vector_words,
        "fields": [
            {
                "name": field.name,
                "flags": "0x{:08x}".format(field.flags),
                "offset": offset,
                "typeReferenceAddress": "0x{:x}".format(
                    field.type_reference_address
                ),
                "typeReference": field.type_reference,
            }
            for field, offset in zip(descriptor.fields, offsets)
        ],
        "metadata": metadata,
    }


def select_nested_types(
    target: Descriptor,
    target_metadata: Mapping[str, object],
    candidates: Mapping[str, Sequence[Tuple[Descriptor, Optional[Mapping[str, object]]]]],
) -> Tuple[Mapping[str, Mapping[str, object]], Sequence[Mapping[str, object]]]:
    target_offsets = list(target_metadata["fieldOffsets"])  # type: ignore[arg-type]
    target_size = int(target_metadata["size"])
    selected: Dict[str, Mapping[str, object]] = {}
    semantic_layout: List[Mapping[str, object]] = [
        {
            "path": "layerIndex",
            "absoluteOffset": target_offsets[0],
            "typeReference": target.fields[0].type_reference,
        }
    ]
    for index, field in enumerate(target.fields[1:], start=1):
        type_name = TOP_LEVEL_NESTED_TYPES[field.name]
        start = target_offsets[index]
        end = target_offsets[index + 1] if index + 1 < len(target_offsets) else target_size
        storage_byte_count = end - start
        type_candidates = list(candidates[type_name])
        fitting = [
            item
            for item in type_candidates
            if item[1] is not None
            and (
                item[1]["size"] is None
                or int(item[1]["size"]) <= storage_byte_count
            )
        ]
        if len(fitting) != 1:
            raise AnalysisError(
                "{} has {} nested candidates fitting {} bytes".format(
                    field.name, len(fitting), storage_byte_count
                )
            )
        descriptor, metadata = fitting[0]
        assert metadata is not None
        record = dict(descriptor_record(descriptor, metadata))
        record["enclosingField"] = field.name
        record["enclosingOffset"] = start
        record["enclosingStorageByteCount"] = storage_byte_count
        selected[field.name] = record
        child_offsets = list(metadata["fieldOffsets"])  # type: ignore[arg-type]
        for child, child_offset in zip(descriptor.fields, child_offsets):
            semantic_layout.append(
                {
                    "path": "{}.{}".format(field.name, child.name),
                    "absoluteOffset": start + child_offset,
                    "relativeOffset": child_offset,
                    "typeReference": child.type_reference,
                }
            )
    semantic_layout.sort(key=lambda item: (int(item["absoluteOffset"]), str(item["path"])))
    return selected, semantic_layout


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value & (sign - 1)) - (value & sign)


def parse_text_evidence(output: str) -> TextEvidence:
    target_set = {start for start, _ in CODE_REGIONS.values()}
    callsites: Dict[int, List[str]] = {target: [] for target in target_set}
    region_memory: Dict[str, Dict[int, int]] = {
        name: {} for name in CODE_REGIONS
    }
    section_start: Optional[int] = None
    section_end: Optional[int] = None
    for line in output.splitlines():
        match = BYTE_LINE.match(line)
        if match is None:
            continue
        address = int(match.group(1), 16)
        octets = bytes.fromhex(match.group(2))
        if section_start is None:
            section_start = address
        section_end = address + len(octets)
        for offset in range(0, len(octets) - 3, 4):
            instruction_address = address + offset
            instruction = struct.unpack_from("<I", octets, offset)[0]
            if instruction & 0xFC000000 == 0x94000000:
                destination = instruction_address + sign_extend(
                    instruction & 0x03FFFFFF, 26
                ) * 4
                if destination in target_set:
                    callsites[destination].append(
                        "0x{:x}".format(instruction_address)
                    )
        line_end = address + len(octets)
        for name, (start, end) in CODE_REGIONS.items():
            overlap_start = max(address, start)
            overlap_end = min(line_end, end)
            for byte_address in range(overlap_start, overlap_end):
                region_memory[name][byte_address] = octets[byte_address - address]
    if section_start is None or section_end is None:
        raise AnalysisError("dyld_info returned no (__TEXT,__text) bytes")
    code: Dict[str, bytes] = {}
    for name, (start, end) in CODE_REGIONS.items():
        if set(region_memory[name]) != set(range(start, end)):
            raise AnalysisError("incomplete code region " + name)
        code[name] = bytes(region_memory[name][address] for address in range(start, end))
    return TextEvidence(
        code=code,
        direct_bl_callsites=callsites,
        section_start=section_start,
        section_end=section_end,
    )


def analyze() -> Mapping[str, object]:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise AnalysisError("analysis requires native arm64 macOS")
    if not DYLD_INFO.is_file():
        raise AnalysisError("Command Line Tools dyld_info is missing")
    product_version = command_output(("/usr/bin/sw_vers", "-productVersion"))
    build_version = command_output(("/usr/bin/sw_vers", "-buildVersion"))
    if (
        product_version != EXPECTED_MACOS_PRODUCT_VERSION
        or build_version != EXPECTED_MACOS_BUILD_VERSION
    ):
        raise AnalysisError("macOS product or build version differs from the frozen target")

    uuid_output = run_dyld_info(("-uuid",))
    uuid_match = re.search(r"UUID: ([0-9A-F-]{36})", uuid_output)
    if uuid_match is None:
        uuid_match = re.search(r"\b([0-9A-F]{8}(?:-[0-9A-F]{4}){3}-[0-9A-F]{12})\b", uuid_output)
    if uuid_match is None or uuid_match.group(1) != EXPECTED_UUID:
        raise AnalysisError("DesignLibrary UUID differs from the frozen target")

    section_specs = (
        ("__TEXT", "__const"),
        ("__TEXT", "__constg_swiftt"),
        ("__TEXT", "__swift5_reflstr"),
        ("__TEXT", "__swift5_typeref"),
        ("__TEXT", "__swift5_fieldmd"),
        ("__AUTH_CONST", "__const"),
    )
    sections: Dict[Tuple[str, str], Section] = {}
    for segment, name in section_specs:
        sections[(segment, name)] = parse_section_bytes(
            segment,
            name,
            run_dyld_info(("-section_bytes", segment, name)),
        )
    memory = merged_memory(sections.values())
    type_labels = parse_type_labels(
        run_dyld_info(("-section", "__TEXT", "__swift5_typeref"))
    )
    descriptors = scan_descriptors(
        sections[("__TEXT", "__constg_swiftt")],
        memory,
        sections[("__TEXT", "__swift5_fieldmd")],
        type_labels,
    )
    target_matches = [
        descriptor
        for descriptor in descriptors
        if descriptor.name == TARGET_TYPE
        and tuple(field.name for field in descriptor.fields) == TARGET_FIELDS
    ]
    if len(target_matches) != 1:
        raise AnalysisError(
            "expected one exact BackgroundFilter descriptor, found {}".format(
                len(target_matches)
            )
        )
    target = target_matches[0]
    slide, slide_match_count = infer_shared_cache_slide(
        sections[("__AUTH_CONST", "__const")], memory, descriptors
    )
    target_metadata = metadata_for_descriptor(
        sections[("__AUTH_CONST", "__const")], memory, target, slide
    )
    if target_metadata is None:
        raise AnalysisError("BackgroundFilter has no static metadata record")
    if target_metadata["size"] != 0x1F8 or target_metadata["stride"] != 0x1F8:
        raise AnalysisError("BackgroundFilter size or stride differs from 0x1f8")
    if target_metadata["fieldOffsets"] != [0, 8, 0x98, 0xE0, 0x114, 0x160, 0x1D0, 0x1F0]:
        raise AnalysisError("BackgroundFilter field offsets differ from the frozen trace")

    nested: Dict[str, List[Mapping[str, object]]] = {}
    nested_descriptors: Dict[
        str, List[Tuple[Descriptor, Optional[Mapping[str, object]]]]
    ] = {}
    for type_name in NESTED_TYPES:
        matches = [descriptor for descriptor in descriptors if descriptor.name == type_name]
        nested_descriptors[type_name] = [
            (
                descriptor,
                metadata_for_descriptor(
                    sections[("__AUTH_CONST", "__const")],
                    memory,
                    descriptor,
                    slide,
                ),
            )
            for descriptor in matches
        ]
        nested[type_name] = [
            descriptor_record(descriptor, metadata)
            for descriptor, metadata in nested_descriptors[type_name]
        ]
    selected_nested, semantic_layout = select_nested_types(
        target, target_metadata, nested_descriptors
    )
    auxiliary_types: Dict[str, Mapping[str, object]] = {}
    for type_name, field_names, expected_size in (
        ("YCC", YCC_FIELDS, 69),
        ("FaceEffectDimming", FACE_EFFECT_DIMMING_FIELDS, 24),
    ):
        matches = [
            descriptor
            for descriptor in descriptors
            if descriptor.name == type_name
            and tuple(field.name for field in descriptor.fields) == field_names
        ]
        if len(matches) != 1:
            raise AnalysisError("expected one exact {} descriptor".format(type_name))
        metadata = metadata_for_descriptor(
            sections[("__AUTH_CONST", "__const")], memory, matches[0], slide
        )
        if metadata is None or metadata["size"] != expected_size:
            raise AnalysisError("{} metadata size differs".format(type_name))
        auxiliary_types[type_name] = descriptor_record(matches[0], metadata)
    parameter_descriptors = [
        descriptor
        for descriptor in descriptors
        if descriptor.name == "Parameters"
        and tuple(field.name for field in descriptor.fields) == PARAMETERS_FIELDS
    ]
    if len(parameter_descriptors) != 1:
        raise AnalysisError(
            "expected one exact GlassMaterialProvider.Parameters descriptor"
        )
    parameters_descriptor = parameter_descriptors[0]
    parameters_metadata = metadata_for_descriptor(
        sections[("__AUTH_CONST", "__const")],
        memory,
        parameters_descriptor,
        slide,
    )
    if parameters_metadata is None:
        raise AnalysisError("Parameters has no static metadata record")
    if parameters_metadata["size"] != 0x401 or parameters_metadata["stride"] != 0x408:
        raise AnalysisError("Parameters size or stride differs from the frozen code")

    text_evidence = parse_text_evidence(
        run_dyld_info(("-section_bytes", "__TEXT", "__text"))
    )
    code_regions: Dict[str, Mapping[str, object]] = {}
    for name, (start, end) in CODE_REGIONS.items():
        code = text_evidence.code[name]
        code_regions[name] = {
            "start": "0x{:x}".format(start),
            "end": "0x{:x}".format(end),
            "byteCount": len(code),
            "sha256": hashlib.sha256(code).hexdigest(),
            "directBLCallsites": list(text_evidence.direct_bl_callsites[start]),
        }

    source_path = Path(__file__).resolve()
    return {
        "designLibraryBackgroundFilterMetadataAnalysisSchemaVersion": 1,
        "classification": (
            "native static Swift metadata decode; no Apple render value, image, crop, "
            "margin, or provider return selected any descriptor"
        ),
        "host": {
            "system": platform.system(),
            "machine": platform.machine(),
            "macOSProductVersion": product_version,
            "macOSBuildVersion": build_version,
            "hardwareModel": command_output(("/usr/sbin/sysctl", "-n", "hw.model")),
        },
        "framework": {
            "path": str(FRAMEWORK),
            "uuid": EXPECTED_UUID,
        },
        "tool": {
            "dyldInfo": str(DYLD_INFO),
            "python": sys.version.split()[0],
            "source": SOURCE_RELATIVE_PATH,
            "sourceSHA256": sha256(source_path),
        },
        "sharedCacheSlide": "0x{:x}".format(slide),
        "sharedCacheSlideMetadataMatchCount": slide_match_count,
        "decodedStructDescriptorCount": len(descriptors),
        "backgroundFilter": descriptor_record(target, target_metadata),
        "nestedTypeCandidates": nested,
        "selectedNestedTypes": selected_nested,
        "selectedAuxiliaryTypes": auxiliary_types,
        "semanticLayout": semantic_layout,
        "parameters": descriptor_record(parameters_descriptor, parameters_metadata),
        "codeRegions": code_regions,
        "constructorABI": {
            "output": "x8 -> BackgroundFilter (504 bytes)",
            "source": "x0 -> GlassMaterialProvider.Parameters",
            "layerIndex": "x1 -> BackgroundFilter.layerIndex",
            "environmentFlags": "x2 -> BackgroundFilter.flags.rawValue",
            "terminalWriteStart": "0x24091bfb8",
            "terminalWriteEndExclusive": "0x24091c0ec",
        },
        "claims": {
            "concreteProviderPayloadType": (
                "DesignLibrary.GlassMaterialProvider.BackgroundFilter"
            ),
            "captured384BytesWerePrefixOnly": True,
            "completePayloadByteCount": 0x1F8,
            "parametersLayoutRecovered": True,
            "constructorInputBoundaryRecovered": True,
            "publicInputConstructionRecovered": False,
            "cropAllocationPolicyRecovered": False,
            "liquidGlassParityEstablished": False,
            "productionShaderChangeAuthorized": False,
        },
    }


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    try:
        result = analyze()
    except AnalysisError as error:
        print(str(error), file=sys.stderr)
        return 1
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        sys.stdout.write(encoded)
    else:
        arguments.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
