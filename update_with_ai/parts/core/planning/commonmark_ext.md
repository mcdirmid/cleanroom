# commonmark_ext external component

## Intent

Specification files, developer guides, and starter templates depend on standard Markdown formatting tools to maintain clean document styling. When templating systems inject foreign control syntax into Markdown documents, Abstract Syntax Tree formatters corrupt list indentations, line wraps, and table cells. The commonmark_ext external component encapsulates the external CommonMark comment and text token standards, ensuring that template engines operate exclusively through standard HTML comment structures and delimited parameter identifiers that formatters preserve without corrupting document layout.

By establishing non-rendering comment conventions and token definitions for directives, loops, and parameter placeholders, the external boundary protects Markdown document structure from formatting corruption.

## Grounding

### Knowledge Provisions

- CommonMark HTML comment conventions and regular expression token patterns. [commonmark_operations]
