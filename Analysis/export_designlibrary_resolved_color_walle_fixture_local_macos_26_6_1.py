#!/usr/bin/env python3
"""Export every proved Color.Resolved case as an immutable Walle fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import struct
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import analyze_designlibrary_resolved_color_mixer_local_macos_26_6_1 as resolved


type JsonObject = dict[str, Any]

ANALYZER_SHA256 = "40509f1210c45588791e39d989d6409fa7496b171a250919f1151ed0a4974ed5"
CANONICAL_RESULT_SHA256 = "4a58f3434e13625ab7ce5ff4762e50df1600f6d09e173b950f0480418b4bf683"
SWIFT_PROBE_SHA256 = "770867a91881fbba8d5ae34802d71e9b5f9b63e4ba0e87ca7fe02c02b958ba09"
EXPECTED_OUTPUT_STREAM_SHA256 = (
    "096f07a965544de4f41d83fd532eaa397c887d8992e30e4ff67e6e624857a4b9"
)
MAGIC = b"WLGRCV1\0"
VERSION = 1
RECORD_SIZE = 104


class ExportError(RuntimeError):
    """Raised when fixture provenance or Apple output differs."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def command_output(arguments: tuple[str, ...]) -> str:
    completed = subprocess.run(
        arguments,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise ExportError("command failed: " + " ".join(arguments))
    return completed.stdout.strip()


def use_native_apple_subprocess_environment() -> None:
    retained = {
        name: os.environ[name]
        for name in ("HOME", "LOGNAME", "SSH_AUTH_SOCK", "TMPDIR", "USER")
        if name in os.environ
    }
    os.environ.clear()
    os.environ.update(retained)
    os.environ["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    os.environ["DEVELOPER_DIR"] = "/Library/Developer/CommandLineTools"


def export(output_directory: Path) -> JsonObject:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ExportError("fixture export requires native arm64 macOS")
    product_version = command_output(("/usr/bin/sw_vers", "-productVersion"))
    build_version = command_output(("/usr/bin/sw_vers", "-buildVersion"))
    hardware_model = command_output(("/usr/sbin/sysctl", "-n", "hw.model"))
    if (
        product_version != "26.6.1"
        or build_version != "25G76"
        or hardware_model != "MacBookPro18,2"
    ):
        raise ExportError("fixture host differs")

    analysis = Path(__file__).resolve().parent
    analyzer = analysis / "analyze_designlibrary_resolved_color_mixer_local_macos_26_6_1.py"
    canonical = analysis / "designlibrary_resolved_color_mixer_local_macos_26_6_1_result.json"
    swift_source = analysis / resolved.SWIFT_PROBE_NAME
    expected_sources = (
        (analyzer, ANALYZER_SHA256),
        (canonical, CANONICAL_RESULT_SHA256),
        (swift_source, SWIFT_PROBE_SHA256),
    )
    for path, expected in expected_sources:
        if sha256_file(path) != expected:
            raise ExportError("source SHA-256 differs for " + path.name)

    use_native_apple_subprocess_environment()
    samples = resolved.sample_set()
    with tempfile.TemporaryDirectory(prefix="lg-resolved-color-fixture-") as directory:
        executable = Path(directory) / "resolved-color-components"
        completed = subprocess.run(
            (
                "/usr/bin/xcrun",
                "swiftc",
                "-O",
                str(swift_source),
                "-o",
                str(executable),
            ),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if completed.returncode != 0:
            raise ExportError(
                "native Swift fixture probe build failed: "
                + completed.stderr.decode("utf-8", errors="replace").strip()
            )

        inspect_requests = [
            request
            for sample in samples
            for request in (
                ("inspect", sample.from_words),
                ("inspect", sample.to_words),
            )
        ]
        inspected = resolved.swift_batch(executable, inspect_requests)
        mixed = [
            resolved.mixed_public_components(
                inspected[index * 2],
                inspected[index * 2 + 1],
                sample.fraction_bits,
            )
            for index, sample in enumerate(samples)
        ]
        outputs = resolved.swift_batch(
            executable,
            [("construct", components) for components in mixed],
        )

    output_stream = b"".join(struct.pack("<4I", *value) for value in outputs)
    if sha256_bytes(output_stream) != EXPECTED_OUTPUT_STREAM_SHA256:
        raise ExportError("full public output stream differs from the proved private stream")

    records = bytearray()
    labels = []
    for index, (sample, public, components, output) in enumerate(
        zip(samples, inspected[::2], mixed, outputs, strict=True)
    ):
        to_public = inspected[index * 2 + 1]
        record = struct.pack(
            "<8IQ16I",
            *sample.from_words,
            *sample.to_words,
            sample.fraction_bits,
            *public,
            *to_public,
            *components,
            *output,
        )
        if len(record) != RECORD_SIZE:
            raise ExportError("fixture record size differs")
        records.extend(record)
        labels.append(sample.label)

    header = struct.pack(
        "<8s4I",
        MAGIC,
        VERSION,
        len(samples),
        RECORD_SIZE,
        0,
    )
    fixture = header + records
    output_directory.mkdir(parents=True, exist_ok=False)
    fixture_path = output_directory / "resolved_color_v1_fixture.bin"
    manifest_path = output_directory / "resolved_color_v1_fixture.json"
    fixture_path.write_bytes(fixture)
    manifest: JsonObject = {
        "walleResolvedColorFixtureManifestSchemaVersion": 1,
        "classification": (
            "all 205 deterministic cases reconstructed through the public "
            "SwiftUI Color.Resolved getters and sRGB constructor after the "
            "same public composition was proved bitwise equal to the complete "
            "private DesignLibrary helper"
        ),
        "host": {
            "system": platform.system(),
            "machine": platform.machine(),
            "macOSProductVersion": product_version,
            "macOSBuildVersion": build_version,
            "hardwareModel": hardware_model,
        },
        "fixture": {
            "path": fixture_path.name,
            "magic": MAGIC.rstrip(b"\0").decode("ascii"),
            "version": VERSION,
            "headerSize": len(header),
            "recordSize": RECORD_SIZE,
            "recordCount": len(samples),
            "byteCount": len(fixture),
            "sha256": sha256_bytes(fixture),
            "labels": labels,
        },
        "coverage": {
            "curatedCases": len(samples) - resolved.RANDOM_SAMPLE_COUNT,
            "randomCases": resolved.RANDOM_SAMPLE_COUNT,
            "randomSeed": f"0x{resolved.RANDOM_SEED:08x}",
            "perRecord": [
                "from raw linear RGBA words",
                "to raw linear RGBA words",
                "binary64 fraction word",
                "from public sRGB RGBA words",
                "to public sRGB RGBA words",
                "mixed public sRGB RGBA words",
                "reconstructed output raw linear RGBA words",
            ],
            "outputStreamSHA256": sha256_bytes(output_stream),
            "provedPrivateOutputStreamSHA256": EXPECTED_OUTPUT_STREAM_SHA256,
        },
        "provenanceSHA256": {
            "analyzer": ANALYZER_SHA256,
            "canonicalResult": CANONICAL_RESULT_SHA256,
            "swiftProbe": SWIFT_PROBE_SHA256,
            "exporter": sha256_file(Path(__file__).resolve()),
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_directory", type=Path)
    arguments = parser.parse_args()
    try:
        result = export(arguments.output_directory)
    except (ExportError, resolved.AnalysisError) as error:
        print("fixture export failed: " + str(error))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
