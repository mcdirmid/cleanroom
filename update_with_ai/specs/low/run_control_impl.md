<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
  - virtual_file_name.md
  - dag_storage.md
  - dag_node_cleaner.md
  - change_summary_validator.md
  - run_control.md
-->

# Implementation LLS: run_control_impl

## Data Types
```python
from typing import Optional
from dag_node_cleaner import ChangeMessage, FeedbackMessage
from change_summary_validator import ChangeValidator
from run_control import RunController, RunControlFactory, RunControlConfig

class _RunControllerImpl(RunController):
    def __init__(self, config: RunControlConfig, change_validator: Optional[ChangeValidator] = None) -> None: ...

class RunControlFactoryImpl(RunControlFactory):
    def __init__(self) -> None: ...
```

## Behavioral Description

- `RunControlFactoryImpl.create_run_control` constructs a `RunController` configured with verification commands, dependency blame targets, and a `ChangeValidator`.
- The `advance` tool specifies metadata with the name `advance` and accepts an optional change summary parameter.
- The `fail` tool specifies metadata with the name `fail` and accepts an explanation parameter.
- The `blame` tool specifies metadata with the name `blame` and accepts target and explanation parameters.
- Executing the `advance` tool runs configured verification checks; advancing without modifying workspace files and without passing verification checks produces a `ToolFailure` with feedback and prevents termination.
- When workspace file modifications occurred, the `advance` tool requires a change summary validated by a `ChangeValidator` within configured length bounds.
- Executing the `advance` tool produces a `TerminationOutcome` carrying a `ChangeMessage` only when workspace files were modified, and without a `ChangeMessage` when unmodified and verification passed.
- Executing the `fail` tool produces a `TerminationOutcome` communicating that the run failed.
- Executing the `blame tool` resolves the blamed `VirtualFileName` to its owning dependency `NodeId` and forms a `TerminationOutcome` carrying a `FeedbackMessage`.
- Executing the `blame tool` with an invalid target produces a `ToolFailure` listing all valid blame targets.

## Invariants

- Termination tools emit terminal outcomes that conclude the session.
- Advancing requires either validated file modifications or passing verification checks.
- Change messages are emitted only when workspace files were modified.
- Invalid blame attempts list all valid configured blame targets.
