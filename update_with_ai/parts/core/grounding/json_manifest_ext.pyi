'''
# External Specification: json_manifest_ext

## External Mechanics & API Documentation

The `json_manifest_ext` external component specifies build target manifest JSON schema deserialization and extraction using the Python standard library. External boundary specifications define no standalone library files; dependent implementation components (specifically `bazel_manifest_loader_impl`) import and invoke Python's standard `json` library directly. The manifest schema is defined and emitted by the Starlark build rule `update_with_ai` in `update_with_ai/support/lib/update_with_ai.bzl`.

**Target Manifest JSON Document Schema**

Build manifests emitted by Cleanroom build rules provide JSON dictionary structures:
- `label: str` (required): Canonical or apparent Bazel target label string (`"//pkg:target_name"`).
- `name: str` (required): Target name string (`"target_name"`).
- `prompt: str` (optional): Natural-language prompt instructions for the agent run.
- `tools: List[str]` (optional): Tool target label strings.
- `deps: List[str]` (optional): Prerequisite upstream target labels (including resolved star deps, feedback deps, and guide).
- `silent_deps: List[str]` (optional): Dependencies whose modifications do not invalidate this target and whose outputs are not readable.
- `feedback_deps: List[str]` (optional): Downstream targets allowed to send diagnostic feedback.
- `star_deps: List[str]` (optional): Dependencies whose transitive closure over star deps is readable.
- `src: str` (optional): The node's declared primary writable source file path (readable by deps).
- `template: Optional[str]` (optional): Repo-relative template file path initializing `src` if absent.
- `template_parameters: Optional[Mapping[str, Any]]` (optional): Dictionary of parameter bindings for template evaluation (default: `{}`).
- `guide: Optional[str]` (optional): Optional target label providing task guidance.
- `allows_step_mode: bool` (optional): Indicates whether the node permits guide step mode (default: True).
- `silent_srcs: List[str]` (optional): Paths the agent can write that are not readable by deps.
- `verify: Optional[str]` (optional): Shell command string executed on verification.
- `dependency_paths: List[Mapping[str, str]]` (optional): List of mappings from dependency target label to file path.

**JSON Text Deserialization & Structural Validation**

- **Module**: `json` (Python standard library).
- **Deserialization API**: `json.loads(text: str) -> Any`.
- **Validation**:
  - Verifies that root JSON value is a `dict`.
  - Confirms `"label"` key is present and non-empty.
  - Supplies default empty collections (`[]`) and `None` for optional fields.
- **Error Exceptions**:
  - `json.JSONDecodeError`: Raised on malformed JSON text, syntax errors, or unclosed delimiters.

## Build Dependencies

(none)

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
        if "label" not in raw_data or not isinstance(raw_data["label"], str) or not raw_data["label"].strip():
            return False, {"error": f"Manifest missing valid 'label' field: {manifest_path}"}
            
        manifest = {
            "label": raw_data["label"].strip(),
            "name": raw_data.get("name", ""),
            "prompt": raw_data.get("prompt", ""),
            "tools": raw_data.get("tools", []),
            "deps": raw_data.get("deps", []),
            "silent_deps": raw_data.get("silent_deps", []),
            "feedback_deps": raw_data.get("feedback_deps", []),
            "star_deps": raw_data.get("star_deps", []),
            "src": raw_data.get("src", ""),
            "template": raw_data.get("template"),
            "template_parameters": raw_data.get("template_parameters", {}),
            "guide": raw_data.get("guide"),
            "allows_step_mode": raw_data.get("allows_step_mode", True),
            "silent_srcs": raw_data.get("silent_srcs", []),
            "verify": raw_data.get("verify"),
            "dependency_paths": raw_data.get("dependency_paths", []),
        }
        return True, manifest
    except (json.JSONDecodeError, OSError) as exc:
        return False, {"error": f"Failed to parse manifest JSON {manifest_path}: {exc}"}
```
'''
