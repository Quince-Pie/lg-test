#!/usr/bin/env python3
"""Validate public filter -> provider -> Group.margin -> render-margin composition.

The predecessor writer gate used a compact shadow/bleed expression discovered
from opened outputs.  Later experiments authenticated the actual DesignLibrary
provider, its complete finite branch universe, the live public/provider field
mapping, and the Parameters-to-provider constructor.  This successor freezes
that recovered producer law before observing four new material/profile/geometry
configurations and retains the predecessor's exact setter/copy/get_bounds join.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any

import validate_backdrop_margin_writer_execution as base
import validate_backdrop_margin_writer_execution_retry as retry


VALIDATION_SCHEMA_VERSION = 1
PREREGISTRATION_SCHEMA_VERSION = 2
PREREGISTRATION_NAME = (
    "backdrop_margin_writer_provider_composition_local_macos_26_6_1_"
    "preregistration.json"
)
PROVIDER_LAW = (
    "max(abs(inputShadowOffset.x), abs(inputShadowOffset.y)) "
    "+ abs(inputShadowAmount)"
)
CASES = {
    ("clear", "light", "materialize", "circle-451-center"),
    ("clear", "dark", "materialize", "circle-459-center"),
    ("regular", "light", "materialize", "circle-467-center"),
    ("regular", "dark", "materialize", "circle-475-center"),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_preregistration(
    value: Any,
    material: str,
    appearance: str,
    direction: str,
    geometry: str,
) -> dict[str, Any]:
    preregistration = base.mapping(value, "provider-composition preregistration")
    require(
        preregistration.get(
            "backdropMarginWriterProviderCompositionPreregistrationSchemaVersion"
        )
        == PREREGISTRATION_SCHEMA_VERSION,
        "provider-composition preregistration schema differs",
    )

    candidate = base.mapping(
        preregistration.get("frozenCandidate"), "frozen provider composition"
    )
    require(
        candidate.get("perRecordProviderReturn") == PROVIDER_LAW,
        "frozen provider law differs",
    )
    require(
        candidate.get("regularGroupMargin")
        == "maximum over all 32 retained per-record provider returns",
        "frozen regular Group.margin law differs",
    )
    require(
        candidate.get("clearGroupMargin") == "exact binary64 positive zero",
        "frozen clear Group.margin law differs",
    )
    require(
        candidate.get("modelStorage") == "binary64"
        and candidate.get("renderStorage")
        == "round-to-nearest-even binary32"
        and candidate.get("capturedTargetValueUsedToChooseCandidate") is False
        and candidate.get("cropOrImageUsedToChooseCandidate") is False,
        "frozen storage or output-blind contract differs",
    )

    cases = base.sequence(preregistration.get("prospectiveCases"), "prospective cases")
    identities = {
        (
            case.get("material"),
            case.get("appearance"),
            case.get("direction"),
            case.get("geometry"),
        )
        for case in cases
        if isinstance(case, dict)
    }
    require(identities == CASES and len(cases) == len(CASES), "case matrix differs")
    identity = (material, appearance, direction, geometry)
    require(identity in CASES, "runtime profile is not a frozen case")
    selected = [
        case
        for case in cases
        if isinstance(case, dict)
        and (
            case.get("material"),
            case.get("appearance"),
            case.get("direction"),
            case.get("geometry"),
        )
        == identity
    ]
    require(len(selected) == 1, "runtime profile is not unique")
    case = selected[0]
    for key in (
        "expectedGroupMarginF64",
        "expectedRenderMarginF32",
        "expectedWriterPointers",
        "expectedCrop",
        "expectedImageDigest",
    ):
        require(case.get(key) is None, "prospective Apple output was present at freeze")
    require(
        case.get("exactConfigurationPreviouslyCaptured") is False
        and case.get("appleOutputAvailableAtFreeze") is False,
        "prospective case was not output-blind",
    )

    acceptance = base.mapping(preregistration.get("acceptance"), "acceptance")
    required_acceptance = (
        "requireAllExactCodeGates",
        "requireEveryEventWithinBound",
        "requireAtLeastOneCompleteSetterCopyBoundsChain",
        "requireEveryStructurallyJoinedChainToMatchCandidateBitwise",
        "requireEverySetterToExposeExactAdjacentProducer",
        "requireEveryProducerReturnToEqualSetterInputBitwise",
        "requireExactPublicProviderOperationOrder",
        "requireNoCapturedValueForSelection",
        "zeroTolerance",
    )
    require(
        all(acceptance.get(key) is True for key in required_acceptance),
        "acceptance contract differs",
    )

    root = Path(__file__).resolve().parent.parent
    evidence = base.sequence(preregistration.get("frozenEvidence"), "frozen evidence")
    require(len(evidence) >= 5, "frozen evidence set is incomplete")
    for index, entry_value in enumerate(evidence):
        entry = base.mapping(entry_value, f"frozen evidence {index}")
        path = root / str(entry.get("path"))
        require(path.is_file(), f"frozen evidence is missing: {path}")
        require(sha256(path) == entry.get("sha256"), f"frozen evidence differs: {path}")
    return preregistration


def provider_transition_candidate(
    timeline: dict[str, Any],
    material: str,
    appearance: str,
    direction: str,
    geometry: str,
) -> dict[str, Any]:
    # Reuse the predecessor solely for strict timeline structure/identity checks.
    # Its fitted candidate is discarded without reading any writer output.
    base_candidate = retry._FROZEN_TRANSITION_CANDIDATE(
        timeline, material, appearance, direction, geometry
    )
    dynamic = base.mapping(
        timeline.get("dynamicBackgroundUniforms"), "dynamic background uniforms"
    )
    records = base.sequence(dynamic.get("records"), "dynamic records")
    decoded: list[dict[str, Any]] = []
    for expected_index, value in enumerate(records, 1):
        record = base.mapping(value, f"dynamic record {expected_index}")
        require(record.get("sampleIndex") == expected_index, "sample index differs")
        inputs = base.mapping(
            base.mapping(record.get("filter"), "filter").get("inputValues"),
            "filter input values",
        )
        shadow_amount = base.finite_number(
            inputs.get("inputShadowAmount"), "inputShadowAmount"
        )
        offset_x, offset_y = base.decode_shadow_offset(
            inputs.get("inputShadowOffset"), "inputShadowOffset"
        )

        # Exact selected provider operation order: FABS both axes, FCMP/FCSEL
        # their maximum, FABS the shape term, then one binary64 FADD.
        absolute_x = math.fabs(offset_x)
        absolute_y = math.fabs(offset_y)
        axis = absolute_x if absolute_x >= absolute_y else absolute_y
        shape = math.fabs(shadow_amount)
        provider_return = axis + shape
        require(math.isfinite(provider_return), "provider return is non-finite")
        decoded.append(
            {
                "sampleIndex": expected_index,
                "inputShadowAmountF64": shadow_amount,
                "inputShadowOffsetF64": [offset_x, offset_y],
                "axisF64": axis,
                "shapeF64": shape,
                "providerReturnF64": provider_return,
                "providerReturnF64RawLittleEndianHex": struct.pack(
                    "<d", provider_return
                ).hex(),
            }
        )

    require(len(decoded) == 32, "provider candidate record count differs")
    provider_maximum = max(record["providerReturnF64"] for record in decoded)
    selected_margin = 0.0 if material == "clear" else provider_maximum
    margin_raw = struct.pack("<d", selected_margin)
    render_raw = struct.pack("<f", selected_margin)
    return {
        "recordCount": len(decoded),
        "records": decoded,
        "perRecordProviderLaw": PROVIDER_LAW,
        "providerMaximumF64": provider_maximum,
        "providerMaximumF64RawLittleEndianHex": struct.pack(
            "<d", provider_maximum
        ).hex(),
        "maximumRequiredMarginF64": selected_margin,
        "maximumRequiredMarginF64RawLittleEndianHex": margin_raw.hex(),
        "expectedRenderMarginF32": struct.unpack("<f", render_raw)[0],
        "expectedRenderMarginF32RawLittleEndianHex": render_raw.hex(),
        "selectedMaterialLaw": (
            "clear material stores exact binary64 positive zero"
            if material == "clear"
            else "regular material stores the maximum exact provider return"
        ),
        "predecessorStructuralRecordCount": base_candidate["recordCount"],
        "capturedWriterValueUsedToBuildCandidate": False,
    }


def validate(
    trace_path: Path,
    timeline_path: Path,
    preregistration_path: Path,
    material: str,
    appearance: str,
    direction: str,
    geometry: str,
) -> dict[str, Any]:
    validate_preregistration(
        base.load_json(preregistration_path, "provider-composition preregistration"),
        material,
        appearance,
        direction,
        geometry,
    )

    original_preregistration = base.validate_preregistration
    original_candidate = base.transition_candidate
    original_events = base.validate_events
    base.validate_preregistration = validate_preregistration
    base.transition_candidate = provider_transition_candidate
    base.validate_events = retry.validate_events
    try:
        result = base.validate(
            trace_path,
            timeline_path,
            preregistration_path,
            material,
            appearance,
            direction,
            geometry,
        )
    finally:
        base.validate_preregistration = original_preregistration
        base.transition_candidate = original_candidate
        base.validate_events = original_events

    trace = base.mapping(base.load_json(trace_path, "trace"), "trace")
    events = [
        base.mapping(value, "event")
        for value in base.sequence(trace.get("events"), "events")
    ]
    callers = base.validate_callers(trace)
    provenance = retry.validate_producer_provenance(trace, events, callers)
    candidate = base.mapping(result.get("candidate"), "validated candidate")

    result["backdropMarginWriterProviderCompositionValidationSchemaVersion"] = (
        VALIDATION_SCHEMA_VERSION
    )
    result["classification"] = (
        "prospective output-blind exact public-provider-Group-writer composition "
        "on one frozen direct-M1 profile"
    )
    result["writerExecution"]["producerProvenance"] = provenance
    result["writerExecution"]["publicProviderComposition"] = {
        "perRecordProviderLaw": PROVIDER_LAW,
        "recordCount": candidate["recordCount"],
        "allProviderPredictionsBuiltWithoutWriterValues": True,
        "allStructurallyJoinedWriterChainsMatchBitwise": True,
    }
    result["sealedConclusion"].update(
        {
            "publicProviderGroupWriterCompositionProspectiveBitExactForThisCase": True,
            "adjacentMarginProducerCodeOpened": True,
            "adjacentMarginProducerArithmeticDecoded": True,
            "upstreamAllocationMarginPolicyEstablishedForThisCase": True,
            "fourCaseMatrixPassed": False,
            "generalSelectedRegionPolicyEstablished": False,
            "physicalRetinaColorPixelCompositorTransferPassed": False,
            "independentWalleZeroByteFrameParityPassed": False,
            "productionShaderAuthorized": False,
            "liquidGlassParityEstablished": False,
        }
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("preregistration", type=Path)
    parser.add_argument("--material", required=True, choices=("clear", "regular"))
    parser.add_argument("--appearance", required=True, choices=("light", "dark"))
    parser.add_argument("--direction", required=True, choices=("materialize",))
    parser.add_argument("--geometry", required=True)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate(
        arguments.trace,
        arguments.timeline,
        arguments.preregistration,
        arguments.material,
        arguments.appearance,
        arguments.direction,
        arguments.geometry,
    )
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
