"""
Tests for the SandboxImpl implementation.
"""

import os
import shutil
import tempfile
import unittest
from typing import Any, Dict, List, Optional, Tuple

from lib.sandbox import SandboxConfig
from lib.sandbox_impl import SandboxImpl
from lib.file_reader import FileReaderConfig
from lib.file_editor import FileEditorConfig
from lib.guide_delivery import GuideDeliveryConfig
from lib.run_control import RunControlConfig
from lib.tool_provider import (
    PresentedToolResult,
    ToolDefinition,
    ToolFailure,
    ToolResult,
)


class _StubFileReader:
    def __init__(self) -> None:
        self.calls: List[Tuple[str, Tuple[Any, ...]]] = []
        self.tool_definitions: List[ToolDefinition] = []
        self.session_start_reads: List[PresentedToolResult] = []
        self.read_result: Any = ToolResult(content="read", supersedes=False)

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

    def search_files(self, path: Any, pattern: Any, offset: Any = 0, limit: Any = None) -> Any:
        self._record("search_files", path, pattern, offset, limit)
        return self.read_result

    def sanitize_paths(self, text: str) -> str:
        self._record("sanitize_paths", text)
        return text

    def resolve_path(self, file_path: Any) -> Any:
        return "/ws/" + str(file_path)

    def is_readable(self, file_path: Any) -> bool:
        return True


class _StubFileEditor:
    def __init__(self) -> None:
        self.calls: List[Tuple[str, Tuple[Any, ...]]] = []
        self.tool_definitions: List[ToolDefinition] = []
        self.write_result: Any = ToolResult(content="write", supersedes=True)
        self.write_occurred: Any = False

    def _record(self, name: str, *args: Any) -> None:
        self.calls.append((name, args))

    def get_tool_definitions(self) -> Any:
        self._record("get_tool_definitions")
        return self.tool_definitions

    def replace(self, file_path: Any, old_str: Any, new_str: Any, expect_multiple: Any = False) -> Any:
        self._record("replace", file_path, old_str, new_str, expect_multiple)
        return self.write_result

    def update_lines(self, file_path: Any, start_line: Any, end_line: Any, new_str: Any) -> Any:
        self._record("update_lines", file_path, start_line, end_line, new_str)
        return self.write_result

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

    def is_writable(self, file_path: Any) -> bool:
        return True


class _StubGuideDelivery:
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
    def __init__(self, config: SandboxConfig, diff_size_limit: Optional[int] = None) -> None:
        self.file_reader = _StubFileReader()
        self.file_editor = _StubFileEditor()
        self.guide_delivery = _StubGuideDelivery()
        self.run_control = _StubRunControl()
        self.factory_calls: List[Tuple[str, Tuple[Any, ...]]] = []

        def make_file_reader(frc: FileReaderConfig) -> Any:
            self.factory_calls.append(("file_reader", (frc,)))
            return self.file_reader

        def make_file_editor(fec: FileEditorConfig, fr: Any) -> Any:
            self.factory_calls.append(("file_editor", (fec, fr)))
            return self.file_editor

        def make_guide_delivery(gdc: GuideDeliveryConfig) -> Any:
            self.factory_calls.append(("guide_delivery", (gdc,)))
            return self.guide_delivery

        def make_run_control(rcc: RunControlConfig, fr: Any, fe: Any, gd: Any) -> Any:
            self.factory_calls.append(("run_control", (rcc, fr, fe, gd)))
            return self.run_control

        self.sandbox = SandboxImpl(
            config=config,
            make_file_reader=make_file_reader,
            make_file_editor=make_file_editor,
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
    def test_file_reader_config_derived(self) -> None:
        h = _SandboxHarness(_config())
        (frc,) = h.call("file_reader")
        self.assertIsInstance(frc, FileReaderConfig)
        self.assertEqual(frc.file_mappings, {"a.txt": "/ws/a.txt", "guide.txt": "/ws/guide.md"})
        self.assertEqual(frc.readable_paths, ["a.txt", "guide.txt"])
        self.assertEqual(frc.search_result_limit, 5)
        self.assertTrue(frc.session_start_reads_enabled)

    def test_file_editor_config_derived(self) -> None:
        h = _SandboxHarness(_config())
        (fec, fr) = h.call("file_editor")
        self.assertIsInstance(fec, FileEditorConfig)
        self.assertEqual(fec.writable_paths, ["a.txt"])
        self.assertIs(fr, h.file_reader)

    def test_guide_delivery_config_derived(self) -> None:
        h = _SandboxHarness(_config(guide="guide.txt", step_sections_enabled=True))
        (gdc,) = h.call("guide_delivery")
        self.assertIsInstance(gdc, GuideDeliveryConfig)
        self.assertEqual(gdc.guide, "/ws/guide.md")
        self.assertTrue(gdc.step_sections_enabled)

    def test_guide_delivery_config_no_guide(self) -> None:
        h = _SandboxHarness(_config())
        (gdc,) = h.call("guide_delivery")
        self.assertIsNone(gdc.guide)

    def test_run_control_config_derived(self) -> None:
        h = _SandboxHarness(_config(feedback_pending=True))
        (rcc, _, _, _) = h.call("run_control")
        self.assertIsInstance(rcc, RunControlConfig)
        self.assertTrue(rcc.feedback_pending)
        self.assertEqual(rcc.blame_targets, {})
        self.assertEqual(rcc.diff_size_limit, 1000)

    def test_diff_size_limit_passed_through(self) -> None:
        h = _SandboxHarness(_config(), diff_size_limit=40)
        (rcc, _, _, _) = h.call("run_control")
        self.assertEqual(rcc.diff_size_limit, 40)

    def test_run_control_receives_sandbox_components(self) -> None:
        h = _SandboxHarness(_config())
        (_, fr, fe, gd) = h.call("run_control")
        self.assertIs(fr, h.file_reader)
        self.assertIs(fe, h.file_editor)
        self.assertIs(gd, h.guide_delivery)

    def test_step_mode_excludes_guide_from_readable_paths(self) -> None:
        h = _SandboxHarness(_config(guide="guide.txt", step_sections_enabled=True))
        (frc,) = h.call("file_reader")
        self.assertEqual(frc.readable_paths, ["a.txt"])

    def test_no_step_mode_keeps_guide_readable(self) -> None:
        h = _SandboxHarness(_config(guide="guide.txt", step_sections_enabled=False))
        (frc,) = h.call("file_reader")
        self.assertEqual(frc.readable_paths, ["a.txt", "guide.txt"])


class TestDelegation(unittest.TestCase):
    def setUp(self) -> None:
        self.h = _SandboxHarness(_config())

    def test_read_file_delegates(self) -> None:
        result = self.h.sandbox.read_file("a.txt", include_line_numbers=True)
        self.assertEqual(self.h.file_reader.calls, [("read_file", ("a.txt", True))])
        self.assertIs(result, self.h.file_reader.read_result)

    def test_read_file_default_line_numbers(self) -> None:
        self.h.sandbox.read_file("a.txt")
        self.assertEqual(self.h.file_reader.calls, [("read_file", ("a.txt", False))])

    def test_replace_delegates(self) -> None:
        result = self.h.sandbox.replace("a.txt", "old", "new", expect_multiple=True)
        self.assertEqual(self.h.file_editor.calls, [("replace", ("a.txt", "old", "new", True))])
        self.assertIs(result, self.h.file_editor.write_result)

    def test_update_lines_delegates(self) -> None:
        result = self.h.sandbox.update_lines("a.txt", 1, 3, "content")
        self.assertEqual(self.h.file_editor.calls, [("update_lines", ("a.txt", 1, 3, "content"))])
        self.assertIs(result, self.h.file_editor.write_result)

    def test_search_files_delegates(self) -> None:
        result = self.h.sandbox.search_files("a.txt", "needle")
        self.assertEqual(self.h.file_reader.calls, [("search_files", ("a.txt", "needle", None, None))])
        self.assertIs(result, self.h.file_reader.read_result)

    def test_get_write_occurred_delegates(self) -> None:
        self.h.file_editor.write_occurred = True
        self.assertTrue(self.h.sandbox.get_write_occurred())
        self.assertEqual(self.h.file_editor.calls, [("get_write_occurred", ())])

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
        fr_reads = [PresentedToolResult(name="read_file", arguments={}, result=ToolResult(content="r", supersedes=False))]
        gd_reads = [PresentedToolResult(name="advance", arguments={}, result=ToolResult(content="g", supersedes=False))]
        self.h.file_reader.session_start_reads = fr_reads
        self.h.guide_delivery.session_start_reads = gd_reads
        result = self.h.sandbox.get_session_start_reads()
        self.assertEqual(result, fr_reads + gd_reads)
        self.assertEqual(self.h.file_reader.calls, [("get_session_start_reads", ())])
        self.assertEqual(self.h.guide_delivery.calls, [("get_session_start_reads", ())])

    def test_get_tool_definitions_composes_in_order(self) -> None:
        fr_defs = [{"name": "read_file"}, {"name": "search_files"}]
        fe_defs = [{"name": "replace"}, {"name": "update_lines"}]
        gd_defs = [{"name": "advance"}]
        rc_defs = [{"name": "fail"}, {"name": "blame"}]
        self.h.file_reader.tool_definitions = fr_defs
        self.h.file_editor.tool_definitions = fe_defs
        self.h.guide_delivery.tool_definitions = gd_defs
        self.h.run_control.tool_definitions = rc_defs
        result = self.h.sandbox.get_tool_definitions()
        self.assertEqual(result, fr_defs + fe_defs + gd_defs + rc_defs)
        self.assertEqual(self.h.file_reader.calls, [("get_tool_definitions", ())])
        self.assertEqual(self.h.file_editor.calls, [("get_tool_definitions", ())])
        self.assertEqual(self.h.guide_delivery.calls, [("get_tool_definitions", ())])
        self.assertEqual(self.h.run_control.calls, [("get_tool_definitions", ())])


class TestStepMode(unittest.TestCase):
    def setUp(self) -> None:
        self.h = _SandboxHarness(_config(guide="guide.txt", step_sections_enabled=True))

    def test_read_guide_in_step_mode_fails(self) -> None:
        result = self.h.sandbox.read_file("guide.txt")
        self.assertIsInstance(result, ToolFailure)
        self.assertEqual(self.h.file_reader.calls, [])

    def test_read_other_file_in_step_mode_delegates(self) -> None:
        self.h.sandbox.read_file("a.txt")
        self.assertEqual(self.h.file_reader.calls, [("read_file", ("a.txt", False))])

    def test_search_guide_in_step_mode_fails(self) -> None:
        result = self.h.sandbox.search_files("guide.txt", "x")
        self.assertIsInstance(result, ToolFailure)
        self.assertEqual(self.h.file_reader.calls, [])

    def test_read_guide_not_in_step_mode_delegates(self) -> None:
        h = _SandboxHarness(_config(guide="guide.txt", step_sections_enabled=False))
        h.sandbox.read_file("guide.txt")
        self.assertEqual(h.file_reader.calls, [("read_file", ("guide.txt", False))])


class TestSmoke(unittest.TestCase):
    def test_reads_real_file_through_default_wiring(self) -> None:
        reader = _StubFileReader()
        reader.read_result = [ToolResult(content="hello", supersedes=False)]

        config = _config(
            file_mappings={"a.txt": "/ws/a.txt"},
            readable_paths=["a.txt"],
            writable_paths=[],
        )
        sandbox = SandboxImpl(
            config=config,
            make_file_reader=lambda frc: reader,
            make_file_editor=lambda fec, fr: _StubFileEditor(),
            make_guide_delivery=lambda gdc: _StubGuideDelivery(),
            make_run_control=lambda rcc, fr, fe, gd: _StubRunControl(),
        )
        result = sandbox.read_file("a.txt")
        self.assertIn("hello", str(result[0].content))

if __name__ == "__main__":
    unittest.main()
