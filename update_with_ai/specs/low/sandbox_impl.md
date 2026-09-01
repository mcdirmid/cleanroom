<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
  - virtual_file_name.md
  - file_reader.md
  - file_editor.md
  - guide_delivery.md
  - run_control.md
  - sandbox.md
-->

# Implementation LLS: sandbox_impl

## Data Types
```python
from typing import Optional
from file_reader import FileReaderFactory
from file_editor import FileEditorFactory
from guide_delivery import GuideDeliveryFactory
from run_control import RunControlFactory
from sandbox import Sandbox, SandboxFactory, SandboxConfig

class _SandboxImpl(Sandbox):
    def __init__(self, config: SandboxConfig) -> None: ...

class SandboxFactoryImpl(SandboxFactory):
    def __init__(
        self,
        file_reader_factory: FileReaderFactory,
        file_editor_factory: FileEditorFactory,
        run_control_factory: RunControlFactory,
        guide_delivery_factory: Optional[GuideDeliveryFactory] = None,
    ) -> None: ...
```

## Behavioral Description

- `SandboxFactoryImpl.create_sandbox` constructs sub-components via sub-factories (`FileReaderFactory`, `FileEditorFactory`, `RunControlFactory`, and optional `GuideDeliveryFactory`) and aggregates them into a `Sandbox`.
- Composes all available tools provided by its `FileReader`, `FileEditor`, `RunController`, and optional `GuideDelivery`.
- Produces a startup interaction combining `read_file` tool results from session-start reads and an initial `advance` tool result from step delivery when progressive guide delivery is configured.
- Materializes startup templates for missing read-write files without overwriting existing workspace files.
- Dispatches tool executions to the corresponding underlying component using virtual file names.
- In step mode, executing the advance tool delivers the next step section from guide delivery upon passing verification before termination.
- Executing the advance tool with no step sections remaining concludes with a termination outcome upon passing verification and change summary checks.
- Provides queries indicating whether any workspace file modifications occurred during the session.

## Invariants

- Composed tools are exposed exclusively through virtual file name abstractions.
- Materializing templates never overwrites existing read-write files.
- Startup interactions deliver session-start reads before initial guide step deliveries.
- Step-mode advance executions deliver subsequent guide sections before terminating.
