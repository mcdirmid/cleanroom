# Cross-Model Differential Defect Analysis: Coincident Cognitive Blind Spots & Edge-Case Coverage in Single-Model Cleanroom Ensembles

## 1. Executive Summary & The Empirical Phenomenon

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

This document investigates:
1. The exact mechanical and semantic nature of the three undetected defects.
2. Why Cleanroom's single-model double-blind isolation failed to prevent or detect them.
3. Why 95% line and 90% branch coverage failed to flag the omissions.
4. The theoretical implications for AI software engineering and the architectural necessity of heterogeneous multi-model Cleanroom ensembles.

---

## 2. Anatomy of the Three Undetected Defects

### Defect 1: Off-by-One Retry Accounting on Action Recovery (`DAGRunner.run`)

#### The Formal Contract (`low/dag_engine_lite.pyi` & `low/dag_engine_lite_impl.pyi`)
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

#### Qwen's Implementation Flaw (`P_qwen: lib_1.py:927`)
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

#### Why Qwen's Self-Test ($V_{\text{qwen}}$) Missed It
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

#### How Foreign Tests Caught It
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

### Defect 2: Node Re-Registration Stale Edge Accumulation (`DAG.add_node`)

#### The Formal Contract (`low/dag_engine_lite.pyi`)
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

#### Qwen's Implementation Flaw (`P_qwen: lib_1.py:598`)
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

#### Why Qwen's Self-Test Missed It
Qwen's Certifier authored 4 unit tests for `add_node`:
1. `test_add_node_registers_definition`
2. `test_add_node_with_dependencies`
3. `test_add_node_priority_stored`
4. `test_add_node_retries_stored`

Every single test initialized an empty DAG, added a node once, and verified properties on the fresh node. The Certifier never authored a scenario exercising the re-registration postcondition.

#### How Foreign Tests Caught It
Gemini 3.8 Flash authored:
```python
def test_re_register_node_replaces_definition_and_dependencies(self) -> None:
    dag.add_node("target", action=lambda: 1, dependencies=["dep1"])
    dag.add_node("target", action=lambda: 2, dependencies=["dep2"])
    self.assertEqual(dag.get_dependencies("target"), {"dep2"})
# FAILED: AssertionError: Items in the first set but not the second: 'dep1'
```

---

### Defect 3: Cross-Component State Desynchronization on Node Removal (`WaveScheduler`)

#### The Formal Contract (`low/dag_engine_lite_impl.pyi`)
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

#### Qwen's Implementation Flaw (`P_qwen: lib_1.py:773`)
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

#### Why Qwen's Self-Test Missed It
Qwen tested `dag.remove_node()` extensively in `TestDAGOperations` on the `DAG` class in isolation. It tested `WaveScheduler` in `TestWaveSchedulerOperations` on static graphs that were never mutated during the scheduler's lifecycle. It never authored an integration test combining dynamic graph removal with wave scheduler state queries.

#### How Foreign Tests Caught It
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

## 3. Theoretical Analysis: Why Single-Model Cleanroom Missed These Defects

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

### A. The Limits of Physical Isolation ($\mathcal{I} = 0$) Under Identical Weights ($\theta_{\text{synth}} = \theta_{\text{cert}}$)

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

### B. The Structural Coverage Illusion: Statement & Branch Reachability $\ne$ Permutation Coverage

A natural question arises: **Why didn't Cleanroom's Coverage Arbiter reject the implementation?** Cleanroom recorded 95.0% statement coverage and 90.0% branch coverage on Qwen's library!

This discrepancy exposes the fundamental flaw of relying exclusively on AST-based structural code coverage:

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
   **Coverage output**: Line 935 was executed 2 times. Both the `True` and `False` branches of `if attempt > 0` were fully covered. Statement coverage: 100%. Branch coverage: 100%.
   Yet the logic was completely broken for any action that recovered on attempt 1!

2. **The State-Space Permutation Blind Spot on Defect 2 and 3**:
   - `DAG.add_node` had 100% statement coverage because nodes were added in every test.
   - `WaveScheduler._sync_states` had 100% statement coverage because waves were scheduled in every test.
   - Structural coverage only records that code was executed; it does not measure whether the state-space transition graph $(\mathcal{S} \times \mathcal{A} \to \mathcal{S}')$ was explored across multi-action sequences (e.g. `add(A)` $\to$ `add(A, new_deps)` or `init_scheduler()` $\to$ `remove(B)` $\to$ `sync()`).

### C. The Upstream Scenario Derivation Bottleneck

Cleanroom's architectural integrity relies on the upstream pipeline:
$$\text{High} \longrightarrow \text{Planning} \longrightarrow \text{Scenarios} \longrightarrow \text{Low} \longrightarrow \text{Code / Tests}$$

In `benchmarks/parts/dag_engine_lite/scenarios/dag_engine_lite.md`, the concrete scenarios written for the task included 7 distinct journeys (linear DAG, cycle detection, missing dependencies, priority scheduling, skip-downstream propagation, critical path calculation, and runner reporting).

However:
- None of the 7 scenarios walked an action that failed once and recovered on retry.
- None of the 7 scenarios walked re-registering an existing node to modify its dependencies.
- None of the 7 scenarios walked dynamic graph deletion after scheduler initialization.

Because the scenario canvas contained these epistemic omissions, the formal contracts in `low/*.pyi` remained purely declarative docstrings without concrete operational walkthroughs. When the Certifier worker generated unit tests, it prioritized the explicit scenario journeys and the primary postconditions, leaving the edge-case docstrings unexercised.

---

## 4. Why Foreign Models Did Not Share the Blind Spots

When independent models authored test suites from the identical `low/*.pyi` specification, their differing training distributions, inductive biases, and reasoning heuristics generated radically different adversarial tests:

| Model | Underlying Inductive Bias | Edge Case Prioritized in Test Suite |
| :--- | :--- | :--- |
| **DeepSeek-V3 / Flash** | Execution-trace simulation & loop invariants | *Retry Recovery Invariant*: Specifically created an action closure that tracks invocation count and raises an error on attempts 0 and 1, succeeding on attempt 2, then asserted `retries_attempted == 2`. |
| **Gemini 3.8 Flash** | Idempotency & dynamic reconfiguration | *Graph Mutation Invariants*: Tested that re-adding a node replaces prior dependencies, and that removing a node cleans up incident edges and scheduler state. |
| **Gemini 4 Argon** | Architectural contract robustness | *Failure Policy & Lifecycle Invariants*: Asserted rigorous scheduler-to-runner state consistency under mixed failure policies. |

Because their cognitive priors were uncorrelated with Qwen's cognitive priors:
$$\mathcal{I}(\text{Prior}_{\text{gemini}}; \text{Prior}_{\text{qwen}}) \approx 0$$
The cross-model differential pass rate immediately plummeted, unmasking the defects that homogeneous self-testing could never detect.

---

## 5. Architectural Remedies for Cleanroom

To permanently close this vulnerability and prevent coincident cognitive blind spots from greenlighting defective code, Cleanroom incorporates three concrete architectural upgrades:

### 1. Mandatory Heterogeneous Role Ensembles (Baseline 4)
In production Cleanroom configurations, **the Synthesizer ($W_{\text{lib}}$) and the Certifier ($W_{\text{test}}$) must never share identical model weights**.
- Example Pairing: Synthesizer = `Qwen3.6-35B` (Tier 1 Local) $\times$ Certifier = `DeepSeek-V3` (Tier 2 Cloud) $\times$ Arbiter = `Gemini-Flash` (Tier 3 Frontier).
- By ensuring that $\theta_{\text{synth}} \ne \theta_{\text{cert}}$, the probability of coincident cognitive blind spots drops by orders of magnitude:
  $$P_{\text{coincident}}(\theta_1, \theta_2) \ll P_{\text{coincident}}(\theta_1, \theta_1)$$

### 2. Semantic Boundary & Mutation Testing (`mutmut`)
AST branch coverage must be augmented with automated mutation testing:
- Inject first-order boundary mutants into the synthesized library (e.g. changing `retries_attempted += 1` to `pass`, altering comparison operators, or retaining sets).
- Any mutant that survives the Certifier's test suite immediately halts Pass 2 verification with a **Mutation Gap Blame**, forcing the Certifier to author tests distinguishing between the mutant and the intended contract before the implementation is certified.

### 3. Automated Scenario Fuzzing & Permutation Matrices
In the upstream `scenarios/*.md` generation phase, Cleanroom's Scenario Arbiter must enforce state-space permutation coverage:
- For every state-mutating operation (such as `add_node` or `remove_node`), the scenario generator must automatically generate:
  1. Initial invocation on empty state.
  2. Redundant re-invocation on identical state (idempotency).
  3. Re-invocation with conflicting parameters (mutation/replacement).
  4. Inter-service lifecycle mutation (mutating component A while component B holds a reference).

---

## 6. Conclusion

The failure of Qwen's Cleanroom run on foreign independent tests is not evidence that double-blind isolation is ineffective; rather, it is definitive proof that **physical isolation alone is insufficient if the agents share identical cognitive biases**.

Cleanroom's double-blind boundary successfully eliminated cheating, coupling gaps, and tautological assertion tampering. However, achieving absolute defect suppression ($P_{\text{escape}} = 0$) requires **both physical isolation ($\mathcal{I} = 0$) AND model heterogeneity ($\theta_1 \ne \theta_2$)**, supported by adversarial mutation testing that transcends simple structural AST coverage.