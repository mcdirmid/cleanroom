"""
Tests for the RunControlImpl implementation.

Written from the LLS (specs/low/run_control_impl.md, specs/low/run_control.md,
specs/low/tool_provider.md, specs/low/dag_clean_logic.md,
specs/low/dag_storage.md, specs/low/file_view.md, specs/low/guide_delivery.md):
verification callback invocation and failing feedback, diff computation,
the change-message soft/hard bounds and grace counters, the feedback-pending
gate, blame target resolution to owning nodes, and fail.

The API returns a ToolCallOutcome per tool call: a sequence of one or more
results (ToolResult or PresentedToolResult values) or a Signal (ToolFailure,
TerminateAgentWithSuccess, TerminateAgentWithFailure). Verification results
set the supersession flag; termination results never do (termination tools
produce no ToolResult). The change-message requirement applies only to the
terminating advance; the feedback-pending gate is checked only when advance
would otherwise signal successful termination without a change.
"""

import os
import shutil
import tempfile
import unittest
from typing import Any, Dict, List, Optional, Tuple

from update_with_ai.lib.run_control import RunControlConfig
from update_with_ai.lib.run_control_impl import RunControlImpl
from update_with_ai.lib.file_view import FileViewConfig
from update_with_ai.lib.file_view_impl import FileViewImpl
from update_with_ai.lib.guide_delivery import GuideDeliveryConfig
from update_with_ai.lib.guide_delivery_impl import GuideDeliveryImpl
from update_with_ai.lib.tool_provider import (
    PresentedToolResult,
    ToolResult,
    ToolFailure,
    TerminateAgentWithSuccess,
    TerminateAgentWithFailure,
)
from update_with_ai.lib.dag_clean_logic import ChangeResult, FeedbackResult, NoChangeResult
from update_with_ai.lib.dag_storage import NodeMessage

GUIDE = (
    "# Guide: Converting\n\n"
    "## Summary\n\n"
    "The artifact conforms to this guide.\n\n"
    "## Checklist: Imports\n\n"
    "- [ ] Imports come from the closure\n\n"
    "## Checklist: Contracts\n\n"
    "- [ ] Signatures match the LLS\n"
)


class TestRunControlImpl(unittest.TestCase):
    """Main coverage: verification, diff computation, the change-message
    machinery, the feedback-pending gate, blame, and fail."""

    def setUp(self) -> None:
        """Set up a temp workspace with a writable file, a read-only file,
        and a mapped-but-missing writable target."""
        self.temp_dir = tempfile.mkdtemp()

        self.test_file_path = os.path.join(self.temp_dir, "test.txt")
        with open(self.test_file_path, "w", encoding="utf-8") as f:
            f.write("Line 1: Hello World\n")
            f.write("Line 2: This is a test\n")
            f.write("Line 3: Another line\n")
            f.write("Line 4: Final line\n")

        self.second_path = os.path.join(self.temp_dir, "second.txt")
        with open(self.second_path, "w", encoding="utf-8") as f:
            f.write("Second line one\n")
            f.write("Second line two\n")

        self.ro_path = os.path.join(self.temp_dir, "ro.txt")
        with open(self.ro_path, "w", encoding="utf-8") as f:
            f.write("Read only line 1\n")

        self.new_file_path = os.path.join(self.temp_dir, "new.txt")

        self.file_mappings = {
            "test.txt": self.test_file_path,
            "second.txt": self.second_path,
            "ro.txt": self.ro_path,
            "new.txt": self.new_file_path,
        }
        self.readable_paths = ["test.txt", "second.txt", "ro.txt", "new.txt"]
        self.writable_paths = ["test.txt", "second.txt", "new.txt"]
        self.blame_targets = {"agent": "//pkg:agent", "system": "//pkg:system"}

        self.guide_path = os.path.join(self.temp_dir, "guide.md")
        with open(self.guide_path, "w", encoding="utf-8") as f:
            f.write(GUIDE)

    def _run_control(
        self,
        verification_callback: Optional[Any] = None,
        feedback_pending: bool = False,
        blame_targets: Optional[Dict[str, str]] = None,
        diff_size_limit: int = 1000,
        step_sections: bool = False,
        guide: Optional[str] = None,
    ) -> RunControlImpl:
        """Construct a RunControlImpl with the fixture components: a real
        FileViewImpl (the changed-file and diff information the termination
        rules read) and a real GuideDeliveryImpl (the step-state gating the
        advance rules consult)."""
        file_view = FileViewImpl(FileViewConfig(
            file_mappings=self.file_mappings,
            readable_paths=self.readable_paths,
            writable_paths=self.writable_paths,
            templates={},
            search_result_limit=5,
            session_start_reads_enabled=True,
        ))
        guide_real = self.guide_path if guide == "guide.md" else guide
        guide_delivery = GuideDeliveryImpl(GuideDeliveryConfig(
            guide=guide_real,
            step_sections_enabled=step_sections,
        ))
        return RunControlImpl(
            RunControlConfig(
                verification_callback=verification_callback,
                feedback_pending=feedback_pending,
                blame_targets=blame_targets if blame_targets is not None else self.blame_targets,
                diff_size_limit=diff_size_limit,
            ),
            file_view=file_view,
            guide_delivery=guide_delivery,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir)

    # ------------------------------------------------------------------
    # Outcome narrowing helpers
    # ------------------------------------------------------------------

    def as_tool_result(self, outcome: Any) -> ToolResult:
        if isinstance(outcome, list):
            assert len(outcome) >= 1, f"Expected a result sequence, got {outcome!r}"
            outcome = outcome[0]
        assert isinstance(outcome, ToolResult), f"Expected ToolResult, got {outcome!r}"
        return outcome

    def as_tool_failure(self, outcome: Any) -> ToolFailure:
        assert isinstance(outcome, ToolFailure), f"Expected ToolFailure, got {outcome!r}"
        return outcome

    def as_success(self, outcome: Any) -> TerminateAgentWithSuccess:
        assert isinstance(outcome, TerminateAgentWithSuccess), (
            f"Expected TerminateAgentWithSuccess, got {outcome!r}"
        )
        return outcome

    def as_terminate_failure(self, outcome: Any) -> TerminateAgentWithFailure[Any]:
        assert isinstance(outcome, TerminateAgentWithFailure), (
            f"Expected TerminateAgentWithFailure, got {outcome!r}"
        )
        return outcome

    def assert_supersedes(self, outcome: Any, supersedes: bool) -> ToolResult:
        result = self.as_tool_result(outcome)
        assert result.supersedes is supersedes, (
            f"Expected supersedes={supersedes}, got {result!r}"
        )
        return result

    def _edit(self, control: RunControlImpl, old: str = "This is a test",
              new: str = "New content") -> None:
        self.assert_supersedes(
            control.file_view.edit_file("test.txt", old, new), True
        )

    # ------------------------------------------------------------------
    # get_tool_definitions
    # ------------------------------------------------------------------

    def test_get_tool_definitions_fail_always_blame_conditional(self) -> None:
        # The failure tool is always provided; the blame tool only when blame
        # targets are configured.
        names = [d["function"]["name"] for d in self._run_control().get_tool_definitions()]
        self.assertIn("fail", names)
        self.assertIn("blame", names)
        no_targets = [d["function"]["name"] for d in self._run_control(
            blame_targets={}
        ).get_tool_definitions()]
        self.assertIn("fail", no_targets)
        self.assertNotIn("blame", no_targets)

    # ------------------------------------------------------------------
    # advance: verification
    # ------------------------------------------------------------------

    def test_advance_no_callback_no_changes_terminates_no_change(self) -> None:
        # No callback, no writes: verification is treated as passed and the
        # run signals successful termination with no change.
        result = self.as_success(self._run_control().advance())
        self.assertEqual(result.value.type, "no_change")

    def test_verification_callback_invoked_on_advance(self) -> None:
        # The injected verification callback is invoked by advance when
        # configured; a passing verification proceeds to termination.
        called: List[bool] = []

        def callback() -> Tuple[bool, str]:
            called.append(True)
            return (True, "ok")

        result = self.as_success(self._run_control(verification_callback=callback).advance())
        self.assertEqual(called, [True])
        self.assertEqual(result.value.type, "no_change")

    def test_advance_callback_failing_provides_feedback_never_failure(self) -> None:
        # A failing verification provides feedback — a ToolResult with the
        # failure details and guidance, supersedes set, note pinned to
        # "Verification failed." — never a tool failure and never termination.
        def callback() -> Tuple[bool, str]:
            return (False, "lint errors found")

        result = self.assert_supersedes(
            self._run_control(verification_callback=callback).advance(), True
        )
        self.assertIn("lint errors found", result.content)
        self.assertIn("Verification failed", result.content)
        self.assertIn("advance() again", result.content)
        self.assertIn("blame() or fail()", result.content)
        self.assertEqual(result.note, "Verification failed.")

    def test_advance_callback_failing_feedback_has_no_diff(self) -> None:
        # A failing verification's feedback does not include the run's diff.
        def callback() -> Tuple[bool, str]:
            return (False, "bad")

        control = self._run_control(verification_callback=callback)
        self._edit(control)
        result = self.assert_supersedes(control.advance(), True)
        self.assertNotIn("### diff", result.content)

    def test_advance_callback_failing_session_continues(self) -> None:
        # A failing verification never terminates the run: a second advance
        # also returns feedback.
        def callback() -> Tuple[bool, str]:
            return (False, "bad")

        control = self._run_control(verification_callback=callback)
        self.assert_supersedes(control.advance(), True)
        self.assert_supersedes(control.advance(), True)

    def test_advance_callback_exception_tool_failure(self) -> None:
        # A verification-callback exception is reported as a ToolFailure with
        # text starting "Verification error: " (pinned; tests may assert it).
        def callback() -> Tuple[bool, str]:
            raise RuntimeError("callback blew up")

        failure = self.as_tool_failure(
            self._run_control(verification_callback=callback).advance()
        )
        self.assertTrue(failure.value.startswith("Verification error: "))

    # ------------------------------------------------------------------
    # advance: diff computation
    # ------------------------------------------------------------------

    def test_advance_changed_files_empty_message_shows_diff(self) -> None:
        # Files changed and the change message is empty: a tool failure that
        # lists the changed files and shows the run's diff (the diff is shown
        # only in this case), instructing the agent to call advance again
        # with one {file, summary} entry per changed file.
        control = self._run_control()
        self._edit(control)
        failure = self.as_tool_failure(control.advance())
        self.assertIn("test.txt", failure.value)
        self.assertIn("### diff for test.txt", failure.value)
        self.assertIn("-Line 2: This is a test", failure.value)
        self.assertIn("+Line 2: New content", failure.value)
        self.assertIn("advance(changes=", failure.value)

    def test_advance_diff_truncated_when_exceeds_diff_size_limit(self) -> None:
        # The verification diff is truncated when it exceeds the diff size
        # limit, reporting the truncated size and the full change counts; the
        # truncation footer is pinned.
        control = self._run_control(diff_size_limit=40)
        self._edit(control)
        failure = self.as_tool_failure(control.advance())
        self.assertIn("diff truncated", failure.value)
        self.assertIn("showing 40 of", failure.value)

    # ------------------------------------------------------------------
    # advance: the change-message machinery
    # ------------------------------------------------------------------

    def test_advance_change_message_success_forms_change_result(self) -> None:
        # On a passing verification with changed files and a valid change
        # message, advance signals successful termination carrying a
        # ChangeResult whose messages are built from the changes: one
        # NodeMessage of kind "change" per entry.
        control = self._run_control()
        self._edit(control)
        result = self.as_success(control.advance(
            changes=[{"file": "test.txt", "summary": "Updated the test line"}]
        ))
        self.assertIsInstance(result.value, ChangeResult)
        assert isinstance(result.value, ChangeResult)
        self.assertEqual(
            result.value.messages,
            [NodeMessage(kind="change", text="test.txt: Updated the test line")],
        )

    def test_advance_missing_file_or_summary_fails(self) -> None:
        # An entry with a missing/empty file or summary is rejected requiring
        # both fields.
        control = self._run_control()
        self._edit(control)
        no_file = self.as_tool_failure(control.advance(
            changes=[{"file": "", "summary": "changed"}]
        ))
        self.assertIn("non-empty 'file'", no_file.value)
        no_summary = self.as_tool_failure(control.advance(
            changes=[{"file": "test.txt", "summary": ""}]
        ))
        self.assertIn("non-empty one-sentence 'summary'", no_summary.value)

    def test_advance_unknown_file_in_changes_fails(self) -> None:
        # An entry naming a file the run did not change is rejected, naming
        # the changed files.
        control = self._run_control()
        self._edit(control)
        failure = self.as_tool_failure(control.advance(
            changes=[{"file": "nope.txt", "summary": "changed"}]
        ))
        self.assertIn("nope.txt", failure.value)
        self.assertIn("test.txt", failure.value)

    def test_advance_uncovered_changed_file_fails(self) -> None:
        # Two files changed, the change message covers only one: the failure
        # lists the uncovered files.
        control = self._run_control()
        self._edit(control)
        self.assert_supersedes(
            control.file_view.edit_file("second.txt", "Second line one", "Second: first"),
            True,
        )
        failure = self.as_tool_failure(control.advance(
            changes=[{"file": "test.txt", "summary": "changed"}]
        ))
        self.assertIn("second.txt", failure.value)

    def test_advance_net_out_change_rejected_then_no_change(self) -> None:
        # A write that nets out to no change (an edit later undone) is not a
        # change: a claimed change for it is rejected (the run net-changed
        # nothing and is directed to report no change), and advance() with no
        # changes signals NoChangeResult.
        control = self._run_control()
        self._edit(control)
        self._edit(control, old="New content", new="This is a test")
        failure = self.as_tool_failure(control.advance(
            changes=[{"file": "test.txt", "summary": "I changed it"}]
        ))
        self.assertIn("net-changed nothing", failure.value)
        self.assertIn("with no changes", failure.value)
        result = self.as_success(control.advance())
        self.assertIsInstance(result.value, NoChangeResult)

    def test_advance_soft_bound_rejection_guidance(self) -> None:
        # A summary over the soft bound (200) is rejected with shortening
        # guidance naming the soft bound and directing a short sentence
        # naming the parts of the file that changed.
        control = self._run_control()
        self._edit(control)
        failure = self.as_tool_failure(control.advance(
            changes=[{"file": "test.txt", "summary": "x" * 201}]
        ))
        self.assertIn("short sentence", failure.value)
        self.assertIn("200", failure.value)
        self.assertIn("parts of the file that changed", failure.value)

    def test_advance_soft_grace_accepts_within_hard_bound(self) -> None:
        # A summary over the soft bound is rejected up to the grace count (4),
        # then accepted on the next advance call when within the hard bound
        # (500): advance signals successful termination with a ChangeResult.
        control = self._run_control()
        self._edit(control)
        for _ in range(4):
            self.as_tool_failure(control.advance(
                changes=[{"file": "test.txt", "summary": "x" * 201}]
            ))
        outcome = control.advance(
            changes=[{"file": "test.txt", "summary": "y" * 480}]
        )
        self.assertIsInstance(outcome, TerminateAgentWithSuccess)
        assert isinstance(outcome, TerminateAgentWithSuccess)
        self.assertIsInstance(outcome.value, ChangeResult)
        assert isinstance(outcome.value, ChangeResult)
        self.assertEqual(
            outcome.value.messages,
            [NodeMessage(kind="change", text="test.txt: " + "y" * 480)],
        )

    def test_advance_hard_bound_rejection_guidance(self) -> None:
        # A summary over the hard bound (500) is rejected with guidance to
        # shorten it to the hard limit.
        control = self._run_control()
        self._edit(control)
        failure = self.as_tool_failure(control.advance(
            changes=[{"file": "test.txt", "summary": "x" * 600}]
        ))
        self.assertIn("500", failure.value)
        self.assertIn("Shorten it", failure.value)

    def test_advance_hard_grace_turns_advance_into_failure(self) -> None:
        # A summary over the hard bound is rejected up to the grace count (4),
        # then advance() turns into a hard failure (TerminateAgentWithFailure)
        # on the next advance call.
        control = self._run_control()
        self._edit(control)
        for _ in range(4):
            self.as_tool_failure(control.advance(
                changes=[{"file": "test.txt", "summary": "x" * 600}]
            ))
        outcome = control.advance(
            changes=[{"file": "test.txt", "summary": "x" * 600}]
        )
        self.assertIsInstance(outcome, TerminateAgentWithFailure)

    # ------------------------------------------------------------------
    # advance: the feedback-pending gate
    # ------------------------------------------------------------------

    def test_advance_feedback_pending_no_change_fails(self) -> None:
        # When feedback is pending and advance would otherwise signal
        # successful termination without a change, advance returns a tool
        # failure directing the agent to change, blame, or fail; the session
        # continues (no termination signal is produced).
        failure = self.as_tool_failure(self._run_control(feedback_pending=True).advance())
        self.assertIn("feedback", failure.value)
        self.assertIn("blame() or fail()", failure.value)

    def test_advance_feedback_pending_gate_checked_after_change_message(self) -> None:
        # The feedback-pending gate is checked only when advance would
        # otherwise signal successful termination without a change: with a
        # changed file and an empty change message, the change-message
        # requirement (showing the diff) is checked first, not the feedback
        # gate.
        control = self._run_control(feedback_pending=True)
        self._edit(control)
        failure = self.as_tool_failure(control.advance())
        self.assertIn("### diff", failure.value)
        self.assertIn("advance(changes=", failure.value)

    def test_advance_feedback_pending_with_change_succeeds(self) -> None:
        # A run processing feedback terminates successfully when the run
        # changed files and reports the change.
        control = self._run_control(feedback_pending=True)
        self._edit(control)
        result = self.as_success(control.advance(
            changes=[{"file": "test.txt", "summary": "Updated the test line"}]
        ))
        self.assertIsInstance(result.value, ChangeResult)

    # ------------------------------------------------------------------
    # advance: step-mode gating
    # ------------------------------------------------------------------

    def test_advance_step_mode_delivers_sections_then_terminates(self) -> None:
        # In step mode with step sections remaining, a passing verification
        # delivers the next step section (a PresentedToolResult) and the
        # session continues — never a tool failure for the change message;
        # when no sections remain, advance proceeds to the termination
        # machinery.
        control = self._run_control(step_sections=True, guide="guide.md")
        first = control.advance()
        assert isinstance(first, list) and isinstance(first[0], PresentedToolResult)
        self.assertIn("Checklist: Imports", first[0].result.content)
        second = control.advance()
        assert isinstance(second, list) and isinstance(second[0], PresentedToolResult)
        self.assertIn("Checklist: Contracts", second[0].result.content)
        outcome = control.advance()
        self.assertIsInstance(outcome, TerminateAgentWithSuccess)
        assert isinstance(outcome, TerminateAgentWithSuccess)
        self.assertIsInstance(outcome.value, NoChangeResult)

    def test_advance_step_mode_changed_run_never_fails_on_change_message(self) -> None:
        # In step mode, an advance with step sections remaining carries no
        # change message: even with a changed run, the advance delivers the
        # next step section instead of failing on the change-message
        # requirement.
        control = self._run_control(step_sections=True, guide="guide.md")
        self._edit(control)
        first = control.advance()
        assert isinstance(first, list) and isinstance(first[0], PresentedToolResult)
        self.assertIn("Checklist: Imports", first[0].result.content)

    def test_advance_step_mode_failing_verification_restates_summary(self) -> None:
        # In step mode, a failing verification's output is the restated guide
        # summary with the reason (via guide_delivery's output rule); the
        # next step section is not delivered.
        def callback() -> Tuple[bool, str]:
            return (False, "lint error here")

        control = self._run_control(
            verification_callback=callback, step_sections=True, guide="guide.md"
        )
        feedback = control.advance()
        assert isinstance(feedback, list) and feedback
        result = feedback[0]
        assert isinstance(result, ToolResult)
        self.assertIn("The artifact conforms to this guide.", result.content)
        self.assertIn("lint error here", result.content)
        self.assertNotIn("Checklist", result.content)

    # ------------------------------------------------------------------
    # fail / blame
    # ------------------------------------------------------------------

    def test_fail_returns_pinned_value(self) -> None:
        # fail returns TerminateAgentWithFailure[str] with its value pinned to
        # "Task failed"; termination tools produce no ToolResult.
        result = self.as_terminate_failure(self._run_control().fail())
        self.assertEqual(result.value, "Task failed")
        self.assertEqual(result.type, "terminate_failure")

    def test_blame_no_targets_configured_fails(self) -> None:
        # blame with no configured blame targets is a precondition violation:
        # a ToolFailure; the tool is not offered when targets are empty.
        failure = self.as_tool_failure(
            self._run_control(blame_targets={}).blame([("x", "fix it")])
        )
        self.assertIn("not configured", failure.value)

    def test_blame_empty_list_fails(self) -> None:
        failure = self.as_tool_failure(self._run_control().blame([]))
        self.assertIn("must not be empty", failure.value)

    def test_blame_invalid_target_fails(self) -> None:
        failure = self.as_tool_failure(
            self._run_control().blame([("not_a_dep", "fix it")])
        )
        self.assertIn("not_a_dep", failure.value)

    def test_blame_mixed_valid_and_invalid_fails(self) -> None:
        # If any pair's target is invalid, blame returns a ToolFailure (no
        # partial result).
        failure = self.as_tool_failure(
            self._run_control().blame([("agent", "fix it"), ("nope", "redo")])
        )
        self.assertIn("nope", failure.value)

    def test_blame_success_resolves_targets_to_owning_nodes(self) -> None:
        # Each valid (target, feedback) pair is resolved through the
        # blame_targets mapping to the owning node's NodeId and delivered as
        # one feedback message (a NodeMessage with kind "feedback") in a
        # FeedbackResult.
        result = self.as_success(
            self._run_control().blame([("agent", "fix the output"), ("system", "redo")])
        )
        self.assertIsInstance(result.value, FeedbackResult)
        assert isinstance(result.value, FeedbackResult)
        self.assertEqual(
            result.value.messages,
            [
                ("//pkg:agent", NodeMessage(kind="feedback", text="fix the output")),
                ("//pkg:system", NodeMessage(kind="feedback", text="redo")),
            ],
        )

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def test_termination_signals_are_not_results(self) -> None:
        # Termination tools produce no ToolResult: a successful advance and a
        # fail are signals, never result sequences.
        control = self._run_control()
        self.assertIsInstance(control.advance(), TerminateAgentWithSuccess)
        self.assertIsInstance(control.fail(), TerminateAgentWithFailure)

    def test_no_state_persists_across_runs(self) -> None:
        # A fresh run_control for the same components starts clean: the
        # change-summary grace counters are reset (the first soft-limit
        # rejection is a rejection, not an acceptance) and advance with no
        # changes terminates without change.
        control1 = self._run_control()
        self._edit(control1)
        for _ in range(4):
            self.as_tool_failure(control1.advance(
                changes=[{"file": "test.txt", "summary": "x" * 201}]
            ))
        self.as_success(control1.advance(
            changes=[{"file": "test.txt", "summary": "y" * 480}]
        ))
        control2 = self._run_control()
        result = self.as_success(control2.advance())
        self.assertIsInstance(result.value, NoChangeResult)


if __name__ == "__main__":
    unittest.main()
