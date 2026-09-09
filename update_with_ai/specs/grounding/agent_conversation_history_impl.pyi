from typing import List
from framework import operation, override, singleton_type
import agent_conversation_history
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
- Operates as an agent_session singleton managing the sequence of conversation messages within the active session scope, accessing data types from imported agent_conversation_history and tool_provider in the same lifecycle tier.
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
    def append_tool_response(self, response: tool_provider.Response, tool_name: str, tool_call_id: str) -> None:
        """
PURPOSE:
Appends a tool response, replacing superseded results with a stub

FRESH_REQUIREMENTS:
- Tool execution response notes and content from the tool provider are included in visible tool message content.
- An unprompted tool response presented at session start is preceded in the conversation history by a synthetic assistant tool invocation message addressing the corresponding tool name.

INHERITED_REQUIREMENTS:
- [ConversationHistory] When an appended tool result supersedes an earlier result for the same resource, the earlier result is replaced in place with a stub.

GROUNDING_ARGUMENT:
- Receives the response, tool_name, and tool_call_id as parameters, accesses visible tool notes and content from the imported tool_provider.Response data type, inspects prior entries in self.messages to replace superseded resource results with stubs, and prepends synthetic tool invocations when unprompted at session start.
"""
        ...

    @operation
    @override
    def get_model_request(self) -> agent_conversation_history.ModelRequest:
        """
PURPOSE:
Formats messages into a provider model request

FRESH_REQUIREMENTS:
- Messages in a model request are formatted according to model provider roles for system, user, assistant, and tool messages.
- Messages in a model request omit internal metadata fields starting with an underscore.

INHERITED_REQUIREMENTS:
- [ConversationHistory] The conversation history produces a model request prepared for transmission to a language model.

GROUNDING_ARGUMENT:
- Reads self.messages stored directly on the agent_session singleton, transforms roles and strips internal metadata keys from message contents, and produces an agent_conversation_history.ModelRequest value record without requiring external singleton collaborators.
"""
        ...
