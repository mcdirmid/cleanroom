# Formal Verification & Pragmatic Quality Engineering in Autofab (`formal_todo.md`)

> **Status:** Design Discussion & Master Implementation Roadmap  
> **Author:** Cleanroom Architecture Pair  
> **Target Models:** Fast reasoning & utility models (e.g., Gemini Flash / DeepSeek Flash)  
> **Primary Objective:** Maximize software quality and eliminate edge-case defect classes in general-purpose code without requiring full correctness proofs or heavyweight interactive theorem provers.

---

## 1. Problem Statement & Philosophy

Autofab already possesses an extensive verification pipeline:
* **HLS (`high/`)**: Behavioral requirements and contracts in Markdown.
* **Planning (`planning/`) & Scenarios (`scenarios/`)**: Architectural design and concrete execution traces.
* **Low (`low/`)**: Typed interface signatures with rich, natural language docstrings.
* **Lib (`lib/`)**: General-purpose implementation code.
* **Tests (`tests/`) & QA (`qa/`, `pretense/`)**: Specification-derived unit tests, property testing, and adversarial audits.

### The Objective: Quality Improvement, Not Proof of System Correctness
In traditional mission-critical engineering, formal verification (FV) aims to produce a mathematical certificate that an entire system is mathematically correct with respect to a formal specification. However:
1. **General-purpose code** (handling filesystems, CLI parsing, JSON serialization, network requests, dynamic collections) cannot be completely formalized without turning specifications into bloated, unmaintainable formal logic programs.
2. **Replacing natural language in `low` is unacceptable:** Natural language carries high semantic density (intent, heuristics, UX expectations, edge-case rationale). Replacing it with mathematical formulas destroys expressiveness and cripples the LLM's high-level reasoning.
3. **We do not need to prove the system is correct:** We want to catch the subtle edge-case bugs that human authors and LLM unit tests routinely miss (boundary conditions, off-by-one errors, unexpected `NoneType` dereferences, collection emptiness bugs, state transition inconsistencies, conservation law violations).

### The LLM-First Feasibility Lens
Unlike traditional formal methods where a human mathematician writes proofs:
* **The LLM (specifically fast, token-efficient models like Gemini Flash) does all the authoring.**
* Extra boilerplate or scaffolding code is acceptable **if and only if** Gemini Flash can author it effortlessly from the interface.
* **Token Efficiency:** The specifications and feedback must not inflate context windows with thousands of lines of solver logs or theorem tactics.
* **Actionable Feedback Loop:** The solver/verifier must produce concrete, deterministic counterexamples (e.g., `Failed when x=[], size=0`) rather than cryptic SMT timeouts, enabling the LLM to fix the code in a single prompt step without thrashing or getting stuck in development loops.

---

## 2. The Verification Spectrum: What Fits General-Purpose Code

| Method | Expressiveness | Proof Rigor | General-Purpose Viability | LLM Authorability (Flash) | Feedback Quality | Verdict for Autofab |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Interactive Theorem Provers (Lean 4, Coq)** | Low (Formal Logic only) | 100% Mathematical Proof | Terrible (Breaks on real I/O, external libs) | Poor (Requires complex tactic proofs) | Poor (Unsolved proof obligations) | **REJECT** (Academic lock-in) |
| **Formal Modeling (TLA+, Alloy)** | High for state, Low for code | Model-level correctness | High for state machines, Low for general code | Moderate (Good at TLA+ specs) | Good (State trace counterexamples) | **RESERVE** for complex state machines only |
| **Property-Based Testing (Hypothesis)** | High (Python code) | Empirical Falsification (Not a proof) | Excellent | High | Good (Shrunk test cases) | **KEEP** (Already in use) |
| **SMT-Backed Symbolic Execution (CrossHair, Z3)** | High (Python expressions) | Sound Bounded / Deductive Verification | High for algorithmic components & invariants | **Excellent** (Short docstring/inline assertions) | **Outstanding** (Exact concrete variable assignments) | **PRIMARY CANDIDATE** |
| **Sound Absence of Runtime Errors (AoRTE Static Analysis)** | High (Native Types) | Sound proof of crash-freedom | Excellent | **Trivial** (Leverages typing + assertions) | **Outstanding** (Line + Type mismatch) | **PRIMARY CANDIDATE** |

---

## 3. Architecture: The Pragmatic Dual-Channel Contract

To retain full natural language expressiveness in `low/*.pyi` while enabling automated verification on general-purpose `lib/*.py` code, specifications operate on two complementary channels:

```
┌────────────────────────────────────────────────────────┐
│                      low/*.pyi                         │
│                                                        │
│  def windowed(seq: Sequence[T], n: int) -> list[...]:  │
│      """Natural Language Specification:                │
│      Yields sliding windows of size n from seq.        │
│      If n > len(seq), yields an empty list.            │
│      If n <= 0, raises ValueError.                     │
│                                                        │
│      # Machine-Verifiable Invariants:                  │
│      post: len(result) == max(0, len(seq) - n + 1)     │
│      post: all(len(w) == n for w in result)            │
│      """                                               │
└───────────────────────────────────────────┬────────────┘
                                            │
               ┌────────────────────────────┴───────────────────────────┐
               ▼                                                        ▼
┌──────────────────────────────┐                         ┌──────────────────────────────┐
│        lib/*.py (Code)       │                         │       tests/*_test.py        │
│                              │                         │                              │
│  General-purpose Python      │                         │  Standard specification-     │
│  implementation.             │                         │  derived unit & PBT tests.   │
└──────────────┬───────────────┘                         └──────────────┬───────────────┘
               │                                                        │
               ▼                                                        ▼
┌──────────────────────────────┐                         ┌──────────────────────────────┐
│      roles.formal_qa         │                         │          roles.qa            │
│                              │                         │                              │
│  Symbolic SMT execution      │                         │  Test suite execution        │
│  (CrossHair / Z3 / Deal)     │                         │  (pytest, coverage)          │
│  Checks invariants over      │                         │  Validates integration,      │
│  entire symbolic domain.     │                         │  I/O, and external mocks.    │
└──────────────┬───────────────┘                         └──────────────────────────────┘
               │
               ▼ (On Failure)
     Concrete Counterexample:
     `windowed(seq=[1, 2], n=0) -> raised UnboundLocalError instead of ValueError`
               │
               ▼
     Immediate 1-Step Fix by LLM
```

### Channel 1: The Natural Language Narrative (Intent & Context)
* Author: `low` engineer (Gemini Flash).
* Form: Detailed docstrings in `low/*.pyi`.
* Purpose: Conveys high-level semantic meaning, user expectations, error handling policies, and design intent to human readers and downstream `lib` and `test` engineers.

### Channel 2: Lightweight Invariant Anchors (Safety & Edge-Case Traps)
* Author: `low` engineer or auto-scaffolded by contract linting.
* Form: 1 to 3 lines of executable Python boolean expressions (PEP 316 / CrossHair syntax) or type-level assertions.
* Characteristics:
  * **Short & Token-Efficient:** Takes less than 30 tokens per function.
  * **Easy for Flash:** Flash models can effortlessly write `post: len(result) <= len(items)` or `pre: factor > 0`.
  * **Zero Logic Syntax:** Written in standard Python syntax, not first-order predicate calculus.

---

## 4. Designing the Non-Thrashing Feedback Loop

The critical risk in pairing LLMs with formal solvers is **solver thrashing**:
* The solver times out or cannot analyze third-party C-extensions / file handles.
* The LLM doesn't understand the solver's internal error and hallucinates useless edits, getting trapped in an infinite retry loop.

To prevent this, the Autofab harness must enforce four strict operational guardrails:

### Guardrail 1: Ground-Truth Concrete Counterexamples Only
The verifier (`bin/check_files` in `formal_qa` role) must never return raw SMT formulas, Z3 AST dumps, or proof obligation trees. It must only output concrete Python call traces:
```
VERIFICATION FAILED: lib/formatting.py:format_table
Counterexample found:
  Called: format_table(rows=[[]], headers=["Name"])
  Violated Postcondition: 'len(result.lines) >= 2' (line 14 in low/formatting.pyi)
  Returned: result.lines = ['Name']
```
This is immediately comprehensible to Gemini Flash: it sees the exact input that triggered the bug and can patch the off-by-one check in `lib` in one step.

### Guardrail 2: Deterministic Solver Timeouts & Degraded Fallbacks
* If symbolic analysis of a function takes more than $T$ seconds (e.g. 5 seconds):
  * Do **not** fail the build or blame the LLM.
  * Emit an informational note: `[SKIP: SMT-TIMEOUT] Function exceeds symbolic path limit; deferred to dynamic PBT`.
  * This guarantees the agent never gets stuck on undecidable loop unrolling or complex recursion.

### Guardrail 3: Boundary Pragmas for Unverifiable External I/O
General-purpose code interacts with external systems (files, sockets, OS processes) that cannot be symbolically executed.
* Provide an explicit, sanctioned pragma convention:
  ```python
  # pragma: no-verify (reason: external_io)
  ```
  or caller assumption declarations:
  ```python
  # assume: file_descriptor.is_open()
  ```
* This gives the LLM a clean escape hatch for side-effecting code, preventing thrashing.

### Guardrail 4: Clear Ownership & Blame Routing
* If an invariant in `low` is mathematically inconsistent with the natural language spec (e.g., `pre: x > 0` but spec says `handle negative x by returning None`):
  * The `formal_qa` role blames `low` or `spec_qa`.
* If the code in `lib` violates an invariant on an admitted input:
  * The `formal_qa` role blames `lib`.

---

## 5. The Omission Defect Blind Spot: When Both Lib and Tests Miss a Requirement

A foundational blind spot of code coverage is **omission defects**:
> *If `tests` misses a requirement AND `lib` misses the exact same requirement, code coverage (line/branch) is 100%, fuzzing passes without a complaint, and the system is completely blind to the fact that the requirement does not exist.*

Code coverage only measures: *"did we execute all lines of `lib` that exist?"*  
It cannot measure: *"did we implement all requirements that SHOULD exist?"*

### Why Correlated Omission Occurs with LLMs
Because both `lib` and `tests` are authored downstream by LLMs reading the same upstream specifications (`high`, `low`):
1. **Implicit Edge Cases:** An edge case (e.g. empty sequence, negative retry count, unicode surrogate pair) is not explicitly spelled out in prose. Both the `lib` author and the `test` author assume "normal" inputs.
2. **Cognitive Skips:** A complex requirement is stated in `high/*.md`, but omitted during `low/*.pyi` translation. Both `lib` and `tests` look at `low` and omit the feature.
3. **Over-Mocking / Blind Mocks:** Tests mock out the very edge-case interaction that `lib` fails to implement.

---

## 6. How Z3 Solves Omission: SMT-Powered Input Space Partitioning

Z3 (and SMT solvers in general) does not need to analyze arbitrary Python runtime code to solve omission defects. Instead, **Z3 analyzes the mathematical partitioning of the specification itself**.

### A. Input Domain Completeness (Gap Hunting)
For any function, the specification defines discrete behavior over disjoint input partitions.
For example, consider a date/time windowing function:
* Partition 1: `start < end` and `window > 0` $\implies$ valid window sequence
* Partition 2: `start >= end` $\implies$ raises `InvalidRangeError`

An LLM extracts these conditions into a 15-line Z3 check. Z3 is asked:
$$\exists \text{start, end, window such that } \neg (\text{Partition}_1 \lor \text{Partition}_2)$$

Z3 immediately returns `SAT` with:
$$\text{start} = 0, \text{end} = 10, \text{window} \le 0$$
**Z3 has mechanically discovered the omitted requirement**: neither `lib` nor `tests` handled `window <= 0` because the specification had a partition gap. The LLM can now patch `low` to add the missing partition before any implementation or test code is generated.

### B. Inconsistency & Contradiction Hunting
When multiple complex requirements interact (e.g. CLI flag combinations, permission matrices, pricing tiers), specifications often contain subtle contradictions.
Z3 checks whether two conflicting requirement branches can be simultaneously satisfied:
$$\exists \text{inputs such that } (\text{Condition}_A \land \text{Condition}_B \land \text{Expected}_A \neq \text{Expected}_B)$$
If `SAT`, Z3 produces the exact input combination where the specification contradicts itself, preventing LLM authoring thrash.

---

## 7. The Four Viable Non-Holistic Approaches

Instead of attempting holistic end-to-end verification, Autofab targets four non-holistic, modular verification approaches:

```
┌────────────────────────────────────────────────────────────────────────┐
│                      NON-HOLISTIC FORMAL SUITE                         │
├─────────────────────────┬──────────────────────┬───────────────────────┤
│ Approach                │ Target Problem       │ Mechanism             │
├─────────────────────────┼──────────────────────┼───────────────────────┤
│ 1. SMT Domain           │ Specification gaps & │ Z3 finds uncovered    │
│    Partitioning         │ omission defects     │ input partitions      │
├─────────────────────────┼──────────────────────┼───────────────────────┤
│ 2. Specification        │ Unimplemented or     │ Formal bipartite      │
│    Coverage (Spec-Cov)  │ untested specs       │ requirement graph     │
├─────────────────────────┼──────────────────────┼───────────────────────┤
│ 3. SMT Contract Checks  │ Algorithmic leaf     │ CrossHair / Z3 checks │
│    (Leaf Invariants)    │ logic bugs           │ pre/post conditions   │
├─────────────────────────┼──────────────────────┼───────────────────────┤
│ 4. Metamorphic /        │ System consistency & │ Symbolic verification │
│    Algebraic Invariants │ transformation bugs  │ of algebraic laws     │
└─────────────────────────┴──────────────────────┴───────────────────────┘
```

### Approach 1: SMT Domain Partitioning (The Omission Hunter)
* **Where it runs:** Upstream in `roles.spec_qa`.
* **What it does:** Extracts boolean guard conditions from `low/*.pyi` and asks Z3 to prove that $\bigvee_{i} \text{guard}_i \equiv \text{True}$ over the admitted type domain.
* **Output:** Counterexamples representing missing specification branches (unhandled edge cases).

### Approach 2: Specification Coverage (`Spec-Cov`)
* **Where it runs:** Downstream in `roles.coverage`.
* **What it does:** Every requirement clause, acceptance criterion, and `Raises:` error in `high` and `low` is tagged with a deterministic requirement anchor (e.g. `[REQ-01]`, `[REQ-02]`).
* **The Gate:** A static AST verifier builds a bipartite graph linking each `[REQ-XX]` to:
  1. An implementing block in `lib/*.py`.
  2. An explicit assertion in `tests/*_test.py` tagged `@covers("REQ-XX")`.
* **Result:** If a requirement in `low` is omitted in `lib` and `tests`, the build fails with: `REQ-03 is specified in low/parser.pyi:25 but unasserted in tests/parser_test.py`.

### Approach 3: SMT Contract Checks on "Islands of Logic"
* **Where it runs:** In `roles.formal_qa` on leaf functions marked `# verify: smt`.
* **What it does:** Uses CrossHair / Z3 to check lightweight 1-line pre/post-conditions on pure algorithmic modules (version comparison, text diffing, graph acyclicity, range intersection).
* **Avoids:** Does not attempt SMT over network sockets, subprocesses, or complex dynamic external libraries.

### Approach 4: Metamorphic & Algebraic Property Verification
* **Where it runs:** In `tests/` and `pretense/`.
* **What it does:** Verifies algebraic laws that general-purpose code must satisfy:
  * **Idempotence:** $f(f(x)) = f(x)$ (formatting, sanitization).
  * **Round-trip Invertibility:** $decode(encode(x)) = x$ (serialization, codecs).
  * **Monotonicity / Permutation-Invariance:** Ordering, filtering, sorting properties.

---

## 8. Combining with Pretense: Elevating State Machines from Fuzzing to Formal Verification

Autofab already possesses an executable state machine framework in **Pretense** ([`design-docs/pretense.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/pretense.md)). 

Currently, Pretense uses state machines for **informal testing**:
* **Interface State Machines (`parts/*/pretense/*_pretense.py`)**: Define discrete state models (`self.state`), 1:1 transitions (`@transition`), preconditions (`requires(...)`), and single-argument assertions (`assert condition`).
* **Hypothesis Stateful Fuzzer**: Pretense uses `hypothesis.stateful.RuleBasedStateMachine` to generate **50 random transition walks** across the state graph.

This is a massive missed opportunity: **Pretense state machines are already formal transition systems written in Python!**  
Instead of inventing a foreign formal modeling language (like TLA+ or Alloy), we can upgrade Pretense itself from statistical fuzzing to **bounded formal verification**.

### The Epistemic Flaw Identified in Pretense
`design-docs/pretense.md` explicitly noted the core vulnerability of informal stateful fuzzing:
> *"When both the library and state machine authors share an omission blind spot, the abstract model tautology ($SUT \equiv Model_{SM}$) conceals missing postconditions behind 100% fuzz pass rates."*

Because Hypothesis simply takes 50 random steps along whatever transitions the LLM implemented, if a transition or invariant is missing, Hypothesis never explores it and reports complete success.

### How Formal Methods Elevate Pretense

```
┌────────────────────────────────────────────────────────────────────────┐
│                   THE FORMALIZED PRETENSE PIPELINE                     │
├────────────────────────────────────────────────────────────────────────┤
│ 1. Pretense State Machine (Authored by LLM in Python)                  │
│    - Discrete state: self.state                                        │
│    - Transitions: @transition(Target.method)                          │
│    - Antecedents: requires(...)                                       │
│    - Invariants: assert condition                                      │
├───────────────────────────────────┬────────────────────────────────────┤
│       Informal Fuzzing (Old)      │       Formal Verification (New)    │
│                                   │                                    │
│  Hypothesis runs 50 random walks  │  1. Z3 Antecedent Completeness:    │
│  - Heuristic sampling             │     Proves no unhandled state/args │
│  - Misses rare edge sequences     │  2. Bounded Model Checking (BMC):  │
│  - Subject to model tautology     │     Exhaustively unrolls k steps   │
│                                   │     to prove invariants hold for   │
│                                   │     ALL possible call sequences    │
└───────────────────────────────────┴────────────────────────────────────┘
```

#### A. Z3 Antecedent Completeness (Breaking the Model Tautology)
Before running the state machine against `lib`:
* For each method $M$, extract all transition guards (`requires(...)`).
* Ask Z3: $\exists s \in \text{State}, \text{args} \in \text{Domain}$ such that no transition guard applies.
* **If SAT:** Z3 hands the agent an unhandled state/input tuple that the LLM forgot to model in Pretense! This forces the agent to fix the state machine *before* testing the library, shattering the shared omission blind spot.

#### B. Symbolic Bounded Model Checking (BMC) over Transitions
Instead of relying on Hypothesis to randomly stumble upon a 7-step sequence that triggers an invariant violation:
* A lightweight BMC runner unrolls the Pretense state machine for $k$ steps ($k=3..5$ transitions).
* Z3 searches the **complete combinatorial space** of all possible transition sequences:
  $$s_0 \xrightarrow{t_1(a_1)} s_1 \xrightarrow{t_2(a_2)} s_2 \xrightarrow{t_3(a_3)} s_3$$
* If an assertion `assert condition` can fail anywhere in that bounded space, Z3 outputs the exact sequence of method calls:
  `[queue.push(item), queue.cancel(id), queue.pop()] -> AssertionError at line 42`
* Flash receives a minimal 3-step reproduction trace to fix the bug in one step.

#### C. Token Efficiency & Agent Feasibility
* **Zero new syntax for the LLM:** Flash authors the exact same Python Pretense classes it already knows how to write.
* **Zero interactive proof burden:** The translation from Pretense `@transition` and `requires` to Z3 constraints is purely mechanical and performed by harness tooling (`pre_lint` / `pretense_qa`).
* **High ROI:** Transforms an informal 50-example Monte Carlo fuzzer into an exhaustive mathematical verifier of protocol safety.

---

## 9. Partial Lean 4 Specifications as Executable Reference Oracles

An alternative or complementary formal approach is using **Lean 4** to author **partial, executable reference specifications**.

Lean 4 is both an interactive theorem prover and a modern, compiled, purely functional programming language. Crucially, **specifications in Lean do not need to be 100% proved to provide immense engineering value**.

### The Four Primitives for Partial Lean Specs

```lean
-- parts/<name>/lean/Model.lean
structure QueueState where
  items : List String
  capacity : Nat

-- 1. Pure Functional Reference Implementation
def push (s : QueueState) (item : String) : Option QueueState :=
  if s.items.length < s.capacity then
    some { s with items := item :: s.items }
  else
    none

-- 2. Formal Invariants with 'sorry' Holes (Decoupled from Proof)
theorem push_preserves_capacity (s : QueueState) (item : String) (s' : QueueState) :
  push s item = some s' → s'.items.length ≤ s'.capacity := by
  sorry  -- Typechecked and verified for consistency without manual proof!

-- 3. Opaque External Stubs (Black-boxing OS/IO)
opaque DatabaseConnection : Type
```

1. **The `sorry` Primitive:** Allows stating precise mathematical invariants and theorems while skipping the manual proof tactics. Lean's type checker (`lake build`) verifies that types compose, signatures match, and invariants are syntactically sound.
2. **Exhaustive Pattern Matching (Zero Omissions):** Lean enforces match completeness at compile time. An LLM writing a Lean reference model cannot accidentally omit an enum branch, status code, or null case—the compiler flags it instantly as a missing constructor.
3. **`opaque` and `axiom` Boundaries:** External realities (filesystems, network sockets, C-libraries) are black-boxed as opaque types, allowing the model to focus strictly on pure algorithmic transitions.
4. **`SlimCheck` Counterexample Falsification:** Lean's built-in testing engine searches for counterexamples to stated theorems before or instead of interactive proofs.

### Differential Oracle Architecture (Lean $\longleftrightarrow$ Python)

```
┌────────────────────────────────────────────────────────┐
│                   Lean 4 Specification                 │
│                 (parts/*/lean/Model.lean)              │
│                                                        │
│  - Exhaustive inductive types                          │
│  - Pure functional reference transitions               │
│  - Formal invariant declarations (with 'sorry' allowed)│
└───────────────────────────┬────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
    [lake build] (Type Oracle)     [Lean Native Binary / JSON CLI]
    Catches omissions & match      (Compiled Executable Reference Model)
    gaps deterministically                      │
                                                ▼
                                   [roles.qa / pretense]
                                   Differential Testing:
                                   `assert py_res == lean_oracle(input)`
```

* **Compilation:** Lean 4 compiles directly to native binaries or shared C-libraries via `lake build`.
* **Differential Testing:** The Autofab test runner invokes both the general-purpose Python `lib/*.py` and the compiled Lean 4 executable, comparing outputs across thousands of inputs.
* **Breaks the Shared Blind Spot:** Because the Lean specification is authored under strict functional and typing constraints, it serves as an uncompromising, independent oracle against which the Python implementation is audited.

---

## 10. Implementation Roadmap for Autofab

### Phase 1: Toolchain Evaluation & Proof-of-Concept
- [ ] Evaluate **CrossHair** (`crosshair-tool`) in an isolated Autofab parts directory for leaf contract verification.
- [ ] Prototype a lightweight **Z3 Partition Checker** in Python that extracts docstring preconditions from `low/*.pyi` and checks for domain coverage completeness.
- [ ] Prototype an antecedent completeness check for Pretense `@transition` methods using Z3.
- [ ] Prototype a toy **Lean 4 Partial Spec** for a small pure component (e.g. `semver_solver`) and evaluate differential execution against Python.

### Phase 2: Specification Coverage (`Spec-Cov`) Implementation
- [ ] Design a lightweight requirement tagging convention (`[REQ-XX]`) for `high/*.md` and `low/*.pyi`.
- [ ] Implement a static `spec_cov` linter in `autofab_py/support/lib/` to verify bipartite coverage between `low` requirements and `test` assertions.
- [ ] Integrate `spec_cov` into `roles.coverage` so 100% code coverage without 100% spec coverage fails the gate.

### Phase 3: Pretense BMC & Invariant Formalization
- [ ] Integrate Z3 bounded unrolling into `roles.pretense_qa` alongside existing Hypothesis fuzzing.
- [ ] Benchmark Gemini Flash on repairing Pretense state machines when presented with Z3 antecedent counterexamples vs. Hypothesis random failure traces.

### Phase 4: Role & Methodology Integration (`autofab_roles.toml`)
- [ ] Define `[roles.formal_qa]` as an optional verification gate in `autofab_py/autofab_roles.toml`:
  - Placed downstream of `lib`.
  - Runs prior to or alongside `qa`.
- [ ] Scaffolding and linter integration:
  - Add contract syntax checking to `low_lint.py`.
  - Add pragma support for uncontracted / unverifiable third-party calls in `lib_lint.py`.

### Phase 5: Benchmark & Efficiency Evaluation
- [ ] Run comparative benchmark flights (`bin/evaluate_model_efficiency.py`) comparing:
  - **Baseline:** Standard Cleanroom pipeline (`high` $\to$ `low` $\to$ `lib` $\to$ `test` $\to$ `qa`).
  - **Pretense Fuzzing:** Standard Pretense pipeline (Hypothesis 50 examples).
  - **Pretense Formal:** Pretense + Z3 Antecedent Completeness + BMC.
  - **Lean Oracle:** Differential verification against partial Lean 4 reference models.
- [ ] Measure:
  - Total tokens consumed.
  - Rounds to DAG convergence.
  - Soundness against cross-testing mutation suites.
  - Rate of caught omission defects.

---

## 11. Key Takeaways

1. **Improve Quality $\ne$ Total Correctness:** Formal verification in Autofab serves as an automated, adversarial edge-case hunter, not a mathematical proof trophy.
2. **Preserve Natural Language:** Natural language in `low` remains the supreme source of truth for design semantics and broad behavior. Formal invariants serve only as targeted boundary anchors.
3. **Pretense IS the Formal Model:** We do not need a foreign language like TLA+ or Alloy. Pretense's Python state machines (`@transition`, `requires`, `assert`) are already discrete transition systems. By replacing random Hypothesis walks with Z3-backed Bounded Model Checking (BMC), Pretense becomes a formal verification engine.
4. **Partial Lean Specs are Feasible:** Lean 4 allows writing pure executable reference models where theorems and invariants use `sorry` holes. Lean's mandatory match exhaustiveness catches omission bugs, and compiled Lean models act as differential testing oracles for general-purpose Python.
5. **Z3 Breaks the Model Tautology:** Checking transition antecedents with Z3 proves that the state machine has zero unhandled states or input gaps before testing `lib`, killing the shared omission blind spot.
6. **Spec-Cov Kills Correlated Omission:** Enforcing a formal bipartite graph between tagged specification requirements and test assertions prevents `lib` and `tests` from silently ignoring a feature.
7. **Designed for Fast LLMs:** By restricting formal contracts to 1-3 lines of Python expressions and providing concrete counterexample diagnostics, Gemini Flash can write, verify, and repair code with minimal token overhead and zero risk of getting stuck.
