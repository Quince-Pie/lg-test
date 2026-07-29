"""Canonical metadata for versioned Liquid Glass identification probes."""

from typing import Any

import numpy as np
from numpy.typing import NDArray


type CodeImage = NDArray[np.uint8]
type UInt32Image = NDArray[np.uint32]


ADAPTIVE_SPATIAL_PROBES: dict[str, dict[str, Any]] = {
    **{
        f"context-rgb-grid-b{block_size:04d}-train": {
            "probeKind": "independent-rgb-palette-blocks",
            "role": "training",
            "blockSizePixels": block_size,
            "levels": [0, 32, 64, 96, 128, 160, 192, 224, 255],
            "seed": "0x7308c145",
        }
        for block_size in (4, 16, 64, 256)
    },
    **{
        f"context-rgb-midpoint-b{block_size:04d}-holdout": {
            "probeKind": "source-safe-rgb-palette-blocks",
            "role": "holdout",
            "blockSizePixels": block_size,
            "levels": [16, 48, 80, 112, 144, 176, 208, 240],
            "seed": "0x49f7b8c3",
            "combinationCount": 507,
            "excludedSourceRoundTripRgbCodes": [
                [16, 240, 144],
                [16, 240, 176],
                [16, 240, 208],
                [16, 208, 240],
                [16, 240, 240],
            ],
        }
        for block_size in (4, 16, 64, 256)
    },
    "context-rgb-grid-b0016-shifted-check": {
        "probeKind": "periodically-shifted-rgb-palette-blocks",
        "role": "translation-equivariance-check",
        "blockSizePixels": 16,
        "levels": [0, 32, 64, 96, 128, 160, 192, 224, 255],
        "seed": "0x7308c145",
        "sourceShiftPixels": [37, 53],
    },
    **{
        f"noise-{channel}-m{center:03d}-a032-b0016-{role}": {
            "probeKind": f"{channel}-binary-blocks",
            "role": "training" if role == "train" else "holdout",
            "blockSizePixels": 16,
            "centerCode": center,
            "amplitudeCodes": 32,
            "levels": [center - 32, center + 32],
            "seed": "0x31415926" if role == "train" else "0xa7f43c19",
        }
        for channel in ("gray", "rgb")
        for center in (64, 128, 192)
        for role in ("train", "holdout")
    },
}

CLEAR_KERNEL_PROBES: dict[str, dict[str, Any]] = {
    f"noise-rgb-a064-kernel-{name_role}-{index:02d}": {
        "probeKind": "independent-rgb-binary-pixels",
        "role": metadata_role,
        "blockSizePixels": 1,
        "centerCode": 128,
        "amplitudeCodes": 64,
        "levels": [64, 192],
        "seed": f"0x{seed:08x}",
    }
    for name_role, metadata_role, seeds in (
        ("train", "training", (0xD1B54A32, 0x94D049BB, 0x8538ECB5, 0xC2B2AE35)),
        ("holdout", "holdout", (0x27D4EB2F, 0x165667B1)),
    )
    for index, seed in enumerate(seeds)
}

CLEAR_TOMOGRAPHY_AMPLITUDES = (17, 31, 47, 64)
CLEAR_TOMOGRAPHY_PROBES: dict[str, dict[str, Any]] = {
    f"noise-rgb-a{amplitude:03d}-tomography-{name_role}-{index:02d}": {
        "probeKind": "independent-rgb-binary-pixels",
        "role": metadata_role,
        "blockSizePixels": 1,
        "centerCode": 128,
        "amplitudeCodes": amplitude,
        "levels": [128 - amplitude, 128 + amplitude],
        "seed": f"0x{seed:08x}",
        "amplitudeGroup": f"{name_role}-{index:02d}",
    }
    for name_role, metadata_role, seeds in (
        ("train", "training", (0xD1B54A32, 0x94D049BB, 0x8538ECB5, 0xC2B2AE35)),
        ("holdout", "holdout", (0xA24BAED4, 0x9FB21C65)),
    )
    for index, seed in enumerate(seeds)
    for amplitude in (
        (17, 31, 47) if metadata_role == "training" else CLEAR_TOMOGRAPHY_AMPLITUDES
    )
}

CLEAR_AMPLITUDE_SWEEP_TRAINING_AMPLITUDES = tuple(
    amplitude
    for amplitude in range(1, 64)
    if amplitude not in (17, 31, 47)
)
CLEAR_AMPLITUDE_SWEEP_HOLDOUT_AMPLITUDES = (
    2,
    7,
    14,
    23,
    32,
    40,
    48,
    56,
    63,
)
CLEAR_AMPLITUDE_SWEEP_PROBES: dict[str, dict[str, Any]] = {
    f"noise-rgb-a{amplitude:03d}-sweep-{name_role}-{index:02d}": {
        "probeKind": "independent-rgb-binary-pixels",
        "role": metadata_role,
        "blockSizePixels": 1,
        "centerCode": 128,
        "amplitudeCodes": amplitude,
        "levels": [128 - amplitude, 128 + amplitude],
        "seed": f"0x{seed:08x}",
        "amplitudeGroup": f"{name_role}-{index:02d}",
        "scenes": scenes,
    }
    for name_role, metadata_role, seeds, amplitudes, scenes in (
        (
            "train",
            "training",
            (0xD1B54A32,),
            CLEAR_AMPLITUDE_SWEEP_TRAINING_AMPLITUDES,
            ("circle-4000-center",),
        ),
        (
            "holdout",
            "holdout",
            (0xA24BAED4, 0x9FB21C65),
            CLEAR_AMPLITUDE_SWEEP_HOLDOUT_AMPLITUDES,
            (
                "circle-4000-center",
                "circle-6000-upper-left",
                "rect-6000x4000-r000-center",
                "rect-4000x6000-r000-center",
            ),
        ),
    )
    for index, seed in enumerate(seeds)
    for amplitude in amplitudes
}

CLEAR_GRID_BASIS_BOUNDARY_AMPLITUDES = (
    1,
    2,
    3,
    15,
    16,
    17,
    31,
    32,
    33,
    47,
    48,
    49,
    63,
    64,
)
CLEAR_GRID_BASIS_CELL_AMPLITUDES = (1, 17, 32, 63, 64)
CLEAR_GRID_BASIS_SEED = 0x6A09E667
CLEAR_GRID_BASIS_PROBES: dict[str, dict[str, Any]] = {
    **{
        f"noise-rgb-a{amplitude:03d}-grid2-shift-{phase_y}{phase_x}-train": {
            "probeKind": "phase-shifted-rgb-binary-2x2-blocks",
            "role": "training",
            "blockSizePixels": 2,
            "phasePixels": [phase_x, phase_y],
            "centerCode": 128,
            "amplitudeCodes": amplitude,
            "levels": [128 - amplitude, 128 + amplitude],
            "seed": f"0x{CLEAR_GRID_BASIS_SEED:08x}",
            "amplitudeGroup": f"grid2-shift-{phase_y}{phase_x}",
            "scenes": ("circle-4000-center",),
            "sourceControl": (
                (phase_x, phase_y) == (0, 0)
                and amplitude in (1, 17, 32, 64)
            )
            or ((phase_x, phase_y) != (0, 0) and amplitude == 32),
        }
        for phase_y in range(2)
        for phase_x in range(2)
        for amplitude in (
            range(1, 65)
            if (phase_x, phase_y) == (0, 0)
            else CLEAR_GRID_BASIS_BOUNDARY_AMPLITUDES
        )
    },
    **{
        f"noise-rgb-a{amplitude:03d}-cell2-basis-{phase_y}{phase_x}-train": {
            "probeKind": "rgb-binary-2x2-cell-basis",
            "role": "training",
            "blockSizePixels": 2,
            "phasePixels": [phase_x, phase_y],
            "centerCode": 128,
            "amplitudeCodes": amplitude,
            "levels": [128 - amplitude, 128, 128 + amplitude],
            "seed": f"0x{CLEAR_GRID_BASIS_SEED:08x}",
            "amplitudeGroup": f"cell2-basis-{phase_y}{phase_x}",
            "scenes": ("circle-4000-center",),
            "sourceControl": amplitude == 32,
        }
        for phase_y in range(2)
        for phase_x in range(2)
        for amplitude in CLEAR_GRID_BASIS_CELL_AMPLITUDES
    },
}


def hash32(
    x: UInt32Image,
    y: UInt32Image,
    *,
    seed: int,
) -> UInt32Image:
    """Mirror GlassCapture's wrapping UInt32 coordinate hash."""
    with np.errstate(over="ignore"):
        hashed = (x ^ np.uint32(seed)) * np.uint32(0x9E3779B1)
        hashed ^= y * np.uint32(0x85EBCA77)
        hashed ^= hashed >> np.uint32(16)
        hashed *= np.uint32(0x7FEB352D)
        hashed ^= hashed >> np.uint32(15)
        hashed *= np.uint32(0x846CA68B)
        hashed ^= hashed >> np.uint32(16)
    return hashed


def expand_blocks(
    values: CodeImage, *, width: int, height: int, block: int
) -> CodeImage:
    return np.ascontiguousarray(
        np.repeat(
            np.repeat(values, block, axis=0),
            block,
            axis=1,
        )[:height, :width]
    )


def block_coordinates(
    *,
    width: int,
    height: int,
    block: int,
) -> tuple[UInt32Image, UInt32Image]:
    block_width = (width + block - 1) // block
    block_height = (height + block - 1) // block
    y, x = np.indices((block_height, block_width), dtype=np.uint32)
    return x, y


def palette_blocks(
    *,
    width: int,
    height: int,
    block: int,
    levels: list[int],
    seed: int,
) -> CodeImage:
    x, y = block_coordinates(width=width, height=height, block=block)
    palette = np.asarray(levels, dtype=np.uint8)
    channels = [
        palette[hash32(x, y, seed=seed ^ channel_seed) % np.uint32(palette.size)]
        for channel_seed in (0x243F6A88, 0x85A308D3, 0x13198A2E)
    ]
    return expand_blocks(
        np.stack(channels, axis=2),
        width=width,
        height=height,
        block=block,
    )


def source_safe_midpoint_blocks(
    *,
    width: int,
    height: int,
    block: int,
    levels: list[int],
    seed: int,
) -> CodeImage:
    x, y = block_coordinates(width=width, height=height, block=block)
    source_indexes = hash32(x, y, seed=seed) % np.uint32(507)
    for excluded_index in (312, 376, 440, 496, 504):
        source_indexes += source_indexes >= excluded_index
    palette = np.asarray(levels, dtype=np.uint8)
    blocks = np.stack(
        (
            palette[source_indexes % 8],
            palette[(source_indexes // 8) % 8],
            palette[(source_indexes // 64) % 8],
        ),
        axis=2,
    )
    return expand_blocks(
        blocks,
        width=width,
        height=height,
        block=block,
    )


def binary_blocks(
    *,
    width: int,
    height: int,
    block: int,
    center: int,
    amplitude: int,
    seed: int,
    independent_rgb: bool,
) -> CodeImage:
    x, y = block_coordinates(width=width, height=height, block=block)
    channel_seeds = (
        (0x243F6A88, 0x85A308D3, 0x13198A2E) if independent_rgb else (0, 0, 0)
    )
    channels = [
        np.where(
            hash32(x, y, seed=seed ^ channel_seed) & np.uint32(1),
            center + amplitude,
            center - amplitude,
        ).astype(np.uint8)
        for channel_seed in channel_seeds
    ]
    return expand_blocks(
        np.stack(channels, axis=2),
        width=width,
        height=height,
        block=block,
    )


def expected_adaptive_reference(
    background: str,
    *,
    width: int,
    height: int,
) -> CodeImage:
    """Regenerate one v2.11+ source independently from the capture app."""
    if width <= 0 or height <= 0:
        raise ValueError("reference dimensions must be positive")
    metadata = ADAPTIVE_SPATIAL_PROBES[background]
    kind = str(metadata["probeKind"])
    block = int(metadata["blockSizePixels"])
    levels = [int(value) for value in metadata["levels"]]
    seed = int(str(metadata["seed"]), 0)
    if kind == "independent-rgb-palette-blocks":
        return palette_blocks(
            width=width,
            height=height,
            block=block,
            levels=levels,
            seed=seed,
        )
    if kind == "source-safe-rgb-palette-blocks":
        return source_safe_midpoint_blocks(
            width=width,
            height=height,
            block=block,
            levels=levels,
            seed=seed,
        )
    if kind == "periodically-shifted-rgb-palette-blocks":
        unshifted = palette_blocks(
            width=width,
            height=height,
            block=block,
            levels=levels,
            seed=seed,
        )
        shift_x, shift_y = (int(value) for value in metadata["sourceShiftPixels"])
        return np.roll(
            unshifted,
            shift=(-shift_y, -shift_x),
            axis=(0, 1),
        )
    if kind in {"gray-binary-blocks", "rgb-binary-blocks"}:
        return binary_blocks(
            width=width,
            height=height,
            block=block,
            center=int(metadata["centerCode"]),
            amplitude=int(metadata["amplitudeCodes"]),
            seed=seed,
            independent_rgb=kind == "rgb-binary-blocks",
        )
    raise ValueError(f"unknown adaptive probe kind: {kind}")


def expected_clear_kernel_reference(
    background: str,
    *,
    width: int,
    height: int,
) -> CodeImage:
    """Regenerate one v2.13 clear-kernel source independently."""
    if width <= 0 or height <= 0:
        raise ValueError("reference dimensions must be positive")
    metadata = CLEAR_KERNEL_PROBES[background]
    return binary_blocks(
        width=width,
        height=height,
        block=int(metadata["blockSizePixels"]),
        center=int(metadata["centerCode"]),
        amplitude=int(metadata["amplitudeCodes"]),
        seed=int(str(metadata["seed"]), 0),
        independent_rgb=True,
    )


def expected_clear_tomography_reference(
    background: str,
    *,
    width: int,
    height: int,
) -> CodeImage:
    """Regenerate one v2.14 amplitude-tomography source independently."""
    if width <= 0 or height <= 0:
        raise ValueError("reference dimensions must be positive")
    metadata = CLEAR_TOMOGRAPHY_PROBES[background]
    return binary_blocks(
        width=width,
        height=height,
        block=int(metadata["blockSizePixels"]),
        center=int(metadata["centerCode"]),
        amplitude=int(metadata["amplitudeCodes"]),
        seed=int(str(metadata["seed"]), 0),
        independent_rgb=True,
    )


def expected_clear_amplitude_sweep_reference(
    background: str,
    *,
    width: int,
    height: int,
) -> CodeImage:
    """Regenerate one v2.15 dense-amplitude source independently."""
    if width <= 0 or height <= 0:
        raise ValueError("reference dimensions must be positive")
    metadata = CLEAR_AMPLITUDE_SWEEP_PROBES[background]
    return binary_blocks(
        width=width,
        height=height,
        block=int(metadata["blockSizePixels"]),
        center=int(metadata["centerCode"]),
        amplitude=int(metadata["amplitudeCodes"]),
        seed=int(str(metadata["seed"]), 0),
        independent_rgb=True,
    )


def clear_grid_basis_blocks(
    *,
    width: int,
    height: int,
    phase_x: int,
    phase_y: int,
    center: int,
    amplitude: int,
    seed: int,
    cell_basis: bool,
) -> CodeImage:
    if (
        width <= 0
        or height <= 0
        or phase_x not in (0, 1)
        or phase_y not in (0, 1)
    ):
        raise ValueError("invalid clear grid-basis geometry")
    pixel_x = np.arange(width, dtype=np.int64)
    pixel_y = np.arange(height, dtype=np.int64)
    if cell_basis:
        block_x = pixel_x // 2
        block_y = pixel_y // 2
    else:
        block_x = (pixel_x + phase_x) // 2
        block_y = (pixel_y + phase_y) // 2
    unique_x = np.arange(int(block_x.max()) + 1, dtype=np.uint32)
    unique_y = np.arange(int(block_y.max()) + 1, dtype=np.uint32)
    x, y = np.meshgrid(unique_x, unique_y)
    channels = [
        np.where(
            hash32(x, y, seed=seed ^ channel_seed) & np.uint32(1),
            center + amplitude,
            center - amplitude,
        ).astype(np.uint8)
        for channel_seed in (0x243F6A88, 0x85A308D3, 0x13198A2E)
    ]
    expanded = np.stack(channels, axis=2)[
        block_y[:, np.newaxis],
        block_x[np.newaxis, :],
    ]
    if not cell_basis:
        return np.ascontiguousarray(expanded)
    active = (
        (pixel_y[:, np.newaxis] % 2 == phase_y)
        & (pixel_x[np.newaxis, :] % 2 == phase_x)
    )
    return np.ascontiguousarray(
        np.where(active[:, :, np.newaxis], expanded, center).astype(np.uint8)
    )


def expected_clear_grid_basis_reference(
    background: str,
    *,
    width: int,
    height: int,
) -> CodeImage:
    """Regenerate one v2.16 phase-aligned source independently."""
    metadata = CLEAR_GRID_BASIS_PROBES[background]
    phase_x, phase_y = (int(value) for value in metadata["phasePixels"])
    return clear_grid_basis_blocks(
        width=width,
        height=height,
        phase_x=phase_x,
        phase_y=phase_y,
        center=int(metadata["centerCode"]),
        amplitude=int(metadata["amplitudeCodes"]),
        seed=int(str(metadata["seed"]), 0),
        cell_basis=metadata["probeKind"] == "rgb-binary-2x2-cell-basis",
    )
