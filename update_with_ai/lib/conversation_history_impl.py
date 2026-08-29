"""
lib/conversation_history_impl.py

Implementation of ConversationHistory protocol for OpenAI format.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple, Union, cast

try:
    from openai.types.chat import (
        ChatCompletionAssistantMessageParam,
        ChatCompletionSystemMessageParam,
        ChatCompletionToolMessageParam,
        ChatCompletionUserMessageParam,
    )
    from openai.types.chat.chat_completion_message import ChatCompletionMessage
    from openai.types.chat.chat_completion_message_function_tool_call import (
        ChatCompletionMessageFunctionToolCall,
        Function,
    )
except ImportError:
    class ChatCompletionAssistantMessageParam(dict):  # type: ignore
        pass
    class ChatCompletionSystemMessageParam(dict):  # type: ignore
        pass
    class ChatCompletionToolMessageParam(dict):  # type: ignore
        pass
    class ChatCompletionUserMessageParam(dict):  # type: ignore
        pass
    class Function:  # type: ignore
        def __init__(self, name: str, arguments: str) -> None:
            self.name = name
            self.arguments = arguments
    class ChatCompletionMessageFunctionToolCall:  # type: ignore
        def __init__(self, id: str, function: Function, type: str = "function") -> None:
            self.id = id
            self.function = function
            self.type = type
    class ChatCompletionMessage:  # type: ignore
        def __init__(self, content: Any = None, role: str = "assistant", tool_calls: Any = None) -> None:
            self.content = content
            self.role = role
            self.tool_calls = tool_calls

from .conversation_history import ConversationHistory, HistoryEntry, LogEvent, LoggerCallback, RenderedMessage, StubMapping
from .tool_provider import PresentedToolResult, ToolCall, ToolResult

STUB_TEXT = "Content removed because newer version is available."


class ConversationHistoryImpl(ConversationHistory):
    """
    Maintains conversation message history and handles OpenAI schema conversions
    and in-place stubbing of superseded tool results.
    """

    def __init__(self) -> None:
        self._messages: List[HistoryEntry] = []
        self._stub_live: StubMapping = {}
        self._synthetic_call_counter = 0

    def reset(self) -> None:
        """Reset history, stub mappings, and counters to an empty state."""
        self._messages = []
        self._stub_live = {}
        self._synthetic_call_counter = 0

    def _invoke_logger(
        self,
        logger: Optional[LoggerCallback],
        event: LogEvent,
        data: Dict[str, Any],
    ) -> None:
        """Invoke the logger callback, catching and ignoring exceptions."""
        if logger is None:
            return
        try:
            logger(event, data)
        except Exception:
            pass

    @staticmethod
    def _stub_key_for(tool_call: ToolCall, arguments: Any) -> Tuple[str, str]:
        """Extract key for identifying the file or tool command for stubbing."""
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except Exception:
                arguments = None
        if isinstance(arguments, dict):
            file_path = arguments.get("file_path")
            if file_path is not None:
                return ("file", str(file_path))
        return ("tool", tool_call["function"]["name"])

    def _stub_tool_result(
        self,
        index: int,
        replacement_message: HistoryEntry,
        logger: Optional[LoggerCallback],
    ) -> None:
        """Stub an earlier tool result in place with static stub text."""
        stubbed = dict(self._messages[index])
        stubbed["content"] = STUB_TEXT
        stubbed.pop("_note", None)
        stubbed["_stubbed"] = True
        self._messages[index] = stubbed
        self._invoke_logger(
            logger,
            "message_stubbed",
            {
                "stubbed_message": stubbed,
                "replacement_message": replacement_message,
            },
        )

    def initialize(
        self,
        prompt: str,
        session_start_results: Optional[List[PresentedToolResult]] = None,
        logger: Optional[LoggerCallback] = None,
    ) -> None:
        """Initialize conversation with prompt and session-start results."""
        self.reset()
        if prompt:
            msg: HistoryEntry = {"role": "user", "content": prompt}
            self._messages.append(msg)
            self._invoke_logger(logger, "message_added", {"message": msg})

        if session_start_results:
            for result in session_start_results:
                self.add_tool_result(None, result, logger)

    def append_message(
        self,
        message: HistoryEntry,
        logger: Optional[LoggerCallback] = None,
    ) -> None:
        """Append a message entry to the conversation and notify the logger."""
        self._messages.append(message)
        self._invoke_logger(logger, "message_added", {"message": message})

    def add_tool_result(
        self,
        tool_call: Optional[ToolCall],
        result: ToolResult | PresentedToolResult,
        logger: Optional[LoggerCallback] = None,
    ) -> None:
        """Append a tool result and apply in-place stubbing if superseding."""
        if isinstance(result, PresentedToolResult):
            call_id = f"call_auto_{self._synthetic_call_counter}"
            self._synthetic_call_counter += 1
            synthetic_call: ToolCall = {
                "id": call_id,
                "type": "function",
                "function": {
                    "name": result.name,
                    "arguments": json.dumps(result.arguments),
                },
            }
            call_msg: HistoryEntry = {"role": "assistant", "tool_calls": [synthetic_call]}
            self.append_message(call_msg, logger)
            tool_call = synthetic_call
            result = result.result

        assert tool_call is not None
        tool_name = tool_call["function"]["name"]
        arguments = tool_call["function"]["arguments"]

        new_message: HistoryEntry = {
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": result.content,
            "_tool_name": tool_name,
            "_arguments": arguments,
            "_note": result.note,
        }

        if result.supersedes:
            stub_key = self._stub_key_for(tool_call, arguments)
            new_message["_stub_key"] = stub_key
            previous = self._stub_live.get(stub_key)
            if previous is not None:
                self._stub_tool_result(previous, new_message, logger)
            self._stub_live[stub_key] = len(self._messages)

        self._messages.append(new_message)
        self._invoke_logger(logger, "message_added", {"message": new_message})

    def get_history(self) -> List[HistoryEntry]:
        """Return the full conversation history list in chronological order."""
        return self._messages

    @staticmethod
    def _clean_message_for_openai(msg: HistoryEntry) -> HistoryEntry:
        """Remove internal metadata fields before sending to OpenAI."""
        return {k: v for k, v in msg.items() if not k.startswith("_")}

    def _convert_message_to_openai(
        self, msg: HistoryEntry
    ) -> Union[
        ChatCompletionUserMessageParam,
        ChatCompletionAssistantMessageParam,
        ChatCompletionToolMessageParam,
        ChatCompletionSystemMessageParam,
    ]:
        """Convert internal HistoryEntry to OpenAI message schema."""
        clean_msg = self._clean_message_for_openai(msg)
        role = clean_msg.get("role")
        if role == "user":
            return cast(ChatCompletionUserMessageParam, {"role": "user", "content": clean_msg.get("content")})
        elif role == "assistant":
            assistant_msg: ChatCompletionAssistantMessageParam = {"role": "assistant"}
            if "content" in clean_msg:
                assistant_msg["content"] = clean_msg.get("content")
            if "tool_calls" in clean_msg and clean_msg.get("tool_calls"):
                tool_calls = clean_msg.get("tool_calls")
                if tool_calls:
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": tc.get("function", {}).get("name", ""),
                                "arguments": tc.get("function", {}).get("arguments", ""),
                            },
                        }
                        for tc in tool_calls
                    ]
            return assistant_msg
        elif role == "tool":
            content = clean_msg.get("content", "")
            note = msg.get("_note", "")
            if note:
                content = content + ("\n" if content else "") + note
            return cast(ChatCompletionToolMessageParam, {
                "role": "tool",
                "tool_call_id": clean_msg.get("tool_call_id", ""),
                "content": content,
            })
        elif role == "system":
            return cast(ChatCompletionSystemMessageParam, {"role": "system", "content": clean_msg.get("content")})
        else:
            raise ValueError(f"Unknown message role: {role}")

    def get_rendered_messages(
        self,
        system_prompt: Optional[str] = None,
    ) -> List[RenderedMessage]:
        """Format and return rendered messages ready for model requests."""
        rendered: List[RenderedMessage] = []
        if system_prompt:
            rendered.append({"role": "system", "content": system_prompt})
        rendered.extend(
            self._convert_message_to_openai(msg) for msg in self._messages
        )
        return rendered

    @staticmethod
    def convert_tool_call_to_dict(tc: Any) -> ToolCall:
        """Convert an OpenAI function tool call to our ToolCall dict format."""
        tc_id = getattr(tc, "id", "") or (tc.get("id", "") if isinstance(tc, dict) else "")
        tc_type = getattr(tc, "type", "function") or (tc.get("type", "function") if isinstance(tc, dict) else "function")
        fn = getattr(tc, "function", None) or (tc.get("function") if isinstance(tc, dict) else None)
        fn_name = getattr(fn, "name", "") if fn is not None else ""
        if not fn_name and isinstance(fn, dict):
            fn_name = fn.get("name", "")
        fn_args = getattr(fn, "arguments", "") if fn is not None else ""
        if not fn_args and isinstance(fn, dict):
            fn_args = fn.get("arguments", "")
        return {
            "id": tc_id,
            "type": tc_type,
            "function": {
                "name": fn_name,
                "arguments": fn_args,
            },
        }

    @staticmethod
    def convert_openai_message_to_dict(message: Any) -> HistoryEntry:
        """Convert OpenAI message to our Message dict format."""
        msg: HistoryEntry = {"role": "assistant"}
        content = getattr(message, "content", None) if not isinstance(message, dict) else message.get("content")
        msg["content"] = content

        tool_calls = getattr(message, "tool_calls", None) if not isinstance(message, dict) else message.get("tool_calls")
        if tool_calls:
            converted = []
            for tc in tool_calls:
                converted.append(ConversationHistoryImpl.convert_tool_call_to_dict(tc))
            msg["tool_calls"] = converted
        return msg
