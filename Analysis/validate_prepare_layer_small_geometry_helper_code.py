#!/usr/bin/env python3
"""Validate the output-blind small-geometry helper code opening."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import validate_prepare_layer_filter_sdf_small_geometry as frozen


VALIDATION_SCHEMA_VERSION = 1
EXTENSION_SCHEMA_VERSION = 1
EXPECTED_SPECS = [
    {
        "name": "gaussianExpansionFactor",
        "function": "CA::OGL::gaussian_expansion_factor(double)",
        "relativeToPrepareLayer": -96880,
        "symbolByteCount": 200,
        "expectedCodeSHA256": None,
    },
    {
        "name": "backdropGetBounds",
        "function": (
            "CA::Render::BackdropLayer::get_bounds("
            "CA::Render::Layer const*, CA::Rect&, CA::Rect*) const"
        ),
        "relativeToPrepareLayer": 364616,
        "symbolByteCount": 80,
        "expectedCodeSHA256": None,
    },
]
EXPECTED_CONFIGURATION = {
    "material": "regular",
    "appearance": "light",
    "direction": "materialize",
    "geometry": "circle-127-center",
    "selectedSampleIndex": 2,
    "selectedMarkerInterval": 2,
    "selectedQualifiedHelperOrdinal": 14,
    "filterDispatchOrdinal": 4,
    "sdfDispatchOrdinal": 2,
    "helperSpecifications": EXPECTED_SPECS,
    "captureRule": (
        "while stopped at the unchanged structurally selected helper, resolve "
        "each preregistered function by prepare_layer-relative address, exact "
        "function name, and byte count; retain every code byte and static ARM64 "
        "instruction before starting the unchanged Filter/SDF execution trace"
    ),
    "staticMemoryReadsOnly": True,
    "breakpointsAdded": 0,
    "instructionStepsAdded": 0,
    "expectedCodeSHA256": None,
    "cropValuesUsedForSelection": False,
    "outputValuesUsedForSelection": False,
    "filterAndSDFCaptureChanged": False,
}


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} is not an object")
    return value


def sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{label} is not an array")
    return value


def integer(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} is not an integer")
    return value


def payload(value: Any, byte_count: int, label: str) -> bytes:
    if not isinstance(value, str):
        raise ValueError(f"{label} is not a string")
    try:
        result = bytes.fromhex(value)
    except ValueError as error:
        raise ValueError(f"{label} is not hexadecimal") from error
    if len(result) != byte_count:
        raise ValueError(f"{label} byte count differs")
    return result


def validate_target(
    raw: Any,
    spec: Mapping[str, Any],
    prepare_start: int,
    prepare_module: Mapping[str, Any],
) -> tuple[dict[str, Any], bytes]:
    target = mapping(raw, f"{spec['name']} target")
    byte_count = integer(spec.get("symbolByteCount"), "helper symbol byte count")
    code = payload(target.get("hex"), byte_count, f"{spec['name']} code")
    digest = hashlib.sha256(code).hexdigest()
    start = prepare_start + integer(
        spec.get("relativeToPrepareLayer"), "helper relative address"
    )
    module = mapping(target.get("module"), f"{spec['name']} module")
    instructions = list(sequence(target.get("instructions"), "helper instructions"))
    if (
        target.get("name") != spec.get("name")
        or target.get("function") != spec.get("function")
        or target.get("relativeToPrepareLayer") != spec.get("relativeToPrepareLayer")
        or target.get("symbolStart") != start
        or target.get("symbolEnd") != start + byte_count
        or target.get("symbolByteCount") != byte_count
        or target.get("expectedSHA256") is not None
        or target.get("observedSHA256") != digest
        or target.get("instructionCount") != byte_count // 4
        or len(instructions) != byte_count // 4
        or target.get("cropValuesUsedForSelection") is not False
        or target.get("outputValuesUsedForSelection") is not False
        or module.get("valid") is not True
        or module.get("path") != prepare_module.get("path")
        or module.get("loadAddress") != prepare_module.get("loadAddress")
    ):
        raise ValueError(f"{spec['name']} target identity differs")

    for index, raw_instruction in enumerate(instructions):
        instruction = mapping(raw_instruction, f"{spec['name']} instruction {index}")
        offset = index * 4
        if (
            instruction.get("pc") != start + offset
            or instruction.get("offset") != offset
            or instruction.get("rawLittleEndianHex")
            != code[offset : offset + 4].hex()
            or not isinstance(instruction.get("mnemonic"), str)
            or not instruction.get("mnemonic")
            or not isinstance(instruction.get("operands"), str)
            or not isinstance(instruction.get("comment"), str)
        ):
            raise ValueError(f"{spec['name']} static instruction differs")
    canonical = json.dumps(
        instructions, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return (
        {
            "name": spec["name"],
            "function": spec["function"],
            "relativeToPrepareLayer": spec["relativeToPrepareLayer"],
            "symbolByteCount": byte_count,
            "codeSHA256": digest,
            "instructionCount": len(instructions),
            "instructionsSHA256": hashlib.sha256(canonical).hexdigest(),
            "codeHashAcceptedBeforeCapture": False,
        },
        code,
    )


def validate(
    trace_path: Path, timeline_path: Path, inventory_path: Path
) -> dict[str, Any]:
    inherited = frozen.validate(trace_path, timeline_path, inventory_path)
    if inherited.get("conclusion") != "success":
        raise ValueError("inherited small-geometry diagnostic differs")

    trace = mapping(json.loads(trace_path.read_text(encoding="utf-8")), "trace")
    prepare = mapping(trace.get("prepareLayer"), "prepare layer")
    prepare_start = integer(prepare.get("symbolStart"), "prepare layer start")
    prepare_module = mapping(prepare.get("module"), "prepare layer module")
    extension = mapping(
        trace.get("prepareLayerSmallGeometryHelperCodeExtension"),
        "helper-code extension",
    )
    raw_targets = list(sequence(extension.get("targets"), "helper-code targets"))
    if (
        extension.get("prepareLayerSmallGeometryHelperCodeExtensionSchemaVersion")
        != EXTENSION_SCHEMA_VERSION
        or extension.get("configuration") != EXPECTED_CONFIGURATION
        or extension.get("status") != "finalized"
        or extension.get("statusBeforeFinalization") != "static-code-capture-closed"
        or sequence(extension.get("failures"), "helper-code failures")
        or extension.get("finalFailureCount") != 0
        or extension.get("finalTargetCount") != len(EXPECTED_SPECS)
        or extension.get("finalInstructionCount") != 70
        or len(raw_targets) != len(EXPECTED_SPECS)
    ):
        raise ValueError("helper-code extension identity differs")

    targets: list[dict[str, Any]] = []
    for raw, spec in zip(raw_targets, EXPECTED_SPECS, strict=True):
        target, _code = validate_target(raw, spec, prepare_start, prepare_module)
        targets.append(target)

    filter_extension = mapping(
        trace.get("prepareLayerFilterMapBoundsExtension"), "Filter extension"
    )
    boundaries = [
        mapping(raw, "opaque boundary")
        for raw in sequence(
            filter_extension.get("opaqueCalleeBoundaries"), "opaque boundaries"
        )
    ]
    for target in targets:
        matches = [
            boundary
            for boundary in boundaries
            if mapping(boundary.get("entryFrame"), "boundary entry").get("function")
            == target["function"]
        ]
        if len(matches) != 1:
            raise ValueError(f"{target['name']} execution boundary is not unique")
        entry = mapping(matches[0].get("entryFrame"), "helper boundary entry")
        if (
            entry.get("symbolStart") != prepare_start + target["relativeToPrepareLayer"]
            or entry.get("symbolEnd")
            != entry.get("symbolStart") + target["symbolByteCount"]
        ):
            raise ValueError(f"{target['name']} code/execution join differs")

    inherited_sealed = mapping(
        inherited.get("sealedConclusion"), "inherited sealed conclusion"
    )
    return {
        "prepareLayerSmallGeometryHelperCodeValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "classification": (
            "prospective output-blind static code opening of the exact Gaussian "
            "shadow-expansion and backdrop-bounds helpers, joined by symbol identity "
            "to their independently retained execution boundaries"
        ),
        "conclusion": "success",
        "inputs": inherited["inputs"],
        "profile": inherited["profile"],
        "selection": {
            **inherited["selection"],
            "helperCodeHashesAcceptedBeforeCapture": False,
            "staticMemoryReadsOnly": True,
            "breakpointsAdded": 0,
            "instructionStepsAdded": 0,
        },
        "targets": targets,
        "sealedConclusion": {
            **inherited_sealed,
            "smallGeometryHelperCodeOpeningPassed": True,
            "gaussianExpansionGeneralSemanticsDecoded": False,
            "backdropAllocationGeneralSemanticsDecoded": False,
            "regularGeometryTransferPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate(arguments.trace, arguments.timeline, arguments.inventory)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
