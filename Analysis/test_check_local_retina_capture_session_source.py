#!/usr/bin/env python3
"""Static checks for the native presentation-session preflight."""

from __future__ import annotations

import unittest
from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parent / "check_local_retina_capture_session.swift"
).read_text(encoding="utf-8")


class LocalRetinaCaptureSessionSourceTests(unittest.TestCase):
    def test_fails_closed_on_lock_or_sleep(self) -> None:
        self.assertIn('"CGSSessionScreenIsLocked"', SOURCE)
        self.assertIn("CGDisplayIsAsleep(displayID)", SOURCE)
        self.assertIn("!sessionLocked", SOURCE)
        self.assertIn("!displayAsleep", SOURCE)
        self.assertIn("exit(passed ? 0 : 1)", SOURCE)

    def test_freezes_the_exact_retina_host(self) -> None:
        self.assertIn("[3456, 2234]", SOURCE)
        self.assertIn("[1728, 1117]", SOURCE)
        self.assertIn("expectedBackingScale = 2.0", SOURCE)
        self.assertIn("CGMainDisplayID()", SOURCE)

    def test_emits_machine_readable_json(self) -> None:
        self.assertIn("JSONSerialization.data", SOURCE)
        self.assertIn(".sortedKeys", SOURCE)
        self.assertIn('"passed": passed', SOURCE)


if __name__ == "__main__":
    unittest.main()
