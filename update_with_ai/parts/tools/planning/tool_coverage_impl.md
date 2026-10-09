<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-07T00:11:26Z
CHANGE: new file
CODE_HASH: f1e4fb1b80c9
SPEC_QA_AUDIT: 2026-10-09T21:19:01Z
-->

# tool_coverage_impl implementation component

imports: agent_session
implements: tool_coverage

## Intent

The tool_coverage_impl implementation component provides concrete algorithms for AST-aware non-executable line filtering, Python trace execution capture, span grouping, and structured report serialization.

The implementation traverses abstract syntax trees to identify docstrings, signatures, and pragma exclusion lines, resets module loader state to ensure clean test imports, executes unittest suites under trace instrumentation to tally line hits, groups uncovered statements into contiguous spans, and formats console and log outputs with actionable agent guidance.

## Factored Contracts

### Contracts

- The coverage evaluator identifies target pairs by globbing part library implementation files and companion tests. [scan_target_pairs]
- The coverage evaluator parses source syntax trees to detect pragma comment lines and statement bodies. [detect_pragma_statements]
- The coverage evaluator parses source syntax trees to detect docstrings and signature continuation lines. [detect_signature_docstrings]
- The coverage evaluator resets sys modules state to ensure fresh test suite imports under tracing. [reset_module_cache]
- The coverage evaluator runs unit test suites under Python trace instrumentation to capture executed line counts. [trace_test_execution]
- The coverage evaluator captures unit test suite import errors and execution failures. [capture_test_failures]
- The coverage evaluator calculates covered and missed line counts to compute coverage percentage. [compute_coverage_metrics]
- The coverage evaluator extracts source text lines for missing spans and applies presentation clamping. [clamp_missing_spans]
- The coverage evaluator writes formatted coverage reports to specified log file paths. [sync_coverage_log]

### Woven Contracts

- When discovering targets, the evaluator scans part directories for implementation files and companion tests. [scan_target_pairs, tool_coverage: [discover_target_pairs]]
- When extracting non-executable lines, the evaluator detects pragma statements, docstrings, and signature continuations. [detect_pragma_statements, detect_signature_docstrings, tool_coverage: [extract_non_executable_lines]]
- When measuring single-target coverage, the evaluator resets module caches, traces test execution, captures errors, and computes metrics. [reset_module_cache, trace_test_execution, capture_test_failures, compute_coverage_metrics, tool_coverage: [measure_target_coverage]]
- When formatting reports, the evaluator extracts source lines and clamps spans to maximum configured limits. [clamp_missing_spans, tool_coverage: [format_spans_report, format_coverage_report]]
- When evaluating module coverage, the evaluator runs target measurement, checks thresholds, and synchronizes the log file. [compute_coverage_metrics, sync_coverage_log, tool_coverage: [evaluate_module_coverage]]

## Grounding

### Knowledge Provisions

- Module statement coverage evaluation and report generation services. [coverage_evaluation_service]
- AST non-executable statement line extraction and contiguous span calculation. [coverage_span_analysis]

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
