# sandbox_file_reader interface component

imports: tool_provider, file_alias

## Purpose

The sandbox_file_reader interface component provides safe workspace file inspection tools while preventing premature instruction exposure and unanchored edits.

Autonomous agents require structured access to workspace files, but naive whole-file reads risk flooding prompt context and enabling unanchored edits across writable targets. Furthermore, when workflows enforce guided step-by-step progression, unconstrained file access risks bypassing phase pacing. The sandbox_file_reader interface component establishes a governed inspection layer that balances external context injection with safety guardrails, ensuring file inspection remains scoped to the agent's immediate operational phase.

**Out of scope:** The sandbox_file_reader interface component does not inject session startup context, deliver progressive workflow instructions, or advance workflow steps; these are handled by other components.

## Types and Behavior

The *read manager* is an agent session service that installs the following tools for inspecting workspace files:

- A *read tool* that reads file content, taking a *file alias parameter* and a parameter specifying if the agent wants content formatted with *line numbers* or not. Executing the read tool distinguishes reading attempts on the guide file to provide *progressive delivery* feedback.

- A *search tool* that searches pattern matches across the session's read-only and read-write files, accepting a *regex pattern parameter*.

To support session startup context injection, the read manager exposes the agent session's set of *read-only files* and *read-write files*. When a guide is provided by *step-mode*, the read manager is configured with a *guide file*, which is an unbound file, so that an agent trying to read the guide file will receive corrective error responses.
