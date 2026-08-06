#!/usr/bin/env python3
"""Tests for exact local-host symbol-inventory validation."""

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from validate_local_host_symbol_inventory import EXPECTED_ROLES, validate


ANALYSIS = Path(__file__).parent
PREREGISTRATION = ANALYSIS / "local_host_symbol_inventory_preregistration.json"


def _valid_trace() -> dict[str, object]:
    preregistration = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    host = preregistration["hostAntecedent"]
    functions = preregistration["selection"]["symbols"]
    symbols = []
    modules = []
    for index, (role, function) in enumerate(
        zip(EXPECTED_ROLES, functions, strict=True)
    ):
        payload = bytes((index + 1, index + 2, index + 3, index + 4))
        uuid = (
            host["swiftUICoreUUID"]
            if role in ("groupMargin", "updateSDFEffects")
            else host["quartzCoreUUID"]
        )
        load_address = 0x100000000 + index * 0x100000
        start = load_address + 0x1000
        module = {
            "valid": True,
            "path": "/System/Library/Frameworks/Test.framework/Test",
            "uuid": uuid,
            "loadAddress": load_address,
        }
        modules.append(module)
        symbols.append(
            {
                "role": role,
                "requestedFunction": function,
                "resolutionCount": 1,
                "code": {
                    "function": function,
                    "symbolStart": start,
                    "symbolEnd": start + len(payload),
                    "symbolByteCount": len(payload),
                    "moduleOffset": 0x1000,
                    "codeSHA256": hashlib.sha256(payload).hexdigest(),
                    "hex": payload.hex(),
                    "module": module,
                },
            }
        )
    return {
        "localHostSymbolInventorySchemaVersion": 1,
        "status": "finalized",
        "statusBeforeFinalization": "captured",
        "configuration": {
            "maximumSymbolByteCount": 0x40000,
            "symbols": [
                {"role": role, "function": function}
                for role, function in zip(EXPECTED_ROLES, functions, strict=True)
            ],
            "capturedMarginUsedForSelection": False,
            "capturedCropUsedForSelection": False,
            "capturedImageUsedForSelection": False,
            "capturedPixelUsedForSelection": False,
        },
        "target": {"triple": "arm64-apple-macosx26.6.0"},
        "process": {"stopFunction": "main"},
        "modules": modules,
        "symbols": symbols,
        "failures": [],
        "finalSymbolCount": 5,
        "finalFailureCount": 0,
    }


class LocalHostSymbolInventoryValidationTests(unittest.TestCase):
    def _validate(self, trace: dict[str, object]) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.json"
            path.write_text(json.dumps(trace), encoding="utf-8")
            return validate(path, PREREGISTRATION)

    def test_valid_inventory_passes(self) -> None:
        result = self._validate(_valid_trace())
        self.assertEqual(result["status"], "passed")
        self.assertEqual(len(result["symbols"]), 5)
        self.assertTrue(result["zeroTolerance"])

    def test_tampered_code_fails(self) -> None:
        trace = _valid_trace()
        trace["symbols"][0]["code"]["hex"] = "00000000"
        with self.assertRaisesRegex(ValueError, "code hash differs"):
            self._validate(trace)

    def test_wrong_framework_uuid_fails(self) -> None:
        trace = _valid_trace()
        trace["symbols"][0]["code"]["module"]["uuid"] = "WRONG"
        with self.assertRaisesRegex(ValueError, "module UUID differs"):
            self._validate(trace)

    def test_output_based_selection_fails(self) -> None:
        trace = copy.deepcopy(_valid_trace())
        trace["configuration"]["capturedPixelUsedForSelection"] = True
        with self.assertRaisesRegex(ValueError, "trace capturedPixel"):
            self._validate(trace)


if __name__ == "__main__":
    unittest.main()
