<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
  - file_reader.md
  - virtual_file_name.md
-->

# Interface LLS: file_editor

## Data Types
```python
from typing import Protocol, TypeAlias, Sequence, Mapping
from dataclasses import dataclass
from tool_provider import Tool, ToolProvider, ToolFailure
from file_reader import ReadWriteFile
from virtual_file_name import VirtualFileMapping

FileTemplate: TypeAlias = str
TemplateMapping: TypeAlias = Mapping[ReadWriteFile, FileTemplate]

@dataclass(frozen=True)
class FileEditorConfig:
    read_write_files: Sequence[ReadWriteFile]
    file_mappings: VirtualFileMapping
    templates: TemplateMapping

class FileEditor(ToolProvider, Protocol):
    def get_replacement_tool(self) -> Tool: ...
    def get_line_update_tool(self) -> Tool: ...
    def materialize_templates(self) -> None: ...

class FileEditorFactory(Protocol):
    def create_file_editor(self, config: FileEditorConfig) -> FileEditor: ...
```

- `FileTemplate` → corresponds to *template*: initial content for a *read-write file*.
- `TemplateMapping` → corresponds to template mappings.
- `FileEditorConfig` → corresponds to file editor configuration.
- `FileEditor` → corresponds to *file editor*: a *tool provider* providing a *text replacement tool* and a *line update tool*.
- `FileEditorFactory` → corresponds to *file editor factory*: a provider that constructs *file editors* configured for specific sessions.

## Term definitions

- **template** → the `FileTemplate` alias
- **text replacement tool** → term definition: a *tool* (returned by `get_replacement_tool`) that replaces matching text within a *read-write file*
- **line update tool** → term definition: a *tool* (returned by `get_line_update_tool`) that replaces a range of lines within a *read-write file*
- **file editor** → term definition: a *tool provider* providing a *text replacement tool* and a *line update tool*
- **file editor factory** → term definition: a provider that constructs *file editors* configured for specific sessions

## Component-Provided Operations

### `get_replacement_tool`

```python
def get_replacement_tool(self) -> Tool: ...
```

**Purpose:** (FileEditor) Retrieves the text replacement tool instance.

**Preconditions:** None.

**Postconditions:**
- Returns a `Tool` that replaces exact matching text in a target `ReadWriteFile`.

**Failure Handling:** Unmapped or non-writable `VirtualFileName`, ambiguous (multiple matches), or absent target text produces a `ToolFailure`.

**HLS Justification:** "Executing a *file editor* tool with an unmapped or non-writable *virtual file name* produces a *tool failure*."

### `get_line_update_tool`

```python
def get_line_update_tool(self) -> Tool: ...
```

**Purpose:** (FileEditor) Retrieves the line range update tool instance.

**Preconditions:** None.

**Postconditions:**
- Returns a `Tool` that replaces a bounded line range in a target `ReadWriteFile`.

**Failure Handling:** Unmapped or non-writable `VirtualFileName`, or out-of-bounds line numbers produce a `ToolFailure`.

**HLS Justification:** "Executing a *file editor* tool with an unmapped or non-writable *virtual file name* produces a *tool failure*."

### `materialize_templates`

```python
def materialize_templates(self) -> None: ...
```

**Purpose:** (FileEditor) Materializes initial template content into missing read-write files at session start.

**Preconditions:** None.

**Postconditions:**
- Writes configured template content to missing target files without overwriting existing files.

**Failure Handling:** Missing files are populated; existing files are preserved.

**HLS Justification:** "A *file editor* materializes *templates* into missing *read-write files* without overwriting existing files."

### `create_file_editor`

```python
def create_file_editor(self, config: FileEditorConfig) -> FileEditor: ...
```

**Purpose:** (FileEditorFactory) Creates a file editor instance configured with writable files and templates.

**Preconditions:** None.

**Postconditions:**
- Returns a `FileEditor` configured with `config`.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Creating a *file editor* through a *file editor factory* yields a *file editor* configured with *read-write files*, path mappings, and *templates*."

## Invariants

- Existing files are never overwritten during template materialization.
- Replaced text matches exact character sequences within target files.
