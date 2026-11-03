# coverage_impl implementation component

implements: coverage

## Purpose

The coverage_impl implementation component realizes module test coverage evaluation, syntax tree statement filtering, trace-based execution counting, and structured report formatting.

Trace-based coverage evaluation and syntax tree analysis require concrete execution semantics to filter non-executable lines and run test suites hermetically. Accurately attributing missing statements to grounding requirements requires parsing abstract syntax trees to ignore signature continuations and docstrings, resetting module loader state to ensure clean test imports, and formatting contiguous span reports with source code context. The coverage_impl implementation component provides concrete algorithms for syntax tree line filtering, trace execution capture, span grouping, and coverage threshold validation.

**Out of scope:** The coverage_impl implementation component does not modify source files, schedule graph traversals, or install conversational tools; these are handled by other components.

## Types and Behavior

A system's *coverage evaluator* realizes test coverage evaluation and report formatting as a system service.

The coverage evaluator discovers target mappings by scanning the part directories of a repository for implementation files and companion test suites, registering normalized target stems and package aliases.

The coverage evaluator extracts candidate non-executable lines by parsing source text into abstract syntax trees, identifying docstring constants, class and function signature continuations, and line indices marked with pragma no cover comments together with their statement bodies.

The coverage evaluator executes a single-target test suite under trace instrumentation, clearing cached target, test, and library package modules from memory across package namespaces, injecting local part package and constituent directory paths into module search paths to prevent loading cross-workspace shadows, capturing test suite runner failures, and collecting executed line hits on the implementation file.

The coverage evaluator formats uncovered line sequences into compact comma-separated range strings and paired contiguous span tuples, and formats source context snippets for uncovered spans by extracting the corresponding source file lines and clamping output to a maximum span limit when requested.

The coverage evaluator formats comprehensive coverage reports incorporating test outcomes, coverage metrics, uncovered code spans, and grounding attribution instructions directing the agent to formulate blame feedback strictly in terms of how the blamed file is not compliant with the common source of truth specification, permitting line numbers only within the blamed file while strictly forbidding exposing details of other files.

The coverage evaluator enforces minimum coverage thresholds, returning exit status indications and synchronizing formatted output to the specified coverage log files.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-29T00:30:00Z
CHANGE: Format grounding attribution instructions permitting line numbers in blamed file while forbidding exposing details of other files
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
