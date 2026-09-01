<!-- Dependencies (md files to read alongside this one):
-->

# External LLS: json_manifest_ext

## Data Types
```python
from typing import Sequence, Optional, TypeAlias
from dataclasses import dataclass

ManifestNodeReference: TypeAlias = str
ManifestFilePath: TypeAlias = str
ManifestDirectoryPath: TypeAlias = str
ManifestRawContent: TypeAlias = str
TaskPromptText: TypeAlias = str
VerificationCommand: TypeAlias = str

@dataclass(frozen=True)
class DependencyPathEntry:
    label: ManifestNodeReference
    path: ManifestFilePath

@dataclass(frozen=True)
class JsonManifest:
    label: ManifestNodeReference
    name: str
    prompt: TaskPromptText = ""
    tools: Sequence[str] = ()
    deps: Sequence[ManifestNodeReference] = ()
    silent_deps: Sequence[ManifestNodeReference] = ()
    feedback_deps: Sequence[ManifestNodeReference] = ()
    star_deps: Sequence[ManifestNodeReference] = ()
    src: Optional[ManifestFilePath] = None
    template: Optional[ManifestFilePath] = None
    guide: Optional[ManifestNodeReference] = None
    silent_srcs: Sequence[ManifestFilePath] = ()
    verify: Optional[VerificationCommand] = None
    dependency_paths: Sequence[DependencyPathEntry] = ()

def parse_json_manifest(content: ManifestRawContent) -> JsonManifest: ...
def load_json_manifest(file_path: ManifestFilePath) -> JsonManifest: ...
def locate_manifest_file(manifest_name: ManifestFilePath, search_directories: Sequence[ManifestDirectoryPath]) -> Optional[ManifestFilePath]: ...
```

- `ManifestNodeReference` → corresponds to *manifest node reference*: an external target identifier string representing a workspace target (such as a target label, dependency target, guide target, feedback target, or config target).
- `ManifestFilePath` → corresponds to *manifest file path*: an external filesystem path string relative to a target package directory or workspace root (such as a declared source file, template, or silent source file).
- `ManifestDirectoryPath` → corresponds to a filesystem directory path searched during manifest file discovery (such as base directories in `RUNFILES_DIR`, `BAZEL_RUNFILES`, or the script execution directory).
- `ManifestRawContent` → corresponds to raw JSON string content of a manifest file.
- `TaskPromptText` → corresponds to the prompt instruction text for the node.
- `VerificationCommand` → corresponds to the shell verification command for the node.
- `DependencyPathEntry` → structured record mapping a dependency label to its relative path.
- `JsonManifest` → corresponds to *json manifest*: an external JSON record written by the build system into `<name>_manifest.json` describing a target's configuration, sources, dependencies, guide, template, and verification command.
- `parse_json_manifest` → parses raw JSON manifest string content into a `JsonManifest` record.
- `load_json_manifest` → reads and parses a manifest file from a filesystem path into a `JsonManifest` record.
- `locate_manifest_file` → resolves a candidate manifest filename against search directories (such as runfiles bases or fallback directory), returning the first existing path.
