from typing import Optional, Set
from framework import operation, override, singleton_type
import agent_storage
import bazel_target
import dag_storage
import file_paths
import update_with_ai_proto_ext

@singleton_type('system')
class AgentStorage(agent_storage.AgentStorage):
    """
PURPOSE:
Implements graph storage with in-memory definitions, manifest loader coordination, and package textproto persistence

FRESH_REQUIREMENTS:
- The agent storage maintains node definitions and task prompts mapped to nodes in dag storage.
- The agent storage serializes pending messages and reverse dependencies for nodes from dag storage into protobuf text format files using proto package store from update with ai proto ext.
- All nodes located within the same package directory resolved by the bazel target share a common package message file named `.update_with_ai.textproto`.
- The agent storage resolves the package directory against the workspace root to read and write message files at their absolute path, creating files if missing and ignoring absent files on read.
- Propagating dependencies exclude silent dependencies declared on a node.

INHERITED_REQUIREMENTS:
- [AgentStorage] The agent storage maintains nodes, dependencies, reverse dependencies, and pending messages from workspace targets.
- [AgentStorage] The agent storage provides task prompts and node definitions for declared nodes.
- [AgentStorage] Declared dependencies marked propagating mark dependent nodes dirty when changed.

GROUNDING_ARGUMENT:
- As a system singleton, AgentStorage maintains node definitions and task prompts mapped to nodes in dag storage, coordinates with imported bazel_target and file_paths in the same system lifecycle tier, and persists pending messages and reverse dependencies to package textproto files via update_with_ai_proto_ext.
"""

    @operation
    @override
    def get_node_definition(self, node: dag_storage.Node) -> Optional[agent_storage.NodeDefinition]:
        """
PURPOSE:
Retrieves stored metadata definition for a node

GROUNDING_ARGUMENT:
- Receives the node parameter directly and retrieves the matching node definition from local in-memory state.
"""
        ...

    @operation
    @override
    def get_dependencies(self, node: dag_storage.Node) -> Set[dag_storage.Dependency]:
        """
PURPOSE:
Establishes dependencies that refer to the node's upstream nodes in the graph
"""
        ...

    @operation
    @override
    def get_dependents(self, node: dag_storage.Node) -> Set[dag_storage.Node]:
        """
PURPOSE:
Establishes dependents that refer to downstream nodes depending on it
"""
        ...

    @operation
    @override
    def get_messages(self, node: dag_storage.Node) -> Set[dag_storage.Message]:
        """
PURPOSE:
Establishes messages explaining why the node requires cleaning
"""
        ...

    @operation
    @override
    def is_dirty(self, node: dag_storage.Node) -> bool:
        """
PURPOSE:
Defines dirty state on a node to indicate that it needs to be cleaned

INHERITED_REQUIREMENTS:
- [DagStorage] A node is dirty if, but not only if, it has messages.
"""
        ...

    @operation
    @override
    def register_dependent(self, node: dag_storage.Node) -> None:
        """
PURPOSE:
Provides that a node can be registered as a dependent to all of its non-silent dependencies

INHERITED_REQUIREMENTS:
- [DagStorage] Registering a node as a dependent adds the node to the dependents of all of its non-silent dependencies.
"""
        ...

    @operation
    @override
    def clear_dependents(self, node: dag_storage.Node) -> None:
        """
PURPOSE:
Provides that the dependents of a node can be cleared to avoid stale dependent relationships

INHERITED_REQUIREMENTS:
- [DagStorage] Clearing the dependents of a node empties all recorded dependents for that node.
"""
        ...

    @operation
    @override
    def add_message(self, message: dag_storage.Message, to: dag_storage.Node) -> None:
        """
PURPOSE:
Provides that messages can be added to a node to inform on why it needs to be cleaned

INHERITED_REQUIREMENTS:
- [DagStorage] Adding a message to a node records the message for that node.
"""
        ...

    @operation
    @override
    def clear_messages(self, node: dag_storage.Node) -> None:
        """
PURPOSE:
Provides that messages of a node can be cleared to inform that it no longer needs to be cleaned

INHERITED_REQUIREMENTS:
- [DagStorage] Clearing messages for a node removes all recorded messages for that node.
"""
        ...

@singleton_type('system')
class DagStorage(dag_storage.DagStorage):
    """
PURPOSE:
Implements dag storage maintaining graph structure, dependents, and pending messages

GROUNDING_ARGUMENT:
- As a system singleton, DagStorage maintains dependency graph topology and persists message and dependent records to package textproto files via bazel_target and update_with_ai_proto_ext in the same system lifecycle tier.
"""

    @operation
    @override
    def get_dependencies(self, node: dag_storage.Node) -> Set[dag_storage.Dependency]:
        """
PURPOSE:
Retrieves upstream dependencies for a node

GROUNDING_ARGUMENT:
- Receives the node parameter directly and reads recorded upstream dependencies from local storage state.
"""
        ...

    @operation
    @override
    def get_dependents(self, node: dag_storage.Node) -> Set[dag_storage.Node]:
        """
PURPOSE:
Retrieves downstream dependents for a node

GROUNDING_ARGUMENT:
- Receives the node parameter directly and queries reverse dependencies from package textproto files using bazel_target and update_with_ai_proto_ext.
"""
        ...

    @operation
    @override
    def get_messages(self, node: dag_storage.Node) -> Set[dag_storage.Message]:
        """
PURPOSE:
Retrieves pending messages for a node

GROUNDING_ARGUMENT:
- Receives the node parameter directly and queries pending messages from package textproto files using bazel_target and update_with_ai_proto_ext.
"""
        ...

    @operation
    @override
    def is_dirty(self, node: dag_storage.Node) -> bool:
        """
PURPOSE:
Determines whether a node has pending messages or missing declared source file requiring cleaning

FRESH_REQUIREMENTS:
- A node in dag storage is dirty if it has messages explaining why it requires cleaning, or if its declared source file is missing from the workspace root, recording a change message to implement the source file for the node.

INHERITED_REQUIREMENTS:
- [DagStorage] A node is dirty if, but not only if, it has messages.

GROUNDING_ARGUMENT:
- Receives the node parameter directly, evaluating whether the pending messages set retrieved from package textproto storage is non-empty, or whether its declared source file is missing from the workspace root, recording a change message to implement the source file via add_message when missing.
"""
        ...

    @operation
    @override
    def register_dependent(self, node: dag_storage.Node) -> None:
        """
PURPOSE:
Registers a node as a dependent of its non-silent dependencies

FRESH_REQUIREMENTS:
- Registering a node as a dependent adds the node to the dependents of all of its non-silent dependencies.

INHERITED_REQUIREMENTS:
- [DagStorage] Registering a node as a dependent adds the node to the dependents of all of its non-silent dependencies.

GROUNDING_ARGUMENT:
- Receives the node parameter directly, inspects its non-silent dependencies from local state, and writes updated reverse dependencies to package textproto files using bazel_target and update_with_ai_proto_ext.
"""
        ...

    @operation
    @override
    def clear_dependents(self, node: dag_storage.Node) -> None:
        """
PURPOSE:
Clears downstream dependents for a node

FRESH_REQUIREMENTS:
- Clearing the dependents of a node empties all recorded dependents for that node.

INHERITED_REQUIREMENTS:
- [DagStorage] Clearing the dependents of a node empties all recorded dependents for that node.

GROUNDING_ARGUMENT:
- Receives the node parameter directly and empties recorded dependents for that node in package textproto storage using bazel_target and update_with_ai_proto_ext.
"""
        ...

    @operation
    @override
    def add_message(self, message: dag_storage.Message, to: dag_storage.Node) -> None:
        """
PURPOSE:
Records a message for a node

FRESH_REQUIREMENTS:
- Adding a message to a node records the message explaining why the node requires cleaning.

INHERITED_REQUIREMENTS:
- [DagStorage] Adding a message to a node records the message for that node.

GROUNDING_ARGUMENT:
- Receives message and target node as parameters and records the message in package textproto storage using bazel_target and update_with_ai_proto_ext.
"""
        ...

    @operation
    @override
    def clear_messages(self, node: dag_storage.Node) -> None:
        """
PURPOSE:
Clears recorded messages for a node

FRESH_REQUIREMENTS:
- Clearing messages for a node removes all recorded messages explaining why it requires cleaning.

INHERITED_REQUIREMENTS:
- [DagStorage] Clearing messages for a node removes all recorded messages for that node.

GROUNDING_ARGUMENT:
- Receives the node parameter directly and clears recorded messages in package textproto storage using bazel_target and update_with_ai_proto_ext.
"""
        ...
