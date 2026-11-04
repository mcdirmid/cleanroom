# coverage_impl implementation component

## Intent

The coverage_impl implementation component provides concrete algorithms for AST-aware non-executable line filtering, Python trace execution capture, span grouping, AST-based span ownership classification, and structured report serialization.

The implementation traverses abstract syntax trees to identify docstrings, signatures, and pragma exclusion lines, resets module loader state to ensure clean test imports, executes unittest suites under trace instrumentation to tally line hits, groups uncovered statements into contiguous spans, parses syntax trees to classify span ownership dispositions between library pragma requirements and test coverage deficits, and formats console and log outputs with actionable agent guidance leading with the precondition exemption directing the agent to first classify whether a span is an *Error raise or precondition guard belonging to the library as a pragma annotation rather than a test requirement, permitting line numbers only within the blamed file while strictly forbidding exposing details of other files, and instructing the agent when an uncovered span persists across rounds or after test updates to deeply examine the library implementation to determine whether the span is structurally or logically unreachable.

## Factored Contracts

### Contracts

- A system's coverage evaluator realizes test coverage evaluation and report formatting as a system service. [system_coverage_evaluator]
- The coverage evaluator identifies target pairs by globbing part library implementation files and companion tests. [scan_target_pairs]
- The coverage evaluator parses source syntax trees to detect pragma comment lines and statement bodies. [detect_pragma_statements]
- The coverage evaluator parses source syntax trees to detect docstrings and signature continuation lines. [detect_signature_docstrings]
- The coverage evaluator resets sys modules state to ensure fresh test suite imports under tracing. [reset_module_cache]
- The coverage evaluator injects local package paths into module search paths before test execution. [inject_local_package_paths]
- The coverage evaluator runs unit test suites under Python trace instrumentation to capture executed line counts. [trace_test_execution]
- The coverage evaluator captures unit test suite import errors and execution failures. [capture_test_failures]
- The coverage evaluator calculates covered and missed line counts to compute coverage percentage. [compute_coverage_metrics]
- The coverage evaluator extracts source text lines for missing spans and applies presentation clamping. [clamp_missing_spans]
- The coverage evaluator parses source syntax trees to classify uncovered spans into library pragma requirements and test coverage deficits. [classify_uncovered_spans]
- The coverage evaluator writes formatted coverage reports to specified log file paths. [sync_coverage_log]
- The coverage evaluator persists evaluated span classifications and ownership status into the workspace coverage status buffer. [persist_coverage_status]
- The coverage evaluator returns exit status indications when enforcing minimum coverage thresholds. [return_threshold_exit_status]

### Woven Contracts

- When discovering targets, the evaluator scans part directories for implementation files and companion tests. [scan_target_pairs, coverage: [discover_target_pairs]]
- When extracting non-executable lines, the evaluator detects pragma statements, docstrings, and signature continuations. [detect_pragma_statements, detect_signature_docstrings, coverage: [extract_non_executable_lines]]
- When measuring single-target coverage, the evaluator resets module caches, traces test execution, captures errors, and computes metrics. [reset_module_cache, trace_test_execution, capture_test_failures, compute_coverage_metrics, coverage: [measure_target_coverage]]
- When formatting reports, the evaluator classifies spans, extracts source lines, labels dispositions, and clamps spans to maximum configured limits. [classify_uncovered_spans, clamp_missing_spans, coverage: [format_spans_report, format_coverage_report]]
- When evaluating module coverage, the evaluator runs target measurement, checks thresholds, persists workspace status, and synchronizes the log file. [compute_coverage_metrics, persist_coverage_status, sync_coverage_log, coverage: [evaluate_module_coverage]]

## Grounding

### Knowledge Provisions

- Module statement coverage evaluation and report generation services. [coverage_evaluation_service]
- AST non-executable statement line extraction, contiguous span calculation, and span ownership classification. [coverage_span_analysis]

### Inherited Deferred Requirements

- Discovery of implementation and test targets across repository part packages.
  - Grounded: [coverage_evaluation_service]
- AST parsing and pragma comment detection for non-executable statement lines.
  - Grounded: [coverage_span_analysis]
- Python trace execution and test suite error capture.
  - Grounded: [coverage_evaluation_service]

### Knowledge Requirements

- Target implementation and test path arguments.
  - Grounded: [caller input, coverage_evaluation_service]

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-11-03T23:45:00Z
CHANGE: Instruct coverage auditor when uncovered spans persist to examine library implementation for unreachable code
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->
