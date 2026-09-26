# sandbox_guide_delivery_impl implementation component

imports: tool_provider, agent_file_alias, agent_node_config
implements: sandbox_guide_delivery

## Assumptions and Requirements

### Requirements

1. When initialized for an agent session, the guide delivery obtains its guide parsed from configured guide file content.
2. Parsing extracts guide summary from content preceding the first section heading and under headings titled Summary, captures verification failure instructions when heading begins with Verification failure, and creates sequential step sections for subsequent level-two headings excluding Summary, Lint checks, or Verification failure.
3. Advancing step when verification passes emits a response containing guide summary alone alongside instructions to edit the document as needed before advancing again when no step has been delivered yet.
4. Advancing step when verification passes emits a response presenting guide summary above next step section content introduced by Now check carefully: alongside instructions to make edits if the source file does not conform to any checklist item and call advance() only when conforming, transitioning to that step section when previous steps have been delivered and further step sections remain.
5. Advancing step when verification fails emits a response combining guide summary, verification failure instructions, and failure diagnostics without activating a step section when no step has been delivered yet.
6. Advancing step when verification fails emits a response combining guide summary, current step section content introduced by Now check carefully:, verification failure instructions, and failure diagnostics without advancing when a step is active.
7. When no guide is configured or no step sections remain, the guide delivery indicates that no steps remain and advancing produces no response.

## Grounding Facts

### Knowledge Needed

- Guide file content from `agent_node_config`.
- Guide section headings.
- Current step index and remaining step count.
- Verification outcome and failure diagnostics.

### Actions Needed

- Parse guide markdown into summary, failure instructions, and steps.
- Format progression response text on step advance.
- Format diagnostic feedback response text on verification failure.
