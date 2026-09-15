# sandbox_file_reader interface component

imports: tool_provider, agent_file_alias

## Purpose

The sandbox_file_reader interface component provides safe workspace file inspection tools while preventing premature instruction exposure and unanchored edits.

Autonomous agents require structured access to workspace files, but naive whole-file reads risk flooding prompt context and enabling unanchored edits across writable targets. Furthermore, when workflows enforce guided step-by-step progression, unconstrained file access risks bypassing phase pacing. The sandbox_file_reader interface component establishes a governed inspection layer that balances external context injection with safety guardrails, ensuring file inspection remains scoped to the agent's immediate operational phase.

**Out of scope:** The sandbox_file_reader interface component does not inject session startup context, deliver progressive workflow instructions, or advance workflow steps; these are handled by other components.

## Types and Behavior

The *read manager* is an agent session service that manages inspection of workspace files.

The read manager provides:

- A *view file tool* that inspects file content, accepting a file alias *path parameter*.

- A *search tool* that searches pattern matches across the session's read-only and read-write files, accepting a regex pattern *pattern parameter*.

The read manager exposes the session *read-only files* and *read-write files*. When step mode is active, the read manager is configured with an unbound *guide file*.
