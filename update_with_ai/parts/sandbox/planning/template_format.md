<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-09T21:19:01Z
LAST_CHANGED: 2026-10-06T00:52:38Z
CHANGE: import commonmark_ext and weave token contracts
CODE_HASH: 3fb60791ce2d
SPEC_QA_AUDIT: 2026-10-09T21:19:01Z
-->

# template_format interface component

imports: agent_session, commonmark_ext

## Intent

Multi-stage agent pairing requires readable template files that survive Abstract Syntax Tree formatting tools and remain coherent when parameter bindings are missing or partial. Standard template engines destroy document layouts and fail when bindings are omitted. The template_format interface component establishes a declarative contract for formatting templates, evaluating parameter substitutions, conditional block inclusion, and collection repetitions while preserving unbound parameter structures.

By tolerating partial bindings and preserving unrendered placeholders, the template formatter allows multi-stage agent workflows to progressively instantiate templates across operational phases without layout breakage.

## Factored Contracts

### Contracts

- A caller supplies template text when requesting template formatting. [format_template_text_supplied]
- A caller supplies parameter bindings when requesting template formatting. [format_template_params_supplied]
- An agent session's template formatter formats template text using parameter bindings to produce formatted text. [format_template_text]
- The template formatter substitutes parameter placeholders matching bound keys with their string representations. [substitute_bound_placeholders]
- The template formatter preserves parameter placeholders absent from parameter bindings as unrendered placeholders. [preserve_absent_placeholders]
- The template formatter evaluates conditional blocks based on the truthiness of their condition keys. [eval_conditional_blocks]
- The template formatter evaluates line-suffix conditionals based on the truthiness of their condition keys. [eval_suffix_conditionals]
- The template formatter includes conditional content when the condition key is true. [include_condition_true]
- The template formatter includes conditional content when the condition key is absent from parameters. [include_condition_absent]
- The template formatter omits conditional content when the condition key is false. [omit_condition_false]
- The template formatter repeats loop blocks across items when the collection key resolves to a sequence. [repeat_loop_blocks]
- The template formatter repeats line-suffix loops across items when the collection key resolves to a sequence. [repeat_suffix_loops]
- The template formatter binds loop item variables during repetition. [bind_loop_item_variables]

### Woven Contracts

- When formatting template text, bound parameter placeholders are substituted while absent placeholders are preserved unrendered. [format_template_text_supplied, format_template_params_supplied, format_template_text, substitute_bound_placeholders, preserve_absent_placeholders]
- Conditional blocks and line-suffix conditionals are included when condition keys are true or absent, and omitted when false. [eval_conditional_blocks, eval_suffix_conditionals, include_condition_true, include_condition_absent, omit_condition_false]
- Loop blocks and line-suffix loops iterate over sequence collections, binding loop item variables for each repetition. [repeat_loop_blocks, repeat_suffix_loops, bind_loop_item_variables]

## Grounding

### Knowledge Provisions

- Formats template text with parameter substitutions and conditional evaluations. [template_formatting]
- Evaluates conditional blocks and line-suffix conditions based on parameters. [conditional_evaluation]
- Repeats loop blocks and line-suffix loops across sequence elements. [loop_repetition]

### Knowledge Requirements

- Parsing markdown text and HTML comment directives.
  - Deferred: Requires CommonMark comment directive parsing in implementation.
- Resolving dot-separated parameter bindings in hierarchical dictionaries.
  - Deferred: Requires nested parameter resolution in implementation.
