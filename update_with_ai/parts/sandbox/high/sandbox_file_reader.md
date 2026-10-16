<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-15T17:42:46Z
LAST_CHANGED: 2026-10-11T02:20:00Z
CHANGE: Split the read manager capabilities into declarative statements
CODE_HASH: d610347ba20d
SPEC_QA_AUDIT: 2026-10-15T17:42:46Z
-->

# sandbox_file_reader interface component

imports: agent_session, agent_file_alias, tool_provider

## Purpose

The sandbox_file_reader interface component provides safe workspace file read tools while preventing premature instruction exposure and unanchored edits.

Autonomous agents require structured access to workspace files, but naive whole-file reads risk flooding prompt context and enabling unanchored edits across writable targets. Furthermore, when workflows enforce guided step-by-step progression, unconstrained file access risks bypassing phase pacing. The sandbox_file_reader interface component establishes a governed read layer that balances external context injection with safety guardrails, ensuring file read remains scoped to the agent's immediate operational phase.

**Out of scope:** The sandbox_file_reader interface component does not inject session startup context, deliver progressive workflow instructions, or advance workflow steps; these are handled by other components.

**Delegated:** File alias mapping and access checking are delegated to agent_file_alias; tool registration and parameter schemas are delegated to tool_provider; session lifecycle scoping is delegated to agent_session.

## Types and Behavior

An agent session's *read manager* regulates file reading and exposes the session read-only files and read-write files.

The read manager can also *check read access* for a workspace path, confirming access for declared files while failing with guidance that lists readable file aliases when access is disallowed.

An agent session's *view file tool* reads the content of a file specified by its file alias path parameter.

An agent session's *search tool* searches pattern matches across the session's read-only and read-write files according to its regex pattern parameter.
