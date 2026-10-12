<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T18:21:03Z
LAST_CHANGED: 2026-10-11T03:06:09Z
CHANGE: Align workspace_work_impl scenarios with the high-level specification
CODE_HASH: a26befa8db0c
-->

# Concrete scenarios for `workspace_work_impl` (implementation)

Scenarios 1 through 5 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones
is what makes realizability structural: an implementation scenario that cannot name a realization
for its observation is a defect in the implementation rather than a gap in the set. Scenarios 6
through 10 cover behaviours the interface does not expose to a caller, and each of them is a
candidate for the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — Taking a missing unit from nothing to clean

Given: role alpha is active with role beta as its upstream role, scope_a contains the unit
widget, the alpha-role target for widget does not exist yet, and the pending work buffer is empty.

1. The agent asks for work in scope_a as role alpha.
   Observed: one ready item, the alpha-role target for widget, reported with the reason that the
   target is missing and with no blocked items; the target is materialized from its starter
   template; and the ready target is recorded in the pending work buffer.
   Realized by: role configuration lookups through `workspace_registry` for alpha's source pattern
   and its upstream roles; directory-scoped discovery, dependency checking, and role precedence
   through `control_work_scheduler`; in-band source metadata extraction through `src_metadata` for
   the dirtiness reason; starter template materialization through `dag_storage`; and the
   component's own pending buffer mechanics, which write the ready target into
   `.cleanroom_pending_work.json`.

2. The agent completes the target and submits it.
   Observed: the target is no longer in the pending work buffer, and the buffer's other entries
   are untouched.
   Realized by: the component's own pending buffer mechanics, matching the submitted target by its
   full path or by its unit stem and filtering that entry out without clearing the others.

3. The agent asks for work again in scope_a as role alpha.
   Observed: the pending target is found clean, the buffer is cleared, and nothing is ready or
   blocked.
   Realized by: in-band source metadata extraction through `src_metadata` to judge the pending
   target, the component's own deletion of `.cleanroom_pending_work.json`, and
   `control_work_scheduler` for the re-evaluation.

### Scenario 2 — Being stopped while a pending target is still dirty

Given: the pending work buffer lists the alpha-role target for widget, and that target is dirty.

1. The agent asks for work in scope_a as role alpha.
   Observed: the request is refused, naming the pending target and directing the agent to
   complete or blame it.
   Realized by: the component's own read of the pending buffer; in-band source metadata extraction
   through `src_metadata` to judge the pending target; and the component's own refusal, which
   names the offending target.

2. The agent asks again, forcing discovery.
   Observed: the request is not refused.
   Realized by: the component's own handling of the forcing input, which skips the pending check.

3. The agent completes the pending target and asks again without forcing.
   Observed: the target is found clean, the buffer is cleared, and discovery proceeds.
   Realized by: `src_metadata`, the component's buffer deletion, and `control_work_scheduler`.

### Scenario 3 — A unit held back by a dirty upstream role

Given: scope_a contains the unit widget, which is dirty in role beta and in role alpha, and role
beta precedes role alpha in role precedence.

1. The agent asks for work in scope_a as role alpha.
   Observed: the alpha-role task for widget is among the blocked items and not among the ready
   items, and its blocked reason names the dirty beta-role prerequisite for the same unit.
   Realized by: role configuration lookups through `workspace_registry` for alpha's upstream
   roles; `control_work_scheduler` for directory-scoped dependency checking and precedence; and
   in-band source metadata extraction through `src_metadata` for the beta-role target's
   dirtiness.

2. The agent brings the beta-role target for widget clean and asks again.
   Observed: the alpha-role task for widget is now ready.
   Realized by: the same path, now finding the beta-role target clean.

### Scenario 4 — What a target's dependencies look like

Given: role alpha declares role beta as a star-role dependency and role gamma as a silent
cross-role dependency, and the unit widget depends on the unit gadget.

1. The agent asks for work in scope_a as role alpha.
   Observed: the ready item for widget carries dependency files that include the star-role
   specification contracts for gadget and exclude the peer gamma-role implementation file for
   gadget.
   Realized by: role configuration lookups through `workspace_registry` for the star-role and
   silent cross-role dependencies, and the component's own filtering of the dependency list.

2. The agent asks which contracts govern the alpha-role target for widget.
   Observed: the answer includes the upstream specification contracts for widget and the
   interface definitions the target depends on, and every returned path is an existing readable
   file.
   Realized by: role definition lookups through `workspace_registry`, and the component's own
   discovery of the contract and interface files on disk.

### Scenario 5 — Asking as a role that does not exist

Given: no role definition declares role zeta.

1. The agent asks for work in scope_a as role zeta.
   Observed: the request fails explicitly and names zeta, and no work is reported.
   Realized by: role configuration lookups through `workspace_registry`, whose resolution of an
   undeclared role fails, and the component's own propagation of that failure without
   substituting a synthetic role.

## Implementation-only

### Scenario 6 — Judging a pending target that is missing

Given: role alpha declares a source pattern and upstream dependencies, the alpha-role target for
widget is missing from disk, and the beta-role target for widget is clean.

1. The agent asks whether the pending alpha-role target for widget is dirty.
   Observed: dirty, and the target is materialized from a starter template.
   Realized by: in-band source metadata extraction through `src_metadata`, which finds no
   metadata for a missing file, and starter template materialization through `dag_storage`.

2. The agent asks again once the materialized target carries current in-band metadata.
   Observed: not dirty.
   Realized by: `src_metadata`, now finding current metadata on a present target.

### Scenario 7 — An auditor unit whose feedback targets are not all audited

Given: the active role epsilon is an auditor whose feedback role targets are the alpha-role and
beta-role targets for widget, the alpha-role target has no role audit attribute, and the beta-role
target carries a current one.

1. The agent asks whether the auditor unit for widget is dirty.
   Observed: dirty, because the alpha-role feedback target lacks the required role audit
   attribute.
   Realized by: in-band source metadata extraction through `src_metadata` across every feedback
   role target configured for the active auditor role, with that role's feedback dependencies and
   audit tag supplied by role configuration lookups through `workspace_registry`.

2. The alpha-role target is given a current role audit attribute and is not modified afterwards,
   and the agent asks again.
   Observed: not dirty.
   Realized by: `src_metadata`, now finding a current audit attribute on every feedback target.

3. The alpha-role target is modified after that audit, and the agent asks again.
   Observed: dirty.
   Realized by: `src_metadata`, comparing the target's modification against its audit attribute.

4. The beta-role target is removed, and the agent asks again.
   Observed: dirty, because a feedback target is missing.
   Realized by: `src_metadata`, reporting a feedback target that is absent.

### Scenario 8 — A target path that matches no role

Given: one target path matches no configured role source pattern.

1. The agent asks for the contracts of that path.
   Observed: an explicit exception, and no synthetic path resolution.
   Realized by: role configuration lookups through `workspace_registry`, whose pattern resolution
   finds no match, and the component's own propagation of that failure.

### Scenario 9 — Where units and dependencies come from

Given: one part directory has a build definition declaring the units widget and gadget and
widget's dependency on gadget; a second part directory has only specifications, whose widget
specification declares imports, implements, and assembles entries; a third has neither, only
component directories named widget and gadget.

1. The agent asks for work in the first part directory.
   Observed: widget and gadget are discovered as units, with widget depending on gadget.
   Realized by: the component's own discovery mechanics, reading the build definition when one is
   present.

2. The agent asks for work in the second part directory.
   Observed: units and dependencies come from the specifications, covering the imported,
   implemented, and assembled entries.
   Realized by: the component's own discovery mechanics, reading the specifications when no build
   definition is present.

3. The agent asks for work in the third part directory.
   Observed: widget and gadget are discovered as units from their filesystem component names.
   Realized by: the component's own discovery mechanics, deriving unit names from component
   directories when neither a build definition nor a specification is present.

### Scenario 10 — Recording ready work and compiling the summary

Given: the agent is working as alpha inside a role workspace, scope_a holds the ready unit
widget, dirty because the beta-role contract changed, and the blocked unit gadget, whose
prerequisite sprocket is dirty.

1. The agent asks for work.
   Observed: the pending work buffer lists the widget target path; the summary details widget as
   a ready task with the reason that the beta-role contract changed, its dependency paths, and
   its companion contract files; details gadget as blocked with the cause that sprocket is dirty;
   and gives role-specific instructions for alpha.
   Realized by: the component's own pending buffer write, the queue compiled from
   `control_work_scheduler` with the directory scope, dependency and contract lookups through
   `workspace_registry`, and dirtiness reasons from `src_metadata`.
