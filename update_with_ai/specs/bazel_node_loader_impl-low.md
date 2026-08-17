<!-- Dependencies (md files to read alongside this one):
  - bazel_node_loader-low.md
  - tool_provider-low.md
  - agent_loop-low.md
-->

# Implementation LLS: bazel_node_loader_impl

## Data Types

```python
from bazel_node_loader import BazelNodeLoader, BazNode
from tool_provider import ToolProvider, ToolExecutor
from agent_loop import AgentResult
```

```python
class BazNodeImpl(BazNode): ...
```

```python
class BazelNodeLoaderImpl(BazelNodeLoader): ...
```

`BazNodeImpl` extends the interface's `BazNode` data-class Protocol (which itself extends `ToolProvider`), adding implementation-internal state and implementing the tool-provider operations:
- **`get_tool_definitions`**: for each tool label declared in `tools`, dynamically loads the tool provider module via `importlib` (converting `//pkg:tool` to the module `pkg.tool`), calls `get_tool_definitions()` on it, and extends the result list.
- **`execute_tool`**: for each tool label in `tools`, loads the tool provider (if not already loaded) and calls `execute_tool(name, arguments)`, returning the first `ToolCallOutcome` produced. A tool call that no declared provider handles returns `ToolFailure("Tool {name} not found")`.
- **`run_prompt`** — `run_prompt(self, prompt: str, tool_executor: ToolExecutor) -> AgentResult`: gets the `agent_loop` (set externally as `_agent_loop`) and calls `run_agent(prompt=prompt, tools=self.get_tool_definitions(), tool_executor=tool_executor)`. Returns an `AgentResult`; if no agent loop is configured, returns a loop-failure result (`(error, [])`).

**Internal state** (implementation-internal, not exposed to interface consumers):
- `_tool_providers`: cache of loaded `ToolProvider` instances keyed by tool label (populated lazily on first use, so a tool provider is loaded at most once per node).
- `_dependency_nodes`: list of `BazNodeImpl` instances for each dependency, including silent dependencies (resolved at load time).
- `_agent_loop`: the agent loop used for running prompts (set externally after construction).

**Manifest fields** (static data from manifest, per the interface spec's `BazNode`):
- `label`, `prompt`, `tools`, `deps`, `silent_deps`, `srcs`, `silent_srcs`.

## Config

None — the implementation bundles no imported capabilities via Config (BazNode instances are constructed by the implementation); the agent loop used for prompt running is set externally on each node after construction (see Internal state).

**HLS Justification:** The implementation bundles no imported capabilities; the agent loop is externally configured.

## Behavioral Description

`BazelNodeLoaderImpl` (declared above) implements the `BazelNodeLoader` Protocol by constructing nodes from manifests and caching them by label.

- **`load_node`** — Loads a node from its manifest file (detected via runfiles). Constructs a `BazNodeImpl` with all manifest fields; tool providers are resolved lazily on first use and cached in `_tool_providers`. Caches the result by label on success. Returns `None` if the manifest does not exist. A manifest that cannot be deserialized raises an error; the cache is not populated (a node is cached only after successful deserialization).

- **`load_graph`** — Loads the root node and recursively loads its dependencies (declared and silent). Returns a mapping of labels to `BazNodeImpl` instances (root and all transitive deps, including silent deps).

- **`get_node_prompt`** — Returns the node's `prompt` if loaded (from cache or manifest), or `None` if the node does not exist.

**HLS Justification:** Loads manifests from runfiles and constructs node instances at runtime.

## Invariants

- Tools are loaded dynamically via `importlib` from the configured module path.
- Nodes are cached by label; repeated loads of the same label return the cached instance.
- Partial loads do not populate the cache; a node is cached only after successful deserialization.
- Invalid labels produce `None`, not a partial cache entry.
- Manifest file paths are derived deterministically from labels (e.g., `//pkg:target` → `pkg/target_manifest.json` in runfiles).

## Non-Concerns

- **Manifest resolution algorithm:** The exact mechanism for resolving a label to a manifest path (e.g., `RUNFILES_DIR`, `//pkg:target` → `pkg/target_manifest.json`) is implementation-specific.
- **Cache eviction policy:** Whether and when the cache evicts entries is unspecified.
- **T_tool resolution:** The implementation resolves `T_tool` (from `tool_provider`) to `str` in failure signals (`ToolFailure("Tool {name} not found")`).

