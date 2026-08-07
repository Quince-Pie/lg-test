#!/usr/bin/env python3
"""Capture DesignLibrary's Configuration/Environment-to-flags boundary."""

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
SOURCE_NAME = "probe_designlibrary_environment_resolution_local_macos_26_6_1.c"
BRIDGE_NAME = "invoke_designlibrary_public_configuration_resolution_arm64.S"

PRODUCER_START = 0x2409737F8
PRODUCER_END = 0x240973CDC
EXPECTED_PRODUCER_SHA256 = (
    "69bd75dcc4daad7956b6b41560fc39a1ec5bd4187712c945788477ec6dd97090"
)

ENVIRONMENT_FIELDS = (
    ("pixelLength", 0),
    ("colorScheme", 8),
    ("colorSchemeContrast", 9),
    ("controlTint", 12),
    ("containerStyle", 32),
    ("textDimensions", 176),
    ("luminance", 204),
    ("dimensions", 216),
    ("idiom", 242),
    ("appearsActive", 243),
    ("windowAppearsActive", 244),
    ("windowBackgroundIsOpaque", 245),
    ("glassMaterialForeground", 246),
    ("hasTintedElements", 247),
    ("accessibilityReduceTransparency", 248),
    ("accessibilityReduceMotion", 249),
    ("accessibilityShowButtonShapes", 250),
    ("isLowPowerModeEnabled", 251),
    ("frost", 252),
    ("pocketParameters", 256),
    ("diffusion", 262),
)

DIRECT_ENVIRONMENT_FIELDS = (
    "colorSchemeContrast",
    "idiom",
    "appearsActive",
    "windowAppearsActive",
    "windowBackgroundIsOpaque",
    "glassMaterialForeground",
    "hasTintedElements",
    "accessibilityReduceTransparency",
    "accessibilityReduceMotion",
    "accessibilityShowButtonShapes",
    "isLowPowerModeEnabled",
    "diffusion",
)

EXPECTED_ENUMS = {
    "DesignIdiom": (
        "universal",
        "mac",
        "phone",
        "pad",
        "tv",
        "watch",
        "spatial",
        "carPlay",
        "touchBar",
    ),
    "ResolvedDiffusion": ("automatic", "increased"),
}

ENVIRONMENT_CASES = (
    ("baseline", None, b""),
    ("pixel_length_half", 0, struct.pack("<d", 0.5)),
    ("pixel_length_two", 0, struct.pack("<d", 2.0)),
    ("color_scheme_light", 8, b"\x00"),
    ("color_scheme_dark", 8, b"\x01"),
    ("contrast_standard", 9, b"\x00"),
    ("contrast_increased", 9, b"\x01"),
    ("appears_active_false", 243, b"\x00"),
    ("appears_active_true", 243, b"\x01"),
    ("window_active_false", 244, b"\x00"),
    ("window_active_true", 244, b"\x01"),
    ("window_opaque_false", 245, b"\x00"),
    ("window_opaque_true", 245, b"\x01"),
    ("glass_foreground_false", 246, b"\x00"),
    ("glass_foreground_true", 246, b"\x01"),
    ("has_tinted_elements_false", 247, b"\x00"),
    ("has_tinted_elements_true", 247, b"\x01"),
    ("reduce_transparency_false", 248, b"\x00"),
    ("reduce_transparency_true", 248, b"\x01"),
    ("reduce_motion_false", 249, b"\x00"),
    ("reduce_motion_true", 249, b"\x01"),
    ("show_button_shapes_false", 250, b"\x00"),
    ("show_button_shapes_true", 250, b"\x01"),
    ("low_power_false", 251, b"\x00"),
    ("low_power_true", 251, b"\x01"),
    ("idiom_universal", 242, b"\x00"),
    ("idiom_mac", 242, b"\x01"),
    ("idiom_phone", 242, b"\x02"),
    ("idiom_pad", 242, b"\x03"),
    ("idiom_tv", 242, b"\x04"),
    ("idiom_watch", 242, b"\x05"),
    ("idiom_spatial", 242, b"\x06"),
    ("idiom_car_play", 242, b"\x07"),
    ("idiom_touch_bar", 242, b"\x08"),
    ("diffusion_automatic", 262, b"\x00"),
    ("diffusion_increased", 262, b"\x01"),
)

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

MODIFIER_NAMES = (
    "color_scheme_light",
    "color_scheme_dark",
    "adaptive_false",
    "adaptive_true",
    "adaptive_light",
    "adaptive_dark",
    "adaptive_animatable_false",
    "adaptive_animatable_true",
)

EXPECTED_FIELD_LOADS = {
    0x2409738C0: ("ldrsw", "x8, [x0, #0x38]"),
    0x2409738D4: ("ldrsw", "x8, [x22, #0x34]"),
    0x2409738E8: ("ldrsw", "x9, [x22, #0x40]"),
    0x240973904: ("ldrsw", "x8, [x22, #0x3c]"),
    0x24097390C: ("ldrsw", "x8, [x22, #0x34]"),
    0x240973934: ("ldrsw", "x9, [x22, #0x40]"),
    0x240973964: ("ldrsw", "x20, [x22, #0x18]"),
    0x240973A04: ("ldrsw", "x8, [x22, #0x50]"),
    0x240973A1C: ("ldrsw", "x9, [x22, #0x48]"),
    0x240973A34: ("ldrsw", "x9, [x22, #0x4c]"),
    0x240973ABC: ("ldrsw", "x8, [x22, #0x44]"),
    0x240973B3C: ("ldrsw", "x8, [x22, #0x30]"),
    0x240973B68: ("ldrsw", "x8, [x22, #0x60]"),
    0x240973BC8: ("ldrsw", "x8, [x22, #0x54]"),
}

EXPECTED_OWNERSHIP_AND_RETURN_INSTRUCTIONS = {
    0x240973C40: ("mov", "x1, x16"),
    0x240973C44: ("mov", "x0, x21"),
    0x240973C48: ("bl", "0x240973cdc"),
    0x240973C5C: ("mov", "x1, x16"),
    0x240973C60: ("mov", "x0, x19"),
    0x240973C64: ("bl", "0x240973cdc"),
    0x240973C68: ("orr", "x0, x20, x22"),
}

TYPE_PATTERN = re.compile(
    r"^TYPE Environment size=(\d+) stride=(\d+) flags=0x([0-9a-f]+) "
    r"extra_inhabitants=(\d+)$"
)
FIELD_PATTERN = re.compile(r"^FIELD Environment (\d+) (\S+) offset=(\d+)$")
ENUM_PATTERN = re.compile(
    r"^ENUM (\S+) payload_cases=(\d+) empty_cases=(\d+)$"
)
CASE_PATTERN = re.compile(r"^CASE (\S+) (\d+) (\S+)$")
FLAGS_PATTERN = re.compile(r"^FLAGS (\S+) bits=0x([0-9a-f]{16})$")
BYTES_PATTERN = re.compile(
    r"^(ENVIRONMENT|CONFIGURATION|RESOLVED|KEY) (\S+) bytes=([0-9a-f]+)$"
)
BYTE_LINE = re.compile(r"^0x([0-9A-Fa-f]+):((?: [0-9A-Fa-f]{2})+)\s*$")
INSTRUCTION_LINE = re.compile(
    r"^0x([0-9A-Fa-f]+)\s+([^\s]+)(?:\s+(.*?))?\s*$"
)


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


def parse_probe_output(output: str) -> Mapping[str, object]:
    layout: Optional[Tuple[int, int, int, int]] = None
    fields: List[Tuple[str, int]] = []
    enum_counts: Dict[str, Tuple[int, int]] = {}
    enum_cases: Dict[str, List[str]] = {}
    flags: Dict[str, int] = {}
    groups: Dict[str, Dict[str, bytes]] = {
        "ENVIRONMENT": {},
        "CONFIGURATION": {},
        "RESOLVED": {},
        "KEY": {},
    }

    for line in output.splitlines():
        match = TYPE_PATTERN.fullmatch(line)
        if match is not None:
            if layout is not None:
                raise CaptureError("duplicate Environment layout")
            layout = (
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3), 16),
                int(match.group(4)),
            )
            continue
        match = FIELD_PATTERN.fullmatch(line)
        if match is not None:
            if int(match.group(1)) != len(fields):
                raise CaptureError("Environment field indices are not contiguous")
            fields.append((match.group(2), int(match.group(3))))
            continue
        match = ENUM_PATTERN.fullmatch(line)
        if match is not None:
            name = match.group(1)
            if name in enum_counts:
                raise CaptureError("duplicate enum " + name)
            enum_counts[name] = (int(match.group(2)), int(match.group(3)))
            enum_cases[name] = []
            continue
        match = CASE_PATTERN.fullmatch(line)
        if match is not None:
            name = match.group(1)
            entries = enum_cases.get(name)
            if entries is None or int(match.group(2)) != len(entries):
                raise CaptureError(name + " enum cases are not contiguous")
            entries.append(match.group(3))
            continue
        match = FLAGS_PATTERN.fullmatch(line)
        if match is not None:
            name = match.group(1)
            if name in flags:
                raise CaptureError("duplicate flags case " + name)
            flags[name] = int(match.group(2), 16)
            continue
        match = BYTES_PATTERN.fullmatch(line)
        if match is not None:
            group = groups[match.group(1)]
            name = match.group(2)
            if name in group:
                raise CaptureError("duplicate byte record " + name)
            group[name] = bytes.fromhex(match.group(3))
            continue
        raise CaptureError("unrecognized probe output: " + line)

    if layout != (263, 264, 0x00030007, 0x7FFFFFFE):
        raise CaptureError("Environment value-witness layout differs")
    if tuple(fields) != ENVIRONMENT_FIELDS:
        raise CaptureError("Environment fields or offsets differ")
    if set(enum_counts) != set(EXPECTED_ENUMS):
        raise CaptureError("environment enum identities differ")
    for name, expected in EXPECTED_ENUMS.items():
        if enum_counts[name] != (0, len(expected)):
            raise CaptureError(name + " enum payload/empty counts differ")
        if tuple(enum_cases[name]) != expected:
            raise CaptureError(name + " enum case order differs")

    environment_names = tuple(name for name, _, _ in ENVIRONMENT_CASES)
    configuration_names = tuple("configuration_" + name for name in STATIC_NAMES)
    modifier_names = tuple("modifier_" + name for name in MODIFIER_NAMES)
    all_names = set(environment_names + configuration_names + modifier_names)
    if set(flags) != all_names:
        raise CaptureError("flags case identities differ")
    if set(groups["ENVIRONMENT"]) != set(environment_names):
        raise CaptureError("Environment mutation case identities differ")
    if set(groups["CONFIGURATION"]) != set(configuration_names + modifier_names):
        raise CaptureError("Configuration case identities differ")
    if set(groups["RESOLVED"]) != all_names or set(groups["KEY"]) != all_names:
        raise CaptureError("resolved/key case identities differ")
    if any(len(value) != 263 for value in groups["ENVIRONMENT"].values()):
        raise CaptureError("Environment bytes are truncated")
    if any(len(value) != 144 for value in groups["CONFIGURATION"].values()):
        raise CaptureError("Configuration bytes are truncated")
    if any(len(value) != 321 for value in groups["RESOLVED"].values()):
        raise CaptureError("Resolved bytes are truncated")
    if any(len(value) != 49 for value in groups["KEY"].values()):
        raise CaptureError("resolved key bytes are truncated")

    baseline = groups["ENVIRONMENT"]["baseline"]
    for name, offset, value in ENVIRONMENT_CASES:
        expected = bytearray(baseline)
        if offset is not None:
            expected[offset : offset + len(value)] = value
        if groups["ENVIRONMENT"][name] != bytes(expected):
            raise CaptureError(name + " mutates bytes outside its frozen input")

    for name in all_names:
        key_flags = struct.unpack_from("<Q", groups["KEY"][name], 24)[0]
        if key_flags != flags[name]:
            raise CaptureError(name + " produced flags differ from resolved key")
    regular = groups["CONFIGURATION"]["configuration_regular"]
    for name in environment_names:
        if groups["RESOLVED"][name][128:272] != regular:
            raise CaptureError(name + " resolved style differs from regular")
    for name in configuration_names + modifier_names:
        if groups["RESOLVED"][name][128:272] != groups["CONFIGURATION"][name]:
            raise CaptureError(name + " resolved style differs from Configuration")

    return {
        "layout": layout,
        "fields": tuple(fields),
        "enums": {name: tuple(values) for name, values in enum_cases.items()},
        "flags": flags,
        "environments": groups["ENVIRONMENT"],
        "configurations": groups["CONFIGURATION"],
        "resolved": groups["RESOLVED"],
        "keys": groups["KEY"],
    }


def resolved_configuration_record(storage: bytes) -> Mapping[str, object]:
    if len(storage) != 49:
        raise CaptureError("resolved key is not 49 bytes")
    return {
        "baseStorageHex": storage[0:13].hex(),
        "subvariantStorage": storage[13],
        "frostStorage": storage[14],
        "optionsBits": "0x{0:016x}".format(struct.unpack_from("<Q", storage, 16)[0]),
        "environmentFlagsBits": "0x{0:016x}".format(
            struct.unpack_from("<Q", storage, 24)[0]
        ),
        "interactionStorage": storage[32],
        "optimizationLevelStorage": storage[33],
        "contentEffectStorage": storage[34],
        "layersBits": "0x{0:016x}".format(struct.unpack_from("<Q", storage, 40)[0]),
        "colorSchemeStorage": storage[48],
    }


def resolved_case_record(
    parsed: Mapping[str, object],
    name: str,
) -> Mapping[str, object]:
    flags = parsed["flags"]
    resolved = parsed["resolved"]
    keys = parsed["keys"]
    assert isinstance(flags, dict)
    assert isinstance(resolved, dict)
    assert isinstance(keys, dict)
    value = resolved[name]
    return {
        "name": name,
        "producedFlagsBits": "0x{0:016x}".format(flags[name]),
        "resolvedCompositeLuminanceBits": "0x{0:08x}".format(
            struct.unpack_from("<I", value, 8)[0]
        ),
        "resolvedColorSchemeStorage": value[102],
        "resolvedStyleFlagsStorage": value[296],
        "resolvedConfiguration": resolved_configuration_record(keys[name]),
    }


def semantic_record(parsed: Mapping[str, object]) -> Mapping[str, object]:
    environments = parsed["environments"]
    configurations = parsed["configurations"]
    assert isinstance(environments, dict)
    assert isinstance(configurations, dict)
    baseline = environments["baseline"]
    environment_records: List[Mapping[str, object]] = []
    for name, offset, value in ENVIRONMENT_CASES:
        record = dict(resolved_case_record(parsed, name))
        record["mutationOffset"] = offset
        record["mutationStorageHex"] = value.hex()
        environment_records.append(record)
    static_records: List[Mapping[str, object]] = []
    for static_name in STATIC_NAMES:
        name = "configuration_" + static_name
        record = dict(resolved_case_record(parsed, name))
        record["name"] = static_name
        static_records.append(record)
    modifier_records: List[Mapping[str, object]] = []
    for modifier_name in MODIFIER_NAMES:
        name = "modifier_" + modifier_name
        configuration = configurations[name]
        record = dict(resolved_case_record(parsed, name))
        record["name"] = modifier_name
        record["publicConfigurationOptionsBits"] = "0x{0:016x}".format(
            struct.unpack_from("<Q", configuration, 40)[0]
        )
        record["publicConfigurationColorSchemeStorage"] = configuration[49]
        modifier_records.append(record)
    return {
        "baselineEnvironment": {
            "pixelLengthBits": "0x{0:016x}".format(
                struct.unpack_from("<Q", baseline, 0)[0]
            ),
            "colorSchemeStorage": baseline[8],
            "colorSchemeContrastStorage": baseline[9],
            "idiomStorage": baseline[242],
            "appearsActiveStorage": baseline[243],
            "windowAppearsActiveStorage": baseline[244],
            "windowBackgroundIsOpaqueStorage": baseline[245],
            "glassMaterialForegroundStorage": baseline[246],
            "hasTintedElementsStorage": baseline[247],
            "accessibilityReduceTransparencyStorage": baseline[248],
            "accessibilityReduceMotionStorage": baseline[249],
            "accessibilityShowButtonShapesStorage": baseline[250],
            "isLowPowerModeEnabledStorage": baseline[251],
            "frostStorage": baseline[252:256].hex(),
            "diffusionStorage": baseline[262],
        },
        "environmentCases": environment_records,
        "staticConfigurations": static_records,
        "regularModifiers": modifier_records,
    }


def parse_instructions(output: str) -> Mapping[int, Tuple[str, str]]:
    result: Dict[int, Tuple[str, str]] = {}
    for line in output.splitlines():
        match = INSTRUCTION_LINE.fullmatch(line)
        if match is None:
            continue
        address = int(match.group(1), 16)
        if not PRODUCER_START <= address < PRODUCER_END:
            continue
        if address in result:
            raise CaptureError("duplicate instruction at {0:#x}".format(address))
        result[address] = (
            match.group(2).lower(),
            (match.group(3) or "").split(";", 1)[0].strip(),
        )
    return result


def producer_static_evidence() -> Mapping[str, object]:
    section_output = command_output(
        (str(DYLD_INFO), "-section_bytes", "__TEXT", "__text", str(FRAMEWORK))
    )
    memory: Dict[int, int] = {}
    for line in section_output.splitlines():
        match = BYTE_LINE.fullmatch(line)
        if match is None:
            continue
        address = int(match.group(1), 16)
        octets = bytes.fromhex(match.group(2))
        for index, value in enumerate(octets):
            byte_address = address + index
            if PRODUCER_START <= byte_address < PRODUCER_END:
                if byte_address in memory:
                    raise CaptureError("duplicate producer code byte")
                memory[byte_address] = value
    expected_addresses = set(range(PRODUCER_START, PRODUCER_END))
    if set(memory) != expected_addresses:
        raise CaptureError("producer code bytes are incomplete")
    code = bytes(memory[address] for address in range(PRODUCER_START, PRODUCER_END))
    observed_sha256 = hashlib.sha256(code).hexdigest()
    if observed_sha256 != EXPECTED_PRODUCER_SHA256:
        raise CaptureError("environment-flags producer code differs")

    instructions = parse_instructions(
        command_output((str(DYLD_INFO), "-disassemble", str(FRAMEWORK)))
    )
    if not set(range(PRODUCER_START, PRODUCER_END, 4)).issubset(instructions):
        raise CaptureError("producer disassembly coverage differs")
    for address, expected in {
        **EXPECTED_FIELD_LOADS,
        **EXPECTED_OWNERSHIP_AND_RETURN_INSTRUCTIONS,
    }.items():
        if instructions.get(address) != expected:
            raise CaptureError(
                "producer instruction differs at {0:#x}".format(address)
            )
    observed_x22_loads = {
        address: instruction
        for address, instruction in instructions.items()
        if instruction[0] == "ldrsw" and "[x22, #0x" in instruction[1]
    }
    expected_x22_loads = {
        address: instruction
        for address, instruction in EXPECTED_FIELD_LOADS.items()
        if "[x22, #0x" in instruction[1]
    }
    if observed_x22_loads != expected_x22_loads:
        raise CaptureError("producer Environment metadata-offset loads differ")

    excluded = tuple(
        name for name, _ in ENVIRONMENT_FIELDS if name not in DIRECT_ENVIRONMENT_FIELDS
    )
    return {
        "start": "0x{0:x}".format(PRODUCER_START),
        "endExclusive": "0x{0:x}".format(PRODUCER_END),
        "byteCount": len(code),
        "instructionCount": len(code) // 4,
        "sha256": observed_sha256,
        "directlyReadEnvironmentFields": list(DIRECT_ENVIRONMENT_FIELDS),
        "notDirectlyReadEnvironmentFields": list(excluded),
        "fieldOffsetLoadInstructions": [
            {
                "address": "0x{0:x}".format(address),
                "mnemonic": instruction[0],
                "operands": instruction[1],
            }
            for address, instruction in sorted(EXPECTED_FIELD_LOADS.items())
        ],
        "ownedArgumentDestructionAndReturnInstructions": [
            {
                "address": "0x{0:x}".format(address),
                "mnemonic": instruction[0],
                "operands": instruction[1],
            }
            for address, instruction in sorted(
                EXPECTED_OWNERSHIP_AND_RETURN_INSTRUCTIONS.items()
            )
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

    analysis_directory = Path(__file__).resolve().parent
    source = analysis_directory / SOURCE_NAME
    bridge = analysis_directory / BRIDGE_NAME
    if not source.is_file() or not bridge.is_file():
        raise CaptureError("native probe source or assembly bridge is missing")
    if b"/nix/store" in source.read_bytes() or b"/nix/store" in bridge.read_bytes():
        raise CaptureError("native probe source embeds a Nix store path")

    static_evidence = producer_static_evidence()
    with tempfile.TemporaryDirectory(prefix="lg-environment-flags-") as temporary:
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
                "-o",
                str(executable),
            )
        )
        if b"/nix/store" in executable.read_bytes():
            raise CaptureError("native probe executable embeds a Nix store path")
        parsed_runs = [
            parse_probe_output(command_output((str(executable), "--matrix")))
            for _ in range(3)
        ]
        executable_sha256 = sha256(executable)

    semantic_runs = [semantic_record(parsed) for parsed in parsed_runs]
    if any(record != semantic_runs[0] for record in semantic_runs[1:]):
        raise CaptureError("semantic records vary across fresh processes")
    semantic = semantic_runs[0]
    result = {
        "designLibraryEnvironmentFlagsResolutionCaptureSchemaVersion": SCHEMA_VERSION,
        "classification": (
            "authenticated native Swift code plus direct ABI invocation on valid "
            "Apple-created Configuration and Environment values; no GUI session, "
            "render, image, crop, or Nix store path is used"
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
            "probeExecutableSHA256": executable_sha256,
            "freshProcessRuns": 3,
        },
        "runtimeLayout": {
            "name": "Environment",
            "size": 263,
            "stride": 264,
            "valueWitnessFlags": "0x00030007",
            "extraInhabitantCount": 0x7FFFFFFE,
            "fields": [
                {"name": name, "offset": offset}
                for name, offset in ENVIRONMENT_FIELDS
            ],
        },
        "environmentEnums": {
            name: [
                {"storage": index, "name": case_name}
                for index, case_name in enumerate(cases)
            ]
            for name, cases in EXPECTED_ENUMS.items()
        },
        "environmentFlagsProducer": static_evidence,
        **semantic,
        "measuredInvariants": {
            "environmentMutationCaseCount": len(ENVIRONMENT_CASES),
            "publicStaticConfigurationCount": len(STATIC_NAMES),
            "regularModifierCount": len(MODIFIER_NAMES),
            "allDesignIdiomCasesMeasured": True,
            "allResolvedDiffusionCasesMeasured": True,
            "eachMutationChangesOnlyItsFrozenInputBytes": True,
            "producerOutputMatchesResolvedKeyBitwise": True,
            "providerRetainsConsumedConfiguration": True,
            "stateRegeneratedAfterOwnedEnvironmentConsumption": True,
            "resolvedStyleCopiesProviderConfiguration": True,
            "freshProcessSemanticStabilityEstablished": True,
        },
        "claims": {
            "environmentFlagsProducerCodeAuthenticated": True,
            "environmentFlagsProducerDirectFieldSetEstablished": True,
            "environmentFlagsForAllPublicStaticConfigurationsEstablished": True,
            "environmentFlagsForMeasuredRegularModifiersEstablished": True,
            "publicEnvironmentFlagsProducerBoundaryEstablished": True,
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
