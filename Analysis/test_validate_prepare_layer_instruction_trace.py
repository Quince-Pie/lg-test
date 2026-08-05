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


def semantic_registers(*, pc: int, sp: int, x3: int) -> dict[str, object]:
    general = []
    for name in validator.full_base.GENERAL_REGISTER_NAMES:
        byte_count = 4 if name == "cpsr" else 8
        value = {"pc": pc, "sp": sp, "x3": x3}.get(name, 0)
        general.append(register_record(name, byte_count, value))
    simd = []
    for name in validator.full_base.SIMD_REGISTER_NAMES:
        byte_count = 4 if name in {"fpsr", "fpcr"} else 16
        simd.append(register_record(name, byte_count))
    return {"general": general, "simd": simd}


def memory_snapshot(address: int, byte_count: int) -> dict[str, object]:
    payload = bytes(byte_count)
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
