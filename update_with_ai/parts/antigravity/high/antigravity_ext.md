<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T23:37:36Z
LAST_CHANGED: 2026-10-12T21:45:00Z
CHANGE: author antigravity_ext external component
CODE_HASH: 0054c68f2cbc
-->

# antigravity_ext external component

## Purpose

The antigravity_ext external component defines the external Google Antigravity platform boundary for skill manifests, boundary isolation rules, subagent dispatch schemas, and transcript execution logs.

Direct coupling between core cleanroom orchestration and platform-specific environment conventions causes portability degradation and fragility across agent hosts. The antigravity_ext external component encapsulates the filesystem structures, schema definitions, and log formats required for integrating Cleanroom workspaces with Google Antigravity.

**Out of scope:** The antigravity_ext external component does not generate project files, schedule workflows, or execute agent turns; these are handled by other components.

## Grounding Gaps Covered

The antigravity_ext component provides external domain knowledge and format mechanics for the Google Antigravity desktop IDE and CLI execution environment.

Grounding gaps covered include:

- Antigravity skill structure and frontmatter: Defines the YAML frontmatter specification containing skill name and description, together with Markdown body instructions for skills located at `.agents/skills/<skill_name>/SKILL.md` or within global plugin directories at `~/.gemini/config/plugins/<plugin_name>/skills/<skill_name>/SKILL.md`.

- Workspace isolation rules format: Defines the Markdown rule format for `.agents/rules/<rule_name>.md` enforcing boundaries that forbid autonomous subagents from inspecting, reading, or modifying files outside their provisioned role workspace root.

- Subagent invocation payload schema: Defines the JSON parameter schemas for the `invoke_subagent` tool, including `TypeName`, `Role`, `Prompt`, and `Workspace` path parameters, establishing the protocol for binding child agent execution directly to isolated sibling directories without inheriting the parent workspace.

- Transcript execution event log schema: Defines the JSONL event record schema in `<appDataDir>/brain/<conversation_id>/.system_generated/logs/transcript.jsonl`, specifying step objects with step indices, event types, status indicators, tool invocation records, and model token usage metrics covering input tokens, cached tokens, and completion tokens.
