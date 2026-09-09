'''
# External Specification: json_manifest_ext

## External Mechanics & API Documentation

The `json_manifest_ext` external component specifies build target manifest JSON schema deserialization and extraction using the Python standard library. External boundary specifications define no standalone library files; dependent implementation components (specifically `bazel_manifest_loader_impl`) import and invoke Python's standard `json` library directly.

**Target Manifest JSON Document Schema**

Build manifests emitted by Cleanroom build rules provide JSON dictionary structures:
- `target: str` (required): Canonical Bazel target label string (`"//pkg:target_name"`).
- `dependencies: List[str]` (optional): Prerequisite upstream target labels.
- `silent_dependencies: List[str]` (optional): Dependencies whose modifications do not invalidate this target.
- `star_dependencies: List[str]` (optional): Star dependencies expanded during graph construction.
- `feedback_dependencies: List[str]` (optional): Downstream targets allowed to send diagnostic feedback.
- `guide: Optional[str]` (optional): Optional target label providing task guidance.
- `config: Optional[str]` (optional): Optional target label providing node configuration.
- `primary_sources: List[str]` (optional): Read-write package source file paths.
- `templates: Mapping[str, str]` (optional): Mapping from destination source path to initial template content file path.
- `silent_sources: List[str]` (optional): Read-only package source file paths.
- `task_prompt: str` (optional): Natural-language prompt instructions for the agent run.
- `verification_commands: List[str]` (optional): Shell verification command strings.

**JSON Text Deserialization & Structural Validation**

- **Module**: `json` (Python standard library).
- **Deserialization API**: `json.loads(text: str) -> Any`.
- **Validation**:
  - Verifies that root JSON value is a `dict`.
  - Confirms `"target"` key is present and non-empty.
  - Supplies default empty collections (`[]`, `{}`) for optional list and mapping fields.
- **Error Exceptions**:
  - `json.JSONDecodeError`: Raised on malformed JSON text, syntax errors, or unclosed delimiters.

## Build Dependencies

The `json_manifest_ext` component relies exclusively on the Python standard library (`json`).

The consuming implementation component `bazel_manifest_loader_impl` requires no external pip dependencies in `update_with_ai/lib/BUILD.bazel`:
```python
py_library(
    name = "bazel_manifest_loader_impl",
    srcs = ["bazel_manifest_loader_impl.py"],
    deps = [
        ":bazel_manifest_loader",
        ":bazel_graph_storage",
        ":file_alias",
    ],
)
```

## Usage Snippets

### `Deserializing Target Manifest JSON`

```python
import json
from pathlib import Path
from typing import Any, Mapping, Tuple

def parse_target_manifest_file(manifest_path: str) -> Tuple[bool, Mapping[str, Any]]:
    """Loads and deserializes a build target manifest JSON file with structural defaults."""
    p = Path(manifest_path)
    if not p.is_file():
        return False, {"error": f"Manifest file does not exist: {manifest_path}"}
        
    try:
        raw_data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw_data, dict):
            return False, {"error": f"Manifest JSON must be an object: {manifest_path}"}
        if "target" not in raw_data or not isinstance(raw_data["target"], str):
            return False, {"error": f"Manifest missing valid 'target' field: {manifest_path}"}
            
        manifest = {
            "target": raw_data["target"],
            "dependencies": raw_data.get("dependencies", []),
            "silent_dependencies": raw_data.get("silent_dependencies", []),
            "star_dependencies": raw_data.get("star_dependencies", []),
            "feedback_dependencies": raw_data.get("feedback_dependencies", []),
            "guide": raw_data.get("guide"),
            "config": raw_data.get("config"),
            "primary_sources": raw_data.get("primary_sources", []),
            "templates": raw_data.get("templates", {}),
            "silent_sources": raw_data.get("silent_sources", []),
            "task_prompt": raw_data.get("task_prompt", ""),
            "verification_commands": raw_data.get("verification_commands", []),
        }
        return True, manifest
    except (json.JSONDecodeError, OSError) as exc:
        return False, {"error": f"Failed to parse manifest JSON {manifest_path}: {exc}"}
```
'''
