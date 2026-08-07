#!/usr/bin/env python3
"""Static contracts for the corrected native presentation-session preflight."""

from __future__ import annotations

import unittest
from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parent / "check_local_retina_capture_session_v2.swift"
).read_text(encoding="utf-8")


class LocalRetinaCaptureSessionV2SourceTests(unittest.TestCase):
    def test_absent_lock_key_is_the_unlocked_encoding(self) -> None:
        self.assertIn('private let lockKey = "CGSSessionScreenIsLocked"', SOURCE)
        self.assertIn("sessionLockedValue ?? sessionLockFieldPresent", SOURCE)
        self.assertIn("sessionLockFieldValid", SOURCE)

    def test_empty_malformed_locked_or_logged_out_sessions_fail(self) -> None:
        for condition in (
            "!session.isEmpty",
            "sessionLockFieldValid",
            "!sessionLocked",
            "sessionOnConsole",
            "sessionLoginDone",
            "!displayAsleep",
        ):
            self.assertIn(condition, SOURCE)
        self.assertIn("exit(passed ? 0 : 1)", SOURCE)

    def test_freezes_the_exact_retina_host(self) -> None:
        self.assertIn("[3456, 2234]", SOURCE)
        self.assertIn("[1728, 1117]", SOURCE)
        self.assertIn("expectedBackingScale = 2.0", SOURCE)
        self.assertIn("CGMainDisplayID()", SOURCE)

    def test_emits_auditable_machine_readable_state(self) -> None:
        for field in (
            '"sessionDictionaryAvailable"',
            '"sessionLockFieldPresent"',
            '"sessionLockFieldValid"',
            '"sessionLoginDone"',
            '"passed"',
        ):
            self.assertIn(field, SOURCE)
        self.assertIn("JSONSerialization.data", SOURCE)
        self.assertIn(".sortedKeys", SOURCE)


if __name__ == "__main__":
    unittest.main()
