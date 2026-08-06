#!/usr/bin/env python3
"""Validate the fresh helper trace selected by the output-blind inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import analyze_prepare_layer_crop_union_operand_matrix as crop_analysis
import validate_prepare_layer_crop_transfer as crop_validator
import validate_prepare_layer_mask_instruction_trace as trace_validator
import validate_prepare_layer_mask_instruction_inventory as inventory_validator


VALIDATION_SCHEMA_VERSION = 1


def load_inventory(path: Path) -> tuple[dict[str, Any], str, int]:
    payload = path.read_bytes()
    document = json.loads(payload.decode("utf-8"))
    selection = document.get("structuralSelection") or {}
    helper = document.get("helper") or {}
    sealed = document.get("sealedConclusion") or {}
    ordinal = selection.get("sample2TargetQualifiedOrdinal")
    if (
        document.get("prepareLayerMaskInstructionInventoryValidationSchemaVersion")
        != inventory_validator.VALIDATION_SCHEMA_VERSION
        or document.get("conclusion") != "success"
        or helper.get("codeSHA256")
        != inventory_validator.KNOWN_HELPER_CODE_SHA256
        or selection.get("sampleIndex") != 2
        or not isinstance(ordinal, int)
        or not 1 <= ordinal <= trace_validator.MAXIMUM_QUALIFIED_HELPER_ENTRY_COUNT
        or selection.get("cropOrOutputValuesUsedForSelection") is not False
        or sealed.get("allHelperEntriesRetainedWithoutSelection") is not True
        or sealed.get("sample2ProducerRoleMappedByLastPriorHelper") is not True
        or sealed.get("cropOrOutputValuesUsedForSelection") is not False
        or sealed.get("exactHelperSemanticsDecoded") is not False
        or sealed.get("productionShaderAuthorized") is not False
    ):
        raise ValueError("prepare_layer_mask inventory validation differs")
    return document, hashlib.sha256(payload).hexdigest(), ordinal


def selected_configuration(ordinal: int) -> dict[str, Any]:
    result = dict(trace_validator.EXPECTED_CONFIGURATION)
    result["targetQualifiedOrdinal"] = ordinal
    result["entrySelectionRule"] = inventory_validator.selection_rule(ordinal)
    return result


def validate(
    trace_path: Path,
    timeline_path: Path,
    inventory_path: Path,
    expected_geometry: str = trace_validator.EXPECTED_GEOMETRY,
) -> dict[str, Any]:
    inventory, inventory_sha, ordinal = load_inventory(inventory_path)
    original_ordinal = trace_validator.TARGET_QUALIFIED_ORDINAL
    original_configuration = trace_validator.EXPECTED_CONFIGURATION
    trace_validator.TARGET_QUALIFIED_ORDINAL = ordinal
    trace_validator.EXPECTED_CONFIGURATION = selected_configuration(ordinal)
    try:
        result = trace_validator.validate(
            trace_path, timeline_path, expected_geometry
        )
    finally:
        trace_validator.TARGET_QUALIFIED_ORDINAL = original_ordinal
        trace_validator.EXPECTED_CONFIGURATION = original_configuration

    trace = trace_validator.mapping(
        crop_validator.load_json(trace_path, "trace"), "trace"
    )
    extension = trace_validator.mapping(
        trace.get("prepareLayerMaskInstructionExtension"), "helper extension"
    )
    transport = trace_validator.mapping(
        extension.get("prepareLayerMaskInventoryCalibrationTransport"),
        "selected transport",
    )
    source = trace_validator.mapping(
        transport.get("inventoryValidationSource"), "inventory source"
    )
    inventory_inputs = inventory.get("inputs") or {}
    if (
        transport.get("prepareLayerMaskInventoryCalibrationTransportSchemaVersion")
        != inventory_validator.TRANSPORT_SCHEMA_VERSION
        or transport.get("mode") != "selected"
        or transport.get("targetQualifiedOrdinal") != ordinal
        or transport.get("inventorySentinelOrdinal")
        != inventory_validator.INVENTORY_SENTINEL_ORDINAL
        or transport.get("knownHelperCodeSHA256")
        != inventory_validator.KNOWN_HELPER_CODE_SHA256
        or source.get("fileName") != inventory_path.name
        or source.get("sha256") != inventory_sha
        or source.get("inventoryTraceSHA256")
        != inventory_inputs.get("traceSHA256")
        or source.get("inventoryTimelineSHA256")
        != inventory_inputs.get("timelineSHA256")
        or transport.get("cropOrOutputValuesReadByTransport") is not False
        or transport.get("newBreakpointAddedByTransport") is not False
        or transport.get("captureByteRangeChangedByTransport") is not False
        or transport.get("steppingRuleChangedByTransport") is not False
    ):
        raise ValueError("selected calibration transport differs")
    selected_trace_sha = crop_analysis.sha256_file(trace_path)
    if selected_trace_sha == inventory_inputs.get("traceSHA256"):
        raise ValueError("selected trace is not a fresh capture")
    helper = result["helper"]
    if (
        helper.get("codeSHA256")
        != inventory_validator.KNOWN_HELPER_CODE_SHA256
        or helper.get("selectedMarkerInterval") != 2
        or helper.get("selectedQualifiedOrdinal") != ordinal
    ):
        raise ValueError("selected helper identity differs")
    result[
        "prepareLayerMaskInventorySelectedTraceValidationSchemaVersion"
    ] = VALIDATION_SCHEMA_VERSION
    result["classification"] = (
        "fresh prepare_layer_mask helper trace selected only by the complete "
        "output-blind inventory's last-prior caller-role/depth mapping to the "
        "independent structural producer store"
    )
    result["inventoryCalibration"] = {
        "validation": str(inventory_path),
        "validationSHA256": inventory_sha,
        "traceSHA256": inventory_inputs.get("traceSHA256"),
        "timelineSHA256": inventory_inputs.get("timelineSHA256"),
        "sample2TargetQualifiedOrdinal": ordinal,
        "sample2TargetHelperRecordIndex": (
            inventory.get("structuralSelection") or {}
        ).get("sample2TargetHelperRecordIndex"),
        "cropOrOutputValuesUsedForSelection": False,
        "selectedCaptureIsFreshProcess": True,
    }
    result["helper"]["codeExpectedBeforeSelectedCapture"] = True
    result["sealedConclusion"]["completeOutputBlindInventoryPassed"] = True
    result["sealedConclusion"]["freshStructuralSelectionPassed"] = True
    result["sealedConclusion"]["cropOrOutputValuesUsedForSelection"] = False
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--expected-geometry", default=trace_validator.EXPECTED_GEOMETRY)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = validate(
        arguments.trace,
        arguments.timeline,
        arguments.inventory,
        arguments.expected_geometry,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
