<!-- Dependencies (md files to read alongside this one):
  - build_runner_impl.md
  - build_agent_config.md
  - build_graph_storage_impl.md
  - build_agent_config_impl.md
  - agent_loop_impl.md
  - agent_node_clean_logic_impl.md
  - sandbox_impl.md
  - dag_cleaner_impl.md
-->

# Implementation LLS: build_asm

## Data Types
```python
from build_runner_impl import BuildRunnerImpl

class BuildAsm:
    def build(self) -> BuildRunnerImpl: ...
```

Constructed with no configuration: the concrete implementations are selected
here, at construction. `build` provides a configured interface-only
`BuildRunnerImpl` assembled through the factories wired here (see
Composition); the runner's operations create the components per call. This
assembly performs configuration and assembly only and is never tested.

## Composition

- BuildGraphStorageFileImpl (graph storage)
- BuildAgentConfigImpl (agent configuration loading)
- AgentLoopImpl (agent loop)
- AgentNodeCleanLogicImpl (clean logic)
- FileViewImpl (file machinery, wired into the sandbox)
- GuideDeliveryImpl (step-mode delivery, wired into the sandbox)
- RunControlImpl (verification and termination, wired into the sandbox)
- SandboxImpl (sandbox)
- DagCleanerImpl (DAG cleaning)

## Behavioral Description

- Assembles the concrete implementations at construction: the graph factory wraps `BuildGraphStorageFileImpl`; the clean-logic factory wraps `BuildAgentConfigImpl` (config-target selection, agent-configuration loading, and API-key resolution from the environment), `AgentLoopImpl`, `SandboxImpl`, and `AgentNodeCleanLogicImpl`, applying the configuration's sandbox gates to each sandbox it constructs; the DAG factory wraps `DagCleanerImpl` over the graph and the clean logic.
- `build` provides a fresh `BuildRunnerImpl` assembled through these factories; the runner's operations create the components per call.
- No functionality beyond configuration and assembly is performed; this assembly is never tested.

## Invariants

- The concrete implementations are selected here, at construction; the runner's operations never select components.
- No persistent state is held across calls: each `build` call assembles a fresh runner.

## Non-Concerns

- **Consumption:** how the assembled runner is used (entry points, generated wrappers) is unspecified here.
- **Selection policy:** the concrete implementations wired here are a default assembly; other selections may differ.
