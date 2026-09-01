# Toward a Rigorous Ontology for High-Level Specifications

## 1. The Core Problem: The "Generic Term" Trap

Currently, high-level specifications (HLS) treat all concepts as flat natural-language "Terms".
Under this model:
- `tool definition` is just a prose term.
- `tool result` is just a prose term.
- `read-only file` is just a prose term.
- `virtual name` is just a prose term.

Because everything is a flat "term" defined in free-form English:
1. **No Typing or Structural Role**: There is no distinction between:
   - A **Data Type / Record Shape** (e.g. `ToolDefinition`, `ToolResult`, `PresentedToolResult`).
   - An **Entity Classification / Partition** (e.g. `read-only file` vs `read-write file`).
   - A **Protocol / Interface Capability** (e.g. `ToolProvider` as a capability to supply definitions and execute calls).
   - An **Operational State / Mode** (e.g. `step mode`, `feedback pending`).
2. **Missing Wiring Semantics**: An interface says "Provides tool definitions and executes tool calls", but there is no structural mechanism specifying:
   - Is `tool_provider` an abstract capability/protocol that other modules implement?
   - Or is it a concrete registry that other modules contribute tools into?
   - How does `file_reader` "install" or "provide" its `read_file` and `search_files` tools into the tool surface?

---

## 2. Re-Examining Root Abstractions: What is `tool_provider`?

Let us dissect `tool_provider.md`. What are the fundamental entities it actually defines?

### A. Data Types (Values & Structures)
These are concrete domain data shapes exchanged across boundaries:
- `ToolDefinition`: A declarative schema defining a tool name, parameters, and description for the model.
- `ToolCall`: An invocation requested by the model naming a tool and its argument dictionary.
- `ToolResult`: The execution outcome containing content, supersession flag, and optional note.
- `PresentedToolResult`: A `ToolResult` attributed with the `ToolCall` name and arguments.
- `Signal`: Execution flow control outcome (`Continue`, `TerminateSuccess(value)`, `TerminateFailure(reason)`, `ToolFailure(message)`).

### B. Capabilities / Protocols
- `ToolExecutor` / `ToolSurface`: An interface with the capability to:
  1. `describe_tools() -> list[ToolDefinition]`
  2. `execute_tool(call: ToolCall) -> Signal | ToolResult`

### C. The Composition Model (How Tools are Contributed)
How does `file_reader` relate to `tool_provider`?
There are two distinct architectural concepts:
1. **A Component that Provides Tools (`ToolContributor`)**:
   `file_reader` defines two specific tools (`read_file`, `search_files`).
   It provides their `ToolDefinition` schemas and executes calls matching those names.
2. **A Tool Aggregator / Facade (`ToolSurface` / `Sandbox`)**:
   `sandbox` aggregates multiple tool contributors (`file_reader`, `file_editor`, `guide_delivery`, `run_control`) into a single unified `ToolExecutor` for the `agent_loop`.

---

## 3. Proposal for a Structured HLS Ontology

Instead of a flat `## Terms` section containing arbitrary nouns, an HLS specification should structure its ontology into distinct ontological categories:

```markdown
# component_name

## Ontology

### Types
- `ToolDefinition`: a declarative schema (name, description, parameter schemas) describing a callable tool.
- `ToolCall`: an invocation request specifying a tool name and argument mapping.
- `ToolResult`: a successful execution payload (content, note, supersession flag).
- `ToolFailure`: an execution rejection signal carrying recovery guidance for the model.

### Partitions
- `read-only file`: workspace file permitted for plain reads; edits prohibited.
- `read-write file`: workspace file permitted for line-numbered reads and edits.

### State & Scopes
- `Session`: the lifecycle scope bounded by the agent run start and termination.
- `Active Line View`: the transient per-file state established by a line-numbered read.

### Contracts & Roles
- `ToolContributor`: an interface that declares a set of `ToolDefinition`s and handles their execution.
- `ToolDispatcher`: a router that delegates `ToolCall`s to the appropriate `ToolContributor`.
```

---

## 4. Key Questions for Rethinking HLS

1. **Should HLS formally distinguish Data Types from Behavioral Partitions and Roles?**
   - If `ToolDefinition` is declared under `### Types`, downstream LLS can automatically map it to a type alias or dataclass without ambiguity.
   - If `read-only file` is declared under `### Partitions`, the HLS audit can enforce that `**Inputs**` declares the collection defining that partition.

2. **How should Tool Contribution be modeled?**
   - Is `file_reader` a `ToolContributor` that exports tool schemas and execution handlers?
   - Or is `file_reader` a pure file library, and an adapter/executor creates the tools?

3. **How does this eliminate grounding bugs?**
   - By categorizing every term into its ontological role (Type, Partition, State, Role), the rules for grounding, input sourcing, and failure handling become exact and verifiable.
