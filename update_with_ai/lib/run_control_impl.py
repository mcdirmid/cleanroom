"""Run control implementation with advance, fail, and blame tools."""

from typing import Optional, Callable, Tuple, Sequence, List, TypeAlias
from .tool_provider import (
    Tool,
    ToolMetadata,
    ToolResult,
    ToolFailure,
    TerminationOutcome,
    ToolOutcome,
    ToolArguments,
)
from .run_control import RunController, RunControlFactory, RunControlConfig
from .dag_node_cleaner import ChangeMessage, FeedbackMessage
from .change_summary_validator import ChangeValidator

VerificationResult: TypeAlias = Tuple[bool, str]
VerificationFn: TypeAlias = Callable[[], VerificationResult]


class RunControlFactoryImpl(RunControlFactory):
    def __init__(self, change_validator: Optional[ChangeValidator] = None) -> None:
        self._change_validator = change_validator

    def create_run_control(
        self,
        config: RunControlConfig,
        verification_fn: Optional[VerificationFn] = None,
        workspace_dirty_check_fn: Optional[Callable[[], bool]] = None,
        change_validator: Optional[ChangeValidator] = None,
    ) -> RunController:
        validator = change_validator if change_validator is not None else self._change_validator
        return _RunControllerImpl(
            config=config,
            verification_fn=verification_fn,
            workspace_dirty_check_fn=workspace_dirty_check_fn,
            change_validator=validator,
        )


class _RunControllerImpl(RunController):
    def __init__(
        self,
        config: RunControlConfig,
        verification_fn: Optional[VerificationFn] = None,
        workspace_dirty_check_fn: Optional[Callable[[], bool]] = None,
        change_validator: Optional[ChangeValidator] = None,
    ) -> None:
        self.config = config
        self.verification_fn = verification_fn
        self.workspace_dirty_check_fn = workspace_dirty_check_fn
        self.change_validator = change_validator

    def get_advance_tool(self) -> Tool:
        class AdvanceTool:
            def __init__(self, parent: _RunControllerImpl) -> None:
                self.parent = parent

            def get_metadata(self) -> ToolMetadata:
                return ToolMetadata(
                    name="advance",
                    purpose="Verify session state and advance/complete",
                    parameters_schema={"change_summary": "string"},
                )

            def execute(self, arguments: ToolArguments) -> ToolOutcome:
                summary = str(arguments.get("change_summary", "")).strip()
                if self.parent.change_validator is not None:
                    err = self.parent.change_validator.validate_change_summary(summary, [])
                    if err:
                        return ToolFailure(feedback=err)

                is_dirty = bool(self.parent.workspace_dirty_check_fn and self.parent.workspace_dirty_check_fn())
                has_verification = self.parent.verification_fn is not None

                if is_dirty:
                    if self.parent.config.change_summary_required:
                        if not summary:
                            return ToolFailure(
                                feedback="Change summary is required when files were modified."
                            )
                elif not has_verification and self.parent.change_validator is None and not summary:
                    return ToolFailure(
                        feedback="No workspace files were modified and no verification check was configured. Please implement the requested changes before advancing."
                    )

                if has_verification and self.parent.verification_fn:
                    ok, msg = self.parent.verification_fn()
                    if not ok:
                        return ToolFailure(feedback=f"Verification failed: {msg}")
                return TerminationOutcome(content="Advanced and completed")

        return AdvanceTool(self)

    def get_fail_tool(self) -> Tool:
        class FailTool:
            def __init__(self, parent: _RunControllerImpl) -> None:
                self.parent = parent

            def get_metadata(self) -> ToolMetadata:
                return ToolMetadata(
                    name="fail",
                    purpose="Terminate run in failure",
                    parameters_schema={"explanation": "string"},
                )

            def execute(self, arguments: ToolArguments) -> ToolOutcome:
                return TerminationOutcome(
                    content=str(arguments.get("explanation", "") or arguments.get("reason", "Failed"))
                )

        return FailTool(self)

    def get_blame_tool(self) -> Optional[Tool]:
        if not self.config.blame_targets:
            return None

        class BlameTool:
            def __init__(self, parent: _RunControllerImpl) -> None:
                self.parent = parent

            def get_metadata(self) -> ToolMetadata:
                return ToolMetadata(
                    name="blame",
                    purpose="Attribute failure to dependency file",
                    parameters_schema={"target": "string", "explanation": "string"},
                )

            def execute(self, arguments: ToolArguments) -> ToolOutcome:
                target_file = str(arguments.get("target", "") or arguments.get("file_name", ""))
                targets = self.parent.config.blame_targets or {}
                if target_file not in targets:
                    return ToolFailure(
                        feedback=f"Invalid blame target {target_file}. Valid: {list(targets.keys())}"
                    )
                dep_node = targets[target_file]
                return TerminationOutcome(
                    content=f"Blamed {dep_node} via {target_file}"
                )

        return BlameTool(self)

    def get_tools(self) -> Sequence[Tool]:
        tools: List[Tool] = [self.get_advance_tool(), self.get_fail_tool()]
        blame = self.get_blame_tool()
        if blame:
            tools.append(blame)
        return tools
