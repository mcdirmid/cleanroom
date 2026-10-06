# Planning Canvas Specification Architecture

## 1. Overview & Architectural Purpose

In the Cleanroom engineering pipeline, the **Planning Canvas** (`planning/<name>.md`) bridges literate High-Level Specifications (`high/<name>.md`) and formal Low-Level Python interface stubs (`low/<name>.pyi`) before runtime library code (`lib/*.py`) or deterministic unit tests (`tests/*_test.py`) are created.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         THE 4-STAGE CLEANROOM PIPELINE                           │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   1. High-Level Spec (high/*.md)                                                 │
│      Literate architectural prose, italic semantic markers, lifecycle tiers       │
│                                                                                  │
│                                  │  high_to_planning.md                          │
│                                  ▼                                               │
│   2. Planning Canvas (planning/*.md)                                             │
│      Intent prose, Factored Contracts with slugs, Epistemic Grounding DAG        │
│                                  │                                               │
│                                  ├── Gate 1: SPEC_QA Arbiter (spec_qa)           │
│                                  ▼  planning_to_low.md                           │
│   3. Low-Level Spec (low/*.pyi)                                                  │
│      Typed Python stubs, DbC docstrings, Natural Language GROUNDING: arguments   │
│                                  │                                               │
│                                  ├── Gate 2: LOW_QA Arbiter (low_qa)             │
│                                  ▼  low_to_lib.md / low_to_test.md               │
│   4. Library & Tests (lib/*.py & tests/*_test.py)                                │
│      Double-blind implementation and contract tests                              │
│                                  │                                               │
│                                  └── Gate 3: QA & Coverage Arbiters              │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

The core objective of the Planning Canvas is **knowledge organization, semantic factorization, and constructive feasibility proof**:
1. **Purging Intent from Contracts**: Removing architectural rationale, user experience motivations, and context window preservation notes from behavioral contracts into a dedicated prose section (`## Intent`), preventing "why" clauses from contaminating technical requirements.
2. **Factoring into Typing and Atomic Contracts**: Decomposing high-level narrative into static typing requirements under `### Typing` and atomic contract requirements under `### Contracts`. Polarity (precondition, assumption, invariant, postcondition) is inferrable from the natural language of the requirement rather than manual section partitions.
3. **Eliminating Conjunctions**: Ensuring every factored contract statement is strictly atomic with zero coordinating or correlative conjunctions (`and`, `or`, `as well as`), preventing hidden multi-part obligations from obscuring verification.
4. **Weaving Cross-Cutting Interactions Without Tables**: Synthesizing interacting contracts into a flat bullet list of concrete operational outcomes with bracketed slug citations (`### Woven Contracts`), avoiding markdown tables for LLM consumption.
5. **Proving Constructive Feasibility via Epistemic Grounding**: Pairing exported capabilities (`### Knowledge Provisions`) with consumer obligations (`### Knowledge Requirements`) under `## Grounding`, proving that all required data pathways, collaborator capabilities, and environmental states are reachable in a strict Directed Acyclic Graph (DAG).
6. **No Code Syntax or Ast Expressions**: Planning documents do not have access to code. Injecting Python syntax (such as `self._tools` or `.convert()`), method calls, Datalog clauses, or Groundtalk predicates into planning specifications is strictly prohibited.

---

## 2. Canonical Document Structure

Every planning specification conforms to canonical markdown sections. Cleanroom distinguishes between standard components (interfaces and implementations) and external boundary components (`_ext`).

### 2.1 Standard Component Structure (Interface & Implementation)

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
[Exported capabilities with unique slugs: - <sentence>. [<slug>]]
### Inherited Deferred Requirements
[For _impl: verbatim repetition of interface deferrals: - <sentence>.\n  - Grounded: [<slugs>]]
### Knowledge Requirements
[Consumer obligations without slugs: - <sentence>.\n  - Grounded: [<slugs>] or - Deferred: <rationale>]
```

### 2.2 External Boundary Specification Structure (`_ext.md`)

External specifications (`planning/<name>_ext.md`) model third-party libraries, host operating system facilities, foreign serialization protocols, and runtime environment boundaries (e.g. `filesystem_ext`, `openai_ext`, `bazel_manifest_ext`). 

Because external boundaries exist **solely to ground other Cleanroom components** rather than implement internal behavioral contracts, their structure is streamlined:

```markdown
# <name>_ext external component

## Intent
[Continuous prose explaining foreign boundary mechanics, third-party libraries, and encapsulation]

## Grounding
### Knowledge Provisions
[Exported foundational capabilities with unique slugs: - <sentence>. [<slug>]]
```

**External Component Rules**:
- Section inventory is closed strictly to `## Intent` and `## Grounding`.
- `## Factored Contracts` is **strictly prohibited** in external specifications.
- Under `## Grounding`, only `### Knowledge Provisions` is permitted; `### Knowledge Requirements` is **strictly prohibited**.
- External components **cannot be cited in `### Woven Contracts`**. External components supply knowledge provisions for grounding, not behavioral contracts for weaving.
- External components never declare `implements:`.

---

## 3. Intent Specification (`## Intent`)

Architectural intent, conversational UX motivations, token budget economics, and multi-turn lifecycle rationale are vital for human and LLM comprehension. However, embedding intent directly into behavioral requirements (e.g., *"Executing a tool produces a suppression key to hide prior conversation turns and conserve agent context window capacity"*) creates conflated contracts where verification tools cannot distinguish the binding behavioral guarantee from the architectural justification.

**Rules for Intent**:
- The `## Intent` section captures high-level design rationale, domain background, conversational turn minimization, and context management in **continuous prose paragraphs**.
- Sub-headers (`###`) are strictly prohibited under `## Intent`.
- Factored contracts, grounding specifications, and woven contracts must be completely purged of intent clauses, justification phrases ("in order to", "so that", "to indicate"), and background explanations.

---

## 4. Factored Contracts & The Zero-Conjunction Rule

Factored contracts decompose narrative prose from `high/<name>.md` into atomic, single-fact statements categorized across static types and behavioral contracts.

### 4.1 Static Typing (`### Typing`)
- Structural facts expressible solely in type signatures (e.g. record fields, dataclass properties, parameter models, type parameters, and closed variant sets).
- *No Slugs & Never Woven*: Typing facts represent passive schema declarations, do not participate in reachability weaving, and are never cited; items under `### Typing` omit bracketed slugs.
- *Omitted in Implementations*: Implementation specifications (`planning/<name>_impl.md`) omit `### Typing` unless specifying private internal data structures, as public domain types are owned by interface components.

### 4.2 Behavioral Contracts (`### Contracts`)
- Lists atomic behavioral contracts, operational requirements, invariants, and failure rules.
- Polarity (precondition, assumption, invariant, postcondition) is inferrable from natural language rather than encoded in section headers:
  - *Caller Assumptions*: Formulated using caller-obligation syntax (e.g., "A caller supplies an acyclic graph", "A caller guarantees that targets exist") so downstream low-level stubs distinguish caller assumptions from callee postconditions.
  - *Callee Guarantees*: Declarative postconditions guaranteed upon successful or failed execution.
- Every contract bullet ends with a period followed by its unique bracketed snake_case slug: `- <sentence>. [<slug>]`.

### 4.3 The Zero-Conjunction Rule
In legacy specifications, requirements were frequently bundled with conjunctions:
> *Legacy Anti-Pattern*: "A dictionary parameter type converts dictionaries using key and element parameter types, providing feedback when conversion fails."

This sentence combines:
- Dictionary key conversion.
- Dictionary value conversion.
- Failure feedback generation.

When downstream auditing or test derivation attempts to verify a requirement, compound sentences cause **Failure Explanation Asymmetry**: an auditor cannot pinpoint which clause failed.

**The Rule**:
- Coordinating conjunctions (`and`, `or`), correlative conjunctions (`both ... and`), and compound phrases (`as well as`) are **strictly prohibited** in factored contracts when combining multiple independent truths or distinct obligations.
- Multiple actions, composite arguments, or alternative states must be split into distinct atomic bullet points:
  - *Atomic Fact 1*: `A dictionary parameter type converts dictionary keys with a key parameter type. [convert_dict_keys]`
  - *Atomic Fact 2*: `A dictionary parameter type converts dictionary values with an element parameter type. [convert_dict_vals]`
  - *Atomic Fact 3*: `A parameter type provides feedback on conversion failure. [convert_failure_feedback]`
- **The Set Definition Exception**: When a conjunction expresses a closed set, union, or variant enumeration (e.g., `Wire types are limited to wire strings, wire integers, wire booleans, wire floats, wire lists, and wire dictionaries.`), it defines a single set rather than repetition of truth. Splitting a set definition into fragmented atomic lines would falsify the statement; therefore, set-expressing conjunctions cannot and must not be separated.
- **One-Way Conditionals**: One-way conditionals ("A if B") are preserved strictly as one-way conditionals ("A when B"); translating "if" into "if and only if" or synthesizing the uncontracted converse ("not A when not B") is strictly prohibited unless explicitly contracted.

---

## 5. Woven Contracts: Cross-Cutting Interaction Synthesis

While factored contracts isolate individual atoms of behavior, real software emerges from the **interaction** of multiple contracts. Cross-cutting rules (such as parameter validation triggering diagnostic feedback, or default value substitution occurring when an optional parameter is omitted) involve multiple factored contracts acting together.

Under `### Woven Contracts`, these interactions are explicitly synthesized into concrete operational behaviors, failure outcomes, and dispatch paths:
- **Flat Bullet List**: Woven contracts are formatted strictly as a flat bullet list (`- `); markdown tables (`|`) are strictly prohibited.
- **Sentence and Citation Syntax**: Each woven contract bullet is a complete declarative English sentence ending with a period followed by its bracketed citation list: `- <sentence>. [<citations>]`.
- **Citing Constituent Contracts**: Local contract citations list bare slugs; imported citations group under their component name: `[<local_slugs>, <component>: [<imported_slugs>]]`.
- **Exclusion of External Components (`_ext`)**: External components are never cited in woven contracts. External components provide knowledge provisions for grounding, not behavioral contracts for weaving.
- **Caller Assumptions**: Caller assumptions are never woven into callee failure ladders or defensive exception branches; caller assumption violations represent undefined behavior rather than handled failure outcomes.
- **Explicit Diagnostic Outcomes**: When an operation fails under multiple conditions, each condition maps to an explicit woven contract stating the concrete diagnostic feedback string or message template.

---

## 6. Epistemic Grounding Architecture

Cleanroom software construction relies on formal grounding specifications to ensure that high-level contracts are constructively feasible before writing runtime implementation code (`lib/`) and unit tests (`tests/`).

Historically, Cleanroom attempted to verify grounding through two paradigms:
1. **Relational Groundtalk (`.gt`)**: Custom Datalog Horn-clause reachability solvers (struggled with complex expressions, nested collections, and custom toolchain friction).
2. **Static Python Grounding (`grounding/*.py`)**: Straight-line typed Python feasibility proofs checked via Pyright. While this resolved toolchain friction, it introduced **Mechanistic Hallucination of Success**: because Pyright only verifies syntactic type assignability, LLMs routinely pacified the type checker by fabricating phantom literals, accessing arbitrary dictionary keys, or copying contract docstrings into hollow functions terminating in `raise NotImplementedError`.

Cleanroom solves this through **Pure Epistemic Grounding via Slugs in Planning Specifications**, verified by `spec_qa`, translated into Natural Language Grounding Arguments (`GROUNDING:`) in Low-Level Specifications, and verified by `low_qa`.

### 6.1 Slug Asymmetry: Why Provisions Have Slugs and Requirements Do Not

In Cleanroom Planning, slugs exist **exclusively for citation and reachability**:
- **`### Contracts` have slugs** because they are cited in `### Woven Contracts` and traced into unit tests.
- **`### Knowledge Provisions` have slugs** because they are cited in `Grounded: [...]` lists by consumers and internal operations.
- **`### Typing` omits slugs** because static type definitions are not cited in reachability.
- **`### Knowledge Requirements` omit slugs** because requirements are terminal sinks—they are *consumers* of knowledge, never providers. No other construct ever cites a requirement.

### 6.2 Knowledge Provisions (`### Knowledge Provisions`)
- What values, states, or operational capabilities does this component make available to others or to its own operations?
- Every provision ends with a unique bracketed snake_case slug: `- <sentence>. [<slug>]`.

### 6.3 Knowledge Requirements (`### Knowledge Requirements`)
- What information, observations, or actions must be available to satisfy the component's contracts?
- Formatted as plain declarative sentences without slugs: `- <sentence>.`
- Every requirement is followed immediately by an indented sub-bullet:
  - `  - Grounded: [<slugs>]`: Proven via cited knowledge provisions or external inputs.
  - `  - Deferred: <rationale>`: In interface specifications, requirements depending on concrete backing state, disk storage, or environment access declare deferral.

### 6.4 Verbatim Repetition & The Zero-Deferred Invariant
When an implementation component (`_impl`) implements an interface, it repeats every deferred requirement sentence **verbatim** under `### Inherited Deferred Requirements`:

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

**Benefits & Rules**:
1. **Self-Contained & Literate**: The implementation document is completely readable without having to look up external requirement IDs in the interface.
2. **The Zero-Deferred Invariant**: In implementation specifications (`planning/<name>_impl.md`), open deferrals (`  - Deferred:`) are strictly prohibited; 100% of inherited and local requirements must be grounded.
3. **Inherited Grounding Audit**: Every inherited deferred requirement must be grounded by at least one imported or local knowledge provision. If a requirement needs zero knowledge provisions, it should have been grounded earlier in the interface.

### 6.5 Strict Component Qualification of Imported Provisions
To prevent ambiguity and enforce clean architecture boundaries:
- **Imported Provisions Must Be Qualified**: Any imported knowledge provision cited in a `  - Grounded:` sub-bullet must be explicitly qualified with its component name: `<component>: [<slug>]` (e.g. `[filesystem_ext: [host_path_operations]]`, `[dag_storage: [dag_storage_service]]`).
- **Bare Slugs Reserved for Local Provisions**: Unqualified bare slugs are strictly reserved for local knowledge provisions declared within the same file's `### Knowledge Provisions`, or the special keyword `caller input`.
- Citing imported provisions without qualification triggers an immediate structural linter error.

### 6.6 The Strict Acyclicity Invariant (DAG Anti-Circularity)
Because grounding allows internal composition (a requirement grounded by local provision slugs):
1. **No Tautologies**: A provision $[P]$ cannot ground the requirement that enables $[P]$.
2. **No Cycles**: Provision $[A]$ cannot ground a requirement that enables $[B]$ which grounds a requirement that enables $[A]$.
3. **Well-Founded Base**: Every grounding path must terminate in external imports (`component: [slug]`) or caller input parameters (`caller input`). The directed graph over provisions must be an acyclic DAG.

---

## 7. Downstream Translation to Low-Level Specifications (`low/`)

When translating planning specifications into Low-Level Specifications (`low/`), the grounding resolutions established in `planning/<name>_impl.md` are translated into **Natural Language Grounding Arguments** under a dedicated `GROUNDING:` docstring section in `low/<name>_impl.pyi`.

### Rules for `GROUNDING:` in Low-Level Stubs:
1. **Implementation Stubs Only (`_impl.pyi`)**:
   - `GROUNDING:` sections appear strictly in implementation stubs (`low/<name>_impl.pyi`).
   - Interface stubs (`low/<name>.pyi`) define abstract protocols and must never mention collaborator singletons or implementation classes.
2. **Citing Collaborator Classes and Methods**:
   - Unlike interface contracts, the `GROUNDING:` argument in an implementation stub is explicitly expected to cite:
     - Imported component names (e.g. `agent_node_config`, `dag_storage`)
     - Collaborator class names (e.g. `NodeConfig`, `DagStorage`, `EditManager`)
     - Collaborator method and property names (e.g. `DagStorage.materialize_template`, `EditManager.has_modifications`)
     - Private backing state fields (e.g. `self._tools`)
3. **Execution Blueprint for Library Implementers**:
   - Library code (`lib/<name>_impl.py`) directly implements the collaborator lookups and method invocations argued in `GROUNDING:`.

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
```

---

## 8. Verification Architecture: The Auditor Roles (`spec_qa` & `low_qa`)

Cleanroom coordinates verification through dedicated, independent **Auditor Roles**. To keep authoring agents in deep semantic reasoning mode and prevent mechanistic constraint-satisfaction gaming, Cleanroom enforces the foundational principle:

> **"Authors Author; Arbiters Lint and Audit."**

Authoring models (`high`, `planning`, `low`, `lib`, `test`) are deliberately insulated from interactive linters and type checkers. When an authoring agent is given direct access to a linter, it inevitably degenerates into mechanistic gaming—tinkering with ASTs, regexes, and syntax to pacify tools rather than reasoning deeply about domain semantics and contract fidelity.

Instead:
- **Linters and verifiers are owned by Arbiters**: `spec_lint.py` is owned by `spec_qa`; `low_lint.py` and Pyright are owned by `low_qa`.
- **Arbiters execute verification suites internally**: `spec_qa` and `low_qa` run linters and static analyzers as fast pre-flight sanity checks, translating any mechanical defects into actionable, non-prescriptive blame feedback for the author.

### 8.1 The Three-Gate Cleanroom Pipeline

1. **Gate 1 (`spec_qa`)**: Certifies conceptual specification integrity, Zero-Conjunction factorization, provision DAG acyclicity, and epistemic reachability between `high/*.md` and `planning/*.md`. Stamps `SPEC_QA_AUDIT: <timestamp>`.
2. **Gate 2 (`low_qa`)**: Certifies static type soundness, structural stubs, and concrete collaborator grounding blueprints in `low/*.pyi` and `low/*_impl.pyi`. Stamps `LOW_QA_AUDIT: <timestamp>`.
3. **Gate 3 (`qa` & `coverage`)**: Certifies double-blind runtime implementation correctness and 100% statement test coverage in `lib/*.py` and `tests/*_test.py`. Stamps `QA_AUDIT: <timestamp>` and `COVERAGE_AUDIT: <timestamp>`.

---

## 9. Common Pitfalls & Checklist

- [ ] **Code syntax in planning**: Inserting Python statements, method calls (`.convert()`), or field declarations (`self._foo`) into planning grounding.
- [ ] **Slugs on requirements**: Appending bracketed slugs to `### Knowledge Requirements` bullets instead of keeping them purely on `### Knowledge Provisions` and `### Contracts`.
- [ ] **Conjunction leakage**: Using `and`, `or`, `as well as`, or `both ... and` to combine distinct facts or obligations in factored contracts.
- [ ] **Splitting set conjunctions**: Breaking a closed set or variant enumeration into fragmented partial statements that falsify the set definition.
- [ ] **Weaving typing contracts**: Including typing facts in woven contracts instead of keeping them purely in `### Typing`.
- [ ] **Citing external components in woven contracts**: Citing `_ext` components in `### Woven Contracts` instead of using them purely for grounding.
- [ ] **Bare imported provisions**: Citing imported knowledge provision slugs without component qualification (`<component>: [<slug>]`).
- [ ] **Open deferrals in implementations**: Leaving `  - Deferred:` sub-bullets in `planning/<name>_impl.md`.
- [ ] **Paraphrasing inherited deferrals**: Altering the wording of deferred interface requirements under `### Inherited Deferred Requirements` instead of repeating them verbatim.
- [ ] **Circular grounding**: Grounding a provision using itself or creating cyclic dependencies among local provisions.
- [ ] **Phantom imports**: Citing `component: [slug]` in grounding or woven contracts without declaring `component` in front-matter `imports:`.
- [ ] **Markdown tables**: Using tabular grids anywhere in the document instead of flat bullet lists.
- [ ] **Missing period**: Terminating a factored contract, woven contract, provision, or requirement sentence without a period.
- [ ] **Sub-headers under Intent or Woven Contracts**: Introducing unauthorized `###` sub-headers.
