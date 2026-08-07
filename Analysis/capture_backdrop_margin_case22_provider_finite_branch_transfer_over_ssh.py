#!/usr/bin/env python3
"""Run the frozen finite case-22 corpus against native DesignLibrary.

Corpus construction and analysis run under the repository's Nix development
environment.  The authenticated provider itself runs in a fresh native Apple
Command Line Tools executable over SSH and never inherits a Nix store path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import analyze_backdrop_margin_case22_provider_complete_semantics as complete
import generate_backdrop_margin_case22_provider_finite_branch_corpus as generator


CAPTURE_SCHEMA_VERSION = 1
REMOTE_HOST = "quince@10.0.41.19"
SSH_PREFIX = ("ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10")
EXPECTED_UUID = "1e98080269f53e6989ef50088297fcf5"
EXPECTED_PROVIDER_CODE_SHA256 = (
    "a76c6f0b03cc6b64c6b040220f495c5f22d7e1e5322efb3cb139554dd397c10b"
)
REMOTE_DIRECTORY_PATTERN = re.compile(r"/tmp/lg-case22-finite\.[A-Za-z0-9]+")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{path} is unreadable: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def run(
    command: Sequence[str],
    *,
    cwd: Optional[Path] = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        stderr = getattr(error, "stderr", "")
        raise ValueError(f"command failed: {command!r}: {stderr}") from error


def require_frozen_files(
    repository: Path, preregistration: dict[str, Any]
) -> list[dict[str, str]]:
    records = preregistration.get("frozenFiles")
    if not isinstance(records, list) or not records:
        raise ValueError("preregistration frozen files are missing")
    verified = []
    for value in records:
        if not isinstance(value, dict):
            raise ValueError("a frozen file record is not an object")
        relative = value.get("path")
        expected = value.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise ValueError("a frozen file record is incomplete")
        path = repository / relative
        observed = sha256_path(path)
        if observed != expected:
            raise ValueError(f"frozen file differs: {relative}")
        verified.append(
            {"path": relative, "sha256": observed, "absolutePath": str(path)}
        )
    return verified


def require_clean_tracked_repository(repository: Path) -> str:
    status = run(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=repository
    )
    if status.stdout:
        raise ValueError("tracked repository state is dirty")
    return run(["git", "rev-parse", "HEAD"], cwd=repository).stdout.strip()


def remote_host_identity() -> dict[str, str]:
    command = (
        "/usr/bin/sw_vers -productVersion; "
        "/usr/bin/sw_vers -buildVersion; "
        "/usr/bin/uname -m; "
        "/usr/sbin/sysctl -n hw.model; "
        "/usr/sbin/sysctl -n machdep.cpu.brand_string"
    )
    lines = run([*SSH_PREFIX, REMOTE_HOST, command]).stdout.splitlines()
    if len(lines) != 5:
        raise ValueError("remote host identity is incomplete")
    keys = (
        "macOSProductVersion",
        "macOSBuildVersion",
        "architecture",
        "hardwareModel",
        "processor",
    )
    return dict(zip(keys, lines))


def require_host_identity(
    observed: dict[str, str], preregistration: dict[str, Any]
) -> None:
    expected = preregistration.get("nativeAppleHost")
    if not isinstance(expected, dict) or observed != expected:
        raise ValueError(f"native Apple host differs: {observed!r}")


def create_remote_directory() -> str:
    directory = run(
        [
            *SSH_PREFIX,
            REMOTE_HOST,
            "/usr/bin/mktemp -d /tmp/lg-case22-finite.XXXXXX",
        ]
    ).stdout.strip()
    if REMOTE_DIRECTORY_PATTERN.fullmatch(directory) is None:
        raise ValueError(f"remote temporary directory is unsafe: {directory!r}")
    return directory


def remove_remote_directory(directory: str) -> None:
    if REMOTE_DIRECTORY_PATTERN.fullmatch(directory) is None:
        raise ValueError("refusing to remove an unvalidated remote directory")
    run([*SSH_PREFIX, REMOTE_HOST, f"/bin/rm -rf -- {shlex.quote(directory)}"])


def compile_remote_invoker(repository: Path, directory: str) -> dict[str, str]:
    source_names = {
        "invoke_backdrop_margin_case22_provider_local_macos_26_6_1.c": "provider.c",
        "invoke_backdrop_margin_case22_provider_local_macos_26_6_1_arm64.s": "shim.s",
    }
    for local_name, remote_name in source_names.items():
        local_path = repository / "Analysis" / local_name
        run(
            [
                "scp",
                "-q",
                "-o",
                "BatchMode=yes",
                str(local_path),
                f"{REMOTE_HOST}:{directory}/{remote_name}",
            ]
        )
    compile_command = (
        f"cd {shlex.quote(directory)} && "
        "/Library/Developer/CommandLineTools/usr/bin/clang "
        "-std=c23 -O2 -Wall -Wextra -Wpedantic -Wconversion -Wshadow -Werror "
        "-isysroot /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk "
        "-mmacosx-version-min=26.0 provider.c shim.s -o provider-invoker && "
        "/usr/bin/shasum -a 256 provider-invoker && "
        "/Library/Developer/CommandLineTools/usr/bin/clang --version | "
        "/usr/bin/head -n 1"
    )
    lines = run([*SSH_PREFIX, REMOTE_HOST, compile_command]).stdout.splitlines()
    if len(lines) != 2 or not re.fullmatch(r"[0-9a-f]{64}  provider-invoker", lines[0]):
        raise ValueError("native invoker compilation identity is incomplete")
    return {
        "command": compile_command,
        "executableSHA256": lines[0].split()[0],
        "clangVersion": lines[1],
        "usesNixStorePath": False,
    }


def invoke_native_provider(
    directory: str, records: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    executable = f"{directory}/provider-invoker"
    try:
        process = subprocess.Popen(
            [*SSH_PREFIX, REMOTE_HOST, executable],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except OSError as error:
        raise ValueError(f"native provider launch failed: {error}") from error
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None

    uuid_line = process.stdout.readline().rstrip("\n")
    code_line = process.stdout.readline().rstrip("\n")
    expected_uuid_line = f"DESIGN_LIBRARY_UUID={EXPECTED_UUID}"
    if uuid_line != expected_uuid_line or not code_line.startswith("PROVIDER_CODE="):
        process.kill()
        raise ValueError("native provider identity header differs")
    try:
        provider_code = bytes.fromhex(code_line.removeprefix("PROVIDER_CODE="))
    except ValueError as error:
        process.kill()
        raise ValueError("native provider code header is not hexadecimal") from error
    code_sha256 = sha256_bytes(provider_code)
    if len(provider_code) != 984 or code_sha256 != EXPECTED_PROVIDER_CODE_SHA256:
        process.kill()
        raise ValueError("native provider code identity differs")

    for record in records:
        process.stdin.write(str(record["objectHex"]) + "\n")
    process.stdin.close()

    actual_records = []
    for ordinal, record in enumerate(records):
        line = process.stdout.readline().rstrip("\n")
        prefix = f"RESULT={ordinal}:"
        if not line.startswith(prefix):
            process.kill()
            raise ValueError(f"native result {ordinal} is missing or reordered")
        result_word = line.removeprefix(prefix)
        try:
            raw = bytes.fromhex(result_word)
        except ValueError as error:
            process.kill()
            raise ValueError(f"native result {ordinal} is not hexadecimal") from error
        if len(raw) != 8:
            process.kill()
            raise ValueError(f"native result {ordinal} width differs")
        actual_records.append(
            {
                "ordinal": ordinal,
                "objectSHA256": record["objectSHA256"],
                "predictedReturnRawLittleEndianHex": record[
                    "predictedReturnRawLittleEndianHex"
                ],
                "appleReturnRawLittleEndianHex": result_word,
                "returnMatchedBitwise": (
                    result_word == record["predictedReturnRawLittleEndianHex"]
                ),
            }
        )
    remaining_stdout = process.stdout.read()
    stderr = process.stderr.read()
    returncode = process.wait()
    if returncode != 0 or remaining_stdout or stderr:
        raise ValueError(
            "native provider process failed or emitted unexpected transport output: "
            f"status={returncode}, stdout={remaining_stdout!r}, stderr={stderr!r}"
        )
    return (
        {
            "designLibraryUUID": EXPECTED_UUID,
            "providerCodeByteCount": len(provider_code),
            "providerCodeSHA256": code_sha256,
            "processExitStatus": returncode,
            "stderrEmpty": True,
        },
        actual_records,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--llvm-mc", default="llvm-mc")
    arguments = parser.parse_args()
    repository = Path(__file__).resolve().parent.parent
    started = datetime.now(timezone.utc).isoformat()
    remote_directory = ""
    try:
        preregistration = load_json(arguments.preregistration)
        if (
            preregistration.get(
                "backdropMarginCase22ProviderFiniteBranchTransferPreregistrationSchemaVersion"
            )
            != 1
        ):
            raise ValueError("finite-branch preregistration schema differs")
        source_commit = require_clean_tracked_repository(repository)
        frozen_files = require_frozen_files(repository, preregistration)
        trace_sha256 = sha256_path(arguments.trace)
        if trace_sha256 != preregistration.get("retrospectiveTrace", {}).get("sha256"):
            raise ValueError("retrospective provider trace differs")
        trace = complete.load_json(arguments.trace)
        code = complete.provider_code(trace)
        instructions = complete.disassemble(code, arguments.llvm_mc)
        corpus = generator.generate(instructions)
        frozen_corpus = preregistration.get("frozenCorpus")
        if not isinstance(frozen_corpus, dict):
            raise ValueError("frozen corpus contract is missing")
        if (
            corpus["corpus"]["recordCount"] != frozen_corpus.get("recordCount")
            or corpus["corpus"]["rawObjectsAndPredictionsSHA256"]
            != frozen_corpus.get("rawObjectsAndPredictionsSHA256")
            or corpus["coverage"] != frozen_corpus.get("coverage")
        ):
            raise ValueError("regenerated finite corpus differs from preregistration")
        host = remote_host_identity()
        require_host_identity(host, preregistration)
        remote_directory = create_remote_directory()
        compilation = compile_remote_invoker(repository, remote_directory)
        provider, records = invoke_native_provider(
            remote_directory, corpus["corpus"]["records"]
        )
        result = {
            "backdropMarginCase22ProviderFiniteBranchTransferCaptureSchemaVersion": (
                CAPTURE_SCHEMA_VERSION
            ),
            "classification": (
                "prospective native Apple execution of a hash-frozen, "
                "output-blind finite-object provider branch corpus"
            ),
            "startedAtUTC": started,
            "completedAtUTC": datetime.now(timezone.utc).isoformat(),
            "inputs": {
                "sourceCommit": source_commit,
                "preregistration": {
                    "path": str(arguments.preregistration),
                    "sha256": sha256_path(arguments.preregistration),
                },
                "retrospectiveTrace": {
                    "path": str(arguments.trace),
                    "sha256": trace_sha256,
                    "usedOnlyForAuthenticatedCodeAndOutputBlindEmulation": True,
                },
                "frozenFiles": frozen_files,
            },
            "nativeAppleHost": host,
            "nativeCompilation": compilation,
            "provider": provider,
            "corpus": {
                "recordCount": len(records),
                "rawObjectsAndPredictionsSHA256": corpus["corpus"][
                    "rawObjectsAndPredictionsSHA256"
                ],
                "predictedCoverage": corpus["coverage"],
                "records": records,
            },
            "transport": {
                "remoteHost": REMOTE_HOST,
                "sshBatchMode": True,
                "providerExecutedOutsideNix": True,
                "appleOutputsConsultedForCandidateGeneration": False,
                "allRecordsDispatchedBeforeMatchClassification": True,
            },
        }
        arguments.output.write_text(
            json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        matches = sum(record["returnMatchedBitwise"] for record in records)
        print(f"CAPTURE_OUTPUT={arguments.output}")
        print(f"APPLE_RETURN_MATCHES={matches}/{len(records)}")
        return 0
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    finally:
        if remote_directory:
            remove_remote_directory(remote_directory)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
