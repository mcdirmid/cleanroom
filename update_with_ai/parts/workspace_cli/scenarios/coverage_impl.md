# Concrete scenarios for `coverage_impl` (implementation)

Scenarios 1 through 8 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones
is what makes realizability structural: an implementation scenario that cannot name a realization
for its observation is a defect in the implementation rather than a gap in the set. Scenarios 9
through 11 cover behaviours the interface does not expose to a caller, and each of them is a
candidate for the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — The coverage record of one module

Given: the coverage evaluator has measured the alpha-role implementation module `alpha_widget`,
whose implementation file is `parts/alpha/lib/widget.py` and whose companion test suite is
`parts/alpha/tests/widget_test.py`, over ten executable statements of which six were executed by
the test and four were not, with the missed statements on lines 12, 13, 24, and 41.

1. The caller asks for the coverage of that module.
   Observed: a module coverage record naming `alpha_widget`, `parts/alpha/lib/widget.py`, and
   `parts/alpha/tests/widget_test.py`, reporting ten total executable statements, six covered,
   four missed, a coverage percentage of 60, the missing lines 12, 13, 24, and 41, a test passed
   status of passed, and no test error description.
   Realized by: the component's own record construction as a system service, which fills the record
   from the measured line hits and the extracted candidate lines.

### Scenario 2 — Discovering the implementation and test pairs

Given: the repository holds the parts alpha, beta, and gamma; alpha holds `parts/alpha/lib/widget.py`
with `parts/alpha/tests/widget_test.py`, beta holds `parts/beta/lib/gadget.py` with
`parts/beta/tests/gadget_test.py`, and gamma holds only specifications, with no implementation file
and no test suite.

1. The caller asks the coverage evaluator to discover the module pairs.
   Observed: two pairs come back, `parts/alpha/lib/widget.py` with `parts/alpha/tests/widget_test.py`
   and `parts/beta/lib/gadget.py` with `parts/beta/tests/gadget_test.py`, and nothing comes back for
   gamma.
   Realized by: the component's own scan of the part directories, which registers a normalized
   target stem and package alias for each implementation file that has a companion test suite.

### Scenario 3 — Non-executable lines are not candidates

Given: the implementation file `parts/alpha/lib/widget.py` holds a module docstring on lines 1
through 3, the signature `def resize(widget, height):` continued on the following line with
`height: int,` followed by `) -> None:`, a body statement on line 9 carrying a `no cover` pragma
comment, and the ordinary statement `widget.height = height` on line 11.

1. The caller asks for the candidate executable lines of `parts/alpha/lib/widget.py`.
   Observed: the candidate lines are 9 and 11, with the docstring lines 1 through 3, the signature
   continuation line, and no body line of the pragma-annotated statement other than line 9 itself
   excluded.
   Realized by: the component's own syntax tree parsing of the source text, which identifies
   docstring constants, signature continuation lines, and pragma-annotated lines together with the
   statements they cover.

### Scenario 4 — Measuring one target

Given: the implementation file `parts/alpha/lib/widget.py` holds the executable lines 5 and 6, and
the companion test suite `parts/alpha/tests/widget_test.py` executes only line 5 of them.

1. The caller asks for the statement coverage of that one target.
   Observed: the measurement reports two total executable statements, one covered, one missed, and
   a coverage percentage of 50, with the missed line 6.
   Realized by: the component's own execution of the test suite under trace instrumentation, which
   records the executed hits on the implementation file, and its own extraction of the candidate
   lines to form the denominator.

### Scenario 5 — A test suite that fails during execution

Given: the companion test suite `parts/alpha/tests/widget_test.py` raises `AssertionError: widget
height was 3` before finishing, and it executes the implementation line 5 before raising.

1. The caller asks for the statement coverage of that one target.
   Observed: the module coverage record reports a test passed status of failed and a test error
   description naming the assertion, and the covered lines reported for the implementation file
   still include line 5.
   Realized by: the component's own capture of the test suite runner failure, which records the
   error while retaining the line hits collected before the failure.

### Scenario 6 — Formatting missing lines into ranges and spans

Given: the implementation file `parts/alpha/lib/widget.py` holds executable lines 12, 13, 14, 24,
and 41, and none of them were executed.

1. The caller asks for the missing line ranges of that module.
   Observed: the compact comma-separated range string `12-14, 24, 41` and the contiguous spans
   `(12, 14)`, `(24, 24)`, and `(41, 41)`.
   Realized by: the component's own formatting of the uncovered line sequence into comma-separated
   ranges and paired contiguous span tuples.

### Scenario 7 — Report output when the spans exceed the limit

Given: the implementation file `parts/alpha/lib/widget.py` has 400 uncovered statements spread over
spans `(1, 200)` and `(300, 500)`, and the caller requests a report clamped to 10 context lines.

1. The caller asks for the coverage report clamped to 10 context lines.
   Observed: the report carries the two uncovered spans, at most 10 source code context lines
   around them, and the same actionable guidance for defect attribution that an unclamped report
   carries.
   Realized by: the component's own context snippet extraction, which reads the corresponding
   source lines and clamps the output to the requested span limit, and its own report formatting.

### Scenario 8 — Enforcing the configured threshold

Given: the implementation file `parts/alpha/lib/widget.py` reports a coverage percentage of 60, the
configured threshold is 80 percent, and the designated coverage log file
`/ws/alpha_scope_a/logs/coverage.log` does not yet exist.

1. The caller asks the coverage evaluator to enforce the threshold for that module.
   Observed: the report states that the 80 percent threshold was not met, the coverage log file
   exists and carries the formatted report, and the exit status indicates the threshold was
   missed.
   Realized by: the component's own threshold comparison and its own report write to the
   designated coverage log file, whose exit status indication it returns.

2. The caller asks again after the module reports 90 percent.
   Observed: the report states that the 80 percent threshold was met, the log file is rewritten
   with the new report, and the exit status indicates the threshold was met.
   Realized by: the same threshold comparison and report write, now finding the coverage above the
   threshold.

## Implementation-only

### Scenario 9 — A target whose test module was already imported

Given: the companion test suite `parts/alpha/tests/widget_test.py` was executed once already by the
evaluator, and it passes on a second execution that covers line 6 as well as line 5.

1. The caller asks for the statement coverage of the target a second time.
   Observed: the second measurement reports both lines 5 and 6 covered and a coverage percentage of
   100, rather than reusing the line hits of the first execution.
   Realized by: the component's own clearing of the cached target and test modules from memory
   across the package namespaces before each measurement, and its injection of the local package
   paths into the module search paths.

### Scenario 10 — A target whose companion test suite is missing

Given: the implementation file `parts/beta/lib/gadget.py` exists and no test suite exists under
`parts/beta/tests/`.

1. The caller asks the coverage evaluator to discover the module pairs.
   Observed: no pair comes back for `parts/beta/lib/gadget.py`, and no other pair is dropped.
   Realized by: the component's own pairing scan, which registers only implementation files that
   have a companion test suite.

### Scenario 11 — A module with no executable statements

Given: the implementation file `parts/alpha/lib/marker.py` holds only a module docstring and no
statement.

1. The caller asks for the statement coverage of that target.
   Observed: the record reports zero total executable statements, zero covered, zero missed, and no
   missing lines, with no division failure.
   Realized by: the component's own syntax tree filtering, which leaves an empty candidate line
   sequence, and its own record construction over an empty denominator.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T04:11:44Z
CHANGE: Drop the removed agent_session realization from the coverage record scenario
-->
