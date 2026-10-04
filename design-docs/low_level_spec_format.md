# Low-Level Specification Architecture

## 1. Overview & Architectural Purpose

In the Cleanroom engineering pipeline, the **Low-Level Specification** (`low/<name>.pyi`) defines formal Python interface and implementation stubs derived from the Planning Canvas (`planning/<name>.md`). It precedes Groundtalk feasibility verification (`grounding/<name>.gt`), runtime library code (`lib/*.py`), and unit tests (`tests/*_test.py`).

```
┌─────────────────────────────────┐
│ Planning Canvas (planning/*)    │  <-- Typing Requirements & Contract Requirements
└──────────────┬──────────────────┘
               │  planning_to_low.md
               ▼
┌─────────────────────────────────┐
│ Low-Level Stubs (low/*.pyi)     │  <-- AST Types, INVARIANTS, PRECONDITIONS,
└──────────────┬──────────────────┘      POSTCONDITIONS
               │  low_to_grounding.md
               ▼
┌─────────────────────────────────┐
│ Groundtalk Specs (grounding/*.gt)│ <-- Groundtalk Horn rules & feasibility queries
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│ Library & Tests (lib/, test/)   │
└─────────────────────────────────┘
```

The low-level specification formalizes the Planning Canvas into:
1. **Python Structural AST**: Strong typing, generic parameters, variant hierarchies, and lifecycle tiers.
2. **Design-by-Contract Docstrings**: Organizing behavioral requirements into classical invariants, preconditions, and postconditions.
3. **Decoupled Relational Formalization**: Low-level stubs contain **zero** Datalog predicates, facts, or Horn rules. Groundtalk logic is compiled separately into `grounding/<name>.gt`.

---

## 2. Docstring Contract Structure

Low-level stubs assign planning requirements to three canonical contract sections:

### 2.1 `INVARIANTS:` (Type-Level Invariants)
- Declared in class docstrings on `@singleton_type`, `@poly_type`, or `@data_type` classes.
- Defines state consistency rules, scope guarantees, and structural invariants that hold across all instances of the type.
- **No Precondition Repetition**: Invariants declared on a type hold across all operations of that type and must **never be repeated as preconditions** on operations in that type.
- Example:
  ```python
  @singleton_type("agent_session")
  class ToolManager(Protocol):
      """Session service that maintains and executes tools.

      INVARIANTS:
      - Installed tools in a tool manager have unique names.
      """
  ```

### 2.2 `PRECONDITIONS:` (Invocation Prerequisites)
- Declared on `@operation` methods.
- Defines prerequisites and constraints that callers must satisfy before invoking the operation.
- Does not repeat type invariants established at the class level.
- Example:
  ```python
  @operation
  def execute_tool_by_wire(self, name: str, wire_parameter_bindings: WireParameterBindings) -> ToolResponse:
      """Executes a tool by name with wire parameter bindings.

      PRECONDITIONS:
      - Caller supplies wire type parameter bindings for declared parameters.
  ```

### 2.3 `POSTCONDITIONS:` (Operational Outcomes, Constant Properties, & State Provenance)
- Declared on `@operation` methods and stateful or constant `@property` members.
- Defines guaranteed outcomes upon invocation, including return values, state transitions, collaborator delegations, and structured failure responses.
- Uses normative language: `- WHEN <condition>, MUST <outcome>.` and `- MUST <outcome>.`

#### No Verbatim Copy-Down to Refinements/Subtypes
Postconditions do **not** need to be copied down to refinements, subtypes, or implementation stubs verbatim:
- If a method or property override has nothing new or strengthened to add beyond its supertype contract, **do not add anything**; leave the body as `...` without redundant docstring boilerplate.
- The grounding process and downstream verification consider requirements in the type and all of its supertype declarations transitively.
- Only declare `POSTCONDITIONS:` on an override when introducing a genuine specialization or strengthening (e.g. when an interface protocol first refines an abstract property to a constant string, or an operation adds concrete formatting/filtering rules not present in the supertype).
- In an implementation stub (`_impl.pyi`), properties and operations that merely fulfill the base interface contract without adding new behavioral branches should remain bare without duplicating base postconditions.

#### Sourced State & Prohibiting Collaborator Mentions
When a service exposes state via a property but has no local mutator/installation method (such as `ReadManager.read_only_files`), the state comes from external sources rather than local mutation. However, **low-level specifications must NEVER mention specific collaborators** (e.g. `NodeConfig`, `ToolManager`, `AliasManager`) in docstrings, preconditions, or postconditions:
- Collaborators do not necessarily exist in the module's interface scope and must never be forced in as unneeded imports.
- Even in implementation components (`_impl.pyi`), collaborator names are prohibited in docstrings; postconditions state the requirement generically (e.g. `- MUST expose declared read-only files from other objects.`).
- Specific collaborator wiring and provenance are resolved strictly downstream during Grounding (`grounding/*.gt`).

```python
    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        """Exposes the session read-only files.

        POSTCONDITIONS:
        - MUST expose declared read-only files from other objects.
        """
        ...
```

#### Concrete Strings for Descriptions and Diagnostics
Descriptions, error messages, and guidance strings must be generated explicitly in docstrings and postconditions during low-level specification authoring, rather than deferred or left as vague paraphrases.

#### Data Provenance & Preventing Origin Amnesia in Postconditions
A contract must never merely state an output type without stating the **origin and derivation rules** for its non-trivial fields:
- **Anti-pattern**: `MUST provide the session task guide.` (What is in it? Where does it come from?)
- **Proper pattern**:
  - `MUST retrieve the guide target manifest via the manifest loader.`
  - `MUST extract the guide summary from content preceding the first section heading.`
  - `MUST capture verification failure instructions when a heading begins with "Verification failure".`
  - `MUST create sequential step sections for subsequent level-two headings.`

Every composite output record requires its constituent arguments to be mapped to either:
1. **Direct Input**: Parameters passed to the operation.
2. **Collaborator State**: State retrieved from collaborator singletons in scope.
3. **Synthesized Transformation**: Content parsed, mapped, or formatted from declared inputs or collaborators.
4. **Contractual Defaults**: Literal constants explicitly dictated by the contract itself.

Without explicit data provenance in low-level specifications, downstream grounding cannot construct valid feasibility proofs without resorting to phantom literals, and library and test implementations will diverge on ad-hoc assumptions.

---

## 3. Decoupling from Groundtalk Logic

Earlier revisions embedded Datalog syntax directly in stub docstrings (`NEW_PREDICATES:`, `GROUNDING_PROVISIONS:`, `GROUNDING_ARGUMENT:`). This created ununified phantom variables, artificial relational database predicates (`one_by_name`, `entity_name`), and unreadable docstrings.

In the low-level specification:
- Docstrings are **strictly human- and LLM-readable English contracts**.
- Bridge predicates and derivation rules are extracted downstream during `low_to_grounding.md` into `grounding/<name>.gt`.
- Low-level specifications remain clean, pure Python interface definitions that can be reviewed, type-checked by Pyright, and used directly by library developers and test authors.
