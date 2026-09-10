from framework import data_type, operation, singleton_type
from typing import Protocol
from dataclasses import dataclass
import agent_conversation_history
import agent_loop_guard
import model_config
import runner_logger
import tool_provider

@dataclass(frozen=True)
@data_type
class AgentOutcome:
    """
PURPOSE:
Final outcome of an agent session run
"""

    def __init__(self, is_success: bool, response: tool_provider.Response, conversation_history: agent_conversation_history.ConversationHistory) -> None:
        ...

    @property
    def is_success(self) -> bool:
        """
PURPOSE:
Indicates whether the session completed successfully
"""
        ...

    @property
    def response(self) -> tool_provider.Response:
        """
PURPOSE:
Final response from the concluding tool execution
"""
        ...

    @property
    def conversation_history(self) -> agent_conversation_history.ConversationHistory:
        """
PURPOSE:
Final conversation history of the session
"""
        ...

@singleton_type('agent_session')
class AgentRunner(Protocol):
    """
PURPOSE:
Defined as an agent session service that drives the agent turn loop
"""

    @operation
    def run(self) -> AgentOutcome:
        """
PURPOSE:
Drives the multi-turn agent loop until termination or limit exceeded

FRESH_REQUIREMENTS:
- The agent runner drives turns by sending model requests to a language model and executing requested tools.
- The agent runner appends model responses and correlates tool responses with tool call identifiers in conversation history.
- The agent runner records log events for model requests, responses, and tool executions to the runner logger, providing summaries with turn progress, tool calls with arguments or text snippets, and execution outcomes.
- The agent runner evaluates tool executions with the loop guard, injecting reminders or terminating on failure.
- When a model response contains no tool executions, the agent runner injects a tool reminder into the conversation history and continues the turn loop.
- When tool execution produces a termination outcome, the agent runner concludes and returns an agent outcome.
- When the conversation limit from model config is exceeded, the agent runner concludes with a failure outcome.
"""
        ...
