#!/usr/bin/env python3
"""Measure the native Parameters mixer with valid Apple-initialized values."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


RESULT_SCHEMA_VERSION = 1
SOURCE_RELATIVE_PATH = (
    "Analysis/capture_designlibrary_parameters_mixer_basis_local_macos_26_6_1.py"
)
EXPECTED_MACOS_PRODUCT_VERSION = "26.6.1"
EXPECTED_MACOS_BUILD_VERSION = "25G76"
EXPECTED_HARDWARE_MODEL = "MacBookPro18,2"
PARAMETERS_BYTE_COUNT = 0x401
PARAMETERS_STRIDE = 0x408
NORMALIZED_DEFAULT_PARAMETERS_SHA256 = (
    "9de341bfd47d97aa6f14b3228c8654e3eace7066cf4294879e130b1dd73607d3"
)
C_SOURCE_NAME = "probe_designlibrary_parameters_mixer_local_macos_26_6_1.c"
ASSEMBLY_SOURCE_NAME = "invoke_designlibrary_parameters_mixer_arm64.S"
C_SOURCE_SHA256 = (
    "d2241e57c6667b3c259ef5b9dbb6963323535b968b7a8f722cebc6ceedeabc6f"
)
ASSEMBLY_SOURCE_SHA256 = (
    "3c2587d7bc178abe7ff2b1c2ba7f583a7b7b7e615f1a9d3aca90428e4713103d"
)

SAMPLE_FRACTIONS = ("0", "0.25", "0.5", "0.75", "1")
THRESHOLD_FRACTIONS = ("-0.5", "0", "0.25", "0.5", "0.75", "1", "1.5")


@dataclass(frozen=True)
class ScalarField:
    name: str
    container: Optional[str]
    offset: int
    format: str
    policy: str = "linear"


@dataclass(frozen=True)
class ColorField:
    name: str
    container: str
    offset: int


CONTAINER_RANGES = {
    "shadow": (24, 176),
    "blur": (176, 256),
    "refraction": (256, 312),
    "faceEffects": (312, 392),
    "edgeBleed": (392, 500),
    "tinting": (500, 520),
    "highlights": (520, 784),
    "sdrAdjustment": (784, 824),
    "lensing": (824, 880),
    "controlContentLensing": (880, 912),
    "controlDisplacement": (912, 944),
    "contrastEdge": (944, 968),
    "innerGlow": (968, 992),
    "radiosity": (992, 1025),
}

CONTAINER_PRESENCE = {
    "shadow": (168, 0, 1),
    "blur": (248, 0, 1),
    "refraction": (308, 0, 1),
    "faceEffects": (385, 0, 1),
    "edgeBleed": (497, 0, 2),
    "tinting": (516, 0, 1),
    "highlights": (776, 0, 1),
    "sdrAdjustment": (816, 0, 1),
    "lensing": (872, 0, 1),
    "controlContentLensing": (904, 0, 1),
    "controlDisplacement": (936, 0, 1),
    "contrastEdge": (960, 0, 1),
    "innerGlow": (984, 0, 1),
    "radiosity": (1024, 0, 1),
}

CONTAINER_ACTIVATORS = {
    "shadow": (40, "d"),
    "blur": (176, "d"),
    "refraction": (256, "d"),
    "faceEffects": (312, "f"),
    "edgeBleed": (392, "d"),
    "tinting": (504, "f"),
    "highlights": (520, "f"),
    "sdrAdjustment": (784, "f"),
    "lensing": (824, "f"),
    "controlContentLensing": (880, "d"),
    "controlDisplacement": (912, "d"),
    "contrastEdge": (944, "f"),
    "innerGlow": (968, "f"),
    "radiosity": (992, "d"),
}

SCALAR_FIELDS = (
    ScalarField("backdropScale", None, 0, "f", "interior-ordered-maximum"),
    ScalarField("updateRate", None, 8, "d", "preserve-from"),
    ScalarField("contentOpacity", None, 16, "f", "preserve-from"),
    ScalarField("shadow.offset.width", "shadow", 24, "d"),
    ScalarField("shadow.offset.height", "shadow", 32, "d"),
    ScalarField("shadow.amount", "shadow", 40, "d"),
    ScalarField("shadow.height", "shadow", 48, "d"),
    ScalarField("shadow.inset", "shadow", 56, "d"),
    ScalarField("shadow.blurRadius", "shadow", 64, "d"),
    ScalarField("shadow.shadowRadius", "shadow", 72, "d"),
    ScalarField("shadow.ycc.black", "shadow", 80, "f"),
    ScalarField("shadow.ycc.white", "shadow", 84, "f"),
    ScalarField("shadow.ycc.saturation", "shadow", 88, "f"),
    ScalarField("shadow.opacity", "shadow", 152, "f"),
    ScalarField("shadow.vibrancyContribution", "shadow", 160, "d"),
    ScalarField("blur.radius", "blur", 176, "d"),
    ScalarField("blur.distances.0", "blur", 184, "d"),
    ScalarField("blur.distances.1", "blur", 192, "d"),
    ScalarField("blur.distances.2", "blur", 200, "d"),
    ScalarField("blur.distances.3", "blur", 208, "d"),
    ScalarField("blur.opacities.0", "blur", 224, "f"),
    ScalarField("blur.opacities.1", "blur", 228, "f"),
    ScalarField("blur.opacities.2", "blur", 232, "f"),
    ScalarField("blur.opacities.3", "blur", 236, "f"),
    ScalarField("blur.opacities.4", "blur", 240, "f"),
    ScalarField("blur.opacity", "blur", 244, "f"),
    ScalarField("refraction.innerHeight", "refraction", 256, "d"),
    ScalarField("refraction.innerAmount", "refraction", 264, "d"),
    ScalarField("refraction.outerHeight", "refraction", 272, "d"),
    ScalarField("refraction.outerAmount", "refraction", 280, "d"),
    ScalarField("refraction.outerDistances.0", "refraction", 288, "d"),
    ScalarField("refraction.outerDistances.1", "refraction", 296, "d"),
    ScalarField("refraction.outerOpacity", "refraction", 304, "f"),
    ScalarField("faceEffects.opacity", "faceEffects", 312, "f"),
    ScalarField("faceEffects.ycc.black", "faceEffects", 316, "f"),
    ScalarField("faceEffects.ycc.white", "faceEffects", 320, "f"),
    ScalarField("faceEffects.ycc.saturation", "faceEffects", 324, "f"),
    ScalarField("edgeBleed.amount", "edgeBleed", 392, "d"),
    ScalarField("edgeBleed.height", "edgeBleed", 400, "d"),
    ScalarField("edgeBleed.blurRadius", "edgeBleed", 408, "d"),
    ScalarField("edgeBleed.opacity", "edgeBleed", 416, "f"),
    ScalarField("edgeBleed.distances.0", "edgeBleed", 420, "f"),
    ScalarField("edgeBleed.distances.1", "edgeBleed", 424, "f"),
    ScalarField("edgeBleed.ycc.black", "edgeBleed", 428, "f"),
    ScalarField("edgeBleed.ycc.white", "edgeBleed", 432, "f"),
    ScalarField("edgeBleed.ycc.saturation", "edgeBleed", 436, "f"),
    ScalarField("tinting.opacity", "tinting", 500, "f"),
    ScalarField("tinting.distances.0", "tinting", 504, "f"),
    ScalarField("tinting.distances.1", "tinting", 508, "f"),
    ScalarField("tinting.distances.2", "tinting", 512, "f"),
    ScalarField("highlights.hdr", "highlights", 520, "f"),
    ScalarField("highlights.inset", "highlights", 528, "d"),
    ScalarField("highlights.key.height", "highlights", 536, "d"),
    ScalarField("highlights.key.opacity", "highlights", 544, "f"),
    ScalarField("highlights.key.spread", "highlights", 552, "d"),
    ScalarField("highlights.key.curvature", "highlights", 560, "d"),
    ScalarField("highlights.key.amount", "highlights", 568, "d"),
    ScalarField("highlights.key.ycc.black", "highlights", 576, "f"),
    ScalarField("highlights.key.ycc.white", "highlights", 580, "f"),
    ScalarField("highlights.key.ycc.saturation", "highlights", 584, "f"),
    ScalarField("highlights.key.offset", "highlights", 648, "d"),
    ScalarField("highlights.fill.height", "highlights", 656, "d"),
    ScalarField("highlights.fill.opacity", "highlights", 664, "f"),
    ScalarField("highlights.fill.spread", "highlights", 672, "d"),
    ScalarField("highlights.fill.curvature", "highlights", 680, "d"),
    ScalarField("highlights.fill.amount", "highlights", 688, "d"),
    ScalarField("highlights.fill.ycc.black", "highlights", 696, "f"),
    ScalarField("highlights.fill.ycc.white", "highlights", 700, "f"),
    ScalarField("highlights.fill.ycc.saturation", "highlights", 704, "f"),
    ScalarField("highlights.fill.offset", "highlights", 768, "d"),
    ScalarField("sdrAdjustment.headroomTransitionPoint", "sdrAdjustment", 784, "f"),
    ScalarField("sdrAdjustment.shadowOpacityShift", "sdrAdjustment", 788, "f"),
    ScalarField("sdrAdjustment.faceDimming.whitePointShift", "sdrAdjustment", 792, "f"),
    ScalarField("sdrAdjustment.faceDimming.distances.0", "sdrAdjustment", 800, "d"),
    ScalarField("sdrAdjustment.faceDimming.distances.1", "sdrAdjustment", 808, "d"),
    ScalarField("lensing.refractionHeight", "lensing", 824, "f"),
    ScalarField("lensing.refractionAmount", "lensing", 828, "f"),
    ScalarField("lensing.refractionInset", "lensing", 832, "f"),
    ScalarField("lensing.aberrationHeight", "lensing", 836, "f"),
    ScalarField("lensing.aberrationAmount", "lensing", 840, "f"),
    ScalarField("lensing.aberrationInset", "lensing", 844, "f"),
    ScalarField("lensing.aberrationAngle", "lensing", 848, "d"),
    ScalarField("lensing.edgeDistances.0", "lensing", 856, "f"),
    ScalarField("lensing.edgeDistances.1", "lensing", 860, "f"),
    ScalarField("lensing.edgeOpacities.0", "lensing", 864, "f"),
    ScalarField("lensing.edgeOpacities.1", "lensing", 868, "f"),
    ScalarField("controlContentLensing.height", "controlContentLensing", 880, "d"),
    ScalarField("controlContentLensing.amount", "controlContentLensing", 888, "d"),
    ScalarField("controlContentLensing.inset", "controlContentLensing", 896, "d"),
    ScalarField("controlDisplacement.height", "controlDisplacement", 912, "d"),
    ScalarField("controlDisplacement.amount", "controlDisplacement", 920, "d"),
    ScalarField("controlDisplacement.inset", "controlDisplacement", 928, "d"),
    ScalarField("contrastEdge.hdr", "contrastEdge", 944, "f"),
    ScalarField("contrastEdge.opacity", "contrastEdge", 948, "f"),
    ScalarField("contrastEdge.width", "contrastEdge", 952, "d"),
    ScalarField("innerGlow.hdr", "innerGlow", 968, "f"),
    ScalarField("innerGlow.opacity", "innerGlow", 972, "f"),
    ScalarField("innerGlow.radius", "innerGlow", 976, "d"),
    ScalarField("radiosity.height", "radiosity", 992, "d"),
    ScalarField("radiosity.amount", "radiosity", 1000, "d"),
    ScalarField("radiosity.saturation", "radiosity", 1008, "d"),
    ScalarField("radiosity.radius", "radiosity", 1016, "d"),
)

COLOR_FIELDS = (
    ColorField("shadow.ycc.normalFill", "shadow", 92),
    ColorField("shadow.ycc.dodgeFill", "shadow", 112),
    ColorField("shadow.ycc.burnFill", "shadow", 132),
    ColorField("faceEffects.ycc.normalFill", "faceEffects", 328),
    ColorField("faceEffects.ycc.dodgeFill", "faceEffects", 348),
    ColorField("faceEffects.ycc.burnFill", "faceEffects", 368),
    ColorField("edgeBleed.ycc.normalFill", "edgeBleed", 440),
    ColorField("edgeBleed.ycc.dodgeFill", "edgeBleed", 460),
    ColorField("edgeBleed.ycc.burnFill", "edgeBleed", 480),
    ColorField("highlights.key.ycc.normalFill", "highlights", 588),
    ColorField("highlights.key.ycc.dodgeFill", "highlights", 608),
    ColorField("highlights.key.ycc.burnFill", "highlights", 628),
    ColorField("highlights.fill.ycc.normalFill", "highlights", 708),
    ColorField("highlights.fill.ycc.dodgeFill", "highlights", 728),
    ColorField("highlights.fill.ycc.burnFill", "highlights", 748),
)


def semantic_byte_offsets() -> frozenset[int]:
    offsets: set[int] = set()
    for field in SCALAR_FIELDS:
        byte_count = struct.calcsize("<" + field.format)
        offsets.update(range(field.offset, field.offset + byte_count))
    for field in COLOR_FIELDS:
        offsets.update(range(field.offset, field.offset + 17))
    for presence_offset, _, _ in CONTAINER_PRESENCE.values():
        offsets.add(presence_offset)
    return frozenset(offsets)


SEMANTIC_BYTE_OFFSETS = semantic_byte_offsets()


def padding_ranges() -> tuple[tuple[int, int], ...]:
    ranges = []
    start: Optional[int] = None
    for offset in range(PARAMETERS_BYTE_COUNT + 1):
        is_padding = (
            offset < PARAMETERS_BYTE_COUNT and offset not in SEMANTIC_BYTE_OFFSETS
        )
        if is_padding and start is None:
            start = offset
        elif not is_padding and start is not None:
            ranges.append((start, offset))
            start = None
    return tuple(ranges)


SEMANTIC_PADDING_RANGES = padding_ranges()


class CaptureError(RuntimeError):
    """Raised when the native basis capture violates its frozen contract."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def digest_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def normalize_parameters(payload: bytes) -> bytes:
    if len(payload) not in (PARAMETERS_BYTE_COUNT, PARAMETERS_STRIDE):
        raise CaptureError("cannot normalize a non-Parameters payload")
    normalized = bytearray(payload)
    for offset in range(PARAMETERS_BYTE_COUNT):
        if offset not in SEMANTIC_BYTE_OFFSETS:
            normalized[offset] = 0
    if len(normalized) == PARAMETERS_STRIDE:
        normalized[PARAMETERS_BYTE_COUNT:] = bytes(
            PARAMETERS_STRIDE - PARAMETERS_BYTE_COUNT
        )
    return bytes(normalized)


def command_output(arguments: tuple[str, ...]) -> str:
    completed = subprocess.run(
        arguments,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise CaptureError("command failed: " + " ".join(arguments))
    return completed.stdout.strip()


def run_checked(arguments: tuple[str, ...], payload: Optional[bytes] = None) -> bytes:
    completed = subprocess.run(
        arguments,
        check=False,
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise CaptureError(
            "command failed: "
            + " ".join(arguments)
            + ": "
            + completed.stderr.decode("utf-8", "replace")
        )
    return completed.stdout


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def scalar_bits(format_code: str, value: float) -> str:
    if format_code == "f":
        return "0x{:08x}".format(struct.unpack("<I", struct.pack("<f", value))[0])
    return "0x{:016x}".format(struct.unpack("<Q", struct.pack("<d", value))[0])


def unpack_scalar(format_code: str, payload: bytes, offset: int) -> float:
    return float(struct.unpack_from("<" + format_code, payload, offset)[0])


def expected_linear(format_code: str, fraction: float) -> float:
    from_value = 2.0
    to_value = 4.0
    one_minus_fraction = 1.0 - fraction
    if format_code == "f":
        from_product = f32(f32(from_value) * f32(one_minus_fraction))
        to_product = f32(f32(to_value) * f32(fraction))
        return f32(from_product + to_product)
    from_product = from_value * one_minus_fraction
    to_product = to_value * fraction
    return from_product + to_product


def initialize_ycc(payload: bytearray, offset: int) -> None:
    payload[offset : offset + 69] = bytes(69)
    payload[offset + 28] = 1
    payload[offset + 48] = 1
    payload[offset + 68] = 1


def make_present(default_parameters: bytes, container: str) -> bytearray:
    payload = bytearray(default_parameters)
    start, end = CONTAINER_RANGES[container]
    payload[start:end] = bytes(end - start)

    if container == "shadow":
        initialize_ycc(payload, 80)
    elif container == "faceEffects":
        initialize_ycc(payload, 316)
    elif container == "edgeBleed":
        initialize_ycc(payload, 428)
    elif container == "highlights":
        initialize_ycc(payload, 576)
        initialize_ycc(payload, 696)

    presence_offset, present_value, _ = CONTAINER_PRESENCE[container]
    payload[presence_offset] = present_value
    activator_offset, activator_format = CONTAINER_ACTIVATORS[container]
    struct.pack_into("<" + activator_format, payload, activator_offset, 1.0)
    return payload


def compile_probe(analysis_directory: Path, output: Path) -> tuple[str, ...]:
    c_source = analysis_directory / C_SOURCE_NAME
    assembly_source = analysis_directory / ASSEMBLY_SOURCE_NAME
    if sha256(c_source) != C_SOURCE_SHA256:
        raise CaptureError("C probe source differs")
    if sha256(assembly_source) != ASSEMBLY_SOURCE_SHA256:
        raise CaptureError("arm64 bridge source differs")
    arguments = (
        "/usr/bin/xcrun",
        "clang",
        "-std=c23",
        "-arch",
        "arm64",
        "-O2",
        "-Wall",
        "-Wextra",
        "-Wpedantic",
        "-Werror",
        str(c_source),
        str(assembly_source),
        "-o",
        str(output),
    )
    run_checked(arguments)
    return arguments


def invoke_probe(
    executable: Path,
    from_parameters: bytes,
    to_parameters: bytes,
    fraction: str,
) -> bytes:
    if len(from_parameters) != PARAMETERS_STRIDE or len(to_parameters) != PARAMETERS_STRIDE:
        raise CaptureError("Parameters input stride differs")
    arguments = (str(executable), fraction)
    raw_output = run_checked(arguments, from_parameters + to_parameters)
    if len(raw_output) != PARAMETERS_BYTE_COUNT:
        raise CaptureError("Parameters mixer output size differs")
    raw_repeated = run_checked(arguments, from_parameters + to_parameters)
    output = normalize_parameters(raw_output)
    repeated = normalize_parameters(raw_repeated)
    if output != repeated:
        differing = [
            index
            for index, (first, second) in enumerate(zip(output, repeated))
            if first != second
        ]
        raise CaptureError(
            "Parameters mixer output is not repeatable at offsets "
            + repr(differing)
            + " for fraction "
            + fraction
        )
    return output


def capture_scalar_fields(
    executable: Path, default_parameters: bytes
) -> dict[str, object]:
    records: dict[str, object] = {}
    for field in SCALAR_FIELDS:
        if field.container is None:
            from_parameters = bytearray(default_parameters)
            to_parameters = bytearray(default_parameters)
        else:
            from_parameters = make_present(default_parameters, field.container)
            to_parameters = make_present(default_parameters, field.container)
        struct.pack_into("<" + field.format, from_parameters, field.offset, 2.0)
        struct.pack_into("<" + field.format, to_parameters, field.offset, 4.0)

        samples = []
        for fraction_text in SAMPLE_FRACTIONS:
            fraction = float(fraction_text)
            output = invoke_probe(
                executable, bytes(from_parameters), bytes(to_parameters), fraction_text
            )
            observed = unpack_scalar(field.format, output, field.offset)
            if field.policy == "preserve-from":
                expected = 2.0
            elif field.policy == "interior-ordered-maximum":
                expected = 2.0 if fraction <= 0.0 else 4.0
            else:
                expected = expected_linear(field.format, fraction)
            if scalar_bits(field.format, observed) != scalar_bits(field.format, expected):
                raise CaptureError(field.name + " scalar policy differs")
            sample: dict[str, object] = {
                "fraction": fraction_text,
                "fractionBits": scalar_bits("d", fraction),
                "value": observed,
                "valueBits": scalar_bits(field.format, observed),
                "outputSHA256": digest_bytes(output),
            }
            if field.container is not None:
                presence_offset, present_value, _ = CONTAINER_PRESENCE[field.container]
                if output[presence_offset] != present_value:
                    raise CaptureError(field.name + " unexpectedly became nil")
                sample["presenceByte"] = output[presence_offset]
            samples.append(sample)
        records[field.name] = {
            "container": field.container,
            "offset": field.offset,
            "type": "Float" if field.format == "f" else "Double",
            "policy": field.policy,
            "fromValue": 2.0,
            "toValue": 4.0,
            "samples": samples,
        }
    return records


def capture_backdrop_reverse_direction(
    executable: Path, default_parameters: bytes
) -> list[dict[str, object]]:
    from_parameters = bytearray(default_parameters)
    to_parameters = bytearray(default_parameters)
    struct.pack_into("<f", from_parameters, 0, 4.0)
    struct.pack_into("<f", to_parameters, 0, 2.0)
    records = []
    for fraction_text in SAMPLE_FRACTIONS:
        output = invoke_probe(
            executable, bytes(from_parameters), bytes(to_parameters), fraction_text
        )
        observed = unpack_scalar("f", output, 0)
        expected = 4.0 if float(fraction_text) < 1.0 else 2.0
        if scalar_bits("f", observed) != scalar_bits("f", expected):
            raise CaptureError("reverse backdropScale policy differs")
        records.append(
            {
                "fraction": fraction_text,
                "value": observed,
                "valueBits": scalar_bits("f", observed),
                "outputSHA256": digest_bytes(output),
            }
        )
    return records


def capture_optional_presence(
    executable: Path, default_parameters: bytes
) -> dict[str, object]:
    records: dict[str, object] = {}
    for container in CONTAINER_RANGES:
        present = make_present(default_parameters, container)
        absent = bytes(default_parameters)
        activator_offset, activator_format = CONTAINER_ACTIVATORS[container]
        presence_offset, present_value, absent_value = CONTAINER_PRESENCE[container]
        directions: dict[str, object] = {}
        for direction, from_parameters, to_parameters in (
            ("someToNil", bytes(present), absent),
            ("nilToSome", absent, bytes(present)),
        ):
            samples = []
            for fraction_text in SAMPLE_FRACTIONS:
                fraction = float(fraction_text)
                output = invoke_probe(
                    executable, from_parameters, to_parameters, fraction_text
                )
                observed = unpack_scalar(activator_format, output, activator_offset)
                expected = 1.0 - fraction if direction == "someToNil" else fraction
                expected_presence = (
                    absent_value if expected == 0.0 else present_value
                )
                if output[presence_offset] != expected_presence:
                    raise CaptureError(container + " optional presence differs")
                if expected_presence == present_value and scalar_bits(
                    activator_format, observed
                ) != scalar_bits(
                    activator_format,
                    f32(expected) if activator_format == "f" else expected,
                ):
                    raise CaptureError(container + " optional zero-extension differs")
                samples.append(
                    {
                        "fraction": fraction_text,
                        "activatorValue": observed,
                        "activatorBits": scalar_bits(activator_format, observed),
                        "presenceByte": output[presence_offset],
                        "outputSHA256": digest_bytes(output),
                    }
                )
            directions[direction] = samples
        records[container] = {
            "storageRange": list(CONTAINER_RANGES[container]),
            "presenceOffset": presence_offset,
            "presentValue": present_value,
            "nilValue": absent_value,
            "activatorOffset": activator_offset,
            "activatorType": "Float" if activator_format == "f" else "Double",
            "directions": directions,
        }
    return records


def capture_edge_boolean(
    executable: Path, default_parameters: bytes
) -> dict[str, object]:
    records: dict[str, object] = {}
    for direction, from_value, to_value in (("falseToTrue", 0, 1), ("trueToFalse", 1, 0)):
        from_parameters = make_present(default_parameters, "edgeBleed")
        to_parameters = make_present(default_parameters, "edgeBleed")
        from_parameters[497] = from_value
        to_parameters[497] = to_value
        samples = []
        for fraction_text in THRESHOLD_FRACTIONS:
            fraction = float(fraction_text)
            output = invoke_probe(
                executable, bytes(from_parameters), bytes(to_parameters), fraction_text
            )
            expected = from_value if fraction < 0.5 else to_value
            if output[497] != expected:
                raise CaptureError("edgeBleed boolean threshold differs")
            samples.append(
                {
                    "fraction": fraction_text,
                    "value": output[497],
                    "outputSHA256": digest_bytes(output),
                }
            )
        records[direction] = samples
    return records


def capture_colors(
    executable: Path, default_parameters: bytes
) -> dict[str, object]:
    from_components = (0.2, 0.3, 0.4, 0.5)
    to_components = (0.8, 0.7, 0.6, 0.9)
    records: dict[str, object] = {}
    reference_by_fraction: dict[str, bytes] = {}
    raw_linear_difference_observed = False
    for field in COLOR_FIELDS:
        from_parameters = make_present(default_parameters, field.container)
        to_parameters = make_present(default_parameters, field.container)
        struct.pack_into("<ffffB", from_parameters, field.offset, *from_components, 0)
        struct.pack_into("<ffffB", to_parameters, field.offset, *to_components, 0)
        samples = []
        for fraction_text in SAMPLE_FRACTIONS:
            fraction = float(fraction_text)
            output = invoke_probe(
                executable, bytes(from_parameters), bytes(to_parameters), fraction_text
            )
            color_bytes = output[field.offset : field.offset + 17]
            components = struct.unpack_from("<ffff", output, field.offset)
            if output[field.offset + 16] != 0:
                raise CaptureError(field.name + " color unexpectedly became nil")
            if fraction == 0.0:
                expected_endpoint = struct.pack("<ffffB", *from_components, 0)
                if color_bytes != expected_endpoint:
                    raise CaptureError(field.name + " from color endpoint differs")
            elif fraction == 1.0:
                expected_endpoint = struct.pack("<ffffB", *to_components, 0)
                if color_bytes != expected_endpoint:
                    raise CaptureError(field.name + " to color endpoint differs")
            else:
                raw_linear = tuple(
                    f32(
                        f32(f32(start) * f32(1.0 - fraction))
                        + f32(f32(end) * f32(fraction))
                    )
                    for start, end in zip(from_components, to_components)
                )
                if tuple(components[:3]) != raw_linear[:3]:
                    raw_linear_difference_observed = True
                if scalar_bits("f", components[3]) != scalar_bits(
                    "f", raw_linear[3]
                ):
                    raise CaptureError(field.name + " alpha interpolation differs")
            previous = reference_by_fraction.setdefault(fraction_text, color_bytes)
            if color_bytes != previous:
                raise CaptureError("resolved color policy differs by YCC location")
            samples.append(
                {
                    "fraction": fraction_text,
                    "components": list(components),
                    "componentBits": [scalar_bits("f", value) for value in components],
                    "optionalTag": output[field.offset + 16],
                    "colorBytes": color_bytes.hex(),
                    "outputSHA256": digest_bytes(output),
                }
            )
        records[field.name] = {
            "container": field.container,
            "offset": field.offset,
            "samples": samples,
        }
    if not raw_linear_difference_observed:
        raise CaptureError("resolved color RGB unexpectedly uses raw component mixing")
    return {
        "fromComponents": list(from_components),
        "toComponents": list(to_components),
        "locationCount": len(COLOR_FIELDS),
        "locations": records,
        "allLocationsBitwiseIdenticalByFraction": True,
        "alphaUsesBinary32LinearInterpolation": True,
        "interiorRGBDiffersFromRawBinary32ComponentInterpolation": True,
    }


def capture() -> dict[str, object]:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise CaptureError("capture requires native arm64 macOS")
    product_version = command_output(("/usr/bin/sw_vers", "-productVersion"))
    build_version = command_output(("/usr/bin/sw_vers", "-buildVersion"))
    hardware_model = command_output(("/usr/sbin/sysctl", "-n", "hw.model"))
    if (
        product_version != EXPECTED_MACOS_PRODUCT_VERSION
        or build_version != EXPECTED_MACOS_BUILD_VERSION
        or hardware_model != EXPECTED_HARDWARE_MODEL
    ):
        raise CaptureError("host differs from the frozen target")

    source_path = Path(__file__).resolve()
    analysis_directory = source_path.parent
    with tempfile.TemporaryDirectory(prefix="lg-parameters-mixer-") as temporary:
        executable = Path(temporary) / "parameters-mixer-probe"
        compile_arguments = compile_probe(analysis_directory, executable)
        defaults = [run_checked((str(executable), "--default")) for _ in range(3)]
        if any(len(payload) != PARAMETERS_STRIDE for payload in defaults):
            raise CaptureError("default Parameters stride differs")
        if defaults[1:] != defaults[:-1]:
            raise CaptureError("default Parameters bytes are not repeatable")
        raw_default_parameters = defaults[0]
        default_parameters = normalize_parameters(raw_default_parameters)
        if (
            digest_bytes(default_parameters)
            != NORMALIZED_DEFAULT_PARAMETERS_SHA256
        ):
            raise CaptureError(
                "normalized default Parameters bytes differ: "
                + digest_bytes(default_parameters)
            )

        scalar_fields = capture_scalar_fields(executable, default_parameters)
        reverse_backdrop = capture_backdrop_reverse_direction(
            executable, default_parameters
        )
        optional_presence = capture_optional_presence(executable, default_parameters)
        edge_boolean = capture_edge_boolean(executable, default_parameters)
        colors = capture_colors(executable, default_parameters)

    return {
        "designLibraryParametersMixerBasisCaptureSchemaVersion": RESULT_SCHEMA_VERSION,
        "classification": (
            "native direct invocation of the frozen private Parameters mixer with "
            "Apple-default-initialized valid values; no GUI, render, image, crop, "
            "provider return, Nix store path, or Retina presentation session is used"
        ),
        "host": {
            "system": platform.system(),
            "machine": platform.machine(),
            "macOSProductVersion": product_version,
            "macOSBuildVersion": build_version,
            "hardwareModel": hardware_model,
        },
        "tool": {
            "python": sys.version.split()[0],
            "source": SOURCE_RELATIVE_PATH,
            "sourceSHA256": sha256(source_path),
            "cSource": "Analysis/" + C_SOURCE_NAME,
            "cSourceSHA256": C_SOURCE_SHA256,
            "assemblySource": "Analysis/" + ASSEMBLY_SOURCE_NAME,
            "assemblySourceSHA256": ASSEMBLY_SOURCE_SHA256,
            "compileCommand": list(compile_arguments),
        },
        "nativeABI": {
            "staticTextAddress": "0x240861000",
            "staticDefaultInitializerAddress": "0x24093c0f8",
            "staticDefaultStorageAddress": "0x298f0e710",
            "staticMixerAddress": "0x2409406a8",
            "parametersByteCount": PARAMETERS_BYTE_COUNT,
            "parametersStride": PARAMETERS_STRIDE,
        },
        "defaultParameters": {
            "repeatCount": 3,
            "rawSHA256": digest_bytes(raw_default_parameters),
            "normalizedPaddingRanges": [
                list(bounds) for bounds in SEMANTIC_PADDING_RANGES
            ],
            "normalizedSHA256": digest_bytes(default_parameters),
            "normalizedBytes": default_parameters.hex(),
        },
        "scalarFieldCount": len(SCALAR_FIELDS),
        "scalarFields": scalar_fields,
        "reverseBackdropScale": reverse_backdrop,
        "optionalContainerCount": len(CONTAINER_RANGES),
        "optionalPresence": optional_presence,
        "edgeBleedUseDarkenBlending": {
            "offset": 497,
            "selectionThreshold": "to at t >= 0.5; from at t < 0.5",
            "directions": edge_boolean,
        },
        "resolvedColors": colors,
        "claims": {
            "appleDefaultParametersBytesEstablished": True,
            "allEnumeratedNumericScalarPoliciesMeasuredBitwise": True,
            "allNonColorNumericScalarsUseDeclaredPolicies": True,
            "updateRatePreservedFromFirstEndpoint": True,
            "contentOpacityPreservedFromFirstEndpoint": True,
            "backdropScaleInteriorOrderedMaximumEstablished": True,
            "allFourteenOptionalContainerZeroExtensionPoliciesEstablished": True,
            "edgeBleedBooleanHalfThresholdEstablished": True,
            "allFifteenResolvedColorLocationsShareOneBitwisePolicy": True,
            "resolvedColorAlphaLinearPolicyEstablished": True,
            "resolvedColorInteriorRGBIsNotRawComponentLinear": True,
            "resolvedColorExactTransferLawEstablished": False,
            "allParametersFieldBlendSemanticsEstablished": False,
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
        result = capture()
    except (CaptureError, OSError, struct.error) as error:
        print("capture failed: " + str(error), file=sys.stderr)
        return 1
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(payload, end="")
    else:
        arguments.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
