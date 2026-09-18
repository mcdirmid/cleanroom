from typing import Optional, Sequence, Set
from . import loop_conversation
from . import loop_driver
from . import loop_node_cleaner
from update_with_ai.parts.agent.lib import agent_node_config
from update_with_ai.parts.agent.lib import agent_storage
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.sandbox.lib import sandbox
from update_with_ai.parts.sandbox.lib import template_format
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleScope,
    Singleton,
    enter_phase,
    get_default_registry,
    get_singleton,
)


class CleanedNodes(loop_node_cleaner.CleanedNodes, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        self._nodes: Sequence[dag_storage.Node] = ()

    @property
    def nodes(self) -> Sequence[dag_storage.Node]:
        # Requirement: [CleanedNodes] The cleaned nodes service presents the sequence of nodes currently being cleaned in the agent session.
        if not self._nodes:
            raise RuntimeError("CleanedNodes has not been configured with nodes.")
        return self._nodes

    def set_nodes(self, nodes: Sequence[dag_storage.Node]) -> None:
        # Requirement: The cleaned nodes present the nodes currently being cleaned to session services.
        self._nodes = tuple(nodes)


class NodeCleaner(loop_node_cleaner.NodeCleaner, Singleton):
    tier = "system"

    def __init__(self) -> None:
        self._last_outcome: Optional[loop_driver.LoopOutcome] = None

    def clean_nodes(
        self, nodes: Sequence[dag_storage.Node]
    ) -> Set[dag_storage.Message]:
        dirty_nodes = list(nodes)
        storage = get_singleton(agent_storage.AgentStorage)
        defns = [storage.get_node_definition(n) for n in dirty_nodes]

        # Requirement: When dirty nodes define no task prompt, cleaning resolves the nodes without establishing an agent session phase, producing change messages for downstream dependent nodes when incoming pending messages indicate changes from upstream dependencies, and producing no propagating messages otherwise.
        has_prompt = any(d is not None and bool(d.task_prompt) for d in defns)
        if not has_prompt:
            self._last_outcome = None
            has_changes = any(
                any(isinstance(m, dag_storage.Change) for m in storage.get_messages(n))
                for n in dirty_nodes
            )
            if has_changes:
                return {dag_storage.Change()}
            return set()

        def setup_session(session: LifecycleScope) -> None:
            # Requirement: The node cleaner cleans dirty nodes within an agent session phase where the cleaned nodes present the nodes currently being cleaned to session services, retrying the session phase once upon encountering an unexpected execution failure before propagating the failure.
            cleaned_nodes = session.get_singleton(CleanedNodes)
            cleaned_nodes.set_nodes(dirty_nodes)

        def _execute_session() -> Set[dag_storage.Message]:
            # Requirement: The node cleaner cleans dirty nodes within an agent session phase where the cleaned nodes present the nodes currently being cleaned to session services, retrying the session phase once upon encountering an unexpected execution failure before propagating the failure.
            with enter_phase("agent_session", setup=setup_session) as session:
                # Requirement: Within the agent session phase, missing read-write files materialize from sandbox startup templates.
                sb = session.get_singleton(sandbox.Sandbox)
                sb.materialize_startup_templates()

                hist = session.get_singleton(loop_conversation.Conversation)
                n_cfg = session.get_singleton(agent_node_config.NodeConfig)
                formatter = session.get_singleton(template_format.TemplateFormatter)

                # Requirement: The conversation is initialized with startup context comprising the node definition and task prompt retrieved from graph storage for dirty nodes, incoming pending messages ordered deterministically by content and formatted with their message content, and paired startup tool executions from the sandbox formatted with synthetic tool requests and captured responses.
                # Requirement: The task prompt is formatted using the template formatter.
                guide_file_alias: Optional[str] = None
                if n_cfg.guide_file is not None:
                    guide_file_alias = n_cfg.guide_file.relative_path
                else:
                    for ro in n_cfg.read_only_files:
                        if ro.relative_path.endswith(".md"):
                            guide_file_alias = ro.relative_path
                            break

                node_items: list[dict[str, str]] = []
                for n in dirty_nodes:
                    defn = storage.get_node_definition(n)
                    prompt_str = (
                        str(defn.task_prompt)
                        if defn is not None and defn.task_prompt
                        else ""
                    )
                    alias_str = n_cfg.src_file_alias_by_node.get(n, "")
                    node_items.append(
                        {"src_alias": alias_str, "task_prompt": prompt_str}
                    )

                is_multi_node = len(dirty_nodes) > 1

                guide_instruction = ""
                if guide_file_alias is not None:
                    if n_cfg.is_step_mode:
                        # Requirement: Task prompt instructions for a guided node include directing the agent to call advance without arguments to view each guide step and omit a change summary until all guide steps are complete when guide step mode is active.
                        guide_instruction = "Call advance() without arguments to view each guide step. Do not supply change_summary until all guide steps are complete."
                    else:
                        # Requirement: Task prompt instructions for a guided node include identifying the guide file by its file alias and directing the agent to call the submit tool with a change summary describing modifications when complete, or call submit without arguments if no workspace files were modified, when guide step mode is inactive.
                        guide_instruction = f"The guide is in file {guide_file_alias}. Call submit with a change summary describing modifications when complete, or call submit without arguments if no workspace files were modified. Inspect {guide_file_alias} using view_file for all implementation constraints, contracts, and requirements."

                # Requirement: When cleaning multiple nodes, the task prompt enumerates each target file identified by its file alias alongside its task prompt.
                # Requirement: The task prompt is formatted using the template formatter.
                prompt_template = (
                    "<!-- if: is_multi_node -->\n"
                    "Process the following files:\n"
                    "<!-- for: node in nodes -->\n"
                    "- `<node.src_alias>`: <node.task_prompt>\n"
                    "<!-- endfor -->\n"
                    "\n"
                    "Call submit(target='<file_name>') to submit each file individually.\n"
                    "<!-- endif -->\n"
                    "<!-- if: not_multi_node -->\n"
                    "<task_prompt>\n"
                    "<!-- endif -->\n"
                    "<!-- if: has_guide -->\n"
                    "\n"
                    "<guide_instruction>\n"
                    "<!-- endif -->"
                )
                single_prompt = node_items[0]["task_prompt"] if node_items else ""
                rendered_prompt = formatter.format_template(
                    prompt_template,
                    {
                        "is_multi_node": is_multi_node,
                        "not_multi_node": not is_multi_node,
                        "nodes": node_items,
                        "task_prompt": single_prompt,
                        "has_guide": bool(guide_instruction),
                        "guide_instruction": guide_instruction,
                    },
                ).strip()

                hist.append_message(
                    loop_conversation.Message(role="user", content=rendered_prompt)
                )

                # Requirement: The conversation is initialized with startup context comprising the node definition and task prompt retrieved from graph storage for dirty nodes, incoming pending messages ordered deterministically by content and formatted with their message content, and paired startup tool executions from the sandbox formatted with synthetic tool requests and captured responses.
                # Requirement: Incoming feedback and change messages are formatted per target node identified by its file alias, prefaced with directives to fix read-write target files based on the feedback.
                for n in dirty_nodes:
                    target_name = n_cfg.src_file_alias_by_node.get(n) or ", ".join(
                        sorted(f.relative_path for f in n_cfg.read_write_files)
                    )
                    messages_sorted = sorted(
                        storage.get_messages(n),
                        key=lambda m: (m.content, type(m).__name__),
                    )
                    for msg in messages_sorted:
                        if isinstance(msg, dag_storage.Feedback):
                            body = f"Fix {target_name} based on feedback: {msg.content}"
                        else:
                            prefix = f"Incoming {type(msg).__name__.lower()}"
                            if is_multi_node:
                                body = (
                                    f"{prefix} for {target_name}: {msg.content}"
                                    if msg.content
                                    else f"{prefix} for {target_name}"
                                )
                            else:
                                body = (
                                    f"{prefix}: {msg.content}"
                                    if msg.content
                                    else prefix
                                )
                        hist.append_message(
                            loop_conversation.Message(role="user", content=body)
                        )

                for i, startup_exec in enumerate(sb.get_startup_tool_executions()):
                    hist.append_tool_response(
                        response=startup_exec.response,
                        tool_name=startup_exec.tool_name,
                        tool_call_id=f"startup_{i}_{startup_exec.tool_name}",
                        wire_parameter_bindings=startup_exec.wire_parameter_bindings,
                    )

                runner = session.get_singleton(loop_driver.LoopDriver)
                outcome = runner.run()
                self._last_outcome = outcome

                messages: Set[dag_storage.Message] = set()
                # Requirement: Resolving dirty nodes produces no propagating messages when the outcome signals run failure, leaving the nodes dirty and communicating that processing cannot continue.
                if not outcome.is_success:
                    return messages

                content = outcome.response.content if outcome.response else ""
                # Requirement: Resolving dirty nodes produces feedback messages containing the blame explanation and addressed to the blamed dependency node owning the blamed file when the outcome signals blame attributed to that dependency node.
                if content.startswith("Blamed "):
                    blame_target_str = ""
                    blame_exp = ""
                    after_blamed = content[len("Blamed ") :]
                    if ": " in after_blamed:
                        blame_target_str, blame_exp = after_blamed.split(": ", 1)
                        blame_target_str = blame_target_str.strip()
                        blame_exp = blame_exp.strip()
                    else:
                        blame_target_str = after_blamed.strip()

                    n_cfg = session.get_singleton(agent_node_config.NodeConfig)
                    blamed_node: Optional[dag_storage.Node] = None
                    for bt in n_cfg.blame_targets:
                        bt_alias = getattr(
                            bt, "relative_path", getattr(bt, "short_name", str(bt))
                        )
                        if (
                            bt_alias == blame_target_str
                            or str(bt) == blame_target_str
                        ):
                            blamed_node = bt.owning_node
                            break
                        if (
                            hasattr(bt, "owning_node")
                            and bt.owning_node is not None
                            and (
                                bt.owning_node.unit_address == blame_target_str
                                or f"{bt.owning_node.unit_address}#{bt.owning_node.role_address}"
                                == blame_target_str
                            )
                        ):
                            blamed_node = bt.owning_node
                            break

                    if blamed_node is None:
                        if "#" in blame_target_str:
                            u, r = blame_target_str.split("#", 1)
                            blamed_node = dag_storage.Node(
                                unit_address=u, role_address=r
                            )
                        else:
                            blamed_node = dag_storage.Node(
                                unit_address=blame_target_str, role_address=""
                            )

                    messages.add(
                        dag_storage.Feedback(
                            content=blame_exp or content, target=blamed_node
                        )
                    )
                # Requirement: Resolving dirty nodes produces change messages for downstream dependent nodes when the outcome signals successful advancement with workspace file modifications, and no change messages or change summaries when no workspace files were modified.
                elif sb.has_modifications:
                    messages.add(dag_storage.Change())

                return messages

        # Requirement: The node cleaner cleans dirty nodes within an agent session phase where the cleaned nodes present the nodes currently being cleaned to session services, retrying the session phase once upon encountering an unexpected execution failure before propagating the failure.
        for attempt in range(2):
            try:
                return _execute_session()
            except Exception:
                if attempt == 1:
                    raise
        return set()

    def clean(self, nodes: Sequence[dag_storage.Node]) -> bool:
        storage = get_singleton(agent_storage.AgentStorage)
        msgs = self.clean_nodes(nodes)
        if self._last_outcome is not None and not self._last_outcome.is_success:
            # Requirement: Resolving dirty nodes produces no propagating messages when the outcome signals run failure, leaving the nodes dirty and communicating that processing cannot continue.
            # Requirement: [NodeCleaner] Processing cannot continue only if a failure occurs while cleaning the nodes that cannot be handled by cleaning any other node.
            for node in nodes:
                if not storage.is_dirty(node):
                    storage.add_message(dag_storage.Feedback(), to=node)
            return False

        # Requirement: Cleaning dirty nodes registers the nodes as dependents to their non-silent dependencies in graph storage, delivering resulting change messages to downstream dependents and feedback messages to their addressed dependency node.
        for node in nodes:
            storage.register_dependent(node)
            storage.clear_messages(node)

        # Requirement: Cleaning dirty nodes registers the nodes as dependents to their non-silent dependencies in graph storage, delivering resulting change messages to downstream dependents and feedback messages to their addressed dependency node.
        for m in msgs:
            if isinstance(m, dag_storage.Change):
                for node in nodes:
                    for dependent in storage.get_dependents(node):
                        storage.add_message(m, to=dependent)
            elif isinstance(m, dag_storage.Feedback):
                if m.target is not None:
                    storage.add_message(m, to=m.target)
                else:
                    for node in nodes:
                        for dependency in storage.get_dependencies(node):
                            storage.add_message(m, to=dependency.node)

        # Requirement: [NodeCleaner] Cleaning dirty nodes communicates whether processing should continue.
        return True


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        NodeCleaner,
        keys=[NodeCleaner, loop_node_cleaner.NodeCleaner],
        tier="system",
    )
    reg.register_singleton(
        CleanedNodes,
        keys=[CleanedNodes, loop_node_cleaner.CleanedNodes],
        tier="agent_session",
    )
