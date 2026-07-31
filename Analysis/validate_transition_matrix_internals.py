"""Validate byte-exact private matrix-constructor evidence."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any, Never


class MatrixInternalsValidationError(ValueError):
    """The captured constructor evidence is incomplete or inconsistent."""


GLASS_BACKGROUND_RENDER_SYMBOL = (
    "_ZN2CA3OGL21GlassBackgroundFilter6renderEPKNS_6Render6Filter"
    "EPKNS0_5LayerERNS0_7ContextEfPPNS0_7SurfaceEPfS8_"
    "PKNS_11ColorMatrixE"
)


def _fail(message: str) -> Never:
    raise MatrixInternalsValidationError(message)


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{field} is not an object")
    return value


def _list(value: object, field: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(f"{field} is not an array")
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


def validate_glass_uniform_call_site(matrix_basis: object) -> None:
    """Fail unless the real QuartzCore uniform-bind call site is captured."""

    basis = _mapping(matrix_basis, "matrixUniformBasis")
    records = _list(basis.get("records"), "matrixUniformBasis.records")
    neutral_records = [
        _mapping(record, "matrixUniformBasis.records[]")
        for record in records
        if isinstance(record, Mapping)
        and record.get("name") == "neutral-axes"
    ]
    if len(neutral_records) != 1:
        _fail("neutral-axes intervention is not unique")
    render = _mapping(
        neutral_records[0].get("render"),
        "neutral-axes.render",
    )
    bindings = _list(
        render.get("glassFragmentUniformBindings"),
        "neutral-axes glass bindings",
    )
    call_sites = [
        binding.get("uniformCallSite")
        for binding in bindings
        if isinstance(binding, Mapping)
        and binding.get("uniformCallSite") is not None
    ]
    if len(call_sites) != 1:
        _fail(
            "neutral-axes does not contain exactly one uniform call site"
        )
    call_site = _mapping(call_sites[0], "uniformCallSite")
    if (
        call_site.get("schemaVersion") != 2
        or call_site.get("executed") is not True
        or call_site.get("capture")
        != "transition-matrix-uniform-01-neutral-axes"
    ):
        _fail("uniformCallSite metadata differs")

    frames = _list(call_site.get("frames"), "uniformCallSite.frames")
    if call_site.get("frameCount") != len(frames) or not frames:
        _fail("uniformCallSite frame count differs")
    code_window_count = 0
    render_code_count = 0
    for expected_index, value in enumerate(frames):
        frame = _mapping(value, f"uniformCallSite.frames[{expected_index}]")
        if frame.get("index") != expected_index:
            _fail("uniformCallSite frame order differs")
        return_address = _hex_integer(
            frame.get("returnAddress"),
            "uniformCallSite returnAddress",
        )
        if "imageBase" in frame or "imageOffset" in frame:
            image_base = _hex_integer(
                frame.get("imageBase"),
                "uniformCallSite imageBase",
            )
            image_offset = _hex_integer(
                frame.get("imageOffset"),
                "uniformCallSite imageOffset",
            )
            if return_address != image_base + image_offset:
                _fail("uniformCallSite image offset is inconsistent")

        symbol_code_value = frame.get("symbolCode")
        if symbol_code_value is not None:
            if frame.get("symbol") != GLASS_BACKGROUND_RENDER_SYMBOL:
                _fail("uniformCallSite symbol-code owner differs")
            image_path = frame.get("imagePath")
            if (
                not isinstance(image_path, str)
                or "/QuartzCore.framework/" not in image_path
            ):
                _fail("uniformCallSite symbol code is not from QuartzCore")
            image_base = _hex_integer(
                frame.get("imageBase"),
                "uniformCallSite symbol-code imageBase",
            )
            symbol_address = _hex_integer(
                frame.get("symbolAddress"),
                "uniformCallSite symbolAddress",
            )
            symbol_offset = _hex_integer(
                frame.get("symbolOffset"),
                "uniformCallSite symbolOffset",
            )
            if return_address != symbol_address + symbol_offset:
                _fail("uniformCallSite symbol offset is inconsistent")
            symbol_code = _mapping(
                symbol_code_value,
                "uniformCallSite symbolCode",
            )
            if (
                symbol_code.get("symbol")
                != GLASS_BACKGROUND_RENDER_SYMBOL
                or symbol_code.get("requestedByteCount") != 0x2000
            ):
                _fail("uniformCallSite symbol-code metadata differs")
            code = _byte_capture(
                symbol_code,
                field="uniformCallSite symbolCode",
                expected_class=(
                    "mapped arm64e QuartzCore symbol prefix"
                ),
                expected_length=0x2000,
            )
            start_address = _hex_integer(
                symbol_code.get("startAddress"),
                "uniformCallSite symbol-code startAddress",
            )
            image_offset = _hex_integer(
                symbol_code.get("imageOffset"),
                "uniformCallSite symbol-code imageOffset",
            )
            if (
                start_address != symbol_address
                or symbol_address != image_base + image_offset
            ):
                _fail(
                    "uniformCallSite symbol-code address is inconsistent"
                )
            if not any(code):
                _fail("uniformCallSite symbol code is entirely zero")
            render_code_count += 1

        code_value = frame.get("codeWindow")
        if code_value is None:
            continue
        image_path = frame.get("imagePath")
        if (
            not isinstance(image_path, str)
            or "/QuartzCore.framework/" not in image_path
        ):
            _fail("uniformCallSite code window is not from QuartzCore")
        code_window = _mapping(
            code_value,
            "uniformCallSite codeWindow",
        )
        code = _byte_capture(
            code_window,
            field="uniformCallSite codeWindow",
            expected_class="mapped arm64e call-site window",
            expected_length=0x800,
        )
        if not any(code):
            _fail("uniformCallSite code window is entirely zero")
        start_address = _hex_integer(
            code_window.get("startAddress"),
            "uniformCallSite codeWindow startAddress",
        )
        return_offset = _integer(
            code_window.get("returnInstructionOffset"),
            "uniformCallSite returnInstructionOffset",
        )
        if (
            return_offset != 0x400
            or start_address + return_offset != return_address & ~0x3
        ):
            _fail("uniformCallSite code window address is inconsistent")
        code_window_count += 1

    if (
        code_window_count < 1
        or code_window_count > 8
        or call_site.get("quartzCoreCodeWindowCount")
        != code_window_count
    ):
        _fail("uniformCallSite QuartzCore code-window count differs")
    if (
        render_code_count != 1
        or call_site.get("glassBackgroundRenderCodeCaptureCount")
        != render_code_count
    ):
        _fail("uniformCallSite glass render-code count differs")
