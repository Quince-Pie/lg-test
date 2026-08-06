#!/usr/bin/env python3
"""Unit contracts for the Group.margin execution validator."""

from __future__ import annotations

import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

import validate_backdrop_margin_group_execution as validator


class BackdropMarginGroupExecutionValidatorTests(unittest.TestCase):
    def test_snapshot_requires_exact_bytes_address_and_digest(self) -> None:
        payload = struct.pack("<d", 83.0)
        snapshot = {
            "address": 0x1234,
            "byteCount": len(payload),
            "hex": payload.hex(),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        self.assertEqual(
            validator.validate_snapshot(snapshot, 0x1234, 8, "test"), payload
        )
        altered = dict(snapshot, address=0x1235)
        with self.assertRaisesRegex(ValueError, "metadata differs"):
            validator.validate_snapshot(altered, 0x1234, 8, "test")

    def test_vector_validation_preserves_low_binary64_word(self) -> None:
        low = struct.pack("<d", 83.0)
        payload = low + bytes(8)
        vector = {
            "byteCount": 16,
            "rawLittleEndianHex": payload.hex(),
            "lowF64RawLittleEndianHex": low.hex(),
            "lowF64": 83.0,
            "lowF64Finite": True,
        }
        self.assertEqual(validator.validate_vector(vector, "v8"), low)
        vector["lowF64RawLittleEndianHex"] = bytes(8).hex()
        with self.assertRaisesRegex(ValueError, "low word differs"):
            validator.validate_vector(vector, "v8")

    def test_preregistration_keeps_every_live_operand_unknown(self) -> None:
        value = {
            "backdropMarginGroupExecutionPreregistrationSchemaVersion": 1,
            "profile": {
                "material": "regular",
                "appearance": "light",
                "direction": "materialize",
                "geometry": "circle-127-center",
                "exactPublicProfilePreviouslyCaptured": True,
                "exactGroupExecutionPreviouslyCaptured": False,
            },
            "openedProducer": {
                "function": validator.PRODUCER_FUNCTION,
                "swiftUICoreUUID": validator.SWIFTUICORE_UUID,
                "moduleOffset": validator.PRODUCER_MODULE_OFFSET,
                "symbolByteCount": validator.PRODUCER_BYTE_COUNT,
                "codeSHA256": validator.PRODUCER_CODE_SHA256,
                "callerFunction": validator.CALLER_FUNCTION,
                "callerReturnAfterProducerOffset": 5764,
                "directCallInstructionOffsets": validator.DIRECT_CALL_OFFSETS,
                "directCallTargetModuleOffsets": (
                    validator.DIRECT_TARGET_MODULE_OFFSETS
                ),
                "stageInstructionOffsets": sorted(validator.STAGES),
            },
            "unknownBeforeCapture": {
                key: None
                for key in (
                    "groupRecordCount",
                    "groupRecordBytes",
                    "sideTableBytes",
                    "taggedPayloadBytes",
                    "discriminatorSequence",
                    "directCalleeSymbols",
                    "directCalleeCodeHashes",
                    "branchOperands",
                    "accumulatorWords",
                    "nestedIndirectTarget",
                )
            },
            "acceptance": {
                key: True
                for key in (
                    "requireExactProducerCode",
                    "requireExactCallerCallsite",
                    "requireCompleteSelectedInvocations",
                    "requireRawGroupRecords",
                    "requireRawSideTableAndTaggedPayloads",
                    "requireEveryDiscriminatorAndAccumulatorStage",
                    "requireExactBranchStageSequence",
                    "requireGetterReturnToMatchAdjacentSetterBitwise",
                    "requireNoValueBasedSelection",
                    "zeroTolerance",
                )
            },
        }
        self.assertIs(validator.validate_preregistration(value), value)
        value["unknownBeforeCapture"]["branchOperands"] = []
        with self.assertRaisesRegex(ValueError, "was not sealed"):
            validator.validate_preregistration(value)

    def test_each_discriminator_has_one_exact_branch_stage_sequence(self) -> None:
        self.assertEqual(
            validator.expected_record_stage_offsets(2),
            [0x0BC, 0x0D8, 0x148, 0x278],
        )
        self.assertEqual(
            validator.expected_record_stage_offsets(3),
            [0x0BC, 0x0D8, 0x148, 0x278],
        )
        self.assertEqual(
            validator.expected_record_stage_offsets(1),
            [0x0BC, 0x184, 0x1F8, 0x278],
        )
        self.assertEqual(
            validator.expected_record_stage_offsets(21),
            [0x0BC, 0x16C, 0x278],
        )
        self.assertEqual(
            validator.expected_record_stage_offsets(22),
            [0x0BC, 0x20C, 0x268, 0x26C, 0x278],
        )
        self.assertEqual(validator.expected_record_stage_offsets(0), [0x0BC, 0x278])

    def test_cli_result_is_strict_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "value.json"
            path.write_text(json.dumps({"value": 83.0}), encoding="utf-8")
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")), {"value": 83.0}
            )


if __name__ == "__main__":
    unittest.main()
