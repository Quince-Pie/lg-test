"""Validate byte-exact private matrix-constructor evidence."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any, Never


class MatrixInternalsValidationError(ValueError):
    """The captured constructor evidence is incomplete or inconsistent."""


def _fail(message: str) -> Never:
    raise MatrixInternalsValidationError(message)


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{field} is not an object")
    return value


def _integer(value: object, field: str) -> int:
    if type(value) is not int:
        _fail(f"{field} is not an integer")
    return value


def _hex_integer(value: object, field: str) -> int:
    if not isinstance(value, str):
        _fail(f"{field} is not a hexadecimal string")
    try:
        return int(value, 16)
    except ValueError:
        _fail(f"{field} is not valid hexadecimal")


def _byte_capture(
    value: object,
    *,
    field: str,
    expected_class: str,
    expected_length: int,
) -> bytes:
    capture = _mapping(value, field)
    if capture.get("class") != expected_class:
        _fail(f"{field}.class differs")
    if capture.get("lengthBytes") != expected_length:
        _fail(f"{field}.lengthBytes differs")
    encoded = capture.get("hex")
    if not isinstance(encoded, str) or len(encoded) != expected_length * 2:
        _fail(f"{field}.hex has the wrong length")
    try:
        raw = bytes.fromhex(encoded)
    except ValueError:
        _fail(f"{field}.hex is not valid hexadecimal")
    if len(raw) != expected_length:
        _fail(f"{field}.hex decodes to the wrong length")
    digest = capture.get("sha256")
    if not isinstance(digest, str):
        _fail(f"{field}.sha256 is absent")
    if hashlib.sha256(raw).hexdigest() != digest:
        _fail(f"{field}.sha256 differs")
    return raw


def validate_vibrant_matrix_internals(matrix_basis: object) -> None:
    """Fail unless the vibrant-matrix code and constant bytes are coherent."""

    basis = _mapping(matrix_basis, "matrixUniformBasis")
    internals = _mapping(
        basis.get("vibrantMatrixInternals"),
        "vibrantMatrixInternals",
    )
    if internals.get("schemaVersion") != 1:
        _fail("vibrantMatrixInternals.schemaVersion differs")
    if internals.get("executed") is not True:
        _fail("vibrantMatrixInternals did not execute")
    if (
        internals.get("symbol")
        != "MTCAColorMatrixMakeWithVibrantShadowAttributes"
    ):
        _fail("vibrantMatrixInternals.symbol differs")

    function_length = _integer(
        internals.get("functionCodeByteCount"),
        "functionCodeByteCount",
    )
    instruction_offset = _integer(
        internals.get("dataPageInstructionOffset"),
        "dataPageInstructionOffset",
    )
    capture_offset = _integer(
        internals.get("dataCaptureOffset"),
        "dataCaptureOffset",
    )
    capture_length = _integer(
        internals.get("dataCaptureByteCount"),
        "dataCaptureByteCount",
    )
    if (
        function_length != 0x324
        or instruction_offset != 0x2C
        or capture_offset != 0x530
        or capture_length != 0x100
    ):
        _fail("vibrantMatrixInternals byte ranges differ")

    code = _byte_capture(
        internals.get("code"),
        field="code",
        expected_class="mapped arm64e instructions",
        expected_length=function_length,
    )
    constant_data = _byte_capture(
        internals.get("constantData"),
        field="constantData",
        expected_class="pc-relative mapped constant data",
        expected_length=capture_length,
    )
    if code[:4] != bytes.fromhex("7f2303d5"):
        _fail("constructor entry instruction differs")
    if not any(constant_data):
        _fail("constant-data capture is entirely zero")

    instruction = _hex_integer(
        internals.get("dataPageInstruction"),
        "dataPageInstruction",
    )
    captured_instruction = int.from_bytes(
        code[instruction_offset : instruction_offset + 4],
        "little",
    )
    if captured_instruction != instruction:
        _fail("captured ADRP instruction differs from constructor code")
    if instruction & 0x9F00_001F != 0x9000_0008:
        _fail("constructor data-page instruction is not ADRP x8")

    page_delta = _integer(
        internals.get("dataPageDeltaPages"),
        "dataPageDeltaPages",
    )
    function_address = _hex_integer(
        internals.get("functionAddress"),
        "functionAddress",
    )
    data_page_address = _hex_integer(
        internals.get("dataPageAddress"),
        "dataPageAddress",
    )
    data_capture_address = _hex_integer(
        internals.get("dataCaptureAddress"),
        "dataCaptureAddress",
    )
    image_base = _hex_integer(
        internals.get("imageBase"),
        "imageBase",
    )
    image_offset = _hex_integer(
        internals.get("imageOffset"),
        "imageOffset",
    )
    expected_page = (
        (function_address + instruction_offset) & ~0xFFF
    ) + page_delta * 0x1000
    if data_page_address != expected_page:
        _fail("decoded data-page address is inconsistent")
    if data_capture_address != data_page_address + capture_offset:
        _fail("constant-data address is inconsistent")
    if function_address != image_base + image_offset:
        _fail("constructor image offset is inconsistent")
    image_path = internals.get("imagePath")
    if not isinstance(image_path, str) or not image_path.endswith(
        "/CoreMaterial"
    ):
        _fail("constructor image path differs")
