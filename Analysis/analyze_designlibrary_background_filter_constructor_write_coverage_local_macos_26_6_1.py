#!/usr/bin/env python3
"""Prove BackgroundFilter constructor write coverage from native code."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path


DYLD_INFO = Path("/Library/Developer/CommandLineTools/usr/bin/dyld_info")
FRAMEWORK = Path(
    "/System/Library/PrivateFrameworks/DesignLibrary.framework/Versions/A/DesignLibrary"
)
EXPECTED_UUID = "1E980802-69F5-3E69-89EF-50088297FCF5"
EXPECTED_MACOS_PRODUCT_VERSION = "26.6.1"
EXPECTED_MACOS_BUILD_VERSION = "25G76"
EXPECTED_HARDWARE_MODEL = "MacBookPro18,2"
SOURCE_RELATIVE_PATH = (
    "Analysis/"
    "analyze_designlibrary_background_filter_constructor_write_coverage_"
    "local_macos_26_6_1.py"
)

CONSTRUCTOR_START = 0x24091BD00
CONSTRUCTOR_END = 0x24091C114
CONSTRUCTOR_SHA256 = (
    "71a592bc8a187fe8bcca0fa50c3f4d36ea3c2916dbd5d16f3fa1df05b86f131d"
)
TERMINAL_WRITE_START = 0x24091BFB8
TERMINAL_WRITE_END = 0x24091C0EC
BACKGROUND_FILTER_BYTE_COUNT = 0x1F8
EXPECTED_INITIALIZED_RANGES = (
    (0x000, 0x15D),
    (0x160, 0x1CA),
    (0x1D0, 0x1DC),
    (0x1E0, 0x1F8),
)
EXPECTED_PADDING_RANGES = (
    (0x15D, 0x160),
    (0x1CA, 0x1D0),
    (0x1DC, 0x1E0),
)

BYTE_LINE = re.compile(r"^0x([0-9A-Fa-f]+):((?: [0-9A-Fa-f]{2})+)\s*$")
INSTRUCTION_LINE = re.compile(
    r"^0x([0-9A-Fa-f]+)\s+([^\s]+)(?:\s+(.*?))?\s*$"
)
MEMORY_OPERAND = re.compile(
    r"\[(x[0-9]+|sp)(?:,\s*#(-?0x[0-9A-Fa-f]+|-?[0-9]+))?\]"
)
ADD_IMMEDIATE = re.compile(
    r"^(x[0-9]+),\s*(x[0-9]+),\s*#(0x[0-9A-Fa-f]+|[0-9]+)$"
)
REGISTER = re.compile(r"^([xwqdsbh][0-9]+|[xw]zr)$")


class AnalysisError(RuntimeError):
    """Raised when native code differs from the fail-closed contract."""


def run(arguments: Sequence[str]) -> str:
    completed = subprocess.run(
        [str(DYLD_INFO), *arguments, str(FRAMEWORK)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise AnalysisError(
            "dyld_info failed: "
            + " ".join(arguments)
            + "\n"
            + completed.stderr.strip()
        )
    return completed.stdout


def command_output(arguments: Sequence[str]) -> str:
    completed = subprocess.run(
        list(arguments),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise AnalysisError(
            "command failed: "
            + " ".join(arguments)
            + "\n"
            + completed.stderr.strip()
        )
    return completed.stdout.strip()


def parse_code_bytes(output: str, start: int, end: int) -> bytes:
    memory: dict[int, int] = {}
    for line in output.splitlines():
        match = BYTE_LINE.match(line)
        if match is None:
            continue
        address = int(match.group(1), 16)
        payload = bytes.fromhex(match.group(2))
        for index, value in enumerate(payload):
            byte_address = address + index
            if start <= byte_address < end:
                if byte_address in memory:
                    raise AnalysisError(
                        "duplicate constructor byte at {:#x}".format(byte_address)
                    )
                memory[byte_address] = value
    missing = [address for address in range(start, end) if address not in memory]
    if missing:
        raise AnalysisError(
            "constructor byte coverage has {} gaps; first at {:#x}".format(
                len(missing), missing[0]
            )
        )
    return bytes(memory[address] for address in range(start, end))


def parse_instructions(
    output: str,
    start: int,
    end: int,
) -> list[Mapping[str, object]]:
    instructions: list[Mapping[str, object]] = []
    for line in output.splitlines():
        match = INSTRUCTION_LINE.match(line)
        if match is None:
            continue
        address = int(match.group(1), 16)
        if not start <= address < end:
            continue
        instructions.append(
            {
                "address": address,
                "mnemonic": match.group(2).lower(),
                "operands": (match.group(3) or "").strip(),
            }
        )
    expected_addresses = list(range(start, end, 4))
    observed_addresses = [int(value["address"]) for value in instructions]
    if observed_addresses != expected_addresses:
        raise AnalysisError("constructor disassembly address coverage differs")
    return instructions


def register_width(name: str) -> int:
    if not REGISTER.match(name):
        raise AnalysisError("unrecognized store register " + name)
    if name.startswith(("x", "d")):
        return 8
    if name.startswith(("w", "s")):
        return 4
    if name.startswith("q"):
        return 16
    if name.startswith("h"):
        return 2
    if name.startswith("b"):
        return 1
    raise AnalysisError("unsupported store register " + name)


def parse_immediate(value: str) -> int:
    return int(value, 0)


def merge_ranges(ranges: Iterable[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    ordered = sorted(ranges)
    if not ordered:
        return ()
    merged: list[tuple[int, int]] = []
    current_start, current_end = ordered[0]
    for start, end in ordered[1:]:
        if start > current_end:
            merged.append((current_start, current_end))
            current_start, current_end = start, end
        else:
            current_end = max(current_end, end)
    merged.append((current_start, current_end))
    return tuple(merged)


def complement_ranges(
    ranges: Sequence[tuple[int, int]],
    end: int,
) -> tuple[tuple[int, int], ...]:
    cursor = 0
    result: list[tuple[int, int]] = []
    for start, stop in ranges:
        if cursor < start:
            result.append((cursor, start))
        cursor = stop
    if cursor < end:
        result.append((cursor, end))
    return tuple(result)


def store_width(mnemonic: str, source: str) -> int:
    if mnemonic in ("strb",):
        return 1
    if mnemonic in ("strh", "sturh"):
        return 2
    if mnemonic in ("str", "stur"):
        return register_width(source)
    if mnemonic == "stp":
        return register_width(source) * 2
    raise AnalysisError("unsupported store mnemonic " + mnemonic)


def analyze_terminal_writes(
    instructions: Sequence[Mapping[str, object]],
) -> Mapping[str, object]:
    aliases: dict[str, int] = {"x20": 0, "x1": 0x114}
    ranges: list[tuple[int, int]] = []
    records: list[Mapping[str, object]] = []
    store_bases = set()
    for instruction in instructions:
        address = int(instruction["address"])
        if not TERMINAL_WRITE_START <= address < TERMINAL_WRITE_END:
            continue
        mnemonic = str(instruction["mnemonic"])
        operands = str(instruction["operands"])
        add = ADD_IMMEDIATE.match(operands)
        if mnemonic == "add" and add is not None:
            destination, source, immediate = add.groups()
            if source in aliases:
                aliases[destination] = aliases[source] + parse_immediate(immediate)
            continue
        if mnemonic not in ("str", "stur", "strb", "strh", "sturh", "stp"):
            continue
        parts = [part.strip() for part in operands.split(",", 2)]
        source = parts[0]
        memory = MEMORY_OPERAND.search(operands)
        if memory is None:
            raise AnalysisError("store memory operand is unresolved")
        base, immediate = memory.groups()
        store_bases.add(base)
        if base not in aliases:
            raise AnalysisError("terminal store base is not output-derived: " + base)
        offset = aliases[base] + (parse_immediate(immediate) if immediate else 0)
        width = store_width(mnemonic, source)
        stop = offset + width
        if not 0 <= offset < stop <= BACKGROUND_FILTER_BYTE_COUNT:
            raise AnalysisError("terminal store escapes BackgroundFilter output")
        ranges.append((offset, stop))
        records.append(
            {
                "address": "0x{:x}".format(address),
                "mnemonic": mnemonic,
                "operands": operands,
                "outputStart": offset,
                "outputEndExclusive": stop,
                "byteCount": width,
            }
        )
    merged = merge_ranges(ranges)
    padding = complement_ranges(merged, BACKGROUND_FILTER_BYTE_COUNT)
    initialized_count = sum(end - start for start, end in merged)
    if merged != EXPECTED_INITIALIZED_RANGES:
        raise AnalysisError("constructor initialized ranges differ")
    if padding != EXPECTED_PADDING_RANGES:
        raise AnalysisError("constructor padding ranges differ")
    if initialized_count != 491:
        raise AnalysisError("constructor initialized byte count differs")
    return {
        "terminalWriteStart": "0x{:x}".format(TERMINAL_WRITE_START),
        "terminalWriteEndExclusive": "0x{:x}".format(TERMINAL_WRITE_END),
        "storeCount": len(records),
        "storeBaseRegisters": sorted(store_bases),
        "stores": records,
        "initializedRanges": [list(value) for value in merged],
        "initializedByteCount": initialized_count,
        "paddingRanges": [list(value) for value in padding],
        "paddingByteCount": BACKGROUND_FILTER_BYTE_COUNT - initialized_count,
    }


def all_store_bases(
    instructions: Sequence[Mapping[str, object]],
) -> Mapping[str, object]:
    records = []
    for instruction in instructions:
        mnemonic = str(instruction["mnemonic"])
        if mnemonic not in ("str", "stur", "strb", "strh", "sturh", "stp"):
            continue
        operands = str(instruction["operands"])
        memory = MEMORY_OPERAND.search(operands)
        if memory is None:
            raise AnalysisError("constructor store memory operand is unresolved")
        records.append(
            {
                "address": "0x{:x}".format(int(instruction["address"])),
                "mnemonic": mnemonic,
                "operands": operands,
                "baseRegister": memory.group(1),
            }
        )
    bases = sorted({str(value["baseRegister"]) for value in records})
    if bases != ["sp", "x1", "x20", "x8"]:
        raise AnalysisError("constructor memory-store base set differs")
    return {
        "storeCount": len(records),
        "baseRegisters": bases,
        "sourceParametersBaseRegister": "x22",
        "sourceParametersBaseAppearsInStore": "x22" in bases,
        "stores": records,
    }


def normalized_instruction_sha256(
    instructions: Sequence[Mapping[str, object]],
) -> str:
    normalized = "\n".join(
        "{address:016x} {mnemonic} {operands}".format(
            address=int(value["address"]),
            mnemonic=value["mnemonic"],
            operands=value["operands"],
        )
        for value in instructions
    )
    return hashlib.sha256((normalized + "\n").encode("utf-8")).hexdigest()


def native_identity() -> Mapping[str, str]:
    product = command_output(("/usr/bin/sw_vers", "-productVersion"))
    build = command_output(("/usr/bin/sw_vers", "-buildVersion"))
    hardware = command_output(("/usr/sbin/sysctl", "-n", "hw.model"))
    if product != EXPECTED_MACOS_PRODUCT_VERSION or build != EXPECTED_MACOS_BUILD_VERSION:
        raise AnalysisError("macOS identity differs")
    if hardware != EXPECTED_HARDWARE_MODEL:
        raise AnalysisError("hardware identity differs")
    if platform.machine() != "arm64" or platform.system() != "Darwin":
        raise AnalysisError("native architecture differs")
    uuid_output = run(("-uuid",))
    if EXPECTED_UUID not in uuid_output.upper():
        raise AnalysisError("DesignLibrary UUID differs")
    return {
        "system": platform.system(),
        "machine": platform.machine(),
        "hardwareModel": hardware,
        "macOSProductVersion": product,
        "macOSBuildVersion": build,
        "designLibraryUUID": EXPECTED_UUID,
    }


def analyze(source_path: Path) -> Mapping[str, object]:
    if not DYLD_INFO.is_file():
        raise AnalysisError("Command Line Tools dyld_info is missing")
    identity = native_identity()
    code = parse_code_bytes(
        run(("-section_bytes", "__TEXT", "__text")),
        CONSTRUCTOR_START,
        CONSTRUCTOR_END,
    )
    digest = hashlib.sha256(code).hexdigest()
    if digest != CONSTRUCTOR_SHA256:
        raise AnalysisError("BackgroundFilter constructor SHA-256 differs")
    instructions = parse_instructions(
        run(("-disassemble",)),
        CONSTRUCTOR_START,
        CONSTRUCTOR_END,
    )
    writes = analyze_terminal_writes(instructions)
    stores = all_store_bases(instructions)
    source_digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    return {
        "designLibraryBackgroundFilterConstructorWriteCoverageAnalysisSchemaVersion": 1,
        "classification": (
            "native static proof of exact BackgroundFilter constructor store "
            "coverage; no Apple application launch or captured render value"
        ),
        "host": identity,
        "constructor": {
            "start": "0x{:x}".format(CONSTRUCTOR_START),
            "end": "0x{:x}".format(CONSTRUCTOR_END),
            "byteCount": len(code),
            "sha256": digest,
            "instructionCount": len(instructions),
            "normalizedInstructionSHA256": normalized_instruction_sha256(
                instructions
            ),
        },
        "abiPrologue": {
            "sourceParameters": "x0 copied to x22",
            "layerIndex": "x1 copied to x21",
            "environmentFlags": "x2 copied to x19",
            "output": "x8 copied to x20",
        },
        "allMemoryStores": stores,
        "outputWriteCoverage": writes,
        "claims": {
            "backgroundFilterByteCount": BACKGROUND_FILTER_BYTE_COUNT,
            "initializedByteCount": 491,
            "paddingByteCount": 13,
            "sourceParametersWritten": False,
            "full504BytesRetainedByProspectiveCapture": True,
            "onlyInitialized491BytesAreCausalJoinGate": True,
            "liquidGlassParityEstablished": False,
            "productionShaderChangeAuthorized": False,
        },
        "tool": {
            "dyldInfo": str(DYLD_INFO),
            "python": platform.python_version(),
            "source": SOURCE_RELATIVE_PATH,
            "sourceSHA256": source_digest,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        result = analyze(Path(__file__).resolve())
    except (OSError, ValueError, KeyError, AnalysisError) as error:
        parser.error(str(error))
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if arguments.output is None:
        print(payload, end="")
    else:
        arguments.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
