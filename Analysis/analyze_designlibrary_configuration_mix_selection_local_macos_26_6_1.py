#!/usr/bin/env python3
"""Prove public Configuration mix pass-through and direct one-hot resolution."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import struct
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

import analyze_designlibrary_background_filter_metadata_local_macos_26_6_1 as metadata
import analyze_designlibrary_resolved_composite_weight_pipeline_local_macos_26_6_1 as weights
import analyze_designlibrary_resolved_recipe_provenance_local_macos_26_6_1 as provenance


RESULT_SCHEMA_VERSION = 1
SOURCE_RELATIVE_PATH = (
    "Analysis/"
    "analyze_designlibrary_configuration_mix_selection_local_macos_26_6_1.py"
)
METADATA_ANALYZER_SHA256 = (
    "a50569535c5452a4a4e3db0940be09968b4de38bc86aeda12c95ab3c0a653aff"
)
PROVENANCE_ANALYZER_SHA256 = (
    "7492526b9ce67f21eee811a5a7d0f5effc1348be97f3aa4c2429d13e7c497145"
)
WEIGHT_ANALYZER_SHA256 = (
    "530922f37038ca23dbfe3cca43c3fe3a703fdf337dde7f393afda180b41ea3d0"
)
EXPECTED_HARDWARE_MODEL = provenance.EXPECTED_HARDWARE_MODEL

DESCRIPTORS = {
    "configurationMix": {
        "address": 0x2409D2188,
        "name": "Mix",
        "fields": ("from", "to", "fraction"),
        "offsets": None,
        "size": None,
        "stride": None,
    },
    "resolvedCompositeKey": weights.DESCRIPTORS["resolvedCompositeKey"],
    "resolvedConfiguration": weights.DESCRIPTORS["resolvedConfiguration"],
    "resolvedConfigurationMix": weights.DESCRIPTORS["resolvedConfigurationMix"],
}

EXPECTED_TYPE_REFERENCES = {
    ("configurationMix", "from"): (
        "_____ 13DesignLibrary21GlassMaterialProviderV13ConfigurationV"
    ),
    ("configurationMix", "to"): (
        "_____ 13DesignLibrary21GlassMaterialProviderV13ConfigurationV"
    ),
    ("configurationMix", "fraction"): "Sd",
    ("resolvedCompositeKey", "resolved"): (
        "_____ 13DesignLibrary21GlassMaterialProviderV21ResolvedConfigurationV"
    ),
    ("resolvedCompositeKey", "colorScheme"): "_____ 7SwiftUI11ColorSchemeO",
    ("resolvedConfigurationMix", "from"): (
        "_____ 13DesignLibrary21GlassMaterialProviderV21ResolvedConfigurationV"
    ),
    ("resolvedConfigurationMix", "to"): (
        "_____ 13DesignLibrary21GlassMaterialProviderV21ResolvedConfigurationV"
    ),
    ("resolvedConfigurationMix", "fraction"): "Sd",
}

CODE_REGIONS = {
    "publicConfigurationMix": (
        0x24091023C,
        0x2409102F0,
        "624f423bce22102c792898145e2000797b39ee00856df73158559d2781cdcd89",
    ),
    "resolvedConfigurationBuilder": (
        0x2409791C0,
        0x2409795D0,
        "592c7927b0d8f776d18d76d24c49e75deccd67411900f9070fe1a138a540165f",
    ),
    "resolvedConfigurationMixBuilder": (
        0x2409796B0,
        0x240979B40,
        "cc7c0f445edd5f08e0be7196bdbe865c35ba029a465c156a5e0bc14bf076447e",
    ),
    "resolvedConfigurationSelectionHelper": (
        0x2409861E0,
        0x240986580,
        "a65a676a38e6e56c0b15a6abed6b298e6eba4c75aca57ffc194a7d96bad4d68f",
    ),
    "glassMaterialProviderResolve": (
        0x240989FF0,
        0x24098AB0C,
        "7e328da4ed833e903d83cd3c77fb48ce19674c2098d5eed0c641ad4c86037d99",
    ),
    "genericValueCopy": (
        0x24098B114,
        0x24098B174,
        "47bec8778fab32e98650268cdee03385dfcb283c9a2c52d5c2b717d5301323b2",
    ),
}

TARGET_STARTS = {
    CODE_REGIONS["resolvedConfigurationBuilder"][0]: "resolvedConfigurationBuilder",
    CODE_REGIONS["resolvedConfigurationMixBuilder"][0]: (
        "resolvedConfigurationMixBuilder"
    ),
    CODE_REGIONS["resolvedConfigurationSelectionHelper"][0]: (
        "resolvedConfigurationSelectionHelper"
    ),
    CODE_REGIONS["genericValueCopy"][0]: "genericValueCopy",
}

EXPECTED_DIRECT_CALLS = {
    "resolvedConfigurationBuilder": (
        0x24097915C,
        0x240979920,
        0x240979A90,
        0x2409864C0,
        0x24098A4FC,
    ),
    "resolvedConfigurationMixBuilder": (0x2409793BC,),
    "resolvedConfigurationSelectionHelper": (
        0x240979104,
        0x2409798C8,
        0x240979A38,
        0x24098A4A0,
    ),
    "genericValueCopy": (
        0x240988788,
        0x2409887B0,
        0x24098A268,
        0x24098A588,
        0x24098A5A8,
        0x24098A850,
    ),
}

EXPECTED_FLOATING_INVENTORIES = {
    "publicConfigurationMix": {},
    "resolvedConfigurationBuilder": {},
    "resolvedConfigurationMixBuilder": {},
    "resolvedConfigurationSelectionHelper": {},
    "glassMaterialProviderResolve": {"fcmp": 1, "fcsel": 2, "fmov": 2},
    "genericValueCopy": {},
}

DIRECT_DICTIONARY_HEADER_ADDRESS = 0x2409AF6F0
DIRECT_DICTIONARY_HEADER = bytes.fromhex(
    "01000000000000000200000000000000"
)

CRITICAL_INSTRUCTIONS = {
    # Public Configuration.mix(with:by:) preserves the supplied Double in d8.
    0x24091025C: ("mov.16b", "v8, v0"),
    0x240910294: ("mov", "x0, x20"),
    0x24091029C: ("bl", "0x240914b5c"),
    0x2409102A0: ("ldrsw", "x8, [x22, #0x14]"),
    0x2409102A4: ("add", "x1, x24, x8"),
    0x2409102B0: ("bl", "0x240914b5c"),
    0x2409102B4: ("ldrsw", "x8, [x22, #0x18]"),
    0x2409102B8: ("str", "d8, [x24, x8]"),
    0x2409102BC: ("orr", "x0, x23, #0x8000000000000000"),
    # Configuration resolution identifies the indirect Mix payload and delegates it.
    0x2409792CC: ("ldr", "x8, [x20]"),
    0x2409792D0: ("lsr", "x9, x8, #62"),
    0x240979388: ("cmp", "w9, #0x2"),
    0x240979390: ("and", "x0, x8, #0x3fffffffffffffff"),
    0x2409793BC: ("bl", "0x2409796b0"),
    0x2409793C0: ("stur", "x0, [x29, #-0x70]"),
    0x2409793C4: ("mov", "x26, x1"),
    # The Mix builder copies and independently resolves both Configuration endpoints.
    0x2409797F4: ("mov", "x0, x19"),
    0x2409797FC: ("bl", "0x24097a698"),
    0x240979814: ("mov", "x0, x21"),
    0x24097981C: ("bl", "0x24097a698"),
    0x2409798C8: ("bl", "0x2409861e0"),
    0x240979920: ("bl", "0x2409791c0"),
    0x240979968: ("mov", "x0, #0x0"),
    0x240979974: ("ldrsw", "x8, [x0, #0x14]"),
    0x240979978: ("add", "x27, x20, x8"),
    0x240979990: ("mov", "x0, x27"),
    0x240979998: ("bl", "0x24097a698"),
    0x240979A38: ("bl", "0x2409861e0"),
    0x240979A90: ("bl", "0x2409791c0"),
    # Two exact 48-byte ResolvedConfiguration values and the unchanged fraction
    # become the 104-byte ResolvedConfiguration.Mix payload at box offset 0x10.
    0x240979ADC: ("mov", "w1, #0x78"),
    0x240979AE0: ("mov", "w2, #0x7"),
    0x240979AE8: ("ldur", "q0, [x29, #-0x88]"),
    0x240979AEC: ("ldur", "q1, [x29, #-0x78]"),
    0x240979AF0: ("stp", "q0, q1, [x0, #0x10]"),
    0x240979AF4: ("ldur", "q0, [x29, #-0x68]"),
    0x240979AF8: ("ldur", "q1, [x29, #-0xe8]"),
    0x240979AFC: ("ldur", "q2, [x29, #-0xd8]"),
    0x240979B00: ("stp", "q0, q1, [x0, #0x30]"),
    0x240979B04: ("ldur", "q0, [x29, #-0xc8]"),
    0x240979B08: ("stp", "q2, q0, [x0, #0x50]"),
    0x240979B0C: ("ldrsw", "x8, [x19, #0x18]"),
    0x240979B10: ("ldur", "x9, [x29, #-0xf0]"),
    0x240979B14: ("ldr", "d0, [x9, x8]"),
    0x240979B18: ("str", "d0, [x0, #0x70]"),
    0x240979B1C: ("mov", "x1, #0x8000000000"),
    # Provider.resolve(State) reaches this exact configuration path.
    0x2409864C0: ("bl", "0x2409791c0"),
    0x24098A4A0: ("bl", "0x2409861e0"),
    0x24098A4FC: ("bl", "0x2409791c0"),
    # All 48 ResolvedConfiguration bytes are copied into the dictionary key.
    0x24098A540: ("ldur", "q0, [x29, #-0x98]"),
    0x24098A544: ("ldur", "q1, [x29, #-0x88]"),
    0x24098A548: ("stp", "q0, q1, [x29, #-0xd0]"),
    0x24098A54C: ("ldur", "q0, [x29, #-0x78]"),
    0x24098A550: ("stur", "q0, [x29, #-0xb0]"),
    0x24098A608: ("ldur", "q0, [x29, #-0x88]"),
    0x24098A60C: ("ldur", "q1, [x29, #-0x98]"),
    0x24098A610: ("stp", "q0, q2, [x9, #0x10]"),
    0x24098A614: ("str", "q1, [x9]"),
    # The key's ColorScheme is copied through its runtime metadata offset.
    0x24098A624: ("ldrsw", "x8, [x8, #0x14]"),
    0x24098A630: ("add", "x0, x9, x8"),
    0x24098A634: ("add", "x1, x27, x20"),
    0x24098A638: ("mov", "x2, x22"),
    0x24098A64C: ("blraa", "x10, x17"),
    # The native Dictionary storage has count one and receives one exact key/value.
    0x24098A81C: ("ldr", "q0, [x8, #0x6f0]"),
    0x24098A820: ("str", "q0, [x0, #0x10]"),
    0x24098A844: ("ldur", "x26, [x8, #-0x100]"),
    0x24098A848: ("mov", "x0, x26"),
    0x24098A84C: ("mov", "x1, x22"),
    0x24098A850: ("bl", "0x24098b114"),
    0x24098A854: ("mov", "x8, #0x3ff0000000000000"),
    0x24098A858: ("str", "x8, [x22, x25]"),
    0x24098A860: ("bl", "0x240979dc0"),
    # Resolved.composite is emitted as that dictionary plus its Float luminance.
    0x24098A8AC: ("str", "x25, [x19]"),
    0x24098A8B0: ("str", "s8, [x19, #0x8]"),
}


class AnalysisError(RuntimeError):
    """Raised when native mix-selection evidence differs from the contract."""


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


def descriptor_evidence() -> tuple[Mapping[str, object], int, int]:
    section_specs = (
        ("__TEXT", "__const"),
        ("__TEXT", "__constg_swiftt"),
        ("__TEXT", "__swift5_reflstr"),
        ("__TEXT", "__swift5_typeref"),
        ("__TEXT", "__swift5_fieldmd"),
        ("__AUTH_CONST", "__const"),
    )
    sections = {
        spec: metadata.parse_section_bytes(
            spec[0],
            spec[1],
            metadata.run_dyld_info(("-section_bytes", spec[0], spec[1])),
        )
        for spec in section_specs
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
    slide, slide_match_count = metadata.infer_shared_cache_slide(
        sections[("__AUTH_CONST", "__const")], memory, descriptors
    )
    by_address = {descriptor.address: descriptor for descriptor in descriptors}
    records: dict[str, object] = {}
    for role, expected in DESCRIPTORS.items():
        address = int(expected["address"])
        descriptor = by_address.get(address)
        if descriptor is None:
            raise AnalysisError(role + " descriptor is absent")
        if descriptor.name != expected["name"]:
            raise AnalysisError(role + " descriptor name differs")
        if tuple(field.name for field in descriptor.fields) != expected["fields"]:
            raise AnalysisError(role + " descriptor fields differ")
        layout = metadata.metadata_for_descriptor(
            sections[("__AUTH_CONST", "__const")], memory, descriptor, slide
        )
        expected_offsets = expected["offsets"]
        if expected_offsets is None:
            if layout is not None:
                raise AnalysisError(role + " unexpectedly has static metadata")
        else:
            if layout is None:
                raise AnalysisError(role + " static metadata is absent")
            if tuple(layout["fieldOffsets"]) != expected_offsets:
                raise AnalysisError(role + " field offsets differ")
            if layout["size"] != expected["size"] or layout["stride"] != expected["stride"]:
                raise AnalysisError(role + " size or stride differs")
        record = metadata.descriptor_record(descriptor, layout)
        references = {
            field["name"]: field["typeReference"] for field in record["fields"]
        }
        for (reference_role, field_name), reference in EXPECTED_TYPE_REFERENCES.items():
            if reference_role == role and references[field_name] != reference:
                raise AnalysisError(role + "." + field_name + " type differs")
        records[role] = record
    return records, slide, slide_match_count


def direct_calls(text: metadata.Section) -> Mapping[str, tuple[int, ...]]:
    result: dict[str, list[int]] = {name: [] for name in TARGET_STARTS.values()}
    for address in range(text.start, text.end - 3, 4):
        instruction = struct.unpack(
            "<I", metadata.read_bytes(text.memory, address, 4)
        )[0]
        if instruction & 0xFC000000 != 0x94000000:
            continue
        destination = address + provenance.sign_extend(
            instruction & 0x03FFFFFF, 26
        ) * 4
        name = TARGET_STARTS.get(destination)
        if name is not None:
            result[name].append(address)
    frozen = {name: tuple(values) for name, values in result.items()}
    if frozen != EXPECTED_DIRECT_CALLS:
        raise AnalysisError("mix-selection direct call graph differs")
    return frozen


def floating_inventory(
    instructions: Mapping[int, tuple[str, str]], start: int, end: int
) -> Mapping[str, int]:
    return dict(
        sorted(
            Counter(
                instructions[address][0]
                for address in range(start, end, 4)
                if instructions[address][0].startswith("f")
            ).items()
        )
    )


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

    dependencies = (
        (metadata.__file__, METADATA_ANALYZER_SHA256, "metadata analyzer"),
        (provenance.__file__, PROVENANCE_ANALYZER_SHA256, "provenance analyzer"),
        (weights.__file__, WEIGHT_ANALYZER_SHA256, "weight analyzer"),
    )
    for dependency, expected, label in dependencies:
        if sha256(Path(dependency).resolve()) != expected:
            raise AnalysisError(label + " dependency differs")

    descriptors, slide, slide_match_count = descriptor_evidence()
    text = metadata.parse_section_bytes(
        "__TEXT",
        "__text",
        metadata.run_dyld_info(("-section_bytes", "__TEXT", "__text")),
    )
    constants = metadata.parse_section_bytes(
        "__TEXT",
        "__const",
        metadata.run_dyld_info(("-section_bytes", "__TEXT", "__const")),
    )
    observed_header = metadata.read_bytes(
        constants.memory,
        DIRECT_DICTIONARY_HEADER_ADDRESS,
        len(DIRECT_DICTIONARY_HEADER),
    )
    if observed_header != DIRECT_DICTIONARY_HEADER:
        raise AnalysisError("direct dictionary header constant differs")

    instructions = provenance.parse_instructions(
        metadata.run_dyld_info(("-disassemble",))
    )
    code_records: dict[str, Mapping[str, object]] = {}
    inventories: dict[str, Mapping[str, int]] = {}
    for name, (start, end, expected_sha256) in CODE_REGIONS.items():
        code = metadata.read_bytes(text.memory, start, end - start)
        observed_sha256 = hashlib.sha256(code).hexdigest()
        if observed_sha256 != expected_sha256:
            raise AnalysisError(name + " code differs")
        if not set(range(start, end, 4)).issubset(instructions):
            raise AnalysisError(name + " disassembly coverage differs")
        code_records[name] = {
            "start": "0x{:x}".format(start),
            "endExclusive": "0x{:x}".format(end),
            "byteCount": end - start,
            "instructionCount": (end - start) // 4,
            "sha256": observed_sha256,
        }
        inventories[name] = floating_inventory(instructions, start, end)
    if inventories != EXPECTED_FLOATING_INVENTORIES:
        raise AnalysisError("mix-selection floating instruction inventories differ")

    contracts = []
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

    source_path = Path(__file__).resolve()
    return {
        "designLibraryConfigurationMixSelectionAnalysisSchemaVersion": (
            RESULT_SCHEMA_VERSION
        ),
        "classification": (
            "native static Swift metadata/code/control-flow analysis; no Apple "
            "application, render, image, public timeline sample, crop, or provider "
            "return is read"
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
            "sharedCacheSlide": "0x{:x}".format(slide),
            "sharedCacheSlideMetadataMatchCount": slide_match_count,
        },
        "tool": {
            "dyldInfo": str(metadata.DYLD_INFO),
            "python": sys.version.split()[0],
            "source": SOURCE_RELATIVE_PATH,
            "sourceSHA256": sha256(source_path),
            "metadataAnalyzerSHA256": METADATA_ANALYZER_SHA256,
            "provenanceAnalyzerSHA256": PROVENANCE_ANALYZER_SHA256,
            "weightAnalyzerSHA256": WEIGHT_ANALYZER_SHA256,
        },
        "swiftDescriptors": descriptors,
        "codeRegions": code_records,
        "directBLCallsites": {
            name: ["0x{:x}".format(address) for address in addresses]
            for name, addresses in direct_calls(text).items()
        },
        "floatingInstructionInventories": inventories,
        "instructionContracts": contracts,
        "directDictionaryStorageHeader": {
            "address": "0x{:x}".format(DIRECT_DICTIONARY_HEADER_ADDRESS),
            "bytes": observed_header.hex(),
            "littleEndianWords": list(struct.unpack("<QQ", observed_header)),
        },
        "configurationMixModel": {
            "publicMethod": "Configuration.mix(with:by:)",
            "sourceType": "Configuration.Mix",
            "sourceFields": ["from", "to", "fraction"],
            "sourceFractionType": "Double",
            "sourceFractionOperation": (
                "the incoming d0 bit pattern is preserved in d8 and stored once "
                "without floating-point arithmetic"
            ),
            "resolvedType": "ResolvedConfiguration.Mix",
            "resolvedLayout": {
                "fromOffset": 0,
                "toOffset": 48,
                "fractionOffset": 96,
                "size": 104,
                "stride": 104,
            },
            "resolution": (
                "recursively resolve from and to, then load the original source "
                "fraction through the same Configuration.Mix metadata offset and "
                "store its unchanged binary64 bits at resolved payload offset 96"
            ),
        },
        "directResolveCompositeModel": {
            "keyType": "(ResolvedConfiguration, ColorScheme)",
            "keyConstruction": (
                "copy all 48 ResolvedConfiguration bytes, then copy ColorScheme "
                "through the Key runtime metadata offset"
            ),
            "dictionaryEntryCount": 1,
            "dictionaryValueType": "Double",
            "dictionaryValueBits": "0x3ff0000000000000",
            "dictionaryValue": 1.0,
            "resolvedCompositeDestination": "Resolved runtime offsets 0 and 8",
            "luminanceType": "Float",
        },
        "mechanismBoundary": {
            "publicConfigurationMix": (
                "one ResolvedComposite key at weight 1.0 whose "
                "ResolvedConfiguration base contains a recursive Mix"
            ),
            "resolvedAnimation": (
                "separate ResolvedComposite dictionary VectorArithmetic proven by "
                "the locked weight-pipeline analyzer"
            ),
            "sameMechanism": False,
        },
        "claims": {
            "publicConfigurationMixFieldsEstablished": True,
            "publicConfigurationMixByStoredBitwiseUnchanged": True,
            "resolvedConfigurationMixLayoutEstablished": True,
            "configurationMixEndpointsRecursivelyResolved": True,
            "configurationMixByCopiedToResolvedFractionBitwiseUnchanged": True,
            "directResolveKeyIsResolvedConfigurationAndColorScheme": True,
            "directResolveProducesExactlyOneKeyAtBinary64One": True,
            "publicConfigurationMixDistinctFromResolvedAnimationWeights": True,
            "transitionProgressToPublicConfigurationMixByLawEstablished": False,
            "publicControlsToResolvedConfigurationSelectionLawEstablished": False,
            "environmentToResolvedConfigurationSelectionLawEstablished": False,
            "allRuntimeWeightProductionLawEstablished": False,
            "resolvedConfigurationMixConsumptionArithmeticEstablished": False,
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
    except (
        AnalysisError,
        metadata.AnalysisError,
        provenance.AnalysisError,
        weights.AnalysisError,
    ) as error:
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
