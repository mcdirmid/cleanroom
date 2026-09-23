# Requirements specified in bazel_node_config_impl.pyi

import json
import os
import re
import subprocess
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, Type
from . import bazel_manifest_loader
from . import bazel_target
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.agent.lib import agent_file_alias
from . import file_paths
from update_with_ai.parts.agent.lib import agent_config
from update_with_ai.parts.agent.lib import agent_node_config
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.sandbox.lib import tool_provider
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleResolutionError,
    Singleton,
    get_default_registry,
    get_singleton,
)


class _CommandVerificationCheck(agent_node_config.VerificationCheck):
    def __init__(self, command: str, cwd: Optional[str] = None) -> None:
        self._command = command
        self._cwd = cwd

    def verify(self) -> Tuple[bool, str]:
        env = os.environ.copy()
        if not env.get("BUILD_WORKSPACE_DIRECTORY"):
            env["BUILD_WORKSPACE_DIRECTORY"] = self._cwd or os.getcwd()
        try:
            res = subprocess.run(
                self._command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self._cwd,
                env=env,
                stdin=subprocess.DEVNULL,
            )
            passed = res.returncode == 0
            output = res.stdout
            if res.stderr:
                output = f"{output}\n{res.stderr}".strip() if output else res.stderr
            return passed, output
        except Exception as e:
            return False, str(e)


def _make_host_path(cls: Any, path: str) -> Any:
    if issubclass(cls, str):
        return cls(path)
    obj = object.__new__(cls)
    object.__setattr__(obj, "path", path)
    return obj


def _parse_guide_markdown(content: str) -> agent_node_config.Guide:
    lines = content.splitlines()
    summary_lines: List[str] = []
    sections: List[agent_node_config.StepSection] = []
    verification_failure_lines: Optional[List[str]] = None

    current_title: Optional[str] = None
    current_section_lines: List[str] = []

    for line in lines:
        if line.startswith("## "):
            if current_title is None:
                summary_lines = list(current_section_lines)
            else:
                if current_title.startswith("Verification failure"):
                    verification_failure_lines = list(current_section_lines)
                elif not current_title.startswith("Lint checks"):
                    sections.append(
                        agent_node_config.StepSection(
                            index=len(sections),
                            title=current_title,
                            content="\n".join(current_section_lines).strip(),
                        )
                    )
            current_title = line[3:].strip()
            current_section_lines = []
        else:
            current_section_lines.append(line)

    if current_title is not None:
        if current_title.startswith("Verification failure"):
            verification_failure_lines = list(current_section_lines)
        elif not current_title.startswith("Lint checks"):
            sections.append(
                agent_node_config.StepSection(
                    index=len(sections),
                    title=current_title,
                    content="\n".join(current_section_lines).strip(),
                )
            )

    summary = "\n".join(summary_lines).strip()
    vf_text = (
        "\n".join(verification_failure_lines).strip()
        if verification_failure_lines is not None
        else None
    )
    return agent_node_config.Guide(
        summary=summary,
        sections=sections,
        verification_failure=vf_text,
    )


def _load_per_node_info(n: dag_storage.Node) -> agent_node_config.PerNodeInfo:
    all_feedback: List[str] = []
    try:
        storage = get_singleton(dag_storage.DagStorage)
        msgs = storage.get_messages(n)
        all_feedback.extend(
            m.content
            for m in msgs
            if isinstance(m, dag_storage.Feedback) and m.content
        )
    except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
        pass
    feedback = tuple(all_feedback)

    try:
        loader = get_singleton(bazel_manifest_loader.BazelManifestLoader)
    except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
        loader = None

    try:
        node_util = get_singleton(bazel_target.BazelTarget)
    except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
        node_util = None

    manifest_raw = loader.get_manifest(n) if loader is not None else None
    data: Dict[str, Any] = {}
    if manifest_raw is not None:
        try:
            data = json.loads(str(manifest_raw))
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    pkg_path = ""
    if node_util is not None:
        pkg_dir = node_util.extract_directory(n)
        pkg_path = pkg_dir.path.lstrip("/")

    rw_files: Set[agent_file_alias.ReadWriteFile] = set()
    src_alias: Optional[str] = None

    src = data.get("src")
    if src:
        if src.startswith(pkg_path + "/") or (
            pkg_path and src.startswith("/" + pkg_path + "/")
        ):
            norm_rel = os.path.normpath(src.lstrip("/"))
        else:
            norm_rel = os.path.normpath(os.path.join(pkg_path, src))
        ws_path = _make_host_path(agent_file_alias.WorkspacePath, norm_rel)
        rw = agent_file_alias.ReadWriteFile(
            relative_path=norm_rel, workspace_path=ws_path, owning_node=n
        )
        rw_files.add(rw)
        src_alias = norm_rel

    silent_srcs = data.get("silent_srcs", [])
    for s_src in silent_srcs:
        norm_rel = os.path.normpath(os.path.join(pkg_path, s_src))
        ws_path = _make_host_path(agent_file_alias.WorkspacePath, norm_rel)
        rw = agent_file_alias.ReadWriteFile(
            relative_path=norm_rel, workspace_path=ws_path, owning_node=n
        )
        rw_files.add(rw)

    templates: Set[
        Tuple[agent_file_alias.BoundFile, agent_file_alias.FileContent]
    ] = set()
    template_rel = data.get("template")
    if template_rel and rw_files:
        content_str: Optional[str] = None
        cand_paths = [
            template_rel,
            os.path.join(
                os.environ.get("BUILD_WORKSPACE_DIRECTORY", ""), template_rel
            ),
        ]
        for base in (
            os.environ.get("RUNFILES_DIR", ""),
            os.environ.get("BAZEL_RUNFILES", ""),
        ):
            if base:
                cand_paths.extend(
                    [
                        os.path.join(base, template_rel),
                        os.path.join(base, "_main", template_rel),
                    ]
                )
        for cp in cand_paths:
            if cp and os.path.exists(cp) and os.path.isfile(cp):
                try:
                    with open(cp, "r", encoding="utf-8") as f:
                        content_str = f.read()
                        break
                except (OSError, UnicodeDecodeError):
                    pass
        if content_str is not None:
            content_obj = agent_file_alias.FileContent(content_str)
            for rw in rw_files:
                if rw.owning_node == n:
                    templates.add((rw, content_obj))

    template_parameters: Dict[str, Any] = {}
    raw_params = data.get("template_parameters")
    if isinstance(raw_params, dict):
        template_parameters.update(raw_params)
    elif isinstance(raw_params, str):
        try:
            decoded = json.loads(raw_params)
            if isinstance(decoded, dict):
                template_parameters.update(decoded)
        except (json.JSONDecodeError, ValueError):
            pass

    allows_step = data.get(
        "allows_step_mode",
        data.get("step_mode", data.get("step_sections", True)),
    )
    allows_step_mode = bool(allows_step)

    guide_target = data.get("guide")
    guide_file: Optional[agent_file_alias.UnboundFile] = None
    guide: Optional[agent_node_config.Guide] = None
    if guide_target:
        guide_filename = (
            guide_target.split(":")[-1]
            if ":" in guide_target
            else os.path.basename(guide_target)
        )
        if not guide_filename.endswith(".md"):
            guide_filename += ".md"
        guide_file = agent_file_alias.UnboundFile(relative_path=guide_filename)

        guide_cand_paths = [
            os.path.join(
                os.environ.get("BUILD_WORKSPACE_DIRECTORY", ""),
                "update_python_with_ai/guides",
                guide_filename,
            ),
            os.path.join("update_python_with_ai/guides", guide_filename),
        ]
        for base in (
            os.environ.get("RUNFILES_DIR", ""),
            os.environ.get("BAZEL_RUNFILES", ""),
        ):
            if base:
                guide_cand_paths.extend(
                    [
                        os.path.join(
                            base, "update_python_with_ai/guides", guide_filename
                        ),
                        os.path.join(
                            base,
                            "_main/update_python_with_ai/guides",
                            guide_filename,
                        ),
                    ]
                )
        for gp in guide_cand_paths:
            if gp and os.path.exists(gp) and os.path.isfile(gp):
                try:
                    with open(gp, "r", encoding="utf-8") as gf:
                        g_text = gf.read()
                    guide = _parse_guide_markdown(g_text)
                    break
                except (OSError, UnicodeDecodeError):
                    pass

    deps = data.get("deps", [])
    star_deps = data.get("star_deps", [])
    silent_deps = set(data.get("silent_deps", []))
    feedback_deps = set(data.get("feedback_deps", []))

    star_closure: List[str] = []
    star_seen: Set[str] = set()
    frontier = [sd for sd in star_deps if sd not in silent_deps]
    while frontier:
        curr_label = frontier.pop(0)
        if curr_label in star_seen:
            continue
        star_seen.add(curr_label)
        star_closure.append(curr_label)
        curr_node = (
            node_util.normalize(curr_label)
            if node_util is not None
            else dag_storage.Node(unit_address=curr_label)  # pragma: no cover (assumption: node_util is registered in system tier)
        )
        dep_manifest_raw = (
            loader.get_manifest(curr_node) if loader is not None else None
        )
        if dep_manifest_raw:
            try:
                dep_data = json.loads(str(dep_manifest_raw))
                for next_sd in dep_data.get("star_deps", []):
                    if next_sd not in star_seen and next_sd not in silent_deps:
                        frontier.append(next_sd)
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

    blame_targets: Set[agent_file_alias.BoundFile] = set()
    read_only_files: Set[agent_file_alias.ReadOnlyFile] = set()
    rw_paths = {rw.workspace_path.path for rw in rw_files}

    all_deps = list(deps) + [sd for sd in star_closure if sd not in deps]
    for dep_label in all_deps:
        if dep_label in silent_deps:
            continue
        dep_node = (
            node_util.normalize(dep_label)
            if node_util is not None
            else dag_storage.Node(unit_address=dep_label)  # pragma: no cover (assumption: node_util is registered in system tier)
        )
        is_blame = dep_label in feedback_deps
        dep_manifest_raw = (
            loader.get_manifest(dep_node) if loader is not None else None
        )
        dep_srcs: List[str] = []
        dep_pkg = (
            node_util.extract_directory(dep_node).path.lstrip("/")
            if node_util is not None
            else ""  # pragma: no cover (assumption: node_util is registered in system tier)
        )

        if dep_manifest_raw:
            try:
                dep_data = json.loads(str(dep_manifest_raw))
                if dep_data.get("src"):
                    dep_srcs.append(dep_data["src"])
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        elif "guides" in dep_label:
            guide_fn = dep_label.split(":")[-1]
            if not guide_fn.endswith(".md"):
                guide_fn += ".md"
            dep_srcs.append(guide_fn)
        elif "specs" in dep_label:
            target_base = (
                dep_label.split(":")[-1]
                .replace("_low", "")
                .replace("_high", "")
                .replace("_lib", "")
            )
            if dep_label.endswith("_low") or dep_label.endswith("_grounding"):
                dep_srcs.append(f"grounding/{target_base}.pyi")
            elif dep_label.endswith("_high"):
                dep_srcs.append(f"high/{target_base}.md")
        else:
            target_name = dep_label.split(":")[-1]
            dep_srcs.append(f"{target_name}.py")

        for ds in dep_srcs:
            if ds.startswith(dep_pkg + "/") or (
                dep_pkg and ds.startswith("/" + dep_pkg + "/")
            ):
                norm_rel = os.path.normpath(ds.lstrip("/"))
            else:
                norm_rel = os.path.normpath(os.path.join(dep_pkg, ds))

            ws_path = _make_host_path(
                agent_file_alias.WorkspacePath, norm_rel
            )
            bound_file = agent_file_alias.ReadOnlyFile(
                relative_path=norm_rel,
                workspace_path=ws_path,
                owning_node=dep_node,
            )
            if norm_rel not in rw_paths:
                read_only_files.add(bound_file)

            if is_blame:
                blame_targets.add(bound_file)

    ws_dir = os.environ.get("BUILD_WORKSPACE_DIRECTORY") or os.getcwd()
    verify_cmd = data.get("verify")
    node_checks: List[agent_node_config.VerificationCheck] = []
    if verify_cmd and str(verify_cmd).strip():
        check = _CommandVerificationCheck(
            command=str(verify_cmd).strip(), cwd=ws_dir
        )
        node_checks.append(check)
    verification_checks = tuple(node_checks)

    v_msg = data.get("verification_success_message")
    verification_success_message = (
        str(v_msg).strip() if v_msg and str(v_msg).strip() else None
    )

    return agent_node_config.PerNodeInfo(
        node=n,
        read_only_files=read_only_files,
        read_write_files=rw_files,
        templates=templates,
        template_parameters=template_parameters,
        allows_step_mode=allows_step_mode,
        guide_file=guide_file,
        guide=guide,
        blame_targets=blame_targets,
        verification_checks=verification_checks,
        src_file_alias=src_alias,
        verification_success_message=verification_success_message,
        feedback=feedback,
    )


class NodeConfig(agent_node_config.NodeConfig, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._per_node_cache: Dict[dag_storage.Node, agent_node_config.PerNodeInfo] = {}
        self._cached_version: int = -1
        self._allows_step_mode_override: Optional[bool] = None
        self._is_step_mode_override: Optional[bool] = None

    def initialize(self) -> None:
        self._sync_cache()

    def _sync_cache(self) -> None:
        try:
            role_cfg = get_singleton(agent_node_config.RoleConfig)
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
            return

        if role_cfg.version == self._cached_version:
            return

        active_nodes = set(role_cfg.nodes)

        for n in list(self._per_node_cache.keys()):
            if n not in active_nodes:
                del self._per_node_cache[n]

        for n in role_cfg.nodes:
            if n not in self._per_node_cache:
                self._per_node_cache[n] = _load_per_node_info(n)

        self._cached_version = role_cfg.version

    def _active_per_node_infos(self) -> List[agent_node_config.PerNodeInfo]:
        try:
            role_cfg = get_singleton(agent_node_config.RoleConfig)
            return [
                self._per_node_cache[n]
                for n in role_cfg.nodes
                if n in self._per_node_cache
            ]
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
            return list(self._per_node_cache.values())

    @property
    def per_node_info_by_node(
        self,
    ) -> Mapping[dag_storage.Node, agent_node_config.PerNodeInfo]:
        # Requirement: The session per node info by node mapping each active node to its per node info.
        # Requirement: [NodeConfig] The node config provides the session per node info by node, mapping each active node to its per node info.
        self._sync_cache()
        return dict(self._per_node_cache)

    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        # Requirement: The session read-only files aggregating read-only files across the active nodes, excluding files present in the session read-write files.
        # Requirement: [NodeConfig] The node config provides the session read-only files restricted to inspection.
        self._sync_cache()
        rw_paths = {rw.workspace_path.path for rw in self.read_write_files}
        res: Set[agent_file_alias.ReadOnlyFile] = set()
        for pni in self._active_per_node_infos():
            for ro in pni.read_only_files:
                if ro.workspace_path.path not in rw_paths:
                    if (
                        self.is_step_mode
                        and self.guide_file is not None
                        and ro.relative_path == self.guide_file.relative_path
                    ):
                        continue
                    res.add(ro)
        return res

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        # Requirement: The session read-write files and templates aggregating read-write files and templates across the active nodes, mapping read-write files to initial file content.
        # Requirement: [NodeConfig] The node config provides the session read-write files permitted for inspection and modification.
        self._sync_cache()
        res: Set[agent_file_alias.ReadWriteFile] = set()
        for pni in self._active_per_node_infos():
            res.update(pni.read_write_files)
        return res

    @property
    def allows_step_mode(self) -> bool:
        # Requirement: Whether the node allows step mode resolved when the session contains exactly one node.
        # Requirement: [NodeConfig] The node config indicates whether the node allows step mode, permitting guide step mode when enabled by agent config.
        if self._allows_step_mode_override is not None:
            return self._allows_step_mode_override
        self._sync_cache()
        infos = self._active_per_node_infos()
        if len(infos) == 1:
            return infos[0].allows_step_mode
        if not infos:
            return True
        return False

    @property
    def is_step_mode(self) -> bool:
        # Requirement: Whether step mode is active, enabled when the agent config enables step mode, the session contains exactly one node, the target node allows step mode, and session feedback is absent.
        # Requirement: [NodeConfig] The node config indicates whether session step mode is active, enabled when agent config enables step mode, the session contains exactly one node, the node allows step mode, and session feedback is absent.
        if self._is_step_mode_override is not None:
            return self._is_step_mode_override
        self._sync_cache()
        infos = self._active_per_node_infos()
        if len(infos) != 1:
            return False
        m_cfg: Optional[agent_config.AgentConfig] = None
        try:
            m_cfg = get_singleton(agent_config.AgentConfig)
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
            pass
        model_step_mode = m_cfg.is_step_mode if m_cfg is not None else False
        return (
            model_step_mode
            and self.allows_step_mode
            and not bool(self.feedback)
        )

    @property
    def guide_file(self) -> Optional[agent_file_alias.UnboundFile]:
        # Requirement: The session guide file and task guide from the single active node when guide step mode is active.
        # Requirement: [NodeConfig] The node config provides the session guide file when step mode is active.
        self._sync_cache()
        if not self.is_step_mode:
            return None
        infos = self._active_per_node_infos()
        if len(infos) == 1:
            return infos[0].guide_file
        return None

    @property
    def templates(
        self,
    ) -> Set[Tuple[agent_file_alias.BoundFile, agent_file_alias.FileContent]]:
        # Requirement: The session read-write files and templates aggregating read-write files and templates across the active nodes, mapping read-write files to initial file content.
        # Requirement: [NodeConfig] The node config provides the session templates, mapping read-write files to initial file content.
        self._sync_cache()
        res: Set[Tuple[agent_file_alias.BoundFile, agent_file_alias.FileContent]] = set()
        for pni in self._active_per_node_infos():
            res.update(pni.templates)
        return res

    @property
    def template_parameters(self) -> Mapping[str, Any]:
        # Requirement: The session template parameters combining template parameters across the active nodes.
        # Requirement: [NodeConfig] The node config provides the session template parameters, providing parameter bindings for template evaluation.
        self._sync_cache()
        res: Dict[str, Any] = {}
        for pni in self._active_per_node_infos():
            res.update(pni.template_parameters)
        return res

    @property
    def guide(self) -> Optional[agent_node_config.Guide]:
        # Requirement: The session guide file and task guide from the single active node when guide step mode is active.
        # Requirement: [NodeConfig] The node config provides the session guide, providing structured instructional text when step mode is active.
        self._sync_cache()
        if not self.is_step_mode:
            return None
        infos = self._active_per_node_infos()
        if len(infos) == 1:
            return infos[0].guide
        return None

    @property
    def blame_targets(self) -> Set[agent_file_alias.BoundFile]:
        # Requirement: The session blame targets aggregating blame targets across the active nodes, and blame targets by node mapping each active node to its declared blame targets.
        # Requirement: [NodeConfig] The node config provides the session blame targets, which are bound files owned by upstream dependency nodes eligible for defect attribution.
        self._sync_cache()
        res: Set[agent_file_alias.BoundFile] = set()
        for pni in self._active_per_node_infos():
            res.update(pni.blame_targets)
        return res

    @property
    def blame_targets_by_node(
        self,
    ) -> Mapping[dag_storage.Node, Set[agent_file_alias.BoundFile]]:
        # Requirement: The session blame targets aggregating blame targets across the active nodes, and blame targets by node mapping each active node to its declared blame targets.
        # Requirement: [NodeConfig] The node config provides the session blame targets by node, which are bound files eligible for defect attribution mapped by session node.
        self._sync_cache()
        return {
            pni.node: set(pni.blame_targets) for pni in self._active_per_node_infos()
        }

    @property
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        # Requirement: The session verification checks aggregating verification checks across the active nodes, and verification checks by node mapping each active node to its verification checks.
        # Requirement: [NodeConfig] The node config provides the session verification checks evaluated during session advancement.
        self._sync_cache()
        res: List[agent_node_config.VerificationCheck] = []
        for pni in self._active_per_node_infos():
            res.extend(pni.verification_checks)
        return res

    @property
    def verification_checks_by_node(
        self,
    ) -> Mapping[dag_storage.Node, Sequence[agent_node_config.VerificationCheck]]:
        # Requirement: The session verification checks aggregating verification checks across the active nodes, and verification checks by node mapping each active node to its verification checks.
        # Requirement: [NodeConfig] The node config provides the session verification checks by node evaluated for each session node.
        self._sync_cache()
        return {
            pni.node: tuple(pni.verification_checks)
            for pni in self._active_per_node_infos()
        }

    @property
    def src_file_alias_by_node(self) -> Mapping[dag_storage.Node, str]:
        # Requirement: The session src file alias by node mapping each active node to the relative path of its declared source file alias.
        # Requirement: [NodeConfig] The node config provides the session src file alias by node, mapping each session node to the relative path of its declared source file alias.
        self._sync_cache()
        res: Dict[dag_storage.Node, str] = {}
        for pni in self._active_per_node_infos():
            if pni.src_file_alias is not None:
                res[pni.node] = pni.src_file_alias
        return res

    @property
    def verification_success_message(self) -> Optional[str]:
        # Requirement: The session verification success message from the active node when the session contains exactly one node.
        # Requirement: [NodeConfig] The node config provides the session verification success message, exposing informative verification feedback when configured.
        self._sync_cache()
        infos = self._active_per_node_infos()
        if len(infos) == 1:
            return infos[0].verification_success_message
        return None

    @property
    def feedback(self) -> Sequence[str]:
        # Requirement: The session feedback combining feedback messages retrieved from graph storage across the active nodes.
        # Requirement: [NodeConfig] The node config provides the session feedback, exposing incoming feedback delivered to the node when present.
        self._sync_cache()
        res: List[str] = []
        for pni in self._active_per_node_infos():
            res.extend(pni.feedback)
        return tuple(res)


_EXECROOT_PATTERN: re.Pattern[str] = re.compile(
    r"/(?:[^\s:;\"\'`()<>{}\[\]/]+/)*execroot/[^\s:;\"\'`()<>{}\[\]/]+/"
)


class AliasManager(agent_file_alias.AliasManager, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._aliases: Dict[str, agent_file_alias.FileAlias] = {}
        self._short_name_to_aliases: Dict[str, List[agent_file_alias.BoundFile]] = {}
        self._paths: Dict[str, str] = {}
        self._masking_patterns: List[Tuple[re.Pattern[str], str]] = []
        self._cached_version: Optional[int] = None
        env_root = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
        root_path = env_root if env_root and os.path.isabs(env_root) else os.getcwd()
        self._workspace_root: file_paths.WorkspaceRoot = _make_host_path(
            file_paths.WorkspaceRoot, os.path.normpath(root_path)
        )

    def initialize(self) -> None:
        self._sync_cache()

    def _sync_cache(self) -> None:
        try:
            role_cfg = get_singleton(agent_node_config.RoleConfig)
            n_cfg = get_singleton(agent_node_config.NodeConfig)
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
            return

        if role_cfg.version == self._cached_version:
            return

        self._aliases.clear()
        self._paths.clear()
        self._short_name_to_aliases.clear()
        self._masking_patterns.clear()

        patterns: List[Tuple[re.Pattern[str], str]] = []
        declared_files = n_cfg.read_write_files | n_cfg.read_only_files
        for f in sorted(
            declared_files,
            key=lambda x: len(x.workspace_path.path),
            reverse=True,
        ):
            self._aliases[f.relative_path] = f
            norm_ws = os.path.normpath(f.workspace_path.path)
            abs_path = os.path.normpath(
                os.path.join(self._workspace_root.path, norm_ws)
            )
            self._paths[abs_path] = f.relative_path
            self._paths[norm_ws] = f.relative_path
            escaped = re.escape(norm_ws)
            pat = re.compile(
                r"/?(?:[^\s:;\"\'`()<>{}\[\]/]+/)*"
                + escaped
                + r"(?=[:\s;\"\'`()<>{}\[\]]|$)"
            )
            patterns.append((pat, f.relative_path))

        short_names: Dict[str, List[agent_file_alias.BoundFile]] = {}
        for f in declared_files:
            basename = os.path.basename(f.relative_path)
            short_names.setdefault(basename, []).append(f)
        self._short_name_to_aliases = short_names

        self._masking_patterns = patterns

        if n_cfg.guide_file is not None:
            self._aliases[n_cfg.guide_file.relative_path] = n_cfg.guide_file

        self._cached_version = role_cfg.version

    @property
    def actual_type(self) -> Type[agent_file_alias.FileAlias]:
        return agent_file_alias.FileAlias

    @property
    def wire_type(self) -> Type[str]:
        return str

    def convert(self, wire_value: str) -> agent_file_alias.FileAlias:
        # Requirement: Converting a wire type string produces the matching file alias if its relative path is found, or if its short name unambiguously resolves to a single declared bound file, and produces an unbound file if the relative path is not found or is ambiguous.
        self._sync_cache()
        if wire_value in self._aliases:
            return self._aliases[wire_value]
        matches = self._short_name_to_aliases.get(wire_value)
        if matches is not None and len(matches) == 1:
            return matches[0]
        return agent_file_alias.UnboundFile(relative_path=wire_value)

    def sanitize_text(self, text: str) -> str:
        # Requirement: The alias manager sanitizes output text by masking occurrences of each file's relative workspace path and any preceding path prefix with its relative path, using performant regular expression patterns that disallow directory separators within prefix segments to prevent catastrophic backtracking, stripping workspace root path prefixes, and stripping execution root path prefixes.
        self._sync_cache()
        res = text
        for pattern, rel_path in self._masking_patterns:
            res = pattern.sub(rel_path, res)
        for host_path, rel_path in self._paths.items():
            if host_path in res:
                res = res.replace(host_path, rel_path)
        if self._workspace_root and self._workspace_root.path:
            ws_root_slash = self._workspace_root.path.rstrip("/") + "/"
            if ws_root_slash in res:
                res = res.replace(ws_root_slash, "")
            if self._workspace_root.path in res:
                res = res.replace(self._workspace_root.path, "")
        res = _EXECROOT_PATTERN.sub("", res)
        return res

    @property
    def workspace_root(self) -> file_paths.WorkspaceRoot:
        return self._workspace_root


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        NodeConfig,
        keys=[NodeConfig, agent_node_config.NodeConfig],
        tier=agent_session,
    )
    reg.register_singleton(
        AliasManager,
        keys=[
            AliasManager,
            agent_file_alias.AliasManager,
            tool_provider.ParameterType,
            tool_provider.ParameterConverter,
        ],
        tier=agent_session,
    )
