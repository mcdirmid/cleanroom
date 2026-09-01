<!-- Dependencies (md files to read alongside this one):
  - tool_provider.md
  - virtual_file_name.md
  - file_reader.md
  - file_editor.md
  - guide_delivery.md
  - run_control.md
-->

# Interface LLS: sandbox

## Data Types
```python
from typing import Protocol, TypeAlias, Sequence, Mapping, Optional
from dataclasses import dataclass
from tool_provider import ToolProvider, ToolResult
from virtual_file_name import VirtualFileMapping
from file_reader import ReadOnlyFile, ReadWriteFile, SessionStartRead
from file_editor import FileTemplate
from guide_delivery import TaskGuide
from run_control import RunControlConfig

StartupInteraction: TypeAlias = Sequence[ToolResult]

@dataclass(frozen=True)
class SandboxConfig:
    file_mappings: VirtualFileMapping
    read_only_files: Sequence[ReadOnlyFile]
    read_write_files: Sequence[ReadWriteFile]
    templates: Mapping[ReadWriteFile, FileTemplate]
    guide: Optional[TaskGuide] = None
    step_mode_guide_name: Optional[str] = None
    run_control: Optional[RunControlConfig] = None
    search_result_limit: Optional[int] = None

class SandboxFactory(Protocol):
    def create_sandbox(self, config: SandboxConfig) -> "Sandbox": ...

class Sandbox(ToolProvider, Protocol):
    def get_session_start_reads(self) -> Sequence[SessionStartRead]: ...
    def get_startup_interaction(self) -> StartupInteraction: ...
    def materialize_startup_templates(self) -> None: ...
    def has_file_modifications(self) -> bool: ...
```

- `StartupInteraction` → corresponds to *startup interaction*: a collection of initial tool results (carrying *session-start reads* and an optional initial *step delivery*) provided at session start.
- `SandboxConfig` → corresponds to *sandbox configuration*: a set of parameters configuring file mappings, permissions, templates, search bounds, *guides*, verification checks, and blame targets for a *sandbox*.
- `SandboxFactory` → corresponds to *sandbox factory*: a provider that constructs *sandboxes* configured from *sandbox configurations*.
- `Sandbox` → corresponds to *sandbox*: a *tool provider* composing tools from a *file reader*, a *file editor*, a *run controller*, and an optional *guide delivery*.

## Term definitions

- **sandbox configuration** → the `SandboxConfig` alias
- **startup interaction** → the `StartupInteraction` alias
- **sandbox** → term definition: a *tool provider* composing tools from a *file reader*, a *file editor*, a *run controller*, and an optional *guide delivery*
- **sandbox factory** → term definition: a provider that constructs *sandboxes* configured from *sandbox configurations*

## Component-Provided Operations

### `get_session_start_reads`

```python
def get_session_start_reads(self) -> Sequence[SessionStartRead]: ...
```

**Purpose:** (Sandbox) Retrieves pre-injected session-start reads for declared read-only files.

**Preconditions:** None.

**Postconditions:**
- Returns plain-content reads for all declared `ReadOnlyFile` targets.

**Failure Handling:** Always succeeds.

**HLS Justification:** "A *sandbox* provides *session-start reads* for declared *read-only files* at run start."

### `get_startup_interaction`

```python
def get_startup_interaction(self) -> StartupInteraction: ...
```

**Purpose:** (Sandbox) Retrieves initial tool results combining session-start reads and an optional initial step delivery.

**Preconditions:** None.

**Postconditions:**
- Returns session-start reads for declared read-only files followed by an initial step delivery when progressive guide delivery is active.

**Failure Handling:** Always succeeds.

**HLS Justification:** "A *sandbox* produces a *startup interaction* carrying *session-start reads* for all declared *read-only files*, along with an initial *step delivery* when progressive guide delivery is configured."

### `materialize_startup_templates`

```python
def materialize_startup_templates(self) -> None: ...
```

**Purpose:** (Sandbox) Populates missing read-write files with starter templates at startup.

**Preconditions:** None.

**Postconditions:**
- Writes starter templates to missing files without overwriting existing files.

**Failure Handling:** Unhandled filesystem exceptions.

**HLS Justification:** "A *sandbox* materializes *templates* for missing *read-write files* at startup without overwriting existing files."

### `has_file_modifications`

```python
def has_file_modifications(self) -> bool: ...
```

**Purpose:** (Sandbox) Queries whether any workspace file modifications occurred during the session.

**Preconditions:** None.

**Postconditions:**
- Returns `True` if files were modified relative to startup baseline; `False` otherwise.

**Failure Handling:** Always succeeds.

**HLS Justification:** "A *sandbox* allows querying whether any workspace file modifications occurred during the run."

### `create_sandbox`

```python
def create_sandbox(self, config: SandboxConfig) -> Sandbox: ...
```

**Purpose:** (SandboxFactory) Creates an isolated sandbox instance configured from a sandbox configuration.

**Preconditions:** None.

**Postconditions:**
- Returns a `Sandbox` configured from `config` using sub-component factories.

**Failure Handling:** Always succeeds.

**HLS Justification:** "Creating a *sandbox* through a *sandbox factory* yields a *sandbox* configured from a *sandbox configuration*."

## Invariants

- Composed tools are exposed exclusively through virtual file name abstractions.
- Advance operations coordinate progressive guide delivery before final termination verification.
- Materializing templates never overwrites existing read-write files.
