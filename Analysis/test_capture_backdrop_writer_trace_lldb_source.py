#!/usr/bin/env python3
"""Portable source-level tests for the LLDB callback module."""

import importlib.util
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


class CaptureBackdropWriterTraceLLDBSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_with_stub_lldb()

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
        self.assertEqual(self.module.CAPTURE_BACKDROP_CODE_BYTE_COUNT, 0x4000)
        self.assertEqual(self.module.CAPTURE_BACKDROP_LATE_OFFSET, 0x2B58)
        self.assertEqual(self.module.WATCHPOINT_BYTE_COUNT, 8)
        self.assertEqual(self.module.MAXIMUM_HITS_PER_WATCHPOINT, 6)
        self.assertEqual(self.module.MAXIMUM_TOTAL_HITS, 24)
        self.assertEqual(len(self.module.WATCH_SPECS), 4)


if __name__ == "__main__":
    unittest.main()
