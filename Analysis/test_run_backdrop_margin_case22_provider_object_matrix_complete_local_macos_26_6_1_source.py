#!/usr/bin/env python3
"""Source contracts for the native unlocked provider-matrix runner."""

from __future__ import annotations

import json
import os
import re
import subprocess
import unittest
from pathlib import Path


ANALYSIS = Path(__file__).resolve().parent
RUNNER = (
    ANALYSIS
    / "run_backdrop_margin_case22_provider_object_matrix_complete_local_macos_26_6_1.sh"
)
SOURCE = RUNNER.read_text(encoding="utf-8")
PREREGISTRATION = json.loads(
    (
        ANALYSIS
        / "backdrop_margin_case22_provider_object_matrix_complete_local_macos_26_6_1_preregistration.json"
    ).read_text(encoding="utf-8")
)


class CompleteProviderObjectMatrixNativeRunnerSourceTests(unittest.TestCase):
    def test_bash_source_is_valid_and_executable(self) -> None:
        subprocess.run(["bash", "-n", RUNNER], check=True)
        self.assertTrue(os.access(RUNNER, os.X_OK))

    def test_uses_native_command_line_tools_without_a_store_path(self) -> None:
        self.assertIn("swift=/Library/Developer/CommandLineTools/usr/bin/swift", SOURCE)
        self.assertIn("lldb=/Library/Developer/CommandLineTools/usr/bin/lldb", SOURCE)
        self.assertIn(
            "python=/Library/Developer/CommandLineTools/usr/bin/python3",
            SOURCE,
        )
        self.assertNotIn("/nix/store/", SOURCE)
        self.assertNotIn("nix develop", SOURCE)

    def test_exact_profile_is_complete_and_matches_preregistration(self) -> None:
        match = re.search(
            r"readonly -a common_environment=\(\n(?P<body>.*?)\n\)",
            SOURCE,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        environment = dict(
            line.strip().split("=", 1) for line in match.group("body").splitlines()
        )
        self.assertEqual(environment, PREREGISTRATION["profile"])

    def test_preflight_precedes_each_native_lldb_stage(self) -> None:
        selected_preflight = SOURCE.index('run_preflight "$selected_directory"')
        selected_lldb = SOURCE.index(
            'LG_BACKDROP_MARGIN_WRITER_TRACE_OUTPUT="$selected_trace"'
        )
        complete_preflight = SOURCE.index('run_preflight "$complete_directory"')
        complete_lldb = SOURCE.index(
            'LG_CASE22_PROVIDER_OBJECT_MATRIX_MINIMAL_TRACE_OUTPUT="$complete_trace"'
        )
        self.assertLess(selected_preflight, selected_lldb)
        self.assertLess(selected_lldb, complete_preflight)
        self.assertLess(complete_preflight, complete_lldb)

    def test_second_stage_does_not_branch_on_the_first_observed_value(self) -> None:
        selected_status = SOURCE.index("selected_status=$?")
        complete_preflight = SOURCE.index('run_preflight "$complete_directory"')
        complete_status = SOURCE.index("complete_status=$?")
        between = SOURCE[selected_status:complete_status]
        self.assertLess(selected_status, complete_preflight)
        self.assertNotIn('[[ "$selected_status"', between)
        self.assertNotIn("returnF64", between)
        self.assertNotIn("providerEntryObject", between)

    def test_validator_runs_after_both_stages_and_records_its_status(self) -> None:
        selected_status = SOURCE.index("selected_status=$?")
        complete_status = SOURCE.index("complete_status=$?")
        validator_call = SOURCE.index('"$python" "$validator"')
        status_write = SOURCE.index('>"$validation_status_file"')
        self.assertLess(selected_status, complete_status)
        self.assertLess(complete_status, validator_call)
        self.assertLess(validator_call, status_write)
        self.assertIn('--selected-artifact-directory "$selected_directory"', SOURCE)
        self.assertIn('--complete-artifact-directory "$complete_directory"', SOURCE)
        self.assertIn('--output "$validation_output"', SOURCE)
        self.assertNotIn("captureContractPassed", SOURCE)

    def test_frozen_hashes_and_clean_output_guards_are_present(self) -> None:
        for digest in (
            PREREGISTRATION["binary"]["sha256"],
            PREREGISTRATION["completeCapture"]["sha256"],
            PREREGISTRATION["nativeSessionPreflight"]["sha256"],
            PREREGISTRATION["prospectiveValidator"]["sha256"],
        ):
            self.assertIn(digest, SOURCE)
        self.assertIn("git status --porcelain --untracked-files=no", SOURCE)
        self.assertIn(
            '[[ -e "$selected_directory" || -e "$complete_directory" ]]',
            SOURCE,
        )


if __name__ == "__main__":
    unittest.main()
