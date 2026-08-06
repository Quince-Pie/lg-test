#!/usr/bin/env python3
"""Decode exact Gaussian constants and delegated backdrop-bounds arithmetic."""

from __future__ import annotations

import argparse
import copy
import ctypes
import hashlib
import json
import math
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_prepare_layer_small_geometry_helper_semantics as validator


ANALYSIS_SCHEMA_VERSION = 1
RUN_ID = 31088316959
HEAD_SHA = "a16e7545a83ee2a2f0cc160694b3bbe7f68c9b10"
ARTIFACT_ID = 8962518110
ARTIFACT_DIGEST = (
    "sha256:1911d52945e3e3a223dd640ca7b31bb6886fade3af215fcaa2e685703590f0c3"
)
TRACE_SHA256 = "eb0c54f6550f29c1b987806334f20dd20df5329e8e482928567a9986cb79de08"
TIMELINE_SHA256 = "a3983d0361c190cf98258bccbf9d86605e8dfec99fb5e7e19c24d9b80135810d"
VALIDATION_SHA256 = "0cdb6e48bcc60ecc72b9218c0f934790cd74723000a598a1e0b339e01b7fc9bd"
GAUSSIAN_FUNCTION = "CA::OGL::gaussian_expansion_factor(double)"
BACKDROP_WRAPPER_FUNCTION = (
    "CA::Render::BackdropLayer::get_bounds("
    "CA::Render::Layer const*, CA::Rect&, CA::Rect*) const"
)
GET_BACKDROP_BOUNDS_FUNCTION = (
    "CA::Render::BackdropLayer::get_backdrop_bounds("
    "CA::Render::Layer const*, CA::Rect&) const"
)
GET_BACKDROP_BOUNDS_CODE_SHA256 = (
    "3296daa4d858acc2a259be7771e48c312ff7010fa3d7cd590a9f28bd17a4ff17"
)
EXPECTED_CONSTANT_HEX = {
    "highThreshold": "295c8fc2f528e03f",
    "lowThreshold": "7b14ae47e17a743f",
    "activeShift": "7b14ae47e17a74bf",
    "logIntercept": "666666666666fa3f",
    "logSlope": "333333333333d33f",
    "highIntercept": "40bcac6e7695f93f",
    "highSlope": "326f6748ccdbb93f",
    "alternateModeReturn": "6666666666660640",
}
EXPECTED_GET_BACKDROP_INSTRUCTIONS = {
    0: "001cc03d",
    20: "ac000054",
    24: "28200191",
    32: "2080c53c",
    40: "08800191",
    48: "210140fd",
    56: "4204006d",
    64: "000d813c",
    80: "0902f092",
    92: "a5020054",
    108: "2d020054",
    112: "022440bd",
    116: "4240211e",
    120: "42c0221e",
    124: "4300c03d",
    132: "63d4644e",
    136: "4300803d",
    140: "4328621e",
    144: "0338631e",
    148: "0010701e",
    152: "4004401f",
    156: "4300016d",
    180: "1f7d00a9",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is unreadable: {error}") from error


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} is not an object")
    return value


def sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{label} is not an array")
    return value


def normalized_validation(value: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(value))
    inputs = dict(mapping(result.get("inputs"), "validation inputs"))
    inputs.pop("trace", None)
    inputs.pop("timeline", None)
    result["inputs"] = inputs
    return result


def binary64_fma(left: float, right: float, addend: float) -> float:
    if hasattr(math, "fma"):
        return math.fma(left, right, addend)
    function = ctypes.CDLL(None).fma
    function.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double]
    function.restype = ctypes.c_double
    return float(function(left, right, addend))


def binary32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def f64_hex(value: float) -> str:
    return struct.pack("<d", value).hex()


def register_v0(registers: Any, label: str) -> float:
    register_set = mapping(registers, label)
    matches = [
        mapping(raw, f"{label} SIMD register")
        for raw in sequence(register_set.get("simd"), f"{label} SIMD registers")
        if mapping(raw, f"{label} SIMD register").get("name") == "v0"
    ]
    if len(matches) != 1:
        raise ValueError(f"{label} v0 is not unique")
    raw = bytes.fromhex(str(matches[0].get("hex")))
    if len(raw) != 16:
        raise ValueError(f"{label} v0 byte count differs")
    return struct.unpack_from("<d", raw)[0]


def general_register(registers: Any, name: str, label: str) -> int:
    register_set = mapping(registers, label)
    matches = [
        mapping(raw, f"{label} general register")
        for raw in sequence(register_set.get("general"), f"{label} registers")
        if mapping(raw, f"{label} general register").get("name") == name
    ]
    if len(matches) != 1:
        raise ValueError(f"{label} {name} is not unique")
    value = matches[0].get("unsignedValue")
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} {name} is not an integer")
    return value


def snapshot_bytes(value: Any, label: str) -> tuple[int, bytes]:
    snapshot = mapping(value, label)
    address = snapshot.get("address")
    if not isinstance(address, int) or isinstance(address, bool):
        raise ValueError(f"{label} address is not an integer")
    try:
        raw = bytes.fromhex(str(snapshot.get("hex")))
    except ValueError as error:
        raise ValueError(f"{label} is not hexadecimal") from error
    if snapshot.get("byteCount") != len(raw):
        raise ValueError(f"{label} byte count differs")
    return address, raw


def boundary_by_function(boundaries: Any, function: str) -> Mapping[str, Any]:
    matches = [
        mapping(raw, "opaque boundary")
        for raw in sequence(boundaries, "opaque boundaries")
        if mapping(
            mapping(raw, "opaque boundary").get("entryFrame"), "entry frame"
        ).get("function")
        == function
    ]
    if len(matches) != 1:
        raise ValueError(f"{function} boundary is not unique")
    return matches[0]


def backdrop_boundary_rectangles(
    boundary: Mapping[str, Any],
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    destination = general_register(
        boundary.get("registersAtEntry"), "x2", "backdrop entry"
    )
    entry_address, entry = snapshot_bytes(
        boundary.get("stackAtEntry"), "backdrop entry stack"
    )
    return_address, returned = snapshot_bytes(
        boundary.get("stackAtReturn"), "backdrop return stack"
    )
    if entry_address != return_address:
        raise ValueError("backdrop stack address differs")
    offset = destination - entry_address
    if offset < 0 or offset + 32 > len(entry):
        raise ValueError("backdrop rectangle is outside retained stack")
    return (
        struct.unpack_from("<4d", entry, offset),
        struct.unpack_from("<4d", returned, offset),
    )


def replay_gaussian(x: float, constants: Mapping[str, float], mode: int = 0) -> float:
    if mode & 1:
        return constants["alternateModeReturn"]
    if x >= constants["highThreshold"]:
        return binary64_fma(x, constants["highSlope"], constants["highIntercept"])
    if x <= constants["lowThreshold"]:
        return 0.0
    shifted = x + constants["activeShift"]
    clamped = 0.0 if shifted < 0.0 else shifted
    logarithm = math.log(clamped + clamped)
    candidate = binary64_fma(
        logarithm, constants["logSlope"], constants["logIntercept"]
    )
    candidate = 0.0 if candidate < 0.0 else candidate
    return candidate if abs(logarithm) < math.inf else 0.0


def replay_get_backdrop_bounds(
    base: tuple[float, float, float, float], margin_f32: float
) -> tuple[float, float, float, float]:
    margin = float(binary32(margin_f32))
    negative_margin = -margin
    origin_x = base[0] + negative_margin
    origin_y = base[1] + negative_margin
    doubled_negative = negative_margin + negative_margin
    width = base[2] - doubled_negative
    height = binary64_fma(negative_margin, -2.0, base[3])
    if width <= 0.0 or height <= 0.0:
        width = 0.0
        height = 0.0
    return origin_x, origin_y, width, height


def analyze(
    trace_path: Path,
    timeline_path: Path,
    inventory_path: Path,
    validation_path: Path,
) -> dict[str, Any]:
    for path, expected, label in (
        (trace_path, TRACE_SHA256, "trace"),
        (timeline_path, TIMELINE_SHA256, "timeline"),
        (validation_path, VALIDATION_SHA256, "CI validation"),
    ):
        if sha256(path) != expected:
            raise ValueError(f"{label} SHA-256 differs")
    trace = mapping(load_json(trace_path, "trace"), "trace")
    ci_validation = mapping(
        load_json(validation_path, "CI validation"), "CI validation"
    )
    independent = validator.validate(trace_path, timeline_path, inventory_path)
    if normalized_validation(ci_validation) != normalized_validation(independent):
        raise ValueError("independent validation differs from CI validation")

    extension = mapping(
        trace.get("prepareLayerSmallGeometryHelperSemanticsExtension"),
        "helper-semantics extension",
    )
    gaussian = mapping(extension.get("gaussian"), "Gaussian capture")
    constant_records = sequence(gaussian.get("constants"), "Gaussian constants")
    constants: dict[str, float] = {}
    exact_constants: list[dict[str, Any]] = []
    for raw in constant_records:
        item = mapping(raw, "Gaussian constant")
        name = str(item.get("name"))
        raw_hex = str(item.get("rawLittleEndianHex"))
        if EXPECTED_CONSTANT_HEX.get(name) != raw_hex:
            raise ValueError(f"{name} exact word differs")
        value = struct.unpack("<d", bytes.fromhex(raw_hex))[0]
        constants[name] = value
        exact_constants.append(
            {
                "name": name,
                "rawLittleEndianHex": raw_hex,
                "binary64Bits": int.from_bytes(bytes.fromhex(raw_hex), "little"),
                "binary64": value,
                "binary64Hex": value.hex(),
            }
        )
    if set(constants) != set(EXPECTED_CONSTANT_HEX):
        raise ValueError("Gaussian constant set differs")
    global_flag = mapping(gaussian.get("globalModeFlag"), "global mode flag")
    if global_flag.get("rawLittleEndianHex") != "00":
        raise ValueError("global mode flag differs")

    filter_extension = mapping(
        trace.get("prepareLayerFilterMapBoundsExtension"), "Filter extension"
    )
    boundaries = filter_extension.get("opaqueCalleeBoundaries")
    gaussian_boundary = boundary_by_function(boundaries, GAUSSIAN_FUNCTION)
    gaussian_input = register_v0(
        gaussian_boundary.get("registersAtEntry"), "Gaussian entry"
    )
    gaussian_return = register_v0(
        gaussian_boundary.get("registersAtReturn"), "Gaussian return"
    )
    gaussian_replay = replay_gaussian(gaussian_input, constants)
    if f64_hex(gaussian_replay) != f64_hex(gaussian_return):
        raise ValueError("Gaussian selected replay differs")
    high_join = replay_gaussian(constants["highThreshold"], constants)
    active_join = binary64_fma(
        math.log(
            2.0
            * max(
                0.0,
                constants["highThreshold"] + constants["activeShift"],
            )
        ),
        constants["logSlope"],
        constants["logIntercept"],
    )
    if f64_hex(high_join) != f64_hex(active_join):
        raise ValueError("Gaussian high-threshold join differs")

    callee = mapping(extension.get("getBackdropBounds"), "get_backdrop_bounds")
    if (
        callee.get("function") != GET_BACKDROP_BOUNDS_FUNCTION
        or callee.get("symbolByteCount") != 188
        or callee.get("instructionCount") != 47
        or callee.get("observedCodeSHA256") != GET_BACKDROP_BOUNDS_CODE_SHA256
    ):
        raise ValueError("get_backdrop_bounds code identity differs")
    instructions = {
        mapping(raw, "callee instruction").get("offset"): mapping(
            raw, "callee instruction"
        ).get("rawLittleEndianHex")
        for raw in sequence(callee.get("instructions"), "callee instructions")
    }
    for offset, raw_hex in EXPECTED_GET_BACKDROP_INSTRUCTIONS.items():
        if instructions.get(offset) != raw_hex:
            raise ValueError(f"get_backdrop_bounds+{offset:#x} differs")

    backdrop_boundary = boundary_by_function(boundaries, BACKDROP_WRAPPER_FUNCTION)
    backdrop_input, backdrop_return = backdrop_boundary_rectangles(backdrop_boundary)
    conditional_candidate = replay_get_backdrop_bounds((0.0, 0.0, 127.0, 127.0), 83.0)
    if tuple(backdrop_return) != conditional_candidate:
        raise ValueError("conditional nominal-base/83-margin replay differs")

    return {
        "prepareLayerSmallGeometryHelperSemanticsAnalysisSchemaVersion": (
            ANALYSIS_SCHEMA_VERSION
        ),
        "classification": (
            "retrospective exact decode of prospectively retained Gaussian data "
            "and complete delegated backdrop code; selected arithmetic is replayed "
            "bit for bit, while live object fields, their writer, unseen geometry "
            "transfer, and product parity remain closed"
        ),
        "run": {
            "id": RUN_ID,
            "headSHA": HEAD_SHA,
            "artifactID": ARTIFACT_ID,
            "artifactDigest": ARTIFACT_DIGEST,
            "traceSHA256": TRACE_SHA256,
            "timelineSHA256": TIMELINE_SHA256,
            "ciValidationSHA256": VALIDATION_SHA256,
            "independentValidationEqualExceptCallerPaths": True,
        },
        "gaussianExpansionFactor": {
            "function": GAUSSIAN_FUNCTION,
            "codeSHA256": validator.GAUSSIAN_CODE_SHA256,
            "globalModeFlagUnsignedValue": 0,
            "constants": exact_constants,
            "exactLaw": {
                "globalMode": "if mode & 1: return 2.8",
                "low": "if x <= 0.005: return 0",
                "active": (
                    "if 0.005 < x < 0.505: return finite_or_zero("
                    "max(0, fma(log(2*max(0,x-0.005)),0.3,1.65)))"
                ),
                "high": (
                    "if x >= 0.505: return fma(x,0.10101010101010102,1.598989898989899)"
                ),
                "activeHighJoinIsBitExact": True,
                "joinF64": high_join,
                "joinHex": f64_hex(high_join),
            },
            "selectedReplay": {
                "inputF64": gaussian_input,
                "inputHex": f64_hex(gaussian_input),
                "replayF64": gaussian_replay,
                "replayHex": f64_hex(gaussian_replay),
                "returnF64": gaussian_return,
                "returnHex": f64_hex(gaussian_return),
                "bitExact": True,
            },
            "appleLibmLogBoundaryRemainsForCrossPlatformBitwiseTransfer": True,
        },
        "getBackdropBounds": {
            "function": GET_BACKDROP_BOUNDS_FUNCTION,
            "relativeToPrepareLayer": 364696,
            "symbolByteCount": 188,
            "instructionCount": 47,
            "codeSHA256": GET_BACKDROP_BOUNDS_CODE_SHA256,
            "exactSemantics": {
                "baseSelection": [
                    "load self rectangle origin at +0x60 and size at +0x70",
                    "use the self rectangle when min(self.width,self.height) > 0",
                    "otherwise load layer rectangle origin at +0x48 and size at +0x58",
                ],
                "validity": [
                    "return the selected base unchanged when max(size) is unordered or >= DBL_MAX",
                    "return the selected base unchanged when min(size) <= 0",
                ],
                "expansion": [
                    "load one binary32 margin from self+0x24",
                    "convert -margin to binary64",
                    "add -margin to both origins",
                    "add 2*margin to both sizes, with height formed by binary64 FMA",
                    "if either expanded size <= 0, zero both size lanes",
                ],
            },
            "selectedBoundary": {
                "inputBufferF64": list(backdrop_input),
                "inputBufferHex": struct.pack("<4d", *backdrop_input).hex(),
                "returnF64": list(backdrop_return),
                "returnHex": struct.pack("<4d", *backdrop_return).hex(),
            },
            "conditionalNominalBaseMargin83Replay": {
                "assumption": (
                    "stored base rectangle is [0,0,127,127] and self+0x24 is "
                    "binary32 83; neither object field was retained in this run"
                ),
                "replayF64": list(conditional_candidate),
                "replayHex": struct.pack("<4d", *conditional_candidate).hex(),
                "matchesReturn": True,
                "directlyCapturedFact": False,
            },
        },
        "conclusion": {
            "gaussianExactPiecewiseLawDecoded": True,
            "gaussianSelectedReplayBitExact": True,
            "getBackdropBoundsCompleteSemanticsDecoded": True,
            "liveBackdropBaseAndMarginFieldsCaptured": False,
            "backdropMarginWriterDecoded": False,
            "dynamicTopologyLawDecoded": False,
            "prospectiveUnseenGeometryTransferPassed": False,
            "capturedInputOpticalParityPassed": False,
            "independentPrivateInputGenerationPassed": False,
            "physicalOutputTransferPassed": False,
            "independentWalleZeroByteFrameParityPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
        "nextExactGate": {
            "capture": [
                "the wrapper-entry BackdropLayer object fields through +0x80",
                "the wrapper-entry Layer rectangle fields from +0x48 through +0x68",
                "the exact BackdropLayer+0x24 writer identity and arithmetic",
            ],
            "requiresNewAppleCapture": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("validation", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = analyze(
        arguments.trace,
        arguments.timeline,
        arguments.inventory,
        arguments.validation,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
