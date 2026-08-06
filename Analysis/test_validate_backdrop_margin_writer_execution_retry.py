"""Tests for the material-specific ABI-correct writer gate."""

from __future__ import annotations

import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import test_validate_backdrop_margin_writer_execution as fixture
import validate_backdrop_margin_writer_execution as frozen
import validate_backdrop_margin_writer_execution_retry as retry


SYNTHETIC_CALLER_FUNCTION = "synthetic SwiftUI margin caller"
SYNTHETIC_CALLER_CODE = b"\x1f\x20\x03\xd5" * 4
SYNTHETIC_MODULE_LOAD = 0x500000000
SYNTHETIC_CALLER_START = SYNTHETIC_MODULE_LOAD + 0x3000
SYNTHETIC_CALLER_RETURN_OFFSET = 12
SYNTHETIC_PRODUCER_TARGET_OFFSET = 0x1000
SYNTHETIC_SETTER_TARGET_OFFSET = 0x2000


def bl_instruction(address: int, target: int) -> str:
    displacement = target - address
    assert displacement % 4 == 0
    immediate = (displacement // 4) & 0x03FFFFFF
    return (0x94000000 | immediate).to_bytes(4, "little").hex()


class BackdropMarginWriterExecutionRetryValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch.multiple(
            retry,
            CALLER_FUNCTION=SYNTHETIC_CALLER_FUNCTION,
            CALLER_BYTE_COUNT=len(SYNTHETIC_CALLER_CODE),
            CALLER_CODE_SHA256=hashlib.sha256(SYNTHETIC_CALLER_CODE).hexdigest(),
            CALLER_RETURN_SYMBOL_OFFSET=SYNTHETIC_CALLER_RETURN_OFFSET,
            PRODUCER_TARGET_MODULE_OFFSET=SYNTHETIC_PRODUCER_TARGET_OFFSET,
            SETTER_STUB_MODULE_OFFSET=SYNTHETIC_SETTER_TARGET_OFFSET,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def paths(self, root: Path) -> tuple[Path, Path, Path]:
        trace = fixture.trace()
        copy_entry = trace["events"][1]
        copy_store = trace["events"][2]
        assert isinstance(copy_entry, dict)
        assert isinstance(copy_store, dict)
        opaque_argument = 0x500000000
        copy_entry["renderArgument"] = opaque_argument
        copy_store["entryRenderArgument"] = opaque_argument
        copy_store["entryRenderArgumentMatched"] = False

        caller_return = SYNTHETIC_CALLER_START + SYNTHETIC_CALLER_RETURN_OFFSET
        caller = trace["callers"][0]
        assert isinstance(caller, dict)
        caller.update(
            {
                "function": SYNTHETIC_CALLER_FUNCTION,
                "pc": caller_return,
                "symbolStart": SYNTHETIC_CALLER_START,
                "symbolEnd": SYNTHETIC_CALLER_START + len(SYNTHETIC_CALLER_CODE),
                "symbolOffset": SYNTHETIC_CALLER_RETURN_OFFSET,
                "symbolByteCount": len(SYNTHETIC_CALLER_CODE),
                "codeSHA256": hashlib.sha256(SYNTHETIC_CALLER_CODE).hexdigest(),
                "hex": SYNTHETIC_CALLER_CODE.hex(),
                "module": {
                    "valid": True,
                    "path": (
                        "/System/Library/Frameworks/SwiftUICore.framework/SwiftUICore"
                    ),
                    "uuid": retry.SWIFTUICORE_UUID,
                    "loadAddress": SYNTHETIC_MODULE_LOAD,
                },
            }
        )
        trace["finalCallerCodeByteCount"] = len(SYNTHETIC_CALLER_CODE)
        producer_target = SYNTHETIC_MODULE_LOAD + SYNTHETIC_PRODUCER_TARGET_OFFSET
        producer_code = b"\xc0\x03\x5f\xd6"
        trace["producerCallees"] = [
            {
                "function": "synthetic margin producer",
                "selectedTarget": producer_target,
                "symbolStart": producer_target,
                "symbolEnd": producer_target + len(producer_code),
                "symbolOffset": 0,
                "symbolByteCount": len(producer_code),
                "codeSHA256": hashlib.sha256(producer_code).hexdigest(),
                "hex": producer_code.hex(),
                "completeCodeCaptured": True,
                "module": {
                    "valid": True,
                    "path": (
                        "/System/Library/Frameworks/SwiftUICore.framework/SwiftUICore"
                    ),
                    "uuid": retry.SWIFTUICORE_UUID,
                    "loadAddress": SYNTHETIC_MODULE_LOAD,
                },
            }
        ]
        trace["finalProducerCalleeCount"] = 1
        trace["finalProducerCalleeCodeByteCount"] = len(producer_code)
        configuration = trace["configuration"]
        assert isinstance(configuration, dict)
        configuration.update(
            {
                "baseCaptureSHA256": retry.BASE_CAPTURE_SHA256,
                "maximumProducerCount": 64,
                "maximumProducerByteCount": 131072,
                "maximumTotalProducerByteCount": 2 * 1024 * 1024,
                "producerSelfSnapshotByteCount": 0x60,
                "setterCallFromReturnPC": -4,
                "producerBridgeFromReturnPC": -8,
                "producerCallFromReturnPC": -12,
                "producerBridgeInstructionHex": "e0031caa",
                "producerSelectedByCapturedMargin": False,
            }
        )
        setter = trace["events"][0]
        assert isinstance(setter, dict)
        producer_self = 0x600000160
        stack_pointer = producer_self - 0x160
        producer_snapshot = bytes(range(0x60))
        setter["backtrace"] = [{}, {"pc": caller_return}]
        setter["producerInvocation"] = {
            "complete": True,
            "callerReturnPC": caller_return,
            "setterCall": {
                "address": caller_return - 4,
                "instructionHex": bl_instruction(
                    caller_return - 4,
                    SYNTHETIC_MODULE_LOAD + SYNTHETIC_SETTER_TARGET_OFFSET,
                ),
                "target": (SYNTHETIC_MODULE_LOAD + SYNTHETIC_SETTER_TARGET_OFFSET),
            },
            "bridge": {
                "address": caller_return - 8,
                "instructionHex": "e0031caa",
            },
            "producerCall": {
                "address": caller_return - 12,
                "instructionHex": bl_instruction(caller_return - 12, producer_target),
                "target": producer_target,
            },
            "producerCalleeIndex": 0,
            "producerSelf": producer_self,
            "stackPointerAtSetterEntry": stack_pointer,
            "producerSelfOffsetFromStackPointer": 0x160,
            "producerSelfSnapshot": {
                "address": producer_self,
                "byteCount": len(producer_snapshot),
                "sha256": hashlib.sha256(producer_snapshot).hexdigest(),
                "hex": producer_snapshot.hex(),
            },
            "producerReturnF64": setter["marginF64"],
            "producerReturnF64RawLittleEndianHex": setter[
                "marginF64RawLittleEndianHex"
            ],
            "capturedMarginUsedForSelection": False,
        }

        preregistration = fixture.preregistration()
        preregistration.update(
            {
                "backdropMarginWriterExecutionRetryPreregistrationSchemaVersion": 2,
                "supersedesUndispatchedVersion": {
                    "commit": "c7e1a3f",
                    "workflowDispatchCountBeforeSupersession": 0,
                    "appleOutputForProspectiveCasesAvailable": False,
                    "reason": (
                        "opened antecedent materialize artifacts disproved a "
                        "universal material law"
                    ),
                },
            }
        )
        candidate = preregistration["frozenCandidate"]
        assert isinstance(candidate, dict)
        candidate.update(
            {
                "materialSelector": {
                    "clear": "exact binary64 +0.0",
                    "regular": (
                        "maximum over all 32 retained per-record required margins"
                    ),
                },
                "candidateCalibratedFromOpenedAppleWriterValues": True,
                "prospectiveCaseOutputUsedToChooseCandidate": False,
            }
        )
        acceptance = preregistration["acceptance"]
        assert isinstance(acceptance, dict)
        acceptance.update(
            {
                "requireEveryStructurallyJoinedChainToMatchMaterialLawBitwise": True,
                "requireEverySetterToExposeExactAdjacentProducer": True,
                "requireExactOpenedSwiftUICoreCallerIdentity": True,
                "requireProducerCompleteCode": True,
                "requireProducerSelfSnapshot": True,
                "zeroTolerance": True,
            }
        )
        case = preregistration["prospectiveCases"][0]
        assert isinstance(case, dict)
        case["expectedProducerIdentity"] = None

        values = (
            (root / "trace.json", trace),
            (root / "timeline.json", fixture.timeline()),
            (root / "preregistration.json", preregistration),
        )
        for path, value in values:
            path.write_text(json.dumps(value), encoding="utf-8")
        return values[0][0], values[1][0], values[2][0]

    def test_frozen_accidental_x2_assertion_rejects_the_real_abi(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.paths(Path(directory))
            with self.assertRaisesRegex(ValueError, "copy entry/store"):
                frozen.validate(
                    *paths,
                    "regular",
                    "light",
                    "materialize",
                    "circle-347-center",
                )

    def test_retry_keeps_joins_and_proves_the_adjacent_producer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.paths(Path(directory))
            result = retry.validate(
                *paths,
                "regular",
                "light",
                "materialize",
                "circle-347-center",
            )
        self.assertEqual(result["conclusion"], "success")
        self.assertEqual(
            result["backdropMarginWriterExecutionRetryValidationSchemaVersion"],
            2,
        )
        discovery = result["writerExecution"]["opaqueEntryArgumentDiscovery"]
        self.assertFalse(discovery["isRenderObject"])
        self.assertEqual(
            discovery["copyStoreEventCountValidatedWithoutX2RenderAssumption"],
            1,
        )
        provenance = result["writerExecution"]["producerProvenance"]
        self.assertTrue(provenance["allSetterInvocationsExposeExactAdjacentProducer"])
        self.assertTrue(provenance["allProducerReturnsEqualSetterInputsBitwise"])
        self.assertTrue(result["sealedConclusion"]["opaqueCopyArgumentABIResolved"])
        self.assertTrue(
            result["sealedConclusion"][
                "regularTransitionMaximumLawProspectiveBitExactForThisCase"
            ]
        )

    def test_retry_still_rejects_a_model_pointer_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.paths(root)
            trace = json.loads(paths[0].read_text(encoding="utf-8"))
            trace["events"][2]["entryModelMatched"] = False
            paths[0].write_text(json.dumps(trace), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "model entry/store"):
                retry.validate(
                    *paths,
                    "regular",
                    "light",
                    "materialize",
                    "circle-347-center",
                )

    def test_one_bit_producer_return_difference_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.paths(root)
            trace = json.loads(paths[0].read_text(encoding="utf-8"))
            invocation = trace["events"][0]["producerInvocation"]
            invocation["producerReturnF64RawLittleEndianHex"] = "0100000000c05440"
            paths[0].write_text(json.dumps(trace), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "producer return"):
                retry.validate(
                    *paths,
                    "regular",
                    "light",
                    "materialize",
                    "circle-347-center",
                )

    def test_clear_material_uses_exact_zero_not_the_regular_maximum(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self.paths(root)
            trace = json.loads(paths[0].read_text(encoding="utf-8"))
            trace["configuration"]["material"] = "clear"
            setter = trace["events"][0]
            copy_store = trace["events"][2]
            bounds = trace["events"][3]
            setter["marginF64"] = 0.0
            setter["marginF64RawLittleEndianHex"] = struct.pack("<d", 0.0).hex()
            invocation = setter["producerInvocation"]
            invocation["producerReturnF64"] = 0.0
            invocation["producerReturnF64RawLittleEndianHex"] = struct.pack(
                "<d", 0.0
            ).hex()
            copy_store["marginF32"] = 0.0
            copy_store["marginF32RawLittleEndianHex"] = struct.pack("<f", 0.0).hex()
            bounds["marginF32"] = 0.0
            bounds["marginF32RawLittleEndianHex"] = struct.pack("<f", 0.0).hex()
            prefix = bytearray.fromhex(bounds["renderPrefix"]["hex"])
            prefix[36:40] = struct.pack("<f", 0.0)
            bounds["renderPrefix"] = fixture.snapshot(
                bounds["renderSelf"], bytes(prefix)
            )
            paths[0].write_text(json.dumps(trace), encoding="utf-8")

            timeline = json.loads(paths[1].read_text(encoding="utf-8"))
            timeline["material"] = "clear"
            paths[1].write_text(json.dumps(timeline), encoding="utf-8")

            preregistration = json.loads(paths[2].read_text(encoding="utf-8"))
            preregistration["prospectiveCases"][0]["material"] = "clear"
            paths[2].write_text(json.dumps(preregistration), encoding="utf-8")

            result = retry.validate(
                *paths,
                "clear",
                "light",
                "materialize",
                "circle-347-center",
            )
        self.assertEqual(result["conclusion"], "success")
        self.assertEqual(result["candidate"]["maximumRequiredMarginF64"], 0.0)
        self.assertEqual(result["candidate"]["expectedRenderMarginF32"], 0.0)
        self.assertEqual(result["candidate"]["capturedInputTransitionMaximumF64"], 83.0)
        self.assertTrue(result["sealedConclusion"]["materialSpecificMarginLawSelected"])
        self.assertTrue(
            result["sealedConclusion"][
                "clearZeroMarginLawProspectiveBitExactForThisCase"
            ]
        )
        self.assertFalse(
            result["sealedConclusion"][
                "transitionMaximumCandidateProspectiveBitExactForThisCase"
            ]
        )


if __name__ == "__main__":
    unittest.main()
