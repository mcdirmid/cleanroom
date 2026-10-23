# benchmark interface component

## Purpose

The benchmark interface component defines model efficiency evaluation, financial rate computation, telemetry harvesting, and empirical verification reporting across model tiers and benchmark suites.

Evaluating language models across agentic development tasks requires standardized measurement of token efficiency, context caching ratios, step latencies, and financial costs alongside deterministic verification outcomes. Without uniform empirical definitions, cross-model comparisons suffer from inconsistent token accounting, hidden reasoning token omissions, and unverified code artifacts. The benchmark interface component provides canonical data representations for model capabilities, benchmark units, execution telemetry, and verification results, defining the contract for model efficiency assessment.

**Out of scope:** The benchmark interface component does not transmit network requests, spawn external subprocesses, or parse filesystem logs; these are handled by other components.

## Types and Behavior

A *model specification* describes an evaluated language model, carrying an *identifier*, a *tier number*, a *tier label*, a *provider name*, an *uncached input rate*, a *cached input rate*, an *output rate*, an optional *endpoint*, an optional *quantization*, and a *default harness*. The model specification computes a *financial cost* from non-cached inbound tokens, cached inbound tokens, and outbound tokens according to its rate card.

A *benchmark unit* identifies an evaluation target, carrying a *suite name*, a *task identifier*, a *unit directory*, a *target address*, and optional metadata (*archetype description*, *specification line count*, *target library line count*, and *description*).

A *flight telemetry* record captures operational metrics from an evaluation run, carrying *non-cached inbound tokens*, *cached inbound tokens*, *outbound tokens*, *total tokens*, financial cost, *step latencies*, *wall clock seconds*, and *role execution rounds*. Role execution rounds map role short names to execution round counts tallied during flight cleaning, where a round represents a Cleanroom role dispatch pass across targets until termination, encompassing all model steps executed within that pass.

A *verification outcome* record summarizes quality gates for a completed flight, carrying a *specification linter pass* status, a *type error count*, a *unit tests passed* count, a *unit tests failed* count, a *line coverage percentage*, a *branch coverage percentage*, and a *mutation score percentage*.

A *flight trace* records the complete empirical outcome of an evaluation run, carrying a *flight identifier*, an *ISO timestamp*, a *research question tag*, a model specification dictionary, a benchmark unit dictionary, a *methodology name*, *stages executed*, a flight telemetry record, and a verification outcome record.

A system's *benchmark evaluator* coordinates benchmark flight execution across model specifications and benchmark units, provides model and suite catalogs mapping identifiers to specifications and units, provisions ephemeral flight scope directories preserving the package structure of the benchmark unit's enclosing scope to isolate role workspaces and prevent concurrent flight collisions, marks specifications clean up to specification QA within the flight scope to isolate code and test generation, executes flights with optional custom results directory destinations, evaluates verification gates, archives synthesized library, test, and Cleanroom event log artifacts into sequential run files embedding flight telemetry metrics exclusively for successful flights that pass verification gates, drains benchmark unit directories and tears down ephemeral flight scopes and provisioned role workspaces upon flight completion, and produces flight traces and formatted summary reports.

The component maintains a canonical *suite catalog* mapping suite identifiers—derived from the constituent part directories in benchmark parts (such as dag_engine, dag_engine_lite, and semver_solver)—to sequences of benchmark units, and provides *log harvesting* to extract empirical token usage, step latencies, and execution round counts from Cleanroom execution logs and subagent session transcripts.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-19T18:45:00Z
LAST_CHANGED: 2026-10-22T23:10:00Z
CHANGE: Derive benchmark suites from part directory names in benchmark parts and make descriptive metadata optional
SPEC_QA_AUDIT: 2026-10-19T18:45:00Z
-->
