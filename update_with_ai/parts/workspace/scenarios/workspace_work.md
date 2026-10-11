<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-11T22:09:02Z
LAST_CHANGED: 2026-10-11T03:06:09Z
CHANGE: Align workspace_work interface scenarios with the high-level specification
CODE_HASH: 0348960327ce
-->

# Concrete scenarios for `workspace_work` (interface)

## Scenario 1 — Taking a missing unit from nothing to clean

Given: role alpha is active with role beta as its upstream role, scope_a contains the unit
widget, the alpha-role target for widget does not exist yet, and the pending work buffer is empty.

1. The agent asks for work in scope_a as role alpha.
   Observed: one ready item, the alpha-role target for widget, reported with the reason that the
   target is missing and with no blocked items; the target is materialized from its starter
   template; and the ready target is recorded in the pending work buffer.

2. The agent completes the target and submits it.
   Observed: the target is no longer in the pending work buffer, and the buffer's other entries
   are untouched.

3. The agent asks for work again in scope_a as role alpha.
   Observed: the pending target is found clean, the buffer is cleared, and nothing is ready or
   blocked.

## Scenario 2 — Being stopped while a pending target is still dirty

Given: the pending work buffer lists the alpha-role target for widget, and that target is dirty.

1. The agent asks for work in scope_a as role alpha.
   Observed: the request is refused, naming the pending target and directing the agent to
   complete or blame it.

2. The agent asks again, forcing discovery.
   Observed: the request is not refused.

3. The agent completes the pending target and asks again without forcing.
   Observed: the target is found clean, the buffer is cleared, and discovery proceeds.

## Scenario 3 — A unit held back by a dirty upstream role

Given: scope_a contains the unit widget, which is dirty in role beta and in role alpha, and role
beta precedes role alpha in role precedence.

1. The agent asks for work in scope_a as role alpha.
   Observed: the alpha-role task for widget is among the blocked items and not among the ready
   items, and its blocked reason names the dirty beta-role prerequisite for the same unit.

2. The agent brings the beta-role target for widget clean and asks again.
   Observed: the alpha-role task for widget is now ready.

## Scenario 4 — What a target's dependencies look like

Given: role alpha declares role beta as a star-role dependency and role gamma as a silent
cross-role dependency, and the unit widget depends on the unit gadget.

1. The agent asks for work in scope_a as role alpha.
   Observed: the ready item for widget carries dependency files that include the star-role
   specification contracts for gadget and exclude the peer gamma-role implementation file for
   gadget.

2. The agent asks which contracts govern the alpha-role target for widget.
   Observed: the answer includes the upstream specification contracts for widget and the
   interface definitions the target depends on, and every returned path is an existing readable
   file.

## Scenario 5 — Asking as a role that does not exist

Given: no role definition declares role zeta.

1. The agent asks for work in scope_a as role zeta.
   Observed: the request fails explicitly and names zeta, and no work is reported.
