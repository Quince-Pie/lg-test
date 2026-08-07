#!/usr/bin/env python3
"""Authenticate and exhaustively validate Configuration flag-seed production."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple


SCHEMA_VERSION = 1
EXPECTED_PRODUCT_VERSION = "26.6.1"
EXPECTED_BUILD_VERSION = "25G76"
EXPECTED_HARDWARE_MODEL = "MacBookPro18,2"
EXPECTED_FRAMEWORK_UUID = "1E980802-69F5-3E69-89EF-50088297FCF5"
FRAMEWORK = Path(
    "/System/Library/PrivateFrameworks/DesignLibrary.framework/Versions/A/"
    "DesignLibrary"
)
DYLD_INFO = Path("/Library/Developer/CommandLineTools/usr/bin/dyld_info")
XCRUN = Path("/usr/bin/xcrun")

SOURCE_NAME = "probe_designlibrary_configuration_flag_seed_local_macos_26_6_1.c"
BRIDGE_NAME = "invoke_designlibrary_configuration_flag_seed_arm64.S"
PUBLIC_BRIDGE_NAME = "invoke_designlibrary_public_configuration_resolution_arm64.S"

HELPER_START = 0x240974E60
HELPER_END = 0x240975028
HELPER_SHA256 = "ac4057c8edc1ffa817b6a1dc9693d2b9ef95650ab9b70223a98e00642b5c8076"
MIX_METADATA_ACCESSOR_START = 0x240912FE0
MIX_METADATA_ACCESSOR_END = 0x240913000
MIX_METADATA_ACCESSOR_SHA256 = (
    "b9fda459e045c61886dd72ab311a8edf74c62e1cb72913f8f79bef50e88ed86b"
)
PROJECTOR_STUB_START = 0x2409A5CD0
PROJECTOR_STUB_END = 0x2409A5CE0
PROJECTOR_STUB_SHA256 = (
    "0f34a958e6e6dd9580d38018a9dacd58477f007093fd695020c19a398c1ee166"
)
MIX_DESCRIPTOR = 0x2409D2188
MIX_FIELD_DESCRIPTOR = 0x2409D6C94

CONFIGURATION_BYTES = 144
MIX_BYTES = 296
MIX_ALLOCATION_BYTES = 320
REGULAR_BASE = 0xC000000000000000
CLEAR_BASE = 0xC000000000000008
DISPLAY_ANGLE = 0x0002
ADAPTIVE = 0x4000
EXTERNAL_LUMINANCE = 0x8000
NOISE_OPTIONS = 0x009F327D

STATIC_NAMES = (
    "regular",
    "clear",
    "control",
    "text",
    "identity",
    "menu",
    "dock",
    "appIcons",
    "widgets",
    "avplayer",
    "facetime",
    "controlCenter",
    "notificationCenter",
    "monogram",
    "bubbles",
    "focusBorder",
    "focusPlatter",
    "keyboard",
    "sidebar",
    "abuttedSidebar",
    "inspector",
    "loupe",
    "slider",
    "camera",
    "cartouchePopover",
    "siriSnippet",
    "carplayUltra",
)
EXTRA_PUBLIC_NAMES = (
    "regular_entryField",
    "clear_watchPasscode",
    "text_watchFacePhotos",
    "regular_external_true",
    "regular_external_false",
    "clear_external_true",
    "clear_external_false",
    "regular_adaptive_false",
    "nested_source_regular_clear",
)
EXPECTED_SUBVARIANTS = {
    "entryField": 12,
    "watchFacePhotos": 15,
    "watchPasscode": 20,
}
DIRECT_KINDS = (
    "regular_inline",
    "clear_inline",
    "other_inline",
    "text_reference",
    "focus_reference",
)

BYTE_LINE = re.compile(r"^0x([0-9A-Fa-f]+):((?: [0-9A-Fa-f]{2})+)\s*$")
INSTRUCTION_LINE = re.compile(
    r"^0x([0-9A-Fa-f]+)\s+([a-z0-9.]+)(?:\s+(.*?))?\s*$"
)
TYPE_PATTERN = re.compile(
    r"^TYPE Mix size=(\d+) stride=(\d+) flags=0x([0-9a-f]+) "
    r"extra_inhabitants=(\d+) offsets=(\d+),(\d+),(\d+)$"
)
PUBLIC_PATTERN = re.compile(
    r"^PUBLIC name=(\S+) base=0x([0-9a-f]{16}) subvariant=(\d+) "
    r"options=0x([0-9a-f]{16}) result=0x([0-9a-f]{16}) "
    r"bytes=([0-9a-f]+)$"
)
SUBVARIANT_PATTERN = re.compile(r"^SUBVARIANT name=(\S+) storage=(\d+)$")
MIX_PATTERN = re.compile(
    r"^MIX case=(\S+) from=(\S+) to=(\S+) "
    r"fraction_bits=0x([0-9a-f]{16}) "
    r"outer_options=0x([0-9a-f]{16}) result=0x([0-9a-f]{16}) "
    r"allocation=(\d+) payload=([0-9a-f]+)$"
)
DIRECT_PATTERN = re.compile(
    r"^DIRECT kind=(\S+) subvariant=(\d+) "
    r"options=0x([0-9a-f]{16}) result=0x([0-9a-f]{16})$"
)
INDIRECT_PATTERN = re.compile(
    r"^INDIRECT from=0x([0-9a-f]{16}) to=0x([0-9a-f]{16}) "
    r"outer=0x([0-9a-f]{16}) result=0x([0-9a-f]{16})$"
)

EXPECTED_INSTRUCTIONS = {
    0x240974EC0: ("ldr", "x22, [x20, #0x28]"),
    0x240974EC4: ("str", "x22, [x19]"),
    0x240974EC8: ("ldr", "x9, [x20]"),
    0x240974ECC: ("ldrb", "w8, [x20, #0x9]"),
    0x240974ED0: ("lsr", "x10, x9, #62"),
    0x240974EE0: ("sub", "w8, w8, #0x13"),
    0x240974EE4: ("and", "x9, x22, #0x2"),
    0x240974EE8: ("cmn", "w8, #0x4"),
    0x240974EEC: ("ccmp", "x9, #0x0, #0x4, hs"),
    0x240974EF4: ("and", "x8, x22, #0xfffffffffffffffd"),
    0x240974F08: ("and", "x0, x9, #0x3fffffffffffffff"),
    0x240974F30: ("ldr", "x9, [x21, #0x28]"),
    0x240974F34: ("tbnz", "w9, #0xe, 0x240974f48"),
    0x240974F38: ("ldrsw", "x10, [x8, #0x14]"),
    0x240974F3C: ("add", "x10, x21, x10"),
    0x240974F40: ("ldrb", "w10, [x10, #0x29]"),
    0x240974F44: ("tbz", "w10, #0x6, 0x240974f50"),
    0x240974F48: ("orr", "x22, x22, #0x4000"),
    0x240974F50: ("tbz", "w9, #0xf, 0x240974f6c"),
    0x240974F54: ("ldrsw", "x10, [x8, #0x14]"),
    0x240974F5C: ("ldrb", "w10, [x10, #0x29]"),
    0x240974F60: ("tbz", "w10, #0x7, 0x240974f6c"),
    0x240974F64: ("orr", "x22, x22, #0x8000"),
    0x240974F6C: ("tbnz", "w9, #0x1, 0x240974fdc"),
    0x240974F70: ("ldrsw", "x8, [x8, #0x14]"),
    0x240974F74: ("add", "x8, x21, x8"),
    0x240974F78: ("ldr", "x20, [x8, #0x28]"),
    0x240974F98: ("tbnz", "w20, #0x1, 0x240974ff8"),
    0x240974FA0: ("mov", "x10, #-0x4000000000000000"),
    0x240974FA4: ("cmp", "x9, x10"),
    0x240974FAC: ("mov", "x10, #0x8"),
    0x240974FB0: ("movk", "x10, #0xc000, lsl #48"),
    0x240974FBC: ("cmp", "w8, #0x14"),
    0x240974FC4: ("cmp", "w8, #0x8"),
    0x240974FCC: ("cmp", "w8, #0x1"),
    0x240974FD4: ("orr", "x8, x22, #0x4000"),
    0x240974FF8: ("orr", "x8, x22, #0x2"),
    0x240975014: ("cmp", "w8, #0xc"),
    0x24097501C: ("tbz", "w22, #0xe, 0x240975000"),
    0x240975020: ("and", "x8, x22, #0xffffffffffffbfff"),
}


class CaptureError(RuntimeError):
    """Raised when native evidence differs from the frozen contract."""


def command_output(arguments: Sequence[str], cwd: Optional[Path] = None) -> str:
    completed = subprocess.run(
        list(arguments),
        cwd=str(cwd) if cwd is not None else None,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise CaptureError(
            "command failed ({0}): {1}\n{2}".format(
                completed.returncode,
                " ".join(arguments),
                completed.stderr.strip(),
            )
        )
    return completed.stdout


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def digest_json(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def section_memory(section: str) -> Mapping[int, int]:
    output = command_output(
        (str(DYLD_INFO), "-section_bytes", "__TEXT", section, str(FRAMEWORK))
    )
    memory: Dict[int, int] = {}
    for line in output.splitlines():
        match = BYTE_LINE.fullmatch(line)
        if match is None:
            continue
        address = int(match.group(1), 16)
        for index, value in enumerate(bytes.fromhex(match.group(2))):
            byte_address = address + index
            if byte_address in memory:
                raise CaptureError("duplicate byte in " + section)
            memory[byte_address] = value
    if not memory:
        raise CaptureError(section + " section is empty")
    return memory


def read_bytes(memory: Mapping[int, int], start: int, end: int) -> bytes:
    try:
        return bytes(memory[address] for address in range(start, end))
    except KeyError as error:
        raise CaptureError("missing section byte at {0:#x}".format(error.args[0]))


def read_integer(memory: Mapping[int, int], address: int, fmt: str) -> int:
    size = struct.calcsize(fmt)
    return int(struct.unpack(fmt, read_bytes(memory, address, address + size))[0])


def read_cstring(memory: Mapping[int, int], address: int) -> str:
    output = bytearray()
    for offset in range(256):
        try:
            value = memory[address + offset]
        except KeyError as error:
            raise CaptureError("string crosses an unavailable section") from error
        if value == 0:
            return output.decode("utf-8")
        output.append(value)
    raise CaptureError("unterminated metadata string")


def parse_instructions(output: str) -> Mapping[int, Tuple[str, str]]:
    instructions: Dict[int, Tuple[str, str]] = {}
    for line in output.splitlines():
        match = INSTRUCTION_LINE.fullmatch(line)
        if match is None:
            continue
        address = int(match.group(1), 16)
        if not HELPER_START <= address < HELPER_END:
            continue
        operands = (match.group(3) or "").split(";", 1)[0].strip().lower()
        instructions[address] = (match.group(2).lower(), operands)
    return instructions


def decode_bl_target(address: int, word: int) -> int:
    if word & 0xFC000000 != 0x94000000:
        raise CaptureError("expected arm64 BL at {0:#x}".format(address))
    immediate = word & 0x03FFFFFF
    if immediate & (1 << 25):
        immediate -= 1 << 26
    return address + immediate * 4


def static_evidence() -> Mapping[str, object]:
    text = section_memory("__text")
    auth_stubs = section_memory("__auth_stubs")
    constg = section_memory("__constg_swiftt")
    fieldmd = section_memory("__swift5_fieldmd")
    reflstr = section_memory("__swift5_reflstr")
    constants = section_memory("__const")

    helper = read_bytes(text, HELPER_START, HELPER_END)
    if hashlib.sha256(helper).hexdigest() != HELPER_SHA256:
        raise CaptureError("Configuration flag-seed helper code differs")
    metadata_accessor = read_bytes(
        text,
        MIX_METADATA_ACCESSOR_START,
        MIX_METADATA_ACCESSOR_END,
    )
    if hashlib.sha256(metadata_accessor).hexdigest() != MIX_METADATA_ACCESSOR_SHA256:
        raise CaptureError("Mix metadata accessor code differs")
    projector_stub = read_bytes(
        auth_stubs,
        PROJECTOR_STUB_START,
        PROJECTOR_STUB_END,
    )
    if hashlib.sha256(projector_stub).hexdigest() != PROJECTOR_STUB_SHA256:
        raise CaptureError("swift_projectBox stub code differs")

    instructions = parse_instructions(
        command_output((str(DYLD_INFO), "-disassemble", str(FRAMEWORK)))
    )
    expected_addresses = set(range(HELPER_START, HELPER_END, 4))
    if set(instructions) != expected_addresses:
        raise CaptureError("flag-seed disassembly coverage differs")
    for address, expected in EXPECTED_INSTRUCTIONS.items():
        if instructions.get(address) != expected:
            raise CaptureError(
                "flag-seed instruction differs at {0:#x}: {1!r}".format(
                    address,
                    instructions.get(address),
                )
            )
    call_word = struct.unpack_from("<I", helper, 0xAC)[0]
    if decode_bl_target(HELPER_START + 0xAC, call_word) != PROJECTOR_STUB_START:
        raise CaptureError("indirect-base projector call target differs")

    descriptor_flags = read_integer(constg, MIX_DESCRIPTOR, "<I")
    descriptor_name_address = MIX_DESCRIPTOR + 8 + read_integer(
        constg,
        MIX_DESCRIPTOR + 8,
        "<i",
    )
    field_descriptor_address = MIX_DESCRIPTOR + 16 + read_integer(
        constg,
        MIX_DESCRIPTOR + 16,
        "<i",
    )
    field_count = read_integer(constg, MIX_DESCRIPTOR + 20, "<I")
    field_offset_vector_words = read_integer(
        constg,
        MIX_DESCRIPTOR + 24,
        "<I",
    )
    if (
        descriptor_flags & 0x1F != 0x11
        or read_cstring(constants, descriptor_name_address) != "Mix"
        or field_descriptor_address != MIX_FIELD_DESCRIPTOR
        or field_count != 3
        or field_offset_vector_words != 2
    ):
        raise CaptureError("Mix context descriptor differs")

    record_size = read_integer(fieldmd, MIX_FIELD_DESCRIPTOR + 10, "<H")
    described_count = read_integer(fieldmd, MIX_FIELD_DESCRIPTOR + 12, "<I")
    if record_size != 12 or described_count != 3:
        raise CaptureError("Mix field descriptor header differs")
    field_names: List[str] = []
    for index in range(described_count):
        record = MIX_FIELD_DESCRIPTOR + 16 + index * record_size
        name_address = record + 8 + read_integer(fieldmd, record + 8, "<i")
        field_names.append(read_cstring(reflstr, name_address))
    if field_names != ["from", "to", "fraction"]:
        raise CaptureError("Mix field names differ")

    return {
        "flagSeedHelper": {
            "start": "0x{0:x}".format(HELPER_START),
            "endExclusive": "0x{0:x}".format(HELPER_END),
            "byteCount": len(helper),
            "instructionCount": len(helper) // 4,
            "sha256": HELPER_SHA256,
            "criticalInstructionCount": len(EXPECTED_INSTRUCTIONS),
        },
        "mixMetadataAccessor": {
            "start": "0x{0:x}".format(MIX_METADATA_ACCESSOR_START),
            "endExclusive": "0x{0:x}".format(MIX_METADATA_ACCESSOR_END),
            "sha256": MIX_METADATA_ACCESSOR_SHA256,
        },
        "projectorStub": {
            "start": "0x{0:x}".format(PROJECTOR_STUB_START),
            "endExclusive": "0x{0:x}".format(PROJECTOR_STUB_END),
            "sha256": PROJECTOR_STUB_SHA256,
            "runtimeBinding": "swift_projectBox",
        },
        "mixDescriptor": {
            "address": "0x{0:x}".format(MIX_DESCRIPTOR),
            "name": "Mix",
            "fieldNames": field_names,
            "fieldCount": field_count,
            "fieldOffsetVectorWords": field_offset_vector_words,
        },
    }


def expected_direct(base: int, subvariant: int, options: int) -> int:
    tag = base >> 62
    if tag == 0:
        if 15 <= subvariant <= 18:
            return options & ~DISPLAY_ANGLE
        return options
    if tag == 2:
        raise ValueError("indirect Mix requires both endpoint options")
    if tag != 3:
        return options
    if base == REGULAR_BASE and subvariant == 12:
        return options & ~ADAPTIVE
    if base == CLEAR_BASE:
        if subvariant in (1, 20):
            return options | ADAPTIVE
        if subvariant == 8:
            return options | DISPLAY_ANGLE
    return options


def expected_mix(from_options: int, to_options: int, outer_options: int) -> int:
    result = outer_options
    result |= (from_options | to_options) & (DISPLAY_ANGLE | ADAPTIVE)
    result |= (from_options & to_options) & EXTERNAL_LUMINANCE
    return result


def option_variants() -> Tuple[int, ...]:
    return tuple(
        NOISE_OPTIONS
        | (DISPLAY_ANGLE if index & 1 else 0)
        | (ADAPTIVE if index & 2 else 0)
        | (EXTERNAL_LUMINANCE if index & 4 else 0)
        for index in range(8)
    )


def parse_common(
    line: str,
    runtime: Dict[str, object],
) -> bool:
    match = TYPE_PATTERN.fullmatch(line)
    if match is not None:
        if runtime:
            raise CaptureError("duplicate Mix runtime layout")
        runtime.update(
            {
                "size": int(match.group(1)),
                "stride": int(match.group(2)),
                "valueWitnessFlags": "0x" + match.group(3),
                "extraInhabitantCount": int(match.group(4)),
                "fieldOffsets": [
                    int(match.group(5)),
                    int(match.group(6)),
                    int(match.group(7)),
                ],
            }
        )
        return True
    if line == "PROJECTOR symbol=swift_projectBox":
        if runtime.get("projector") is not None:
            raise CaptureError("duplicate projector binding")
        runtime["projector"] = "swift_projectBox"
        return True
    return False


def validate_runtime(runtime: Mapping[str, object]) -> None:
    expected = {
        "size": 296,
        "stride": 296,
        "valueWitnessFlags": "0x00030007",
        "extraInhabitantCount": 0x7FFFFFFF,
        "fieldOffsets": [0, 144, 288],
        "projector": "swift_projectBox",
    }
    if runtime != expected:
        raise CaptureError("Mix runtime metadata differs")


def normalize_public_record(record: Mapping[str, object]) -> Mapping[str, object]:
    base = int(record["base"])
    tag = base >> 62
    return {
        "name": record["name"],
        "baseRepresentationTag": tag,
        **({"inlineBaseBits": "0x{0:016x}".format(base)} if tag == 3 else {}),
        "subvariantStorage": record["subvariant"],
        "optionsBits": "0x{0:016x}".format(int(record["options"])),
        "resultBits": "0x{0:016x}".format(int(record["result"])),
    }


def parse_public_output(output: str) -> Mapping[str, object]:
    runtime: Dict[str, object] = {}
    public: Dict[str, Dict[str, object]] = {}
    subvariants: Dict[str, int] = {}
    mixes: List[Dict[str, object]] = []
    mix_cases = set()

    for line in output.splitlines():
        if parse_common(line, runtime):
            continue
        match = PUBLIC_PATTERN.fullmatch(line)
        if match is not None:
            name = match.group(1)
            if name in public:
                raise CaptureError("duplicate public Configuration " + name)
            storage = bytes.fromhex(match.group(6))
            if len(storage) != CONFIGURATION_BYTES:
                raise CaptureError(name + " Configuration storage differs")
            record = {
                "name": name,
                "base": int(match.group(2), 16),
                "subvariant": int(match.group(3)),
                "options": int(match.group(4), 16),
                "result": int(match.group(5), 16),
                "storage": storage,
            }
            if (
                struct.unpack_from("<Q", storage, 0)[0] != record["base"]
                or storage[9] != record["subvariant"]
                or struct.unpack_from("<Q", storage, 40)[0] != record["options"]
            ):
                raise CaptureError(name + " printed fields differ from storage")
            public[name] = record
            continue
        match = SUBVARIANT_PATTERN.fullmatch(line)
        if match is not None:
            name = match.group(1)
            if name in subvariants:
                raise CaptureError("duplicate Subvariant " + name)
            subvariants[name] = int(match.group(2))
            continue
        match = MIX_PATTERN.fullmatch(line)
        if match is not None:
            case = match.group(1)
            if case in mix_cases:
                raise CaptureError("duplicate mix case " + case)
            mix_cases.add(case)
            payload = bytes.fromhex(match.group(8))
            if len(payload) != MIX_BYTES:
                raise CaptureError(case + " Mix payload differs")
            mixes.append(
                {
                    "case": case,
                    "from": match.group(2),
                    "to": match.group(3),
                    "fractionBits": int(match.group(4), 16),
                    "outerOptions": int(match.group(5), 16),
                    "result": int(match.group(6), 16),
                    "allocation": int(match.group(7)),
                    "payload": payload,
                }
            )
            continue
        raise CaptureError("unrecognized public probe output: " + line)

    validate_runtime(runtime)
    expected_public_names = set(STATIC_NAMES) | set(EXTRA_PUBLIC_NAMES)
    if set(public) != expected_public_names:
        raise CaptureError("public Configuration identities differ")
    if subvariants != EXPECTED_SUBVARIANTS:
        raise CaptureError("public Subvariant initialization differs")

    for name, record in public.items():
        base = int(record["base"])
        if base >> 62 == 2:
            if name != "nested_source_regular_clear":
                raise CaptureError("unexpected indirect public Configuration " + name)
            expected = expected_mix(
                int(public["regular"]["options"]),
                int(public["clear"]["options"]),
                int(record["options"]),
            )
        else:
            expected = expected_direct(
                base,
                int(record["subvariant"]),
                int(record["options"]),
            )
        if int(record["result"]) != expected:
            raise CaptureError(name + " direct helper result differs")

    for record in mixes:
        case = str(record["case"])
        from_name = str(record["from"])
        to_name = str(record["to"])
        if from_name not in public or to_name not in public:
            raise CaptureError(case + " references an absent public Configuration")
        payload = record["payload"]
        assert isinstance(payload, bytes)
        if (
            payload[:144] != public[from_name]["storage"]
            or payload[144:288] != public[to_name]["storage"]
            or struct.unpack_from("<Q", payload, 288)[0] != record["fractionBits"]
            or record["allocation"] != MIX_ALLOCATION_BYTES
        ):
            raise CaptureError(case + " boxed Mix payload differs")
        expected = expected_mix(
            int(public[from_name]["options"]),
            int(public[to_name]["options"]),
            int(record["outerOptions"]),
        )
        if int(record["result"]) != expected:
            raise CaptureError(case + " indirect helper result differs")

    expected_static_cases = {
        "static_{0}_{1}".format(from_name, to_name)
        for from_name in STATIC_NAMES
        for to_name in STATIC_NAMES
    }
    observed_static_cases = {
        str(record["case"])
        for record in mixes
        if str(record["case"]).startswith("static_")
    }
    if observed_static_cases != expected_static_cases:
        raise CaptureError("ordered public static Mix matrix differs")
    if len(mixes) != 741:
        raise CaptureError("public Mix case count differs")

    normalized_public = [
        normalize_public_record(public[name])
        for name in (*STATIC_NAMES, *EXTRA_PUBLIC_NAMES)
    ]
    normalized_mixes = [
        {
            "case": record["case"],
            "from": record["from"],
            "to": record["to"],
            "fractionBits": "0x{0:016x}".format(int(record["fractionBits"])),
            "fromOptionsBits": "0x{0:016x}".format(
                int(public[str(record["from"])]["options"])
            ),
            "toOptionsBits": "0x{0:016x}".format(
                int(public[str(record["to"])]["options"])
            ),
            "outerOptionsBits": "0x{0:016x}".format(
                int(record["outerOptions"])
            ),
            "resultBits": "0x{0:016x}".format(int(record["result"])),
        }
        for record in mixes
    ]
    normalized = {
        "runtime": runtime,
        "subvariants": subvariants,
        "public": normalized_public,
        "mixes": normalized_mixes,
    }
    return {
        "runtime": runtime,
        "subvariants": subvariants,
        "public": normalized_public,
        "mixes": normalized_mixes,
        "normalizedSHA256": digest_json(normalized),
    }


def base_for_kind(kind: str) -> int:
    return {
        "regular_inline": REGULAR_BASE,
        "clear_inline": CLEAR_BASE,
        "other_inline": 0xC000000000000080,
        "text_reference": 0,
        "focus_reference": 1 << 62,
    }[kind]


def parse_exhaustive_output(output: str) -> Mapping[str, object]:
    runtime: Dict[str, object] = {}
    direct: List[Tuple[str, int, int, int]] = []
    indirect: List[Tuple[int, int, int, int]] = []
    direct_keys = set()
    indirect_keys = set()

    for line in output.splitlines():
        if parse_common(line, runtime):
            continue
        match = DIRECT_PATTERN.fullmatch(line)
        if match is not None:
            record = (
                match.group(1),
                int(match.group(2)),
                int(match.group(3), 16),
                int(match.group(4), 16),
            )
            key = record[:3]
            if key in direct_keys:
                raise CaptureError("duplicate direct exhaustive case")
            direct_keys.add(key)
            direct.append(record)
            continue
        match = INDIRECT_PATTERN.fullmatch(line)
        if match is not None:
            record = tuple(int(match.group(index), 16) for index in range(1, 5))
            key = record[:3]
            if key in indirect_keys:
                raise CaptureError("duplicate indirect exhaustive case")
            indirect_keys.add(key)
            indirect.append(record)
            continue
        raise CaptureError("unrecognized exhaustive probe output: " + line)

    validate_runtime(runtime)
    variants = option_variants()
    expected_direct_keys = {
        (kind, subvariant, options)
        for kind in DIRECT_KINDS
        for subvariant in range(256)
        for options in variants
    }
    if direct_keys != expected_direct_keys or len(direct) != 10_240:
        raise CaptureError("direct exhaustive domain differs")
    for kind, subvariant, options, result in direct:
        expected = expected_direct(base_for_kind(kind), subvariant, options)
        if result != expected:
            raise CaptureError(
                "direct exhaustive result differs for {0}/{1}/{2:#x}".format(
                    kind,
                    subvariant,
                    options,
                )
            )

    expected_indirect_keys = {
        (from_options, to_options, outer_options)
        for from_options in variants
        for to_options in variants
        for outer_options in variants
    }
    if indirect_keys != expected_indirect_keys or len(indirect) != 512:
        raise CaptureError("indirect exhaustive domain differs")
    for from_options, to_options, outer_options, result in indirect:
        if result != expected_mix(from_options, to_options, outer_options):
            raise CaptureError("indirect exhaustive result differs")

    direct_normalized = [
        [kind, subvariant, "0x{0:016x}".format(options), "0x{0:016x}".format(result)]
        for kind, subvariant, options, result in direct
    ]
    indirect_normalized = [
        [
            "0x{0:016x}".format(from_options),
            "0x{0:016x}".format(to_options),
            "0x{0:016x}".format(outer_options),
            "0x{0:016x}".format(result),
        ]
        for from_options, to_options, outer_options, result in indirect
    ]
    return {
        "runtime": runtime,
        "directCaseCount": len(direct),
        "indirectCaseCount": len(indirect),
        "directStreamSHA256": digest_json(direct_normalized),
        "indirectStreamSHA256": digest_json(indirect_normalized),
        "combinedStreamSHA256": digest_json(
            {"direct": direct_normalized, "indirect": indirect_normalized}
        ),
    }


def stable_runs(
    parsed_runs: Sequence[Mapping[str, object]],
    label: str,
) -> Mapping[str, object]:
    if not parsed_runs:
        raise CaptureError(label + " has no runs")
    if any(run != parsed_runs[0] for run in parsed_runs[1:]):
        raise CaptureError(label + " semantic records vary across fresh processes")
    return parsed_runs[0]


def selected_records(
    public_evidence: Mapping[str, object],
) -> Mapping[str, object]:
    public_records = {
        str(record["name"]): record for record in public_evidence["public"]
    }
    mix_records = {
        str(record["case"]): record for record in public_evidence["mixes"]
    }
    return {
        "subvariantSpecialCases": [
            public_records[name]
            for name in (
                "regular_entryField",
                "clear_watchPasscode",
                "text_watchFacePhotos",
            )
        ],
        "optionMixCases": [
            mix_records[name]
            for name in (
                "external_both_true",
                "external_true_false",
                "adaptive_false_display_angle",
            )
        ],
        "nestedMixCases": [
            public_records["nested_source_regular_clear"],
            mix_records["nested_regular_clear_to_dock"],
            mix_records["nested_dock_to_regular_clear"],
        ],
    }


def capture(output_path: Path) -> Mapping[str, object]:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise CaptureError("capture requires native arm64 macOS")
    product_version = command_output(("/usr/bin/sw_vers", "-productVersion")).strip()
    build_version = command_output(("/usr/bin/sw_vers", "-buildVersion")).strip()
    hardware_model = command_output(("/usr/sbin/sysctl", "-n", "hw.model")).strip()
    if (
        product_version != EXPECTED_PRODUCT_VERSION
        or build_version != EXPECTED_BUILD_VERSION
        or hardware_model != EXPECTED_HARDWARE_MODEL
    ):
        raise CaptureError("host differs from the frozen target profile")
    uuid_output = command_output((str(DYLD_INFO), "-uuid", str(FRAMEWORK)))
    if EXPECTED_FRAMEWORK_UUID not in uuid_output:
        raise CaptureError("DesignLibrary UUID differs")

    static = static_evidence()
    analysis_directory = Path(__file__).resolve().parent
    source = analysis_directory / SOURCE_NAME
    bridge = analysis_directory / BRIDGE_NAME
    public_bridge = analysis_directory / PUBLIC_BRIDGE_NAME
    for path in (source, bridge, public_bridge):
        if not path.is_file():
            raise CaptureError(path.name + " is missing")

    with tempfile.TemporaryDirectory(prefix="lg-configuration-flag-seed-") as temporary:
        executable = Path(temporary) / "probe"
        command_output(
            (
                str(XCRUN),
                "clang",
                "-std=c2x",
                "-arch",
                "arm64",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Wconversion",
                "-Wsign-conversion",
                "-Werror",
                str(source),
                str(bridge),
                str(public_bridge),
                "-o",
                str(executable),
            )
        )
        if b"/nix/store" in executable.read_bytes():
            raise CaptureError("probe executable embeds a Nix store path")
        public_runs = [
            parse_public_output(command_output((str(executable), "--public")))
            for _ in range(3)
        ]
        exhaustive_runs = [
            parse_exhaustive_output(command_output((str(executable), "--exhaustive")))
            for _ in range(3)
        ]
        executable_sha256 = sha256(executable)

    public_evidence = stable_runs(public_runs, "public matrix")
    exhaustive_evidence = stable_runs(exhaustive_runs, "exhaustive matrix")
    runtime = public_evidence["runtime"]
    if runtime != exhaustive_evidence["runtime"]:
        raise CaptureError("runtime Mix metadata varies by mode")

    result = {
        "designLibraryConfigurationFlagSeedCaptureSchemaVersion": SCHEMA_VERSION,
        "classification": (
            "authenticated private helper invocation and instruction-path exhaustive "
            "storage validation; native Apple Swift ABI with no GUI session, render, "
            "image, crop, or Nix store path"
        ),
        "host": {
            "system": platform.system(),
            "machine": platform.machine(),
            "macOSProductVersion": product_version,
            "macOSBuildVersion": build_version,
            "hardwareModel": hardware_model,
        },
        "framework": {
            "path": str(FRAMEWORK),
            "uuid": EXPECTED_FRAMEWORK_UUID,
        },
        "tool": {
            "python": sys.version.split()[0],
            "clang": command_output((str(XCRUN), "clang", "--version")).splitlines()[0],
            "captureSource": "Analysis/" + Path(__file__).name,
            "captureSourceSHA256": sha256(Path(__file__).resolve()),
            "probeSource": "Analysis/" + SOURCE_NAME,
            "probeSourceSHA256": sha256(source),
            "assemblyBridge": "Analysis/" + BRIDGE_NAME,
            "assemblyBridgeSHA256": sha256(bridge),
            "publicAssemblyBridge": "Analysis/" + PUBLIC_BRIDGE_NAME,
            "publicAssemblyBridgeSHA256": sha256(public_bridge),
            "probeExecutableSHA256": executable_sha256,
            "freshProcessRunsPerMode": 3,
        },
        "staticEvidence": static,
        "runtimeMixLayout": runtime,
        "optionBits": {
            "displayAngle": "0x0000000000000002",
            "adaptive": "0x0000000000004000",
            "externalLuminance": "0x0000000000008000",
            "exhaustivePassThroughNoise": "0x00000000009f327d",
        },
        "exactLaw": {
            "initialValue": "outer Configuration.options",
            "directBase": {
                "tag0Subvariants15Through18": "clear displayAngle",
                "regularSubvariant12": "clear adaptive",
                "clearSubvariants1And20": "set adaptive",
                "clearSubvariant8": "set displayAngle",
                "allOtherCases": "preserve outer options",
            },
            "indirectMix": {
                "displayAngle": "outer OR from OR to",
                "adaptive": "outer OR from OR to",
                "externalLuminance": "outer OR (from AND to)",
                "allOtherBits": "outer only",
                "fractionRead": False,
                "recursiveEndpointSeedEvaluation": False,
            },
        },
        "publicValidation": {
            "staticConfigurationCount": len(STATIC_NAMES),
            "orderedStaticMixCount": len(STATIC_NAMES) ** 2,
            "totalPublicConfigurationCount": len(public_evidence["public"]),
            "totalPublicMixCount": len(public_evidence["mixes"]),
            "subvariants": public_evidence["subvariants"],
            "normalizedStreamSHA256": public_evidence["normalizedSHA256"],
            "staticConfigurations": public_evidence["public"][: len(STATIC_NAMES)],
            **selected_records(public_evidence),
        },
        "exhaustiveValidation": {
            "directBaseRepresentationCount": len(DIRECT_KINDS),
            "subvariantStorageCountPerDirectRepresentation": 256,
            "relevantOptionCombinationCount": 8,
            "directCaseCount": exhaustive_evidence["directCaseCount"],
            "indirectCaseCount": exhaustive_evidence["indirectCaseCount"],
            "totalCaseCount": (
                int(exhaustive_evidence["directCaseCount"])
                + int(exhaustive_evidence["indirectCaseCount"])
            ),
            "directStreamSHA256": exhaustive_evidence["directStreamSHA256"],
            "indirectStreamSHA256": exhaustive_evidence["indirectStreamSHA256"],
            "combinedStreamSHA256": exhaustive_evidence["combinedStreamSHA256"],
            "classification": (
                "all helper storage branches and relevant option truth-table states; "
                "not a claim that every UInt8 Subvariant storage is public API state"
            ),
        },
        "measuredInvariants": {
            "helperCodeAuthenticated": True,
            "mixMetadataAndFieldsAuthenticated": True,
            "projectorRuntimeBindingAuthenticated": True,
            "allOrderedPublicStaticMixesMatchExactLaw": True,
            "allExhaustiveStorageCasesMatchExactLaw": True,
            "boxedMixPreservesBothConfigurationsBitwise": True,
            "boxedMixPreservesFractionBitwise": True,
            "mixFractionDoesNotAffectFlagSeed": True,
            "freshProcessSemanticStabilityEstablished": True,
        },
        "claims": {
            "configurationToFlagSeedLawEstablished": True,
            "arbitraryNestedConfigurationMixFlagSeedLawEstablished": True,
            "liveSwiftUIEnvironmentUpdateLawEstablished": False,
            "transitionProgressProductionLawEstablished": False,
            "integerCropAllocationPolicyEstablished": False,
            "retinaCompositorColorLawEstablished": False,
            "independentWalleZeroByteFrameParityEstablished": False,
            "liquidGlassParityEstablished": False,
            "productionShaderChangeAuthorized": False,
        },
    }
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    try:
        capture(arguments.output.resolve())
    except CaptureError as error:
        print("CAPTURE_ERROR: " + str(error), file=sys.stderr)
        return 1
    print(str(arguments.output.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
