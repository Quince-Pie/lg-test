#!/usr/bin/env python3
"""Tests for the opened inline integer-crop semantic decoder."""

import copy
import hashlib
import struct
import unittest
from unittest import mock

import analyze_prepare_layer_crop_writer_semantics as analyzer
import validate_prepare_layer_instruction_trace as validator
from test_validate_prepare_layer_instruction_trace import (
    crop_argument_memory,
    crop_instruction,
    memory_snapshot,
    semantic_registers,
)


INPUT_RECTS = (
    (491.993896484375, 167.50625610351562, 356.84995422363284, 364.4998474121094),
    (490.0, 166.0, 360.0, 368.0),
    (490.0, 166.0, 360.0, 368.0),
    (490.0, -115.993896484375, 641.993896484375, 649.993896484375),
)


def step(index: int, instruction: dict[str, object]) -> dict[str, object]:
    return {
        "stepIndex": index,
        "kind": "scope-instruction",
        "instruction": instruction,
    }


def prepare_instruction(offset: int, raw: str) -> dict[str, object]:
    return {
        "scopeName": "prepareLayer",
        "scopeOffset": offset,
        "rawLittleEndianHex": raw,
        "mnemonic": "synthetic",
        "operands": "",
    }


def analysis_fixture() -> tuple[dict[str, object], dict[str, object]]:
    steps = []
    states = []
    invocations = []
    stores = []
    crop_start = 0x1_9000_0000
    sp = 0x1_7000_C000
    for invocation_index, rect in enumerate(INPUT_RECTS):
        caller_role = 0x1_7100_0000 + invocation_index * 0x10_000
        target = caller_role + validator.SEMANTIC_CROP_CALLER_ROLE_OFFSET
        addresses = {
            "x0": 0x2_1000_0000 + invocation_index * 0x10_000,
            "x1": 0x2_2000_0000 + invocation_index * 0x10_000,
            "x2": 0x2_3000_0000 + invocation_index * 0x10_000,
            "x3": 0x2_4000_0000 + invocation_index * 0x10_000,
            "x4": caller_role + 0x420,
            "x5": target,
        }
        state_start = len(states)
        entry_step = len(steps)
        for local_index, offset in enumerate(analyzer.ADD_BACKGROUND_NO_OP_OFFSETS):
            instruction = crop_instruction(
                validator.SEMANTIC_CROP_SCOPE_NAME,
                crop_start,
                offset,
                f"{offset:08x}"[-8:],
                "synthetic",
            )
            step_index = len(steps)
            steps.append(step(step_index, instruction))
            registers = semantic_registers(
                pc=crop_start + offset,
                sp=sp,
                general_values={
                    **addresses,
                    "x19": 0 if offset == 0x074 else caller_role,
                    "x24": 0,
                    "x14": 0,
                },
            )
            states.append(
                {
                    "stateIndex": len(states),
                    "invocationIndex": invocation_index,
                    "invocationStateIndex": local_index,
                    "stepIndex": step_index,
                    "instruction": instruction,
                    "registers": registers,
                }
            )
        return_step = len(steps) - 1
        rect_bytes = struct.pack("<4d", *rect)
        argument_entry = crop_argument_memory(addresses)
        argument_return = copy.deepcopy(argument_entry)
        for values in (argument_entry, argument_return):
            values[-1]["memory"] = memory_snapshot(
                target, validator.SEMANTIC_CROP_ARGUMENT_MEMORY_BYTE_COUNT
            )
        caller = memory_snapshot(
            caller_role, validator.SEMANTIC_CROP_CALLER_ROLE_BYTE_COUNT
        )
        target_memory = memory_snapshot(
            target, validator.SEMANTIC_CROP_TARGET_BYTE_COUNT, rect_bytes
        )
        invocations.append(
            {
                "invocationIndex": invocation_index,
                "entryStepIndex": entry_step,
                "returnStepIndex": return_step,
                "instructionStateStartIndex": state_start,
                "instructionStateCount": len(analyzer.ADD_BACKGROUND_NO_OP_OFFSETS),
                "entryArgumentMemory": argument_entry,
                "returnArgumentMemory": argument_return,
                "callerRoleBase": caller_role,
                "callerRoleAtEntry": caller,
                "callerRoleAtReturn": copy.deepcopy(caller),
                "targetAtEntry": target_memory,
                "targetAtReturn": copy.deepcopy(target_memory),
            }
        )
        for offset, raw in analyzer.CORE_INSTRUCTIONS.items():
            steps.append(step(len(steps), prepare_instruction(offset, raw)))
        for offset, raw in analyzer.FRACTIONAL_GUARD_INSTRUCTIONS.items():
            steps.append(step(len(steps), prepare_instruction(offset, raw)))
        if invocation_index in {0, 3}:
            for offset, raw in analyzer.PADDING_PATH_INSTRUCTIONS.items():
                steps.append(step(len(steps), prepare_instruction(offset, raw)))
        if invocation_index < 3:
            stores.append(
                {
                    "cropI32": [490, 166, 360, 368],
                }
            )
    trace = {
        "instructionSteps": steps,
        "semanticCropInvocations": invocations,
        "semanticCropInstructionStates": states,
    }
    validation = {
        "semanticCropTrace": {
            "invocationCount": 4,
            "changedOpaqueTargetBoundaryCount": 0,
            "storeLinks": stores,
        }
    }
    return trace, validation


class PrepareLayerCropWriterSemanticAnalysisTests(unittest.TestCase):
    def test_selected_crop_paths_replay_exactly(self) -> None:
        trace, validation = analysis_fixture()
        with mock.patch.object(
            analyzer.validator, "validate_documents", return_value=validation
        ):
            result = analyzer.analyze_documents(trace, {}, validation)
        self.assertEqual(result["addBackgroundNoOpInvocationCount"], 4)
        self.assertEqual(result["observedDownstreamCropCount"], 3)
        self.assertEqual(
            result["invocations"][0]["integerEnclosureI32"],
            [491, 167, 358, 366],
        )
        self.assertEqual(
            result["invocations"][0]["replayedWorkingCropI32"],
            [490, 166, 360, 368],
        )
        self.assertFalse(result["invocations"][1]["onePixelBorderExecuted"])
        self.assertEqual(
            result["invocations"][3]["replayedWorkingCropI32"],
            [489, -117, 644, 652],
        )
        self.assertTrue(result["conclusion"]["inlineFiniteCropEnclosureDecoded"])
        self.assertFalse(result["conclusion"]["productionShaderAuthorized"])

    def test_no_op_claim_rejects_argument_memory_mutation(self) -> None:
        trace, validation = analysis_fixture()
        changed = trace["semanticCropInvocations"][0]["returnArgumentMemory"][0][
            "memory"
        ]
        changed["hex"] = "01" + changed["hex"][2:]
        changed["sha256"] = hashlib.sha256(bytes.fromhex(changed["hex"])).hexdigest()
        with mock.patch.object(
            analyzer.validator, "validate_documents", return_value=validation
        ):
            with self.assertRaisesRegex(ValueError, "add-background memory changed"):
                analyzer.analyze_documents(trace, {}, validation)

    def test_crop_core_instruction_mutation_fails_closed(self) -> None:
        trace, validation = analysis_fixture()
        target = next(
            item
            for item in trace["instructionSteps"]
            if item["instruction"]["scopeName"] == "prepareLayer"
            and item["instruction"]["scopeOffset"] == 0x39C0
        )
        target["instruction"]["rawLittleEndianHex"] = "00000000"
        with mock.patch.object(
            analyzer.validator, "validate_documents", return_value=validation
        ):
            with self.assertRaisesRegex(ValueError, r"instruction \+0x39c0 differs"):
                analyzer.analyze_documents(trace, {}, validation)

    def test_clamp_constants_and_signed_enclosure_are_exact(self) -> None:
        self.assertEqual(analyzer.LOWER_BOUND.hex(), "-0x1.fffffff000000p+28")
        self.assertEqual(analyzer.UPPER_BOUND.hex(), "0x1.0000000000000p+29")
        clamped, enclosed = analyzer.integer_enclosure(
            (-600_000_000.0, -2.25, 2_000_000_000.0, 4.5)
        )
        self.assertEqual(clamped[0], analyzer.LOWER_BOUND)
        self.assertEqual(clamped[2], analyzer.UPPER_BOUND - analyzer.LOWER_BOUND)
        self.assertEqual(enclosed[1:], (-3, 1_073_741_823, 6))


if __name__ == "__main__":
    unittest.main()
