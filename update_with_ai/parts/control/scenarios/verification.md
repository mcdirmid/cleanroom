# Concrete scenarios for `verification` (interface)

## Scenario 1 — Evaluating one target whose check fails amid compiler noise

Given: the alpha-role target node for unit widget is dirty and is configured with the verification
check whose criteria is `widget/src/widget.py type-checks`, and the check exits with the non-zero
exit code 1 while writing the output `Build loading: 4 packages`, `--- Running widget type check
---`, `error: widget/src/widget.py line 7: the sprocket field type is not accepted`,
`warning: widget/src/widget.py line 9: unused widget import`, `Analyzed 12 targets` and
`Elapsed 3.4s`.

1. The agent evaluates the verification checks of the alpha-role target node for unit widget.
   Observed: one verification result reporting a failed status, carrying the sanitized diagnostic
   output `error: widget/src/widget.py line 7: the sprocket field type is not accepted` and
   `warning: widget/src/widget.py line 9: unused widget import` only, and reporting that the result
   was not reused from cache.

2. The agent evaluates a verification check realized as a command object specifying a shell command string.
   Observed: the shell command executes with a bounded timeout, returning sanitized diagnostic output and pass/fail status.

## Scenario 2 — Reusing a cached result while the target files are unchanged

Given: a previous evaluation of the alpha-role target node for unit widget failed with the
diagnostic output `error: widget/src/widget.py line 7: the sprocket field type is not accepted`, the
target file `widget/src/widget.py` has not been modified since that evaluation, and the verification
check whose criteria is `widget/src/widget.py type-checks` still exits with exit code 1.

1. The agent evaluates the verification checks of the alpha-role target node for unit widget again.
   Observed: one verification result reporting a failed status with the same diagnostic output, and
   reporting that the result was reused from cache rather than evaluated.

## Scenario 3 — Re-evaluating once the target files have changed

Given: a previous evaluation of the alpha-role target node for unit widget failed, the target file
`widget/src/widget.py` is modified at `2026-03-04T05:06:07Z` after that evaluation, and the
verification check whose criteria is `widget/src/widget.py type-checks` now exits with exit code 0.

1. The agent evaluates the verification checks of the alpha-role target node for unit widget.
   Observed: one verification result reporting a passed status and reporting that the result was not
   reused from cache, because the target file contents changed since the previous evaluation.

## Scenario 4 — Evaluating every active target of the session

Given: the session has two active targets, the alpha-role target node for unit widget, whose
verification check exits with exit code 0, and the beta-role target node for unit gadget, whose
verification check exits with the non-zero exit code 1 while writing
`error: gadget/src/gadget.py line 3: the widget field is undeclared`.

1. The agent evaluates the verification checks of every active target in the session.
   Observed: two verification results, the first reporting a passed status for the alpha-role target
   node for unit widget and the second reporting a failed status carrying the sanitized diagnostic
   output `error: gadget/src/gadget.py line 3: the widget field is undeclared` for the beta-role
   target node for unit gadget.

## Scenario 5 — Evaluating the active targets of a session that has none

Given: the session has no active target, and no verification check is configured for the session.

1. The agent evaluates the verification checks of every active target in the session.
   Observed: no verification result is reported, and no check is run.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:17:14Z
CHANGE: Author control verification concrete scenarios
-->
