"""Capture exact live operands of the opened ``SDFStyle.Group.margin`` getter.

The writer and producer adapters remain immutable.  This overlay selects only
getter invocations made by the already authenticated ``updateSDFEffects`` call
site, then retains the collection records, tagged side payloads, case numbers,
branch operands, and accumulator.  No margin, crop, image, or pixel value
selects an invocation or branch.

LLDB imports this file with the macOS system Python, so it avoids newer-only
syntax.
"""

import hashlib
import math
import struct

import lldb

import capture_backdrop_margin_writer_producer_lldb as writer


GROUP_EXECUTION_SCHEMA_VERSION = 1
SWIFTUICORE_UUID = "A8FC6D2D-DFE9-3557-A734-7F2B231F8C97"
PRODUCER_FUNCTION = "SwiftUI.SDFStyle.Group.margin.getter : CoreGraphics.CGFloat"
PRODUCER_BYTE_COUNT = 732
PRODUCER_CODE_SHA256 = (
    "5414dac1e2dce7753af9afe072ceb3b7f938ec894df81bd621866f50d03b015d"
)
PRODUCER_MODULE_OFFSET = 0x3715D0

CALLER_FUNCTION = (
    "SwiftUI.SDFLayer.updateSDFEffects(for: SwiftUI.SDFStyle, at: inout "
    "Swift.Int, in: SwiftUI.DisplayList.ViewRenderer.Environment, "
    "backdropGroupID: Swift.Optional<SwiftUI.BackdropGroupID>, blend: "
    "SwiftUI.Material.Layer.SDFLayer.GroupLayer.Blend, opacity: Swift.Float, "
    "options: SwiftUI.Material.Layer.SDFLayer.GroupLayer.Options, gain: "
    "Swift.Float, maxColorComponent: Swift.Float) -> ()"
)
CALLER_RETURN_AFTER_PRODUCER_OFFSET = 5764

GROUP_SELF_BYTE_COUNT = 0x60
GROUP_TAG_BYTE_OFFSET = 0x10
GROUP_SIDE_STORAGE_OFFSET = 0x18
GROUP_RECORD_STORAGE_OFFSET = 0x20
COLLECTION_COUNT_OFFSET = 0x10
COLLECTION_ELEMENTS_OFFSET = 0x20
GROUP_RECORD_BYTE_COUNT = 0x80
SIDE_ENTRY_BYTE_COUNT = 0x38
SIDE_PAYLOAD_BYTE_COUNT = 0x80
MAXIMUM_COLLECTION_COUNT = 64
MAXIMUM_TAG2_VALUE_COUNT = 256
MAXIMUM_INVOCATION_COUNT = 512
MAXIMUM_STAGE_COUNT = 8192
MAXIMUM_DIRECT_TARGET_COUNT = 16
MAXIMUM_DIRECT_TARGET_BYTE_COUNT = 131072
MAXIMUM_TOTAL_DIRECT_TARGET_BYTE_COUNT = 2 * 1024 * 1024

DIRECT_CALL_OFFSETS = (
    0x0B8,
    0x0D4,
    0x144,
    0x168,
    0x180,
    0x208,
    0x254,
    0x25C,
    0x274,
)
EXPECTED_DIRECT_CALL_TARGET_MODULE_OFFSETS = (
    0x144E24,
    0x4F38,
    0xB6CD0,
    0x4F38,
    0x4F38,
    0x4F38,
    0x4F38,
    0xD64010,
    0xB7F38,
)

STAGE_INSTRUCTIONS = {
    0x0BC: ("discriminator", "1f500071"),
    0x0D8: ("case23Projected", "000040fd"),
    0x148: ("case23Contribution", "00216a1e"),
    0x16C: ("case21Projected", "080040fd"),
    0x184: ("case1Projected", "087840b9"),
    0x1F8: ("case1Reduction", "0021601e"),
    0x20C: ("case22Projected", "140040f9"),
    0x268: ("case22IndirectCall", "910b3fd7"),
    0x26C: ("case22Return", "081ca04e"),
    0x278: ("loopAccumulator", "18070091"),
    0x2B0: ("getterReturn", "001da84e"),
}

PROJECTION_STAGE_OFFSETS = (0x0D8, 0x16C, 0x184, 0x20C)
REGISTER_NAMES = (
    "x0",
    "x8",
    "x9",
    "x17",
    "x20",
    "x21",
    "x22",
    "x23",
    "x24",
    "x28",
)
VECTOR_NAMES = ("v0", "v8", "v9", "v10")

_writer_new_trace = writer._new_trace
_writer_finalize = writer.finalize


def _set_callback(breakpoint, callback, label):
    error = breakpoint.SetScriptCallbackFunction(__name__ + "." + callback)
    if error is not None and hasattr(error, "Success") and not error.Success():
        raise RuntimeError(error.GetCString() or label + " callback rejected")


def _new_trace():
    trace = _writer_new_trace()
    trace["classification"] = (
        "output-blind writer, adjacent-producer, and live Group.margin operand "
        "diagnostic; not prospective public-input transfer, optical parity, "
        "physical-output parity, or production authority"
    )
    trace["groupMarginExecution"] = {
        "groupMarginExecutionTraceSchemaVersion": GROUP_EXECUTION_SCHEMA_VERSION,
        "status": "initialized",
        "configuration": {
            "producerFunction": PRODUCER_FUNCTION,
            "producerByteCount": PRODUCER_BYTE_COUNT,
            "producerCodeSHA256": PRODUCER_CODE_SHA256,
            "producerModuleOffset": PRODUCER_MODULE_OFFSET,
            "callerFunction": CALLER_FUNCTION,
            "callerReturnAfterProducerOffset": CALLER_RETURN_AFTER_PRODUCER_OFFSET,
            "groupSelfByteCount": GROUP_SELF_BYTE_COUNT,
            "groupTagByteOffset": GROUP_TAG_BYTE_OFFSET,
            "groupSideStorageOffset": GROUP_SIDE_STORAGE_OFFSET,
            "groupRecordStorageOffset": GROUP_RECORD_STORAGE_OFFSET,
            "collectionCountOffset": COLLECTION_COUNT_OFFSET,
            "collectionElementsOffset": COLLECTION_ELEMENTS_OFFSET,
            "groupRecordByteCount": GROUP_RECORD_BYTE_COUNT,
            "sideEntryByteCount": SIDE_ENTRY_BYTE_COUNT,
            "sidePayloadByteCount": SIDE_PAYLOAD_BYTE_COUNT,
            "maximumCollectionCount": MAXIMUM_COLLECTION_COUNT,
            "maximumTag2ValueCount": MAXIMUM_TAG2_VALUE_COUNT,
            "maximumInvocationCount": MAXIMUM_INVOCATION_COUNT,
            "maximumStageCount": MAXIMUM_STAGE_COUNT,
            "maximumDirectTargetCount": MAXIMUM_DIRECT_TARGET_COUNT,
            "maximumDirectTargetByteCount": MAXIMUM_DIRECT_TARGET_BYTE_COUNT,
            "maximumTotalDirectTargetByteCount": (
                MAXIMUM_TOTAL_DIRECT_TARGET_BYTE_COUNT
            ),
            "directCallOffsets": list(DIRECT_CALL_OFFSETS),
            "directCallTargetModuleOffsets": list(
                EXPECTED_DIRECT_CALL_TARGET_MODULE_OFFSETS
            ),
            "stageOffsets": sorted(STAGE_INSTRUCTIONS),
            "selection": (
                "all Group.margin invocations whose immediate caller is the "
                "opened SwiftUICore updateSDFEffects symbol at return offset 5764"
            ),
            "capturedMarginUsedForSelection": False,
            "capturedCropUsedForSelection": False,
            "capturedImageUsedForSelection": False,
            "capturedPixelUsedForSelection": False,
        },
        "producerCodeGate": None,
        "directCalls": [],
        "directTargets": [],
        "breakpoints": [],
        "invocations": [],
        "failures": [],
    }
    return trace


def _extension():
    trace = writer.base._state.get("trace")
    if trace is None:
        return None
    return trace.get("groupMarginExecution")


def _write_trace():
    writer.base._write_trace()


def _failure(stage, error):
    extension = _extension()
    if extension is not None:
        extension["failures"].append({"stage": str(stage), "message": str(error)})
    writer.base._failure("group-margin-" + str(stage), error)


def _snapshot_or_empty(process, address, byte_count, label):
    if byte_count == 0:
        payload = b""
        return {
            "address": address,
            "byteCount": 0,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "hex": "",
        }
    return writer._snapshot_memory(process, address, byte_count, label)


def _u64_at(payload, offset, label):
    if offset < 0 or offset + 8 > len(payload):
        raise RuntimeError(label + " is outside the retained payload")
    return struct.unpack_from("<Q", payload, offset)[0]


def _bounded_count(payload, label, maximum):
    count = _u64_at(payload, COLLECTION_COUNT_OFFSET, label + " count")
    if count > maximum:
        raise RuntimeError("%s count %d exceeds %d" % (label, count, maximum))
    return count


def _vector_record(frame, name):
    payload = writer.base._register_bytes(frame, name)
    if len(payload) < 8:
        raise RuntimeError(name + " is too short for binary64")
    raw = payload[:8]
    value = struct.unpack("<d", raw)[0]
    return {
        "byteCount": len(payload),
        "rawLittleEndianHex": payload.hex(),
        "lowF64RawLittleEndianHex": raw.hex(),
        "lowF64": value if math.isfinite(value) else None,
        "lowF64Finite": math.isfinite(value),
    }


def _capture_tagged_payloads(process, side_entries, side_count):
    payloads = []
    for index in range(side_count):
        offset = index * SIDE_ENTRY_BYTE_COUNT
        tagged = _u64_at(side_entries, offset, "side entry")
        tag = tagged >> 60
        address = tagged & 0x0FFFFFFFFFFFFFFF
        record = {
            "sideEntryIndex": index,
            "taggedWordRawLittleEndianHex": side_entries[offset : offset + 8].hex(),
            "tag": tag,
            "payloadAddress": address,
            "payloadSnapshot": None,
            "tag2ValueStorage": None,
        }
        if tag in (2, 5) and address != 0:
            snapshot = _snapshot_or_empty(
                process,
                address,
                SIDE_PAYLOAD_BYTE_COUNT,
                "Group.margin tagged side payload",
            )
            record["payloadSnapshot"] = snapshot
            if tag == 2:
                payload = bytes.fromhex(snapshot["hex"])
                value_storage = _u64_at(payload, 0x18, "tag-2 value-storage pointer")
                header_snapshot = _snapshot_or_empty(
                    process,
                    value_storage,
                    COLLECTION_ELEMENTS_OFFSET,
                    "Group.margin tag-2 value-storage header",
                )
                header = bytes.fromhex(header_snapshot["hex"])
                value_count = _bounded_count(
                    header, "tag-2 value storage", MAXIMUM_TAG2_VALUE_COUNT
                )
                values_snapshot = _snapshot_or_empty(
                    process,
                    value_storage + COLLECTION_ELEMENTS_OFFSET,
                    value_count * 8,
                    "Group.margin tag-2 binary64 values",
                )
                record["tag2ValueStorage"] = {
                    "address": value_storage,
                    "valueCount": value_count,
                    "headerSnapshot": header_snapshot,
                    "valuesSnapshot": values_snapshot,
                }
        payloads.append(record)
    return payloads


def _capture_group_value(frame):
    process = frame.GetThread().GetProcess()
    self_address = writer.base._register_u64(frame, "x20")
    self_snapshot = _snapshot_or_empty(
        process,
        self_address,
        GROUP_SELF_BYTE_COUNT,
        "Group.margin self value",
    )
    self_payload = bytes.fromhex(self_snapshot["hex"])
    tag = self_payload[GROUP_TAG_BYTE_OFFSET]
    side_storage = _u64_at(
        self_payload, GROUP_SIDE_STORAGE_OFFSET, "Group.margin side storage"
    )
    record_storage = _u64_at(
        self_payload, GROUP_RECORD_STORAGE_OFFSET, "Group.margin record storage"
    )
    result = {
        "self": self_address,
        "selfSnapshot": self_snapshot,
        "collectionTagByte": tag,
        "sideStorage": side_storage,
        "recordStorage": record_storage,
        "sideStorageHeader": None,
        "recordStorageHeader": None,
        "sideEntryCount": None,
        "recordCount": None,
        "sideEntriesSnapshot": None,
        "recordsSnapshot": None,
        "taggedSidePayloads": [],
        "storagePath": None,
    }
    inline_first_word = _u64_at(self_payload, 0x00, "Group.margin inline word 0")
    inline_second_word = _u64_at(self_payload, 0x08, "Group.margin inline word 1")
    uses_direct_storage = tag >> 6 < 2
    uses_bridged_storage = (
        tag == 0x80 and inline_first_word == 3 and inline_second_word == 0
    )
    if not uses_direct_storage and not uses_bridged_storage:
        result["storagePath"] = "none"
        return result
    result["storagePath"] = "direct" if uses_direct_storage else "bridged-0x80"
    side_header_snapshot = _snapshot_or_empty(
        process,
        side_storage,
        COLLECTION_ELEMENTS_OFFSET,
        "Group.margin side-storage header",
    )
    record_header_snapshot = _snapshot_or_empty(
        process,
        record_storage,
        COLLECTION_ELEMENTS_OFFSET,
        "Group.margin record-storage header",
    )
    side_header = bytes.fromhex(side_header_snapshot["hex"])
    record_header = bytes.fromhex(record_header_snapshot["hex"])
    side_count = _bounded_count(
        side_header, "Group.margin side storage", MAXIMUM_COLLECTION_COUNT
    )
    record_count = _bounded_count(
        record_header, "Group.margin record storage", MAXIMUM_COLLECTION_COUNT
    )
    side_entries_snapshot = _snapshot_or_empty(
        process,
        side_storage + COLLECTION_ELEMENTS_OFFSET,
        side_count * SIDE_ENTRY_BYTE_COUNT,
        "Group.margin side entries",
    )
    records_snapshot = _snapshot_or_empty(
        process,
        record_storage + COLLECTION_ELEMENTS_OFFSET,
        record_count * GROUP_RECORD_BYTE_COUNT,
        "Group.margin records",
    )
    result.update(
        {
            "sideStorageHeader": side_header_snapshot,
            "recordStorageHeader": record_header_snapshot,
            "sideEntryCount": side_count,
            "recordCount": record_count,
            "sideEntriesSnapshot": side_entries_snapshot,
            "recordsSnapshot": records_snapshot,
            "taggedSidePayloads": _capture_tagged_payloads(
                process,
                bytes.fromhex(side_entries_snapshot["hex"]),
                side_count,
            ),
        }
    )
    return result


def _decode_bl_target(code, start, instruction_offset):
    word = struct.unpack_from("<I", code, instruction_offset)[0]
    if word & 0xFC000000 != 0x94000000:
        raise RuntimeError("producer +0x%x is not BL" % instruction_offset)
    displacement = word & 0x03FFFFFF
    if displacement & 0x02000000:
        displacement -= 0x04000000
    return start + instruction_offset + displacement * 4


def _capture_direct_target(process, address):
    target = process.GetTarget()
    resolved = target.ResolveLoadAddress(address)
    record = {
        "selectedTarget": address,
        "resolved": resolved.IsValid(),
        "function": "",
        "symbolStart": None,
        "symbolEnd": None,
        "symbolOffset": None,
        "symbolByteCount": None,
        "completeCodeCaptured": False,
        "completeCodeFailure": None,
        "codeSHA256": None,
        "hex": None,
        "module": (
            writer.base._module_record(resolved.GetModule(), target)
            if resolved.IsValid()
            else {"valid": False}
        ),
    }
    if not resolved.IsValid():
        record["completeCodeFailure"] = "target address is unresolved"
        return record
    symbol = resolved.GetSymbol()
    if not symbol.IsValid():
        record["completeCodeFailure"] = "target symbol is unresolved"
        return record
    start = symbol.GetStartAddress().GetLoadAddress(target)
    end = symbol.GetEndAddress().GetLoadAddress(target)
    record["function"] = symbol.GetName() or ""
    if (
        start == lldb.LLDB_INVALID_ADDRESS
        or end == lldb.LLDB_INVALID_ADDRESS
        or not start <= address < end
    ):
        record["completeCodeFailure"] = "target symbol bounds are unavailable"
        return record
    byte_count = end - start
    record.update(
        {
            "symbolStart": start,
            "symbolEnd": end,
            "symbolOffset": address - start,
            "symbolByteCount": byte_count,
        }
    )
    if byte_count <= 0 or byte_count > MAXIMUM_DIRECT_TARGET_BYTE_COUNT:
        record["completeCodeFailure"] = "target symbol exceeds byte bound"
        return record
    if (
        writer.base._state["groupDirectTargetTotalBytes"] + byte_count
        > MAXIMUM_TOTAL_DIRECT_TARGET_BYTE_COUNT
    ):
        record["completeCodeFailure"] = "target total exceeds byte bound"
        return record
    payload = writer.base._read_memory(
        process, start, byte_count, "Group.margin direct target code"
    )
    record.update(
        {
            "completeCodeCaptured": True,
            "completeCodeFailure": None,
            "codeSHA256": hashlib.sha256(payload).hexdigest(),
            "hex": payload.hex(),
        }
    )
    writer.base._state["groupDirectTargetTotalBytes"] += byte_count
    return record


def _capture_direct_calls(process, producer_gate, code):
    extension = _extension()
    if extension["directCalls"]:
        return
    module_base = producer_gate["module"]["loadAddress"]
    targets = extension["directTargets"]
    keys = writer.base._state["groupDirectTargetKeys"]
    for call_offset, expected_target_offset in zip(
        DIRECT_CALL_OFFSETS,
        EXPECTED_DIRECT_CALL_TARGET_MODULE_OFFSETS,
    ):
        target_address = _decode_bl_target(
            code, producer_gate["symbolStart"], call_offset
        )
        if target_address - module_base != expected_target_offset:
            raise RuntimeError("Group.margin direct-call target differs")
        target_index = keys.get(target_address)
        if target_index is None:
            if len(targets) >= MAXIMUM_DIRECT_TARGET_COUNT:
                raise RuntimeError("Group.margin direct-target count exceeded")
            target_index = len(targets)
            targets.append(_capture_direct_target(process, target_address))
            keys[target_address] = target_index
        extension["directCalls"].append(
            {
                "instructionOffset": call_offset,
                "instructionHex": code[call_offset : call_offset + 4].hex(),
                "target": target_address,
                "targetModuleOffset": expected_target_offset,
                "targetIndex": target_index,
            }
        )


def _install_stage_breakpoints(frame, gate, code):
    if writer.base._state.get("groupStageBreakpoints"):
        return
    target = frame.GetThread().GetProcess().GetTarget()
    process = frame.GetThread().GetProcess()
    breakpoints = {}
    for offset, (name, expected_hex) in STAGE_INSTRUCTIONS.items():
        address = gate["symbolStart"] + offset
        observed = writer.base._read_memory(
            process, address, 4, "Group.margin stage instruction"
        )
        if observed.hex() != expected_hex or code[offset : offset + 4] != observed:
            raise RuntimeError("Group.margin %s instruction differs" % name)
        breakpoint = target.BreakpointCreateByAddress(address)
        if not breakpoint.IsValid() or breakpoint.GetNumLocations() != 1:
            raise RuntimeError("Group.margin %s breakpoint is unresolved" % name)
        _set_callback(breakpoint, "producer_stage", name)
        breakpoints[offset] = breakpoint
        _extension()["breakpoints"].append(
            {
                "name": name,
                "id": breakpoint.GetID(),
                "address": address,
                "instructionOffset": offset,
                "instructionHex": expected_hex,
                "selection": "fixed offset in exact producer code",
            }
        )
    writer.base._state["groupStageBreakpoints"] = breakpoints


def _gate_producer(frame):
    extension = _extension()
    existing = extension.get("producerCodeGate")
    target = frame.GetThread().GetProcess().GetTarget()
    symbol = frame.GetSymbol()
    if not symbol.IsValid():
        raise RuntimeError("Group.margin symbol is invalid")
    start = symbol.GetStartAddress().GetLoadAddress(target)
    end = symbol.GetEndAddress().GetLoadAddress(target)
    module = writer.base._module_record(frame.GetModule(), target)
    if (
        start == lldb.LLDB_INVALID_ADDRESS
        or end == lldb.LLDB_INVALID_ADDRESS
        or end - start != PRODUCER_BYTE_COUNT
        or frame.GetPC() != start
        or (frame.GetFunctionName() or symbol.GetName() or "") != PRODUCER_FUNCTION
        or module.get("uuid") != SWIFTUICORE_UUID
        or start - module.get("loadAddress", 0) != PRODUCER_MODULE_OFFSET
    ):
        raise RuntimeError("Group.margin exact symbol identity differs")
    if existing is not None:
        if existing["symbolStart"] != start or existing["symbolEnd"] != end:
            raise RuntimeError("Group.margin symbol moved during execution")
        return existing, bytes.fromhex(existing["hex"])
    process = frame.GetThread().GetProcess()
    code = writer.base._read_memory(
        process, start, PRODUCER_BYTE_COUNT, "Group.margin complete code"
    )
    digest = hashlib.sha256(code).hexdigest()
    if digest != PRODUCER_CODE_SHA256:
        raise RuntimeError("Group.margin complete-code SHA-256 differs")
    gate = {
        "function": PRODUCER_FUNCTION,
        "symbolStart": start,
        "symbolEnd": end,
        "symbolByteCount": PRODUCER_BYTE_COUNT,
        "codeSHA256": digest,
        "hex": code.hex(),
        "module": module,
    }
    extension["producerCodeGate"] = gate
    _capture_direct_calls(process, gate, code)
    _install_stage_breakpoints(frame, gate, code)
    _write_trace()
    return gate, code


def _selected_caller(frame):
    thread = frame.GetThread()
    if thread.GetNumFrames() < 2:
        return None
    caller = thread.GetFrameAtIndex(1)
    target = thread.GetProcess().GetTarget()
    symbol = caller.GetSymbol()
    if not symbol.IsValid():
        return None
    start = symbol.GetStartAddress().GetLoadAddress(target)
    module = writer.base._module_record(caller.GetModule(), target)
    pc = caller.GetPC()
    if (
        start == lldb.LLDB_INVALID_ADDRESS
        or (caller.GetFunctionName() or symbol.GetName() or "") != CALLER_FUNCTION
        or module.get("uuid") != SWIFTUICORE_UUID
        or pc - start != CALLER_RETURN_AFTER_PRODUCER_OFFSET
    ):
        return None
    return {
        "function": CALLER_FUNCTION,
        "pc": pc,
        "symbolStart": start,
        "symbolOffset": pc - start,
        "module": module,
    }


def producer_entry(frame, _breakpoint_location, _internal_dict):
    thread = frame.GetThread()
    thread_id = thread.GetThreadID()
    stack = writer.base._state["groupInvocationStacks"].setdefault(thread_id, [])
    try:
        _gate_producer(frame)
        caller = _selected_caller(frame)
        invocations = _extension()["invocations"]
        if caller is None or len(invocations) >= MAXIMUM_INVOCATION_COUNT:
            stack.append(None)
            return False
        invocation_index = len(invocations)
        invocation = {
            "invocationIndex": invocation_index,
            "threadID": thread_id,
            "entryPC": frame.GetPC(),
            "caller": caller,
            "selectedByCapturedMargin": False,
            "group": _capture_group_value(frame),
            "stages": [],
            "complete": False,
            "setterEventIndex": None,
            "returnF64": None,
            "returnF64RawLittleEndianHex": None,
        }
        invocations.append(invocation)
        stack.append(invocation_index)
        _write_trace()
    except Exception as error:
        stack.append(None)
        _failure("entry", error)
    return False


def _stage_record(frame, invocation, offset, name):
    record = {
        "stageIndex": writer.base._state["groupStageCount"],
        "invocationStageIndex": len(invocation["stages"]),
        "name": name,
        "pc": frame.GetPC(),
        "instructionOffset": offset,
        "registers": {
            register: writer.base._register_u64(frame, register)
            for register in REGISTER_NAMES
        },
        "vectors": {
            register: _vector_record(frame, register) for register in VECTOR_NAMES
        },
    }
    if offset == 0x0BC:
        record["discriminatorCase"] = record["registers"]["x0"] & 0xFFFFFFFF
        record["groupRecordIndex"] = record["registers"]["x24"]
    if offset in PROJECTION_STAGE_OFFSETS:
        address = record["registers"]["x0"]
        record["projectionSnapshot"] = _snapshot_or_empty(
            frame.GetThread().GetProcess(),
            address,
            GROUP_RECORD_BYTE_COUNT,
            "Group.margin projected case payload",
        )
    if offset == 0x268:
        record["authenticatedIndirectTargetRaw"] = record["registers"]["x28"]
        record["authenticatedIndirectModifierRaw"] = record["registers"]["x17"]
    return record


def producer_stage(frame, _breakpoint_location, _internal_dict):
    thread = frame.GetThread()
    thread_id = thread.GetThreadID()
    stack = writer.base._state["groupInvocationStacks"].get(thread_id, [])
    gate = _extension().get("producerCodeGate")
    try:
        if gate is None:
            raise RuntimeError("Group.margin stage ran before its code gate")
        offset = frame.GetPC() - gate["symbolStart"]
        if offset not in STAGE_INSTRUCTIONS:
            raise RuntimeError("Group.margin stage PC differs")
        if not stack:
            raise RuntimeError("Group.margin stage lacks an invocation stack")
        invocation_index = stack[-1]
        if invocation_index is None:
            if offset == 0x2B0:
                stack.pop()
            return False
        if writer.base._state["groupStageCount"] >= MAXIMUM_STAGE_COUNT:
            raise RuntimeError("Group.margin stage count exceeded")
        invocation = _extension()["invocations"][invocation_index]
        name = STAGE_INSTRUCTIONS[offset][0]
        record = _stage_record(frame, invocation, offset, name)
        invocation["stages"].append(record)
        writer.base._state["groupStageCount"] += 1
        if offset == 0x2B0:
            raw = bytes.fromhex(record["vectors"]["v8"]["lowF64RawLittleEndianHex"])
            value = struct.unpack("<d", raw)[0]
            if not math.isfinite(value):
                raise RuntimeError("Group.margin return is not finite")
            invocation["returnF64"] = value
            invocation["returnF64RawLittleEndianHex"] = raw.hex()
            invocation["complete"] = True
            stack.pop()
            writer.base._state["groupCompletedByThread"].setdefault(
                thread_id, []
            ).append(invocation_index)
            _write_trace()
    except Exception as error:
        _failure("stage", error)
    return False


def _install_callback_proxies():
    callbacks = (
        (
            writer.base._state["breakpoints"].get("copyEntry"),
            "copy_entry",
            "copy entry",
        ),
        (
            writer.base._state["breakpoints"].get("marginSetter"),
            "margin_setter",
            "margin setter",
        ),
        (
            writer.base._state["breakpoints"].get("backdropBounds"),
            "backdrop_bounds",
            "backdrop bounds",
        ),
        (
            writer.base._state.get("copyStoreBreakpoint"),
            "copy_margin_store",
            "copy margin store",
        ),
    )
    for breakpoint, callback, label in callbacks:
        if breakpoint is not None:
            _set_callback(breakpoint, callback, label)


def copy_entry(frame, breakpoint_location, internal_dict):
    result = writer.copy_entry(frame, breakpoint_location, internal_dict)
    try:
        _install_callback_proxies()
        _write_trace()
    except Exception as error:
        _failure("callback-proxy", error)
    return result


def margin_setter(frame, breakpoint_location, internal_dict):
    result = writer.margin_setter(frame, breakpoint_location, internal_dict)
    try:
        thread_id = frame.GetThread().GetThreadID()
        completed = writer.base._state["groupCompletedByThread"].get(thread_id, [])
        if not completed:
            return result
        invocation_index = completed.pop()
        invocation = _extension()["invocations"][invocation_index]
        events = writer.base._state["trace"]["events"]
        if not events or events[-1].get("type") != "marginSetter":
            raise RuntimeError("Group.margin completion lacks adjacent setter")
        event = events[-1]
        producer = event.get("producerInvocation", {})
        if producer.get("complete") is not True or producer.get(
            "producerReturnF64RawLittleEndianHex"
        ) != invocation.get("returnF64RawLittleEndianHex"):
            raise RuntimeError("Group.margin return differs from adjacent setter")
        invocation["setterEventIndex"] = event["eventIndex"]
        invocation["setterMarginF64"] = event["marginF64"]
        invocation["setterMarginF64RawLittleEndianHex"] = event[
            "marginF64RawLittleEndianHex"
        ]
        invocation["returnMatchesSetterBitwise"] = True
        producer["groupMarginInvocationIndex"] = invocation_index
        _write_trace()
    except Exception as error:
        _failure("setter-link", error)
    return result


def copy_margin_store(frame, breakpoint_location, internal_dict):
    return writer.copy_margin_store(frame, breakpoint_location, internal_dict)


def backdrop_bounds(frame, breakpoint_location, internal_dict):
    return writer.backdrop_bounds(frame, breakpoint_location, internal_dict)


def finalize():
    _writer_finalize()
    extension = _extension()
    if extension is None:
        return
    extension["statusBeforeFinalization"] = extension["status"]
    extension["status"] = "finalized"
    extension["finalInvocationCount"] = len(extension["invocations"])
    extension["finalCompleteInvocationCount"] = sum(
        invocation.get("complete") is True for invocation in extension["invocations"]
    )
    extension["finalSetterLinkedInvocationCount"] = sum(
        invocation.get("setterEventIndex") is not None
        for invocation in extension["invocations"]
    )
    extension["finalStageCount"] = writer.base._state["groupStageCount"]
    extension["finalDirectTargetCodeByteCount"] = writer.base._state[
        "groupDirectTargetTotalBytes"
    ]
    extension["unfinishedSelectedInvocationCount"] = sum(
        value is not None
        for stack in writer.base._state["groupInvocationStacks"].values()
        for value in stack
    )
    _write_trace()


def __lldb_init_module(debugger, internal_dict):
    writer.base._state["groupInvocationStacks"] = {}
    writer.base._state["groupCompletedByThread"] = {}
    writer.base._state["groupStageBreakpoints"] = {}
    writer.base._state["groupStageCount"] = 0
    writer.base._state["groupDirectTargetKeys"] = {}
    writer.base._state["groupDirectTargetTotalBytes"] = 0
    writer._new_trace = _new_trace
    writer.__lldb_init_module(debugger, internal_dict)
    try:
        _install_callback_proxies()
        target = debugger.GetSelectedTarget()
        breakpoint = target.BreakpointCreateByName(PRODUCER_FUNCTION)
        if not breakpoint.IsValid():
            raise RuntimeError("Group.margin entry breakpoint is invalid")
        _set_callback(breakpoint, "producer_entry", "Group.margin entry")
        writer.base._state["groupProducerBreakpoint"] = breakpoint
        extension = _extension()
        extension["breakpoints"].append(
            {
                "name": "producerEntry",
                "id": breakpoint.GetID(),
                "function": PRODUCER_FUNCTION,
                "selection": "all exact symbol invocations, filtered by caller code identity",
            }
        )
        extension["status"] = "breakpoints-armed"
        _write_trace()
    except Exception as error:
        extension = _extension()
        if extension is not None:
            extension["status"] = "initialization-failed"
        _failure("initialization", error)
