from typing import Sequence, Optional, List, Any
from .tool_provider import Tool, ToolMetadata, ToolArguments, ToolOutcome, ToolResult
from .file_reader import FileReader, FileReaderFactory, FileReaderConfig, SessionStartRead
from .file_editor import FileEditor, FileEditorFactory, FileEditorConfig
from .guide_delivery import GuideDelivery, GuideDeliveryFactory, TaskGuide, Guide
from .run_control import RunController, RunControlFactory, RunControlConfig
from .sandbox import Sandbox, SandboxFactory, SandboxConfig, StartupInteraction


class SandboxFactoryImpl(SandboxFactory):
    def __init__(
        self,
        file_reader_factory: FileReaderFactory,
        file_editor_factory: FileEditorFactory,
        run_control_factory: RunControlFactory,
        guide_delivery_factory: Optional[GuideDeliveryFactory] = None,
    ) -> None:
        self.file_reader_factory = file_reader_factory
        self.file_editor_factory = file_editor_factory
        self.run_control_factory = run_control_factory
        self.guide_delivery_factory = guide_delivery_factory

    def create_sandbox(
        self,
        config: SandboxConfig,
    ) -> Sandbox:
        fr_cfg = FileReaderConfig(
            read_only_files=config.read_only_files,
            read_write_files=config.read_write_files,
            file_mappings=config.file_mappings,
            step_mode_guide=config.step_mode_guide_name,
            search_result_limit=config.search_result_limit,
        )
        fe_cfg = FileEditorConfig(
            read_write_files=config.read_write_files,
            file_mappings=config.file_mappings,
            templates=config.templates,
        )
        rc_cfg = config.run_control or RunControlConfig()

        file_reader = self.file_reader_factory.create_file_reader(fr_cfg)
        file_editor = self.file_editor_factory.create_file_editor(fe_cfg)
        run_control = self.run_control_factory.create_run_control(
            config=rc_cfg,
        )
        target_guide = config.guide
        guide_delivery = (
            self.guide_delivery_factory.create_guide_delivery(target_guide)
            if (self.guide_delivery_factory and target_guide)
            else None
        )

        return _SandboxImpl(
            file_reader=file_reader,
            file_editor=file_editor,
            run_control=run_control,
            guide_delivery=guide_delivery,
        )


class _SandboxImpl(Sandbox):
    def __init__(
        self,
        file_reader: FileReader,
        file_editor: FileEditor,
        run_control: RunController,
        guide_delivery: Optional[GuideDelivery] = None,
    ) -> None:
        self.file_reader = file_reader
        self.file_editor = file_editor
        self.run_control = run_control
        self.guide_delivery = guide_delivery

    def get_session_start_reads(self) -> Sequence[SessionStartRead]:
        return self.file_reader.get_session_start_reads()

    def get_startup_interaction(self) -> StartupInteraction:
        interactions: List[ToolResult] = list(self.get_session_start_reads())
        if self.guide_delivery is not None:
            interactions.append(self.guide_delivery.get_summary_delivery())
        return interactions

    def materialize_startup_templates(self) -> None:
        self.file_editor.materialize_templates()

    def has_file_modifications(self) -> bool:
        return self.file_editor.has_file_modifications()

    def get_tools(self) -> Sequence[Tool]:
        tools: List[Tool] = []
        tools.extend(self.file_reader.get_tools())
        tools.extend(self.file_editor.get_tools())
        control_tools = self.run_control.get_tools()
        if self.guide_delivery is not None:
            wrapped_tools: List[Tool] = []
            for t in control_tools:
                if t.get_metadata().name == "advance":
                    class _AdvanceWrapper:
                        def __init__(self, adv: Tool, gd: GuideDelivery) -> None:
                            self._adv = adv
                            self._gd = gd

                        def get_metadata(self) -> ToolMetadata:
                            return self._adv.get_metadata()

                        def execute(self, arguments: ToolArguments) -> ToolOutcome:
                            if self._gd.has_steps_remaining():
                                next_step = self._gd.advance_step(verification_passed=True)
                                if next_step is not None:
                                    return next_step
                            return self._adv.execute(arguments)

                    wrapped_tools.append(_AdvanceWrapper(t, self.guide_delivery))
                else:
                    wrapped_tools.append(t)
            tools.extend(wrapped_tools)
        else:
            tools.extend(control_tools)
        return tools
