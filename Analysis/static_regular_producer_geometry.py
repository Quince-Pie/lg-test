#!/usr/bin/env python3
"""Predict static regular-material backdrop crop and copy geometry."""

from __future__ import annotations

import math
import struct
from collections.abc import Mapping
from typing import Any


type JsonObject = dict[str, Any]

ALLOCATION_QUANTUM = 64
BACKDROP_SCALE = 0.25
BLEED_AMOUNT_SCALE = 0.35
BLUR_RADIUS = 4.0
BLEED_BLUR_RADIUS = 160.0
RADIUS_SCALE = 1.6
DOD_EXPANSION = 2.8
DOD_SIZE_INCREMENT = -5.6
MAXIMUM_ALIGNMENT_EXPONENT = 7


def float32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def numeric(value: object, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(name + " is not numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(name + " is not finite")
    return result


def align_up(value: int, quantum: int = ALLOCATION_QUANTUM) -> int:
    if value <= 0 or quantum <= 0:
        raise ValueError("allocation extent and quantum must be positive")
    return quantum * ((value + quantum - 1) // quantum)


def _crop_axis(lower: float, upper: float, window: float) -> JsonObject:
    clipped_lower = max(0.0, lower)
    clipped_upper = min(window, upper)
    if clipped_upper <= clipped_lower:
        raise ValueError("expanded shape does not intersect the window")
    scaled_lower = BACKDROP_SCALE * clipped_lower
    scaled_upper = BACKDROP_SCALE * clipped_upper
    crop_origin = math.ceil(scaled_lower)
    crop_upper = math.floor(scaled_upper)
    active_extent = crop_upper - crop_origin
    if active_extent <= 0:
        raise ValueError("producer crop is empty")
    return {
        "expandedBounds": [lower, upper],
        "clippedBounds": [clipped_lower, clipped_upper],
        "scaledBounds": [scaled_lower, scaled_upper],
        "cropOrigin": crop_origin,
        "cropUpperExclusive": crop_upper,
        "activeExtent": active_extent,
        "allocatedExtent": align_up(active_extent),
    }


def _mip_policy(active_extent: list[int], radius1: float) -> JsonObject:
    scaled_radius = float32(float32(radius1) * float32(RADIUS_SCALE))
    maximum_level_count = (
        math.floor(float32(math.log2(float32(max(active_extent))))) + 1
    )
    requested_level_count = (
        max(math.ceil(float32(math.log2(scaled_radius))), 0) + 1
        if scaled_radius != 0.0
        else 1
    )
    if requested_level_count == 1:
        requested_level_count = 2
    level_count = min(requested_level_count, maximum_level_count)
    alignment_exponent = min(level_count, MAXIMUM_ALIGNMENT_EXPONENT)
    return {
        "scaledRadius": scaled_radius,
        "maximumLevelCount": maximum_level_count,
        "requestedLevelCount": requested_level_count,
        "levelCount": level_count,
        "alignmentExponent": alignment_exponent,
        "alignmentScale": 1 << alignment_exponent,
    }


def _selected_axis(
    lower: int,
    extent: int,
    *,
    radius1: float,
    alignment: int,
) -> tuple[int, int]:
    expanded_lower = float(lower) + ((-float(radius1)) * DOD_EXPANSION)
    expanded_extent = math.fma(
        -float(radius1),
        DOD_SIZE_INCREMENT,
        float(extent),
    )
    reduced_lower = expanded_lower / alignment
    reduced_upper = reduced_lower + expanded_extent / alignment
    integer_lower = math.floor(reduced_lower)
    integer_upper = math.ceil(reduced_upper)
    return (
        integer_lower * alignment,
        (integer_upper - integer_lower) * alignment,
    )


def predict(geometry: Mapping[str, Any]) -> JsonObject:
    if geometry.get("shape") != "circle":
        raise ValueError("static regular model requires a circle")
    width = numeric(geometry.get("width"), "geometry width")
    height = numeric(geometry.get("height"), "geometry height")
    if width <= 0 or height != width:
        raise ValueError("static regular model requires a positive circle diameter")
    center_x = numeric(geometry.get("centerX"), "geometry centerX")
    center_y = numeric(geometry.get("centerY"), "geometry centerY")
    window_width = numeric(geometry.get("windowWidth"), "window width")
    window_height = numeric(geometry.get("windowHeight"), "window height")
    if window_width <= 0 or window_height <= 0:
        raise ValueError("window dimensions must be positive")

    margin = float32(float32(BLEED_AMOUNT_SCALE) * float32(width))
    half_width = width / 2.0
    x_axis = _crop_axis(
        center_x - half_width - margin,
        center_x + half_width + margin,
        window_width,
    )
    # Probe geometry is recorded in AppKit's top-left convention; producer
    # textures and their crop MVP use bottom-left coordinates.
    y_axis = _crop_axis(
        window_height - (center_y + half_width) - margin,
        window_height - (center_y - half_width) + margin,
        window_height,
    )
    crop_origin = [x_axis["cropOrigin"], y_axis["cropOrigin"]]
    active_extent = [x_axis["activeExtent"], y_axis["activeExtent"]]
    producer_extent = [
        x_axis["allocatedExtent"],
        y_axis["allocatedExtent"],
    ]

    radius1 = float32(
        float32(0.5 * max(2.0 * BLUR_RADIUS, BLEED_BLUR_RADIUS))
        * float32(BACKDROP_SCALE)
    )
    mip = _mip_policy(active_extent, radius1)
    selected_x = _selected_axis(
        crop_origin[0],
        active_extent[0],
        radius1=radius1,
        alignment=int(mip["alignmentScale"]),
    )
    selected_y = _selected_axis(
        crop_origin[1],
        active_extent[1],
        radius1=radius1,
        alignment=int(mip["alignmentScale"]),
    )
    selected_region = [
        selected_x[0],
        selected_y[0],
        selected_x[1],
        selected_y[1],
    ]
    copy_offset = [
        selected_region[0] - crop_origin[0],
        selected_region[1] - crop_origin[1],
    ]
    return {
        "material": "regular",
        "appearance": "light",
        "backdropScale": BACKDROP_SCALE,
        "inputBleedAmount": margin,
        "inputBlurRadius": BLUR_RADIUS,
        "inputBleedBlurRadius": BLEED_BLUR_RADIUS,
        "radius1": radius1,
        "cropOrigin": crop_origin,
        "activeExtent": active_extent,
        "textureCoordinateClamp": [
            0,
            0,
            active_extent[0] - 1,
            active_extent[1] - 1,
        ],
        "producerExtent": producer_extent,
        "mipPolicy": mip,
        "selectedRegion": selected_region,
        "destinationExtent": selected_region[2:],
        "copyOffset": copy_offset,
        "effectiveOrigin": [
            crop_origin[0] + copy_offset[0],
            crop_origin[1] + copy_offset[1],
        ],
        "axes": {"x": x_axis, "y": y_axis},
    }
