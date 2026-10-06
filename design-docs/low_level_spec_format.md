# Low-Level Specification Architecture

## 1. Overview & Architectural Purpose

In the Cleanroom engineering pipeline, the **Low-Level Specification** (`low/<name>.pyi` and `low/<name>_impl.pyi`) defines formal Python interface and implementation stubs derived from the Planning Canvas (`planning/<name>.md`). It directly precedes runtime library code (`lib/*.py`) and deterministic unit tests (`tests/*_test.py`).

```
┌──────────────────────────────────────────────┐
│ Planning Canvas (planning/*)                 │  <-- Typing, Contracts, Knowledge Provisions &
└──────────────────────┬───────────────────────┘      Grounding Requirements (pure slugs)
                       │  planning_to_low.md
                       ▼
┌──────────────────────────────────────────────┐
│ Low-Level Stubs (low/*.pyi & _impl.pyi)      │  <-- AST Types, Lifecycles, INVARIANTS,
└──────────────────────┬───────────────────────┘      PRECONDITIONS, POSTCONDITIONS, and
                       │                              GROUNDING: (natural language arguments)
                       ▼
┌──────────────────────────────────────────────┐
│ LOW_QA Arbiter (low_qa)                      │  <-- Audits low against planning; runs Pyright &
└──────────────────────┬───────────────────────┘      low_lint internally; stamps LOW_QA_AUDIT
                       │  low_to_lib.md / low_to_test.md
                       ▼
┌──────────────────────────────────────────────┐
│ Library & Tests (lib/, test/)                │  <-- Implementation directly follows GROUNDING:;
└──────────────────────────────────────────────┘      Tests verify interface POSTCONDITIONS:
```

The low-level specification formalizes the Planning Canvas into:
1. **Python Structural AST**: Strong typing, generic parameters, variant hierarchies, and lifecycle tiers (`InTier[TierType]`).
2. **Design-by-Contract Docstrings**: Organizing behavioral requirements into classical invariants, preconditions, and postconditions.
3. **Natural Language Grounding Arguments (`GROUNDING:`)**: In implementation stubs (`_impl.pyi`), grounding resolutions from the Planning Canvas are synthesized into concrete architectural arguments citing collaborator classes, methods, and component names.

---

## 2. Docstring Contract Structure

Low-level stubs assign planning requirements and grounding resolutions to canonical docstring sections:

### 2.1 `INVARIANTS:` (Type-Level Invariants)
- Declared in class docstrings on `@singleton_type`, `@poly_type`, or `@data_type` classes.
- Defines state consistency rules, scope guarantees, and structural invariants that hold across all instances of the type.
- **No Precondition Repetition**: Invariants declared on a type hold across all operations of that type and must **never be repeated as preconditions** on operations in that type.

### 2.2 `PRECONDITIONS:` (Invocation Prerequisites)
- Declared on `@operation` methods.
- Defines prerequisites and constraints that callers must satisfy before invoking the operation.
- Does not repeat type invariants established at the class level.

### 2.3 `POSTCONDITIONS:` (Operational Outcomes & Normative Guarantees)
- Declared on `@operation` methods and stateful or constant `@property` members.
- Defines guaranteed outcomes upon invocation, including return values, state transitions, collaborator delegations, and structured failure responses.
- Uses normative language: `- WHEN <condition>, MUST <outcome>.` and `- MUST <outcome>.`

#### No Verbatim Copy-Down to Refinements/Subtypes
Postconditions do **not** need to be copied down to overrides or implementation stubs verbatim:
- If a method or property override has nothing new or strengthened to add beyond its supertype contract, leave member bodies as `...` without duplicating base postconditions.
- Downstream verification and tests consider requirements in the type and all of its supertype declarations transitively.

---

### 2.4 `GROUNDING:` (Natural Language Grounding Arguments in Implementation Stubs)

The `GROUNDING:` section appears **strictly in implementation stubs** (`low/<name>_impl.pyi`) within class and member docstrings. It bridges the abstract, slug-based grounding from `planning/<name>_impl.md` into concrete Python architectural guidance for the library implementer.

#### Purpose:
- Synthesizes the planning document's grounded knowledge requirements into a clear, natural language argument explaining **why and how** the class or method is grounded.
- Specifically permitted and expected to cite:
  1. **Imported Component Names**: The packaging boundaries supplying capabilities (e.g. `agent_node_config`, `dag_storage`, `sandbox_file_editor`).
  2. **Collaborator Class Names**: The concrete singleton or polymorphic types resolved via lifecycle tiers (e.g. `NodeConfig`, `DagStorage`, `EditManager`).
  3. **Collaborator Member Names**: Specific operations, properties, or data types queried or invoked (e.g. `NodeConfig.read_write_files`, `DagStorage.materialize_template`, `EditManager.has_modifications`).
  4. **Internal Backing State**: Private fields and collections that store or manage state (e.g. `self._installed_tools`).

#### Interface vs. Implementation Boundary on Collaborator Mentions:
- **Interface Stubs (`low/<name>.pyi`)**: Must **NEVER** mention specific collaborators (e.g. `NodeConfig`, `DagStorage`) in docstrings, preconditions, or postconditions. Interfaces remain completely decoupled and abstract protocols.
- **Implementation Stubs (`low/<name>_impl.pyi`)**: Must **ALWAYS** provide natural language grounding arguments under `GROUNDING:`, detailing collaborator wiring and state provenance.

---

## 3. Concrete Example: `sandbox` vs. `sandbox_impl`

### 3.1 Interface Stub: `low/sandbox.pyi` (Decoupled, Abstract)

```python
"""Sandbox low-level interface specification."""

from typing import Protocol
from framework import operation, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier


@singleton_type("agent_session")
class Sandbox(InTier[AgentSessionTier], Protocol):
    """Coordinates session template materialization and file modification tracking."""

    @property
    def has_modifications(self) -> bool:
        """Exposes whether workspace file modifications occurred during the session.

        POSTCONDITIONS:
        - MUST return whether workspace file modifications occurred during the session.
        """
        ...

    @operation
    def materialize_templates(self) -> None:
        """Materializes startup templates into missing read-write files.

        POSTCONDITIONS:
        - MUST materialize startup templates into missing read-write files without overwriting existing files.
        """
        ...
```

### 3.2 Implementation Stub: `low/sandbox_impl.pyi` (Concrete Grounding Arguments)

```python
"""Sandbox implementation low-level specification."""

from framework import operation, override, singleton_type
from support.lib.lifecycle import InTier
from agent_session import AgentSessionTier
import sandbox
import agent_node_config
import dag_storage
import sandbox_file_editor


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

## 4. How `lib/*.py` Uses Grounding Arguments

When writing `lib/<name>_impl.py`, the implementer:
1. Inspects `low/<name>_impl.pyi`.
2. Reads the `GROUNDING:` argument on each class and method.
3. Implements the exact collaborator lookups (`get_singleton(...)`) and invocations specified in `GROUNDING:`.

This completely eliminates guesswork:
- The interface contracts (`POSTCONDITIONS:`) define the testable invariants and failure responses.
- The implementation grounding (`GROUNDING:`) defines the concrete execution blueprint.
- No parallel `grounding/*.py` pseudo-code files or Datalog queries are needed.
