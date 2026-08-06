#!/usr/bin/env python3
"""Validate the frozen local-macOS symbol inventory without tolerances."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_ROLES = (
    "groupMargin",
    "updateSDFEffects",
    "marginSetter",
    "copyRenderLayer",
    "backdropBounds",
)
SWIFTUI_ROLES = frozenset(("groupMargin", "updateSDFEffects"))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"{path} is not a JSON object")
    return value


def validate(
    trace_path: Path,
    preregistration_path: Path,
) -> dict[str, Any]:
    trace = _load(trace_path)
    preregistration = _load(preregistration_path)
    _require(
        trace.get("localHostSymbolInventorySchemaVersion") == 1,
        "trace schema differs",
    )
    _require(
        preregistration.get("localHostSymbolInventoryPreregistrationSchemaVersion")
        == 1,
        "preregistration schema differs",
    )
    _require(trace.get("status") == "finalized", "trace is not finalized")
    _require(
        trace.get("statusBeforeFinalization") == "captured",
        "capture did not close successfully",
    )
    _require(trace.get("failures") == [], "trace contains failures")
    _require(trace.get("finalFailureCount") == 0, "failure count differs")
    _require(
        trace.get("finalSymbolCount") == len(EXPECTED_ROLES),
        "final symbol count differs",
    )

    trace_configuration = trace.get("configuration", {})
    selection = preregistration["selection"]
    for key in (
        "capturedMarginUsedForSelection",
        "capturedCropUsedForSelection",
        "capturedImageUsedForSelection",
        "capturedPixelUsedForSelection",
    ):
        _require(trace_configuration.get(key) is False, f"trace {key} differs")
        _require(selection.get(key) is False, f"preregistration {key} differs")
    maximum = preregistration["captureContract"]["maximumSymbolByteCount"]
    _require(
        trace_configuration.get("maximumSymbolByteCount") == maximum,
        "symbol byte bound differs",
    )
    requested = {
        item["role"]: item["function"]
        for item in trace_configuration.get("symbols", [])
    }
    frozen_requested = dict(zip(EXPECTED_ROLES, selection["symbols"], strict=True))
    _require(requested == frozen_requested, "requested symbol set differs")

    host = preregistration["hostAntecedent"]
    expected_uuid = {
        role: (
            host["swiftUICoreUUID"] if role in SWIFTUI_ROLES else host["quartzCoreUUID"]
        )
        for role in EXPECTED_ROLES
    }
    modules = trace.get("modules", [])
    module_uuids = {item.get("uuid") for item in modules}
    _require(host["swiftUICoreUUID"] in module_uuids, "SwiftUICore is absent")
    _require(host["quartzCoreUUID"] in module_uuids, "QuartzCore is absent")
    _require(
        "arm64" in trace.get("target", {}).get("triple", ""),
        "target is not arm64",
    )

    records = trace.get("symbols", [])
    by_role = {item.get("role"): item for item in records}
    _require(tuple(by_role) == EXPECTED_ROLES, "symbol role order differs")
    summaries: list[dict[str, Any]] = []
    for role in EXPECTED_ROLES:
        record = by_role[role]
        _require(
            record.get("requestedFunction") == frozen_requested[role],
            f"{role} requested function differs",
        )
        _require(record.get("resolutionCount") == 1, f"{role} is ambiguous")
        code = record.get("code", {})
        module = code.get("module", {})
        _require(module.get("valid") is True, f"{role} module is invalid")
        _require(
            module.get("uuid") == expected_uuid[role],
            f"{role} module UUID differs",
        )
        start = code.get("symbolStart")
        end = code.get("symbolEnd")
        byte_count = code.get("symbolByteCount")
        load_address = module.get("loadAddress")
        module_offset = code.get("moduleOffset")
        _require(
            all(isinstance(value, int) for value in (start, end, byte_count)),
            f"{role} bounds are invalid",
        )
        _require(0 < byte_count <= maximum, f"{role} byte count is invalid")
        _require(end - start == byte_count, f"{role} bounds differ")
        _require(isinstance(load_address, int), f"{role} load address is invalid")
        _require(
            module_offset == start - load_address,
            f"{role} module offset differs",
        )
        try:
            payload = bytes.fromhex(code.get("hex", ""))
        except ValueError as error:
            raise ValueError(f"{role} code is not hexadecimal") from error
        _require(len(payload) == byte_count, f"{role} code length differs")
        digest = hashlib.sha256(payload).hexdigest()
        _require(code.get("codeSHA256") == digest, f"{role} code hash differs")
        summaries.append(
            {
                "role": role,
                "function": code.get("function"),
                "moduleUUID": module["uuid"],
                "moduleOffset": module_offset,
                "symbolByteCount": byte_count,
                "codeSHA256": digest,
            }
        )

    return {
        "localHostSymbolInventoryValidationSchemaVersion": 1,
        "status": "passed",
        "trace": str(trace_path),
        "preregistration": str(preregistration_path),
        "host": {
            "macOSProductVersion": host["macOSProductVersion"],
            "macOSBuildVersion": host["macOSBuildVersion"],
            "swiftUICoreUUID": host["swiftUICoreUUID"],
            "quartzCoreUUID": host["quartzCoreUUID"],
        },
        "symbols": summaries,
        "zeroTolerance": True,
        "productAuthority": preregistration["productAuthority"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("preregistration", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = validate(arguments.trace, arguments.preregistration)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(payload, end="")
    else:
        arguments.output.write_text(payload, encoding="utf-8")


if __name__ == "__main__":
    main()
