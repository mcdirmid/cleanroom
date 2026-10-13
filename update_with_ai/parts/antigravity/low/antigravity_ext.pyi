# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-13T01:05:05Z
# LAST_CHANGED: 2026-10-12T21:45:00Z
# CHANGE: author antigravity_ext external low-level specification
# CODE_HASH: 42d29709579c
# --- END CLEANROOM METADATA ---

"""
## External Mechanics & API Documentation

The `antigravity_ext` external component specifies Google Antigravity IDE and CLI customization schemas, subagent tool contracts, and execution transcript formats.

**Antigravity Skill Document Structure**

- Skill files are placed at `.agents/skills/<skill_name>/SKILL.md` (project-local) or within `~/.gemini/config/plugins/<plugin_name>/skills/<skill_name>/SKILL.md` (global plugin).
- YAML Frontmatter contains:
  - `name`: Lowercase identifier of the skill.
  - `description`: High-level summary of when the agent should trigger or mount the skill.
- Markdown Body contains:
  - Procedural instructions, invariants, and guidelines formatted in GitHub Flavored Markdown.

**Workspace Isolation Rules Structure**

- Boundary rule files are placed at `.agents/rules/<rule_name>.md` inside role workspaces.
- Instructs the agent to never read, navigate, or edit files outside the role workspace root.
- Recommends using workspace-local `bin/get_work`, `bin/submit`, `bin/blame`, and `bin/fail`.

**Subagent Invocation Tool Schema (`invoke_subagent`)**

- Tool Name: `invoke_subagent`
- Parameter Schema:
  - `TypeName`: String identifier of the agent template.
  - `Role`: String identifier of the role persona.
  - `Prompt`: String task prompt detailing instructions for the subagent turn.
  - `Workspace`: String path to the target workspace directory. Setting `Workspace: inherit` is strictly prohibited.
  - `Model`: Optional model tier string ("flash", "pro", "inherit").

**Transcript Event Log Schema (`transcript.jsonl`)**

- File Path: `<appDataDir>/brain/<conversation_id>/.system_generated/logs/transcript.jsonl`
- JSONL Step Record Fields:
  - `step_index`: Integer step counter.
  - `source`: String actor identifier (`USER_EXPLICIT`, `MODEL`, `SYSTEM`).
  - `type`: String step kind (`USER_INPUT`, `PLANNER_RESPONSE`, `TOOL_CALL`, `TOOL_RESULT`).
  - `status`: String outcome status (`DONE`, `ERROR`).
  - `tool_calls`: List of tool call objects with name and parameters.
  - `usage` or `metadata`: Object reporting token metrics:
    - `input_tokens`: Uncached prompt tokens.
    - `cached_tokens`: Cached prompt tokens.
    - `output_tokens`: Completion tokens.

## Build Dependencies

- None

## Usage Snippets

### `Reading Antigravity Transcript Telemetry`

```python
import json
from typing import Dict, Any

def parse_transcript_line(line: str) -> Dict[str, Any]:
    \"\"\"Parses a single JSONL line from an Antigravity transcript log.\"\"\"
    data = json.loads(line)
    return {
        "step_index": data.get("step_index", 0),
        "type": data.get("type", ""),
        "input_tokens": data.get("usage", {}).get("input_tokens", 0),
        "cached_tokens": data.get("usage", {}).get("cached_tokens", 0),
        "output_tokens": data.get("usage", {}).get("output_tokens", 0),
    }
```
"""
