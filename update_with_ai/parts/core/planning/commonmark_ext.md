# commonmark_ext external component

## Intent

Specification files, developer guides, and starter templates depend on standard Markdown formatting tools to maintain clean document styling. When templating systems inject foreign control syntax into Markdown documents, Abstract Syntax Tree formatters corrupt list indentations, line wraps, and table cells. The commonmark_ext external component encapsulates the external CommonMark comment and text token standards, ensuring that template engines operate exclusively through standard HTML comment structures and delimited parameter identifiers that formatters preserve without corrupting document layout.

By establishing non-rendering comment conventions and token definitions for directives, loops, and parameter placeholders, the external boundary protects Markdown document structure from formatting corruption.

## Factored Contracts

### Contracts

- A caller supplies Markdown text containing embedded comment directives. [supply_markdown_text]
- CommonMark HTML comments delimited by opening and closing markers behave as non-rendering metadata. [html_comment_metadata]
- Delimited parameter placeholders enclosed in angle brackets with dotted identifier paths identify template variables. [parameter_placeholder_syntax]
- Line-suffix comment placement on table rows preserves table column alignment. [table_suffix_preservation]
- Line-suffix comment placement on list items preserves list structure. [list_suffix_preservation]
- Regular expression patterns identify block conditional delimiters. [regex_block_conditionals]
- Regular expression patterns identify line-suffix conditional markers. [regex_line_conditionals]
- Regular expression patterns identify block loop delimiters. [regex_block_loops]
- Regular expression patterns identify line-suffix loop markers. [regex_line_loops]
- Regular expression patterns identify parameter placeholder substitutions. [regex_parameter_substitutions]

## Woven Contracts

- When parsing Markdown with embedded directives, comments delimited by HTML markers are treated as non-rendering metadata while table and list layouts are preserved. [supply_markdown_text, html_comment_metadata, table_suffix_preservation, list_suffix_preservation]
- When extracting template structures, regular expression patterns identify conditional delimiters, loop markers, and parameter placeholders. [parameter_placeholder_syntax, regex_block_conditionals, regex_line_conditionals, regex_block_loops, regex_line_loops, regex_parameter_substitutions]
