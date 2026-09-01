# High-Level Specification Architecture & Design Guide

## 1. Core Architectural Pillars

A High-Level Specification (HLS) is an ordinary English, declarative specification defining domain concepts and observable behaviors without code syntax, formal DSLs, or low-level implementation details. It serves as the single source of truth for design, low-level specifications (LLS), implementations, and test suites.

### Document Structure & Closed Section Inventory

Every specification file has a unified, closed section inventory:
1. `## Purpose`: Explains the engineering rationale, motivating problem, and failure modes being prevented. May include architectural meta-commentary in blockquotes (`> ...`) to explain design rationale or clarify alternative/disabled modes.
2. `## Types`: Defines natural-language domain types enclosed in *italics* (`- A *<type>* is ...`). (In implementation specs, `## Types` is omitted or restricted strictly to constructor configuration types).
3. `## Behavior`: The unified requirements set expressing operational capabilities, constraints, data transformations, and observable outcomes.

---

## 2. Fundamental Design Principles

### Pillar 1: Natural-Language Domain Ontology
- **Concepts in *Italics***: Concepts are declared as plain-English sentences without colons or code tokens.
- **Types Categorize, They Do Not Act**: `## Types` establishes definitions and boundaries. Active capabilities and operations belong strictly in `## Behavior`.
- **No Untyped Floating Concepts**: Every domain noun referenced in `## Behavior` is italicized and directly traces to an owned or imported type.
- **Clarifying Examples Over Subtype Proliferation**: Parenthetical examples (e.g. `(such as system instructions, a user prompt, or model responses)`) clarify common forms without creating unnecessary wrapper types.
- **Producer and Consumer Roles in Types**: When a type is an open value consumed across boundaries (e.g. *log event*), its definition explicitly states its production and consumption roles (e.g. "*produced by any component and consumed by a runner logger*").
- **No Useless or Unobservable Types**: Do not define types for internal mechanics (e.g. no "real file path" when agents only ever see *virtual file names*).

### Pillar 2: Complete Purpose Rationale & Grounding (The Grounding Solution)
- **State the "Why", Not Just the "What"**: `## Purpose` must articulate the engineering rationale and failure modes being prevented (e.g. preventing path hallucination, eliminating discovery turns, avoiding tool confusion) rather than just paraphrasing behavioral rules.
- **Complete Rationale Coverage (No Orphan Capabilities)**: Every type in `## Types` and every major capability in `## Behavior` must have its motivating failure mode or purpose represented in `## Purpose`. Compressing for conciseness must never drop coverage of an entire capability (e.g. path sanitization and search in *file reader*).
- **Leaf vs Composite Rationale**:
  - *Leaf Components*: Motivate their specific domain mechanics (e.g. line numbers for editing safety vs plain text for token conservation).
  - *Composite / Facade Components*: Motivate composition, isolation, and coordination (e.g. isolating sub-systems behind a virtual workspace, startup orchestration, intercepting advance to gate guide delivery); they do NOT duplicate sub-component internals.

- **Permissions Grounding**: `*file reader*` explicitly declares `*file reader configuration*` specifying declared `*read-only files*` and `*read-write files*`. During sandbox assembly, permissions from `*sandbox configuration*` are mapped to `*file reader configuration*`, enabling strict runtime enforcement of line numbering on writable files.

### Pillar 3: Anti-Vestigial Configuration Rules
- **Direct Operational Consumption**: Every parameter or field declared in a configuration type must have a corresponding behavioral rule in `## Behavior` describing how the component directly reads or enforces it. Configuration fields that are merely passed through to sub-components are prohibited.
- **No Pass-Through Baggage**: Composite components (like *sandbox*) do not accept configuration fields on behalf of sub-systems (like *blame targets* for *run controller*); sub-components receive their configuration directly during assembly.
- **Continuous Pruning**: When responsibilities shift, immediately audit and prune configuration parameters and requirements whose original purpose no longer exists.

### Pillar 4: Natural Declarative Operations & Behavior
- **Active Operations and Transformations**: Express capabilities naturally in terms of what operations perform and what outputs result:
  - *Initialization*: "Initial *messages* can initialize a *conversation history*."
  - *Modification*: "Appending *messages* and *tool results* adds them to a *conversation history* in chronological order."
  - *Transformation*: "When an appended *tool result* supersedes an earlier result for the same resource, the earlier result is replaced in place with a *stub*."
  - *Output Generation*: "A *conversation history* provides a *model request* for a language model."
- **No Anthropomorphism**: Data structures are not living creatures; write active operational rules about what operations perform or what artifacts contain rather than having passive values "act" on their own.
- **Preconditions as Natural Qualifiers**: Requirements that cannot be enforced as static types are expressed directly as qualifiers on the capability sentence (e.g. "A *dag cleaner* can clean an *acyclic* subgraph rooted at a target *node*"). Violations are non-concerns / unexpected failures by default.
- **Explicit Runtime Expected Failures**: When an operation validates inputs at runtime (such as agent tool calls), explicitly state the produced failure outcome (e.g. "*tool failure*").

### Pillar 5: Compounding Implementation Behaviors
- **Header Order & In-Scope Implementation**: Implementation specs (`<name>_impl.md`) import dependencies, list `types from ...`, and place `implements: <type name>` directly after type statements so the implemented type is strictly in scope.
- **Compounding Details Only**: Implementations pin concrete metadata (tool names, parameter schemas, format strings, metadata stripping) without repeating invariants already established by the interface.
- **No New Domain Types**: Implementation components only implement an existing interface type; they cannot introduce new domain types (which would require assembly in `_asm.md`).

---

## 3. Component Architecture & Layering

```
+-----------------------------------------------------------------------------------+
|                                  build_runner                                     |
|           (Orchestrates Multi-Node Topological Build & Cleaning Passes)           |
+-----------------------------------------------------------------------------------+
        |                                       |                               |
        v                                       v                               v
+------------------+                 +---------------------+         +---------------------+
|   dag_cleaner    |                 | build_graph_storage |         |    runner_logger    |
| (Topological DAG |                 |  (Target Manifests  |         | (Stdout Summaries & |
|    Cleaning)     |                 |  & Virtual Configs) |         |  Disk Transcripts)  |
+------------------+                 +---------------------+         +---------------------+
        |                                       |                               |
        v                                       v                               v
+-----------------------+            +---------------------+         +---------------------+
|  agent_node_cleaner   |            |     dag_storage     |         |  tool_provider /    |
| (Node Task Execution) |            |   (Graph Topology   |         |  virtual_file_name  |
+-----------------------+            |   & Message State)  |         | (Foundation Types)  |
        |                            +---------------------+         +---------------------+
        |                                       |
        |                                       v
        |                            +---------------------+
        |                            | build_message_store |
        |                            | (Package .textproto |
        |                            |     Persistence)    |
        |                            +---------------------+
        |
        +-----------------------------------+
        |                                   |
        v                                   v
+--------------------+              +--------------------+
|    agent_runner    |              |      sandbox       |
| (Turn Loop, Prompt |              | (Hermetic Virtual  |
|  & Repeat Guards)  |              | Workspace Facade)  |
+--------------------+              +--------------------+
        |                                   |
        +---------------+                   +-----------------+-----------------+
        |               |                   |                 |                 |
        v               v                   v                 v                 v
+---------------+ +------------+    +---------------+ +---------------+ +---------------+
| conversation_ | | loop_guard |    |  file_reader  | |  file_editor  | |  run_control  |
|    history    | | (Repetition|    | (Inspection & | |  (Surgical    | |(Verification, |
| (Prompt Buffer| |  Detector) |    |  Sanitizer)   | |  Edits &      | | Blame Routing |
|  & Stubbing)  | +------------+    +---------------+ |  Templates)   | | & Termination)|
+---------------+                                     +---------------+ +---------------+
                                                                                |
                                                                                v
                                                                        +---------------+
                                                                        |guide_delivery |
                                                                        | (Step Guidance|
                                                                        |  Delivery)    |
                                                                        +---------------+
```
