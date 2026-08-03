#!/usr/bin/env python3
"""Tests for the sealed crop-writer watchpoint integrity gate."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import validate_capture_backdrop_writer_trace as validator


def private_fields():
    return {
        "layerStateInputBoundsI32": [-11, -11, 651, 659],
        "layerStateSelectedRectI32": [200, 173, 643, 651],
        "sourceSelectedRectI32": [200, 173, 643, 651],
        "ownerSelectedRectF64": [200.0, 173.0, 643.0, 651.0],
        "ownerRegion248Handle": 0x00C8_00AD_0506_0A2D,
        "ownerRegion270Handle": 0x00C8_00AD_0506_0A2D,
    }


def frame(pc):
    return {
        "frameIndex": 0,
        "pc": pc,
        "function": "CA::Render::writer()",
        "symbolStart": pc - 4,
        "symbolEnd": pc + 64,
        "symbolOffset": 4,
        "module": {
            "valid": True,
            "path": (
                "/System/Library/Frameworks/QuartzCore.framework/Versions/A/QuartzCore"
            ),
            "loadAddress": 0x1900_0000_0,
        },
    }


def passing_trace():
    addresses = {
        "source": 0x1000_0000,
        "owner": 0x2000_0000,
        "layer": 0x3000_0000,
        "layerState": 0x4000_0000,
    }
    watchpoints = []
    events = []
    hit_counts = {}
    for identifier, (name, (base, offset)) in enumerate(
        validator.EXPECTED_WATCH_SPECS.items(), start=1
    ):
        watchpoints.append(
            {
                "id": identifier,
                "hardwareIndex": identifier - 1,
                "name": name,
                "address": addresses[base] + offset,
                "byteCount": 8,
                "initialHex": "00" * 8,
            }
        )
        pc = 0x1901_0000_0 + identifier * 0x100
        writer_frame = frame(pc)
        events.append(
            {
                "eventIndex": identifier - 1,
                "watchpointID": identifier,
                "watchpointName": name,
                "watchpointHitIndex": 1,
                "threadID": 7,
                "stopPC": pc,
                "beforeHex": "00" * 8,
                "afterHex": "%02x" % identifier + "00" * 7,
                "valueChanged": True,
                "frame": writer_frame,
                "backtrace": [writer_frame],
                "codeWindowIndex": 0,
                "privateFieldsAfter": private_fields(),
            }
        )
        hit_counts[name] = 1
    code = bytes(0x400)
    return {
        "captureBackdropWriterTraceSchemaVersion": 1,
        "classification": validator.EXPECTED_CLASSIFICATION,
        "status": "finalized",
        "statusBeforeFinalization": "watchpoints-armed",
        "configuration": {
            "captureBackdropSymbol": validator.EXPECTED_CAPTURE_BACKDROP_SYMBOL,
            "captureBackdropCodeByteCount": 0x4000,
            "captureBackdropCodeSHA256": (
                validator.EXPECTED_CAPTURE_BACKDROP_CODE_SHA256
            ),
            "lateInstructionOffset": 0x2B58,
            "watchpointByteCount": 8,
            "maximumHitsPerWatchpoint": 6,
            "maximumTotalHits": 24,
            "maximumBacktraceFrameCount": 32,
            "symbolCodeWindowByteCount": 0x1000,
            "fallbackCodeWindowByteCount": 0x400,
            "watchSpecs": [
                {"name": name, "base": base, "offset": offset}
                for name, (base, offset) in validator.EXPECTED_WATCH_SPECS.items()
            ],
        },
        "captureBackdrop": {
            "symbolAddress": 0x1900_A5218,
            "codeByteCount": 0x4000,
            "codeSHA256": validator.EXPECTED_CAPTURE_BACKDROP_CODE_SHA256,
            "module": {
                "valid": True,
                "path": (
                    "/System/Library/Frameworks/QuartzCore.framework/Versions/A/"
                    "QuartzCore"
                ),
                "loadAddress": 0x1900_0000_0,
            },
        },
        "objectChain": {
            "addresses": addresses,
            "exact": True,
            "initialPrivateFields": private_fields(),
        },
        "watchpoints": watchpoints,
        "codeWindows": [
            {
                "startAddress": 0x1901_0000_0,
                "byteCount": len(code),
                "source": "pc-centered fallback",
                "sha256": hashlib.sha256(code).hexdigest(),
                "hex": code.hex(),
            }
        ],
        "events": events,
        "failures": [],
        "finalEventCount": len(events),
        "finalFailureCount": 0,
        "watchpointHitCounts": hit_counts,
    }


class CaptureBackdropWriterTraceTests(unittest.TestCase):
    def validate(self, trace):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.json"
            path.write_text(
                json.dumps(trace, sort_keys=True, allow_nan=False) + "\n",
                encoding="utf-8",
            )
            return validator.validate(path)

    def test_passing_trace_remains_semantically_sealed(self):
        result = self.validate(passing_trace())
        self.assertEqual(result["conclusion"], "success")
        self.assertTrue(result["prospectiveGatePassed"])
        self.assertEqual(result["aggregate"]["watchpointCount"], 4)
        self.assertEqual(result["aggregate"]["eventCount"], 4)
        self.assertEqual(result["aggregate"]["distinctWriterSiteCount"], 4)
        self.assertTrue(result["sealedConclusion"]["privateWriterPCsCaptured"])
        self.assertFalse(
            result["sealedConclusion"]["publicLayerStateCropRuleRecovered"]
        )
        self.assertFalse(result["sealedConclusion"]["productionShaderAuthorized"])

    def test_missing_layer_state_writer_fails_closed(self):
        trace = passing_trace()
        name = "layerStateSelectedRectI32"
        trace["events"] = [
            event for event in trace["events"] if event["watchpointName"] != name
        ]
        trace["finalEventCount"] -= 1
        trace["watchpointHitCounts"][name] = 0
        with self.assertRaisesRegex(ValueError, "layerStateSelectedRectI32"):
            self.validate(trace)

    def test_code_window_tampering_fails_closed(self):
        trace = passing_trace()
        trace["codeWindows"][0]["hex"] = "01" + trace["codeWindows"][0]["hex"][2:]
        with self.assertRaisesRegex(ValueError, "code-window identity"):
            self.validate(trace)

    def test_debugger_failure_is_retained_as_failure(self):
        trace = copy.deepcopy(passing_trace())
        trace["failures"] = [{"stage": "writer-watchpoint", "message": "failed"}]
        trace["finalFailureCount"] = 1
        with self.assertRaisesRegex(ValueError, "prospective configuration"):
            self.validate(trace)


if __name__ == "__main__":
    unittest.main()
