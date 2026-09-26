from typing import Optional, Set, Self
from framework import operation, override, singleton_type
import agent_storage
import bazel_target
import dag_storage
import file_paths
import update_with_ai_proto_ext


@singleton_type('system')
class AgentStorage(agent_storage.AgentStorage):
    """Implements graph storage with in-memory definitions, manifest loader coordination, and package textproto persistence.

    REQUIREMENTS:
    - The agent storage maintains node definitions and task prompts mapped to nodes in dag storage.
    - The agent storage serializes pending messages and reverse dependencies for nodes from dag storage into protobuf text format files.
    - All nodes located within the same package directory share a common package message file named `.update_with_ai.textproto`.
    - The agent storage resolves the package directory against the workspace root to read and write message files at their absolute path, creating files if missing and ignoring absent files on read.
    - Propagating dependencies exclude silent dependencies declared on a node.

    GROUNDING_ARGUMENT:
    - As a system singleton, AgentStorage maintains node definitions and task prompts mapped to nodes in dag storage, coordinates with imported bazel_target and file_paths in the same system lifecycle tier, and persists pending messages and reverse dependencies to package textproto files via update_with_ai_proto_ext.
    """

    @operation
    @override
    def get_node_definition(self, node: dag_storage.DagNode) -> Optional[agent_storage.NodeDefinition]:
        """Retrieves stored metadata definition for a node.

        GROUNDING_IMPLEMENTS:
        - action("get_node_definition", Optional[agent_storage.NodeDefinition]): Retrieves node definition.
        """
        ...

    @operation
    @override
    def get_dependencies(self, node: dag_storage.DagNode) -> Set[dag_storage.DagDependency]:
        """Establishes dependencies that refer to the node's upstream nodes in the graph.

        GROUNDING_IMPLEMENTS:
        - action("get_dependencies", Set[dag_storage.DagDependency]): Retrieves dependencies.
        """
        ...

    @operation
    @override
    def get_dependents(self, node: dag_storage.DagNode) -> Set[dag_storage.DagNode]:
        """Establishes dependents that refer to downstream nodes depending on it.

        GROUNDING_PROVISIONS:
        - action("get_dependents", Set[dag_storage.DagNode]): Retrieves downstream dependents.

        GROUNDING_ARGUMENT:
        - action("get_dependents", Self) :- action("extract_directory", bazel_target.BazelTarget), action("read_package_proto", Self).
        """
        ...

    @operation
    @override
    def get_messages(self, node: dag_storage.DagNode) -> Set[dag_storage.DagMessage]:
        """Establishes messages explaining why the node requires cleaning.

        GROUNDING_PROVISIONS:
        - action("get_messages", Set[dag_storage.DagMessage]): Retrieves messages for node.

        GROUNDING_ARGUMENT:
        - action("get_messages", Self) :- action("extract_directory", bazel_target.BazelTarget), action("read_package_proto", Self).
        """
        ...

    @operation
    @override
    def is_dirty(self, node: dag_storage.DagNode) -> bool:
        """Defines dirty state on a node to indicate that it needs to be cleaned.

        GROUNDING_PROVISIONS:
        - action("is_dirty", bool): Returns dirty status.

        GROUNDING_ARGUMENT:
        - action("is_dirty", Self) :- action("get_messages", Self), action("add_message", Self).
        """
        ...

    @operation
    @override
    def register_dependent(self, node: dag_storage.DagNode) -> None:
        """Provides that a node can be registered as a dependent to all of its non-silent dependencies.

        GROUNDING_PROVISIONS:
        - action("register_dependent", None): Registers node as dependent.

        GROUNDING_ARGUMENT:
        - action("register_dependent", Self) :- action("extract_directory", bazel_target.BazelTarget), action("write_package_proto", Self).
        """
        ...

    @operation
    @override
    def clear_dependents(self, node: dag_storage.DagNode) -> None:
        """Provides that the dependents of a node can be cleared to avoid stale dependent relationships.

        GROUNDING_PROVISIONS:
        - action("clear_dependents", None): Clears dependents.

        GROUNDING_ARGUMENT:
        - action("clear_dependents", Self) :- action("extract_directory", bazel_target.BazelTarget), action("write_package_proto", Self).
        """
        ...

    @operation
    @override
    def add_message(self, message: dag_storage.DagMessage, to: dag_storage.DagNode) -> None:
        """Provides that messages can be added to a node to inform on why it needs to be cleaned.

        GROUNDING_PROVISIONS:
        - action("add_message", None): Adds message to node.

        GROUNDING_ARGUMENT:
        - action("add_message", Self) :- action("extract_directory", bazel_target.BazelTarget), action("write_package_proto", Self).
        """
        ...

    @operation
    @override
    def clear_messages(self, node: dag_storage.DagNode) -> None:
        """Provides that messages of a node can be cleared to inform that it no longer needs to be cleaned.

        GROUNDING_PROVISIONS:
        - action("clear_messages", None): Clears messages on node.

        GROUNDING_ARGUMENT:
        - action("clear_messages", Self) :- action("extract_directory", bazel_target.BazelTarget), action("write_package_proto", Self).
        """
        ...


@singleton_type('system')
class DagStorage(dag_storage.DagStorage):
    """Implements dag storage maintaining graph structure, dependents, and pending messages.

    GROUNDING_ARGUMENT:
    - As a system singleton, DagStorage maintains dependency graph topology and persists message and dependent records to package textproto files via bazel_target and update_with_ai_proto_ext in the same system lifecycle tier.
    """

    @operation
    @override
    def get_dependencies(self, node: dag_storage.DagNode) -> Set[dag_storage.DagDependency]:
        """Retrieves upstream dependencies for a node.

        GROUNDING_IMPLEMENTS:
        - action("get_dependencies", Set[dag_storage.DagDependency]): Retrieves upstream dependencies.
        """
        ...

    @operation
    @override
    def get_dependents(self, node: dag_storage.DagNode) -> Set[dag_storage.DagNode]:
        """Retrieves downstream dependents for a node.

        GROUNDING_PROVISIONS:
        - action("get_dependents", Set[dag_storage.DagNode]): Retrieves downstream dependents.

        GROUNDING_ARGUMENT:
        - action("get_dependents", Self) :- action("extract_directory", bazel_target.BazelTarget), action("read_package_proto", Self).
        """
        ...

    @operation
    @override
    def get_messages(self, node: dag_storage.DagNode) -> Set[dag_storage.DagMessage]:
        """Retrieves pending messages for a node.

        GROUNDING_PROVISIONS:
        - action("get_messages", Set[dag_storage.DagMessage]): Retrieves pending messages.

        GROUNDING_ARGUMENT:
        - action("get_messages", Self) :- action("extract_directory", bazel_target.BazelTarget), action("read_package_proto", Self).
        """
        ...

    @operation
    @override
    def is_dirty(self, node: dag_storage.DagNode) -> bool:
        """Determines whether a node has pending messages or missing declared source file requiring cleaning.

        REQUIREMENTS:
        - A node in dag storage is dirty if it has messages explaining why it requires cleaning, or if its declared source file is missing from the workspace root, recording a change message to implement the source file for the node.

        GROUNDING_PROVISIONS:
        - action("is_dirty", bool): Returns dirty status.

        GROUNDING_ARGUMENT:
        - action("is_dirty", Self) :- action("get_messages", Self), action("add_message", Self).
        """
        ...

    @operation
    @override
    def register_dependent(self, node: dag_storage.DagNode) -> None:
        """Registers a node as a dependent of its non-silent dependencies.

        REQUIREMENTS:
        - Registering a node as a dependent adds the node to the dependents of all of its non-silent dependencies.

        GROUNDING_PROVISIONS:
        - action("register_dependent", None): Registers node as dependent.

        GROUNDING_ARGUMENT:
        - action("register_dependent", Self) :- action("extract_directory", bazel_target.BazelTarget), action("write_package_proto", Self).
        """
        ...

    @operation
    @override
    def clear_dependents(self, node: dag_storage.DagNode) -> None:
        """Clears downstream dependents for a node.

        REQUIREMENTS:
        - Clearing the dependents of a node empties all recorded dependents for that node.

        GROUNDING_PROVISIONS:
        - action("clear_dependents", None): Clears dependents.

        GROUNDING_ARGUMENT:
        - action("clear_dependents", Self) :- action("extract_directory", bazel_target.BazelTarget), action("write_package_proto", Self).
        """
        ...

    @operation
    @override
    def add_message(self, message: dag_storage.DagMessage, to: dag_storage.DagNode) -> None:
        """Records a message for a node.

        REQUIREMENTS:
        - Adding a message to a node records the message explaining why the node requires cleaning.

        GROUNDING_PROVISIONS:
        - action("add_message", None): Adds message to node.

        GROUNDING_ARGUMENT:
        - action("add_message", Self) :- action("extract_directory", bazel_target.BazelTarget), action("write_package_proto", Self).
        """
        ...

    @operation
    @override
    def clear_messages(self, node: dag_storage.DagNode) -> None:
        """Clears recorded messages for a node.

        REQUIREMENTS:
        - Clearing messages for a node removes all recorded messages explaining why it requires cleaning.

        GROUNDING_PROVISIONS:
        - action("clear_messages", None): Clears recorded messages.

        GROUNDING_ARGUMENT:
        - action("clear_messages", Self) :- action("extract_directory", bazel_target.BazelTarget), action("write_package_proto", Self).
        """
        ...
