"""External JSON build target manifest schema and helpers."""

from typing import Sequence, Optional, TypeAlias, Mapping, Any, Dict
from dataclasses import dataclass
import json
import os

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


def parse_json_manifest(content: ManifestRawContent) -> JsonManifest:
    data = json.loads(content)
    # If the JSON contains a legacy or batch "targets" wrapper, use the first target entry
    if "targets" in data and isinstance(data["targets"], list) and data["targets"]:
        data = data["targets"][0]

    dep_paths: list[DependencyPathEntry] = []
    raw_dep_paths = data.get("dependency_paths", [])
    if isinstance(raw_dep_paths, dict):
        for k, v in raw_dep_paths.items():
            dep_paths.append(DependencyPathEntry(label=str(k), path=str(v)))
    elif isinstance(raw_dep_paths, (list, tuple)):
        for item in raw_dep_paths:
            if isinstance(item, dict):
                dep_paths.append(DependencyPathEntry(label=str(item.get("label", "")), path=str(item.get("path", ""))))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                dep_paths.append(DependencyPathEntry(label=str(item[0]), path=str(item[1])))

    return JsonManifest(
        label=str(data.get("label") or data.get("name") or ""),
        name=str(data.get("name") or data.get("label") or ""),
        prompt=str(data.get("prompt") or "") if data.get("prompt") is not None else "",
        tools=tuple(str(t) for t in data.get("tools", ())),
        deps=tuple(str(d) for d in data.get("deps", ())),
        silent_deps=tuple(str(d) for d in data.get("silent_deps", ())),
        feedback_deps=tuple(str(d) for d in data.get("feedback_deps", ())),
        star_deps=tuple(str(d) for d in data.get("star_deps", ())),
        src=str(data["src"]) if data.get("src") else None,
        template=str(data["template"]) if data.get("template") else None,
        guide=str(data["guide"]) if data.get("guide") else None,
        silent_srcs=tuple(str(s) for s in data.get("silent_srcs", ())),
        verify=str(data["verify"]) if data.get("verify") else None,
        dependency_paths=tuple(dep_paths),
    )


def load_json_manifest(file_path: ManifestFilePath) -> JsonManifest:
    with open(file_path, "r", encoding="utf-8") as f:
        return parse_json_manifest(f.read())


def locate_manifest_file(manifest_name: ManifestFilePath, search_directories: Sequence[ManifestDirectoryPath]) -> Optional[ManifestFilePath]:
    for base in search_directories:
        if base:
            candidate = os.path.join(base, manifest_name)
            if os.path.isfile(candidate):
                return candidate
    return None
