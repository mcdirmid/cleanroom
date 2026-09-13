# agent_storage interface component

imports: dag_storage

## Purpose

The agent_storage interface component stores workspace target graph relationships, node definitions, pending messages, and reverse dependencies.

Task execution across structured projects requires maintaining target dependency relationships alongside durable inter-node messages. The agent_storage interface component preserves propagating and non-propagating graph relationships, task prompts, and node definitions populated from workspace target manifests, while maintaining pending messages and reverse dependencies for nodes.

**Out of scope:** The agent_storage interface component does not orchestrate agent turns, parse JSON manifest syntax, or execute filesystem edits; these are handled by other components.

## Types and Behavior

A *task prompt* is an instruction describing the work required to clean a node.

A *node definition* is metadata describing task prompts for a node.

The *agent storage* is a system service that is a dag storage backed by workspace build target manifests.

The agent storage:

- Maintains nodes, dependencies, reverse dependencies, and pending messages from workspace targets.

- Provides task prompts and node definitions for declared nodes.

- Marks dependent nodes dirty when propagating dependencies change.
