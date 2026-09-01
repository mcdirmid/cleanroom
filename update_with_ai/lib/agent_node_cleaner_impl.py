from typing import Sequence, Optional, List, Any
from .dag_storage import NodeId, PendingMessage
from .dag_node_cleaner import NodeCleaningOutcome, ChangeMessage, FeedbackMessage
from .agent_runner import AgentRunner
from .agent_node_cleaner import AgentNodeCleaner
from .sandbox import Sandbox, SandboxFactory, SandboxConfig
from .conversation_history import ConversationHistoryFactory, HistoryMessage
from .runner_logger import RunnerLogger
from .build_graph_storage import BuildGraphStorage


class AgentNodeCleanerImpl(AgentNodeCleaner):
    def __init__(
        self,
        runner: AgentRunner,
        sandbox_factory: SandboxFactory,
        conversation_history_factory: ConversationHistoryFactory,
        storage: BuildGraphStorage,
        logger: Optional[RunnerLogger] = None,
    ) -> None:
        self._runner = runner
        self._sandbox_factory = sandbox_factory
        self._conversation_history_factory = conversation_history_factory
        self._storage = storage
        self._logger = logger

    def clean_node(
        self, node: NodeId, pending_messages: Sequence[PendingMessage]
    ) -> NodeCleaningOutcome:
        sandbox_config = self._storage.get_sandbox_config(node)
        task_prompt = self._storage.get_task_prompt(node)

        sandbox = self._sandbox_factory.create_sandbox(sandbox_config)
        sandbox.materialize_startup_templates()

        history = self._conversation_history_factory.create_conversation_history()
        initial_history: List[HistoryMessage] = []
        if task_prompt:
            initial_history.append(HistoryMessage(role="user", content=task_prompt))

        # Seed startup interaction with synthetic tool calls paired with tool results
        startup_interaction = sandbox.get_startup_interaction()
        ro_files = list(sandbox_config.read_only_files)
        call_counter = 0

        for idx, item in enumerate(startup_interaction):
            call_id = f"startup_call_{call_counter}"
            call_counter += 1
            if item.guidance or idx >= len(ro_files):
                # Step delivery (initial advance)
                initial_history.append(
                    HistoryMessage(
                        role="assistant",
                        content="",
                        metadata={"tool_calls": [{"id": call_id, "type": "function", "function": {"name": "advance", "arguments": "{}"}}]},
                    )
                )
                initial_history.append(
                    HistoryMessage(
                        role="tool",
                        content=item.content,
                        metadata={"tool_call_id": call_id, "name": "advance", "guidance": item.guidance},
                    )
                )
            else:
                # Session start read
                vname = ro_files[idx]
                args = f'{{"file_name": "{vname}"}}'
                initial_history.append(
                    HistoryMessage(
                        role="assistant",
                        content="",
                        metadata={"tool_calls": [{"id": call_id, "type": "function", "function": {"name": "read_file", "arguments": args}}]},
                    )
                )
                initial_history.append(
                    HistoryMessage(
                        role="tool",
                        content=item.content,
                        metadata={"tool_call_id": call_id, "name": "read_file"},
                    )
                )

        for m in pending_messages:
            initial_history.append(HistoryMessage(role="user", content=m.content))
        history.initialize(initial_history)

        outcome = self._runner.run(tool_provider=sandbox, history=history, logger=self._logger)

        term_content = outcome.termination.content
        if "Failed" in term_content or "limit exceeded" in term_content:
            return None

        if term_content.startswith("Blamed "):
            return [FeedbackMessage(content=term_content, sender=node)]

        if sandbox.has_file_modifications():
            return [ChangeMessage(content=f"Modified files for {node}", sender=node)]

        return []


