from typing import Optional, Set
from . import agent_conversation
from . import agent_driver
from . import agent_node_config
from . import agent_storage
from . import dag_node_cleaner
from . import dag_storage
from . import sandbox
from support.lib.lifecycle import LifecycleRegistry, LifecycleScope, Singleton, enter_phase, get_default_registry, get_singleton

class CleanedNode(dag_node_cleaner.CleanedNode, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        self._node: Optional[dag_storage.Node] = None

    @property
    def node(self) -> dag_storage.Node:
        # Requirement: [CleanedNode] The cleaned node presents the node currently being cleaned in the agent session.
        if self._node is None:
            raise RuntimeError("CleanedNode has not been configured with a node.")
        return self._node

    def set_node(self, node: dag_storage.Node) -> None:
        # Requirement: The cleaned node is configured with the node currently being cleaned within the agent session phase.
        self._node = node


class NodeCleaner(dag_node_cleaner.NodeCleaner, Singleton):
    tier = "system"

    def __init__(self) -> None:
        self._last_outcome: Optional[agent_driver.AgentOutcome] = None

    def clean_node(self, node: dag_storage.Node) -> Set[dag_storage.Message]:
        storage = get_singleton(agent_storage.AgentStorage)
        defn = storage.get_node_definition(node)

        # Requirement: When a dirty node defines no task prompt, cleaning resolves the node without executing an agent session phase, producing change messages for downstream dependent nodes when incoming pending messages indicate changes from upstream dependencies, and producing no propagating messages otherwise.
        if defn is None or not defn.task_prompt:
            self._last_outcome = None
            has_changes = any(isinstance(m, dag_storage.Change) for m in storage.get_messages(node))
            if has_changes:
                return {dag_storage.Change()}
            return set()

        def setup_session(session: LifecycleScope) -> None:
            # Requirement: Node cleaning executes within an agent session phase, configuring the cleaned node with the dirty node.
            cleaned_node = session.get_singleton(CleanedNode)
            cleaned_node.set_node(node)

        def _execute_session() -> Set[dag_storage.Message]:
            # Requirement: Node cleaning executes within an agent session phase, configuring the cleaned node with the dirty node.
            with enter_phase("agent_session", setup=setup_session) as session:
                defn = storage.get_node_definition(node)

                # Requirement: Startup templates from the sandbox are materialized for missing read-write files.
                sb = session.get_singleton(sandbox.Sandbox)
                sb.materialize_startup_templates()

                hist = session.get_singleton(agent_conversation.Conversation)
                # Requirement: The conversation is seeded with the task prompt, node definition, incoming pending messages ordered deterministically by content and formatted with their message content, and paired startup tool executions from the sandbox.
                if defn is not None and defn.task_prompt:
                    task_prompt = str(defn.task_prompt)
                    # Requirement: When seeding conversation with a task prompt for a node configured with a guide, the prompt is augmented with instructions directing the agent to call advance without arguments to view each guide step and not supply a change summary until all guide steps are complete when guide step mode is active, or identifying the guide file by its file alias and directing the agent to call the finish tool with a change summary describing modifications when complete, or call finish without arguments if no workspace files were modified when guide step mode is inactive.
                    n_cfg = session.get_singleton(agent_node_config.NodeConfig)
                    guide_short_name: Optional[str] = None
                    if n_cfg.guide_file is not None:
                        guide_short_name = n_cfg.guide_file.short_name
                    else:
                        for ro in n_cfg.read_only_files:
                            if ro.short_name.endswith(".md"):
                                guide_short_name = ro.short_name
                                break
                    if guide_short_name is not None:
                        if n_cfg.is_step_mode:
                            task_prompt += "\n\nCall advance() without arguments to view each guide step. Do not supply change_summary until all guide steps are complete."
                        else:
                            task_prompt += f"\n\nThe guide is in file {guide_short_name}. Call finish with a change summary describing modifications when complete, or call finish without arguments if no workspace files were modified."
                    hist.append_message(
                        agent_conversation.Message(role="user", content=task_prompt)
                    )

                # Requirement: The conversation is seeded with the task prompt, node definition, incoming pending messages ordered deterministically by content and formatted with their message content, and paired startup tool executions from the sandbox.
                # Requirement: When incoming feedback messages are present, they are formatted as actionable instructions prefaced with directives to fix read-write target files based on the feedback.
                messages_sorted = sorted(
                    storage.get_messages(node),
                    key=lambda m: (m.content, type(m).__name__),
                )
                n_cfg = session.get_singleton(agent_node_config.NodeConfig)
                rw_names = ", ".join(sorted(f.short_name for f in n_cfg.read_write_files))

                for msg in messages_sorted:
                    if isinstance(msg, dag_storage.Feedback):
                        body = f"Fix {rw_names} based on feedback: {msg.content}"
                        hist.append_message(
                            agent_conversation.Message(role="user", content=body)
                        )
                    else:
                        prefix = f"Incoming {type(msg).__name__.lower()}"
                        body = f"{prefix}: {msg.content}" if msg.content else prefix
                        hist.append_message(
                            agent_conversation.Message(role="user", content=body)
                        )

                # Requirement: The conversation is seeded with the task prompt, node definition, incoming pending messages ordered deterministically by content and formatted with their message content, and paired startup tool executions from the sandbox.
                for i, startup_exec in enumerate(sb.get_startup_tool_executions()):
                    hist.append_tool_response(
                        response=startup_exec.response,
                        tool_name=startup_exec.tool_name,
                        tool_call_id=f"startup_{i}_{startup_exec.tool_name}",
                        wire_parameter_bindings=startup_exec.wire_parameter_bindings,
                    )

                # Requirement: Node cleaning executes an agent driver with the sandbox and conversation.
                runner = session.get_singleton(agent_driver.AgentDriver)
                outcome = runner.run()
                self._last_outcome = outcome

                messages: Set[dag_storage.Message] = set()
                # Requirement: When the agent outcome indicates failure, the node remains dirty and no propagating messages are produced.
                if not outcome.is_success:
                    return messages

                content = outcome.response.content if outcome.response else ""
                # Requirement: When the agent outcome indicates blame, feedback messages containing the blame explanation are produced addressed to the blamed dependency node.
                if content.startswith("Blamed "):
                    blame_target_str = ""
                    blame_exp = ""
                    after_blamed = content[len("Blamed "):]
                    if ": " in after_blamed:
                        blame_target_str, blame_exp = after_blamed.split(": ", 1)
                        blame_target_str = blame_target_str.strip()
                        blame_exp = blame_exp.strip()
                    else:
                        blame_target_str = after_blamed.strip()

                    n_cfg = session.get_singleton(agent_node_config.NodeConfig)
                    blamed_node: Optional[dag_storage.Node] = None
                    for bt in n_cfg.blame_targets:
                        if bt.short_name == blame_target_str or str(bt) == blame_target_str:
                            blamed_node = bt.owning_node
                            break
                        if hasattr(bt, "owning_node") and bt.owning_node is not None and bt.owning_node.address == blame_target_str:
                            blamed_node = bt.owning_node
                            break

                    if blamed_node is None:
                        blamed_node = dag_storage.Node(address=blame_target_str)

                    messages.add(dag_storage.Feedback(content=blame_exp or content, target=blamed_node))
                # Requirement: When the agent outcome indicates change with workspace file modifications, change messages are produced for downstream dependent nodes, and no change messages or change summaries when no workspace files were modified.
                elif sb.has_modifications:
                    messages.add(dag_storage.Change())

                return messages

        # Requirement: Retries execution of the agent session phase a second time before propagating the failure when an agent session phase encounters an unexpected execution failure during node cleaning.
        for attempt in range(2):
            try:
                return _execute_session()
            except Exception:
                if attempt == 1:
                    raise
        return set()  # pragma: no cover (assumption: unreachable statement after 2-iteration retry loop)

    def clean(self, node: dag_storage.Node) -> bool:
        storage = get_singleton(agent_storage.AgentStorage)
        msgs = self.clean_node(node)
        if self._last_outcome is not None and not self._last_outcome.is_success:
            # Requirement: When the agent outcome indicates failure, the node remains dirty and no propagating messages are produced.
            # Requirement: [NodeCleaner] Processing cannot continue only if a failure occurs while cleaning the node that cannot be handled by cleaning any other node.
            if not storage.is_dirty(node):
                storage.add_message(dag_storage.Feedback(), to=node)
            return False

        # Requirement: After a dirty node is cleaned, the node cleaner registers the node as a dependent to its non-silent dependencies.
        storage.register_dependent(node)

        storage.clear_messages(node)

        # Requirement: When delivering messages after cleaning, feedback messages are delivered to their addressed dependency node.
        # Requirement: Change messages are delivered to downstream dependents.
        for m in msgs:
            if isinstance(m, dag_storage.Change):
                for dependent in storage.get_dependents(node):
                    storage.add_message(m, to=dependent)
            elif isinstance(m, dag_storage.Feedback):
                if m.target is not None:
                    storage.add_message(m, to=m.target)
                else:
                    for dependency in storage.get_dependencies(node):  # pragma: no cover (assumption: feedback messages always specify an addressed target)
                        storage.add_message(m, to=dependency.node)

        # Requirement: [NodeCleaner] Cleaning a dirty node communicates whether processing should continue.
        return True


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        NodeCleaner,
        keys=[NodeCleaner, dag_node_cleaner.NodeCleaner],
        tier="system",
    )
    reg.register_singleton(
        CleanedNode,
        keys=[CleanedNode, dag_node_cleaner.CleanedNode],
        tier="agent_session",
    )
