#!/usr/bin/env python3
"""Adversarial tests for the software-instruction trace gate."""

import copy
import hashlib
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
