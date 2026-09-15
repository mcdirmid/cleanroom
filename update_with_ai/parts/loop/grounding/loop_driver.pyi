from framework import data_type, operation, singleton_type
from typing import Protocol
from dataclasses import dataclass
import loop_conversation
import loop_guard
import agent_config
import runner_logger
import tool_provider

@dataclass(frozen=True)
@data_type
class LoopOutcome:
    """
PURPOSE:
Final outcome of an agent session run
"""

    def __init__(self, is_success: bool, response: tool_provider.Response, conversation: loop_conversation.Conversation) -> None:
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
    def conversation(self) -> loop_conversation.Conversation:
        """
PURPOSE:
Final conversation of the session
"""
        ...

@singleton_type('agent_session')
class LoopDriver(Protocol):
    """
PURPOSE:
Defined as an agent session service that drives the agent turn loop
"""

    @operation
    def run(self) -> LoopOutcome:
        """
PURPOSE:
Drives the multi-turn agent loop until termination or limit exceeded

FRESH_REQUIREMENTS:
- The loop driver drives turns by sending model requests to a language model and executing requested tools.
- The loop driver appends model responses and correlates tool responses with tool call identifiers in the conversation.
- The loop driver can dispatch follow-up tool calls specified by tool responses, recording the follow-up execution in the conversation.
- The loop driver records log events for interaction turns, tool executions, and turn outcomes to the runner logger.
- The loop driver evaluates tool executions with the loop guard, injecting reminders or halting with an unexpected failure on runaway repetition.
- When a model response contains no tool executions, the loop driver injects a tool reminder into the conversation and continues the turn loop.
- When tool execution produces a termination outcome, the loop driver concludes and returns a loop outcome, or halts with an unexpected failure if the termination indicates a failing outcome.
- When the conversation limit from agent config is exceeded, the loop driver halts with an unexpected failure.
"""
        ...
