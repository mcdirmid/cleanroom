"""
Tests for the SandboxImpl implementation.

Written from the LLS (specs/low/sandbox_impl.md, specs/low/sandbox.md): the
sandbox is a facade that composes injected components — the file machinery
(file_view), the step-mode delivery (guide_delivery), and the verification
and termination rules (run_control). The tests inject recording stubs for
the three components and assert the sandbox's own contract:

- the construction protocol: the derived component configs (with the
  step-mode gating of the guide's readability), the run_control factory
  receiving the sandbox's file_view and guide_delivery, and the diff size
  limit default;
- the dispatch of each operation to the owning component with the same
  arguments, and the result pass-through for pure delegations;
- the composed tool registry and session-start reads;
- the step-mode read/search gating policy.

Component behavior itself (file semantics, diff truncation, blame
resolution, step-section delivery) is tested in the components' own tests
(file_view_impl_test, run_control_impl_test, guide_delivery_impl_test);
one smoke test wires the default implementations to prove the facade
composes them coherently.
"""

import os
import shutil
import tempfile
import unittest
from typing import Any, Dict, List, Optional, Tuple

from update_with_ai.lib.sandbox import SandboxConfig
from update_with_ai.lib.sandbox_impl import SandboxImpl
from update_with_ai.lib.file_view import FileViewConfig
from update_with_ai.lib.guide_delivery import GuideDeliveryConfig
from update_with_ai.lib.run_control import RunControlConfig
from update_with_ai.lib.tool_provider import (
    PresentedToolResult,
    ToolDefinition,
    ToolFailure,
    ToolResult,
)


class _StubFileView:
    """Recording stub for the file machinery (FileView)."""

    def __init__(self) -> None:
        self.calls: List[Tuple[str, Tuple[Any, ...]]] = []
        self.tool_definitions: List[ToolDefinition] = []
        self.session_start_reads: List[PresentedToolResult] = []
        self.read_result: Any = ToolResult(content="read", supersedes=False)
        self.write_occurred: Any = False

    def _record(self, name: str, *args: Any) -> None:
        self.calls.append((name, args))

    def get_tool_definitions(self) -> Any:
        self._record("get_tool_definitions")
        return self.tool_definitions

    def get_session_start_reads(self) -> Any:
        self._record("get_session_start_reads")
        return self.session_start_reads

    def read_file(self, file_path: Any, include_line_numbers: Any = False) -> Any:
        self._record("read_file", file_path, include_line_numbers)
        return self.read_result

    def edit_file(self, file_path: Any, old_str: Any, new_str: Any, expect_multiple: Any = False) -> Any:
        self._record("edit_file", file_path, old_str, new_str, expect_multiple)
        return self.read_result

    def replace_lines(self, file_path: Any, start_line: Any, end_line: Any, new_str: Any) -> Any:
        self._record("replace_lines", file_path, start_line, end_line, new_str)
        return self.read_result

    def search_files(self, path: Any, pattern: Any) -> Any:
        self._record("search_files", path, pattern)
        return self.read_result

    def get_write_occurred(self) -> Any:
        self._record("get_write_occurred")
        return self.write_occurred

    def get_changed_files(self) -> Any:
        self._record("get_changed_files")
        return []

    def get_run_start_snapshot(self, file_path: Any) -> Any:
        self._record("get_run_start_snapshot", file_path)
        return None

    def get_current_content(self, file_path: Any) -> Any:
        self._record("get_current_content", file_path)
        return None


class _StubGuideDelivery:
    """Recording stub for the step-mode delivery (GuideDelivery)."""

    def __init__(self) -> None:
        self.calls: List[Tuple[str, Tuple[Any, ...]]] = []
        self.tool_definitions: List[ToolDefinition] = []
        self.session_start_reads: List[PresentedToolResult] = []
        self.advance_output: Any = None

    def _record(self, name: str, *args: Any) -> None:
        self.calls.append((name, args))

    def get_tool_definitions(self) -> Any:
        self._record("get_tool_definitions")
        return self.tool_definitions

    def get_session_start_reads(self) -> Any:
        self._record("get_session_start_reads")
        return self.session_start_reads

    def get_advance_output(self, verification_passed: Any, *args: Any, **kwargs: Any) -> Any:
        self._record("get_advance_output", verification_passed)
        return self.advance_output

    def has_step_sections_remaining(self) -> Any:
        self._record("has_step_sections_remaining")
        return False


class _StubRunControl:
    """Recording stub for the verification and termination rules (RunControl)."""

    def __init__(self) -> None:
        self.calls: List[Tuple[str, Tuple[Any, ...]]] = []
        self.tool_definitions: List[ToolDefinition] = []
        self.advance_result: Any = None
        self.fail_result: Any = None
        self.blame_result: Any = None

    def _record(self, name: str, *args: Any) -> None:
        self.calls.append((name, args))

    def get_tool_definitions(self) -> Any:
        self._record("get_tool_definitions")
        return self.tool_definitions

    def advance(self, changes: Any = []) -> Any:
        self._record("advance", changes)
        return self.advance_result

    def fail(self) -> Any:
        self._record("fail")
        return self.fail_result

    def blame(self, blames: Any) -> Any:
        self._record("blame", blames)
        return self.blame_result


class _SandboxHarness:
    """Builds a SandboxImpl around recording stubs and records the factory
    calls (the derived configs and the constructed components)."""

    def __init__(self, config: SandboxConfig, diff_size_limit: Optional[int] = None) -> None:
        self.file_view = _StubFileView()
        self.guide_delivery = _StubGuideDelivery()
        self.run_control = _StubRunControl()
        self.factory_calls: List[Tuple[str, Tuple[Any, ...]]] = []

        def make_file_view(fvc: FileViewConfig) -> Any:
            self.factory_calls.append(("file_view", (fvc,)))
            return self.file_view

        def make_guide_delivery(gdc: GuideDeliveryConfig) -> Any:
            self.factory_calls.append(("guide_delivery", (gdc,)))
            return self.guide_delivery

        def make_run_control(rcc: RunControlConfig, fv: Any, gd: Any) -> Any:
            self.factory_calls.append(("run_control", (rcc, fv, gd)))
            return self.run_control

        self.sandbox = SandboxImpl(
            config=config,
            make_file_view=make_file_view,
            make_guide_delivery=make_guide_delivery,
            make_run_control=make_run_control,
            diff_size_limit=diff_size_limit,
        )

    def call(self, name: str) -> Tuple[Any, ...]:
        for n, args in self.factory_calls:
            if n == name:
                return args
        raise AssertionError(f"factory {name!r} never called; calls: {self.factory_calls}")


def _config(**overrides: Any) -> SandboxConfig:
    """A sandbox config with the default mappings; override any field."""
    base: Dict[str, Any] = dict(
        file_mappings={"a.txt": "/ws/a.txt", "guide.txt": "/ws/guide.md"},
        readable_paths=["a.txt", "guide.txt"],
        writable_paths=["a.txt"],
        blame_targets={},
        search_result_limit=5,
    )
    base.update(overrides)
    return SandboxConfig(**base)


class TestConstruction(unittest.TestCase):
    """The construction protocol: derived configs, step-mode gating, and the
    run_control factory receiving the sandbox's components."""

    def test_file_view_config_derived(self) -> None:
        h = _SandboxHarness(_config())
        (fvc,) = h.call("file_view")
        self.assertIsInstance(fvc, FileViewConfig)
        self.assertEqual(fvc.file_mappings, {"a.txt": "/ws/a.txt", "guide.txt": "/ws/guide.md"})
        self.assertEqual(fvc.readable_paths, ["a.txt", "guide.txt"])
        self.assertEqual(fvc.writable_paths, ["a.txt"])
        self.assertEqual(fvc.search_result_limit, 5)
        self.assertTrue(fvc.session_start_reads_enabled)

    def test_guide_delivery_config_derived(self) -> None:
        h = _SandboxHarness(_config(guide="guide.txt", step_sections_enabled=True))
        (gdc,) = h.call("guide_delivery")
        self.assertIsInstance(gdc, GuideDeliveryConfig)
        self.assertEqual(gdc.guide, "/ws/guide.md")  # resolved via file_mappings
        self.assertTrue(gdc.step_sections_enabled)

    def test_guide_delivery_config_no_guide(self) -> None:
        h = _SandboxHarness(_config())
        (gdc,) = h.call("guide_delivery")
        self.assertIsNone(gdc.guide)

    def test_run_control_config_derived(self) -> None:
        h = _SandboxHarness(_config(feedback_pending=True))
        (rcc, _, _) = h.call("run_control")
        self.assertIsInstance(rcc, RunControlConfig)
        self.assertTrue(rcc.feedback_pending)
        self.assertEqual(rcc.blame_targets, {})
        self.assertEqual(rcc.diff_size_limit, 1000)  # default when None

    def test_diff_size_limit_passed_through(self) -> None:
        h = _SandboxHarness(_config(), diff_size_limit=40)
        (rcc, _, _) = h.call("run_control")
        self.assertEqual(rcc.diff_size_limit, 40)

    def test_run_control_receives_sandbox_components(self) -> None:
        h = _SandboxHarness(_config())
        (_, fv, gd) = h.call("run_control")
        self.assertIs(fv, h.file_view)
        self.assertIs(gd, h.guide_delivery)

    def test_step_mode_excludes_guide_from_readable_paths(self) -> None:
        h = _SandboxHarness(_config(guide="guide.txt", step_sections_enabled=True))
        (fvc,) = h.call("file_view")
        self.assertEqual(fvc.readable_paths, ["a.txt"])  # guide excluded

    def test_no_step_mode_keeps_guide_readable(self) -> None:
        h = _SandboxHarness(_config(guide="guide.txt", step_sections_enabled=False))
        (fvc,) = h.call("file_view")
        self.assertEqual(fvc.readable_paths, ["a.txt", "guide.txt"])


class TestDelegation(unittest.TestCase):
    """Each operation dispatches to the owning component with the same
    arguments and returns its result unchanged."""

    def setUp(self) -> None:
        self.h = _SandboxHarness(_config())

    def test_read_file_delegates(self) -> None:
        result = self.h.sandbox.read_file("a.txt", include_line_numbers=True)
        self.assertEqual(self.h.file_view.calls, [("read_file", ("a.txt", True))])
        self.assertIs(result, self.h.file_view.read_result)

    def test_read_file_default_line_numbers(self) -> None:
        self.h.sandbox.read_file("a.txt")
        self.assertEqual(self.h.file_view.calls, [("read_file", ("a.txt", False))])

    def test_edit_file_delegates(self) -> None:
        result = self.h.sandbox.edit_file("a.txt", "old", "new", expect_multiple=True)
        self.assertEqual(self.h.file_view.calls, [("edit_file", ("a.txt", "old", "new", True))])
        self.assertIs(result, self.h.file_view.read_result)

    def test_replace_lines_delegates(self) -> None:
        result = self.h.sandbox.replace_lines("a.txt", 1, 3, "content")
        self.assertEqual(self.h.file_view.calls, [("replace_lines", ("a.txt", 1, 3, "content"))])
        self.assertIs(result, self.h.file_view.read_result)

    def test_search_files_delegates(self) -> None:
        result = self.h.sandbox.search_files("a.txt", "needle")
        self.assertEqual(self.h.file_view.calls, [("search_files", ("a.txt", "needle"))])
        self.assertIs(result, self.h.file_view.read_result)

    def test_get_write_occurred_delegates(self) -> None:
        self.h.file_view.write_occurred = True
        self.assertTrue(self.h.sandbox.get_write_occurred())
        self.assertEqual(self.h.file_view.calls, [("get_write_occurred", ())])

    def test_advance_delegates(self) -> None:
        changes = [{"file": "a.txt", "summary": "changed"}]
        self.h.run_control.advance_result = ToolResult(content="advance", supersedes=False)
        result = self.h.sandbox.advance(changes)
        self.assertEqual(self.h.run_control.calls, [("advance", (changes,))])
        self.assertIs(result, self.h.run_control.advance_result)

    def test_fail_delegates(self) -> None:
        self.h.run_control.fail_result = ToolFailure[str]("failed")
        result = self.h.sandbox.fail()
        self.assertEqual(self.h.run_control.calls, [("fail", ())])
        self.assertIs(result, self.h.run_control.fail_result)

    def test_blame_delegates(self) -> None:
        self.h.run_control.blame_result = ToolResult(content="blame", supersedes=False)
        result = self.h.sandbox.blame([("a.txt", "fix it")])
        self.assertEqual(self.h.run_control.calls, [("blame", ([("a.txt", "fix it")],))])
        self.assertIs(result, self.h.run_control.blame_result)

    def test_get_session_start_reads_composes(self) -> None:
        fv_reads = [PresentedToolResult(name="read_file", arguments={}, result=ToolResult(content="r", supersedes=False))]
        gd_reads = [PresentedToolResult(name="advance", arguments={}, result=ToolResult(content="g", supersedes=False))]
        self.h.file_view.session_start_reads = fv_reads
        self.h.guide_delivery.session_start_reads = gd_reads
        result = self.h.sandbox.get_session_start_reads()
        self.assertEqual(result, fv_reads + gd_reads)
        self.assertEqual(self.h.file_view.calls, [("get_session_start_reads", ())])
        self.assertEqual(self.h.guide_delivery.calls, [("get_session_start_reads", ())])

    def test_get_tool_definitions_composes_in_order(self) -> None:
        fv_defs = [{"name": "file"}]
        gd_defs = [{"name": "advance"}]
        rc_defs = [{"name": "fail"}, {"name": "blame"}]
        self.h.file_view.tool_definitions = fv_defs
        self.h.guide_delivery.tool_definitions = gd_defs
        self.h.run_control.tool_definitions = rc_defs
        result = self.h.sandbox.get_tool_definitions()
        self.assertEqual(result, fv_defs + gd_defs + rc_defs)
        self.assertEqual(self.h.file_view.calls, [("get_tool_definitions", ())])
        self.assertEqual(self.h.guide_delivery.calls, [("get_tool_definitions", ())])
        self.assertEqual(self.h.run_control.calls, [("get_tool_definitions", ())])


class TestStepMode(unittest.TestCase):
    """The sandbox's own policy: the guide is not readable in step mode."""

    def setUp(self) -> None:
        self.h = _SandboxHarness(_config(guide="guide.txt", step_sections_enabled=True))

    def test_read_guide_in_step_mode_fails(self) -> None:
        result = self.h.sandbox.read_file("guide.txt")
        self.assertIsInstance(result, ToolFailure)
        self.assertEqual(self.h.file_view.calls, [])  # never delegated

    def test_read_other_file_in_step_mode_delegates(self) -> None:
        self.h.sandbox.read_file("a.txt")
        self.assertEqual(self.h.file_view.calls, [("read_file", ("a.txt", False))])

    def test_search_guide_in_step_mode_fails(self) -> None:
        result = self.h.sandbox.search_files("guide.txt", "x")
        self.assertIsInstance(result, ToolFailure)
        self.assertEqual(self.h.file_view.calls, [])

    def test_read_guide_not_in_step_mode_delegates(self) -> None:
        h = _SandboxHarness(_config(guide="guide.txt", step_sections_enabled=False))
        h.sandbox.read_file("guide.txt")
        self.assertEqual(h.file_view.calls, [("read_file", ("guide.txt", False))])


class TestSmoke(unittest.TestCase):
    """One smoke test: the default component implementations wired through
    the factories compose into a working sandbox."""

    def test_reads_real_file_through_default_wiring(self) -> None:
        from update_with_ai.lib.file_view_impl import FileViewImpl
        from update_with_ai.lib.guide_delivery_impl import GuideDeliveryImpl
        from update_with_ai.lib.run_control_impl import RunControlImpl

        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, "a.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("hello")
            config = _config(
                file_mappings={"a.txt": path},
                readable_paths=["a.txt"],
                writable_paths=["a.txt"],
            )
            sandbox = SandboxImpl(
                config=config,
                make_file_view=lambda fvc: FileViewImpl(config=fvc),
                make_guide_delivery=lambda gdc: GuideDeliveryImpl(config=gdc),
                make_run_control=lambda rcc, fv, gd: RunControlImpl(rcc, file_view=fv, guide_delivery=gd),
            )
            result = sandbox.read_file("a.txt")
            self.assertIn("hello", str(result.content))
        finally:
            shutil.rmtree(tmp)
