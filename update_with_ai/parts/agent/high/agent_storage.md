# agent_storage interface component

imports: dag_storage

## Purpose

The agent_storage interface component stores workspace target graph relationships, node definitions, and task prompts.

Task execution across structured projects requires maintaining target dependency relationships alongside durable node state. The agent_storage interface component preserves propagating and non-propagating graph relationships, task prompts, and node definitions populated from workspace target manifests, while evaluating node dirty state and pending messages backed by in-band source file metadata.

**Out of scope:** The agent_storage interface component does not orchestrate agent turns, parse JSON manifest syntax, or execute filesystem edits; these are handled by other components.

## Types and Behavior

A *task prompt* is an instruction describing the work required to clean a node.

A *node definition* is metadata describing task prompts for a node.

A system's *agent storage* is a dag storage backed by workspace build target manifests. Target manifest metadata configures node execution and dependency structures.

The agent storage:

- Maintains nodes and dependencies from workspace target manifests.

- Provides task prompts and node definitions for declared nodes.

- Evaluates node dirty status and derives pending messages from in-band source file metadata.
