<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-07T23:58:18Z
LAST_CHANGED: 2026-10-05T04:50:34Z
CHANGE: Broaden node definition to encapsulate build target attributes, role boundaries, and prompts
CODE_HASH: bc3420fa6c49
-->

# agent_storage interface component

imports: dag_storage

## Purpose

The agent_storage interface component stores workspace target graph relationships, node definitions, and task prompts.

Task execution across structured projects requires maintaining target dependency relationships alongside durable node state. The agent_storage interface component preserves propagating and non-propagating graph relationships, task prompts, and node definitions populated from workspace target manifests, while evaluating node dirty state and pending messages backed by in-band source file metadata.

**Out of scope:** The agent_storage interface component does not orchestrate agent turns, parse JSON manifest syntax, or execute filesystem edits; these are handled by other components.

## Types and Behavior

A *task prompt* is an instruction describing the work required to clean a node.

A *node definition* encapsulates a declared target's execution configuration, role attributes, and task prompts.

A system's *agent storage* is a dag storage backed by workspace build target manifests. Target manifest metadata configures node execution and dependency structures.

The agent storage:

- Maintains nodes and dependencies from workspace target manifests.

- Provides task prompts and node definitions for declared nodes.

- Evaluates node dirty status and derives pending messages from in-band source file metadata.
