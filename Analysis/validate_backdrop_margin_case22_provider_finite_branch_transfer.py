#!/usr/bin/env python3
"""Validate the prospective native finite-branch provider transfer."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import analyze_backdrop_margin_case22_provider_complete_semantics as complete
import generate_backdrop_margin_case22_provider_finite_branch_corpus as generator


VALIDATION_SCHEMA_VERSION = 1
EXPECTED_UUID = "1e98080269f53e6989ef50088297fcf5"
EXPECTED_PROVIDER_CODE_SHA256 = (
    "a76c6f0b03cc6b64c6b040220f495c5f22d7e1e5322efb3cb139554dd397c10b"
)


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{path} is unreadable: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not an object")
    return value


def sequence(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} is not an array")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def current_commit(repository: Path) -> str:
    try:
        process = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository,
            text=True,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f"repository commit is unavailable: {error}") from error
    return process.stdout.strip()


def validate(
    preregistration_path: Path,
    capture_path: Path,
    trace_path: Path,
    llvm_mc: str,
) -> dict[str, Any]:
    repository = Path(__file__).resolve().parent.parent
    preregistration = load_json(preregistration_path)
    capture = load_json(capture_path)
    require(
        preregistration.get(
            "backdropMarginCase22ProviderFiniteBranchTransferPreregistrationSchemaVersion"
        )
        == 1,
        "finite-branch preregistration schema differs",
    )
    require(
        capture.get(
            "backdropMarginCase22ProviderFiniteBranchTransferCaptureSchemaVersion"
        )
        == 1,
        "finite-branch capture schema differs",
    )

    inputs = mapping(capture.get("inputs"), "capture inputs")
    captured_preregistration = mapping(
        inputs.get("preregistration"), "captured preregistration"
    )
    require(
        captured_preregistration.get("sha256") == sha256_path(preregistration_path),
        "captured preregistration hash differs",
    )
    require(
        inputs.get("sourceCommit") == current_commit(repository),
        "capture source commit is not the checked-out commit",
    )
    frozen_files = sequence(preregistration.get("frozenFiles"), "frozen files")
    captured_files = sequence(inputs.get("frozenFiles"), "captured frozen files")
    require(len(frozen_files) == len(captured_files), "frozen file count differs")
    for expected_value, observed_value in zip(frozen_files, captured_files):
        expected = mapping(expected_value, "frozen file")
        observed = mapping(observed_value, "captured frozen file")
        relative = expected.get("path")
        require(isinstance(relative, str), "frozen file path differs")
        digest = sha256_path(repository / relative)
        require(expected.get("sha256") == digest, f"frozen file differs: {relative}")
        require(
            observed.get("path") == relative and observed.get("sha256") == digest,
            f"captured frozen file differs: {relative}",
        )

    require(
        sha256_path(trace_path)
        == mapping(
            preregistration.get("retrospectiveTrace"), "retrospective trace"
        ).get("sha256"),
        "retrospective trace hash differs",
    )
    trace = complete.load_json(trace_path)
    code = complete.provider_code(trace)
    instructions = complete.disassemble(code, llvm_mc)
    regenerated = generator.generate(instructions)
    frozen_corpus = mapping(preregistration.get("frozenCorpus"), "frozen corpus")
    require(
        regenerated["corpus"]["recordCount"] == frozen_corpus.get("recordCount"),
        "regenerated corpus count differs",
    )
    require(
        regenerated["corpus"]["rawObjectsAndPredictionsSHA256"]
        == frozen_corpus.get("rawObjectsAndPredictionsSHA256"),
        "regenerated corpus digest differs",
    )
    require(
        regenerated["coverage"] == frozen_corpus.get("coverage"),
        "regenerated corpus coverage differs",
    )

    require(
        capture.get("nativeAppleHost") == preregistration.get("nativeAppleHost"),
        "native Apple host identity differs",
    )
    compilation = mapping(capture.get("nativeCompilation"), "native compilation")
    require(
        compilation.get("usesNixStorePath") is False
        and "/nix/store/" not in str(compilation.get("command")),
        "native Apple compilation used a Nix store path",
    )
    provider = mapping(capture.get("provider"), "captured provider")
    require(
        provider.get("designLibraryUUID") == EXPECTED_UUID
        and provider.get("providerCodeByteCount") == 984
        and provider.get("providerCodeSHA256") == EXPECTED_PROVIDER_CODE_SHA256
        and provider.get("processExitStatus") == 0
        and provider.get("stderrEmpty") is True,
        "captured native provider identity or transport differs",
    )
    transport = mapping(capture.get("transport"), "capture transport")
    for key in (
        "sshBatchMode",
        "providerExecutedOutsideNix",
        "allRecordsDispatchedBeforeMatchClassification",
    ):
        require(transport.get(key) is True, f"transport gate differs: {key}")
    require(
        transport.get("appleOutputsConsultedForCandidateGeneration") is False,
        "Apple outputs influenced candidate generation",
    )

    captured_corpus = mapping(capture.get("corpus"), "captured corpus")
    expected_records = sequence(
        regenerated["corpus"]["records"], "regenerated corpus records"
    )
    observed_records = sequence(captured_corpus.get("records"), "captured records")
    require(
        captured_corpus.get("recordCount") == len(expected_records)
        and len(observed_records) == len(expected_records),
        "captured corpus count differs",
    )
    require(
        captured_corpus.get("rawObjectsAndPredictionsSHA256")
        == regenerated["corpus"]["rawObjectsAndPredictionsSHA256"],
        "captured corpus digest differs",
    )
    require(
        captured_corpus.get("predictedCoverage") == regenerated["coverage"],
        "captured predicted coverage differs",
    )

    mismatches = []
    normalized_records = []
    for ordinal, (expected_value, observed_value) in enumerate(
        zip(expected_records, observed_records)
    ):
        expected = mapping(expected_value, f"expected record {ordinal}")
        observed = mapping(observed_value, f"captured record {ordinal}")
        predicted = expected.get("predictedReturnRawLittleEndianHex")
        apple = observed.get("appleReturnRawLittleEndianHex")
        require(
            observed.get("ordinal") == ordinal
            and observed.get("objectSHA256") == expected.get("objectSHA256")
            and observed.get("predictedReturnRawLittleEndianHex") == predicted,
            f"captured record {ordinal} identity differs",
        )
        try:
            apple_bytes = bytes.fromhex(str(apple))
        except ValueError as error:
            raise ValueError(f"captured record {ordinal} is not hexadecimal") from error
        require(len(apple_bytes) == 8, f"captured record {ordinal} width differs")
        matched = apple == predicted
        require(
            observed.get("returnMatchedBitwise") is matched,
            f"captured record {ordinal} match flag differs",
        )
        record = {
            "ordinal": ordinal,
            "objectSHA256": expected["objectSHA256"],
            "predictedReturnRawLittleEndianHex": predicted,
            "appleReturnRawLittleEndianHex": apple,
            "returnMatchedBitwise": matched,
        }
        normalized_records.append(record)
        if not matched:
            mismatches.append(record)

    matching_count = len(normalized_records) - len(mismatches)
    all_matched = not mismatches
    return {
        "backdropMarginCase22ProviderFiniteBranchTransferValidationSchemaVersion": (
            VALIDATION_SCHEMA_VERSION
        ),
        "classification": (
            "prospective exact differential validation of native Apple "
            "DesignLibrary against a preregistered finite-object branch corpus"
        ),
        "inputs": {
            "preregistration": {
                "path": str(preregistration_path),
                "sha256": sha256_path(preregistration_path),
            },
            "capture": {"path": str(capture_path), "sha256": sha256_path(capture_path)},
            "retrospectiveTrace": {
                "path": str(trace_path),
                "sha256": sha256_path(trace_path),
            },
        },
        "structuralValidationPassed": True,
        "hypothesis": {
            "recordCount": len(normalized_records),
            "matchingReturnCount": matching_count,
            "allAppleReturnsMatchedPredictionsBitwise": all_matched,
            "mismatches": mismatches,
        },
        "coverage": regenerated["coverage"],
        "authority": {
            "prospectiveFiniteCorpusTransferEstablished": all_matched,
            "all75ObservedFiniteBranchOutcomesTransferred": all_matched,
            "unobservedOutcomesProvedInfeasible": False,
            "completeFiniteProviderLaw": False,
            "publicInputFieldMappingEstablished": False,
            "upstreamIntegerCropAllocationPolicyEstablished": False,
            "liquidGlassParityEstablished": False,
            "productionShaderAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--llvm-mc", default="llvm-mc")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        result = validate(
            arguments.preregistration,
            arguments.capture,
            arguments.trace,
            arguments.llvm_mc,
        )
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(payload, end="")
    else:
        arguments.output.write_text(payload, encoding="utf-8")
    hypothesis = result["hypothesis"]
    print(
        "APPLE_RETURN_MATCHES="
        f"{hypothesis['matchingReturnCount']}/{hypothesis['recordCount']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
