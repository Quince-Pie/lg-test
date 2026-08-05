#!/usr/bin/env python3
"""Adversarial tests for the software-instruction trace gate."""

import copy
import hashlib
import json
import struct
import unittest
from unittest import mock

import validate_prepare_layer_instruction_trace as validator


IDENTITY = {
    "threadID": 0x1_7000_0042,
    "roleBase": 0x1_7000_8000,
    "framePointer": 0x1_7000_A000,
}


def instruction(offset: int) -> dict[str, object]:
    return {
        "pc": 0x1_9000_0000 + offset,
        "scopeName": "prepareLayer",
        "scopeOffset": offset,
        "prepareLayerRelativeOffset": offset,
        "rawLittleEndianHex": "000000f9",
        "mnemonic": "str",
        "operands": "x0, [x0]",
        "comment": "",
        "potentialWriter": True,
        "potentialCall": False,
    }


def transition(index: int, before: bytes, after: bytes) -> dict[str, object]:
    return {
        "transitionIndex": index,
        "callbackSequence": index + 1,
        "stepIndex": index,
        "kind": "scope-instruction",
        "aggregateBeforeHex": before.hex(),
        "aggregateAfterHex": after.hex(),
        "changedLaneOffsets": [
            offset
            for offset in (0, 8, 16, 24)
            if before[offset : offset + 8] != after[offset : offset + 8]
        ],
        "instruction": instruction(index * 4),
        "opaqueBoundary": None,
        "beforeContext": {},
        "afterContext": {},
    }


def step(index: int, before: bytes, after: bytes) -> dict[str, object]:
    changed_lanes = [
        offset
        for offset in (0, 8, 16, 24)
        if before[offset : offset + 8] != after[offset : offset + 8]
    ]
    return {
        "stepIndex": index,
        "kind": "scope-instruction",
        "aggregateBeforeHex": before.hex(),
        "aggregateAfterHex": after.hex(),
        "aggregateChanged": before != after,
        "changedLaneOffsets": changed_lanes,
        "instruction": instruction(index * 4),
        "opaqueBoundary": None,
        "resultPC": 0x1_9000_0004 + index * 4,
        "resultFunction": validator.merge_base.PREPARE_LAYER_FUNCTION,
        "transitionIndex": index if before != after else None,
    }


def known_states() -> list[bytes]:
    p = 481.25
    origin = 480.0
    return [
        bytes(32),
        struct.pack("<4d", p, 384.0 - p, 640.0, 640.0),
        struct.pack("<4d", p, 376.0 - p, 640.0, 648.0),
        struct.pack("<4d", origin, 376.0 - p, p + 640.0 - origin, p + 648.0 - origin),
    ]


def scopes() -> dict[str, dict[str, object]]:
    code = b"\x00\x00\x00\xf9" * 3
    return {
        "prepareLayer": {
            "name": "prepareLayer",
            "startAddress": 0x1_9000_0000,
            "endAddress": 0x1_9000_0000 + len(code),
            "byteCount": len(code),
            "code": code,
        }
    }


def register_record(name: str, byte_count: int, value: int = 0) -> dict[str, object]:
    payload = value.to_bytes(byte_count, "little")
    record: dict[str, object] = {
        "name": name,
        "byteCount": byte_count,
        "hex": payload.hex(),
        "valueString": f"0x{value:x}",
    }
    if byte_count <= 8:
        record["unsignedValue"] = value
    return record


def semantic_registers(
    *,
    pc: int,
    sp: int,
    x3: int = 0,
    general_values: dict[str, int] | None = None,
    v0: bytes | None = None,
) -> dict[str, object]:
    overrides = {} if general_values is None else general_values
    general = []
    for name in validator.full_base.GENERAL_REGISTER_NAMES:
        byte_count = 4 if name == "cpsr" else 8
        value = {"pc": pc, "sp": sp, "x3": x3, **overrides}.get(name, 0)
        general.append(register_record(name, byte_count, value))
    simd = []
    for name in validator.full_base.SIMD_REGISTER_NAMES:
        byte_count = 4 if name in {"fpsr", "fpcr"} else 16
        record = register_record(name, byte_count)
        if name == "v0" and v0 is not None:
            if len(v0) != 16:
                raise ValueError("fixture v0 byte count differs")
            record["hex"] = v0.hex()
        simd.append(record)
    return {"general": general, "simd": simd}


def memory_snapshot(
    address: int, byte_count: int, payload: bytes | None = None
) -> dict[str, object]:
    if payload is None:
        payload = bytes(byte_count)
    if len(payload) != byte_count:
        raise ValueError("fixture memory byte count differs")
    return {
        "address": address,
        "byteCount": byte_count,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "hex": payload.hex(),
    }


def dod_instruction(start: int, offset: int) -> dict[str, object]:
    terminal = offset == validator.SEMANTIC_DOD_RETURN_OFFSET
    return {
        "pc": start + offset,
        "scopeName": validator.SEMANTIC_DOD_SCOPE_NAME,
        "scopeOffset": offset,
        "prepareLayerRelativeOffset": -90584 + offset,
        "rawLittleEndianHex": (
            validator.SEMANTIC_DOD_RETURN_RAW_LITTLE_ENDIAN_HEX
            if terminal
            else "7f2303d5"
        ),
        "mnemonic": "retab" if terminal else "pacibsp",
        "operands": "",
        "comment": "",
        "potentialWriter": False,
        "potentialCall": False,
    }


def semantic_fixture() -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    start = 0x1_8000_0000
    caller = 0x1_9000_0000
    sp = 0x1_7000_C000
    target = IDENTITY["roleBase"] + validator.full_base.AGGREGATE_OFFSET
    aggregate = struct.pack("<4d", 0.0, -0.0, 640.0, 640.0)
    code = bytearray(validator.SEMANTIC_DOD_RETURN_OFFSET + 4)
    code[0:4] = bytes.fromhex("7f2303d5")
    code[-4:] = bytes.fromhex(validator.SEMANTIC_DOD_RETURN_RAW_LITTLE_ENDIAN_HEX)
    semantic_scopes = {
        "prepareLayer": {
            "name": "prepareLayer",
            "startAddress": start + 90584,
            "endAddress": start + 90588,
            "byteCount": 4,
            "code": bytes(4),
        },
        validator.SEMANTIC_DOD_SCOPE_NAME: {
            "name": validator.SEMANTIC_DOD_SCOPE_NAME,
            "startAddress": start,
            "endAddress": start + len(code),
            "byteCount": len(code),
            "code": bytes(code),
        },
    }
    instructions = [
        dod_instruction(start, validator.SEMANTIC_DOD_ENTRY_OFFSET),
        dod_instruction(start, validator.SEMANTIC_DOD_RETURN_OFFSET),
    ]
    steps = []
    for index, instruction_value in enumerate(instructions):
        terminal = index == 1
        steps.append(
            {
                "stepIndex": index,
                "kind": "scope-instruction",
                "aggregateBeforeHex": aggregate.hex(),
                "aggregateAfterHex": aggregate.hex(),
                "aggregateChanged": False,
                "changedLaneOffsets": [],
                "instruction": instruction_value,
                "opaqueBoundary": None,
                "resultPC": caller if terminal else instructions[1]["pc"],
                "resultFunction": "caller" if terminal else "glass DOD",
                "transitionIndex": None,
            }
        )
    states = []
    for index, instruction_value in enumerate(instructions):
        states.append(
            {
                "stateIndex": index,
                "stepIndex": index,
                "instruction": instruction_value,
                "aggregateBeforeHex": aggregate.hex(),
                "registers": semantic_registers(
                    pc=instruction_value["pc"], sp=sp, x3=target
                ),
                "stack": memory_snapshot(sp, validator.SEMANTIC_STACK_BYTE_COUNT),
            }
        )
    digest = hashlib.sha256(
        json.dumps(
            states,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    document = {
        "instructionSteps": steps,
        "semanticDODEntries": [
            {
                "entryIndex": 0,
                "stepIndex": 0,
                "pc": start,
                "argumentX3": target,
                "x3Register": register_record("x3", 8, target),
                "targetAggregateAddress": target,
                "argumentMatchesTarget": True,
            }
        ],
        "semanticDODInvocation": {
            "entryRecordIndex": 0,
            "entryStepIndex": 0,
            "entryPC": start,
            "entryArgumentX3": target,
            "targetAggregateAddress": target,
            "aggregateAtEntryHex": aggregate.hex(),
            "returnStepIndex": 1,
            "returnInstructionStateIndex": 1,
            "returnPC": caller,
            "returnFunction": "caller",
            "aggregateAtReturnHex": aggregate.hex(),
            "instructionStateCount": len(states),
            "instructionStatesSHA256": digest,
            "returnRegisters": semantic_registers(pc=caller, sp=sp, x3=target),
            "returnStack": memory_snapshot(sp, validator.SEMANTIC_STACK_BYTE_COUNT),
        },
        "semanticDODInstructionStates": states,
        "semanticDODActive": False,
        "semanticDODFinished": True,
        "finalSemanticDODEntryCount": 1,
        "finalSemanticDODInstructionStateCount": len(states),
    }
    return document, semantic_scopes


def crop_instruction(
    scope: str,
    start: int,
    offset: int,
    raw: str,
    mnemonic: str,
    *,
    writer: bool = False,
) -> dict[str, object]:
    relative = offset
    if scope == validator.SEMANTIC_CROP_SCOPE_NAME:
        relative += 40128
    return {
        "pc": start + offset,
        "scopeName": scope,
        "scopeOffset": offset,
        "prepareLayerRelativeOffset": relative,
        "rawLittleEndianHex": raw,
        "mnemonic": mnemonic,
        "operands": "",
        "comment": "",
        "potentialWriter": writer,
        "potentialCall": False,
    }


def crop_step(
    index: int,
    instruction_value: dict[str, object],
    aggregate: bytes,
    result_pc: int,
) -> dict[str, object]:
    return {
        "stepIndex": index,
        "kind": "scope-instruction",
        "aggregateBeforeHex": aggregate.hex(),
        "aggregateAfterHex": aggregate.hex(),
        "aggregateChanged": False,
        "changedLaneOffsets": [],
        "instruction": instruction_value,
        "opaqueBoundary": None,
        "resultPC": result_pc,
        "resultFunction": "caller",
        "transitionIndex": None,
    }


def crop_argument_memory(addresses: dict[str, int]) -> list[dict[str, object]]:
    return [
        {
            "registerName": name,
            "memory": memory_snapshot(
                addresses[name], validator.SEMANTIC_CROP_ARGUMENT_MEMORY_BYTE_COUNT
            ),
        }
        for name in ("x0", "x1", "x2", "x3", "x4", "x5")
    ]


def crop_fixture() -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    prepare_start = 0x1_9000_0000
    crop_start = prepare_start + 40128
    aggregate = bytes(validator.full_base.AGGREGATE_BYTE_COUNT)
    sp = 0x1_7000_C000
    crop_code = bytearray(12)
    crop_code[0:4] = bytes.fromhex("7f2303d5")
    crop_code[8:12] = bytes.fromhex("c0035fd6")
    prepare_code = bytearray(validator.CROP_UNION_INPUT_RELATIVE_OFFSET + 4)
    prepare_code[
        validator.CROP_STORE_RELATIVE_OFFSET : validator.CROP_STORE_RELATIVE_OFFSET + 4
    ] = bytes.fromhex(validator.CROP_STORE_RAW_LITTLE_ENDIAN_HEX)
    prepare_code[
        validator.CROP_UNION_INPUT_RELATIVE_OFFSET : validator.CROP_UNION_INPUT_RELATIVE_OFFSET
        + 4
    ] = bytes.fromhex(validator.CROP_UNION_INPUT_RAW_LITTLE_ENDIAN_HEX)
    semantic_scopes = {
        "prepareLayer": {
            "name": "prepareLayer",
            "startAddress": prepare_start,
            "endAddress": prepare_start + len(prepare_code),
            "byteCount": len(prepare_code),
            "code": bytes(prepare_code),
        },
        validator.SEMANTIC_CROP_SCOPE_NAME: {
            "name": validator.SEMANTIC_CROP_SCOPE_NAME,
            "startAddress": crop_start,
            "endAddress": crop_start + len(crop_code),
            "byteCount": len(crop_code),
            "code": bytes(crop_code),
        },
    }
    steps = []
    states = []
    invocations = []
    stores = []
    unions = []
    for invocation_index in range(4):
        caller_role = (
            IDENTITY["roleBase"]
            if invocation_index == 3
            else 0x1_7100_0000 + invocation_index * 0x10_000
        )
        target = caller_role + validator.SEMANTIC_CROP_CALLER_ROLE_OFFSET
        addresses = {
            "x0": 0x2_1000_0000 + invocation_index * 0x10_000,
            "x1": 0x2_2000_0000 + invocation_index * 0x10_000,
            "x2": 0x2_3000_0000 + invocation_index * 0x10_000,
            "x3": 0x2_4000_0000 + invocation_index * 0x10_000,
            "x4": caller_role + 0x420,
            "x5": target,
        }
        entry_index = len(steps)
        entry_instruction = crop_instruction(
            validator.SEMANTIC_CROP_SCOPE_NAME,
            crop_start,
            0,
            "7f2303d5",
            "pacibsp",
        )
        return_instruction = crop_instruction(
            validator.SEMANTIC_CROP_SCOPE_NAME,
            crop_start,
            8,
            "c0035fd6",
            "ret",
        )
        steps.append(
            crop_step(entry_index, entry_instruction, aggregate, crop_start + 8)
        )
        return_index = len(steps)
        caller_pc = prepare_start + 0x2000 + invocation_index * 0x100
        steps.append(crop_step(return_index, return_instruction, aggregate, caller_pc))
        start = len(states)
        for local_index, (step_index, instruction_value) in enumerate(
            ((entry_index, entry_instruction), (return_index, return_instruction))
        ):
            state_registers = semantic_registers(
                pc=instruction_value["pc"],
                sp=sp,
                general_values={**addresses, "x19": caller_role},
            )
            states.append(
                {
                    "stateIndex": len(states),
                    "invocationIndex": invocation_index,
                    "invocationStateIndex": local_index,
                    "stepIndex": step_index,
                    "instruction": instruction_value,
                    "aggregateBeforeHex": aggregate.hex(),
                    "registers": state_registers,
                    "stack": memory_snapshot(sp, validator.SEMANTIC_STACK_BYTE_COUNT),
                    "target": memory_snapshot(
                        target, validator.SEMANTIC_CROP_TARGET_BYTE_COUNT
                    ),
                }
            )
        invocation_states = states[start:]
        invocations.append(
            {
                "invocationIndex": invocation_index,
                "entryStepIndex": entry_index,
                "entryPC": crop_start,
                "entryArgumentRegisters": [
                    register_record(name, 8, addresses[name])
                    for name in ("x0", "x1", "x2", "x3", "x4", "x5")
                ],
                "entryArgumentAddresses": addresses,
                "entryArgumentMemory": crop_argument_memory(addresses),
                "callerRoleBase": caller_role,
                "callerRoleAtEntry": memory_snapshot(
                    caller_role, validator.SEMANTIC_CROP_CALLER_ROLE_BYTE_COUNT
                ),
                "targetAddress": target,
                "targetAtEntry": memory_snapshot(
                    target, validator.SEMANTIC_CROP_TARGET_BYTE_COUNT
                ),
                "aggregateAtEntryHex": aggregate.hex(),
                "instructionStateStartIndex": start,
                "storeLinkIndex": invocation_index if invocation_index < 3 else None,
                "returnStepIndex": return_index,
                "returnInstructionStateIndex": len(states) - 1,
                "returnInstructionScopeOffset": 8,
                "returnInstructionRawLittleEndianHex": "c0035fd6",
                "returnInstructionMnemonic": "ret",
                "returnPC": caller_pc,
                "returnFunction": "caller",
                "returnArgumentMemory": crop_argument_memory(addresses),
                "callerRoleAtReturn": memory_snapshot(
                    caller_role, validator.SEMANTIC_CROP_CALLER_ROLE_BYTE_COUNT
                ),
                "targetAtReturn": memory_snapshot(
                    target, validator.SEMANTIC_CROP_TARGET_BYTE_COUNT
                ),
                "aggregateAtReturnHex": aggregate.hex(),
                "instructionStateCount": len(invocation_states),
                "instructionStatesSHA256": hashlib.sha256(
                    json.dumps(
                        invocation_states,
                        sort_keys=True,
                        separators=(",", ":"),
                        allow_nan=False,
                    ).encode("utf-8")
                ).hexdigest(),
                "returnRegisters": semantic_registers(pc=caller_pc, sp=sp),
                "returnStack": memory_snapshot(sp, validator.SEMANTIC_STACK_BYTE_COUNT),
            }
        )
        if invocation_index == 3:
            continue
        crop = struct.pack("<4i", 490 + invocation_index, 166, 360, 368)
        destination_base = 0x2_9000_0000 + invocation_index * 0x1000
        store_index = len(steps)
        store_instruction = crop_instruction(
            "prepareLayer",
            prepare_start,
            validator.CROP_STORE_RELATIVE_OFFSET,
            validator.CROP_STORE_RAW_LITTLE_ENDIAN_HEX,
            "str",
            writer=True,
        )
        steps.append(
            crop_step(
                store_index,
                store_instruction,
                aggregate,
                store_instruction["pc"] + 4,
            )
        )
        stores.append(
            {
                "storeLinkIndex": invocation_index,
                "sourceInvocationIndex": invocation_index,
                "stepIndex": store_index,
                "instruction": store_instruction,
                "registers": semantic_registers(
                    pc=store_instruction["pc"],
                    sp=sp,
                    general_values={"x19": caller_role, "x28": destination_base},
                    v0=crop,
                ),
                "callerRoleBase": caller_role,
                "sourceIntegerAddress": (
                    caller_role + validator.CROP_INTEGER_SOURCE_OFFSET
                ),
                "sourceInteger": memory_snapshot(
                    caller_role + validator.CROP_INTEGER_SOURCE_OFFSET,
                    validator.CROP_INTEGER_BYTE_COUNT,
                    crop,
                ),
                "destinationAddress": (
                    destination_base + validator.CROP_DESTINATION_OFFSET
                ),
                "destinationBefore": memory_snapshot(
                    destination_base + validator.CROP_DESTINATION_OFFSET,
                    validator.CROP_INTEGER_BYTE_COUNT,
                ),
                "destinationAfter": memory_snapshot(
                    destination_base + validator.CROP_DESTINATION_OFFSET,
                    validator.CROP_INTEGER_BYTE_COUNT,
                    crop,
                ),
                "returnPC": store_instruction["pc"] + 4,
                "unionInputIndex": invocation_index,
            }
        )
        union_index = len(steps)
        union_instruction = crop_instruction(
            "prepareLayer",
            prepare_start,
            validator.CROP_UNION_INPUT_RELATIVE_OFFSET,
            validator.CROP_UNION_INPUT_RAW_LITTLE_ENDIAN_HEX,
            "ldp",
        )
        steps.append(
            crop_step(
                union_index,
                union_instruction,
                aggregate,
                union_instruction["pc"] + 4,
            )
        )
        state = bytearray(validator.CROP_UNION_STATE_BYTE_COUNT)
        crop_offset = (
            validator.CROP_DESTINATION_OFFSET - validator.CROP_UNION_STATE_OFFSET
        )
        state[crop_offset : crop_offset + len(crop)] = crop
        unions.append(
            {
                "unionInputIndex": invocation_index,
                "sourceStoreLinkIndex": invocation_index,
                "stepIndex": union_index,
                "instruction": union_instruction,
                "registers": semantic_registers(
                    pc=union_instruction["pc"],
                    sp=sp,
                    general_values={"x28": destination_base},
                ),
                "layerShapesBase": destination_base,
                "stateAddress": destination_base + validator.CROP_UNION_STATE_OFFSET,
                "state": memory_snapshot(
                    destination_base + validator.CROP_UNION_STATE_OFFSET,
                    validator.CROP_UNION_STATE_BYTE_COUNT,
                    bytes(state),
                ),
            }
        )
    document = {
        "instructionSteps": steps,
        "opaqueCalleeBoundaries": [],
        "semanticCropInvocations": invocations,
        "semanticCropInstructionStates": states,
        "semanticCropStoreLinks": stores,
        "semanticCropUnionInputs": unions,
        "semanticCropActiveInvocationIndex": None,
        "semanticCropCompletedInvocationCount": 4,
        "finalSemanticCropInvocationCount": 4,
        "finalSemanticCropInstructionStateCount": len(states),
        "finalSemanticCropStoreLinkCount": 3,
        "finalSemanticCropUnionInputCount": 3,
    }
    return document, semantic_scopes


def manual_marker(index: int, hit: int, x28: int, result: str) -> dict[str, object]:
    value: dict[str, object] = {
        "manualSelectionMarkerIndex": index,
        "markerHitIndex": hit,
        "pc": 0x1_9000_0000 + validator.SELECTION_MARKER_OFFSET,
        "threadID": IDENTITY["threadID"],
        "framePointer": IDENTITY["framePointer"],
        "observedRoleBase": IDENTITY["roleBase"],
        "observedX28": x28,
        "selectedSource": 0xA_BEEF_0000,
        "selectedIdentity": dict(IDENTITY),
        "prepareRecursionDepth": validator.TARGET_PREPARE_RECURSION_DEPTH,
        "frameIdentityMatches": True,
        "sourceRegisterMatches": x28 == 0xA_BEEF_0000,
        "result": result,
    }
    if result == "selected":
        value["callbackSequence"] = 99
    return value


def source_link_cells(
    registers: dict[str, int], source: int, *, second_value: int | None = None
) -> list[dict[str, object]]:
    result = []
    for index, spec in enumerate(validator.SOURCE_LINK_CELL_SPECS):
        base = registers[spec["baseRegister"]]
        address = base + spec["signedOffset"]
        observed = source if index == 0 or second_value is None else second_value
        payload = observed.to_bytes(8, "little")
        result.append(
            {
                **spec,
                "baseValue": base,
                "address": address,
                "memory": {
                    "address": address,
                    "byteCount": 8,
                    "hex": payload.hex(),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                },
                "observedValue": observed,
                "selectedSourceMatches": observed == source,
            }
        )
    return result


class PrepareLayerInstructionTraceValidatorTests(unittest.TestCase):
    def test_complete_semantic_dod_register_trace_passes(self):
        document, semantic_scopes = semantic_fixture()
        result = validator._semantic_dod_trace(document, semantic_scopes, IDENTITY)
        self.assertEqual(result["entryStepIndex"], 0)
        self.assertEqual(result["returnStepIndex"], 1)
        self.assertEqual(result["instructionStateCount"], 2)

    def test_semantic_dod_entry_pointer_substitution_fails_closed(self):
        document, semantic_scopes = semantic_fixture()
        document["semanticDODEntries"][0]["argumentX3"] += 8
        with self.assertRaisesRegex(ValueError, "entry 0 differs"):
            validator._semantic_dod_trace(document, semantic_scopes, IDENTITY)

    def test_missing_semantic_dod_instruction_state_fails_closed(self):
        document, semantic_scopes = semantic_fixture()
        document["semanticDODInstructionStates"].pop()
        with self.assertRaisesRegex(ValueError, "state inventory differs"):
            validator._semantic_dod_trace(document, semantic_scopes, IDENTITY)

    def test_semantic_dod_register_or_stack_tampering_fails_closed(self):
        document, semantic_scopes = semantic_fixture()
        registers = document["semanticDODInstructionStates"][0]["registers"]
        registers["general"][3]["unsignedValue"] += 1
        with self.assertRaisesRegex(ValueError, "raw value differs"):
            validator._semantic_dod_trace(document, semantic_scopes, IDENTITY)

        document, semantic_scopes = semantic_fixture()
        document["semanticDODInstructionStates"][0]["stack"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "identity differs"):
            validator._semantic_dod_trace(document, semantic_scopes, IDENTITY)

    def test_complete_background_filter_crop_trace_passes(self):
        document, semantic_scopes = crop_fixture()
        result = validator._semantic_crop_trace(document, semantic_scopes, IDENTITY)
        self.assertEqual(result["invocationCount"], 4)
        self.assertEqual(result["instructionStateCount"], 8)
        self.assertEqual(len(result["storeLinks"]), 3)
        self.assertEqual(len(result["unionInputs"]), 3)
        self.assertEqual(result["unionInputs"][-1]["cropI32"], [492, 166, 360, 368])

    def test_crop_target_or_state_tampering_fails_closed(self):
        document, semantic_scopes = crop_fixture()
        document["semanticCropInstructionStates"][0]["target"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "identity differs"):
            validator._semantic_crop_trace(document, semantic_scopes, IDENTITY)

        document, semantic_scopes = crop_fixture()
        document["semanticCropInvocations"][1]["targetAddress"] += 8
        with self.assertRaisesRegex(ValueError, "target relation differs"):
            validator._semantic_crop_trace(document, semantic_scopes, IDENTITY)

    def test_crop_store_and_union_substitution_fails_closed(self):
        document, semantic_scopes = crop_fixture()
        document["semanticCropStoreLinks"][1]["sourceInvocationIndex"] = 0
        with self.assertRaisesRegex(ValueError, "semantic crop store 1 differs"):
            validator._semantic_crop_trace(document, semantic_scopes, IDENTITY)

        document, semantic_scopes = crop_fixture()
        union = document["semanticCropUnionInputs"][2]["state"]
        payload = bytearray.fromhex(union["hex"])
        payload[16] ^= 1
        union["hex"] = payload.hex()
        union["sha256"] = hashlib.sha256(payload).hexdigest()
        with self.assertRaisesRegex(ValueError, "semantic crop union input 2 differs"):
            validator._semantic_crop_trace(document, semantic_scopes, IDENTITY)

    def test_dual_source_link_requires_both_exact_cells(self):
        source = 0xA_BEEF_0000
        registers = {
            "x10": 0x1_1000_0000,
            "x20": 0xA_2000_0000,
        }
        self.assertTrue(
            validator._source_link_cells(
                source_link_cells(registers, source),
                "epoch",
                registers,
                source,
            )
        )
        self.assertFalse(
            validator._source_link_cells(
                source_link_cells(registers, source, second_value=0),
                "epoch",
                registers,
                source,
            )
        )

    def test_source_link_rejects_missing_or_forged_cell_evidence(self):
        source = 0xA_BEEF_0000
        registers = {
            "x10": 0x1_1000_0000,
            "x20": 0xA_2000_0000,
        }
        values = source_link_cells(registers, source)
        with self.assertRaisesRegex(ValueError, "inventory differs"):
            validator._source_link_cells(values[:1], "epoch", registers, source)
        values[1]["observedValue"] = 0
        with self.assertRaisesRegex(ValueError, "cell 1 differs"):
            validator._source_link_cells(values, "epoch", registers, source)

    def test_known_bitwise_state_sequence_passes(self):
        result = validator._known_state_sequence(known_states())
        self.assertEqual(result["carrierP"], 481.25)
        self.assertEqual(result["integerOriginL"], 480)
        self.assertEqual(result["orderedStateIndices"], [0, 1, 2, 3])

    def test_missing_padded_state_fails_closed(self):
        values = known_states()
        with self.assertRaisesRegex(ValueError, "known aggregate state transfer"):
            validator._known_state_sequence([values[0], values[1], values[3]])

    def test_nonfinite_final_state_fails_closed(self):
        values = known_states()
        values[-1] = struct.pack("<4d", 480.0, float("nan"), 641.25, 649.25)
        with self.assertRaisesRegex(ValueError, "non-finite"):
            validator._known_state_sequence(values)

    def test_instruction_bytes_must_match_frozen_scope(self):
        value = instruction(0)
        self.assertEqual(
            validator._instruction(value, "instruction", scopes())["pc"],
            0x1_9000_0000,
        )
        value["rawLittleEndianHex"] = "010000f9"
        with self.assertRaisesRegex(ValueError, "instruction differs"):
            validator._instruction(value, "instruction", scopes())

    def test_continuous_changed_instruction_chain_passes(self):
        states = known_states()
        document = {
            "instructionSteps": [
                step(index, states[index], states[index + 1]) for index in range(3)
            ],
            "aggregateTransitions": [
                transition(index, states[index], states[index + 1])
                for index in range(3)
            ],
            "opaqueCalleeBoundaries": [],
        }
        order = {
            1: "aggregate-instruction-transition",
            2: "aggregate-instruction-transition",
            3: "aggregate-instruction-transition",
        }
        with (
            mock.patch.object(validator, "_context"),
            mock.patch.object(validator, "_after_context"),
        ):
            observed, transitions = validator._steps_and_transitions(
                document, order, scopes(), IDENTITY, states[0], {}
            )
        self.assertEqual(observed, states)
        self.assertEqual(len(transitions), 3)

    def test_discontinuous_instruction_chain_fails_closed(self):
        states = known_states()
        document = {
            "instructionSteps": [
                step(0, states[0], states[1]),
                step(1, states[0], states[2]),
            ],
            "aggregateTransitions": [
                transition(0, states[0], states[1]),
                transition(1, states[0], states[2]),
            ],
            "opaqueCalleeBoundaries": [],
        }
        with (
            mock.patch.object(validator, "_context"),
            mock.patch.object(validator, "_after_context"),
        ):
            with self.assertRaisesRegex(ValueError, "continuity differs"):
                validator._steps_and_transitions(
                    document,
                    {
                        1: "aggregate-instruction-transition",
                        2: "aggregate-instruction-transition",
                    },
                    scopes(),
                    IDENTITY,
                    states[0],
                    {},
                )

    def test_changed_opaque_boundary_fails_closed(self):
        states = known_states()
        boundary = {
            "boundaryIndex": 0,
            "entryFrame": {},
            "returnFrame": {},
            "aggregateChanged": True,
        }
        opaque_step = {
            "stepIndex": 0,
            "kind": "opaque-callee-step-out",
            "aggregateBeforeHex": states[0].hex(),
            "aggregateAfterHex": states[1].hex(),
            "aggregateChanged": True,
            "changedLaneOffsets": [0, 8, 16, 24],
            "instruction": None,
            "opaqueBoundary": boundary,
            "resultPC": 1,
            "resultFunction": "caller",
            "transitionIndex": 0,
        }
        with self.assertRaisesRegex(ValueError, "opaque mutation"):
            validator._steps_and_transitions(
                {
                    "instructionSteps": [opaque_step],
                    "aggregateTransitions": [],
                    "opaqueCalleeBoundaries": [boundary],
                },
                {},
                scopes(),
                IDENTITY,
                states[0],
                {},
            )

    def test_changed_instruction_requires_writer_or_call_decode(self):
        states = known_states()
        document = {
            "instructionSteps": [step(0, states[0], states[1])],
            "aggregateTransitions": [transition(0, states[0], states[1])],
            "opaqueCalleeBoundaries": [],
        }
        document["instructionSteps"][0]["instruction"]["potentialWriter"] = False
        document["aggregateTransitions"][0]["instruction"]["potentialWriter"] = False
        with self.assertRaisesRegex(ValueError, "aggregate transition 0 differs"):
            validator._steps_and_transitions(
                document,
                {1: "aggregate-instruction-transition"},
                scopes(),
                IDENTITY,
                states[0],
                {},
            )

    def test_failed_envelope_never_reaches_inherited_context(self):
        trace = {
            "prepareLayerInstructionTraceSchemaVersion": (
                validator.EXPECTED_TRACE_SCHEMA_VERSION
            ),
            "classification": validator.EXPECTED_CLASSIFICATION,
            "status": "finalized",
            "statusBeforeFinalization": "selected-instruction-path-failed",
            "configuration": copy.deepcopy(validator.EXPECTED_CONFIGURATION),
            "failures": [{"stage": "trace", "message": "failed"}],
            "finalFailureCount": 1,
        }
        with mock.patch.object(
            validator.active_validator, "_inherited_frame_context"
        ) as inherited:
            with self.assertRaisesRegex(ValueError, "envelope differs"):
                validator.validate_documents(trace, {})
        inherited.assert_not_called()

    def test_manual_trace_crosses_rejected_marker_before_exact_source(self):
        document = {
            "manualSelectionMarkers": [
                manual_marker(0, 2, 0xA_BAD_0000, "rejected"),
                manual_marker(1, 3, 0xA_BEEF_0000, "selected"),
            ]
        }
        self.assertEqual(
            validator._manual_selection_markers(
                document,
                {99: "selected-instruction-path-closed"},
                0x1_9000_0000,
                IDENTITY,
                0xA_BEEF_0000,
            ),
            (1, 99),
        )

    def test_manual_trace_cannot_reject_the_exact_source_identity(self):
        document = {
            "manualSelectionMarkers": [manual_marker(0, 2, 0xA_BEEF_0000, "rejected")]
        }
        with self.assertRaisesRegex(ValueError, "rejection differs"):
            validator._manual_selection_markers(
                document,
                {},
                0x1_9000_0000,
                IDENTITY,
                0xA_BEEF_0000,
            )

    def test_configuration_never_authorizes_product_changes(self):
        self.assertIn("product-parity-remain-sealed", validator.EXPECTED_CLASSIFICATION)
        self.assertIn(
            "no aggregate change",
            validator.EXPECTED_CONFIGURATION["opaqueBoundaryRule"],
        )


if __name__ == "__main__":
    unittest.main()
