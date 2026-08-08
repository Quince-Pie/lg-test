#!/usr/bin/env python3
"""Resolve the Walle-size near-square AGX selector calibration."""

from pathlib import Path

import validate_raster_near_square_selector_sweep as sweep


sweep.RIG_VERSION = "metal-raster-small-near-square-selector-sweep-1.0.0"
sweep.ROLE = "walle-small-near-square-fixed-grid-reciprocal-selector-calibration"
sweep.PREREGISTRATION = Path(__file__).with_name(
    "raster_small_near_square_selector_sweep_preregistration.json"
)
sweep.PREREGISTRATION_REPOSITORY_PATH = (
    "Analysis/raster_small_near_square_selector_sweep_preregistration.json"
)
sweep.WIDTH_FIXED_LOWER = 114_688
sweep.WIDTH_FIXED_UPPER = 147_456
sweep.SAMPLE_X = 320
sweep.SAMPLE_Y = 321
sweep.TILE = sweep.SAMPLE_X // sweep.TILE_SIZE
sweep.LOCAL_PIXEL = sweep.SAMPLE_X - sweep.TILE * sweep.TILE_SIZE
sweep.WIDTH_COUNT = sweep.WIDTH_FIXED_UPPER - sweep.WIDTH_FIXED_LOWER + 1
sweep.CASE_COUNT = sweep.WIDTH_COUNT * len(sweep.HEIGHT_DELTAS)
sweep.RAW_BYTES = sweep.CASE_COUNT * sweep.RECORD.size
sweep.SELECTOR_FILE = "raster-small-near-square-selectors-u32le.zlib"
sweep.OFFSET_FILE = "raster-small-near-square-selector-offsets-i8.bin"


if __name__ == "__main__":
    raise SystemExit(sweep.main())
