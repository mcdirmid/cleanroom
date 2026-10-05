# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T04:28:01Z
# LAST_CHANGED: 2026-10-05T04:26:30Z
# CHANGE: new file
# CODE_HASH: bbb5da1a8ad1
# --- END CLEANROOM METADATA ---

"""
## External Mechanics & API Documentation

The `json_ext` external component specifies JSON serialization, deserialization, and truncated payload repair mechanics using Python standard library `json` APIs and deterministic bracket-balancing state machines. External boundary specifications define no standalone library files; dependent components import standard JSON functions or the external boundary implementation directly.

**JSON Parsing & Deserialization**

- **Module**: `json`
- **Parse API**: `json.loads(text: str, strict: bool = False) -> Any`
- **Error Exceptions**:
  - `json.JSONDecodeError`: Raised when the input string is not a valid JSON document.
  - `ValueError`: General value error on malformed input.

**Deterministic JSON Serialization**

- **Dump API**: `json.dumps(obj: Any, sort_keys: bool = True) -> str`
- **Key Sorting**: `sort_keys=True` ensures deterministic key order across serialization runs.

**Truncated Response Repair & Bracket Balancing**

- **Repair API**: `repair_truncated_json(raw: str) -> str`
- **String Quote Balancing**: Tracks string quote states and unescaped double quotes, closing unclosed string literals.
- **Escape Handling**: Drops trailing backslashes that would unbalance escape sequences.
- **Delimiter Stripping**: Strips trailing commas before container closure.
- **Container Nesting**: Maintains a delimiter stack tracking open `{` and `[`, appending matching closing delimiters in reverse order.
- **Incomplete Key Fallback**: When an open object ends with an incomplete key or key-colon, appends empty string value `""` before closing containers.
- **Empty Object Fallback**: When no opening brace exists or repair cannot produce a valid dictionary, returns `{}`.

## Build Dependencies

(none)

## Usage Snippets

### `Parsing and Deterministic Serialization`

```python
import json
from typing import Any

def parse_json(text: str) -> Any:
    \"\"\"Parses a JSON string into Python objects.\"\"\"
    return json.loads(text, strict=False)

def dump_json(obj: Any, sort_keys: bool = True) -> str:
    \"\"\"Serializes Python objects into a JSON string with deterministic key order.\"\"\"
    return json.dumps(obj, sort_keys=sort_keys)
```

### `Repairing Truncated JSON Responses`

```python
import json
from typing import Optional

def repair_truncated_json(raw: str) -> str:
    \"\"\"Repairs truncated JSON strings by balancing unclosed quotes and containers.\"\"\"
    raw = raw.strip()
    if not raw:
        return "{}"
    try:
        val = json.loads(raw, strict=False)
        if isinstance(val, dict):
            return raw
    except (json.JSONDecodeError, ValueError):
        pass

    start_idx = raw.find("{")
    if start_idx == -1:
        return "{}"
    raw = raw[start_idx:]

    def try_close(cand: str) -> Optional[str]:
        in_string = False
        escape = False
        stack = []
        for ch in cand:
            if escape:
                escape = False
                continue
            if ch == "\\\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if not in_string:
                if ch in "{[":
                    stack.append("}" if ch == "{" else "]")
                elif ch in "}]":
                    if stack and stack[-1] == ch:
                        stack.pop()

        if escape:
            cand = cand[:-1]
        if in_string:
            cand += '"'

        trimmed = cand.rstrip()
        while trimmed and trimmed[-1] == ",":
            trimmed = trimmed[:-1].rstrip()

        c1 = trimmed
        for close_char in reversed(stack):
            c1 += close_char
        try:
            v = json.loads(c1, strict=False)
            if isinstance(v, dict):
                return c1
        except (json.JSONDecodeError, ValueError):
            pass

        c2 = trimmed + ': ""'
        for close_char in reversed(stack):
            c2 += close_char
        try:
            v = json.loads(c2, strict=False)
            if isinstance(v, dict):
                return c2
        except (json.JSONDecodeError, ValueError):
            pass

        return None

    res = try_close(raw)
    if res is not None:
        return res

    for i in range(len(raw) - 1, -1, -1):
        if raw[i] in (",", "{"):
            res = try_close(raw[: i + (1 if raw[i] == "{" else 0)])
            if res is not None:
                return res

    return "{}"
```
"""
