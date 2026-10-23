# Concrete scenarios for `verification_impl` (implementation)

Scenarios 1 through 5 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones is
what makes realizability structural: an implementation scenario that cannot name a realization for
its observation is a defect in the implementation rather than a gap in the set. Scenarios 6 through
10 cover behaviours the interface does not expose to a caller, and each of them is a candidate for
the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — Evaluating one target whose check fails amid compiler noise

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
   Realized by: the retrieval of the verification checks configured on the target node through the
   `agent_node_config` session service, scoped to the active `agent_session`; the component's own
   sequential execution of each check command as a subprocess; the component's own capture of the
   exit code and error output; the component's own scrubbing of the diagnostic lines that begin with
   a build progress indicator or a load banner; and the component's own file hash cache, which the
   evaluation writes with the failing outcome.

### Scenario 2 — Reusing a cached result while the target files are unchanged

Given: a previous evaluation of the alpha-role target node for unit widget failed with the
diagnostic output `error: widget/src/widget.py line 7: the sprocket field type is not accepted`, the
target file `widget/src/widget.py` has not been modified since that evaluation, and the verification
check whose criteria is `widget/src/widget.py type-checks` still exits with exit code 1.

1. The agent evaluates the verification checks of the alpha-role target node for unit widget again.
   Observed: one verification result reporting a failed status with the same diagnostic output, and
   reporting that the result was reused from cache rather than evaluated.
   Realized by: the component's own comparison of the target's current read-write file hashes
   against the file hash recorded from the previous evaluation in the same file hash cache, which
   returns the recorded result without invoking a check subprocess.

### Scenario 3 — Re-evaluating once the target files have changed

Given: a previous evaluation of the alpha-role target node for unit widget failed, the target file
`widget/src/widget.py` is modified at `2026-03-04T05:06:07Z` after that evaluation, and the
verification check whose criteria is `widget/src/widget.py type-checks` now exits with exit code 0.

1. The agent evaluates the verification checks of the alpha-role target node for unit widget.
   Observed: one verification result reporting a passed status and reporting that the result was not
   reused from cache, because the target file contents changed since the previous evaluation.
   Realized by: the component's own file hash comparison finding that the recorded hash no longer
   matches the target's current read-write file hash, followed by sequential subprocess execution of
   each configured check and the caching of the passing outcome alongside the current file hashes.

### Scenario 4 — Evaluating every active target of the session

Given: the session has two active targets, the alpha-role target node for unit widget, whose
verification check exits with exit code 0, and the beta-role target node for unit gadget, whose
verification check exits with the non-zero exit code 1 while writing
`error: gadget/src/gadget.py line 3: the widget field is undeclared`.

1. The agent evaluates the verification checks of every active target in the session.
   Observed: two verification results, the first reporting a passed status for the alpha-role target
   node for unit widget and the second reporting a failed status carrying the sanitized diagnostic
   output `error: gadget/src/gadget.py line 3: the widget field is undeclared` for the beta-role
   target node for unit gadget.
   Realized by: the component's own iteration over the active targets bounded by the
   `agent_session` lifecycle tier, the retrieval of the checks configured on each target node
   through `agent_node_config`, and the component's own per-target subprocess execution and file
   hash cache, which records each outcome separately.

### Scenario 5 — Evaluating the active targets of a session that has none

Given: the session has no active target, and no verification check is configured for the session.

1. The agent evaluates the verification checks of every active target in the session.
   Observed: no verification result is reported, and no check is run.
   Realized by: the component's own iteration over the active targets bounded by the
   `agent_session` lifecycle tier, which yields no target to evaluate.

## Implementation-only

### Scenario 6 — A target that configures no verification check

Given: the alpha-role target node for unit widget is dirty, the target node configures no
verification check, and the session configures no verification check for the session.

1. The agent evaluates the verification checks of the alpha-role target node for unit widget.
   Observed: one verification result reporting a passed status and reporting that the result was not
   reused from cache.
   Realized by: the retrieval of the verification checks through `agent_node_config`, which returns
   the node's checks or the checks configured globally for the session, and the component's own
   handling of an empty check sequence, which reports a passing result without invoking any
   subprocess.

### Scenario 7 — A target that configures no check of its own

Given: the session is configured with the verification check whose criteria is `widget/src/widget.py
type-checks`, the alpha-role target node for unit widget configures no verification check of its
own, and that check exits with the non-zero exit code 1 while writing
`error: widget/src/widget.py line 7: the sprocket field type is not accepted`.

1. The agent evaluates the verification checks of the alpha-role target node for unit widget.
   Observed: one verification result reporting a failed status, carrying the sanitized diagnostic
   output `error: widget/src/widget.py line 7: the sprocket field type is not accepted`.
   Realized by: the retrieval of the verification checks through `agent_node_config`, which falls
   back to the checks configured globally for the session when the target node configures none, and
   the component's own subprocess execution of that check.

### Scenario 8 — What the file hash cache is keyed on

Given: the alpha-role target node for unit widget is configured with a verification check, the
target's read-write files are `widget/src/widget.py` and `widget/notes/draft.md`, and a previous
evaluation ran that check and recorded the current hash of each of the two files.

1. The agent evaluates the verification checks of the alpha-role target node for unit widget again
   while only `widget/notes/draft.md` has been modified since the recorded evaluation.
   Observed: one verification result reporting that the result was not reused from cache.
   Realized by: the component's own file hash comparison over every read-write file of the target,
   which finds the recorded hash of `widget/notes/draft.md` stale even though
   `widget/src/widget.py` still matches.

### Scenario 9 — A check that fails without writing any diagnostic

Given: the alpha-role target node for unit widget is configured with the verification check whose
criteria is `widget/src/widget.py type-checks`, and the check exits with the non-zero exit code 2
while writing the output `Build loading: 4 packages` and `Elapsed 0.1s` only.

1. The agent evaluates the verification checks of the alpha-role target node for unit widget.
   Observed: one verification result reporting a failed status and carrying empty sanitized
   diagnostic output.
   Realized by: the component's own classification of a non-zero exit code as a failing outcome,
   which does not depend on the check having produced any error output, and the component's own
   scrubbing of every line the check wrote.

### Scenario 10 — Caching a failure so that the check runs once per file state

Given: the alpha-role target node for unit widget is configured with the verification check whose
criteria is `widget/src/widget.py type-checks`, the check exits with the non-zero exit code 1 while
writing `error: widget/src/widget.py line 7: the sprocket field type is not accepted`, and the
target's files have not been modified since a previous failing evaluation.

1. The agent evaluates the verification checks of the alpha-role target node for unit widget again.
   Observed: one verification result reporting a failed status with the same diagnostic output and
   reporting that the result was reused from cache, so the check subprocess is not invoked twice for
   an unchanged file state.
   Realized by: the component's own file hash cache, which stored the failing outcome with the
   recorded file hashes at the previous evaluation and therefore returns it without execution.

<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:17:14Z
CHANGE: Author control verification_impl concrete scenarios
-->
