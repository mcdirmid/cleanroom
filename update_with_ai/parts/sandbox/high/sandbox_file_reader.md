# sandbox_file_reader interface component

imports: agent_session, agent_file_alias, tool_provider, file_paths

## Purpose

The sandbox_file_reader interface component provides safe workspace file read tools while preventing premature instruction exposure and unanchored edits.

Autonomous agents require structured access to workspace files, but naive whole-file reads risk flooding prompt context and enabling unanchored edits across writable targets. Furthermore, when workflows enforce guided step-by-step progression, unconstrained file access risks bypassing phase pacing. The sandbox_file_reader interface component establishes a governed read layer that balances external context injection with safety guardrails, ensuring file read remains scoped to the agent's immediate operational phase.

**Out of scope:** The sandbox_file_reader interface component does not inject session startup context, deliver progressive workflow instructions, or advance workflow steps; these are handled by other components.

## Types and Behavior

An agent session's *read manager* regulates file reading. The read manager exposes the session read-only files and read-write files. To validate external file access, the read manager can also *check read access* for a workspace path, confirming access for declared files while failing with guidance listing readable file aliases when access is disallowed.

An agent session's *view file tool* reads the content of a file specified by its file alias path parameter.

An agent session's *search tool* searches pattern matches across the session's read-only and read-write files according to its regex pattern parameter.
