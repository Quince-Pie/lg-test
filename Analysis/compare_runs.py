#!/usr/bin/env python3
"""Quantify repeatability between two validated GlassCapture artifacts."""

import argparse
import json
import platform
import statistics
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from measure import Artifact, Measurements, file_sha256


type JsonObject = dict[str, Any]
type RecordIndex = dict[str, JsonObject]


def reference_records(manifest: JsonObject) -> RecordIndex:
    return {
        str(record["background"]): record for record in manifest.get("references", [])
    }


def static_records(manifest: JsonObject) -> RecordIndex:
    return {
        "|".join(
            str(record[field])
            for field in ("background", "scene", "overlay", "appearance")
        ): record
        for record in manifest.get("captures", [])
    }


def sweep_records(manifest: JsonObject) -> RecordIndex:
    result: RecordIndex = {}
    traversals = (
        ("forwardCold", "frames"),
        ("reverseWarm", "reverseFrames"),
        ("forwardColdRepeat", "repeatFrames"),
    )
    for sequence in manifest.get("sweepSequences", []):
        for traversal, field in traversals:
            for record in sequence.get(field, []):
                key = "|".join(
                    (
                        str(sequence["id"]),
                        traversal,
                        str(record["index"]),
                    )
                )
                result[key] = record
    return result


def dynamic_endpoint_records(manifest: JsonObject) -> RecordIndex:
    result: RecordIndex = {}
    for sequence in manifest.get("dynamicSequences", []):
        frames = sequence.get("frames", [])
        if frames:
            initial = min(frames, key=lambda frame: int(frame["index"]))
            result[f"{sequence['id']}|initial"] = initial
        post_settle = sequence.get("postSettleFrame")
        if isinstance(post_settle, dict):
            result[f"{sequence['id']}|postSettle"] = post_settle
    return result


def distribution(values: list[int]) -> JsonObject:
    if not values:
        return {
            "minimum": 0,
            "median": 0,
            "p95": 0,
            "maximum": 0,
        }
    return {
        "minimum": min(values),
        "median": statistics.median(values),
        "p95": float(np.percentile(values, 95)),
        "maximum": max(values),
    }


@dataclass(slots=True)
class RunComparator:
    left: Artifact
    right: Artifact

    def artifact_summary(self, artifact: Artifact) -> JsonObject:
        manifest = artifact.manifest
        return {
            "file": artifact.path.name,
            "sha256": file_sha256(artifact.path) if artifact.path.is_file() else None,
            "schemaVersion": manifest.get("schemaVersion"),
            "rigVersion": manifest.get("rigVersion"),
            "ciCommit": manifest.get("ciCommit"),
            "osVersion": manifest.get("osVersion"),
            "osBuild": manifest.get("osBuild"),
            "architecture": manifest.get("architecture"),
            "hostModel": manifest.get("hostModel"),
            "runnerImageVersion": manifest.get("runnerImageVersion"),
            "xcodeVersion": manifest.get("xcodeVersion"),
            "backingScaleFactor": manifest.get("backingScaleFactor"),
            "requestedSuite": manifest.get("requestedSuite"),
            "dynamicDurationSeconds": manifest.get("dynamicDurationSeconds"),
            "transitionOriginNormalized": manifest.get("transitionOriginNormalized"),
            "reduceTransparency": manifest.get("reduceTransparency"),
            "increaseContrast": manifest.get("increaseContrast"),
            "reduceMotion": manifest.get("reduceMotion"),
            "windowKey": manifest.get("windowKey"),
            "applicationActive": manifest.get("applicationActive"),
        }

    def compare_records(
        self,
        left_records: RecordIndex,
        right_records: RecordIndex,
    ) -> JsonObject:
        left_keys = left_records.keys()
        right_keys = right_records.keys()
        shared = sorted(left_keys & right_keys)
        left_only = sorted(left_keys - right_keys)
        right_only = sorted(right_keys - left_keys)
        exact: list[str] = []
        differences: list[JsonObject] = []

        for key in shared:
            left = left_records[key]
            right = right_records[key]
            left_hash = left.get("pixelSha256")
            right_hash = right.get("pixelSha256")
            if isinstance(left_hash, str) and left_hash and left_hash == right_hash:
                exact.append(key)
                continue
            difference = Measurements.pixel_difference(
                self.left.code_image(str(left["file"])),
                self.right.code_image(str(right["file"])),
            )
            differences.append({"key": key, **difference})

        changed_pixels = [
            int(difference["changedPixels"])
            for difference in differences
            if "changedPixels" in difference
        ]
        return {
            "leftCases": len(left_records),
            "rightCases": len(right_records),
            "sharedCases": len(shared),
            "exactCases": len(exact),
            "differingCases": len(differences),
            "leftOnly": left_only,
            "rightOnly": right_only,
            "changedPixels": distribution(changed_pixels),
            "maximumChangedFraction": max(
                (
                    float(difference.get("changedFraction", 0))
                    for difference in differences
                ),
                default=0,
            ),
            "maximumChannelDelta": max(
                (
                    int(difference.get("maximumChannelDelta", 0))
                    for difference in differences
                ),
                default=0,
            ),
            "maximumMeanAbsoluteChannelDelta": max(
                (
                    float(difference.get("meanAbsoluteChannelDelta", 0))
                    for difference in differences
                ),
                default=0,
            ),
            "differences": differences,
        }

    def run(self) -> JsonObject:
        return {
            "comparisonSchemaVersion": 1,
            "comparisonImplementation": {
                "file": "Analysis/compare_runs.py",
                "sha256": file_sha256(Path(__file__).resolve()),
                "python": platform.python_version(),
                "numpy": np.__version__,
            },
            "leftArtifact": self.artifact_summary(self.left),
            "rightArtifact": self.artifact_summary(self.right),
            "references": self.compare_records(
                reference_records(self.left.manifest),
                reference_records(self.right.manifest),
            ),
            "staticCaptures": self.compare_records(
                static_records(self.left.manifest),
                static_records(self.right.manifest),
            ),
            "dynamicEndpoints": self.compare_records(
                dynamic_endpoint_records(self.left.manifest),
                dynamic_endpoint_records(self.right.manifest),
            ),
            "sweepStates": self.compare_records(
                sweep_records(self.left.manifest),
                sweep_records(self.right.manifest),
            ),
            "interpretation": (
                "Cross-run differences are a measured Apple repeatability envelope, "
                "not a parity tolerance that another renderer may spend."
            ),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare shared pixels in two validated GlassCapture artifacts."
    )
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with (
        closing(Artifact.open(args.left)) as left,
        closing(Artifact.open(args.right)) as right,
    ):
        report = RunComparator(left, right).run()

    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report is None:
        print(encoded, end="")
    else:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded, encoding="utf-8")
        print(args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
