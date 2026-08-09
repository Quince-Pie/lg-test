#!/usr/bin/env python3
"""Capture the executing natural GlassBackgroundFilter ROI boundary."""

from __future__ import annotations

import json
import math
import struct

import lldb


_pending = {}
_entry_index = 0


def read(process, address, size):
    error = lldb.SBError()
    data = process.ReadMemory(address, size, error)
    return data if error.Success() and len(data) == size else None


def u64(process, address):
    data = read(process, address, 8)
    return struct.unpack("<Q", data)[0] if data is not None else None


def i32x4(process, address):
    data = read(process, address, 16)
    return list(struct.unpack("<4i", data)) if data is not None else None


def f64_values(process, address, count):
    data = read(process, address, 8 * count)
    if data is None:
        return None
    values = list(struct.unpack(f"<{count}d", data))
    return values if all(math.isfinite(value) for value in values) else None


def frame_name(frame):
    return frame.GetDisplayFunctionName() or frame.GetFunctionName() or "?"


def roi_entry(frame, _location, _dict):
    global _entry_index
    process = frame.GetThread().GetProcess()
    thread = frame.GetThread()
    caller = thread.GetFrameAtIndex(1)
    if "accumulate_sdf_element_bounds" not in frame_name(caller):
        return False

    rect_pointer = frame.FindRegister("x3").GetValueAsUnsigned()
    input_rect = f64_values(process, rect_pointer, 4)
    if (
        input_rect is None
        or not -2048.0 < input_rect[0] < 2048.0
        or not -2048.0 < input_rect[1] < 2048.0
        or not 0.0 < input_rect[2] < 2048.0
        or not 0.0 < input_rect[3] < 2048.0
    ):
        return False

    layer_pointer = caller.FindRegister("x22").GetValueAsUnsigned()
    transform_pointer = u64(process, layer_pointer + 0x50)
    _entry_index += 1
    record = {
        "entryIndex": _entry_index,
        "inputRect": input_rect,
        "rectPointer": f"0x{rect_pointer:x}",
        "integerLayerBounds": i32x4(process, layer_pointer + 0x90),
        "transform": (
            None
            if transform_pointer is None
            else f64_values(process, transform_pointer, 16)
        ),
        "backtrace": [frame_name(item) for item in list(thread)[:18]],
    }
    thread_id = thread.GetThreadID()
    _pending.setdefault(thread_id, []).append(record)
    return_address = frame.FindRegister("lr").GetValueAsUnsigned()
    breakpoint = process.GetTarget().BreakpointCreateByAddress(return_address)
    breakpoint.SetOneShot(True)
    breakpoint.SetThreadID(thread_id)
    breakpoint.SetScriptCallbackFunction(f"{__name__}.roi_return")
    return False


def roi_return(frame, _location, _dict):
    records = _pending.get(frame.GetThread().GetThreadID())
    if not records:
        return False
    record = records.pop()
    process = frame.GetThread().GetProcess()
    record["outputRect"] = f64_values(
        process, int(record["rectPointer"], 16), 4
    )
    print("LG_GLASS_BACKGROUND_ROI " + json.dumps(record, sort_keys=True), flush=True)
    return False


def __lldb_init_module(debugger, _dict):
    breakpoint = debugger.GetSelectedTarget().BreakpointCreateByName(
        "CA::OGL::GlassBackgroundFilter::ROI(CA::Render::Filter const*, "
        "CA::Render::Layer const*, CA::Rect&) const"
    )
    breakpoint.SetScriptCallbackFunction(f"{__name__}.roi_entry")
    print(
        "LG_GLASS_BACKGROUND_ROI "
        + json.dumps(
            {
                "phase": "installed",
                "breakpoint": breakpoint.GetID(),
                "locations": breakpoint.GetNumLocations(),
            },
            sort_keys=True,
        ),
        flush=True,
    )
