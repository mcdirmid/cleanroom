# template_format interface component

imports: agent_session

## Assumptions and Requirements

### Requirements

1. The template formatter formats template documents using supplied parameter bindings.
2. Substitutes parameter placeholders matching bound keys with their corresponding string representations.
3. Preserves parameter placeholders whose keys are absent from the supplied parameters as unrendered placeholders.
4. Evaluates conditional blocks and line-suffix conditionals based on the truthiness of their condition keys in the parameters, including enclosed content when true or absent from parameters and omitting content when false.
5. Repeats loop blocks and line-suffix loops across items when the collection key resolves to a sequence in the parameters, binding loop item variables during repetition.

## Grounding Facts

### Knowledge Needed

- Template document string.
- Supplied parameter bindings.
- Placeholder, conditional, and loop syntax rules.

### Actions Needed

- Substitute bound parameter placeholders.
- Evaluate conditional blocks and line-suffix conditionals.
- Expand loop blocks across sequence items.
