# coverage_impl implementation component

implements: coverage

## Purpose

The coverage_impl implementation component realizes module test coverage evaluation, syntax tree statement filtering, unified pytest test execution under coverage tracking, AST-based span ownership classification, and structured report formatting.

Test execution under coverage tracking and syntax tree analysis require concrete execution semantics to filter non-executable lines and run test suites hermetically matching the QA test runner. Accurately attributing missing statements to grounding requirements requires parsing abstract syntax trees to ignore signature continuations and docstrings, executing test suites via the unified pytest runner under coverage tracking, classifying uncovered spans by ownership, and formatting contiguous span reports with source code context. The coverage_impl implementation component provides concrete algorithms for syntax tree line filtering, test execution capture, span grouping, span classification, and coverage threshold validation.

**Out of scope:** The coverage_impl implementation component does not modify source files, schedule graph traversals, or install conversational tools; these are handled by other components.

## Types and Behavior

A system's *coverage evaluator* realizes test coverage evaluation and report formatting as a system service.

The coverage evaluator discovers target mappings by scanning the part directories of a repository for implementation files and companion test suites, registering normalized target stems and package aliases.

The coverage evaluator extracts candidate non-executable lines by parsing source text into abstract syntax trees, identifying docstring constants, class and function signature continuations, and line indices marked with pragma no cover comments together with their statement bodies.

The coverage evaluator executes a single-target test suite using the unified pytest test runner under coverage tracking, isolating test execution errors, capturing test suite runner failures, and collecting executed line hits on the implementation file.

The coverage evaluator formats uncovered line sequences into compact comma-separated range strings and paired contiguous span tuples, and formats source context snippets for uncovered spans by extracting the corresponding source file lines and clamping output to a maximum span limit when requested.

The coverage evaluator parses abstract syntax trees to classify each uncovered statement span by ownership and disposition, identifying contract violation error raises or unreachable branches as library-owned pragma candidates (`LIB-PRAGMA-REQUIRED: raises <ErrorName>`), defensive precondition guards as library-owned guards (`LIB-PRAGMA-REQUIRED: precondition guard`), and positive-path postconditions, invariants, or success branches as test-owned deficits (`TEST-COVERAGE-DEFICIT: missing unit test assertion`).

The coverage evaluator formats comprehensive coverage reports incorporating test outcomes, coverage metrics, uncovered code spans labeled with ownership dispositions, and grounding attribution instructions leading with the precondition exemption directing the agent to first classify whether a span is an `*Error` raise or precondition guard belonging to the library as a pragma annotation rather than a test requirement, permitting line numbers only within the blamed file while strictly forbidding exposing details of other files, instructing the agent when an uncovered span persists across rounds or after test updates to deeply examine the library implementation to determine whether the span is structurally or logically unreachable, and providing an escape valve directing using fail when 100% coverage appears unreachable without violating contracts.

The coverage evaluator enforces minimum coverage thresholds, returning exit status indications, synchronizing formatted output to the specified coverage log files, and recording evaluated span classifications and ownership status into the workspace coverage status buffer (`.coverage_spans.json`) for attribution validation.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-11-04T12:08:00Z
CHANGE: Unify test execution in coverage evaluator with the standard pytest runner under coverage tracking
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
