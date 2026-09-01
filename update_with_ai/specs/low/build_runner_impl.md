<!-- Dependencies (md files to read alongside this one):
  - dag_storage.md
  - dag_cleaner.md
  - dag_node_cleaner.md
  - runner_logger.md
  - manifest_node_loader.md
  - build_runner.md
-->

# Implementation LLS: build_runner_impl

## Data Types
```python
from dag_storage import DagStorage
from dag_cleaner import DagCleaner
from dag_node_cleaner import NodeCleaner
from runner_logger import RunnerLogger
from manifest_node_loader import ManifestLoader
from build_runner import BuildRunner

class BuildRunnerImpl(BuildRunner):
    def __init__(
        self,
        storage: DagStorage,
        cleaner: DagCleaner,
        node_cleaner: NodeCleaner,
        logger: RunnerLogger,
        manifest_loader: ManifestLoader,
    ) -> None: ...
```

## Behavioral Description

- `BuildRunnerImpl` resolves target labels and loads workspace target graphs into `DagStorage` using `ManifestLoader`.
- Executes cleaning passes in topological order across the acyclic subgraph rooted at `root` using `DagCleaner`.
- Marking a node dirty injects a non-triggering check `ChangeMessage` with text set to `"check"`.
- Injecting feedback or broadcasting changes transmits caller-provided message content to target queues or reverse dependencies.
- Halts cleaning and returns a failing `BuildResult` if any node cleaning fails or a cycle is encountered.
- Logs execution events, cumulative token usage, and pass duration to standard output and transcript files using `RunnerLogger`.

## Invariants

- Cleanings execute sequentially per topological level.
- Node cleaning failure or graph cycle detection immediately halts the cleaning pass.
- When an agent session concludes, cumulative token usage and pass duration are logged.
