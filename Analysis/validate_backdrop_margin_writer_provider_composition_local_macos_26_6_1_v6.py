#!/usr/bin/env python3
"""Validate public filter -> provider -> Group.margin -> render-margin composition.

The first provider-composition transfer cleanly falsified a provider-only
Group.margin law: the opened regular/light target was the maximum public bleed
amount, bit for bit, rather than the smaller maximum provider return.  This
successor freezes the corrected ``max(bleed, provider)`` contribution before
opening the remaining regular holdout.  It retains the authenticated provider
operation order and the exact setter/copy/get_bounds object join.
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


VALIDATION_SCHEMA_VERSION = 2
PREREGISTRATION_SCHEMA_VERSION = 6
PREREGISTRATION_NAME = (
    "backdrop_margin_writer_provider_composition_local_macos_26_6_1_"
    "v6_preregistration.json"
)
PROVIDER_LAW = (
    "max(abs(inputShadowOffset.x), abs(inputShadowOffset.y)) "
    "+ abs(inputShadowAmount)"
)
REGULAR_CONTRIBUTION_LAW = (
    "max(inputBleedAmount, authenticated per-record provider return)"
)
CASES = {
    ("clear", "light", "materialize", "circle-451-center"),
    ("clear", "dark", "materialize", "circle-459-center"),
    ("regular", "light", "materialize", "circle-467-center"),
    ("regular", "dark", "materialize", "circle-475-center"),
}
LIVE_QUARTZCORE_UUID = "F1BA3189-E95A-3ECA-B59A-5A6872754484"
LIVE_SWIFTUICORE_UUID = "99606D45-C40A-3C69-AE51-5F0C4E32E531"
LIVE_COPY_CODE_SHA256 = (
    "5bdf866c13bfb00d9becada24ff9876f84515fa36acb4ee274785d5176593a1e"
)
LIVE_SETTER_CODE_SHA256 = (
    "2421048e418c6cdcc7622dd65f881e514e0852687f7920e6c4bdaf75a301f6dd"
)
LIVE_CALLER_CODE_SHA256 = (
    "d60a0510382f913b937ceb2c20111c4dcf1b4dd9d6d49388c2fe5c4d2683168c"
)
CALIBRATION_CASE = (
    "regular",
    "light",
    "materialize",
    "circle-467-center",
)


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
        candidate.get("perRecordRegularGroupContribution")
        == REGULAR_CONTRIBUTION_LAW,
        "frozen regular contribution law differs",
    )
    require(
        candidate.get("regularGroupMargin")
        == "maximum over all 32 retained per-record regular group contributions",
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
        and candidate.get("capturedTargetValueUsedToChooseCandidate") is True
        and candidate.get("prospectiveFreshCaseOutputUsedToChooseCandidate") is False
        and candidate.get("cropOrImageUsedToChooseCandidate") is False,
        "frozen storage or calibration contract differs",
    )

    cases = base.sequence(preregistration.get("caseMatrix"), "case matrix")
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
    require(
        case.get("expectedWriterPointers") is None
        and case.get("expectedCrop") is None
        and case.get("expectedImageDigest") is None,
        "case contains forbidden pointer, crop, or image expectation",
    )
    if identity == CALIBRATION_CASE:
        require(
            case.get("role") == "calibration-falsification"
            and case.get("exactConfigurationPreviouslyCaptured") is True
            and case.get("appleInputAvailableAtFreeze") is True
            and case.get("appleTargetWriterOutputAvailableAtFreeze") is True
            and case.get("expectedGroupMarginF64") == 163.45
            and case.get("expectedGroupMarginF64RawLittleEndianHex")
            == "66666666666e6440"
            and case.get("expectedRenderMarginF32") == 163.4499969482422
            and case.get("expectedRenderMarginF32RawLittleEndianHex") == "33732343",
            "opened calibration case differs",
        )
    else:
        require(
            case.get("role") == "prospective-holdout"
            and case.get("exactConfigurationPreviouslyCaptured") is False
            and case.get("appleInputAvailableAtFreeze") is False
            and case.get("appleTargetWriterOutputAvailableAtFreeze") is False
            and case.get("expectedGroupMarginF64") is None
            and case.get("expectedGroupMarginF64RawLittleEndianHex") is None
            and case.get("expectedRenderMarginF32") is None
            and case.get("expectedRenderMarginF32RawLittleEndianHex") is None,
            "prospective holdout was not sealed unseen",
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
        "requireExactOpenedSwiftUICoreCallerIdentity",
        "requireNoCapturedValueForCaptureSelection",
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
        bleed = base.finite_number(
            inputs.get("inputBleedAmount"), "inputBleedAmount"
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
        regular_contribution = (
            bleed if bleed >= provider_return else provider_return
        )
        decoded.append(
            {
                "sampleIndex": expected_index,
                "inputBleedAmountF64": bleed,
                "inputShadowAmountF64": shadow_amount,
                "inputShadowOffsetF64": [offset_x, offset_y],
                "axisF64": axis,
                "shapeF64": shape,
                "providerReturnF64": provider_return,
                "providerReturnF64RawLittleEndianHex": struct.pack(
                    "<d", provider_return
                ).hex(),
                "regularGroupContributionF64": regular_contribution,
                "regularGroupContributionF64RawLittleEndianHex": struct.pack(
                    "<d", regular_contribution
                ).hex(),
            }
        )

    require(len(decoded) == 32, "provider candidate record count differs")
    provider_maximum = max(record["providerReturnF64"] for record in decoded)
    bleed_maximum = max(record["inputBleedAmountF64"] for record in decoded)
    regular_maximum = max(
        record["regularGroupContributionF64"] for record in decoded
    )
    selected_margin = 0.0 if material == "clear" else regular_maximum
    margin_raw = struct.pack("<d", selected_margin)
    render_raw = struct.pack("<f", selected_margin)
    return {
        "recordCount": len(decoded),
        "records": decoded,
        "perRecordProviderLaw": PROVIDER_LAW,
        "perRecordRegularGroupContributionLaw": REGULAR_CONTRIBUTION_LAW,
        "providerMaximumF64": provider_maximum,
        "providerMaximumF64RawLittleEndianHex": struct.pack(
            "<d", provider_maximum
        ).hex(),
        "bleedMaximumF64": bleed_maximum,
        "bleedMaximumF64RawLittleEndianHex": struct.pack(
            "<d", bleed_maximum
        ).hex(),
        "regularGroupContributionMaximumF64": regular_maximum,
        "regularGroupContributionMaximumF64RawLittleEndianHex": struct.pack(
            "<d", regular_maximum
        ).hex(),
        "maximumRequiredMarginF64": selected_margin,
        "maximumRequiredMarginF64RawLittleEndianHex": margin_raw.hex(),
        "expectedRenderMarginF32": struct.unpack("<f", render_raw)[0],
        "expectedRenderMarginF32RawLittleEndianHex": render_raw.hex(),
        "selectedMaterialLaw": (
            "clear material stores exact binary64 positive zero"
            if material == "clear"
            else (
                "regular material stores the maximum exact max(bleed, provider) "
                "contribution"
            )
        ),
        "predecessorStructuralRecordCount": base_candidate["recordCount"],
        "candidateLawCalibratedFromOpenedWriterTarget": True,
        "capturedWriterValueReadDuringCandidateEvaluation": False,
        "prospectiveFreshCaseOutputUsedToBuildCandidate": False,
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

    original_quartzcore_uuid = base.QUARTZCORE_UUID
    original_copy_sha256 = base.CODE_GATES["copy"]["sha256"]
    original_setter_sha256 = base.CODE_GATES["setter"]["sha256"]
    original_swiftuicore_uuid = retry.SWIFTUICORE_UUID
    original_caller_sha256 = retry.CALLER_CODE_SHA256
    original_preregistration = base.validate_preregistration
    original_candidate = base.transition_candidate
    original_events = base.validate_events
    base.QUARTZCORE_UUID = LIVE_QUARTZCORE_UUID
    base.CODE_GATES["copy"]["sha256"] = LIVE_COPY_CODE_SHA256
    base.CODE_GATES["setter"]["sha256"] = LIVE_SETTER_CODE_SHA256
    retry.SWIFTUICORE_UUID = LIVE_SWIFTUICORE_UUID
    retry.CALLER_CODE_SHA256 = LIVE_CALLER_CODE_SHA256
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
        base.QUARTZCORE_UUID = original_quartzcore_uuid
        base.CODE_GATES["copy"]["sha256"] = original_copy_sha256
        base.CODE_GATES["setter"]["sha256"] = original_setter_sha256
        retry.SWIFTUICORE_UUID = original_swiftuicore_uuid
        retry.CALLER_CODE_SHA256 = original_caller_sha256
        base.validate_preregistration = original_preregistration
        base.transition_candidate = original_candidate
        base.validate_events = original_events

    trace = base.mapping(base.load_json(trace_path, "trace"), "trace")
    events = [
        base.mapping(value, "event")
        for value in base.sequence(trace.get("events"), "events")
    ]
    callers = base.validate_callers(trace)
    retry.SWIFTUICORE_UUID = LIVE_SWIFTUICORE_UUID
    retry.CALLER_CODE_SHA256 = LIVE_CALLER_CODE_SHA256
    try:
        provenance = retry.validate_producer_provenance(trace, events, callers)
    finally:
        retry.SWIFTUICORE_UUID = original_swiftuicore_uuid
        retry.CALLER_CODE_SHA256 = original_caller_sha256
    candidate = base.mapping(result.get("candidate"), "validated candidate")
    identity = (material, appearance, direction, geometry)
    case_role = (
        "calibration-falsification"
        if identity == CALIBRATION_CASE
        else "prospective-holdout"
    )

    result["backdropMarginWriterProviderCompositionValidationSchemaVersion"] = (
        VALIDATION_SCHEMA_VERSION
    )
    result["classification"] = (
        "exact public-provider-Group-writer composition on one frozen direct-M1 "
        f"{case_role} profile"
    )
    result["profile"]["caseRole"] = case_role
    result["writerExecution"]["producerProvenance"] = provenance
    result["writerExecution"]["publicProviderComposition"] = {
        "perRecordProviderLaw": PROVIDER_LAW,
        "perRecordRegularGroupContributionLaw": REGULAR_CONTRIBUTION_LAW,
        "recordCount": candidate["recordCount"],
        "candidateLawCalibratedFromOpenedWriterTarget": True,
        "candidateEvaluatedWithoutReadingCurrentWriterValues": True,
        "prospectiveFreshCaseOutputUsedToChooseCandidate": False,
        "allStructurallyJoinedWriterChainsMatchBitwise": True,
    }
    result["sealedConclusion"].update(
        {
            "publicProviderGroupWriterCompositionBitExactForThisCase": True,
            "publicProviderGroupWriterCompositionProspectiveBitExactForThisCase": (
                case_role == "prospective-holdout"
            ),
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
