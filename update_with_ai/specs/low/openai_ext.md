<!-- Dependencies (md files to read alongside this one):
  - conversation_history.md
  - tool_provider.md
-->

# External LLS: openai_ext

## Data Types
```python
from typing import Protocol, TypeAlias, Sequence
from dataclasses import dataclass
from tool_provider import ToolMetadata
from conversation_history import HistoryMessage

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
    def create_chat_completion(self, request: CompletionRequest) -> CompletionResponse: ...
```

- `ModelName` → corresponds to *model name*: an identifier designating a target language model for completion requests.
- `PromptTokens` → corresponds to prompt token count metric.
- `CompletionTokens` → corresponds to completion token count metric.
- `CompletionRequest` → corresponds to *completion request*: an external service payload containing a *model request* and *tool metadata*.
- `CompletionResponse` → corresponds to *completion response*: an external service outcome containing generated *messages* and token usage metrics.
- `OpenAiExt` → external protocol for creating chat completions against OpenAI-compatible endpoints.
