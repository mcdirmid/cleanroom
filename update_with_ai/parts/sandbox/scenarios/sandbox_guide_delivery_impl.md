<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T21:57:18Z
LAST_CHANGED: 2026-10-11T03:17:20Z
CHANGE: Author sandbox sandbox_guide_delivery_impl concrete scenarios
CODE_HASH: 6b00e684a52a
-->

# Concrete scenarios for `sandbox_guide_delivery_impl` (implementation)

Scenarios 1 through 7 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones
is what makes realizability structural: an implementation scenario that cannot name a realization
for its observation is a defect in the implementation rather than a gap in the set. Scenarios 8
through 11 cover behaviours the interface does not expose to a caller, and each of them is a
candidate for the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — Parsing a guide out of content carrying a summary, a checklist, and two milestones

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
   Realized by: the component's own markdown section scan over the configured guide file content
   supplied by the step-mode session configuration of `agent_node_config`, which indexes level-two
   headings into sequential step sections, captures a heading beginning with `Verification failure`
   as the verification failure instructions, and excludes sections whose title begins with `Summary`
   or `Lint checks`.

2. The agent asks the guide delivery for its configured guide.
   Observed: that same guide, carrying the summary "clean the widget target by inspecting the widget
   contract and then the widget source", the two step sections numbered 1 and 2 in that order with
   their content, and the verification failure instructions "the widget source must set
   widget_height to 42".
   Realized by: the component's own stored guide, exposed by the parse operation that writes it.

3. The agent asks the guide delivery whether steps remain.
   Observed: steps remain, because neither of the two step sections has been delivered.
   Realized by: the component's own step offset against the parsed step sections, which the parse
   operation writes and step advancement advances.

### Scenario 2 — Parsing content that carries no step section

Given: step mode is active for the agent session of role beta, the content of one guide file is
empty, and the content of another guide file holds the heading "## Summary", then the line "clean
the gadget target", then the heading "## Lint checks", then the line "- the gadget source ends with
a newline".

1. The agent asks the guide delivery to parse the empty content.
   Observed: a guide holding no step section and no verification failure instruction, and the guide
   delivery reports that no steps remain.
   Realized by: the component's own markdown section scan, which finds no level-two heading and
   therefore creates no step section, and its own step offset, which then reports that no steps
   remain.

2. The agent asks the guide delivery to parse the checklist-only content.
   Observed: a guide holding no step section and no verification failure instruction, and the guide
   delivery reports that no steps remain, because the headings "Summary" and "Lint checks" are
   excluded from the step sections.
   Realized by: the same scan, whose exclusion of titles beginning with `Summary` or `Lint checks`
   leaves no step section, over the configured guide file content of `agent_node_config`.

### Scenario 3 — Recording an initial primer and delivering both milestones on passing verifications

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
   Realized by: the component's own initial primer record, written by the recording operation that
   session entry drives.

2. The agent asks the guide delivery to advance a step with verification passed and empty failure
   diagnostics.
   Observed: the response delivers the content "Read widget/contracts/widget.md and confirm the
   declared field." as the next milestone, which is step section 1, and steps remain because step
   section 2 has not been delivered.
   Realized by: the component's own step offset, which activates step section 1 and assembles the
   milestone response, with the step sections coming from the parsed configured guide content of
   `agent_node_config`.

3. The agent asks the guide delivery to advance a step with verification passed and empty failure
   diagnostics.
   Observed: the response delivers the content "Set widget_height to 42 in widget/src/widget.py."
   as the next milestone, which is step section 2, and the guide delivery now reports that no steps
   remain because no step section follows step section 2.
   Realized by: the component's own step offset, which activates step section 2 and then reports
   that no further step section remains.

### Scenario 4 — Advancing once every milestone has been delivered

Given: step mode is active for the agent session of role alpha, the guide holds the step section 1
titled "Inspect the widget contract" with the content "Read widget/contracts/widget.md and confirm
the declared field." and the step section 2 titled "Clean the widget source" with the content "Set
widget_height to 42 in widget/src/widget.py.", both step sections have been delivered in that
order, and the guide delivery reports that no steps remain.

1. The agent asks the guide delivery to advance a step with verification passed and empty failure
   diagnostics.
   Observed: no response is produced, and the guide delivery still reports that no steps remain.
   Realized by: the component's own step offset, which already stands past the last step section, so
   no response is assembled.

### Scenario 5 — A failing verification before any milestone has been delivered

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
   Realized by: the component's own failure response assembly, which combines the recorded initial
   primer content with the captured verification failure instructions and the supplied failure
   diagnostics, and its own step offset, which stays before step section 1.

2. The agent asks the guide delivery to advance a step with verification passed and empty failure
   diagnostics.
   Observed: the response delivers the content "Read widget/contracts/widget.md and confirm the
   declared field." as the next milestone, which is step section 1, so the failed advancement left
   the delivery before any step section.
   Realized by: the component's own step offset, unchanged by the failed advancement, and its own
   milestone response assembly.

### Scenario 6 — A failing verification while a milestone is active

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
   Realized by: the component's own failure response assembly, which combines the active step
   section content introduced by `Now check carefully:` with the captured verification failure
   instructions and the supplied failure diagnostics, and its own step offset, which is left where
   it stands.

2. The agent asks the guide delivery to advance a step with verification passed and empty failure
   diagnostics.
   Observed: the response delivers the content "Set widget_height to 42 in widget/src/widget.py."
   as the next milestone, which is step section 2, because the delivery held its position at step
   section 1.
   Realized by: the component's own step offset, which the failed advancement left at step section
   1, and its own milestone response assembly.

### Scenario 7 — A failing verification where the guide configures no failure instructions

Given: step mode is active for the agent session of role gamma, the guide holds the step section 1
titled "Inspect the sprocket contract" with the content "Read sprocket/contracts/sprocket.md and
confirm the declared field.", holds no verification failure instructions, and no step section has
been delivered.

1. The agent asks the guide delivery to advance a step with verification not passed and the failure
   diagnostics "sprocket/src/sprocket.py still holds sprocket_height = 10".
   Observed: the response reports the failure diagnostics "sprocket/src/sprocket.py still holds
   sprocket_height = 10", reports no verification failure instructions, delivers no step section
   content, and the guide delivery still reports that steps remain.
   Realized by: the component's own failure response assembly, which has no captured verification
   failure instructions to add, and its own step offset, which stays before step section 1.

## Implementation-only

### Scenario 8 — The response an advancement emits for a delivered milestone

Given: step mode is active for the agent session of role alpha, the guide holds the step section 1
titled "Inspect the widget contract" with the content "Read widget/contracts/widget.md and confirm
the declared field." and the step section 2 titled "Clean the widget source" with the content "Set
widget_height to 42 in widget/src/widget.py."; no step section has been delivered.

1. The agent asks the guide delivery to advance a step with verification passed and empty failure
   diagnostics.
   Observed: the response introduces the content "Read widget/contracts/widget.md and confirm the
   declared field." with the introduction `Now check carefully:` and instructs the agent to check
   that source file carefully, to make edits where the source file does not conform to a checklist
   item, and to request step advancement only once the source file conforms.
   Realized by: the component's own milestone response assembly, which prefixes the delivered step
   section content with the constant introduction `Now check carefully:` and appends its own
   conformance instructions.

2. The agent asks the guide delivery to advance a step with verification passed and empty failure
   diagnostics.
   Observed: the response introduces the content "Set widget_height to 42 in widget/src/widget.py."
   with the introduction `Now check carefully:` and the same conformance instructions.
   Realized by: the same response assembly, applied to the step section that the component's own
   step offset now holds.

### Scenario 9 — A failed advancement where the session recorded no initial primer

Given: step mode is active for the agent session of role delta, the guide holds the summary "clean
the widget target by inspecting the widget contract and then the widget source", the step section 1
titled "Inspect the widget contract" with the content "Read widget/contracts/widget.md and confirm
the declared field.", and the verification failure instructions "the widget source must set
widget_height to 42"; no initial primer has been recorded and no step section has been delivered.

1. The agent asks the guide delivery to advance a step with verification not passed and the failure
   diagnostics "widget/src/widget.py still holds widget_height = 30".
   Observed: the response reports the failure diagnostics "widget/src/widget.py still holds
   widget_height = 30", the verification failure instructions "the widget source must set
   widget_height to 42", and the guide summary "clean the widget target by inspecting the widget
   contract and then the widget source" in place of an initial primer, and no step section is
   activated.
   Realized by: the component's own failure response assembly, which substitutes the parsed guide
   summary when its initial primer record, written by the recording operation, holds nothing.

### Scenario 10 — A session configured with no guide at all

Given: step mode is active for the agent session of role epsilon, and the session supplies no guide
file content.

1. The agent asks the guide delivery whether steps remain.
   Observed: no steps remain, and the guide delivery exposes no guide.
   Realized by: the component's own step offset over a parse that found no guide, left empty by the
   session-entry initialization.

2. The agent asks the guide delivery to advance a step with verification passed and empty failure
   diagnostics.
   Observed: no response is produced.
   Realized by: the component's own step offset, which reports that no steps remain and assembles no
   response.

### Scenario 11 — Sections whose titles only begin with an excluded word

Given: step mode is active for the agent session of role zeta, and the guide file content holds the
heading "## Summary", then the line "clean the widget target by inspecting the widget contract",
then the heading "## Lint checks for the widget source", then the line "- the widget source ends with
a newline", then the heading "## Verification failure for the widget source", then the line "the
widget source must set widget_height to 42", then the heading "## Inspect the widget contract", then
the line "Read widget/contracts/widget.md and confirm the declared field.".

1. The agent asks the guide delivery to parse that content into a guide.
   Observed: the guide carries exactly one step section, numbered 1 and titled "Inspect the widget
   contract" with the content "Read widget/contracts/widget.md and confirm the declared field.", the
   summary "clean the widget target by inspecting the widget contract", and the verification failure
   instructions "the widget source must set widget_height to 42".
   Realized by: the component's own markdown section scan, which takes the section titled `Summary`
   as the summary, captures the section whose title begins with `Verification failure`, and excludes
   sections whose titles begin with `Summary`, `Lint checks`, or `Verification failure` from the step
   sections.
