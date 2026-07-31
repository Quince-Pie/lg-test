from __future__ import annotations

import copy
import hashlib
import unittest

from validate_transition_matrix_internals import (
    MatrixInternalsValidationError,
    validate_glass_uniform_call_site,
    validate_vibrant_matrix_internals,
)


def _capture(raw: bytes, class_name: str) -> dict[str, object]:
    return {
        "class": class_name,
        "lengthBytes": len(raw),
        "hex": raw.hex(),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _valid_basis() -> dict[str, object]:
    code = bytearray(0x324)
    code[:4] = bytes.fromhex("7f2303d5")
    instruction = 0xD0000068
    code[0x2C:0x30] = instruction.to_bytes(4, "little")
    constants = bytes(range(256))
    return {
        "vibrantMatrixInternals": {
            "schemaVersion": 1,
            "executed": True,
            "symbol": (
                "MTCAColorMatrixMakeWithVibrantShadowAttributes"
            ),
            "functionAddress": "0x0000000180001234",
            "functionCodeByteCount": 0x324,
            "dataPageInstructionOffset": 0x2C,
            "dataPageInstruction": f"{instruction:08x}",
            "dataPageDeltaPages": 14,
            "dataPageAddress": "0x000000018000f000",
            "dataCaptureOffset": 0x530,
            "dataCaptureAddress": "0x000000018000f530",
            "dataCaptureByteCount": 0x100,
            "imagePath": (
                "/System/Library/PrivateFrameworks/"
                "CoreMaterial.framework/Versions/A/CoreMaterial"
            ),
            "imageBase": "0x0000000180000000",
            "imageOffset": "0x1234",
            "code": _capture(
                bytes(code),
                "mapped arm64e instructions",
            ),
            "constantData": _capture(
                constants,
                "pc-relative mapped constant data",
            ),
        }
    }


def _valid_call_site_basis() -> dict[str, object]:
    return_address = 0x0000_0001_8000_1400
    code = bytes.fromhex("1f2003d5") * (0x800 // 4)
    call_site = {
        "schemaVersion": 1,
        "executed": True,
        "capture": "transition-matrix-uniform-01-neutral-axes",
        "frameCount": 1,
        "quartzCoreCodeWindowCount": 1,
        "frames": [
            {
                "index": 0,
                "returnAddress": f"0x{return_address:016x}",
                "imagePath": (
                    "/System/Library/Frameworks/"
                    "QuartzCore.framework/Versions/A/QuartzCore"
                ),
                "imageBase": "0x0000000180000000",
                "imageOffset": "0x1400",
                "codeWindow": {
                    **_capture(
                        code,
                        "mapped arm64e call-site window",
                    ),
                    "startAddress": "0x0000000180001000",
                    "returnInstructionOffset": 0x400,
                },
            }
        ],
    }
    return {
        "records": [
            {
                "name": "neutral-axes",
                "render": {
                    "glassFragmentUniformBindings": [
                        {"uniformCallSite": call_site},
                        {},
                    ]
                },
            }
        ]
    }


class MatrixInternalsValidatorTests(unittest.TestCase):
    def test_accepts_coherent_capture(self) -> None:
        validate_vibrant_matrix_internals(_valid_basis())

    def test_rejects_changed_constant_byte(self) -> None:
        basis = copy.deepcopy(_valid_basis())
        internals = basis["vibrantMatrixInternals"]
        assert isinstance(internals, dict)
        constants = internals["constantData"]
        assert isinstance(constants, dict)
        encoded = str(constants["hex"])
        constants["hex"] = "ff" + encoded[2:]
        with self.assertRaisesRegex(
            MatrixInternalsValidationError,
            "sha256",
        ):
            validate_vibrant_matrix_internals(basis)

    def test_rejects_misdirected_page(self) -> None:
        basis = copy.deepcopy(_valid_basis())
        internals = basis["vibrantMatrixInternals"]
        assert isinstance(internals, dict)
        internals["dataPageAddress"] = "0x0000000180010000"
        with self.assertRaisesRegex(
            MatrixInternalsValidationError,
            "data-page address",
        ):
            validate_vibrant_matrix_internals(basis)

    def test_rejects_non_adrp_instruction(self) -> None:
        basis = copy.deepcopy(_valid_basis())
        internals = basis["vibrantMatrixInternals"]
        assert isinstance(internals, dict)
        code = bytearray.fromhex(
            str(
                (
                    internals["code"]
                    if isinstance(internals["code"], dict)
                    else {}
                ).get("hex", "")
            )
        )
        code[0x2C:0x30] = (0).to_bytes(4, "little")
        internals["dataPageInstruction"] = "00000000"
        internals["code"] = _capture(
            bytes(code),
            "mapped arm64e instructions",
        )
        with self.assertRaisesRegex(
            MatrixInternalsValidationError,
            "not ADRP",
        ):
            validate_vibrant_matrix_internals(basis)


class GlassUniformCallSiteValidatorTests(unittest.TestCase):
    def test_accepts_coherent_call_site(self) -> None:
        validate_glass_uniform_call_site(_valid_call_site_basis())

    def test_rejects_changed_code_byte(self) -> None:
        basis = copy.deepcopy(_valid_call_site_basis())
        records = basis["records"]
        assert isinstance(records, list)
        call_site = records[0]["render"][
            "glassFragmentUniformBindings"
        ][0]["uniformCallSite"]
        code_window = call_site["frames"][0]["codeWindow"]
        encoded = str(code_window["hex"])
        code_window["hex"] = "00" + encoded[2:]
        with self.assertRaisesRegex(
            MatrixInternalsValidationError,
            "sha256",
        ):
            validate_glass_uniform_call_site(basis)

    def test_rejects_inconsistent_return_address(self) -> None:
        basis = copy.deepcopy(_valid_call_site_basis())
        records = basis["records"]
        assert isinstance(records, list)
        call_site = records[0]["render"][
            "glassFragmentUniformBindings"
        ][0]["uniformCallSite"]
        call_site["frames"][0]["returnAddress"] = (
            "0x0000000180001404"
        )
        with self.assertRaisesRegex(
            MatrixInternalsValidationError,
            "image offset",
        ):
            validate_glass_uniform_call_site(basis)


if __name__ == "__main__":
    unittest.main()
