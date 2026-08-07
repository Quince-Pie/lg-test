#!/usr/bin/env python3
"""Prove ResolvedComposite's exact keyed blend-weight arithmetic and builder join."""

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
import analyze_designlibrary_resolved_recipe_provenance_local_macos_26_6_1 as provenance


RESULT_SCHEMA_VERSION = 1
SOURCE_RELATIVE_PATH = (
    "Analysis/"
    "analyze_designlibrary_resolved_composite_weight_pipeline_local_macos_26_6_1.py"
)
METADATA_ANALYZER_SHA256 = (
    "a50569535c5452a4a4e3db0940be09968b4de38bc86aeda12c95ab3c0a653aff"
)
PROVENANCE_ANALYZER_SHA256 = (
    "7492526b9ce67f21eee811a5a7d0f5effc1348be97f3aa4c2429d13e7c497145"
)
EXPECTED_HARDWARE_MODEL = provenance.EXPECTED_HARDWARE_MODEL

DESCRIPTORS = {
    "resolvedTint": {
        "address": 0x2409D23F8,
        "name": "ResolvedTint",
        "fields": ("tags", "color"),
        "offsets": (0, 8),
        "size": 28,
        "stride": 32,
    },
    "resolved": {
        "address": 0x2409D2DC4,
        "name": "Resolved",
        "fields": (
            "composite",
            "focusOffset",
            "configuration",
            "resolved",
            "dimensions",
            "tints",
            "tintRecipe",
            "colorScheme",
            "customFill",
            "customGlow",
            "style",
            "controlTint",
            "styleFlags",
            "fixedBackgroundColor",
        ),
        "offsets": None,
        "size": None,
        "stride": None,
    },
    "resolvedAnimatableData": {
        "address": 0x2409D2DEC,
        "name": "AnimatableData",
        "fields": ("composite", "focusOffset", "tints"),
        "offsets": (0, 16, 32),
        "size": 40,
        "stride": 40,
    },
    "resolvedComposite": {
        "address": 0x2409D2E30,
        "name": "ResolvedComposite",
        "fields": ("values", "luminance"),
        "offsets": (0, 8),
        "size": 12,
        "stride": 16,
    },
    "resolvedCompositeKey": {
        "address": 0x2409D2E4C,
        "name": "Key",
        "fields": ("resolved", "colorScheme"),
        "offsets": None,
        "size": None,
        "stride": None,
    },
    "resolvedConfiguration": {
        "address": 0x2409D2E90,
        "name": "ResolvedConfiguration",
        "fields": (
            "base",
            "subvariant",
            "frost",
            "options",
            "flags",
            "interaction",
            "optimizationLevel",
            "contentEffect",
            "layers",
        ),
        "offsets": (0, 13, 14, 16, 24, 32, 33, 34, 40),
        "size": 48,
        "stride": 48,
    },
    "resolvedConfigurationMix": {
        "address": 0x2409D2EAC,
        "name": "Mix",
        "fields": ("from", "to", "fraction"),
        "offsets": (0, 48, 96),
        "size": 104,
        "stride": 104,
    },
}

EXPECTED_TYPE_REFERENCES = {
    ("resolved", "composite"): (
        "_____ 13DesignLibrary21GlassMaterialProviderV17ResolvedCompositeV"
    ),
    ("resolvedAnimatableData", "composite"): (
        "_____ 13DesignLibrary21GlassMaterialProviderV17ResolvedCompositeV"
    ),
    ("resolvedComposite", "values"): (
        "SDy_____SdG "
        "13DesignLibrary21GlassMaterialProviderV17ResolvedCompositeV3KeyV"
    ),
    ("resolvedComposite", "luminance"): "Sf",
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
    "resolvedAnimatableZero": (
        0x24097C040,
        0x24097C094,
        "fde3f77e41919787f13274019cbb11ed30b06d75edca427f06f10ed0efeef747",
    ),
    "resolvedAnimatableAdd": (
        0x24097C094,
        0x24097C184,
        "ddbfbe740991dc8eab5d32da2517a092519210530266ead45e17207c16b1a526",
    ),
    "resolvedAnimatableSubtract": (
        0x24097C184,
        0x24097C21C,
        "086aeabd198b4f5675a1cd18169fbff0406b7642fbf29b791fbc6f7a2b8998bf",
    ),
    "resolvedAnimatableScale": (
        0x24097C21C,
        0x24097C504,
        "a13eb7a50e339d973203bbd75bf64d71c46039db05d597fe6dbebbf84b04f5ee",
    ),
    "resolvedAnimatableMagnitudeSquared": (
        0x24097C504,
        0x24097C558,
        "0f5f3e5ebd0959e27be50d93eee3b377bbddcae68f9f84883c5d70e1d31b4d84",
    ),
    "resolvedAnimatableGetter": (
        0x24097C8DC,
        0x24097C968,
        "6e1d788806440612193cc14503dc9a43ae4fb7f433d1df4b683e9f619c268357",
    ),
    "resolvedAnimatableSetter": (
        0x24097CA84,
        0x24097CB20,
        "cc3af499c6124ef22179eba234c9b68ce9ea2b33c52115f457c72d7838e47579",
    ),
    "resolvedCompositeScale": (
        0x2409810F8,
        0x24098137C,
        "dbe3108cef5d11f5252f11349031894d3184f61d58ed05b682020e2227874be6",
    ),
    "resolvedCompositeMagnitudeSquared": (
        0x24098137C,
        0x240981418,
        "bf44b7c124baf5fca26fd649e0f7d88f5a0af0503e78441ad3840e8c9a000f21",
    ),
    "resolvedCompositeSubtract": (
        0x240983878,
        0x240983F8C,
        "eb14906ebbd161d19d3cfdc5261ea565d0f9e53a48c32bfc7bca2d9564aa8cb3",
    ),
    "resolvedCompositeAdd": (
        0x240983F8C,
        0x2409846A4,
        "ed7e25b93b77011ef85f23db20f072d9f3ae35d17eb033e4cc286c8b023a4d08",
    ),
}

EXPECTED_DIRECT_CALLS = {
    "resolvedAnimatableZero": (),
    "resolvedAnimatableAdd": (),
    "resolvedAnimatableSubtract": (),
    "resolvedAnimatableScale": (),
    "resolvedAnimatableMagnitudeSquared": (),
    "resolvedAnimatableGetter": (),
    "resolvedAnimatableSetter": (),
    "resolvedCompositeScale": (0x24097C2E8, 0x24097C578),
    "resolvedCompositeMagnitudeSquared": (0x24097C528, 0x24097C5E4),
    "resolvedCompositeSubtract": (0x24097C1D0, 0x24097C7D8, 0x24097C874),
    "resolvedCompositeAdd": (0x24092FA14, 0x24097C0E8, 0x24097C6BC),
}

EXPECTED_FLOATING_INVENTORIES = {
    "resolvedAnimatableZero": {},
    "resolvedAnimatableAdd": {"fadd": 2},
    "resolvedAnimatableSubtract": {"fsub": 2},
    "resolvedAnimatableScale": {"fmul.2d": 1},
    "resolvedAnimatableMagnitudeSquared": {"fadd": 3, "fmul": 2},
    "resolvedAnimatableGetter": {},
    "resolvedAnimatableSetter": {},
    "resolvedCompositeScale": {"fcmp": 1, "fcvt": 1, "fmul": 2},
    "resolvedCompositeMagnitudeSquared": {"fadd": 1, "fcvt": 1, "fmul": 2},
    "resolvedCompositeSubtract": {"fneg": 1, "fsub": 2},
    "resolvedCompositeAdd": {"fadd": 2},
}

CRITICAL_INSTRUCTIONS = {
    # Resolved.AnimatableData.zero and field layout.
    0x24097C06C: ("stp", "xzr, xzr, [x19, #0x10]"),
    0x24097C078: ("str", "x21, [x19]"),
    0x24097C07C: ("str", "wzr, [x19, #0x8]"),
    0x24097C080: ("str", "x0, [x19, #0x20]"),
    # Resolved AnimatableData vector arithmetic.
    0x24097C0E8: ("bl", "0x240983f8c"),
    0x24097C0F4: ("fadd", "d0, d9, d11"),
    0x24097C0F8: ("fadd", "d1, d10, d12"),
    0x24097C1D0: ("bl", "0x240983878"),
    0x24097C1DC: ("fsub", "d0, d9, d11"),
    0x24097C1E0: ("fsub", "d1, d10, d12"),
    0x24097C2E8: ("bl", "0x2409810f8"),
    0x24097C2F4: ("fmul.2d", "v0, v0, v1[0]"),
    0x24097C528: ("bl", "0x24098137c"),
    0x24097C52C: ("fmul", "d1, d8, d8"),
    0x24097C530: ("fmul", "d2, d9, d9"),
    0x24097C534: ("fadd", "d1, d1, d2"),
    0x24097C538: ("fadd", "d8, d0, d1"),
    0x24097C544: ("fadd", "d0, d8, d0"),
    # Getter proves Resolved's runtime offsets; output is the 40-byte vector.
    0x24097C8FC: ("ldr", "x21, [x20]"),
    0x24097C900: ("ldr", "s10, [x20, #0x8]"),
    0x24097C904: ("ldp", "d8, d9, [x20, #0x10]"),
    0x24097C924: ("ldr", "x20, [x20, #0x58]"),
    0x24097C940: ("str", "x21, [x19]"),
    0x24097C944: ("str", "s10, [x19, #0x8]"),
    0x24097C948: ("stp", "d8, d9, [x19, #0x10]"),
    0x24097C94C: ("str", "x22, [x19, #0x20]"),
    # Setter writes the same Resolved offsets from AnimatableData.
    0x24097CAA0: ("mov", "x19, x20"),
    0x24097CAA4: ("ldr", "x21, [x0]"),
    0x24097CAA8: ("ldr", "s10, [x0, #0x8]"),
    0x24097CAAC: ("ldp", "d8, d9, [x0, #0x10]"),
    0x24097CAB0: ("ldr", "x22, [x0, #0x20]"),
    0x24097CAC8: ("str", "x21, [x19]"),
    0x24097CACC: ("str", "s10, [x19, #0x8]"),
    0x24097CAD0: ("add", "x20, x19, #0x10"),
    0x24097CAFC: ("ldr", "x0, [x19, #0x58]"),
    0x24097CB04: ("str", "x20, [x19, #0x58]"),
    # ResolvedComposite.scale(by:): canonical zero and exact value arithmetic.
    0x240981194: ("fcmp", "d8, #0.0"),
    0x240981198: ("b.ne", "0x2409811c0"),
    0x2409811B4: ("str", "x19, [x20]"),
    0x2409811B8: ("str", "wzr, [x20, #0x8]"),
    0x2409812AC: ("ldr", "d0, [x8, x21, lsl #3]"),
    0x2409812B0: ("fmul", "d9, d8, d0"),
    0x2409812E8: ("str", "d9, [x8, x21, lsl #3]"),
    0x240981320: ("fcvt", "s0, d8"),
    0x240981324: ("ldr", "s1, [x19, #0x8]"),
    0x240981328: ("fmul", "s0, s1, s0"),
    0x24098132C: ("str", "s0, [x19, #0x8]"),
    # ResolvedComposite magnitude and keyed add/subtract operations.
    0x240981380: ("fmul", "s0, s0, s0"),
    0x24098138C: ("fcvt", "d0, s0"),
    0x2409813DC: ("ldr", "d1, [x12, x13]"),
    0x2409813E0: ("fmul", "d1, d1, d1"),
    0x2409813E4: ("fadd", "d0, d0, d1"),
    0x240983D24: ("fneg", "d10, d10"),
    0x240983E10: ("fsub", "d10, d11, d10"),
    0x240983F20: ("fsub", "s8, s9, s8"),
    0x240984520: ("fadd", "d10, d10, d11"),
    0x240984638: ("fadd", "s8, s9, s8"),
    # Public resolveLayers helper passes Resolved.composite.values unchanged.
    0x2409235F0: ("ldr", "x8, [x22]"),
    0x2409235F4: ("ldr", "s0, [x22, #0x8]"),
    0x24092361C: ("stp", "x9, x8, [sp, #-0x10]!"),
    0x240923620: ("mov", "x8, x28"),
    0x240923628: ("bl", "0x2409801bc"),
    # The intermediate caller preserves that incoming dictionary into builder x2.
    0x240980214: ("ldr", "x25, [x29, #0x18]"),
    0x240980710: ("stur", "x25, [x29, #-0xd8]"),
    0x240980EE0: ("ldp", "x8, x2, [x29, #-0xe0]"),
    0x240980EF0: ("bl", "0x240981b4c"),
    # Builder dictionary traversal, exact count, value load, and d9 factor load.
    0x240981BA0: ("str", "x2, [x19, #0x88]"),
    0x240981EBC: ("ldr", "x0, [x19, #0x88]"),
    0x240981EC4: ("ldr", "x8, [x9, #0x40]!"),
    0x240981ECC: ("ldr", "x9, [x0, #0x10]"),
    0x240981ED0: ("str", "x9, [x19, #0xb0]"),
    0x240982854: ("ldp", "x9, x28, [x19, #0x80]"),
    0x2409828A8: ("ldr", "x9, [x28, #0x38]"),
    0x2409828AC: ("ldr", "d0, [x9, x20, lsl #3]"),
    0x240982934: ("ldrsw", "x8, [x20, #0x30]"),
    0x240982938: ("ldr", "d9, [x28, x8]"),
}


class AnalysisError(RuntimeError):
    """Raised when native weight-pipeline evidence differs from the contract."""


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
    targets = {start: name for name, (start, _, _) in CODE_REGIONS.items()}
    result: dict[str, list[int]] = {name: [] for name in CODE_REGIONS}
    for address in range(text.start, text.end - 3, 4):
        instruction = struct.unpack(
            "<I", metadata.read_bytes(text.memory, address, 4)
        )[0]
        if instruction & 0xFC000000 != 0x94000000:
            continue
        destination = address + provenance.sign_extend(
            instruction & 0x03FFFFFF, 26
        ) * 4
        name = targets.get(destination)
        if name is not None:
            result[name].append(address)
    frozen = {name: tuple(values) for name, values in result.items()}
    if EXPECTED_DIRECT_CALLS is not None and frozen != EXPECTED_DIRECT_CALLS:
        raise AnalysisError("weight-pipeline direct call graph differs")
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
    if sha256(Path(metadata.__file__).resolve()) != METADATA_ANALYZER_SHA256:
        raise AnalysisError("metadata analyzer dependency differs")
    if sha256(Path(provenance.__file__).resolve()) != PROVENANCE_ANALYZER_SHA256:
        raise AnalysisError("provenance analyzer dependency differs")

    descriptors, slide, slide_match_count = descriptor_evidence()
    text = metadata.parse_section_bytes(
        "__TEXT",
        "__text",
        metadata.run_dyld_info(("-section_bytes", "__TEXT", "__text")),
    )
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
        raise AnalysisError("weight-pipeline floating instruction inventories differ")

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

    for region_name in (
        "resolveLayersHelper",
        "resolvedRecipeIntermediateBuilder",
        "resolvedRecipeBuilder",
    ):
        start, end, expected_sha256 = provenance.CODE_REGIONS[region_name]
        observed = hashlib.sha256(
            metadata.read_bytes(text.memory, start, end - start)
        ).hexdigest()
        if observed != expected_sha256:
            raise AnalysisError(region_name + " dependency code differs")

    source_path = Path(__file__).resolve()
    return {
        "designLibraryResolvedCompositeWeightPipelineAnalysisSchemaVersion": (
            RESULT_SCHEMA_VERSION
        ),
        "classification": (
            "native static Swift metadata/code/control-flow/arithmetic analysis; "
            "no Apple application, render, image, captured public value, crop, "
            "or provider return is read"
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
        },
        "swiftDescriptors": descriptors,
        "codeRegions": code_records,
        "directBLCallsites": {
            name: ["0x{:x}".format(address) for address in addresses]
            for name, addresses in direct_calls(text).items()
        },
        "floatingInstructionInventories": inventories,
        "instructionContracts": contracts,
        "resolvedCompositeModel": {
            "valuesType": (
                "Dictionary<ResolvedComposite.Key, Double>"
            ),
            "keyType": "(ResolvedConfiguration, ColorScheme)",
            "luminanceType": "Float",
            "mixType": "(from: ResolvedConfiguration, to: ResolvedConfiguration, fraction: Double)",
            "zero": {
                "values": "empty dictionary",
                "luminance": 0.0,
            },
            "addition": {
                "keyDomain": "dictionary-key union",
                "sharedKeyOperation": "binary64 addition",
                "leftOnlyOperation": "identity",
                "rightOnlyOperation": "identity",
                "luminanceOperation": "binary32 addition",
            },
            "subtraction": {
                "keyDomain": "dictionary-key union",
                "sharedKeyOperation": "binary64 subtraction",
                "leftOnlyOperation": "identity",
                "rightOnlyOperation": "binary64 negation",
                "luminanceOperation": "binary32 subtraction",
            },
            "scale": {
                "zeroFactorOperation": "canonical empty dictionary and zero luminance",
                "nonzeroValueOperation": "each binary64 value multiplied by binary64 factor",
                "luminanceOperation": "factor converted to binary32, then binary32 multiplication",
            },
            "magnitudeSquared": (
                "binary32 luminance squared then converted to binary64, plus the "
                "binary64 square of every dictionary value"
            ),
        },
        "builderWeightJoin": {
            "producer": "Resolved.composite.values at runtime offset 0",
            "publicResolveLayersHelperCallsite": "0x240923628",
            "resolvedRecipeCallerEntryStackArgument": "incoming stack + 0x8",
            "resolvedRecipeBuilderRegister": "x2",
            "builderDictionarySlot": "builder stack + 0x88",
            "builderCountSlot": "builder stack + 0xb0",
            "builderFactorRegister": "d9",
            "factorScalarType": "binary64 Double",
            "preservesDictionaryPointerAcrossJoin": True,
        },
        "claims": {
            "resolvedAnimatableDataLayoutEstablished": True,
            "resolvedCompositeLayoutEstablished": True,
            "resolvedCompositeValuesAreKeyedBinary64Weights": True,
            "resolvedCompositeKeyIsResolvedConfigurationAndColorScheme": True,
            "resolvedConfigurationSemanticFieldsEstablished": True,
            "resolvedConfigurationMixLayoutEstablished": True,
            "resolvedCompositeVectorArithmeticEstablished": True,
            "resolvedCompositeZeroFactorCanonicalizationEstablished": True,
            "resolvedCompositeLuminanceUsesBinary32Arithmetic": True,
            "resolvedCompositeDictionaryPointerReachesRecipeBuilderUnchanged": True,
            "recipeBuilderConsumesDictionaryCountAndBinary64Values": True,
            "recipeBuilderD9FactorComesFromResolvedCompositeValues": True,
            "publicControlsToResolvedConfigurationSelectionLawEstablished": False,
            "environmentToResolvedConfigurationSelectionLawEstablished": False,
            "transitionProgressToMixFractionLawEstablished": False,
            "allRuntimeWeightProductionLawEstablished": False,
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
