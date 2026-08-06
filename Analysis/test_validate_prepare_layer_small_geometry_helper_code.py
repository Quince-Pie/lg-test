#!/usr/bin/env python3
"""Checks for the small-geometry helper-code validator."""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

import validate_prepare_layer_small_geometry_helper_code as validator


class SmallGeometryHelperCodeValidatorTests(unittest.TestCase):
    def test_discovered_code_hash_is_derived_from_retained_bytes(self) -> None:
        code = bytes.fromhex("1f2003d5c0035fd6")
        start = 0x1000
        spec = {
            "name": "probe",
            "function": "probe()",
            "relativeToPrepareLayer": 0,
            "symbolByteCount": len(code),
            "expectedCodeSHA256": None,
        }
        target = {
            "name": "probe",
            "function": "probe()",
            "relativeToPrepareLayer": 0,
            "symbolStart": start,
            "symbolEnd": start + len(code),
            "symbolByteCount": len(code),
            "expectedSHA256": None,
            "observedSHA256": hashlib.sha256(code).hexdigest(),
            "hex": code.hex(),
            "instructionCount": 2,
            "instructions": [
                {
                    "pc": start,
                    "offset": 0,
                    "rawLittleEndianHex": code[:4].hex(),
                    "mnemonic": "nop",
                    "operands": "",
                    "comment": "",
                },
                {
                    "pc": start + 4,
                    "offset": 4,
                    "rawLittleEndianHex": code[4:].hex(),
                    "mnemonic": "ret",
                    "operands": "",
                    "comment": "",
                },
            ],
            "module": {"valid": True, "path": "/QuartzCore", "loadAddress": 1},
            "cropValuesUsedForSelection": False,
            "outputValuesUsedForSelection": False,
        }
        result, retained = validator.validate_target(
            target,
            spec,
            start,
            {"valid": True, "path": "/QuartzCore", "loadAddress": 1},
        )
        self.assertEqual(retained, code)
        self.assertEqual(result["codeSHA256"], hashlib.sha256(code).hexdigest())
        self.assertFalse(result["codeHashAcceptedBeforeCapture"])

    def test_configuration_accepts_no_code_or_output_candidate(self) -> None:
        configuration = validator.EXPECTED_CONFIGURATION
        self.assertIsNone(configuration["expectedCodeSHA256"])
        self.assertTrue(configuration["staticMemoryReadsOnly"])
        self.assertEqual(configuration["breakpointsAdded"], 0)
        self.assertEqual(configuration["instructionStepsAdded"], 0)
        self.assertFalse(configuration["cropValuesUsedForSelection"])
        self.assertFalse(configuration["outputValuesUsedForSelection"])
        for spec in validator.EXPECTED_SPECS:
            self.assertIsNone(spec["expectedCodeSHA256"])

    def test_product_authority_remains_closed(self) -> None:
        source = Path(validator.__file__).read_text(encoding="utf-8")
        self.assertIn('"gaussianExpansionGeneralSemanticsDecoded": False', source)
        self.assertIn('"backdropAllocationGeneralSemanticsDecoded": False', source)
        self.assertIn('"regularGeometryTransferPassed": False', source)
        self.assertIn('"productionShaderAuthorized": False', source)
        self.assertIn('"liquidGlassParityEstablished": False', source)
        self.assertNotIn('"liquidGlassParityEstablished": True', source)


if __name__ == "__main__":
    unittest.main()
