# lib/manifest_node_loader_impl.py
"""
Implementation of the LLS ManifestNodeLoader interface.
"""

from typing import Any, Dict, List, Optional, Tuple
import json
import os
import subprocess
from pathlib import Path

from .build_graph_storage import NodeDefinition, PackageDirectory, GraphConfig
from .dag_storage import NodeId, NodeDependencies
from .manifest_node_loader import ManifestNodeLoader, LoadedGraphManifests
from .file_reader import FileMapping, ReadablePaths, VirtualName
from .file_editor import TemplateMapping, WritablePaths
from .run_control import BlameTargets, VerificationCallback
from .sandbox import SandboxConfig


def _virtual_names(paths: List[str]) -> Dict[str, str]:
    if not paths:
        return {}
    parts = [p.split("/") for p in paths]
    result: Dict[str, str] = {}
    for i, orig in enumerate(paths):
        p = parts[i]
        for length in range(1, len(p) + 1):
            cand = "/".join(p[-length:])
            collisions = [
                j for j, other in enumerate(parts)
                if j != i and len(other) >= length and "/".join(other[-length:]) == cand
            ]
            if not collisions:
                result[orig] = cand
                break
        else:
            result[orig] = orig
    return result


def _build_sandbox_config(
    manifest: Dict[str, Any],
    file_mappings: FileMapping,
    readable_paths: ReadablePaths,
    writable_paths: WritablePaths,
    templates: TemplateMapping,
    guide: Optional[VirtualName],
    blame_targets: BlameTargets,
) -> SandboxConfig:
    vcmd = manifest.get("verification_command")
    callback: VerificationCallback = None
    if vcmd:
        def make_cb(cmd: str) -> VerificationCallback:
            def cb() -> Tuple[bool, str]:
                try:
                    proc = subprocess.run(
                        cmd, shell=True, capture_output=True, text=True, timeout=120
                    )
                    return proc.returncode == 0, proc.stdout + proc.stderr
                except Exception as e:
                    return False, str(e)
            return cb
        callback = make_cb(vcmd)

    return SandboxConfig(
        file_mappings=file_mappings,
        readable_paths=readable_paths,
        writable_paths=writable_paths,
        blame_targets=blame_targets,
        search_result_limit=manifest.get("search_result_limit", 5),
        session_start_reads_enabled=manifest.get("session_start_reads_enabled", True),
        guide=guide,
        step_sections_enabled=manifest.get("step_sections_enabled", True),
        feedback_pending=manifest.get("feedback_pending", False),
        templates=templates,
        verification_callback=callback,
    )


def _synthesized_manifest(label: NodeId) -> Dict[str, Any]:
    return {
        "label": label,
        "prompt": f"Generated synthetic node for dependency {label}",
        "src": "",
        "silent_srcs": [],
        "deps": [],
        "silent_deps": [],
        "star_deps": [],
        "feedback_deps": [],
        "tools": [],
        "search_result_limit": 5,
        "session_start_reads_enabled": True,
        "step_sections_enabled": True,
        "feedback_pending": False,
    }


def _synthesized_definition() -> NodeDefinition:
    return NodeDefinition(
        prompt="Generated synthetic node",
        sandbox_config=SandboxConfig(
            file_mappings={},
            readable_paths=[],
            writable_paths=[],
            blame_targets={},
            search_result_limit=5,
            session_start_reads_enabled=True,
            step_sections_enabled=True,
            feedback_pending=False,
            templates={},
            verification_callback=None,
        ),
    )


def _package_dir_from_label(label: NodeId, workspace_root: Path) -> str:
    clean = label.lstrip("/")
    if ":" in clean:
        pkg_part, _ = clean.split(":", 1)
    else:
        pkg_part = clean
    return str(workspace_root / pkg_part)


class ManifestNodeLoaderImpl(ManifestNodeLoader):
    def resolve_graph(self, config: GraphConfig) -> LoadedGraphManifests:
        if config.workspace_root is None:
            raise ValueError("ManifestNodeLoader requires workspace_root in config")

        workspace_root = Path(config.workspace_root)
        real_root = Path(
            os.environ.get("BUILD_WORKSPACE_DIRECTORY") or workspace_root
        )

        manifests = list(workspace_root.rglob("*_manifest.json"))
        raw: Dict[NodeId, Any] = {}
        pkg_dirs: Dict[NodeId, PackageDirectory] = {}

        for json_path in manifests:
            with open(json_path) as f:
                manifest = json.load(f)
            node_id: NodeId = manifest["label"]
            rel_pkg = json_path.parent.relative_to(workspace_root)
            pkg_dirs[node_id] = str(real_root / rel_pkg)
            raw[node_id] = manifest

        definitions: Dict[NodeId, NodeDefinition] = {}
        adjacency: Dict[NodeId, List[NodeId]] = {}
        propagating_deps: Dict[NodeId, List[NodeId]] = {}
        silent_deps_map: Dict[NodeId, List[NodeId]] = {}
        package_dirs: Dict[NodeId, PackageDirectory] = {}

        for node_id, manifest in raw.items():
            raw_deps: List[NodeId] = list(manifest.get("deps", []))
            feedback_deps: List[NodeId] = list(manifest.get("feedback_deps", []))
            star_deps: List[NodeId] = [str(sd) for sd in manifest.get("star_deps", [])]
            deps: List[NodeId] = list(raw_deps)
            for fd in feedback_deps:
                if fd not in deps:
                    deps.append(fd)
            for sd in star_deps:
                if sd not in deps:
                    deps.append(sd)

            dep_srcs: Dict[str, str] = {}
            for dep in deps:
                dep_manifest = raw.get(dep)
                if dep_manifest is None:
                    continue
                dep_pkg = pkg_dirs.get(dep)
                if dep_pkg is None:
                    continue
                dep_src: str = str(dep_manifest.get("src") or "")
                if dep_src:
                    dep_srcs.setdefault(dep_src, dep_pkg)

            closure: List[NodeId] = []
            closure_seen: set = set()
            queue: List[NodeId] = list(star_deps)
            while queue:
                lbl = queue.pop(0)
                if lbl in closure_seen:
                    continue
                closure_seen.add(lbl)
                closure.append(lbl)
                dep_manifest = raw.get(lbl)
                if dep_manifest is None:
                    continue
                follow: List[NodeId] = list(dep_manifest.get("star_deps", []))
                queue.extend(follow)

            for lbl in closure:
                dep_manifest = raw.get(lbl)
                if dep_manifest is None:
                    continue
                dep_pkg = pkg_dirs.get(lbl)
                if dep_pkg is None:
                    continue
                dep_src = str(dep_manifest.get("src") or "")
                if dep_src:
                    dep_srcs.setdefault(dep_src, dep_pkg)

            own_src: str = str(manifest.get("src") or "")
            own_silent_srcs: List[str] = [str(s) for s in manifest.get("silent_srcs", [])]
            pkg_dir = pkg_dirs[node_id]

            guide_label: Optional[NodeId] = manifest.get("guide")  # pyright: ignore[reportArgumentType]
            guide_src: Optional[str] = None
            files: Dict[str, str] = {
                s: os.path.join(d, s) for s, d in dep_srcs.items()
            }
            if own_src:
                files[own_src] = os.path.join(pkg_dir, own_src)
            for s in own_silent_srcs:
                files[s] = os.path.join(pkg_dir, s)
            if guide_label:
                guide_manifest = raw.get(guide_label)
                guide_pkg = pkg_dirs.get(guide_label)
                if guide_manifest is not None and guide_pkg is not None:
                    gs = str(guide_manifest.get("src") or "")
                    if gs:
                        files[gs] = os.path.join(guide_pkg, gs)
                        guide_src = gs

            virtual_of = _virtual_names(list(files.keys()))

            file_mappings: FileMapping = {
                virtual_of[s]: real for s, real in files.items()
            }
            readable_paths = ([virtual_of[own_src]] if own_src else []) + [
                virtual_of[s] for s in own_silent_srcs
            ] + [
                virtual_of[s] for s in dep_srcs if s != own_src
            ]
            writable_paths = ([virtual_of[own_src]] if own_src else []) + [
                virtual_of[s] for s in own_silent_srcs
            ]

            templates: Dict[str, str] = {}
            template_rel = manifest.get("template")
            if template_rel and own_src:
                template_path = real_root / str(template_rel)
                if os.path.exists(template_path):
                    with open(template_path, "r", encoding="utf-8") as f:
                        templates[virtual_of[own_src]] = f.read()

            guide_virtual: Optional[str] = (
                virtual_of.get(guide_src) if guide_src else None
            )
            if guide_virtual and guide_virtual not in readable_paths:
                readable_paths.append(guide_virtual)

            blame_targets: Dict[str, str] = {}
            for fd in manifest.get("feedback_deps", []):
                fd_manifest = raw.get(fd)
                if fd_manifest is None:
                    continue
                fd_src = str(fd_manifest.get("src") or "")
                if fd_src and fd_src in virtual_of:
                    blame_targets[virtual_of[fd_src]] = fd

            definitions[node_id] = NodeDefinition(
                prompt=manifest["prompt"],
                sandbox_config=_build_sandbox_config(
                    manifest,
                    file_mappings=file_mappings,
                    readable_paths=readable_paths,
                    writable_paths=writable_paths,
                    templates=templates,
                    guide=guide_virtual,
                    blame_targets=blame_targets,
                ),
            )

            silent_deps: List[NodeId] = list(manifest.get("silent_deps", []))
            all_deps: List[NodeId] = deps + silent_deps
            if guide_label and guide_label not in all_deps:
                all_deps.append(guide_label)

            adjacency[node_id] = all_deps
            propagating_deps[node_id] = deps
            silent_deps_map[node_id] = silent_deps
            package_dirs[node_id] = pkg_dir

        declared_deps: List[NodeId] = []
        for manifest in raw.values():
            declared_deps.extend(manifest.get("deps", []))
            declared_deps.extend(manifest.get("silent_deps", []))
            declared_deps.extend(manifest.get("star_deps", []))
            guide_label = manifest.get("guide")
            if guide_label:
                declared_deps.append(guide_label)

        for dep in declared_deps:
            if dep in raw or dep in definitions:
                continue
            raw[dep] = _synthesized_manifest(dep)
            definitions[dep] = _synthesized_definition()
            adjacency[dep] = []
            propagating_deps[dep] = []
            silent_deps_map[dep] = []
            package_dirs[dep] = _package_dir_from_label(dep, real_root)

        return LoadedGraphManifests(
            node_definitions=definitions,
            node_dependencies=adjacency,
            package_directories=package_dirs,
            propagating_dependencies=propagating_deps,
            silent_dependencies=silent_deps_map,
        )
