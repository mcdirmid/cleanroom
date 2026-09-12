'''
# External Specification: commonmark_ext

## External Mechanics & API Documentation

The `commonmark_ext` external component specifies the CommonMark and GitHub Flavored Markdown (GFM) document format, HTML comment directive tokens, and parameter placeholder patterns. External boundary specifications define no standalone library files; dependent implementation components (specifically `template_format_impl`) import and reference standard regex modules and CommonMark formatting rules directly.

**CommonMark HTML Comment Blocks and Raw Inlines**

CommonMark (v0.31.2) specifies two mechanisms for non-rendered HTML comments:
1. **HTML Block (Type 2)**:
   - Starts with `<!--` and ends with `-->`.
   - Used for block-level directives (block `if` and block `for`):
     - Block `if` start: `<!-- if: <identifier> -->`
     - Block `if` end: `<!-- endif -->`
     - Block `for` start: `<!-- for: <item_var> in <collection_path> -->`
     - Block `for` end: `<!-- endfor -->`
   - Preserved verbatim by formatters (e.g., Prettier, mdformat, markdownlint) on separate lines.
2. **Raw HTML Inlines**:
   - Inline comments `<!-- ... -->` within a Markdown paragraph, list item, or table cell.
   - Used for line-suffix directives:
     - Line conditional: `<content> <!-- if: <identifier> -->`
     - Line loop: `<content> <!-- for: <item_var> in <collection_path> -->`
   - Preserved by formatters at the end of lines or inside table cells without inserting empty paragraphs or breaking pipe table delimiters.

**Parameter Placeholder Syntax**

- Parameter tokens use angle-bracket notation: `<identifier>` or `<record.field>` (e.g. `<name>`, `<op.summary>`).
- Regex pattern: `<([a-zA-Z_][a-zA-Z0-9_]*(?:\\.[a-zA-Z_][a-zA-Z0-9_]*)*)>`.
- When a parameter key is found in the evaluation context, the token is substituted with its string representation.
- When a parameter key is absent, the token is preserved verbatim as `<identifier>`, ensuring that unrendered and partially-bound templates remain readable.

**Whitespace Normalization**

Formatters often insert blank lines around block HTML elements (`<!-- ... -->`). When evaluating block directives into tight lists, extraneous blank lines adjacent to directive markers are normalized to preserve list compactness.

## Build Dependencies

(none)

## Usage Snippets

### `Matching and Substituting CommonMark Directives`

```python
import re
from typing import Any, Mapping, Tuple

VAR_RE = re.compile(r"<([a-zA-Z_][a-zA-Z0-9_]*(?:\\.[a-zA-Z_][a-zA-Z0-9_]*)*)>")
LINE_IF_RE = re.compile(r"^(.*?)\\s*<!--\\s*if:\\s*(\\w+)\\s*-->\\s*$")
LINE_FOR_RE = re.compile(r"^(.*?)\\s*<!--\\s*for:\\s*(\\w+)\\s+in\\s+([a-zA-Z0-9_.]+)\\s*-->\\s*$")
BLOCK_IF_START = re.compile(r"^\\s*<!--\\s*if:\\s*(\\w+)\\s*-->\\s*$")
BLOCK_IF_END = re.compile(r"^\\s*<!--\\s*endif\\s*-->\\s*$")
BLOCK_FOR_START = re.compile(r"^\\s*<!--\\s*for:\\s*(\\w+)\\s+in\\s+([a-zA-Z0-9_.]+)\\s*-->\\s*$")
BLOCK_FOR_END = re.compile(r"^\\s*<!--\\s*endfor\\s*-->\\s*$")

def resolve_field(path: str, context: Mapping[str, Any]) -> Tuple[bool, Any]:
    parts = path.split(".")
    val: Any = context
    for p in parts:
        if isinstance(val, (dict, Mapping)) and p in val:
            val = val[p]
        else:
            return False, None
    return True, val

def substitute_parameters(text: str, context: Mapping[str, Any]) -> str:
    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        found, val = resolve_field(key, context)
        return str(val) if found else m.group(0)
    return VAR_RE.sub(repl, text)
```
'''
