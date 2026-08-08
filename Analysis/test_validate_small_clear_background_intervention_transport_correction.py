#!/usr/bin/env python3
"""Tests for the Tghn sample-2 transport-correction validator."""

import unittest

import validate_small_clear_background_intervention_transport_correction as subject


def missing_branch_record(
    *,
    executed: bool = False,
    reason: str = "captured small-clear Tghn render pass unavailable",
    trace: object | None = None,
) -> dict[str, object]:
    replay: dict[str, object] = {
        "executed": executed,
        "reason": reason,
        "capturedPassCount": 2,
    }
    if trace is not None:
        replay["smallClearBackgroundIntervention"] = trace
    return {"render": {"exactPassReplay": replay}}


class SmallClearBackgroundTransportCorrectionTests(unittest.TestCase):
    def test_preregistered_no_pipeline_candidate_is_ineligible(self) -> None:
        subject.validate_missing_branch_replay(missing_branch_record(), 2)

    def test_missing_branch_cannot_execute_an_unrelated_pass(self) -> None:
        with self.assertRaisesRegex(ValueError, "replay executed"):
            subject.validate_missing_branch_replay(
                missing_branch_record(executed=True), 2
            )

    def test_missing_branch_reason_is_exact(self) -> None:
        with self.assertRaisesRegex(ValueError, "reason differs"):
            subject.validate_missing_branch_replay(
                missing_branch_record(reason="captured glass render pass unavailable"),
                2,
            )

    def test_missing_branch_cannot_contain_an_intervention(self) -> None:
        with self.assertRaisesRegex(ValueError, "unexpectedly contains"):
            subject.validate_missing_branch_replay(
                missing_branch_record(trace={"executed": True}), 2
            )

    def test_missing_branch_pass_count_must_be_nonnegative_integer(self) -> None:
        record = missing_branch_record()
        record["render"]["exactPassReplay"]["capturedPassCount"] = -1  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "pass count"):
            subject.validate_missing_branch_replay(record, 2)


if __name__ == "__main__":
    unittest.main()
