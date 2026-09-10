# sandbox_guide_delivery_impl implementation component

imports: tool_provider, file_alias, node_config
implements: sandbox_guide_delivery

## Purpose

The sandbox_guide_delivery_impl implementation component realizes sequential guide markdown parsing and progressive step progression.

Agent guidance documents contain disparate front-matter, structural summaries, and checklist sections that must be filtered into actionable milestone chunks. The sandbox_guide_delivery_impl implementation component extracts high-level task summaries and active instructional sections from markdown text while omitting verification lint checklists, managing current step offsets to ensure instructions advance monotonically upon successful phase verification.

**Out of scope:** The sandbox_guide_delivery_impl implementation component does not execute build steps, evaluate test assertions, or persist guide text to disk; these are handled by other components.

## Types and Behavior

A guide delivery parses file content into a task guide, extracting the summary from content preceding the first section heading, and creating sequential step sections for subsequent level-two headings while excluding sections whose title begins with `Lint checks`. When initialized for an agent session, the guide delivery obtains its guide from the node config.

A guide delivery begins before the first step section. When advancing a step with passed verification:

- If no steps have been delivered yet, the guide delivery emits a response containing the guide summary alone without delivering a step section.

- If steps have already been delivered and further step sections remain, the guide delivery emits a response presenting the guide summary above the next step section content and advances its index to that section.

Failing verification halts progression and provides diagnostic feedback. When advancing a step with failed verification:

- If no step section has been delivered yet, the guide delivery retains its index and emits a response combining the guide summary and failure diagnostics.

- If a step section is currently active, the guide delivery retains the current step index without advancement and emits a response combining the guide summary, the current step section content, and the failure diagnostics.

When no guide is configured or no step sections remain, the guide delivery indicates that no steps remain and advancing produces no response.
