<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T00:13:59Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: 217ce572100c
-->

# tool_coverage_impl implementation component

imports: agent_session
implements: tool_coverage

## Purpose

The tool_coverage_impl implementation component realizes module test coverage evaluation, AST statement filtering, trace-based execution counting, and structured report formatting.

Trace-based coverage evaluation and AST syntax tree analysis require concrete execution semantics to filter non-executable lines and run test suites hermetically. Accurately attributing missing statements to grounding requirements requires parsing abstract syntax trees to ignore signature continuations and docstrings, resetting module loader state to ensure clean test imports, and formatting contiguous span reports with source code context. The tool_coverage_impl implementation component provides concrete algorithms for AST line filtering, trace execution capture, span grouping, and coverage threshold validation.

**Out of scope:** The tool_coverage_impl implementation component does not modify source files, schedule graph traversals, or install conversational tools; these are handled by other components.

## Types and Behavior

A session's *coverage evaluator* realizes test coverage evaluation and report formatting as a session service.

The coverage evaluator:

- Discovers target mappings by scanning repository part directories for implementation files and companion test suites, registering normalized target stems and package aliases.

- Extracts candidate non-executable lines by parsing source text into abstract syntax trees, identifying docstring constants, class and function signature continuations, and line indices marked with pragma no cover comments along with their statement bodies.

- Executes single-target test suites under Python trace instrumentation, clearing cached target modules from memory, injecting local package paths into module search paths, capturing test suite runner failures, and collecting executed line hits on the implementation file.

- Formats uncovered line sequences into compact comma-separated range strings and paired contiguous span tuples.

- Formats source context snippets for uncovered spans, extracting corresponding source file lines and clamping output to a maximum span limit when requested.

- Formats comprehensive coverage reports incorporating test outcomes, coverage metrics, uncovered code spans, and grounding attribution instructions.

- Enforces minimum coverage thresholds, returning exit status indications and synchronizing formatted output to specified coverage log files.
