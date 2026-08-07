#!/usr/bin/env python3
"""Transfer flags-produced context Parameters into the retained live timeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Mapping, Sequence, Tuple

import capture_designlibrary_material_context_live_timeline_transfer_local_macos_26_6_1 as base


SCHEMA_VERSION = 1
EXPECTED_TIMELINE_SHA256 = (
    "0a7db5d9416c4c69f19b608de73e9225e7edf8629e112de2be0d07cab1adc711"
)
EXPECTED_FLAGS_BITS = "0x0000000000099183"
CASE_NAMES = tuple("sample_{0:02d}".format(index) for index in range(1, 33))
EXPECTED_CASE_NAMES = tuple(
    "material_context_flags_live:" + name for name in CASE_NAMES
)


def validate_preregistration(
    path: Path,
) -> Tuple[Sequence[Sequence[object]], Sequence[Sequence[object]]]:
    value = base.load_json(path, "flags-live-timeline transfer preregistration")
    if (
        value.get(
            "designLibraryMaterialContextFlagsLiveTimelineTransferPreregistrationSchemaVersion"
        )
        != 1
    ):
        raise base.CaptureError(
            "flags-live-timeline transfer preregistration schema differs"
        )
    predecessors = value.get("predecessors")
    if not isinstance(predecessors, dict) or predecessors != {
        "flagsProducedContextMatrixSHA256": base.EXPECTED_CONTEXT_RESULT_SHA256,
        "publicTimelineSHA256": EXPECTED_TIMELINE_SHA256,
    }:
        raise base.CaptureError("flags-live-timeline predecessors differ")
    boundary = value.get("inputBoundary")
    if (
        not isinstance(boundary, dict)
        or boundary.get("environmentFlagsBits") != EXPECTED_FLAGS_BITS
    ):
        raise base.CaptureError("flags-live-timeline input boundary differs")
    cases = value.get("cases")
    expected_words = value.get("expectedPublicSignatureWords")
    if not isinstance(cases, list) or not isinstance(expected_words, list):
        raise base.CaptureError("flags-live-timeline frozen table is absent")
    if len(cases) != 32 or len(expected_words) != 32:
        raise base.CaptureError("flags-live-timeline frozen table length differs")
    for index, (case, words) in enumerate(zip(cases, expected_words), start=1):
        expected_name = "sample_{0:02d}".format(index)
        if (
            not isinstance(case, list)
            or len(case) != 3
            or case[0] != expected_name
            or not isinstance(words, list)
            or len(words) != 5
            or words[0] != index
        ):
            raise base.CaptureError("flags-live-timeline frozen case order differs")
        for raw in tuple(case[1:]) + tuple(words[1:]):
            if not isinstance(raw, str):
                raise base.CaptureError("flags-live-timeline frozen word is not text")
            expected_length = 18 if raw.startswith("0x") else 16
            if len(raw) != expected_length:
                raise base.CaptureError("flags-live-timeline frozen word width differs")
            try:
                int(raw, 16)
            except ValueError as error:
                raise base.CaptureError(
                    "flags-live-timeline frozen word is invalid"
                ) from error
    acceptance = value.get("acceptance")
    if not isinstance(acceptance, dict) or acceptance.get("freshProcessCount") != 3:
        raise base.CaptureError("flags-live-timeline frozen acceptance differs")
    outcomes = value.get("outcomes")
    if not isinstance(outcomes, dict) or any(
        outcome is not None for outcome in outcomes.values()
    ):
        raise base.CaptureError(
            "flags-live-timeline preregistration outcomes are opened"
        )
    return cases, expected_words


def parse_runtime(
    output: str,
    frozen_cases: Sequence[Sequence[object]],
) -> Sequence[Mapping[str, object]]:
    records: List[Mapping[str, object]] = []
    for line in output.splitlines():
        match = base.RUNTIME_PATTERN.fullmatch(line)
        if match is None:
            continue
        records.append(
            {
                "qualifiedName": match.group(1),
                "flagsBits": match.group(2),
                "fractionBits": match.group(3),
                "dimensionBits": match.group(4),
            }
        )
    expected = [
        {
            "qualifiedName": "material_context_flags_live:" + str(case[0]),
            "flagsBits": EXPECTED_FLAGS_BITS,
            "fractionBits": str(case[1]),
            "dimensionBits": str(case[2]),
        }
        for case in frozen_cases
    ]
    if records != expected:
        raise base.CaptureError("flags-live-timeline runtime inputs differ")
    return records


def configure_base() -> None:
    base.PROBE_SOURCE_NAME = "probe_designlibrary_material_context_flags_live_timeline_transfer_local_macos_26_6_1.c"
    base.BASE_CONTEXT_PROBE_SOURCE_NAME = "probe_designlibrary_material_context_live_timeline_transfer_local_macos_26_6_1.c"
    base.LLDB_ADAPTER_NAME = "capture_designlibrary_material_context_flags_live_timeline_transfer_local_macos_26_6_1_lldb.py"
    base.PREREGISTRATION_NAME = "designlibrary_material_context_flags_live_timeline_transfer_local_macos_26_6_1_preregistration.json"
    base.CASE_NAMES = CASE_NAMES
    base.EXPECTED_CASE_NAMES = EXPECTED_CASE_NAMES
    base.EXPECTED_FLAGS_BITS = EXPECTED_FLAGS_BITS
    base.EXPECTED_PUBLIC_TIMELINE_SHA256 = EXPECTED_TIMELINE_SHA256
    base.RUNTIME_PATTERN = base.re.compile(
        r"^FLAGS_LIVE_MATERIAL_CONTEXT_CASE "
        r"(material_context_flags_live:\S+) flags=(0x[0-9a-f]{16}) "
        r"fraction_bits=(0x[0-9a-f]{16}) "
        r"dimension_bits=(0x[0-9a-f]{16})$"
    )
    base.FIELD_TRANSFER = (
        ("shadow.amount", 40, "inputShadowAmount"),
        ("blur.radius", 176, "inputBlurRadiusTimesTwo"),
        ("refraction.innerAmount", 264, "inputInnerRefractionAmount"),
        ("edgeBleed.amount", 392, "inputBleedAmount"),
    )
    base.validate_preregistration = validate_preregistration
    base.parse_runtime = parse_runtime


def capture(output_path: Path) -> Mapping[str, object]:
    configure_base()
    result = dict(base.capture(output_path))
    result.pop("designLibraryMaterialContextLiveTimelineTransferCaptureSchemaVersion")
    result[
        "designLibraryMaterialContextFlagsLiveTimelineTransferCaptureSchemaVersion"
    ] = SCHEMA_VERSION
    result["classification"] = (
        "prospectively frozen flags-produced Material.Context dimensions run "
        "through Apple's exact Parameters builder in fresh headless native "
        "processes, then transferred by the already-proved binary64 scale "
        "operation into independently retained public filter words"
    )
    result["predecessors"]["publicTimeline"] = {
        "path": "artifacts/gh-run-31118243811/transition-timeline.json",
        "sha256": EXPECTED_TIMELINE_SHA256,
    }
    capture_source = Path(__file__).resolve()
    result["tool"]["captureSource"] = "Analysis/" + capture_source.name
    result["tool"]["captureSourceSHA256"] = base.environment.sha256(capture_source)
    for case in result["cases"]:
        case["qualifiedName"] = "material_context_flags_live:" + str(case["name"])
        case["allPublicPredictionsMatchBitwise"] = case.pop(
            "allProviderPredictionsMatchBitwise"
        )
        predictions = case.pop("providerPredictions")
        for prediction in predictions:
            prediction["publicInput"] = prediction.pop("providerOffset")
            prediction["expectedPublicRawLittleEndianHex"] = prediction.pop(
                "expectedLiveRawLittleEndianHex"
            )
            prediction["predictedPublicRawLittleEndianHex"] = prediction.pop(
                "predictedLiveRawLittleEndianHex"
            )
        case["publicPredictions"] = predictions
    invariants = result["measuredInvariants"]
    invariants.pop("environmentFlagsAreExactZero")
    invariants["environmentFlagsMatchProducedRegularLight"] = True
    invariants["publicPredictionMatchCounts"] = invariants.pop(
        "providerPredictionMatchCounts"
    )
    invariants["totalPublicPredictionCount"] = invariants.pop(
        "totalProviderPredictionCount"
    )
    invariants["totalPublicPredictionMatchCount"] = invariants.pop(
        "totalProviderPredictionMatchCount"
    )
    result["claims"] = {
        "exactFlagsProducedContextToOpenedLivePublicFieldsTransferEstablished": True,
        "allThirtyTwoOpenedLivePublicFieldsReplayBitwise": True,
        "completeLiveParametersTransferEstablished": False,
        "generalContextToParametersValueLawEstablished": False,
        "generalIntegerCropAllocationPolicyEstablished": False,
        "retinaCompositorColorLawEstablished": False,
        "independentWalleZeroByteFrameParityEstablished": False,
        "liquidGlassParityEstablished": False,
        "productionShaderChangeAuthorized": False,
    }
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    try:
        capture(arguments.output.resolve())
    except base.CaptureError as error:
        print("CAPTURE_ERROR: " + str(error), file=base.sys.stderr)
        return 1
    print(str(arguments.output.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
