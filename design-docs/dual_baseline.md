# Dual-Baseline Synthesis & Differential Fuzzing (`dual_baseline.md`)

## 1. Executive Summary

As AI code generation models scale in raw capability, an architectural question arises in automated software engineering:
> **Can we achieve correctness more efficiently by generating two independent baseline implementations from an interface specification and cross-checking them differentially, rather than routing a single implementation through a multi-stage double-blind Cleanroom pipeline?**

This document establishes the formal design, economic trade-offs, and verification mechanics of **Dual-Baseline Synthesis with Differential Hypothesis Fuzzing**, comparing it directly against the **Cleanroom Double-Blind Pipeline** on an **equal footing**.

### The Equal-Footing Benchmark Scope
To evaluate both paradigms rigorously without confounding variables:
1. **Identical Inputs**: Both approaches start from the exact same pre-authored formal specification: High-Level Specifications (`high/*.md`), Planning Canvases (`planning/*.md`), and Low-Level Typed Python Stubs (`low/*.pyi`). The specification authoring ladder is **excluded** from the benchmark comparison; only the **`lib` / `test` / `auditor`** phases are measured.
2. **Identical Testing Tooling**: Both approaches utilize **Stateful Property-Based Testing (`hypothesis.stateful.RuleBasedStateMachine`)** to generate thousands of randomized operational sequences and shrink failures to minimal traces.
3. **Strictly Oracle-Driven Arbiters**: In both approaches, the auditor/arbiter executes deterministic test suites and fuzzers first. The arbiter **only reads large text specifications when an actual failure or divergence occurs** (the Anti-Speculation Rule).

---

## 2. The Twin Inherent Vulnerabilities of Both Approaches

A critical theoretical finding of this architecture is that **neither approach is immune to fundamental cognitive limitations of large language models**. Both Cleanroom and Dual Baseline face two shared failure modes:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        THE TWIN INHERENT VULNERABILITIES                               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   1. SHARED OMISSION VULNERABILITY (Coincident Failures / Knight-Leveson)              │
│      * Models trained on similar open-source corpora share cognitive blind spots.      │
│      * In Cleanroom: Lib author and Test author both omit edge-case invariants.        │
│      * In Dual Baseline: Base 1 and Base 2 both omit edge-case logic and rules.        │
│      * Outcome: 100% false agreement and green test passes on broken code!             │
│                                                                                        │
│   2. SHARED UNDERSPECIFICATION VULNERABILITY (Ambiguity & Silence)                     │
│      * Specs inevitably have gaps (e.g. exception propagation on task failure).        │
│      * In Cleanroom: Single interpretation chosen silently; may be fragile.           │
│      * In Dual Baseline: Independent models interpret gaps differently, causing        │
│        divergences that force Arbiter adjudication to lock down the spec.              │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### A. Shared Omission Vulnerability (The Knight-Leveson Fallacy in LLMs)
In 1986, Knight and Leveson empirically disproved the independence assumption in N-version programming: independently written software systems fail on the exact same inputs because human engineers share cognitive models.

With LLMs, this problem is amplified by shared pre-training corpora (The Stack, GitHub, common tutorials):
* **In Cleanroom ($W_{\text{lib}} \parallel W_{\text{test}}$)**:
  Even though the Lib author and Test author work in strict physical double-blind isolation ($\mathcal{I} = 0$), both models may share the same conceptual bias (e.g. conceiving of DAG operations as strictly linear, forward sequences). The Test author fails to author an invariant for node re-registration edge clearance, and the Lib author fails to implement it. Statement coverage reaches 95%, branch coverage reaches 90%, all tests pass, but a critical soundness defect escapes.
* **In Dual Baseline ($Base_1 \parallel Base_2$)**:
  Baseline 1 and Baseline 2 are prompted independently. If both models share the same training prior regarding DAG data structures, *both* will omit node re-registration edge clearance in their implementations, and *both* will omit it from their Hypothesis rules.
  When $Base_1$ and $Base_2$ are cross-tested and differentially fuzzed, **they agree with 100% parity across thousands of fuzzing steps**. Differential testing reports zero divergences, giving false confidence in an incorrect system.
* **The Antidote**: Bounded state-machine invariant fuzzing with exhaustive strategy generation. However, if the invariant itself is omitted from the specification rules, both paradigms fail coincidentally.

### B. Shared Underspecification Vulnerability
Specifications, no matter how detailed, occasionally leave peripheral details ungrounded or ambiguous (e.g. whether a failed task raises `TaskExecutionError` or returns `TaskReport(status=FAILED)`, or tie-breaking order in topological sorts):
* **In Cleanroom**:
  The Lib author picks an interpretation. The Test author, reading the same text, may pick the same interpretation or fail during QA. If both pick the same interpretation, the uncontracted behavior becomes de facto production logic without ever being formalized.
* **In Dual Baseline**:
  Because $Base_1$ and $Base_2$ generate code independently, they frequently make **different interpretations** of underspecified areas.
  When cross-tested, this difference triggers an immediate divergence.
  **This is Dual Baseline's greatest asset**: it turns ambiguity into a deterministic failure that wakes up the Arbiter. The Arbiter inspects the spec, discovers that the contract was silent, and triggers an HLS-first specification patch to lock down the behavior permanently.

---

## 3. Architecture Comparison: Cleanroom vs. Dual-Baseline

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        ARCHITECTURAL EXECUTION TOPOLOGIES                              │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   A. CLEANROOM PIPELINE (Double-Blind Isolation):                                      │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │ Specification (low/*.pyi)                                                      │   │
│   │   ├──► W_lib: Synthesizes Production Library (lib/*.py)                         │   │
│   │   └──► W_test: Synthesizes Unit Tests + Hypothesis State Machine (tests/)       │   │
│   │          (Strict physical double-blind isolation: I = 0)                       │   │
│   │                                                                                │   │
│   │ Execution: Pytest & Hypothesis run tests/ against lib/                         │   │
│   │ Arbiter: W_qa runs tests; blames W_lib if assertions fail.                      │   │
│   └────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                        │
│   B. DUAL-BASELINE PIPELINE (Co-Generation & Differential Fuzzing):                    │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │ Specification (low/*.pyi)                                                      │   │
│   │   ├──► Baseline 1: Generates (Lib_1 + Test_1 + Hypothesis_1) in parallel        │   │
│   │   └──► Baseline 2: Generates (Lib_2 + Test_2 + Hypothesis_2) in parallel        │   │
│   │                                                                                │   │
│   │ Execution:                                                                     │   │
│   │   1. Cross-Matrix: Test_1 vs. Lib_2, Test_2 vs. Lib_1                          │   │
│   │   2. Differential Lockstep Fuzzing: assert Lib_1(s, a) == Lib_2(s, a)          │   │
│   │ Arbiter: Event-driven; only wakes up if Cross-Matrix fails or Fuzzer diverges. │   │
│   └────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Detailed Operational Topologies:

#### Cleanroom (`lib` + `test` + `auditor` with Hypothesis)
1. **$W_{\text{lib}}$ Workspace**: Receives `low/*.pyi` and planning grounding. Synthesizes `lib/*.py`. Has zero visibility into test code.
2. **$W_{\text{test}}$ Workspace**: Receives `low/*.pyi` and planning grounding. Synthesizes example-based unit tests (`tests/*_impl_test.py`) and a Hypothesis state machine (`tests/*_state_machine_test.py`). Has zero visibility into implementation code.
3. **Execution & Blame Loop**:
   - $W_{\text{qa}}$ runs unit tests and Hypothesis fuzzing against `lib/*.py`.
   - If tests pass $\to$ certified.
   - If tests fail $\to$ $W_{\text{qa}}$ captures the minimal shrunk trace, executes `bin/blame lib/<unit>.py "<trace>"`, and hands the workspace back to $W_{\text{lib}}$ for an iterative repair round.

#### Dual-Baseline (`base_1` + `base_2` + `auditor` with Hypothesis)
1. **Baseline 1 ($Base_1$)**: Prompted directly with `low/*.pyi`. Generates $Lib_1$ and $Test_1$ (including Hypothesis state machine) co-located in a single prompt step.
2. **Baseline 2 ($Base_2$)**: Prompted concurrently with the identical prompt and seed/temperature variations. Generates $Lib_2$ and $Test_2$ in parallel.
3. **Differential Execution Engine**:
   - **Step 1 (Self-Check)**: Verify $Test_1$ passes on $Lib_1$, and $Test_2$ passes on $Lib_2$.
   - **Step 2 (Cross-Check)**: Run $Test_1$ on $Lib_2$, and $Test_2$ on $Lib_1$.
   - **Step 3 (Lockstep Differential Fuzzing)**: Feed thousands of identical random action sequences to $Lib_1$ and $Lib_2$ in parallel, asserting after every operation:
     `assert Lib_1.query_state() == Lib_2.query_state()`.
4. **Arbiter Protocol**:
   - If Steps 1–3 pass with zero divergences $\to$ certified immediately without arbiter tokens.
   - If a cross-test or differential assertion trips $\to$ Arbiter receives the minimal reproducing trace, reads `low/*.pyi`, determines which baseline violated the spec, and issues an automated repair round.

---

## 4. Quantitative Resource Accounting (Token & Latency Comparison)

A rigorous comparison must evaluate the actual token consumption and wall-clock latency within the benchmarked phase (`lib/test/auditor`):

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                     RESOURCE CONSUMPTION MATRIX (BENCHMARKED PHASE)                    │
├───────────────────────────────┬────────────────────────────┬───────────────────────────┤
│ Metric                        │ Cleanroom Pipeline         │ Dual-Baseline Cross-Check │
├───────────────────────────────┼────────────────────────────┼───────────────────────────┤
│ Synthesis Track 1             │ W_lib (lib/*.py): ~10k tok │ Base 1 (Lib_1 + Test_1):  │
│                               │                            │ ~15k tokens               │
│ Synthesis Track 2             │ W_test (tests/): ~10k tok  │ Base 2 (Lib_2 + Test_2):  │
│                               │                            │ ~15k tokens               │
│ Parallel Execution Mode       │ W_lib || W_test            │ Base 1 || Base 2          │
├───────────────────────────────┼────────────────────────────┼───────────────────────────┤
│ Clean Pass Total Tokens       │ ~20,000 tokens             │ ~30,000 tokens (+50%)     │
├───────────────────────────────┼────────────────────────────┼───────────────────────────┤
│ Iteration / Divergence Cost   │ Blame on Lib: ~8k tokens   │ Arbiter Triage: ~4k tok   │
│                               │                            │ Fix on losing Lib: ~8k tok│
│ Total with 1 Divergence       │ ~28,000 tokens             │ ~42,000 tokens (+50%)     │
├───────────────────────────────┼────────────────────────────┼───────────────────────────┤
│ Wall-Clock Latency            │ max(T_lib, T_test) + T_qa  │ max(T_b1, T_b2) + T_cross │
│                               │ ≈ 45 – 60 seconds          │ ≈ 50 – 75 seconds         │
├───────────────────────────────┼────────────────────────────┼───────────────────────────┤
│ Model Cognitive Friction      │ Role workspaces & tooling  │ Zero (Standard code task) │
└───────────────────────────────┴────────────────────────────┴───────────────────────────┘
```

### Key Economic Takeaways:
1. **Dual Baseline Consumes 30%–50% MORE Synthesis Tokens**:
   Because Dual Baseline produces two complete production libraries and two complete test suites, it burns significantly more raw output tokens on clean runs than Cleanroom (which produces one production library and one test suite).
2. **Wall-Clock Latency Is Nearly Identical**:
   Both architectures run their synthesis tracks in parallel. Even though a baseline prompt generates both code and tests in a single step, modern high-throughput inference engines complete both tracks in roughly 60 seconds.
3. **The Cognitive Distribution Dividend**:
   Dual Baseline's greatest advantage is **not token savings, but pre-training alignment**:
   - Asking a model: *"Here is an interface stub (`.pyi`). Write the implementation class and a Hypothesis test suite"* matches the exact distribution of GitHub code and standard coding benchmarks (SWE-bench, HumanEval).
   - The model experiences zero friction with custom role workspace CLI commands (`get_work`, `check_files`, `submit`) inside its generation prompt.

---

## 5. The Differential Lockstep Fuzzing Engine

In traditional example-based testing, the test author must write explicit assertion predicates:
```python
# Traditional test authoring: model must conceive expected value
assert dag.get_dependencies("A") == {"C"}
```
If the test author forgets to write the assertion or miscalculates the expected return value, the test provides zero verification value.

### The Power of Assertion-Free Parity Testing
Under Dual Baseline, we can synthesize a **Lockstep Differential State Machine**:
```python
class DifferentialDAGMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.sut_a = ImplementationA()
        self.sut_b = ImplementationB()

    @rule(node_id=st.text(min_size=1, max_size=5), deps=st.sets(st.text(...)))
    def add_node(self, node_id, deps):
        res_a = self.sut_a.add_node(node_id, deps)
        res_b = self.sut_b.add_node(node_id, deps)
        assert res_a == res_b, f"Return value divergence on add_node({node_id}): {res_a} != {res_b}"

    @invariant()
    def state_parity(self):
        assert self.sut_a.all_nodes() == self.sut_b.all_nodes()
        assert self.sut_a.all_edges() == self.sut_b.all_edges()
```

#### Why This Is a Breakthrough for Budget Models:
1. **No Assertion Conception Required**: Neither model has to predict what the graph *should* look like after 30 arbitrary mutations. The testing engine simply asserts that **both independent implementations produced the exact same state**.
2. **Shrinking Discovers the Minimal Divergence**:
   If Implementation A cleared stale reverse edges on re-registration but Implementation B accumulated them, Hypothesis automatically shrinks the failure sequence to the minimal 2-step divergence trace:
   ```
   Falsifying example:
   state.add_node(node_id='a', deps={'b'})
   state.add_node(node_id='a', deps={'c'})
   AssertionError: sut_a.all_edges() != sut_b.all_edges()
   ```

---

## 6. The Arbiter Protocol for Dual Baseline

When differential testing trips, how does the system adjudicate without degenerating into hallucinated prompt arguments?

The Arbiter operates under a deterministic decision protocol:

```
                              ┌───────────────────────────────┐
                              │  Divergence Trace Received:   │
                              │  Minimal Reproducing Sequence │
                              └───────────────┬───────────────┘
                                              │
                                              ▼
                              ┌───────────────────────────────┐
                              │   Arbiter inspects low/*.pyi  │
                              │   for target operation        │
                              └───────────────┬───────────────┘
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
         [ Case 1: Spec is Explicit ]                    [ Case 2: Spec is Silent ]
         Contract clearly dictates outcome               Ambiguous or uncontracted behavior
                      │                                               │
         ┌────────────┴────────────┐                     ┌────────────┴────────────┐
         ▼                         ▼                     ▼                         ▼
   Impl A matches            Impl B matches        Flag Specification        Update HLS
   spec; Impl B broke        spec; Impl A broke    Defect to User            first & re-align
   contract.                 contract.             or Coordinator.           both models.
         │                         │
         ▼                         ▼
   Issue Blame to B;         Issue Blame to A;
   Keep A as canonical.      Keep B as canonical.
```

### Deterministic Adjudication Rules:
1. **The Spec Is the Sole Oracle**: The Arbiter never votes based on "which code looks cleaner." It looks strictly at the declared postconditions in `low/*.pyi`.
2. **Winner Selection**: Whichever implementation satisfied the postcondition is certified. The losing implementation is either patched via an automated blame round or discarded in favor of the winning implementation.
3. **Spec Defect Feedback**: If the specification omitted the requirement, the round is aborted as a **Specification Hole**. The specification is patched first under the HLS-first rule, preventing uncontracted behavior from entering production.

---

## 7. Comparison Matrix: Cleanroom vs. Dual Baseline

| Evaluation Dimension | Cleanroom Pipeline (`lib` + `test`) | Dual-Baseline Cross-Check (`base_1` + `base_2`) | Pretense Baseline (Single Agent) |
| :--- | :---: | :---: | :---: |
| **Token Efficiency** | Moderate ($\sim$11M–20M net tokens) | Lower ($\sim$15M–25M tokens) | **Highest** ($\sim$5.7M–6.9M tokens; 37%–74% cheaper) |
| **Wall Clock Latency** | Higher (1100s–1200s; multi-round dispatch) | Moderate ($\approx$ 600s–800s) | **Lowest** (260s–490s; 2.4x–4.2x faster) |
| **Model Pre-Training Fit** | Lower (Requires role CLI protocol) | **High** (Standard class + pytest prompt) | **High** (Standard class + Pretense proto prompt) |
| **Double-Blind Independence** | **Strict Physical Isolation** ($\mathcal{I} = 0$) | Co-generation within prompt; broken by cross-testing | Single prompt ($\mathcal{I} > 0$); bounded by state machine |
| **Assertion Synthesis Burden** | High (Test author must conceive assertions) | **Zero for Fuzzing** (Direct state parity assertion) | Low (State transitions & fake synthesis provided) |
| **Vulnerability to Omission** | High (If test author omits invariant) | High (If both models omit invariant) | Moderate (State machine forces explicit transitions) |
| **Surfacing Underspecification** | Weak (Silent single-track assumption) | **Strong** (Divergence exposes spec holes) | Moderate (Pretense rejects inconsistent transitions) |
| **Arbiter Cognitive Load** | Event-driven on test failure | Event-driven on divergence or cross-test failure | Self-contained (Single-round execution; no arbiter) |

### 7.1 Empirical Evidence: Pretense as a Baseline Equalizer (`dag_engine_lite`)

Recent empirical benchmarks on `dag_engine_lite` reveal that arming a single-agent baseline with **Pretense** fundamentally shifts the cost/quality boundary:

| Metric | DeepSeek-Flash Cleanroom (Net) | DeepSeek-Flash Pretense Baseline | Gemini-3.8-Flash Cleanroom (Net) | Gemini-3.8-Flash Pretense Baseline | Qwen-MoE Cleanroom | Qwen-MoE Pretense Baseline |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Passing Tests** | **49P / 0F** | **33P / 0F** | **60P / 0F** | **57P / 0F** | **98P / 0F** | **92P / 0F** |
| **Pyright (Lib)** | **0 errors** | **0 errors** | **0 errors** | **0 errors** | **0 errors** | **0 errors** |
| **Token Cost** | $0.1779 | **$0.1332** (-25%) | $0.7487 | **$0.1972** (**-74%**) | $0.0000 (12.8M tok) | **$0.0000** (**6.7M tok**, -48%) |
| **Wall Clock** | 1180.9s | **492.3s** (2.4x) | 1135.0s | **266.4s** (**4.2x**) | 2223.8s | **1151.5s** (1.9x) |

#### Rationale for the Cost Advantage:
1. **Zero Multi-Agent Overhead**: Cleanroom incurs dispatch, workspace provisioning, and arbiter review rounds. The baseline completes in exactly one round.
2. **Pretense Replaces Ad-Hoc Test Scaffolding**: Rather than wasting thousands of tokens writing fragile mock frameworks and AST test helpers, Pretense gives the model an executable transition proto and automatic fake synthesizer.
3. **Execution Watchdogs Eliminate Hangs**: With `PYTHONFAULTHANDLER=1` and `PRETENSE_TIMEOUT=45.0s`, infinite loops and stalls dump immediate stack traces, keeping single-agent iterations lean and deterministic.

---

## 8. Empirical Benchmark Plan (`semver_solver`)

To empirically validate the theoretical trade-offs codified in this document, the upcoming `semver_solver` benchmark will be executed under three experimental arms:

1. **Arm 1: Canonical Cleanroom (`lib` + `test` + Hypothesis)**:
   $W_{\text{lib}}$ and $W_{\text{test}}$ dispatched under physical double-blind isolation, audited by $W_{\text{qa}}$.
2. **Arm 2: Dual Baseline with Differential Fuzzing**:
   Two parallel baseline runs prompted with `low/semver_solver.pyi`, evaluated via cross-test execution and lockstep Hypothesis differential state fuzzing.
3. **Arm 3: Single Baseline (Control)**:
   Standard industry baseline (single model generating code and tests in one step).

### Measured Outcome Metrics:
- **Defect Escape Rate**: Evaluated via foreign cross-testing against frontier reference test suites (Gemini Argon / DeepSeek).
- **Token Efficiency**: Total input and output tokens consumed across all rounds to reach certified convergence.
- **Specification Hole Discovery Rate**: Number of genuine contract ambiguities surfaced by divergence.
- **Convergence Rate**: Percentage of runs reaching zero-defect certification without human intervention.
