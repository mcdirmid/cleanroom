# sandbox_guide_delivery interface component

imports: tool_provider, agent_file_alias, agent_node_config

## Assumptions and Requirements

### Requirements

1. A guide delivery is an agent session service configured with a guide that delivers instructions to an agent progressively.
2. The guide delivery can parse file content into a guide.
3. The guide delivery can advance step with a verification passed indicator and failure diagnostics, delivering instructional text when verification passes, or retaining the current milestone and reporting failure diagnostics alongside verification failure instructions when verification fails.
4. The guide delivery exposes whether progressive steps remain to be completed.
5. The guide delivery exposes its configured guide.

## Grounding Facts

### Knowledge Needed

- Guide file content and step structure.
- Verification pass/fail status and failure diagnostics.
- Remaining steps status.

### Actions Needed

- Parse guide file content into structured steps.
- Advance guide step on verification success.
- Report failure diagnostics and retain step on verification failure.
