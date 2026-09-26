# Groundtalk: Declarative Grounding Logic & Forward-Chaining Engine

## 1. Executive Summary & Purpose

**Groundtalk** is the formal relational logic language and deterministic inference engine governing Cleanroom's grounding phase. It bridges literate High-Level Specifications (`high/*.md`) and structural Python interface stubs (`grounding/*.pyi`) before any runtime library code (`lib/*.py`) is authored.

Groundtalk formalizes capability feasibility and knowledge custody into verifiable Horn clauses, evaluated by a lightweight, zero-dependency **forward-chaining engine** embedded directly into [`grounding_tool.py`](file:///Users/seanmcdirmid/projects/cleanroom-grounding/update_with_ai/support/lib/grounding_tool.py).

### Core Responsibilities of Groundtalk
1. **Language Specification**: Defines atomic capability (`action`) and state custody (`knows`) predicates with polymorphic subtyping subsumption and dual-key concept typing.
2. **Obligation Contract**: Categorizes declarations into intrinsic axioms (`GROUNDING_IMPLEMENTS:`), exported guarantees (`GROUNDING_PROVISIONS:`), and consumed dependencies (`GROUNDING_REQUIREMENTS:`).
3. **Deterministic Reachability Solver**: Computes the least fixed-point reachability closure over scoped component environments $(a - e)$ in polynomial time.
4. **Derivation Witness Extraction (Why-Provenance)**: When proof succeeds, synthesizes step-by-step provenance trees to guide downstream library code generation (`grounding_to_lib`).
5. **Diagnostic Gap Pinpointing (Why-Not Provenance)**: When proof fails, isolates exact missing goals and harvests partially satisfied rules ("near-misses") to feed Cleanroom's Neuro-Symbolic Gap Inspector.

---

## 2. Groundtalk Language Syntax & Predicates

All Groundtalk statements in an operation or property scope decompose into two typed predicates:

### 2.1 `action(...)` (Capability Feasibility)
Actions represent operational capabilities or state transformations invoked on domain entities:
- **Unary Action**: `action(verb, TargetType): <justification>`
  - Descriptive, unambiguous snake_case verbs: e.g. `action("read", agent_file_alias.FileAlias)`, `action("install", Self)`, `action("record_last_read_write", agent_file_alias.FileAlias)`.
- **Relational Action**: `action(verb, TargetType, preposition, AuxType): <justification>`
  - Auxiliary types describe domain inputs, never collaborators: e.g., `action("format", str, "with", template_format.TemplateParameters)`.

#### Action Target Semantics & `Self`
- When an action acts upon, invokes, or registers the instance itself, the target type is `Self` (e.g. `action("install", Self)` or `action("call", Self)`).
- When an action converts or transforms an argument, the target type is the entity being transformed (e.g. `action("convert", WireType)`), not `Self`.
- Generalized supertypes in provisions assert universal capability across all subtypes (e.g. `ToolManager` providing `action("install", Tool)` for any tool subtype).

### 2.2 `knows(...)` (Knowledge Custody)
`knows` is strictly reserved for ambient contextual data or state observations that an entity inspects or exposes:
- **Syntax**: `knows(text_concept, pyi_type): <justification>`
  - `text_concept`: Descriptive snake_case term identifying the domain qualification or scope (e.g. `"agent_session"`, `"mcp_mode"`). It never duplicates the property or type name.
  - `pyi_type`: Structural Python type annotation (e.g. `Set[agent_file_alias.ReadOnlyFile]`, `bool`).
  - Example: `knows("agent_session", Set[agent_file_alias.ReadOnlyFile])`.

#### What `knows` is NOT:
- **Not Duplicate Property Names**: Never duplicate property names (e.g. `knows("read_only_files", Set[ReadOnlyFile])` is invalid; use `knows("agent_session", Set[ReadOnlyFile])`).
- **Not Singletons**: Visible singletons in the same tier are accessible by import. Never write `knows(AliasManager)`.
- **Not Properties of Arguments**: Receiving `target_file: BoundFile` makes `target_file.workspace_path` intrinsic to holding `BoundFile`. Never write `knows("workspace_path")`.
- **Not Internal Assembly Plumbing**: Intermediate plumbing variables needed only to fulfill an action are inferred by the solver, never declared as manual `knows` requirements.

### 2.3 Dual-Key Semantics & Structural Disambiguation
In Groundtalk, `knows` is modeled as a binary relation over two distinct terminal symbols:
```datalog
knows(Concept, Type)
```
- **Concept** (first key): Identifies the semantic domain qualification (e.g. `agent_session`).
- **Type** (second key): Identifies the structural Python type (e.g. `Set_ReadOnlyFile`, `Set_ReadWriteFile`).

#### Disambiguation Without String Hacks
Dual-keying allows multiple properties to share a broad conceptual tag (`agent_session`) while using the structural type to uniquely distinguish them:
- Property 1 provides: `knows(agent_session, Set_ReadOnlyFile)`
- Property 2 provides: `knows(agent_session, Set_ReadWriteFile)`

In Groundtalk, these are distinct ground atoms. A requirement demanding `knows(agent_session, Set_ReadOnlyFile)` unifies strictly with Property 1 and cannot accidentally unify with Property 2.

---

## 3. The Three Grounding Obligation Categories

Groundtalk formalizes three orthogonal categories of grounding declarations:

| Category | Obligation (Must be Proved?) | Availability (Can it Prove Others?) | Primary Usage |
| :--- | :---: | :---: | :--- |
| **`GROUNDING_IMPLEMENTS:`** | **No** (Intrinsic Axiom) | **Yes** (Local & Session Scope) | Declares capabilities constructed/realized by this operation itself (e.g. `action("call", Self)` on `ViewFileTool.call`). |
| **`GROUNDING_PROVISIONS:`** | **Yes** (Must be Proved) | **Yes** (Exported to Collaborators) | Declares state observations or capabilities exported to consumers (e.g. `knows("agent_session", Set[ReadOnlyFile])` on `ReadManager.read_only_files`). |
| **`GROUNDING_REQUIREMENTS:`** | **Yes** (Must be Proved) | **No** (Local Consumption Only) | Declares dependencies required from collaborators or environment $(a - e)$ (e.g. `action("read", FileAlias)` on `ViewFileTool.call`). |

### 3.1 `GROUNDING_IMPLEMENTS:` (Intrinsic Capabilities)
- When an operation implements an interface contract or realizes a specific capability, it declares what it *implements*.
- Because this capability is being constructed by the operation itself, it is an **intrinsic truth**—the reasoner takes it as a given fact for that scope without requiring an external derivation.
- It is immediately available to satisfy other requirements or downstream proofs within the class or session.
- Example:
  ```python
  GROUNDING_IMPLEMENTS:
    - action("call", Self): Implements tool execution for the view file tool.
  ```

### 3.2 `GROUNDING_PROVISIONS:` (Exported Guarantees)
- Declares state observations or capabilities that this entity provides outward to other components.
- The implementation **must prove** how this provision is satisfied (e.g., via internal delegation to an imported collaborator singleton in the same lifecycle tier).
- Once proven, this fact compounds into the reachable scope environment $(d)$ of consuming components.

### 3.3 `GROUNDING_REQUIREMENTS:` (Consumed Dependencies)
- Declares capabilities and knowledge required from external collaborators or the environment $(a - e)$ to fulfill the operation's obligations.
- The reasoner must establish an unbroken derivation path from available providers to these requirements.
- These facts are consumed locally and are never exported to external scopes.

### 3.4 External Boundary Capabilities (`_ext`)
External primitives (`*_ext.pyi`) represent the hardware, OS, or external service boundaries (e.g. filesystem, process execution). 
- `_ext.pyi` modules declare hardcoded grounding provisions as foundational axioms (e.g. `action("read_text", HostPath)`, `action("write_text", HostPath)`).
- When any component declares `imports: <component>_ext`, all grounding facts provided by that extension module become globally reachable facts in scope environment $(e)$ for that component.

---

## 4. Groundtalk Relational Semantics & Subtyping

Groundtalk represents all components, types, scopes, and obligations as a Datalog universe of relational tuples:

```datalog
% Scope Environment (a - e)
param(Scope, Name, Type).
prop(Type, PropName, ReturnType).
op(Type, OpName).
singleton(Component, ServiceType, Tier).
imports(Component, ImportedComponent).
ext_fact(Component, Fact).

% Groundtalk Declarations
implements(Scope, Fact).
provides(Scope, Fact).
requires(Scope, Fact).
```

### 4.1 Subtyping & Subsumption Rules

Pure Datalog lacks native object-oriented typing, but Groundtalk models subtyping and polymorphic subsumption concisely using recursive Horn clauses:

#### Class Hierarchy Transitive Closure:
```datalog
subtype(T, T) :- type(T).
subtype(Sub, Super) :- extends(Sub, Super).
subtype(Sub, Super) :- extends(Sub, Mid), subtype(Mid, Super).
```

#### Predicate Subsumption Rules:
Because Groundtalk's predicate vocabulary is strictly confined to `knows` and `action`, three rules cover 100% of polymorphic reachability across the entire architecture:

1. **Covariant Knowledge Observation (`knows`)**:
   If an environment possesses knowledge of a specialized subtype `Sub` (e.g. `ReadOnlyFile`), it satisfies any consumer requirement expecting the general supertype `Super` (e.g. `FileAlias`):
   ```datalog
   knows(Concept, Super) :- knows(Concept, Sub), subtype(Sub, Super).
   ```

2. **Covariant Capability Targeting (`action`)**:
   If a service provides a capability for any `Super` (e.g. `ToolManager` provides `action("install", Tool)`), it can act upon any specialized `Sub` (e.g. `ViewFileTool`):
   ```datalog
   action(Verb, Sub) :- action(Verb, Super), subtype(Sub, Super).
   action_rel(Verb, Sub, Prep, Aux) :- action_rel(Verb, Super, Prep, Aux), subtype(Sub, Super).
   ```

---

## 5. The Groundtalk Forward-Chaining Solver Engine

Groundtalk is executed by an embedded, zero-dependency **forward-chaining logic engine** in [`grounding_tool.py`](file:///Users/seanmcdirmid/projects/cleanroom-grounding/update_with_ai/support/lib/grounding_tool.py).

### 5.1 Why Forward Chaining?
In Cleanroom, **failure diagnosis is as important as proof success**:
- **Why-Provenance (Success)**: As each rule fires ($\text{NewFact} \leftarrow \text{Rule}(\text{Premise}_1, \text{Premise}_2)$), antecedent pointers are recorded. Tracing these backward generates the exact step-by-step derivation witness blueprint for `lib/*.py` code generation.
- **Why-Not Provenance (Failure)**: Unlike boolean SAT/SMT solvers (which return an opaque `unsat`), a forward chainer computes the full closure of reachable facts. Missing obligations are isolated by trivial set subtraction:
  $$\text{Gaps} = \text{GROUNDING\_REQUIREMENTS} - \text{ReachableFacts}$$

### 5.2 Fact Universe Scaling: Hybrid Backward/Forward Evaluation
In large codebases with dozens of units, hundreds of domain types, and deep class hierarchies, naive forward chaining across the Cartesian product of all types and subsumption rules would generate thousands of irrelevant facts.

Groundtalk uses a **Hybrid Backward/Forward Chaining strategy**:

```
                       ┌──────────────────────────────┐
                       │  Target Scope Goals (Reqs)   │
                       └──────────────┬───────────────┘
                                      │
                                      ▼
                       ┌──────────────────────────────┐
                       │ 1. Backward Relevance Pruner │
                       │    (Cone of Influence Filter)│
                       └──────────────┬───────────────┘
                                      │
                         Pruned Active Symbol Universe
                                      │
                                      ▼
                       ┌──────────────────────────────┐
                       │ 2. Semi-Naive Forward        │
                       │    Chaining Closure          │
                       └──────────────┬───────────────┘
                                      │
                         Reachable Facts & Witness Graph
                                      │
                                      ▼
                       ┌──────────────────────────────┐
                       │ 3. Goal Diff & Near-Misses   │
                       └──────────────────────────────┘
```

1. **Step 1: Goal-Directed Backward Relevance Pruner (Cone of Influence)**:
   - Before forward expansion, the engine performs a fast backward crawl starting from the target goals (`GROUNDING_REQUIREMENTS:` and `GROUNDING_PROVISIONS:`).
   - It filters the **relevant cone of symbols**: only the types, supertypes, subtypes, action verbs, and services that can syntactically participate in deriving the target goals are admitted.
   - All unrelated types, logger services, or distant imported singletons outside this cone are pruned.

2. **Step 2: Scoped Semi-Naive Forward Chaining**:
   - The forward chainer executes strictly within the local component's scoped environment $(a - e)$ and pruned symbol cone.
   - Using **semi-naive evaluation**, the engine evaluates inference rules in iterative rounds, matching rules only against facts newly derived in the immediate preceding round ($\Delta \text{Facts}$).
   - The engine reaches the fixed point in 2–4 quick iterations (<2ms).

3. **Step 3: Dual-Mode Output**:
   - **Success**: Proven goals trace antecedent edges back through the derivation graph to emit the code generation witness blueprint.
   - **Failure**: Set subtraction isolates the exact missing goals, while active rule evaluations isolate "near-misses" (rules where $N-1$ premises succeeded) to supply immediate context to the Neuro-Symbolic Gap Inspector.

---

## 6. Engine Interface Specification

The Groundtalk engine exposes a clean, programmatic interface inside `grounding_tool.py`:

```python
class GroundtalkEngine:
    def verify_scope(
        self,
        scope_id: str,
        environment: ScopedEnvironment,
        implements: List[GroundtalkFact],
        provisions: List[GroundtalkFact],
        requirements: List[GroundtalkFact],
    ) -> GroundtalkResult:
        """Executes hybrid backward pruning and semi-naive forward chaining."""
        ...
```

### 6.1 Return Types
- **`GroundtalkSuccess`**:
  ```python
  @dataclass(frozen=True)
  class GroundtalkSuccess:
      scope_id: str
      witness_tree: Dict[GroundtalkFact, DerivationWitness]
  ```
- **`GroundtalkFailure`**:
  ```python
  @dataclass(frozen=True)
  class GroundtalkFailure:
      scope_id: str
      missing_requirements: Set[GroundtalkFact]
      missing_provisions: Set[GroundtalkFact]
      near_misses: List[NearMiss]
      reachable_facts: Set[GroundtalkFact]
  ```

---

## 7. Lineage, Related Systems & Justification

Groundtalk synthesizes established principles from four major computer science lineages:

| Lineage / System | Core Mechanism | Groundtalk Adoption & Extension |
| :--- | :--- | :--- |
| **Academic Datalog Why-Not Provenance** (PUG, GProM, NedExplain) | Explains missing query answers by identifying unsatisfied inputs or filter blocks. | Direct set subtraction ($\text{Goals} - \text{Reachable}$) and near-miss harvesting for LLM inspection. |
| **Compiler Trait Solvers** (Rust `Chalk`) | Horn clause solver proving trait bounds; reports unsatisfied trait bounds. | Subtyping subsumption rules and capability covariance over object models. |
| **Compile-Time Dependency Injection** (Google `Dagger`) | Static reachability over lifecycle modules; reports `[MissingBinding]` errors. | Scoped lifecycle tier containment and service compounding. |
| **AI Planning** (PDDL / STRIPS) | Preconditions vs. effects; unsolvability explanations for unreachable goals. | `GROUNDING_REQUIREMENTS:` (preconditions) vs. `GROUNDING_PROVISIONS:`/`IMPLEMENTS:` (effects). |

### Why a Custom Forward Chainer?
1. **The Tooling Gap**: Academic why-not prototypes and compiler trait engines do not exist as standalone, zero-dependency Python packages.
2. **Minimal, Focused Problem Domain**: Cleanroom's predicate domain is strictly bounded to `action` and `knows`, and components form strict DAGs. A complete semi-naive forward chainer with subtyping subsumption requires only ~150–200 lines of standard Python.
3. **Native Neuro-Symbolic Diagnostic Pipeline**: A bespoke engine provides full control over the failure artifact, directly extracting the goal difference and near-misses to drive the LLM Gap Inspector.
4. **Hermetic Bazel Execution**: Embedding the engine directly inside `grounding_tool.py` eliminates external pip wheels, C++ toolchains, and environment drift.
