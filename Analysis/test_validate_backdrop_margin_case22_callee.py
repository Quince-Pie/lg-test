#!/usr/bin/env python3
"""Unit contracts for the case-22 callee trace validator."""

from __future__ import annotations

import hashlib
import struct
import unittest

import validate_backdrop_margin_case22_callee as validator


def register(name: str, payload: bytes) -> dict[str, object]:
    result: dict[str, object] = {
        "name": name,
        "byteCount": len(payload),
        "hex": payload.hex(),
        "valueString": None,
    }
    if len(payload) <= 8:
        result["unsignedValue"] = int.from_bytes(payload, "little")
    return result


class BackdropMarginCase22CalleeValidatorTests(unittest.TestCase):
    def test_full_register_snapshot_requires_exact_names_and_bytes(self) -> None:
        snapshot = {
            "general": [
                register(name, struct.pack("<Q", index))
                for index, name in enumerate(validator.GENERAL_REGISTER_NAMES)
            ],
            "simd": [
                register(name, bytes([index % 256]) * (8 if name in ("fpsr", "fpcr") else 16))
                for index, name in enumerate(validator.SIMD_REGISTER_NAMES)
            ],
        }
        values = validator.validate_register_snapshot(snapshot, "test")
        self.assertEqual(values["x20"], 20)
        snapshot["general"][20]["unsignedValue"] = 21
        with self.assertRaisesRegex(ValueError, "scalar value differs"):
            validator.validate_register_snapshot(snapshot, "test")

    def test_symbol_requires_complete_self_hashed_code(self) -> None:
        code = b"\x00\x00\x80\xd2\xc0\x03\x5f\xd6"
        symbol = {
            "selectedAddress": 0x1000,
            "function": "test",
            "symbolStart": 0x1000,
            "symbolEnd": 0x1008,
            "symbolOffset": 0,
            "symbolByteCount": 8,
            "codeSHA256": hashlib.sha256(code).hexdigest(),
            "hex": code.hex(),
            "module": {
                "valid": True,
                "path": "/test",
                "uuid": "test",
                "loadAddress": 0x1000,
            },
        }
        validated, payload = validator.validate_symbol(symbol, "test", 0x1000)
        self.assertEqual(validated["function"], "test")
        self.assertEqual(payload, code)
        symbol["codeSHA256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "code hash differs"):
            validator.validate_symbol(symbol, "test", 0x1000)

    def test_preregistration_keeps_every_machine_result_unknown(self) -> None:
        value = {
            "backdropMarginCase22CalleePreregistrationSchemaVersion": 1,
            "profile": {
                "material": "regular",
                "appearance": "light",
                "direction": "materialize",
                "geometry": "circle-127-center",
                "profilePreviouslyOpened": True,
                "case22TargetAddressPreviouslyOpened": True,
                "case22TargetCodePreviouslyOpened": False,
            },
            "selection": {
                "groupInvocationIndex": 20,
                "calibratedFromOpenedRunID": 31118243811,
                "ordinalChoiceWasRetrospective": True,
                "openedOrdinalReturnF64": 17.778189659118652,
                "openedOrdinalReturnF64RawLittleEndianHex": "0000007037c73140",
                "runtimeSelector": "fixed structural invocation ordinal only",
                "runtimeSelectionReadsOpenedReturn": False,
                "capturedMarginUsedForRuntimeSelection": False,
                "capturedCropUsedForRuntimeSelection": False,
                "capturedImageUsedForRuntimeSelection": False,
                "capturedPixelUsedForRuntimeSelection": False,
                "prospectiveTransferAuthority": False,
            },
            "unknownBeforeCapture": {
                key: None
                for key in (
                    "targetFunction",
                    "targetSymbolBounds",
                    "targetCodeBytes",
                    "targetCodeSHA256",
                    "objectBytes",
                    "pointerProbeBytes",
                    "instructionSequence",
                    "instructionRegisters",
                    "instructionStacks",
                    "opaqueCalleeIdentities",
                    "opaqueCalleeCodeBytes",
                    "returnWord",
                    "exactArithmetic",
                )
            },
            "acceptance": {
                key: True
                for key in (
                    "requireUnchangedInheritedGroupValidation",
                    "requireExactAuthenticatedTargetOffset",
                    "requireCompleteTargetSymbolAndCode",
                    "requireCompleteSelectedInstructionTrace",
                    "requireFullGeneralAndSIMDRegisters",
                    "requireBoundedStackAndObjectSnapshots",
                    "requireOpaqueCalleeCodeAndBoundaries",
                    "requireExactReturnToGroupStage",
                    "requireNoValueBasedRuntimeSelection",
                    "zeroTolerance",
                )
            },
        }
        self.assertIs(validator.validate_preregistration(value), value)
        value["unknownBeforeCapture"]["returnWord"] = "0000000000000000"
        with self.assertRaisesRegex(ValueError, "was not sealed"):
            validator.validate_preregistration(value)


if __name__ == "__main__":
    unittest.main()
