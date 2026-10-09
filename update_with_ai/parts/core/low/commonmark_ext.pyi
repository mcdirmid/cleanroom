# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-09T21:19:01Z
# LAST_CHANGED: 2026-10-05T04:26:30Z
# CHANGE: new file
# CODE_HASH: 26aa7cc69588
# LOW_QA_AUDIT: 2026-10-09T21:19:01Z
# --- END CLEANROOM METADATA ---

r"""
## External Mechanics & API Documentation

The `commonmark_ext` external component specifies CommonMark and GitHub Flavored Markdown token conventions and regular expression patterns for HTML comment directives and parameter placeholders. External boundary specifications define no standalone library files; template formatters and readers import standard regular expression mechanisms directly.

**HTML Comment Block & Inline Directives**

- **Comment Open**: `<!--`
- **Comment Close**: `-->`
- **Block Directives**: Standalone comment blocks matching CommonMark block type 2 HTML comments.
- **Line-Suffix Directives**: Comments placed at the trailing end of table rows or list item lines without disrupting row alignment or indentation.

**Token Placeholders & Identifier Paths**

- **Parameter Placeholder Syntax**: `<parameter.path>` enclosed in angle brackets with dot-separated identifier keys.
- **Matching Rules**: Angle brackets enclosing valid identifier paths are distinguished from HTML tags.

**Regular Expression Patterns**

- **Block Conditionals**: Pattern matching `<!-- IF <cond> -->` and `<!-- ENDIF -->`.
- **Line Conditionals**: Pattern matching trailing `<!-- IF <cond> -->` on single lines.
- **Block Loops**: Pattern matching `<!-- FOR <item> IN <list> -->` and `<!-- ENDFOR -->`.
- **Line Loops**: Pattern matching trailing `<!-- FOR <item> IN <list> -->`.
- **Parameter Substitutions**: Pattern matching `<[a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)*>`.

## Build Dependencies

(none)

## Usage Snippets

### `Matching Directives and Placeholders`

```python
import re

PLACEHOLDER_PATTERN = re.compile(r"<([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)*)>")
BLOCK_IF_START = re.compile(r"<!--\s*IF\s+([^\s]+)\s*-->")
BLOCK_IF_END = re.compile(r"<!--\s*ENDIF\s*-->")

def find_placeholders(text: str) -> list[str]:
    return PLACEHOLDER_PATTERN.findall(text)
```
"""
