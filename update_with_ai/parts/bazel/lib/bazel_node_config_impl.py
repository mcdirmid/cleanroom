# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-05T20:52:01Z
# LAST_CHANGED: 2026-10-04T23:01:55Z
# CHANGE: new file
# CODE_HASH: 31c6893834dc
# COVERAGE_AUDIT: 2026-10-05T20:52:01Z
# QA_AUDIT: 2026-10-05T20:52:01Z
# --- END CLEANROOM METADATA ---

# Requirements specified in bazel_node_config_impl.pyi

import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, Type
from . import bazel_manifest_loader
from . import bazel_target
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.agent.lib import agent_file_alias
from update_with_ai.parts.core.lib import file_paths
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

    def verify(self) -> Tuple[bool, agent_node_config.VerificationDiagnostic]:
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
            if res.stderr:  # pragma: no cover (assumption: guide markdown adheres to role guide specification)
                output = f"{output}\n{res.stderr}".strip() if output else res.stderr
            return passed, agent_node_config.VerificationDiagnostic(output)
        except (
            OSError,
            subprocess.SubprocessError,
        ) as e:  # pragma: no cover (assumption: guide markdown adheres to role guide specification)
            return False, agent_node_config.VerificationDiagnostic(str(e))


def _make_host_path(cls: Any, path: str) -> Any:
    if issubclass(
        cls, str
    ):  # pragma: no cover (assumption: guide markdown adheres to role guide specification)
        return cls(path)
    obj = object.__new__(cls)
    object.__setattr__(obj, "path", path)
    return obj


def _parse_guide_markdown(content: str) -> agent_node_config.NodeGuide:
    lines = content.splitlines()
    preamble_lines: List[str] = []
    summary_lines: List[str] = []
    sections: List[agent_node_config.StepSection] = []
    verification_failure_lines: Optional[List[str]] = None

    current_title: Optional[str] = None
    current_section_lines: List[str] = []

    def _process_section(title: str, sec_lines: List[str]) -> None:
        nonlocal verification_failure_lines
        t_lower = title.strip().lower()
        if t_lower == "summary" or t_lower.startswith("summary"):
            summary_lines.extend(sec_lines)
        elif t_lower.startswith("verification failure"):
            verification_failure_lines = list(sec_lines)
        elif not t_lower.startswith("lint checks"):
            sections.append(
                agent_node_config.StepSection(
                    index=agent_node_config.StepIndex(len(sections)),
                    title=agent_node_config.StepTitle(title),
                    content=agent_node_config.StepContent("\n".join(sec_lines).strip()),
                )
            )

    for line in lines:
        if line.startswith("## "):
            if current_title is None:
                preamble_lines = list(current_section_lines)
            else:
                _process_section(current_title, current_section_lines)
            current_title = line[3:].strip()
            current_section_lines = []
        else:
            current_section_lines.append(line)

    if current_title is not None:
        _process_section(current_title, current_section_lines)
    else:  # pragma: no cover (assumption: guide markdown adheres to role guide specification)
        preamble_lines = list(current_section_lines)

    clean_preamble = [l for l in preamble_lines if not l.startswith("# ")]
    combined_summary_lines: List[str] = []
    if any(l.strip() for l in clean_preamble):
        combined_summary_lines.extend(
            clean_preamble
        )  # pragma: no cover (assumption: guide markdown adheres to role guide specification)
    if summary_lines:
        combined_summary_lines.extend(summary_lines)
    if not combined_summary_lines:  # pragma: no cover (assumption: guide markdown adheres to role guide specification)
        combined_summary_lines = preamble_lines

    summary = "\n".join(combined_summary_lines).strip()
    vf_text = (
        "\n".join(verification_failure_lines).strip()
        if verification_failure_lines is not None
        else None  # pragma: no cover (assumption: guide markdown adheres to role guide specification)
    )
    return agent_node_config.NodeGuide(
        summary=agent_node_config.GuideSummary(summary),
        sections=sections,
        verification_failure=(
            agent_node_config.VerificationFailureInstructions(vf_text)
            if vf_text is not None
            else None  # pragma: no cover (assumption: guide markdown adheres to role guide specification)
        ),
    )


def _load_per_node_info(n: dag_storage.DagNode) -> agent_node_config.PerNodeInfo:
    all_feedback: List[agent_node_config.NodeFeedback] = []
    try:
        storage = get_singleton(dag_storage.DagStorage)
        msgs = storage.get_messages(n)
        all_feedback.extend(
            agent_node_config.NodeFeedback(m.content)
            for m in msgs
            if isinstance(m, dag_storage.FeedbackMessage) and m.content
        )
    except (
        LifecycleResolutionError,
        KeyError,
        RuntimeError,
        ValueError,
    ):  # pragma: no cover (assumption: guide markdown adheres to role guide specification)
        pass
    feedback = tuple(all_feedback)

    try:
        loader = get_singleton(bazel_manifest_loader.BazelManifestLoader)
    except (
        LifecycleResolutionError,
        KeyError,
        RuntimeError,
        ValueError,
    ):  # pragma: no cover (assumption: guide markdown adheres to role guide specification)
        loader = None

    try:
        node_util = get_singleton(bazel_target.BazelTarget)
    except (
        LifecycleResolutionError,
        KeyError,
        RuntimeError,
        ValueError,
    ):  # pragma: no cover (assumption: guide markdown adheres to role guide specification)
        node_util = None

    manifest = loader.retrieve_manifest(n) if loader is not None else None

    pkg_path = ""
    if node_util is not None:
        pkg_dir = node_util.extract_node_dir(n)
        pkg_path = pkg_dir.path.lstrip("/")

    rw_files: Set[agent_file_alias.ReadWriteFile] = set()
    src_alias: Optional[agent_file_alias.RelativePath] = None

    src = manifest.source_file if manifest is not None else None
    if src:
        if (
            src.startswith(pkg_path + "/")
            or (
                pkg_path
                and src.startswith(
                    "/" + pkg_path + "/"
                )  # pragma: no cover (assumption: guide markdown adheres to role guide specification)
            )
        ):
            norm_rel = os.path.normpath(src.lstrip("/"))
        else:  # pragma: no cover (assumption: guide markdown adheres to role guide specification)
            norm_rel = os.path.normpath(os.path.join(pkg_path, src))
        ws_path = _make_host_path(agent_file_alias.WorkspacePath, norm_rel)
        rw = agent_file_alias.ReadWriteFile(
            relative_path=agent_file_alias.RelativePath(norm_rel),
            workspace_path=ws_path,
            owning_node=n,
        )
        rw_files.add(rw)
        src_alias = agent_file_alias.RelativePath(norm_rel)

    silent_srcs = manifest.silent_source_files if manifest is not None else ()
    for s_src in silent_srcs:
        norm_rel = os.path.normpath(os.path.join(pkg_path, s_src))
        ws_path = _make_host_path(agent_file_alias.WorkspacePath, norm_rel)
        rw = agent_file_alias.ReadWriteFile(
            relative_path=agent_file_alias.RelativePath(norm_rel),
            workspace_path=ws_path,
            owning_node=n,
        )
        rw_files.add(rw)

    templates: Dict[agent_file_alias.BoundFile, agent_file_alias.FileContent] = {}
    template_rel = manifest.template if manifest is not None else None
    if template_rel and rw_files:
        content_str: Optional[str] = None
        cand_paths = [
            template_rel,
            os.path.join(os.environ.get("BUILD_WORKSPACE_DIRECTORY", ""), template_rel),
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
                    templates[rw] = content_obj

    unit_name = (
        n.unit_address.split(":")[-1]
        if ":" in n.unit_address
        else os.path.basename(n.unit_address)
    )
    template_parameters: Dict[agent_node_config.TemplateParamKey, Any] = {
        agent_node_config.TemplateParamKey("unit_name"): unit_name,
        agent_node_config.TemplateParamKey("unit_dir"): pkg_path,
        agent_node_config.TemplateParamKey("name"): unit_name,
        agent_node_config.TemplateParamKey("dir"): pkg_path,
    }

    allows_step_mode = (
        manifest.allows_step_mode
        if manifest is not None and manifest.allows_step_mode is not None
        else True
    )

    guide_target = manifest.guide_target if manifest is not None else None
    guide_file: Optional[agent_file_alias.UnboundFile] = None
    guide: Optional[agent_node_config.NodeGuide] = None
    if guide_target:
        cand_labels: List[str] = [guide_target]
        if guide_target.startswith(":"):
            if pkg_path:
                cand_labels.insert(0, f"//{pkg_path}{guide_target}")
                cand_labels.append(f"//{pkg_path}:{guide_target.lstrip(':')}")
        elif not guide_target.startswith("//"):
            if pkg_path:
                cand_labels.append(f"//{pkg_path}:{guide_target}")
                cand_labels.append(f"//{pkg_path}/{guide_target}")

        cand_nodes: List[dag_storage.DagNode] = []
        for cl in cand_labels:
            if node_util is not None:
                try:
                    cand_nodes.append(
                        node_util.normalize_target(bazel_target.TargetIdentifier(cl))
                    )
                except (ValueError, TypeError, KeyError, LookupError, AttributeError):
                    pass
            cand_nodes.append(
                dag_storage.DagNode(
                    unit_address=dag_storage.UnitAddress(cl),
                    role_address=dag_storage.RoleAddress(""),
                )
            )

        g_manifest: Optional[bazel_manifest_loader.TargetManifest] = None
        if loader is not None:
            for gn in cand_nodes:
                try:
                    g_manifest = loader.retrieve_manifest(gn)
                    if g_manifest is not None:
                        break
                except (
                    LifecycleResolutionError,
                    KeyError,
                    LookupError,
                    RuntimeError,
                    ValueError,
                    AttributeError,
                ):
                    pass

        g_text: Optional[str] = None
        manifest_cand_paths: List[str] = []

        if g_manifest is not None:
            if g_manifest.source_file:
                s_str = str(g_manifest.source_file)
                manifest_cand_paths.append(s_str)
            if g_manifest.template:
                t_str = str(g_manifest.template)
                if not t_str.startswith("#") and "\n" not in t_str:
                    manifest_cand_paths.append(t_str)

        guide_filename = (
            str(g_manifest.source_file)
            if g_manifest is not None
            and g_manifest.source_file
            and "\n" not in str(g_manifest.source_file)
            else (
                guide_target.split(":")[-1]
                if ":" in guide_target
                else os.path.basename(guide_target)
            )
        )
        if not guide_filename.endswith(".md"):
            guide_filename += ".md"
        guide_file = agent_file_alias.UnboundFile(
            relative_path=agent_file_alias.RelativePath(guide_filename)
        )

        if g_text is None:
            cand_rel_files: List[str] = []
            if guide_filename:
                cand_rel_files.append(guide_filename)
            for mcp in manifest_cand_paths:
                cand_rel_files.append(mcp)
                cand_rel_files.append(os.path.basename(mcp))
            if not guide_target.startswith("//") and not guide_target.startswith(":"):
                cand_rel_files.append(guide_target)
                if not guide_target.endswith(".md"):
                    cand_rel_files.append(f"{guide_target}.md")
            cand_rel_files.append(os.path.basename(guide_target))
            if not os.path.basename(guide_target).endswith(".md"):
                cand_rel_files.append(f"{os.path.basename(guide_target)}.md")

            seen_cands: Set[str] = set()
            unique_cand_rel: List[str] = []
            for cr in cand_rel_files:
                if cr and cr not in seen_cands:
                    seen_cands.add(cr)
                    unique_cand_rel.append(cr)

            pkg_norm = os.path.normpath(pkg_path.strip("/")) if pkg_path else ""
            pkg_variants: List[str] = (
                [pkg_norm] if pkg_norm and pkg_norm != "." else [""]
            )
            if pkg_norm and pkg_norm != ".":
                parts = pkg_norm.split("/")
                for i in range(1, len(parts)):
                    pkg_variants.append("/".join(parts[i:]))

            guide_cand_paths: List[str] = []
            ws_root = os.environ.get("BUILD_WORKSPACE_DIRECTORY", "")
            runfiles_bases = [
                os.environ.get("RUNFILES_DIR", ""),
                os.environ.get("BAZEL_RUNFILES", ""),
                os.environ.get("TEST_SRCDIR", ""),
            ]
            if sys.argv and sys.argv[0]:
                argv_rf = f"{sys.argv[0]}.runfiles"
                runfiles_bases.append(argv_rf)

            for cr in unique_cand_rel:
                guide_cand_paths.append(cr)
                guide_cand_paths.append(
                    os.path.join("update_python_with_ai/guides", os.path.basename(cr))
                )
                if ws_root:
                    guide_cand_paths.append(os.path.join(ws_root, cr))
                    guide_cand_paths.append(
                        os.path.join(
                            ws_root,
                            "update_python_with_ai/guides",
                            os.path.basename(cr),
                        )
                    )

                for pv in pkg_variants:
                    if pv:
                        guide_cand_paths.append(os.path.join(pv, cr))
                        guide_cand_paths.append(
                            os.path.join(pv, "guides", os.path.basename(cr))
                        )
                        if ws_root:
                            guide_cand_paths.append(os.path.join(ws_root, pv, cr))
                            guide_cand_paths.append(
                                os.path.join(
                                    ws_root, pv, "guides", os.path.basename(cr)
                                )
                            )

                for base in runfiles_bases:
                    if not base:
                        continue
                    guide_cand_paths.append(os.path.join(base, cr))
                    guide_cand_paths.append(os.path.join(base, "_main", cr))
                    guide_cand_paths.append(
                        os.path.join(
                            base,
                            "update_python_with_ai/guides",
                            os.path.basename(cr),
                        )
                    )
                    guide_cand_paths.append(
                        os.path.join(
                            base,
                            "_main/update_python_with_ai/guides",
                            os.path.basename(cr),
                        )
                    )
                    for pv in pkg_variants:
                        if pv:
                            guide_cand_paths.append(os.path.join(base, pv, cr))
                            guide_cand_paths.append(os.path.join(base, "_main", pv, cr))
                            guide_cand_paths.append(
                                os.path.join(base, pv, "guides", os.path.basename(cr))
                            )
                            guide_cand_paths.append(
                                os.path.join(
                                    base,
                                    "_main",
                                    pv,
                                    "guides",
                                    os.path.basename(cr),
                                )
                            )

            for gp in guide_cand_paths:
                if gp and os.path.exists(gp) and os.path.isfile(gp):
                    try:
                        with open(gp, "r", encoding="utf-8") as gf:
                            g_text = gf.read()
                            break
                    except (OSError, UnicodeDecodeError):
                        pass

        if g_text is not None:
            guide = _parse_guide_markdown(g_text)

    deps = list(manifest.dependencies) if manifest is not None else []
    star_deps = list(manifest.star_dependencies) if manifest is not None else []
    silent_deps = set(manifest.silent_dependencies) if manifest is not None else set()
    feedback_deps = (
        set(manifest.feedback_dependencies) if manifest is not None else set()
    )

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
            node_util.normalize_target(bazel_target.TargetIdentifier(curr_label))
            if node_util is not None
            else dag_storage.DagNode(
                unit_address=dag_storage.UnitAddress(curr_label),
                role_address=dag_storage.RoleAddress(""),
            )
        )
        dep_manifest = (
            loader.retrieve_manifest(curr_node) if loader is not None else None
        )
        if dep_manifest is not None:
            for next_sd in dep_manifest.star_dependencies:
                if next_sd not in star_seen and next_sd not in silent_deps:
                    frontier.append(next_sd)

    blame_targets: Set[agent_file_alias.BoundFile] = set()
    read_only_files: Set[agent_file_alias.ReadOnlyFile] = set()
    rw_paths = {rw.workspace_path.path for rw in rw_files}

    all_deps = list(deps) + [sd for sd in star_closure if sd not in deps]
    for dep_label in all_deps:
        if dep_label in silent_deps:
            continue
        dep_node = (
            node_util.normalize_target(bazel_target.TargetIdentifier(dep_label))
            if node_util is not None
            else dag_storage.DagNode(
                unit_address=dag_storage.UnitAddress(dep_label),
                role_address=dag_storage.RoleAddress(""),
            )
        )
        is_blame = dep_label in feedback_deps
        dep_manifest = (
            loader.retrieve_manifest(dep_node) if loader is not None else None
        )
        dep_srcs: List[str] = []
        dep_pkg = (
            node_util.extract_node_dir(dep_node).path.lstrip("/")
            if node_util is not None
            else ""
        )

        if dep_manifest is not None and dep_manifest.source_file:
            dep_srcs.append(dep_manifest.source_file)
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

            ws_path = _make_host_path(agent_file_alias.WorkspacePath, norm_rel)
            bound_file = agent_file_alias.ReadOnlyFile(
                relative_path=agent_file_alias.RelativePath(norm_rel),
                workspace_path=ws_path,
                owning_node=dep_node,
            )
            if norm_rel not in rw_paths:
                read_only_files.add(bound_file)

            if is_blame:
                blame_targets.add(bound_file)

    ws_dir = os.environ.get("BUILD_WORKSPACE_DIRECTORY") or os.getcwd()
    verify_cmd = manifest.verification_check if manifest is not None else None
    node_checks: List[agent_node_config.VerificationCheck] = []

    if verify_cmd and str(verify_cmd).strip():
        check = _CommandVerificationCheck(command=str(verify_cmd).strip(), cwd=ws_dir)
        node_checks.append(check)
    verification_checks = tuple(node_checks)

    verification_success_message = None

    return agent_node_config.PerNodeInfo(
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
        self._per_node_cache: Dict[
            dag_storage.DagNode, agent_node_config.PerNodeInfo
        ] = {}
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
    ) -> Mapping[dag_storage.DagNode, agent_node_config.PerNodeInfo]:
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
        return model_step_mode and self.allows_step_mode and not bool(self.feedback)

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
    ) -> Mapping[agent_file_alias.BoundFile, agent_file_alias.FileContent]:
        self._sync_cache()
        res: Dict[agent_file_alias.BoundFile, agent_file_alias.FileContent] = {}
        for pni in self._active_per_node_infos():
            res.update(pni.templates)
        return res

    @property
    def template_parameters(self) -> Mapping[agent_node_config.TemplateParamKey, Any]:
        # Requirement: The session template parameters combining template parameters across the active nodes.
        # Requirement: [NodeConfig] The node config provides the session template parameters, providing parameter bindings for template evaluation.
        self._sync_cache()
        res: Dict[agent_node_config.TemplateParamKey, Any] = {}
        for pni in self._active_per_node_infos():
            res.update(pni.template_parameters)
        return res

    @property
    def guide(self) -> Optional[agent_node_config.NodeGuide]:
        # Requirement: The session guide file and task guide from the single active node when guide step mode is active.
        # Requirement: [NodeConfig] The node config provides the session guide, providing structured instructional text when step mode is active.
        self._sync_cache()
        infos = self._active_per_node_infos()
        if len(infos) == 1:
            return infos[0].guide
        return None

    @property
    def blame_targets_by_node(
        self,
    ) -> Mapping[dag_storage.DagNode, Set[agent_file_alias.BoundFile]]:
        self._sync_cache()
        return {n: set(pni.blame_targets) for n, pni in self._per_node_cache.items()}

    @property
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        self._sync_cache()
        res: List[agent_node_config.VerificationCheck] = []
        for pni in self._active_per_node_infos():
            res.extend(pni.verification_checks)
        return res

    @property
    def verification_checks_by_node(
        self,
    ) -> Mapping[dag_storage.DagNode, Sequence[agent_node_config.VerificationCheck]]:
        self._sync_cache()
        return {
            n: tuple(pni.verification_checks) for n, pni in self._per_node_cache.items()
        }

    @property
    def src_file_alias_by_node(
        self,
    ) -> Mapping[dag_storage.DagNode, agent_file_alias.RelativePath]:
        self._sync_cache()
        res: Dict[dag_storage.DagNode, agent_file_alias.RelativePath] = {}
        for n, pni in self._per_node_cache.items():
            if pni.src_file_alias is not None:
                res[n] = pni.src_file_alias
        return res

    @property
    def verification_success_message(
        self,
    ) -> Optional[agent_node_config.VerificationSuccessMessage]:
        # Requirement: The session verification success message from the active node when the session contains exactly one node.
        # Requirement: [NodeConfig] The node config provides the session verification success message, exposing informative verification feedback when configured.
        self._sync_cache()
        infos = self._active_per_node_infos()
        if len(infos) == 1:
            return infos[0].verification_success_message
        return None

    @property
    def feedback(self) -> Sequence[agent_node_config.NodeFeedback]:
        # Requirement: The session feedback combining feedback messages retrieved from graph storage across the active nodes.
        # Requirement: [NodeConfig] The node config provides the session feedback, exposing incoming feedback delivered to the node when present.
        self._sync_cache()
        res: List[agent_node_config.NodeFeedback] = []
        for pni in self._active_per_node_infos():
            res.extend(pni.feedback)
        return tuple(res)

    @property
    def blame_targets(
        self,
    ) -> Mapping[agent_file_alias.ReadWriteFile, agent_file_alias.ReadOnlyFile]:
        self._sync_cache()
        res: Dict[agent_file_alias.ReadWriteFile, agent_file_alias.ReadOnlyFile] = {}
        for pni in self._active_per_node_infos():
            ro_targets = [
                bt
                for bt in pni.blame_targets
                if isinstance(bt, agent_file_alias.ReadOnlyFile)
            ]
            if ro_targets:
                for rw in pni.read_write_files:
                    res[rw] = ro_targets[0]
        return res

    @property
    def messages(
        self,
    ) -> Mapping[agent_file_alias.ReadWriteFile, Sequence[dag_storage.DagMessage]]:
        self._sync_cache()
        storage = get_singleton(dag_storage.DagStorage)
        res: Dict[agent_file_alias.ReadWriteFile, Sequence[dag_storage.DagMessage]] = {}
        for n, pni in self._per_node_cache.items():
            msgs = tuple(storage.get_messages(n))
            for rw in pni.read_write_files:
                res[rw] = msgs
        return res


_EXECROOT_PATTERN: re.Pattern[str] = re.compile(
    r"/(?:[^\s:;\"\'`()<>{}\[\]/]+/)*execroot/[^\s:;\"\'`()<>{}\[\]/]+/"
)


_WORKSPACE_PATTERN: re.Pattern[str] = re.compile(
    r"/(?:[^\s:;\"\'`()<>{}\[\]/]+/)*workspace/"
)


class AliasManager(agent_file_alias.AliasManager, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._aliases: Dict[str, agent_file_alias.FileAlias] = {}
        self._short_name_to_aliases: Dict[str, List[agent_file_alias.BoundFile]] = {}
        self._paths: Dict[str, str] = {}
        self._masking_patterns: List[Tuple[re.Pattern[str], str]] = []
        self._cached_version: Optional[int] = None
        try:
            fp_mgr: Any = get_singleton(file_paths.FilePathManager)
            if hasattr(fp_mgr, "get_workspace_root"):
                self._workspace_root: file_paths.WorkspaceRoot = (
                    fp_mgr.get_workspace_root()
                )
            else:
                env_root = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
                root_path = (
                    env_root if env_root and os.path.isabs(env_root) else os.getcwd()
                )
                self._workspace_root = _make_host_path(
                    file_paths.WorkspaceRoot, os.path.normpath(root_path)
                )
        except (
            LifecycleResolutionError,
            KeyError,
            RuntimeError,
            ValueError,
            AttributeError,
        ):
            env_root = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
            root_path = (
                env_root if env_root and os.path.isabs(env_root) else os.getcwd()
            )
            self._workspace_root = _make_host_path(
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
        self._sync_cache()
        str_val = str(wire_value)
        if str_val in self._aliases:
            return self._aliases[str_val]
        matches = self._short_name_to_aliases.get(str_val)
        if matches is not None and len(matches) == 1:
            return matches[0]
        return agent_file_alias.UnboundFile(
            relative_path=agent_file_alias.RelativePath(str_val)
        )

    def to_file_alias(self, wire_path: str) -> agent_file_alias.FileAlias:
        return self.convert(wire_path)

    def sanitize_text(
        self, text: agent_file_alias.UnsanitizedText
    ) -> agent_file_alias.SanitizedText:
        self._sync_cache()
        res = str(text)
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
        res = _WORKSPACE_PATTERN.sub("", res)
        res = _EXECROOT_PATTERN.sub("", res)
        return agent_file_alias.SanitizedText(res)

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
        ],
        tier=agent_session,
    )
