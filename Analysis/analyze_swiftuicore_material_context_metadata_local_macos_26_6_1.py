#!/usr/bin/env python3
"""Decode SwiftUI Material.Context metadata from the native dyld cache."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Mapping, Sequence, Tuple

import analyze_designlibrary_background_filter_metadata_local_macos_26_6_1 as metadata


SCHEMA_VERSION = 1
DYLD_INFO = Path("/Library/Developer/CommandLineTools/usr/bin/dyld_info")
FRAMEWORK = Path(
    "/System/Library/Frameworks/SwiftUICore.framework/Versions/A/SwiftUICore"
)
EXPECTED_UUID = "99606D45-C40A-3C69-AE51-5F0C4E32E531"
EXPECTED_PRODUCT_VERSION = "26.6.1"
EXPECTED_BUILD_VERSION = "25G76"
EXPECTED_HARDWARE_MODEL = "MacBookPro18,2"
SOURCE_RELATIVE_PATH = (
    "Analysis/analyze_swiftuicore_material_context_metadata_local_macos_26_6_1.py"
)

CONTEXT_FIELDS = (
    "environment",
    "role",
    "substrate",
    "shapeDimensions",
    "shapeMetrics",
)
CONTEXT_OFFSETS = (0, 16, 17, 24, 48)
CONTEXT_SIZE = 73
CONTEXT_STRIDE = 80
SHAPE_METRICS_FIELDS = (
    "minimumDistance",
    "minimumDistanceOfLargestArea",
    "maximumDistance",
)
SHAPE_METRICS_OFFSETS = (0, 8, 16)
SHAPE_METRICS_SIZE = 24
SHAPE_METRICS_STRIDE = 24


class AnalysisError(RuntimeError):
    """Raised when native Material.Context metadata differs."""


def run_dyld_info(arguments: Sequence[str]) -> str:
    completed = subprocess.run(
        [str(DYLD_INFO), *arguments, str(FRAMEWORK)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise AnalysisError(
            "dyld_info failed: " + " ".join(arguments) + "\n" + completed.stderr.strip()
        )
    return completed.stdout


def command_output(arguments: Sequence[str]) -> str:
    completed = subprocess.run(
        list(arguments),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise AnalysisError("command failed: " + " ".join(arguments))
    return completed.stdout.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def selected_descriptor(
    descriptors: Sequence[metadata.Descriptor],
    name: str,
    fields: Tuple[str, ...],
) -> metadata.Descriptor:
    matches = [
        descriptor
        for descriptor in descriptors
        if descriptor.name == name
        and tuple(field.name for field in descriptor.fields) == fields
    ]
    if len(matches) != 1:
        raise AnalysisError(
            "expected one exact {0} descriptor, found {1}".format(name, len(matches))
        )
    return matches[0]


def require_layout(
    record: Mapping[str, object],
    *,
    size: int,
    stride: int,
    offsets: Tuple[int, ...],
    label: str,
) -> None:
    value = record.get("metadata")
    if not isinstance(value, Mapping):
        raise AnalysisError(label + " has no static metadata")
    if (
        value.get("size") != size
        or value.get("stride") != stride
        or tuple(value.get("fieldOffsets", ())) != offsets
    ):
        raise AnalysisError(label + " layout differs")


def analyze() -> Mapping[str, object]:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise AnalysisError("analysis requires native arm64 macOS")
    product_version = command_output(("/usr/bin/sw_vers", "-productVersion"))
    build_version = command_output(("/usr/bin/sw_vers", "-buildVersion"))
    hardware_model = command_output(("/usr/sbin/sysctl", "-n", "hw.model"))
    if (
        product_version != EXPECTED_PRODUCT_VERSION
        or build_version != EXPECTED_BUILD_VERSION
        or hardware_model != EXPECTED_HARDWARE_MODEL
    ):
        raise AnalysisError("native host differs from the frozen target")

    uuid_output = run_dyld_info(("-uuid",))
    match = re.search(
        r"\b([0-9A-F]{8}(?:-[0-9A-F]{4}){3}-[0-9A-F]{12})\b",
        uuid_output,
    )
    if match is None or match.group(1) != EXPECTED_UUID:
        raise AnalysisError("SwiftUICore UUID differs")

    section_specs = (
        ("__TEXT", "__const"),
        ("__TEXT", "__constg_swiftt"),
        ("__TEXT", "__swift5_reflstr"),
        ("__TEXT", "__swift5_typeref"),
        ("__TEXT", "__swift5_fieldmd"),
        ("__AUTH_CONST", "__const"),
    )
    sections: Dict[Tuple[str, str], metadata.Section] = {}
    for segment, name in section_specs:
        sections[(segment, name)] = metadata.parse_section_bytes(
            segment,
            name,
            run_dyld_info(("-section_bytes", segment, name)),
        )
    memory = metadata.merged_memory(sections.values())
    type_labels = metadata.parse_type_labels(
        run_dyld_info(("-section", "__TEXT", "__swift5_typeref"))
    )
    descriptors = metadata.scan_descriptors(
        sections[("__TEXT", "__constg_swiftt")],
        memory,
        sections[("__TEXT", "__swift5_fieldmd")],
        type_labels,
    )
    slide, slide_match_count = metadata.infer_shared_cache_slide(
        sections[("__AUTH_CONST", "__const")], memory, descriptors
    )

    context = selected_descriptor(descriptors, "Context", CONTEXT_FIELDS)
    shape_metrics = selected_descriptor(
        descriptors, "ShapeMetrics", SHAPE_METRICS_FIELDS
    )
    context_metadata = metadata.metadata_for_descriptor(
        sections[("__AUTH_CONST", "__const")], memory, context, slide
    )
    shape_metrics_metadata = metadata.metadata_for_descriptor(
        sections[("__AUTH_CONST", "__const")], memory, shape_metrics, slide
    )
    context_record = metadata.descriptor_record(context, context_metadata)
    shape_metrics_record = metadata.descriptor_record(
        shape_metrics, shape_metrics_metadata
    )
    require_layout(
        context_record,
        size=CONTEXT_SIZE,
        stride=CONTEXT_STRIDE,
        offsets=CONTEXT_OFFSETS,
        label="Material.Context",
    )
    require_layout(
        shape_metrics_record,
        size=SHAPE_METRICS_SIZE,
        stride=SHAPE_METRICS_STRIDE,
        offsets=SHAPE_METRICS_OFFSETS,
        label="Material.ShapeMetrics",
    )
    context_types = tuple(field.type_reference or "" for field in context.fields)
    if (
        "7SwiftUI17EnvironmentValuesV" not in context_types[0]
        or "7SwiftUI9ShapeRoleO" not in context_types[1]
        or "7SwiftUI8MaterialVAAE9SubstrateO" not in context_types[2]
        or "12CoreGraphics7CGFloatV" not in context_types[3]
        or "7SwiftUI8MaterialVAAE12ShapeMetricsV" not in context_types[4]
    ):
        raise AnalysisError("Material.Context field types differ")

    source = Path(__file__).resolve()
    return {
        "swiftUICoreMaterialContextMetadataAnalysisSchemaVersion": SCHEMA_VERSION,
        "classification": (
            "native static Swift metadata decode of Material.Context and "
            "Material.ShapeMetrics; no Apple render value, Parameters payload, "
            "image, crop, pixel, or provider return selected a descriptor"
        ),
        "host": {
            "system": platform.system(),
            "machine": platform.machine(),
            "macOSProductVersion": product_version,
            "macOSBuildVersion": build_version,
            "hardwareModel": hardware_model,
        },
        "framework": {"path": str(FRAMEWORK), "uuid": EXPECTED_UUID},
        "tool": {
            "python": sys.version.split()[0],
            "dyldInfo": str(DYLD_INFO),
            "source": SOURCE_RELATIVE_PATH,
            "sourceSHA256": sha256(source),
        },
        "decodedStructDescriptorCount": len(descriptors),
        "sharedCacheSlide": "0x{0:x}".format(slide),
        "sharedCacheSlideMetadataMatchCount": slide_match_count,
        "materialContext": context_record,
        "shapeMetrics": shape_metrics_record,
        "controlledMutationBoundary": {
            "roleOptionalStorageOffset": 16,
            "substrateOptionalStorageOffset": 17,
            "shapeDimensionsOptionalStorageRange": [24, 41],
            "shapeDimensionsLowerBoundOffset": 24,
            "shapeDimensionsUpperBoundOffset": 32,
            "shapeDimensionsOptionalTagOffset": 40,
            "shapeMetricsOptionalStorageRange": [48, 73],
            "shapeMetricsOptionalTagOffset": 72,
        },
        "claims": {
            "materialContextLayoutEstablished": True,
            "shapeMetricsLayoutEstablished": True,
            "liveContextValueProductionEstablished": False,
            "contextToParametersValueLawEstablished": False,
            "independentWalleZeroByteFrameParityEstablished": False,
            "liquidGlassParityEstablished": False,
            "productionShaderChangeAuthorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    try:
        result = analyze()
    except (AnalysisError, metadata.AnalysisError) as error:
        print("ANALYSIS_ERROR: " + str(error), file=sys.stderr)
        return 1
    output = arguments.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(str(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
