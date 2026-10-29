# Pretense: Stateful State-Machine Verification & Fake Synthesis in Cleanroom (`pretense.md`)

## Table of Contents

1. [Executive Summary & Terminology Lexicon](#1-executive-summary--terminology-lexicon)
   - [Standardized Terminology Lexicon](#standardized-terminology-lexicon)
2. [Empirical Genesis: Cross-Model Differential Defect Analysis & Coincident Cognitive Blind Spots](#2-empirical-genesis-cross-model-differential-defect-analysis--coincident-cognitive-blind-spots)
   - [The Empirical Phenomenon & Cross-Model Outcomes](#the-empirical-phenomenon--cross-model-outcomes)
   - [Anatomy of the Three Undetected Defects](#anatomy-of-the-three-undetected-defects)
   - [Theoretical Analysis: Why Single-Model Cleanroom Missed These Defects](#theoretical-analysis-why-single-model-cleanroom-missed-these-defects)
   - [Why Foreign Models Did Not Share the Blind Spots](#why-foreign-models-did-not-share-the-blind-spots)
   - [Architectural Remedies: The Necessity of Pretense](#architectural-remedies-the-necessity-of-pretense)
3. [Theoretical Architecture: Why Hypothesis State Machines?](#3-theoretical-architecture-why-hypothesis-state-machines)
4. [Cleanroom Pipeline Integration: Author & Auditor Roles](#4-cleanroom-pipeline-integration-author--auditor-roles)
5. [State Machines as Dual-Role Assets: Fakes and Test Drivers](#5-state-machines-as-dual-role-assets-fakes-and-test-drivers)
   - [Dynamic Input Generation: The "Strategies as Values" Architecture](#dynamic-input-generation-the-strategies-as-values-architecture)
6. [Path Coverage vs. Hypothesis State-Machine Transitions](#6-path-coverage-vs-hypothesis-state-machine-transitions)
7. [Contract Traceability: Requirements in Comments vs. Slugs](#7-contract-traceability-requirements-in-comments-vs-slugs)
8. [Comparison Matrix: Verification Strategies](#8-comparison-matrix-verification-strategies)
9. [The Pretense CLI Runner & Repository Architecture](#9-the-pretense-cli-runner--repository-architecture)
10. [Implementation Roadmap & Milestones](#10-implementation-roadmap--milestones)
11. [Role Architecture Plan: `pretense`, `pretense_qa`, and `pretense_coverage`](#11-role-architecture-plan-pretense-pretense_qa-and-pretense_coverage)
12. [Empirical Benchmarking: Pretense as a Baseline Equalizer](#12-empirical-benchmarking-pretense-as-a-baseline-equalizer)
13. [Future Empirical Study: Cleanroom vs. State-Machine-Driven TDD](#13-future-empirical-study-cleanroom-vs-state-machine-driven-tdd)

---

## 1. Executive Summary & Terminology Lexicon

Empirical benchmarking across model tiers on `dag_engine_lite` revealed a critical blind spot in LLM-generated software verification:
1. **AST Statement & Branch Coverage Is Shallow**: A test suite achieving 95% line coverage and 90% branch coverage greenlit three genuine soundness bugs (off-by-one retry accounting, node re-registration stale edge accumulation, and cross-component scheduler desynchronization).
2. **Mutation Testing (`mutmut`) is Obsolete & Blind to Omission**: AST mutators only mutate existing syntax lines. If an implementation completely omits a state cleanup or synchronization loop, `mutmut` has no syntax nodes to mutate and reports false 100% kill rates. Furthermore, `mutmut` runs in separate subprocesses taking minutes to hours. Pretense's differential state fuzzing ($Lib \equiv Spec$) completely replaces and obsoletes `mutmut`.
3. **Open-Ended "Chaos Testers" Lack a Termination Metric**: Asking an LLM to author arbitrary "chaos" or "edge-case" tests without an objective stopping condition degrades into unbound token consumption with no mathematical convergence criteria.

This design document establishes **Pretense**—Cleanroom's unified state-machine-driven testing, verification, and fake synthesis engine. Powered by Hypothesis's conjecture fuzzing engine (`hypothesis.stateful.RuleBasedStateMachine`), Pretense forces models to verify state-transition invariants through bounded, deterministic search, minimal-trace shrinking, and automatic fake synthesis.

---

### Standardized Terminology Lexicon

To prevent conflation across specifications, state machines, implementations, and test harnesses, Pretense establishes a strict terminology standard:

| Term | Exact Definition | Canonical Location |
| :--- | :--- | :--- |
| **The Specification** | The authoritative, declarative contract of record. Defines *what* contracts, types, protocols, postconditions, and invariants must hold, without mandating procedural algorithms. | `high/*.md`, `planning/*.md`, `low/*.pyi` |
| **Pretense State Machine** | An **executable state transition model** written in Python (transitions, antecedents, abstract collections). It is an executable artifact derived from the specification, **NOT** a synonym for the specification itself! | `parts/*/tests/*_state_machine.py` |
| **Pretense Fake Adapter** | A concrete runtime object conforming to an interface `Protocol`, compiled from an interface state machine (`machine.as_fake()`) to be injected into a concrete implementation under test. | Ephemeral instance passed to `lib` |
| **Test Driver** | An outward-calling harness instantiated from a state machine to drive concrete implementations (adversarial fuzzer in Hypothesis or static scenario runner in unit tests). | Harness runtime wrapper |
| **Intra-Component Objects** | Concrete classes defined within the same component's `_impl` module. They are **real and tested together in lockstep** (zero internal faking). | `parts/<name>/lib/*_impl.py` |
| **Inter-Component Collaborators**| External singletons imported from other components. Modeled via imported interface state machines and injected as fake adapters. | `parts/<other>/low/*.pyi` |
| **Step** | A single prompt $\leftrightarrow$ tool-call interaction cycle between an agent and the harness. | Runtime interaction step |
| **Round** | A full Cleanroom role dispatch wave across assigned targets until completion, blame, or exhaustion. | Role dispatch pass |

---

## 2. Empirical Genesis: Cross-Model Differential Defect Analysis & Coincident Cognitive Blind Spots

### The Empirical Phenomenon & Cross-Model Outcomes

In the empirical evaluation of Cleanroom architectures against traditional software engineering baselines on the `dag_engine_lite` benchmark suite, the single-model Cleanroom run using **Qwen3.6-35B-A3B-oQ6-mtp** (Tier 1 Local MoE) achieved an ostensibly perfect verification outcome:
- **Internal Cleanroom Status**: Verified & Passed (Pass 1 and Pass 2 gates cleared).
- **Static Type Checking**: 0 Pyright diagnostics.
- **Self-Authored Test Suite ($V_{\text{self}} \to P_{\text{self}}$)**: 60/60 tests passing (100%).
- **Structural Code Coverage**: 95.0% Statement Coverage, 90.0% Branch Coverage.
- **Specification Linter Diagnostics**: 0 errors.

Under standard software engineering quality metrics, this library implementation ($P_{\text{qwen}}$) would be certified for production deployment. Furthermore, because Cleanroom enforced strict double-blind physical isolation ($\mathcal{I} = 0$) between the Synthesizer workspace ($W_{\text{lib}}$) and the Certifier workspace ($W_{\text{test}}$), the test suite did not suffer from the classic **Contamination Trap** of single-agent joint context TDD (where an agent rewrites test assertions to tautologically affirm broken code).

However, when independent foreign test suites authored from the exact same formal Low-Level Specification (`low/*.pyi`) by different frontier and cloud model families (**DeepSeek-V3/Flash**, **Gemini 3.8 Flash**, and **Gemini 4 Argon**) were executed against Qwen's Cleanroom implementation via the differential cross-testing runner (`bin/run_cross_tests.py`), **three genuine soundness defects** were immediately exposed:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│               CROSS-MODEL DIFFERENTIAL VERIFICATION OUTCOMES (ON P_qwen)               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   Certifier Test Suite (V)             Pass / Fail Rate   Soundness Status             │
│   ──────────────────────────────────   ────────────────   ──────────────────────────   │
│   Qwen Cleanroom (Self: V_qwen)        60 / 60 (100.0%)   PASS (Coincident Blind Spot) │
│   DeepSeek Cleanroom (V_deepseek)      47 / 48 ( 97.9%)   FAIL (Off-by-One Retry Bug)  │
│   Gemini 3.8 Flash (V_gemini_flash)    32 / 36 ( 88.9%)   FAIL (3 Defects Exposed)     │
│   Gemini 4 Argon (V_gemini_argon)      19 / 20 ( 95.0%)   FAIL (Dynamic Retry Bug)     │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

This empirical result established the core motivation for Pretense:
1. The exact mechanical and semantic nature of the three undetected defects.
2. Why Cleanroom's single-model double-blind isolation failed to prevent or detect them.
3. Why 95% line and 90% branch coverage failed to flag the omissions.
4. The theoretical implications for AI software engineering and the architectural necessity of state-machine transition fuzzing and heterogeneous multi-model ensembles.

---

### Anatomy of the Three Undetected Defects

#### Defect 1: Off-by-One Retry Accounting on Action Recovery (`DAGRunner.run`)

##### The Formal Contract (`low/dag_engine_lite.pyi` & `low/dag_engine_lite_impl.pyi`)
```python
@data_type
@dataclass(frozen=True)
class NodeResult(Generic[T]):
    """Outcome record of a node execution.
    Args:
        ...
        retries_attempted: Number of retries executed before final state.
    """
    node_id: str
    state: NodeState
    value: Optional[T] = None
    error: Optional[Exception] = None
    duration_seconds: float = 0.0
    retries_attempted: int = 0
```
- **Contract Invariant**: An execution consists of 1 initial invocation (`attempt 0`) plus up to $N$ retry invocations (`attempt 1 .. N`). If an action fails once and succeeds on the second try, exactly **1 retry** was executed (`retries_attempted == 1`). If it fails twice and succeeds on the third try, exactly **2 retries** were executed (`retries_attempted == 2`).

##### Qwen's Implementation Flaw (`P_qwen: lib_1.py:927`)
```python
retries_attempted = 0
caught_exc: Optional[Exception] = None
action_value: Any = None
for attempt in range(1 + max_retries):
    try:
        action_value = definition.action()
        node_succeeded = True
        break
    except Exception as exc:
        caught_exc = exc
        if attempt > 0:
            retries_attempted += 1
```
- **The Defect**: Notice that Qwen placed `if attempt > 0: retries_attempted += 1` inside the `except` block.
  - If `attempt 0` fails: `attempt > 0` is `False`, so `retries_attempted` remains `0`.
  - If `attempt 1` executes and **succeeds**: the loop executes `action_value = definition.action(); node_succeeded = True; break`. It **never reaches the `except` block**!
  - `retries_attempted` remains `0`, even though 1 retry was executed!
  - If `attempt 1` fails and `attempt 2` succeeds: `retries_attempted` is incremented once during attempt 1, but attempt 2 succeeds and breaks before `except`, leaving `retries_attempted == 1` instead of `2`.
- **The Only Case It Works**: When **all retries fail and the action is exhausted**. If `max_retries = 2`, and all 3 attempts fail, attempts 1 and 2 hit `except`, leaving `retries_attempted == 2`.

##### Why Qwen's Self-Test ($V_{\text{qwen}}$) Missed It
Qwen's Certifier ($W_{\text{test}}$) authored exactly one test for retries:
```python
def test_run_retries_on_failure(self) -> None:
    ...
    def eventually_fails():
        call_count["count"] += 1
        raise RuntimeError("still failing")
    dag.add_node("a", action=eventually_fails, retries=2)
    report = runner.run()
    self.assertEqual(call_count["count"], 3)
    self.assertEqual(report.results["a"].state, dag_engine_lite.NodeState.FAILED)
    self.assertEqual(report.results["a"].retries_attempted, 2)
```
Qwen's test author tested **only the total exhaustion failure mode**. Because all 3 attempts failed, Qwen's buggy implementation coincidentally emitted `retries_attempted = 2`, matching the test assertion perfectly.

##### How Foreign Tests Caught It
DeepSeek-V3 authored:
```python
def test_run_retries_failed_action_until_success(self) -> None:
    # Fails twice, succeeds on attempt index 2 (retry 2)
    ...
    self.assertEqual(result.retries_attempted, 2)
# FAILED: AssertionError: 1 != 2
```
Gemini 3.8 Flash authored:
```python
def test_run_node_retries_and_recovers(self) -> None:
    # Fails once, succeeds on retry 1
    ...
    self.assertEqual(result.retries_attempted, 1)
# FAILED: AssertionError: 0 != 1
```

---

#### Defect 2: Node Re-Registration Stale Edge Accumulation (`DAG.add_node`)

##### The Formal Contract (`low/dag_engine_lite.pyi`)
```python
def add_node(
    self,
    node_id: str,
    action: Callable[[], Any],
    dependencies: Optional[Collection[str]] = None,
    priority: int = 0,
    retries: int = 0,
) -> None:
    """Adds a task node to the graph.
    ...
    POSTCONDITIONS:
    - If a node with the same identifier exists, MUST replace the node definition and dependencies.
    """
```

##### Qwen's Implementation Flaw (`P_qwen: lib_1.py:598`)
```python
def add_node(self, node_id: str, action: Callable[[], Any], dependencies=None, priority=0, retries=0) -> None:
    deps = frozenset(dependencies) if dependencies else frozenset()
    definition = dag_engine_lite.NodeDefinition(node_id, action, deps, priority, retries)
    self._nodes[node_id] = definition
    if node_id not in self._upstream:
        self._upstream[node_id] = set()
    if node_id not in self._downstream:
        self._downstream[node_id] = set()
    for dep in deps:
        self.add_edge(dep, node_id)
```
- **The Defect**: `add_node` overwrites `self._nodes[node_id]`, but **fails to remove existing dependency edges** from `self._upstream[node_id]` or `self._downstream[old_dep]`.
- If node `target` was initially registered with `dependencies=["dep1"]`, and then re-registered with `dependencies=["dep2"]`, `add_edge("dep2", "target")` adds the new edge, but the incoming edge from `dep1` remains in `self._upstream["target"]`!
- Calling `dag.get_dependencies("target")` returns `{"dep1", "dep2"}` instead of `{"dep2"}`.

##### Why Qwen's Self-Test Missed It
Qwen's Certifier authored 4 unit tests for `add_node`:
1. `test_add_node_registers_definition`
2. `test_add_node_with_dependencies`
3. `test_add_node_priority_stored`
4. `test_add_node_retries_stored`

Every single test initialized an empty DAG, added a node once, and verified properties on the fresh node. The Certifier never authored a scenario exercising the re-registration postcondition.

##### How Foreign Tests Caught It
Gemini 3.8 Flash authored:
```python
def test_re_register_node_replaces_definition_and_dependencies(self) -> None:
    dag.add_node("target", action=lambda: 1, dependencies=["dep1"])
    dag.add_node("target", action=lambda: 2, dependencies=["dep2"])
    self.assertEqual(dag.get_dependencies("target"), {"dep2"})
# FAILED: AssertionError: Items in the first set but not the second: 'dep1'
```

---

#### Defect 3: Cross-Component State Desynchronization on Node Removal (`WaveScheduler`)

##### The Formal Contract (`low/dag_engine_lite_impl.pyi`)
```python
@singleton_type("system")
class WaveScheduler(dag_engine_lite.WaveScheduler):
    """Concrete realization of sequential wave scheduler.
    GROUNDING:
    - Resolves the active DAG service via get_singleton(dag_engine_lite.DAG).
    - Maintains scheduling state across _dag and _states dictionary mapping node identifiers to dag_engine_lite.NodeState.
    - Synchronizes dynamic node state by discovering registered nodes from _dag.all_nodes(), initializing root nodes to dag_engine_lite.NodeState.READY and non-root nodes to dag_engine_lite.NodeState.PENDING.
    """
```

##### Qwen's Implementation Flaw (`P_qwen: lib_1.py:773`)
```python
def _sync_states(self) -> None:
    all_nodes = self._dag.all_nodes()
    for node_id in all_nodes:
        if node_id not in self._states:
            deps = self._dag.get_dependencies(node_id)
            if not deps:
                self._states[node_id] = dag_engine_lite.NodeState.READY
            else:
                self._states[node_id] = dag_engine_lite.NodeState.PENDING
```
- **The Defect**: `_sync_states` is unidirectional additive. It scans `self._dag.all_nodes()` and adds new nodes to `self._states`.
- If a caller calls `dag.remove_node("removable")`, the node is removed from the DAG. When `scheduler.get_all_states()` is invoked, `_sync_states()` runs, but does **not purge** keys from `self._states` that are no longer in `self._dag.all_nodes()`.
- The removed node remains indefinitely in the scheduler's state dictionary as a zombie node.

##### Why Qwen's Self-Test Missed It
Qwen tested `dag.remove_node()` extensively in `TestDAGOperations` on the `DAG` class in isolation. It tested `WaveScheduler` in `TestWaveSchedulerOperations` on static graphs that were never mutated during the scheduler's lifecycle. It never authored an integration test combining dynamic graph removal with wave scheduler state queries.

##### How Foreign Tests Caught It
Gemini 3.8 Flash authored:
```python
def test_remove_node_synchronizes_scheduler_state(self) -> None:
    dag.add_node("keeper", action=lambda: 1)
    dag.add_node("removable", action=lambda: 2)
    scheduler.next_wave()
    dag.remove_node("removable")
    self.assertNotIn("removable", scheduler.get_all_states())
# FAILED: AssertionError: 'removable' unexpectedly found in {'keeper': <NodeState.READY>, 'removable': <NodeState.READY>}
```

---

### Theoretical Analysis: Why Single-Model Cleanroom Missed These Defects

The discovery that a single-model Cleanroom run greenlit three genuine defects provides profound insight into the mechanics of LLM-based software verification.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│               INFORMATION CONFINEMENT vs. COGNITIVE MODEL CONFINEMENT                  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   TRADITIONAL SINGLE AGENT (I > 0)          CLEANROOM SINGLE-MODEL (I = 0, θ_1 = θ_2)  │
│   ┌──────────────────────────────────┐      ┌─────────────────┐      ┌───────────────┐ │
│   │           Joint Context          │      │ Synthesizer     │      │ Certifier     │ │
│   │                                  │      │ Model Weights θ │      │ Model Weights │ │
│   │   [Code] ◄──────► [Tests]        │      │ (W_lib Sandbox) │      │ (W_test)      │ │
│   │     ▲                │           │      └────────┬────────┘      └───────┬───────┘ │
│   │     └────────────────┘           │               │ Physical Barrier      │         │
│   │       Tautological Loop          │               │   (I = 0)             │         │
│   └──────────────────────────────────┘               ▼                       ▼         │
│     * Cheating & assertion mutation                  [ P_code ]             [ V_test ] │
│     * Shared working memory                          Both share the same Prior Bias:   │
│                                                      P(interpretation | spec text)     │
│                                                      ==> Coincident Blind Spots!       │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

#### A. The Limits of Physical Isolation ($\mathcal{I} = 0$) Under Identical Weights ($\theta_{\text{synth}} = \theta_{\text{cert}}$)

Cleanroom's double-blind isolation enforces an information-theoretic barrier:
$$\mathcal{I}(W_{\text{test}}; W_{\text{lib}}) = 0$$
The Certifier cannot read the Synthesizer's code, cannot inspect its variable names, and cannot modify assertions to match the Synthesizer's runtime behavior. This completely eliminates **intentional cheating** and **tautological self-affirmation**.

However, if both $W_{\text{lib}}$ and $W_{\text{test}}$ are driven by the same frozen model weights ($\theta$), they sample from identical probability distributions over semantic interpretations:
$$P(M \mid S, \theta)$$
where $S$ is the specification and $M$ is the mental model of system behaviors.

When an interface contract is slightly nuanced or multi-faceted:
1. **The Synthesizer** samples an implementation that addresses the most salient, canonical interpretation of the contract (the "happy path" or the most obvious failure mode, such as retry exhaustion).
2. **The Certifier**, prompted with the same specification text and governed by the same statistical priors, samples test cases for *that exact same salient interpretation*.
3. Because both agents share the same cognitive blind spot, neither agent conceives of the complementary edge case (e.g., action recovery on attempt 1, re-registration replacing edges, or post-init dynamic node removal).
4. The Certifier writes tests that certify the Synthesizer's incomplete implementation with 100% mathematical pass rates.

This creates a **Coincident Error**:
$$P\left(V_\theta(P_\theta) = \mathbf{PASS} \;\middle|\; V_{\text{oracle}}(P_\theta) = \mathbf{FAIL}\right) > 0$$

#### B. The Structural Coverage Illusion: Statement & Branch Reachability $\ne$ Permutation Coverage

Cleanroom recorded 95.0% statement coverage and 90.0% branch coverage on Qwen's library. This discrepancy exposes the fundamental flaw of relying exclusively on AST-based structural code coverage:

1. **The Branch Coverage Trap on Defect 1**:
   ```python
   except Exception as exc:
       caught_exc = exc
       if attempt > 0:           # <--- Line covered? YES. Branch covered? YES!
           retries_attempted += 1 # <--- Line covered? YES!
   ```
   When Qwen's test suite executed `test_run_retries_on_failure` (exhausting all 3 attempts):
   - On attempt 0: `attempt > 0` was `False` (false branch evaluated).
   - On attempt 1: `attempt > 0` was `True` (true branch evaluated, line executed).
   - On attempt 2: `attempt > 0` was `True` (true branch evaluated, line executed).
   **Coverage output**: Line 935 was executed 2 times. Both the `True` and `False` branches of `if attempt > 0` were fully covered. Statement coverage: 100%. Branch coverage: 100%. Yet the logic was completely broken for any action that recovered on attempt 1!

2. **The State-Space Permutation Blind Spot on Defect 2 and 3**:
   - `DAG.add_node` had 100% statement coverage because nodes were added in every test.
   - `WaveScheduler._sync_states` had 100% statement coverage because waves were scheduled in every test.
   - Structural coverage only records that code was executed; it does not measure whether the state-space transition graph $(\mathcal{S} \times \mathcal{A} \to \mathcal{S}')$ was explored across multi-action sequences (e.g. `add(A)` $\to$ `add(A, new_deps)` or `init_scheduler()` $\to$ `remove(B)` $\to$ `sync()`).

#### C. The Upstream Scenario Derivation Bottleneck

In `benchmarks/parts/dag_engine_lite/scenarios/dag_engine_lite.md`, the concrete scenarios written for the task included 7 distinct journeys. However, none walked an action that failed once and recovered on retry, none walked re-registering an existing node to modify dependencies, and none walked dynamic node removal after scheduler initialization. Because the scenario canvas contained these omissions, the formal contracts in `low/*.pyi` remained purely declarative docstrings without concrete operational walkthroughs.

---

### Why Foreign Models Did Not Share the Blind Spots

When independent models authored test suites from the identical `low/*.pyi` specification, their differing training distributions, inductive biases, and reasoning heuristics generated radically different adversarial tests:

| Model | Underlying Inductive Bias | Edge Case Prioritized in Test Suite |
| :--- | :--- | :--- |
| **DeepSeek-V3 / Flash** | Execution-trace simulation & loop invariants | *Retry Recovery Invariant*: Specifically created an action closure that tracks invocation count and raises an error on attempts 0 and 1, succeeding on attempt 2, then asserted `retries_attempted == 2`. |
| **Gemini 3.8 Flash** | Idempotency & dynamic reconfiguration | *Graph Mutation Invariants*: Tested that re-adding a node replaces prior dependencies, and that removing a node cleans up incident edges and scheduler state. |
| **Gemini 4 Argon** | Architectural contract robustness | *Failure Policy & Lifecycle Invariants*: Asserted rigorous scheduler-to-runner state consistency under mixed failure policies. |

Because their cognitive priors were uncorrelated with Qwen's cognitive priors:
$$\mathcal{I}(\text{Prior}_{\text{gemini}}; \text{Prior}_{\text{qwen}}) \approx 0$$
The cross-model differential pass rate plummeted, unmasking defects that homogeneous self-testing could never detect.

---

### Architectural Remedies: The Necessity of Pretense

This empirical finding demonstrates that **physical isolation alone is insufficient if agents share identical cognitive biases**. Pretense permanently closes this vulnerability through:
1. **Hypothesis State Machines**: Transition-space fuzzing replaces example-based static sequences with thousands of randomized action permutations ($S \times A \to S'$).
2. **Minimal Shrinking Traces**: Falsifications shrink to minimal 2-step counterexamples for instant blame attribution.
3. **Automatic Fake Synthesis**: Decouples inter-component dependencies so tests cannot mask partner desynchronizations.
4. **Pretense as an Equalizer**: Bridges the gap between single-model baselines and multi-agent Cleanroom pipelines.

---

## 3. Theoretical Architecture: Why Hypothesis State Machines?

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│             EXAMPLE-BASED TESTING vs. HYPOTHESIS STATE-MACHINE TESTING                 │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   A. EXAMPLE-BASED UNIT TEST (Current Cleanroom Certifier W_test)                       │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │ def test_scenario():                                                           │   │
│   │     dag.add_node("A") ──► dag.add_node("B") ──► dag.validate() ──► PASS        │   │
│   └────────────────────────────────────────────────────────────────────────────────┘   │
│     * Only tests the specific static sequence the LLM happened to conceive.           │
│     * High branch coverage, but misses interleavings, mutations, and recovery.         │
│                                                                                        │
│   B. HYPOTHESIS STATE MACHINE (RuleBasedStateMachine)                                  │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │ Rules: @rule(node_id, deps) def add_node(...)                                  │   │
│   │        @rule(node_id) def remove_node(...)                                     │   │
│   │        @rule() def next_wave(...)                                              │   │
│   │ Invariant: @invariant() def check_invariants(...)                              │   │
│   └────────────────────────────────────────────────────────────────────────────────┘   │
│     * Explores thousands of random operation sequences:                              │
│       add(A) ──► add(A, new_deps) ──► init_sched() ──► remove(A) ──► wave()            │
│     * Falsification: Invariant violated!                                               │
│     * Shrinking: Reduces 40-step failure to minimal 2-step reproducible counterexample.│
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Why Cheap Models Can Author State Machines
Smaller models (e.g. Qwen 35B) fail when asked to *imagine* obscure edge cases from an open-ended prompt. However, authoring a Hypothesis `RuleBasedStateMachine` does not require imagining edge cases:
- The model is instructed to map each method in `low/*.pyi` to a single `@rule` definition.
- The model copies the postconditions into `@invariant` methods.
- **Hypothesis's deterministic engine does the search**. The model does not need to predict the failure path; it only specifies the rules and the invariants.

---

## 4. Cleanroom Pipeline Integration: Author & Auditor Roles

### A. New Author Role: `property_test`
Cleanroom introduces an independent author role: **`property_test`**.
- **Input**: Low-Level Specifications (`low/*.pyi`, `low/*_impl.pyi`).
- **Workspace**: Isolated sandbox $W_{\text{prop}}$ under double-blind physical isolation ($\mathcal{I} = 0$) from $W_{\text{lib}}$.
- **Output Artifact**: `tests/<unit>_state_machine_test.py`.
- **Structural Template**:
  ```python
  from hypothesis.stateful import RuleBasedStateMachine, Bundle, rule, invariant
  import hypothesis.strategies as st

  class ModuleStateMachine(RuleBasedStateMachine):
      nodes = Bundle("nodes")

      @rule(target=nodes, node_id=st.text(min_size=1, max_size=5))
      def create_node(self, node_id): ...

      @rule(node_id=nodes, new_deps=st.sets(nodes))
      def re_register_node(self, node_id, new_deps): ...

      @invariant()
      def graph_acyclic_and_consistent(self): ...

  TestModule = ModuleStateMachine.TestCase
  TestModule.settings = hypothesis.settings(max_examples=100, stateful_step_count=30)
  ```

### B. Auditor Integration: Rolling into `qa` vs. `property_qa`
Rather than creating an additional orchestration barrier, Hypothesis execution is rolled directly into the existing **`qa`** arbiter role:
1. `qa` executes standard unit tests (`tests/<unit>_impl_test.py`).
2. If unit tests pass, `qa` executes property tests (`pytest tests/<unit>_state_machine_test.py`).
3. **Deterministic Termination**: The test runner enforces strict settings:
   - `max_examples=100`
   - `stateful_step_count=30`
   - `deadline=5000` (5 seconds per example)
   - Deterministic seed reproduction via `.hypothesis` database.

### C. Shrunk Counterexample as Minimal Blame Critique
When Hypothesis falsifies an invariant, its shrinking engine reduces the execution sequence to the minimal steps required to reproduce the failure.
For example, on Defect 2 (stale edge accumulation):
```
Falsifying example:
state = ModuleStateMachine()
v1 = state.create_node(node_id='a')
state.re_register_node(node_id='a', new_deps={'b'})
state.re_register_node(node_id='a', new_deps={'c'})
state.assert_dependencies_match()
AssertionError: 'b' unexpectedly in dependencies of 'a'
```
The `qa` auditor automatically captures this shrunk trace and feeds it directly into `bin/blame <culprit_file> "<shrunk_trace>"`. The Synthesizer receives an unambiguous, minimal 3-step reproduction without any conversational noise.

---

## 5. State Machines as Dual-Role Assets: Fakes and Test Drivers

In software testing, maintaining separate test harnesses, mock frameworks, and fake implementations leads to substantial code duplication and a well-known vulnerability: **Mock Drift** (where the fake behaves differently from the real implementation because the fake itself is unverified).

Because a state machine formalizes:
1. **Antecedents**: Guard preconditions determining legal transitions.
2. **Action**: The interface method invocation.
3. **Consequents**: The state mutation and postcondition assertions.

A state machine is naturally isomorphic to an **In-Memory Reference Model (Fake)**. In Cleanroom, state machines serve a dual operational role:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│               THE DUAL-ROLE STATE MACHINE ARCHITECTURE: DRIVER & FAKE                   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│                               Low-Level Specification                                  │
│                                    (low/*.pyi)                                         │
│                                         │                                              │
│                    ┌────────────────────┴────────────────────┐                         │
│                    ▼                                         ▼                         │
│        [ Reference State Model ]                  [ Production Synthesis ]             │
│        (Pure In-Memory State Machine)             (Optimized Concrete Realization)     │
│                    │                                         │                         │
│                    ├────────────────────┬────────────────────┤                         │
│                    │                    │                    │                         │
│                    ▼                    │                    ▼                         │
│       ┌────────────────────────┐        │        ┌────────────────────────┐            │
│       │ AS AN IN-MEMORY FAKE   │        │        │ AS A TEST DRIVER       │            │
│       │ Cleanroom parts import │        │        │ Hypothesis drives both │            │
│       │ the model to test      │        │        │ SUT and Fake in lock-  │            │
│       │ downstream consumers   │        │        │ step, checking parity: │            │
│       │ without heavy deps.    │        │        │ SUT(s, a) == Fake(s, a)│            │
│       └────────────────────────┘        │        └────────────────────────┘            │
│                                         │                    │                         │
│                                         ▼                    ▼                         │
│                              Zero Mock Drift!       Differential Parity!               │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### A. Calling Direction Inversion: Test Driver vs. In-Memory Fake

A fundamental insight of this dual architecture is that the **calling direction completely inverts** depending on whether the state machine is acting as a Test Driver or as a Fake:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        CALLING DIRECTION INVERSION TOPOLOGY                            │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   1. TEST DRIVER MODE (Outward Calling):                                               │
│   ┌───────────────┐        ┌──────────────────────┐        ┌───────────────────────┐   │
│   │ Test Harness  │ ─────► │ StateMachine Rule    │ ─────► │ Real Component (SUT)  │   │
│   │ (Hypothesis)  │        │ Checks Precondition  │        │ Executes Real Action  │   │
│   └───────────────┘        └──────────┬───────────┘        └───────────────────────┘   │
│                                       │ Updates Internal State & Asserts               │
│                                       ▼                                                │
│                                                                                        │
│   2. IN-MEMORY FAKE MODE (Inward Calling):                                             │
│   ┌───────────────┐        ┌──────────────────────┐        ┌───────────────────────┐   │
│   │ Consumer Code │ ─────► │ Fake Method Endpoint │ ─────► │ Selects Valid Rule    │   │
│   │ Under Test    │        │ (Implements .pyi)    │        │ & Returns Fake Value  │   │
│   └───────────────┘        └──────────────────────┘        └───────────────────────┘   │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

1. **Test Driver Mode (Outward Calling)**:
   - The test harness (Hypothesis or deterministic scenario runner) actively drives execution.
   - It picks a state machine rule whose antecedents (`@precondition`) are satisfied.
   - The rule invokes the method on the real component under test (`self.sut.method(...)`), and updates its internal state to reflect the transition.
2. **Fake Mode (Inward Calling)**:
   - The calling direction goes the other way around: downstream consumer code calls into the Fake (which implements the interface Protocol).
   - Preconditions are now used to **verify that the consumer is making a legal call** relative to the Fake's current lifecycle state.
   - The state mutation step inside the rule *is how the Fake models its behavior at all*.
   - **Multi-Transition Disambiguation in Fakes (The Zero-Ambiguity Invariant)**:
     In a rich API, multiple discrete transitions might map to the *same* interface method (e.g. `add_node` on a fresh node vs. `add_node` on an existing duplicate node; or `execute_tool` on success vs. failure).
     When consumer code calls that method on the Fake:
     - The Fake inspects its internal state and evaluates **all** candidate transitions bound to that method.
     - For each candidate transition, it evaluates the `@transition.require` block and the `@transition.arguments` recognizer block (testing against the concrete caller arguments). If arguments cannot validate, it moves to the next candidate transition.
     - **Zero Precedence**: There is no priority or fallback ordering. The Fake **continues checking all transitions** even after finding a match to guarantee that the transition match is unique.
     - **Outcome Invariants**:
       1. **If 0 transitions match**: The caller violated the API contract or attempted an illegal state transition. The Fake fails immediately with `NoMatchingTransitionError`.
       2. **If >1 transitions match**: The specification is ambiguous! The Fake **fails immediately with an `AmbiguousTransitionError`**. The fix requires the author to tighten transition constraints, add discriminative argument recognizers, or introduce additional seeding to eliminate the ambiguity.
       3. **If exactly 1 transition matches**: The Fake executes that transition, updates its internal state, and returns the result.

---

### B. Interface Segregation, Semantic Binding & Importing vs. Implementing

In modular software design, interfaces are segregated to decouple client components. Pretense formalizes two fundamentally different relationships between state machines: **Implementing** vs. **Importing**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│               IMPLEMENTING vs. IMPORTING STATE MACHINES IN PREFENSE                    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   1. IMPLEMENTING A STATE MACHINE (Realization / Subtyping / Semantic Binding):        │
│   • Relationship: Subclassing / Conformance (A_impl IS-A A_spec)                       │
│   • Example: DagEngineLiteImplStateMachine(DagEngineLiteStateMachine)                  │
│   • Purpose: Inherits interface transitions, replaces ungrounded/seeded behaviors with │
│     concrete domain logic, and verifies the real implementation against the contract.  │
│                                                                                        │
│   ──────────────────────────────────────────────────────────────────────────────────   │
│                                                                                        │
│   2. IMPORTING A STATE MACHINE (Composition / Collaborator Fakes / Seeding):           │
│   • Relationship: Object composition (A_sm HAS-A B_sm)                                 │
│   • Example: DagEngineLiteStateMachine imports StorageStateMachine                     │
│   • Purpose: B_sm compiles fake adapters (fake_storage = b_sm.as_fake(Storage))        │
│     injected into the SUT under test. Seeding B_sm is modeled as TRANSITIONS on A_sm!  │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

#### 1. Implementing Another State Machine (Realization / Semantic Binding)
An implementation state machine **implements** an interface state machine through class inheritance:
`class ComponentImplStateMachine(ComponentStateMachine): ...`

* **Conforms to Interface**: Inherits the public interface transitions declared on the interface state machine.
* **Semantic Binding**: Ties segregated interface contracts together. If `ToolManagerImpl` implements both `ToolInstaller` and `ToolExecutor`, its implementation state machine subclasses both interface machines:
  $$\text{Executor State} = f(\text{Installer State})$$
  It verifies that a tool installed via `install_tool` is dynamically executable via `execute_tool`, replacing static test seeds with real operational consistency.
* **Intra-Component Verification**: Verifies all concrete intra-component objects (`_impl.py`) in lockstep within an active lifecycle scope.

#### 2. Importing State Machines (Collaborators, Injected Fakes & Seeding Transitions)
When a component under test depends on external collaborator components (e.g. `Scheduler` depends on `DagStorage`), its state machine **imports** the collaborator's interface state machine:
`self.storage_sm = StorageStateMachine()`

* **Drives Injected Fakes**: The imported state machine provides the fake singletons injected into the SUT:
  `fake_storage = self.storage_sm.as_fake(DagStorage)`
* **Seeding Fakes as First-Class Transitions**: Perturbing, configuring, or injecting faults into the collaborator fake (e.g. `storage_sm.seed_storage_error(...)`) **must be modeled as transitions on the host state machine**:
  ```python
  @transition
  def seed_external_storage_error(
      self,
      ctx: TransitionContext[None, [str, str], None],
  ) -> None:
      ctx.arguments(generate=lambda: ("node_x", "Disk Full"))
      ctx.consequent(lambda res, node_id, err: (
          self.storage_sm.seed_node_error(node_id, error=err)
      ))
  ```
* **Why Seeding Must Be a Transition**: In Hypothesis stateful property fuzzing, transitions are the operations selected during random walks. If collaborator seeding were only static pre-test setup, Hypothesis could only fuzz static happy-path configurations. By making seeding a transition, **Hypothesis interleaves collaborator faults with SUT operations** (e.g. `schedule_node` $\to$ `seed_storage_error` $\to$ `retry_node` $\to$ `seed_storage_recovery`), verifying resilience and recovery dynamics automatically.

---

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│               INTERFACE SEGREGATION vs. IMPLEMENTATION SEMANTIC BINDING                │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   1. SEGREGATED INTERFACE STATE MACHINES (Isolated Contracts for Fakes):               │
│                                                                                        │
│   ToolInstallerStateMachine (Client A Fake):                                           │
│   - Interface method: install_tool(tool)                                               │
│   - Consequent State: tracks installed_tools. Zero execution mechanics!                │
│                                                                                        │
│   ToolExecutorStateMachine (Client B Fake):                                            │
│   - Interface method: execute_tool(name, params)                                       │
│   - Antecedent State: seeded_tools / seeded_responses (open configuration)             │
│   - Zero installation mechanics! Just returns seeded responses for tools.              │
│                                                                                        │
│   ──────────────────────────────────────────────────────────────────────────────────   │
│                                                                                        │
│   2. IMPLEMENTATION STATE MACHINE (Semantic Binding):                                  │
│                                                                                        │
│   ToolManagerStateMachine(ToolInstallerStateMachine, ToolExecutorStateMachine):       │
│   - Replaces seeded state with a PURE FUNCTION of installer state:                     │
│     seeded_tools = f(installed_tools)                                                  │
│   - Binds Semantics:                                                                   │
│     * Tool installed via Installer ──► Executable via Executor                         │
│     * Tool NOT installed          ──► Raises ToolNotFoundError                         │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

#### 1. Segregated Interface State Machines in Isolation
Each interface state machine models *only its own segregated contract*:
* **`ToolInstallerStateMachine` (Consequent State)**:
  - Consumed by clients that register tools (e.g. `PluginLoader`).
  - Operates on high-level `Tool` objects.
  - Its `installed_tools` attribute is a **consequent**: it accumulates tools as `install_tool` transitions occur. It knows nothing about wire details or execution.
* **`ToolExecutorStateMachine` (Seeded Antecedent State)**:
  - Consumed by clients that execute tools (e.g. `AgentLoop`).
  - Operates on wire details (tool names as strings, parameter dictionaries).
  - In isolation, its available tools and responses are **seeded** by client tests (`seed_tool(name)`, `seed_response(name, params, response)`). It knows nothing about registration or plugins.

#### 2. The Implementation State Machine: Replacing Seeds with Functional Binding
When a concrete component (`ToolManagerImpl`) implements both interfaces, its Pretense state machine extends both interface state machines and performs **semantic binding**:
* Instead of available tools and responses being seeded, **they become a pure function over the installer's `installed_tools`**:
  $$\text{Executor State} = f(\text{Installer State})$$
* The implementation state machine verifies that:
  1. A tool installed via `install_tool` can be executed via `execute_tool`.
  2. A tool that was never installed raises `ToolNotFoundError`.
  3. Execution outputs are derived from the real installed tool rather than arbitrary static seeds.

```python
# parts/tools/lib/tool_manager_machine.py
class ToolManagerStateMachine(ToolInstallerStateMachine, ToolExecutorStateMachine):
    def __init__(self) -> None:
        super().__init__()

    # SEMANTIC BINDING: Available tools are no longer seeded;
    # they are dynamically derived from the installer's installed_tools!
    @property
    def seeded_tools(self) -> set[str]:
        return set(self.installed_tools.keys())

    @transition
    @antecedent(lambda self, name, params: name in self.installed_tools)
    def execute_installed_tool(self, name: str, params: dict) -> ToolResponse:
        """Binding Rule 1: A tool that IS installed can be executed."""
        tool = self.installed_tools[name]
        return tool.execute(params)

    @transition
    @antecedent(lambda self, name, params: name not in self.installed_tools)
    def execute_uninstalled_tool_fails(self, name: str, params: dict) -> None:
        """Binding Rule 2: A tool that was NOT installed raises ToolNotFoundError."""
        with pytest.raises(ToolNotFoundError):
            self.sut.execute_tool(name, params)
```

#### 3. Multiple Interface Extension & Composition
Pretense explicitly supports components that implement multiple interfaces.
Because each interface state machine only defines transitions for its own methods, Python multiple inheritance (`class ComponentStateMachine(InterfaceAMachine, InterfaceBMachine)`) merges their transition pools cleanly.
Cross-cutting behavior is expressed via shared antecedents and invariants in the implementation state machine subclass.

---

### C. Outside vs. Inside the Implementation: Multi-Fake Synthesis & Surface Taxonomy

A core architectural principle in Pretense is that **outside the implementation under test, you only ever deal with State Machines**:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│             SPECIFICATION / TEST HARNESS PLANE vs. IMPLEMENTATION PLANE                │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   OUTSIDE THE IMPLEMENTATION (Test Harness & Client State Machine):                    │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │ * Only sees and composes State Machines!                                       │   │
│   │   self.tools_machine = ToolsComponentStateMachine()                            │   │
│   │                                                                                │   │
│   │ * State Queries: Asserts directly against the machine's public state:          │   │
│   │   assert expected_tool in self.tools_machine.installed_tools                   │   │
│   │                                                                                │   │
│   │ * Seeding: Directly configures environmental outcomes:                         │   │
│   │   self.tools_machine.seed_response("bash", {"cmd": "ls"}, output="ok")        │   │
│   └──────────────────────────────────────┬─────────────────────────────────────────┘   │
│                                          │                                             │
│                                          │ Multi-Fake Synthesis: .as_fake(Protocol)    │
│                                          ▼                                             │
│   INSIDE THE IMPLEMENTATION UNDER TEST (Concrete Python Realization):                  │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │ * Injected with Multiple Ephemeral Fake Adapters from the SAME State Machine:   │   │
│   │   fake_installer = self.tools_machine.as_fake(ToolInstaller)                   │   │
│   │   fake_executor  = self.tools_machine.as_fake(ToolExecutor)                    │   │
│   │                                                                                │   │
│   │ * Implementation calls fake_installer.install_tool(tool):                      │   │
│   │   [fake_installer] ──dispatches Object Method Transition──► tools_machine      │   │
│   │                                                                                │   │
│   │ * Implementation calls fake_executor.execute_tool("bash", params):             │   │
│   │   [fake_executor]  ──dispatches Object Method Transition──► tools_machine      │   │
│   └────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

#### 1. One Component State Machine Provides Multiple Fake Objects
In Cleanroom, an interface component (`low/<component>.pyi`) can define **multiple singletons and protocols**. For example:
- `parts/dag_engine_lite` defines `DAG`, `WaveScheduler`, and `DAGRunner`.
- `parts/tools` defines `ToolInstaller` and `ToolExecutor`.

Therefore, the **Interface State Machine operates at the Component level**, and can synthesize **multiple fake adapter objects**:
```python
fake_installer = tools_machine.as_fake(ToolInstaller)
fake_executor = tools_machine.as_fake(ToolExecutor)
```
- Each fake adapter satisfies its specific interface `Protocol`.
- **All synthesized fake adapters share the same underlying component state machine.**
- If `PluginLoaderImpl` calls `install_tool()` via `fake_installer`, the state is immediately reflected when another collaborator calls `execute_tool()` via `fake_executor`!

#### 2. The Three Surfaces of an Interface State Machine: Transitions vs. Queries vs. Seeding
Calling every method on a state machine a "transition" creates confusion, because queries and test-seeding methods are **not associated with an object method call on the fakes**. 

Pretense strictly delineates three distinct surfaces on an interface state machine:

| Surface Category | Associated with an Object Method? | Exposed on Fake Adapters? | Role in Pretense |
| :--- | :---: | :---: | :--- |
| **1. Object Method Transitions (`@transition`)** | **Yes** | **Yes** (Dispatched by Fakes) | The state mutations and return-value computations that correspond 1:1 with interface method calls on the synthesized fakes (e.g. `add_node()`, `install_tool()`, `execute_tool()`). |
| **2. Public State Queries (Consequents)** | **No** | **No** (Specification Plane only) | Public attributes and read-only query properties (e.g. `machine.installed_tools`, `machine.all_nodes`, `machine.get_state(id)`). Inspected by client state machines in assertions or invariants to verify side-effects without inspecting call logs. |
| **3. Seeding Methods (Configuration Mutators)** | **No** | **No** (Specification Plane only) | Public configuration hooks (e.g. `machine.seed_response(args, resp)`, `machine.seed_storage_error(id)`). Invoked by test drivers or client state machines to configure environmental conditions, inject simulated failures, or establish initial states. |

#### 3. Why This Taxonomy Matters
1. **Purity of Fake Adapters**:
   - The fake adapters injected into production implementations expose **strictly the interface methods declared in `low/*.pyi`**.
   - A production class cannot accidentally call `fake.seed_*()` or inspect `fake.installed_tools` because those methods are not on the interface protocol.
2. **Clarity in State Machine Driving**:
   - When Hypothesis or a unit test driver runs:
     - **Transitions** are the actions that advance the component under test.
     - **Queries** are the observations checked by `@invariant`s.
     - **Seeding Methods** are the chaos and configuration hooks that perturb the environment.

#### 4. Collaborator State Machine Importing & Seeding Transitions
When an implementation under test depends on external collaborator components, its State Machine imports the collaborator's Interface State Machine directly:

```python
class FooStateMachine(StateMachine[FooState]):
    def __init__(self, state: FooState | None = None, singletons: dict[type, Any] | None = None) -> None:
        super().__init__(state=state or FooState(), singletons=singletons)
        # Import collaborator interface state machine:
        self.bar_sm = BarStateMachine()

    # Seeding the imported collaborator fake is modeled as a first-class transition!
    @transition
    def seed_bar_outcome(
        self,
        ctx: TransitionContext[None, [str, BarResult], None],
    ) -> None:
        ctx.arguments(generate=lambda: ("action_x", BarResult(success=True)))
        ctx.consequent(lambda res, action, outcome: (
            self.bar_sm.seed_bar_outcome(action, outcome)
        ))

    @transition(Foo.do_foo)
    def do_foo_transition(
        self,
        ctx: TransitionContext[Foo, [str], None],
    ) -> None:
        ctx.arguments(generate=lambda: ("param_1",))
        ctx.returns(lambda param: None)
        ctx.consequent(lambda res, param: (
            self.state.executed_foos.append(param)
        ))
```

Under test:
```python
# 1. Instantiate state machine with real SUT singletons:
foo_sm = FooStateMachine(singletons={Foo: scope.get_singleton(Foo)})

# 2. Extract collaborator fake from the imported collaborator state machine:
bar_fake = foo_sm.bar_sm.as_fake(Bar)
registry.register_instance(bar_fake, keys=[Bar])

# 3. Hypothesis fuzzes both do_foo_transition and seed_bar_outcome!
# Interleaving seeding transitions with SUT actions exercises error handling dynamically.

# 4. Verify collaborator side-effects directly via imported state machine queries:
assert "action_x" in foo_sm.bar_sm.invoked_actions
```
- The production code only ever sees `bar_fake` conforming to `Bar` (`low/bar.pyi`).
- The test harness configures and observes collaborator state entirely through `foo_sm.bar_sm` without brittle mock introspection or call-recording wrappers.
- Seeding transitions ensure environmental chaos and failure recoveries are actively explored during stateful fuzz walks.

---

### D. Poly Types & Collaborator Execution (e.g. `tool_provider.py` & `ToolManager`)

Cleanroom specifies abstract collaborator extension points via `@poly_type`. A classic example is tool execution:
- An abstract poly type `Tool` defines `execute(params) -> ToolResult`.
- The singleton `ToolManager` provides `execute_tool(tool_name: str, params: dict) -> ToolResult`.
- **At the Interface Level**:
  `ToolManager.execute_tool` specifies that it resolves the installed tool matching `tool_name` and invokes its `execute` method with translated parameters.
  - *What the tool actually does* is completely open-ended and ungrounded at this level—it is up to external components implementing specific concrete tools.
- **Testing `ToolManager` with a Poly Type Test Spy**:
  To test `ToolManager`, the test installs a lightweight fake `Tool` (a test spy):
  ```python
  class SpyTool:
      def __init__(self):
          self.execution_count = 0
          self.last_params = None

      def execute(self, params):
          self.execution_count += 1
          self.last_params = params
          return ToolResult(success=True)
  ```
  The test driver verifies that `ToolManager` correctly routed to the tool:
  `assert spy_tool.execution_count == 1`. It makes no assertions about tool domain side-effects.

#### Poly Types as Protocols: The Singleton vs. Data Type Modality
`@poly_type` classes represent purely abstract protocols. Unlike singletons, they cannot be resolved via `get_singleton(...)` unless a concrete realization is registered or passed. When poly types are realized as data types rather than singletons, they bypass lifecycle tiers, which represents a recognized structural weakness in Cleanroom's approach so far (see Section 4.H.5 for the comprehensive analysis).

---

### E. The Dual-Use Dilemma: Simulation in Fakes vs. Assertion in Test Drivers

This leads to a crucial question in dual-use state machine design:
> *"If the state machine asserts that behavior happens, those assertions will fail when used as a Fake, because the Fake didn't do the real work!"*

#### The Anatomy of the Dilemma
Consider `ToolManager.execute_tool("bash", cmd)`:
1. **In Test Driver Mode (Outward Calling)**:
   The harness calls the real SUT (`sut.execute_tool(...)`).
   The SUT does the actual routing and calls the collaborator `spy_tool.execute(...)`.
   The state machine wants to assert:
   `assert spy_tool.execution_count == 1`
2. **In Fake Mode (Inward Calling)**:
   A downstream client calls `fake_tool_manager.execute_tool("bash", cmd)`.
   If the fake executed that same assertion (`assert spy_tool.execution_count == 1`), the test would **fail immediately**! Why? Because the fake *itself* must perform the routing to make `spy_tool.execution_count == 1`, rather than asserting that someone else did it!

#### The Cleanroom Resolution: Simulation vs. Parity Verification
The Cleanroom State Machine DSL cleanly separates the **Reference Simulation** from **Parity Assertions**:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                      SIMULATION vs. PARITY DISPATCH TOPOLOGY                           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   TRANSITION BODY (Pure Simulation):                                                   │
│   def execute_tool(self, name, params):                                                │
│       tool = self.installed_tools[name]                                               │
│       return tool.execute(params) # Actually invokes collaborator in Fake mode!         │
│                                                                                        │
│   1. WHEN EXECUTED AS A FAKE (Inward Calling):                                         │
│      Consumer calls Fake ──► Runs Simulation Body ──► Returns simulated result.        │
│      (Zero assertions fail; collaborator receives the simulated call!)                 │
│                                                                                        │
│   2. WHEN EXECUTED AS A TEST DRIVER (Outward Calling):                                 │
│      Harness calls SUT:                                                                │
│          sut_res = sut.execute_tool(name, params)                                      │
│      Harness runs Simulation:                                                          │
│          sim_res = fake.execute_tool(name, params)                                     │
│      Harness verifies Parity:                                                          │
│          assert sut_res == sim_res                                                     │
│          assert collaborator_spy.execution_count == 1                                  │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

1. **The Transition Body is an Executable Simulation**:
   The transition body does not assert that an external entity performed the action; it **performs the simulated action directly** (e.g. updating internal state, routing to the collaborator tool, and returning the simulated result).
2. **When running as a Fake**:
   The transition body runs directly. Because it actually calls the collaborator tool and returns the result, the downstream client gets the realistic behavior it expects.
3. **When running as a Test Driver**:
   Metaprogramming wraps the transition:
   - It invokes the concrete SUT method.
   - It runs the simulation on the reference model.
   - It checks **differential parity**: the SUT's returned value and effects on collaborators must match the simulation's returned value and effects!

---

### F. How Hypothesis Handles Dynamic Dataflow (And Why `Bundle` Fails)

A critical question arises in property-based stateful testing: **How does Hypothesis handle dynamic dataflow**—where the parameters of a downstream transition depend on values dynamically emitted or returned by the real component at runtime (as opposed to static inputs that can be chosen purely from the method signature)?

#### 1. The Append-Only Trap of `Bundle`
Hypothesis natively provides `Bundle` as a dynamic queue. When a component returns an identifier (e.g. `node_id`), a rule captures it via `target=bundle`:
```python
node_ids = Bundle("node_ids")

@rule(target=node_ids)
def create_node(self):
    return self.sut.add_node("A")

@rule(nid=node_ids)
def remove_node(self, nid):
    self.sut.remove_node(nid)
```

**Why `Bundle` Fails for Stateful Systems**:
* **Bundles are Strictly Append-Only**: Once an item is placed into a `Bundle`, **Hypothesis never removes it**. There is no `bundle.remove(item)`.
* **Broken State Transitions**: In real software, entities transition through lifecycles: `PENDING` $\to$ `READY` $\to$ `RUNNING` $\to$ `COMPLETED` $\to$ `CANCELLED`. If `Bundle` holds all entities forever:
  - When `remove_node(nid)` or `cancel_task(task_id)` is called, the entity is deleted or cancelled in the SUT, but **it remains in the `Bundle`**.
  - Subsequent rules drawing from the bundle will draw deleted or dead entities.
  - If you attempt to guard this using `hypothesis.assume(nid in self.live_nodes)`, Hypothesis repeatedly draws dead nodes, hits failed assumptions, and aborts the entire test run with:
    `HypothesisException: Unsatisfiable: Too many examples rejected`.

#### 2. The Superior Alternative: Dynamic State Tracking with `st.data()`
Because `Bundle` cannot handle deletion or state transitions, the correct stateful pattern is to track live entities in pure Python collections on `self` (`self.active_tasks`, `self.cancelled_tasks`) and use **`st.data()`**:

```python
class TaskStateMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.active_tasks = set()
        self.cancelled_tasks = set()

    # Step 1: Positive Transition (only eligible when active tasks exist!)
    @precondition(lambda self: len(self.active_tasks) > 0)
    @rule(data=st.data())
    def cancel_active_task(self, data):
        # Dynamically draws strictly from current active tasks:
        task_id = data.draw(st.sampled_from(sorted(self.active_tasks)))
        self.sut.cancel(task_id)
        self.active_tasks.remove(task_id)
        self.cancelled_tasks.add(task_id)

    # Step 2: Negative Transition (only eligible when cancelled tasks exist!)
    @precondition(lambda self: len(self.cancelled_tasks) > 0)
    @rule(data=st.data())
    def cancel_already_cancelled_task(self, data):
        # Dynamically draws strictly from cancelled tasks to verify error:
        task_id = data.draw(st.sampled_from(sorted(self.cancelled_tasks)))
        with pytest.raises(AlreadyCancelledError):
            self.sut.cancel(task_id)
```

**Why `st.data()` + `@precondition` Wins**:
1. **0% Assumption Rejection**: The `@precondition` ensures `cancel_active_task` is **never scheduled** when `self.active_tasks` is empty.
2. **Exact Lifecycle Partitioning**: Every drawn entity is guaranteed to be in the precise lifecycle phase required by the transition.
3. **Full Shrinking Support**: `data.draw()` is tightly integrated with Hypothesis's binary engine; any drawn value is minimized toward canonical edge cases on failure.

---

### G. The Signature Incompatibility Trap of Raw Hypothesis & Universal `st.data()` Compilation

While `st.data()` solves the fuzzer's dynamic state selection problem, **writing raw Hypothesis rules directly creates a fatal incompatibility with unit tests and fakes**:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                     THE RAW HYPOTHESIS SIGNATURE INCOMPATIBILITY                       │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   RAW HYPOTHESIS RULE:                                                                 │
│   @rule(data=st.data())                                                                │
│   def cancel_task(self, data: DataObject): ...                                         │
│                                                                                        │
│   1. INCOMPATIBLE WITH UNIT TESTS:                                                     │
│      A unit test wants to test an explicit scenario:                                   │
│          runner.cancel_task(task_id="task_1")  <--- FAILS!                             │
│      The rule signature requires a Hypothesis DataObject, NOT a task_id!               │
│                                                                                        │
│   2. INCOMPATIBLE WITH IN-MEMORY PROTOCOL FAKES:                                       │
│      The interface stub (low/task_runner.pyi) defines:                                 │
│          def cancel_task(self, task_id: str) -> None: ...                              │
│      The Hypothesis class CANNOT satisfy this Protocol because its signature           │
│      takes (self, data) instead of (self, task_id: str)!                               │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

Hypothesis **tightly couples parameter generation with state mutation**.

#### The Cleanroom Solution: Universal `st.data()` Compilation
In Cleanroom, the author writes the transition with its **pure domain signature**:
```python
@transition
@antecedent(lambda self, task_id: task_id in self.active_tasks)
def cancel_task(self, task_id: str) -> None:
    self.active_tasks.remove(task_id)
    self.cancelled_tasks.add(task_id)
```

Under the hood, Cleanroom's compiler targets **100% of Hypothesis parameters using `st.data()`**:
```python
# Automatically synthesized by the Cleanroom compiler:
@precondition(lambda self: len(self.spec.active_tasks) > 0)
@rule(data=st.data())
def fuzzer_cancel_task(self, data):
    # Compiler generates dynamic draw from antecedent set:
    task_id = data.draw(st.sampled_from(sorted(self.spec.active_tasks)))
    self.target_service.cancel_task(task_id)
    self.spec.cancel_task(task_id)
```

#### Why Universal `st.data()` Compilation Wins:
1. **Total Uniformity**: The compiler doesn't need to distinguish between "static strategy parameters" vs. "dynamic bundle parameters". **Every single parameter is drawn via `data.draw()`**.
2. **Complete Elimination of `Bundle`**: Avoids the append-only bug, prevents lifecycle leaks, and eliminates `assume()` draw rejections.
3. **Pure Signatures for the Author**:
   - In **Unit Tests**: Authors call `runner.cancel_task("task_1")` directly with literal values (<0.1ms deterministic replay).
   - In **Fakes**: Downstream clients call `fake.cancel_task("task_1")` directly (100% conforming to `low/<unit>.pyi`).
   - In **Hypothesis**: The compiler handles the `st.data()` drawing plumbing invisibly.

---

### H. Component Boundaries, Lifecycle Scoping (`enter_phase`), Symmetrical Fakes & Poly Types

A fundamental architectural principle of Cleanroom is that **the Component is the unit of specification and verification, not the individual class**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   CLEANROOM COMPONENT-LEVEL STATE MACHINE ARCHITECTURE                 │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   COMPONENT UNDER TEST (e.g. parts/dag_engine_lite):                                   │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │  REAL INTRA-COMPONENT OBJECTS (Tested Together in Lockstep):                   │   │
│   │  * DAG (Real)                                                                  │   │
│   │  * WaveScheduler (Real)                                                        │   │
│   │  * DAGRunner (Real)                                                            │   │
│   │  (No faking each other! They are co-designed and must stay in sync)            │   │
│   └──────────────────────────────────────┬─────────────────────────────────────────┘   │
│                                          │                                             │
│                                          │ Resolves via scope.get_singleton()          │
│                                          ▼                                             │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │  SYMMETRICAL COMPONENT FAKES (Smaller Interface State Machines):               │   │
│   │  * FakeDagStorage (Interface State Machine from parts/storage)                 │   │
│   │    - Interface Methods: get_node(), put_node() (State transitions)             │   │
│   │    - Seeding Methods:   seed_storage_failure(), seed_node_state()              │   │
│   └────────────────────────────────────────────────────────────────────────────────┘   │
│                                          ▲                                             │
│                                          │ Seeding Delegation                          │
│   ┌──────────────────────────────────────┴─────────────────────────────────────────┐   │
│   │  COMPONENT TEST DRIVER (Outer State Machine):                                  │   │
│   │  * Drives real intra-component methods: add_node(), run_batch()                │   │
│   │  * Seeding Transitions: delegate directly to FakeDagStorage.seed_*()           │   │
│   └────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

#### 1. Components as Systems of Objects (Intra-Component vs. Inter-Component)
In real software systems, critical defects rarely occur in isolated, stateless functions; they emerge from the dynamic interactions and synchronization between collaborating objects:
* **Intra-Component Real Objects (Zero Internal Faking)**:
  All objects defined within the same component (`low/<name>.pyi` $\to$ `lib/<name>_impl.py`) are **real and tested together in lockstep**. For example, in `parts/dag_engine_lite`, `DAG`, `WaveScheduler`, and `DAGRunner` collaborate directly. We never fake `DAG` when testing `WaveScheduler`, nor fake `WaveScheduler` when testing `DAGRunner`. Testing individual classes in isolation with artificial mocks creates fragile test suites that miss intra-component contract drift and synchronization defects (such as Defect 3 in our benchmarks, where `DAG` and `WaveScheduler` desynchronized).
* **Inter-Component Collaborators (Faked at Component Interface)**:
  Fakes exist **strictly for singletons accessed from imported collaborator components** (e.g. `parts/storage`). External components are faked at their `.pyi` interface boundary.

#### 2. Lifecycle Scope Mechanics: `enter_phase` (Scoped) vs. `begin_phase` / `close` (Non-Scoped for State Machines)
A critical distinction in Cleanroom's runtime (`support.lib.lifecycle`) is between lexical context managers and open-ended lifecycle sessions:

1. **Scoped Testing (`enter_phase`)**:
   Designed for discrete, lexical unit test methods:
   ```python
   with enter_phase(target_tier, registry=test_registry) as scope:
       # All singleton resolutions, mutations, and actions happen inside this scope:
       runner = scope.get_singleton(DAGRunner)
       runner.run_batch()
   # UPON EXIT: The scope terminates. All singletons instantiated or mutated
   # in this phase tier are deterministically finalized and torn down!
   ```
   * *Lexical Lifespan*: Once the `with enter_phase(...)` block or lambda exits, the phase scope ends, and all singletons bound to that tier are discarded. Doing setup code inside an `enter_phase` block is undone once the scope block exits; state cannot be retained across executions without an active phase scope.

2. **Non-Scoped Testing (`begin_phase` & `scope.close()`)**:
   Designed specifically for multi-step stateful test fixtures, asynchronous sessions, and **State Machines**:
   ```python
   # 1. Start open-ended phase session:
   scope = begin_phase(target_tier, registry=test_registry)

   # 2. Step / Transition Execution:
   #    Use scope.activate() context manager during transitions to bind the ambient ContextVar
   #    so internal get_singleton() calls inside collaborators resolve against this scope:
   with scope.activate():
       runner = get_singleton(DAGRunner)
       runner.run_batch()

   # State persists across transitions in the same state machine run...

   # 3. Explicit Teardown when state machine finishes:
   scope.close() # Deterministically tears down singletons in LIFO order!
   ```
   * `begin_phase` creates and opens the `LifecycleScope`, executes module startup/initialization, and leaves the scope open across transitions.
   * `with scope.activate():` temporarily activates the scope for the duration of a transition, allowing ambient `get_singleton(...)` calls within constituent classes to resolve seamlessly.
   * `scope.close()` tears down all instantiated singletons in reverse order of creation (LIFO) and finalizes the phase.
   * This eliminates the need to hack context managers with manual `__enter__` / `__exit__` calls inside state machine harnesses.

#### 3. Architectural Symmetry: Interface State Machines as the Basis for Component Fakes
Pretense achieves complete architectural symmetry across the entire system:
* The component under test is driven by an implementation **Component State Machine**.
* Its external dependencies are modeled by **Interface State Machines**.
* But what is a Fake? **A Fake is simply a runtime adapter compiled from an Interface State Machine!**
* The interface specification of an external component (`low/<external>.pyi`) has an executable Interface State Machine modeling that external component's interface protocol, invariants, and legal transitions. When needed by an implementation under test, `interface_machine.as_fake()` compiles an ephemeral adapter that implements the protocol and forwards calls into the state machine.

#### 4. Object Method Transitions vs. State Queries vs. Seeding Delegation
As established in the surface taxonomy, an interface state machine cleanly separates object methods from test configuration and query hooks:
1. **Object Method Transitions (`@transition`)**:
   - Mapped 1:1 with methods declared in `low/<external>.pyi` (e.g. `get_node(id)`, `write_record(rec)`).
   - In the state machine, these methods are implemented via transitions. When the implementation under test calls the fake adapter, the adapter dispatches to the state machine, which evaluates transition antecedents, mutates its internal state model, and returns simulated results matching the interface contract.
2. **Public State Queries (Consequent State Observables)**:
   - Attributes or read properties (e.g. `storage_machine.persisted_nodes`) queried directly by the test harness or client state machine to assert side-effects.
3. **Seeding Methods (Test Configuration Mutators) & Seeding Delegation**:
   - Direct configuration methods on the state machine (e.g. `storage_machine.seed_node(id, data)`, `worker_machine.seed_failure(task_id)`).
   - When the test driver's state machine drives the component under test, it frequently needs to simulate environmental conditions or pre-populate collaborator state.
   - The test driver does **not** reach into private data structures or mutate ambient globals.
   - Instead, the outer state machine has **seeding transitions that delegate directly to the public seeding methods of the imported state machine**:
     ```python
     @transition
     def seed_external_storage_error(self, node_id: str):
         # Delegates directly to the imported state machine's public seeding API:
         self.storage_machine.seed_node_error(node_id, error="Disk Full")
     ```
   - This preserves perfect architectural encapsulation: the outer component drives its own real objects in lockstep, and manipulates collaborator environments strictly through the imported state machine's public seeding API.

#### 5. Poly Types: Abstract Protocols vs. Singletons & The Data Type Weakness
Polymorphic types (`@poly_type`) present a unique architectural challenge:
* **Pure Abstract Protocols**: A `@poly_type` class (e.g. `Tool`, `Plugin`, `Filter`) is an abstract protocol, not a singleton. It has no lifecycle tier and cannot be resolved on demand via `get_singleton(Key)` unless a concrete realization is registered or passed.
* **Two Realization Modalities**:
  1. *Realized by a Singleton*: A singleton class implements the poly type protocol and is registered in a lifecycle tier (e.g. `BashToolImpl(Tool, Singleton)`). This integrates smoothly with `LifecycleRegistry`.
  2. *Realized as a Data Type / Value Object*: An ad-hoc data class or record implements the poly type protocol (e.g. lightweight parameter objects or closure-like handlers).
* **The Structural Weakness of Poly Types as Data Types**:
  Using data types to implement poly types rather than singletons represents an identified architectural weakness in Cleanroom's approach so far:
  - Data types bypass the `LifecycleRegistry` entirely.
  - They lack lifecycle phase scoping, teardown hooks, and automatic dependency injection.
  - They must be constructed ad-hoc and passed manually down call chains, creating plumbing friction and breaking the uniform singleton lifecycle model.
* **Handling Poly Types in Component State Machines**:
  - In component state machines, poly types consumed by the component are supplied via lightweight **Test Spies** (or mock protocol implementations) that conform strictly to the `@poly_type` protocol (as shown in Section 4.D).
  - When an imported collaborator fake produces or consumes poly types, the collaborator fake's state machine generates or seeds fake poly type instances.
  - In Hypothesis fuzzing, strategies draw from a collection of compliant test spy instances to exercise polymorphic dispatch across varying parameter configurations.

#### 6. End-to-End Component State Machine Example
Here is the complete pattern uniting component-level real objects, open-ended lifecycle management (`begin_phase` & `scope.close()`), imported interface state machines, and seeding delegation:

```python
from support.lib.lifecycle import LifecycleRegistry, begin_phase, system, get_singleton
from cleanroom.state_machine import StateMachine, transition, invariant, antecedent
from parts.dag_engine_lite.lib.dag import DAG
from parts.dag_engine_lite.lib.wave_scheduler import WaveScheduler
from parts.dag_engine_lite.lib.dag_runner import DAGRunner
from parts.dag_engine_lite.lib import dag_engine_tier, __initialize__
from parts.storage.lib.dag_storage import DagStorage
from parts.storage.support.dag_storage_machine import DagStorageStateMachine  # Interface state machine!


class DAGEngineComponentStateMachine(StateMachine):
    def __init__(self) -> None:
        super().__init__()
        # 1. Initialize isolated LifecycleRegistry for this test run:
        self.registry = LifecycleRegistry()
        __initialize__(self.registry)  # Registers real DAG, WaveScheduler, DAGRunner

        # 2. Compile Ephemeral Fake Adapter from Imported State Machine:
        self.storage_machine = DagStorageStateMachine()
        self.registry.register_instance(
            self.storage_machine.as_fake(),
            keys=[DagStorage],
            tier=dag_engine_tier,
        )

        # 3. Begin open lifecycle phase session (non-scoped, persists across transitions):
        self.scope = begin_phase(dag_engine_tier, registry=self.registry)

        # 4. Resolve real intra-component singletons from the scope:
        self.dag = self.scope.get_singleton(DAG)
        self.scheduler = self.scope.get_singleton(WaveScheduler)
        self.runner = self.scope.get_singleton(DAGRunner)

        # 5. Component Abstract Reference State:
        self.nodes: set[str] = set()

    def teardown(self) -> None:
        # Deterministically tears down and finalizes all singletons in LIFO order:
        self.scope.close()

    # --- INTRA-COMPONENT REAL TRANSITIONS ---
    @transition
    @antecedent(lambda self, node_id, deps: node_id not in self.nodes)
    def add_node(self, node_id: str, deps: set[str]) -> None:
        # Drives real DAG in lockstep with reference state:
        with self.scope.activate():
            self.dag.add_node(node_id, deps)
            self.nodes.add(node_id)

    @transition
    @antecedent(lambda self: len(self.nodes) > 0)
    def run_next_wave(self) -> None:
        # Drives real Runner (which internally coordinates real Scheduler and Fake Storage):
        with self.scope.activate():
            self.runner.run_batch()

    # --- SEEDING DELEGATION TRANSITIONS ---
    @transition
    def seed_storage_outage(self, node_id: str) -> None:
        # Seeding transition delegates directly to the imported state machine's seeding API:
        self.storage_machine.seed_node_error(node_id, error="Disk Full")

    # --- INTRA-COMPONENT INVARIANTS ---
    @invariant
    def internal_state_in_sync(self) -> None:
        # Verifies mutual cohesion across real collaborating intra-component singletons!
        with self.scope.activate():
            assert self.scheduler.all_known_nodes() == self.dag.all_nodes()
```

#### Why Component-Level Lifecycle Testing Wins:
1. **True System-Level Fidelity**: Real objects within the component are exercised together, eliminating the artificial isolation that masks integration bugs.
2. **Zero Constructor Plumbing**: Objects resolve dependencies via `scope.get_singleton(...)`, adhering to Cleanroom's strict zero-injection constructor rule.
3. **Symmetrical Composition**: Fakes are themselves state machines, ensuring consistent modeling and enabling seamless seeding delegation.
4. **Guaranteed Reset Between Runs**: Every Hypothesis test run executes within an isolated lifecycle scope (via `begin_phase` + `scope.close()` or `enter_phase`), guaranteeing zero state leakage across thousands of fuzzing iterations.

---

### I. Eliminating Mock Drift
In conventional software engineering, fakes and mocks frequently drift out of sync with production code because they are unverified. Under this dual architecture:
1. The **Fake IS the reference oracle** used to verify the real production library under thousands of randomized Hypothesis iterations.
2. If the Fake's logic disagrees with the production contract, the differential test fails immediately.
3. Therefore, the Fake is **empirically proven to match the production implementation**, guaranteeing that downstream Cleanroom parts consuming the Fake are testing against an exact, certified behavioral model.

---

### J. Hypothesis Shrinking Invariants: Why Shrinking Guarantees True Defects

A natural question when delegating test generation and minimization to an external library is: **Does Hypothesis ensure that the bug still exists in its shrunken examples?**

The answer is **yes, unconditionally, by mathematical construction**:
1. **The Conjecture Engine Core**: Hypothesis does not shrink at the AST or test-code level. Under the hood, Hypothesis generates inputs from an abstract byte stream managed by its engine (`conjecture`).
2. **Re-Execution Verification Loop**: When Hypothesis discovers an input or transition sequence of length $N$ that causes an invariant or assertion to fail:
   - It enters a deterministic shrinking loop.
   - It tries deleting steps, replacing complex values with simpler ones (e.g. empty strings, zeros, smaller sets), and merging operations.
   - **Crucially: for every candidate reduction, Hypothesis re-executes the candidate sequence directly against the SUT.**
3. **The Same-Exception Invariant & Defect Drift Prevention**:
   * *Question*: If a candidate reduction respects transition preconditions but raises a *different* error (e.g., an incidental `KeyError` or unexpected exception), how is this not just another bug?
   * *Answer*: It **is** often another bug (or a hole in the specification's preconditions). However, Hypothesis's shrinking engine enforces **Defect Invariance** to prevent **Defect Drift**:
     - When minimizing a specific failure (e.g. `AssertionError: Stale edges retained`), the reducer's objective is to isolate the *minimal reproducing trace for that specific defect*.
     - If the reducer accepted any candidate that threw *any* exception, the shrink process would immediately "swerve" toward trivial, early-exit crashes (e.g. `IndexError` on empty collection or `KeyError`), completely losing the subtle, deep defect you were trying to diagnose!
     - Therefore, during minimization of Defect A, candidate reductions that trigger a different error are rejected for *that* shrink path.
     - However, Hypothesis does **not** discard the newly discovered error: it records the failing input into its internal example database (`.hypothesis`), allowing it to be surfaced and minimized independently as its own distinct defect in subsequent passes.
4. **Outcome**: The final counterexample presented to the developer or coordinator is guaranteed to be a valid, minimal, 100% reproducible execution path on the actual production code.

#### 1. Synthesizing Deterministic Unit Tests from Shrunken Traces

A major breakthrough of Pretense's named transition architecture is that **counterexamples are automatically compiled into standalone unit tests**:

1. **Seeding as State Machine Transitions**:
   - To Hypothesis, exploring the state space requires exercising both object method calls AND environmental configurations (e.g. simulating a tool failure, injecting a timeout, or pre-populating mock data).
   - Therefore, seeding methods are registered as **Seeding Transitions** on the State Machine Interface.
   - Crucially, seeding methods live exclusively on the State Machine Plane—they do **not** pollute the low-level production interface stubs (`low/*.pyi`).
2. **The Trace as an Ordered Sequence of Named Transitions**:
   - Because every transition (both object method transitions and seeding transitions) is declared with an explicit identifier (`@proto.transition(...) def name(): pass`), Hypothesis's shrunken failure trace is simply an ordered list of named calls and arguments:
     ```
     Step 1: sm.seed_tool_outcome("bash", ToolResult(success=False))
     Step 2: dag.add_node("A", set())
     Step 3: scheduler.next_wave() -> Crash!
     ```
3. **Automated Unit Test Code Generation**:
   - Pretense inspects the minimized trace and synthesizes a pure, zero-dependency Python unit test:
     ```python
     def test_reproduce_shrunken_defect_dag_desync() -> None:
         sm = DagEngineLiteStateMachine()
         dag = sm.as_fake(DAG)
         scheduler = sm.as_fake(WaveScheduler)
         
         # Replay minimized trace:
         dag.add_node("A", set())
         dag.add_node("B", {"A"})
         wave = scheduler.next_wave()
         assert wave == ["A"], f"Expected ['A'], got {wave}"
     ```
   - **Properties of the Synthesized Test**:
     - Runs in $<0.1\text{ms}$ (instantaneous, no fuzzing loop).
     - 100% deterministic (replays the exact shrunken counterexample).
     - Directly injects into Cleanroom coordinator blame critiques (`bin/blame <culprit_file> "<critique with synthesized test>"`), giving downstream role workers an immediate failing regression test to satisfy.

---

### K. Declarative Requirements vs. Post-Dispatch Imperative Checks

Why make requirements declarative via `@transition.require` rather than an imperative `require()` / `assume()` inside the body?

#### 1. Generation vs. Post-Dispatch Rejection (The Sampling Collapse Problem)
- If preconditions are evaluated *inside* the function body via an imperative `require()` (equivalent to Hypothesis's `assume()`):
  - In a state machine with 20 rules, Hypothesis or the driver randomly selects an arbitrary rule (e.g., `execute_wave`).
  - It enters the function and hits `if not self.is_running: raise UnsatisfiedAssumption`.
  - If a rule is only valid 10% of the time, 90% of random step selections are aborted.
  - After a small number of consecutive rejections, Hypothesis halts with:
    `HypothesisException: Could not satisfy assumption` or `Unsatisfiable: Too many examples rejected`.
- With **declarative `@transition.require`**:
  - Before picking which transition to fire, the engine evaluates the requirements of candidate transitions against the current state.
  - The selection pool is dynamically filtered to **only transitions that are currently legal to execute**.
  - Rejection rate is **0%**. Every drawn step advances the test.

#### 2. The Generator-Recognizer Dualism
Declarative requirements formalize the dual relationship between test drivers and fakes:
- **In Test Driver / Fuzzer Mode (Generator)**:
  - Declarative `@transition.require(predicate)` filters *which* transitions can be generated given current state.
- **In Fake Mode (Recognizer / Protocol Implementation)**:
  - Downstream consumers call inward with concrete arguments.
  - Declarative requirements act as **recognizers**: they determine whether this transition matches the incoming call before executing state mutations.

---

### L. The Bidirectional Argument Recognizer / Generator (`NotBound`)

In stateful systems, method arguments are deeply interdependent (e.g., `deps` must be a subset of existing nodes in `state`, and `deps` cannot contain `node_id`). Defining arguments across disconnected individual decorators introduces invalid combinations. Pretense unifies argument handling into a **single joint recognizer / generator function** per transition.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│             BIDIRECTIONAL ARGUMENT RECOGNIZER / GENERATOR (NotBound)                    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   Incoming Call:  args_fn(state, arg1, arg2, ...)                                      │
│                                │                                                       │
│             ┌──────────────────┴──────────────────┐                                    │
│             ▼                                     ▼                                    │
│   Args == NotBound?                     Args are Concrete Values?                      │
│   (GENERATION MODE:                     (RECOGNITION MODE:                             │
│    Fuzzing / Simulation)                 Fake Ingestion / Replay)                      │
│             │                                     │                                    │
│             ▼                                     ▼                                    │
│   Synthesize valid parameters           Validate values satisfy contract?              │
│   from current state.                             │                                    │
│             │                            ┌────────┴────────┐                           │
│             │                            ▼                 ▼                           │
│             │                          Valid?           Invalid?                       │
│             │                           (Yes)             (No)                         │
│             │                            │                 │                           │
│             ▼                            ▼                 ▼                           │
│   Return (arg1, arg2, ...)      Return (arg1, ...)    Return None (Rejection)          │
│   to provide()                  to provide()          -> Try next candidate transition │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

#### 1. The `NotBound` Sentinel & Execution Modes
Pretense introduces a singleton sentinel `NotBound`:
1. **Generative Mode (Fuzzing / Simulation / Test Exploration)**:
   - When the test engine or state machine runner wants to execute a transition, it passes `NotBound` for arguments.
   - The argument function detects `arg is NotBound` and synthesizes valid, mutually consistent parameter values from `state`.
2. **Recognition Mode (Fake Adapter / Ingestion)**:
   - Downstream code calls the fake interface method: `fake.add_node("task_1", deps={"task_0"})`.
   - The concrete values are passed into candidate transitions' argument recognizers.
   - If the arguments violate the transition's domain (e.g. `"task_1"` already exists in `state.nodes`), the function returns `None` (rejection).
   - The Fake can then evaluate alternative candidate transitions bound to the same interface method (e.g. `add_duplicate_node`) or raise a contract error.
3. **Partial Binding**:
   - A test can specify one argument concretely while leaving others unbound:
     `args_fn(state, node_id="root", deps=NotBound)`.
   - The function respects the bound `node_id` and synthesizes the missing `deps` from `state`.

#### 2. Composable Recognizers & `make_tup`
Rather than writing verbose boilerplate in every transition, Pretense provides composable recognizer/generator functions:

```python
# Individual preset recognizers / generators:
def choose_node_id(state: DAGState, node_id: str | NotBoundType) -> str | None:
    if node_id is NotBound:
        return f"node_{len(state.nodes)}"
    return node_id if node_id not in state.nodes else None

def choose_deps(state: DAGState, deps: set[str] | NotBoundType) -> set[str] | None:
    if deps is NotBound:
        return set()
    return deps if deps.issubset(state.nodes) else None

# Composed together via make_tup:
add_fresh_node.arguments(make_tup(choose_node_id, choose_deps))
```

Pretense state collections also provide built-in bidirectional helpers:
- `collection.get_in(val)`:
  - If `val is NotBound`: generates an element drawn from `collection`.
  - If `val in collection`: returns `val` (recognized).
  - If `val not in collection`: returns `None` (rejected).
- `collection.get_not_in(val, prefix="item_")`:
  - If `val is NotBound`: generates a fresh identifier not currently in `collection` (see Negative Membership Tiers below).
  - If `val not in collection`: returns `val` (recognized).
  - If `val in collection`: returns `None` (rejected duplicate).
- `collection.get_subset(val)`:
  - If `val is NotBound`: generates a valid subset of `collection`.
  - If `val.issubset(collection)`: returns `val` (recognized).
  - Otherwise: returns `None` (rejected dangling reference).

#### 3. Statistical Selection of Arguments and Return Values
Uniform random selection is rarely sufficient in real-world systems: tests need **skewed or weighted distributions** (e.g. 70% typical small inputs, 20% boundary values, 10% stress inputs; or favoring high-degree nodes in a DAG).

Pretense encapsulates Hypothesis's frequency and sampling primitives behind `choose_weighted`:
```python
def choose_batch_size(state: DAGState, size: int | NotBoundType) -> int | None:
    if size is NotBound:
        # 70% small batches (1-5), 20% medium (10-50), 10% stress (1000+)
        return choose_weighted(
            (0.70, lambda draw: draw.integers(1, 5)),
            (0.20, lambda draw: draw.integers(10, 50)),
            (0.10, lambda draw: draw.integers(1000, 5000)),
        )
    return size if size > 0 else None
```
- **Under Hypothesis**: `choose_weighted` uses `st.frequency(...)` via the dynamic draw hook. If a failure occurs at batch size `4218`, Hypothesis shrinks it to `1000`, then down to the minimal reproducing boundary.
- **Outside Hypothesis**: It falls back to standard weighted random selection (`random.choices`), keeping unit test replay instant (<0.01ms).

#### 4. Negative Membership Generation (`get_not_in` & The Four Tiers)
When testing negative membership (e.g. `add_fresh_node` where `node_id not in state.nodes`, or looking up non-existent keys), where do valid absent values come from?

Pretense structures negative generation into four distinct tiers:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                      NEGATIVE MEMBERSHIP GENERATION TIERS                              │
├────────────────────────┬──────────────────────────────────┬────────────────────────────┤
│ Tier                   │ Generation Technique             │ Bug Class Uncovered        │
├────────────────────────┼──────────────────────────────────┼────────────────────────────┤
│ 1. The "Graveyard"     │ Pick from items recently removed │ Resurrection bugs, stale   │
│    (Tombstone History) │ or deleted from the collection.  │ cache / dangling pointers. │
├────────────────────────┼──────────────────────────────────┼────────────────────────────┤
│ 2. Near-Miss Mutations │ Mutate an existing element       │ Case-folding, whitespace,  │
│    (Off-by-One/Typo)   │ ("node_1" -> "node_1 ", "Node_1")│ delimiter confusion.       │
├────────────────────────┼──────────────────────────────────┼────────────────────────────┤
│ 3. Open Universe       │ Draw arbitrary unicode / strings │ Buffer limits, bizarre     │
│    (Hypothesis Fuzz)   │ via st.text() filtered by not-in.│ characters, escapes.       │
├────────────────────────┼──────────────────────────────────┼────────────────────────────┤
│ 4. Deterministic Fresh │ Prefix + incrementing sequence   │ Clean happy-path fresh     │
│    (Sequential ID)     │ ("task_0", "task_1", ...)        │ additions (fast replay).   │
└────────────────────────┴──────────────────────────────────┴────────────────────────────┘
```

1. **Tier 1: The "Graveyard" (Recently Removed / Tombstones)**:
   In stateful systems, deleting an item and immediately re-adding or querying it is where bugs cluster (stale weak references, uncleaned reverse indices, partial deletions). Pretense collections (`PretenseSet`, `PretenseDict`) maintain a rolling ring buffer of deleted items (`_tombstones`). In fuzzing mode, `get_not_in` draws from recently removed tombstones with high probability to catch resurrection defects.
2. **Tier 2: Near-Miss Mutations (Adversarial Negatives)**:
   Takes existing members and introduces slight mutations (toggle case, append trailing whitespace, add suffix). This catches normalization flaws where the SUT assumes case-insensitivity or string trimming that the specification does not allow.
3. **Tier 3: Open Universe Fuzzing**:
   Hypothesis draws arbitrary strings from `st.text().filter(...)`. This exercises exotic UTF-8 edge cases, zero bytes, newline injections, and extreme lengths.
4. **Tier 4: Deterministic Sequential Fallback**:
   In fast unit tests and static scenario replays, it generates `f"{prefix}{idx}"` monotonically, executing in $<0.001\text{ms}$ with zero randomness.

#### 5. Hypothesis Integration: Dynamic Scope Context (`contextvars`)
**Question**: *Can we use these generator/recognizer lambdas directly in Hypothesis if we feed them `NotBound`? And does this pollute function signatures with `draw`?*

**Answer**: **Yes, with 100% preservation of Hypothesis's shrinking and reproducibility guarantees, and zero signature pollution via dynamic scoping.**

In Hypothesis, the `data` strategy (`@rule(data=st.data())`) provides a `DataObject` with a method `data.draw(strategy) -> T` (often referred to conceptually as a `DrawFn`). Calling `data.draw(...)` ensures that every generated input or choice originates from Hypothesis's underlying byte-stream engine (`conjecture`), enabling full counterexample shrinking and deterministic replay.

Rather than polluting every recognizer/generator signature with a `draw` parameter, Pretense places the active draw context in **dynamic scope** using Python's standard library `contextvars.ContextVar`:

```python
from contextvars import ContextVar
from typing import Any, Callable

# Dynamic scope context holding the active Hypothesis draw function:
_CURRENT_DRAW: ContextVar[Callable[..., Any] | None] = ContextVar(
    "_CURRENT_DRAW", default=None
)
```

##### How Dynamic Scope Executes in Practice:
1. **Zero Signature Pollution**:
   The argument lambdas and choosers maintain pure, clean signatures:
   ```python
   def choose_node_id(state: DAGState, node_id: str | NotBoundType) -> str | None: ...
   ```
2. **Context-Agnostic Collection Helpers**:
   Helpers inspect `_CURRENT_DRAW.get()` automatically:
   ```python
   class PretenseSet(set[T]):
       def get_in(self, val: T | NotBoundType) -> T | None:
           if val is NotBound:
               draw = _CURRENT_DRAW.get()
               if draw is not None:
                   # Running under Hypothesis: draw from conjecture engine!
                   return draw(st.sampled_from(list(self)))
               # Standalone / Fake fallback: fast deterministic selection
               return next(iter(self)) if self else None
           return val if val in self else None
   ```
3. **Hypothesis Runner Dispatch: Inner SUT Invocation & Parity Assertion**:
   When Pretense compiles the state machine to a Hypothesis `RuleBasedStateMachine`, the rule wrapper sets the dynamic scope around transition execution and exercises both the real implementation under test (`self.sut`) and the reference state machine model (`self.state`), asserting **differential parity**:
   > [!IMPORTANT]
   > **Generation Must Never Return `None`**: If a transition's requirements were satisfied, its argument generator **must** produce valid parameters when called with `NotBound`. Returning `None` in generation mode indicates a specification defect (e.g. contradictory preconditions or an unhandled edge-case in argument generation). The runner immediately crashes with an assertion error rather than silently skipping the step:
   ```python
   @rule(data=st.data())
   def step_transition(self, data: st.DataObject) -> None:
       token = _CURRENT_DRAW.set(data.draw)
       try:
           # 1. Generate valid, mutually consistent arguments from current state
           args = transition.arguments(self.state, self, NotBound, NotBound)
           assert args is not None, (
               f"Specification Defect: Transition '{transition.name}' passed requirements "
               f"but failed to generate valid arguments for state: {self.state}"
           )

           # 2. Invoke real method on the SUT directly via transition.target (unbound method)
           sut_exc: Exception | None = None
           sut_res: Any = None
           try:
               sut_res = transition.target(self.sut, *args)
           except Exception as e:
               sut_exc = e

           sut_outcome = Raised(sut_exc) if sut_exc is not None else Value(sut_res)

           # 3. If transition defines a return recognizer/generator, recognize the SUT's outcome
           if transition.return_fn is not None:
               recognized_outcome = transition.return_fn(self.state, self, *args, sut_outcome)
               assert recognized_outcome is not None, (
                   f"Return Contract Violation: SUT produced invalid outcome {sut_outcome!r} "
                   f"which was rejected by the returns recognizer for '{transition.name}'"
               )
               valid_outcome = recognized_outcome
           else:
               assert sut_exc is None, f"SUT raised unexpected exception: {sut_exc!r}"
               valid_outcome = Value(sut_res)

           # 4. If outcome is an exception, the operation aborted: provide() does NOT execute!
           if isinstance(valid_outcome, Raised):
               return # Operation aborted with expected domain error; state remains unmutated

           # 5. Invoke reference state model (provider verifies postconditions & mutates state)
           # Provider crashes (AssertionError) if postconditions or state invariants are violated!
           transition.provider(self.state, self, *args, valid_outcome.val)
       finally:
           _CURRENT_DRAW.reset(token)
   ```
4. **Outcome**:
   - In **Hypothesis Fuzzing**: Every `get_in`, `get_subset`, or `choose_*` draws from `conjecture`. Shrinking and replay work 100% reliably.
   - In **In-Memory Fakes**: `_CURRENT_DRAW` is `None`. Concrete incoming arguments are validated against state in $<0.01\text{ms}$.
   - In **Deterministic Unit Tests**: `_CURRENT_DRAW` is `None`. Unbound arguments fall back to fast deterministic generation without any Hypothesis dependency.
3. **Standalone Deterministic Execution**:
   In unit test static scenarios or fast local simulations, feeding `NotBound` without a draw hook uses fast deterministic generation (`next(iter(...))` or prefix counters), executing in $<0.1\text{ms}$ with zero external dependencies.

---

### M. The Pretense State-Machine DSL (Single-Method `TransitionContext` Architecture)

Pretense formalizes a class-based state machine architecture (`StateMachine[StateT]`):
1. **Single Decorated Method per Transition**: Each transition is declared as a single method inside the state machine class decorated with `@transition(TargetClass.method)`.
2. **Type-Parameterized Context (`ctx: TransitionContext[Target, P, R]`)**:
   - `Target`: The target singleton type (e.g. `DAG`, `WaveScheduler`). Enforces static type alignment with `Target.method` via Pyright.
   - `P`: Parameter specification (`ParamSpec`) matching the method's domain parameters.
   - `R`: Return type (`TypeVar`).
3. **Five Decoupled Lifecycle Blocks**:
   - `ctx.requires(lambda check: check(cond, "reason"))` (formerly `antecedent`): Evaluates reference model state (`self.state`) before arguments are drawn. Precondition governing legal transition firing. If `check` fails, the transition is **not ready to fire**.
   - `ctx.arguments(generate=lambda: tuple, recognize=lambda *args: bool | None)`: Bidirectional input binding. The `recognize` lambda receives domain arguments `*args: P`, keeping the reference model pure.
   - `ctx.returns(lambda *args: R | Outcome[R])`: Computes simulated return value or validates return outcome matching `R`.
   - `ctx.ensures(lambda res, target, check, *args: ...)`: **First-class postcondition verification (Mode B `check` pattern exclusively)**. Evaluated strictly during test execution against the real SUT (never during fake simulation). Receives the return value, the immediate singleton under test (`target`), and an assertion helper `check` (which also provides access to collaborating singletons via `check.get(OtherSingleton)`). If `check` fails, raises `AssertionError` (contract violation).
   - `ctx.update(lambda res, *args: None)` (formerly `consequent`): Applies reference model state mutations and bookkeeping to `self.state`.
   - `ctx.raises(exc_type, match=...)`: Shorthand for contracted error paths.
4. **Dual-Role Execution**:
   - **Under Test**: Initialized with real target objects (`objects={DAG: real_dag}`, `sut=instance`, or direct instance references). Underneath, the runner calls `real_dag.add_node(*args)` automatically, verifies `returns`, evaluates `ensures` against the concrete SUT, and updates `self.state`.
   - **As a Fake**: Synthesizes in-memory fakes (`fake_dag = sm.as_fake(DAG)`). Dispatched calls update `self.state` with zero mock drift across collaborating singletons. **`ensures` is omitted during fake execution.**
5. **Poly Types**: Polymorphic types without singletons are deferred to a subsequent design phase.

```
                              ┌────────────────────────────────────────┐
                              │       Pretense State Machine DSL       │
                              │    (class MySM(StateMachine[State]))   │
                              └───────────────────┬────────────────────┘
                                                  │
                  ┌───────────────────────────────┼───────────────────────────────┐
                  ▼                               ▼                               ▼
      ┌────────────────────────┐      ┌────────────────────────┐      ┌────────────────────────┐
      │        TARGET 1        │      │        TARGET 2        │      │        TARGET 3        │
      │   Unit Test Replay     │      │   In-Memory Fake       │      │   Hypothesis Fuzzer    │
      │                        │      │                        │      │                        │
      │ • Static scenario      │      │ • Inward calling       │      │ • Outward calling      │
      │   replay (<0.1ms)      │      │ • sm.as_fake(Protocol) │      │ • Adversarial fuzzing  │
      │ • 100% deterministic   │      │ • Disambiguates by     │      │ • Calls real singleton │
      │ • Direct scenario      │      │   recognize/antecedent │      │   underneath           │
      │   traceability         │      │ • Shared self.state    │      │ • Parity against spec  │
      └────────────────────────┘      └────────────────────────┘      └────────────────────────┘
```

#### DSL Syntax Example: Cleanroom DAG State Machine

```python
from pretense import StateMachine, TransitionContext, transition
from update_with_ai.parts.dag_engine_lite.low.dag_engine_lite import DAG, WaveScheduler

class DAGState:
    def __init__(self) -> None:
        self.nodes: set[str] = set()
        self.edges: dict[str, set[str]] = {}
        self.pending_nodes: set[str] = set()
        self.active_waves: list[list[str]] = []

class DAGStateMachine(StateMachine[DAGState]):
    state: DAGState

    def __init__(self, state: DAGState | None = None, singletons: dict[type, Any] | None = None) -> None:
        super().__init__(state=state or DAGState(), singletons=singletons)

    # =========================================================================
    # Transition 1: Add Fresh Node (Success Path on DAG singleton)
    # =========================================================================
    @transition(DAG.add_node)
    def add_fresh_node(self, ctx: TransitionContext[DAG, [str, set[str]], None]) -> None:
        # 1. Requires: pure state precondition using check (failing check = not ready to fire)
        ctx.requires(lambda check: check(len(self.state.nodes) < 1000, "DAG at capacity"))

        # 2. Arguments: lambdas receive domain arguments (node_id: str, deps: set[str])
        ctx.arguments(
            generate=lambda: (f"task_{len(self.state.nodes)}", set()),
            recognize=lambda node_id, deps: (
                node_id not in self.state.nodes and deps.issubset(self.state.nodes)
            ),
        )

        # 3. Returns: computes expected outcome R (None)
        ctx.returns(lambda node_id, deps: None)

        # 4. Ensures: verifies real SUT postconditions (omitted during fakes)
        # Receives (res, dag, check, node_id, deps); failing check = AssertionError
        ctx.ensures(lambda res, dag, check, node_id, deps: (
            check(dag.has_node(node_id), "Fresh node must be present in DAG"),
            check.equal(dag.get_dependencies(node_id), deps, "Dependencies must match"),
        ))

        # 5. Update: applies reference model state mutations
        ctx.update(lambda res, node_id, deps: (
            self.state.nodes.add(node_id),
            self.state.edges.setdefault(node_id, set()).update(deps),
            self.state.pending_nodes.add(node_id),
        ))

    # =========================================================================
    # Transition 2: Add Duplicate Node (Error Path expecting ValueError)
    # =========================================================================
    @transition(DAG.add_node)
    def add_duplicate_node(self, ctx: TransitionContext[DAG, [str, set[str]], None]) -> None:
        ctx.requires(lambda check: check(len(self.state.nodes) > 0, "Must have existing nodes"))

        ctx.arguments(
            generate=lambda: (next(iter(self.state.nodes)), set()),
            recognize=lambda node_id, deps: node_id in self.state.nodes,
        )

        # Expected error outcome: raises ValueError in Fake mode, verifies in Driver mode
        ctx.raises(ValueError, match="already exists")

    # =========================================================================
    # Transition 3: Schedule Wave (Collaborating WaveScheduler singleton)
    # =========================================================================
    @transition(WaveScheduler.schedule_next)
    def schedule_wave(self, ctx: TransitionContext[WaveScheduler, [], list[str]]) -> None:
        ctx.requires(lambda check: check(len(self.state.pending_nodes) > 0, "Must have pending nodes"))
        ctx.arguments(generate=lambda: ())
        ctx.returns(lambda: sorted(list(self.state.pending_nodes)))
        ctx.ensures(lambda wave, scheduler, check: (
            # scheduler is the immediate object under test;
            # cross-object access to DAG is available via check.get(DAG):
            check(len(wave) > 0, "Scheduled wave must not be empty"),
            check(all(check.get(DAG).has_node(n) for n in wave), "All wave nodes must exist in DAG"),
        ))
        ctx.update(lambda wave: (
            self.state.active_waves.append(wave),
            self.state.pending_nodes.difference_update(wave),
        ))

    # =========================================================================
    # Global Invariant: Dependencies Must Exist
    # =========================================================================
    def invariant_dependencies_exist(self) -> None:
        for node, deps in self.state.edges.items():
            for dep in deps:
                assert dep in self.state.nodes, f"Missing dependency {dep} for node {node}"
```

#### How the Three Targets Execute:

1. **Target 1: Deterministic Unit Test Runner (Static Scenarios)**
   - Used directly in `tests/*_test.py` to verify concrete scenarios from `scenarios/*.md`.
   - The test author calls transitions sequentially:
     ```python
     def test_scenario_reregistration(self) -> None:
         sm = DAGStateMachine()
         sm.dispatch(DAG.add_node, "A", set())
         sm.dispatch(DAG.add_node, "B", {"A"})
         sm.check_invariants()
     ```
   - Execution is instant (<0.1ms), fully deterministic, and directly traceable to contract slugs.

2. **Target 2: In-Memory Protocol Fake (for Downstream Consumer Parts)**
   - Synthesizes fake instances implementing interface Protocols:
     ```python
     sm = DAGStateMachine()
     fake_dag = sm.as_fake(DAG)
     fake_scheduler = sm.as_fake(WaveScheduler)

     # Downstream component calls into fake_dag:
     scheduler = Scheduler(dag=fake_dag)
     scheduler.register_task("A", [])
     ```
   - When consumer calls `fake_dag.add_node(node_id, deps)`:
     - The Fake inspects candidate transitions (`add_fresh_node`, `add_duplicate_node`).
     - It tests requirements (`ctx.requires()`) and evaluates `recognize(node_id, deps)`.
     - If `node_id` is fresh, `add_fresh_node` recognizes it. The Fake executes `returns` (yielding `None`), calls `update` to mutate `self.state`, and returns `None`. Note: `ensures` is explicitly omitted during fake execution.
     - If `node_id` already exists, `add_fresh_node` rejects, `add_duplicate_node` recognizes it, raises `ValueError`, propagating directly into the consumer's exception handler.
     - **Shared State**: When `fake_scheduler.schedule_next()` is called, it reads the updated `self.state` directly. Zero mock drift between collaborating singletons!

3. **Target 3: Hypothesis `RuleBasedStateMachine` (Adversarial Parity & Postcondition Fuzzing)**
   - Initialized with real SUT objects:
     ```python
     sm = DAGStateMachine(objects={
         DAG: scope.get_singleton(DAG),
         WaveScheduler: scope.get_singleton(WaveScheduler),
     })
     TestDAGProperty = sm.to_hypothesis_test_case(settings=hypothesis.settings(max_examples=100))
     ```
   - During each fuzz step:
     - Hypothesis checks `requires()` and generates inputs via `generate()`.
     - Pretense resolves the target object for the transition class (`DAG`) and calls `real_dag.add_node(*args)` underneath.
     - Pretense verifies differential parity between real return value and `returns(*args)`.
     - Pretense evaluates `ensures(res, target, check, *args)` against the real SUT, verifying behavioral postconditions across both immediate and collaborating objects on every random walk step!
     - Pretense executes `update(res, *args)` on `sm.state`.
     - State machine invariants are verified.
   - Hypothesis drives thousands of interleaved transitions, actively verifying postconditions across complex operation permutations and shrinking any discovered failure into a minimal trace.

---

### N. The Behavioral Envelope Principle: Dynamic Dataflow in Fakes

Does it make sense to faithfully model deep dynamic dataflow in a Fake?

**No. In fact, attempting to faithfully model dynamic dataflow in an interface fake is fundamentally impossible by architectural construction.**

In Cleanroom, an interface component (`<unit>.pyi`) deliberately leaves concrete execution mechanics and environmental bindings **ungrounded**. The interface author (and therefore the interface fake) does not know:
- Where configuration files live on disk (which belongs in `_ext` boundary specifications).
- What execution harness, subprocess runner, or container runtime will execute operations.
- How complex domain algorithms will solve constraints.

Therefore, an interface fake could not simulate the production implementation even if it wanted to: **the required grounding information does not exist at the interface level.** The fake is strictly bounded by the epistemic contract of the interface.

#### 1. What Clients Actually Need: Equivalence Classes
A downstream client component (e.g. `AgentLoopImpl` or `DAGRunnerImpl`) consuming `ToolManager` does not care *how* `ToolManager` resolves tools or computes results. The client only branches on the **behavioral envelope**—the discrete equivalence classes of dynamic outputs that exercise its own control flow:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        THE BEHAVIORAL ENVELOPE OF A FAKE                               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   Real SUT (ToolManagerImpl):                                                          │
│   [ Resolves tool ] ──► [ Validates schema ] ──► [ Spawns subprocess ] ──► Computes    │
│                                                                                        │
│   Fake (FakeToolManager):                                                              │
│   ┌────────────────────────────────────────────────────────────────────────────────┐   │
│   │ Outcome A: Success(output="mock_data")   ──► Exercises Client Happy Path       │   │
│   │ Outcome B: Failure(error="tool_crashed") ──► Exercises Client Error / Retry    │   │
│   │ Outcome C: Exception(ToolNotFoundError)  ──► Exercises Client Abort Logic      │   │
│   └────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

The client's implementation only has three control branches:
1. What does the client do when the tool **succeeds**?
2. What does the client do when the tool **fails**?
3. What does the client do when the tool **raises an exception or times out**?

The Fake does not need to compute *why* a tool succeeded or failed. It only needs to be able to **emit those outcome classes** so the client's branches can be exercised.

#### 2. Epistemic Incompleteness: Keeping Interfaces Ungrounded
This confirms the core design principle of keeping interface specifications ungrounded:
- In `low/tool_manager.pyi`, the interface declares `execute_tool(name: str, params: dict) -> ToolResult`.
- It guarantees that `ToolResult` contains either `success == True` or `success == False`.
- It intentionally leaves the execution environment ungrounded: clients have no business knowing whether tools run in Docker, subprocesses, or in-memory functions.
- Because the interface is epistemically incomplete regarding execution details, the Interface State Machine (the Fake) models only what is known: the static protocol (e.g. tools must be registered before execution) and simple, seedable outcome transitions (`execute_tool_success`, `execute_tool_failure`).

#### 3. Seeded Outcomes Over Computed Semantics
In client unit tests, dynamic dataflow in the Fake is **configured or seeded**, not computed:
```python
def test_agent_loop_retries_on_tool_failure(self):
    fake_tools = ToolManagerSpec.as_fake()
    fake_tools.configure_outcome("bash", ToolResult(success=False, error="exit code 1"))

    loop = AgentLoop(tools=fake_tools)
    report = loop.step()
    assert report.retries_attempted == 1
```

By decoupling the Fake from real dynamic execution:
1. **Zero Fragility**: The Fake never fails due to OS quirks, filesystems, or subprocess deadlocks.
2. **Minimal LLM Burden**: Cheap models don't need to generate complex mock engines. They only define the static state transitions and seedable outcome variants.
3. **Deterministic Exhaustion**: Client unit tests can deterministically drive every failure and recovery branch in <0.1ms.

---

### O. Empirical Survey of Cleanroom Interfaces (`update_with_ai/parts/*/low`)

To validate this design against production Cleanroom components, we surveyed the actual low-level interface stubs (`low/*.pyi`) across `update_with_ai/parts/`. The analysis reveals a consistent pattern: **Cleanroom interfaces ground static dataflow completely while systematically leaving dynamic dataflow ungrounded.**

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                   EMPIRICAL SURVEY: STATIC vs. DYNAMIC DATAFLOW IN CLEANROOM                     │
├───────────────────────┬─────────────────────────────────────┬────────────────────────────────────┤
│ Component (.pyi)      │ Static Dataflow (Grounded in .pyi)  │ Dynamic Dataflow (Left Ungrounded) │
├───────────────────────┼─────────────────────────────────────┼────────────────────────────────────┤
│ sandbox/tool_provider │ Tool registration, schema bindings, │ Concrete tool side-effects,        │
│                       │ parameter conversion errors.        │ subprocess execution environment.  │
├───────────────────────┼─────────────────────────────────────┼────────────────────────────────────┤
│ loop/guard            │ Method signatures (evaluate, reset),│ Warning & fatal streak counts,     │
│                       │ LoopReminder vs. LoopFailure types. │ line-range edit diff extraction.   │
├───────────────────────┼─────────────────────────────────────┼────────────────────────────────────┤
│ control/work_scheduler│ Task scheduling signatures,         │ Specific dirty nodes in storage,   │
│                       │ topological role precedence rank.   │ prompt template formatting.        │
├───────────────────────┼─────────────────────────────────────┼────────────────────────────────────┤
│ workspace/provision   │ commission() signature,             │ Real host OS filesystem paths,     │
│                       │ exact permission bits (444/644/755).│ zipapp runner binary extraction.   │
└───────────────────────┴─────────────────────────────────────┴────────────────────────────────────┘
```

#### Detailed Case Studies from the Codebase:

#### 1. `sandbox/low/tool_provider.pyi` (`ToolProviderType` & `Tool`)
- **Static Dataflow Grounded**:
  - Declares `install_tool(tool: Tool) -> None` and `execute_tool(name, params) -> ToolResponse`.
  - Fully grounds parameter descriptor resolution, required vs. optional parameters, default values, and `ParameterConversionError` diagnostics.
- **Dynamic Dataflow Ungrounded**:
  - The tool itself is an abstract `@poly_type class Tool(Protocol)`.
  - The interface specifies only that `execute_tool` calls the resolved tool and returns its response. What the tool computes or mutates is open-ended.
- **State Machine Dualism**:
  - **Interface Fake (`FakeToolProvider`)**: Maintains an in-memory dictionary of installed tools, performs static parameter schema checking, and returns a configured `ToolResponse(success=True/False)`. Zero subprocesses spawned.
  - **Implementation Test (`ToolProviderImplTest`)**: Verifies actual wire conversion, actual collaborator tool invocation, and detailed error feedback.

#### 2. `loop/low/guard.pyi` (`LoopGuard`)
- **Static Dataflow Grounded**:
  - Declares `evaluate(tool_name, arguments) -> Optional[Union[LoopReminder, LoopFailure]]` and `reset() -> None`.
  - Defines the static data types `LoopReminder` and `LoopFailure`.
- **Dynamic Dataflow Ungrounded**:
  - The interface specifies that reaching the warning threshold produces a reminder and reaching the fatal threshold produces a failure.
  - It does **not** ground the numeric thresholds (e.g. 2 repetitions) nor does it ground how consecutive line-bounded file edits are extracted from `file_editor.EditingTool`.
- **State Machine Dualism**:
  - **Interface Fake (`FakeLoopGuard`)**: Allows downstream tests of `AgentLoop` to easily simulate warning or failure outcomes via `fake_guard.set_next_evaluation(LoopReminder(...))` without having to carefully construct duplicate edit streaks.
  - **Implementation Test (`LoopGuardImplTest`)**: Drives the concrete SUT with repeated calls and asserts that exactly 2 duplicate calls yield a `LoopReminder`.

#### 3. `control/low/work_scheduler.pyi` (`WorkScheduler`)
- **Static Dataflow Grounded**:
  - Declares `schedule_work(subgraph, dir_scope, max_batch_size) -> WorkSchedule`.
  - Defines `ScheduledTask` record structure (`node`, `task_prompt`, `dependency_paths`, `feedback_messages`).
  - Declares `compute_role_precedence(role_deps) -> Mapping[str, int]`.
- **Dynamic Dataflow Ungrounded**:
  - Does not ground how dirty nodes are scanned from `DagStorage`, nor does it ground the text composition of task prompt strings.
- **State Machine Dualism**:
  - **Interface Fake (`FakeWorkScheduler`)**: Downstream orchestrators (`Coordinate`, `Submit`) test batch loops by configuring `fake_scheduler.set_pending_tasks([task1, task2])` followed by `[]` to test loop termination.
  - **Implementation Test (`WorkSchedulerImplTest`)**: Verifies actual DAG longest-path topological sorting against real `dag_storage.DagStorage` state.

#### 4. `workspace/low/provision.pyi` (`WorkspaceProvisioner`)
- **Static Dataflow Grounded**:
  - Declares `commission(role_name, dir_scope, ...) -> WorkspaceDescriptor`.
  - Fully grounds exact permission bit contracts (`0o444` for read-only stubs/contracts, `0o644` for writable targets, `0o755` for runner tools).
- **Dynamic Dataflow Ungrounded**:
  - Does not ground host OS directory locations, how zipapp binaries are compressed, or actual environment variable bindings.
- **State Machine Dualism**:
  - **Interface Fake (`FakeWorkspaceProvisioner`)**: Returns an in-memory `WorkspaceDescriptor(path="/fake/ws", role=role_name)` instantly without touching the host filesystem.
  - **Implementation Test (`WorkspaceProvisionerImplTest`)**: Executes against real temporary directories, verifying that file chunks stream properly and `os.stat().st_mode` matches the required permission bits.

#### The Cleanroom Interface Design Rule
From this survey, we formalize the Cleanroom Interface Design Rule:
> **"An interface component MUST ground static dataflow completely (signatures, parameters, protocol sequences, error hierarchies) so that clients can be verified in isolation. It MUST leave dynamic dataflow ungrounded (leaving host bindings, concrete thresholds, and algorithmic derivations to `_impl`) so that interface fakes remain lightweight, seedable, and zero-dependency."**

### Dynamic Input Generation: The "Strategies as Values" Architecture

#### 1. The Core Defect: The "Single-Sample Trap" in State-Machine Fuzzing

In state-machine-driven testing, API operations are defined as transitions consisting of five decoupled lifecycle blocks:
1. `ctx.requires(...)`: Model state preconditions.
2. `ctx.arguments(generate=..., recognize=...)`: Input generation and recognition.
3. `ctx.returns(...)`: Expected outcome computation / validation.
4. `ctx.ensures(...)`: Real SUT postcondition checks.
5. `ctx.update(...)`: Reference model state mutation.

Historically, the argument generation block was authored using zero-parameter lambdas returning a single, static sample tuple:
```python
ctx.arguments(
    generate=lambda: (">=1.0.0",),
    recognize=lambda req: isinstance(req, str),
)
```
While Hypothesis state machines permuted the **temporal sequence** of transition invocations across random walks (e.g. `parse_range` $\to$ `solve` $\to$ `parse_range`), the input arguments supplied to each transition were **identical constant literals on every single iteration**.

This created three severe systemic failure modes:
1. **Zero Data-Domain Exploration**: Hypothesis never generated boundary inputs, empty strings, whitespace, wildcards (`*`, `x`), operator permutations (`~=`, `^`, `||`), negative integers, or structural variations. The test engine was blind to data-domain defects.
2. **False Sense of Verification**: Test logs reported that hundreds of state-machine iterations passed with 0 failures, creating high confidence despite critical semantic holes.
3. **The Coverage-Arbiter Anti-Pruning Cascade**: Because test runs only passed static happy-path literals, valid defensive branches in the library implementation (e.g., stripping trailing whitespace, handling empty clauses from `||`, parsing wildcard operators) recorded 0% statement coverage. Downstream `pretense_coverage` arbiters, under strict instruction to achieve 100% statement coverage, routinely violated the information embargo by reading private `lib/` implementation lines and blaming the implementer to delete or prune valid defensive code as "dead, unexecutable code". Once implementers pruned this code to satisfy coverage, the library failed soundness verification when evaluated against foreign test suites.

#### 2. The Architectural Solution: "A Strategy Can Just Be a Value"

Rather than introducing heavy meta-abstractions, complex wrapper classes, or separate generator hierarchies, Pretense treats Hypothesis `SearchStrategy` objects **directly as values** within generated argument collections.

Anywhere an argument value is expected in `ctx.arguments(generate=...)`, the author can pass a concrete literal, a data structure, or a `SearchStrategy`:

```python
# 1. Direct standalone strategy for single-argument transitions:
ctx.arguments(
    generate=st.integers(min_value=0, max_value=100),
    recognize=lambda count: isinstance(count, int) and 0 <= count <= 100,
)

# 2. Tuple mixing concrete values and dynamic strategies:
ctx.arguments(
    generate=(
        st.text(min_size=1, max_size=50),
        st.integers(min_value=-10, max_value=10),
        "fixed_scope",
    ),
    recognize=lambda name, delta, scope: isinstance(name, str) and scope == "fixed_scope",
)

# 3. Callable factory returning a tuple of strategies:
ctx.arguments(
    generate=lambda: (
        st.sampled_from([">=1.0.0", "^2.1.0", "~1.0", "*", ">=1.0.0, <2.0.0"]),
        st.booleans(),
    ),
    recognize=lambda spec, prerelease: isinstance(spec, str) and isinstance(prerelease, bool),
)

# 4. Draw-aware callable for interdependent or complex multi-stage sampling:
ctx.arguments(
    generate=lambda draw: (
        draw(st.integers(min_value=1, max_value=10)),
        draw(st.text(alphabet="abcdef", min_size=1, max_size=10)),
    ),
    recognize=lambda count, tag: isinstance(count, int) and isinstance(tag, str),
)
```

#### 3. Execution Dualism: Dynamic Draw vs. Deterministic Fallback

Pretense transparently resolves argument strategies based on the active execution context:

```
                            ┌─────────────────────────────────────────┐
                            │    ctx.arguments(generate=...)          │
                            │  (strategies as values, sequences, fn)  │
                            └────────────────────┬────────────────────┘
                                                 │
                                                 ▼
                                     Is generation active?
                                 (args_fn called without args)
                                                 │
                                ┌────────────────┴────────────────┐
                                ▼                                 ▼
                     Inside Hypothesis Fuzzing            Outside Hypothesis
                   (with_draw(data.draw) active)       (Unit Tests / Fake Adapter)
                                │                                 │
                                ▼                                 ▼
                    data.draw(search_strategy)          search_strategy.example()
                                │                       (with warning suppression)
                                ▼                                 │
                     Dynamic adversarial sample                   ▼
                   with shrinking on failure          Deterministic representative sample
```

1. **Inside Hypothesis Stateful Fuzzing (`compile_hypothesis_test_case`)**:
   - The compiled `RuleBasedStateMachine` executes each rule within `with with_draw(data.draw):`.
   - When `curr_t.args_fn` evaluates the argument generator, `_resolve_generated_arguments` unpacks the items.
   - For every item satisfying `_is_strategy(val)` (detected duck-typed via `example`, `filter`, and `map` or `isinstance(val, SearchStrategy)`), Pretense invokes `draw(val)`.
   - Hypothesis actively explores the entire combinatorial data space across all transitions, generating boundary values, extreme strings, empty collections, and edge-case permutations, while automatically shrinking any counterexample to its minimal reproduction trace.

2. **Outside Hypothesis (Deterministic Unit Tests & Fake Adapters)**:
   - When executing `Test<Target>Unit`, fake adapter method dispatch (`fake.method(...)`), or direct `sm.dispatch_transition(...)` calls outside a Hypothesis rule, `get_current_draw()` returns `None`.
   - `_resolve_argument_value` automatically falls back to invoking `val.example()`.
   - Pretense wraps the `.example()` evaluation inside a scoped `warnings.catch_warnings()` filter that suppresses Hypothesis's `NonInteractiveExampleWarning`, ensuring unit tests and CLI runners remain completely clean and free of spurious warning logs.
   - Tests and fakes require zero additional test fixtures, mocks, or `@given` wrappers.

#### 4. Systemic Impact & Soundness Guarantees

This mechanism directly resolves the cross-model defect gap and the coverage arbiter ping-pong loop:
1. **Full Temporal and Spatial Fuzzing**: State-machine testing now explores both **operation paths** (order of transitions) and **data domains** (boundary values within transitions).
2. **Defensive Code Protection**: Edge-case inputs naturally exercise defensive branches in library implementations (e.g. whitespace stripping, empty input guards, syntax variations), legitimately satisfying 100% statement coverage.
3. **Elimination of "Dead-Code" Pruning Blames**: Coverage arbiters no longer encounter unreached defensive branches. Because the branches are actively exercised by dynamic strategy values, arbiters cannot falsely demand their removal, preserving soundness against foreign test suites and real-world inputs.
4. **Information Embargo Integrity**: Neither the test author nor the coverage auditor needs to inspect private library lines to hardcode arbitrary constants; declaring input domains declaratively via standard Hypothesis strategies (`st.text()`, `st.integers()`, `st.sampled_from()`) allows the verification engine to stress implementations autonomously.

#### 5. Empirical Validation: Comparative Analysis on `semver_solver`

The introduction of dynamic strategies as values was empirically benchmarked on the `semver_solver` suite, comparing Run 1 (static single-sample literals) against Run 2 (generative strategies as values).

##### A. Convergence Velocity & Cost Reduction
Because dynamic inputs exercised defensive branches naturally during test runs, Cleanroom eliminated the multi-round ping-pong cycle where coverage arbiters demanded dead-code deletions:

| Model / Harness | Run 1 Rounds | Run 2 Rounds | Round Reduction | Run 1 Cost | Run 2 Cost | Cost Savings |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`deepseek-flash Cleanroom`** | 32 rounds | **17 rounds** | **-47%** | $0.4716 | **$0.4073** | **-14%** |
| **`gemini-3.8-flash Cleanroom`** | 20 rounds | **14 rounds** | **-30%** | $1.2007 | **$0.8424** | **-30%** |
| **`deepseek-flash Baseline`** | 1 round | 1 round | — | $0.0542 | $0.0863 | — |
| **`gemini-3.8-flash Baseline`** | 1 round | 1 round | — | $0.0768 | $0.3466 | — |

##### B. Test Oracle Transformation
Test authors transitioned from hardcoded literals to comprehensive generative strategies:

```python
# Before (Run 1: Static Single-Sample Trap):
@transition(VersionEngine.parse_version)
def parse_version(self, ctx: TransitionContext) -> None:
    ctx.arguments(
        generate=lambda: ("1.0.0",),  # Invariant literal on every step!
        recognize=lambda text: True,
    )

# After (Run 2: Strategies as Values):
_VERSION_STRATEGY = st.builds(
    Version,
    st.integers(0, 20), st.integers(0, 20), st.integers(0, 20),
    st.one_of(st.just(()), st.lists(st.sampled_from(["alpha", "beta", "rc", "1", "2"])).map(tuple)),
    st.one_of(st.just(()), st.lists(st.sampled_from(["build", "001"])).map(tuple)),
)

_RANGE_TEXT_POOL = (
    "*", "x", "X", "1.x", "1.*", "1.2.x", "1.2.*", "==1.0.0", "=1.0.0", "!=",
    "<1.0.0", "<=1.0.0", ">1.0.0", ">=1.0.0", "^1.2.3", "^0.2.3", "^0.0.3",
    "~1.2.3", "1.0.0 - 2.0.0", ">=1.0.0 <2.0.0", "1.0.0 || 2.0.0", ">=1.0.0-alpha",
)

@transition(VersionEngine.satisfies)
def satisfies(self, ctx: TransitionContext) -> None:
    ctx.arguments(
        generate=(_VERSION_STRATEGY, st.sampled_from(_RANGE_TEXT_POOL).map(VersionRange), st.booleans()),
        recognize=lambda v, r, p: True,
    )
```

##### C. Diagnostic Rigor & Bug Hunting Power
The defect detection rate of the synthesized test suites doubled, exposing subtle bugs across foreign implementations that static tests missed:

| Test Suite | Run 1 Defect Detection Rate | Run 2 Defect Detection Rate | Foreign Bugs Uncovered |
| :--- | :---: | :---: | :---: |
| **`deepseek-flash Cleanroom`** | 6.33% (31 bugs) | **12.63% (36 bugs)** | **+100% Increase in Diagnostic Rigor** |
| **`gemini-3.8-flash Cleanroom`** | 3.50% (8 bugs) | **3.92% (10 bugs)** | Higher coverage on wildcard & caret bounds |
| **`gemini-3.8-flash Baseline`** | 0.00% (0 bugs) | **3.04% (7 bugs)** | Now catches foreign contract violations |

New bugs caught include:
- `ValueError: invalid literal for int() with base 10: 'x'` in caret wildcards (`^0.x`).
- Inverted descending precedence sorting when prerelease versions are mixed with standard releases.
- Unhandled crashes when bare wildcards (`*`) are supplied as dependency constraints to the solver.
- Subtle relational operator and caret boundary miscalculations.

---

### 5.6 Unified Domain Architecture: Symmetrical Generation, Validation, and Relational Perturbation

#### The Generator-Recognizer Duality Problem
In earlier iterations of Pretense, transition arguments were declared using separate generative and recognitive procedures:
```python
ctx.arguments(
    generate=lambda: (st.sampled_from(["a", "b"]), st.integers(1, 10)),
    recognize=lambda name=None, count=None: name in ("a", "b") and 1 <= count <= 10,
)
```
This separation introduced three acute failure modes:
1. **Redundant Boilerplate**: Specifying both constructive generation and analytical recognition duplicated the contract twice across distinct paradigms.
2. **Alignment Drift**: In complex transitions, models frequently drifted between the generator and the recognizer (e.g. generating integers while validating strings, or generating values that the recognizer immediately rejected).
3. **Single-Value Degeneration**: Under boilerplate fatigue or scaffold imitation, smaller models collapsed `generate` to static single constants (e.g. `lambda: ("sample_name",)` or `lambda: ("1.0.0",)`), destroying state-space fuzzing.

#### The `Domain` Abstraction
In formal specification theory, generator and recognizer are two operational facets of a single mathematical entity: a **Domain** $D$.
- **Sampling (Generator)**: $x \sim D$ (constructive draw via Hypothesis `SearchStrategy[T]`).
- **Membership (Recognizer)**: $x \in D$ (analytical predicate `validate(val) -> bool`).

Pretense provides a first-class `Domain[T]` abstraction. Transitions declare parameter domains directly:

```python
ctx.arguments(
    name=Domain.set(["alpha", "beta", "gamma"]),
    count=Domain.range(1, 100),
    active=Domain.boolean(),
    pattern=Domain.regex(r"^[a-z]+_\d+$"),
    target=Domain.type(TargetClass),
)
```

Native Python primitives (`set`, `range`, `re.Pattern`, `type`) automatically promote to `Domain`:
```python
ctx.arguments(
    name={"alpha", "beta", "gamma"},
    count=range(1, 100),
    active=bool,
    pattern=re.compile(r"^[a-z]+_\d+$"),
    target=TargetClass,
)
```

Pretense automatically tuples the strategies for fuzzing (`st.tuples(...)`) and synthesizes the composite recognizer predicate (`lambda *args: all(...)`).

#### Discriminated Cases & Dependent Domains
State machine transitions must not merely wrap API signatures 1:1; they must represent **discriminated equivalence partitions** (e.g. `withdraw_success` vs `withdraw_insufficient_funds`, or `is_less_than_true` vs `is_less_than_false`).

When arguments are inter-constrained across parameters (e.g., $B$ depends on $A$), `ctx.arguments` accepts **Dependent Domains** using closures:
$$\text{arg}_N : \text{Domain} \mid (\text{arg}_1, \dots, \text{arg}_{N-1}) \to \text{Domain}$$

```python
ctx.arguments(
    min_val=Domain.range(0, 50),
    max_val=lambda min_val: Domain.range(min_val + 1, 100),
)
```

#### Constructive Perturbation (`Domain.perturb`)
For complex objects and non-scalar types where building an inverse constraint solver is impossible:
- **Do NOT attempt to write general algorithmic constraint solvers** inside test harnesses (avoiding the Circular Oracle fallacy).
- **Use constructive derivation via `Domain.perturb`**:
  Derives candidate values constructively by applying targeted mutations to an anchor value (`anchor` can be a previous argument or current state machine state):
  ```python
  Domain.perturb(
      anchor,
      mutations=[
          # Near-boundary deltas stressing adjacent edge cases
          lambda v, draw: replace(v, major=v.major + draw(st.integers(1, 5))),
          lambda v, draw: replace(v, minor=v.minor + draw(st.integers(1, 5))),
          lambda v, draw: replace(v, patch=v.patch + draw(st.integers(1, 5))),
      ],
      validator=lambda v2: (v2.major, v2.minor, v2.patch) > (anchor.major, anchor.minor, anchor.patch),
  )
  ```
- **Symmetry Rule**: The validator must recognize the union of all declared mutation branches.

#### Anti-Dummy Scaffolding Enforcement
The Pretense scaffolding generator (`pretense_lint.py --scaffold`) enforces this architecture strictly:
1. It never emits static dummy literals (e.g., `"sample_name"`, `1`, `True`).
2. Arguments with clear types or semantic naming are scaffolded into standard domains (`Domain.range`, `Domain.set`, `Domain.type`, `Domain.boolean`).
3. For unresolved, ambiguous, or custom domain arguments, the scaffolder emits `Domain.required("parameter_name")`. `Domain.required` type-checks cleanly under Pyright but raises an explicit `NotImplementedError` at test runtime if left unspecialized, forcing the authoring model to supply an intentional domain rather than silently inheriting dummy constants.

---

## 6. Path Coverage vs. Hypothesis State-Machine Transitions

### Are There Path Coverage Tools for Python?
- **Standard Tooling (`coverage.py`)**: Only supports Statement (C0) and Branch/Arc (C1) coverage. It does not measure path combinations.
- **Symbolic & Concolic Execution (`crosshair`, `pyexz3`)**:
  - `crosshair` uses the Z3 SMT solver to find inputs that violate type annotations and postconditions along branch paths.
  - *Limitation*: Highly fragile on complex object state, dictionaries, and dynamic Python dispatch. Often times out on multi-class interactions.
- **McCabe Cyclomatic Complexity**: Measures path count upper bounds, but does not measure test execution across paths.

### Why Hypothesis State Machines Subsume Path Coverage
Full path coverage on source code is computationally intractable due to unbounded loops ($2^n$ paths). However, bugs in stateful software do not arise from abstract AST branch combinations; they arise from **sequences of state mutations** (e.g. Write $\to$ Read $\to$ Mutate $\to$ Delete).

Hypothesis state machines test **path coverage in the state transition graph** $(\mathcal{S} \times \mathcal{A} \to \mathcal{S}')$:
- By generating bounded random walks across API actions, Hypothesis explores diverse execution paths through the underlying implementation automatically.
- Any branch condition dependent on prior state (such as `if node_id in self._upstream`) is naturally explored under both branches without requiring an explicit static test for each combination.

---

## 7. Contract Traceability: Requirements in Comments vs. Slugs

### Why Informal Comments Fail
If tests use unstructured comments (e.g. `# Covers requirement: replace existing node`):
- Natural language parsing is ambiguous.
- An LLM can write vague assertions under an assertive comment without actually testing the invariant.
- Linters cannot verify completeness without semantic NLP models.

### The Cleanroom Solution: Deterministic Contract Slugs via Comments
Cleanroom already establishes factored contract slugs in `planning/*.md` and `low/*.pyi`:
```python
# low/dag_engine_lite.pyi
@operation
def add_node(self, node_id: str, ...) -> None:
    """
    POSTCONDITIONS:
    - [slug:dag.add_node.register] MUST register definition.
    - [slug:dag.add_node.replace_deps] WHEN node exists, MUST replace dependencies.
    """
```

In the test suite, test methods document requirement coverage directly via standard Python comments or docstrings:
```python
# [slug:dag.add_node.replace_deps]
@rule(node_id=nodes, new_deps=st.sets(nodes))
def re_register_node_replaces_deps(self, node_id, new_deps):
    """Verifies that re-registering an existing node clears old edges."""
    ...
```
Or in standard unit tests:
```python
def test_re_register_node_replaces_dependencies(self) -> None:
    # [slug:dag.add_node.replace_deps]
    dag = DAG()
    dag.add_node("target", action=lambda: 1, dependencies=["dep1"])
    dag.add_node("target", action=lambda: 2, dependencies=["dep2"])
    self.assertEqual(dag.get_dependencies("target"), {"dep2"})
```

### Deterministic Linter Audit (Zero-Token Python Tooling)
1. **Linter Extraction**: A simple AST tool parses all `[slug:...]` tags from `low/*.pyi` docstrings.
2. **Test Tag Verification**: The linter parses all `# [slug:...]` comment lines or docstring tags within test functions in `tests/*_test.py` and `tests/*_state_machine_test.py`. No runtime decorators or metadata frameworks are needed.
3. **Traceability Gate**: If any slug defined in `low/*.pyi` has 0 corresponding test assertions, Pass 1 halts with a deterministic error:
   `[TRACEABILITY ERROR]: Uncovered contract slug 'dag.add_node.replace_deps' in parts/dag_engine_lite.`
4. This audit requires **zero LLM tokens**, zero runtime framework dependencies, and gives the authoring agent an exact, actionable checklist.

---

## 8. Comparison Matrix: Verification Strategies

| Metric / Capability | AST Branch Coverage | `mutmut` Mutation | LLM Chaos Tester (#4) | Pretense State Machine (#3) |
| :--- | :---: | :---: | :---: | :---: |
| **Detects Errors of Omission** | **No** | **No** | Yes (Unreliable) | **Yes (Deterministic)** |
| **Defect 1 (Retry Recoveries)** | Missed | Weak Alert | Depends on prompt | **Caught via rule parameter search** |
| **Defect 2 (Re-registration)** | Missed | Missed | Depends on prompt | **Caught via repeated rule calls** |
| **Defect 3 (Dynamic Sync)** | Missed | Missed | Depends on prompt | **Caught via interleaved rules** |
| **Deterministic Termination** | Immediate | Bounded by mutants | **None (No stopping metric)** | **Bounded by `max_examples`** |
| **Blame Diagnostic Quality** | None | Diff patch | Prose description | **Minimal Shrunk Trace** |
| **Compute / Token Cost** | Free ($0) | High CPU (Subprocesses) | High Token Cost | **Fast Python Execution ($0 Tokens)** |

### Why `mutmut` is Obsolete and Dropped from Pretense

Mutation testing (`mutmut`) was previously evaluated as a certifier gate, but is **formally dropped** in favor of Pretense state machines:
1. **Inverted Verification Paradigm**: `mutmut` mutates source code to test static, example-based tests (`assert add(1, 2) == 3`). Pretense inverts this by mutating inputs and transition sequences to test the production code.
2. **Blind to Sequence & Lifecycle Bugs**: `mutmut` only performs single-line AST mutations (e.g. flipping `<` to `<=`). It is completely blind to multi-class desynchronization, stale edge accumulation, and lifecycle leaks.
3. **Differential Parity Subsumes Mutation Testing**: Under Pretense differential testing ($Lib \equiv Spec$), every meaningful branch in `lib` must match the state machine oracle. Any code change that alters observable behavior will fail differential parity during pseudo-random walks.
4. **Eliminates Devastating CPU Overhead**: `mutmut` requires spawning hundreds of separate subprocesses, taking minutes to hours, and constantly stalling on equivalent mutants. Pretense runs thousands of state transitions in milliseconds directly in-process.

---

## 9. The Pretense CLI Runner & Repository Architecture

### A. Generic, Standalone CLI Tool (`uv run pretense`)
Pretense is designed as a **generic, standalone testing and fake-synthesis tool**, completely decoupled from Cleanroom internal framework details:
- **CLI Ergonomics**: Works like `pytest` as far as flags and options are concerned:
  - `uv run pretense`: Recursively discovers and executes all state machines.
  - `uv run pretense parts/dag_engine_lite/pretense`: Target-specific directory execution.
  - `-k <pattern>`: Filter by state machine prototype or transition names.
  - `-v` / `-q`: Verbosity controls.
  - `--max-examples=<int>`: Controls Hypothesis fuzzing sample bounds.
  - `--seed=<int>`: Deterministic PRNG seed for reproducible test replay.

### B. Parallel Directory Structure & Consolidated Component Files (`parts/*/pretense/*_pretense.py`)
Pretense state machines live in a **parallel directory structure**, strictly segregated from existing Cleanroom unit tests in `tests/`:
```
parts/<component>/
├── high/                       # Cleanroom High-Level Spec
├── low/                        # Cleanroom Interface Protocols (.pyi)
├── lib/                        # Production Implementation (*_impl.py)
├── tests/                      # Cleanroom Unit Tests (*_test.py)
└── pretense/                   # Consolidated Pretense Suites
    └── <component>_pretense.py # Single unified pretense file per component
```

#### Consolidated Single-File Structure
Rather than fragmenting pretense logic into separate `_machine.py`, `_test.py`, and `_fuzz.py` files, Pretense consolidates the entire specification, fake factory, unit tests, and fuzzing suite for each component into a single, cohesive file: **`<component>_pretense.py`**.

Each `<component>_pretense.py` file follows a standardized five-section layout:
1. **Pretense State Definitions**: Typed dataclasses (`@dataclass`) representing canonical state models.
2. **Component Transitions**: Declarative transitions (`@proto.transition(...)`) registered against interface protocols, using the Four-Lambda architecture (`require`, `arguments`, `returns`, `provide`).
3. **Synthesized Fake Factory**: Zero-boilerplate factory function (`make_<component>_fake(...)`) utilizing `sm.as_fake(Protocol)` for dependency injection into downstream parts.
4. **Deterministic Unit Tests**:
   - `Test<Component>Unit`: Fast verification of the synthesized fake state machine in isolation.
   - `Test<Component>ImplReal`: Direct verification of the concrete library implementation (`lib/*_impl.py`) against lifecycle scopes, providing full statement and branch coverage.
5. **Hypothesis Property Fuzz Tests**: Stateful random walk fuzzer (`to_hypothesis_test_case` or `RuleBasedStateMachine`) asserting invariants and differential parity ($Lib \equiv Spec$).

#### CLI Ergonomics & Execution Modes
- `uv run pretense <path>`: Recursively discovers and executes all pretense targets across all sections, including Hypothesis fuzzing.
- `uv run pretense <path> --no-fuzz`: Bypasses long-running fuzzing runs and executes only deterministic unit tests instantly (<0.01s per suite).
- `uv run pretense <path> --cov`: Evaluates statement coverage of the target `lib/*_impl.py` file under test.
- `uv run pretense <path> --no-fuzz --cov`: Evaluates statement coverage achieved exclusively by the deterministic, non-fuzz unit test targets.
- `-k <pattern>`: Filter targets by class or test name.
- `--seed=<int>`: Deterministic PRNG seed for reproducible fuzz execution.

### C. Elimination of Hypothesis `Bundle` (Pure `DataObject` & State Inspection)
Pretense strictly **eliminates Hypothesis `Bundle`** in favor of direct domain state inspection via `DataObject` / `data.draw` under dynamic scope:
- In traditional Hypothesis, rules store output references in `Bundle("names")` so downstream rules can draw from them.
- However, `Bundle` introduces artificial state that is inaccessible in Fake mode and incompatible with in-memory protocol synthesis.
- In Pretense, domain state is held in standard typed dataclasses (`self.state: DAGState`). When argument generators need a valid existing member, they draw directly from domain state (`state.nodes.get_in(val)` calls `draw.sampled_from(list(state.nodes))`).
- This guarantees that **100% of state-machine logic is identical between In-Memory Fake mode and Test Driver mode**.

---

## 10. Implementation Roadmap & Milestones

### Phase 1: Pretense CLI & DSL Core
- [x] Implement `pretense` CLI runner (`uv run pretense`) with pytest-compatible discovery, path arguments, and keyword filtering.
- [x] Implement `StateMachineProto` with `@proto.transition(Target.method)` marker header registration.
- [x] Implement the Four-Lambda lifecycle (`require`, `arguments`, `returns`, `provide`) with dynamic scope `_CURRENT_DRAW`.
- [x] Implement the Zero-Ambiguity Invariant in Fake dispatch (evaluating all candidate transitions; failing on 0 or >1 matches).
- [x] Implement bidirectional collection helpers (`PretenseSet`, `PretenseDict`) with four-tier negative membership generation (`get_not_in`).

### Phase 2: Hypothesis Compilation & Counterexample Synthesis
- [x] Implement `compile_hypothesis_test_case(proto=..., sut_factory=...)` compiling prototypes into `RuleBasedStateMachine`.
- [x] Implement automated unit test synthesis from shrunken Hypothesis counterexample traces.
- [x] Format counterexample test functions into Cleanroom blame directives (`bin/blame <culprit_file> "<critique>"`).

### Phase 3: Benchmark & Empirical Study
- [x] Port `benchmarks/parts/dag_engine_lite` to Pretense in `benchmarks/parts/dag_engine_lite/pretense/`.
- [x] Verify that `uv run pretense` catches all 3 seeded defects (retry recovery, duplicate re-registration, wave desynchronization).
- [ ] Execute Treatment A vs. Treatment B empirical evaluation comparing Cleanroom double-blind pipeline vs State-Machine-Driven TDD.

### Phase 4: Full Repository Coverage & Role Integration
- [x] Author `<component>_pretense.py` suites for all 48 `lib/*_impl.py` components across `update_with_ai/parts/`.
- [x] Achieve non-fuzz deterministic test coverage across all components via `--no-fuzz --cov`.
- [x] Clean static typing validation across all pretense suites (`uv run pyright update_with_ai/parts/*/pretense/` -> 0 errors).
- [ ] Integrate parallel Cleanroom methodology roles: `pretense` (author role) and `pretense_qa` (arbiter role).

### Phase 5: Ergonomics Redesign & Unified State Machine Architecture (Completed)
- [x] **TODO 1: Class-Based State Machine DSL (`StateMachine` & `@transition`)**:
  - Replaced the verbose `StateMachineProto` 4-function syntax with single decorated methods inside `StateMachine` subclasses (`@transition(TargetClass.method)` or `@transition.seeding()`).
  - Implemented generic `TransitionContext[Target, P, R]` parameterized by the target singleton type, parameter specification (`ParamSpec` `P`), and return type (`R`).
  - Decorated methods are callable at runtime (`sm.method(*args, **kwargs)`), dispatching via `method_proxy` to `dispatch_transition`, fully compliant with Pyright type checking.
- [x] **TODO 2: Pure Reference Model (Decoupled Lambdas)**:
  - Ensured lambdas (`antecedent`, `arguments`, `returns`, `consequent`) receive only domain parameters (`*args: P`, `res: R`) and reference `self.state`, keeping the reference model clean and pure.
  - Concrete target instances are decoupled from transition lambdas; target singletons are managed by the runtime adapter.
- [x] **TODO 3: Underneath Target Singleton Dispatch**:
  - Supported initializing state machines under test with singleton instances keyed by type (`singletons={TargetClass: instance}`).
  - When driving implementation logic under test, the runtime harness automatically dispatches calls to `instance.method(*args)` underneath and asserts parity against `returns` and `consequent`.
- [x] **TODO 4: In-Memory Fake Synthesis (`sm.as_fake(Target)`)**:
  - State machines synthesize dynamic fake adapters conforming to interface protocols: `fake = sm.as_fake(Target)`.
  - Dispatched calls route to the matching transition, updating `sm.state` and returning synthesized results with zero mock drift across collaborating singletons.
- [x] **TODO 5: Full Repository & Benchmark Migration**:
  - Migrated all 54 canonical pretense suites across `update_with_ai/parts/` and `update_python_with_ai/parts/`.
  - Migrated all 18 historical and baseline pretense suites under `benchmarks/results/` (`dag_engine_lite` and `semver_solver`).
- [x] **TODO 6: Scaffolder & Template Alignment**:
  - Updated `update_python_with_ai/templates/pretense_template.py` with the class-based `@transition` DSL.
  - Updated `update_python_with_ai/support/lib/pretense_lint.py` scaffold generator and verified via `update_python_with_ai/support/tests/pretense_lint_test.py`.
- [ ] **TODO 7: Collaborator State Machine Importing & Seeding Transitions (Next Step)**:
  - Formalized architectural design for importing external collaborator state machines (`self.collab_sm = CollabStateMachine()`) and obtaining injected collaborator fakes (`fake_collab = self.collab_sm.as_fake(CollabProtocol)`).
  - Next milestone: Implement multi-machine compositional integration tests validating Hypothesis dynamic interleaving of collaborator seeding transitions with SUT operational transitions.
- [ ] **TODO 8: Semantic Binding / Implementing vs. Importing (Next Step)**:
  - Architectural model formalized: implementation state machines *implement* interface state machines via class inheritance (`class ComponentImplStateMachine(ComponentStateMachine): ...`), distinct from importing collaborator state machines.
  - Next milestone: Author composite implementation state machines for multi-interface components (e.g. `ToolManagerImpl` extending `ToolInstaller` and `ToolExecutor`).
- [ ] **TODO 9: Poly Types (Deferred)**:
  - Defer polymorphic types without singletons (such as dynamic tool instances) to a subsequent design phase.

### Phase 6: First-Class Postconditions & DSL Refinement (`requires`, `update`, `ensures`) (Completed)
- [x] **TODO 10: DSL Keyword Alignment (`requires` & `update`)**:
  - Rename `ctx.antecedent` $\to$ `ctx.requires`.
  - Rename `ctx.consequent` $\to$ `ctx.update`.
  - Provide non-breaking aliases in `TransitionContext` (`ctx.antecedent` delegating to `ctx.requires`, and `ctx.consequent` delegating to `ctx.update`) to ensure 100% backward compatibility for existing test suites.
- [x] **TODO 11: Direct Singleton Storage in the State Machine State**:
  - Decouple `StateMachine` from Cleanroom lifecycle phases and phase runners. Singletons under test are stored directly in the state machine state (`self.singletons` or `self.state.singletons`), holding direct references to concrete service objects.
  - In fake mode, singleton references are omitted/empty; in real/fuzz test mode, singletons are populated directly.
  - Implement dynamic target resolution: when executing a transition bound to `TargetClass.method`, resolve the immediate target singleton instance matching `TargetClass` from the state machine's singletons dictionary.
- [x] **TODO 12: Unified `check` Pattern for `requires` and `ensures` (Mode B Only)**:
  - Eliminate boolean return ambiguity: standardise 100% on the **`check` pattern** across both contract blocks.
  - **In `requires`**: `ctx.requires(lambda check: check(condition, "reason"))`
    - Evaluated before arguments/firing on every candidate step.
    - **Simple Flag-Based Evaluation**: `check` simply sets `self.ok = False` if condition fails and records the reason string. All checks execute sequentially (e.g. `(check(a), check(b))` in a lambda or statements in a `def`). No exceptions are raised, and all failure reasons are captured.
    - The runner queries `check.ok` after the block to determine if the transition is **ready to fire**.
    - If a fake call finds no matching transition, the collected reasons are formatted into `NoMatchingTransitionError` diagnostics.
    - Preserves backward compatibility: if lambda takes 0 arguments (`lambda: bool`), evaluates truthiness directly.
  - **In `ensures`**: `ctx.ensures(lambda res, target, check, *args: (check(...), check.equal(...)))`
    - Evaluated strictly during real/fuzz tests after execution.
    - Receives `res` (return value), `target` (immediate singleton under test), `check` (assertion & lookup helper), and `*args` (domain inputs).
    - If `check` fails, raises `AssertionError` immediately with formatted message and diffs, indicating a **behavioral contract violation**.
    - `check.get(OtherSingleton)` provides direct access to collaborating singletons under test for cross-object postconditions.
    - `check.equal(actual, expected, msg="")` provides formatted diff assertions.
- [x] **TODO 13: Execution Topology Wiring**:
  - **In-Memory Fakes (`FakeAdapter`)**: Explicitly skip `ensures`. Fakes evaluate only `requires` $\to$ `arguments` $\to$ `returns` $\to$ `update`.
  - **Hypothesis Stateful Fuzzer (`compile_hypothesis_test_case`)**: Evaluate `ensures` after every real method execution and outcome recognition, asserting postconditions across all random walk iterations.
  - **Deterministic Dispatch (`dispatch_transition`)**: Evaluate `ensures` when singletons under test are present in the state machine.
- [x] **TODO 14: Scaffold & Guide Realignment**:
  - Update `update_python_with_ai/support/lib/pretense_lint.py --scaffold` to generate the 5-block transition structure using `check` for both `requires` and `ensures`.
  - Update `update_python_with_ai/templates/pretense_template.py`.
  - Update `update_python_with_ai/guides/pretense.md` to instruct models on authoring postconditions in `ensures`, deprecating redundant manual assertions in Sections 3 and 4.

---

## 11. Role Architecture Plan: `pretense`, `pretense_qa`, and `pretense_coverage`

To operationalize Pretense within autonomous Cleanroom execution, we establish two new roles parallel to `test` and `qa`:
- **`pretense`**: Author role responsible for creating and maintaining `{unit_dir}/pretense/{unit_name}_pretense.py`.
- **`pretense_qa`**: Arbiter role responsible for executing pretense verification, evaluating deterministic non-fuzz coverage, and running bounded Hypothesis property fuzzing.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                      PARALLEL VERIFICATION PIPELINE TOPOLOGY                           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│                                [ low/*.pyi ]                                           │
│                                      │                                                 │
│                    ┌─────────────────┴─────────────────┐                               │
│                    ▼                                   ▼                               │
│            [ lib/*.py ]                        [ low/*.pyi ]                           │
│                 │                                    │                                 │
│                 ├──────────────────┬─────────────────┤                                 │
│                 │ (Standard Path)  │ (Pretense Path) │                                 │
│                 ▼                  ▼                 ▼                                 │
│          [ tests/*_test.py ]             [ pretense/*_pretense.py ]                    │
│            (Role: test)                        (Role: pretense)                        │
│                 │                                    │                                 │
│                 ▼                                    ▼                                 │
│             [ Role: qa ]                     [ Role: pretense_qa ]                     │
│        (pytest unit tests)               (pretense --no-fuzz & fuzz)                   │
│                 │                                    │                                 │
│                 ▼                                    ▼                                 │
│          [ Role: coverage ]                 [ Coverage Criteria ]                      │
│        (pytest-cov 100%)                 (pretense --no-fuzz --cov 100%)               │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### A. The 20k Guide Constraint & AST-Driven Templating Strategy

Cleanroom enforces a strict **20,000 character limit** on role guide markdown files (`guides/*.md`). A guide exceeding this limit compromises model focus, exhausts context, and violates Cleanroom behavioral invariants.

Because a full Pretense suite contains state machine prototypes, transitions, four-lambda handlers, synthesized fakes, deterministic unit tests, and Hypothesis fuzz harnesses, **explaining all of this syntax in prompt prose would easily exceed 20k characters and lead to frequent model hallucinations**.

#### The Solution: Heavy AST-Driven Scaffolding & Templating
Instead of asking the LLM to write pretense files from scratch, the `pretense` role relies on a **deterministic scaffolding tool**:
`uv run python -m update_python_with_ai.support.lib.pretense_lint --scaffold {target_file} --pyi {unit_dir}/low/{unit_name}.pyi --impl {unit_dir}/lib/{unit_name}.py`

The scaffolding generator uses Python AST inspection of `low/{unit_name}.pyi` and `lib/{unit_name}.py` to automatically produce 80% of the target file:
1. **Preamble & Imports**: Imports for `StateMachineProto`, `NotBound`, lifecycle phases, protocols from `low/`, and classes from `lib/`.
2. **State Dataclass**: Emits `@dataclass class <Component>State:` with default attributes inferred from protocol properties.
3. **Transition Stubs**: For each protocol method in `low/*.pyi`:
   - `@proto.transition(Protocol.method)`
   - `def method_name(): pass`
   - `@method_name.arguments` with recognized parameter types and `NotBound` handling
   - `@method_name.returns` with return value wrapping (`Value(...)` / `Raised(...)`)
   - `@method_name.provide` with state mutation stub
4. **Synthesized Fake Factory**: `make_<component>_fake(state=None) -> Protocol:` using `sm.as_fake(...)`.
5. **Unit Test Classes**:
   - `Test<Component>Unit`: Test template exercising fake methods.
   - `Test<Component>ImplReal`: Populated lifecycle registry setup (`enter_phase`), instantiating real singleton, and exercising all methods.
6. **Hypothesis Fuzz Suite Skeleton**: `@settings(max_examples=30)` with `given(...)` or `to_hypothesis_test_case(...)`.

#### The Role Guide (`guides/pretense.md` < 15,000 characters)
Because the scaffold tool generates all structural boilerplate, the role guide only needs to instruct the model on **semantic domain logic**:
1. How to represent state transitions and domain invariants in the state dataclass.
2. How to implement the `@arguments` recognizer/generator and `@provide` state mutator.
3. How to write real implementation tests in `Test<Component>ImplReal` to achieve 100% statement coverage of unhandled branches in `lib/*_impl.py`.

### B. Methodology Configuration (`cleanroom_roles.toml`)

The role definitions for `cleanroom_roles.toml` establishing the 3-role Pretense pipeline parallel to `test`, `qa`, and `coverage`:

```toml
[roles.pretense]
name = "pretense"
persona = "Pretense Engineer"
src_pattern = "{unit_dir}/pretense/{unit_name}_pretense.py"
guide = "update_python_with_ai/guides/pretense.md"
template = "update_python_with_ai/templates/pretense_template.py"
template_command = "uv run python -m update_python_with_ai.support.lib.pretense_lint --scaffold {target_file} --pyi {unit_dir}/low/{unit_name}.pyi --impl {unit_dir}/lib/{unit_name}.py"
prompt_template = "Files are aligned according to the guide."
allows_step_mode = true
role_deps = []
star_role_deps = ["low"]
silent_role_deps = ["spec_qa"]
stub_role_deps = ["lib"]
silent_cross_role_deps = ["lib"]
tools = [
    "update_python_with_ai.support.lib.pretense_lint",
    "update_python_with_ai.support.lib.build_lint_common",
]
active_component_types = ["implementation"]
verify_template = "uv run python -m update_python_with_ai.support.lib.pretense_lint {unit_dir}/pretense/{unit_name}_pretense.py --pyi {unit_dir}/low/{unit_name}.pyi && uv run pyright {unit_dir}/pretense/{unit_name}_pretense.py"
verification_success_message = "{unit_name}_pretense.py passed static checks (syntax & types). IMPORTANT: Static verification does NOT execute test suites. Call check_file often to verify pretense structure."

[roles.pretense_qa]
name = "pretense_qa"
persona = "Pretense QA Arbiter"
src_pattern = ""
guide = "update_python_with_ai/guides/pretense_qa.md"
prompt_template = "Files are aligned according to the guide."
allows_step_mode = false
role_deps = []
star_role_deps = ["low"]
feedback_role_deps = ["lib", "pretense"]
tools = []
active_component_types = ["implementation"]
verify_template = "uv run pretense {unit_dir}/pretense/{unit_name}_pretense.py"
verification_success_message = "Pretense test {unit_name}_pretense.py passed."

[roles.pretense_coverage]
name = "pretense_coverage"
persona = "Pretense Coverage Arbiter"
src_pattern = ""
guide = "update_python_with_ai/guides/pretense_coverage.md"
prompt_template = "Files are aligned according to the guide."
allows_step_mode = false
role_deps = []
silent_role_deps = ["pretense_qa"]
star_role_deps = ["low"]
feedback_role_deps = ["lib", "pretense"]
tools = []
active_component_types = ["implementation"]
verify_template = "uv run pretense {unit_dir}/pretense/{unit_name}_pretense.py --no-fuzz --cov --threshold 100.0"
verification_success_message = "All lines of {unit_name}.py are covered by {unit_name}_pretense.py."
```

### C. Execution Pipeline & Feedback Loop

1. **Double-Blind Authoring (`pretense`)**:
   - `pretense` role workspace is provisioned with `low/*.pyi` (authoritative contract) and `lib/*_impl.py` (for non-fuzz real test coverage targeting).
   - In scaffold mode, `bin/get_work` runs `template_command` to generate the 5-section scaffold if the target file is missing.
   - Author implements `@proto.transition` logic, fake verification in `Test<Target>Unit`, and real implementation coverage in `Test<Target>ImplReal`.
2. **Behavioral & Fuzzing Arbiter Gate (`pretense_qa`)**:
   - `pretense_qa` runs `uv run pretense {unit_dir}/pretense/{unit_name}_pretense.py`.
   - Executes deterministic unit tests, state machine fakes, and bounded Hypothesis fuzzing (`--max-examples=50`).
   - If tests fail, it attributes single-paragraph blame to either `pretense` (if test asserts unmandated behavior) or `lib` (if implementation violates contracts).
   - On pass, stamps `PRETENSE_QA_AUDIT` across both verified target files.
3. **100% Statement Coverage Arbiter Gate (`pretense_coverage`)**:
   - `pretense_coverage` runs `uv run pretense {unit_dir}/pretense/{unit_name}_pretense.py --no-fuzz --cov --threshold 100.0`.
   - Asserts 100% statement coverage across `lib/<unit_name>.py`.
   - If uncovered statements exist, delivers targeted blame to `pretense` (missing requirement assertions) or `lib` (unreachable code needing restructuring or `# pragma: no cover (assumption: <reason>)`).
   - On 100% coverage, stamps `PRETENSE_COVERAGE_AUDIT` across both verified target files.

---

## 12. Empirical Benchmarking: Pretense as a Baseline Equalizer

A key finding from empirical benchmarking across DeepSeek-Flash, Gemini 3.8 Flash, and local Qwen-MoE on the `dag_engine_lite` benchmark is that **Pretense fundamentally alters the baseline vs. Cleanroom economic calculus**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                      PREFENSE AS A BASELINE EQUALIZER                                  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   CONVENTIONAL BASELINE (Without Pretense)                                             │
│   • Single model prompted to write code and raw pytest test cases.                     │
│   • Tautological bias: tests assert only the developer's assumptions.                 │
│   • Frequent deadlocks, silent omissions, and poor branch coverage.                    │
│                                                                                        │
│   PREFENSE-POWERED BASELINE (--baseline --pretense)                                    │
│   • Single model prompted with Low-Level Specs and Pretense State Machine protocol.    │
│   • Pretense provides executable transition semantics, automatic fake synthesis, and   │
│     structured property fuzzing out-of-the-box.                                        │
│   • Closes the quality gap with Cleanroom while saving 37%–74% in token cost!         │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Empirical Cross-Model Telemetry (`dag_engine_lite`)

| Configuration | Model & Harness | Unit / Fuzz Tests | Pyright (Lib) | Wall Clock (s) | Cost ($USD) | Total Tokens | Net Rounds |
| :--- | :--- | :---: | :---: | ---: | ---: | ---: | :---: |
| **Cleanroom (Net)** | **DeepSeek-Flash** (DSH) | **49P / 0F** | **0 errors** | 1180.9s | $0.1779 | 11,088,411 | 8 |
| **Pretense Baseline** | **DeepSeek-Flash** (DSH) | **33P / 0F** | **0 errors** | 492.3s | **$0.1332** | 6,932,259 | 1 |
| **Cleanroom (Net)** | **Gemini-3.8-Flash** (Antigravity) | **60P / 0F** | **0 errors** | 1135.0s | $0.7487 | 20,750,091 | 16 |
| **Pretense Baseline** | **Gemini-3.8-Flash** (Antigravity) | **57P / 0F** | **0 errors** | 266.4s | **$0.1972** | 5,747,750 | 1 |
| **Cleanroom (Net)** | **Qwen-MoE** (DSH / Local) | **98P / 0F** | **0 errors** | 2223.8s | $0.0000 | 12,852,569 | 14 |
| **Pretense Baseline** | **Qwen-MoE** (DSH / Local) | **92P / 0F** | **0 errors** | 1151.5s | **$0.0000** | 6,719,320 | 1 |

### Why Pretense Allows the Baseline to Compete for Lower Cost:
1. **Executable Oracle Without Multi-Agent Tax**: In Cleanroom, independent roles (`pretense`, `pretense_qa`, `pretense_coverage`) verify code through successive dispatch waves and arbiter review. Pretense's declarative structure provides an executable behavioral oracle that keeps a single-agent baseline grounded without paying multi-role dispatch tokens.
2. **Watchdog-Protected Execution**: Built-in `--timeout` watchdog in `pretense/cli.py` combined with `PYTHONFAULTHANDLER=1` and `PRETENSE_TIMEOUT=45.0s` terminates and tracebacks any infinite loops, allowing single-agent baselines to recover rapidly rather than hanging indefinitely.
3. **When to Choose Each**:
   - Use **Pretense Baseline** when developer cost and execution speed are paramount on well-specified modular components.
   - Use **Cleanroom Double-Blind Pipeline** when developing mission-critical systems where zero-defect guarantees, spec-level verification (`spec_qa`), and independent bipartite arbitration are strictly required.

---

## 13. Future Empirical Study: Cleanroom vs. State-Machine-Driven TDD

While Cleanroom is founded on the principle that independent, double-blind declarative specifications prevent specification drift and coincident blindspots, **TDD is an important empirical baseline that must be scientifically evaluated**.

If an agent directly authors an executable State Machine test suite from high-level requirements and implements code against it in a tight TDD loop, **could it achieve comparable software reliability at a fraction of Cleanroom's token and round cost?**

### A. The Core Empirical Hypotheses
1. **Cost & Latency Hypothesis**: State-machine-driven TDD eliminates 3–4 specification stages (`high_to_planning`, `planning_to_low`, `spec_qa`, `coverage`), reducing total token consumption and execution steps by $50\%\text{--}70\%$.
2. **Defect Detection Hypothesis**: Without an independent declarative specification (`low/*.pyi`), does TDD catch subtle integration defects (such as Defect 1: retry recovery, Defect 2: re-registration edge cases, Defect 3: multi-class desynchronization) as reliably as Cleanroom?

### B. Identified Hazards to Measure
In an LLM-driven TDD workflow, we must explicitly measure and monitor four critical hazards:
1. **The "Test Gaming" (Reward Hacking) Hazard**:
   When tests fail during the TDD loop, does the LLM genuinely fix the implementation, or does it "game" the test suite by weakening transition preconditions, deleting failing assertions, or altering the state machine to match buggy implementation behavior?
2. **The Coincident Blindspot Hazard**:
   In Cleanroom, `lib` and `test` are authored double-blind from an independent contract. In TDD, if the same model context generates the test suite and then implements the library, any cognitive misconceptions the model holds about the problem domain may be baked into both the tests and the code simultaneously.
3. **The Loss of Objective Blame Attribution**:
   When a test fails, who is blamed? Without an independent source of truth of record (`low/*.pyi`), the agent cannot objectively determine whether a failure is a defect in `lib` or a bug in the test state machine.
4. **Architectural Decay Across Component Boundaries**:
   Without explicit interface specifications (`low/*.pyi`), do multi-component boundaries degrade into tightly-coupled, ad-hoc implementations that cannot be cleanly faked or modularized?

### C. Experimental Benchmark Design
* **Benchmark Target**: `benchmarks/parts/dag_engine_lite` and `benchmarks/parts/semver_solver`.
* **Treatment A (Cleanroom Double-Blind Pipeline)**:
  `High` $\to$ `Planning` $\to$ `Low (.pyi)` $\to$ `Spec QA` $\to$ `Lib` + `Test` $\to$ `QA`.
* **Treatment B (State-Machine-Driven TDD Loop)**:
  `High` $\to$ `State Machine Test Suite` $\to$ `Lib Implementation` $\to$ `TDD Refactor Loop` (run until green).
* **Evaluation Metrics**:
  1. *Total Cost*: Tokens consumed (input/output) and total agent steps/rounds.
  2. *Defect Catch Rate*: Percentage of seeded benchmark defects detected and repaired.
  3. *Cross-Testing Pass Rate*: Running Treatment B's library against Treatment A's independently authored test suite, and vice-versa.
  4. *Mutation Score (`mutmut`)*: Percentage of injected code mutants killed by the test suite.
