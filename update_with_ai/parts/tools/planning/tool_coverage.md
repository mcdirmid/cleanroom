<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T23:58:18Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: 50bf15450b16
SPEC_QA_AUDIT: 2026-10-07T23:58:18Z
-->

# tool_coverage interface component

imports: agent_session

## Intent

The tool_coverage interface component defines data types and operational contracts for module test coverage evaluation, AST statement normalization, contiguous span reporting, and threshold enforcement.

Validating implementation cleanliness requires verifying that every executable statement in a library module is covered by its unit test suite. The coverage evaluator acts as the authoritative interface for discovering target file pairs, extracting executable lines while filtering docstrings and annotations, running test suites under trace instrumentation, formatting contiguous uncovered spans, and asserting coverage thresholds.

## Factored Contracts

### Typing

- A module coverage record encapsulates a module name, a test name, a file path, a test path, total executable count, covered count, missed count, coverage percentage, missing lines list, missing ranges text, missing spans sequence, a test passed flag, and an optional test error.
- A coverage evaluator operates within the agent session lifecycle tier.

### Contracts

- A coverage evaluator discovers available implementation and test file pairs across repository part packages. [discover_target_pairs]
- A coverage evaluator extracts non-executable statement lines from an implementation file using AST structure. [extract_non_executable_lines]
- A coverage evaluator measures single-target statement coverage by executing its test suite under execution tracing. [measure_target_coverage]
- A coverage evaluator formats missing statement line numbers into compact comma-separated range strings. [format_missing_ranges]
- A coverage evaluator groups sorted missing statement line numbers into contiguous span tuples. [group_missing_spans]
- A coverage evaluator normalizes target query strings by stripping Bazel target or path prefixes. [normalize_query_string]
- A coverage evaluator formats source snippet reports for uncovered statement spans with optional span clamping. [format_spans_report]
- A coverage evaluator formats structured coverage reports with agent guidance and deficit metrics. [format_coverage_report]
- A coverage evaluator evaluates module coverage against a percentage threshold and updates log files. [evaluate_module_coverage]

### Woven Contracts

- When measuring single-target coverage, the evaluator extracts non-executable lines and traces the unit test suite to determine covered statements. [extract_non_executable_lines, measure_target_coverage]
- When generating reports, the evaluator formats missing ranges and groups missing lines into spans with source context. [format_missing_ranges, group_missing_spans, format_spans_report, format_coverage_report]
- When evaluating module coverage, the evaluator runs single-target coverage measurement and updates the coverage log file. [measure_target_coverage, evaluate_module_coverage]

## Grounding

### Knowledge Provisions

- Module statement coverage evaluation and report generation services. [coverage_evaluation_service]
- AST non-executable statement line extraction and contiguous span calculation. [coverage_span_analysis]

### Knowledge Requirements

- Discovery of implementation and test targets across repository part packages.
  - Deferred: Provided by coverage evaluator implementation.
- AST parsing and pragma comment detection for non-executable statement lines.
  - Deferred: Provided by coverage evaluator implementation.
- Python trace execution and test suite error capture.
  - Deferred: Provided by coverage evaluator implementation.
