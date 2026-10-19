# Cleanroom Empirical Benchmark Suite & Cross-Model Evaluation Design Document

> **Authoritative Technical & Empirical Benchmarking Specification**  
> This document specifies the comprehensive benchmarking architecture, cross-model evaluation framework, and empirical verification suite for Cleanroom.
> It operationalizes **Task 2 (Cross-Model Empirical Benchmarking Suite)** from [`todo.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/todo.md) and provides the complete experimental methodology required by the research paper: [`paper_submission_design_doc.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/paper_submission_design_doc.md).

---

## Table of Contents

1. [Executive Summary & Core Objectives](#1-executive-summary--core-objectives)
2. [Research Thesis & Theoretical Alignment with the Paper](#2-research-thesis--theoretical-alignment-with-the-paper)
   - [Formal Information Confinement & Double-Blind Invariant](#formal-information-confinement--double-blind-invariant)
   - [Task Asymmetry & Coincident Error Breaking](#task-asymmetry--coincident-error-breaking)
   - [The Fail-Safe Invariant: Non-Convergence as a Safety Victory](#the-fail-safe-invariant-non-convergence-as-a-safety-victory)
   - [The Hidden Benchmark Firewall: Defeating Goodhart's Law](#the-hidden-benchmark-firewall-defeating-goodharts-law)
3. [The 4-Tier Model Spectrum & Role Assignment Architecture](#3-the-4-tier-model-spectrum--role-assignment-architecture)
   - [Tier 1: Free Local Tier ($0 in Token Costs)](#tier-1-free-local-tier-0-in-token-costs)
   - [Tier 2: Budget Cloud Tier (Pennies per Benchmark Flight)](#tier-2-budget-cloud-tier-pennies-per-benchmark-flight)
   - [Tier 3: Mid-Tier Specialized Reasoners](#tier-3-mid-tier-specialized-reasoners)
   - [Tier 4: Frontier / Heavyweight Cloud Tier (Performance Ceilings)](#tier-4-frontier--heavyweight-cloud-tier-performance-ceilings)
   - [Core Benchmarking Matrix](#core-benchmarking-matrix)
   - [Operational Harness Mapping](#operational-harness-mapping)
4. [Paper Research Question (RQ) Alignment Matrix](#4-paper-research-question-rq-alignment-matrix)
   - [RQ1: Coincident Error Manifestation & Information Confinement](#rq1-coincident-error-manifestation--information-confinement)
   - [RQ2: Accidental Agreement Suppression & Branch-to-Spec Invariant Mining](#rq2-accidental-agreement-suppression--branch-to-spec-invariant-mining)
   - [RQ3: Modularity Strategy: Monolithic vs. Divided Implementation Units](#rq3-modularity-strategy-monolithic-vs-divided-implementation-units)
   - [RQ4: Compositional Soundness, Non-Contaminating Blame, & Fail-Safe Invariant](#rq4-compositional-soundness-non-contaminating-blame--fail-safe-invariant)
   - [RQ5: Autonomous Specification-as-Bytecode Evolution](#rq5-autonomous-specification-as-bytecode-evolution)
   - [RQ6: Concurrency Soundness: Adversarial Interleaving & Specialized Triage](#rq6-concurrency-soundness-adversarial-interleaving--specialized-triage)
   - [RQ7: Non-Functional Auditing, Goodhart's Law Evasion, & Performance Deadlocks](#rq7-non-functional-auditing-goodharts-law-evasion--performance-deadlocks)
5. [Subject Systems & Golden Benchmark Corpora](#5-subject-systems--golden-benchmark-corpora)
   - [CPython Standard Library Benchmark Suite](#cpython-standard-library-benchmark-suite)
   - [Mini-SQLite Relational Query & B-Tree Storage Engine](#mini-sqlite-relational-query--b-tree-storage-engine)
   - [Mini-Git Content-Addressable Object & DAG Engine](#mini-git-content-addressable-object--dag-engine)
   - [Deterministic Raft Distributed Consensus Engine](#deterministic-raft-distributed-consensus-engine)
   - [Cleanroom Self-Hosting Production Systems Corpus](#cleanroom-self-hosting-production-systems-corpus)
   - [Prior-Knowledge Probing Protocol](#prior-knowledge-probing-protocol)
   - [Principle of Domain-Specific Generator Preemption (Anti-Parser Rule)](#principle-of-domain-specific-generator-preemption-anti-parser-rule)
6. [Experimental Conditions & Baseline Controls](#6-experimental-conditions--baseline-controls)
   - [Baseline 1: Conventional "Vibe Coding" (Iterative Chat Loop)](#baseline-1-conventional-vibe-coding-iterative-chat-loop)
   - [Baseline 2: Single-Agent Joint Context TDD ($\mathcal{I} > 0$)](#baseline-2-single-agent-joint-context-tdd-mathcali--0)
   - [Baseline 3: Cleanroom Single-Model ($\mathcal{I} = 0$, Task Asymmetry)](#baseline-3-cleanroom-single-model-mathcali--0-task-asymmetry)
   - [Baseline 4: Cleanroom Heterogeneous Cross-Tier Ensembles](#baseline-4-cleanroom-heterogeneous-cross-tier-ensembles)
7. [Unified Metrics, Measurement Instruments & Telemetry](#7-unified-metrics-measurement-instruments--telemetry)
   - [Correctness, Defect Escape & Soundness Metrics](#correctness-defect-escape--soundness-metrics)
   - [Operational Economics, Token Efficiency & KV Cache Metrics](#operational-economics-token-efficiency--kv-cache-metrics)
   - [Systems, Concurrency & Quality Metrics](#systems-concurrency--quality-metrics)
8. [Automated Benchmark Tooling Architecture (`bin/evaluate_model_efficiency.py`)](#8-automated-benchmark-tooling-architecture-binevaluate_model_efficiencypy)
   - [CLI Interface & Execution Modes](#cli-interface--execution-modes)
   - [Pipeline Orchestration & Sandboxed Runner](#pipeline-orchestration--sandboxed-runner)
   - [Multi-Model Adapter Engine](#multi-model-adapter-engine)
   - [Artifact, JSON Telemetry & LaTeX Table Emitter](#artifact-json-telemetry--latex-table-emitter)
9. [Actionable Implementation Roadmap & Milestones](#9-actionable-implementation-roadmap--milestones)

---

## 1. Executive Summary & Core Objectives

The Cleanroom empirical evaluation must establish two decisive contributions:
1. **Academic & Theoretical Rigor (The Research Paper)**: Provide empirical validation for the seven core Research Questions (RQ1–RQ7) articulated in [`paper_submission_design_doc.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/paper_submission_design_doc.md), demonstrating that double-blind isolation ($\mathcal{I} = 0$), task asymmetry, and bipartite boundary contracts eliminate coincident errors, defeat Goodhart's Law, and guarantee a 100% fail-stop safety invariant without human code inspection.
2. **Industrial & Operational Economics (The Production Framework)**: Operationalize Task 2 from [`todo.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/todo.md) by implementing an automated, reproducible benchmarking harness (`bin/evaluate_model_efficiency.py`) that profiles token expenditure, prompt-cache hit rates, turn latencies, and monetary costs across a heterogeneous 4-tier model spectrum—from free local consumer hardware to frontier cloud reasoning engines.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                      CLEANROOM EMPIRICAL BENCHMARKING ARCHITECTURE                     │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   MODEL SPECTRUM (4 TIERS)             BENCHMARK HARNESS            SUBJECT SYSTEMS    │
│   ┌──────────────────────────┐         ┌───────────────────┐        ┌────────────────┐ │
│   │ Tier 1: Free Local ($0)  │ ──────► │                   │ ◄────► │ CPython Stdlib │ │
│   │ Qwen 35B MoE, 27B Dense  │         │                   │        └────────────────┘ │
│   ├──────────────────────────┤         │ evaluate_model_   │        ┌────────────────┐ │
│   │ Tier 2: Budget Cloud     │ ──────► │   efficiency.py   │ ◄────► │ Mini-SQLite    │ │
│   │ DeepSeek V4.1, Gemini 3.8│         │                   │        └────────────────┘ │
│   ├──────────────────────────┤         │ - Sandboxed env   │        ┌────────────────┐ │
│   │ Tier 3: Mid Reasoners    │ ──────► │ - chmod 444 masks │ ◄────► │ Mini-Git       │ │
│   │ o3-mini, Claude Sonnet   │         │ - KV cache logs   │        └────────────────┘ │
│   ├──────────────────────────┤         │ - Oracle diff     │        ┌────────────────┐ │
│   │ Tier 4: Frontier Cloud   │ ──────► │ - mutmut mutants  │ ◄────► │ Raft Consensus │ │
│   │ Gemini Argon, Opus, Sol  │         │ - Telemetry JSON  │        └────────────────┘ │
│   └──────────────────────────┘         └─────────┬─────────┘        ┌────────────────┐ │
│                                                  │                  │ Cleanroom Self │ │
│                                                  ▼                  └────────────────┘ │
│                                        ┌───────────────────┐                           │
│                                        │  RESEARCH PAPERS  │                           │
│                                        │  & COST AUDITS    │                           │
│                                        │  (RQ1-RQ7 Tables) │                           │
│                                        └───────────────────┘                           │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Research Thesis & Theoretical Alignment with the Paper

### Formal Information Confinement & Double-Blind Invariant

The fundamental theorem of Cleanroom synthesis asserts that the mutual information between the synthesized implementation code ($P$) and the synthesized verification test suite ($V$), conditioned on the low-level typed specification ($S = \langle \Sigma, \mathcal{C} \rangle$), must be strictly zero:

$$\mathcal{I}(P; V \mid S) = 0$$

Furthermore, during synthesis and compilation, neither agent may access external out-of-band data or the public internet:

$$\mathcal{I}(\{P, V\}; \text{Internet} \mid S) = 0$$

The empirical benchmark harness must physically enforce this condition via ephemeral OS sibling workspaces (`parts/workspace`) using read-only permission masks (`chmod 444`), verifying that neither agent can inspect sibling implementations or leak tokens across the synthesis boundary.

### Task Asymmetry & Coincident Error Breaking

Classical N-Version Programming (NVP) (Avizienis 1985) failed because independent human teams sharing problem requirements still committed identical, coincident errors (Knight & Leveson 1986). In neural code generation, generating multiple implementations ($P_1, P_2, \dots$) or voting across models repeats the Knight-Leveson trap.

Cleanroom breaks coincident errors through **Task Asymmetry**:
- The **Primal Task** (Library Code Synthesizer $\mathcal{S}$) executes a constructive synthesis mapping:
  $$\mathcal{S}: S \longrightarrow P \quad \left(X \to Y\right)$$
- The **Dual Task** (Verification Certifier $\mathcal{D}$) executes a predicate refutation mapping:
  $$\mathcal{D}: S \longrightarrow V \quad \left(X \times Y \to \mathbb{B}\right)$$

Under the Littlewood-Miller model of multi-version software failure, the joint failure probability is given by:

$$P(\text{Coincident Failure}) = \mathbb{E}[p(\mathcal{S})] \cdot \mathbb{E}[p(\mathcal{D})] + \operatorname{Cov}(p(\mathcal{S}), p(\mathcal{D}))$$

Because the output spaces, prompt templates, and computational tasks are fundamentally asymmetric, the covariance term becomes **negative** ($\operatorname{Cov}(p(\mathcal{S}), p(\mathcal{D})) \le 0$), suppressing coincident errors below the independence threshold.

### The Fail-Safe Invariant: Non-Convergence as a Safety Victory

A central tenet of Cleanroom is the shift from **Liveness** to **Safety**:
- Traditional DevAI loops prioritize liveness: forcing a conversation to output code at all costs, resulting in silent defect escapes.
- Cleanroom prioritizes safety: when specifications are contradictory, ambiguous, or ungrounded, the system must **fail-stop** via deterministic non-convergence:

$$P(\text{Compile to } \mathbf{CLEAN} \mid S \text{ is Contradictory}) = 0.0$$

The benchmark suite must empirically measure this invariant by injecting broken, ambiguous, and ungrounded contracts, validating 100% fail-stop non-convergence and 0% silent corrupt code generation.

### The Hidden Benchmark Firewall: Defeating Goodhart's Law

When LLM coding agents are exposed to raw execution profiles, flame graphs, or benchmark scores, they act as adversarial Goodhart optimizers: hardcoding inputs, stripping bounds checks, and omitting safety validations to minimize the proxy metric.

Cleanroom introduces the **Hidden Benchmark Firewall**:
$$\mathcal{I}(\text{Synthesis Agent}; \text{Profiler Harness}) = 0$$

Performance auditing is mediated exclusively through the Phase 2 Stateful Performance Auditor, which translates physical runtime bottlenecks into abstract architectural advice expressed strictly in declarative specification data invariants (e.g., zero-copy ring buffers, generator pipelines). The benchmark suite evaluates this via the **Goodhart Divergence Index ($GDI$)**:

$$GDI = \frac{\Delta \text{Benchmark Proxy Metric}}{\Delta \text{Out-of-Distribution True Workload Metric}}$$

A system resistant to metric gaming achieves $GDI \approx 1.0$, whereas unblinded agents display $GDI \gg 1.0$ ("tails coming apart").

---

## 3. The 4-Tier Model Spectrum & Role Assignment Architecture

The empirical benchmarking framework evaluates models across four distinct operational tiers, balancing zero-cost local execution, hyper-efficient cloud subagents, mid-tier structural reasoners, and frontier enterprise ceilings.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                             THE 4-TIER MODEL TAXONOMY                                  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   TIER 1: FREE LOCAL ($0)          TIER 2: BUDGET CLOUD (< $1/M)                       │
│   • Qwen 3.6 35B A3B (6-bit MoE)   • DeepSeek V4.1 Flash ($0.15 / $0.60)               │
│     Orchestrator, multi-step       • Gemini 3.8 Flash ($0.75 / $3.75)                  │
│   • Qwen 27B (4-bit Dense)           High-throughput workers, context scraping         │
│     Lightweight sanity tester                                                          │
│                                                                                        │
│   TIER 3: MID REASONERS ($1-$3/M)  TIER 4: FRONTIER CEILING ($2-$4/M)                  │
│   • OpenAI o3-mini ($1.10 / $4.40) • Gemini 4 Argon ($2.00 / $10.00, Vals Index)       │
│     Deadlock-free architect        • Claude Opus 5.5 / 5 ($4.00 / $20.00)              │
│   • Claude 3.5 / 3.7 Sonnet        • OpenAI gpt-6.1-sol ($2.00 / $10.00, Max Effort)   │
│     ($3.00 / $15.00) Gold standard • Meta Muse Wonder Full (~$4.00)                    │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Tier 1: Free Local Tier ($0 in Token Costs)

Designed for zero-marginal-cost execution, local continuous integration, air-gapped development, and stress-testing Cleanroom's architectural gatekeeper invariants against smaller parameter models.

> [!IMPORTANT]
> **Strict Local Runtime Standard**: Cleanroom relies **exclusively on `omlx`** for all local model execution on Apple Silicon. External inference engines (such as vLLM, llama.cpp, or Ollama) are omitted to maximize Apple Silicon unified memory bandwidth, native Metal acceleration, and seamless local OpenAI-compatible endpoint compatibility.

1. **Qwen 3.6 35B A3B (6-bit Quantization / Multi-Token Prediction - MTP)**:
   - *Architecture*: Sparse Mixture-of-Experts (MoE) running locally via **`omlx`** on Apple Silicon (M-series with 64GB+ unified memory).
   - *Framework Role*: Primary local orchestrator, multi-step planner, and local subagent driver. Preserves history traces, enforces structured function calling, and executes terminal workflows efficiently without memory overflow.
   - *Paper Significance*: Proves that Cleanroom's kernel-enforced double-blind isolation and two-pass verification gateway force even resource-constrained local models to converge on verified, zero-defect code without human developer intervention.

2. **Qwen 27B (4-bit Quantization / MTP)**:
   - *Architecture*: Dense local model running locally via **`omlx`** on Apple Silicon, optimized for high-speed local inference (> 45 tokens/sec).
   - *Framework Role*: High-speed local baseline, unit-test runner, code formatter, and lightweight sanity tester. Handles output parsing, docstring extraction, and basic utility loops without consuming cloud credits.

### Tier 2: Budget Cloud Tier (Pennies per Benchmark Flight)

High-throughput, hyper-economical cloud endpoints enabling massive parallel subagent dispatching, topological DAG wave exploration, and high-volume context analysis for pennies per benchmark flight.

1. **DeepSeek V4.1 Flash (Thinking Mode enabled)**:
   - *Pricing*: \$0.15 per 1M input tokens / \$0.60 per 1M output tokens.
   - *Capabilities*: Multi-step reasoning with thinking traces, native multi-token prediction, automatic context caching (reducing multi-turn input costs by up to 75%).
   - *Framework Role*: Primary low-cost cloud subagent driver, dual test certifier ($V$), and iterative implementation patcher. Matches older frontier models on multi-step tasks at a fraction of the cost.

2. **Gemini 3.8 Flash**:
   - *Pricing*: \$0.75 per 1M input tokens / \$3.75 per 1M output tokens.
   - *Capabilities*: Massive 1,000,000-token context window, high queries-per-minute (QPM) throughput ceilings, sub-second TTFT (Time to First Token).
   - *Framework Role*: Broad context analyzer, high-throughput subagent dispatcher, large repository dependency indexer, and high-speed Spec QA auditor.

### Tier 3: Mid-Tier Specialized Reasoners

Specialized reasoning and tool-invocation workhorses providing rigorous architectural control, deadlock-free plan decomposition, and gold-standard code patching.

1. **OpenAI o3-mini**:
   - *Pricing*: \$1.10 per 1M input tokens / \$4.40 per 1M output tokens.
   - *Capabilities*: Deliberative internal reasoning tokens, search-tree planning before tool invocation, structured output schema enforcement.
   - *Framework Role*: Structural architect control point, planning canvas formalizer, and deadlock-free decomposition validator. Tests whether hidden pre-computation prevents coordination deadlocks in multi-agent loops.

2. **Claude 3.5 / 3.7 Sonnet**:
   - *Pricing*: \$3.00 per 1M input tokens / \$15.00 per 1M output tokens.
   - *Capabilities*: Industry gold standard for developer agent tool use, multi-file code editing, AST structural compliance, and precise error recovery.
   - *Framework Role*: Primary operational benchmark, gold-standard code patcher, adversarial concurrency test generator ($\mathcal{D}_{\text{conc}}$), and specialized triage arbiter ($\mathcal{A}_{\text{triage}}$).

### Tier 4: Frontier / Heavyweight Cloud Tier (Performance Ceilings)

State-of-the-art enterprise frontier engines defining the theoretical performance ceiling for autonomous reasoning, macroscopic planning, and multi-agent coordination.

1. **Gemini 4 Argon**:
   - *Pricing*: \$2.00 per 1M input tokens / \$10.00 per 1M output tokens.
   - *Capabilities*: Google's frontier model for complex agentic workflows; leads benchmarks (e.g., Vals Index) for deep multi-agent loops, supported by a 1M-token output limit and ultra-low cache-read costs.
   - *Framework Role*: Enterprise agent lead, macro-architectural planner, high-output HLS author, and cross-package arbiter.

2. **Claude Opus 5.5 / Claude 5**:
   - *Pricing*: \$4.00 per 1M input tokens / \$20.00 per 1M output tokens.
   - *Capabilities*: Unsurpassed instruction fidelity across massive contexts, deep semantic reasoning, zero instruction drift across long subagent delegations.
   - *Framework Role*: Top-level macro planner, Zero-Execution Coordinator ceiling, and complex invariant arbiter.

3. **OpenAI gpt-6.1-sol (Max Effort)**:
   - *Pricing*: \$2.00 per 1M input tokens / \$10.00 per 1M output tokens.
   - *Capabilities*: Flagship reasoning model with maximum deliberation effort, deep verification trees, and recursive subagent spawning.
   - *Framework Role*: Frontier reasoning baseline for recursive synthesis, complex constraint solving, and cross-model validation.

4. **Meta Muse Wonder Full**:
   - *Pricing*: ~\$4.00 per 1M input tokens.
   - *Capabilities*: High-capacity open-weight frontier model evaluated in enterprise cloud deployment; advanced logic, mathematical reasoning, and diverse pre-training representation.
   - *Framework Role*: Cross-vendor control point to evaluate instruction following and contract compliance against Google, Anthropic, and OpenAI ecosystems.

---

### Strategic Focus for Tier 3 & Tier 4 Models: Two Premier Anchor Targets

> [!NOTE]
> **Economical Target Selection**: Due to API cost ceilings and operational efficiency, Tier 3 and Tier 4 models are **strictly evaluated against two high-leverage anchor benchmarks**, rather than running across the entire broad corpus. Tier 1 (`omlx`) and Tier 2 (DeepSeek / Gemini Flash) provide the continuous, high-volume execution across all components.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│               TIER 3 & TIER 4 SELECTIVE BENCHMARK EVALUATION MATRIX                    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   ANCHOR TARGET 1: Mini-SQLite Relational Query & B-Tree Storage Engine                │
│   • Domain: Complex stateful systems code (B-tree rebalancing, 3-valued NULLs, ACID)   │
│   • Golden Oracle: Canonical C sqlite3 binary (bit-for-bit differential verification)  │
│   • Evaluates: RQ3 (Modularity: Monolith vs. Divided Units) & RQ4 (Soundness & Blame)  │
│   • Models Tested: Claude 3.5/3.7 Sonnet, OpenAI o3-mini, Gemini 4 Argon, Claude Opus  │
│                                                                                        │
│   ANCHOR TARGET 2: CPython Algorithmic Systems Module (heapq & graphlib)               │
│   • Domain: Pure algorithmic contracts, cycle detection, and tie-breaking invariants   │
│   • Golden Oracle: Official CPython test suite (test.test_heapq, test.test_graphlib)   │
│   • Evaluates: RQ1 (Coincident Error Breaking) & RQ2 (Bipartite Contract Mining)       │
│   • Models Tested: Claude Sonnet, o3-mini, gpt-6.1-sol, Meta Muse Wonder Full          │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

1. **Anchor Target 1: Mini-SQLite Engine (Systems Focus)**
   - *Why It Matters*: Stateful systems software with pointer balancing, slotted page serialization, 3-valued boolean logic (`NULL = NULL` is NULL), and transactional rollback.
   - *Significance for Tiers 3 & 4*: Tests whether frontier reasoning eliminates architectural deadlocks, correctly decomposes multi-file transactions, and discovers subtle boundary edge cases without regression churn.
2. **Anchor Target 2: CPython Algorithmic Systems Module (`heapq` & `graphlib`) (Algorithmic Focus)**
   - *Why It Matters*: Demonstrates the "Specification Gap" against official Python documentation, testing whether frontier reasoning captures intricate invariants (such as Tarjan SCC cycle detection and custom heap comparator tie-breaks) in fewer turns than budget models.

---

### Core Benchmarking Matrix

The following matrix standardizes the operational role, execution harness, and financial cost across all candidate models:

| Tier | Model | Best Role in Framework | Input / 1M | Output / 1M | Harness Integration |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **Local ($0)** | **Qwen 3.6 35B A3B (MoE)** | Local Orchestrator & Multi-Step Planner | **Free** | **Free** | Loop Harness / **`omlx`** |
| **Local ($0)** | **Qwen 27B (Dense)** | Fast Code Formatter & Local Sanity Tester | **Free** | **Free** | Loop Harness / **`omlx`** |
| **Budget API** | **DeepSeek V4.1 Flash** | High-Volume Worker / Thinking Subagent | \$0.15 | \$0.60 | DSH JSON-RPC / Loop Harness |
| **Budget API** | **Gemini 3.8 Flash** | Broad Context Scraper / High-Volume Dispatcher | \$0.75 | \$3.75 | Antigravity / GenAI SDK |
| **Mid-Tier (Anchor)** | **OpenAI o3-mini** | Plan Decomposer & Deadlock-Free Architect | \$1.10 | \$4.40 | Loop Harness / OpenAI API |
| **Mid-Tier (Anchor)** | **Claude 3.5 / 3.7 Sonnet** | Gold Standard Code Patcher & Tool Invoker | \$3.00 | \$15.00 | Loop Harness / Anthropic API |
| **Frontier (Anchor)** | **Gemini 4 Argon** | Enterprise Agent Lead & High-Output Architect | \$2.00 | \$10.00 | Antigravity / GenAI SDK |
| **Frontier (Anchor)** | **Claude Opus 5.5 / 5** | Top-Level Macro Planner & Subagent Monitor | \$4.00 | \$20.00 | Loop Harness / Anthropic API |
| **Frontier (Anchor)** | **OpenAI gpt-6.1-sol** | Frontier Reasoning Baseline for Recursive Calls | \$2.00 | \$10.00 | Loop Harness / OpenAI API |
| **Frontier (Anchor)** | **Meta Muse Wonder Full** | Alternative Control for Code Generation & Logic | ~\$4.00 | ~\$16.00 | Loop Harness / Together / API |

---

### Operational Harness Mapping

To execute benchmarks deterministically across diverse platforms, Cleanroom maps models to runtime harnesses:

1. **Option 1: Custom In-Process Loop Harness (`--harness loop`) with `omlx`**:
   - Universal adapter for **Local Models (Qwen 35B / 27B)** via the local **`omlx`** server on Apple Silicon.
   - Direct API client driver for **OpenAI (o3-mini, gpt-6.1-sol)**, **Anthropic (Sonnet 3.5/3.7, Opus 5.5)**, and **Meta Muse Wonder Full**.
   - Drives deterministic multi-turn ReAct loop: prompt with active guide $\to$ tool invocation $\to$ deterministic verification gate (`bin/test`) $\to$ in-band metadata update.
2. **Option 4: Google Antigravity Subagent Harness**:
   - Native integration for **Gemini 3.8 Flash** and **Gemini 4 Argon**.
   - The coordinator executes zero code, issuing autonomous subagent invocations (`invoke_subagent`) bound to isolated sibling workspaces (`chmod 444`).
3. **Option 4: DeepSeek Harness (`dsh`) & Direct JSON-RPC**:
   - Native integration for **DeepSeek V4.1 Flash**.
   - Communicates over non-blocking UNIX domain sockets and HTTP JSON-RPC directly with the DSH server, completely bypassing `flock` lease locks on `session.lock`.

---

## 4. Paper Research Question (RQ) Alignment Matrix

The benchmark suite directly implements the experimental evaluation protocols required by the 7 Research Questions in [`paper_submission_design_doc.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/paper_submission_design_doc.md).

> [!TIP]
> **Time-Calibrated Lean Experimental Matrix**: To ensure benchmark flights finish quickly within practical time and API credit budgets while preserving full academic rigor, task scales are calibrated to **lean, high-leverage unit counts**:

| Research Question | Benchmark Scope & Subject System | Lean Scaled Units | Key Focus & Contrast |
| :--- | :--- | :---: | :--- |
| **RQ1: Coincident Errors** | CPython (`heapq`/`bisect`) & Mini-SQLite queries | **8 curated units** | Conditions 1–4; 8 Attractor State Ambiguity tests |
| **RQ2: Bipartite Contracts** | CPython (`heapq`/`graphlib`) & Mini-SQLite | **10 boundary cases** | Directional vs. Bipartite; 2 Algorithmic Guides ($\mathcal{G}$) |
| **RQ3: Modularity Strategy** | Mini-SQLite Engine (1 monolith vs. 3 `_impl` units) | **1 system (3 units)** | CUJ trap & mutation kill on 12 boundary edge cases |
| **RQ4: Fail-Safe Soundness** | Cleanroom DAG & Mini-SQLite stubs | **6 ungrounding trials** | 2 deletions, 2 erasures, 2 contradictions; $B \in \{1,2,4\}$ |
| **RQ5: Spec Evolution** | Mini-SQLite & CPython specs | **10 evolution tasks** | 4 additions, 3 alterations, 3 refactorings; 0 code edits |
| **RQ6: Concurrency Soundness** | Mini-SQLite Pager & Workspace Lock Manager | **6 concurrency defects** | 2 races, 2 deadlocks, 2 async yields; 15 mutants |
| **RQ7: Non-Functional Audit** | Mini-SQLite Event Stream Parser | **1 task (25k records)** | Hidden Firewall vs. Unblinded; 3 trials/condition |

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   TIME-CALIBRATED RESEARCH QUESTION EXPERIMENTAL MAPPING               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   RQ1: Coincident Errors (8 Units) ──► Attractor State Ambiguity (8 cases, I=0 vs I>0) │
│   RQ2: Bipartite Contracts (10 Cases) ──► Directional vs Bipartite; 2 Algo Guides (G)  │
│   RQ3: Modularity Strategy ──► Mini-SQLite (1 Monolith vs 3 Units; 12 Edge Cases)      │
│   RQ4: Compositional Soundness ──► 6 Controlled Spec Ungroundings; Batching B=1,2,4    │
│   RQ5: Autonomous Evolution ──► 10 Evolution Tasks (4 add, 3 alter, 3 refactor)        │
│   RQ6: Concurrency Soundness ──► 6 Injected Defects (2 races, 2 deadlocks, 2 async)    │
│   RQ7: Non-Functional Auditing ──► 25k Event Stream; Hidden Benchmark Firewall (GDI)   │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### RQ1: Coincident Error Manifestation & Information Confinement

- **Objective**: Empirically prove that:
  1. Unconfined LLMs ($\mathcal{I}(P; V \mid S) > 0$) replicate coincident errors on edge cases;
  2. Task asymmetry under double-blind isolation ($\mathcal{I} = 0$, `chmod 444`) breaks error correlation, even with a single foundation model;
  3. Smaller local models (Qwen 35B / 27B via `omlx`) achieve near-zero defect escape rates under Cleanroom gatekeeping.
- **Lean Scale**: **8 curated test units** (4 from CPython `heapq`/`bisect`, 4 from Mini-SQLite queries).
- **Conditions**:
  - *Condition 1 (Task Homogeneity)*: Model generates two implementations $P_1, P_2$ from spec $S$ (classical N-version programming).
  - *Condition 2 (Joint Context / Baseline 2)*: Single agent generates both `lib.py` and `test.py` in the same conversational context ($\mathcal{I} > 0$).
  - *Condition 3 (Cleanroom Single-Model)*: Same model assigned to asymmetric tasks in physically isolated workspaces ($W_{\text{lib}}, W_{\text{test}}$) under `chmod 444` ($\mathcal{I} = 0$).
  - *Condition 4 (Cleanroom Heterogeneous)*: Different models assigned to primal and dual roles (e.g., DeepSeek for $P$, Gemini for $V$).
- **Experiment 1 (The Attractor State Ambiguity Test)**:
  - **8 curated tasks** containing deliberate specification ambiguities (e.g., `<` vs. `<=`, empty collection returns).
  - Measures the shift from silent false convergence (shipping buggy code) to deterministic non-convergence / fail-stop with diagnostic blame.

### RQ2: Accidental Agreement Suppression & Branch-to-Spec Invariant Mining

- **Objective**: Prove that:
  1. The **Bipartite Boundary Principle** ($\langle [s^+], [s^-] \rangle$) eliminates accidental agreement at domain boundaries;
  2. **Branch-to-Specification Invariant Mining** extracts latent edge cases from initial CUJ implementations and lifts surviving mutants into formal contracts.
- **Lean Scale**: **10 curated boundary edge cases** (5 in CPython algorithmic modules, 5 in Mini-SQLite).
- **Conditions**:
  - *Regimen A (Directional / One-Sided)*: Contracts specify only the positive condition ($\Phi(x) \implies \text{SuccessResult}(x)$).
  - *Regimen B (Cleanroom Bipartite)*: Contracts mandate dual atomic slugs ($\langle [s^+]: \Phi(x) \implies \text{Success}, [s^-]: \neg \Phi(x) \implies \text{Error} \rangle$).
- **Experiment 2 (Weight Suppression Baseline / Algorithmic Guidance $\mathcal{G}$)**:
  - Evaluated on **2 classic algorithms** known to exhibit bugs in open-source training data:
    1. Tarjan's Strongly Connected Components (SCC) cycle detection in `graphlib`.
    2. B-tree page rebalancing & underflow merging in Mini-SQLite.
  - Group A: Spec only (model falls into training data attractor bug).
  - Group B: Spec paired with mathematically verified algorithmic guide ($\mathcal{G}$), neutralizing model weight bias.

### RQ3: Modularity Strategy: Monolithic vs. Divided Implementation Units

- **Objective**: Compare large monolithic implementation components against fine-grained collaborating `_impl` units:
  1. *The CUJ Trap*: Monoliths implement only Critical User Journeys (edge-case recall $\le 45\%$), while modular units capture $\ge 95\%$ of boundary edge cases.
  2. *Code Coverage Illusion*: Monoliths achieve $\ge 90\%$ statement coverage while missing boundary branches (mutation score $\le 40\%$), while modular units achieve 100% normalized coverage and $\ge 95\%$ mutation score.
  3. *Regression Churn*: Monoliths suffer 25–40% regression churn; modular units exhibit strictly 0.0% churn.
  4. *KV Cache & Token Economics*: Modular compilation re-uses cached static `.pyi` stubs, reducing marginal token burn by $> 75\%$.
- **Lean Subject System**: Focused squarely on **Mini-SQLite Relational Query & B-Tree Storage Engine** (~1,500 LOC):
  - *Condition Monolith*: `sqlite_engine_monolith_impl` (~1,500 LOC lib + 800 LOC test).
  - *Condition Modular Cleanroom*: 3 Decoupled Units (`btree_pager_impl` ~450 LOC, `table_heap_impl` ~350 LOC, `query_exec_impl` ~500 LOC).
- **Edge-Case Evaluation**: **12 high-impact domain boundary edge cases** (3-valued NULL comparisons, outer join row preservation on empty right tables, B-tree root page splits, secondary index key collision, transaction abort rollbacks).

### RQ4: Compositional Soundness, Non-Contaminating Blame, & Fail-Safe Invariant

- **Objective**:
  1. Prove that unit-verified modules compose soundly without whole-program integration tests (Theorems 2 & 3).
  2. Demonstrate that blame feedback leaks zero implementation code ($\mathcal{I}(P; V \mid \text{Blame}) = 0$).
  3. Validate the **Fail-Safe Invariant** via controlled ungrounding of working specifications.
- **Lean Scale**: **6 targeted controlled specification ungroundings**:
  - *2 Ungrounded Interface Deletions*: Strip imported method declarations or return types; verify Pass 1 static refusal before code synthesis.
  - *2 Boundary Contract Erasures*: Strip negative boundary slugs $[s^-]$; verify divergent completions or branch coverage failure.
  - *2 Injected Contradictory Invariants*: Inject conflicting postconditions; verify assertion deadlock and auditor blame escalation.
- **DAG Concurrency Batching**: Evaluated at batch sizes $B \in \{1, 2, 4\}$ on Mini-SQLite modular units, measuring KV prompt-cache hit rates and parallel wall-clock speedup.

### RQ5: Autonomous Specification-as-Bytecode Evolution

- **Objective**: Validate the core thesis: can software undergo continuous evolution purely through specification edits, with 100% of executable code synthesized without human intervention?
- **Lean Scale**: **10 realistic software evolution tasks** on Mini-SQLite and CPython specs:
  - *4 Feature Additions*: e.g., adding `COUNT(DISTINCT)` aggregation, `NULLS FIRST` sort order.
  - *3 Contract Modifications*: e.g., changing tie-breaking precedence, altering B-tree node split fill factor.
  - *3 Modularity Refactorings*: e.g., extracting secondary index cursor iterators into a distinct protocol.
- **Protocol**: Human edits strictly `low/*.pyi`; Cleanroom DAG detects dirty nodes; workers converge to `CLEAN`; verify 0 manual edits in `lib/` or `tests/`.

### RQ6: Concurrency Soundness: Adversarial Interleaving & Specialized Triage

- **Objective**: Evaluate the two-tier concurrency verification architecture (§2.10.4) and triage calculus (§4.3) across multi-threaded and asynchronous systems:
  1. *Concurrency Blind Spot*: Standard functional test generators ($\mathcal{D}_{\text{func}}$) achieve 100% statement coverage while missing data races and deadlocks.
  2. *Adversarial Interleaving Synthesis*: Concurrency certifier ($\mathcal{D}_{\text{conc}}$) synthesizes barrier stepping, phase latches, and conservation checks, exposing 100% of defects.
  3. *Specialized Triage Arbiter ($\mathcal{A}_{\text{triage}}$)*: Inspects thread stack traces via `sys._current_frames()`, extracts wait-for dependency cycles, and emits abstract lock-ordering blame ($\le 3$ turn convergence).
- **Lean Subject Systems**: Mini-SQLite Pager & Buffer Pool Latches, and Workspace Worktree Lock Manager.
- **Defect Suite**: **6 injected real-world concurrency defects** + **15 targeted concurrency mutants**:
  - *2 Lost Update Races*: dirty page counter updated non-atomically; lease counter increment unsynchronized.
  - *2 Lock Inversion Deadlocks*: buffer pool eviction lock vs. page latch inversion; worker task lock vs. lease lock.
  - *2 Async `await` Interleaving Races*: TOCTOU race across `await` in workspace idle check; async WAL frame flusher yielding control during header write.

### RQ7: Non-Functional Auditing, Goodhart's Law Evasion, & Performance Deadlocks

- **Objective**: Validate the Multi-Agent Auditing Matrix (§4.4) on non-functional optimization:
  1. *Goodhart's Law Evasion*: Proving the **Hidden Benchmark Firewall** ($\mathcal{I}(\text{Agent}; \text{Profiler}) = 0$) prevents metric gaming ($GDI \approx 1.04$), while unblinded agents overfit to proxies ($GDI = 4.82$) and collapse under out-of-distribution stress.
  2. *Stateful Architectural Guidance*: Guiding agents to transition from list accumulation to zero-copy streaming generators in $\le 3$ turns with 0% functional regression.
- **Lean Workload**: Scaled down to **25,000 JSON/CSV records** processed by the Mini-SQLite event stream parser under a $< 64\text{MB}$ memory ceiling, evaluated across 3 conditions with **3 trials each** (total 9 flights).

---

## 5. Subject Systems & Golden Benchmark Corpora

To eliminate evaluation bias, Cleanroom benchmarks systems software equipped with **pre-existing, independent ground-truth oracles**:

| Benchmark Suite | Domain & Key Challenges | Golden Oracle | Verification Method |
| :--- | :--- | :--- | :--- |
| **CPython Standard Library** | Algorithmic edge cases: `heapq`, `bisect`, `fnmatch`, `difflib`, `graphlib` | Canonical CPython test suite (`test.test_*`) | Differential execution against official test suite; Spec Gap analysis |
| **Mini-SQLite Engine** | Relational algebra, B-trees, 3-valued NULLs, ACID rollback, buffer pool | Canonical C `sqlite3` binary | Bit-for-bit differential SQL query batches, error codes, row orders |
| **Mini-Git Object DAG** | Content-addressable hashing, octal tree sorting, LCA commit reachability | Canonical `git` CLI & `libgit2` | `git fsck --full`, differential `git log`, `git cat-file`, `git merge-base` |
| **Raft Distributed Consensus** | Leader election, log compaction, snapshot boundaries, split votes | TLA+ model traces & `PySyncObj` | Differential execution under simulated packet drops & partitions |
| **Cleanroom Self-Hosting** | Compiler, AST linkers, DAG scheduler, sandbox runtime (11 packages, ~15k LOC) | Self-hosting compilation suite (`bin/test`) | Closed-world AST linking, 100% statement coverage, 0 Pyright errors |

### CPython Standard Library Benchmark Suite

The CPython Standard Library suite serves as the foundational algorithmic benchmark:
- **`heapq`**: Binary heap priority queues, custom key tie-breaking, heap invariant maintenance.
- **`bisect`**: Bisection search and insertion, boundary indexing on custom key extractors.
- **`fnmatch`**: Shell-style wildcard pattern matching, regex compilation, escape sequence handling.
- **`difflib`**: Sequence matcher, Myers diff heuristic, ratio calculations.
- **`graphlib`**: Topological sorting, cycle detection, dynamic node readiness propagation.

**Specification Gap Analysis**:
Official Python documentation was written for human developers and relies on unstated assumptions. Comparing reverse-engineered, contract-complete Cleanroom specifications against official Python documentation reveals:
1. *Omitted Boundary Conditions*: Exception types on empty collections, tie-breaking behavior.
2. *Implicit Type Coercions & Sentinels*: Behavior on unorderable types, generator exhaustion.
3. *Unstated Invariants*: Pre- and post-conditions left implicit in prose.

### Mini-SQLite Relational Query & B-Tree Storage Engine

Synthesizes a relational engine in Python:
- B-tree page splits, balance-after-delete, slotted page offsets.
- Relational scan, filter, projection, hash/nested-loop inner and left outer join.
- 3-valued boolean logic (`NULL = NULL` is NULL, `NULL IS NULL` is TRUE).
- Atomic transaction commit and rollback via shadow pager frames.

### Mini-Git Content-Addressable Object & DAG Engine

Synthesizes Git core internals:
- Object storage: Blob, Tree, Commit, and Tag serialization with zlib compression.
- Content-addressable SHA-1 / SHA-256 object store.
- Canonical octal tree entry sorting (directories sorted as if possessing a trailing `/`).
- Directed Acyclic Graph traversal and Lowest Common Ancestor (LCA) merge-base resolution.

### Deterministic Raft Distributed Consensus Engine

Synthesizes Raft distributed consensus:
- Leader election, randomized election timers, term step-downs.
- AppendEntries RPC log replication, commit index progression.
- Snapshot creation and log compaction truncation boundaries.
- Resilient to out-of-order messages, duplicated RPCs, and simulated network partitions.

### Cleanroom Self-Hosting Production Systems Corpus

The ultimate end-to-end integration benchmark: compiling Cleanroom with Cleanroom.
- **11 core packages, 50+ units, ~15,000 LOC of verified Python systems code**.
- Evaluates the production DAG scheduler (`parts/dag`), workspace provisioner (`parts/workspace`), AST linkers, in-band metadata parser (`parts/metadata`), and subagent coordinator (`parts/subagent`).

### Prior-Knowledge Probing Protocol

To isolate specification grounding from pre-training memorization:
1. **Unconditioned Prior Probing**: Query model without specs: *"Provide exact method signatures, exceptions, and edge-case behaviors for module X."* Quantify weight hallucinations and unstated assumptions.
2. **Conditioned Cleanroom Synthesis**: Provide formal Cleanroom specification $S = \langle \Sigma, \mathcal{C} \rangle$ under Double Hermetic Confinement.
3. **Adherence & Disproof of Contamination**: Verify that synthesized implementation $P$ and certifier $V$ conform 100% to provided contracts, abandoning hallucinated priors. Inject arbitrary contract mutations (e.g., inverting comparison tie-breaking) and confirm models adhere strictly to the mutated spec.

### Principle of Domain-Specific Generator Preemption (Anti-Parser Rule)

A foundational architectural policy in Cleanroom:
> **Rule**: *Whenever a deterministic domain-specific compiler or generator exists (e.g., ANTLR for grammars, RE2 for regexes, protobuf compilers for IDLs), developers MUST use it.*

Synthesizing parser tables or regex engines with an LLM is an anti-pattern. Therefore, **grammar parsers are explicitly excluded from the benchmark suite**. Cleanroom benchmarks focus exclusively on stateful systems software that cannot be generated by classical domain-specific compilers.

---

## 6. Experimental Conditions & Baseline Controls

To evaluate Cleanroom's contributions rigorously against standard industry practices, all benchmark tasks are evaluated across four comparative conditions:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                             FOUR EXPERIMENTAL CONDITIONS                               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   BASELINE 1: Vibe Coding (Interactive Chat)                                           │
│   • Developer prompts LLM with natural language requirements.                          │
│   • Runs code manually, pastes errors back in conversational loop.                     │
│   • Shared unconfined context; high defect escape rate.                                │
│                                                                                        │
│   BASELINE 2: Single-Agent Joint Context TDD (I > 0)                                   │
│   • Single LLM generates both lib.py and tests/*_test.py from spec in same context.    │
│   • Tests execute in loop; model self-patches until tests turn green.                  │
│   • Subject to coincident errors and tautological self-affirmation.                    │
│                                                                                        │
│   BASELINE 3: Cleanroom Single-Model (I = 0, Task Asymmetry)                           │
│   • Same model assigned to asymmetric tasks in isolated sibling workspaces.            │
│   • Synthesizer (X -> Y) in W_lib; Certifier (X x Y -> B) in W_test (chmod 444).       │
│   • Gateway enforces AST coverage, closed-world Pyright, and blame isolation.          │
│                                                                                        │
│   BASELINE 4: Cleanroom Heterogeneous Cross-Tier Ensembles                             │
│   • Frontier model as Coordinator / Spec QA Arbiter.                                   │
│   • Budget Cloud or Local models as Implementation & Test Workers.                     │
│   • Maximizes cost efficiency while guaranteeing zero defect escape.                   │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

1. **Baseline 1: Conventional "Vibe Coding"**:
   - Reflects the predominant mode of developer AI usage: conversational prompting from informal intent.
   - Measures defect escape, silent bug propagation, and high human debugging overhead.
2. **Baseline 2: Single-Agent Joint Context TDD ($\mathcal{I} > 0$)**:
   - Reflects modern agentic coding benchmarks (e.g., SWE-bench, Devin-style loops) where a single agent authors both code and tests.
   - Captures the Fatal Contamination Trap: mutual confirmation bias where the test suite certifies the implementation's flawed assumptions.
3. **Baseline 3: Cleanroom Single-Model ($\mathcal{I} = 0$, Task Asymmetry)**:
   - Evaluates Cleanroom's pure architectural mechanism by holding the model constant.
   - Demonstrates that physical isolation and task asymmetry alone suppress coincident errors and enforce the fail-safe invariant.
4. **Baseline 4: Cleanroom Heterogeneous Cross-Tier Ensembles**:
   - Evaluates real-world production deployment: pairing cost-effective models (Tier 1 Local or Tier 2 Budget Cloud) with Tier 3/4 Arbiters.
   - Quantifies the optimal frontier-to-worker economic trade-off.

---

## 7. Unified Metrics, Measurement Instruments & Telemetry

### Correctness, Defect Escape & Soundness Metrics

| Metric | Symbol | Definition & Formula | Target Value |
| :--- | :---: | :--- | :---: |
| **Defect Escape Rate** | $P_{\text{escape}}$ | $\frac{|\text{Units Passing } V \text{ but Failing } V_{\text{oracle}}| fault}{|\text{Total Units Passing } V|}$ | **$0.0\%$** |
| **Coincident Error Rate** | $P_{\text{coincident}}$ | $P(V \text{ passes } P \mid V_{\text{oracle}} \text{ fails } P)$ | **$0.0\%$** |
| **Discordant Failure Rate** | $P_{\text{discordant}}$ | Percentage of imperfect runs where $P$ and $V$ disagreeably fail, halting Pass 2 | **$100.0\%$** |
| **Accidental Agreement Rate** | $P_{\text{accidental}}$ | $\frac{|\text{Boundary Mutants where } V(P_{\text{mutant}}) = \mathbf{PASS}|}{|\text{Total Injected Boundary Mutants}|}$ | **$0.0\%$** |
| **Boundary Mutation Score** | $MS_{\text{boundary}}$ | Percentage of first-order boundary mutants killed by $V$ (via `mutmut`) | **$\ge 95.0\%$** |
| **Concurrency Defect Escape** | $P_{\text{conc\_escape}}$ | $\frac{|\text{Injected Concurrency Defects Not Detected by } V|}{|\text{Total Injected Concurrency Defects}|}$ | **$0.0\%$** |
| **Concurrency Mutation Score** | $MS_{\text{conc}}$ | Percentage of concurrency mutants killed (lock removal, inversion, yield injection) | **$\ge 95.0\%$** |
| **Fail-Safe Halting Rate** | $P_{\text{fail\_stop}}$ | Percentage of flawed / ungrounded specs that halt fail-stop with diagnostic blame | **$100.0\%$** |
| **Silent Defect Emission Rate** | $P_{\text{silent}}$ | Percentage of flawed specs that erroneously compile to `CLEAN` | **$0.0\%$** |

### Operational Economics, Token Efficiency & KV Cache Metrics

| Metric | Symbol | Definition & Formula | Unit |
| :--- | :---: | :--- | :---: |
| **Convergence Turns** | $T_{\text{conv}}$ | Iterative compilation rounds required to reach certified $\mathbf{CLEAN}$ | Integer turns |
| **Gross Token Expenditure** | $\text{Tokens}_{\text{total}}$ | Total input tokens + output tokens consumed per converged target | Tokens |
| **KV Cache Hit Rate** | $\text{Cache}_{\text{hit}}$ | $\frac{\text{Cached Input Tokens}}{\text{Total Input Tokens}}$ on static `.pyi` interface stubs | Percentage ($\%$) |
| **Monetary Cost per Target** | $\text{Cost}_{\text{target}}$ | Total API cost consumed per certified unit | \$ USD |
| **Cost per Certified LOC** | $\$ / \text{LOC}$ | $\frac{\text{Total Compilation Cost}}{\text{Verified Lines of Target Executable Code}}$ | \$ USD / LOC |
| **Wall-Clock Latency** | $t_{\text{wall}}$ | End-to-end elapsed time from dirty trigger to `CLEAN` stamp | Seconds |
| **Regression Churn Rate** | $R_{\text{churn}}$ | Percentage of turns where fixing defect $A$ introduces new defect in feature $B$ | Percentage ($\%$) |

### Systems, Concurrency & Quality Metrics

| Metric | Symbol | Definition & Formula | Target Value |
| :--- | :---: | :--- | :---: |
| **Goodhart Divergence Index** | $GDI$ | $\frac{\Delta \text{Benchmark Proxy Metric}}{\Delta \text{Out-of-Distribution True Workload Metric}}$ | **$0.95 \le GDI \le 1.05$** |
| **Concurrency Triage Precision** | $\text{Prec}_{\text{triage}}$ | $\frac{|\text{Blame Messages Identifying Exact Synchronization Defect}|}{|\text{Total Concurrency Blame Messages Emitted}|}$ | **$\ge 95.0\%$** |
| **Blame Information Leakage** | $\mathcal{I}_{\text{blame}}$ | Mutual information / token n-gram overlap between $P$ and $V$ via blame channel | **$0.0\text{ bits}$** |
| **Spec-to-Code Density** | $\rho_{\text{density}}$ | $\frac{\text{Lines of Specification } S}{\text{Lines of Target Code } P + \text{Lines of Tests } V}$ | **$\rho \ll 1.0$** |
| **DAG Parallel Speedup** | $S_B$ | Speedup factor when compiling DAG with batch concurrency $B \in \{1, 2, 4, 8\}$ | Ratio ($> 1.0$) |

---

## 8. Automated Benchmark Tooling Architecture (`bin/evaluate_model_efficiency.py`)

The automated benchmarking toolchain operationalizes Task 2 from [`todo.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/todo.md) as a production CLI utility:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   BENCHMARK TOOLING PIPELINE (evaluate_model_efficiency.py)            │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   CLI INVOCATION                                                                       │
│   uv run bin/evaluate_model_efficiency.py --suite=cpython --tier=budget --rq=rq1       │
│                                                                                        │
│   1. MATRIX INITIALIZATION & TARGET PROVISIONING                                       │
│      - Discovers active target specifications (e.g., parts/storage, cpython_heapq)     │
│      - Provisions ephemeral sandboxes (../role_workspaces/bench_<run_id>/)             │
│      - Applies OS chmod 444 masks to upstream stubs; sets isolated PYTHONPATH          │
│                                                                                        │
│   2. MULTI-MODEL ADAPTER DISPATCH                                                      │
│      - Option 1 (Loop Harness): Local Ollama/vLLM, OpenAI, Anthropic, Meta endpoints   │
│      - Option 4 (Antigravity): Gemini Flash/Argon via subagent coordinator directive   │
│      - Option 4 (DSH): DeepSeek V4.1 via direct JSON-RPC socket streaming              │
│                                                                                        │
│   3. TWO-PASS GATEWAY VERIFICATION & MUTATION RUNNER                                   │
│      - Pass 1: Static syntax, Pyright type check, closed-world symbol linking          │
│      - Pass 2: Hermetic test execution, 100% normalized statement coverage             │
│      - Differential Oracle: Diff against C sqlite3, native git, CPython test suite     │
│      - Mutation Testing: Injects first-order boundary mutants via mutmut               │
│                                                                                        │
│   4. TELEMETRY AGGREGATION & REPORT EMISSION                                           │
│      - Records tokens, turn latency, KV cache hits, cost per LOC, defect escape        │
│      - Emits structured JSON event logs (logs/benchmarks/<run_id>.json)                │
│      - Generates comparative Markdown & publication-ready LaTeX tables                 │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### CLI Interface & Execution Modes

The benchmarking CLI provides fine-grained controls for time-calibrated experimental flights:

```bash
# High-volume execution across budget and local models on CPython Standard Library
uv run bin/evaluate_model_efficiency.py \
  --suite=cpython \
  --models=qwen-35b,deepseek-v4,gemini-3.8 \
  --rq=rq1 \
  --units=8 \
  --output=reports/cpython_rq1_budget.md

# Targeted Anchor Run for Tier 3 & Tier 4 on Mini-SQLite (Anchor Target 1)
uv run bin/evaluate_model_efficiency.py \
  --suite=mini-sqlite \
  --anchor=systems \
  --models=o3-mini,sonnet-3.7,gemini-4-argon,claude-opus \
  --rq=rq3 \
  --compare-monolith \
  --measure-cache-hits

# Targeted Anchor Run for Tier 3 & Tier 4 on CPython Algorithmic Systems (Anchor Target 2)
uv run bin/evaluate_model_efficiency.py \
  --suite=cpython \
  --anchor=algorithmic \
  --models=o3-mini,sonnet-3.7,gpt-6.1-sol,meta-muse \
  --rq=rq2 \
  --units=10 \
  --mutation-testing

# Evaluate Controlled Spec Ungroundings (RQ4) with lean 6 injections
uv run bin/evaluate_model_efficiency.py \
  --suite=mini-sqlite \
  --rq=rq4 \
  --ungrounded-injections=6 \
  --batch-sizes=1,2,4

# Evaluate Concurrency Soundness (RQ6) with lean 6 defects and specialized triage
uv run bin/evaluate_model_efficiency.py \
  --suite=concurrent-sqlite \
  --rq=rq6 \
  --concurrency-defects=6 \
  --mutation-testing
```

### Pipeline Orchestration & Sandboxed Runner

1. **Workspace Assembly (`parts/workspace`)**:
   - Provisions isolated sibling directories under `../role_workspaces/bench_<timestamp>_<target>/`.
   - Mounts upstream specifications as read-only copies (`chmod 444`).
   - Ensures strict double-blind isolation ($\mathcal{I}(P; V \mid S) = 0$): implementation workers cannot see test files, and test workers cannot see implementation files.
2. **Deterministic Verification Gate (`parts/tools`)**:
   - Runs `tool_linter.py` for spec syntax and closed-world linking.
   - Runs `tool_pyright.py` for type checking against `pyright_spec.json`.
   - Runs `tool_coverage.py` to enforce 100% statement and branch coverage.
   - Runs differential oracle verification against pre-existing golden binaries.
3. **Mutation Testing Integration**:
   - Integrates with `mutmut` to automatically inject boundary mutations and compute $MS_{\text{boundary}}$.
   - Injects concurrency mutations (lock removals, inversions, async yields) for $MS_{\text{conc}}$.

### Multi-Model Adapter Engine

The adapter engine abstracts underlying model communication protocols:
- **`OmlxAdapter`**: Connects directly to the local **`omlx`** server on Apple Silicon (hosting Qwen 3.6 35B MoE and Qwen 27B Dense), tracking memory residency and token throughput over local HTTP JSON endpoints.
- **`DeepSeekAdapter`**: Connects directly to DeepSeek V4.1 via DSH JSON-RPC or direct API, logging cache-read vs. cache-write tokens.
- **`GeminiAdapter`**: Communicates with Gemini 3.8 Flash and Gemini 4 Argon via Google Antigravity or `google-genai` SDK, tracking 1M-context prompt caches.
- **`OpenAIAdapter` / `AnthropicAdapter`**: Drives o3-mini, gpt-6.1-sol, Claude Sonnet 3.5/3.7, and Claude Opus 5.5, tracking reasoning tokens and tool invocations.

### Artifact, JSON Telemetry & LaTeX Table Emitter

Every benchmarking run produces:
1. **Raw Telemetry Stream (`logs/benchmarks/<run_id>.json`)**: Turn-by-turn event logs recording model prompts, tool responses, token counts, execution latency, and verification outcomes.
2. **Markdown Evaluation Report (`reports/<run_id>.md`)**: Human-readable comparative report with executive summaries, cost analysis, and pass/fail breakdowns.
3. **Publication-Ready LaTeX Tables (`reports/latex/rq<N>_table.tex`)**: Formatted LaTeX tables ready for direct inclusion in the research paper submission.

---

## 9. Actionable Implementation Roadmap & Milestones

The cross-model benchmarking suite will be executed in five sequential phases:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        BENCHMARKING IMPLEMENTATION ROADMAP                             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   PHASE 1: Harness Tooling & Multi-Model Adapters (Days 1-2)                          │
│   • Implement bin/evaluate_model_efficiency.py with omlx, DSH, Antigravity adapters.   │
│   • Validate local omlx endpoint streaming for Qwen 35B and 27B models.                │
│   • Configure model configs in model_configs/ and verify mutmut runner integration.    │
│                                                                                        │
│   PHASE 2: CPython Stdlib & Prior-Knowledge Probing (RQ1, RQ2) (Days 3-4)              │
│   • Prior-Knowledge Probing across models on heapq, bisect, fnmatch.                   │
│   • Execute lean 8-unit Attractor State Ambiguity Test across 4 conditions.            │
│   • Anchor Run: Claude Sonnet, o3-mini, and gpt-6.1-sol on Anchor Target 2.            │
│                                                                                        │
│   PHASE 3: Mini-SQLite Systems Benchmark (RQ3, RQ4) (Days 5-7)                         │
│   • Anchor Run: Gemini 4 Argon, Claude Opus, o3-mini on Mini-SQLite (Anchor Target 1). │
│   • Compare Monolith vs. 3 Divided Units on 12 boundary edge cases.                    │
│   • Execute 6 controlled spec ungroundings (2 deletions, 2 erasures, 2 contradictions).│
│   • Benchmark DAG batching speedup (B = 1, 2, 4) and KV prompt-cache efficiency.       │
│                                                                                        │
│   PHASE 4: Concurrency & Non-Functional Benchmarks (RQ6, RQ7) (Days 8-9)               │
│   • Inject 6 concurrency defects into SQLite buffer pool & Workspace lock manager.     │
│   • Evaluate D_conc + A_triage vs. generic auditors; verify wait-for cycle extraction. │
│   • Execute Goodhart's Law evaluation behind Hidden Benchmark Firewall (25k events).   │
│                                                                                        │
│   PHASE 5: Telemetry Consolidation & Paper Table Generation (Day 10)                   │
│   • Aggregate JSON event traces into cross-tier cost and efficiency matrices.          │
│   • Generate publication-ready LaTeX tables for paper Sections 5.3–5.9.                │
│   • Finalize benchmarking documentation in todo.md and design-docs/README.md.          │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Milestone Deliverables

- [ ] **Milestone 1: Harness Architecture Completed**
  - `bin/evaluate_model_efficiency.py` implemented and verified under `uv`.
  - Adapters operational for Local `omlx` (Qwen), DeepSeek (DSH), Gemini (Antigravity), OpenAI, and Anthropic.
- [ ] **Milestone 2: RQ1 & RQ2 Empirical Data Captured**
  - Prior-Knowledge Probing dataset published.
  - Coincident error rates and Attractor State ambiguity results on 8 lean units synthesized into LaTeX tables.
  - Tier 3/4 baseline captured on Anchor Target 2 (CPython algorithmic systems).
- [ ] **Milestone 3: RQ3 & RQ4 Systems Data Captured**
  - Monolith vs. 3 Divided `_impl` units metrics captured for Mini-SQLite across 12 boundary edge cases.
  - Tier 3/4 baseline captured on Anchor Target 1 (Mini-SQLite).
  - 100% fail-stop verification demonstrated across 6 controlled ungrounding injections.
- [ ] **Milestone 4: RQ6 & RQ7 Specialized Auditing Data Captured**
  - Concurrency triage precision and deadlock cycle extraction verified on 6 concurrency defects.
  - Goodhart Divergence Index ($GDI \approx 1.04$) validated on 25k event stream workload.
- [ ] **Milestone 5: Authoritative Paper Tables & Documentation Completed**
  - All empirical evaluation sections in [`paper_submission_design_doc.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/paper_submission_design_doc.md) populated with verified metrics.
  - Master operational documentation updated in [`todo.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/todo.md) and [`design-docs/README.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/README.md).
