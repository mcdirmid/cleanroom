from typing import Optional
from .build_graph_storage import BuildGraphStorage
from .build_agent_config import ConfigTarget
from .build_agent_config_impl import BuildAgentConfigResolverImpl
from .agent_runner_asm import AgentRunnerAsm
from .sandbox_asm import SandboxAsm
from .conversation_history_impl import ConversationHistoryFactoryImpl
from .agent_node_cleaner_impl import AgentNodeCleanerImpl
from .runner_logger import RunnerLogger


class AgentNodeCleanerAsm(AgentNodeCleanerImpl):
    def __init__(
        self,
        config_target: Optional[ConfigTarget] = None,
        storage: Optional[BuildGraphStorage] = None,
        logger: Optional[RunnerLogger] = None,
    ) -> None:
        self.config_resolver = BuildAgentConfigResolverImpl()
        self.config = self.config_resolver.resolve_config(config_target)
        runner = AgentRunnerAsm(
            model=self.config.model,
            base_url=self.config.base_url,
            api_key_env_var=self.config.api_key_env_var,
            timeout_seconds=self.config.timeout_seconds,
        )
        sandbox_factory = SandboxAsm()
        conversation_history_factory = ConversationHistoryFactoryImpl()
        super().__init__(
            runner=runner,
            sandbox_factory=sandbox_factory,
            conversation_history_factory=conversation_history_factory,
            storage=storage,
            logger=logger,
        )
