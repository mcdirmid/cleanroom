<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:14:20Z
CHANGE: Author control submit_impl concrete scenarios
CODE_HASH: 6fa5b1132390
-->

# Concrete scenarios for `submit_impl` (implementation)

Scenarios 1 through 7 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones
is what makes realizability structural: an implementation scenario that cannot name a realization
for its observation is a defect in the implementation rather than a gap in the set. Scenarios 8
through 12 cover behaviours the interface does not expose to a caller, and each of them is a
candidate for the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — Submitting a documented target whose files were modified

Given: role alpha is not an auditor role; the alpha-role target node for unit widget is dirty, has
no in-batch dependency, and has passing verification checks, and its workspace file
`/ws/alpha_scope_a/parts/widget/widget_spec.md` was modified after the target was last clean; the
alpha-role target node for unit gadget is likewise dirty with no in-batch dependency and passing
verification checks, and its workspace file `/ws/alpha_scope_a/parts/gadget/gadget_spec.md` was
modified after that target was last clean.

1. The agent submits the alpha-role target for unit widget with the change summary
   `renamed the widget field`.
   Observed: an accepted submission outcome; the alpha-role target node for unit widget is clean;
   and its change summary is `renamed the widget field`.
   Realized by: verification status through `verification`; role configuration lookups
   through `agent_node_config` for alpha's auditor status; the modification determination through
   `src_metadata`'s comparison of the recorded in-band code hash with the recomputed one; the clean
   status transition with the change summary through `dag_storage`; and the component's own
   accepted outcome construction.

2. The agent submits the alpha-role target for unit gadget with no change summary.
   Observed: the submission is refused with an explicit error, because workspace files were
   modified and no change summary was given, and the alpha-role target node for unit gadget stays
   dirty.
   Realized by: `src_metadata` reporting a modification and the component's own change
   documentation rule, which refuses before `dag_storage` marks the node clean.

### Scenario 2 — Submitting a target whose files were not modified

Given: role alpha is not an auditor role; the alpha-role target node for unit widget is dirty and
has no in-batch dependency; its verification checks are passing; the workspace file
`/ws/alpha_scope_a/parts/widget/widget_spec.md` has not been modified since the target was last
clean.

1. The agent submits the alpha-role target for unit widget with the change summary
   `tidy the widget wording`.
   Observed: the submission is refused with an explicit error, because workspace files were
   unmodified and a change summary was given, and the target node stays dirty.
   Realized by: `src_metadata` reporting no modification, the auditor check through
   `agent_node_config`, and the component's own change documentation rule.

2. The agent submits the alpha-role target for unit widget with no change summary.
   Observed: an accepted submission outcome, and the alpha-role target node for unit widget is
   clean.
   Realized by: `verification` for the passing checks and `dag_storage` for the clean
   status transition.

### Scenario 3 — Submitting an auditor target

Given: role epsilon is an auditor role; the epsilon-role target node for unit widget is dirty, and
its verification checks are passing.

1. The agent submits the epsilon-role target for unit widget with the change summary
   `checked the widget contract`.
   Observed: the submission is refused with an explicit error, because auditor roles must not
   submit change summaries, and the target node stays dirty.
   Realized by: role configuration lookups through `agent_node_config`, which mark epsilon as an
   auditor role, and the component's own refusal, which names that rule.

2. The agent submits the epsilon-role target for unit widget with no change summary.
   Observed: an accepted submission outcome, and the epsilon-role target node for unit widget is
   clean.
   Realized by: `verification` for the passing checks and `dag_storage` for the clean
   status transition.

### Scenario 4 — Submitting a target whose verification has not passed

Given: role alpha is not an auditor role; the alpha-role target node for unit widget is dirty and
its verification check is failing with the feedback `the widget field type is not accepted`; the
alpha-role target node for unit gadget is dirty and its verification checks have not run.

1. The agent submits the alpha-role target for unit widget with the change summary
   `renamed the widget field`.
   Observed: the submission is refused with an explicit error, and the alpha-role target node for
   unit widget stays dirty.
   Realized by: the failing verification status reported by `verification` and the
   component's own refusal, which carries the failing check's feedback.

2. The agent submits the alpha-role target for unit gadget with the change summary
   `renamed the gadget field`.
   Observed: the submission is refused with an explicit error, and the alpha-role target node for
   unit gadget stays dirty.
   Realized by: `verification` reporting that the checks have not run, and the component's
   own refusal.

### Scenario 5 — A target whose in-batch dependency is still dirty

Given: role alpha is not an auditor role; the alpha-role target node for unit widget is dirty and
its verification checks are passing; its two in-batch dependencies are the alpha-role node for unit
gadget, which is dirty and unsubmitted, and the alpha-role node for unit sprocket, which is clean;
the workspace files of all three targets were modified.

1. The agent submits the alpha-role target for unit widget with the change summary
   `renamed the widget field`.
   Observed: the submission is refused with an explicit error, and the alpha-role target node for
   unit widget stays dirty.
   Realized by: the in-batch dependency statuses read through `dag_storage` and the component's own
   in-batch dependency check, which refuses before the clean status transition.

2. The agent submits the alpha-role target for unit gadget with the change summary
   `renamed the gadget field`.
   Observed: an accepted submission outcome, and the alpha-role target node for unit gadget is
   clean.
   Realized by: `verification` for the passing checks and `dag_storage` for the clean
   status transition with the change summary.

3. The agent submits the alpha-role target for unit widget again with the change summary
   `renamed the widget field`.
   Observed: an accepted submission outcome, and the alpha-role target node for unit widget is
   clean.
   Realized by: the same path, now finding every in-batch dependency clean.

### Scenario 6 — Submitting an auditor file target

Given: role epsilon is an auditor role; the audited implementation file in the canonical repository
is `/repo/parts/widget/widget_spec.md`, and its companion test file is
`/repo/parts/widget/widget_test.md`; the local role workspace is `/ws/epsilon_scope_a`, holding
`/ws/epsilon_scope_a/parts/widget/widget_spec.md` and
`/ws/epsilon_scope_a/parts/widget/widget_test.md`.

1. The agent submits `/ws/epsilon_scope_a/parts/widget/widget_test.md` as the epsilon-role file
   target.
   Observed: the submission is refused with an explicit error, because a test file may not be
   submitted as an audit target, and the canonical repository file records no audit tag for role
   epsilon.
   Realized by: the component's own resolution of the target file path and unit name through
   `agent_file_alias` and its own test file submission prohibition, which refuses before
   `src_metadata` writes anything.

2. The agent submits `/ws/epsilon_scope_a/parts/widget/widget_spec.md` as the epsilon-role file
   target.
   Observed: an accepted submission outcome; the canonical repository file
   `/repo/parts/widget/widget_spec.md` records the epsilon audit tag; and the local role workspace
   file `/ws/epsilon_scope_a/parts/widget/widget_spec.md` carries the same updated content.
   Realized by: path resolution through `agent_file_alias`; role configuration lookups through
   `agent_node_config` for epsilon's audit tag; `src_metadata`, which stamps the in-band audit tag
   in the canonical file; and the component's own synchronization of the updated canonical file
   back to the role workspace.

### Scenario 7 — Submitting a producer file target

Given: role alpha is not an auditor role; `/ws/alpha_scope_a/parts/widget/widget_spec.md` is a
read-write file for alpha inside the active directory scope patterns, with canonical repository
copy `/repo/parts/widget/widget_spec.md`; `/ws/alpha_scope_a/parts/widget/widget_contract.md` is a
read-only file for alpha; `/ws/alpha_scope_a/parts/sprocket/sprocket_spec.md` is a read-write file
for alpha outside the active directory scope patterns;
`/ws/alpha_scope_a/parts/gadget/gadget_spec.md` is a read-write file for alpha inside the active
directory scope patterns, with canonical repository copy `/repo/parts/gadget/gadget_spec.md`, and
it has not been modified since its target was last clean; the current UTC timestamp is
`2026-01-12T00:00:00Z`.

1. The agent submits `/ws/alpha_scope_a/parts/widget/widget_contract.md` as the alpha-role file
   target.
   Observed: the submission is refused with an explicit error, and the canonical repository file is
   not updated.
   Realized by: role configuration lookups through `agent_node_config`, whose read-only files
   restrict the bound file to reading, and the component's own write permission check.

2. The agent submits `/ws/alpha_scope_a/parts/sprocket/sprocket_spec.md` as the alpha-role file
   target.
   Observed: the submission is refused with an explicit error, and the canonical repository file is
   not updated.
   Realized by: role configuration lookups through `agent_node_config` for alpha's active
   directory scope patterns and the component's own scope check.

3. The agent modifies `/ws/alpha_scope_a/parts/widget/widget_spec.md` and submits it as the
   alpha-role file target with the change summary `renamed the widget field`.
   Observed: an accepted submission outcome; the canonical repository file
   `/repo/parts/widget/widget_spec.md` records the change summary `renamed the widget field` and
   has any ephemeral code hash stripped; and the local role workspace file
   `/ws/alpha_scope_a/parts/widget/widget_spec.md` carries the same updated content with its
   ephemeral code hash refreshed to reflect the new code baseline.
   Realized by: path resolution through `agent_file_alias`; the modification determination through
   `src_metadata` comparing against the ephemeral code hash; `src_metadata` again, updating the in-band
   change metadata in the canonical file while stripping the ephemeral code hash; and the component's
   own synchronization of the updated canonical file back to the role workspace with a refreshed
   ephemeral code hash.

4. The agent submits `/ws/alpha_scope_a/parts/gadget/gadget_spec.md` as the alpha-role file target
   with no change summary.
   Observed: an accepted submission outcome, and the canonical repository file
   `/repo/parts/gadget/gadget_spec.md` records last cleaned `2026-01-12T00:00:00Z` and no change
   summary, with any ephemeral code hash stripped.
   Realized by: `src_metadata` reporting no modification against the ephemeral code hash and, on the
   clean transition, advancing the in-band last cleaned timestamp, withdrawing the change summary, and
   stripping any ephemeral code hash.

## Implementation-only

### Scenario 8 — What a refused submission reports

Given: role alpha is not an auditor role; the alpha-role target node for unit widget is dirty, its
verification checks have not run, and its in-batch dependency, the alpha-role node for unit
sprocket, is dirty; the workspace file
`/ws/alpha_scope_a/parts/widget/widget_spec.md` was modified after the target was last clean.

1. The agent submits the alpha-role target for unit widget with the change summary
   `renamed the widget field`.
   Observed: the submission is refused with an explicit error stating that verification has not
   passed for the target.
   Realized by: `verification` reporting that the checks have not run, and the component's
   own error construction, which raises that precondition first.

2. The verification checks for the alpha-role target node are run and pass, and the agent submits
   the target again with the same change summary.
   Observed: the submission is refused with an explicit error naming the dirty in-batch dependency
   of unit sprocket in role alpha.
   Realized by: `dag_storage` node status for the in-batch dependency and the component's own error
   construction, which names the offending dependency.

### Scenario 9 — How an auditor submission is reported

Given: role epsilon is an auditor role whose audit tag is `EPSILON_AUDIT`; the audited
implementation file in the canonical repository is `/repo/parts/widget/widget_spec.md`, and its
companion test file is `/repo/parts/widget/widget_test.md`; the local role workspace is
`/ws/epsilon_scope_a`.

1. The agent submits `/ws/epsilon_scope_a/parts/widget/widget_spec.md` as the epsilon-role file
   target.
   Observed: an accepted submission outcome whose message is formatted with the audit tag
   `EPSILON_AUDIT`, and the canonical repository file records that audit tag while its companion
   test file `/repo/parts/widget/widget_test.md` is left unmodified.
   Realized by: the component's own resolution of the audited implementation and its companion test
   file, role configuration lookups through `agent_node_config` for the audit tag, `src_metadata`
   for the in-band stamp, and the component's own outcome message construction.

### Scenario 10 — How a producer submission is reported

Given: role alpha is not an auditor role, and `/ws/alpha_scope_a/parts/widget/widget_spec.md` is a
read-write file for alpha inside the active directory scope patterns with canonical repository copy
`/repo/parts/widget/widget_spec.md`; `/ws/alpha_scope_a/parts/gadget/gadget_spec.md` is likewise a
read-write file for alpha inside those patterns, with canonical repository copy
`/repo/parts/gadget/gadget_spec.md`, and it has not been modified since its target was last clean.

1. The agent modifies the widget file and submits it as the alpha-role file target with the change
   summary `renamed the widget field`.
   Observed: an accepted submission outcome whose message is formatted with the change summary
   `renamed the widget field`.
   Realized by: `src_metadata` updating the in-band change metadata, and the component's own
   outcome message construction, which formats the change summary into the message.

2. The agent submits the gadget file as the alpha-role file target with no change summary.
   Observed: an accepted submission outcome whose message is formatted with the clean status of the
   file.
   Realized by: `src_metadata` reporting no modification, and the component's own outcome message
   construction, which formats the clean status into the message.

### Scenario 11 — A rewrite of the metadata header is not a modification

Given: role alpha is not an auditor role; the alpha-role target node for the widget file is dirty;
`/ws/alpha_scope_a/parts/widget/widget_spec.md` is a read-write file for alpha inside the active
directory scope patterns and has had its in-band metadata header rewritten, with its last cleaned
timestamp advanced to `2026-01-13T00:00:00Z`, while its code body is unchanged since the target was
last clean.

1. The agent submits the file as the alpha-role file target with no change summary.
   Observed: an accepted submission outcome, because the file counts as unmodified.
   Realized by: `src_metadata`, whose modification comparison hashes the whitespace-stripped code
   body outside the metadata header, so the header rewrite leaves the recorded and recomputed code
   hashes equal.

### Scenario 12 — A refused submission leaves no clean status and no change summary

Given: role alpha is not an auditor role; the alpha-role target node for unit widget is dirty with
no change summary, and its verification check is failing with the feedback
`the widget field type is not accepted`; the workspace file
`/ws/alpha_scope_a/parts/widget/widget_spec.md` was modified after the target was last clean.

1. The agent submits the alpha-role target for unit widget with the change summary
   `renamed the widget field`.
   Observed: the submission is refused with an explicit error; the target node stays dirty; and no
   change summary is recorded for it.
   Realized by: `verification` failing the precondition, so that the component's own clean
   status transition through `dag_storage` is never reached.

### Scenario 13 — Refusing submission when session feedback is present and files were unmodified

Given: role alpha is not an auditor role; the alpha-role target node for unit widget is dirty and has
no in-batch dependency; its verification checks are passing; it carries session feedback
`rename widget field`; its workspace file `/ws/alpha_scope_a/parts/widget/widget_spec.md` has not
been modified since the target was last clean.

1. The agent submits the alpha-role target for unit widget with no change summary.
   Observed: the submission is refused with an explicit error explaining that session feedback is
   present and workspace files must be modified to address feedback before submitting or fail must
   be called, and the alpha-role target node for unit widget stays dirty.
   Realized by: session feedback check through `agent_node_config`, file modification check through
   `src_metadata`, and the component's own feedback submission gating rule.

