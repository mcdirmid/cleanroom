# commonmark_ext external component

## Purpose

The commonmark_ext external component defines the external CommonMark and GitHub Flavored Markdown document format, HTML comment directive syntax, and text structures.

Specification files, developer guides, and starter templates depend on standard Markdown formatting tools to maintain clean document styling. When templating systems inject foreign control syntax into Markdown documents, Abstract Syntax Tree formatters corrupt list indentations, line wraps, and table cells. The commonmark_ext external component encapsulates the external CommonMark comment and text token standards, ensuring that template engines operate exclusively through standard HTML comment structures and delimited parameter identifiers that formatters preserve without corrupting document layout.

**Out of scope:** The commonmark_ext external component does not evaluate template expressions, manage session parameter dictionaries, or write files to disk; these are handled by other components.

## Grounding Gaps Covered

The commonmark_ext component provides external formatting knowledge and token mechanics for parsing and structuring CommonMark documents with embedded directives:

- HTML comment block and inline handling: Identifies CommonMark HTML block type 2 comments and inline raw HTML comments delimited by opening and closing markers, ensuring directives are recognized as non-rendering metadata by standard Markdown parsers and viewers.

- Delimited parameter placeholder extraction: Defines parameter placeholder token syntax enclosed in angle brackets with dotted identifier paths, distinguishing unrendered parameter placeholders from markup tags.

- Table and list structure preservation: Establishes line-suffix comment placement conventions for Markdown table rows and bullet list items, preventing formatting engines from injecting spurious blank lines or disrupting table column alignment.

- Regular expression pattern definitions: Specifies regular expression patterns for identifying block conditional delimiters, line-suffix conditional markers, block loop delimiters, line-suffix loop markers, and parameter placeholder substitutions.
