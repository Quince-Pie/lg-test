#!/usr/bin/env python3
"""Prove the exact Color.Resolved policy used by the Parameters mixer."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import analyze_designlibrary_background_filter_metadata_local_macos_26_6_1 as metadata
import analyze_designlibrary_resolved_recipe_provenance_local_macos_26_6_1 as provenance


RESULT_SCHEMA_VERSION = 1
SOURCE_RELATIVE_PATH = (
    "Analysis/analyze_designlibrary_resolved_color_mixer_local_macos_26_6_1.py"
)
METADATA_ANALYZER_SHA256 = (
    "a50569535c5452a4a4e3db0940be09968b4de38bc86aeda12c95ab3c0a653aff"
)
PROVENANCE_ANALYZER_SHA256 = (
    "7492526b9ce67f21eee811a5a7d0f5effc1348be97f3aa4c2429d13e7c497145"
)
EXPECTED_HARDWARE_MODEL = "MacBookPro18,2"
COLOR_MIXER_START = 0x240995160
COLOR_MIXER_END = 0x24099536C
COLOR_MIXER_SHA256 = (
    "20b831c1e0c761aebe66934b1a655aa87d53741cea18896f411d8aa5b174f0c0"
)
PRIVATE_PROBE_NAME = (
    "probe_designlibrary_resolved_color_mixer_local_macos_26_6_1.c"
)
PRIVATE_BRIDGE_NAME = "invoke_designlibrary_resolved_color_mixer_arm64.S"
IMPORT_PROBE_NAME = (
    "probe_designlibrary_resolved_color_import_targets_local_macos_26_6_1.c"
)
SWIFT_PROBE_NAME = (
    "probe_swiftui_resolved_color_components_local_macos_26_6_1.swift"
)
PRIVATE_PROBE_SHA256 = (
    "9fc32ad50623e6eaab9b706741c658c71da2618d3aa4a9aaba4d320cd79e3f21"
)
PRIVATE_BRIDGE_SHA256 = (
    "c0279535a1627749e03ea71d4ee82e422d23566cd7c23dcadc08ab599ed6c07b"
)
IMPORT_PROBE_SHA256 = (
    "f076cb3e40f136e787b1c4ae3365c3dd7a7e5e7c1583537b381baf823144b465"
)
SWIFT_PROBE_SHA256 = (
    "770867a91881fbba8d5ae34802d71e9b5f9b63e4ba0e87ca7fe02c02b958ba09"
)
RANDOM_SEED = 0x4C475243
RANDOM_SAMPLE_COUNT = 192

EXPECTED_DIRECT_CALLS = {
    0x2409A4120: (0x2409951B4,),
    0x2409A4210: (0x240995344,),
    0x2409A4250: (0x240995240, 0x240995260),
    0x2409A4260: (0x2409952D8, 0x2409952F0),
    0x2409A4280: (0x2409952A0, 0x2409952BC),
}

EXPECTED_IMPORT_TARGETS = {
    0x2409A4120: (
        0x22DCE4590,
        "/System/Library/Frameworks/SwiftUICore.framework/Versions/A/SwiftUICore",
        "$s7SwiftUI5ColorV13RGBColorSpaceOMa",
    ),
    0x2409A4210: (
        0x22DBDBCC0,
        "/System/Library/Frameworks/SwiftUICore.framework/Versions/A/SwiftUICore",
        "$s7SwiftUI5ColorV8ResolvedV10colorSpace3red5green4blue7opacityAeC08RGBColorF0O_S4ftcfC",
    ),
    0x2409A4250: (
        0x22DBDC774,
        "/System/Library/Frameworks/SwiftUICore.framework/Versions/A/SwiftUICore",
        "$s7SwiftUI5ColorV8ResolvedV3redSfvg",
    ),
    0x2409A4260: (
        0x22DBDC8C8,
        "/System/Library/Frameworks/SwiftUICore.framework/Versions/A/SwiftUICore",
        "$s7SwiftUI5ColorV8ResolvedV4blueSfvg",
    ),
    0x2409A4280: (
        0x22DBDC820,
        "/System/Library/Frameworks/SwiftUICore.framework/Versions/A/SwiftUICore",
        "$s7SwiftUI5ColorV8ResolvedV5greenSfvg",
    ),
}

CRITICAL_INSTRUCTIONS = {
    # The private ABI receives `to` as s0...s3, t as d4, and `from` as
    # s5...s7 plus its alpha in the first stack slot.
    0x240995188: ("mov.16b", "v11, v7"),
    0x24099518C: ("stp", "s7, s3, [x29, #-0x70]"),
    0x240995190: ("mov.16b", "v9, v6"),
    0x240995194: ("mov.16b", "v8, v5"),
    0x240995198: ("stur", "d4, [x29, #-0x68]"),
    0x24099519C: ("mov.16b", "v13, v2"),
    0x2409951A0: ("mov.16b", "v14, v1"),
    0x2409951A4: ("mov.16b", "v15, v0"),
    0x2409951A8: ("ldr", "s10, [x29, #0x10]"),
    # Runtime metadata constructs RGBColorSpace case tag zero (`sRGB`).
    0x2409951B0: ("mov", "x0, #0x0"),
    0x2409951B4: ("bl", "0x2409a4120"),
    0x240995314: ("ldr", "w1, [x8]"),
    0x24099532C: ("blraa", "x8, x17"),
    # Public component getters are called once for each endpoint and channel.
    0x240995240: ("bl", "0x2409a4250"),
    0x240995260: ("bl", "0x2409a4250"),
    0x2409952A0: ("bl", "0x2409a4280"),
    0x2409952BC: ("bl", "0x2409a4280"),
    0x2409952D8: ("bl", "0x2409a4260"),
    0x2409952F0: ("bl", "0x2409a4260"),
    # Exactly one binary64 subtraction and two conversions create the weights.
    0x240995264: ("fmov", "d1, #1.00000000"),
    0x240995268: ("ldur", "d2, [x29, #-0x68]"),
    0x24099526C: ("fsub", "d1, d1, d2"),
    0x240995270: ("fcvt", "s13, d1"),
    0x240995278: ("fcvt", "s10, d2"),
    # Red, green, blue, and alpha each use two binary32 multiplies and one add.
    0x240995274: ("fmul", "s1, s11, s13"),
    0x24099527C: ("fmul", "s0, s0, s10"),
    0x240995280: ("fadd", "s0, s1, s0"),
    0x2409952C0: ("fmul", "s1, s11, s13"),
    0x2409952C4: ("fmul", "s0, s0, s10"),
    0x2409952C8: ("fadd", "s11, s1, s0"),
    0x2409952F4: ("fmul", "s1, s12, s13"),
    0x2409952F8: ("fmul", "s0, s0, s10"),
    0x2409952FC: ("fadd", "s12, s1, s0"),
    0x240995300: ("fmul", "s0, s8, s13"),
    0x240995304: ("fmul", "s1, s9, s10"),
    0x240995308: ("fadd", "s8, s1, s0"),
    # The four mixed public components are reconstructed as sRGB Resolved.
    0x240995334: ("ldur", "s0, [x29, #-0x68]"),
    0x240995338: ("mov.16b", "v1, v11"),
    0x24099533C: ("mov.16b", "v2, v12"),
    0x240995340: ("mov.16b", "v3, v8"),
    0x240995344: ("bl", "0x2409a4210"),
}


class AnalysisError(RuntimeError):
    """Raised when the native resolved-color evidence differs."""


@dataclass(frozen=True)
class Sample:
    label: str
    from_words: tuple[int, int, int, int]
    to_words: tuple[int, int, int, int]
    fraction_bits: int


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def run_checked(arguments: Sequence[str], input_bytes: bytes = b"") -> bytes:
    completed = subprocess.run(
        list(arguments),
        check=False,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise AnalysisError(
            "command failed: "
            + " ".join(arguments)
            + ": "
            + completed.stderr.decode("utf-8", errors="replace").strip()
        )
    return completed.stdout


def float32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def float32_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def bits_float32(value: int) -> float:
    return struct.unpack("<f", struct.pack("<I", value))[0]


def float64_bits(value: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", value))[0]


def bits_float64(value: int) -> float:
    return struct.unpack("<d", struct.pack("<Q", value))[0]


def words(values: Sequence[float]) -> tuple[int, int, int, int]:
    if len(values) != 4:
        raise AnalysisError("a resolved color must contain four components")
    result = tuple(float32_bits(value) for value in values)
    return result  # type: ignore[return-value]


def sample_set() -> list[Sample]:
    threshold = float32_bits(0.0031308)
    curated = [
        Sample("reference", words((0.2, 0.3, 0.4, 0.5)), words((0.8, 0.7, 0.6, 0.9)), float64_bits(0.25)),
        Sample("reverse", words((0.8, 0.7, 0.6, 0.9)), words((0.2, 0.3, 0.4, 0.5)), float64_bits(0.75)),
        Sample("zero-to-one", words((0.0, 0.0, 0.0, 0.0)), words((1.0, 1.0, 1.0, 1.0)), float64_bits(0.5)),
        Sample("signed-zero", (0x80000000, 0, 0x80000000, 0), (0, 0x80000000, 0, 0x80000000), float64_bits(0.5)),
        Sample("same", words((0.125, 0.25, 0.5, 0.75)), words((0.125, 0.25, 0.5, 0.75)), float64_bits(0.375)),
        Sample("linear-threshold-below", (threshold - 1, threshold - 1, threshold - 1, float32_bits(0.2)), (threshold, threshold, threshold, float32_bits(0.8)), float64_bits(0.5)),
        Sample("linear-threshold-above", (threshold, threshold, threshold, float32_bits(0.2)), (threshold + 1, threshold + 1, threshold + 1, float32_bits(0.8)), float64_bits(0.5)),
        Sample("extended-range", words((-0.25, 1.25, 1.5, -0.1)), words((1.5, -0.125, 0.75, 1.2)), float64_bits(0.625)),
        Sample("subnormal", (1, 0x80000001, 0x00800000, float32_bits(0.1)), (2, 0x80000002, 0x007FFFFF, float32_bits(0.9)), float64_bits(0.5)),
        Sample("extrapolate-low", words((0.1, 0.2, 0.3, 0.4)), words((0.7, 0.8, 0.9, 1.0)), float64_bits(-0.25)),
        Sample("extrapolate-high", words((0.1, 0.2, 0.3, 0.4)), words((0.7, 0.8, 0.9, 1.0)), float64_bits(1.25)),
        Sample("exact-from", words((0.1, 0.2, 0.3, 0.4)), words((0.7, 0.8, 0.9, 1.0)), float64_bits(0.0)),
        Sample("exact-to", words((0.1, 0.2, 0.3, 0.4)), words((0.7, 0.8, 0.9, 1.0)), float64_bits(1.0)),
    ]
    fractions = (-0.25, 0.0, 2.0 ** -24, 0.25, 0.5, 0.75, 1.0 - 2.0 ** -24, 1.0, 1.25)
    generator = random.Random(RANDOM_SEED)
    for index in range(RANDOM_SAMPLE_COUNT):
        from_values = tuple(
            generator.uniform(-0.25, 1.5) for _ in range(3)
        ) + (generator.uniform(-0.2, 1.2),)
        to_values = tuple(
            generator.uniform(-0.25, 1.5) for _ in range(3)
        ) + (generator.uniform(-0.2, 1.2),)
        if index < len(fractions):
            fraction = fractions[index]
        else:
            fraction = generator.uniform(-0.25, 1.25)
        curated.append(
            Sample(
                "random-{:03d}".format(index),
                words(from_values),
                words(to_values),
                float64_bits(fraction),
            )
        )
    return curated


def compile_probes(analysis: Path, temporary: Path) -> Mapping[str, object]:
    private = temporary / "resolved-color-mixer-probe"
    imports = temporary / "resolved-color-import-targets-probe"
    swift = temporary / "resolved-color-components-probe"
    private_arguments = (
        "/usr/bin/xcrun", "clang", "-std=c23", "-arch", "arm64", "-O2",
        "-Wall", "-Wextra", "-Wpedantic", "-Werror",
        str(analysis / PRIVATE_PROBE_NAME), str(analysis / PRIVATE_BRIDGE_NAME),
        "-o", str(private),
    )
    import_arguments = (
        "/usr/bin/xcrun", "clang", "-std=c23", "-arch", "arm64e", "-O2",
        "-Wall", "-Wextra", "-Wpedantic", "-Werror",
        str(analysis / IMPORT_PROBE_NAME), "-o", str(imports),
    )
    swift_arguments = (
        "/usr/bin/xcrun", "swiftc", "-O", str(analysis / SWIFT_PROBE_NAME),
        "-o", str(swift),
    )
    for arguments in (private_arguments, import_arguments, swift_arguments):
        run_checked(arguments)
    return {
        "private": private,
        "imports": imports,
        "swift": swift,
        "commands": {
            "private": [Path(value).name if value.startswith(str(analysis)) or value.startswith(str(temporary)) else value for value in private_arguments],
            "imports": [Path(value).name if value.startswith(str(analysis)) or value.startswith(str(temporary)) else value for value in import_arguments],
            "swift": [Path(value).name if value.startswith(str(analysis)) or value.startswith(str(temporary)) else value for value in swift_arguments],
        },
    }


def parse_import_targets(output: str) -> tuple[int, Mapping[int, tuple[int, str, str]]]:
    lines = output.splitlines()
    if not lines or not lines[0].startswith("rgb-color-space-tag "):
        raise AnalysisError("resolved-color import probe lacks the RGB tag")
    tag = int(lines[0].split()[1])
    targets: dict[int, tuple[int, str, str]] = {}
    for line in lines[1:]:
        fields = line.split(" ", 3)
        if len(fields) != 4:
            raise AnalysisError("resolved-color import target record differs")
        targets[int(fields[0], 16)] = (int(fields[1], 16), fields[2], fields[3])
    return tag, targets


def swift_batch(executable: Path, requests: Sequence[tuple[str, Sequence[int]]]) -> list[tuple[int, int, int, int]]:
    payload = "".join(
        operation + " " + " ".join("{:08x}".format(word) for word in values) + "\n"
        for operation, values in requests
    ).encode("ascii")
    output = run_checked((str(executable), "batch"), payload).decode("ascii")
    lines = output.splitlines()
    if len(lines) != len(requests):
        raise AnalysisError("Swift resolved-color response count differs")
    result = []
    for line in lines:
        fields = line.split()
        if len(fields) != 4:
            raise AnalysisError("Swift resolved-color response width differs")
        result.append(tuple(int(field, 16) for field in fields))
    return result  # type: ignore[return-value]


def fmul(left: int, right: int) -> int:
    return float32_bits(float32(bits_float32(left) * bits_float32(right)))


def fadd(left: int, right: int) -> int:
    return float32_bits(float32(bits_float32(left) + bits_float32(right)))


def mixed_public_components(
    from_components: Sequence[int],
    to_components: Sequence[int],
    fraction_bits: int,
) -> tuple[int, int, int, int]:
    fraction = bits_float64(fraction_bits)
    from_weight = float32_bits(float32(1.0 - fraction))
    to_weight = float32_bits(float32(fraction))
    mixed = []
    for index in range(3):
        from_product = fmul(from_components[index], from_weight)
        to_product = fmul(to_components[index], to_weight)
        mixed.append(fadd(from_product, to_product))
    from_alpha = fmul(from_components[3], from_weight)
    to_alpha = fmul(to_components[3], to_weight)
    mixed.append(fadd(to_alpha, from_alpha))
    return tuple(mixed)  # type: ignore[return-value]


def capture_samples(
    private: Path, swift: Path, samples: Sequence[Sample]
) -> Mapping[str, object]:
    inspect_requests = []
    private_input = bytearray()
    for sample in samples:
        inspect_requests.extend(
            (("inspect", sample.from_words), ("inspect", sample.to_words))
        )
        private_input.extend(
            struct.pack(
                "<8IQ", *sample.from_words, *sample.to_words, sample.fraction_bits
            )
        )
    inspected = swift_batch(swift, inspect_requests)
    public_components = []
    for index, sample in enumerate(samples):
        public_components.append(
            mixed_public_components(
                inspected[index * 2], inspected[index * 2 + 1], sample.fraction_bits
            )
        )
    public_outputs = swift_batch(
        swift, [("construct", components) for components in public_components]
    )
    private_output = run_checked((str(private),), bytes(private_input))
    if len(private_output) != len(samples) * 16:
        raise AnalysisError("private resolved-color output length differs")
    private_outputs = [
        struct.unpack_from("<4I", private_output, index * 16)
        for index in range(len(samples))
    ]
    for index, (private_words, public_words) in enumerate(
        zip(private_outputs, public_outputs)
    ):
        if private_words != public_words:
            raise AnalysisError(
                "private/public resolved-color law differs for " + samples[index].label
            )

    detailed = []
    detailed_indexes = set(range(13))
    detailed_indexes.update(range(13, min(21, len(samples))))
    for index in sorted(detailed_indexes):
        sample = samples[index]
        detailed.append(
            {
                "label": sample.label,
                "fromRawWords": ["0x{:08x}".format(word) for word in sample.from_words],
                "toRawWords": ["0x{:08x}".format(word) for word in sample.to_words],
                "fractionBits": "0x{:016x}".format(sample.fraction_bits),
                "fromPublicWords": ["0x{:08x}".format(word) for word in inspected[index * 2]],
                "toPublicWords": ["0x{:08x}".format(word) for word in inspected[index * 2 + 1]],
                "mixedPublicWords": ["0x{:08x}".format(word) for word in public_components[index]],
                "outputRawWords": ["0x{:08x}".format(word) for word in private_outputs[index]],
            }
        )
    public_output_bytes = b"".join(struct.pack("<4I", *value) for value in public_outputs)
    return {
        "curatedSampleCount": len(samples) - RANDOM_SAMPLE_COUNT,
        "randomSampleCount": RANDOM_SAMPLE_COUNT,
        "totalSampleCount": len(samples),
        "randomSeed": "0x{:08x}".format(RANDOM_SEED),
        "inputSHA256": digest_bytes(bytes(private_input)),
        "privateOutputSHA256": digest_bytes(private_output),
        "publicCompositionOutputSHA256": digest_bytes(public_output_bytes),
        "allOutputsBitwiseEqual": True,
        "detailedSamples": detailed,
    }


def static_evidence() -> Mapping[str, object]:
    text = metadata.parse_section_bytes(
        "__TEXT",
        "__text",
        metadata.run_dyld_info(("-section_bytes", "__TEXT", "__text")),
    )
    code = metadata.read_bytes(
        text.memory, COLOR_MIXER_START, COLOR_MIXER_END - COLOR_MIXER_START
    )
    if digest_bytes(code) != COLOR_MIXER_SHA256:
        raise AnalysisError("resolved-color mixer code differs")
    instructions = provenance.parse_instructions(
        metadata.run_dyld_info(("-disassemble",))
    )
    calls: dict[int, list[int]] = {}
    for address in range(COLOR_MIXER_START, COLOR_MIXER_END, 4):
        instruction = struct.unpack(
            "<I", metadata.read_bytes(text.memory, address, 4)
        )[0]
        if instruction & 0xFC000000 == 0x94000000:
            destination = address + provenance.sign_extend(
                instruction & 0x03FFFFFF, 26
            ) * 4
            calls.setdefault(destination, []).append(address)
    frozen_calls = {key: tuple(value) for key, value in calls.items()}
    if frozen_calls != EXPECTED_DIRECT_CALLS:
        raise AnalysisError("resolved-color mixer direct calls differ")
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
    return {
        "start": "0x{:x}".format(COLOR_MIXER_START),
        "endExclusive": "0x{:x}".format(COLOR_MIXER_END),
        "byteCount": len(code),
        "instructionCount": len(code) // 4,
        "sha256": digest_bytes(code),
        "directCalls": {
            "0x{:x}".format(destination): [
                "0x{:x}".format(address) for address in addresses
            ]
            for destination, addresses in frozen_calls.items()
        },
        "instructionContracts": contracts,
    }


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

    analysis = Path(__file__).resolve().parent
    dependencies = (
        (Path(metadata.__file__).resolve(), METADATA_ANALYZER_SHA256, "metadata analyzer"),
        (Path(provenance.__file__).resolve(), PROVENANCE_ANALYZER_SHA256, "provenance analyzer"),
        (analysis / PRIVATE_PROBE_NAME, PRIVATE_PROBE_SHA256, "private probe"),
        (analysis / PRIVATE_BRIDGE_NAME, PRIVATE_BRIDGE_SHA256, "private bridge"),
        (analysis / IMPORT_PROBE_NAME, IMPORT_PROBE_SHA256, "import probe"),
        (analysis / SWIFT_PROBE_NAME, SWIFT_PROBE_SHA256, "Swift probe"),
    )
    for path, expected, label in dependencies:
        if sha256(path) != expected:
            raise AnalysisError(label + " source differs")

    code = static_evidence()
    with tempfile.TemporaryDirectory(prefix="lg-resolved-color-") as directory:
        executables = compile_probes(analysis, Path(directory))
        import_output = run_checked((str(executables["imports"]),)).decode("utf-8")
        rgb_tag, import_targets = parse_import_targets(import_output)
        if rgb_tag != 0:
            raise AnalysisError("resolved-color mixer does not construct sRGB")
        if import_targets != EXPECTED_IMPORT_TARGETS:
            raise AnalysisError("resolved-color mixer import targets differ")
        samples = capture_samples(
            executables["private"], executables["swift"], sample_set()
        )

    source_path = Path(__file__).resolve()
    return {
        "designLibraryResolvedColorMixerAnalysisSchemaVersion": RESULT_SCHEMA_VERSION,
        "classification": (
            "native static private-code and dynamic direct-ABI analysis joined "
            "bitwise to public SwiftUI Color.Resolved accessors and constructor; "
            "no GUI, render, image, crop, provider return, or Nix store path is used"
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
            "python": sys.version.split()[0],
            "source": SOURCE_RELATIVE_PATH,
            "sourceSHA256": sha256(source_path),
            "metadataAnalyzerSHA256": METADATA_ANALYZER_SHA256,
            "provenanceAnalyzerSHA256": PROVENANCE_ANALYZER_SHA256,
            "privateProbeSHA256": PRIVATE_PROBE_SHA256,
            "privateBridgeSHA256": PRIVATE_BRIDGE_SHA256,
            "importProbeSHA256": IMPORT_PROBE_SHA256,
            "swiftProbeSHA256": SWIFT_PROBE_SHA256,
            "compileCommands": executables["commands"],
        },
        "codeRegion": code,
        "rgbColorSpace": {"case": "sRGB", "runtimeEnumTag": rgb_tag},
        "resolvedImportTargets": {
            "0x{:x}".format(stub): {
                "staticTarget": "0x{:x}".format(target[0]),
                "image": target[1],
                "symbol": target[2],
            }
            for stub, target in import_targets.items()
        },
        "exactLaw": {
            "rgbEndpointRead": "public Color.Resolved red/green/blue getters",
            "fromWeight": "Float(1.0 - t), after one binary64 subtraction",
            "toWeight": "Float(t)",
            "componentArithmetic": (
                "two separately rounded binary32 multiplies followed by one "
                "binary32 add; no fused multiply-add"
            ),
            "alphaEndpointRead": "stored linear opacity fields directly",
            "outputConstruction": (
                "public Color.Resolved.init(colorSpace: .sRGB, red:green:blue:opacity:)"
            ),
            "storageEffect": (
                "RGB is sRGB transfer decode of the interpolated public sRGB "
                "components; output storage remains linear RGB"
            ),
        },
        "bitwiseValidation": samples,
        "claims": {
            "completePrivateResolvedColorMixerCodeEstablished": True,
            "privateABIEstablished": True,
            "allPrivateImportTargetsResolved": True,
            "sRGBColorSpaceSelectionEstablished": True,
            "publicComponentGetterAndConstructorJoinEstablished": True,
            "binary32OperationOrderEstablished": True,
            "directPrivateAndPublicCompositionSamplesBitwiseEqual": True,
            "resolvedColorExactTransferLawEstablished": True,
            "allParametersFieldBlendSemanticsEstablished": True,
            "transitionProgressToPublicConfigurationMixByLawEstablished": False,
            "publicControlsToResolvedConfigurationSelectionLawEstablished": False,
            "environmentToResolvedConfigurationSelectionLawEstablished": False,
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
