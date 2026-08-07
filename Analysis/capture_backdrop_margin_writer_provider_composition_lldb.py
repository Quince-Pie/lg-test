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

# The producer module snapshots writer._new_trace during import.  Set the live
# structural identity first so both the original trace factory and all symbol
# gates use one UUID from their first instruction.
writer.QUARTZCORE_UUID = LIVE_QUARTZCORE_UUID

import capture_backdrop_margin_writer_producer_lldb as producer  # noqa: E402


def finalize():
    producer.finalize()


def __lldb_init_module(debugger, internal_dict):
    writer.QUARTZCORE_UUID = LIVE_QUARTZCORE_UUID
    producer.__lldb_init_module(debugger, internal_dict)
    trace = writer._state.get("trace")
    if trace is not None:
        trace["backdropMarginWriterProviderCompositionCaptureSchemaVersion"] = 1
        trace["configuration"].update(
            {
                "quartzCoreUUID": LIVE_QUARTZCORE_UUID,
                "quartzCoreIdentityRetargetUsesCapturedValue": False,
                "quartzCoreIdentityRetargetUsesCropImageOrPixel": False,
            }
        )
        writer._write_trace()
