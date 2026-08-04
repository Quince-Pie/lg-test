#!/usr/bin/env python3
"""Portable source-level tests for the LLDB callback module."""

import importlib.util
import inspect
import sys
import types
import unittest
from pathlib import Path


ANALYSIS_ROOT = Path(__file__).resolve().parent
MODULE_PATH = ANALYSIS_ROOT / "capture_backdrop_writer_trace_lldb.py"


def load_with_stub_lldb():
    module_name = "capture_backdrop_writer_trace_lldb_source_test"
    specification = importlib.util.spec_from_file_location(module_name, MODULE_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError("LLDB trace module spec is unavailable")
    module = importlib.util.module_from_spec(specification)
    previous = sys.modules.get("lldb")
    sys.modules["lldb"] = types.ModuleType("lldb")
    try:
        specification.loader.exec_module(module)
    finally:
        if previous is None:
            del sys.modules["lldb"]
        else:
            sys.modules["lldb"] = previous
    return module


class FileSpec:
    def __init__(self, directory, filename):
        self.directory = directory
        self.filename = filename

    def GetDirectory(self):
        return self.directory

    def GetFilename(self):
        return self.filename

    def GetPath(self, _destination, _length):
        raise AssertionError("Apple's two-argument GetPath must not be called")


class Error:
    def Success(self):
        return True

    def GetCString(self):
        return None


class RegisterData:
    def __init__(self, payload):
        self.payload = payload

    def IsValid(self):
        return True

    def GetByteSize(self):
        return len(self.payload)

    def GetUnsignedInt8(self, _error, offset):
        return self.payload[offset]


class Register:
    def __init__(self, payload):
        self.payload = payload

    def IsValid(self):
        return True

    def GetByteSize(self):
        return len(self.payload)

    def GetData(self):
        return RegisterData(self.payload)

    def GetValue(self):
        return "0x" + self.payload[::-1].hex()

    def GetValueAsUnsigned(self, _fallback):
        return int.from_bytes(self.payload, "little")


class RegisterFrame:
    def __init__(self, registers):
        self.registers = registers

    def FindRegister(self, name):
        return self.registers[name]


class CaptureBackdropWriterTraceLLDBSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_with_stub_lldb()
        cls.module.lldb.SBError = Error

    def test_file_spec_path_uses_portable_directory_and_filename_accessors(self):
        self.assertEqual(
            self.module._file_spec_path(
                FileSpec(
                    "/System/Library/Frameworks/QuartzCore.framework/Versions/A",
                    "QuartzCore",
                )
            ),
            "/System/Library/Frameworks/QuartzCore.framework/Versions/A/QuartzCore",
        )

    def test_file_spec_path_handles_partial_and_empty_specs(self):
        self.assertEqual(
            self.module._file_spec_path(FileSpec(None, "QuartzCore")),
            "QuartzCore",
        )
        self.assertEqual(
            self.module._file_spec_path(FileSpec("/System/Library", None)),
            "/System/Library",
        )
        self.assertEqual(self.module._file_spec_path(FileSpec(None, None)), "")

    def test_harness_keeps_the_exact_trace_bounds(self):
        self.assertEqual(self.module.TRACE_SCHEMA_VERSION, 4)
        self.assertEqual(self.module.CAPTURE_BACKDROP_CODE_BYTE_COUNT, 0x4000)
        self.assertEqual(self.module.CAPTURE_BACKDROP_LATE_OFFSET, 0x2B58)
        self.assertEqual(self.module.WATCHPOINT_BYTE_COUNT, 8)
        self.assertEqual(self.module.MAXIMUM_HITS_PER_WATCHPOINT, 6)
        self.assertEqual(self.module.MAXIMUM_TOTAL_HITS, 24)
        self.assertEqual(self.module.MAXIMUM_LATE_CANDIDATE_COUNT, 512)
        self.assertEqual(self.module.MAXIMUM_LATE_CANDIDATE_DIAGNOSTIC_COUNT, 16)
        self.assertEqual(self.module.PC_CENTERED_CODE_WINDOW_BYTE_COUNT, 0x1000)
        self.assertEqual(self.module.PC_CENTERED_CODE_WINDOW_BACKTRACK, 0x800)
        self.assertEqual(self.module.STACK_SNAPSHOT_BYTE_COUNT, 0x800)
        self.assertEqual(self.module.REGISTER_POINTER_SNAPSHOT_BYTE_COUNT, 0x100)
        self.assertEqual(self.module.REGISTER_POINTER_SNAPSHOT_BACKTRACK, 0x40)
        self.assertEqual(len(self.module.GENERAL_REGISTER_NAMES), 34)
        self.assertEqual(len(self.module.SIMD_REGISTER_NAMES), 34)
        self.assertEqual(len(self.module.WATCH_SPECS), 4)

    def test_watchpoint_callback_accepts_apple_lldbs_three_arguments(self):
        self.assertEqual(
            list(inspect.signature(self.module.capture_writer_watchpoint).parameters),
            ["frame", "watchpoint", "_internal_dict"],
        )

    def test_register_record_preserves_exact_sbdata_bytes(self):
        payload = bytes(range(16))
        record = self.module._register_record(
            RegisterFrame({"v0": Register(payload)}), "v0"
        )
        self.assertEqual(record["name"], "v0")
        self.assertEqual(record["byteCount"], 16)
        self.assertEqual(record["hex"], payload.hex())
        self.assertNotIn("unsignedValue", record)


if __name__ == "__main__":
    unittest.main()
