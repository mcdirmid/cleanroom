<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T03:11:56Z
CHANGE: Author sandbox template_format concrete scenarios
CODE_HASH: 8bc7835f5324
-->

# Concrete scenarios for `template_format` (interface)

## Scenario 1 — Substituting bound keys and preserving absent ones

Given: an agent session for role alpha; the template text holds the line "Owner: <owner>", then the
line "Checked at <checked_at>.", then a blank line, then the line
"Release <release> is approved: <approved>."; and the parameters bind `owner` to the string
`alpha`, `release` to the string `2026-01-02T03:04:05Z`, and `approved` to the boolean true, while
binding no key named `checked_at`.

1. The agent formats the template text using the parameters.
   Observed: the formatted text holds the line "Owner: alpha", then the line
   "Checked at <checked_at>.", then the blank line, then the line
   "Release 2026-01-02T03:04:05Z is approved: True.".

2. The agent formats the same template text again using the same parameters.
   Observed: the same formatted text, and the template text supplied to the formatter is unchanged
   byte for byte.

## Scenario 2 — Formatting with no parameters at all

Given: an agent session for role alpha; the parameters bind no key at all; and the template text is
"Owner: <owner>".

1. The agent formats the template text using the parameters.
   Observed: the formatted text is "Owner: <owner>", with the placeholder unrendered.

2. The agent formats the empty template text using the parameters.
   Observed: the formatted text is empty.

## Scenario 3 — A conditional block under a bound key

Given: an agent session for role alpha; the parameters bind `approved` to the boolean true; and the
template text holds the block conditional marker opening the condition key `approved`, then the line
"Owner review complete.", then the closing block conditional marker.

1. The agent formats the template text using the parameters.
   Observed: the formatted text holds the line "Owner review complete." and holds no block
   conditional marker.

2. The agent formats the same template text using parameters that bind `approved` to the boolean
   false.
   Observed: the formatted text omits the line "Owner review complete." and holds no block
   conditional marker.

## Scenario 4 — A conditional block under an absent key

Given: an agent session for role alpha, the parameters bind `release` to the string `widget` and bind
no key named `approved`, and the template text holds the block conditional marker opening the
condition key `approved`, then the line "Owner review complete.", then the closing block conditional
marker.

1. The agent formats the template text using the parameters.
   Observed: the formatted text holds the line "Owner review complete.", because the condition key
   `approved` is absent from the parameters.

## Scenario 5 — Line-suffix conditionals across a bullet list

Given: an agent session for role alpha, the parameters bind `approved` to the boolean true and
`draft` to the boolean false, and the template text holds the lines "- Owner review
<!-- if: approved -->" and "- Draft release <!-- if: draft -->" in that order.

1. The agent formats the template text "- Owner review <!-- if: approved -->" using the parameters.
   Observed: the formatted text is the line "- Owner review".

2. The agent formats the template text "- Draft release <!-- if: draft -->" using the parameters.
   Observed: the formatted text omits that line entirely.

3. The agent formats the template text holding the lines "- Owner review <!-- if: approved -->" and
   "- Draft release <!-- if: draft -->" using the parameters.
   Observed: the formatted text holds exactly the line "- Owner review", and the omitted second line
   leaves no blank line between the first line and the end of the text.

## Scenario 6 — A loop block across a collection

Given: an agent session for role alpha; the parameters bind `reviewed` to the list of the strings
`widget` and `gadget`; and the template text holds the block loop marker opening the collection key
`reviewed` with the loop variable `item`, then the line "- <item>", then the closing block loop
marker.

1. The agent formats the template text using the parameters.
   Observed: the formatted text holds the line "- widget" followed by the line "- gadget", and
   holds no block loop marker.

2. The agent formats the same template text using parameters that bind `reviewed` to the empty list.
   Observed: the formatted text holds no line and holds no block loop marker.

3. The agent formats the same template text using parameters that bind `reviewed` to the list of the
   single string `sprocket`.
   Observed: the formatted text holds exactly the line "- sprocket".

## Scenario 7 — Line-suffix loops across a collection

Given: an agent session for role alpha, the parameters bind `reviewed` to the list of the strings
`widget` and `gadget`, and the parameters bind `release` to the string `2026-01-02T03:04:05Z`.

1. The agent formats the template text "- <item> <!-- for: item in reviewed -->" using the
   parameters.
   Observed: the formatted text holds the line "- widget" followed by the line "- gadget".

2. The agent formats the same template text using parameters that bind `reviewed` to the single
   string `widget`.
   Observed: the formatted text holds exactly the line "- widget".

3. The agent formats the template text "Release <release> <!-- for: item in reviewed -->" using
   parameters that bind `reviewed` to the list of the strings `widget` and `gadget`.
   Observed: the formatted text holds the line "Release 2026-01-02T03:04:05Z" repeated once for each
   of the strings `widget` and `gadget`, and the loop variable `item` is bound to the string `widget`
   during the first repetition and to the string `gadget` during the second.

## Scenario 8 — Loop content nested in a conditional block

Given: an agent session for role alpha; the parameters bind `approved` to the boolean true and
`reviewed` to the list of the strings `widget` and `gadget`; the parameters bind no key named
`checked_at`; and the template text holds the block conditional marker opening the condition key
`approved`, then the lines "Reviewed <item> at <checked_at>." enclosed by the block loop marker
opening the collection key `reviewed` with the loop variable `item`, then the closing block
conditional marker.

1. The agent formats the template text using the parameters.
   Observed: the formatted text holds the line "Reviewed widget at <checked_at>." followed by the
   line "Reviewed gadget at <checked_at>.", with the placeholder for the absent key `checked_at`
   preserved in both lines.

2. The agent formats the same template text using parameters that bind `approved` to the boolean
   false.
   Observed: the formatted text holds no line at all, because the conditional content is omitted
   together with the loop content it encloses.

## Scenario 9 — Placeholder tokens that do not resolve

Given: an agent session for role alpha, and the parameters bind `reviewed` to the list of the strings
`widget` and `gadget` and bind no key named `checked_at`.

1. The agent formats the template text "<checked_at>" using the parameters.
   Observed: the formatted text is "<checked_at>".

2. The agent formats the template text "<reviewed.0>" using the parameters.
   Observed: the formatted text is "<reviewed.0>".

3. The agent formats the template text "Reviewed <reviewed> times." using the parameters.
   Observed: the formatted text is "Reviewed ['widget', 'gadget'] times."

## Scenario 10 — Text that is not a template directive

Given: an agent session for role alpha, and the parameters bind `approved` to the boolean true and
`release` to the string `widget`.

1. The agent formats the template text "<release" using the parameters.
   Observed: the formatted text is "<release", because the token is not a parameter placeholder
   token.

2. The agent formats the template text "A <!-- note: approved --> B" using the parameters.
   Observed: the formatted text is "A <!-- note: approved --> B", because the comment is neither a
   conditional comment nor a loop comment.

3. The agent formats the template text "Value <release> and <approved>." using the parameters.
   Observed: the formatted text is "Value widget and True."

## Scenario 11 — A line-suffix conditional in the middle of a line

Given: an agent session for role alpha, the parameters bind `approved` to the boolean true and
`release` to the string `widget`, and the template text holds the line
"Review <release>. <!-- if: approved --> Owner signed.".

1. The agent formats the template text using the parameters.
   Observed: the formatted text holds the line "Review widget. <!-- if: approved --> Owner signed."

## Scenario 12 — A template that binds a directive marker name

Given: an agent session for role alpha; the parameters bind `endif` to the string `widget`; and the
template text is "<endif>".

1. The agent formats the template text "<endif>" using the parameters.
   Observed: the formatted text is "widget", because a parameter placeholder token is substituted
   whatever its key is named.
