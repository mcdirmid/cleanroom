from typing import List, Optional, Self
from framework import operation, override, singleton_type
import agent_config
import loop_conversation
import openai_ext
import tool_provider

@singleton_type('agent_session')
class Conversation(loop_conversation.Conversation):
    """Implements conversation with role formatting and response stubbing.

    GROUNDING_ARGUMENT:
    - Operates as an agent_session singleton managing the sequence of conversation messages within the active session scope.
    """

    @property
    @override
    def messages(self) -> List[loop_conversation.ConversationMessage]:
        """Exposes the conversation history.

        GROUNDING_IMPLEMENTS:
        - knows("messages", List[loop_conversation.ConversationMessage]): Tracks session conversation messages.
        """
        ...

    @operation
    @override
    def append_message(self, message: loop_conversation.ConversationMessage) -> None:
        """Appends a message to the conversation history.

        GROUNDING_IMPLEMENTS:
        - action("append_message", None): Appends message to session conversation.
        """
        ...

    @operation
    @override
    def append_tool_response(self, response: tool_provider.ToolResponse, tool_name: str, tool_call_id: str, wire_parameter_bindings: Optional[tool_provider.WireParameterBindings]=...) -> None:
        """
        REQUIREMENTS:
        - A tool response's suppression key identifies the latest preceding response with the same key in the conversation for replacement with a stub, while responses with unmatched keys are preserved intact.
        - When a response is replaced with a stub, tool arguments in the correlating assistant invocation message retain their parameter keys, preserving non-string values and eliding string values longer than the supersede arg keep limit configured by the agent config to their trailing characters prefixed with a stub marker and ellipsis.
        - A stub retains the reminder from the superseded tool response, which the newly appended response inherits when omitted.
        - Each unprompted tool response presented at session start is preceded in the conversation by a synthetic assistant tool invocation message formatted according to OpenAI tool calling conventions, correlating with the response tool call identifier and ordering serialized argument parameters deterministically by parameter name, presenting the tool execution as if initiated by the model.

        GROUNDING_PROVISIONS:
        - action("append_tool_response", None): Appends tool response and stubs previous.

        GROUNDING_ARGUMENT:
        - action("append_tool_response", Self) :- action("stub_superseded_response", Self), action("synthesize_assistant_invocation", Self), knows("suppression_key", tool_provider.ToolResponse), knows("supersede_arg_keep", agent_config.AgentConfig).
        """
        ...

    @operation
    @override
    def get_model_request(self) -> loop_conversation.ModelRequest:
        """
        REQUIREMENTS:
        - The conversation formats messages in a model request according to OpenAI chat completion conventions for system, user, assistant, and tool messages.
        - Tool execution response notes, content, and reminders from the tool provider are included in visible tool message content, formatting active reminders on messages and superseded stubs to remind the agent in the assembled model request.

        GROUNDING_IMPLEMENTS:
        - action("get_model_request", loop_conversation.ModelRequest): Formats messages into model request.
        """
        ...
