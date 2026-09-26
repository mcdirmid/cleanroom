# template_format interface component

imports: agent_session

## Purpose

The template_format interface component defines template evaluation and formatting contracts for parameterized Markdown documents in agent sessions.

Multi-stage agent pairing requires readable template files that survive Abstract Syntax Tree formatting tools and remain coherent when parameter bindings are missing or partial. Standard template engines destroy document layouts and fail when bindings are omitted. The template_format interface component establishes a declarative contract for formatting templates, evaluating parameter substitutions, conditional block inclusion, and collection repetitions while preserving unbound parameter structures.

**Out of scope:** The template_format interface component does not parse JSON manifests, read files from disk, or manage agent session lifecycles; these are handled by other components.

## Types and Behavior

An agent session's *template formatter* formats template documents using supplied parameter bindings.

The template formatter can *format template* text using *parameters* to produce formatted text. When formatting template text, the template formatter:

- Substitutes parameter placeholders matching bound keys with their corresponding string representations.

- Preserves parameter placeholders whose keys are absent from the supplied parameters as unrendered placeholders.

- Evaluates conditional blocks and line-suffix conditionals based on the truthiness of their condition keys in the parameters, including enclosed content when true or absent from parameters and omitting content when false.

- Repeats loop blocks and line-suffix loops across items when the collection key resolves to a sequence in the parameters, binding loop item variables during repetition.
