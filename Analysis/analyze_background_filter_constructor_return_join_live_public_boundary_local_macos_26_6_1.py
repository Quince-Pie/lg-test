#!/usr/bin/env python3
"""Compare prospectively selected live Parameters with same-run public state."""

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import analyze_background_filter_constructor_live_public_boundary_local_macos_26_6_1 as legacy
import capture_designlibrary_parameters_mixer_basis_local_macos_26_6_1 as basis


SCHEMA_VERSION = 1
CASE_COUNT = 32
MAPPED_FIELD_COUNT = 49
MAPPED_COMPONENT_COUNT = CASE_COUNT * MAPPED_FIELD_COUNT
EXPECTED_ARTIFACT_DIRECTORY_NAME = (
    "local-background-filter-constructor-timeline-marker-return-join-4bda1b4-run1"
)
PREREGISTRATION_NAME = (
    "background_filter_constructor_return_join_live_public_boundary_"
    "local_macos_26_6_1_preregistration.json"
)
EXPECTED_PREREGISTRATION_SHA256 = (
    "4989483973cb9bbed473796102b59589616b6ab1d84ad80a189d5a6288248c1e"
)
EXPECTED_CAPTURE_COMMIT = "4bda1b463123b9c22be05cbef36841b22aaf68f6"
EXPECTED_VALIDATION_SHA256 = (
    "93ea10f0d2a6981d652d66ff5a2f113622b2cf393a8115490ca9b0a2bbaabe6f"
)
EXPECTED_TRACE_SHA256 = (
    "b13b08a1d5e9d90aa60dea3c46f06074a00eba3609a96e9bc36e92b2e0dd831d"
)
EXPECTED_TIMELINE_SHA256 = (
    "ebdd4a6ad942b21ab88eec7a5bd22b6b4ef399d5370279c46c904e3e272da2c2"
)
EXPECTED_DEPENDENCY_SHA256 = {
    "preCaptureMappingPreregistration": (
        "f634ac687b0b86f614fef18e6f4929d56cf31cd0b77d5a4b14034a03cb0a6030"
    ),
    "preCaptureMappingAnalysis": (
        "6329a734fb875ceb140559fabb539c14fef69b0768f886525453d7867da9052e"
    ),
    "authenticatedGetterMappingSource": (
        "d9406c8d9390d58ed9c399426b8a1fee1436de49e6198bd9c0b7c5bcddf24e7f"
    ),
    "authenticatedGetterMappingResult": (
        "308943d6d5cb16166cd7a1a3f63a824a2b4e47f93bab18e13f7fccac51b94767"
    ),
    "parametersBasisSource": (
        "829e758062d1905ed5635b09bf458337bebce3e41f506ec301d80c66112d2442"
    ),
    "returnJoinPreregistration": (
        "26d61690f6b1f177da679e4fe13324689b36322a3ced3b91bb7f987377cbb44e"
    ),
    "returnJoinValidator": (
        "4db2cd6c8bedcfb33d2e63cf05fc3c273f62c34e85dd4de4de5ad2775ae27f76"
    ),
    "returnJoinResult": (
        "e21834578e16099d06fd8fde52589b53cd67f97cd295a555e5d5c839a28cda44"
    ),
}


type JSONObject = dict[str, object]


class AnalysisError(RuntimeError):
    """Raised when a frozen input or exact comparison contract differs."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_source_sha256(path: Path) -> str:
    payload = path.read_bytes()
    needle = EXPECTED_PREREGISTRATION_SHA256.encode()
    if payload.count(needle) != 1:
        raise AnalysisError("analysis preregistration hash slot differs")
    return hashlib.sha256(payload.replace(needle, b"0" * 64)).hexdigest()


def load_json(path: Path, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AnalysisError(label + " is unreadable") from error
    if not isinstance(value, Mapping):
        raise AnalysisError(label + " is not an object")
    return value


def validate_frozen_inputs(analysis_directory: Path, source_path: Path) -> JSONObject:
    dependency_paths = {
        "preCaptureMappingPreregistration": (
            analysis_directory
            / "background_filter_constructor_live_public_boundary_"
            "local_macos_26_6_1_preregistration.json"
        ),
        "preCaptureMappingAnalysis": Path(legacy.__file__).resolve(),
        "authenticatedGetterMappingSource": (
            analysis_directory
            / "analyze_designlibrary_material_context_weighted_live_public_boundary.py"
        ),
        "authenticatedGetterMappingResult": (
            analysis_directory
            / "designlibrary_material_context_weighted_live_public_boundary_"
            "analysis_result.json"
        ),
        "parametersBasisSource": Path(basis.__file__).resolve(),
        "returnJoinPreregistration": (
            analysis_directory
            / "background_filter_constructor_timeline_marker_return_join_"
            "local_macos_26_6_1_preregistration.json"
        ),
        "returnJoinValidator": (
            analysis_directory
            / "validate_background_filter_constructor_timeline_marker_return_join_"
            "local_macos_26_6_1.py"
        ),
        "returnJoinResult": (
            analysis_directory
            / "background_filter_constructor_timeline_marker_return_join_"
            "4bda1b4_result.json"
        ),
    }
    for name, path in dependency_paths.items():
        if not path.is_file() or sha256(path) != EXPECTED_DEPENDENCY_SHA256[name]:
            raise AnalysisError(name + " identity differs")

    preregistration_path = analysis_directory / PREREGISTRATION_NAME
    if (
        not preregistration_path.is_file()
        or sha256(preregistration_path) != EXPECTED_PREREGISTRATION_SHA256
    ):
        raise AnalysisError("analysis preregistration identity differs")
    preregistration = load_json(preregistration_path, "analysis preregistration")
    source_identity = preregistration.get("sourceIdentity")
    if not isinstance(source_identity, Mapping):
        raise AnalysisError("analysis source identity is absent")
    if (
        preregistration.get(
            "backgroundFilterConstructorReturnJoinLivePublicBoundaryPreregistrationSchemaVersion"
        )
        != 1
        or preregistration.get("artifactDirectoryName")
        != EXPECTED_ARTIFACT_DIRECTORY_NAME
        or preregistration.get("caseCount") != CASE_COUNT
        or preregistration.get("mappedFieldCount") != MAPPED_FIELD_COUNT
        or preregistration.get("mappedComponentCount") != MAPPED_COMPONENT_COUNT
        or source_identity.get("analysisSourceNormalizedSHA256")
        != normalized_source_sha256(source_path)
    ):
        raise AnalysisError("analysis preregistration contract differs")

    return {
        "preregistration": {
            "path": "Analysis/" + preregistration_path.name,
            "sha256": sha256(preregistration_path),
        },
        **{
            name: {
                "path": "Analysis/" + path.name,
                "sha256": sha256(path),
            }
            for name, path in dependency_paths.items()
        },
    }


def validate_artifact(
    artifact_directory: Path,
) -> tuple[Mapping[str, object], Mapping[str, object], Mapping[str, object], JSONObject]:
    if artifact_directory.name != EXPECTED_ARTIFACT_DIRECTORY_NAME:
        raise AnalysisError("artifact directory identity differs")
    validation_path = artifact_directory / "validation.json"
    trace_path = artifact_directory / "background-filter-direct-join-trace.json"
    timeline_path = artifact_directory / "transition-timeline.json"
    expected = {
        validation_path: EXPECTED_VALIDATION_SHA256,
        trace_path: EXPECTED_TRACE_SHA256,
        timeline_path: EXPECTED_TIMELINE_SHA256,
    }
    for path, digest in expected.items():
        if not path.is_file() or sha256(path) != digest:
            raise AnalysisError(path.name + " identity differs")

    validation = load_json(validation_path, "return-join validation")
    trace = load_json(trace_path, "return-join trace")
    timeline = load_json(timeline_path, "same-run public timeline")
    authority = validation.get("authority")
    public_joins = validation.get("publicJoins")
    if not isinstance(authority, Mapping) or not isinstance(public_joins, Mapping):
        raise AnalysisError("validated join authority is absent")
    if (
        validation.get(
            "backgroundFilterConstructorTimelineMarkerReturnJoinLocalMacOSValidationSchemaVersion"
        )
        != 1
        or validation.get("captureCommit") != EXPECTED_CAPTURE_COMMIT
        or validation.get("captureContractPassed") is not True
        or authority.get("liveParametersBuilderToConstructorJoinedBitwise") is not True
        or authority.get("liveInitializedConstructorReturnToProviderJoinedBitwise")
        is not True
        or authority.get("sameRunPublicProvider18FieldJoinEstablishedSamples1Through32")
        is not True
        or public_joins.get("all32SamplesAcceptanceGated") is not True
        or public_joins.get("selectionUsesCapturedValues") is not False
    ):
        raise AnalysisError("validated return-join contract differs")
    if (
        trace.get(
            "backgroundFilterConstructorTimelineMarkerReturnJoinLocalMacOSLldbTraceSchemaVersion"
        )
        != 1
        or trace.get("status") != "finalized"
        or trace.get("finalChainCount") != 1526
        or trace.get("finalCompleteChainCount") != 1526
        or trace.get("finalConstructorReturnSnapshotCount") != 1526
        or trace.get("finalFailureCount") != 0
    ):
        raise AnalysisError("return-join trace contract differs")

    identities: JSONObject = {
        "validation": {"path": str(validation_path), "sha256": sha256(validation_path)},
        "constructorTrace": {"path": str(trace_path), "sha256": sha256(trace_path)},
        "sameRunPublicTimeline": {
            "path": str(timeline_path),
            "sha256": sha256(timeline_path),
        },
    }
    return validation, trace, timeline, identities


def live_parameters(
    validation: Mapping[str, object], trace: Mapping[str, object]
) -> tuple[list[bytes], list[JSONObject]]:
    public_joins = validation.get("publicJoins")
    chains_value = trace.get("chains")
    if not isinstance(public_joins, Mapping) or not isinstance(chains_value, Sequence):
        raise AnalysisError("selected live chain domain differs")
    selected_value = public_joins.get("selectedChains")
    if not isinstance(selected_value, Sequence) or len(selected_value) != CASE_COUNT:
        raise AnalysisError("selected live chain count differs")

    payloads: list[bytes] = []
    records: list[JSONObject] = []
    selected_indices: list[int] = []
    for expected_sample, selected_value_item in enumerate(selected_value, start=1):
        if not isinstance(selected_value_item, Mapping):
            raise AnalysisError("selected live chain is not an object")
        chain_index = selected_value_item.get("structurallySelectedChainIndex")
        if (
            selected_value_item.get("sampleIndex") != expected_sample
            or not isinstance(chain_index, int)
            or isinstance(chain_index, bool)
            or not 0 <= chain_index < len(chains_value)
        ):
            raise AnalysisError("selected live chain identity differs")
        chain_value = chains_value[chain_index]
        if not isinstance(chain_value, Mapping):
            raise AnalysisError("selected trace chain is not an object")
        snapshot = chain_value.get("builderOutputAtReturn")
        if (
            chain_value.get("chainIndex") != chain_index
            or chain_value.get("stage") != "complete"
            or not isinstance(snapshot, Mapping)
        ):
            raise AnalysisError("selected trace chain topology differs")
        encoded = snapshot.get("hex")
        if not isinstance(encoded, str):
            raise AnalysisError("selected Parameters bytes are absent")
        try:
            payload = bytes.fromhex(encoded)
        except ValueError as error:
            raise AnalysisError("selected Parameters bytes are malformed") from error
        if (
            len(payload) != basis.PARAMETERS_BYTE_COUNT
            or legacy.digest_bytes(payload) != snapshot.get("sha256")
            or legacy.digest_bytes(payload) != selected_value_item.get("parametersSHA256")
        ):
            raise AnalysisError("selected Parameters identity differs")
        normalized = basis.normalize_parameters(payload)
        selected_indices.append(chain_index)
        payloads.append(payload)
        records.append(
            {
                "sampleIndex": expected_sample,
                "structurallySelectedChainIndex": chain_index,
                "rawParametersSHA256": legacy.digest_bytes(payload),
                "normalizedParametersSHA256": legacy.digest_bytes(normalized),
                "rawParametersHex": payload.hex(),
                "normalizedParametersHex": normalized.hex(),
            }
        )
    if len(set(selected_indices)) != CASE_COUNT:
        raise AnalysisError("selected live chains are not distinct")
    return payloads, records


def analyze(artifact_directory: Path, output_path: Path) -> Mapping[str, object]:
    analysis_directory = Path(__file__).resolve().parent
    source_path = Path(__file__).resolve()
    frozen_inputs = validate_frozen_inputs(analysis_directory, source_path)
    validation, trace, timeline, artifact_inputs = validate_artifact(
        artifact_directory.resolve()
    )
    payloads, parameter_records = live_parameters(validation, trace)
    samples = legacy.same_run_public_samples(timeline)
    fields = legacy.mapped_field_results(payloads, samples)
    field_count = len(fields)
    component_count = sum(int(field["componentCount"]) for field in fields)
    match_count = sum(int(field["bitwiseMatchCount"]) for field in fields)
    mismatch_count = component_count - match_count
    if field_count != MAPPED_FIELD_COUNT or component_count != MAPPED_COMPONENT_COUNT:
        raise AnalysisError("mapped comparison domain differs")

    exact_fields = [
        str(field["parametersField"])
        for field in fields
        if field["bitwiseMismatchCount"] == 0
    ]
    rejected_fields = [
        str(field["parametersField"])
        for field in fields
        if field["bitwiseMismatchCount"] != 0
    ]
    per_case: list[JSONObject] = []
    for sample_index in range(1, CASE_COUNT + 1):
        matches = sum(
            field["observations"][sample_index - 1]["matchedBitwise"] is True
            for field in fields
        )
        per_case.append(
            {
                "sampleIndex": sample_index,
                "mappedFieldCount": field_count,
                "bitwiseMatchCount": matches,
                "bitwiseMismatchCount": field_count - matches,
            }
        )

    exact = mismatch_count == 0
    result: JSONObject = {
        "backgroundFilterConstructorReturnJoinLivePublicBoundaryAnalysisSchemaVersion": (
            SCHEMA_VERSION
        ),
        "classification": (
            "post-capture exact execution of the pre-capture frozen 49-field getter "
            "mapping against all prospectively selected same-run live Parameters values"
        ),
        "inputs": frozen_inputs
        | artifact_inputs
        | {
            "analysisSource": {
                "path": "Analysis/" + source_path.name,
                "sha256": sha256(source_path),
            }
        },
        "liveParameters": parameter_records,
        "mappedFields": fields,
        "perCase": per_case,
        "measuredInvariants": {
            "caseCount": CASE_COUNT,
            "prospectivelySelectedLiveParametersCount": len(payloads),
            "sameRunPublicSampleCount": len(samples),
            "mappedFieldCount": field_count,
            "mappedComponentCount": component_count,
            "mappedComponentBitwiseMatchCount": match_count,
            "mappedComponentBitwiseMismatchCount": mismatch_count,
            "fullyExactMappedFieldCount": len(exact_fields),
            "rejectedMappedFieldCount": len(rejected_fields),
            "fullyExactMappedFields": exact_fields,
            "rejectedMappedFields": rejected_fields,
            "capturedValuesUsedForSampleOrChainSelection": False,
        },
        "interpretation": {
            "acceptedBoundary": (
                "all compared Parameters payloads were selected prospectively by "
                "event order and were already joined bitwise through the live provider"
            ),
            "mappedTransfer": (
                "all 49 pre-capture-frozen scalar/discrete getter laws match same-run "
                "public state bitwise"
                if exact
                else "at least one pre-capture-frozen getter law differs from same-run "
                "public state; the mismatch is retained without reselection"
            ),
            "excludedBoundary": (
                "CGColor transfer, inputClamp, crop/allocation, physical compositor "
                "color, and final Walle pixels remain separate gates"
            ),
        },
        "authority": {
            "liveParametersBuilderToProviderTransferEstablished": True,
            "generalPublicParameters49FieldConstructionLawEstablished": exact,
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
