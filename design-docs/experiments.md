# Autofab Experiment Framework & Conditional Specification Architecture

## 1. Executive Summary & Vision

In empirical software engineering and autonomous multi-agent systems, rigorous scientific progress requires evaluating novel methodologies, information filters, and prompt architectures against established baselines under identical environmental conditions. Without a structured experimentation framework, researchers and developers face severe operational failure modes:
1. **Stealth Regressions**: Modifying production prompts, guides, or verification tools directly breaks existing baselines and invalidates historical comparison benchmarks.
2. **File Duplication Sprawl**: Cloning separate versions of guides (e.g. `qa.md` vs `qa_structured_blame.md`) or specifications introduces severe maintenance drift and violates Cleanroom's Single Source of Truth invariant.
3. **Instruction Leakage & Contamination**: If experimental rules or syntax are visible to baseline agents, models suffer cognitive confusion or prematurely adopt experimental behaviors during control flights.
4. **Ad-hoc Patching**: Trying to conditionally branch behavior via ad-hoc monkey-patching or string replacement in shell scripts leads to brittle, untestable pipelines.

The **Autofab Experiment Framework** provides a first-class, declarative infrastructure for running controlled experiments across the entire repository. Its cornerstone is the **Conditional Markdown Preprocessor**, which allows specifications (`high/*.md`, `planning/*.md`), companion guides (`guides/*.md`), and workspace instructions (`AGENTS.md`) to define conditional content blocks evaluated dynamically during workspace provisioning and flight execution.

```
                               CANONICAL REPOSITORY PLANE
                                           │
                     ┌─────────────────────┴─────────────────────┐
                     ▼                                           ▼
             Markdown Files (.md)                        Python Code (.py, .pyi)
    <!-- if experiment:structured_blame -->         if is_experiment_active("structured_blame"):
       [Structured Blame Instructions]                 [Structured Blame Validation Engine]
    <!-- else -->                                   else:
       [Legacy Paragraph Instructions]                 [Legacy Paragraph Validation Engine]
    <!-- endif -->
                     │                                           │
                     └─────────────────────┬─────────────────────┘
                                           │
                       WORKSPACE MATERIALIZATION / EXECUTION
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │       ACTIVE EXPERIMENT: structured_blame     │
                    │  - Materializes pure experimental text       │
                    │  - Evaluates experimental code branches      │
                    │  - Archives to: <model>-structured-blame/    │
                    └──────────────────────────────────────────────┘
```

---

## 2. Core Architectural Invariants

### Invariant 1: Single Source of Truth (No Sibling File Cloning)
- There must never be separate duplicate files for experiments (e.g., `guides/qa_exp.md` or `high/engine_v2.md`).
- All behavioral variations, guide amendments, and specification contracts for an experiment reside within the single canonical file using declarative conditional directives.

### Invariant 2: Total Epistemic Isolation (Zero Cross-Condition Contamination)
- An agent executing under Condition A (Baseline) must NEVER observe experimental syntax, tokens, or directives (`<!-- if experiment:... -->`) in its provisioned workspace.
- An agent executing under Condition B (Experiment) must receive pure, cohesive, and unambiguous instructions tailored strictly to Condition B.
- Directives and inactive branches are completely stripped during workspace materialization.

### Invariant 3: Reversible Zero-Debt Graduation & Rollback
- If an experiment succeeds and graduates to the canonical standard, retiring the experiment requires simply deleting the conditional directives and retaining the winning branch.
- If an experiment is rejected, deleting the directive blocks cleanly restores the original baseline with zero residual side effects.

### Invariant 4: First-Class Benchmark Result Provenance
- Benchmark results, synthesized code artifacts, test suites, and event logs produced under an experiment must be archived in distinctly qualified directories (`benchmarks/results/<suite>/<model>-<experiment>/`).
- Experimental flights must never overwrite or collide with baseline control runs.

---

## 3. Conditional Markdown Specification Directives: CommonMark Grounding

### The CommonMark HTML Comment Standard

In Autofab, Markdown documents strictly follow the **CommonMark specification (v0.31.2)** and GitHub-Flavored Markdown (GFM), as formalized in [`autofab/parts/core/high/commonmark_ext.md`](file:///Users/seanmcdirmid/projects/cleanroom/autofab/parts/core/high/commonmark_ext.md) and [`design-docs/template_format.md`](file:///Users/seanmcdirmid/projects/cleanroom/design-docs/template_format.md).

A common question is: *Should we use CommonMark or HTML comments?*
**HTML comments *are* CommonMark.**

Standard CommonMark has no native conditional syntax (no `if` statements). Under the official CommonMark specification:
- **Section 4.6 (HTML Blocks, Type 2)**: Defines block-level comments beginning with `<!--` and ending with `-->` as valid structural blocks that parsers preserve without parsing internal text as markdown markup.
- **Section 6.8 (Raw HTML)**: Defines inline HTML comments that can be embedded anywhere within text lines without breaking inline syntax.

### Why CommonMark HTML Comments Are Strictly Superior to Alternatives

| Approach | Formatting & AST Safety | Viewer Preview Behavior | Linter Compatibility | LLM Prompt Safety |
| :--- | :--- | :--- | :--- | :--- |
| **CommonMark HTML Comments (`<!-- if ... -->`)** | **100% Safe**: Prettier, `mdformat`, and AST parsers treat them as intact comment blocks; never split mid-line. | **Invisible**: Renders invisibly in GitHub previews, IDE preview panes, and VS Code. | **Passing**: 100% compliant with `markdownlint` and specification boundary linters. | **Zero Leakage**: Stripped cleanly during workspace materialization. |
| **Jinja2 / Liquid (`{% if ... %}`)** | **Unsafe**: Markdown formatters treat `{%` as plain text, re-indenting blocks into list items or wrapping control lines mid-token. | **Ugly**: Displays raw template syntax (`{% if ... %}`) in previews. | **Failing**: Triggers markdown syntax errors in table rows and code fences. | **Contaminating**: If unrendered, models attempt to parse Jinja syntax as prompt instructions. |
| **Custom Fences / Directives (`::: if ...`)** | **Fragile**: Non-standard; requires custom parser plugins; breaks generic CommonMark readers. | **Leaking**: Renders as raw fenced blocks or broken blockquotes. | **Failing**: Fails standard linter checks. | **Confusing**: Models may interpret `:::` as markdown blockquote or code block formatting. |
| **Pseudo HTML Tags (`<if ...>`, `<else>`)** | **Risky**: Can conflict with XML/HTML parsing; formatters rewrap unknown tags. | **Inconsistent**: Some renderers hide unknown tags, others escape them into visible text. | **Warning**: Triggers unclosed tag warnings in HTML checkers. | **Ambiguous**: Confuses models expecting standard HTML. |

### Syntax Specification

Directives follow the CommonMark block-level and inline comment standards:

```markdown
<!-- if experiment:<experiment_id> -->
<conditional markdown content for experiment_id>
<!-- elif experiment:<other_experiment_id> -->
<conditional markdown content for other_experiment_id>
<!-- else -->
<baseline / control markdown content>
<!-- endif -->
```

Also supporting the colon-syntax variant for parity with `template_format.md`:
```markdown
<!-- if: experiment.structured_blame -->
...
<!-- else -->
...
<!-- endif -->
```

### Negation and Compound Directives

The preprocessor supports standard Boolean expressions:
- Negation:
  ```markdown
  <!-- if not experiment:structured_blame -->
  Legacy instructions shown when structured_blame is NOT active.
  <!-- endif -->
  ```
- Conjunction (`and`) and Disjunction (`or`):
  ```markdown
  <!-- if experiment:structured_blame and experiment:anti_pruning_gate -->
  Active only when both experimental features are enabled.
  <!-- endif -->
  ```

### Example: Companion Guide Directives (`guides/qa.md`)

```markdown
### Attributing Blame for Target Defects

<!-- if experiment:structured_blame -->
When a test failure or specification violation is detected, author structured feedback using the formal blame tuple:

```bash
bin/blame <culprit_file> \
  --spec-slug="[slug:<part>.<method>.<facet>]" \
  --viol="[viol:<category>.<name>]" \
  --facet="<constrained noun phrase>" \
  --witness="input=<val>, exp=<val>, obs=<val>"
```
Do not write conversational essays or cite companion file details. Conclude your round with `bin/submit`.
<!-- else -->
When a test failure or specification violation is detected, author concise, diagnostic feedback explaining what contracted requirement failed:

```bash
bin/blame <culprit_file> "<diagnostic critique single paragraph>"
```
Ensure your critique contains no newlines and does not cite test function names. Conclude your round with `bin/submit`.
<!-- endif -->
```

---

## 4. Workspace Evaluation & Materialization Lifecycle

When an Autofab workspace is provisioned or refreshed, files are projected from the canonical repository tree into the role workspace. The materialization pipeline intercepts all Markdown and specification files:

```
Canonical Repo (.md) ──► [Condition Evaluator] ──► Role Workspace (.md)
                              ▲
                              │ Active Experiments:
                              │ {"structured_blame": True}
```

### Evaluation Algorithm (`markdown_preprocessor.py`)

1. **Token Scanning**: Scans line by line tracking conditional depth:
   - `<!-- if <condition> -->`
   - `<!-- elif <condition> -->`
   - `<!-- else -->`
   - `<!-- endif -->`
2. **Expression Evaluation**:
   - Parses the condition into tokens (`experiment:<name>`, `not`, `and`, `or`).
   - Checks membership in `active_experiments: Set[str]`.
   - Resolves to a Boolean truth value.
3. **Branch Filtering**:
   - Lines belonging to active branches are emitted into the materialized file.
   - Lines belonging to inactive branches are discarded.
   - Directive lines (`<!-- if ... -->`, etc.) are stripped entirely.
4. **Indentation & Formatting Preservation**:
   - Content within conditional blocks maintains exact line breaks, indentation, code fences, and whitespace.

### Verification of Materialized Workspaces

To prevent syntax errors in conditional blocks from causing silent prompt corruption, the preprocessor enforces strict validation gates:
- **Unbalanced Fences**: Any `<!-- if ... -->` without a closing `<!-- endif -->` (or nested mismatch) raises a hard error during workspace provisioning.
- **Dangling Directives**: An `<!-- else -->` or `<!-- elif ... -->` without a preceding `<!-- if ... -->` immediately halts execution.
- **Unknown Experiment IDs**: If a condition references an unregistered experiment identifier, the preprocessor warns or rejects based on strictness mode.

---

## 5. Experiment Control Planes & Activation Hierarchy

An experiment can be enabled or disabled through three cascading control planes:

```
                            PRECEDENCE HIERARCHY
   Highest:  1. Explicit CLI Flags       (--experiment <name>, --structured-blame)
      ▲
      │      2. Environment Variables    (AUTOFAB_EXPERIMENT=<name>, AUTOFAB_<EXP>=1)
      │
   Lowest:   3. Configuration Files      ([experimental] in autofab_roles.toml)
```

### 1. CLI Execution Flags
When running benchmark evaluations, orchestrations, or cleans:
```bash
# General experiment syntax:
uv run autofab benchmark --suite semver_solver --model deepseek-flash --experiment structured_blame

# Ergonomic boolean flag alias:
uv run autofab benchmark --suite semver_solver --model deepseek-flash --structured-blame
```

### 2. Environment Variables
The CLI entrypoint exports active experiments into the process environment:
```bash
export AUTOFAB_EXPERIMENT=structured_blame
export AUTOFAB_STRUCTURED_BLAME=1
```
Because environment variables are inherited by all child processes, subshells, and worker invocations, role micro-binaries (`bin/blame`, `bin/check_files`, `bin/submit`) immediately inherit the active experiment context without requiring file mutations.

### 3. Configuration Files (`autofab_roles.toml`)
For standing repository configurations or persistent lab environments:
```toml
[experimental]
active_experiments = ["structured_blame"]
```

---

## 6. Python Runtime Integration: `experiments.py`

In addition to Markdown guides and specifications, Python implementation code and linters must query active experiments cleanly:

```python
# autofab/support/lib/experiments.py

from __future__ import annotations
import os
from typing import Set

_KNOWN_EXPERIMENTS = {
    "structured_blame",
    "anti_pruning_gate",
    "tier2_meta_auditor",
}

def get_active_experiments() -> Set[str]:
    """Resolves all currently active experiment identifiers from env and config."""
    active: Set[str] = set()
    
    # 1. Primary env variable: comma-separated list
    raw_env = os.environ.get("AUTOFAB_EXPERIMENT", "").strip()
    if raw_env:
        for item in raw_env.split(","):
            token = item.strip().lower()
            if token:
                active.add(token)
                
    # 2. Specific boolean toggle aliases:
    if os.environ.get("AUTOFAB_STRUCTURED_BLAME", "0").lower() in ("1", "true", "yes"):
        active.add("structured_blame")
        
    return active

def is_experiment_active(experiment_id: str) -> bool:
    """Returns True if the designated experiment is currently active."""
    return experiment_id.lower() in get_active_experiments()
```

### Usage in Production & Linter Logic

In `bin/blame` / `attribution_impl.py`:
```python
from autofab.support.lib.experiments import is_experiment_active

if is_experiment_active("structured_blame"):
    # Enforce structured tuple flags (--spec-slug, --viol, --facet)
    parsed = parse_structured_blame_arguments(args)
    firewall.validate_structured_tuple(parsed)
else:
    # Legacy baseline: accept free-form natural language paragraph
    parsed = parse_legacy_blame_arguments(args)
```

---

## 7. Benchmark Result Archival & Naming Standards

To ensure that empirical experiments produce unambiguous, reproducible, and non-colliding results, the benchmark evaluator partitions output directories based on active experiments.

### Directory Resolution Schema

In [`autofab/parts/benchmark/lib/benchmark_impl.py`](file:///Users/seanmcdirmid/projects/cleanroom/autofab/parts/benchmark/lib/benchmark_impl.py):

$$\text{Results Dir} = \text{benchmarks/results} \,/\, \langle \text{benchmark\_id} \rangle \,/\, \langle \text{folder\_name} \rangle$$

Where $\langle \text{folder\_name} \rangle$ is dynamically constructed:
1. Base: `model_id` (e.g. `deepseek-flash`)
2. Methodology: `-combined` or `-pretense`
3. Agent mode: `-baseline`
4. **Experiment Suffix**: `-[experiment_name]` (hyphenated)

### Comparative Benchmark Matrix

| Target Suite | Model | Flight Mode | Active Experiment | Result Archival Directory |
| :--- | :--- | :--- | :--- | :--- |
| `semver_solver` | `deepseek-flash` | Standard Multi-Role | *(None / Baseline)* | `benchmarks/results/semver_solver/deepseek-flash/` |
| `semver_solver` | `deepseek-flash` | Standard Multi-Role | `structured_blame` | `benchmarks/results/semver_solver/deepseek-flash-structured-blame/` |
| `semver_solver` | `deepseek-flash` | Single-Agent Baseline | *(None / Baseline)* | `benchmarks/results/semver_solver/deepseek-flash-baseline/` |
| `semver_solver` | `deepseek-flash` | Single-Agent Baseline | `structured_blame` | `benchmarks/results/semver_solver/deepseek-flash-baseline-structured-blame/` |
| `dag_engine` | `qwen-35b` | Combined Multi-Role | `structured_blame` | `benchmarks/results/dag_engine/qwen-35b-combined-structured-blame/` |

### Telemetry Provenance in Artifact Headers

When synthesized artifacts (`lib_<N>.py`, `test_<N>.py`) are archived, the embedded header comment records active experiments:

```python
# --- AUTOFAB BENCHMARK FLIGHT METRICS ---
# FLIGHT_ID: benchmarks_flight_semver_solver_20261107_153022
# MODEL: deepseek-flash (tier: budget)
# METHODOLOGY: standard
# EXPERIMENTS: structured_blame
# STATUS: PASS (55P / 0F, 0 Pyright errors)
# COST_USD: $0.1742
# ROUNDS: coverage:3, lib:3, qa:4, test:3
# --- END AUTOFAB BENCHMARK FLIGHT METRICS ---
```

---

## 8. Step-by-Step Guide for Creating a New Experiment

When introducing an experimental capability into Autofab, follow this structured protocol:

### Phase 1: Registration & Design Doc
1. Define a concise snake_case experiment slug: e.g., `structured_blame`.
2. Register the slug in `_KNOWN_EXPERIMENTS` in `experiments.py`.
3. Add a dedicated section or companion design doc detailing hypotheses and metrics.

### Phase 2: Dark-Launch Plumbing (Before Implementation)
1. Add the CLI flag `--experiment <slug>` and any aliases (e.g. `--structured-blame`) to `benchmark_impl.py` and `autofab_role_tool.py`.
2. Update results directory resolution to append `-[experiment-slug]` when active.
3. Verify that running with the flag creates the new directory name and tags the flight record, while running without the flag leaves baseline behavior 100% untouched.

### Phase 3: Conditional Guide & Spec Authoring
1. Locate the relevant companion guides in `autofab_py/guides/` (e.g. `qa.md`, `coverage.md`, `low_to_lib.md`).
2. Wrap experimental instructions in `<!-- if experiment:<slug> -->` blocks with matching `<!-- else -->` baseline fallbacks.
3. Test the markdown preprocessor to verify that both branches render cleanly.

### Phase 4: Gated Implementation
1. Gate new code paths, validation rules, or AST checks behind `if is_experiment_active("<slug>"):`.
2. Ensure baseline tests continue to pass 100% when the experiment is inactive.
3. Author unit tests covering both the active and inactive states.

### Phase 5: Empirical Comparative Flight (A/B Testing)
1. Run the control benchmark flight:
   ```bash
   uv run autofab benchmark --suite semver_solver --model deepseek-flash
   ```
2. Run the experimental benchmark flight:
   ```bash
   uv run autofab benchmark --suite semver_solver --model deepseek-flash --experiment structured_blame
   ```
3. Compare telemetry:
   - $T_{\text{conv}}$ (Rounds and waves to convergence)
   - Token expenditure and cost ($USD)
   - Information leakage ($\mathcal{I}(P; V \mid \text{Blame})$)
   - Cross-soundness against foreign test suites

### Phase 6: Graduation or Clean Retirement
- **Graduation (Success)**:
  1. Remove `<!-- if ... -->` directives from `.md` files, retaining the experimental block as standard content.
  2. Remove `if is_experiment_active(...)` guards in Python, making the experimental logic default.
  3. Deprecate the experiment flag.
- **Retirement (Failure)**:
  1. Remove `<!-- if ... -->` blocks from `.md` files, keeping the baseline content.
  2. Delete experimental code branches.
  3. Zero architectural debt remains.
