import json
import os
import re
import subprocess
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, Type
from . import bazel_manifest_loader
from . import bazel_target
from update_with_ai.parts.dag.lib import dag_node_cleaner
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.agent.lib import agent_file_alias
from . import file_paths
from update_with_ai.parts.agent.lib import agent_config
from update_with_ai.parts.agent.lib import agent_node_config
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
        try:
            res = subprocess.run(
                self._command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self._cwd,
                env=env,
            )
            passed = res.returncode == 0
            output = res.stdout
            if res.stderr:
                output = f"{output}\n{res.stderr}".strip() if output else res.stderr
            return passed, output
        except (subprocess.SubprocessError, OSError) as e:
            return False, str(e)


class NodeConfig(agent_node_config.NodeConfig, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        self._read_only_files: Set[agent_file_alias.BoundFile] = set()
        self._read_write_files: Set[agent_file_alias.BoundFile] = set()
        self._templates: Set[
            Tuple[agent_file_alias.BoundFile, agent_file_alias.FileContent]
        ] = set()
        self._template_parameters: Dict[str, Any] = {}
        self._allows_step_mode: bool = True
        self._is_step_mode: bool = False
        self._guide_file: Optional[agent_file_alias.UnboundFile] = None
        self._guide: Optional[agent_node_config.Guide] = None
        self._blame_targets: Set[agent_file_alias.BoundFile] = set()
        self._verification_checks: List[agent_node_config.VerificationCheck] = []
        self._verification_success_message: Optional[str] = None
        self._feedback: Tuple[str, ...] = ()

    def initialize(self) -> None:
        try:
            cleaned_node = get_singleton(dag_node_cleaner.CleanedNode)
            node = cleaned_node.node
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
            return

        try:
            storage = get_singleton(dag_storage.DagStorage)
            msgs = storage.get_messages(node)
            self._feedback = tuple(
                m.content
                for m in msgs
                if isinstance(m, dag_storage.Feedback) and m.content
            )
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
            self._feedback = ()

        loader = get_singleton(bazel_manifest_loader.BazelManifestLoader)
        manifest_raw = loader.get_manifest(node)
        if manifest_raw is None:
            return

        node_util = get_singleton(bazel_target.BazelTarget)
        pkg_dir = node_util.extract_directory(node)
        pkg_path = pkg_dir.path.lstrip("/")

        try:
            data = json.loads(str(manifest_raw))
        except (json.JSONDecodeError, ValueError, TypeError):
            return

        # 1. Declared source files -> read_write_files
        src = data.get("src")
        if src:
            norm_rel = os.path.normpath(os.path.join(pkg_path, src))
            ws_path = _make_host_path(agent_file_alias.WorkspacePath, norm_rel)
            short_name = os.path.basename(norm_rel)
            rw = agent_file_alias.ReadWriteFile(
                short_name=short_name, workspace_path=ws_path, owning_node=node
            )
            self._read_write_files.add(rw)

        # Silent sources -> read_write_files
        silent_srcs = data.get("silent_srcs", [])
        for s_src in silent_srcs:
            norm_rel = os.path.normpath(os.path.join(pkg_path, s_src))
            ws_path = _make_host_path(agent_file_alias.WorkspacePath, norm_rel)
            short_name = os.path.basename(norm_rel)
            rw = agent_file_alias.ReadWriteFile(
                short_name=short_name, workspace_path=ws_path, owning_node=node
            )
            self._read_write_files.add(rw)

        # 2. Templates
        template_rel = data.get("template")
        if template_rel and self._read_write_files:
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
                for rw in self._read_write_files:
                    self._templates.add((rw, content_obj))

        # 2.5 Template parameters
        raw_params = data.get("template_parameters")
        if isinstance(raw_params, dict):
            self._template_parameters = dict(raw_params)
        elif isinstance(raw_params, str):
            try:
                decoded = json.loads(raw_params)
                if isinstance(decoded, dict):
                    self._template_parameters = decoded
            except (json.JSONDecodeError, ValueError):
                pass

        # 3. Guide
        guide_target = data.get("guide")
        m_cfg: Optional[agent_config.AgentConfig] = None
        try:
            m_cfg = get_singleton(agent_config.AgentConfig)
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
            pass
        model_step_mode = m_cfg.is_step_mode if m_cfg is not None else False
        allows_step = data.get(
            "allows_step_mode", data.get("step_mode", data.get("step_sections", True))
        )
        self._allows_step_mode = bool(allows_step)
        self._is_step_mode = (
            model_step_mode and self._allows_step_mode and not bool(self._feedback)
        )

        if guide_target and self._is_step_mode:
            guide_filename = (
                guide_target.split(":")[-1]
                if ":" in guide_target
                else os.path.basename(guide_target)
            )
            if not guide_filename.endswith(".md"):
                guide_filename += ".md"
            self._guide_file = agent_file_alias.UnboundFile(short_name=guide_filename)

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
                        self._guide = _parse_guide_markdown(g_text)
                        break
                    except (OSError, UnicodeDecodeError):
                        pass

        # 4. Read-only files from direct deps and transitive star_deps
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
            curr_node = node_util.normalize(curr_label)
            dep_manifest_raw = loader.get_manifest(curr_node)
            if dep_manifest_raw:
                try:
                    dep_data = json.loads(str(dep_manifest_raw))
                    for next_sd in dep_data.get("star_deps", []):
                        if next_sd not in star_seen and next_sd not in silent_deps:
                            frontier.append(next_sd)
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass

        all_deps = list(deps) + [sd for sd in star_closure if sd not in deps]
        for dep_label in all_deps:
            if dep_label in silent_deps:
                continue
            if self._is_step_mode and guide_target and dep_label == guide_target:
                continue

            dep_node = node_util.normalize(dep_label)
            is_blame = dep_label in feedback_deps
            dep_manifest_raw = loader.get_manifest(dep_node)
            dep_srcs: List[str] = []
            dep_pkg = node_util.extract_directory(dep_node).path.lstrip("/")

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
                norm_rel = os.path.normpath(os.path.join(dep_pkg, ds))
                ws_path = _make_host_path(agent_file_alias.WorkspacePath, norm_rel)
                short_name = os.path.basename(norm_rel)
                ro = agent_file_alias.ReadOnlyFile(
                    short_name=short_name, workspace_path=ws_path, owning_node=dep_node
                )
                self._read_only_files.add(ro)
                if is_blame:
                    self._blame_targets.add(ro)

        # 5. Verification checks
        verify_cmd = data.get("verify")
        if verify_cmd and str(verify_cmd).strip():
            ws_dir = os.environ.get("BUILD_WORKSPACE_DIRECTORY") or os.getcwd()
            self._verification_checks.append(
                _CommandVerificationCheck(command=str(verify_cmd).strip(), cwd=ws_dir)
            )

        v_msg = data.get("verification_success_message")
        if v_msg and str(v_msg).strip():
            self._verification_success_message = str(v_msg).strip()

    @property
    def read_only_files(self) -> Set[agent_file_alias.BoundFile]:
        # Requirement: The node config exposes declared direct dependencies and transitive star dependencies resolved across dependency manifests using the bazel manifest loader as the session's read-only files, excluding silent dependencies.
        return self._read_only_files

    @property
    def read_write_files(self) -> Set[agent_file_alias.BoundFile]:
        # Requirement: The node config exposes declared source files and silent source files as read-write files.
        return self._read_write_files

    @property
    def allows_step_mode(self) -> bool:
        # Requirement: The node config exposes whether the node allows step mode from the target node manifest.
        return self._allows_step_mode

    @property
    def is_step_mode(self) -> bool:
        # Requirement: The node config exposes whether step mode is active, enabled when the agent config enables step mode, the node allows step mode, and session feedback is absent.
        return self._is_step_mode

    @property
    def templates(
        self,
    ) -> Set[Tuple[agent_file_alias.BoundFile, agent_file_alias.FileContent]]:
        # Requirement: The node config exposes templates mapping read-write files to initial file content.
        return self._templates

    @property
    def template_parameters(self) -> Mapping[str, Any]:
        # Requirement: The node config exposes declared template parameters from the manifest.
        return self._template_parameters

    @property
    def guide_file(self) -> Optional[agent_file_alias.UnboundFile]:
        # Requirement: The node config exposes the declared guide target as the guide file when step mode is active.
        return self._guide_file

    @property
    def guide(self) -> Optional[agent_node_config.Guide]:
        # Requirement: The node config exposes the declared guide target as the task guide when step mode is active.
        return self._guide

    @property
    def blame_targets(self) -> Set[agent_file_alias.BoundFile]:
        # Requirement: The node config exposes declared feedback dependencies as blame targets mapped to owning dependency nodes.
        return set(self._blame_targets)

    @property
    def verification_checks(self) -> List[agent_node_config.VerificationCheck]:
        # Requirement: The node config exposes declared verification checks from the manifest verification command.
        return list(self._verification_checks)

    @property
    def verification_success_message(self) -> Optional[str]:
        # Requirement: Declared verification success message from the manifest as the session verification success message.
        return self._verification_success_message

    @property
    def feedback(self) -> Sequence[str]:
        # Requirement: Declared feedback messages retrieved from graph storage for the target node as the session feedback.
        return self._feedback


def _make_host_path(cls, path: str):
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


class AliasManager(agent_file_alias.AliasManager, Singleton):
    tier = "agent_session"

    def __init__(self) -> None:
        self._aliases: Dict[str, agent_file_alias.FileAlias] = {}
        self._paths: Dict[str, str] = {}
        self._masking_patterns: List[Tuple[re.Pattern[str], str]] = []
        env_root = os.environ.get("BUILD_WORKSPACE_DIRECTORY")
        root_path = env_root if env_root and os.path.isabs(env_root) else os.getcwd()
        self._workspace_root = _make_host_path(
            file_paths.WorkspaceRoot, os.path.normpath(root_path)
        )

    def initialize(self) -> None:
        try:
            n_cfg = get_singleton(agent_node_config.NodeConfig)
        except (LifecycleResolutionError, KeyError, RuntimeError, ValueError):
            return

        patterns: List[Tuple[re.Pattern[str], str]] = []
        for f in sorted(
            (n_cfg.read_write_files | n_cfg.read_only_files),
            key=lambda x: len(x.workspace_path.path),
            reverse=True,
        ):
            self._aliases[f.short_name] = f
            norm_ws = os.path.normpath(f.workspace_path.path)
            abs_path = os.path.normpath(
                os.path.join(self._workspace_root.path, norm_ws)
            )
            self._paths[abs_path] = f.short_name
            self._paths[norm_ws] = f.short_name
            escaped = re.escape(norm_ws)
            pat = re.compile(
                r"/?(?:[^\s:;\"\'`()<>{}\[\]/]+/)*"
                + escaped
                + r"(?=[:\s;\"\'`()<>{}\[\]]|$)"
            )
            patterns.append((pat, f.short_name))

        self._masking_patterns = patterns

        if n_cfg.guide_file is not None:
            self._aliases[n_cfg.guide_file.short_name] = n_cfg.guide_file

    @property
    def actual_type(self) -> Type:
        return agent_file_alias.FileAlias

    @property
    def wire_type(self) -> tool_provider.WireType:
        return tool_provider.String()

    def convert(self, wire_value: str) -> agent_file_alias.FileAlias:
        # Requirement: The alias manager converts short names to matching file aliases, producing unbound files when unmapped.
        return self._aliases.get(wire_value, agent_file_alias.UnboundFile(wire_value))

    def sanitize_text(self, text: str) -> str:
        # Requirement: The alias manager sanitizes output text by masking occurrences of each file's relative workspace path and any preceding path prefix with its minimal short name, using performant regular expression patterns that disallow directory separators within prefix segments to prevent catastrophic backtracking.
        res = text
        for pattern, short_name in self._masking_patterns:
            res = pattern.sub(short_name, res)
        for host_path, short_name in self._paths.items():
            if host_path in res:
                res = res.replace(host_path, short_name)
        return res

    @property
    def workspace_root(self) -> file_paths.WorkspaceRoot:
        return self._workspace_root


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        NodeConfig,
        keys=[NodeConfig, agent_node_config.NodeConfig],
        tier="agent_session",
    )
    reg.register_singleton(
        AliasManager,
        keys=[
            AliasManager,
            agent_file_alias.AliasManager,
            tool_provider.ParameterConverter,
        ],
        tier="agent_session",
    )
