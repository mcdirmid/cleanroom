import difflib
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

from lib.run_control import RunControlConfig
from lib.run_control_impl import RunControlImpl
from lib.file_reader import FileReader
from lib.file_editor import FileEditor
from lib.guide_delivery import GuideDelivery
from lib.change_summary_validator import ChangeSummaryValidator, ClaimedChanges, ValidationOutcome
from lib.tool_provider import ToolDefinition
from lib.tool_provider import (
    PresentedToolResult,
    ToolResult,
    ToolFailure,
    TerminateAgentWithSuccess,
    TerminateAgentWithFailure,
)
from lib.dag_clean_logic import ChangeResult, FeedbackResult, NoChangeResult
from lib.dag_storage import NodeMessage

GUIDE = (
    "# Guide: Converting\n\n"
    "## Summary\n\n"
    "The artifact conforms to this guide.\n\n"
    "## Checklist: Imports\n\n"
    "- [ ] Imports come from the closure\n\n"
    "## Checklist: Contracts\n\n"
    "- [ ] Signatures match the LLS\n"
)




class _MockFileReader(FileReader):
    def __init__(self, files: Dict[str, str], readable_paths: List[str]) -> None:
        self.files = dict(files)
        self.readable_paths = list(readable_paths)

    def get_readable_paths(self) -> List[str]:
        return list(self.readable_paths)

    def is_readable(self, path: str) -> bool:
        return path in self.readable_paths

    def resolve_path(self, path: str) -> str:
        return path

    def read_file(self, path: str, line_numbers: bool = True) -> PresentedToolResult:
        if path not in self.files:
            return [ToolFailure(f"File not found: {path}")]
        return [ToolResult(content=self.files[path])]

    def get_file_size(self, path: str) -> int:
        return len(self.files.get(path, ""))

    def sanitize_paths(self, text: str) -> str:
        return text


class _MockFileEditor(FileEditor):
    def __init__(self, files: Dict[str, str], writable_paths: List[str]) -> None:
        self.snapshots = dict(files)
        self.current = dict(files)
        self.writable_paths = list(writable_paths)
        self.changed_files: Set[str] = set()
        self.write_occurred = False

    def get_tool_definitions(self) -> List[ToolDefinition]:
        return []

    def replace(self, file_path: str, old_str: str, new_str: str, expect_multiple: bool = False) -> ToolCallOutcome:
        if file_path not in self.writable_paths:
            return ToolFailure(f"Not writable: {file_path}")
        content = self.current.get(file_path, "")
        if old_str not in content:
            return ToolFailure("old_str not found")
        self.current[file_path] = content.replace(old_str, new_str, 1 if not expect_multiple else -1)
        self.changed_files.add(file_path)
        self.write_occurred = True
        return ToolResult(content="Replaced", supersedes=True)

    def update_lines(self, file_path: str, start_line: int, end_line: int, new_str: str) -> ToolCallOutcome:
        self.changed_files.add(file_path)
        self.write_occurred = True
        return ToolResult(content="Updated", supersedes=True)

    def get_write_occurred(self) -> bool:
        return self.write_occurred

    def get_changed_files(self) -> List[str]:
        return sorted(self.changed_files)

    def get_run_start_snapshot(self, file_path: str) -> Optional[str]:
        return self.snapshots.get(file_path)

    def get_current_content(self, file_path: str) -> Optional[str]:
        return self.current.get(file_path)

    def is_writable(self, file_path: str) -> bool:
        return file_path in self.writable_paths


class _MockGuideDelivery(GuideDelivery):
    def __init__(self, guide: Optional[str] = None, step_sections_enabled: bool = False) -> None:
        self.guide = guide
        self.step_sections_enabled = step_sections_enabled
        self.step_count = 2 if (guide and step_sections_enabled) else 0
        self.current_step = 0

    def get_tool_definitions(self) -> List[ToolDefinition]:
        return []

    def get_session_start_reads(self) -> List[PresentedToolResult]:
        return []

    def has_step_sections_remaining(self) -> bool:
        return self.step_sections_enabled and self.current_step < self.step_count

    def get_advance_output(self, verification_passed: bool, failure_reason: Optional[str] = None) -> Optional[PresentedToolResult]:
        if not self.step_sections_enabled:
            return None
        if not verification_passed:
            content = f"The artifact conforms to this guide.\n\n{failure_reason}\n\nVerification failed; correct the reported issues before calling advance() again, or call blame() or fail() to end the run."
            return PresentedToolResult(
                name="advance",
                arguments={},
                result=ToolResult(content=content, supersedes=True, note="Verification failed."),
            )
        if self.current_step < self.step_count:
            self.current_step += 1
            section = "Checklist: Imports" if self.current_step == 1 else "Checklist: Contracts"
            return PresentedToolResult(name="advance", arguments={}, result=ToolResult(content=f"## {section}\n\nContent", supersedes=True))
        return None

    def sanitize_paths(self, text: str) -> str:
        return text



class _MockChangeSummaryValidator(ChangeSummaryValidator):
    def __init__(self, file_editor: FileEditor, diff_size_limit: int = 1000) -> None:
        self.file_editor = file_editor
        self.diff_size_limit = diff_size_limit
        self.calls: List[tuple] = []
        self._soft_rejections: int = 0
        self._hard_rejections: int = 0

    def compute_diff_summary(self) -> str:
        self.calls.append(("compute_diff_summary", ()))
        chunks = []
        for f in self.file_editor.get_changed_files():
            snapshot = self.file_editor.get_run_start_snapshot(f)
            current = self.file_editor.get_current_content(f)
            if snapshot != current:
                orig_lines = snapshot.splitlines(keepends=True) if snapshot is not None else []
                new_lines = current.splitlines(keepends=True) if current is not None else []
                diff = list(difflib.unified_diff(orig_lines, new_lines, fromfile=f"a/{f}", tofile=f"b/{f}"))
                chunks.append(f"### diff for {f}\n" + "".join(diff))
        diff_text = "\n".join(chunks)
        if len(diff_text) > self.diff_size_limit:
            total_chars = len(diff_text)
            diff_text = diff_text[:self.diff_size_limit] + f"\n... [diff truncated: showing {self.diff_size_limit} of {total_chars} characters]"
        return diff_text

    def get_effective_changes(self) -> List[str]:
        effectively_changed: List[str] = []
        for file_path in self.file_editor.get_changed_files():
            current = self.file_editor.get_current_content(file_path)
            if current != self.file_editor.get_run_start_snapshot(file_path):
                effectively_changed.append(file_path)
        return effectively_changed

    def validate_change_summaries(self, changes: ClaimedChanges) -> ValidationOutcome:
        self.calls.append(("validate_change_summaries", (changes,)))
        changes = changes or []
        effectively_changed = self.get_effective_changes()
        if not effectively_changed:
            if changes:
                return ToolFailure[str]("Cannot advance: the run wrote files but net-changed nothing — each file's current content equals its content at run start. Call advance() with no changes to report no change.")
            return None
        if not changes:
            msg_text = (
                f"Cannot advance: the run changed files ({', '.join(effectively_changed)}). "
                "Call advance(changes=[{file, summary}, ...]) with one entry per changed file — "
                "each summary one short sentence on what changed in that file (not how it was done) — "
                "so the next agent knows what changed, or call fail() or blame() to end the run.\n\n"
                f"The run's diff:\n{self.compute_diff_summary()}"
            )
            return ToolFailure[str](msg_text)

        claimed_files = [c.get("file", "") for c in changes]

        for entry in changes:
            fn = entry.get("file", "")
            sm = entry.get("summary", "")
            if not fn or not sm or not sm.strip():
                return ToolFailure[str]("Cannot advance: each change entry must have a non-empty 'file' and a non-empty one-sentence 'summary' of what changed in that file.")
            if fn not in effectively_changed:
                return ToolFailure[str](f"Cannot advance: '{fn}' was not changed by this run; report only the changed files ({', '.join(effectively_changed)}).")
            length = len(sm.strip())
            if length > 500:
                if self._hard_rejections >= 4:
                    raise RuntimeError(f"the change summary for '{fn}' could not be shortened to the hard limit (500 characters) after repeated attempts.")
                self._hard_rejections += 1
                return ToolFailure[str](f"Cannot advance: the summary for '{fn}' is {length} characters (max 500 — the hard limit). Shorten it to at most 500 characters: name the parts of the file that changed in one short sentence, dropping how it was done, then call advance() again with the shortened summary.")
            if length > 300:
                if self._soft_rejections < 4:
                    self._soft_rejections += 1
                    return ToolFailure[str](f"Cannot advance: the summary for '{fn}' is {length} characters (aim for at most 300). Shorten it to at most 300 characters: name the parts of the file that changed in one short sentence, so the next agent knows what to pay attention to when updating further artifacts, dropping how it was done, then call advance() again with the shortened summary.")

        missing = [f for f in effectively_changed if f not in claimed_files]
        if missing:
            return ToolFailure[str](f"Cannot advance: changes list is missing entries for changed files: {', '.join(missing)}")

        self._soft_rejections = 0
        self._hard_rejections = 0
        return None

    def reset_validator_state(self) -> None:
        self._soft_rejections = 0
        self._hard_rejections = 0


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
        files = {
            "test.txt": "Line 1: Hello World\nLine 2: This is a test\nLine 3: Another line\nLine 4: Final line\n",
            "second.txt": "Second line one\nSecond line two\n",
            "ro.txt": "Read only line 1\n",
            "new.txt": "",
        }
        file_reader = _MockFileReader(files, self.readable_paths)
        file_editor = _MockFileEditor(files, self.writable_paths)
        guide_real = self.guide_path if guide == "guide.md" else guide
        guide_delivery = _MockGuideDelivery(guide_real, step_sections)
        validator = _MockChangeSummaryValidator(file_editor=file_editor, diff_size_limit=diff_size_limit)
        return RunControlImpl(
            RunControlConfig(
                verification_callback=verification_callback,
                feedback_pending=feedback_pending,
                blame_targets=blame_targets if blame_targets is not None else self.blame_targets,
                diff_size_limit=diff_size_limit,
            ),
            file_reader=file_reader,
            file_editor=file_editor,
            guide_delivery=guide_delivery,
            validator=validator,
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
            control.file_editor.replace("test.txt", old, new), True
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
            control.file_editor.replace("second.txt", "Second line one", "Second: first"),
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
        # A summary over the soft bound (300) is rejected with shortening
        # guidance naming the soft bound and directing a short sentence
        # naming the parts of the file that changed.
        control = self._run_control()
        self._edit(control)
        failure = self.as_tool_failure(control.advance(
            changes=[{"file": "test.txt", "summary": "x" * 301}]
        ))
        self.assertIn("short sentence", failure.value)
        self.assertIn("300", failure.value)
        self.assertIn("parts of the file that changed", failure.value)

    def test_advance_soft_grace_accepts_within_hard_bound(self) -> None:
        # A summary over the soft bound is rejected up to the grace count (4),
        # then accepted on the next advance call when within the hard bound
        # (500): advance signals successful termination with a ChangeResult.
        control = self._run_control()
        self._edit(control)
        for _ in range(4):
            self.as_tool_failure(control.advance(
                changes=[{"file": "test.txt", "summary": "x" * 301}]
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

    def test_advance_feedback_pending_no_change_warns_then_succeeds(self) -> None:
        # When feedback is pending and advance would otherwise signal
        # successful termination without a change, the first advance returns a
        # tool failure warning that feedback was not responded to; the second
        # advance without changes succeeds with NoChangeResult.
        control = self._run_control(feedback_pending=True)
        failure = self.as_tool_failure(control.advance())
        self.assertIn("Warning: feedback was given", failure.value)
        self.assertIn("advance() again", failure.value)
        result = self.as_success(control.advance())
        self.assertIsInstance(result.value, NoChangeResult)

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

    def test_blame_target_not_in_blame_targets_fails(self) -> None:
        # A blame pair with a target that is not a key of blame_targets returns
        # a ToolFailure.
        failure = self.as_tool_failure(
            self._run_control().blame([("not_a_dep", "fix it")])
        )
        self.assertIn("not_a_dep", failure.value)
        self.assertIn("agent", failure.value)
        self.assertIn("system", failure.value)

    def test_blame_mixed_valid_and_invalid_fails(self) -> None:
        # If any pair's target is invalid, blame returns a ToolFailure (no
        # partial result).
        failure = self.as_tool_failure(
            self._run_control().blame([("agent", "fix it"), ("nope", "redo")])
        )
        self.assertIn("nope", failure.value)
        self.assertIn("agent", failure.value)
        self.assertIn("system", failure.value)

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

    def test_blame_resolves_dict_format_to_owning_nodes(self) -> None:
        result = self.as_success(
            self._run_control().blame([
                {"target": "agent", "feedback": "fix the output"},
                {"target": "system", "feedback": "redo"},
            ])
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
                changes=[{"file": "test.txt", "summary": "x" * 301}]
            ))
        self.as_success(control1.advance(
            changes=[{"file": "test.txt", "summary": "y" * 480}]
        ))
        control2 = self._run_control()
        result = self.as_success(control2.advance())
        self.assertIsInstance(result.value, NoChangeResult)


if __name__ == "__main__":
    unittest.main()
