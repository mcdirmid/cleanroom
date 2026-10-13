<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T23:37:36Z
LAST_CHANGED: 2026-10-11T04:09:00Z
CHANGE: Removed the unused agent_session import and its delegation clause: the low-level specification places the coverage evaluator under the system lifecycle tier with no agent_session member, so the interface now declares no imports.
CODE_HASH: b999cce9061f
SPEC_QA_AUDIT: 2026-10-12T23:37:36Z
-->

# tool_coverage interface component

## Purpose

The tool_coverage interface component defines module test coverage evaluation, executable line extraction, contiguous span reporting, and coverage threshold enforcement for Cleanroom library implementations.

Autonomous verification requires precise line and statement coverage tracking to ensure implementation modules are fully exercised by their unit test suites before being certified as clean. Without automated statement normalization and contiguous span extraction, docstrings, type annotations, and pragma exclusion lines skew coverage metrics, while voluminous raw line listings flood agent context windows. The tool_coverage interface component provides syntax-aware non-executable line filtering, measures single-target test coverage under execution tracing, groups uncovered statements into contiguous spans, and formats structured deficit guidance for test and implementation arbiters.

**Out of scope:** The tool_coverage interface component does not modify source files, schedule graph traversals, or install conversational tools; these are handled by other components.

## Types and Behavior

A *module coverage* record reports the test coverage metrics of a single library module, carrying a *module name*, a *test name*, an implementation *file path*, a *test path*, *total executable* statements, *covered* statements, *missed* statements, a *coverage percentage*, *missing lines*, *missing ranges*, *missing spans*, a *test passed* status, and a *test error* description when execution fails.

A system's *coverage evaluator* coordinates statement coverage measurement and report generation.

The coverage evaluator discovers the implementation and test file pairs across the part packages of a repository, and extracts candidate executable lines from implementation source files by filtering out docstrings, function and class signature continuation lines, and pragma exclusion annotations.

The coverage evaluator measures single-target statement coverage by executing the corresponding unit test suite under trace instrumentation, isolating test execution errors and recording covered line hits.

The coverage evaluator formats missing statement lines into compact comma-separated range strings and contiguous span ranges, and formats structured coverage reports presenting missing statement spans, source code context lines, presentation span clamping when output exceeds limits, and actionable guidance for defect attribution.

The coverage evaluator enforces configured coverage thresholds, reporting whether coverage targets are met and writing formatted reports to the designated coverage log files.
