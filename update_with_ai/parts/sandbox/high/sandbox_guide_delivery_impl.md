<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-13T01:05:05Z
LAST_CHANGED: 2026-10-11T02:20:00Z
CHANGE: Make step advancement declarative and split the parsing paragraph
CODE_HASH: f272c5e064d6
SPEC_QA_AUDIT: 2026-10-13T01:05:05Z
-->

# sandbox_guide_delivery_impl implementation component

imports: tool_provider, agent_file_alias, agent_node_config
implements: sandbox_guide_delivery

## Purpose

The sandbox_guide_delivery_impl implementation component realizes sequential guide markdown parsing and progressive step progression.

Agent guidance documents contain disparate front-matter, structural summaries, and checklist sections that must be filtered into actionable milestone chunks. The sandbox_guide_delivery_impl implementation component extracts high-level task summaries and active instructional sections from markdown text while omitting verification lint checklists, managing current step offsets to ensure instructions advance monotonically upon successful phase verification.

**Out of scope:** The sandbox_guide_delivery_impl implementation component does not execute build steps, evaluate test assertions, or persist guide text to disk; these are handled by other components.

## Types and Behavior

When initialized for an agent session, the guide delivery obtains its guide parsed from configured guide file content. Parsing extracts the guide summary from content preceding the first section heading and under any heading titled `Summary`, and captures verification failure instructions when a section heading begins with `Verification failure`.

Parsing creates sequential step sections for subsequent level-two headings, excluding sections whose title begins with `Summary`, `Lint checks`, or `Verification failure`.

Passing verification satisfies the prerequisite milestone criteria for step advancement.

Advancing a step when verification passes:

- Emits a response presenting the content of the next step section introduced by `Now check carefully:` alongside instructions to check carefully, to make edits when the source file does not conform to a checklist item, and to request step advancement only once the source file conforms.

- Transitions to that step section when further step sections remain.

Failing verification preserves the current delivery position while communicating diagnostic feedback.

Advancing a step when verification fails:

- Emits a response combining the initial primer content, or the guide summary when an initial primer is omitted, with any configured verification failure instructions and the failure diagnostics, without activating a step section when no step section has been delivered.

- Emits a response combining the current step section content introduced by `Now check carefully:` with any configured verification failure instructions and the failure diagnostics, without advancing to subsequent sections when a step section is currently active.

When no guide is configured or no step sections remain, the guide delivery indicates that no steps remain and advancing produces no response.
