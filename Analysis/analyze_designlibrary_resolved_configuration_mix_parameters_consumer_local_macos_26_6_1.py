#!/usr/bin/env python3
"""Prove ResolvedConfiguration.Mix routing into the native Parameters mixer."""

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
import analyze_designlibrary_configuration_mix_selection_local_macos_26_6_1 as selection
import analyze_designlibrary_resolved_composite_weight_pipeline_local_macos_26_6_1 as weights
import analyze_designlibrary_resolved_recipe_provenance_local_macos_26_6_1 as provenance


RESULT_SCHEMA_VERSION = 1
SOURCE_RELATIVE_PATH = (
    "Analysis/"
    "analyze_designlibrary_resolved_configuration_mix_parameters_consumer_"
    "local_macos_26_6_1.py"
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
SELECTION_ANALYZER_SHA256 = (
    "93c95c65c326765c675f3f4e727285706bf48adb5d42d5bdcd11ad0c3600d1de"
)
EXPECTED_HARDWARE_MODEL = provenance.EXPECTED_HARDWARE_MODEL
PARAMETERS_BYTE_COUNT = 0x401

DESCRIPTORS = {
    "parameters": {
        "address": 0x2409D2878,
        "name": "Parameters",
        "fields": metadata.PARAMETERS_FIELDS,
        "offsets": (
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
        ),
        "size": PARAMETERS_BYTE_COUNT,
        "stride": 0x408,
    },
    "resolvedCompositeKey": selection.DESCRIPTORS["resolvedCompositeKey"],
    "resolvedConfiguration": selection.DESCRIPTORS["resolvedConfiguration"],
    "resolvedConfigurationMix": selection.DESCRIPTORS[
        "resolvedConfigurationMix"
    ],
}

EXPECTED_TYPE_REFERENCES = {
    key: value
    for key, value in selection.EXPECTED_TYPE_REFERENCES.items()
    if key[0] in DESCRIPTORS
}

CODE_REGIONS = {
    "parametersMixer": (
        0x2409406A8,
        0x2409423E8,
        "5b7a4251a998d06a37ed3eea775f2886e286ce91fe7f34e01b8c40551fbbb28a",
    ),
    "resolvedConfigurationParametersConsumer": (
        0x2409423E8,
        0x240943DB0,
        "d868539b5a430eeb94351221e6f8bacb7d4dd6cd8fc39be56996f84ef3b5d78a",
    ),
    "builderKeyConsumerSlice": (
        0x24098293C,
        0x240982AB8,
        "f3b19e0951d50fd0c70dcf815ac0518e68781838ffec820dadc14f8a342797ab",
    ),
}

TARGET_STARTS = {
    CODE_REGIONS["parametersMixer"][0]: "parametersMixer",
    CODE_REGIONS["resolvedConfigurationParametersConsumer"][0]: (
        "resolvedConfigurationParametersConsumer"
    ),
}

EXPECTED_DIRECT_CALLS = {
    "parametersMixer": (
        0x240942A6C,
        0x24096A9E8,
        0x24096B398,
        0x24096BE5C,
    ),
    "resolvedConfigurationParametersConsumer": (
        0x2409429F8,
        0x240942A50,
        0x240982A44,
    ),
}

EXPECTED_PARAMETERS_MIXER_CALL_GRAPH = {
    0x240917F64: (0x2409407A0, 0x240940918),
    0x240917F80: (0x240941854, 0x240941A68),
    0x24093ACAC: (0x240940B14,),
    0x24093ACD0: (0x240940B7C,),
    0x24093B6C4: (0x240941E9C,),
    0x24093D0E0: (0x240940A5C,),
    0x24093D8C8: (0x240940C70,),
    0x24093E070: (0x2409414DC,),
    0x24093E8AC: (0x2409417AC,),
    0x24093E9E4: (0x240941D3C, 0x240941E88),
    0x240995160: (0x240941008, 0x240941150, 0x2409411F8),
    0x2409A40E0: (0x2409417E8,),
    0x2409A5910: (0x240940718, 0x24094184C, 0x240941A60, 0x2409423B0),
}

EXPECTED_FLOATING_INVENTORIES = {
    "parametersMixer": {
        "fadd": 16,
        "fadd.2d": 8,
        "fadd.2s": 3,
        "fcmeq.2d": 6,
        "fcmeq.4s": 1,
        "fcmp": 36,
        "fcsel": 17,
        "fcvt": 2,
        "fmov": 62,
        "fmul": 32,
        "fmul.2d": 16,
        "fmul.2s": 6,
        "fsub": 1,
    },
    "resolvedConfigurationParametersConsumer": {
        "fadd": 3,
        "fcmp": 2,
        "fcsel": 8,
        "fmov": 16,
        "fmul": 1,
    },
    "builderKeyConsumerSlice": {"fcmp": 1, "fmov": 1},
}

CRITICAL_INSTRUCTIONS = {
    # The dictionary iterator materializes one full Key at x24. Its first 48
    # bytes are copied twice and one copy is passed as the consumer's x0 input.
    0x24098293C: ("mov", "x0, x28"),
    0x240982940: ("ldr", "x24, [x19, #0x90]"),
    0x240982944: ("mov", "x1, x24"),
    0x240982948: ("bl", "0x24092e834"),
    0x2409829D8: ("ldp", "q0, q1, [x24]"),
    0x2409829E4: ("ldr", "q0, [x24, #0x20]"),
    0x2409829E8: ("ldp", "q2, q1, [x24]"),
    0x2409829F8: ("ldr", "q0, [x24, #0x20]"),
    0x240982A24: ("add", "x0, x19, #0xb70"),
    0x240982A28: ("add", "x1, x19, #0x980"),
    0x240982A2C: ("bl", "0x240944850"),
    0x240982A30: ("add", "x8, x19, #0x1, lsl #12"),
    0x240982A34: ("add", "x8, x8, #0x68"),
    0x240982A38: ("add", "x0, x19, #0x480"),
    0x240982A3C: ("mov", "x1, x20"),
    0x240982A40: ("mov", "x2, x23"),
    0x240982A44: ("bl", "0x2409423e8"),
    0x240982AA8: ("add", "x0, x24, x25"),
    # The consumer copies the 48-byte input, decodes base tag 2 as Mix, and
    # loads the exact boxed from/to/fraction layout established by metadata.
    0x24094243C: ("mov", "x20, x0"),
    0x240942440: ("mov", "x21, x8"),
    0x24094259C: ("ldp", "q0, q1, [x20]"),
    0x2409425A8: ("ldr", "q0, [x20, #0x20]"),
    0x240942638: ("ldr", "x16, [x19, #0x2320]"),
    0x24094263C: ("ldrb", "w8, [x10, #0x8fc]"),
    0x240942640: ("lsr", "w9, w8, #6"),
    0x240942958: ("cmp", "w9, #0x2"),
    0x240942960: ("b.ne", "0x240942e54"),
    0x240942964: ("ldp", "q0, q1, [x16, #0x40]"),
    0x240942970: ("ldr", "q0, [x16, #0x60]"),
    0x240942978: ("ldr", "x8, [x16, #0x70]"),
    0x24094297C: ("str", "x8, [x19, #0x11b0]"),
    0x240942980: ("ldp", "q0, q1, [x16, #0x10]"),
    0x24094298C: ("ldr", "q0, [x16, #0x30]"),
    # Both endpoints enter this same consumer recursively.
    0x2409429E4: ("add", "x8, x19, #0x160"),
    0x2409429E8: ("add", "x0, x19, #0x1, lsl #12"),
    0x2409429EC: ("add", "x0, x0, #0xa30"),
    0x2409429F8: ("bl", "0x2409423e8"),
    0x240942A38: ("add", "x8, x19, #0x1, lsl #12"),
    0x240942A3C: ("add", "x8, x8, #0xa30"),
    0x240942A40: ("add", "x0, x19, #0x1, lsl #12"),
    0x240942A44: ("add", "x0, x0, #0x560"),
    0x240942A50: ("bl", "0x2409423e8"),
    # The stored fraction is loaded directly into d0; the two full recursive
    # Parameters values and output pointer are then supplied to the mixer.
    0x240942A54: ("ldr", "d0, [x19, #0x11b0]"),
    0x240942A58: ("add", "x8, x19, #0x1, lsl #12"),
    0x240942A5C: ("add", "x8, x8, #0x560"),
    0x240942A60: ("add", "x0, x19, #0x1, lsl #12"),
    0x240942A64: ("add", "x0, x0, #0xa30"),
    0x240942A68: ("add", "x20, x19, #0x160"),
    0x240942A6C: ("bl", "0x2409406a8"),
    # Mixer ABI and exact 1,025-byte initial/final transfers.
    0x2409406F4: ("mov", "x22, x20"),
    0x2409406F8: ("str", "q0, [sp, #0x180]"),
    0x2409406FC: ("mov", "x21, x0"),
    0x240940700: ("str", "x8, [sp, #0x148]"),
    0x24094070C: ("add", "x0, sp, #0x600"),
    0x240940710: ("mov", "x1, x22"),
    0x240940714: ("mov", "w2, #0x401"),
    # Backdrop scale is first for t <= 0, second for t >= 1, and the ordered
    # larger endpoint for 0 < t < 1.
    0x24094071C: ("ldr", "q1, [sp, #0x180]"),
    0x240940720: ("fcmp", "d1, #0.0"),
    0x240940724: ("b.ls", "0x240940750"),
    0x240940728: ("fmov", "d0, #1.00000000"),
    0x24094072C: ("fcmp", "d1, d0"),
    0x240940730: ("b.ge", "0x240940748"),
    0x240940734: ("ldr", "s0, [x22]"),
    0x240940738: ("ldr", "s1, [x21]"),
    0x24094073C: ("fcmp", "s0, s1"),
    0x240940740: ("fcsel", "s0, s1, s0, ls"),
    0x240940748: ("ldr", "s0, [x21]"),
    0x24094074C: ("str", "s0, [sp, #0x600]"),
    # The universal binary64 weights are t and oneMinusT = 1.0 - t. The only
    # two fcvt instructions in the whole mixer derive their binary32 forms.
    0x240940CEC: ("ldr", "q19, [sp, #0x180]"),
    0x240940D20: ("fmov", "d16, #1.00000000"),
    0x240940D24: ("fsub", "d16, d16, d19"),
    0x240940D4C: ("str", "q16, [sp, #0x150]"),
    0x240940D50: ("fcvt", "s6, d16"),
    0x240940D58: ("fcvt", "s7, d19"),
    0x240941F50: ("ldr", "x0, [sp, #0x148]"),
    0x2409423A8: ("add", "x1, sp, #0x600"),
    0x2409423AC: ("mov", "w2, #0x401"),
}


class AnalysisError(RuntimeError):
    """Raised when native Parameters-consumer evidence differs."""


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
        descriptor = by_address.get(int(expected["address"]))
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
            if layout["size"] != expected["size"] or layout["stride"] != expected[
                "stride"
            ]:
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
        raise AnalysisError("Parameters-consumer direct callers differ")
    return frozen


def region_call_graph(
    text: metadata.Section, start: int, end: int
) -> Mapping[int, tuple[int, ...]]:
    calls: dict[int, list[int]] = {}
    for address in range(start, end, 4):
        instruction = struct.unpack(
            "<I", metadata.read_bytes(text.memory, address, 4)
        )[0]
        if instruction & 0xFC000000 != 0x94000000:
            continue
        destination = address + provenance.sign_extend(
            instruction & 0x03FFFFFF, 26
        ) * 4
        calls.setdefault(destination, []).append(address)
    return {destination: tuple(addresses) for destination, addresses in calls.items()}


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
        (selection.__file__, SELECTION_ANALYZER_SHA256, "selection analyzer"),
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
        raise AnalysisError("Parameters-consumer floating inventories differ")

    mixer_start, mixer_end, _ = CODE_REGIONS["parametersMixer"]
    mixer_call_graph = region_call_graph(text, mixer_start, mixer_end)
    if mixer_call_graph != EXPECTED_PARAMETERS_MIXER_CALL_GRAPH:
        raise AnalysisError("Parameters mixer direct call graph differs")

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
        "designLibraryResolvedConfigurationMixParametersConsumerAnalysisSchemaVersion": (
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
            "selectionAnalyzerSHA256": SELECTION_ANALYZER_SHA256,
        },
        "swiftDescriptors": descriptors,
        "codeRegions": code_records,
        "directBLCallsites": {
            name: ["0x{:x}".format(address) for address in addresses]
            for name, addresses in direct_calls(text).items()
        },
        "parametersMixerDirectCallGraph": {
            "0x{:x}".format(destination): [
                "0x{:x}".format(address) for address in addresses
            ]
            for destination, addresses in mixer_call_graph.items()
        },
        "floatingInstructionInventories": inventories,
        "instructionContracts": contracts,
        "consumerModel": {
            "builderInput": (
                "the first 48 bytes of each ResolvedComposite.Key, independently "
                "of its following ColorScheme field"
            ),
            "resolvedConfigurationByteCount": 48,
            "mixDiscriminatorValue": 2,
            "mixPayloadBoxOffsets": {
                "from": 0x10,
                "to": 0x40,
                "fraction": 0x70,
            },
            "mixPayloadSemanticOffsets": {
                "from": 0,
                "to": 48,
                "fraction": 96,
            },
            "endpointOperation": (
                "invoke the same ResolvedConfiguration-to-Parameters consumer "
                "recursively once for from and once for to"
            ),
            "fractionOperation": (
                "load the stored binary64 fraction directly into d0 immediately "
                "before the Parameters mixer call"
            ),
        },
        "parametersMixerModel": {
            "fromRegister": "x20",
            "toRegister": "x0",
            "fractionRegister": "d0",
            "outputRegister": "x8",
            "parametersByteCount": PARAMETERS_BYTE_COUNT,
            "initialTransfer": "copy all 1,025 from bytes into working output",
            "finalTransfer": "copy all 1,025 working bytes to the output pointer",
            "universalBinary64Weights": {
                "to": "t",
                "from": "1.0 - t",
                "operation": "one binary64 fsub",
            },
            "binary32WeightConversionCount": 2,
            "backdropScale": {
                "type": "Float",
                "tLessThanOrEqualToZero": "from",
                "tGreaterThanOrEqualToOne": "to",
                "strictInteriorOrderedInputs": "larger of from and to",
            },
            "specializedBranchesRemain": (
                "optional-zero canonicalization, endpoint selection, and nested "
                "helper policies still require field-by-field semantic decoding"
            ),
        },
        "claims": {
            "builderKeyResolvedConfigurationConsumerJoinEstablished": True,
            "builderSeparatesResolvedConfigurationAndColorScheme": True,
            "resolvedConfigurationMixDispatchEstablished": True,
            "resolvedConfigurationMixEndpointsRecursivelyConsumed": True,
            "resolvedConfigurationMixFractionPassedToMixerBitwiseUnchanged": True,
            "parametersMixerCompleteCodeRegionEstablished": True,
            "parametersMixerCompleteDirectCallGraphEstablished": True,
            "parametersMixerExactInputAndOutputByteCountsEstablished": True,
            "parametersMixerUniversalWeightDerivationEstablished": True,
            "parametersMixerBackdropScalePolicyEstablished": True,
            "allParametersFieldBlendSemanticsEstablished": False,
            "transitionProgressToPublicConfigurationMixByLawEstablished": False,
            "publicControlsToResolvedConfigurationSelectionLawEstablished": False,
            "environmentToResolvedConfigurationSelectionLawEstablished": False,
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
    except (
        AnalysisError,
        metadata.AnalysisError,
        provenance.AnalysisError,
        weights.AnalysisError,
        selection.AnalysisError,
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
