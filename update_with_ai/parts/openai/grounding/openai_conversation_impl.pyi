from typing import List, Optional
from framework import operation, override, singleton_type
import agent_conversation
import openai_ext
import tool_provider

@singleton_type('agent_session')
class Conversation(agent_conversation.Conversation):
    """
PURPOSE:
Implements conversation with role formatting and response stubbing

INHERITED_REQUIREMENTS:
- [Conversation] Initial messages can seed the conversation at session start.
- [Conversation] Appending messages and tool responses adds them in chronological order.

GROUNDING_ARGUMENT:
- Operates as an agent_session singleton managing the sequence of conversation messages within the active session scope, accessing data types from imported agent_conversation, openai_ext, and tool_provider in the same lifecycle tier.
"""

    @property
    @override
    def messages(self) -> List[agent_conversation.Message]:
        """
PURPOSE:
Current sequence of messages in the session

GROUNDING_ARGUMENT:
- Returns the internal sequence of messages maintained within the agent_session singleton, initialized at session startup and populated via mutable operations (append_message, append_tool_response).
"""
        ...

    @operation
    @override
    def append_message(self, message: agent_conversation.Message) -> None:
        """
PURPOSE:
Appends a message to the history

GROUNDING_ARGUMENT:
- Receives the message value object directly as a parameter and appends it to the local messages sequence stored in self.
"""
        ...

    @operation
    @override
    def append_tool_response(self, response: tool_provider.Response, tool_name: str, tool_call_id: str, wire_parameter_bindings: Optional[tool_provider.WireParameterBindings]=...) -> None:
        """
PURPOSE:
Appends a tool response, replacing superseded results with a stub

FRESH_REQUIREMENTS:
- A tool response's suppression key identifies the latest preceding response with the same key in the conversation for replacement with a stub, while responses with unmatched keys are preserved intact.
- A stub retains the reminder from the superseded tool response, which the newly appended response inherits when omitted.
- Each unprompted tool response presented at session start is preceded in the conversation by a synthetic assistant tool invocation message formatted according to OpenAI tool calling conventions, correlating with the response tool call identifier and ordering serialized argument parameters deterministically by parameter name, presenting the tool execution as if initiated by the model.

INHERITED_REQUIREMENTS:
- [Conversation] Stubs previous responses identified by a suppression key.

GROUNDING_ARGUMENT:
- Receives the response, tool_name, tool_call_id, and optional wire_parameter_bindings as parameters, inspects response.suppression_key against prior tool responses in self.messages to replace the latest preceding response having a matching suppression key with a stub while preserving unmatched responses and superseded reminders, and prepends synthetic tool invocations conforming to openai_ext tool calling conventions correlating by tool call identifier with deterministically ordered argument parameters when unprompted at session start.
"""
        ...

    @operation
    @override
    def get_model_request(self) -> agent_conversation.ModelRequest:
        """
PURPOSE:
Formats messages into a provider model request

FRESH_REQUIREMENTS:
- The conversation formats messages in a model request according to OpenAI chat completion conventions for system, user, assistant, and tool messages.
- Tool execution response notes, content, and reminders from the tool provider are included in visible tool message content, formatting active reminders on messages and superseded stubs to remind the agent in the assembled model request.

INHERITED_REQUIREMENTS:
- [Conversation] The conversation produces a model request prepared for transmission to a language model.

GROUNDING_ARGUMENT:
- Reads self.messages stored directly on the agent_session singleton, transforms roles and tool call structures adhering to openai_ext chat completion schemas, and formats active reminders into visible tool message content, producing an agent_conversation.ModelRequest value record without requiring external singleton collaborators.
"""
        ...
