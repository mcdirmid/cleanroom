# Architecture & Design: Epistemic Grounding in Planning Specifications

## Executive Summary

Cleanroom software construction relies on formal grounding specifications to ensure that high-level contracts are constructively feasible before writing runtime implementation code (`lib/`) and unit tests (`tests/`). 

Historically, Cleanroom attempted to verify grounding through two paradigms:
1. **Relational Groundtalk (`.gt`)**: Custom Datalog Horn-clause reachability solvers. (Struggled with complex expressions, nested collections, and custom toolchain friction).
2. **Static Python Grounding (`grounding/*.py`)**: Straight-line typed Python feasibility proofs checked via Pyright.

While Python grounding resolved toolchain friction, it introduced a severe behavioral failure mode: **Mechanistic Hallucination of Success**. Because Pyright only verifies syntactic type assignability, LLMs routinely pacify the type checker by fabricating phantom literals, accessing arbitrary dictionary keys, or copying contract docstrings into hollow functions that terminate in `raise NotImplementedError`. The LLM achieves "0 type errors" while proving zero actual semantic grounding.

Furthermore, Planning documents **do not have access to code**; injecting Python syntax (such as `self._tools` or `.convert()`) into planning specifications violates Cleanroom's strict abstraction layers.

This document establishes the new architecture: **Pure Epistemic Grounding via Slugs in Planning Specifications, verified by `spec_qa`, translated into Natural Language Grounding Arguments (`GROUNDING:`) in Low-Level Specifications, and verified by `low_qa` before implementation begins**.

---

## 1. Document Structure: Factored Contracts & Grounding

Every planning specification conforms to three canonical `##` sections in strict order:

```markdown
# <name> <component_type> component

imports: <imported_modules>
implements: <interface>  # (implementation components only)

## Intent
[Continuous prose paragraphs explaining architectural rationale, UX motivations, and trade-offs]

## Factored Contracts
### Typing
[Static structural types, record fields, variants: - <sentence>.]
### Contracts
[Atomic behavioral contracts with unique semantic slugs: - <sentence>. [<slug>]]
### Woven Contracts
[Synthesized cross-cutting interactions with bracketed slug citations: - <sentence>. [<citations>]]

## Grounding
### Knowledge Provisions
[What knowledge, state, or actions this component provides: - <sentence>. [<slug>]]
### Inherited Deferred Requirements
[For _impl components: verbatim repetition of inherited interface deferrals, each with - Grounded:]
### Knowledge Requirements
[Pure elicitation of needed knowledge/actions without slugs, each with - Grounded: or - Deferred:]
```

---

## 2. Slug Asymmetry: Why Provisions Have Slugs and Requirements Do Not

In Cleanroom Planning, slugs exist **exclusively for citation and reachability**:
- **`### Contracts` have slugs** because they are cited in `### Woven Contracts` and traced into unit tests.
- **`### Knowledge Provisions` have slugs** because they are cited in `Grounded: [...]` lists by consumers and internal operations.
- **`### Typing` omits slugs** because static type definitions are not cited in reachability.
- **`### Knowledge Requirements` omit slugs** because requirements are terminal sinks—they are *consumers* of knowledge, never providers. No other construct ever cites a requirement.

### Verbatim Repetition for Inherited Deferred Requirements
When an implementation component (`_impl`) implements an interface, it does not refer to abstract requirement slugs. Instead, it **repeats the deferred requirement sentence verbatim**:

```markdown
# In interface (planning/sandbox.md):
### Knowledge Requirements
- To materialize startup templates, the sandbox must know declared session files and starter templates.
  - Deferred: Requires session configuration backing state in implementation.

# In implementation (planning/sandbox_impl.md):
### Inherited Deferred Requirements
- To materialize startup templates, the sandbox must know declared session files and starter templates.
  - Grounded: [agent_node_config: [session_config_read_write_files, session_config_templates]]
```

### Benefits of Verbatim Repetition:
1. **Self-Contained & Literate**: The implementation document is completely readable without having to look up external requirement IDs in the interface.
2. **Deterministic Mechanical Auditing**: An auditor verifies 100% parity by checking that every sentence marked `- Deferred:` in the interface is repeated verbatim in the implementation under `### Inherited Deferred Requirements` with a `- Grounded:` sub-bullet.
3. **No Slug Bureaucracy**: Eliminates artificial slug names for requirements that only ever exist to be resolved locally.

---

## 3. The Pure Epistemic Model: Provisions, Requirements, and Grounding

1. **Knowledge Provisions (`### Knowledge Provisions`)**:
   - What values, states, or operational capabilities does this component make available to others or to its own operations?
   - Every provision ends with a unique bracketed snake_case slug: `- <sentence>. [<slug>]`.
2. **Knowledge Requirements (`### Knowledge Requirements`)**:
   - What information, observations, or actions must be available to satisfy the component's contracts?
   - Formatted as plain declarative sentences without slugs: `- <sentence>.`
3. **Sub-Bullet Grounding (`- Grounded: [...]`)**:
   - Directly under each requirement, an indented sub-bullet specifies the exact slug or combination of slugs that grounds it:
     ```markdown
     - To execute tools by name, the manager must resolve the tool, convert arguments, and invoke tool execution.
       - Grounded: [installed_tools_collection, wire_value_conversion, tool_execution_capability]
     ```
   - Multiple slugs can be combined in bracketed citations to satisfy composite requirements.
4. **Sub-Bullet Deferral (`- Deferred: ...`)**:
   - In interface specifications, requirements that depend on concrete backing state or external environment access are marked deferred:
     ```markdown
     - To provide installed tools, the tool manager must access backing tool storage.
       - Deferred: Requires concrete backing collection in implementation.
     ```

---

## 4. The Strict Acyclicity Invariant (Anti-Circularity)

Because grounding allows internal composition (a requirement grounded by local provision slugs), there is a critical danger: **Circular / Tautological Grounding**.
- *Invalid Tautology*: A provision `[execute_tool]` requiring an action that is grounded directly by `[execute_tool]`.
- *Invalid Cycle*: Provision `[A]` grounds a requirement that enables `[B]`, which grounds a requirement that enables `[A]`.

### Deterministic DAG Verification over Slugs
Because provisions have unique slugs and requirements cite provision slugs in `Grounded: [...]`:
1. **Dependency Mapping**:
   - Each provision $P$ is associated with the knowledge requirements needed to realize it.
   - Each knowledge requirement points to the provision slugs in its `Grounded: [...]` list.
2. **The Acyclicity Invariant**:
   - The directed graph between provisions must contain **zero cycles**.
   - A provision can never appear in the grounding closure of its own prerequisite requirements.
3. **Well-Founded Base**:
   - Every grounding path must terminate in external imports (`component: [slug]`) or caller input parameters.

---

## 5. Case Study: Internal Grounding in `tool_provider`

Consider `tool_provider.md` and `tool_provider_impl.md`. Notice how requirements have **no slugs**, while provisions **have slugs** that are cited to ground them.

### 5.1 Interface Planning: `planning/tool_provider.md`

```markdown
# tool_provider interface component

imports: agent_session

## Intent
...

## Factored Contracts

### Typing
- A tool has a name.
- A tool has a set of tool parameters.
- A tool parameter specifies a parameter type.
- A parameter type converts wire values to python values.

### Contracts
- A tool manager provides installed tools. [provide_installed_tools]
- A tool manager installs tools for the agent session. [install_tools]
- A tool manager executes tools by name with wire parameter bindings. [execute_tool_by_name]

### Woven Contracts
- When executing a tool by name, the tool is resolved from installed tools, wire arguments are converted, and the tool is invoked with python bindings. 
  [provide_installed_tools, execute_tool_by_name]

## Grounding

### Knowledge Provisions
- The tool manager exposes the collection of installed tools. [installed_tools_collection]
- A parameter type converts wire values to python values. [wire_value_conversion]
- A tool executes with python parameter bindings. [tool_execution_capability]

### Knowledge Requirements
- To provide installed tools, the tool manager must access backing tool storage.
  - Deferred: Requires concrete backing collection in implementation.
- To install tools, the tool manager must mutate backing tool storage.
  - Deferred: Requires concrete state mutation in implementation.
- To execute tools by name, the manager must resolve the tool, convert arguments, and invoke tool execution.
  - Grounded: [installed_tools_collection, wire_value_conversion, tool_execution_capability]
```

### 5.2 Implementation Planning: `planning/tool_provider_impl.md`

```markdown
# tool_provider_impl implementation component

implements: tool_provider

## Intent
...

## Factored Contracts

### Contracts
- Installed tools are maintained in a private session dictionary. [maintain_private_tool_dict]

### Woven Contracts
- Installing a tool updates the private tool dictionary, and providing installed tools exposes the dictionary contents.
  [maintain_private_tool_dict, tool_provider: [install_tools, provide_installed_tools]]

## Grounding

### Knowledge Provisions
- Private dictionary mapping tool names to installed tools. [private_tool_storage]
- Mutation capability to insert tools into private dictionary. [private_tool_mutation]

### Inherited Deferred Requirements
- To provide installed tools, the tool manager must access backing tool storage.
  - Grounded: [private_tool_storage]
- To install tools, the tool manager must mutate backing tool storage.
  - Grounded: [private_tool_mutation]

### Knowledge Requirements
(None)
```

---

## 6. Case Study: Collaborator Grounding in `sandbox_impl`

### 6.1 Interface Planning: `planning/sandbox.md`

```markdown
# sandbox interface component

## Intent
...

## Factored Contracts

### Contracts
- An agent session's sandbox coordinates starter template materialization. [sandbox_coordinates_template_materialization]
- An agent session's sandbox coordinates file modification tracking. [sandbox_coordinates_modification_tracking]
- The sandbox materializes startup templates into missing read-write files at session start. [materialize_startup_templates]
- The sandbox exposes whether workspace file modifications occurred during the session. [expose_modifications_occurred]

### Woven Contracts
- Materializing startup templates writes boilerplate into missing read-write files without overwriting existing workspace content. 
  [sandbox_coordinates_template_materialization, materialize_startup_templates]
- Workspace modification queries indicate whether files were changed during the active session. 
  [sandbox_coordinates_modification_tracking, expose_modifications_occurred]

## Grounding

### Knowledge Provisions
- Exposes whether workspace files were modified during the session. [session_modifications_status]
- Capability to materialize starter templates into missing files. [session_template_materialization]

### Knowledge Requirements
- To materialize templates, the sandbox must know declared session files and starter templates.
  - Deferred: Requires session configuration backing state in implementation.
- To materialize templates, the sandbox must invoke template writing on storage.
  - Deferred: Requires storage backing capability in implementation.
- To expose modifications, the sandbox must know whether file writes occurred.
  - Deferred: Requires edit tracking backing state in implementation.
```

---

### 6.2 Implementation Planning: `planning/sandbox_impl.md`

```markdown
# sandbox_impl implementation component

imports: sandbox_file_editor, dag_storage, agent_node_config
implements: sandbox

## Intent
...

## Factored Contracts

### Contracts
- Querying file modifications delegates to the edit manager. [delegate_file_modifications]
- Materializing startup templates resolves session read-write files and templates from session config. [resolve_read_write_files_and_templates_from_session_config]
- Materializing startup templates delegates to dag storage. [delegate_template_materialization]
- Materializing startup templates writes template content to missing read-write files. [write_template_to_missing_files]
- Materializing startup templates preserves existing files without overwriting. [preserve_existing_files_on_materialization]

### Woven Contracts
- Querying session modifications retrieves modification state from the edit manager. 
  [delegate_file_modifications, sandbox: [expose_modifications_occurred], sandbox_file_editor: [writes_occurred_true_on_diff, writes_occurred_false_on_match]]
- Materializing startup templates resolves files and templates from session config and invokes dag storage to write missing files while preserving existing content. 
  [resolve_read_write_files_and_templates_from_session_config, delegate_template_materialization, write_template_to_missing_files, preserve_existing_files_on_materialization, sandbox: [materialize_startup_templates, preserve_existing_files_during_materialization], agent_node_config: [session_config_read_write_files, session_config_templates], dag_storage: [materialize_node_template]]

## Grounding

### Knowledge Provisions
(None)

### Inherited Deferred Requirements
- To materialize templates, the sandbox must know declared session files and starter templates.
  - Grounded: [agent_node_config: [session_config_read_write_files, session_config_templates]]
- To materialize templates, the sandbox must invoke template writing on storage.
  - Grounded: [dag_storage: [materialize_node_template], agent_node_config: [file_alias_owning_node]]
- To expose modifications, the sandbox must know whether file writes occurred.
  - Grounded: [sandbox_file_editor: [writes_occurred_true_on_diff, writes_occurred_false_on_match]]

### Knowledge Requirements
(None)
```

---

## 7. Downstream Synthesis: Low-Level Grounding Arguments (`GROUNDING:`)

When translating planning specifications into Low-Level Specifications (`low/`), the grounding resolutions established in `planning/<name>_impl.md` are translated into **Natural Language Grounding Arguments** under a dedicated `GROUNDING:` docstring section in `low/<name>_impl.pyi`.

### Rules for `GROUNDING:` in Low-Level Stubs:
1. **Implementation Stubs Only (`_impl.pyi`)**:
   - `GROUNDING:` sections appear **strictly in implementation stubs** (`low/<name>_impl.pyi`).
   - Interface stubs (`low/<name>.pyi`) define abstract protocols and must **never** mention collaborator singletons or implementation classes.
2. **Citing Collaborator Classes and Methods**:
   - Unlike interface contracts, the `GROUNDING:` argument in an implementation stub is explicitly expected to cite:
     - Imported component names (e.g. `agent_node_config`, `dag_storage`)
     - Collaborator class names (e.g. `NodeConfig`, `DagStorage`, `EditManager`)
     - Collaborator method and property names (e.g. `DagStorage.materialize_template`, `EditManager.has_modifications`)
     - Private backing state fields (e.g. `self._tools`)
3. **Execution Blueprint for Library Implementers**:
   - Library code (`lib/<name>_impl.py`) directly implements the collaborator lookups and method invocations argued in `GROUNDING:`.

### Example in `low/sandbox_impl.pyi`:
```python
@singleton_type("agent_session")
class Sandbox(sandbox.Sandbox, InTier[AgentSessionTier]):
    """Realizes session template materialization and file modification tracking.

    GROUNDING:
    - Coordinates session startup and change tracking by delegating template writing
      to DagStorage, resolving session files from NodeConfig, and querying file diffs
      from EditManager within the agent session tier.
    """

    @property
    @override
    def has_modifications(self) -> bool:
        """Exposes whether workspace file modifications occurred during the session.

        GROUNDING:
        - Grounded via EditManager.has_modifications from sandbox_file_editor,
          querying whether diff-based file mutations were recorded.
        """
        ...

    @operation
    @override
    def materialize_templates(self) -> None:
        """Materializes startup templates into missing read-write files.

        GROUNDING:
        - Grounded via NodeConfig from agent_node_config to resolve session read-write files
          and starter templates, FileAlias.owning_node to identify target nodes, and
          DagStorage.materialize_template from dag_storage to write boilerplate without
          overwriting existing files.
        """
        ...
```

---

## 8. Verification Architecture: The Auditor Roles (`spec_qa` & `low_qa`)

Cleanroom coordinates verification through dedicated, independent **Auditor Roles**. To keep authoring agents in deep semantic reasoning mode and prevent mechanistic constraint-satisfaction gaming, Cleanroom enforces the foundational principle:

> **"Authors Author; Arbiters Lint and Audit."**

Authoring models (`high`, `planning`, `low`, `lib`, `test`) are deliberately insulated from interactive linters and type checkers. When an authoring agent is given direct access to a linter, it inevitably degenerates into mechanistic gaming—tinkering with ASTs, regexes, and syntax to pacify tools rather than reasoning deeply about domain semantics and contract fidelity.

Instead:
- **`low_lint.py` and Pyright are moved entirely from `low` to `low_qa`**: The `low` author focuses purely on structural type design, lifecycle modeling, and translating planning grounding into literate `GROUNDING:` docstrings.
- **Arbiters execute verification suites internally**: `spec_qa` and `low_qa` run linters and static analyzers as fast pre-flight sanity checks, translating any mechanical defects into actionable, non-prescriptive blame feedback for the author.

```
┌─────────────────────────────────────────────────────────────┐
│                 TIER 1: SPECIFICATION TIER                  │
├─────────────────────────────────────────────────────────────┤
│   High-Level Spec (high/*.md)       [Author: zero linters]  │
│              │                                              │
│              ▼                                              │
│   Planning Canvas (planning/*.md)   [Author: zero linters]  │
│              │                                              │
│              ▼                                              │
│   SPEC_QA Arbiter (spec_qa)   ◄── Audits high & planning    │
│        ├── Runs linters internally (zero author gaming)     │
│        ├── Audits HLS-to-Planning semantic coverage         │
│        ├── Verifies Knowledge Provisions & DAG Acyclicity   │
│        └── Delivers Blame Critique OR stamps:               │
│            SPEC_QA_AUDIT: <timestamp>                       │
└──────────────────────────────┬──────────────────────────────┘
                               │ unlocks
┌──────────────────────────────▼──────────────────────────────┐
│                    TIER 2: LOW-LEVEL TIER                   │
├─────────────────────────────────────────────────────────────┤
│   Low-Level Stubs (low/*.pyi & _impl.pyi with GROUNDING:)   │
│              │                      [Author: zero linters]  │
│              ▼                                              │
│   LOW_QA Arbiter (low_qa)     ◄── Audits low against plan   │
│        ├── Runs Pyright & low_lint.py internally (moved)    │
│        ├── Audits contract completeness (INVARIANTS, etc.)  │
│        ├── Verifies GROUNDING: arguments against planning   │
│        └── Delivers Blame Critique OR stamps:               │
│            LOW_QA_AUDIT: <timestamp>                        │
└──────────────────────────────┬──────────────────────────────┘
                               │ unlocks
┌──────────────────────────────▼──────────────────────────────┐
│                TIER 3: IMPLEMENTATION TIER                  │
├─────────────────────────────────────────────────────────────┤
│   Library & Tests (lib/*.py & tests/*_test.py)              │
│              │                      [Authors: zero linters] │
│              ▼                                              │
│   QA & Coverage Arbiters (qa, coverage)                     │
│        └── Certify runtime behavior with QA_AUDIT &         │
│            COVERAGE_AUDIT                                   │
└─────────────────────────────────────────────────────────────┘
```

### 8.1 Responsibilities of `spec_qa`
- Audits `high/*.md` and `planning/*.md`.
- Runs structural linters and provision DAG cycle checks internally.
- Verifies that 100% of high-level architectural contracts are captured in planning.
- Verifies knowledge provisions, sub-bullet grounding, and the zero-deferred rule on `_impl.md`.
- Stamps `SPEC_QA_AUDIT: <timestamp>` on `planning/<name>.md`.

### 8.2 Responsibilities of `low_qa`
- Audits `low/<name>.pyi` and `low/<name>_impl.pyi` against `planning/<name>.md`.
- **Owns `low_lint.py` and Pyright verification**: Executes static type checking and structural linting as an internal pre-flight check, keeping the `low` author model unencumbered by mechanistic loops.
- Verifies that 100% of planning contracts are mapped to `INVARIANTS:`, `PRECONDITIONS:`, and `POSTCONDITIONS:`.
- Verifies that `GROUNDING:` sections in `_impl.pyi` accurately translate the grounded knowledge requirements into concrete collaborator classes and methods.
- Verifies that interface stubs (`low/<name>.pyi`) do not leak collaborator names.
- Stamps `LOW_QA_AUDIT: <timestamp>` on `low/<name>.pyi` and `low/<name>_impl.pyi`.

---

## 9. Pipeline Transformation: The Three-Gate Cleanroom Pipeline

```
OLD PIPELINE:
HLS -> Planning -> Low (.pyi) -> Grounding (.py) -> Grounding QA -> Lib (.py) -> Tests -> QA -> Coverage

NEW PIPELINE:
HLS -> Planning -> Spec QA -> Low (.pyi) -> Low QA -> Lib (.py) -> Tests -> QA -> Coverage
```

### The Three Independent Verification Gates:
1. **Gate 1 (`spec_qa`)**: Certifies conceptual specification integrity, contract factorization, and epistemic reachability.
2. **Gate 2 (`low_qa`)**: Certifies static type soundness, structural stubs, and concrete collaborator grounding blueprints before code is written.
3. **Gate 3 (`qa` & `coverage`)**: Certifies double-blind runtime implementation correctness and statement test coverage.

### What is Eliminated:
- **`grounding/*.py`**: The parallel pseudo-executable Python stubs are completely deleted.
- **`low_to_grounding.md`**: Deprecated.
- **`grounding_qa` role**: Retired.
- **Author-facing lint distractions**: Authors remain focused purely on semantic domain reasoning.
