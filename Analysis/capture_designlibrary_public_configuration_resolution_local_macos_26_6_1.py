#!/usr/bin/env python3
"""Capture public Configuration-to-Resolved behavior through Apple's Swift ABI."""

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

SOURCE_NAME = "probe_designlibrary_public_configuration_resolution_local_macos_26_6_1.c"
BRIDGE_NAME = "invoke_designlibrary_public_configuration_resolution_arm64.S"

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

MIX_FRACTIONS = (
    ("negative_quarter", -0.25),
    ("zero", 0.0),
    ("quarter", 0.25),
    ("half", 0.5),
    ("three_quarters", 0.75),
    ("one", 1.0),
    ("five_quarters", 1.25),
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

EXPECTED_LAYOUTS = {
    "Configuration": (144, 144, 0x00030007, 0x7FFFFFFF),
    "GlassMaterialProvider": (144, 144, 0x00030007, 0x7FFFFFFF),
    "State": (305, 312, 0x00030007, 0x7FFFFFFF),
    "Resolved": (321, 328, 0x00030007, 0x7FFFFFFF),
}

EXPECTED_FIELDS = {
    "Configuration": (
        ("base", 0),
        ("frost", 8),
        ("subvariant", 9),
        ("size", 16),
        ("options", 40),
        ("interactionState", 48),
        ("colorScheme", 49),
        ("optimizationLevel", 50),
        ("contentEffect", 51),
        ("_adaptiveHysteresisRange", 52),
        ("tints", 72),
        ("controlTint", 80),
        ("fixedBackgroundColor", 88),
        ("luminance", 112),
        ("customFill", 120),
        ("customGlow", 128),
    ),
    "State": (
        ("adaptedColorScheme", 0),
        ("awaitingInitialLuminance", 1),
        ("environment", 8),
        ("flags", 272),
        ("tints", 280),
        ("fixedBackgroundColor", 288),
    ),
    "Resolved": (
        ("composite", 0),
        ("focusOffset", 16),
        ("configuration", 32),
        ("resolved", 40),
        ("dimensions", 56),
        ("tints", 88),
        ("tintRecipe", 96),
        ("colorScheme", 102),
        ("customFill", 104),
        ("customGlow", 112),
        ("style", 128),
        ("controlTint", 272),
        ("styleFlags", 296),
        ("fixedBackgroundColor", 304),
    ),
}

TYPE_PATTERN = re.compile(
    r"^TYPE (\S+) size=(\d+) stride=(\d+) flags=0x([0-9a-f]+) "
    r"extra_inhabitants=(\d+) metadata=0x[0-9a-f]+$"
)
FIELD_PATTERN = re.compile(r"^FIELD (\S+) (\d+) (\S+) offset=(\d+)$")
VALUE_PATTERN = re.compile(r"^VALUE (\S+) (\S+) bytes=([0-9a-f]+)$")
DICTIONARY_PATTERN = re.compile(
    r"^DICTIONARY (\S+) allocation=(\d+) bytes=([0-9a-f]+)$"
)
KEY_PATTERN = re.compile(r"^KEY (\S+) slot=(\d+) bytes=([0-9a-f]+)$")
MIX_PATTERN = re.compile(r"^MIX (\S+) allocation=(\d+) bytes=([0-9a-f]+)$")


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
    layouts: Dict[str, Tuple[int, int, int, int]] = {}
    fields: Dict[str, List[Tuple[str, int]]] = {}
    values: Dict[Tuple[str, str], bytes] = {}
    dictionaries: Dict[str, bytes] = {}
    keys: Dict[str, bytes] = {}
    slots: Dict[str, int] = {}
    mixes: Dict[str, bytes] = {}

    for line in output.splitlines():
        match = TYPE_PATTERN.fullmatch(line)
        if match is not None:
            layouts[match.group(1)] = (
                int(match.group(2)),
                int(match.group(3)),
                int(match.group(4), 16),
                int(match.group(5)),
            )
            continue
        match = FIELD_PATTERN.fullmatch(line)
        if match is not None:
            type_name = match.group(1)
            index = int(match.group(2))
            entries = fields.setdefault(type_name, [])
            if index != len(entries):
                raise CaptureError(type_name + " field indices are not contiguous")
            entries.append((match.group(3), int(match.group(4))))
            continue
        match = VALUE_PATTERN.fullmatch(line)
        if match is not None:
            identity = (match.group(1), match.group(2))
            if identity in values:
                raise CaptureError("duplicate value " + repr(identity))
            values[identity] = bytes.fromhex(match.group(3))
            continue
        match = DICTIONARY_PATTERN.fullmatch(line)
        if match is not None:
            name = match.group(1)
            allocation = int(match.group(2))
            data = bytes.fromhex(match.group(3))
            if allocation != 224 or len(data) != allocation:
                raise CaptureError(name + " dictionary allocation differs")
            dictionaries[name] = data
            continue
        match = KEY_PATTERN.fullmatch(line)
        if match is not None:
            name = match.group(1)
            slot = int(match.group(2))
            data = bytes.fromhex(match.group(3))
            if slot not in (0, 1) or len(data) != 49:
                raise CaptureError(name + " dictionary key differs")
            keys[name] = data
            slots[name] = slot
            continue
        match = MIX_PATTERN.fullmatch(line)
        if match is not None:
            name = match.group(1)
            allocation = int(match.group(2))
            data = bytes.fromhex(match.group(3))
            if allocation != 128 or len(data) != 104:
                raise CaptureError(name + " mix allocation differs")
            mixes[name] = data
            continue
        raise CaptureError("unrecognized probe output: " + line)

    if layouts != EXPECTED_LAYOUTS:
        raise CaptureError("runtime value-witness layouts differ")
    frozen_fields = {name: tuple(entries) for name, entries in fields.items()}
    if frozen_fields != EXPECTED_FIELDS:
        raise CaptureError("runtime field names or offsets differ")
    if set(dictionaries) != set(keys) or set(slots) != set(keys):
        raise CaptureError("dictionary/key identities differ")
    for name, dictionary in dictionaries.items():
        if struct.unpack_from("<Q", dictionary, 0x10)[0] != 1:
            raise CaptureError(name + " dictionary count is not one")
        occupancy = struct.unpack_from("<Q", dictionary, 0x40)[0]
        if occupancy not in (0xFFFFFFFFFFFFFFFE, 0xFFFFFFFFFFFFFFFD):
            raise CaptureError(name + " dictionary occupancy mask differs")
        value_bits = (
            struct.unpack_from("<Q", dictionary, 0xB8)[0],
            struct.unpack_from("<Q", dictionary, 0xC0)[0],
        )
        if sorted(value_bits) != [0, 0x3FF0000000000000]:
            raise CaptureError(name + " dictionary values are not {0, 1.0}")
        if value_bits[slots[name]] != 0x3FF0000000000000:
            raise CaptureError(name + " selected key slot and weight slot differ")
    return {
        "layouts": layouts,
        "fields": frozen_fields,
        "values": values,
        "dictionaries": dictionaries,
        "keys": keys,
        "slots": slots,
        "mixes": mixes,
    }


def resolved_configuration_record(
    storage: bytes,
    color_scheme: Optional[int] = None,
) -> Mapping[str, object]:
    if len(storage) != 48:
        raise CaptureError("ResolvedConfiguration storage is not 48 bytes")
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
        **({"colorSchemeStorage": color_scheme} if color_scheme is not None else {}),
    }


def assert_common_value_invariants(
    parsed: Mapping[str, object],
    configuration_kind: str,
    resolved_kind: str,
    names: Sequence[str],
) -> None:
    values = parsed["values"]
    keys = parsed["keys"]
    assert isinstance(values, dict)
    assert isinstance(keys, dict)
    for name in names:
        configuration = values.get((configuration_kind, name))
        resolved = values.get((resolved_kind, name))
        key = keys.get(name)
        if configuration is None or len(configuration) != 144:
            raise CaptureError(name + " Configuration bytes are absent or truncated")
        if resolved is None or len(resolved) != 321:
            raise CaptureError(name + " Resolved bytes are absent or truncated")
        if key is None or len(key) != 49:
            raise CaptureError(name + " key bytes are absent or truncated")
        if resolved[128:272] != configuration:
            raise CaptureError(name + " Resolved.style does not preserve Configuration")
        if resolved[8:12] != struct.pack("<f", 1.0):
            raise CaptureError(name + " ResolvedComposite luminance is not 1.0")


def static_records(parsed: Mapping[str, object]) -> List[Mapping[str, object]]:
    assert_common_value_invariants(
        parsed,
        "Configuration",
        "Resolved",
        STATIC_NAMES,
    )
    values = parsed["values"]
    keys = parsed["keys"]
    assert isinstance(values, dict)
    assert isinstance(keys, dict)
    records: List[Mapping[str, object]] = []
    for name in STATIC_NAMES:
        configuration = values[("Configuration", name)]
        provider = values.get(("Provider", name))
        if provider != configuration:
            raise CaptureError(name + " provider initializer is not an exact copy")
        key = keys[name]
        records.append(
            {
                "name": name,
                "resolvedConfiguration": resolved_configuration_record(
                    key[:48],
                    key[48],
                ),
            }
        )
    return records


def mix_records(parsed: Mapping[str, object]) -> List[Mapping[str, object]]:
    names = tuple(name for name, _ in MIX_FRACTIONS)
    assert_common_value_invariants(
        parsed,
        "ConfigurationMix",
        "ResolvedMix",
        names,
    )
    keys = parsed["keys"]
    mixes = parsed["mixes"]
    assert isinstance(keys, dict)
    assert isinstance(mixes, dict)
    if set(mixes) != set(names):
        raise CaptureError("mix payload identities differ")

    records: List[Mapping[str, object]] = []
    endpoint_pair = None
    outer_tail = None
    for name, fraction in MIX_FRACTIONS:
        key = keys[name]
        payload = mixes[name]
        if key[8:13] != b"\0\0\0\0\x80":
            raise CaptureError(name + " outer mix base is not indirect")
        if payload[96:104] != struct.pack("<d", fraction):
            raise CaptureError(name + " mix fraction bits differ")
        endpoints = (
            resolved_configuration_record(payload[:48]),
            resolved_configuration_record(payload[48:96]),
        )
        if endpoint_pair is None:
            endpoint_pair = endpoints
        elif endpoint_pair != endpoints:
            raise CaptureError("mix endpoints vary with fraction")
        tail = resolved_configuration_record(b"\0" * 13 + key[13:48])
        tail = {key_name: value for key_name, value in tail.items() if key_name != "baseStorageHex"}
        if outer_tail is None:
            outer_tail = tail
        elif outer_tail != tail:
            raise CaptureError("outer mix key varies beyond its box pointer")
        records.append(
            {
                "name": name,
                "fraction": fraction,
                "fractionBits": "0x{0:016x}".format(
                    struct.unpack("<Q", payload[96:104])[0]
                ),
                "outerBaseRepresentation": {
                    "kind": "indirectBox",
                    "tagByte": key[12],
                },
                "outerResolvedConfigurationTail": tail,
                "outerColorSchemeStorage": key[48],
                "from": endpoints[0],
                "to": endpoints[1],
            }
        )
    return records


def modifier_records(parsed: Mapping[str, object]) -> List[Mapping[str, object]]:
    assert_common_value_invariants(
        parsed,
        "ConfigurationModifier",
        "ResolvedModifier",
        MODIFIER_NAMES,
    )
    values = parsed["values"]
    keys = parsed["keys"]
    assert isinstance(values, dict)
    assert isinstance(keys, dict)
    records: List[Mapping[str, object]] = []
    for name in MODIFIER_NAMES:
        configuration = values[("ConfigurationModifier", name)]
        key = keys[name]
        records.append(
            {
                "name": name,
                "publicConfigurationOptionsBits": "0x{0:016x}".format(
                    struct.unpack_from("<Q", configuration, 40)[0]
                ),
                "publicConfigurationColorSchemeStorage": configuration[49],
                "resolvedConfiguration": resolved_configuration_record(
                    key[:48],
                    key[48],
                ),
            }
        )
    return records


def initial_state_record(parsed: Mapping[str, object]) -> Mapping[str, object]:
    values = parsed["values"]
    assert isinstance(values, dict)
    state = values.get(("State", "initial"))
    if state is None or len(state) != 305:
        raise CaptureError("initial State bytes are absent or truncated")
    return {
        "adaptedColorSchemeStorage": state[0],
        "awaitingInitialLuminanceStorage": state[1],
        "flagsBits": "0x{0:016x}".format(struct.unpack_from("<Q", state, 272)[0]),
        "fixedBackgroundColorStorageHex": state[288:305].hex(),
    }


def stable_record(
    parsed_runs: Sequence[Mapping[str, object]],
    extractor,
    label: str,
):
    records = [extractor(parsed) for parsed in parsed_runs]
    if any(record != records[0] for record in records[1:]):
        raise CaptureError(label + " semantic records vary across fresh processes")
    return records[0]


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

    with tempfile.TemporaryDirectory(prefix="lg-public-configuration-") as temporary:
        temporary_directory = Path(temporary)
        executable = temporary_directory / "probe"
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
        parsed_by_mode: Dict[str, List[Mapping[str, object]]] = {}
        for mode in ("static", "mix", "modifier"):
            parsed_by_mode[mode] = [
                parse_probe_output(
                    command_output((str(executable), "--" + mode))
                )
                for _ in range(3)
            ]
        executable_sha256 = sha256(executable)

    static = stable_record(parsed_by_mode["static"], static_records, "static")
    mixes = stable_record(parsed_by_mode["mix"], mix_records, "mix")
    modifiers = stable_record(
        parsed_by_mode["modifier"],
        modifier_records,
        "modifier",
    )
    initial_states = [
        initial_state_record(parsed)
        for mode_runs in parsed_by_mode.values()
        for parsed in mode_runs
    ]
    if any(state != initial_states[0] for state in initial_states[1:]):
        raise CaptureError("initial State semantic fields vary across fresh processes")

    result = {
        "designLibraryPublicConfigurationResolutionCaptureSchemaVersion": SCHEMA_VERSION,
        "classification": (
            "direct native invocation of exported Apple Swift ABI; no DesignLibrary "
            "SDK module, GUI session, application, render, image, crop, or Nix store "
            "path is used"
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
            "freshProcessRunsPerMode": 3,
        },
        "runtimeLayouts": {
            name: {
                "size": layout[0],
                "stride": layout[1],
                "valueWitnessFlags": "0x{0:08x}".format(layout[2]),
                "extraInhabitantCount": layout[3],
                "fields": [
                    {"name": field_name, "offset": offset}
                    for field_name, offset in EXPECTED_FIELDS.get(name, ())
                ],
            }
            for name, layout in EXPECTED_LAYOUTS.items()
        },
        "initialState": initial_states[0],
        "staticConfigurations": static,
        "regularToClearMixes": mixes,
        "regularModifiers": modifiers,
        "measuredInvariants": {
            "staticConfigurationCount": len(static),
            "mixFractionCount": len(mixes),
            "modifierCount": len(modifiers),
            "nativeDictionaryAllocationBytes": 224,
            "nativeDictionaryCapacitySlots": 2,
            "nativeDictionaryEntryCount": 1,
            "nativeDictionaryValueBits": "0x3ff0000000000000",
            "nativeDictionaryValue": 1.0,
            "resolvedConfigurationBytes": 48,
            "resolvedCompositeKeySemanticBytes": 49,
            "resolvedConfigurationMixPayloadBytes": 104,
            "resolvedConfigurationMixAllocationBytes": 128,
            "providerInitializerCopiesAllConfigurationBytes": True,
            "resolvedStyleCopiesAllConfigurationBytes": True,
            "resolvedCompositeLuminanceBits": "0x3f800000",
            "publicMixFractionPreservedBitwise": True,
            "mixEndpointsIndependentOfFraction": True,
            "freshProcessSemanticStabilityEstablished": True,
        },
        "claims": {
            "publicStaticConfigurationDefaultsToResolvedKeysEstablished": True,
            "publicRegularClearMixRuntimePayloadEstablished": True,
            "publicRegularColorAndAdaptiveModifierResolutionEstablished": True,
            "initialProviderStateLayoutEstablished": True,
            "environmentToConfigurationSelectionLawEstablished": False,
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
