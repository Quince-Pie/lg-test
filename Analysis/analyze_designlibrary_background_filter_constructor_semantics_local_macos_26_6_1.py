#!/usr/bin/env python3
"""Prove BackgroundFilter constructor byte origins from native ARM64 code."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union

import analyze_designlibrary_background_filter_constructor_write_coverage_local_macos_26_6_1 as coverage


RESULT_SCHEMA_VERSION = 1
CONSTRUCTOR_START = coverage.CONSTRUCTOR_START
CONSTRUCTOR_END = coverage.CONSTRUCTOR_END
CONSTRUCTOR_SHA256 = coverage.CONSTRUCTOR_SHA256
BACKGROUND_FILTER_BYTE_COUNT = coverage.BACKGROUND_FILTER_BYTE_COUNT

SHADOW_OPTIONAL_HELPER_START = 0x240917F64
SHADOW_OPTIONAL_HELPER_END = 0x240917F80
SHADOW_OPTIONAL_HELPER_SHA256 = (
    "31156c1bee375fc0b5dd502966dbc45ddfd7902d61538e88bbd9fe2752126d28"
)

TERMINAL_WRITE_START = coverage.TERMINAL_WRITE_START
TERMINAL_WRITE_END = coverage.TERMINAL_WRITE_END
INITIALIZED_RANGES = coverage.EXPECTED_INITIALIZED_RANGES
PADDING_RANGES = coverage.EXPECTED_PADDING_RANGES
EXPECTED_NIL_INDETERMINATE_RANGES = (
    (93, 96),
    (113, 116),
    (133, 136),
    (140, 144),
    (309, 312),
    (329, 332),
    (417, 420),
    (437, 440),
)

GROUPS = (
    "shadow",
    "blur",
    "refraction",
    "faceEffects",
    "edgeBleed",
    "sdrAdjustment",
)

PRESENT_BRANCHES = {
    0x24091BD90: ("shadow", True, "b.ne", "w0, #0x1"),
    0x24091BE4C: ("blur", False, "b.eq", "w12, #0x1"),
    0x24091BE78: ("refraction", False, "b.eq", "w12, #0x1"),
    0x24091BE94: ("faceEffects", True, "b.ne", "w12, #0x1"),
    0x24091BF00: ("edgeBleed", True, "b.ne", "w15, #0x200"),
    0x24091BF94: ("sdrAdjustment", True, "b.ne", "w2, #0x1"),
}

EXPECTED_PRESENT_TRANSFERS = (
    ("layerIndex", 0, 0, 8),
    ("parameters", 24, 8, 144),
    ("parameters", 176, 152, 72),
    ("parameters", 256, 224, 52),
    ("parameters", 312, 276, 73),
    ("parameters", 392, 352, 106),
    ("parameters", 784, 464, 12),
    ("parameters", 800, 480, 16),
    ("environmentFlags", 0, 496, 8),
)

NO_OP_MNEMONICS = {
    "pacibsp",
    "cmp",
    "retab",
}

MEMORY_OPERAND = re.compile(r"^\[(x[0-9]+|sp)(?:,\s*#(-?0x[0-9A-Fa-f]+|-?[0-9]+))?\]$")
REGISTER = re.compile(r"^([xwqdsbhv])([0-9]+)$")


class AnalysisError(RuntimeError):
    """Raised when code or symbolic dataflow differs from the frozen contract."""


@dataclass(frozen=True)
class Pointer:
    space: str
    offset: int


ByteOrigin = str
RegisterValue = Union[Pointer, tuple[ByteOrigin, ...]]


def constant(value: int) -> ByteOrigin:
    return "constant:{:02x}".format(value)


def origin(space: str, offset: int) -> ByteOrigin:
    return "{}:{:04x}".format(space, offset)


def unknown(label: str, offset: int) -> ByteOrigin:
    return "unknown:{}:{:04x}".format(label, offset)


def parse_immediate(value: str) -> int:
    return int(value.lstrip("#"), 0)


def split_operands(value: str) -> list[str]:
    result: list[str] = []
    start = 0
    depth = 0
    for index, character in enumerate(value):
        if character == "[":
            depth += 1
        elif character == "]":
            depth -= 1
        elif character == "," and depth == 0:
            result.append(value[start:index].strip())
            start = index + 1
    result.append(value[start:].strip())
    return result


def register_width(name: str) -> int:
    match = REGISTER.match(name)
    if match is None:
        raise AnalysisError("unrecognized register " + name)
    prefix = match.group(1)
    return {
        "x": 8,
        "w": 4,
        "q": 16,
        "d": 8,
        "s": 4,
        "h": 2,
        "b": 1,
        "v": 16,
    }[prefix]


class SymbolicMachine:
    def __init__(
        self,
        instructions: Sequence[Mapping[str, object]],
        present: Mapping[str, bool],
    ) -> None:
        self.instructions = {int(value["address"]): value for value in instructions}
        self.present = dict(present)
        self.gpr: dict[int, RegisterValue] = {}
        self.simd: dict[int, tuple[ByteOrigin, ...]] = {}
        self.stack: dict[int, ByteOrigin] = {}
        self.output: dict[int, ByteOrigin] = {}
        self.parameter_reads: set[int] = set()
        self.executed: list[int] = []
        self.sp = Pointer("stack", 0)
        self.gpr[0] = Pointer("parameters", 0)
        self.gpr[1] = tuple(origin("layerIndex", value) for value in range(8))
        self.gpr[2] = tuple(origin("environmentFlags", value) for value in range(8))
        self.gpr[8] = Pointer("output", 0)

    def gpr_read(self, name: str) -> RegisterValue:
        if name == "sp":
            return self.sp
        if name in ("xzr", "wzr"):
            return tuple(constant(0) for _ in range(register_width(name)))
        match = REGISTER.match(name)
        if match is None or match.group(1) not in ("x", "w"):
            raise AnalysisError("invalid general register " + name)
        prefix, raw_index = match.groups()
        value = self.gpr.get(
            int(raw_index),
            tuple(unknown("gpr" + raw_index, offset) for offset in range(8)),
        )
        if prefix == "x":
            return value
        if isinstance(value, Pointer):
            raise AnalysisError("pointer read through " + name)
        return value[:4]

    def gpr_write(self, name: str, value: RegisterValue) -> None:
        if name == "sp":
            if not isinstance(value, Pointer):
                raise AnalysisError("non-pointer stack write")
            self.sp = value
            return
        match = REGISTER.match(name)
        if match is None or match.group(1) not in ("x", "w"):
            raise AnalysisError("invalid general destination " + name)
        prefix, raw_index = match.groups()
        index = int(raw_index)
        if prefix == "x":
            if not isinstance(value, Pointer) and len(value) != 8:
                raise AnalysisError("x-register width differs")
            self.gpr[index] = value
            return
        if isinstance(value, Pointer) or len(value) != 4:
            raise AnalysisError("w-register width differs")
        self.gpr[index] = value + tuple(constant(0) for _ in range(4))

    def simd_read(self, name: str) -> tuple[ByteOrigin, ...]:
        match = REGISTER.match(name)
        if match is None or match.group(1) not in ("q", "d", "s", "h", "b", "v"):
            raise AnalysisError("invalid SIMD register " + name)
        prefix, raw_index = match.groups()
        index = int(raw_index)
        value = self.simd.get(
            index,
            tuple(unknown("simd" + raw_index, offset) for offset in range(16)),
        )
        return value[: register_width(name)]

    def simd_write(self, name: str, value: tuple[ByteOrigin, ...]) -> None:
        match = REGISTER.match(name)
        if match is None or match.group(1) not in ("q", "d", "s", "h", "b", "v"):
            raise AnalysisError("invalid SIMD destination " + name)
        width = register_width(name)
        if len(value) != width:
            raise AnalysisError("SIMD write width differs")
        index = int(match.group(2))
        tail = tuple(
            unknown("simd-tail" + str(index), offset) for offset in range(width, 16)
        )
        self.simd[index] = value + tail

    def register_read(self, name: str) -> RegisterValue:
        if name == "sp" or name.startswith(("x", "w")):
            return self.gpr_read(name)
        return self.simd_read(name)

    def register_write(self, name: str, value: RegisterValue) -> None:
        if name == "sp" or name.startswith(("x", "w")):
            self.gpr_write(name, value)
        else:
            if isinstance(value, Pointer):
                raise AnalysisError("pointer written to SIMD register")
            self.simd_write(name, value)

    def address(self, operand: str) -> Pointer:
        match = MEMORY_OPERAND.match(operand)
        if match is None:
            raise AnalysisError("unsupported memory operand " + operand)
        base_name, displacement = match.groups()
        base = self.gpr_read(base_name)
        if not isinstance(base, Pointer):
            raise AnalysisError("memory base is not a pointer: " + base_name)
        return Pointer(
            base.space,
            base.offset + (parse_immediate(displacement) if displacement else 0),
        )

    def memory_read(self, address: Pointer, width: int) -> tuple[ByteOrigin, ...]:
        if address.space == "parameters":
            self.parameter_reads.update(range(address.offset, address.offset + width))
            return tuple(
                origin("parameters", address.offset + value) for value in range(width)
            )
        if address.space == "stack":
            return tuple(
                self.stack.get(
                    address.offset + value,
                    unknown("stack", address.offset + value),
                )
                for value in range(width)
            )
        if address.space == "output":
            return tuple(
                self.output.get(
                    address.offset + value,
                    unknown("output", address.offset + value),
                )
                for value in range(width)
            )
        raise AnalysisError("unsupported memory space " + address.space)

    def memory_write(
        self,
        address: Pointer,
        value: tuple[ByteOrigin, ...],
    ) -> None:
        if address.space == "stack":
            target = self.stack
        elif address.space == "output":
            target = self.output
        else:
            raise AnalysisError("write escaped stack/output")
        for offset, byte in enumerate(value):
            target[address.offset + offset] = byte

    def execute_load(self, mnemonic: str, operands: list[str]) -> None:
        destination = operands[0]
        width = {
            "ldrb": 1,
            "ldrh": 2,
            "ldurh": 2,
        }.get(mnemonic, register_width(destination))
        address = self.address(operands[1])
        value = self.memory_read(address, width)
        # The absent FaceEffects path reuses its exact Optional tag as the
        # default dodge-fill tag.  The preceding compare proves that byte is 1.
        if (
            address == Pointer("parameters", 0x181)
            and width == 1
            and not self.present["faceEffects"]
        ):
            value = (constant(1),)
        destination_width = register_width(destination)
        if destination_width > width:
            value += tuple(constant(0) for _ in range(destination_width - width))
        self.register_write(destination, value)

    def execute_pair_load(self, operands: list[str]) -> None:
        first, second, memory = operands
        width = register_width(first)
        if register_width(second) != width:
            raise AnalysisError("pair-load width differs")
        address = self.address(memory)
        self.register_write(first, self.memory_read(address, width))
        self.register_write(
            second,
            self.memory_read(Pointer(address.space, address.offset + width), width),
        )

    def execute_store(self, mnemonic: str, operands: list[str]) -> None:
        source = operands[0]
        width = {
            "strb": 1,
            "strh": 2,
            "sturh": 2,
        }.get(mnemonic, register_width(source))
        value = self.register_read(source)
        if isinstance(value, Pointer):
            raise AnalysisError("pointer stored as symbolic bytes")
        self.memory_write(self.address(operands[1]), value[:width])

    def execute_pair_store(self, operands: list[str]) -> None:
        first, second, memory = operands
        first_value = self.register_read(first)
        second_value = self.register_read(second)
        if isinstance(first_value, Pointer) or isinstance(second_value, Pointer):
            raise AnalysisError("pointer pair store is unsupported")
        if len(first_value) != len(second_value):
            raise AnalysisError("pair-store width differs")
        address = self.address(memory)
        self.memory_write(address, first_value)
        self.memory_write(
            Pointer(address.space, address.offset + len(first_value)),
            second_value,
        )

    def execute(self) -> None:
        pc = CONSTRUCTOR_START
        while pc < TERMINAL_WRITE_END:
            if pc in self.executed:
                raise AnalysisError("constructor control flow looped")
            self.executed.append(pc)
            instruction = self.instructions.get(pc)
            if instruction is None:
                raise AnalysisError("instruction missing at {:#x}".format(pc))
            mnemonic = str(instruction["mnemonic"])
            operands = split_operands(str(instruction["operands"]))
            next_pc = pc + 4
            if mnemonic in NO_OP_MNEMONICS:
                pass
            elif mnemonic in ("ldr", "ldur", "ldrb", "ldrh", "ldurh"):
                self.execute_load(mnemonic, operands)
            elif mnemonic == "ldp":
                self.execute_pair_load(operands)
            elif mnemonic in ("str", "stur", "strb", "strh", "sturh"):
                self.execute_store(mnemonic, operands)
            elif mnemonic == "stp":
                self.execute_pair_store(operands)
            elif mnemonic in ("add", "sub"):
                destination, source, immediate = operands
                source_value = self.gpr_read(source)
                if not isinstance(source_value, Pointer):
                    raise AnalysisError("non-pointer add/sub at {:#x}".format(pc))
                delta = parse_immediate(immediate)
                if mnemonic == "sub":
                    delta = -delta
                self.gpr_write(
                    destination,
                    Pointer(source_value.space, source_value.offset + delta),
                )
            elif mnemonic == "mov":
                destination, source = operands
                if source.startswith("#"):
                    width = register_width(destination)
                    immediate = parse_immediate(source)
                    value = tuple(
                        constant((immediate >> (8 * index)) & 0xFF)
                        for index in range(width)
                    )
                    self.register_write(destination, value)
                else:
                    self.register_write(destination, self.register_read(source))
            elif mnemonic.startswith("movi"):
                destination = operands[0]
                self.register_write(
                    destination,
                    tuple(constant(0) for _ in range(register_width(destination))),
                )
            elif mnemonic == "and":
                destination, source, mask_text = operands
                source_value = self.gpr_read(source)
                if isinstance(source_value, Pointer):
                    raise AnalysisError("pointer AND is unsupported")
                mask = parse_immediate(mask_text)
                value = []
                for index, byte in enumerate(source_value):
                    byte_mask = (mask >> (index * 8)) & 0xFF
                    if byte_mask == 0xFF:
                        value.append(byte)
                    elif byte_mask == 0:
                        value.append(constant(0))
                    else:
                        raise AnalysisError("partial-byte AND is unsupported")
                self.gpr_write(destination, tuple(value))
            elif mnemonic == "lsr":
                destination, source, shift_text = operands
                shift = parse_immediate(shift_text)
                if shift % 8:
                    raise AnalysisError("non-byte LSR is unsupported")
                source_value = self.gpr_read(source)
                if isinstance(source_value, Pointer):
                    raise AnalysisError("pointer LSR is unsupported")
                byte_shift = shift // 8
                value = source_value[byte_shift:] + tuple(
                    constant(0) for _ in range(byte_shift)
                )
                self.gpr_write(destination, value)
            elif mnemonic == "bl":
                if pc != 0x24091BD80 or operands != ["0x240917f64"]:
                    raise AnalysisError("unexpected constructor call")
                result = 0 if self.present["shadow"] else 1
                self.gpr_write(
                    "w0",
                    tuple(
                        constant((result >> (8 * index)) & 0xFF) for index in range(4)
                    ),
                )
                self.gpr_write(
                    "x8",
                    tuple(unknown("helper-x8", value) for value in range(8)),
                )
            elif mnemonic == "b":
                next_pc = int(operands[0], 0)
            elif mnemonic in ("b.eq", "b.ne"):
                branch = PRESENT_BRANCHES.get(pc)
                if branch is None:
                    raise AnalysisError("unregistered conditional branch")
                group, taken_when_present, expected_mnemonic, expected_compare = branch
                compare = self.instructions.get(pc - 4)
                if (
                    mnemonic != expected_mnemonic
                    or compare is None
                    or compare.get("mnemonic") != "cmp"
                    or compare.get("operands") != expected_compare
                ):
                    raise AnalysisError("optional branch contract differs")
                take = self.present[group] == taken_when_present
                if take:
                    next_pc = int(operands[0], 0)
            else:
                raise AnalysisError(
                    "unsupported instruction at {:#x}: {} {}".format(
                        pc, mnemonic, str(instruction["operands"])
                    )
                )
            pc = next_pc
        if pc != TERMINAL_WRITE_END:
            raise AnalysisError("constructor execution end differs")


def ranges(values: Sequence[int]) -> list[list[int]]:
    if not values:
        return []
    ordered = sorted(set(values))
    result: list[list[int]] = []
    start = previous = ordered[0]
    for value in ordered[1:]:
        if value != previous + 1:
            result.append([start, previous + 1])
            start = value
        previous = value
    result.append([start, previous + 1])
    return result


def expected_present_output() -> dict[int, ByteOrigin]:
    result: dict[int, ByteOrigin] = {}
    for space, source_start, output_start, byte_count in EXPECTED_PRESENT_TRANSFERS:
        for index in range(byte_count):
            result[output_start + index] = origin(space, source_start + index)
    return result


def validate_present_path(machine: SymbolicMachine) -> None:
    expected = expected_present_output()
    expected_written = {
        offset for start, end in INITIALIZED_RANGES for offset in range(start, end)
    }
    if set(machine.output) != expected_written:
        raise AnalysisError("all-present output write coverage differs")
    if machine.output != expected:
        for offset in sorted(set(machine.output) | set(expected)):
            if machine.output.get(offset) != expected.get(offset):
                raise AnalysisError(
                    "all-present byte origin differs at {:#x}: {} != {}".format(
                        offset,
                        machine.output.get(offset),
                        expected.get(offset),
                    )
                )
        raise AnalysisError("all-present byte origins differ")


def path_record(
    mask: int,
    machine: SymbolicMachine,
) -> Mapping[str, Any]:
    present = [group for index, group in enumerate(GROUPS) if mask & (1 << index)]
    absent = [group for group in GROUPS if group not in present]
    constant_offsets = [
        offset
        for offset, value in machine.output.items()
        if value.startswith("constant:")
    ]
    indeterminate_offsets = [
        offset
        for offset, value in machine.output.items()
        if value.startswith("unknown:")
    ]
    parameter_offsets = [
        offset
        for offset, value in machine.output.items()
        if value.startswith("parameters:")
    ]
    return {
        "pathMask": mask,
        "presentGroups": present,
        "absentGroups": absent,
        "executedInstructionCount": len(machine.executed),
        "parameterReadRanges": ranges(sorted(machine.parameter_reads)),
        "parameterOriginOutputRanges": ranges(parameter_offsets),
        "constantOutputRanges": ranges(constant_offsets),
        "indeterminateOutputRanges": ranges(indeterminate_offsets),
    }


def validate_helper(
    code_output: str,
    disassembly_output: str,
) -> Mapping[str, Any]:
    code = coverage.parse_code_bytes(
        code_output,
        SHADOW_OPTIONAL_HELPER_START,
        SHADOW_OPTIONAL_HELPER_END,
    )
    digest = hashlib.sha256(code).hexdigest()
    if digest != SHADOW_OPTIONAL_HELPER_SHA256:
        raise AnalysisError("shadow optional helper SHA-256 differs")
    instructions = coverage.parse_instructions(
        disassembly_output,
        SHADOW_OPTIONAL_HELPER_START,
        SHADOW_OPTIONAL_HELPER_END,
    )
    normalized = [
        (str(value["mnemonic"]), str(value["operands"])) for value in instructions
    ]
    expected = [
        ("ldrb", "w8, [x0, #0x90]"),
        ("cbz", "w8, 0x240917f78"),
        ("ldr", "w8, [x0]"),
        ("add", "w0, w8, #0x1"),
        ("ret", ""),
        ("mov", "w0, #0x0"),
        ("ret", ""),
    ]
    if normalized != expected:
        raise AnalysisError("shadow optional helper semantics differ")
    return {
        "start": "0x{:x}".format(SHADOW_OPTIONAL_HELPER_START),
        "endExclusive": "0x{:x}".format(SHADOW_OPTIONAL_HELPER_END),
        "byteCount": len(code),
        "instructionCount": len(instructions),
        "sha256": digest,
        "law": (
            "return 0 when the copied Shadow optional tag byte at +0x90 "
            "is zero; otherwise return uint32_at_0 + 1"
        ),
    }


def analyze(source_path: Path) -> Mapping[str, Any]:
    identity = coverage.native_identity()
    code_output = coverage.run(("-section_bytes", "__TEXT", "__text"))
    disassembly_output = coverage.run(("-disassemble",))
    constructor_code = coverage.parse_code_bytes(
        code_output, CONSTRUCTOR_START, CONSTRUCTOR_END
    )
    if hashlib.sha256(constructor_code).hexdigest() != CONSTRUCTOR_SHA256:
        raise AnalysisError("BackgroundFilter constructor SHA-256 differs")
    instructions = coverage.parse_instructions(
        disassembly_output, CONSTRUCTOR_START, CONSTRUCTOR_END
    )
    helper = validate_helper(code_output, disassembly_output)

    paths = []
    path_machines: dict[int, SymbolicMachine] = {}
    all_present_machine: Optional[SymbolicMachine] = None
    for mask in range(1 << len(GROUPS)):
        present = {
            group: bool(mask & (1 << index)) for index, group in enumerate(GROUPS)
        }
        machine = SymbolicMachine(instructions, present)
        machine.execute()
        expected_written = {
            offset for start, end in INITIALIZED_RANGES for offset in range(start, end)
        }
        if set(machine.output) != expected_written:
            raise AnalysisError("output write coverage differs on path {}".format(mask))
        paths.append(path_record(mask, machine))
        path_machines[mask] = machine
        if mask == (1 << len(GROUPS)) - 1:
            all_present_machine = machine
    if all_present_machine is None:
        raise AnalysisError("all-present path was not executed")
    validate_present_path(all_present_machine)

    path_matrix_payload = json.dumps(
        paths,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    all_present_mask = (1 << len(GROUPS)) - 1
    single_absent_paths = [
        paths[all_present_mask ^ (1 << index)] for index in range(len(GROUPS))
    ]
    indeterminate_offsets = sorted(
        {
            offset
            for machine in path_machines.values()
            for offset, value in machine.output.items()
            if value.startswith("unknown:")
        }
    )
    if ranges(indeterminate_offsets) != [
        list(value) for value in EXPECTED_NIL_INDETERMINATE_RANGES
    ]:
        raise AnalysisError("nil-path indeterminate byte ranges differ")
    unknown_kinds = sorted(
        {
            ":".join(value.split(":")[:2])
            for machine in path_machines.values()
            for value in machine.output.values()
            if value.startswith("unknown:")
        }
    )
    if unknown_kinds != ["unknown:gpr11", "unknown:stack"]:
        raise AnalysisError("nil-path indeterminate origin kinds differ")

    source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
    return {
        "designLibraryBackgroundFilterConstructorSemanticsAnalysisSchemaVersion": (
            RESULT_SCHEMA_VERSION
        ),
        "classification": (
            "native static symbolic byte-origin proof over every one of the "
            "64 optional-presence paths; no Apple application launch, render, "
            "image, pixel, or captured runtime value"
        ),
        "host": identity,
        "constructor": {
            "start": "0x{:x}".format(CONSTRUCTOR_START),
            "endExclusive": "0x{:x}".format(CONSTRUCTOR_END),
            "byteCount": len(constructor_code),
            "instructionCount": len(instructions),
            "sha256": CONSTRUCTOR_SHA256,
        },
        "shadowOptionalHelper": helper,
        "optionalBranchContracts": [
            {
                "branchAddress": "0x{:x}".format(address),
                "group": group,
                "takenWhenPresent": taken_when_present,
                "branchMnemonic": mnemonic,
                "precedingCompare": compare,
            }
            for address, (
                group,
                taken_when_present,
                mnemonic,
                compare,
            ) in PRESENT_BRANCHES.items()
        ],
        "allPresentPath": {
            "pathMask": all_present_mask,
            "groups": list(GROUPS),
            "executedInstructionCount": len(all_present_machine.executed),
            "writtenByteCount": len(all_present_machine.output),
            "writtenRanges": [list(value) for value in INITIALIZED_RANGES],
            "unwrittenPaddingRanges": [list(value) for value in PADDING_RANGES],
            "transfers": [
                {
                    "source": source,
                    "sourceStart": source_start,
                    "outputStart": output_start,
                    "byteCount": byte_count,
                }
                for source, source_start, output_start, byte_count in EXPECTED_PRESENT_TRANSFERS
            ],
            "parameterReadRanges": ranges(sorted(all_present_machine.parameter_reads)),
            "all491WrittenByteOriginsProvedExactly": True,
            "arithmeticAppliedToPresentPayloadBytes": False,
        },
        "optionalPresenceProof": {
            "pathCount": len(paths),
            "pathMatrixSHA256": hashlib.sha256(path_matrix_payload).hexdigest(),
            "allPathsPreserveExact491ByteWriteCoverage": True,
            "executedInstructionCountRange": [
                min(value["executedInstructionCount"] for value in paths),
                max(value["executedInstructionCount"] for value in paths),
            ],
            "indeterminateOutputRangesAcrossAnyNilPath": ranges(indeterminate_offsets),
            "indeterminateNestedPaddingByteCountAcrossAnyNilPath": len(
                indeterminate_offsets
            ),
            "indeterminateOriginKinds": unknown_kinds,
            "allAbsentPath": paths[0],
            "singleAbsentPaths": single_absent_paths,
        },
        "claims": {
            "optionalPresencePathCount": len(paths),
            "allOptionalPresencePathsExecutedSymbolically": len(paths) == 64,
            "nilPathIndeterminateNestedPaddingByteCount": len(indeterminate_offsets),
            "presentShadowBytesCopiedExactly": True,
            "presentBlurBytesCopiedExactly": True,
            "presentRefractionBytesCopiedExactly": True,
            "presentFaceEffectsBytesCopiedExactly": True,
            "presentEdgeBleedBytesCopiedExactly": True,
            "presentSDRAdjustmentSemanticBytesCopiedExactly": True,
            "layerIndexCopiedExactly": True,
            "environmentFlagsCopiedExactly": True,
            "constructorPerformsCrossFieldOpticalArithmetic": False,
            "publicParametersConstructionLawEstablished": False,
            "upstreamCropAllocationPolicyEstablished": False,
            "independentWalleZeroByteFrameParityEstablished": False,
            "liquidGlassParityEstablished": False,
            "productionShaderChangeAuthorized": False,
        },
        "tool": {
            "dyldInfo": str(coverage.DYLD_INFO),
            "python": platform.python_version(),
            "source": (
                "Analysis/"
                "analyze_designlibrary_background_filter_constructor_semantics_"
                "local_macos_26_6_1.py"
            ),
            "sourceSHA256": source_sha256,
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
