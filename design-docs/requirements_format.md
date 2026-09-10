# Requirements Specification Format: Natural Language Requirements

## 1. Overview & Architectural Purpose

Requirements bridge the ontological structure established during **Grounding** with the executable behavior validated during **Low-Level Specification (LLS)** and unit testing.

While Grounding captures the static structural contract (what entities exist, their types, properties, and operations), the dynamic semantic contract is partitioned into two distinct sections:
- **Assumptions (`## Assumptions`)**: Preconditions and input/environment invariants assumed by the component. A failure of an assumption results in **undefined behavior**, unless there is an explicit requirement to handle it.
- **Requirements (`## Requirements`)**: Guaranteed behavioral contracts, observable outcomes, state transitions, and explicit failure-handling obligations that the component must deterministically satisfy.

### Assumptions vs. Requirements

Separating assumptions from requirements provides crucial architectural clarity:
1. **Assumptions are Preconditions**: They declare what the component assumes callers and upstream systems satisfy.
   - *Undefined Behavior on Failure*: If an assumption fails, the resulting system behavior is completely undefined (the component is not required to catch, validate, or gracefully recover from the violation).
   - *Explicit Handling Exception*: If the specification explicitly includes a requirement stating how to detect or handle that condition (e.g. failing with an error message), then handling it becomes a binding requirement (defined behavior).
   - *Preconditions on Client Operations*: Preconditions on operations invoked by client components (e.g., `All installed tools in a tool manager have unique names` for `install_tool`, or `All parameters of a tool have unique names` for `Tool.parameters`) must be declared under `## Assumptions` in the interface specification so calling code understands what it must satisfy.
2. **Requirements are Binding Guarantees**: They declare what the component promises to deliver when assumptions are met, or explicit failure behaviors that must be handled deterministically.
   - *Software Interface Contract*: `When tool execution fails, the response content includes error and diagnostic messages along with guidance on how the agent can execute the tool correctly.` (Contract that all concrete `Tool` implementers must satisfy).
   - *Private Model Defense in Implementation*: In implementation specifications (`tool_provider_impl`), requirements define how the system defends against the unreliable black-box AI model (e.g., `Executing a tool by name fails if no installed tool matches the requested name`). Because the AI model is a black box and the runner is not a semantic proxy for it, these manager-oriented failure protections are strictly implementation requirements, not interface contracts for other software components.
3. **The Grounded Failure Principle**:
   Never assume or invent expected failures where none are specified in upstream interfaces. Downstream implementations must not introduce failure-handling requirements for operations whose interface definitions do not declare that they can fail. An invalid input or unmet condition on an operation without an explicit failure requirement is an assumption violation resulting in undefined behavior, not an expected failure that downstream components must deterministically handle.
4. **Model Boundary Defense & Comprehensive Verification**:
   Because inputs from an external AI model cannot be assumed to follow contracts, components sitting on the model interaction boundary (such as tools, parameter converters, and tool managers) naturally require comprehensive verification. The `## Purpose` section should motivate that we cannot assume the model follows the contract and must verify everything, which drives the architectural necessity for expected failures. However, for those failures to be binding requirements rather than undefined behavior, they must be grounded explicitly in the interface specification.

### The Natural Language Sentence Standard

Formal logic notations with universal/existential quantifiers (`for any...`), invocation variables (`v_call`), parameter accessors (`@name`), and formula predicates introduce premature pseudo-code and implementation assumptions into high-level grounding specifications. Attempting to formally specify internal algorithmic mechanics at this stage is counter-productive to downstream code generation.

Instead, assumptions and requirements are listed directly as **natural language strings**:
- **One Sentence per Item**: Each assumption and requirement is stated as a single, clear, declarative sentence.
- **No Formula Language**: No AST predicates, boolean algebra symbols (`==`, `!=`), or pseudo-code expressions.
- **No Quantifiers**: No `for any`, `there exists`, or bound variable prefixes (`v_call`, `v_param`).
- **Grounded Terminology**: Sentences naturally reference the types, operations, and properties established in the 4-column grounding table.

---

## 2. Core Principles & Sentence Formulation

### 2.1 Declarative Behavioral Phrasing
Each requirement expresses an observable behavioral guarantee or constraint rather than imperative execution instructions:
- *Good*: `When a parameter is required, an argument must be supplied for tool execution.`
- *Bad*: `for any v_param of Parameter, if v_param.is_required then v_param is nl"argument must be supplied for tool execution"`

### 2.2 Operational Preconditions and Failure Handling
Describe conditional failures and the recovery guidance delivered to callers:
- *Good*: `When tool execution fails, the response content includes error and diagnostic messages along with guidance on how the agent can execute the tool correctly.`
- *Good*: `Requesting a tool from the tool manager when no installed tool matches the name results in an expected failure.`
- *Good*: `Executing the read tool fails if line numbers are not requested when reading a read-write file.`

### 2.3 Observable Lookup and Registry Contracts
Express lookup and discovery results directly without prescribing internal indexing algorithms or hash maps:
- *Good*: `Requesting a tool from the tool manager by name returns the installed tool matching that name.`
- *Good*: `Getting tool names from the tool manager returns the names of all tools available to be requested.`

### 2.4 Environmental Isolation & Transformation
State transformations, sanitization, and masking behavior as clear guarantees:
- *Good*: `On successful read tool execution for a read-only file, the returned file content is sanitized to mask host paths.`
- *Good*: `Sanitizing text masks occurrences of host paths with the corresponding file alias short names.`

### 2.5 Scope Attribution: Object Types, Data Type Operators, and Orphaned Requirements

Each requirement and assumption in a grounding document must explicitly list the scope it applies to:
- **`Type.operation:`**: Applied to a callable operation of an object type (typically representing operational postconditions, state transitions, return values, or operation-specific failure handling).
- **`Type:`**: Applied directly to an object type (representing invariants on the type, environmental invariants, or invariants across the object type's properties) or an operator-like requirement on a data type.
- **`orphaned:`**: Applied when a requirement or assumption cannot be attributed to an active object type or valid data-type operator.

#### Object Types vs. Data Types
- **Object Types**: Active services (`singleton type`, `poly type`, `override singleton type`, `override poly type`) actively execute lifecycle operations, maintain mutable state, and enforce contracts. They own behavioral requirements and operational postconditions.
- **Data Types (Allowed Operator-Like Requirements)**: Data types (`data type`, `variant`) are passive records and values. However, requirements on data types **are allowed** if they describe operator-like behaviors intrinsic to the value itself (such as converting to a string, formatting, displaying itself by its short name, or structural equality comparisons). For example:
  `- FileAlias: A file alias displays itself by its short name when converted to a string.`
- **Data Types (Prohibited Property Formation Requirements)**: What is **strictly prohibited** on data types is requiring how their properties are formed, derived, or computed (for example, *"A file alias short name is a minimal unambiguous relative path identifying the file within an agent session"*). Data types are passive; deriving, binding, and validating property values is the responsibility of active object types/services that create or manage them (e.g. `AliasManager`).
- **Orphaned Requirements**: When an HLS prescribes how a data type's properties are formed without attributing the responsibility to an active object service in scope, that requirement is **not viable** on the data type and must be listed as **`orphaned:`**:
  `- orphaned: A file alias short name is a minimal unambiguous relative path identifying the file within an agent session.`
- **Retention of Orphaned Requirements**: Orphaned requirements must still be listed in grounding documents because they highlight architectural omissions in the specification that need to be resolved (such as updating `file_alias` so that `AliasManager` is explicitly given responsibility for computing and verifying minimal short names).

#### Attributing Invariants and Assumptions
- An invariant on a property of an object type applies to the type (`Type: <sentence>`), as do general state invariants.
- Postconditions, outcome mutations, and error recovery behaviors apply to the specific operation (`Type.operation: <sentence>`).
- Assumptions (preconditions) should ideally be operation preconditions (`Type.operation: <sentence>`) or environmental preconditions on an object type (`Type: <sentence>`). Any assumption that cannot be bound to an object type must also be listed as `orphaned:`.

### 2.6 Grounded Behavioral Satisfiability & Custody
- **Satisfiability**: Every requirement must be deterministically satisfiable by the component using only its declared in-scope collaborators, inputs, and configuration. If a requirement states that a component performs an action or enforces an invariant requiring external knowledge that is not provided to it, the requirement is ungrounded.
- **Anti-Floating Requirements**: Requirements must not rely on hand-wavy external mechanisms (such as "loads configuration from a target module" without specifying how the target identity is acquired). Custody of all necessary inputs must be traceable.
- **Semantic Grounding vs Syntactic Check**: Merely binding a requirement string to an operation name (`Type.operation:`) only satisfies syntactic attribution. It does NOT guarantee semantic grounding unless the operation actually has the necessary arguments and collaborators to fulfill the contract.

---

## 3. Distinguishing Behavioral Requirements from Table Definitions, Knowledge, and Purpose

A critical task when extracting requirements from HLS prose is separating true behavioral contracts from structural definitions, static knowledge, and domain purpose:

1. **Constituent Properties vs. Requirements**:
   - Statements in prose that simply introduce or enumerate the fields of a record (e.g., *"A log event provides an event name, a single-line summary, and a verbose transcript representation"*, or *"A model configuration defines model identifiers, timeouts, and iteration limits"*) define static structure.
   - These belong exclusively in the 4-column grounding table as `property` rows. They are **never** behavioral requirements and must not be duplicated under `## Requirements`.
2. **Static Knowledge and Algebraic Relationships vs. Requirements**:
   - Statements describing static type knowledge, type algebra, or mathematical relations between types (e.g., *"Concatenating a workspace root and a workspace path produces an absolute path"*) describe semantic definitions, not observable behavioral contracts on an active component.
   - Such knowledge belongs in ontological comments or type definitions, not in `## Requirements`.
3. **Domain Purpose and Semantic Intent ("indicates") vs. Requirements**:
   - Clauses explaining the purpose or rationale of a flag or data state (e.g., *"A dependency can be silent to indicate that the dependent node does not depend on the dependency's content and so does not need to receive change messages about the dependency"*) express domain purpose.
   - The information is simply given to the component (the dependency is flagged as silent in the implementation of dag storage, typically directed by user instructions or manifests). There is no runtime "call" to make it silent, and the component does not decide why it is silent.
   - The observing service (such as `dag_storage`) merely exposes the property and checks it in its operations (e.g., excluding silent dependencies when registering dependents). Statements explaining what a flag indicates or why it exists describe domain purpose, not behavioral requirements, and must never be placed in `## Requirements`.
4. **Type-System Constraints**:
   - Constraints handled by the static type system (such as `actual_type` referencing a data type or `wire_type` being a string/integer/boolean) are declared in the grounding table and omitted from requirements.
5. **Definitional Clarifications**:
   - Clarifications explaining what a concept represents conceptually (e.g. why an actual type is meta or why a tool has a description) belong in the table `comment` column as justification, not in `## Requirements`.
6. **Trivial State Mutations**:
   - Do NOT specify basic setter or registration mechanics (e.g., `Installing a tool adds it to the tool manager's tools`). Basic setters need no standalone requirements because lookup and retrieval contracts already verify availability.
7. **Focus on True Behavioral Rules**:
   - Focus strictly on validation boundaries, conditional branches, expected failure signals, and caller diagnostic recovery.

---

## 4. Document Placement Standard

Requirements and assumptions are placed directly in the specification documents. Cleanroom uses the canonical Python interface stub (`.pyi`) format, where requirements are co-located inside class and method docstrings.

### 4.1 Canonical Format: Python Interface Stubs (`.pyi`)

In `.pyi` grounding specifications (see [New Grounding Format](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/new_grounding_format.md)), requirements and assumptions are embedded directly into class and method docstrings under structured headers:
- `PURPOSE:` Architectural rationale and intent.
- `FRESH_ASSUMPTIONS:` Caller preconditions authored locally on this member.
- `INHERITED_ASSUMPTIONS:` Preconditions inherited from ancestors, managed by `grounding_tool.py --sync`.
- `FRESH_REQUIREMENTS:` Behavioral contracts and guarantees authored locally on this member.
- `INHERITED_REQUIREMENTS:` Behavioral contracts inherited from ancestors, managed by `grounding_tool.py --sync`.
- `GROUNDING_ARGUMENT:` Semantic derivation path establishing runtime values.

```python
@operation
def execute_tool(self, actual_parameter_bindings: ActualParameterBindings) -> Response:
    """
PURPOSE:
Executes the tool with validated parameter bindings.

FRESH_REQUIREMENTS:
- When a parameter is required, an argument must be supplied for tool execution.
- When tool execution fails, the response content includes error and diagnostic messages along with guidance on how the agent can execute the tool correctly.

INHERITED_REQUIREMENTS:
- [Tool] Executing a tool produces an observable Response record.
"""
    ...
```

For top-level requirements not attributed to an active object type, they are placed in the module's `__orphan__()` function:

```python
def __orphan__() -> None:
    """
PURPOSE:
Captures system-wide or non-attributed architectural requirements.

FRESH_REQUIREMENTS:
- A file alias short name is a minimal unambiguous relative path identifying the file within an agent session.
"""
    ...
```

### 4.2 Historical Format: 4-Column Markdown Tables (`.md`)

*(Note: Superseded by the `.pyi` format; preserved for historical context on earlier specifications).*

In legacy markdown grounding specifications (`<name>.md`), the **Assumptions** (if any) and **Requirements** sections were placed directly after the 4-column ontological table:

```markdown
# <component_name> grounding

imports: ...
implements: ...

| kind | name | type signature | comment |
| :--- | :--- | :--- | :--- |
| ... | ... | ... | ... |

## Assumptions

- <Type>.<operation>: <Assumption sentence 1>.
- <Type>: <Assumption sentence 2>.

## Requirements

- <Type>.<operation>: <Requirement sentence 1>.
- <Type>: <Requirement sentence 2>.
- orphaned: <Requirement sentence 3>.
```

---

## 5. Testing Natural Language Tool Guidance & Error Messages via Supervising LLMs (TODO)

### 5.1 The Verification Boundary in Deterministic Unit Tests
Requirements specifying that failed tool executions return error and diagnostic messages along with guidance on how the agent can execute the tool correctly (e.g., `When tool execution fails, the response content includes error and diagnostic messages along with guidance on how the agent can execute the tool correctly`) represent natural language guidance intended for an LLM agent rather than static string contracts.

In deterministic unit tests:
- Tests must never assert specific unpinned English wording or substrings.
- Standard unit tests cannot evaluate whether diagnostic text actually provides sufficient, actionable semantic guidance to help an agent recover.
- Consequently, these requirements are currently marked as untestable in deterministic unit test suites and cataloged in the `# Untested requirements:` footer.

### 5.2 Future Verification via Supervising LLMs

**TODO**:
- Develop a verification mechanism where unit tests can generate a suite of targeted evaluation questions to ask a supervising LLM.
- The supervising LLM inspects the tool failure response and answers questions verifying:
  1. Does the message accurately diagnose the specific failure condition that occurred?
  2. Does the message provide clear, actionable instructions enabling an agent to fix its parameters and invoke the tool correctly?
- This will enable rigorous automated verification of natural language agent guidance without relying on brittle, unpinned string-matching assertions in unit tests.

---

## 6. Grounding Problems and Fabricated Requirements

### 6.1 Grounding Problems
A **grounding problem** occurs when a semantic gap exists between the High-Level Specification (HLS) and the executable Low-Level Specification (LLS / library implementation):
1. **Incomplete Derivation Paths**: An HLS requires a capability or property, but the grounding specification cannot derive it from declared collaborators or inputs (`GROUNDING_ARGUMENT:` failure).
2. **Omitted Operational Branches**: An HLS specifies nominal happy-path behaviors or partial failure cases, but omits non-standard branches, unprompted responses, or empty input sets. The grounding and implementation are left with undefined behavior for real runtime scenarios.
3. **Unchecked Architectural Notes**: An HLS communicates architectural intent, operational boundaries, or failure-mode warnings in its `## Purpose` or meta-notes, but alignment drops them instead of formulating binding `FRESH_REQUIREMENTS:`.

**Resolution Protocol**:
Grounding problems MUST be resolved upstream at the specification level (HLS and grounding `.pyi`), never downstream in code. When a grounding gap is identified, the HLS must be refined with explicit behavioral guarantees, outcome branches, and intent notes, which are then formally grounded into `FRESH_REQUIREMENTS:` with complete derivation arguments.

### 6.2 Fabricated Requirements (Anti-Pattern)
A **fabricated requirement** occurs when library implementation code (`_impl.py`) or unit tests (`_impl_test.py`) introduce behaviors, artificial return signals, short-circuit terminations, or `# Requirement:` comments that do not exist in the grounding specification (`FRESH_REQUIREMENTS:` or `INHERITED_REQUIREMENTS:`).

**The Cascading Failure of Fabricated Requirements**:
1. **Masking Specification Gaps**: Instead of escalating an unhandled case back to the HLS, the implementer invents ad-hoc code (e.g. terminating an iterative session when no tools are called) and decorates it with a fake `# Requirement:` comment.
2. **Bias Rule Inversion in Tests**: A test author looks at the fabricated code, transcribes its behavior, and writes a unit test that explicitly asserts the fabricated behavior.
3. **Verification Bypass**: Because the test suite actively asserts and passes the fabricated behavior, automated verification and type-checking succeed, creating a dangerous illusion of system correctness while catastrophic runtime failures (such as bypassing verification checks or aborting prematurely) occur in production.

**Strict Architectural Rules**:
- **Verbatim Citation**: Every `# Requirement:` comment in library code and test suites must quote verbatim an exact requirement string from `FRESH_REQUIREMENTS:` or `INHERITED_REQUIREMENTS:` in the grounding specification.
- **Zero Unmandated Behavior**: No library code may implement synthetic outcomes, artificial completion paths, or side-effects not mandated by the grounding contract.
- **Independent QA Auditing**: Passing test suites must be audited (by QA and alignment tooling) to ensure that assertions genuinely verify the specific postconditions of the requirements they cite, rather than asserting fabricated shortcuts or passing via tautology.


