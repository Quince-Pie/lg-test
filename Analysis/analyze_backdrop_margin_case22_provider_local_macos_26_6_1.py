#!/usr/bin/env python3
"""Replay the selected local DesignLibrary margin-provider path exactly."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_backdrop_margin_case22_provider_local_macos_26_6_1 as validator


ANALYSIS_SCHEMA_VERSION = 1
TRACE_SHA256 = "19e7d74f3aba55e5c6924d7119fddcf20578a98a4e7b946cc4a435918df4059f"
PREREGISTRATION_SHA256 = (
    "9d1e65309058303dfa40574827d38ba8ce602c77cb98e363da348b4e4bf4ba06"
)
VALIDATION_SHA256 = "eccee6478fffcdecefa238243374c92330a5428e7e8bde6c44457da28ac0db04"

EXPECTED_PROVIDER_PATH = (
    0x000,
    0x004,
    0x008,
    0x00C,
    0x010,
    0x014,
    0x018,
    0x01C,
    0x020,
    0x024,
    0x028,
    0x02C,
    0x030,
    0x034,
    0x038,
    0x03C,
    0x040,
    0x044,
    0x048,
    0x04C,
    0x050,
    0x054,
    0x058,
    0x05C,
    0x060,
    0x064,
    0x068,
    0x06C,
    0x070,
    0x074,
    0x078,
    0x07C,
    0x080,
    0x088,
    0x08C,
    0x090,
    0x094,
    0x098,
    0x09C,
    0x0A0,
    0x0A4,
    0x0A8,
    0x110,
    0x114,
    0x118,
    0x11C,
    0x120,
    0x124,
    0x128,
    0x12C,
    0x130,
    0x16C,
    0x170,
    0x174,
    0x178,
    0x17C,
    0x180,
    0x1B4,
    0x1B8,
    0x1BC,
    0x1C0,
    0x1C4,
    0x1D0,
    0x1D4,
    0x1D8,
    0x1DC,
    0x1E0,
    0x1E4,
    0x1E8,
    0x1EC,
    0x1F0,
    0x1F4,
    0x1F8,
    0x1FC,
)

EXPECTED_PATH_INSTRUCTIONS = {
    0x01C: "8aae406d",
    0x020: "8c0e40fd",
    0x024: "8d1640fd",
    0x028: "8e1e40fd",
    0x02C: "888a40bd",
    0x030: "894a40fd",
    0x034: "001da84e",
    0x038: "d03d0094",
    0x03C: "82c1601e",
    0x040: "a341611e",
    0x044: "a821601e",
    0x048: "01e4006f",
    0x04C: "23ac631e",
    0x050: "4228631e",
    0x054: "c009601e",
    0x058: "4020601e",
    0x05C: "009c621e",
    0x060: "42c1601e",
    0x064: "63c1601e",
    0x068: "4020631e",
    0x06C: "629c621e",
    0x070: "4028601e",
    0x074: "0821201e",
    0x078: "6d000054",
    0x07C: "2821601e",
    0x080: "4c000054",
    0x088: "819a496d",
    0x08C: "85924a6d",
    0x090: "828e4b6d",
    0x094: "c820601e",
    0x098: "4a030054",
    0x09C: "a820601e",
    0x0A0: "4a030054",
    0x0A4: "8820601e",
    0x0A8: "4a030054",
    0x110: "8020621e",
    0x114: "429c641e",
    0x118: "4020631e",
    0x11C: "639c621e",
    0x120: "2820601e",
    0x124: "ad010054",
    0x128: "811241bd",
    0x12C: "2820201e",
    0x130: "ec010054",
    0x16C: "817640fd",
    0x170: "827e40fd",
    0x174: "2820601e",
    0x178: "aafeff54",
    0x17C: "4820601e",
    0x180: "aa010054",
    0x1B4: "81b240fd",
    0x1B8: "847a41bd",
    0x1BC: "21c0601e",
    0x1C0: "8820201e",
    0x1C4: "6c000054",
    0x1D0: "0020631e",
    0x1D4: "639c601e",
    0x1D8: "6020621e",
    0x1DC: "449c631e",
    0x1E0: "8020611e",
    0x1E4: "209c641e",
    0x1FC: "ff0f5fd6",
}

HELPER_CONSTANT_HEX = {
    "highThreshold": "295c8fc2f528e03f",
    "lowThreshold": "7b14ae47e17a743f",
    "activeShift": "7b14ae47e17a74bf",
    "highShift": "295c8fc2f528e0bf",
    "highSpan": "ae47e17a14aedf3f",
    "highScale": "999999999999a93f",
    "logSlope": "333333333333d33f",
    "intercept": "666666666666fa3f",
}

OBJECT_F64_FIELDS = {
    "axisX": 0x008,
    "axisY": 0x010,
    "shapeRadius": 0x018,
    "shapeInset": 0x028,
    "gaussianRadius": 0x038,
    "gaussianGate": 0x090,
    "directionGate": 0x098,
    "direction0": 0x0A0,
    "direction1": 0x0A8,
    "direction2": 0x0B0,
    "direction3": 0x0B8,
    "direction4": 0x0C0,
    "secondary0": 0x0E8,
    "secondary1": 0x0F8,
    "absoluteCandidate": 0x160,
}

OBJECT_F32_FIELDS = {
    "gaussianInput": 0x088,
    "secondary1Gate": 0x110,
    "absoluteCandidateGate": 0x178,
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


def f32_raw(value: float) -> str:
    return struct.pack("<f", value).hex()


def f64_raw(value: float) -> str:
    return struct.pack("<d", value).hex()


def f64_from_raw(raw: str) -> float:
    data = bytes.fromhex(raw)
    if len(data) != 8:
        raise ValueError("binary64 word has the wrong byte count")
    return struct.unpack("<d", data)[0]


def snapshot_raw(value: Any, label: str) -> bytes:
    snapshot = mapping(value, label)
    try:
        raw = bytes.fromhex(str(snapshot.get("hex")))
    except ValueError as error:
        raise ValueError(f"{label} is not hexadecimal") from error
    if snapshot.get("byteCount") != len(raw):
        raise ValueError(f"{label} byte count differs")
    return raw


def register_raw(registers: Any, name: str, label: str) -> bytes:
    register_set = mapping(registers, label)
    matches = [
        mapping(item, f"{label} SIMD register")
        for item in sequence(register_set.get("simd"), f"{label} SIMD registers")
        if mapping(item, f"{label} SIMD register").get("name") == name
    ]
    if len(matches) != 1:
        raise ValueError(f"{label} {name} is not unique")
    try:
        raw = bytes.fromhex(str(matches[0].get("hex")))
    except ValueError as error:
        raise ValueError(f"{label} {name} is not hexadecimal") from error
    if len(raw) != 16:
        raise ValueError(f"{label} {name} byte count differs")
    return raw


def normalized_validation(value: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(value))
    inputs = dict(mapping(result.get("inputs"), "validation inputs"))
    inputs.pop("trace", None)
    inputs.pop("preregistration", None)
    result["inputs"] = inputs
    return result


def ordered_max(left: float, right: float) -> float:
    """Match the selected finite FCMP/FCSEL `right if left <= right` form."""
    return right if left <= right else left


def replay_helper(value_f32: float) -> float:
    """Replay the complete finite-input DesignLibrary Gaussian helper law."""
    value = float(struct.unpack("<f", struct.pack("<f", value_f32))[0])
    constants = {name: f64_from_raw(raw) for name, raw in HELPER_CONSTANT_HEX.items()}
    if value >= constants["highThreshold"]:
        result = min(value, 1.0)
        result = result + constants["highShift"]
        result = result / constants["highSpan"]
        result = result * constants["highScale"]
        return result + constants["intercept"]
    if value <= constants["lowThreshold"]:
        return 0.0
    result = value + constants["activeShift"]
    result = ordered_max(result, 0.0)
    result = result + result
    result = math.log(result)
    result = result * constants["logSlope"]
    result = result + constants["intercept"]
    return 0.0 if result < 0.0 else result


def field_values(object_raw: bytes) -> tuple[dict[str, float], dict[str, float]]:
    if len(object_raw) != validator.PROVIDER_OBJECT_BYTE_COUNT:
        raise ValueError("provider object byte count differs")
    f64 = {
        name: struct.unpack_from("<d", object_raw, offset)[0]
        for name, offset in OBJECT_F64_FIELDS.items()
    }
    f32 = {
        name: struct.unpack_from("<f", object_raw, offset)[0]
        for name, offset in OBJECT_F32_FIELDS.items()
    }
    if not all(math.isfinite(value) for value in (*f64.values(), *f32.values())):
        raise ValueError("selected provider field is not finite")
    return f64, f32


def field_records(
    object_raw: bytes, f64: Mapping[str, float], f32: Mapping[str, float]
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for name, offset in OBJECT_F64_FIELDS.items():
        value = f64[name]
        records.append(
            {
                "name": name,
                "objectOffset": offset,
                "storage": "binary64",
                "rawLittleEndianHex": object_raw[offset : offset + 8].hex(),
                "value": value,
                "hexadecimalValue": value.hex(),
                "publicMeaningEstablished": False,
            }
        )
    for name, offset in OBJECT_F32_FIELDS.items():
        value = f32[name]
        records.append(
            {
                "name": name,
                "objectOffset": offset,
                "storage": "binary32",
                "rawLittleEndianHex": object_raw[offset : offset + 4].hex(),
                "value": value,
                "hexadecimalValue": value.hex(),
                "publicMeaningEstablished": False,
            }
        )
    return sorted(records, key=lambda item: (item["objectOffset"], item["storage"]))


def state_map(extension: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    states = [
        mapping(item, "provider instruction state")
        for item in sequence(extension.get("instructionStates"), "instruction states")
    ]
    offsets = tuple(state.get("symbolOffset") for state in states)
    if offsets != EXPECTED_PROVIDER_PATH:
        raise ValueError("selected provider path differs")
    result: dict[int, Mapping[str, Any]] = {}
    for state in states:
        offset = state.get("symbolOffset")
        if not isinstance(offset, int) or isinstance(offset, bool) or offset in result:
            raise ValueError("provider state offset is invalid or repeated")
        result[offset] = state
    for offset, instruction in EXPECTED_PATH_INSTRUCTIONS.items():
        if result[offset].get("instructionHex") != instruction:
            raise ValueError(f"provider instruction +{offset:#x} differs")
    return result


def state_register(
    states: Mapping[int, Mapping[str, Any]], offset: int, name: str
) -> bytes:
    return register_raw(
        states[offset].get("registersBefore"), name, f"provider +{offset:#x}"
    )


def require_f64_register(
    states: Mapping[int, Mapping[str, Any]],
    offset: int,
    name: str,
    expected: float,
    label: str,
) -> dict[str, Any]:
    observed = state_register(states, offset, name)[:8]
    expected_raw = struct.pack("<d", expected)
    if observed != expected_raw:
        raise ValueError(f"{label} replay differs at provider +{offset:#x} {name}")
    return {
        "label": label,
        "stateOffset": offset,
        "register": name,
        "valueF64": expected,
        "rawLittleEndianHex": expected_raw.hex(),
        "bitExact": True,
    }


def analyze(
    trace_path: Path,
    preregistration_path: Path,
    validation_path: Path,
) -> dict[str, Any]:
    for path, expected, label in (
        (trace_path, TRACE_SHA256, "trace"),
        (preregistration_path, PREREGISTRATION_SHA256, "preregistration"),
        (validation_path, VALIDATION_SHA256, "validation"),
    ):
        if sha256(path) != expected:
            raise ValueError(f"{label} SHA-256 differs")

    trace = mapping(load_json(trace_path, "trace"), "trace")
    retained_validation = mapping(
        load_json(validation_path, "validation"), "validation"
    )
    independent_validation = validator.validate(trace_path, preregistration_path)
    if normalized_validation(retained_validation) != normalized_validation(
        independent_validation
    ):
        raise ValueError("independent provider validation differs")
    if retained_validation.get("conclusion") != "success":
        raise ValueError("provider validation did not pass")

    extension = mapping(trace.get("case22ProviderTrace"), "provider extension")
    states = state_map(extension)
    entry = mapping(extension.get("entry"), "provider entry")
    object_raw = snapshot_raw(entry.get("object"), "provider object")
    f64, f32 = field_values(object_raw)

    helpers = sequence(extension.get("helperCallees"), "helper callees")
    if len(helpers) != 1:
        raise ValueError("selected helper count differs")
    helper = mapping(helpers[0], "Gaussian helper")
    helper_entry = register_raw(
        helper.get("registersAtEntry"), "v0", "Gaussian helper entry"
    )
    helper_return_raw = register_raw(
        helper.get("registersAtReturn"), "v0", "Gaussian helper return"
    )[:8]
    if helper_entry[:4] != object_raw[OBJECT_F32_FIELDS["gaussianInput"] : 0x08C]:
        raise ValueError("Gaussian helper input differs from provider object")
    helper_input = struct.unpack("<f", helper_entry[:4])[0]
    helper_replay = replay_helper(helper_input)
    if f64_raw(helper_replay) != helper_return_raw.hex():
        raise ValueError("Gaussian helper selected replay differs")
    if state_register(states, 0x03C, "v0")[:8] != helper_return_raw:
        raise ValueError("Gaussian return differs at provider continuation")

    checkpoints: list[dict[str, Any]] = []
    shape_radius = abs(f64["shapeRadius"])
    checkpoints.append(
        require_f64_register(states, 0x040, "v2", shape_radius, "abs(shapeRadius)")
    )
    negative_inset = -f64["shapeInset"]
    checkpoints.append(
        require_f64_register(states, 0x044, "v3", negative_inset, "-shapeInset")
    )
    inset_expansion = 0.0 if f64["shapeInset"] >= 0.0 else negative_inset
    checkpoints.append(
        require_f64_register(
            states, 0x050, "v3", inset_expansion, "max(-shapeInset, 0)"
        )
    )
    shape_candidate = shape_radius + inset_expansion
    checkpoints.append(
        require_f64_register(
            states,
            0x054,
            "v2",
            shape_candidate,
            "abs(shapeRadius) + max(-shapeInset, 0)",
        )
    )
    gaussian_candidate = f64["gaussianRadius"] * helper_replay
    checkpoints.append(
        require_f64_register(
            states,
            0x058,
            "v0",
            gaussian_candidate,
            "gaussianRadius * gaussianExpansionFactor(gaussianInput)",
        )
    )
    primary_candidate = ordered_max(shape_candidate, gaussian_candidate)
    checkpoints.append(
        require_f64_register(
            states,
            0x060,
            "v0",
            primary_candidate,
            "max(shapeCandidate, gaussianCandidate)",
        )
    )
    axis_x = abs(f64["axisX"])
    axis_y = abs(f64["axisY"])
    checkpoints.append(require_f64_register(states, 0x064, "v2", axis_x, "abs(axisX)"))
    checkpoints.append(require_f64_register(states, 0x068, "v3", axis_y, "abs(axisY)"))
    axis_candidate = ordered_max(axis_x, axis_y)
    checkpoints.append(
        require_f64_register(
            states, 0x070, "v2", axis_candidate, "max(abs(axisX), abs(axisY))"
        )
    )
    base_candidate = axis_candidate + primary_candidate
    checkpoints.append(
        require_f64_register(
            states,
            0x074,
            "v0",
            base_candidate,
            "axisCandidate + primaryCandidate",
        )
    )
    if not (f32["gaussianInput"] > 0.0 and f64["gaussianGate"] > 0.0):
        raise ValueError("selected base-candidate gate differs")

    directions = [f64[f"direction{index}"] for index in range(5)]
    if not (directions[0] < 0.0 and directions[1] < 0.0 and directions[2] >= 0.0):
        raise ValueError("selected directional branch differs")
    directional_candidate = ordered_max(directions[2], directions[3])
    checkpoints.append(
        require_f64_register(
            states,
            0x118,
            "v2",
            directional_candidate,
            "max(direction2, direction3)",
        )
    )
    directional_candidate = ordered_max(directional_candidate, directions[4])
    checkpoints.append(
        require_f64_register(
            states,
            0x120,
            "v3",
            directional_candidate,
            "max(direction2, direction3, direction4)",
        )
    )
    if not (f64["directionGate"] > 0.0 and f32["secondary1Gate"] > 0.0):
        raise ValueError("selected secondary gate differs")
    if not (f64["secondary0"] < 0.0 and f64["secondary1"] >= 0.0):
        raise ValueError("selected secondary branch differs")

    absolute_candidate = abs(f64["absoluteCandidate"])
    checkpoints.append(
        require_f64_register(
            states,
            0x1C0,
            "v1",
            absolute_candidate,
            "abs(absoluteCandidate)",
        )
    )
    if not f32["absoluteCandidateGate"] > 0.0:
        raise ValueError("selected absolute-candidate gate differs")
    selected = ordered_max(base_candidate, directional_candidate)
    checkpoints.append(
        require_f64_register(
            states,
            0x1D8,
            "v3",
            selected,
            "max(baseCandidate, directionalCandidate)",
        )
    )
    selected = ordered_max(selected, f64["secondary1"])
    checkpoints.append(
        require_f64_register(
            states,
            0x1E0,
            "v4",
            selected,
            "max(previous, secondary1)",
        )
    )
    selected = ordered_max(selected, absolute_candidate)
    checkpoints.append(
        require_f64_register(
            states,
            0x1E8,
            "v0",
            selected,
            "max(previous, abs(absoluteCandidate))",
        )
    )
    provider_return = register_raw(
        mapping(extension.get("return"), "provider return").get("registers"),
        "v0",
        "provider return",
    )[:8]
    if provider_return.hex() != f64_raw(selected):
        raise ValueError("selected provider return replay differs")

    constants = [
        {
            "name": name,
            "rawLittleEndianHex": raw,
            "binary64": f64_from_raw(raw),
            "binary64Hex": f64_from_raw(raw).hex(),
        }
        for name, raw in HELPER_CONSTANT_HEX.items()
    ]
    return {
        "backdropMarginCase22ProviderLocalMacOSAnalysisSchemaVersion": (
            ANALYSIS_SCHEMA_VERSION
        ),
        "classification": (
            "retrospective exact decode of the output-blind selected local "
            "DesignLibrary provider path; every retained arithmetic checkpoint "
            "and the parent return are replayed bit for bit, while public field "
            "meaning, unseen branch transfer, and product parity remain closed"
        ),
        "inputs": {
            "trace": str(trace_path),
            "traceSHA256": TRACE_SHA256,
            "preregistration": str(preregistration_path),
            "preregistrationSHA256": PREREGISTRATION_SHA256,
            "validation": str(validation_path),
            "validationSHA256": VALIDATION_SHA256,
            "independentValidationEqualExceptCallerPaths": True,
        },
        "provider": {
            "designLibraryUUID": validator.DESIGN_LIBRARY_UUID,
            "function": validator.PROVIDER_FUNCTION,
            "moduleOffset": validator.PROVIDER_MODULE_OFFSET,
            "symbolByteCount": validator.PROVIDER_BYTE_COUNT,
            "codeSHA256": validator.PROVIDER_CODE_SHA256,
            "executedInstructionCount": len(EXPECTED_PROVIDER_PATH),
            "executedOffsets": list(EXPECTED_PROVIDER_PATH),
            "allSelectedInstructionsContinuousAndExact": True,
            "completeSymbolCaptured": True,
            "allStaticBranchesExecuted": False,
        },
        "object": {
            "byteCount": len(object_raw),
            "sha256": hashlib.sha256(object_raw).hexdigest(),
            "unchangedAcrossCall": True,
            "fieldsUsedBySelectedPath": field_records(object_raw, f64, f32),
        },
        "gaussianExpansionFactor": {
            "function": validator.HELPER_FUNCTION,
            "moduleOffset": validator.HELPER_MODULE_OFFSET,
            "symbolByteCount": validator.HELPER_BYTE_COUNT,
            "codeSHA256": validator.HELPER_CODE_SHA256,
            "constants": constants,
            "finiteInputLaw": {
                "inputDomain": "binary32 promoted exactly to binary64",
                "low": "if x <= 0.005: return 0",
                "active": (
                    "if 0.005 < x < 0.505: return "
                    "max(0, log(2*max(x-0.005,0))*0.3 + 1.65)"
                ),
                "high": ("if x >= 0.505: return ((min(x,1)-0.505)/0.495)*0.05 + 1.65"),
                "operationOrderMatchesMachineCode": True,
            },
            "selectedReplay": {
                "inputF32": helper_input,
                "inputRawLittleEndianHex": helper_entry[:4].hex(),
                "returnF64": helper_replay,
                "returnRawLittleEndianHex": helper_return_raw.hex(),
                "bitExact": True,
            },
            "appleLibmLogBoundaryRemainsForUnseenBitwiseTransfer": True,
        },
        "selectedArithmetic": {
            "checkpoints": checkpoints,
            "shapeCandidateF64": shape_candidate,
            "gaussianCandidateF64": gaussian_candidate,
            "primaryWinner": "shapeCandidate",
            "axisCandidateF64": axis_candidate,
            "baseCandidateF64": base_candidate,
            "directionalCandidateF64": directional_candidate,
            "secondary1F64": f64["secondary1"],
            "absoluteCandidateF64": absolute_candidate,
            "finalWinner": "baseCandidate",
            "exactSelectedIdentity": (
                "max(max(max(max(abs(axisX),abs(axisY)) + "
                "max(abs(shapeRadius)+max(-shapeInset,0), "
                "gaussianRadius*gaussianExpansionFactor(gaussianInput)), "
                "max(direction2,direction3,direction4)), secondary1), "
                "abs(absoluteCandidate))"
            ),
            "returnF64": selected,
            "returnRawLittleEndianHex": provider_return.hex(),
            "parentReturnMatchedBitwise": True,
            "allRetainedArithmeticCheckpointsMatchedBitwise": True,
        },
        "conclusion": {
            "completeProviderCodeCaptured": True,
            "selectedProviderPathCaptured": True,
            "selectedProviderArithmeticDecoded": True,
            "selectedProviderReplayBitExact": True,
            "publicObjectFieldMeaningsDecoded": False,
            "completeFiniteProviderLawDecoded": False,
            "unobservedProviderBranchesProspectivelyValidated": False,
            "publicInputMarginLawDecoded": False,
            "upstreamIntegerCropAllocationPolicyDecoded": False,
            "prospectiveUnseenProfileTransferPassed": False,
            "capturedInputOpticalParityPassed": False,
            "physicalOutputTransferPassed": False,
            "independentWalleZeroByteFrameParityPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
        "nextExactGate": {
            "target": (
                "map provider object offsets to controlled public inputs and cover "
                "the unopened sign/gate branches on the local Retina Mac, then "
                "solve the upstream integer crop/allocation policy"
            ),
            "requiresNewAppleCapture": True,
            "githubActionsRequired": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("preregistration", type=Path)
    parser.add_argument("validation", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = analyze(
        arguments.trace,
        arguments.preregistration,
        arguments.validation,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
