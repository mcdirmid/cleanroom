<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T18:21:03Z
LAST_CHANGED: 2026-10-11T03:14:19Z
CHANGE: Author control control_submit concrete scenarios
CODE_HASH: 6b95eb91cfeb
-->

# Concrete scenarios for `control_submit` (interface)

## Scenario 1 — Submitting a documented target whose files were modified

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

2. The agent submits the alpha-role target for unit gadget with no change summary.
   Observed: the submission is refused with an explicit error, because workspace files were
   modified and no change summary was given, and the alpha-role target node for unit gadget stays
   dirty.

## Scenario 2 — Submitting a target whose files were not modified

Given: role alpha is not an auditor role; the alpha-role target node for unit widget is dirty and
has no in-batch dependency; its verification checks are passing; the workspace file
`/ws/alpha_scope_a/parts/widget/widget_spec.md` has not been modified since the target was last
clean.

1. The agent submits the alpha-role target for unit widget with the change summary
   `tidy the widget wording`.
   Observed: the submission is refused with an explicit error, because workspace files were
   unmodified and a change summary was given, and the target node stays dirty.

2. The agent submits the alpha-role target for unit widget with no change summary.
   Observed: an accepted submission outcome, and the alpha-role target node for unit widget is
   clean.

## Scenario 3 — Submitting an auditor target

Given: role epsilon is an auditor role; the epsilon-role target node for unit widget is dirty, and
its verification checks are passing.

1. The agent submits the epsilon-role target for unit widget with the change summary
   `checked the widget contract`.
   Observed: the submission is refused with an explicit error, because auditor roles must not
   submit change summaries, and the target node stays dirty.

2. The agent submits the epsilon-role target for unit widget with no change summary.
   Observed: an accepted submission outcome, and the epsilon-role target node for unit widget is
   clean.

## Scenario 4 — Submitting a target whose verification has not passed

Given: role alpha is not an auditor role; the alpha-role target node for unit widget is dirty and
its verification check is failing with the feedback `the widget field type is not accepted`; the
alpha-role target node for unit gadget is dirty and its verification checks have not run.

1. The agent submits the alpha-role target for unit widget with the change summary
   `renamed the widget field`.
   Observed: the submission is refused with an explicit error, and the alpha-role target node for
   unit widget stays dirty.

2. The agent submits the alpha-role target for unit gadget with the change summary
   `renamed the gadget field`.
   Observed: the submission is refused with an explicit error, and the alpha-role target node for
   unit gadget stays dirty.

## Scenario 5 — A target whose in-batch dependency is still dirty

Given: role alpha is not an auditor role; the alpha-role target node for unit widget is dirty and
its verification checks are passing; its two in-batch dependencies are the alpha-role node for unit
gadget, which is dirty and unsubmitted, and the alpha-role node for unit sprocket, which is clean;
the workspace files of all three targets were modified.

1. The agent submits the alpha-role target for unit widget with the change summary
   `renamed the widget field`.
   Observed: the submission is refused with an explicit error, and the alpha-role target node for
   unit widget stays dirty.

2. The agent submits the alpha-role target for unit gadget with the change summary
   `renamed the gadget field`.
   Observed: an accepted submission outcome, and the alpha-role target node for unit gadget is
   clean.

3. The agent submits the alpha-role target for unit widget again with the change summary
   `renamed the widget field`.
   Observed: an accepted submission outcome, and the alpha-role target node for unit widget is
   clean.

## Scenario 6 — Submitting an auditor file target

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

2. The agent submits `/ws/epsilon_scope_a/parts/widget/widget_spec.md` as the epsilon-role file
   target.
   Observed: an accepted submission outcome; the canonical repository file
   `/repo/parts/widget/widget_spec.md` records the epsilon audit tag; and the local role workspace
   file `/ws/epsilon_scope_a/parts/widget/widget_spec.md` carries the same updated content.

## Scenario 7 — Submitting a producer file target

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

2. The agent submits `/ws/alpha_scope_a/parts/sprocket/sprocket_spec.md` as the alpha-role file
   target.
   Observed: the submission is refused with an explicit error, and the canonical repository file is
   not updated.

3. The agent modifies `/ws/alpha_scope_a/parts/widget/widget_spec.md` and submits it as the
   alpha-role file target with the change summary `renamed the widget field`.
   Observed: an accepted submission outcome; the canonical repository file
   `/repo/parts/widget/widget_spec.md` records the change summary `renamed the widget field`; and
   the local role workspace file `/ws/alpha_scope_a/parts/widget/widget_spec.md` carries the same
   updated content.

4. The agent submits `/ws/alpha_scope_a/parts/gadget/gadget_spec.md` as the alpha-role file target
   with no change summary.
   Observed: an accepted submission outcome, and the canonical repository file
   `/repo/parts/gadget/gadget_spec.md` records last cleaned `2026-01-12T00:00:00Z` and no change
   summary.
