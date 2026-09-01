"""OpenAI external completion types and client implementation."""

import os
import json
import urllib.request
import urllib.error
from typing import Protocol, TypeAlias, Sequence, Mapping, Any, Optional
from dataclasses import dataclass
from .conversation_history import HistoryMessage
from .tool_provider import ToolMetadata

ModelName: TypeAlias = str
PromptTokens: TypeAlias = int
CompletionTokens: TypeAlias = int


@dataclass(frozen=True)
class CompletionRequest:
    messages: Sequence[HistoryMessage]
    model: ModelName
    tools: Sequence[ToolMetadata] = ()


@dataclass(frozen=True)
class CompletionResponse:
    message: HistoryMessage
    prompt_tokens: PromptTokens
    completion_tokens: CompletionTokens


class OpenAiExt(Protocol):
    def create_chat_completion(self, request: CompletionRequest) -> CompletionResponse:
        ...


class OpenAiExtImpl(OpenAiExt):
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: int = 60,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def create_chat_completion(self, request: CompletionRequest) -> CompletionResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        openai_messages = []
        for msg in request.messages:
            entry: dict[str, Any] = {
                "role": msg.role,
                "content": str(msg.content) if msg.content is not None else "",
            }
            if msg.metadata and "tool_call_id" in msg.metadata:
                entry["tool_call_id"] = msg.metadata["tool_call_id"]
            if msg.metadata and "tool_calls" in msg.metadata:
                entry["tool_calls"] = msg.metadata["tool_calls"]
            openai_messages.append(entry)

        payload: dict[str, Any] = {
            "model": request.model,
            "messages": openai_messages,
        }

        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.purpose,
                        "parameters": t.parameters_schema,
                    },
                }
                for t in request.tools
            ]
            payload["tool_choice"] = "auto"

        req_data = json.dumps(payload).encode("utf-8")
        http_req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(http_req, timeout=self.timeout_seconds) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API call failed ({e.code}): {err_body}") from e
        except Exception as e:
            raise RuntimeError(f"OpenAI API call failed: {e}") from e

        choices = resp_data.get("choices", [])
        if not choices:
            raise RuntimeError("OpenAI API returned no choices")

        choice = choices[0]
        choice_msg = choice.get("message", {})
        role = choice_msg.get("role", "assistant")
        content = choice_msg.get("content")
        tool_calls = choice_msg.get("tool_calls")

        metadata: dict[str, Any] = {}
        if tool_calls:
            metadata["tool_calls"] = tool_calls

        usage = resp_data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        return CompletionResponse(
            message=HistoryMessage(role=role, content=content, metadata=metadata if metadata else None),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
