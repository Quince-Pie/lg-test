#!/usr/bin/env python3
"""Prove Apple's exact Parameters weighted-blend pipeline and unity fast path."""

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
import analyze_designlibrary_parameters_animatable_resolver_local_macos_26_6_1 as resolver
import analyze_designlibrary_resolved_recipe_provenance_local_macos_26_6_1 as provenance


RESULT_SCHEMA_VERSION = 1
SOURCE_RELATIVE_PATH = (
    "Analysis/"
    "analyze_designlibrary_parameters_animatable_blend_pipeline_local_macos_26_6_1.py"
)
PROVENANCE_ANALYZER_SHA256 = (
    "7492526b9ce67f21eee811a5a7d0f5effc1348be97f3aa4c2429d13e7c497145"
)
RESOLVER_ANALYZER_SHA256 = (
    "516bbfa6098c32404c289cd5ee9230f480aefac373f35c6f45c57c11583ecd5d"
)
EXPECTED_HARDWARE_MODEL = provenance.EXPECTED_HARDWARE_MODEL
PARAMETERS_BYTE_COUNT = resolver.PARAMETERS_BYTE_COUNT
ANIMATABLE_DATA_BYTE_COUNT = resolver.ANIMATABLE_DATA_BYTE_COUNT

CODE_REGIONS = {
    "parametersToAnimatableData": (
        0x240931924,
        0x2409320F0,
        "e80427b6ae84bdc570a114238b931c9734fc981ee354a556b3b743579ba64f01",
    ),
    "animatableScaleBy": (
        0x240930D54,
        0x240931044,
        "090ef1a9d96be5ffc1e91bd3ef08d0576a4e1ee2cb716bc9634507db0d7d6527",
    ),
    "animatableAdd": (
        0x24093A060,
        0x24093ABD4,
        "416a882870d2fec1cbef5e99cb812e224a42a360f9c4bbfd0cad7e3e44092fbb",
    ),
    "shadowScaleHelper": (
        0x240931044,
        0x2409310A4,
        "5162a7f79fda3078ef34cb2fc747f9b3be273c2a775b03b967776a928e22ba34",
    ),
    "edgeBleedScaleHelper": (
        0x24093110C,
        0x240931168,
        "a3d58707e8853ed55fe635e7ac59996de4fc4619f48e6e4295a0e6a9914b50fb",
    ),
    "highlightsScaleHelper": (
        0x240935128,
        0x240935190,
        "14734fbf39301e6d45e00642ccdbc21f34a4367e2481d1f6ba64f0d416856be2",
    ),
    "radiosityAddHelper": (
        0x240931228,
        0x240931298,
        "829d19eeab78001b7c4c9eb9683d1dd561e6de1a08eddd2dda3d74ea6c184b0c",
    ),
    "packedAddHelper": (
        0x240939C30,
        0x240939C48,
        "721101551c278cd2d282bafc6adbc3de11665f72e5c8e26a16a129a136a328ea",
    ),
    "shadowZeroHelper": (
        0x24093ABD4,
        0x24093ABF8,
        "031224f600de8437c62b369f2a7b5ee61532012200ea05d8297d96c43a3ab2b0",
    ),
    "highlightsZeroHelper": (
        0x24093ABF8,
        0x24093AC2C,
        "a5ccdc8d3fe442067db3e61ce8f0b84fd2a318a2d9d3db58de6540c1f5357314",
    ),
}

EXPECTED_DIRECT_CALLS = {
    "parametersToAnimatableData": (0x24093320C, 0x240933278, 0x2409820D0),
    "animatableScaleBy": (0x2409820DC,),
    "animatableAdd": (0x24098210C,),
    "shadowScaleHelper": (0x240930D98, 0x2409394D8),
    "edgeBleedScaleHelper": (0x240930E74,),
    "highlightsScaleHelper": (
        0x240930EBC,
        0x240930EC8,
        0x24093146C,
        0x240931478,
        0x2409356F0,
        0x2409356FC,
    ),
    "radiosityAddHelper": (0x24093AB9C,),
    "packedAddHelper": (
        0x240934600,
        0x240934654,
        0x240939CB0,
        0x240939DB0,
        0x240939E08,
        0x240939F2C,
        0x24093A010,
        0x24093A228,
        0x24093A454,
        0x24093A4F8,
        0x24093A738,
        0x24093A7B8,
    ),
    "shadowZeroHelper": (0x240931630, 0x2409319C4, 0x240981D9C),
    "highlightsZeroHelper": (0x240931638, 0x240931C98, 0x240981DA8),
}

EXPECTED_FLOATING_INVENTORIES = {
    "parametersToAnimatableData": {
        "fcsel": 1,
        "fcvt": 2,
        "fcvtn": 2,
        "fmov": 2,
    },
    "animatableScaleBy": {
        "fcvt": 1,
        "fmul": 4,
        "fmul.2d": 9,
        "fmul.2s": 4,
        "fmul.4s": 13,
        "fmul.s": 7,
    },
    "animatableAdd": {
        "fadd": 10,
        "fadd.2d": 16,
        "fadd.2s": 4,
        "fadd.4s": 10,
        "fmov": 22,
    },
    "shadowScaleHelper": {
        "fcvt": 1,
        "fmul": 1,
        "fmul.2d": 4,
        "fmul.4s": 4,
        "fmul.s": 1,
    },
    "edgeBleedScaleHelper": {
        "fcvt": 1,
        "fmul": 1,
        "fmul.2d": 1,
        "fmul.4s": 5,
        "fmul.s": 1,
    },
    "highlightsScaleHelper": {
        "fcvt": 1,
        "fmul": 2,
        "fmul.2d": 2,
        "fmul.4s": 4,
        "fmul.s": 1,
    },
    "radiosityAddHelper": {"fadd.2d": 2, "fmov": 2},
    "packedAddHelper": {"fadd.4s": 4},
    "shadowZeroHelper": {},
    "highlightsZeroHelper": {},
}

BYTE_COPY_CALLS = {
    0x240932040: 0x114,
    0x24093A0B0: 0x481,
    0x24093A590: 0x105,
    0x24093A5A4: 0x105,
    0x24093A658: 0x105,
    0x24093ABAC: 0x481,
    0x2409820F0: 0x481,
    0x240982B28: 0x401,
}

EXPECTED_CONVERTER_WRITE_RANGES = (
    (0, 149),
    (160, 233),
    (240, 289),
    (304, 385),
    (400, 513),
    (528, 821),
    (832, 865),
    (880, 945),
    (960, 993),
    (1008, 1041),
    (1056, 1073),
    (1088, 1105),
    (1120, 1153),
)

CRITICAL_INSTRUCTIONS = {
    0x240982020: ("fmov", "d12, #1.00000000"),
    0x24098203C: ("mov", "w8, #0x1"),
    0x2409820A8: ("str", "w8, [x19, #0x7c]"),
    0x2409820C4: ("add", "x8, x19, #0x480"),
    0x2409820C8: ("add", "x20, x19, #0x1, lsl #12"),
    0x2409820CC: ("add", "x20, x20, #0x68"),
    0x2409820D0: ("bl", "0x240931924"),
    0x2409820D4: ("add", "x20, x19, #0x480"),
    0x2409820D8: ("mov.16b", "v0, v9"),
    0x2409820DC: ("bl", "0x240930d54"),
    0x2409820E0: ("add", "x0, x19, #0x1, lsl #12"),
    0x2409820E4: ("add", "x0, x0, #0xd90"),
    0x2409820E8: ("add", "x1, x19, #0x480"),
    0x2409820EC: ("mov", "w2, #0x481"),
    0x2409820F4: ("add", "x8, x19, #0x1, lsl #12"),
    0x2409820F8: ("add", "x8, x8, #0x470"),
    0x2409820FC: ("add", "x0, x19, #0x1, lsl #12"),
    0x240982100: ("add", "x0, x0, #0x900"),
    0x240982104: ("add", "x1, x19, #0x1, lsl #12"),
    0x240982108: ("add", "x1, x1, #0xd90"),
    0x24098210C: ("bl", "0x24093a060"),
    0x240982938: ("ldr", "d9, [x28, x8]"),
    0x240982B04: ("ldr", "x8, [x19, #0xb0]"),
    0x240982B08: ("cmp", "x8, #0x1"),
    0x240982B0C: ("b.ne", "0x2409820c4"),
    0x240982B10: ("fcmp", "d9, d12"),
    0x240982B14: ("b.ne", "0x2409820c4"),
    0x240982B18: ("add", "x0, x19, #0xc60"),
    0x240982B1C: ("add", "x1, x19, #0x1, lsl #12"),
    0x240982B20: ("add", "x1, x1, #0x68"),
    0x240982B24: ("mov", "w2, #0x401"),
    0x240982BE4: ("str", "wzr, [x19, #0x7c]"),
    0x240982CC0: ("ldr", "w8, [x19, #0x7c]"),
    0x240982CC4: ("tbz", "w8, #0x0, 0x240982cd8"),
    0x240982CC8: ("add", "x0, x19, #0x1, lsl #12"),
    0x240982CCC: ("add", "x0, x0, #0x900"),
    0x240982CD0: ("add", "x20, x19, #0xc60"),
    0x240982CD4: ("bl", "0x2409323f4"),
}


class AnalysisError(RuntimeError):
    """Raised when the native blend pipeline differs from the frozen contract."""


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
        raise AnalysisError("blend-pipeline direct call graph differs")
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


def range_record(start: int, end: int) -> Mapping[str, int]:
    return {"start": start, "endExclusive": end, "byteCount": end - start}


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
    if sha256(Path(provenance.__file__).resolve()) != PROVENANCE_ANALYZER_SHA256:
        raise AnalysisError("provenance analyzer dependency differs")
    if sha256(Path(resolver.__file__).resolve()) != RESOLVER_ANALYZER_SHA256:
        raise AnalysisError("resolver analyzer dependency differs")

    text = metadata.parse_section_bytes(
        "__TEXT",
        "__text",
        metadata.run_dyld_info(("-section_bytes", "__TEXT", "__text")),
    )
    builder_start, builder_end, builder_sha256 = provenance.CODE_REGIONS[
        "resolvedRecipeBuilder"
    ]
    builder_code = metadata.read_bytes(
        text.memory, builder_start, builder_end - builder_start
    )
    if hashlib.sha256(builder_code).hexdigest() != builder_sha256:
        raise AnalysisError("ResolvedRecipe builder code differs")

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
    required_regions = list(CODE_REGIONS.values()) + [
        (builder_start, builder_end, builder_sha256)
    ]
    for start, end, _ in required_regions:
        if not set(range(start, end, 4)).issubset(instructions):
            raise AnalysisError("disassembly coverage differs")

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

    copy_records: list[Mapping[str, object]] = []
    for callsite, byte_count in sorted(BYTE_COPY_CALLS.items()):
        target = provenance.branch_destination(text, callsite)
        expected_count_instruction = ("mov", "w2, #{:#x}".format(byte_count))
        if target != provenance.BYTE_COPY_STUB:
            raise AnalysisError("byte-copy target differs")
        if instructions.get(callsite - 4) != expected_count_instruction:
            raise AnalysisError("byte-copy count differs")
        copy_records.append(
            {
                "callsite": "0x{:x}".format(callsite),
                "target": "0x{:x}".format(target),
                "byteCount": byte_count,
            }
        )

    inventories: dict[str, Mapping[str, int]] = {}
    for name, (start, end, _) in CODE_REGIONS.items():
        observed = floating_inventory(instructions, start, end)
        if observed != EXPECTED_FLOATING_INVENTORIES[name]:
            raise AnalysisError(name + " floating instruction inventory differs")
        inventories[name] = observed

    converter_start, converter_end, _ = CODE_REGIONS["parametersToAnimatableData"]
    converter_writes = resolver.output_write_coverage(
        instructions,
        converter_start,
        converter_end,
        {"x8": 0},
        byte_copy_calls={0x240932040: 0x114},
    )
    if converter_writes != EXPECTED_CONVERTER_WRITE_RANGES:
        raise AnalysisError("Parameters-to-AnimatableData write coverage differs")
    converter_written_byte_count = sum(end - start for start, end in converter_writes)
    if converter_written_byte_count != 989:
        raise AnalysisError("converter written-byte count differs")
    converter_unwritten = provenance.complement_ranges(
        converter_writes, ANIMATABLE_DATA_BYTE_COUNT
    )

    scale_arithmetic = {
        mnemonic
        for name in (
            "animatableScaleBy",
            "shadowScaleHelper",
            "edgeBleedScaleHelper",
            "highlightsScaleHelper",
        )
        for mnemonic in inventories[name]
        if mnemonic != "fcvt"
    }
    if not scale_arithmetic or any(
        not mnemonic.startswith("fmul") for mnemonic in scale_arithmetic
    ):
        raise AnalysisError("scale path contains non-multiplication arithmetic")
    add_arithmetic = {
        mnemonic
        for name in ("animatableAdd", "radiosityAddHelper", "packedAddHelper")
        for mnemonic in inventories[name]
        if mnemonic != "fmov"
    }
    if not add_arithmetic or any(
        not mnemonic.startswith("fadd") for mnemonic in add_arithmetic
    ):
        raise AnalysisError("add path contains non-addition arithmetic")

    source_path = Path(__file__).resolve()
    return {
        "designLibraryParametersAnimatableBlendPipelineAnalysisSchemaVersion": (
            RESULT_SCHEMA_VERSION
        ),
        "classification": (
            "native static metadata/code/control-flow/arithmetic analysis; no "
            "Apple application, render, image, public value, selected layer, "
            "runtime weight, crop, or provider return is read"
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
            "provenanceAnalyzerSHA256": PROVENANCE_ANALYZER_SHA256,
            "resolverAnalyzerSHA256": RESOLVER_ANALYZER_SHA256,
        },
        "resolvedRecipeBuilder": {
            "start": "0x{:x}".format(builder_start),
            "endExclusive": "0x{:x}".format(builder_end),
            "byteCount": builder_end - builder_start,
            "sha256": builder_sha256,
        },
        "codeRegions": code_records,
        "directBLCallsites": {
            name: ["0x{:x}".format(address) for address in addresses]
            for name, addresses in direct_calls(text).items()
        },
        "instructionContracts": contracts,
        "authenticatedByteCopies": copy_records,
        "floatingInstructionInventories": inventories,
        "parametersToAnimatableDataWriteCoverage": {
            "writtenRanges": [
                range_record(start, end) for start, end in converter_writes
            ],
            "writtenByteCount": converter_written_byte_count,
            "notWrittenRanges": [
                range_record(start, end) for start, end in converter_unwritten
            ],
            "notWrittenByteCount": (
                ANIMATABLE_DATA_BYTE_COUNT - converter_written_byte_count
            ),
        },
        "weightedRecurrence": {
            "equation": "A_next = A + scale(parameters.animatableData, factor)",
            "parametersToAnimatableDataCallsite": "0x2409820d0",
            "scaleFactorRegister": "d9/v9",
            "scaleCallsite": "0x2409820dc",
            "scaledValueStableCopyCallsite": "0x2409820f0",
            "scaledValueStableCopyByteCount": ANIMATABLE_DATA_BYTE_COUNT,
            "addCallsite": "0x24098210c",
            "resolverCallsite": "0x240982cd4",
        },
        "singleValueUnityFastPath": {
            "collectionCountSlot": "builder stack + 0xb0",
            "collectionCountPredicate": "equal to 1",
            "runtimeFactorRegister": "d9",
            "unityConstantRegister": "d12",
            "unityConstant": 1.0,
            "factorPredicate": "ordered equal to 1.0",
            "parametersSource": "builder stack + 0x1068",
            "parametersDestination": "builder stack + 0xc60",
            "fullParametersCopyCallsite": "0x240982b28",
            "fullParametersCopyByteCount": PARAMETERS_BYTE_COUNT,
            "blendResolverFlagOffset": 0x7C,
            "flagClearedAfterFullCopy": True,
            "finalResolverGate": "tbz bit 0 at 0x240982cc4",
            "fastPathSkipsResolver": True,
        },
        "claims": {
            "weightedParametersBlendPipelineEstablished": True,
            "weightedRecurrenceIsConvertScaleAdd": True,
            "scalePathFloatingArithmeticIsMultiplicationOnly": True,
            "addPathFloatingArithmeticIsAdditionOnly": True,
            "optionalAwareScaleAndAddBranchesAuthenticated": True,
            "singleValueUnityFastPathEstablished": True,
            "singleValueUnityFastPathCopiesAll1025ParametersBytes": True,
            "singleValueUnityFastPathAvoidsFloatingRoundTrip": True,
            "singleValueUnityFastPathSkipsFinalResolver": True,
            "parametersToAnimatableDataWrittenByteCount": (
                converter_written_byte_count
            ),
            "parametersToAnimatableDataNotWrittenByteCount": (
                ANIMATABLE_DATA_BYTE_COUNT - converter_written_byte_count
            ),
            "publicControlsToLayerSelectionLawEstablished": False,
            "environmentToLayerSelectionLawEstablished": False,
            "runtimeWeightProductionLawEstablished": False,
            "allNestedConversionSemanticsDecoded": False,
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
        resolver.AnalysisError,
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
