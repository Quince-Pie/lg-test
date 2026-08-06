#!/usr/bin/env python3
"""Decode the accepted Gaussian and backdrop wrapper code structurally."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_prepare_layer_small_geometry_helper_code as validator


ANALYSIS_SCHEMA_VERSION = 1
RUN_ID = 31087074253
HEAD_SHA = "251b4f5c731babad2b026a22ad596fb93470a481"
ARTIFACT_ID = 8961996101
ARTIFACT_DIGEST = (
    "sha256:db819539679c8c3a2d3429df8eb3e5ca5ce7d4f9cc1329111de5c38cb965a1cd"
)
TRACE_SHA256 = "cdbc4eb4a3aa6aae9262015f57318248cdb3092a14ad2ddd18f2537ba3377d5d"
TIMELINE_SHA256 = "57b06cab4109d78d743f4a214852389d585f5d4f79022a39ed70f418368dff24"
VALIDATION_SHA256 = "be8281d67e2fd2156484f4cd8a6b430ee21ef1691d9539570a1699699b3810a5"
GAUSSIAN_CODE_SHA256 = (
    "7834bbb95f84915a6544d34b4148f7f267fcc94d2ae730888644535ffc57c0dd"
)
BACKDROP_WRAPPER_CODE_SHA256 = (
    "85a99558cc08c2a693969b55c804cd811e8ef710ac2d02460830f8bf9d6ec85a"
)
QUARTZCORE_UUID = "4D34EB4E-2BBB-3751-A362-8E2EB74656E8"
GET_BACKDROP_BOUNDS_FUNCTION = (
    "CA::Render::BackdropLayer::get_backdrop_bounds("
    "CA::Render::Layer const*, CA::Rect&) const"
)

GAUSSIAN_CONSTANT_LOADS = (
    ("highThreshold", 12, 16),
    ("lowThreshold", 32, 36),
    ("activeShift", 64, 68),
    ("logIntercept", 96, 100),
    ("logSlope", 104, 108),
    ("highIntercept", 160, 164),
    ("highSlope", 168, 172),
    ("alternateModeReturn", 188, 192),
)


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


def instruction_by_offset(target: Mapping[str, Any], offset: int) -> Mapping[str, Any]:
    matches = [
        mapping(raw, "instruction")
        for raw in sequence(target.get("instructions"), "instructions")
        if mapping(raw, "instruction").get("offset") == offset
    ]
    if len(matches) != 1:
        raise ValueError(f"instruction +{offset:#x} is not unique")
    return matches[0]


def instruction_word(instruction: Mapping[str, Any]) -> int:
    try:
        raw = bytes.fromhex(str(instruction.get("rawLittleEndianHex")))
    except ValueError as error:
        raise ValueError("instruction bytes are not hexadecimal") from error
    if len(raw) != 4:
        raise ValueError("instruction byte count differs")
    return int.from_bytes(raw, "little")


def sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def decode_adrp_target(instruction: Mapping[str, Any]) -> int:
    word = instruction_word(instruction)
    if word & 0x9F000000 != 0x90000000:
        raise ValueError("instruction is not ADRP")
    pc = instruction.get("pc")
    if not isinstance(pc, int) or isinstance(pc, bool):
        raise ValueError("instruction PC is not an integer")
    immediate = sign_extend((((word >> 5) & 0x7FFFF) << 2) | ((word >> 29) & 0x3), 21)
    return (pc & ~0xFFF) + (immediate << 12)


def decode_ldr_d_unsigned_offset(instruction: Mapping[str, Any]) -> int:
    word = instruction_word(instruction)
    if word & 0xFFC00000 != 0xFD400000:
        raise ValueError("instruction is not unsigned-offset LDR D")
    return ((word >> 10) & 0xFFF) * 8


def decode_bl_target(instruction: Mapping[str, Any]) -> int:
    word = instruction_word(instruction)
    if word & 0xFC000000 != 0x94000000:
        raise ValueError("instruction is not BL")
    pc = instruction.get("pc")
    if not isinstance(pc, int) or isinstance(pc, bool):
        raise ValueError("instruction PC is not an integer")
    return pc + (sign_extend(word & 0x03FFFFFF, 26) << 2)


def target_by_name(extension: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    matches = [
        mapping(raw, "helper target")
        for raw in sequence(extension.get("targets"), "helper targets")
        if mapping(raw, "helper target").get("name") == name
    ]
    if len(matches) != 1:
        raise ValueError(f"{name} target is not unique")
    return matches[0]


def normalized_validation(value: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(value))
    inputs = mapping(result.get("inputs"), "validation inputs")
    mutable_inputs = dict(inputs)
    mutable_inputs.pop("trace", None)
    mutable_inputs.pop("timeline", None)
    result["inputs"] = mutable_inputs
    return result


def analyze(
    trace_path: Path,
    timeline_path: Path,
    inventory_path: Path,
    validation_path: Path,
) -> dict[str, Any]:
    expected_hashes = (
        (trace_path, TRACE_SHA256, "trace"),
        (timeline_path, TIMELINE_SHA256, "timeline"),
        (validation_path, VALIDATION_SHA256, "CI validation"),
    )
    for path, expected, label in expected_hashes:
        if sha256(path) != expected:
            raise ValueError(f"{label} SHA-256 differs")

    trace = mapping(load_json(trace_path, "trace"), "trace")
    ci_validation = mapping(
        load_json(validation_path, "CI validation"), "CI validation"
    )
    independent = validator.validate(trace_path, timeline_path, inventory_path)
    if normalized_validation(ci_validation) != normalized_validation(independent):
        raise ValueError("independent validation differs from CI validation")
    if ci_validation.get("conclusion") != "success":
        raise ValueError("CI validation did not pass")

    extension = mapping(
        trace.get("prepareLayerSmallGeometryHelperCodeExtension"),
        "helper-code extension",
    )
    if extension.get("status") != "finalized" or extension.get("failures") != []:
        raise ValueError("helper-code extension did not finalize cleanly")
    gaussian = target_by_name(extension, "gaussianExpansionFactor")
    backdrop = target_by_name(extension, "backdropGetBounds")
    if gaussian.get("observedSHA256") != GAUSSIAN_CODE_SHA256:
        raise ValueError("Gaussian code hash differs")
    if backdrop.get("observedSHA256") != BACKDROP_WRAPPER_CODE_SHA256:
        raise ValueError("backdrop wrapper code hash differs")

    module = mapping(gaussian.get("module"), "Gaussian module")
    module_base = module.get("loadAddress")
    if (
        module.get("uuid") != QUARTZCORE_UUID
        or not isinstance(module_base, int)
        or isinstance(module_base, bool)
    ):
        raise ValueError("QuartzCore module identity differs")
    if mapping(backdrop.get("module"), "backdrop module") != module:
        raise ValueError("helper modules differ")

    data_constants: list[dict[str, Any]] = []
    for name, adrp_offset, load_offset in GAUSSIAN_CONSTANT_LOADS:
        adrp = instruction_by_offset(gaussian, adrp_offset)
        load = instruction_by_offset(gaussian, load_offset)
        address = decode_adrp_target(adrp) + decode_ldr_d_unsigned_offset(load)
        data_constants.append(
            {
                "name": name,
                "adrpInstructionOffset": adrp_offset,
                "loadInstructionOffset": load_offset,
                "address": address,
                "moduleRelativeOffset": address - module_base,
                "byteCount": 8,
                "valueAcceptedBeforeNextCapture": None,
            }
        )
    expected_data_offsets = [
        0x394910,
        0x394928,
        0x394930,
        0x394938,
        0x394940,
        0x394918,
        0x394920,
        0x3944F8,
    ]
    if [
        item["moduleRelativeOffset"] for item in data_constants
    ] != expected_data_offsets:
        raise ValueError("Gaussian data references differ")

    global_adrp = instruction_by_offset(gaussian, 0)
    global_flag_address = decode_adrp_target(global_adrp) + 0xA8B
    prepare = mapping(trace.get("prepareLayer"), "prepare_layer")
    prepare_start = prepare.get("symbolStart")
    if not isinstance(prepare_start, int) or isinstance(prepare_start, bool):
        raise ValueError("prepare_layer start is not an integer")
    backdrop_call = instruction_by_offset(backdrop, 36)
    backdrop_callee_start = decode_bl_target(backdrop_call)
    if backdrop_call.get("comment") != GET_BACKDROP_BOUNDS_FUNCTION:
        raise ValueError("backdrop callee symbol differs")
    if backdrop_callee_start - prepare_start != 364696:
        raise ValueError("backdrop callee relative address differs")

    return {
        "prepareLayerSmallGeometryHelperCodeAnalysisSchemaVersion": (
            ANALYSIS_SCHEMA_VERSION
        ),
        "classification": (
            "retrospective structural decode of the prospectively opened helper "
            "code; code bytes and inherited execution are accepted, while data "
            "constant values, delegated backdrop semantics, geometry transfer, "
            "and product parity remain closed"
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
        "quartzCore": {
            "uuid": QUARTZCORE_UUID,
            "loadAddress": module_base,
        },
        "gaussianExpansionFactor": {
            "codeSHA256": GAUSSIAN_CODE_SHA256,
            "symbolByteCount": 200,
            "instructionCount": 50,
            "globalModeFlag": {
                "adrpInstructionOffset": 0,
                "loadInstructionOffset": 4,
                "address": global_flag_address,
                "byteCount": 1,
                "valueAcceptedBeforeNextCapture": None,
            },
            "dataConstants": data_constants,
            "exactSymbolicControlFlow": [
                "if globalModeFlag bit 0 is set: return alternateModeReturn",
                "if x >= highThreshold: return fma(x, highSlope, highIntercept)",
                "if x <= lowThreshold: return 0",
                "z = log(2 * max(0, x + activeShift))",
                "candidate = max(0, fma(z, logSlope, logIntercept))",
                "return candidate when abs(z) < +infinity, otherwise return 0",
            ],
            "generalNumericLawDecoded": False,
            "reasonNumericLawRemainsOpen": (
                "the eight referenced binary64 data words and global mode byte "
                "were not retained by this capture"
            ),
        },
        "backdropGetBounds": {
            "codeSHA256": BACKDROP_WRAPPER_CODE_SHA256,
            "symbolByteCount": 80,
            "instructionCount": 20,
            "activeFlagMask": 0x500,
            "exactWrapperBehavior": [
                "compute active = (*(uint32_t *)(self + 12) & 0x500) != 0",
                "when active, call get_backdrop_bounds(self, layer, primaryRect)",
                "when inactive, zero all 32 bytes of primaryRect",
                "when active and optionalRect is non-null, zero all 32 bytes of optionalRect",
                "return active",
            ],
            "delegatedFunction": GET_BACKDROP_BOUNDS_FUNCTION,
            "delegatedFunctionStart": backdrop_callee_start,
            "delegatedFunctionRelativeToPrepareLayer": 364696,
            "delegatedFunctionCodeAcceptedBeforeNextCapture": None,
            "allocationGeneralLawDecoded": False,
        },
        "conclusion": {
            "transportRetryPassed": True,
            "helperCodeOpeningPassed": True,
            "gaussianSymbolicControlFlowDecoded": True,
            "gaussianGeneralNumericLawDecoded": False,
            "backdropWrapperSemanticsDecoded": True,
            "backdropAllocationGeneralLawDecoded": False,
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
                "the eight structurally referenced Gaussian binary64 words",
                "the structurally referenced global mode byte",
                "the complete get_backdrop_bounds symbol at prepare_layer + 364696",
            ],
            "expectedGaussianConstantValues": None,
            "expectedBackdropCalleeCodeSHA256": None,
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
