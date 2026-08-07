#!/usr/bin/env python3
"""Compose the live blur-distance lane-4 law across frozen byte boundaries."""

import argparse
import hashlib
import json
import struct
from collections.abc import Mapping, Sequence
from pathlib import Path


SCHEMA_VERSION = 1
CHAIN_COUNT = 1526
CASE_COUNT = 32
PARAMETERS_BYTE_COUNT = 1025
PROVIDER_BYTE_COUNT = 504
PARAMETERS_BLUR_START = 176
PROVIDER_BLUR_START = 152
BLUR_BLOCK_BYTE_COUNT = 72
PARAMETERS_BLUR_DISTANCE4_OFFSET = 216
PROVIDER_BLUR_DISTANCE4_OFFSET = 192
PARAMETERS_OUTER_AMOUNT_OFFSET = 280
PROVIDER_OUTER_AMOUNT_OFFSET = 248
EXPECTED_ARTIFACT_DIRECTORY_NAME = (
    "local-background-filter-constructor-timeline-marker-return-join-4bda1b4-run1"
)
EXPECTED_SHA256 = {
    "constructorSemantics": (
        "f2502d578a87e33b8db738846d0278522d75d6a317f14bb169408f1d0a6fe690"
    ),
    "falsified49FieldResult": (
        "d55d1749fe8a3824029f811c87d3f7f416046e5b01e710ae8304e8fd21f80e83"
    ),
    "returnJoinResult": (
        "e21834578e16099d06fd8fde52589b53cd67f97cd295a555e5d5c839a28cda44"
    ),
    "validation": (
        "93ea10f0d2a6981d652d66ff5a2f113622b2cf393a8115490ca9b0a2bbaabe6f"
    ),
    "trace": "b13b08a1d5e9d90aa60dea3c46f06074a00eba3609a96e9bc36e92b2e0dd831d",
    "timeline": (
        "ebdd4a6ad942b21ab88eec7a5bd22b6b4ef399d5370279c46c904e3e272da2c2"
    ),
}


type JSONObject = dict[str, object]


class AnalysisError(RuntimeError):
    """Raised when a frozen input or byte-level composition differs."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AnalysisError(label + " is unreadable") from error
    if not isinstance(value, Mapping):
        raise AnalysisError(label + " is not an object")
    return value


def raw_snapshot(value: object, label: str, byte_count: int) -> bytes:
    if not isinstance(value, Mapping) or not isinstance(value.get("hex"), str):
        raise AnalysisError(label + " is absent")
    try:
        payload = bytes.fromhex(value["hex"])
    except ValueError as error:
        raise AnalysisError(label + " is malformed") from error
    if len(payload) != byte_count:
        raise AnalysisError(label + " width differs")
    return payload


def frozen_inputs(
    analysis_directory: Path, artifact_directory: Path
) -> tuple[JSONObject, Mapping[str, object], Mapping[str, object], Mapping[str, object]]:
    if artifact_directory.name != EXPECTED_ARTIFACT_DIRECTORY_NAME:
        raise AnalysisError("artifact directory identity differs")
    paths = {
        "constructorSemantics": (
            analysis_directory
            / "designlibrary_background_filter_constructor_semantics_"
            "local_macos_26_6_1_result.json"
        ),
        "falsified49FieldResult": (
            analysis_directory
            / "background_filter_constructor_return_join_live_public_boundary_"
            "local_macos_26_6_1_result.json"
        ),
        "returnJoinResult": (
            analysis_directory
            / "background_filter_constructor_timeline_marker_return_join_"
            "4bda1b4_result.json"
        ),
        "validation": artifact_directory / "validation.json",
        "trace": artifact_directory / "background-filter-direct-join-trace.json",
        "timeline": artifact_directory / "transition-timeline.json",
    }
    for name, path in paths.items():
        if not path.is_file() or sha256(path) != EXPECTED_SHA256[name]:
            raise AnalysisError(name + " identity differs")

    semantics = load_json(paths["constructorSemantics"], "constructor semantics")
    failed = load_json(paths["falsified49FieldResult"], "49-field result")
    validation = load_json(paths["validation"], "return-join validation")
    trace = load_json(paths["trace"], "return-join trace")
    timeline = load_json(paths["timeline"], "same-run public timeline")

    all_present = semantics.get("allPresentPath")
    if not isinstance(all_present, Mapping):
        raise AnalysisError("all-present constructor path is absent")
    transfers = all_present.get("transfers")
    required_transfer = {
        "byteCount": BLUR_BLOCK_BYTE_COUNT,
        "outputStart": PROVIDER_BLUR_START,
        "source": "parameters",
        "sourceStart": PARAMETERS_BLUR_START,
    }
    if (
        semantics.get(
            "designLibraryBackgroundFilterConstructorSemanticsAnalysisSchemaVersion"
        )
        != 1
        or all_present.get("all491WrittenByteOriginsProvedExactly") is not True
        or all_present.get("arithmeticAppliedToPresentPayloadBytes") is not False
        or not isinstance(transfers, Sequence)
        or required_transfer not in transfers
    ):
        raise AnalysisError("constructor blur transfer proof differs")

    invariants = failed.get("measuredInvariants")
    authority = validation.get("authority")
    public_joins = validation.get("publicJoins")
    if not isinstance(invariants, Mapping):
        raise AnalysisError("falsified 49-field invariants are absent")
    if (
        invariants.get("mappedFieldCount") != 49
        or invariants.get("mappedComponentCount") != 1568
        or invariants.get("mappedComponentBitwiseMatchCount") != 1536
        or invariants.get("mappedComponentBitwiseMismatchCount") != 32
        or invariants.get("rejectedMappedFields")
        != ["filterArrayGetter.inputBlurDistance4.constantZero"]
    ):
        raise AnalysisError("falsified 49-field boundary differs")
    if not isinstance(authority, Mapping) or not isinstance(public_joins, Mapping):
        raise AnalysisError("validated live authority is absent")
    if (
        validation.get("captureContractPassed") is not True
        or authority.get("liveParametersBuilderToConstructorJoinedBitwise") is not True
        or authority.get("liveInitializedConstructorReturnToProviderJoinedBitwise")
        is not True
        or authority.get("sameRunPublicProvider18FieldJoinEstablishedSamples1Through32")
        is not True
        or public_joins.get("all32SamplesAcceptanceGated") is not True
        or public_joins.get("selectionUsesCapturedValues") is not False
    ):
        raise AnalysisError("validated live join differs")

    identities: JSONObject = {
        name: {"path": str(path), "sha256": sha256(path)}
        for name, path in paths.items()
    }
    return identities, validation, trace, timeline


def analyze(artifact_directory: Path, output_path: Path) -> Mapping[str, object]:
    analysis_directory = Path(__file__).resolve().parent
    identities, validation, trace, timeline = frozen_inputs(
        analysis_directory, artifact_directory.resolve()
    )
    chains_value = trace.get("chains")
    if not isinstance(chains_value, Sequence) or len(chains_value) != CHAIN_COUNT:
        raise AnalysisError("complete chain domain differs")

    lane4_parameter_constructor_matches = 0
    lane4_constructor_provider_matches = 0
    outer_parameter_constructor_matches = 0
    outer_constructor_provider_matches = 0
    live_alias_matches = 0
    lane4_words: set[bytes] = set()
    decoded_chains: list[tuple[bytes, bytes, bytes]] = []
    for chain_index, chain_value in enumerate(chains_value):
        if not isinstance(chain_value, Mapping):
            raise AnalysisError("chain is not an object")
        if chain_value.get("chainIndex") != chain_index or chain_value.get("stage") != "complete":
            raise AnalysisError("chain topology differs")
        parameters = raw_snapshot(
            chain_value.get("builderOutputAtReturn"),
            "builder output",
            PARAMETERS_BYTE_COUNT,
        )
        constructor = raw_snapshot(
            chain_value.get("constructorOutputAtReturn"),
            "constructor return",
            PROVIDER_BYTE_COUNT,
        )
        provider = raw_snapshot(
            chain_value.get("providerObjectAtEntry"),
            "provider object",
            PROVIDER_BYTE_COUNT,
        )
        p_lane4 = parameters[
            PARAMETERS_BLUR_DISTANCE4_OFFSET : PARAMETERS_BLUR_DISTANCE4_OFFSET + 8
        ]
        c_lane4 = constructor[
            PROVIDER_BLUR_DISTANCE4_OFFSET : PROVIDER_BLUR_DISTANCE4_OFFSET + 8
        ]
        v_lane4 = provider[
            PROVIDER_BLUR_DISTANCE4_OFFSET : PROVIDER_BLUR_DISTANCE4_OFFSET + 8
        ]
        p_outer = parameters[
            PARAMETERS_OUTER_AMOUNT_OFFSET : PARAMETERS_OUTER_AMOUNT_OFFSET + 8
        ]
        c_outer = constructor[
            PROVIDER_OUTER_AMOUNT_OFFSET : PROVIDER_OUTER_AMOUNT_OFFSET + 8
        ]
        v_outer = provider[
            PROVIDER_OUTER_AMOUNT_OFFSET : PROVIDER_OUTER_AMOUNT_OFFSET + 8
        ]
        lane4_parameter_constructor_matches += p_lane4 == c_lane4
        lane4_constructor_provider_matches += c_lane4 == v_lane4
        outer_parameter_constructor_matches += p_outer == c_outer
        outer_constructor_provider_matches += c_outer == v_outer
        live_alias_matches += p_lane4 == p_outer
        lane4_words.add(p_lane4)
        decoded_chains.append((parameters, constructor, provider))

    chain_counts = (
        lane4_parameter_constructor_matches,
        lane4_constructor_provider_matches,
        outer_parameter_constructor_matches,
        outer_constructor_provider_matches,
    )
    if chain_counts != (CHAIN_COUNT,) * 4:
        raise AnalysisError("live constructor byte composition differs")

    public_joins = validation["publicJoins"]
    selected_value = public_joins.get("selectedChains")
    uniforms = timeline.get("dynamicBackgroundUniforms")
    records_value = uniforms.get("records") if isinstance(uniforms, Mapping) else None
    if (
        not isinstance(selected_value, Sequence)
        or len(selected_value) != CASE_COUNT
        or not isinstance(records_value, Sequence)
        or len(records_value) != CASE_COUNT
    ):
        raise AnalysisError("same-run selected sample domain differs")

    observations: list[JSONObject] = []
    lane4_public_matches = 0
    outer_public_matches = 0
    for expected_sample, (selected, record) in enumerate(
        zip(selected_value, records_value, strict=True), start=1
    ):
        if not isinstance(selected, Mapping) or not isinstance(record, Mapping):
            raise AnalysisError("same-run selected sample is not an object")
        chain_index = selected.get("structurallySelectedChainIndex")
        filter_value = record.get("filter")
        inputs = filter_value.get("inputValues") if isinstance(filter_value, Mapping) else None
        if (
            selected.get("sampleIndex") != expected_sample
            or record.get("sampleIndex") != expected_sample
            or not isinstance(chain_index, int)
            or isinstance(chain_index, bool)
            or not 0 <= chain_index < CHAIN_COUNT
            or not isinstance(inputs, Mapping)
        ):
            raise AnalysisError("same-run selected sample identity differs")
        blur_distance4 = inputs.get("inputBlurDistance4")
        outer_amount = inputs.get("inputOuterRefractionAmount")
        if (
            not isinstance(blur_distance4, (int, float))
            or isinstance(blur_distance4, bool)
            or not isinstance(outer_amount, (int, float))
            or isinstance(outer_amount, bool)
        ):
            raise AnalysisError("same-run public scalar differs")
        parameters, _, provider = decoded_chains[chain_index]
        p_lane4 = parameters[
            PARAMETERS_BLUR_DISTANCE4_OFFSET : PARAMETERS_BLUR_DISTANCE4_OFFSET + 8
        ]
        v_lane4 = provider[
            PROVIDER_BLUR_DISTANCE4_OFFSET : PROVIDER_BLUR_DISTANCE4_OFFSET + 8
        ]
        p_outer = parameters[
            PARAMETERS_OUTER_AMOUNT_OFFSET : PARAMETERS_OUTER_AMOUNT_OFFSET + 8
        ]
        v_outer = provider[
            PROVIDER_OUTER_AMOUNT_OFFSET : PROVIDER_OUTER_AMOUNT_OFFSET + 8
        ]
        public_lane4 = struct.pack("<d", float(blur_distance4))
        public_outer = struct.pack("<d", float(outer_amount))
        lane4_matched = p_lane4 == v_lane4 == public_lane4
        outer_matched = p_outer == v_outer == public_outer
        lane4_public_matches += lane4_matched
        outer_public_matches += outer_matched
        observations.append(
            {
                "sampleIndex": expected_sample,
                "structurallySelectedChainIndex": chain_index,
                "parametersBlurDistance4RawLittleEndianHex": p_lane4.hex(),
                "providerBlurDistance4RawLittleEndianHex": v_lane4.hex(),
                "publicInputBlurDistance4RawLittleEndianHex": public_lane4.hex(),
                "blurDistance4MatchedBitwise": lane4_matched,
                "parametersOuterAmountRawLittleEndianHex": p_outer.hex(),
                "providerOuterAmountRawLittleEndianHex": v_outer.hex(),
                "publicOuterAmountRawLittleEndianHex": public_outer.hex(),
                "outerAmountMatchedBitwise": outer_matched,
            }
        )
    if lane4_public_matches != CASE_COUNT or outer_public_matches != CASE_COUNT:
        raise AnalysisError("same-run public byte composition differs")

    result: JSONObject = {
        "backgroundFilterConstructorReturnJoinBlurDistance4CompositionSchemaVersion": (
            SCHEMA_VERSION
        ),
        "classification": (
            "retrospective exact structural composition after the frozen constant-zero "
            "prediction failed; the rejected prediction remains preserved unchanged"
        ),
        "inputs": identities
        | {
            "analysisSource": {
                "path": "Analysis/" + Path(__file__).name,
                "sha256": sha256(Path(__file__).resolve()),
            }
        },
        "constructorTransferLaw": {
            "parametersBlurBlockRange": [PARAMETERS_BLUR_START, 248],
            "providerBlurBlockRange": [PROVIDER_BLUR_START, 224],
            "byteCount": BLUR_BLOCK_BYTE_COUNT,
            "arithmeticApplied": False,
            "parametersBlurDistance4Offset": PARAMETERS_BLUR_DISTANCE4_OFFSET,
            "providerBlurDistance4Offset": PROVIDER_BLUR_DISTANCE4_OFFSET,
            "parametersOuterAmountOffset": PARAMETERS_OUTER_AMOUNT_OFFSET,
            "providerOuterAmountOffset": PROVIDER_OUTER_AMOUNT_OFFSET,
        },
        "allChainEvidence": {
            "chainCount": CHAIN_COUNT,
            "parametersBlurDistance4ToConstructorBitwiseMatchCount": (
                lane4_parameter_constructor_matches
            ),
            "constructorBlurDistance4ToProviderBitwiseMatchCount": (
                lane4_constructor_provider_matches
            ),
            "parametersOuterAmountToConstructorBitwiseMatchCount": (
                outer_parameter_constructor_matches
            ),
            "constructorOuterAmountToProviderBitwiseMatchCount": (
                outer_constructor_provider_matches
            ),
            "distinctParametersBlurDistance4WordCount": len(lane4_words),
            "liveProfileBlurDistance4OuterAmountAliasCount": live_alias_matches,
        },
        "sameRunPublicEvidence": {
            "sampleCount": CASE_COUNT,
            "parametersProviderPublicBlurDistance4BitwiseMatchCount": (
                lane4_public_matches
            ),
            "parametersProviderPublicOuterAmountBitwiseMatchCount": outer_public_matches,
            "selectionUsesCapturedValues": False,
            "observations": observations,
        },
        "corrected49FieldBoundary": {
            "preservedRejectedPrediction": (
                "filterArrayGetter.inputBlurDistance4.constantZero"
            ),
            "correctedParametersField": "blur.distances.4",
            "correctedParametersByteRange": [216, 224],
            "correctedPublicInput": "inputBlurDistance4",
            "correctedTransform": "binary64 identity",
            "inheritedExactMappedComponentCount": 1536,
            "correctedBitwiseMatchCount": 32,
            "mappedComponentCount": 1568,
            "mappedComponentBitwiseMatchCount": 1568,
            "mappedComponentBitwiseMismatchCount": 0,
            "fullyExactMappedFieldCount": 49,
            "rejectedMappedFieldCount": 0,
        },
        "interpretation": {
            "established": (
                "the actual live producer supplies inputBlurDistance4 from the fifth "
                "binary64 lane of Parameters.blur.distances; the authenticated "
                "constructor copies that byte range directly to provider +0xc0"
            ),
            "controlledGetterDistinction": (
                "the earlier exact constant-zero intervention remains valid for its "
                "controlled getter/export path and does not describe this live producer path"
            ),
            "semanticDisambiguation": (
                "blur distance 4 and refraction outer amount alias numerically in this "
                "profile, but independent constructor byte origins map Parameters +0xd8 "
                "to provider +0xc0 and Parameters +0x118 to provider +0xf8"
            ),
        },
        "authority": {
            "liveParametersBuilderToProviderTransferEstablished": True,
            "generalPublicParameters49FieldConstructionLawEstablished": True,
            "upstreamCropAllocationPolicyEstablished": False,
            "physicalRetinaColorPixelCompositorTransferEstablished": False,
            "independentWalleZeroByteFrameParityEstablished": False,
            "liquidGlassParityEstablished": False,
            "productionShaderAuthorized": False,
        },
    }
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, suggest_on_error=True)
    parser.add_argument("artifact_directory", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    try:
        analyze(arguments.artifact_directory, arguments.output.resolve())
    except AnalysisError as error:
        print("ANALYSIS_ERROR: " + str(error))
        return 1
    print(str(arguments.output.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
