<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T20:42:15Z
LAST_CHANGED: 2026-10-11T03:11:56Z
CHANGE: Author sandbox template_format_impl concrete scenarios
CODE_HASH: 84418897cfeb
-->

# Concrete scenarios for `template_format_impl` (implementation)

Scenarios 1 through 12 restate the caller observations of the interface scenarios and add, beside
each observation, the realization that produces it. Restating them rather than writing fresh ones is
what makes realizability structural: an implementation scenario that cannot name a realization for
its observation is a defect in the implementation rather than a gap in the set. Scenarios 13 through
16 cover behaviours the interface does not expose to a caller, and each of them is a candidate for
the question of whether it belongs in the interface set instead.

## Reused from the interface

### Scenario 1 — Substituting bound keys and preserving absent ones

Given: an agent session for role alpha; the template text holds the line "Owner: <owner>", then the
line "Checked at <checked_at>.", then a blank line, then the line
"Release <release> is approved: <approved>."; and the parameters bind `owner` to the string
`alpha`, `release` to the string `2026-01-02T03:04:05Z`, and `approved` to the boolean true, while
binding no key named `checked_at`.

1. The agent formats the template text using the parameters.
   Observed: the formatted text holds the line "Owner: alpha", then the line
   "Checked at <checked_at>.", then the blank line, then the line
   "Release 2026-01-02T03:04:05Z is approved: True.".
   Realized by: parameter placeholder tokens parsed through the regular expression definitions of
   `commonmark_ext`, resolved against the parameters by the component's own placeholder
   substitution.

2. The agent formats the same template text again using the same parameters.
   Observed: the same formatted text, and the template text supplied to the formatter is unchanged
   byte for byte.
   Realized by: the component's own substitution, which produces a new text and leaves the supplied
   parameters and template text untouched.

### Scenario 2 — Formatting with no parameters at all

Given: an agent session for role alpha; the parameters bind no key at all; and the template text is
"Owner: <owner>".

1. The agent formats the template text using the parameters.
   Observed: the formatted text is "Owner: <owner>", with the placeholder unrendered.
   Realized by: the component's own placeholder substitution, which retains a token whose key
   resolves to no value in the parameters.

2. The agent formats the empty template text using the parameters.
   Observed: the formatted text is empty.
   Realized by: the component's own line scanning, which finds no token and no directive in an empty
   text.

### Scenario 3 — A conditional block under a bound key

Given: an agent session for role alpha; the parameters bind `approved` to the boolean true; and the
template text holds the block conditional marker opening the condition key `approved`, then the line
"Owner review complete.", then the closing block conditional marker.

1. The agent formats the template text using the parameters.
   Observed: the formatted text holds the line "Owner review complete." and holds no block
   conditional marker.
   Realized by: the block conditional delimiters of `commonmark_ext` and the component's own
   evaluation of the condition key `approved` in the parameters.

2. The agent formats the same template text using parameters that bind `approved` to the boolean
   false.
   Observed: the formatted text omits the line "Owner review complete." and holds no block
   conditional marker.
   Realized by: the same conditional mechanics, which omit the enclosed lines for a false condition.

### Scenario 4 — A conditional block under an absent key

Given: an agent session for role alpha, the parameters bind `release` to the string `widget` and bind
no key named `approved`, and the template text holds the block conditional marker opening the
condition key `approved`, then the line "Owner review complete.", then the closing block conditional
marker.

1. The agent formats the template text using the parameters.
   Observed: the formatted text holds the line "Owner review complete.", because the condition key
   `approved` is absent from the parameters.
   Realized by: the component's own evaluation of the condition key `approved` in the parameters,
   which treats an absent key as true.

### Scenario 5 — Line-suffix conditionals across a bullet list

Given: an agent session for role alpha, the parameters bind `approved` to the boolean true and
`draft` to the boolean false, and the template text holds the lines "- Owner review
<!-- if: approved -->" and "- Draft release <!-- if: draft -->" in that order.

1. The agent formats the template text "- Owner review <!-- if: approved -->" using the parameters.
   Observed: the formatted text is the line "- Owner review".
   Realized by: the line-suffix conditional markers of `commonmark_ext` and the component's
   own retention of the preceding line content.

2. The agent formats the template text "- Draft release <!-- if: draft -->" using the parameters.
   Observed: the formatted text omits that line entirely.
   Realized by: the same line-suffix conditional mechanics, which omit the preceding line content
   for a false condition.

3. The agent formats the template text holding the lines "- Owner review <!-- if: approved -->" and
   "- Draft release <!-- if: draft -->" using the parameters.
   Observed: the formatted text holds exactly the line "- Owner review", and the omitted second line
   leaves no blank line between the first line and the end of the text.
   Realized by: the same line-suffix conditional mechanics, which remove the omitted line rather
   than leaving its position behind.

### Scenario 6 — A loop block across a collection

Given: an agent session for role alpha; the parameters bind `reviewed` to the list of the strings
`widget` and `gadget`; and the template text holds the block loop marker opening the collection key
`reviewed` with the loop variable `item`, then the line "- <item>", then the closing block loop
marker.

1. The agent formats the template text using the parameters.
   Observed: the formatted text holds the line "- widget" followed by the line "- gadget", and
   holds no block loop marker.
   Realized by: the block loop delimiters of `commonmark_ext` and the component's own
   repetition of the enclosed lines, which binds the loop variable `item` in the parameter context.

2. The agent formats the same template text using parameters that bind `reviewed` to the empty list.
   Observed: the formatted text holds no line and holds no block loop marker.
   Realized by: the same repetition mechanics, which produce no occurrence for an empty sequence.

3. The agent formats the same template text using parameters that bind `reviewed` to the list of the
   single string `sprocket`.
   Observed: the formatted text holds exactly the line "- sprocket".
   Realized by: the same repetition mechanics, which produce one occurrence for a one-element
   sequence.

### Scenario 7 — Line-suffix loops across a collection

Given: an agent session for role alpha, the parameters bind `reviewed` to the list of the strings
`widget` and `gadget`, and the parameters bind `release` to the string `2026-01-02T03:04:05Z`.

1. The agent formats the template text "- <item> <!-- for: item in reviewed -->" using the
   parameters.
   Observed: the formatted text holds the line "- widget" followed by the line "- gadget".
   Realized by: the line-suffix loop markers of `commonmark_ext` and the component's own
   repetition of the preceding line content with the loop variable `item` bound in the parameter
   context.

2. The agent formats the same template text using parameters that bind `reviewed` to the single
   string `widget`.
   Observed: the formatted text holds exactly the line "- widget".
   Realized by: the same line-suffix repetition, which repeats once per element of the resolved
   sequence.

3. The agent formats the template text "Release <release> <!-- for: item in reviewed -->" using
   parameters that bind `reviewed` to the list of the strings `widget` and `gadget`.
   Observed: the formatted text holds the line "Release 2026-01-02T03:04:05Z" repeated once for each
   of the strings `widget` and `gadget`, and the loop variable `item` is bound to the string `widget`
   during the first repetition and to the string `gadget` during the second.
   Realized by: the same line-suffix repetition over the resolved sequence, and the component's own
   placeholder substitution, which resolves `release` from the parameters on each repetition.

### Scenario 8 — Loop content nested in a conditional block

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
   Realized by: the block conditional and block loop delimiters of `commonmark_ext`, the
   component's own conditional evaluation, and its own repetition mechanics, which bind the loop
   variable `item` in the parameter context while the placeholder substitution retains the
   unresolved key `checked_at`.

2. The agent formats the same template text using parameters that bind `approved` to the boolean
   false.
   Observed: the formatted text holds no line at all, because the conditional content is omitted
   together with the loop content it encloses.
   Realized by: the component's own conditional evaluation, which precedes the repetition of the
   enclosed block.

### Scenario 9 — Placeholder tokens that do not resolve

Given: an agent session for role alpha, and the parameters bind `reviewed` to the list of the strings
`widget` and `gadget` and bind no key named `checked_at`.

1. The agent formats the template text "<checked_at>" using the parameters.
   Observed: the formatted text is "<checked_at>".
   Realized by: the component's own placeholder resolution, which finds no value for the
   dot-separated key `checked_at` and retains the token unmodified.

2. The agent formats the template text "<reviewed.0>" using the parameters.
   Observed: the formatted text is "<reviewed.0>".
   Realized by: the same resolution, which finds no value for the dot-separated key `reviewed.0` in
   the parameters.

3. The agent formats the template text "Reviewed <reviewed> times." using the parameters.
   Observed: the formatted text is "Reviewed ['widget', 'gadget'] times."
   Realized by: the same resolution, which substitutes the string representation of the resolved
   value.

### Scenario 10 — Text that is not a template directive

Given: an agent session for role alpha, and the parameters bind `approved` to the boolean true and
`release` to the string `widget`.

1. The agent formats the template text "<release" using the parameters.
   Observed: the formatted text is "<release", because the token is not a parameter placeholder
   token.
   Realized by: the parameter placeholder substitution structure of `commonmark_ext`, which the
   component's own scan finds no token to match in that text.

2. The agent formats the template text "A <!-- note: approved --> B" using the parameters.
   Observed: the formatted text is "A <!-- note: approved --> B", because the comment is neither a
   conditional comment nor a loop comment.
   Realized by: the component's own scanning for the directive comment structures of
   `commonmark_ext`, which finds no marker in that comment.

3. The agent formats the template text "Value <release> and <approved>." using the parameters.
   Observed: the formatted text is "Value widget and True."
   Realized by: the component's own substitution of both parameter placeholder tokens from the
   parameters.

### Scenario 11 — A line-suffix conditional in the middle of a line

Given: an agent session for role alpha, the parameters bind `approved` to the boolean true and
`release` to the string `widget`, and the template text holds the line
"Review <release>. <!-- if: approved --> Owner signed.".

1. The agent formats the template text using the parameters.
   Observed: the formatted text holds the line "Review widget. <!-- if: approved --> Owner signed."
   Realized by: the component's own scan, which recognizes the conditional comment only when the
   line ends with it, and its own placeholder substitution for `release`.

### Scenario 12 — A template that binds a directive marker name

Given: an agent session for role alpha; the parameters bind `endif` to the string `widget`; and the
template text is "<endif>".

1. The agent formats the template text using the parameters.
   Observed: the formatted text is "widget", because a parameter placeholder token is substituted
   whatever its key is named.
   Realized by: the component's own placeholder substitution, which resolves the key `endif` from
   the parameters before it examines the text for directive comments.

## Implementation-only

### Scenario 13 — Blank lines a formatting tool left around a block directive

Given: an agent session for role alpha, the parameters bind `approved` to the boolean true, and the
template text holds the line "- Owner review", then a blank line, then the block conditional marker
opening the condition key `approved`, then the line "- Release signed.", then the closing block
conditional marker, then a blank line, then the line "- Owner notified.".

1. The agent formats the template text using the parameters.
   Observed: the formatted text holds the three lines "- Owner review", "- Release signed.", and
   "- Owner notified." consecutively, with no blank line between them and no block conditional
   marker.
   Realized by: the component's own normalization of the blank lines a formatting tool introduces
   around block directive comments, which preserves the tight list spacing of the document.

2. The agent formats a template text holding the block conditional marker opening the condition key
   `approved`, then the line "- Release signed.", then the closing block conditional marker, then a
   blank line, then the line "- Owner notified.".
   Observed: the formatted text holds the lines "- Release signed." and "- Owner notified."
   consecutively, with no blank line between them.
   Realized by: the same normalization, which removes the blank line the formatting tool left after
   the closing block conditional marker.

### Scenario 14 — One collection feeding a block loop and a line-suffix loop

Given: an agent session for role alpha, the parameters bind `reviewed` to the list of the strings
`widget` and `gadget`, and the template text holds the block loop marker opening the collection key
`reviewed` with the loop variable `item`, then the line "- <item>", then the closing block loop
marker, then the line "Total: <item> <!-- for: item in reviewed -->".

1. The agent formats the template text using the parameters.
   Observed: the formatted text holds the lines "- widget" and "- gadget" from the block loop,
   followed by the lines "Total: widget" and "Total: gadget" from the line-suffix loop.
   Realized by: the component's own repetition mechanics for block loops and for line-suffix loops,
   each of which resolves the collection key `reviewed` from the parameters and binds the loop
   variable `item` for its own occurrences.

2. The agent formats the same template text using parameters that bind `reviewed` to the empty list.
   Observed: the formatted text holds no line for either loop.
   Realized by: the same repetition mechanics, which produce no occurrence for an empty sequence in
   either form.

### Scenario 15 — What the loop item variable shadows

Given: an agent session for role alpha; the parameters bind `reviewed` to the list of the strings
`widget` and `gadget`, `owners` to the list of the strings `alpha` and `beta`, and `item` to the
string `sprocket`; and the template text holds the block loop marker opening the collection key
`reviewed` with the loop variable `item`, then the line "- <item>", then the closing block loop
marker, then the block loop marker opening the collection key `owners` with the loop variable
`owner`, then the line "<owner> reviews <item>", then the closing block loop marker.

1. The agent formats the template text using the parameters.
   Observed: the formatted text holds the lines "- widget" and "- gadget", then the lines
   "alpha reviews sprocket" and "beta reviews sprocket", so the loop variable `item` of the first
   loop is bound only during that loop's repetitions and the parameter `item` is resolved in the
   second loop.
   Realized by: the component's own binding of the loop variable into the parameter context for the
   duration of each repetition, and its release of that binding when the repetition ends.

### Scenario 16 — A document with no directive and no placeholder at all

Given: an agent session for role alpha, the parameters bind `approved` to the boolean true, and the
template text holds the line "# Status" followed by the line "Report 42 of 7.".

1. The agent formats the template text using the parameters.
   Observed: the formatted text holds the line "# Status" followed by the line "Report 42 of 7.",
   unchanged.
   Realized by: the component's own scan for angle-bracket placeholder tokens and comment directive
   markers, which finds neither in that text.
