#!/usr/bin/env python3
"""Decode the exact small-geometry SDF, shadow, clip, and Filter arithmetic."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_prepare_layer_filter_sdf_small_geometry as validator


ANALYSIS_SCHEMA_VERSION = 1
TRACE_SHA256 = "61fe2befb665b985b8a1f136ec1777cb9273b472ee7019f9a073d2b5ef09feaa"
TIMELINE_SHA256 = "f82e2f3403cec86dc99abb333e6d8745d4504d229011974bee5ca10c3ed37e67"
VALIDATION_SHA256 = (
    "c4c4c93648b13ee9808a899a65d572ebaf331495aeaa163899ed5ede61e50855"
)
FILTER_STATE_SHA256 = (
    "41b137644eac7e9a0e3688ed4a2d9e3e4e983ebc85b9a59e1a5b632a53523ee3"
)
SDF_STATE_SHA256 = (
    "2b1749abbd0653004c601ddb283b83ae8ff32540f52bd5e7ed849eda575f466e"
)
FILTER_CODE_SHA256 = (
    "e8766dcefdadc0074f7bb4e2bf62955072891858009dca6c72a7eef1c96789d0"
)
SDF_CODE_SHA256 = (
    "1db9b60701304250a5784288bfa03136ab74db137eb021428d0fad7fa87b01ae"
)
ROLE_CARRIER_TRANSLATION_OFFSET = 0x5F0
ROLE_SHADOW_OFFSET = 0x5E0
SDF_PARAMETER_OFFSET = 0x20
BACKDROP_RECTANGLE_BYTE_COUNT = 32

GAUSSIAN_FUNCTION = "CA::OGL::gaussian_expansion_factor(double)"
BLEED_FUNCTION = (
    "CA::Render::get_glass_filter_bleed_blur_radius("
    "CA::Render::KeyValueArray const*)"
)
BACKDROP_FUNCTION = (
    "CA::Render::BackdropLayer::get_bounds("
    "CA::Render::Layer const*, CA::Rect&, CA::Rect*) const"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} is not an object")
    return value


def sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{label} is not an array")
    return value


def finite(value: Any, label: str) -> float:
    result = float(value)
    if isinstance(value, bool) or not math.isfinite(result):
        raise ValueError(f"{label} is not finite")
    return result


def snapshot_bytes(value: Any, label: str) -> bytes:
    snapshot = mapping(value, label)
    try:
        payload = bytes.fromhex(str(snapshot.get("hex")))
    except ValueError as error:
        raise ValueError(f"{label} is not hexadecimal") from error
    if snapshot.get("byteCount") != len(payload):
        raise ValueError(f"{label} byte count differs")
    return payload


def f64_hex(values: Sequence[float]) -> str:
    return struct.pack(f"<{len(values)}d", *values).hex()


def rect_from_snapshot(value: Any, label: str) -> tuple[float, float, float, float]:
    payload = snapshot_bytes(value, label)
    if len(payload) < 32:
        raise ValueError(f"{label} is shorter than one rectangle")
    return struct.unpack_from("<4d", payload)


def binary64_fma(left: float, right: float, addend: float) -> float:
    if hasattr(math, "fma"):
        return math.fma(left, right, addend)
    function = ctypes.CDLL(None).fma
    function.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double]
    function.restype = ctypes.c_double
    return float(function(left, right, addend))


def register_pair(registers: Any, name: str, label: str) -> tuple[float, float]:
    register_set = mapping(registers, label)
    matches = [
        mapping(raw, f"{label} SIMD register")
        for raw in sequence(register_set.get("simd"), f"{label} SIMD registers")
        if mapping(raw, f"{label} SIMD register").get("name") == name
    ]
    if len(matches) != 1:
        raise ValueError(f"{label} {name} is not unique")
    payload = bytes.fromhex(str(matches[0].get("hex")))
    if len(payload) != 16:
        raise ValueError(f"{label} {name} byte count differs")
    return struct.unpack("<2d", payload)


def general_register(registers: Any, name: str, label: str) -> int:
    register_set = mapping(registers, label)
    matches = [
        mapping(raw, f"{label} general register")
        for raw in sequence(register_set.get("general"), f"{label} general registers")
        if mapping(raw, f"{label} general register").get("name") == name
    ]
    if len(matches) != 1:
        raise ValueError(f"{label} {name} is not unique")
    value = matches[0].get("unsignedValue")
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} {name} is not an integer")
    return value


def state_at(states: Sequence[Any], scope: str, offset: int) -> Mapping[str, Any]:
    matches = [
        mapping(raw, "instruction state")
        for raw in states
        if mapping(raw, "instruction state").get("openedScopeName") == scope
        and mapping(
            mapping(raw, "instruction state").get("instruction"), "instruction"
        ).get("scopeOffset")
        == offset
    ]
    if len(matches) != 1:
        raise ValueError(f"{scope}+{offset:#x} is not unique")
    return matches[0]


def state_pair(
    states: Sequence[Any], scope: str, offset: int, register: str
) -> tuple[float, float]:
    state = state_at(states, scope, offset)
    return register_pair(
        state.get("registersAfter"), register, f"{scope}+{offset:#x}"
    )


def boundary_by_function(
    boundaries: Sequence[Any], function: str
) -> Mapping[str, Any]:
    matches = [
        mapping(raw, "opaque boundary")
        for raw in boundaries
        if mapping(
            mapping(raw, "opaque boundary").get("entryFrame"), "boundary entry"
        ).get("function")
        == function
    ]
    if len(matches) != 1:
        raise ValueError(f"{function} boundary is not unique")
    return matches[0]


def boundary_return_scalar(boundary: Mapping[str, Any], label: str) -> float:
    return register_pair(boundary.get("registersAtReturn"), "v0", label)[0]


def role_inputs(first_state: Mapping[str, Any]) -> tuple[tuple[float, float], float]:
    role = snapshot_bytes(first_state.get("callerRoleBefore"), "caller role")
    if len(role) < ROLE_CARRIER_TRANSLATION_OFFSET + 16:
        raise ValueError("caller role is shorter than required inputs")
    carrier = struct.unpack_from("<2d", role, ROLE_CARRIER_TRANSLATION_OFFSET)
    shadow_offset_y = struct.unpack_from("<d", role, ROLE_SHADOW_OFFSET)[0]
    return carrier, shadow_offset_y


def backdrop_rectangles(
    boundary: Mapping[str, Any],
) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]:
    registers = boundary.get("registersAtEntry")
    destination = general_register(registers, "x2", "backdrop entry registers")
    entry_snapshot = mapping(boundary.get("stackAtEntry"), "backdrop entry stack")
    return_snapshot = mapping(boundary.get("stackAtReturn"), "backdrop return stack")
    entry_base = entry_snapshot.get("address")
    return_base = return_snapshot.get("address")
    if (
        not isinstance(entry_base, int)
        or isinstance(entry_base, bool)
        or return_base != entry_base
    ):
        raise ValueError("backdrop stack base differs")
    offset = destination - entry_base
    entry = snapshot_bytes(entry_snapshot, "backdrop entry stack")
    returned = snapshot_bytes(return_snapshot, "backdrop return stack")
    if offset < 0 or offset + BACKDROP_RECTANGLE_BYTE_COUNT > len(entry):
        raise ValueError("backdrop rectangle is outside the retained stack")
    return (
        struct.unpack_from("<4d", entry, offset),
        struct.unpack_from("<4d", returned, offset),
    )


def add_pair(left: tuple[float, float], right: tuple[float, float]) -> tuple[float, float]:
    return left[0] + right[0], left[1] + right[1]


def subtract_pair(
    left: tuple[float, float], right: tuple[float, float]
) -> tuple[float, float]:
    return left[0] - right[0], left[1] - right[1]


def exact_pair(
    candidate: tuple[float, float], observed: tuple[float, float], label: str
) -> None:
    if f64_hex(candidate) != f64_hex(observed):
        raise ValueError(f"{label} differs")


def replay_sdf(
    entry: tuple[float, float, float, float],
    parameters: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    radius, offset_x, offset_y, reserved = parameters
    if reserved != 0.0:
        raise ValueError("SDF reserved parameter differs")
    return (
        entry[0] - radius + offset_x,
        entry[1] - radius + offset_y,
        entry[2] + 2.0 * radius,
        entry[3] + 2.0 * radius,
    )


def analyze(
    trace_path: Path,
    timeline_path: Path,
    inventory_path: Path,
    validation_path: Path,
) -> dict[str, Any]:
    observed_hashes = {
        "trace": sha256(trace_path),
        "timeline": sha256(timeline_path),
        "validation": sha256(validation_path),
    }
    expected_hashes = {
        "trace": TRACE_SHA256,
        "timeline": TIMELINE_SHA256,
        "validation": VALIDATION_SHA256,
    }
    if observed_hashes != expected_hashes:
        raise ValueError("small-geometry artifact hash differs")

    local_validation = validator.validate(trace_path, timeline_path, inventory_path)
    archived_validation = mapping(
        json.loads(validation_path.read_text(encoding="utf-8")), "validation"
    )
    normalized_local_validation = json.loads(
        json.dumps(local_validation, sort_keys=True, allow_nan=False)
    )
    normalized_inputs = mapping(
        normalized_local_validation.get("inputs"), "local validation inputs"
    )
    archived_inputs = mapping(
        archived_validation.get("inputs"), "archived validation inputs"
    )
    normalized_inputs["trace"] = archived_inputs.get("trace")
    normalized_inputs["timeline"] = archived_inputs.get("timeline")
    if (
        local_validation.get("conclusion") != "success"
        or archived_validation.get("conclusion") != "success"
        or normalized_local_validation != archived_validation
        or mapping(local_validation.get("filter"), "Filter validation").get(
            "instructionStatesSHA256"
        )
        != FILTER_STATE_SHA256
        or mapping(local_validation.get("sdf"), "SDF validation").get(
            "instructionStatesSHA256"
        )
        != SDF_STATE_SHA256
    ):
        raise ValueError("small-geometry validation differs")

    trace = mapping(json.loads(trace_path.read_text(encoding="utf-8")), "trace")
    extension = mapping(
        trace.get("prepareLayerFilterMapBoundsExtension"), "Filter extension"
    )
    states = sequence(extension.get("filterInstructionStates"), "Filter states")
    boundaries = sequence(extension.get("opaqueCalleeBoundaries"), "boundaries")

    sdf = mapping(extension.get("sdfMapBoundsDiagnostic"), "SDF diagnostic")
    sdf_entry = rect_from_snapshot(
        mapping(sdf.get("entry"), "SDF entry").get("output"), "SDF entry output"
    )
    sdf_return = rect_from_snapshot(
        mapping(sdf.get("return"), "SDF return").get("output"), "SDF return output"
    )
    sdf_object = snapshot_bytes(
        mapping(sdf.get("entry"), "SDF entry").get("object"), "SDF object"
    )
    sdf_parameters = struct.unpack_from("<4f", sdf_object, SDF_PARAMETER_OFFSET)
    sdf_replay = replay_sdf(sdf_entry, sdf_parameters)
    if f64_hex(sdf_replay) != f64_hex(sdf_return):
        raise ValueError("SDF replay differs")

    filter_entry = rect_from_snapshot(
        mapping(extension.get("filterEntry"), "Filter entry").get("output"),
        "Filter entry output",
    )
    filter_return = rect_from_snapshot(
        mapping(extension.get("filterReturn"), "Filter return").get("output"),
        "Filter return output",
    )
    if f64_hex(filter_entry) != f64_hex(sdf_return):
        raise ValueError("SDF-to-Filter handoff differs")

    carrier, role_shadow_offset_y = role_inputs(
        mapping(states[0], "first Filter state")
    )
    transform_x = -carrier[0]
    transform_y = carrier[1]
    local_origin = (
        filter_entry[0] - transform_x,
        -((filter_entry[1] - transform_y) + filter_entry[3]),
    )
    local_size = filter_entry[2:4]

    gaussian = boundary_by_function(boundaries, GAUSSIAN_FUNCTION)
    bleed = boundary_by_function(boundaries, BLEED_FUNCTION)
    backdrop = boundary_by_function(boundaries, BACKDROP_FUNCTION)
    gaussian_input = register_pair(
        gaussian.get("registersAtEntry"), "v0", "Gaussian entry"
    )[0]
    gaussian_factor = boundary_return_scalar(gaussian, "Gaussian return")
    bleed_radius = boundary_return_scalar(bleed, "bleed return")

    shadow_radius = boundary_return_scalar(
        mapping(boundaries[19], "shadow-radius boundary"), "shadow-radius return"
    )
    shadow_opacity = boundary_return_scalar(
        mapping(boundaries[20], "shadow-opacity boundary"), "shadow-opacity return"
    )
    blur_radius = boundary_return_scalar(
        mapping(boundaries[23], "blur-radius boundary"), "blur-radius return"
    )
    if gaussian_input != shadow_opacity:
        raise ValueError("Gaussian helper input differs from shadow opacity")

    shadow_offset = (
        register_pair(
            mapping(boundaries[18], "shadow-offset boundary").get(
                "registersAtReturn"
            ),
            "v0",
            "shadow-offset x return",
        )[0],
        register_pair(
            mapping(boundaries[18], "shadow-offset boundary").get(
                "registersAtReturn"
            ),
            "v1",
            "shadow-offset y return",
        )[0],
    )
    if shadow_offset[1] != role_shadow_offset_y:
        raise ValueError("shadow offset differs from retained role")

    shadow_expansion = gaussian_factor * shadow_radius
    shadow_origin = (
        local_origin[0] - shadow_expansion,
        local_origin[1] - shadow_expansion,
    )
    shadow_size = (
        binary64_fma(shadow_expansion, 2.0, local_size[0]),
        binary64_fma(shadow_expansion, 2.0, local_size[1]),
    )
    shifted_shadow_origin = add_pair(shadow_origin, shadow_offset)
    shadow_far = add_pair(shifted_shadow_origin, shadow_size)

    radius = max(2.0 * blur_radius, bleed_radius)
    negative_expansion = radius * -2.8
    filter_expansion = radius * 2.8
    expanded_origin = (
        local_origin[0] + negative_expansion,
        local_origin[1] + negative_expansion,
    )
    expanded_size = (
        binary64_fma(radius, 5.6, local_size[0]),
        binary64_fma(radius, 5.6, local_size[1]),
    )
    expanded_far = add_pair(expanded_origin, expanded_size)
    union_origin = (
        min(expanded_origin[0], shifted_shadow_origin[0]),
        min(expanded_origin[1], shifted_shadow_origin[1]),
    )
    union_far = (
        max(expanded_far[0], shadow_far[0]),
        max(expanded_far[1], shadow_far[1]),
    )
    union_size = subtract_pair(union_far, union_origin)

    exact_pair(
        shadow_origin,
        state_pair(states, "glassBackgroundDOD", 0x104, "v5"),
        "shadow expanded origin",
    )
    exact_pair(
        union_origin,
        state_pair(states, "glassBackgroundDOD", 0x1F4, "v0"),
        "shadow/filter union origin",
    )
    exact_pair(
        union_size,
        state_pair(states, "glassBackgroundDOD", 0x1F4, "v5"),
        "shadow/filter union size",
    )

    source_dod = (
        *state_pair(states, "glassBackgroundDOD", 0x1F8, "v0"),
        *state_pair(states, "glassBackgroundDOD", 0x1FC, "v1"),
    )
    backdrop_entry, backdrop_return = backdrop_rectangles(backdrop)
    if f64_hex(source_dod) != f64_hex(backdrop_entry):
        raise ValueError("raw source DOD differs from BackdropLayer input")

    backdrop_origin = backdrop_return[0:2]
    backdrop_size = backdrop_return[2:4]
    backdrop_far = add_pair(backdrop_origin, backdrop_size)
    intersection_origin = (
        max(union_origin[0], backdrop_origin[0]),
        max(union_origin[1], backdrop_origin[1]),
    )
    intersection_far = (
        min(union_far[0], backdrop_far[0]),
        min(union_far[1], backdrop_far[1]),
    )
    intersection_size = subtract_pair(intersection_far, intersection_origin)
    exact_pair(
        intersection_origin,
        state_pair(states, "glassBackgroundDOD", 0x3F0, "v0"),
        "intersection origin",
    )
    exact_pair(
        intersection_size,
        state_pair(states, "glassBackgroundDOD", 0x3F0, "v1"),
        "intersection size",
    )

    world_y = -(intersection_origin[1] + intersection_size[1])
    replay = (
        intersection_origin[0] + transform_x,
        world_y + transform_y,
        intersection_size[0],
        intersection_size[1],
    )
    if f64_hex(replay) != f64_hex(filter_return):
        raise ValueError("complete small-geometry Filter replay differs")

    omitted_shadow_far = (
        local_origin[0] + local_size[0] + shadow_offset[0],
        local_origin[1] + local_size[1] + shadow_offset[1],
    )
    omitted_union_far = (
        max(expanded_far[0], omitted_shadow_far[0]),
        max(expanded_far[1], omitted_shadow_far[1]),
    )
    omitted_intersection_far = (
        min(omitted_union_far[0], backdrop_far[0]),
        min(omitted_union_far[1], backdrop_far[1]),
    )
    omitted_size = subtract_pair(omitted_intersection_far, intersection_origin)
    omitted_world_y = -(intersection_origin[1] + omitted_size[1])
    omitted_replay = (
        intersection_origin[0] + transform_x,
        omitted_world_y + transform_y,
        omitted_size[0],
        omitted_size[1],
    )
    omitted_delta = tuple(
        candidate - observed
        for candidate, observed in zip(omitted_replay, filter_return, strict=True)
    )
    far_edge_advantage = shadow_far[1] - expanded_far[1]
    if omitted_delta != (0.0, far_edge_advantage, 0.0, -far_edge_advantage):
        raise ValueError("isolated shadow residual differs")

    timeline = mapping(
        json.loads(timeline_path.read_text(encoding="utf-8")), "timeline"
    )
    records = sequence(
        mapping(timeline.get("dynamicBackgroundUniforms"), "dynamic uniforms").get(
            "records"
        ),
        "timeline records",
    )
    sample = mapping(records[1], "sample-two timeline record")
    inputs = mapping(
        mapping(sample.get("filter"), "sample-two Filter").get("inputValues"),
        "sample-two Filter inputs",
    )
    expected_timeline_values = {
        "inputShadowRadius": shadow_radius,
        "inputShadowOpacity": shadow_opacity,
        "inputBlurRadius": blur_radius,
    }
    for key, expected in expected_timeline_values.items():
        if finite(inputs.get(key), key) != expected:
            raise ValueError(f"{key} differs from live helper input")
    if 0.5 * finite(inputs.get("inputBleedBlurRadius"), "input bleed blur") != bleed_radius:
        raise ValueError("regular bleed helper return differs")

    filter_validation = mapping(local_validation.get("filter"), "Filter validation")
    sdf_validation = mapping(local_validation.get("sdf"), "SDF validation")
    if (
        filter_validation.get("codeSHA256") != FILTER_CODE_SHA256
        or sdf_validation.get("discoveredCodeSHA256") != SDF_CODE_SHA256
    ):
        raise ValueError("Filter/SDF code identity differs")

    return {
        "prepareLayerFilterSDFSmallGeometryAnalysisSchemaVersion": (
            ANALYSIS_SCHEMA_VERSION
        ),
        "classification": (
            "retrospective exact decode of the prospectively selected output-blind "
            "circle-127 sample-two FilterOp/SDFOp trace; every retained arithmetic "
            "checkpoint and the final producer are compared bit for bit, while "
            "general geometry transfer and parity authority remain closed"
        ),
        "run": {
            "runID": 31084256909,
            "jobID": 92559896529,
            "headSHA": "4cd04d24ca6e8cc85d18cdb2f25551677e3905a0",
            "conclusion": "success",
            "artifactID": 8960916532,
            "artifactName": (
                "liquid-glass-prepare-layer-filter-sdf-small-geometry-31084256909"
            ),
            "artifactSizeBytes": 88842184,
            "artifactDigest": (
                "sha256:28beddbb413117add739c3561b5f6ff4f4721f3ce16d7393cde58871e5bff193"
            ),
        },
        "inputs": {
            "trace": str(trace_path),
            "traceSHA256": observed_hashes["trace"],
            "timeline": str(timeline_path),
            "timelineSHA256": observed_hashes["timeline"],
            "inventory": str(inventory_path),
            "inventorySHA256": sha256(inventory_path),
            "validation": str(validation_path),
            "validationSHA256": observed_hashes["validation"],
            "localValidationPassed": True,
            "localValidationSemanticDifferenceFromCI": False,
            "localValidationPathFieldsDifferFromCI": True,
        },
        "sdf": {
            "codeSHA256": SDF_CODE_SHA256,
            "instructionStatesSHA256": SDF_STATE_SHA256,
            "parametersF32": list(sdf_parameters),
            "parametersHex": struct.pack("<4f", *sdf_parameters).hex(),
            "entryF64": list(sdf_entry),
            "entryHex": f64_hex(sdf_entry),
            "replayF64": list(sdf_replay),
            "replayHex": f64_hex(sdf_replay),
            "returnF64": list(sdf_return),
            "returnHex": f64_hex(sdf_return),
            "replayExact": True,
        },
        "filter": {
            "codeSHA256": FILTER_CODE_SHA256,
            "instructionStatesSHA256": FILTER_STATE_SHA256,
            "entryF64": list(filter_entry),
            "entryHex": f64_hex(filter_entry),
            "carrierTranslationF64": list(carrier),
            "localOriginF64": list(local_origin),
            "localSizeF64": list(local_size),
            "blurRadiusF64": blur_radius,
            "bleedHelperReturnF64": bleed_radius,
            "filterRadiusF64": radius,
            "filterExpansionF64": filter_expansion,
            "expandedOriginF64": list(expanded_origin),
            "expandedSizeF64": list(expanded_size),
            "expandedFarF64": list(expanded_far),
            "shadowOpacityF64": shadow_opacity,
            "gaussianExpansionFactorF64": gaussian_factor,
            "shadowRadiusF64": shadow_radius,
            "shadowExpansionF64": shadow_expansion,
            "shadowOffsetF64": list(shadow_offset),
            "shadowOriginBeforeOffsetF64": list(shadow_origin),
            "shadowSizeF64": list(shadow_size),
            "shadowFarAfterOffsetF64": list(shadow_far),
            "unionOriginF64": list(union_origin),
            "unionSizeF64": list(union_size),
            "unionFarF64": list(union_far),
            "rawSourceDODF64": list(source_dod),
            "rawSourceDODHex": f64_hex(source_dod),
            "backdropInputF64": list(backdrop_entry),
            "backdropInputHex": f64_hex(backdrop_entry),
            "backdropReturnedClipF64": list(backdrop_return),
            "backdropReturnedClipHex": f64_hex(backdrop_return),
            "intersectionOriginF64": list(intersection_origin),
            "intersectionSizeF64": list(intersection_size),
            "replayF64": list(replay),
            "replayHex": f64_hex(replay),
            "returnF64": list(filter_return),
            "returnHex": f64_hex(filter_return),
            "replayExact": True,
        },
        "isolatedFormerResidual": {
            "cause": (
                "the earlier replay omitted Gaussian shadow expansion; after the "
                "[0,8] offset, the expanded shadow far-Y exceeds the main Filter "
                "far-Y and therefore wins the endpoint union"
            ),
            "shadowFarYF64": shadow_far[1],
            "mainFilterFarYF64": expanded_far[1],
            "shadowFarEdgeAdvantageF64": far_edge_advantage,
            "identity": (
                "8 + gaussianExpansionFactor * inputShadowRadius "
                "- 2.8 * max(2 * inputBlurRadius, bleedHelperReturn)"
            ),
            "replayWithoutShadowExpansionF64": list(omitted_replay),
            "replayWithoutShadowExpansionHex": f64_hex(omitted_replay),
            "deltaWithoutShadowExpansionF64": list(omitted_delta),
            "xAndWidthWereAlreadyExact": True,
            "yAndHeightAreNowExact": True,
        },
        "separation": {
            "rawGlassSourceDODF64": list(source_dod),
            "backdropReturnedClipF64": list(backdrop_return),
            "rawSourceAndRecursiveClipAreDistinct": True,
            "constant280SourceDODHypothesisFalsified": True,
            "observedEdgeExpansionF64": 83.0,
            "generalEdgeAllocationLawEstablished": False,
        },
        "conclusion": {
            "selectedSmallGeometrySDFReplayExact": True,
            "selectedSmallGeometryFilterReplayExact": True,
            "formerVerticalResidualExplainedExactly": True,
            "gaussianHelperGeneralLawDecoded": False,
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
            "target": (
                "open the complete 200-byte gaussian_expansion_factor and 80-byte "
                "BackdropLayer::get_bounds functions, freeze their exact general "
                "semantics, then rerun a preregistered unseen-geometry/profile matrix"
            ),
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
