<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T21:57:18Z
LAST_CHANGED: 2026-10-11T02:20:00Z
CHANGE: Split the formatting mechanics sentence from the resolution surface and separate conditional polarity into its own bullets
CODE_HASH: 461aba5adb9d
SPEC_QA_AUDIT: 2026-10-12T21:57:18Z
-->

# template_format_impl implementation component

imports: commonmark_ext
implements: template_format

## Purpose

The template_format_impl implementation component realizes template formatting and parameter resolution for Markdown documents in agent sessions.

Markdown templates in Cleanroom must survive automated formatting passes while preserving document layout across lists and tables. If formatting engines alter whitespace or indent directives as code blocks, subsequent evaluation breaks or corrupts target documents. The template_format_impl implementation component parses CommonMark HTML comment block and line-suffix directives, evaluates conditional inclusion, and expands collection iterations while maintaining document structure and normalizing formatting artifacts.

**Out of scope:** The template_format_impl implementation component does not parse JSON manifests, configure sandbox environments, or manage filesystem permissions; these are handled by other components.

**Delegated:** CommonMark comment and token syntax is delegated to commonmark_ext.

## Types and Behavior

The template formatter realizes template document formatting by scanning for directive syntax with regular expressions and parsing the directive comment and placeholder token structures the external formatting boundary defines.

When formatting template text with parameters, the template formatter resolves values across line-based and block-level document constructs.

The template formatter:

- Replaces parameter placeholder tokens matching dot-separated keys in the parameters with the string representations of their resolved values.

- Retains parameter placeholder tokens whose keys do not resolve to values in the parameters without modification.

- Retains the preceding line content of a line-suffix conditional comment whose condition key evaluates to true, and omits that line when the condition key evaluates to false.

- Includes the lines enclosed by a block conditional marker when the condition key evaluates to true, and omits those lines when the condition key evaluates to false.

- Repeats the preceding line content of a line-suffix loop comment for each item of the resolved sequence, binding the item variable in the parameter context.

- Repeats the lines enclosed by a block loop marker for each element of the resolved sequence, binding the loop variable in the parameter context.

- Normalizes extraneous blank lines introduced around block directive comments by formatting tools to preserve tight list spacing.
