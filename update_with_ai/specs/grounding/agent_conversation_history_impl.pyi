from typing import List, Optional
from framework import operation, override, singleton_type
import agent_conversation_history
import openai_ext
import tool_provider

@singleton_type('agent_session')
class ConversationHistory(agent_conversation_history.ConversationHistory):
    """
PURPOSE:
Implements conversation history with role formatting and metadata stripping

INHERITED_REQUIREMENTS:
- [ConversationHistory] Initial messages can seed the conversation history at session start.
- [ConversationHistory] Appending messages and tool responses adds them in chronological order.

GROUNDING_ARGUMENT:
- Operates as an agent_session singleton managing the sequence of conversation messages within the active session scope, accessing data types from imported agent_conversation_history, openai_ext, and tool_provider in the same lifecycle tier.
"""

    @property
    @override
    def messages(self) -> List[agent_conversation_history.Message]:
        """
PURPOSE:
Current sequence of messages in the session

GROUNDING_ARGUMENT:
- Returns the internal sequence of messages maintained within the agent_session singleton, initialized at session startup and populated via mutable operations (append_message, append_tool_response).
"""
        ...

    @operation
    @override
    def append_message(self, message: agent_conversation_history.Message) -> None:
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
- Each unprompted tool response presented at session start is preceded in the conversation history by a synthetic assistant tool invocation message formatted according to OpenAI tool calling conventions, correlating with the response tool call identifier and ordering serialized argument parameters deterministically by parameter name, presenting the tool execution as if initiated by the model.
- When an appended tool result supersedes an earlier result for the same resource, earlier tool results matching the resource identifier—such as the target read-write file alias identified by internal metadata markers or single-instance tool executions—are replaced in place with a stub, while tool results for distinct resources and read-only files are preserved.
- A stub retains any reminder provided in the superseded tool response to remind the agent in subsequent turns, and when the newly appended tool result does not supply a reminder, it inherits the reminder from the superseded response.

INHERITED_REQUIREMENTS:
- [ConversationHistory] When an appended tool result supersedes an earlier result for the same mutable resource, the earlier result is replaced in place with a stub, while tool results for read-only resources are never superseded.
- [ConversationHistory] A stub retains any reminder provided in the superseded tool response to remind the agent in subsequent turns, and when the newly appended tool response does not supply a reminder, it inherits the reminder from the superseded response.

GROUNDING_ARGUMENT:
- Receives the response, tool_name, tool_call_id, and optional wire_parameter_bindings as parameters, accesses visible tool notes, content, and reminder from the imported tool_provider.Response data type, inspects prior entries in self.messages to replace superseded mutable resource results matching internal metadata markers or tool names with stubs while preserving distinct resources, read-only results, and superseded reminders, and prepends synthetic tool invocations conforming to openai_ext tool calling conventions correlating by tool call identifier with deterministically ordered argument parameters when unprompted at session start.
"""
        ...

    @operation
    @override
    def get_model_request(self) -> agent_conversation_history.ModelRequest:
        """
PURPOSE:
Formats messages into a provider model request

FRESH_REQUIREMENTS:
- The conversation history formats messages in a model request according to OpenAI chat completion conventions for system, user, assistant, and tool messages.
- Messages in a model request omit internal metadata fields starting with an underscore.
- Tool execution response notes, content, and reminders from the tool provider are included in visible tool message content, formatting active reminders on messages and superseded stubs to remind the agent in the assembled model request.

INHERITED_REQUIREMENTS:
- [ConversationHistory] The conversation history produces a model request prepared for transmission to a language model.

GROUNDING_ARGUMENT:
- Reads self.messages stored directly on the agent_session singleton, transforms roles and tool call structures adhering to openai_ext chat completion schemas, strips internal metadata keys from message contents, and formats active reminders into visible tool message content, producing an agent_conversation_history.ModelRequest value record without requiring external singleton collaborators.
"""
        ...
