#!/usr/bin/env python3
"""Tests for the sealed crop-writer watchpoint integrity gate."""

import copy
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

import validate_capture_backdrop_writer_trace as validator


def private_fields():
    return {
        "layerStateInputBoundsI32": [-11, -11, 651, 659],
        "layerStateSelectedRectI32": [200, 173, 643, 651],
        "sourceSelectedRectI32": [200, 160, 643, 664],
        "ownerSelectedRectF64": [200.0, 173.0, 643.0, 651.0],
        "ownerRegion248Handle": 0x00C8_00AD_0506_0A2D,
        "ownerRegion270Handle": 0x00C8_00AD_0506_0A2D,
    }


def raw_snapshot(address, byte_count, fill):
    payload = bytes([fill]) * byte_count
    return {
        "address": address,
        "byteCount": byte_count,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "hex": payload.hex(),
    }


def raw_register(name, byte_count, unsigned):
    payload = unsigned.to_bytes(byte_count, "little")
    record = {
        "name": name,
        "byteCount": byte_count,
        "hex": payload.hex(),
        "valueString": f"0x{unsigned:0{byte_count * 2}x}",
    }
    if byte_count <= 8:
        record["unsignedValue"] = unsigned
    return record


def operand_snapshot(addresses, pc, *, is_prepare_layer=True):
    register_values = {
        "x0": addresses["source"],
        "x1": addresses["owner"],
        "x2": addresses["layer"],
        "x3": addresses["layerState"],
        "x19": addresses["source"],
        "x20": addresses["owner"],
        "x21": addresses["owner"],
        "x22": addresses["layer"],
        "x23": addresses["layerState"],
        "x24": addresses["layer"],
        "x25": addresses["owner"],
        "x26": addresses["layer"],
        "x27": addresses["layerState"],
        "x28": addresses["source"],
        "sp": 0x70_0000_0000,
        "pc": pc,
    }
    general = []
    for name in validator.GENERAL_REGISTER_NAMES:
        byte_count = 4 if name == "cpsr" else 8
        general.append(raw_register(name, byte_count, register_values.get(name, 0)))
    simd = []
    for index, name in enumerate(validator.SIMD_REGISTER_NAMES):
        byte_count = 4 if name in {"fpsr", "fpcr"} else 16
        simd.append(raw_register(name, byte_count, index))
    pointer_groups = {}
    for name in validator.POINTER_PROBE_REGISTER_NAMES:
        address = register_values.get(name, 0)
        if not (
            validator.MINIMUM_POINTER_PROBE_ADDRESS
            <= address
            <= validator.MAXIMUM_POINTER_PROBE_ADDRESS
        ):
            continue
        start = address - validator.REGISTER_POINTER_SNAPSHOT_BACKTRACK
        pointer_groups.setdefault(start, []).append(name)
    pointer_probes = []
    for index, (start, names) in enumerate(sorted(pointer_groups.items()), start=1):
        probe = raw_snapshot(
            start,
            validator.REGISTER_POINTER_SNAPSHOT_BYTE_COUNT,
            index,
        )
        probe.update(
            {
                "registerNames": names,
                "registerValue": start + validator.REGISTER_POINTER_SNAPSHOT_BACKTRACK,
            }
        )
        pointer_probes.append(probe)
    role_groups = {}
    if is_prepare_layer:
        for name in validator.PREPARE_LAYER_ROLE_REGISTER_NAMES:
            address = register_values[name]
            role_groups.setdefault(address, []).append(name)
    role_probes = []
    for index, (address, names) in enumerate(sorted(role_groups.items()), start=1):
        probe = raw_snapshot(
            address,
            validator.PREPARE_LAYER_ROLE_SNAPSHOT_BYTE_COUNT,
            index + 16,
        )
        probe.update(
            {
                "registerNames": names,
                "registerValue": address,
            }
        )
        role_probes.append(probe)
    return {
        "registers": {"general": general, "simd": simd},
        "stack": raw_snapshot(
            register_values["sp"], validator.STACK_SNAPSHOT_BYTE_COUNT, 0x55
        ),
        "objects": {
            base: raw_snapshot(addresses[base], byte_count, index)
            for index, (base, byte_count) in enumerate(
                validator.OBJECT_SNAPSHOT_SPECS.items(), start=1
            )
        },
        "registerPointerProbeCount": len(pointer_probes),
        "registerPointerProbes": pointer_probes,
        "registerPointerProbeFailures": [],
        "prepareLayerRoleProbeCount": len(role_probes),
        "prepareLayerRoleProbes": role_probes,
        "prepareLayerRoleProbeFailures": [],
    }


def frame(pc, function="CA::Render::writer()", symbol_offset=4):
    return {
        "frameIndex": 0,
        "pc": pc,
        "function": function,
        "symbolStart": pc - symbol_offset,
        "symbolEnd": pc + 64,
        "symbolOffset": symbol_offset,
        "module": {
            "valid": True,
            "path": (
                "/System/Library/Frameworks/QuartzCore.framework/Versions/A/QuartzCore"
            ),
            "loadAddress": 0x1900_0000_0,
        },
    }


def rejected_late_candidate(addresses):
    source_rectangle = [200, 173, 643, 651]
    layer_state_rectangle = [200, 173, 643, 651]
    owner_rectangle = [200.0, 173.0, 643.0, 651.0]
    return {
        "lateCandidateIndex": 1,
        "source": addresses["source"],
        "owner": addresses["owner"],
        "layer": addresses["layer"],
        "layerState": addresses["layerState"],
        "sourceOwner": addresses["owner"],
        "layerStateSource": addresses["source"],
        "pointerChainExact": True,
        "mirroredRectangleIdentityExact": True,
        "ownerEqualsLayerStateRectangle": True,
        "sourceEqualsLayerStateRectangle": True,
        "preconvergenceExact": False,
        "rejection": "preconvergence rectangle state differs",
        "mirroredRectangles": {
            "sourceSelectedRectI32": source_rectangle,
            "sourceSelectedRectI32Hex": struct.pack("<4i", *source_rectangle).hex(),
            "layerStateSelectedRectI32": layer_state_rectangle,
            "layerStateSelectedRectI32Hex": struct.pack(
                "<4i", *layer_state_rectangle
            ).hex(),
            "ownerSelectedRectF64Hex": struct.pack("<4d", *owner_rectangle).hex(),
        },
    }


def selected_mirrored_rectangles():
    fields = private_fields()
    source_rectangle = fields["sourceSelectedRectI32"]
    layer_state_rectangle = fields["layerStateSelectedRectI32"]
    owner_rectangle = fields["ownerSelectedRectF64"]
    return {
        "sourceSelectedRectI32": source_rectangle,
        "sourceSelectedRectI32Hex": struct.pack("<4i", *source_rectangle).hex(),
        "layerStateSelectedRectI32": layer_state_rectangle,
        "layerStateSelectedRectI32Hex": struct.pack(
            "<4i", *layer_state_rectangle
        ).hex(),
        "ownerSelectedRectF64Hex": struct.pack("<4d", *owner_rectangle).hex(),
    }


def passing_trace():
    addresses = {
        "source": 0x10_0000_0000,
        "owner": 0x20_0000_0000,
        "layer": 0x30_0000_0000,
        "layerState": 0x40_0000_0000,
    }
    watchpoints = []
    events = []
    code_windows = []
    hit_counts = {}
    for identifier, (name, (base, offset)) in enumerate(
        validator.EXPECTED_WATCH_SPECS.items(), start=1
    ):
        watchpoints.append(
            {
                "id": identifier,
                "deprecatedHardwareIndex": -1,
                "name": name,
                "address": addresses[base] + offset,
                "byteCount": 8,
                "initialHex": "00" * 8,
            }
        )
        offsets = sorted(validator.EXPECTED_CHANGED_PREPARE_LAYER_OFFSETS[name])
        for hit_index, symbol_offset in enumerate(offsets, start=1):
            event_index = len(events)
            pc = 0x1901_0000_0 + (event_index + 1) * 0x100
            writer_frame = frame(
                pc,
                validator.EXPECTED_PREPARE_LAYER_FUNCTION,
                symbol_offset,
            )
            code = bytes([event_index + 1]) * (
                validator.PC_CENTERED_CODE_WINDOW_BYTE_COUNT
            )
            code_windows.append(
                {
                    "startAddress": pc - validator.PC_CENTERED_CODE_WINDOW_BACKTRACK,
                    "byteCount": len(code),
                    "source": "pc-centered",
                    "stopPCOffset": validator.PC_CENTERED_CODE_WINDOW_BACKTRACK,
                    "containsStopPC": True,
                    "sha256": hashlib.sha256(code).hexdigest(),
                    "hex": code.hex(),
                }
            )
            before = bytes([hit_index - 1]) + bytes(7)
            after = bytes([hit_index]) + bytes(7)
            events.append(
                {
                    "eventIndex": event_index,
                    "watchpointID": identifier,
                    "watchpointName": name,
                    "watchpointHitIndex": hit_index,
                    "threadID": 7,
                    "stopPC": pc,
                    "beforeHex": before.hex(),
                    "afterHex": after.hex(),
                    "valueChanged": True,
                    "hardwareStopKind": "watched-bytes-changed",
                    "frame": writer_frame,
                    "backtrace": [writer_frame],
                    "codeWindowIndex": event_index,
                    "privateFieldsAfter": private_fields(),
                    "operandSnapshot": operand_snapshot(addresses, pc),
                }
            )
        hit_counts[name] = len(offsets)
    return {
        "captureBackdropWriterTraceSchemaVersion": 5,
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
            "watchpointIdentityRule": validator.EXPECTED_WATCHPOINT_IDENTITY_RULE,
            "maximumHitsPerWatchpoint": 6,
            "maximumTotalHits": 24,
            "maximumBacktraceFrameCount": 32,
            "maximumLateCandidateCount": 512,
            "maximumLateCandidateDiagnosticCount": 16,
            "pcCenteredCodeWindowByteCount": (
                validator.PC_CENTERED_CODE_WINDOW_BYTE_COUNT
            ),
            "pcCenteredCodeWindowBacktrack": (
                validator.PC_CENTERED_CODE_WINDOW_BACKTRACK
            ),
            "stackSnapshotByteCount": validator.STACK_SNAPSHOT_BYTE_COUNT,
            "registerPointerSnapshotByteCount": (
                validator.REGISTER_POINTER_SNAPSHOT_BYTE_COUNT
            ),
            "registerPointerSnapshotBacktrack": (
                validator.REGISTER_POINTER_SNAPSHOT_BACKTRACK
            ),
            "generalRegisterNames": list(validator.GENERAL_REGISTER_NAMES),
            "simdRegisterNames": list(validator.SIMD_REGISTER_NAMES),
            "pointerProbeRegisterNames": list(validator.POINTER_PROBE_REGISTER_NAMES),
            "pointerProbeAddressRange": [
                validator.MINIMUM_POINTER_PROBE_ADDRESS,
                validator.MAXIMUM_POINTER_PROBE_ADDRESS,
            ],
            "prepareLayerFunction": validator.EXPECTED_PREPARE_LAYER_FUNCTION,
            "prepareLayerRoleRegisterNames": list(
                validator.PREPARE_LAYER_ROLE_REGISTER_NAMES
            ),
            "prepareLayerRoleSnapshotByteCount": (
                validator.PREPARE_LAYER_ROLE_SNAPSHOT_BYTE_COUNT
            ),
            "objectSnapshotSpecs": [
                {"base": base, "byteCount": byte_count}
                for base, byte_count in validator.OBJECT_SNAPSHOT_SPECS.items()
            ],
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
        "lateCandidateCount": 2,
        "lateCandidateDiagnostics": [rejected_late_candidate(addresses)],
        "objectChain": {
            "addresses": addresses,
            "exact": True,
            "pointerChainExact": True,
            "selectedLateCandidateIndex": 2,
            "selectedMirroredRectangleIdentityExact": False,
            "selectedOwnerEqualsLayerStateRectangle": True,
            "selectedSourceEqualsLayerStateRectangle": False,
            "selectedPreconvergenceExact": True,
            "selectedMirroredRectangles": selected_mirrored_rectangles(),
            "initialPrivateFields": private_fields(),
        },
        "watchpoints": watchpoints,
        "codeWindows": code_windows,
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
        self.assertEqual(result["aggregate"]["distinctWatchpointIDCount"], 4)
        self.assertEqual(result["aggregate"]["deprecatedHardwareIndexValues"], [-1])
        self.assertEqual(result["aggregate"]["eventCount"], 5)
        self.assertEqual(result["aggregate"]["distinctWriterSiteCount"], 5)
        self.assertTrue(result["sealedConclusion"]["privateWriterPCsCaptured"])
        self.assertTrue(
            result["sealedConclusion"]["writerInstructionsAndOperandsCaptured"]
        )
        self.assertTrue(result["sealedConclusion"]["prepareLayerRoleStateCaptured"])
        self.assertEqual(result["aggregate"]["requiredX19RoleSnapshotCount"], 5)
        self.assertFalse(
            result["sealedConclusion"]["publicLayerStateCropRuleRecovered"]
        )
        self.assertFalse(result["sealedConclusion"]["productionShaderAuthorized"])

    def test_unchanged_watched_bytes_are_retained_but_not_changed_evidence(self):
        trace = passing_trace()
        event = copy.deepcopy(trace["events"][0])
        event["eventIndex"] = len(trace["events"])
        event["watchpointHitIndex"] = 3
        event["beforeHex"] = event["afterHex"]
        event["valueChanged"] = False
        event["hardwareStopKind"] = "watched-bytes-unchanged"
        trace["events"].append(event)
        trace["finalEventCount"] += 1
        trace["watchpointHitCounts"][event["watchpointName"]] = 3
        result = self.validate(trace)
        self.assertEqual(
            result["aggregate"]["unchangedEventCountsByWatchpoint"][
                event["watchpointName"]
            ],
            1,
        )

    def test_field_with_only_unchanged_watched_bytes_fails_closed(self):
        trace = passing_trace()
        name = "ownerSelectedRectF64"
        for event in trace["events"]:
            if event["watchpointName"] != name:
                continue
            event["afterHex"] = event["beforeHex"]
            event["valueChanged"] = False
            event["hardwareStopKind"] = "watched-bytes-unchanged"
        with self.assertRaisesRegex(ValueError, name):
            self.validate(trace)

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
        trace["codeWindows"][0]["hex"] = "00" + trace["codeWindows"][0]["hex"][2:]
        with self.assertRaisesRegex(ValueError, "code-window identity"):
            self.validate(trace)

    def test_code_window_must_contain_the_stop_pc(self):
        trace = passing_trace()
        trace["codeWindows"][0]["startAddress"] += 4
        with self.assertRaisesRegex(ValueError, "code window"):
            self.validate(trace)

    def test_operand_snapshot_tampering_fails_closed(self):
        trace = passing_trace()
        trace["events"][0]["operandSnapshot"]["registers"]["general"][0]["hex"] = (
            "00" * 8
        )
        with self.assertRaisesRegex(ValueError, "raw value"):
            self.validate(trace)

    def test_missing_required_x19_role_snapshot_fails_closed(self):
        trace = passing_trace()
        operands = trace["events"][0]["operandSnapshot"]
        probe = next(
            item
            for item in operands["prepareLayerRoleProbes"]
            if "x19" in item["registerNames"]
        )
        operands["prepareLayerRoleProbes"].remove(probe)
        operands["prepareLayerRoleProbeFailures"].append(
            {
                "registerNames": probe["registerNames"],
                "registerValue": probe["registerValue"],
                "address": probe["address"],
                "message": "synthetic role read failure",
            }
        )
        with self.assertRaisesRegex(ValueError, "x19 role snapshot"):
            self.validate(trace)

    def test_prepare_layer_role_memory_tampering_fails_closed(self):
        trace = passing_trace()
        probe = trace["events"][0]["operandSnapshot"]["prepareLayerRoleProbes"][0]
        probe["hex"] = "00" + probe["hex"][2:]
        with self.assertRaisesRegex(ValueError, "role memory identity"):
            self.validate(trace)

    def test_late_candidate_diagnostic_tampering_fails_closed(self):
        trace = passing_trace()
        trace["lateCandidateDiagnostics"][0]["sourceOwner"] += 8
        with self.assertRaisesRegex(ValueError, "late candidate pointer chain"):
            self.validate(trace)

    def test_selected_late_candidate_index_fails_closed(self):
        trace = passing_trace()
        trace["objectChain"]["selectedLateCandidateIndex"] = 1
        with self.assertRaisesRegex(ValueError, "selected late candidate"):
            self.validate(trace)

    def test_deprecated_hardware_index_is_not_an_identity_fails_closed(self):
        trace = passing_trace()
        trace["watchpoints"][0]["deprecatedHardwareIndex"] = 0
        with self.assertRaisesRegex(ValueError, "watchpoint identity"):
            self.validate(trace)

    def test_debugger_failure_is_retained_as_failure(self):
        trace = copy.deepcopy(passing_trace())
        trace["failures"] = [{"stage": "writer-watchpoint", "message": "failed"}]
        trace["finalFailureCount"] = 1
        with self.assertRaisesRegex(ValueError, "prospective configuration"):
            self.validate(trace)


if __name__ == "__main__":
    unittest.main()
