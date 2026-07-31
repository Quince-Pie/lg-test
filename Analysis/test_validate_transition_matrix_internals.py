from __future__ import annotations

import copy
import hashlib
import unittest

from validate_transition_matrix_internals import (
    GLASS_BACKGROUND_RENDER_SYMBOL,
    GLASS_MATRIX_CONSTRUCTOR_CALL_OFFSETS,
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


def _branch_link_instruction(
    instruction_address: int,
    target_address: int,
) -> int:
    delta = target_address - instruction_address
    if delta % 4 != 0:
        raise ValueError("BL target is not instruction aligned")
    immediate = delta // 4
    if not -(1 << 25) <= immediate < 1 << 25:
        raise ValueError("BL target is outside the immediate range")
    return 0x9400_0000 | (immediate & 0x03FF_FFFF)


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
    symbol_address = 0x0000_0001_8000_0800
    constructor_address = 0x0000_0001_8000_0400
    code = bytes.fromhex("1f2003d5") * (0x800 // 4)
    symbol_code = bytearray(
        bytes.fromhex("7f2303d5") * (0x2000 // 4)
    )
    source_instructions = []
    for offset in GLASS_MATRIX_CONSTRUCTOR_CALL_OFFSETS:
        instruction = _branch_link_instruction(
            symbol_address + offset,
            constructor_address,
        )
        symbol_code[offset : offset + 4] = instruction.to_bytes(
            4,
            "little",
        )
        source_instructions.append(instruction)
    constructor_code = (
        bytes.fromhex("7f2303d5") * (0x800 // 4)
    )
    call_site = {
        "schemaVersion": 3,
        "executed": True,
        "capture": "transition-matrix-uniform-01-neutral-axes",
        "frameCount": 1,
        "quartzCoreCodeWindowCount": 1,
        "glassBackgroundRenderCodeCaptureCount": 1,
        "glassMatrixConstructorCodeCaptureCount": 1,
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
                "symbol": GLASS_BACKGROUND_RENDER_SYMBOL,
                "symbolAddress": f"0x{symbol_address:016x}",
                "symbolOffset": "0xc00",
                "symbolCode": {
                    **_capture(
                        bytes(symbol_code),
                        "mapped arm64e QuartzCore symbol prefix",
                    ),
                    "symbol": GLASS_BACKGROUND_RENDER_SYMBOL,
                    "startAddress": f"0x{symbol_address:016x}",
                    "imageOffset": "0x800",
                    "requestedByteCount": 0x2000,
                },
                "matrixConstructorCode": {
                    **_capture(
                        constructor_code,
                        (
                            "mapped arm64e QuartzCore "
                            "matrix-constructor region"
                        ),
                    ),
                    "startAddress":
                        f"0x{constructor_address:016x}",
                    "imageOffset": "0x400",
                    "sourceCallOffsets": list(
                        GLASS_MATRIX_CONSTRUCTOR_CALL_OFFSETS
                    ),
                    "sourceCallInstructions": [
                        f"{instruction:08x}"
                        for instruction in source_instructions
                    ],
                    "sourceCallTargets": [
                        f"0x{constructor_address:016x}"
                        for _ in source_instructions
                    ],
                    "requestedByteCount": 0x800,
                },
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

    def test_rejects_changed_symbol_code_byte(self) -> None:
        basis = copy.deepcopy(_valid_call_site_basis())
        records = basis["records"]
        assert isinstance(records, list)
        call_site = records[0]["render"][
            "glassFragmentUniformBindings"
        ][0]["uniformCallSite"]
        symbol_code = call_site["frames"][0]["symbolCode"]
        encoded = str(symbol_code["hex"])
        symbol_code["hex"] = "00" + encoded[2:]
        with self.assertRaisesRegex(
            MatrixInternalsValidationError,
            "sha256",
        ):
            validate_glass_uniform_call_site(basis)

    def test_rejects_changed_matrix_constructor_code_byte(
        self,
    ) -> None:
        basis = copy.deepcopy(_valid_call_site_basis())
        records = basis["records"]
        assert isinstance(records, list)
        call_site = records[0]["render"][
            "glassFragmentUniformBindings"
        ][0]["uniformCallSite"]
        constructor_code = call_site["frames"][0][
            "matrixConstructorCode"
        ]
        encoded = str(constructor_code["hex"])
        constructor_code["hex"] = "00" + encoded[2:]
        with self.assertRaisesRegex(
            MatrixInternalsValidationError,
            "sha256",
        ):
            validate_glass_uniform_call_site(basis)

    def test_rejects_divergent_matrix_constructor_call(
        self,
    ) -> None:
        basis = copy.deepcopy(_valid_call_site_basis())
        records = basis["records"]
        assert isinstance(records, list)
        frame = records[0]["render"][
            "glassFragmentUniformBindings"
        ][0]["uniformCallSite"]["frames"][0]
        symbol_code = frame["symbolCode"]
        raw = bytearray.fromhex(str(symbol_code["hex"]))
        symbol_address = int(str(frame["symbolAddress"]), 16)
        constructor_address = int(
            str(frame["matrixConstructorCode"]["startAddress"]),
            16,
        )
        offset = GLASS_MATRIX_CONSTRUCTOR_CALL_OFFSETS[1]
        instruction = _branch_link_instruction(
            symbol_address + offset,
            constructor_address + 4,
        )
        raw[offset : offset + 4] = instruction.to_bytes(4, "little")
        symbol_code.update(
            _capture(
                bytes(raw),
                "mapped arm64e QuartzCore symbol prefix",
            )
        )
        with self.assertRaisesRegex(
            MatrixInternalsValidationError,
            "BL targets differ",
        ):
            validate_glass_uniform_call_site(basis)


if __name__ == "__main__":
    unittest.main()
