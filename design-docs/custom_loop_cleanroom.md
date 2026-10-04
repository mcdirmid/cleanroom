# Custom Loop Cleanroom: In-Process Autonomous Agent Execution

## 1. Executive Summary & System Context

**Custom Loop Cleanroom** (Option 1) is Cleanroom's headless, in-process autonomous agent execution engine. Powered directly by the native OpenAI API and coordinated through topological build graphs in Bazel, it provides a hermetic, fully automated environment for multi-node DAG cleaning passes without requiring interactive IDE sessions or complex subagent orchestrators.

```
                     ┌──────────────────────────────────────────────┐
                     │            Bazel Invocation Target           │
                     │  bazel run //...:<target>_clean              │
                     └──────────────────────┬───────────────────────┘
                                            │
                                            ▼
                     ┌──────────────────────────────────────────────┐
                     │     bazel_openai_loop_asm (Root Assembly)    │
                     │  - Closes all domain & lifecycle interfaces  │
                     │  - Loads manifest, models, & credentials     │
                     └──────────────────────┬───────────────────────┘
                                            │
                                            ▼
                     ┌──────────────────────────────────────────────┐
                     │          Loop Cleaner (loop_cleaner)         │
                     │  - Computes dirty acyclic subgraph           │
                     │  - Traverses nodes in topological order      │
                     └──────────────┬───────────────────────────────┘
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────────┐
       │             Node Cleaner (loop_node_cleaner)                │
       │  - Initializes Agent Session per Node                       │
       │  - Mounts Role-Restricted Tools (Read, Edit, Run)           │
       │  - Injects Node Task Prompt & Double-Blind Boundaries       │
       └────────────────────────────┬────────────────────────────────┘
                                    │
                                    ▼
       ┌─────────────────────────────────────────────────────────────┐
       │             Agent Turn Driver (loop_driver)                 │
       │  - Multi-turn model requests via OpenAI API                 │
       │  - Correlates tool responses with tool call IDs             │
       │  - Loop Guard: prevents runaway repetition & idle loops     │
       │  - Evaluates Termination Outcomes                           │
       └─────────────────────────────────────────────────────────────┘
```

### Primary Use Cases
1. **Headless Continuous Integration & Nightly Runs**: Unattended verification and regeneration of specs, code, and tests across entire packages.
2. **Deterministic Batch Cleaning**: Propagating upstream contract changes across reverse dependencies in strictly topological order.
3. **High Token Efficiency**: Executes directly against foundation model APIs with minimal prompt overhead, precise message compaction, and zero IDE protocol bloat.

---

## 2. Architectural Subsystems & Component Topology

The Custom Loop Cleanroom is partitioned across modular Cleanroom packages under [`update_with_ai/parts/`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts):

### 2.1 The Root System Assembly: `bazel_openai_loop_asm`
Located in [`update_with_ai/parts/systems/lib/bazel_openai_loop_asm.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/systems/lib/bazel_openai_loop_asm.py), this root assembly closes all internal subsystem interfaces into an executable runtime graph:
- **`bazel_asm`**: Closes build graph loading, target parsing, file path resolution, and graph persistence.
- **`bazel_loop_impl`**: Implements the outer [`loop`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/high/loop.md) interface, driving cleaning passes across target subgraphs.
- **`bazel_openai_config_impl`**: Resolves model credentials, temperature, context limits, and timeout configurations.
- **`dag_asm`**: Provides the foundational acyclic graph model, dirty-state tracking, and message delivery.
- **`loop_asm`**: Implements turn execution, conversation buffers, repetition guards, and node cleaning.
- **`sandbox_asm`**: Implements file reading, file editing, guide delivery, run control, and tool provider registries.
- **`runner_logger_impl`**: Streams unbuffered transcripts, turn counters, and diagnostic traces to stdout and logfiles.

### 2.2 Topological Execution: `LoopCleaner` & `LoopNodeCleaner`
Autonomous cleaning is fundamentally a **dependency-first topological traversal**:
1. **Subgraph Resolution**: Given a target node (e.g. `//parts/spec:spec_linker_test`), `LoopCleaner` identifies all dirty nodes in the directed acyclic subgraph rooted at the target.
2. **Topological Order**: Dependencies are guaranteed to be clean before any dependent node is executed. If a specification node is dirty, it is cleaned first; only then are implementation or test nodes cleaned.
3. **Atomic State Transitions**: When a node completes cleaning, `Loop` broadcasts change notifications to all reverse dependencies, marking them dirty for subsequent passes.

### 2.3 Turn Management: `LoopDriver` & `OpenAIDriver`
Each node's agent session is executed by `LoopDriver` ([`update_with_ai/parts/loop/lib/loop_driver.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/lib/loop_driver.py)):
- **Turn Loop**: Formats conversation messages, invokes the language model via the OpenAI API client, and parses model decisions into tool calls.
- **Tool Dispatch**: Maps tool calls by name to installed tools in the session's `ToolManager`, executes them, and appends the result correlated with the originating `tool_call_id`.
- **Termination Outcomes**: The model signals completion or failure via explicit run control tools (`finish_turn`, `fail_turn`).

### 2.4 Safety Guardrails: `LoopGuard`
Autonomous loops risk getting stuck in repetitive loops or burning quota on hallucinated tool parameters. `LoopGuard` ([`update_with_ai/parts/loop/lib/loop_guard.py`](file:///Users/seanmcdirmid/projects/cleanroom/update_with_ai/parts/loop/lib/loop_guard.py)) enforces three active defenses:
1. **Runaway Repetition Detection**: Tracks recent tool calls and parameter hashes. If an agent repeats identical failing tool calls, `LoopGuard` injects a corrective warning into the conversation. If repetition continues, it halts execution immediately.
2. **Toolless Response Recovery**: If an agent emits conversational prose without making tool calls, `LoopGuard` injects a reminder that session progress requires executing tools, forcing the model back into action.
3. **Hard Turn Limits**: Enforces a strict maximum turn cap per node, preventing runaway token consumption.

---

## 3. Tool Sandboxing & Double-Blind Confinement

Even in a headless loop, Cleanroom's strict **double-blind specification and testing guarantees** are enforced:

### 3.1 Role Confinement
The node cleaner injects role-specific guides and mounts only authorized tools:
- **Specification Role (HLS / Planning / LLS / Grounding)**:
  - Tools: View File, Edit Spec, Run Spec Linters/Compilers (`grounding_tool.py`).
  - Blind to: Implementation details or ad-hoc workarounds.
- **Implementation Role (Library Code)**:
  - Tools: View File (read-only specs), Edit Implementation (`lib/*.py`), Run Linters.
  - Blind to: Test source code (`tests/*_test.py`).
- **Test Role (Unit Tests)**:
  - Tools: View File (read-only specs), Edit Tests (`tests/*_test.py`), Run Bazel Tests (`bazel test`).
  - Blind to: Implementation source code (`lib/*.py`). Must write tests derived strictly from specification contracts.

### 3.2 Bazel Test Execution Flags
When the test role runs unit tests, test commands are executed with Cleanroom's mandatory flags:
```bash
bazel test <target> --test_output=errors --test_timeout=100 --noshow_progress --noshow_loading_progress
```
This guarantees hermetic evaluation, fast failure reporting, and clean transcript capture.

---

## 4. Invocation & Workflow

### 4.1 Bazel Target Execution
Custom loop runs are executed directly through Bazel:
```bash
# Clean dirty dependencies and the target node
bazel run //update_with_ai/parts/systems/bazel_openai_loop_asm:<target>_clean

# Propose an intentional change and propagate it
bazel run //update_with_ai/parts/systems/bazel_openai_loop_asm:<target>_change
```

### 4.2 Comparison with Subagentless Workspaces (Option 3)
| Characteristic | Option 1: Custom Headless Loop | Option 3: Subagentless Workspaces |
| :--- | :--- | :--- |
| **Interface** | CLI / Headless stdout logs | Interactive Antigravity Chat UI |
| **Model Backend** | OpenAI API Client | Antigravity / Google One Ultra Model |
| **Concurrency** | Sequential topological node cleaning | Parallel human-in-the-loop chat workspaces |
| **Best For** | CI/CD, batch processing, regression cleaning | Interactive feature authoring, architectural redesign |
| **Double-Blind Isolation** | Session-level tool & prompt filtering | OS-level `chmod 444` mount isolation |

---

## 5. Summary

The Custom Loop Cleanroom provides a robust, zero-dependency, automated execution pipeline. By embedding DAG dependency management, topological traversal, repetitive loop guards, and role-confined tool sandboxing into an in-process Python loop, it provides reliable unattended Cleanroom development.
