"""Tests for the exact writer-chain validator."""

from __future__ import annotations

import copy
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path
from typing import Optional

import validate_backdrop_margin_writer_execution as validator


def snapshot(address: int, payload: bytes) -> dict[str, object]:
    return {
        "address": address,
        "byteCount": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "hex": payload.hex(),
    }


def module() -> dict[str, object]:
    return {
        "valid": True,
        "path": "/System/Library/Frameworks/QuartzCore.framework/QuartzCore",
        "uuid": validator.QUARTZCORE_UUID,
        "loadAddress": 0x100000000,
    }


def preregistration() -> dict[str, object]:
    return {
        "backdropMarginWriterExecutionPreregistrationSchemaVersion": 1,
        "classification": "synthetic prospective fixture",
        "frozenCandidate": {
            "perRecordRequiredMargin": (
                "max(inputBleedAmount, inputShadowAmount + "
                "max(abs(inputShadowOffset.x), abs(inputShadowOffset.y)))"
            ),
            "transitionMargin": "max over all 32 retained records",
            "modelStorage": "binary64",
            "renderStorage": "round-to-nearest-even binary32",
            "capturedTargetValueUsedToChooseCandidate": False,
        },
        "prospectiveCases": [
            {
                "material": "regular",
                "appearance": "light",
                "direction": "materialize",
                "geometry": "circle-347-center",
                "appleOutputAvailableAtFreeze": False,
                "expectedMarginF64": None,
                "expectedMarginF32": None,
                "expectedWriterPointers": None,
                "expectedCallerIdentity": None,
            }
        ],
        "acceptance": {
            "requireAllExactCodeGates": True,
            "requireEveryEventWithinBound": True,
            "requireAtLeastOneCompleteSetterCopyBoundsChain": True,
            "requireEveryStructurallyJoinedChainToMatchCandidateBitwise": True,
            "requireNoCapturedValueForSelection": True,
        },
    }


def timeline() -> dict[str, object]:
    records = []
    offset = struct.pack("<2d", 0.0, 8.0)
    for sample_index in range(1, 33):
        shadow = 75.0 * sample_index / 32.0
        records.append(
            {
                "sampleIndex": sample_index,
                "filter": {
                    "inputValues": {
                        "inputBleedAmount": 40.0 * sample_index / 32.0,
                        "inputShadowAmount": shadow,
                        "inputShadowOffset": {
                            "hex": offset.hex(),
                            "lengthBytes": 16,
                            "objCType": "{CGSize=dd}",
                        },
                    }
                },
            }
        )
    return {
        "schemaVersion": 5,
        "material": "regular",
        "appearance": "light",
        "direction": "materialize",
        "geometry": {"name": "circle-347-center"},
        "sampleCount": 33,
        "failedSamples": 0,
        "dynamicBackgroundUniforms": {
            "requested": True,
            "executed": True,
            "sampleCount": 32,
            "executedSampleCount": 32,
            "records": records,
        },
    }


def trace() -> dict[str, object]:
    model = 0x200000000
    render = 0x300000000
    copy_start = 0x100100000
    setter_start = 0x100200000
    bounds_start = 0x100300000
    model_prefix = bytes(range(64))
    render_prefix = bytearray(range(64))
    f64 = struct.pack("<d", 83.0)
    f32 = struct.pack("<f", 83.0)
    render_prefix[36:40] = f32
    caller_code = b"\x1f\x20\x03\xd5"
    code_gates = {}
    for name, start in (
        ("copy", copy_start),
        ("setter", setter_start),
        ("bounds", bounds_start),
    ):
        expected = validator.CODE_GATES[name]
        code_gates[name] = {
            "function": expected["function"],
            "symbolStart": start,
            "symbolEnd": start + expected["byteCount"],
            "symbolByteCount": expected["byteCount"],
            "codeSHA256": expected["sha256"],
            "module": module(),
        }
    events = [
        {
            "eventIndex": 0,
            "type": "marginSetter",
            "threadID": 7,
            "pc": setter_start,
            "modelSelf": model,
            "marginF64": 83.0,
            "marginF64RawLittleEndianHex": f64.hex(),
            "modelPrefix": snapshot(model, model_prefix),
            "directCallerIndex": 0,
            "backtrace": [],
        },
        {
            "eventIndex": 1,
            "type": "copyEntry",
            "threadID": 7,
            "pc": copy_start,
            "modelSelf": model,
            "renderArgument": render,
            "modelPrefix": snapshot(model, model_prefix),
            "backtrace": [],
        },
        {
            "eventIndex": 2,
            "type": "copyMarginStore",
            "threadID": 7,
            "pc": copy_start + 948,
            "copyEntryEventIndex": 1,
            "modelSelf": model,
            "renderSelf": render,
            "entryRenderArgument": render,
            "entryModelMatched": True,
            "entryRenderArgumentMatched": True,
            "marginF32": 83.0,
            "marginF32RawLittleEndianHex": f32.hex(),
            "renderMarginBeforeRawLittleEndianHex": bytes(4).hex(),
            "renderPrefixBeforeStore": snapshot(render, bytes(64)),
        },
        {
            "eventIndex": 3,
            "type": "backdropBounds",
            "threadID": 7,
            "pc": bounds_start,
            "renderSelf": render,
            "layer": render - 160,
            "output": 0x400000000,
            "marginF32": 83.0,
            "marginF32RawLittleEndianHex": f32.hex(),
            "renderPrefix": snapshot(render, bytes(render_prefix)),
        },
    ]
    return {
        "backdropMarginWriterExecutionTraceSchemaVersion": 1,
        "status": "finalized",
        "statusBeforeFinalization": "breakpoints-armed",
        "failures": [],
        "finalFailureCount": 0,
        "configuration": {
            "material": "regular",
            "appearance": "light",
            "direction": "materialize",
            "geometry": "circle-347-center",
            "quartzCoreUUID": validator.QUARTZCORE_UUID,
            "copyMarginStoreOffset": 948,
            "copyMarginStoreInstructionHex": "a02600bd",
            "renderMarginOffset": 36,
            "maximumEventCount": 8192,
            "capturedMarginUsedForSelection": False,
            "capturedCropUsedForSelection": False,
            "capturedImageUsedForSelection": False,
        },
        "codeGates": code_gates,
        "callers": [
            {
                "completeCodeCaptured": True,
                "symbolByteCount": len(caller_code),
                "codeSHA256": hashlib.sha256(caller_code).hexdigest(),
                "hex": caller_code.hex(),
            }
        ],
        "finalCallerCount": 1,
        "finalCallerCodeByteCount": len(caller_code),
        "events": events,
        "finalEventCount": len(events),
        "eventTypeCounts": {
            "marginSetter": 1,
            "copyEntry": 1,
            "copyMarginStore": 1,
            "backdropBounds": 1,
        },
    }


class BackdropMarginWriterExecutionValidatorTests(unittest.TestCase):
    def run_validation(
        self,
        trace_value: Optional[dict[str, object]] = None,
    ) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = {
                "trace": root / "trace.json",
                "timeline": root / "timeline.json",
                "prereg": root / "prereg.json",
            }
            values = {
                "trace": trace() if trace_value is None else trace_value,
                "timeline": timeline(),
                "prereg": preregistration(),
            }
            for name, path in paths.items():
                path.write_text(json.dumps(values[name]), encoding="utf-8")
            return validator.validate(
                paths["trace"],
                paths["timeline"],
                paths["prereg"],
                "regular",
                "light",
                "materialize",
                "circle-347-center",
            )

    def test_complete_writer_chain_is_bit_exact(self) -> None:
        result = self.run_validation()
        self.assertEqual(result["conclusion"], "success")
        self.assertEqual(result["candidate"]["maximumRequiredMarginF64"], 83.0)
        self.assertEqual(result["candidate"]["expectedRenderMarginF32"], 83.0)
        self.assertEqual(result["writerExecution"]["completeChainCount"], 1)
        self.assertTrue(
            result["writerExecution"]["allStructurallyJoinedChainsBitExact"]
        )

    def test_one_bit_render_difference_fails_closed(self) -> None:
        value = trace()
        event = value["events"][2]
        assert isinstance(event, dict)
        event["marginF32"] = struct.unpack("<f", bytes.fromhex("0100a642"))[0]
        event["marginF32RawLittleEndianHex"] = "0100a642"
        with self.assertRaisesRegex(ValueError, "frozen transition-maximum"):
            self.run_validation(copy.deepcopy(value))

    def test_missing_setter_join_fails_closed(self) -> None:
        value = trace()
        event = value["events"][0]
        assert isinstance(event, dict)
        event["modelSelf"] = 0xDEADBEEF
        prefix = event["modelPrefix"]
        assert isinstance(prefix, dict)
        prefix["address"] = 0xDEADBEEF
        with self.assertRaisesRegex(ValueError, "no complete"):
            self.run_validation(value)


if __name__ == "__main__":
    unittest.main()
