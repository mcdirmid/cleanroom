<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T23:58:18Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: 6cd758bc24ff
-->

# tool_coverage interface component

imports: agent_session

## Purpose

The tool_coverage interface component defines module test coverage evaluation, AST executable line extraction, contiguous span reporting, and coverage threshold enforcement for Cleanroom library implementations.

Autonomous verification requires precise line and statement coverage tracking to ensure implementation modules are fully exercised by their unit test suites before being certified as clean. Without automated statement normalization and contiguous span extraction, docstrings, type annotations, and pragma exclusion lines skew coverage metrics, while voluminous raw line listings flood agent context windows. The tool_coverage interface component provides AST-aware non-executable line filtering, measures single-target test coverage under execution tracing, groups uncovered statements into contiguous spans, and formats structured deficit guidance for test and implementation arbiters.

**Out of scope:** The tool_coverage interface component does not modify source files, schedule graph traversals, or install conversational tools; these are handled by other components.

## Types and Behavior

A *module coverage* record reports test coverage metrics for a single library module, carrying a *module name*, a *test name*, an implementation *file path*, a *test path*, a count of *total executable* statements, a count of *covered* statements, a count of *missed* statements, a *coverage percentage*, a list of *missing lines*, a formatted string of *missing ranges*, a sequence of contiguous *missing spans*, a boolean *test passed* flag, and an optional *test error* description.

A session's *coverage evaluator* coordinates statement coverage measurement and report generation.

The coverage evaluator:

- Discovers available implementation and test file pairs across repository part packages.

- Extracts candidate executable lines from implementation source files, filtering out docstrings, function and class signature continuation lines, and pragma exclusion annotations.

- Measures single-target statement coverage by executing the corresponding unit test suite under trace instrumentation, isolating test execution errors and recording covered line hits.

- Formats missing statement lines into compact comma-separated range strings and contiguous span ranges.

- Formats structured coverage reports presenting missing statement spans, source code context lines, optional presentation span clamping, and actionable grounding guidance for defect attribution.

- Enforces configured coverage thresholds, reporting whether coverage targets are met and writing formatted reports to designated coverage log files.
