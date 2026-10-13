<!-- CLEANROOM METADATA
LAST_CLEANED: 2026-10-12T23:37:36Z
LAST_CHANGED: 2026-10-11T01:39:02Z
CHANGE: Align node definition with its task prompt and restructure the agent storage operation list
CODE_HASH: 264960eede71
SPEC_QA_AUDIT: 2026-10-12T23:37:36Z
-->

# agent_storage interface component

imports: dag_storage

## Purpose

The agent_storage interface component stores workspace target graph relationships, node definitions, and task prompts.

Task execution across structured projects requires maintaining target dependency relationships alongside durable node state. The agent_storage interface component preserves propagating and silent graph relationships, task prompts, and node definitions populated from workspace target manifests, while evaluating node dirty state and pending messages backed by in-band source file metadata.

**Out of scope:** The agent_storage interface component does not orchestrate agent turns, parse JSON manifest syntax, or execute filesystem edits; these are handled by other components.

**Delegated:** Graph structure, node status, and message propagation are delegated to dag_storage.

## Types and Behavior

A *task prompt* is an instruction describing the work required to clean a node.

A *node definition* encapsulates the execution configuration and task prompt a declared target carries.

A system's *agent storage* is a dag storage backed by workspace build target manifests, where target manifest metadata configures node execution and dependency structure.

The agent storage maintains the nodes and dependencies that workspace target manifests declare, and provides the task prompts and node definitions of declared nodes.

The agent storage evaluates whether a node is dirty from the in-band source file metadata of the node and the change state of its non-silent dependencies.
