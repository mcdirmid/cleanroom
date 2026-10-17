<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:17:16Z
CHANGE: Author control coordinate concrete scenarios
CODE_HASH: ed263389ca63
-->

# Concrete scenarios for `coordinate` (interface)

## Scenario 1 — Dispatching work and populating the open targets

Given: the session has no active target, and the caller holds the execution subgraph rooted at the
alpha-role node for unit widget, holding that node and the beta-role node for unit widget; the
alpha-role node for unit widget is dirty with the file alias `parts/widget/widget_spec.md`, and the
beta-role node for unit widget is dirty with the file alias `parts/widget/widget_contract.md`.

1. The agent asks the session coordinator for work in that execution subgraph.
   Observed: a control dispatch outcome reporting success and carrying the work schedule for the
   alpha-role node for unit widget and the beta-role node for unit widget, and two open targets,
   the alpha-role target for unit widget with the file alias `parts/widget/widget_spec.md` and the
   beta-role target for unit widget with the file alias `parts/widget/widget_contract.md`.

2. The agent checks disk for the scheduled task node whose file was missing.
   Observed: the target file is materialized from its starter template.

3. The agent encounters an ephemeral root session target `//session:target`.
   Observed: the session target is excluded from persistent node registration.

## Scenario 2 — Resolving a default target when the parameter is omitted

Given: the session tracks the open alpha-role target for unit widget with the file alias
`parts/widget/widget_spec.md`, the open beta-role target for unit widget with the file alias
`parts/widget/widget_contract.md`, and the clean gamma-role target for unit gadget with the file
alias `parts/gadget/gadget_spec.md`; the session coordinator most recently accessed the alpha-role
target for unit widget.

1. The agent asks the session coordinator to verify without supplying a target.
   Observed: the verification is performed for the alpha-role target for unit widget, reported
   through the file alias `parts/widget/widget_spec.md`, rather than for the beta-role target for
   unit widget or the clean gamma-role target for unit gadget.

## Scenario 3 — The open targets left once only one remains

Given: the session tracks the open alpha-role target for unit widget with the file alias
`parts/widget/widget_spec.md` and the clean beta-role target for unit widget with the file alias
`parts/widget/widget_contract.md`.

1. The agent asks the session coordinator to verify without supplying a target.
   Observed: the verification is performed for the alpha-role target for unit widget, reported
   through the file alias `parts/widget/widget_spec.md`, because it is the sole open target.

## Scenario 4 — Verifying one named target file

Given: the session tracks the open alpha-role target for unit widget with the file alias
`parts/widget/widget_spec.md`, whose verification check fails with the diagnostic
`the widget field type is not accepted`, and the open beta-role target for unit gadget with the file
alias `parts/gadget/gadget_spec.md`, whose verification check passes.

1. The agent asks the session coordinator to verify the target file
   `parts/widget/widget_spec.md`.
   Observed: a control dispatch outcome reporting the failing diagnostic
   `the widget field type is not accepted` for the alpha-role target for unit widget, and the
   beta-role target for unit gadget is not verified.

## Scenario 5 — Verifying every open target when no target is supplied

Given: the session tracks the open alpha-role target for unit widget with the file alias
`parts/widget/widget_spec.md`, whose verification check fails with the diagnostic
`the widget field type is not accepted`, and the open beta-role target for unit gadget with the file
alias `parts/gadget/gadget_spec.md`, whose verification check passes.

1. The agent asks the session coordinator to verify with no target supplied.
   Observed: a control dispatch outcome reporting the failing diagnostic
   `the widget field type is not accepted` for the alpha-role target for unit widget and reporting
   that the beta-role target for unit gadget verified successfully, and reporting for each target
   whether its result was reused from cache.

## Scenario 6 — Verifying with no open target at all

Given: the session tracks no open target, and its last two targets are the clean alpha-role target
for unit widget and the attributed beta-role target for unit gadget.

1. The agent asks the session coordinator to verify with no target supplied.
   Observed: a control dispatch outcome reporting that no target was verified, and a message
   reporting that no open target is available, so neither the clean alpha-role target for unit
   widget nor the attributed beta-role target for unit gadget is verified.

## Scenario 7 — Submitting an open target

Given: the session tracks the open alpha-role target for unit widget with the file alias
`parts/widget/widget_spec.md` and the open beta-role target for unit gadget with the file alias
`parts/gadget/gadget_spec.md`.

1. The agent submits the target `parts/widget/widget_spec.md` through the session coordinator with
   the change summary `renamed the widget field`.
   Observed: a control dispatch outcome reporting an accepted submission, the alpha-role target for
   unit widget now clean and no longer among the remaining open targets, and the beta-role target
   for unit gadget still open.

## Scenario 8 — Submitting a target that fails its preconditions

Given: the session tracks the open alpha-role target for unit widget with the file alias
`parts/widget/widget_spec.md`, whose verification check fails with the diagnostic
`the widget field type is not accepted`.

1. The agent submits the target `parts/widget/widget_spec.md` through the session coordinator with
   the change summary `renamed the widget field`.
   Observed: a control dispatch outcome reporting that the submission was not accepted and carrying
   an explicit message naming the failing verification, and the alpha-role target for unit widget
   still among the remaining open targets.

## Scenario 9 — Attributing a defect to a culprit

Given: the session tracks the open alpha-role target for unit widget with the file alias
`parts/widget/widget_spec.md`, which declares the eligible culprit beta-role target for unit gadget
with the file alias `parts/gadget/gadget_spec.md`, and which has the in-batch dependent alpha-role
target for unit sprocket with the file alias `parts/sprocket/sprocket_spec.md`; the critique
`the gadget contract declares the widget field twice` carries no newline character.

1. The agent attributes the defect through the session coordinator by blaming
   `parts/gadget/gadget_spec.md` with that critique.
   Observed: a control dispatch outcome reporting an accepted attribution that names the beta-role
   target for unit gadget, the alpha-role target for unit widget no longer among the remaining open
   targets, and the in-batch dependent alpha-role target for unit sprocket no longer among the
   remaining open targets.

## Scenario 10 — Recording task failure for an open target

Given: the session tracks the open alpha-role target for unit widget with the file alias
`parts/widget/widget_spec.md`, and the failure explanation is `the widget contract does not declare
the gadget field`.

1. The agent records the task failure through the session coordinator for
   `parts/widget/widget_spec.md` with that explanation.
   Observed: a control dispatch outcome reporting that the failure was recorded and carrying the
   explanation `the widget contract does not declare the gadget field`, and the alpha-role target
   for unit widget no longer among the remaining open targets.
