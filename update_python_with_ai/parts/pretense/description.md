# Pretense Part (`update_python_with_ai/parts/pretense`)

## Purpose

The **pretense** part provides Cleanroom's unified state-machine-driven testing, verification, and fake synthesis engine.

Software verification driven purely by example-based testing or AST statement coverage suffers from severe blind spots in LLM-generated code: high statement coverage often greenlights state desynchronization, omission bugs, and boundary condition regressions. Pretense solves this by expressing behavioral specifications as executable state transition models. Powered by property-based conjecture search and minimal counterexample shrinking, Pretense verifies state-transition invariants, synthesizes zero-maintenance interface fakes, enforces execution watchdogs against infinite loops, and drives differential testing between specifications and implementations.

## Key Components & Specifications

- [`pretense.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_python_with_ai/parts/pretense/high/pretense.md): Defines the core state machine abstractions, sentinels, outcome descriptors, transition models, stateful collection structures, hypothesis draw contexts, fake adapter contracts, and the `PretenseEngine` interface.
- [`pretense_impl.md`](file:///Users/seanmcdirmid/projects/cleanroom/update_python_with_ai/parts/pretense/high/pretense_impl.md): Realizes the dynamic Hypothesis state machine compiler, active step diagnostic tracking, minimal counterexample unit test synthesis, watchdog timeout enforcement, test discovery, and the `pretense` command-line test runner.

## How It Is Used by Other Parts

Pretense serves as Cleanroom's primary state-machine testing and contract verification engine:
- **`cleanroom_roles.toml`**: Configures the `pretense`, `pretense_qa`, and `pretense_coverage` roles to invoke `uv run pretense ...` across all parts.
- **`update_python_with_ai/support`**: `pretense_lint.py` enforces structural rules on `*_pretense.py` files and validates that state machines conform to Pretense contracts.
- **`benchmark`**: Provisions `.env` watchdogs (`PYTHONFAULTHANDLER=1`, `PRETENSE_TIMEOUT=45.0`) and provides baseline developer models with Pretense verification tools.
- **All constituent parts**: Every Cleanroom part maintains executable state machine specifications under `parts/<name>/pretense/` targeting the part's implementation modules.
