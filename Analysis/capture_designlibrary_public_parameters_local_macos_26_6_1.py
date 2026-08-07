#!/usr/bin/env python3
"""Capture the exact public Configuration-to-Parameters table without a GUI."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import capture_designlibrary_parameters_mixer_basis_local_macos_26_6_1 as basis


SCHEMA_VERSION = 1
EXPECTED_PRODUCT_VERSION = "26.6.1"
EXPECTED_BUILD_VERSION = "25G76"
EXPECTED_HARDWARE_MODEL = "MacBookPro18,2"
EXPECTED_DESIGNLIBRARY_UUID = "1E980802-69F5-3E69-89EF-50088297FCF5"
EXPECTED_SWIFTUICORE_UUID = "99606D45-C40A-3C69-AE51-5F0C4E32E531"

DESIGNLIBRARY = Path(
    "/System/Library/PrivateFrameworks/DesignLibrary.framework/Versions/A/"
    "DesignLibrary"
)
SWIFTUICORE = Path(
    "/System/Library/Frameworks/SwiftUICore.framework/Versions/A/SwiftUICore"
)
DYLD_INFO = Path("/Library/Developer/CommandLineTools/usr/bin/dyld_info")
LLDB = Path("/Library/Developer/CommandLineTools/usr/bin/lldb")
XCRUN = Path("/usr/bin/xcrun")

PROBE_SOURCE_NAME = (
    "probe_designlibrary_public_parameters_local_macos_26_6_1.c"
)
BRIDGE_SOURCE_NAME = "invoke_designlibrary_public_parameters_arm64.S"
LLDB_ADAPTER_NAME = (
    "capture_designlibrary_public_parameters_local_macos_26_6_1_lldb.py"
)
BASIS_SOURCE_NAME = (
    "capture_designlibrary_parameters_mixer_basis_local_macos_26_6_1.py"
)
FRESH_PROCESS_COUNT = 3

STATIC_NAMES = (
    "regular",
    "clear",
    "control",
    "text",
    "identity",
    "menu",
    "dock",
    "appIcons",
    "widgets",
    "avplayer",
    "facetime",
    "controlCenter",
    "notificationCenter",
    "monogram",
    "bubbles",
    "focusBorder",
    "focusPlatter",
    "keyboard",
    "sidebar",
    "abuttedSidebar",
    "inspector",
    "loupe",
    "slider",
    "camera",
    "cartouchePopover",
    "siriSnippet",
    "carplayUltra",
)
MIX_NAMES = (
    "negative_quarter",
    "zero",
    "quarter",
    "half",
    "three_quarters",
    "one",
    "five_quarters",
)
MODIFIER_NAMES = (
    "color_scheme_light",
    "color_scheme_dark",
    "adaptive_false",
    "adaptive_true",
    "adaptive_light",
    "adaptive_dark",
    "adaptive_animatable_false",
    "adaptive_animatable_true",
)
EXPECTED_CASE_NAMES = tuple("static:" + name for name in STATIC_NAMES) + tuple(
    "mix:" + name for name in MIX_NAMES
) + tuple("modifier:" + name for name in MODIFIER_NAMES)

EXPECTED_LAYOUTS = {
    "Configuration": (144, 144, "0x00030007", 2147483647),
    "GlassMaterialProvider": (144, 144, "0x00030007", 2147483647),
    "State": (305, 312, "0x00030007", 2147483647),
    "Resolved": (321, 328, "0x00030007", 2147483647),
}
EXPECTED_PARAMETERS_BUILDER_SHA256 = (
    "07d9b8571ca8fed42e1d8e71b312f00a9c9713ce19f406d6f2c15a9d2403fde4"
)
EXPECTED_PARAMETERS_CALLER_SHA256 = (
    "ba0ad1081cece802ccd1e148660a542145f95bf57a92de4407a3fad55f4679c6"
)

TYPE_PATTERN = re.compile(
    r"^TYPE (\S+) size=(\d+) stride=(\d+) flags=(0x[0-9a-f]+) "
    r"extra_inhabitants=(\d+)$"
)
CASE_PATTERN = re.compile(
    r"^CASE index=(\d+) name=(\S+) layers=(0x[0-9a-f]+) allocation=(\d+)$"
)


class CaptureError(RuntimeError):
    """Raised when native evidence differs from the frozen contract."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def digest_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def native_environment(extra: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    environment = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": "C",
        "LC_ALL": "C",
    }
    for name in ("HOME", "USER", "LOGNAME", "SHELL", "TMPDIR"):
        value = os.environ.get(name)
        if value:
            environment[name] = value
    if extra is not None:
        environment.update(extra)
    if any("/nix/store" in value for value in environment.values()):
        raise CaptureError("native child environment contains a Nix store path")
    return environment


def run_command(
    arguments: Sequence[str],
    cwd: Optional[Path] = None,
    environment: Optional[Mapping[str, str]] = None,
) -> subprocess.CompletedProcess:
    completed = subprocess.run(
        list(arguments),
        cwd=str(cwd) if cwd is not None else None,
        env=dict(environment) if environment is not None else None,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise CaptureError(
            "command failed ({0}): {1}\nstdout:\n{2}\nstderr:\n{3}".format(
                completed.returncode,
                " ".join(arguments),
                completed.stdout.strip(),
                completed.stderr.strip(),
            )
        )
    return completed


def command_output(arguments: Sequence[str]) -> str:
    return run_command(arguments, environment=native_environment()).stdout


def require_uuid(path: Path, expected: str, label: str) -> None:
    output = command_output((str(DYLD_INFO), "-uuid", str(path)))
    if expected not in output:
        raise CaptureError(label + " UUID differs")


def parse_runtime_output(output: str) -> Mapping[str, object]:
    layouts: Dict[str, Tuple[int, int, str, int]] = {}
    cases: List[Mapping[str, object]] = []
    complete_count: Optional[int] = None
    for line in output.splitlines():
        match = TYPE_PATTERN.fullmatch(line)
        if match is not None:
            name = match.group(1)
            if name in layouts:
                raise CaptureError("duplicate runtime layout " + name)
            layouts[name] = (
                int(match.group(2)),
                int(match.group(3)),
                match.group(4),
                int(match.group(5)),
            )
            continue
        match = CASE_PATTERN.fullmatch(line)
        if match is not None:
            cases.append(
                {
                    "index": int(match.group(1)),
                    "name": match.group(2),
                    "allocationBytes": int(match.group(4)),
                }
            )
            continue
        if line.startswith("COMPLETE cases="):
            if complete_count is not None:
                raise CaptureError("duplicate native completion record")
            try:
                complete_count = int(line.removeprefix("COMPLETE cases="))
            except ValueError as error:
                raise CaptureError("invalid native completion record") from error
    if layouts != EXPECTED_LAYOUTS:
        raise CaptureError("native Swift runtime layouts differ")
    if complete_count != len(EXPECTED_CASE_NAMES):
        raise CaptureError("native completion count differs")
    if [case["index"] for case in cases] != list(range(len(EXPECTED_CASE_NAMES))):
        raise CaptureError("native case indices differ")
    if [case["name"] for case in cases] != list(EXPECTED_CASE_NAMES):
        raise CaptureError("native case order differs")
    if {case["allocationBytes"] for case in cases} != {96}:
        raise CaptureError("native Material.Layer array allocation differs")
    return {"layouts": layouts, "cases": cases}


def validate_trace(trace: Mapping[str, object]) -> List[bytes]:
    if (
        trace.get("designLibraryPublicParametersLocalMacOSLldbTraceSchemaVersion")
        != 1
        or trace.get("status") != "complete"
        or trace.get("processExitStatus") != 0
        or trace.get("failures") != []
        or trace.get("finalCaseCount") != len(EXPECTED_CASE_NAMES)
        or trace.get("finalCallCount") != len(EXPECTED_CASE_NAMES)
        or trace.get("finalPendingCallCount") != 0
        or trace.get("allExpectedCasesClosed") is not True
        or trace.get("allCallsReturned") is not True
    ):
        raise CaptureError("LLDB trace did not close cleanly")
    configuration = trace.get("configuration")
    if not isinstance(configuration, dict):
        raise CaptureError("LLDB trace configuration is absent")
    if (
        configuration.get("expectedCaseNames") != list(EXPECTED_CASE_NAMES)
        or configuration.get("parametersByteCount") != basis.PARAMETERS_BYTE_COUNT
        or configuration.get("capturedParametersUsedForSelection") is not False
        or configuration.get("capturedBuilderArgumentsUsedForSelection") is not False
        or configuration.get("allBuilderCallsInsideEveryFixedIntervalRetained")
        is not True
    ):
        raise CaptureError("LLDB trace prospective selection contract differs")
    module = trace.get("module")
    if (
        not isinstance(module, dict)
        or module.get("uuid") != EXPECTED_DESIGNLIBRARY_UUID
        or not str(module.get("path", "")).endswith("/DesignLibrary")
    ):
        raise CaptureError("LLDB DesignLibrary identity differs")
    builder = trace.get("parametersBuilder")
    caller = trace.get("parametersCaller")
    if (
        not isinstance(builder, dict)
        or builder.get("codeSHA256") != EXPECTED_PARAMETERS_BUILDER_SHA256
        or digest_bytes(bytes.fromhex(str(builder.get("hex", ""))))
        != EXPECTED_PARAMETERS_BUILDER_SHA256
        or not isinstance(caller, dict)
        or caller.get("codeSHA256") != EXPECTED_PARAMETERS_CALLER_SHA256
        or digest_bytes(bytes.fromhex(str(caller.get("hex", ""))))
        != EXPECTED_PARAMETERS_CALLER_SHA256
    ):
        raise CaptureError("LLDB exact builder/caller code identity differs")
    cases = trace.get("cases")
    calls = trace.get("calls")
    if not isinstance(cases, list) or not isinstance(calls, list):
        raise CaptureError("LLDB cases or calls are absent")
    if [case.get("name") for case in cases] != list(EXPECTED_CASE_NAMES):
        raise CaptureError("LLDB case order differs")
    if any(
        case.get("status") != "closed"
        or case.get("builderCallCount") != 1
        or case.get("callIndices") != [index]
        for index, case in enumerate(cases)
    ):
        raise CaptureError("LLDB per-case builder cardinality differs")
    payloads = []
    for index, call in enumerate(calls):
        if (
            call.get("index") != index
            or call.get("caseIndex") != index
            or call.get("indexWithinCase") != 0
            or call.get("status") != "returned"
        ):
            raise CaptureError("LLDB builder call topology differs")
        try:
            payload = bytes.fromhex(str(call.get("parametersRawHex", "")))
        except ValueError as error:
            raise CaptureError("LLDB Parameters bytes are invalid") from error
        if (
            len(payload) != basis.PARAMETERS_BYTE_COUNT
            or digest_bytes(payload) != call.get("parametersRawSHA256")
        ):
            raise CaptureError("LLDB Parameters payload identity differs")
        payloads.append(payload)
    return payloads


def run_lldb_capture(
    executable: Path,
    adapter: Path,
    run_directory: Path,
) -> Tuple[Mapping[str, object], Mapping[str, object], str]:
    trace_path = run_directory / "trace.json"
    runtime_stdout_path = run_directory / "runtime-stdout.log"
    runtime_stderr_path = run_directory / "runtime-stderr.log"
    lldb_log_path = run_directory / "lldb.log"
    environment = native_environment(
        {
            "LG_DESIGNLIBRARY_PUBLIC_PARAMETERS_TRACE_OUTPUT": str(trace_path),
        }
    )
    module_name = adapter.stem
    arguments = (
        str(LLDB),
        "-b",
        "-o",
        "target create " + str(executable),
        "-o",
        "settings set target.output-path " + str(runtime_stdout_path),
        "-o",
        "settings set target.error-path " + str(runtime_stderr_path),
        "-o",
        "command script import " + str(adapter),
        "-o",
        "run",
        "-o",
        "script import {0} as capture; capture.finalize()".format(module_name),
        "-o",
        "quit",
    )
    completed = run_command(arguments, cwd=run_directory, environment=environment)
    lldb_log_path.write_text(
        completed.stdout + completed.stderr,
        encoding="utf-8",
    )
    if not trace_path.is_file():
        raise CaptureError("LLDB trace was not written")
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    runtime_stdout = runtime_stdout_path.read_text(encoding="utf-8")
    runtime_stderr = runtime_stderr_path.read_text(encoding="utf-8")
    if runtime_stderr:
        raise CaptureError("native probe wrote to stderr: " + runtime_stderr.strip())
    runtime = parse_runtime_output(runtime_stdout)
    validate_trace(trace)
    return trace, runtime, digest_bytes((completed.stdout + completed.stderr).encode())


def capture(output_path: Path) -> Mapping[str, object]:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise CaptureError("capture requires native arm64 macOS")
    if basis.PARAMETERS_BYTE_COUNT != 0x401:
        raise CaptureError("imported Parameters byte count differs")
    product_version = command_output(("/usr/bin/sw_vers", "-productVersion")).strip()
    build_version = command_output(("/usr/bin/sw_vers", "-buildVersion")).strip()
    hardware_model = command_output(("/usr/sbin/sysctl", "-n", "hw.model")).strip()
    if (
        product_version != EXPECTED_PRODUCT_VERSION
        or build_version != EXPECTED_BUILD_VERSION
        or hardware_model != EXPECTED_HARDWARE_MODEL
    ):
        raise CaptureError("host differs from the frozen target profile")
    require_uuid(DESIGNLIBRARY, EXPECTED_DESIGNLIBRARY_UUID, "DesignLibrary")
    require_uuid(SWIFTUICORE, EXPECTED_SWIFTUICORE_UUID, "SwiftUICore")

    analysis_directory = Path(__file__).resolve().parent
    capture_source = Path(__file__).resolve()
    probe_source = analysis_directory / PROBE_SOURCE_NAME
    bridge_source = analysis_directory / BRIDGE_SOURCE_NAME
    adapter = analysis_directory / LLDB_ADAPTER_NAME
    basis_source = analysis_directory / BASIS_SOURCE_NAME
    required_sources = (
        capture_source,
        probe_source,
        bridge_source,
        adapter,
        basis_source,
    )
    if any(not source.is_file() for source in required_sources):
        raise CaptureError("capture source set is incomplete")
    if any("/nix/store" in str(source) for source in required_sources):
        raise CaptureError("capture source path contains a Nix store path")

    traces: List[Mapping[str, object]] = []
    runtime_records: List[Mapping[str, object]] = []
    lldb_log_sha256: List[str] = []
    with tempfile.TemporaryDirectory(prefix="lg-public-parameters-") as temporary:
        temporary_directory = Path(temporary)
        executable = temporary_directory / "probe"
        run_command(
            (
                str(XCRUN),
                "clang",
                "-std=c2x",
                "-arch",
                "arm64",
                "-O2",
                "-g",
                "-Wall",
                "-Wextra",
                "-Wconversion",
                "-Wsign-conversion",
                "-Werror",
                str(probe_source),
                str(bridge_source),
                "-o",
                str(executable),
            ),
            cwd=temporary_directory,
            environment=native_environment(),
        )
        executable_bytes = executable.read_bytes()
        if b"/nix/store" in executable_bytes:
            raise CaptureError("native probe embeds a Nix store path")
        executable_sha256 = digest_bytes(executable_bytes)
        for run_index in range(FRESH_PROCESS_COUNT):
            run_directory = temporary_directory / "run-{0}".format(run_index)
            run_directory.mkdir()
            trace, runtime, log_digest = run_lldb_capture(
                executable,
                adapter,
                run_directory,
            )
            traces.append(trace)
            runtime_records.append(runtime)
            lldb_log_sha256.append(log_digest)

    raw_payloads_by_run = [validate_trace(trace) for trace in traces]
    normalized_by_run = [
        [basis.normalize_parameters(payload) for payload in payloads]
        for payloads in raw_payloads_by_run
    ]
    if any(
        normalized != normalized_by_run[0]
        for normalized in normalized_by_run[1:]
    ):
        raise CaptureError(
            "normalized public Parameters differ across fresh processes"
        )
    if any(runtime != runtime_records[0] for runtime in runtime_records[1:]):
        raise CaptureError("native runtime records differ across fresh processes")

    unique_parameters: Dict[str, Mapping[str, object]] = {}
    case_records = []
    for index, name in enumerate(EXPECTED_CASE_NAMES):
        normalized = normalized_by_run[0][index]
        normalized_digest = digest_bytes(normalized)
        raw_digests = [
            digest_bytes(raw_payloads[index])
            for raw_payloads in raw_payloads_by_run
        ]
        if normalized_digest not in unique_parameters:
            unique_parameters[normalized_digest] = {
                "normalizedHex": normalized.hex(),
                "caseNames": [],
            }
        unique_parameters[normalized_digest]["caseNames"].append(name)
        category, public_name = name.split(":", 1)
        case_records.append(
            {
                "index": index,
                "name": public_name,
                "category": category,
                "qualifiedName": name,
                "normalizedParametersSHA256": normalized_digest,
                "rawParametersSHA256ByFreshProcess": raw_digests,
                "rawParametersStableAcrossFreshProcesses": (
                    len(set(raw_digests)) == 1
                ),
            }
        )

    result = {
        "designLibraryPublicParametersCaptureSchemaVersion": SCHEMA_VERSION,
        "classification": (
            "direct native invocation of Apple's exported Configuration, "
            "provider, EnvironmentValues, Material.Context, and resolveLayers "
            "Swift ABIs under an exact-code LLDB gate; default context only; "
            "no GUI session, application render, image, crop, or Nix store path"
        ),
        "host": {
            "system": platform.system(),
            "machine": platform.machine(),
            "macOSProductVersion": product_version,
            "macOSBuildVersion": build_version,
            "hardwareModel": hardware_model,
        },
        "frameworks": {
            "DesignLibrary": {
                "path": str(DESIGNLIBRARY),
                "uuid": EXPECTED_DESIGNLIBRARY_UUID,
            },
            "SwiftUICore": {
                "path": str(SWIFTUICORE),
                "uuid": EXPECTED_SWIFTUICORE_UUID,
            },
        },
        "tool": {
            "python": sys.version.split()[0],
            "clang": command_output((str(XCRUN), "clang", "--version")).splitlines()[0],
            "lldb": command_output((str(LLDB), "--version")).splitlines()[0],
            "captureSource": "Analysis/" + capture_source.name,
            "captureSourceSHA256": sha256(capture_source),
            "probeSource": "Analysis/" + probe_source.name,
            "probeSourceSHA256": sha256(probe_source),
            "assemblyBridge": "Analysis/" + bridge_source.name,
            "assemblyBridgeSHA256": sha256(bridge_source),
            "lldbAdapter": "Analysis/" + adapter.name,
            "lldbAdapterSHA256": sha256(adapter),
            "parametersBasisSource": "Analysis/" + basis_source.name,
            "parametersBasisSourceSHA256": sha256(basis_source),
            "probeExecutableSHA256": executable_sha256,
            "probeExecutableContainsNixStorePath": False,
            "freshProcessCount": FRESH_PROCESS_COUNT,
            "lldbLogSHA256ByFreshProcess": lldb_log_sha256,
        },
        "exactCodeGate": {
            "parametersBuilderModuleOffset": 0x120B4C,
            "parametersBuilderByteCount": 0x1334,
            "parametersBuilderCodeSHA256": EXPECTED_PARAMETERS_BUILDER_SHA256,
            "parametersCallerModuleOffset": 0x11F1BC,
            "parametersCallerByteCount": 0xD7C,
            "parametersCallerCodeSHA256": EXPECTED_PARAMETERS_CALLER_SHA256,
            "parametersCallerReturnOffset": 0xD38,
        },
        "parametersLayout": {
            "byteCount": basis.PARAMETERS_BYTE_COUNT,
            "semanticByteCount": len(basis.SEMANTIC_BYTE_OFFSETS),
            "normalizedPaddingRanges": [
                [start, end] for start, end in basis.SEMANTIC_PADDING_RANGES
            ],
        },
        "cases": case_records,
        "uniqueNormalizedParameters": unique_parameters,
        "measuredInvariants": {
            "staticConfigurationCount": len(STATIC_NAMES),
            "regularToClearMixCount": len(MIX_NAMES),
            "regularModifierCount": len(MODIFIER_NAMES),
            "totalCaseCount": len(EXPECTED_CASE_NAMES),
            "parametersBuildsPerCase": 1,
            "materialLayerArrayAllocationBytes": 96,
            "uniqueNormalizedParametersCount": len(unique_parameters),
            "freshProcessSemanticStabilityEstablished": True,
            "everyFixedIntervalRetained": True,
            "capturedParametersUsedForSelection": False,
            "capturedBuilderArgumentsUsedForSelection": False,
        },
        "claims": {
            "defaultContextPublicConfigurationToParametersTableEstablished": True,
            "defaultContextPublicMixToParametersTableEstablished": True,
            "defaultContextPublicModifierToParametersTableEstablished": True,
            "liveSwiftUIEnvironmentSelectionLawEstablished": False,
            "liveTransitionProgressProductionLawEstablished": False,
            "generalIntegerCropAllocationPolicyEstablished": False,
            "retinaCompositorColorLawEstablished": False,
            "independentWalleZeroByteFrameParityEstablished": False,
            "liquidGlassParityEstablished": False,
            "productionShaderChangeAuthorized": False,
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    try:
        capture(arguments.output.resolve())
    except CaptureError as error:
        print("CAPTURE_ERROR: " + str(error), file=sys.stderr)
        return 1
    print(str(arguments.output.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
