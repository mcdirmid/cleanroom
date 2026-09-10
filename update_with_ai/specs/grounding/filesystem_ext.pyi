'''
# External Specification: filesystem_ext

## External Mechanics & API Documentation

The `filesystem_ext` external component specifies host operating system storage access and pattern scanning mechanics using Python standard library APIs. External boundary specifications define no standalone library files; dependent implementation components (specifically `sandbox_file_reader_impl` and `sandbox_file_editor_impl`) import and invoke standard library filesystem modules directly.

**Host Path Reading & UTF-8 Text Decoding**

- **Module**: `pathlib.Path` and `os.path`.
- **Text Read API**: `Path.read_text(encoding="utf-8")`.
- **Pre-check Operations**:
  - `path.exists() -> bool`: Verifies entity presence on disk.
  - `path.is_file() -> bool`: Distinguishes regular readable files from directories or special device nodes.
- **Error Exceptions**:
  - `FileNotFoundError`: Raised when the physical target path does not exist.
  - `IsADirectoryError`: Raised when target path addresses a directory instead of a regular file.
  - `PermissionError`: Raised when file read permissions are denied by the host operating system.
  - `UnicodeDecodeError`: Raised when file content cannot be decoded as valid UTF-8.

**Host Path Writing & Automatic Directory Creation**

- **Text Write API**: `Path.write_text(content, encoding="utf-8")`.
- **Parent Hierarchy Creation**:
  - `path.parent.mkdir(parents=True, exist_ok=True)`: Creates all missing ancestor directories prior to writing without raising an exception if ancestors already exist.
- **Atomic File Updates**: Direct text writing replaces existing file content completely.

**Directory Traversal & Regex Pattern Scanning**

- **Traversal APIs**:
  - `os.walk(top_dir)`: Generates filenames across directory trees recursively.
  - `Path.rglob(pattern)`: Yields relative path matches across directory subtrees.
- **Pattern Compilation**:
  - `re.compile(pattern: str) -> re.Pattern`: Compiles search regex string, raising `re.error` on invalid syntax.
- **Line Matching**:
  - `pattern.search(line: str)`: Scans line strings with 1-indexed numbering via `enumerate(lines, start=1)`.

## Build Dependencies

(none)

## Usage Snippets

### `Reading and Writing Files with Automatic Parent Directory Creation`

```python
from pathlib import Path
from typing import Optional, Tuple

def read_text_file(host_path: str) -> Tuple[bool, str]:
    """Reads UTF-8 text from host path, mapping OS errors to structured results."""
    p = Path(host_path)
    if not p.is_file():
        return False, f"Target is not a regular file: {host_path}"
    try:
        content = p.read_text(encoding="utf-8")
        return True, content
    except (FileNotFoundError, PermissionError, UnicodeDecodeError, OSError) as exc:
        return False, f"Failed to read {host_path}: {exc}"

def write_text_file(host_path: str, content: str) -> Tuple[bool, Optional[str]]:
    """Writes UTF-8 text, creating missing parent directories automatically."""
    p = Path(host_path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return True, None
    except (PermissionError, OSError) as exc:
        return False, f"Failed to write {host_path}: {exc}"
```

### `Regex Line Matching Across Directory Trees`

```python
import os
import re
from pathlib import Path
from typing import Any, List, Mapping

def search_directory_pattern(
    dir_path: str,
    pattern_str: str,
    max_results: int = 50,
) -> Mapping[str, Any]:
    """Searches regular expression pattern across directory files with line numbering."""
    try:
        regex = re.compile(pattern_str)
    except re.error as exc:
        return {"status": "error", "error": f"Invalid regular expression: {exc}"}
        
    results: List[Mapping[str, Any]] = []
    root = Path(dir_path)
    
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            file_path = Path(dirpath) / fname
            try:
                text = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError, OSError):
                continue
                
            for line_no, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    results.append({
                        "path": str(file_path.relative_to(root)),
                        "line": line_no,
                        "content": line,
                    })
                    if len(results) >= max_results:
                        return {"status": "success", "results": results, "truncated": True}
                        
    return {"status": "success", "results": results, "truncated": False}
```
'''
