<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:09:47Z
CHANGE: Author tools tool_coverage concrete scenarios
CODE_HASH: a0a3865f5de9
-->

# Concrete scenarios for `tool_coverage` (interface)

## Scenario 1 — The coverage record of one module

Given: the coverage evaluator has measured the alpha-role implementation module `alpha_widget`,
whose implementation file is `parts/alpha/lib/widget.py` and whose companion test suite is
`parts/alpha/tests/widget_test.py`, over ten executable statements of which six were executed by
the test and four were not, with the missed statements on lines 12, 13, 24, and 41.

1. The caller asks for the coverage of that module.
   Observed: a module coverage record naming `alpha_widget`, `parts/alpha/lib/widget.py`, and
   `parts/alpha/tests/widget_test.py`, reporting ten total executable statements, six covered,
   four missed, a coverage percentage of 60, the missing lines 12, 13, 24, and 41, a test passed
   status of passed, and no test error description.

## Scenario 2 — Discovering the implementation and test pairs

Given: the repository holds the parts alpha, beta, and gamma; alpha holds `parts/alpha/lib/widget.py`
with `parts/alpha/tests/widget_test.py`, beta holds `parts/beta/lib/gadget.py` with
`parts/beta/tests/gadget_test.py`, and gamma holds only specifications, with no implementation file
and no test suite.

1. The caller asks the coverage evaluator to discover the module pairs.
   Observed: two pairs come back, `parts/alpha/lib/widget.py` with `parts/alpha/tests/widget_test.py`
   and `parts/beta/lib/gadget.py` with `parts/beta/tests/gadget_test.py`, and nothing comes back for
   gamma.

## Scenario 3 — Non-executable lines are not candidates

Given: the implementation file `parts/alpha/lib/widget.py` holds a module docstring on lines 1
through 3, the signature `def resize(widget, height):` continued on the following line with
`height: int,` followed by `) -> None:`, a body statement on line 9 carrying a `no cover` pragma
comment, and the ordinary statement `widget.height = height` on line 11.

1. The caller asks for the candidate executable lines of `parts/alpha/lib/widget.py`.
   Observed: the candidate lines are 9 and 11, with the docstring lines 1 through 3, the signature
   continuation line, and no body line of the pragma-annotated statement other than line 9 itself
   excluded.

## Scenario 4 — Measuring one target

Given: the implementation file `parts/alpha/lib/widget.py` holds the executable lines 5 and 6, and
the companion test suite `parts/alpha/tests/widget_test.py` executes only line 5 of them.

1. The caller asks for the statement coverage of that one target.
   Observed: the measurement reports two total executable statements, one covered, one missed, and
   a coverage percentage of 50, with the missed line 6.

## Scenario 5 — A test suite that fails during execution

Given: the companion test suite `parts/alpha/tests/widget_test.py` raises `AssertionError: widget
height was 3` before finishing, and it executes the implementation line 5 before raising.

1. The caller asks for the statement coverage of that one target.
   Observed: the module coverage record reports a test passed status of failed and a test error
   description naming the assertion, and the covered lines reported for the implementation file
   still include line 5.

## Scenario 6 — Formatting missing lines into ranges and spans

Given: the implementation file `parts/alpha/lib/widget.py` holds executable lines 12, 13, 14, 24,
and 41, and none of them were executed.

1. The caller asks for the missing line ranges of that module.
   Observed: the compact comma-separated range string `12-14, 24, 41` and the contiguous spans
   `(12, 14)`, `(24, 24)`, and `(41, 41)`.

## Scenario 7 — Report output when the spans exceed the limit

Given: the implementation file `parts/alpha/lib/widget.py` has 400 uncovered statements spread over
spans `(1, 200)` and `(300, 500)`, and the caller requests a report clamped to 10 context lines.

1. The caller asks for the coverage report clamped to 10 context lines.
   Observed: the report carries the two uncovered spans, at most 10 source code context lines
   around them, and the same actionable guidance for defect attribution that an unclamped report
   carries.

## Scenario 8 — Enforcing the configured threshold

Given: the implementation file `parts/alpha/lib/widget.py` reports a coverage percentage of 60, the
configured threshold is 80 percent, and the designated coverage log file
`/ws/alpha_scope_a/logs/coverage.log` does not yet exist.

1. The caller asks the coverage evaluator to enforce the threshold for that module.
   Observed: the report states that the 80 percent threshold was not met, the coverage log file
   exists and carries the formatted report, and the exit status indicates the threshold was
   missed.

2. The caller asks again after the module reports 90 percent.
   Observed: the report states that the 80 percent threshold was met, the log file is rewritten
   with the new report, and the exit status indicates the threshold was met.
