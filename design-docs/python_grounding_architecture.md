# Architecture & Design: Static Python Type-Checked Grounding Proofs

## Executive Summary

Cleanroom software construction relies on formal grounding specifications to bridge high-level architecture and planning specifications with concrete implementations and tests. Historically, Groundtalk used relational Datalog logic programming (`.gt`) and custom Horn-clause solvers to verify reachability and collaborator wiring. However, relational Datalog solvers struggled with complex expression evaluation, nested generic collections, and required extensive custom tooling that ran separate from mainstream developer toolchains.

This document establishes the new architecture: **Grounding as Static Constructive Feasibility Proofs in Typed Python**. By restricting Python to a straight-line, purely functional dataflow subset, Pyright performs 100% static formal verification in milliseconds with zero runtime execution, zero solver friction, and zero mocking ceremony.

---

## 1. Core Philosophy: Feasibility Verification in Typed Python

In Cleanroom, grounding does not implement runtime algorithms, dynamic loops, or error-handling control flows. Instead, grounding provides **constructive proofs of operational feasibility**:
1. Demonstrating that every required collaborator, service, and data pathway is statically accessible.
2. Demonstrating that data types, wire formats, domain conversions, and collection projections align across all boundaries.
3. Demonstrating that all necessary information to detect, branch, diagnose, and recover from failures is available and correctly typed.

Because these proofs are expressed in standard Python 3.12 with rich type annotations, the formal verifier is standard Pyright. An entire system's grounding proofs can be verified statically in milliseconds.

```
       Planning Canvas (`planning/*.md`)
                     │
                     ▼
       Low-Level Stubs (`low/*.pyi`)
                     │
                     ▼
  Grounding Feasibility Proofs (`grounding/*.py`)  ◄── Pyright Verification (<10ms)
                     │
                     ▼
      Full Implementation (`lib/*.py`)
                     │
                     ▼
         Unit Tests (`tests/*_test.py`)
```

---

## 2. Core Architectural Tenets

### 2.1 No Control Flow / Terminal NotImplementedError
Grounding modules contain **zero control flow**:
- Prohibited: `if`, `elif`, `else`, `match`, `case`
- Prohibited: `while`, `for`, `async for`
- Prohibited: `try`, `except`, `finally`
- Prohibited: `return`, `break`, `continue`, `yield`
- Prohibited: `...` (ellipsis) in executable method bodies
- Terminal Statement: Every method/function body terminates strictly with `raise NotImplementedError` (non-`NotImplementedError` raises are prohibited)

Grounding is straight-line code. Each method in a grounding module consists of sequential variable bindings proving knowledge accessibility and feasibility without dynamic execution. Because methods terminate with `raise NotImplementedError`, Pyright performs static type verification on all preceding statements without requiring return statements or mock response values. Handling errors, catching exceptions, dispatching alternate branches, and returning actual runtime values belong exclusively in `lib/*.py`.

### 2.2 Caller Assumptions vs. Callee Requirements
A critical distinction in Cleanroom formal verification is:
> **"Callees expect assumptions; callers satisfy them."**

1. **Caller Assumptions (`ASSUMPTIONS:`)**:
   - Invariants guaranteed by callers, upstream components, or the environment (e.g., *a dependency graph is acyclic by construction*, *declared workspace files exist*, *inputs conform to parameter contracts*).
   - Callee components accept assumptions axiomatically. Callee code must **never** check caller assumptions. Defensive checks for caller assumptions represent dead assumption code—they cannot be triggered by valid callers, tests are forbidden from simulating assumption violations, and such checks show up as permanent coverage deficits.
   - In grounding, assumptions require **zero code, zero checks, and zero branches**.

2. **Callee Requirements (`POSTCONDITIONS:` / `PRECONDITIONS:` / `INVARIANTS:`)**:
   - Contractual obligations that the callee is required to verify, execute, or construct.
   - Only callee requirements are decomposed into atomic knowledge requirements.

### 2.3 Decomposing Requirements into Knowledge Requirements
Low-level specifications (`low/*.pyi`) state behavioral contracts with conditions and consequents:
$$\text{WHEN } \langle\text{condition}\rangle, \text{ MUST } \langle\text{consequent}\rangle.$$
Control flow (`if/else`, `while`, `try/except`, `for`) is merely the runtime plumbing that ties conditions to consequents dynamically. **Grounding does not care about control flow plumbing; grounding cares about knowledge requirements.**

The first step in grounding is to decompose low-level specification requirements into atomic **Knowledge Requirements**:
- Can we access the necessary information with code?
- Can we perform the required call or evaluate the specified callback?
- Can we express the condition in straight-line code?
- Can we construct and invoke the consequent in straight-line code?

For example, consider the requirement:
> `WHEN a call omits a required parameter lacking a missing note, MUST fail with feedback citing the missing parameter.`

This requirement boils down to five distinct knowledge requirements:
1. *Can we write code to tell if a parameter is required?* `param.is_required`
2. *Can we write code to tell if a call omits a required parameter?* `sample_param_name not in wire_parameter_bindings`
3. *Can we write code to tell a parameter lacks a missing note?* `param.missing_message is None`
4. *Can we write code to create a failure with feedback?* `ToolResponse(is_failed=True, is_terminated=False, content=...)`
5. *Can we write code to cite the missing parameter?* `f"Missing required parameter '{sample_param_name}'"`

Adding on the companion requirement:
> `WHEN a call omits a required parameter specifying a missing note evaluated against present parameters, MUST fail with feedback citing the missing parameter and missing note.`

This introduces additional atomic knowledge requirements:
6. *Can we write code to tell if a required parameter specifies a missing note?* `param.missing_message is not None`
7. *Can we write code to tell what present parameters are?* `present_params: Set[ParameterName] = set(wire_parameter_bindings.keys())`
8. *Can we write code to evaluate the missing note against present parameters?* `note_fn: Callable[[Set[ParameterName]], str] = param.missing_message or (lambda s: ""); note = note_fn(present_params)`
9. *Can we write code to cite the missing note?* `f"Missing required parameter '{sample_param_name}': {note}"`

By writing straight-line Python expressions that evaluate each condition and construct each consequent, the grounding module proves feasibility for **100% of the contract's knowledge requirements** without writing a single line of runtime control flow.

Importantly, **generic mock returns that bypass condition and consequent evaluation are strictly prohibited**. Writing:
```python
# PROHIBITED MECHANISTIC SHORTCUT:
def execute_tool(self, name: ToolName, wire_parameter_bindings: Mapping[ParameterName, WireType]) -> ToolResponse:
    return ToolResponse(is_failed=False, is_terminated=False, content="")
```
passes Pyright type checking and AST syntax linters, but proves **zero** knowledge feasibility. It fails to prove that parameter requirements can be inspected, fails to prove that diagnostics can be formatted, fails to prove that conversions are well-typed, and fails to prove that collaborator operations can be invoked. Every requirement claimed under `COVERED:` must have its condition evaluation expressions and consequent construction expressions materialized in typed code.

#### 2.3.1 Straight-Line Feasibility of Failure Paths Without Failure Propagation
A common confusion arises when a specification demands failure outcomes:
> `WHEN verification fails, MUST fail.`

Because grounding strictly prohibits runtime control flow (`if/else`, `raise`), grounding code cannot dynamically branch or propagate failures at runtime. Nor should it: **grounding specifications are never executed dynamically, so failure cannot and should not be propagated during grounding**.

Instead, grounding proves **constructive feasibility** by demonstrating that:
1. Condition checks can be evaluated (e.g. `passed, diag = sample_check.verify()`).
2. A failed response record can be constructed (e.g. `_fail_response = ToolResponse(is_failed=True, content=f"Verification failed: {diag}")`).

By assigning the failed response to a typed local variable (`_fail_response`), the grounding proof statically proves to Pyright that all condition fields are accessible and all failure diagnostic payloads can be constructed. The method terminates with `raise NotImplementedError`, completely eliminating the need for return statements or mock response objects. Writing a generic mock return (e.g. returning `ToolResponse(is_failed=False)` without evaluating the checks and without constructing the failure response) is a prohibited mechanistic shortcut.

#### 2.3.2 Data Provenance, Constructor Pacification, and Prohibition of Phantom Literals

A particularly subtle failure mode in static type-checked grounding is **Constructor Pacification** (or **Origin Amnesia**).

When a low-level specification postcondition dictates:
> `WHEN guide step mode is active, MUST provide the session task guide.`

Python's static type system requires passing concrete values to instantiate `NodeGuide(summary=..., sections=..., verification_failure=...)`. If the upstream specification states an output type without defining the origin or derivation rules for its constituent fields, a grounding proof might simply pass hardcoded placeholder literals:
```python
# PROHIBITED CONSTRUCTOR PACIFICATION VIA PHANTOM LITERALS:
summary = agent_node_config.GuideSummary("Task Guide Overview")
sections = [StepSection(index=1, title="Step", content="Instructions")]
_res = agent_node_config.NodeGuide(summary=summary, sections=sections)
```
This satisfies Pyright's static type checker, but proves **zero semantic feasibility**. The data was conjured out of thin air rather than proven to be derivable from input arguments, collaborator queries, or build manifests.

Cleanroom enforces the strict **Rule of Data Provenance**:
1. **Demonstrable Provenance**: Every argument passed into an output record constructor, dataclass instantiation, or collaborator method call must have demonstrable provenance:
   - **Direct Input**: Parameters passed directly into the method.
   - **Collaborator State**: Data retrieved via `self.get_singleton(...)`.
   - **Synthesized Transformation**: Content parsed, mapped, or converted from input parameters or collaborator state.
   - **Contractual Defaults**: Literal constants explicitly dictated by the low-level contract itself.
2. **Prohibition of Phantom Literals**: Fabricating arbitrary string literals, numbers, or mock structures to satisfy constructor signatures (e.g. inventing placeholder guide text, fake task prompts, or arbitrary URLs) is strictly classified as a mock bypass and is prohibited.
3. **Mandatory Upstream Blame / Escalation**: If an output record requires fields whose data sources or derivation mechanics cannot be traced to declared parameters, collaborators, or contract-specified defaults, the grounding engineer must not invent placeholder literals. Grounding must fail fast and escalate upstream (submitting a blame) demanding that the upstream contract specify the data provenance.

### 2.4 Single-Element Collection Abstraction
Loops (`for x in xs:`) introduce control flow and stateful iteration. In grounding proofs, collections are reasoned about via **single-element abstraction**:
- Any collection (such as `Mapping[K, V]`, `Sequence[T]`, or `Set[T]`) is represented by exactly one arbitrary representative element.
- Helper functions from `grounding_support` extract representative keys, values, or items without looping:
  ```python
  k: K = key(mapping)
  v: V = value(mapping)
  elem: T = only_elem(sequence)
  ```
- Constructing dictionary arguments uses a representative key-value binding:
  ```python
  actual_bindings: Mapping[ToolParameter[Any, Any], SomeParameterActualType] = {
      param: converted_value
  }
  ```
Mathematically, proving that an operation is well-typed for an arbitrary representative element $x \in X$ proves type soundness for 1, 10, or 10,000 elements. Single-element abstraction completely eliminates the need for loops, list comprehensions, or generators in verification.

### 2.5 Requirement Coverage, Subtype Deferral, and Documentation
The primary job of the grounding process is to **cover as many knowledge requirements as possible** in the interface grounding module (`grounding/<name>.py`). Cleanroom enforces strict completeness rules:

1. **100% Symbol and Member Parity**: Every class, protocol, data type, parameter type, variant, and helper declared in `low/<name>.pyi` must be represented in `grounding/<name>.py` (or `grounding/<name>_impl.py`). Every operation, property, and initialization sequence declared in `low/*.pyi` must be implemented with concrete straight-line code. Skipping classes or leaving methods unimplemented is a fatal grounding failure.
2. **100% Contract Clause Accountability**: Every single postcondition clause (`WHEN ... MUST ...`) and invariant from `low/<name>.pyi` must be accounted for verbatim in member docstrings under `COVERED:` or `DEFERRED:`. Silently dropping, summarizing away, or ignoring contract clauses is strictly prohibited.
3. **Value Types (`@data_type`, `@variant`)**: Must be fully covered immediately in `grounding/<name>.py`. They have no subtypes or deferred state obligations.
4. **Abstract Methods/Properties and State in Non-Impl Protocols**: When an interface component is not an implementation (`_impl`), it represents an abstract service or protocol (`Protocol`). An abstract method or property declared on a protocol provides a capability to *external callers and collaborators*, but **cannot provide values or implementations to itself**. For example, `DagConfig.node_visit_limit` provides a limit that `DagSubgraph` uses to cover its traversal bounds; however, `DagConfig` itself in the abstract interface has no internal backing data source (such as build target manifests or environment defaults) to supply that visit limit. Any abstract method or property whose value or behavior originates from an implementation source (concrete storage, configuration files, environment variables, or algorithm implementations) **cannot cover itself in the interface protocol**. Such requirements must be left uncovered and cataloged under `DEFERRED:`. The implementor (`_impl.py`) provides the backing source and covers them under `COVERED:`. Writing `COVERED:` on an abstract method or property whose body is an empty ellipsis `...` is strictly prohibited.
5. **Implementation Discharge**: In implementation grounding (`grounding/<name>_impl.py`), all inherited `DEFERRED:` obligations from the interface module must be fully discharged and resolved, confirmed via class-level `DISCHARGED:` summaries. Implementation modules must have **zero open `DEFERRED:` entries**.
6. **Decoupling from Runtime Execution Concerns**: Dynamic runtime execution and algorithmic control flow (such as loops, conditionals, branching ladders, exception handling, and socket/disk operations) belong exclusively to the runtime implementation tier (`lib/`). Grounding is strictly a static type and constructive feasibility tier (zero dynamic execution, 100% Pyright type checking). All contractual postconditions in `_impl.py` are claimed and proven under `COVERED:` via straight-line representative dataflows, leaving dynamic control flow as an implementation detail of `lib/`. Dynamic runtime control flow is never checked, cataloged, or reported during grounding reviews or alignment checks.

Because of this structure, member and class docstrings in a grounding module explicitly catalog the status of contractual postconditions and invariants from `low/*.pyi`:

- **`COVERED:`** Lists all contractual postconditions whose decomposed condition and consequent knowledge requirements are proven in straight-line code in this module.
- **`DEFERRED:`** Lists open state obligations that cannot be covered in the interface because they require concrete private storage or subtype specialization. Permissible strictly on singletons and polytypes in non-`_impl` components; must be discharged in `*_impl.py`.
- **`DISCHARGED:`** Class-level summaries in `_impl.py` modules confirming that all inherited interface obligations have been resolved.

```python
class ToolManager(InTier[AgentSessionTier], Protocol):
    @property
    def installed_tools(self) -> Mapping[ToolName, Tool]:
        """
        DEFERRED:
        - Exposes installed tools as a mapping (requires concrete storage in _impl).
        """
        raise NotImplementedError

    def install_tool(self, tool: Tool) -> None:
        """
        DEFERRED:
        - MUST install the tool for the agent session (requires state mutation in _impl).
        """
        raise NotImplementedError

    def execute_tool(
        self, name: ToolName, wire_parameter_bindings: Mapping[ParameterName, WireType]
    ) -> ToolResponse:
        """
        COVERED:
        - WHEN calling a tool whose name does not match any installed tool, MUST fail with feedback citing the unknown tool and listing installed tools:
          - Condition knowledge: name not in tools.
          - Consequent knowledge: ToolResponse(is_failed=True, content=f"Unknown tool '{name}'. Available tools: {', '.join(tools.keys())}").
        - WHEN a call omits a required parameter lacking a missing note, MUST fail with feedback citing the missing parameter:
          - Condition knowledge: param.is_required, sample_param_name not in wire_parameter_bindings, param.missing_message is None.
          - Consequent knowledge: ToolResponse(is_failed=True, content=f"Missing required parameter '{sample_param_name}'").
        - WHEN a call omits a required parameter specifying a missing note evaluated against present parameters, MUST fail with feedback citing the missing parameter and missing note:
          - Condition knowledge: param.is_required, sample_param_name not in wire_parameter_bindings, param.missing_message is not None, present_params = set(wire_parameter_bindings.keys()), note_fn(present_params).
          - Consequent knowledge: ToolResponse(is_failed=True, content=f"Missing required parameter '{sample_param_name}': {evaluated_note}").
        - WHEN a call omits a non-required parameter specifying a default value, MUST bind the default value for the call:
          - Condition knowledge: not param.is_required, param.default_value is not None.
          - Consequent knowledge: action_bindings = {param: SomeParameterActualType(param.default_value)}.
        - WHEN wire conversion fails for a parameter, MUST fail with feedback citing the parameter name and the conversion failure feedback:
          - Condition knowledge: ParameterConversionError(message=...).message.
          - Consequent knowledge: ToolResponse(is_failed=True, content=f"Parameter '{sample_param_name}' conversion failed: {err.message}").
        - WHEN all parameter symbols resolve, required parameters are present, defaults are applied, and wire conversions succeed, MUST call the tool with action parameter bindings and return its tool response:
          - Condition knowledge: pt.convert(sample_wire_val), action_bindings = {param: actual_val}.
          - Consequent knowledge: tool.execute_tool(action_bindings).
        """
        # Proof knowledge feasibility: access installed tools and verify parameter bindings
        tools = self.installed_tools
        _tool_present = name in tools
        _unknown_resp = ToolResponse(is_failed=True, is_terminated=False, content=f"Unknown tool '{name}'")
        _fail_resp = ToolResponse(is_failed=True, is_terminated=False, content="Failure response")
        raise NotImplementedError
```

### 2.6 Hole & Obligation Propagation to Implementation
Grounding specifications operate under an open-world to closed-world refinement model:
- **Interface Grounding (`grounding/<name>.py`)**: Covers all knowledge requirements whose dataflow dependencies are known at the interface level. Any requirements that depend on concrete internal state or mutation are left uncovered and cataloged under `DEFERRED:`.
- **Implementation Grounding (`grounding/<name>_impl.py`)**: Inherits from the interface grounding module, introduces concrete internal state storage, and fully discharges all `DEFERRED:` obligations. No open obligation may remain upon reaching `_impl.py`.
- **Assembly Grounding (`grounding/<name>_asm.py`)**: Wires all constituent implementation singletons together, proving that every service's collaborator requirements are mutually satisfied across the complete system.

### 2.7 External Components (`_ext`)
External/third-party boundaries (such as the OpenAI API, Bazel CLI, or host filesystem) are defined in dedicated specifications (`low/<name>_ext.pyi`).
In the grounding layer:
- External components provide simplified, typed grounding definitions (`grounding/<name>_ext.py`).
- These modules provide clean, typed facades modeling external inputs, outputs, and side-effects.
- They are trusted as axioms without requiring internal verification proofs.

### 2.8 Static Enforcement Only: Pyright & AST Linters
Grounding modules are **never executed dynamically at runtime**:
- They are never imported by production servers or runtime runners.
- They require no test runners, no mock registries, and no dummy input fixtures.
- They are verified purely by:
  1. **Pyright Type Checking**: Verifying 100% type soundness, generics, and lifecycle tier access rules in milliseconds.
  2. **AST Static Linter (`grounding_lint.py`)**: Statically rejecting any forbidden syntax (loops, conditionals, exceptions, raises, early returns).

### 2.9 The Anti-Mechanistic Imperative: Syntactic vs. Semantic Verification
Passing Pyright and AST linters is a baseline syntactic check—representing merely **1%** of verification sanity. Syntactic checkers confirm that types unify and that forbidden AST nodes (`if`, `for`, `try`, `raise`) are absent. However, an automated agent can trivially satisfy syntactic checks mechanically while completely sabotaging grounding semantics by:
1. Omitting classes, variants, parameter types, or helper protocols declared in `low/<name>.pyi`.
2. Omitting operations or leaving methods unimplemented.
3. Silently dropping, summarizing away, or ignoring contractual postconditions (`WHEN ... MUST ...`).
4. Writing trivial mock returns (e.g. `return ToolResponse(is_failed=False, is_terminated=False, content="")` or `return False` or `...`) that bypass condition evaluation and consequent construction.
5. Leaving open `DEFERRED:` items in implementation grounding (`grounding/<name>_impl.py`).

Such mechanistic shortcuts defeat the entire purpose of Cleanroom grounding: downstream library implementations (`lib/*.py`) and unit tests (`tests/*_test.py`) inherit hollow, ungrounded stubs, leading to downstream alignment failures, missing features, and invalid tests.

Semantic verification requires that **100% of symbols and 100% of contractual postconditions** are substantiated in straight-line code.

---

## 3. Static Capability Checking: `InTier[T]`

Cleanroom enforces hierarchical lifecycle tiers (e.g. `SystemTier`, `AgentSessionTier`). A service in a parent tier (such as `SystemTier`) must never depend on or access a singleton in a subordinate tier (such as `AgentSessionTier`).

In Python grounding proofs, this capability is enforced entirely at compile-time via generic `@overload` signatures on `InTier[T].get_singleton`:

```python
class InTier[TierT]:
    @overload
    def get_singleton[S: InTier[SystemTier]](
        self: InTier[SystemTier], key: type[S]
    ) -> S: ...

    @overload
    def get_singleton[S: InTier[SystemTier] | InTier[AgentSessionTier]](
        self: InTier[AgentSessionTier], key: type[S]
    ) -> S: ...

    def get_singleton[S](self, key: type[S]) -> S:
        ...
```

If a system-tier service attempts to call `self.get_singleton(SessionService)`, Pyright statically flags an error:
```
error: Argument of type "type[SessionService]" cannot be assigned to parameter "key" of type "type[S]" in function "get_singleton"
  Type "SessionService" is not assignable to "InTier[SystemTier]"
```
No custom Datalog solver or runtime capability monitor is needed; standard Python static typing enforces Cleanroom tier isolation rules.

---

## 4. Comparison: Legacy Groundtalk vs. Python Grounding

| Dimension | Legacy Groundtalk (`.gt`) | Python Grounding (`.py`) |
|---|---|---|
| **Language** | Custom Datalog DSL | Restricted Typed Python 3.12 |
| **Verifier** | Custom Python solver & AST parser | Pyright + Lightweight AST Linter |
| **Verification Speed** | ~5-30s per component | <10ms per component |
| **Control Flow** | Relational Horn clauses | Straight-line assignments & calls |
| **Collections** | Unary facts & custom axioms | Single-element helper functions |
| **Requirement Tracking** | Stripped negative error paths | Decomposed into Knowledge Requirements |
| **Tooling Support** | Custom VSCode/syntax highlighter | Full Python LSP, Pyright, autocomplete |
| **Lifecycle Tiers** | Custom propositional Horn axioms | Overloaded `InTier[T]` signatures |
| **Mocking Ceremony** | Custom Datalog axioms | Zero (pure static type propagation) |

---

## 5. Grounding QA Arbiter: Verifying the Grounding Layer

To prevent agents from performing lazy or mechanistic alignments, Cleanroom establishes a dedicated verification phase between `grounding` and downstream `lib`/`test` generation: the **Grounding QA Arbiter** (`grounding_qa`).

```
       Planning Canvas (`planning/*.md`)
                     │
                     ▼
       Low-Level Stubs (`low/*.pyi`)
                     │
                     ▼
  Grounding Feasibility Proofs (`grounding/*.py`)  ◄── Pyright Verification (<10ms)
                     │
                     ▼
       Grounding QA Arbiter (`grounding_qa`)       ◄── Semantic Contract Audit & Blame
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
Full Implementation (`lib/*.py`)  Unit Tests (`tests/*_test.py`)
        │                         │
        └────────────┬────────────┘
                     ▼
          QA Arbiter (`qa`)
                     │
                     ▼
       Coverage Arbiter (`coverage`)
```

### 5.1 Responsibilities of the Grounding QA Arbiter
The Grounding QA Arbiter operates as an independent auditor that cross-references `grounding/<name>.py` and `grounding/<name>_impl.py` against `low/<name>.pyi` and `low/<name>_impl.pyi`. It evaluates five strict audit dimensions:

1. **Symbol & Declaration Completeness**:
   - Every class, protocol, data type, parameter type, variant, and helper declared in `low/<name>.pyi` is declared in `grounding/<name>.py`.
   - Every class declared in `low/<name>_impl.pyi` is implemented in `grounding/<name>_impl.py`.
   - Every method, property, and initialization sequence declared in `low/*.pyi` is implemented with concrete straight-line code.

2. **Contract Clause Completeness**:
   - Every single postcondition (`WHEN ... MUST ...`) and invariant clause from `low/<name>.pyi` is quoted verbatim in member docstrings under `COVERED:` or `DEFERRED:`.
   - No postconditions are omitted, merged, or summarized away.
   - Grounding alignment checks evaluate only symbol parity, member parity, type soundness, verbatim postcondition quoting, and straight-line dataflow proofs. Assessments of grounding health must never inspect, check, or report on dynamic runtime control flow or algorithmic execution.

3. **Knowledge Proof Depth (Anti-Mechanistic Audit)**:
   - For every requirement claimed under `COVERED:`, the method body contains typed straight-line expressions evaluating its condition knowledge (checking required flags, testing key membership, evaluating bounds, inspecting error payloads).
   - The method body contains typed straight-line expressions constructing its consequent knowledge (formatting failure responses citing parameter/tool names, invoking callbacks, applying defaults, converting wire formats, invoking collaborator operations).
   - Trivial mock returns or empty stubs that bypass condition and consequent evaluation are flagged as mechanistic defects.

4. **Obligation Discharge**:
   - All `DEFERRED:` obligations from interface grounding are verified to be fully discharged and resolved in `grounding/<name>_impl.py`. Zero open `DEFERRED:` items may remain in implementation grounding.

5. **Assembly and External Integrity**:
   - External stubs (`grounding/<name>_ext.py`) provide typed facades modeling external boundaries.
   - Assembly modules (`grounding/<name>_asm.py`) declare initialization sequences verifying mutual collaborator resolution across all constituent singletons.

### 5.2 Defect Blame Attribution
If the Grounding QA Arbiter detects any missing symbols, omitted postconditions, mock return bypasses, or undischarged deferrals, it attributes blame back to the Grounding Engineer:
- **Non-Prescriptive Blame Feedback**: Feedback is delivered as a single unbroken paragraph citing the exact file, class, method, and the ungrounded requirement or missing symbol from `low/<name>.pyi`.
- **Target Lock and Isolation**: Blame attribution halts progression to `lib` and `test` until the Grounding Engineer resolves the defect and provides a complete semantic proof.
- **Empty Log on Success**: When 100% of symbols, contracts, and knowledge requirements are verified, the Grounding QA log (`logs/<name>_grounding_qa.log`) is emptied to 0 bytes and submitted, allowing Cleanroom to safely advance to library and test implementation.

