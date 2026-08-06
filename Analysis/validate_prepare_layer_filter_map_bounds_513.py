#!/usr/bin/env python3
"""Validate a 513-point trace with the frozen FilterOp validator."""

import argparse
import json
from pathlib import Path

import validate_prepare_layer_filter_map_bounds as frozen
import validate_prepare_layer_mask_instruction_trace as frozen_mask


EXPECTED_GEOMETRY = "circle-513-center"


def validate(trace: Path, timeline: Path, inventory: Path) -> dict[str, object]:
    original_filter_geometry = frozen.EXPECTED_GEOMETRY
    original_mask_geometry = frozen_mask.EXPECTED_GEOMETRY
    frozen.EXPECTED_GEOMETRY = EXPECTED_GEOMETRY
    frozen_mask.EXPECTED_GEOMETRY = EXPECTED_GEOMETRY
    try:
        return frozen.validate(trace, timeline, inventory, EXPECTED_GEOMETRY)
    finally:
        frozen.EXPECTED_GEOMETRY = original_filter_geometry
        frozen_mask.EXPECTED_GEOMETRY = original_mask_geometry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("timeline", type=Path)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = validate(arguments.trace, arguments.timeline, arguments.inventory)
    arguments.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
