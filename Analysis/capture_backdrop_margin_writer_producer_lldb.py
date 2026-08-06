"""Extend the frozen writer-chain capture with its adjacent Swift producer.

The base adapter and its historical hash remain immutable.  This overlay keeps
the same breakpoints and event selection, then uses the already-opened exact
SwiftUICore call-site shape to retain the Double-returning call immediately
before ``setMarginWidth:``.  No captured margin, crop, image, or pixel selects
the producer.

LLDB imports this file with the macOS system Python, so this module avoids
newer-only syntax.
"""

import hashlib
import struct

import lldb

import capture_backdrop_margin_writer_execution_lldb as base


MAXIMUM_PRODUCER_COUNT = 64
MAXIMUM_PRODUCER_BYTE_COUNT = 131072
MAXIMUM_TOTAL_PRODUCER_BYTE_COUNT = 2 * 1024 * 1024
PRODUCER_SELF_SNAPSHOT_BYTE_COUNT = 0x60

SETTER_CALL_FROM_RETURN_PC = -4
PRODUCER_BRIDGE_FROM_RETURN_PC = -8
PRODUCER_CALL_FROM_RETURN_PC = -12
PRODUCER_BRIDGE_INSTRUCTION_HEX = "e0031caa"  # mov x0, x28

BASE_CAPTURE_SHA256 = "f91ba6afb61b491d949ea5dc9d4fc1c82c165e0016aefa84db00a0b15d435ecd"

_base_new_trace = base._new_trace
_base_finalize = base.finalize


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _install_callback_proxies():
    callbacks = (
        (base._state["breakpoints"].get("copyEntry"), "copy_entry", "copy entry"),
        (
            base._state["breakpoints"].get("marginSetter"),
            "margin_setter",
            "margin setter",
        ),
        (
            base._state["breakpoints"].get("backdropBounds"),
            "backdrop_bounds",
            "backdrop bounds",
        ),
        (
            base._state.get("copyStoreBreakpoint"),
            "copy_margin_store",
            "copy margin store",
        ),
    )
    for breakpoint, callback, label in callbacks:
        if breakpoint is not None:
            _set_callback(breakpoint, callback, label)


def _new_trace():
    trace = _base_new_trace()
    trace["classification"] = (
        "output-blind exhaustive live writer-chain and adjacent-producer "
        "capture for prospective material-specific margin transfer; not "
        "optical, physical-output, production-shader, or product-parity authority"
    )
    configuration = trace["configuration"]
    configuration.update(
        {
            "baseCaptureSHA256": BASE_CAPTURE_SHA256,
            "maximumProducerCount": MAXIMUM_PRODUCER_COUNT,
            "maximumProducerByteCount": MAXIMUM_PRODUCER_BYTE_COUNT,
            "maximumTotalProducerByteCount": MAXIMUM_TOTAL_PRODUCER_BYTE_COUNT,
            "producerSelfSnapshotByteCount": PRODUCER_SELF_SNAPSHOT_BYTE_COUNT,
            "setterCallFromReturnPC": SETTER_CALL_FROM_RETURN_PC,
            "producerBridgeFromReturnPC": PRODUCER_BRIDGE_FROM_RETURN_PC,
            "producerCallFromReturnPC": PRODUCER_CALL_FROM_RETURN_PC,
            "producerBridgeInstructionHex": PRODUCER_BRIDGE_INSTRUCTION_HEX,
            "producerSelection": (
                "decode fixed BL at direct-caller return PC minus 12; captured "
                "values never participate"
            ),
            "producerSelectedByCapturedMargin": False,
        }
    )
    trace["producerCallees"] = []
    return trace


def _snapshot_memory(process, address, byte_count, label):
    payload = base._read_memory(process, address, byte_count, label)
    return {
        "address": address,
        "byteCount": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "hex": payload.hex(),
    }


def _decode_bl_target(process, instruction_address, label):
    payload = base._read_memory(process, instruction_address, 4, label)
    word = struct.unpack("<I", payload)[0]
    if word & 0xFC000000 != 0x94000000:
        raise RuntimeError("%s is not an ARM64 BL instruction" % label)
    displacement = word & 0x03FFFFFF
    if displacement & 0x02000000:
        displacement -= 0x04000000
    return {
        "address": instruction_address,
        "instructionHex": payload.hex(),
        "target": instruction_address + displacement * 4,
    }


def _capture_producer_code(process, code_address):
    target = process.GetTarget()
    resolved = target.ResolveLoadAddress(code_address)
    if not resolved.IsValid():
        raise RuntimeError("producer target address is unresolved")
    symbol = resolved.GetSymbol()
    if not symbol.IsValid():
        raise RuntimeError("producer target symbol is unresolved")
    start = symbol.GetStartAddress().GetLoadAddress(target)
    end = symbol.GetEndAddress().GetLoadAddress(target)
    if (
        start == lldb.LLDB_INVALID_ADDRESS
        or end == lldb.LLDB_INVALID_ADDRESS
        or not start <= code_address < end
    ):
        raise RuntimeError("producer target symbol bounds differ")
    module = base._module_record(resolved.GetModule(), target)
    key = (module.get("uuid"), start, end)
    existing = base._state["producerKeys"].get(key)
    if existing is not None:
        return existing
    producers = base._state["trace"]["producerCallees"]
    if len(producers) >= MAXIMUM_PRODUCER_COUNT:
        raise RuntimeError("producer count exceeded the bounded maximum")
    byte_count = end - start
    if byte_count <= 0 or byte_count > MAXIMUM_PRODUCER_BYTE_COUNT:
        raise RuntimeError("producer symbol exceeds the individual byte bound")
    if (
        base._state["producerTotalBytes"] + byte_count
        > MAXIMUM_TOTAL_PRODUCER_BYTE_COUNT
    ):
        raise RuntimeError("producer code exceeded the total byte bound")
    code = base._read_memory(process, start, byte_count, "producer complete code")
    record = {
        "function": symbol.GetName() or "",
        "selectedTarget": code_address,
        "symbolStart": start,
        "symbolEnd": end,
        "symbolOffset": code_address - start,
        "symbolByteCount": byte_count,
        "codeSHA256": hashlib.sha256(code).hexdigest(),
        "hex": code.hex(),
        "completeCodeCaptured": True,
        "module": module,
    }
    index = len(producers)
    producers.append(record)
    base._state["producerKeys"][key] = index
    base._state["producerTotalBytes"] += byte_count
    return index


def _capture_producer_invocation(frame, margin_raw):
    thread = frame.GetThread()
    if thread.GetNumFrames() < 2:
        raise RuntimeError("setter caller frame is unavailable")
    process = thread.GetProcess()
    caller = thread.GetFrameAtIndex(1)
    return_pc = caller.GetPC()
    setter_call = _decode_bl_target(
        process,
        return_pc + SETTER_CALL_FROM_RETURN_PC,
        "setter dispatch call",
    )
    bridge_address = return_pc + PRODUCER_BRIDGE_FROM_RETURN_PC
    bridge = base._read_memory(process, bridge_address, 4, "producer/setter bridge")
    if bridge.hex() != PRODUCER_BRIDGE_INSTRUCTION_HEX:
        raise RuntimeError("producer/setter bridge instruction differs")
    producer_call = _decode_bl_target(
        process,
        return_pc + PRODUCER_CALL_FROM_RETURN_PC,
        "margin producer call",
    )
    producer_index = _capture_producer_code(process, producer_call["target"])
    producer_self = base._register_u64(frame, "x20")
    stack_pointer = base._register_u64(frame, "sp")
    return {
        "complete": True,
        "callerReturnPC": return_pc,
        "setterCall": setter_call,
        "bridge": {
            "address": bridge_address,
            "instructionHex": bridge.hex(),
        },
        "producerCall": producer_call,
        "producerCalleeIndex": producer_index,
        "producerSelf": producer_self,
        "stackPointerAtSetterEntry": stack_pointer,
        "producerSelfOffsetFromStackPointer": producer_self - stack_pointer,
        "producerSelfSnapshot": _snapshot_memory(
            process,
            producer_self,
            PRODUCER_SELF_SNAPSHOT_BYTE_COUNT,
            "margin producer self value",
        ),
        "producerReturnF64": struct.unpack("<d", margin_raw)[0],
        "producerReturnF64RawLittleEndianHex": margin_raw.hex(),
        "capturedMarginUsedForSelection": False,
    }


def margin_setter(frame, _breakpoint_location, _internal_dict):
    try:
        base._gate_symbol(
            frame,
            "setter",
            base.SETTER_FUNCTION,
            base.SETTER_BYTE_COUNT,
            base.SETTER_CODE_SHA256,
        )
        thread = frame.GetThread()
        process = thread.GetProcess()
        model = base._register_u64(frame, "x0")
        v0 = base._register_bytes(frame, "v0")
        if len(v0) < 8:
            raise RuntimeError("v0 is too short for the binary64 setter value")
        raw = v0[:8]
        caller_index = base._capture_caller(frame)
        try:
            producer_invocation = _capture_producer_invocation(frame, raw)
        except Exception as error:
            producer_invocation = {
                "complete": False,
                "failure": str(error),
                "capturedMarginUsedForSelection": False,
            }
        base._append_event(
            {
                "type": "marginSetter",
                "threadID": thread.GetThreadID(),
                "pc": frame.GetPC(),
                "modelSelf": model,
                "marginF64": struct.unpack("<d", raw)[0],
                "marginF64RawLittleEndianHex": raw.hex(),
                "modelPrefix": base._snapshot_prefix(
                    process, model, "margin-setter model object prefix"
                ),
                "directCallerIndex": caller_index,
                "producerInvocation": producer_invocation,
                "backtrace": base._backtrace(thread),
            }
        )
    except Exception as error:
        base._failure("margin-setter", error)
    return False


def copy_entry(frame, breakpoint_location, internal_dict):
    result = base.copy_entry(frame, breakpoint_location, internal_dict)
    try:
        _install_callback_proxies()
        base._write_trace()
    except Exception as error:
        base._failure("producer-overlay-callback-proxy", error)
    return result


def copy_margin_store(frame, breakpoint_location, internal_dict):
    return base.copy_margin_store(frame, breakpoint_location, internal_dict)


def backdrop_bounds(frame, breakpoint_location, internal_dict):
    return base.backdrop_bounds(frame, breakpoint_location, internal_dict)


def finalize():
    _base_finalize()
    trace = base._state["trace"]
    if trace is None:
        return
    trace["finalProducerCalleeCount"] = len(trace["producerCallees"])
    trace["finalProducerCalleeCodeByteCount"] = base._state["producerTotalBytes"]
    base._write_trace()


def __lldb_init_module(debugger, internal_dict):
    base._state["producerKeys"] = {}
    base._state["producerTotalBytes"] = 0
    base._new_trace = _new_trace
    base.__lldb_init_module(debugger, internal_dict)
    try:
        _install_callback_proxies()
        base._write_trace()
    except Exception as error:
        base._failure("producer-overlay-initialization", error)
