<!-- Dependencies (md files to read alongside this one):
  - runner_logger_impl.md
  - build_graph_storage_impl.md
  - build_message_store_impl.md
  - dag_cleaner_impl.md
  - agent_node_cleaner_asm.md
  - bazel_node_id_utils_impl.md
  - manifest_node_loader_impl.md
  - build_runner_impl.md
  - build_agent_config.md
  - build_runner.md
-->

# Implementation LLS: build_asm

## Data Types
```python
from typing import Optional
from build_runner_impl import BuildRunnerImpl
from build_graph_storage_impl import BuildGraphStorageImpl
from build_message_store_impl import BuildMessageStoreImpl
from bazel_node_id_utils_impl import BazelNodeIdUtilsImpl
from manifest_node_loader_impl import ManifestLoaderImpl
from runner_logger_impl import RunnerLoggerImpl
from dag_cleaner_impl import DagCleanerImpl
from agent_node_cleaner_asm import AgentNodeCleanerAsm
from build_agent_config import ConfigTarget

class BuildAsm(BuildRunnerImpl):
    def __init__(self, config_target: Optional[ConfigTarget] = None, workspace_root: str = "") -> None: ...
```

## Composition

- BazelNodeIdUtilsImpl
- BuildMessageStoreImpl
- BuildGraphStorageImpl
- ManifestLoaderImpl
- RunnerLoggerImpl
- DagCleanerImpl
- AgentNodeCleanerAsm
- BuildRunnerImpl

## Behavioral Description

- `BuildAsm` instantiates `BazelNodeIdUtilsImpl`, `BuildMessageStoreImpl`, `BuildGraphStorageImpl`, `ManifestLoaderImpl`, `RunnerLoggerImpl`, `DagCleanerImpl`, and `AgentNodeCleanerAsm` directly within `__init__` before calling `super().__init__()`.
- Passes `workspace_root` and `BazelNodeIdUtilsImpl` to `BuildMessageStoreImpl` and passes the resulting store instance to `BuildGraphStorageImpl`.
- Passes `BazelNodeIdUtilsImpl` to `ManifestLoaderImpl` to parse manifests and populate `BuildGraphStorageImpl`.
- Passes `BuildGraphStorageImpl` to `AgentNodeCleanerAsm`.
- Configures `RunnerLoggerImpl` with the workspace transcript path.
- Executes topological cleaning passes across dirty workspace nodes.

## Invariants

- Implements no functionality beyond assembly.
- Sub-components are instantiated internally and never passed as constructor arguments.
