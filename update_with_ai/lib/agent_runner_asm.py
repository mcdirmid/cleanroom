import os
from typing import Optional
from .openai_ext import OpenAiExtImpl, ModelName
from .loop_guard_impl import LoopGuardImpl
from .runner_logger_impl import RunnerLoggerImpl
from .agent_runner_impl import AgentRunnerImpl


class AgentRunnerAsm(AgentRunnerImpl):
    def __init__(
        self,
        model: ModelName,
        base_url: str = "https://api.openai.com/v1",
        api_key_env_var: Optional[str] = None,
        timeout_seconds: int = 60,
    ) -> None:
        api_key = (
            os.environ.get(api_key_env_var, "")
            if api_key_env_var
            else (os.environ.get("OPENAI_API_KEY") or os.environ.get("AGENT_API_KEY") or "")
        )
        ext = OpenAiExtImpl(
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )
        self.loop_guard = LoopGuardImpl()
        self.logger = RunnerLoggerImpl()
        super().__init__(openai_ext=ext, model=model)

