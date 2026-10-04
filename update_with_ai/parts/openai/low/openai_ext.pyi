"""
## External Mechanics & API Documentation

The `openai_ext` external component specifies the HTTP REST wire protocol for OpenAI-compatible `/v1/chat/completions` endpoints.

**Request Schema & Headers**

- **Endpoint**: `POST {base_url}/v1/chat/completions`
- **Headers**:
  - `Authorization: Bearer {api_key}`
  - `Content-Type: application/json`
- **JSON Payload Fields**:
  - `model`: Model name string.
  - `messages`: List of message objects with `role` (`system`, `user`, `assistant`, `tool`), `content`, and optional `tool_calls` or `tool_call_id`.
  - `tools`: List of function tool schemas with name, description, and JSON schema parameters.
  - `temperature`: Float sampling temperature.
  - `max_tokens`: Optional maximum tokens integer.

**Response Schema**

- **HTTP Status 200 OK**: JSON response with `id`, `choices` array containing message and `finish_reason` (`stop`, `tool_calls`, `length`), and `usage` statistics (`prompt_tokens`, `completion_tokens`, `total_tokens`).
- **Error Codes**:
  - `401 Unauthorized`: Bad API key or credentials.
  - `429 Too Many Requests`: Rate limit or quota exhaustion.
  - `500/502/503/504 Server Error`: Upstream endpoint error.

## Build Dependencies

- `urllib.request` or `httpx`

## Usage Snippets

### `Invoking OpenAI Chat Completions`

```python
import json
import urllib.request
from typing import Any, Mapping

def call_chat_completion(
    base_url: str,
    api_key: str,
    payload: Mapping[str, Any],
    timeout: float = 60.0,
) -> Mapping[str, Any]:
    \"\"\"Sends chat completion request over HTTPS.\"\"\"
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))
```
"""
