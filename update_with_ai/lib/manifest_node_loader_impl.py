"""Manifest node loader parsing JSON declarations into graph storage."""

import os
from typing import Sequence, List, Dict, Optional, Set

from .node_id_utils import NodeIdUtils
from .virtual_file_name import VirtualFileMapperFactory
from .build_graph_storage import BuildGraphStorage, NodeDefinition
from .sandbox import SandboxConfig
from .manifest_node_loader import ManifestLoader, ManifestContent
from .json_manifest_ext import (
    JsonManifest,
    parse_json_manifest,
    load_json_manifest,
    locate_manifest_file,
)
from .guide_delivery import TaskGuide, StepSection


def _derive_virtual_file_names(paths: Sequence[str]) -> Dict[str, str]:
    """Derives minimal unique virtual file names for a sequence of workspace file paths."""
    if not paths:
        return {}

    unique_paths = list(dict.fromkeys(paths))
    parsed = []
    for p in unique_paths:
        norm = os.path.normpath(p).replace("\\", "/")
        parts = [part for part in norm.split("/") if part and part != "."]
        parsed.append((p, parts if parts else [norm]))

    mapping: Dict[str, str] = {}
    for orig_path, parts in parsed:
        k = 1
        while k <= len(parts):
            candidate = "/".join(parts[-k:])
            collides = False
            for other_path, other_parts in parsed:
                if other_path != orig_path:
                    other_suffix = "/".join(other_parts[-k:]) if k <= len(other_parts) else "/".join(other_parts)
                    if other_suffix == candidate:
                        collides = True
                        break
            if not collides:
                mapping[candidate] = orig_path
                break
            k += 1
        else:
            mapping["/".join(parts)] = orig_path

    return mapping


def _parse_guide_sections(content: str) -> TaskGuide:
    lines = content.splitlines()
    summary_lines: List[str] = []
    sections: List[StepSection] = []
    current_title: Optional[str] = None
    current_lines: List[str] = []
    index = 0
    in_summary = True

    for line in lines:
        if line.startswith("## "):
            heading = line[3:].strip()
            if in_summary:
                in_summary = False
            else:
                if current_title and not current_title.lower().startswith("lint checks"):
                    sections.append(
                        StepSection(
                            index=index,
                            title=current_title,
                            content="\n".join(current_lines).strip(),
                        )
                    )
                    index += 1
            current_title = heading
            current_lines = []
        elif in_summary:
            summary_lines.append(line)
        else:
            current_lines.append(line)

    if current_title and not in_summary and not current_title.lower().startswith("lint checks"):
        sections.append(
            StepSection(
                index=index,
                title=current_title,
                content="\n".join(current_lines).strip(),
            )
        )

    return TaskGuide(
        summary="\n".join(summary_lines).strip(),
        sections=tuple(sections),
    )


class ManifestLoaderImpl(ManifestLoader):
    """Implementation of ManifestLoader using NodeIdUtils and JsonManifest."""

    def __init__(
        self,
        node_id_utils: NodeIdUtils,
        virtual_file_mapper_factory: Optional[VirtualFileMapperFactory] = None,
    ) -> None:
        self.node_id_utils = node_id_utils
        self.virtual_file_mapper_factory = virtual_file_mapper_factory

    def load_manifest(
        self, content: ManifestContent, storage: BuildGraphStorage
    ) -> Sequence[NodeDefinition]:
        manifest = parse_json_manifest(content)
        canonical_label = self.node_id_utils.canonicalize_node_id(manifest.label, "")
        pkg_dir = self.node_id_utils.extract_node_directory(canonical_label, "")

        ws_dir = os.environ.get("BUILD_WORKSPACE_DIRECTORY", "")
        search_dirs = [
            os.environ.get("RUNFILES_DIR", ""),
            os.environ.get("BAZEL_RUNFILES", ""),
            ws_dir,
            os.path.join(ws_dir, "bazel-bin") if ws_dir else "",
            os.path.join(os.getcwd(), "bazel-bin"),
            os.getcwd(),
        ]
        expanded_dirs: List[str] = []
        for d in search_dirs:
            if d:
                expanded_dirs.append(d)
                main_sub = os.path.join(d, "_main")
                if os.path.isdir(main_sub):
                    expanded_dirs.append(main_sub)

        known_dep_paths: Dict[str, str] = {
            dp.label: dp.path for dp in manifest.dependency_paths
        }

        manifest_cache: Dict[str, Optional[JsonManifest]] = {
            canonical_label: manifest
        }

        def get_dep_manifest(dep_label: str) -> Optional[JsonManifest]:
            canonical_dep = self.node_id_utils.canonicalize_node_id(dep_label, "")
            if canonical_dep in manifest_cache:
                return manifest_cache[canonical_dep]

            clean_label = canonical_dep
            if clean_label.startswith("@@"):
                clean_label = clean_label[2:]
            elif clean_label.startswith("@") and "//" in clean_label:
                clean_label = clean_label[clean_label.index("//"):]
            if clean_label.startswith("//"):
                clean_label = clean_label[2:]

            pkg_manifest = clean_label.replace(":", "/") + "_manifest.json"
            dep_name = canonical_dep.split(":")[-1] if ":" in canonical_dep else canonical_dep
            bare_manifest = f"{dep_name}_manifest.json"

            for manifest_name in (pkg_manifest, bare_manifest):
                found_path = locate_manifest_file(manifest_name, expanded_dirs)
                if found_path:
                    try:
                        loaded = load_json_manifest(found_path)
                        manifest_cache[canonical_dep] = loaded
                        return loaded
                    except Exception:
                        pass

            manifest_cache[canonical_dep] = None
            return None

        def resolve_dep_src(dep_label: str) -> Optional[str]:
            if dep_label in known_dep_paths:
                return known_dep_paths[dep_label]
            canonical_dep = self.node_id_utils.canonicalize_node_id(dep_label, "")
            if canonical_dep in known_dep_paths:
                return known_dep_paths[canonical_dep]

            dep_m = get_dep_manifest(dep_label)
            if dep_m and dep_m.src:
                dep_pkg = self.node_id_utils.extract_node_directory(canonical_dep, "")
                if dep_pkg and not os.path.isabs(dep_m.src):
                    return os.path.normpath(os.path.join(dep_pkg, dep_m.src))
                return dep_m.src

            return None

        rw_files: List[str] = []
        templates: Dict[str, str] = {}

        if manifest.src:
            src_path = os.path.normpath(os.path.join(pkg_dir, manifest.src)) if pkg_dir and not os.path.isabs(manifest.src) else manifest.src
            rw_files.append(src_path)
            if manifest.template:
                templates[src_path] = manifest.template

        for s in manifest.silent_srcs:
            s_path = os.path.normpath(os.path.join(pkg_dir, s)) if pkg_dir and not os.path.isabs(s) else s
            if s_path not in rw_files:
                rw_files.append(s_path)

        ro_files: List[str] = []

        for d in manifest.deps:
            canonical_d = self.node_id_utils.canonicalize_node_id(d, "")
            dep_src = resolve_dep_src(canonical_d)
            if dep_src and dep_src not in ro_files and dep_src not in rw_files:
                ro_files.append(dep_src)

        visited_star_deps: Set[str] = set()
        star_queue: List[str] = list(manifest.star_deps)
        while star_queue:
            curr_star = star_queue.pop(0)
            canonical_star = self.node_id_utils.canonicalize_node_id(curr_star, "")
            if canonical_star in visited_star_deps:
                continue
            visited_star_deps.add(canonical_star)

            star_src = resolve_dep_src(canonical_star)
            if star_src and star_src not in ro_files and star_src not in rw_files:
                ro_files.append(star_src)

            star_m = get_dep_manifest(canonical_star)
            if star_m:
                for next_star in star_m.star_deps:
                    if next_star not in visited_star_deps:
                        star_queue.append(next_star)

        task_guide: Optional[TaskGuide] = None
        step_mode_guide_name: Optional[str] = None
        if manifest.guide:
            guide_src = resolve_dep_src(manifest.guide)
            if guide_src:
                step_mode_guide_name = guide_src
                for search_base in [""] + expanded_dirs:
                    candidate = os.path.join(search_base, guide_src) if search_base else guide_src
                    if os.path.isfile(candidate):
                        try:
                            with open(candidate, "r", encoding="utf-8") as gf:
                                task_guide = _parse_guide_sections(gf.read())
                            break
                        except Exception:
                            pass
                if not task_guide:
                    task_guide = TaskGuide(summary=guide_src, sections=())

        for fd in manifest.feedback_deps:
            canonical_fd = self.node_id_utils.canonicalize_node_id(fd, "")
            fd_src = resolve_dep_src(canonical_fd)
            if fd_src and fd_src not in ro_files and fd_src not in rw_files:
                ro_files.append(fd_src)

        all_accessible = list(dict.fromkeys(rw_files + ro_files))
        if self.virtual_file_mapper_factory:
            mapper = self.virtual_file_mapper_factory.create_mapper(all_accessible)
            file_mappings = mapper.get_mappings()
        else:
            file_mappings = _derive_virtual_file_names(all_accessible)

        ro_virtual = [
            next((v for v, h in file_mappings.items() if h == ro), ro)
            for ro in ro_files
        ]
        rw_virtual = [
            next((v for v, h in file_mappings.items() if h == rw), rw)
            for rw in rw_files
        ]
        templates_virtual = {
            next((v for v, h in file_mappings.items() if h == orig_k), orig_k): tmpl
            for orig_k, tmpl in templates.items()
        }

        sandbox_config = SandboxConfig(
            file_mappings=file_mappings,
            read_only_files=tuple(ro_virtual),
            read_write_files=tuple(rw_virtual),
            templates=templates_virtual,
            guide=task_guide,
            step_mode_guide_name=step_mode_guide_name,
        )

        all_canonical_deps = [
            self.node_id_utils.canonicalize_node_id(d, "") for d in manifest.deps
        ]
        for sd in manifest.silent_deps:
            canonical_sd = self.node_id_utils.canonicalize_node_id(sd, "")
            if canonical_sd not in all_canonical_deps:
                all_canonical_deps.append(canonical_sd)

        if hasattr(storage, "set_sandbox_config"):
            getattr(storage, "set_sandbox_config")(canonical_label, sandbox_config)
        if hasattr(storage, "set_dependencies"):
            getattr(storage, "set_dependencies")(canonical_label, all_canonical_deps)
        if manifest.prompt and hasattr(storage, "set_task_prompt"):
            getattr(storage, "set_task_prompt")(canonical_label, manifest.prompt)

        node_def = NodeDefinition(
            sandbox_config=sandbox_config,
            prompt=manifest.prompt if manifest.prompt else None,
            config_target=None,
        )
        if hasattr(storage, "set_node_definition"):
            getattr(storage, "set_node_definition")(canonical_label, node_def)

        for d in all_canonical_deps:
            if hasattr(storage, "get_node_definition") and getattr(storage, "get_node_definition")(d) is None:
                empty_cfg = SandboxConfig(
                    file_mappings={},
                    read_only_files=(),
                    read_write_files=(),
                    templates={},
                )
                empty_def = NodeDefinition(sandbox_config=empty_cfg)
                if hasattr(storage, "set_node_definition"):
                    getattr(storage, "set_node_definition")(d, empty_def)

        return [node_def]
