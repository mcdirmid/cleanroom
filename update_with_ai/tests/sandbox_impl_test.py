"""Tests for sandbox_impl derived from LLS."""

import unittest
from typing import Sequence, Optional
from lib.tool_provider import Tool, ToolMetadata, ToolResult, ToolOutcome, ToolArguments
from lib.file_reader import FileReader, FileReaderFactory, FileReaderConfig, SessionStartRead
from lib.file_editor import FileEditor, FileEditorFactory, FileEditorConfig
from lib.run_control import RunController, RunControlFactory, RunControlConfig
from lib.guide_delivery import GuideDelivery, GuideDeliveryFactory, StepDelivery, TaskGuide, StepSection
from lib.sandbox import SandboxConfig
from lib.sandbox_impl import SandboxFactoryImpl


class MockFileReader(FileReader):
    def get_read_tool(self) -> Tool:
        class _T:
            def get_metadata(self) -> ToolMetadata:
                return ToolMetadata("read_file", "Read file", {})
            def execute(self, a: ToolArguments) -> ToolOutcome:
                return ToolResult("content")
        return _T()

    def get_search_tool(self) -> Tool:
        class _T:
            def get_metadata(self) -> ToolMetadata:
                return ToolMetadata("search_files", "Search files", {})
            def execute(self, a: ToolArguments) -> ToolOutcome:
                return ToolResult("search matches")
        return _T()

    def get_session_start_reads(self) -> Sequence[SessionStartRead]:
        return [SessionStartRead(content="Initial read")]

    def sanitize_paths(self, text: str) -> str:
        return text

    def get_tools(self) -> Sequence[Tool]:
        return [self.get_read_tool(), self.get_search_tool()]


class MockFileReaderFactory(FileReaderFactory):
    def __init__(self, reader: FileReader) -> None:
        self.reader = reader

    def create_file_reader(self, config: FileReaderConfig) -> FileReader:
        return self.reader


class MockFileEditor(FileEditor):
    def __init__(self) -> None:
        self.templates_materialized = False
        self.modified = False

    def get_replacement_tool(self) -> Tool:
        class _T:
            def get_metadata(self) -> ToolMetadata:
                return ToolMetadata("replace", "Replace text", {})
            def execute(self, a: ToolArguments) -> ToolOutcome:
                return ToolResult("replaced")
        return _T()

    def get_line_update_tool(self) -> Tool:
        class _T:
            def get_metadata(self) -> ToolMetadata:
                return ToolMetadata("update_lines", "Update lines", {})
            def execute(self, a: ToolArguments) -> ToolOutcome:
                return ToolResult("updated")
        return _T()

    def materialize_templates(self) -> None:
        self.templates_materialized = True

    def has_file_modifications(self) -> bool:
        return self.modified

    def get_tools(self) -> Sequence[Tool]:
        return [self.get_replacement_tool(), self.get_line_update_tool()]


class MockFileEditorFactory(FileEditorFactory):
    def __init__(self, editor: FileEditor) -> None:
        self.editor = editor

    def create_file_editor(self, config: FileEditorConfig) -> FileEditor:
        return self.editor


class MockRunController(RunController):
    def __init__(self) -> None:
        self.advance_executed = False

    def get_advance_tool(self) -> Tool:
        class _T:
            def __init__(self, parent: MockRunController) -> None:
                self.parent = parent
            def get_metadata(self) -> ToolMetadata:
                return ToolMetadata("advance", "Advance pass", {})
            def execute(self, a: ToolArguments) -> ToolOutcome:
                self.parent.advance_executed = True
                return ToolResult("advanced by controller")
        return _T(self)

    def get_fail_tool(self) -> Tool:
        class _T:
            def get_metadata(self) -> ToolMetadata:
                return ToolMetadata("fail", "Fail run", {})
            def execute(self, a: ToolArguments) -> ToolOutcome:
                return ToolResult("failed")
        return _T()

    def get_blame_tool(self) -> Optional[Tool]:
        return None

    def get_tools(self) -> Sequence[Tool]:
        return [self.get_advance_tool(), self.get_fail_tool()]


class MockRunControlFactory(RunControlFactory):
    def __init__(self, controller: RunController) -> None:
        self.controller = controller

    def create_run_control(
        self,
        config: RunControlConfig,
        verification_fn: Optional[object] = None,
        workspace_dirty_check_fn: Optional[object] = None,
    ) -> RunController:
        return self.controller


class SandboxImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.dummy_config = SandboxConfig(
            file_mappings={},
            read_only_files=[],
            read_write_files=[],
            templates={},
        )

    def test_tool_aggregation_and_dispatch(self) -> None:
        """Tests CUJ for aggregating tool definitions from sub-providers.

        Checks postconditions: sandbox exposes read, search, edit, and control tools.
        """
        reader = MockFileReader()
        editor = MockFileEditor()
        controller = MockRunController()
        factory = SandboxFactoryImpl(
            file_reader_factory=MockFileReaderFactory(reader),
            file_editor_factory=MockFileEditorFactory(editor),
            run_control_factory=MockRunControlFactory(controller),
        )
        sandbox = factory.create_sandbox(self.dummy_config)

        tools = sandbox.get_tools()
        names = {t.get_metadata().name for t in tools}
        self.assertIn("read_file", names)
        self.assertIn("search_files", names)
        self.assertIn("replace", names)
        self.assertIn("update_lines", names)
        self.assertIn("advance", names)
        self.assertIn("fail", names)

    def test_session_start_reads_and_templates(self) -> None:
        """Tests CUJ for startup reads and template materialization."""
        reader = MockFileReader()
        editor = MockFileEditor()
        controller = MockRunController()
        factory = SandboxFactoryImpl(
            file_reader_factory=MockFileReaderFactory(reader),
            file_editor_factory=MockFileEditorFactory(editor),
            run_control_factory=MockRunControlFactory(controller),
        )
        sandbox = factory.create_sandbox(self.dummy_config)

        reads = sandbox.get_session_start_reads()
        self.assertEqual(len(reads), 1)
        self.assertEqual(reads[0].content, "Initial read")

        sandbox.materialize_startup_templates()
        self.assertTrue(editor.templates_materialized)

    def test_has_file_modifications_delegation(self) -> None:
        """Tests that has_file_modifications delegates directly to the underlying FileEditor."""
        reader = MockFileReader()
        editor = MockFileEditor()
        controller = MockRunController()
        factory = SandboxFactoryImpl(
            file_reader_factory=MockFileReaderFactory(reader),
            file_editor_factory=MockFileEditorFactory(editor),
            run_control_factory=MockRunControlFactory(controller),
        )
        sandbox = factory.create_sandbox(self.dummy_config)

        editor.modified = False
        self.assertFalse(sandbox.has_file_modifications())
        editor.modified = True
        self.assertTrue(sandbox.has_file_modifications())

    def test_startup_interaction_and_guide_advancement(self) -> None:
        """Tests CUJs for startup interaction and step-by-step guide interception on advance."""
        class MockStepGuideDelivery(GuideDelivery):
            def __init__(self) -> None:
                self.steps = ["Step 1 instructions", "Step 2 instructions"]
            def get_summary_delivery(self) -> StepDelivery:
                return StepDelivery(content="Guide Summary")
            def advance_step(self, verification_passed: bool) -> Optional[StepDelivery]:
                if self.steps:
                    return StepDelivery(content=self.steps.pop(0))
                return None
            def has_steps_remaining(self) -> bool:
                return len(self.steps) > 0

        class MockStepGuideDeliveryFactory(GuideDeliveryFactory):
            def __init__(self, delivery: GuideDelivery) -> None:
                self.delivery = delivery
            def create_guide_delivery(self, guide: TaskGuide) -> GuideDelivery:
                return self.delivery

        reader = MockFileReader()
        editor = MockFileEditor()
        controller = MockRunController()
        guide_delivery = MockStepGuideDelivery()
        guide = TaskGuide(summary="Guide Summary", sections=[StepSection(0, "S1", "Step 1"), StepSection(1, "S2", "Step 2")])
        factory = SandboxFactoryImpl(
            file_reader_factory=MockFileReaderFactory(reader),
            file_editor_factory=MockFileEditorFactory(editor),
            run_control_factory=MockRunControlFactory(controller),
            guide_delivery_factory=MockStepGuideDeliveryFactory(guide_delivery),
        )
        cfg = SandboxConfig(
            file_mappings={},
            read_only_files=[],
            read_write_files=[],
            templates={},
            guide=guide,
        )
        sandbox = factory.create_sandbox(cfg)

        # 1. Test get_startup_interaction combines session-start reads and guide summary
        interactions = sandbox.get_startup_interaction()
        self.assertEqual(len(interactions), 2)
        self.assertEqual(interactions[0].content, "Initial read")
        self.assertEqual(interactions[1].content, "Guide Summary")

        # 2. Test advance tool intercepts when guide has steps remaining
        tools = sandbox.get_tools()
        advance_tool = next(t for t in tools if t.get_metadata().name == "advance")

        # Step 1 interception
        res1 = advance_tool.execute({})
        self.assertIsInstance(res1, StepDelivery)
        self.assertEqual(res1.content, "Step 1 instructions")
        self.assertFalse(controller.advance_executed)

        # Step 2 interception
        res2 = advance_tool.execute({})
        self.assertIsInstance(res2, StepDelivery)
        self.assertEqual(res2.content, "Step 2 instructions")
        self.assertFalse(controller.advance_executed)

        # Terminal delegation to underlying controller
        res_final = advance_tool.execute({})
        self.assertEqual(res_final.content, "advanced by controller")
        self.assertTrue(controller.advance_executed)


if __name__ == "__main__":
    unittest.main()
