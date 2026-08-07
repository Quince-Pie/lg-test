"""Retarget the frozen writer/producer adapter to the live QuartzCore image.

The writer and adjacent-producer adapters remain byte-identical.  macOS 26.6.1
currently loads QuartzCore from a dyld shared-cache image whose UUID differs
from the historical CI-era pin while retaining the preregistered symbol code
hashes.  This structural overlay changes only that module identity before the
frozen adapters install any breakpoint; it does not inspect a margin, crop,
image, pixel, or application value.

LLDB imports this file with the macOS system Python, so newer-only syntax is
deliberately avoided.
"""

import capture_backdrop_margin_writer_execution_lldb as writer


LIVE_QUARTZCORE_UUID = "F1BA3189-E95A-3ECA-B59A-5A6872754484"
LIVE_COPY_CODE_SHA256 = (
    "5bdf866c13bfb00d9becada24ff9876f84515fa36acb4ee274785d5176593a1e"
)
LIVE_SETTER_CODE_SHA256 = (
    "2421048e418c6cdcc7622dd65f881e514e0852687f7920e6c4bdaf75a301f6dd"
)

# The producer module snapshots writer._new_trace during import.  Set the live
# structural identity first so both the original trace factory and all symbol
# gates use one UUID from their first instruction.
writer.QUARTZCORE_UUID = LIVE_QUARTZCORE_UUID
writer.COPY_CODE_SHA256 = LIVE_COPY_CODE_SHA256
writer.SETTER_CODE_SHA256 = LIVE_SETTER_CODE_SHA256

import capture_backdrop_margin_writer_producer_lldb as producer  # noqa: E402


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _install_direct_callback_proxies():
    callbacks = (
        (writer._state["breakpoints"].get("copyEntry"), "copy_entry", "copy entry"),
        (
            writer._state["breakpoints"].get("marginSetter"),
            "margin_setter",
            "margin setter",
        ),
        (
            writer._state["breakpoints"].get("backdropBounds"),
            "backdrop_bounds",
            "backdrop bounds",
        ),
        (
            writer._state.get("copyStoreBreakpoint"),
            "copy_margin_store",
            "copy margin store",
        ),
    )
    for breakpoint, callback, label in callbacks:
        if breakpoint is not None:
            _set_callback(breakpoint, callback, label)


def margin_setter(frame, breakpoint_location, internal_dict):
    return producer.margin_setter(frame, breakpoint_location, internal_dict)


def copy_entry(frame, breakpoint_location, internal_dict):
    result = producer.copy_entry(frame, breakpoint_location, internal_dict)
    # The inherited callback re-proxies to its own dependency namespace.  Keep
    # the directly imported overlay authoritative after every copy entry.
    _install_direct_callback_proxies()
    return result


def copy_margin_store(frame, breakpoint_location, internal_dict):
    return producer.copy_margin_store(frame, breakpoint_location, internal_dict)


def backdrop_bounds(frame, breakpoint_location, internal_dict):
    return producer.backdrop_bounds(frame, breakpoint_location, internal_dict)


def finalize():
    producer.finalize()


def __lldb_init_module(debugger, internal_dict):
    writer.QUARTZCORE_UUID = LIVE_QUARTZCORE_UUID
    writer.COPY_CODE_SHA256 = LIVE_COPY_CODE_SHA256
    writer.SETTER_CODE_SHA256 = LIVE_SETTER_CODE_SHA256
    producer.__lldb_init_module(debugger, internal_dict)
    _install_direct_callback_proxies()
    trace = writer._state.get("trace")
    if trace is not None:
        trace["backdropMarginWriterProviderCompositionCaptureSchemaVersion"] = 1
        trace["configuration"].update(
            {
                "quartzCoreUUID": LIVE_QUARTZCORE_UUID,
                "quartzCoreIdentityRetargetUsesCapturedValue": False,
                "quartzCoreIdentityRetargetUsesCropImageOrPixel": False,
                "directLLDBCallbackProxyModule": __name__,
                "liveWriterCodeInventoryUsesCapturedValue": False,
            }
        )
        writer._write_trace()
