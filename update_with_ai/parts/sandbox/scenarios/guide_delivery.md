<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:17:20Z
CHANGE: Author sandbox guide_delivery concrete scenarios
CODE_HASH: 36f8a1aa0ac8
-->

# Concrete scenarios for `guide_delivery` (interface)

## Scenario 1 — Parsing a guide out of content carrying a summary, a checklist, and two milestones

Given: step mode is active for the agent session of role alpha, and the content of the configured
guide file holds the heading "## Summary", then the line "clean the widget target by inspecting the
widget contract and then the widget source", then the heading "## Lint checks", then the line
"- the widget source ends with a newline", then the heading "## Inspect the widget contract", then
the line "Read widget/contracts/widget.md and confirm the declared field.", then the heading
"## Clean the widget source", then the line "Set widget_height to 42 in widget/src/widget.py.",
then the heading "## Verification failure", then the line "the widget source must set
widget_height to 42"; no step section has been delivered.

1. The agent asks the guide delivery to parse that content into a guide.
   Observed: the guide carries the summary "clean the widget target by inspecting the widget
   contract and then the widget source", exactly two step sections numbered 1 and 2, titled
   "Inspect the widget contract" and "Clean the widget source", holding the content "Read
   widget/contracts/widget.md and confirm the declared field." and "Set widget_height to 42 in
   widget/src/widget.py.", and the verification failure instructions "the widget source must set
   widget_height to 42", while the checklist heading "## Lint checks" contributes no step section.

2. The agent asks the guide delivery for its configured guide.
   Observed: that same guide, carrying the summary "clean the widget target by inspecting the widget
   contract and then the widget source", the two step sections numbered 1 and 2 in that order with
   their content, and the verification failure instructions "the widget source must set
   widget_height to 42".

3. The agent asks the guide delivery whether steps remain.
   Observed: steps remain, because neither of the two step sections has been delivered.

## Scenario 2 — Parsing content that carries no step section

Given: step mode is active for the agent session of role beta, the content of one guide file is
empty, and the content of another guide file holds the heading "## Summary", then the line "clean
the gadget target", then the heading "## Lint checks", then the line "- the gadget source ends with
a newline".

1. The agent asks the guide delivery to parse the empty content.
   Observed: a guide holding no step section and no verification failure instruction, and the guide
   delivery reports that no steps remain.

2. The agent asks the guide delivery to parse the checklist-only content.
   Observed: a guide holding no step section and no verification failure instruction, and the guide
   delivery reports that no steps remain, because the headings "Summary" and "Lint checks" are
   excluded from the step sections.

## Scenario 3 — Recording an initial primer and delivering both milestones on passing verifications

Given: step mode is active for the agent session of role alpha, the guide holds the summary "clean
the widget target by inspecting the widget contract and then the widget source", the step section 1
titled "Inspect the widget contract" with the content "Read widget/contracts/widget.md and confirm
the declared field.", the step section 2 titled "Clean the widget source" with the content "Set
widget_height to 42 in widget/src/widget.py.", and the verification failure instructions "the widget
source must set widget_height to 42"; no initial primer has been recorded and no step section has
been delivered.

1. The agent records the initial primer "the widget target is cleaned in two milestones before the
   beta-role release".
   Observed: the guide delivery holds that primer as the first instructional content of the session
   and reports that steps remain.

2. The agent asks the guide delivery to advance a step with verification passed and empty failure
   diagnostics.
   Observed: the response delivers the content "Read widget/contracts/widget.md and confirm the
   declared field." as the next milestone, which is step section 1, and steps remain because step
   section 2 has not been delivered.

3. The agent asks the guide delivery to advance a step with verification passed and empty failure
   diagnostics.
   Observed: the response delivers the content "Set widget_height to 42 in widget/src/widget.py."
   as the next milestone, which is step section 2, and the guide delivery now reports that no steps
   remain because no step section follows step section 2.

## Scenario 4 — Advancing once every milestone has been delivered

Given: step mode is active for the agent session of role alpha, the guide holds the step section 1
titled "Inspect the widget contract" with the content "Read widget/contracts/widget.md and confirm
the declared field." and the step section 2 titled "Clean the widget source" with the content "Set
widget_height to 42 in widget/src/widget.py.", both step sections have been delivered in that
order, and the guide delivery reports that no steps remain.

1. The agent asks the guide delivery to advance a step with verification passed and empty failure
   diagnostics.
   Observed: no response is produced, and the guide delivery still reports that no steps remain.

## Scenario 5 — A failing verification before any milestone has been delivered

Given: step mode is active for the agent session of role alpha, the guide holds the summary "clean
the widget target by inspecting the widget contract and then the widget source", the step section 1
titled "Inspect the widget contract" with the content "Read widget/contracts/widget.md and confirm
the declared field.", and the verification failure instructions "the widget source must set
widget_height to 42"; the initial primer "the widget target is cleaned in two milestones before the
beta-role release" has been recorded, and no step section has been delivered.

1. The agent asks the guide delivery to advance a step with verification not passed and the failure
   diagnostics "widget/src/widget.py still holds widget_height = 30".
   Observed: the response reports the failure diagnostics "widget/src/widget.py still holds
   widget_height = 30" alongside the verification failure instructions "the widget source must set
   widget_height to 42", no step section content is delivered, and the guide delivery still reports
   that steps remain.

2. The agent asks the guide delivery to advance a step with verification passed and empty failure
   diagnostics.
   Observed: the response delivers the content "Read widget/contracts/widget.md and confirm the
   declared field." as the next milestone, which is step section 1, so the failed advancement left
   the delivery before any step section.

## Scenario 6 — A failing verification while a milestone is active

Given: step mode is active for the agent session of role alpha, the guide holds the step section 1
titled "Inspect the widget contract" with the content "Read widget/contracts/widget.md and confirm
the declared field.", the step section 2 titled "Clean the widget source" with the content "Set
widget_height to 42 in widget/src/widget.py.", and the verification failure instructions "the widget
source must set widget_height to 42"; step section 1 has been delivered and is the milestone the
delivery currently holds.

1. The agent asks the guide delivery to advance a step with verification not passed and the failure
   diagnostics "widget/src/widget.py still holds widget_height = 30".
   Observed: the response reports that diagnostic "widget/src/widget.py still holds
   widget_height = 30" alongside the verification failure instructions "the widget source must set
   widget_height to 42", the delivery retains step section 1 as the milestone it currently holds,
   and no content of step section 2 is delivered.

2. The agent asks the guide delivery to advance a step with verification passed and empty failure
   diagnostics.
   Observed: the response delivers the content "Set widget_height to 42 in widget/src/widget.py."
   as the next milestone, which is step section 2, because the delivery held its position at step
   section 1.

## Scenario 7 — A failing verification where the guide configures no failure instructions

Given: step mode is active for the agent session of role gamma, the guide holds the step section 1
titled "Inspect the sprocket contract" with the content "Read sprocket/contracts/sprocket.md and
confirm the declared field.", holds no verification failure instructions, and no step section has
been delivered.

1. The agent asks the guide delivery to advance a step with verification not passed and the failure
   diagnostics "sprocket/src/sprocket.py still holds sprocket_height = 10".
   Observed: the response reports the failure diagnostics "sprocket/src/sprocket.py still holds
   sprocket_height = 10", reports no verification failure instructions, delivers no step section
   content, and the guide delivery still reports that steps remain.
