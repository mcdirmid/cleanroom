# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-06T12:00:00Z
# LAST_CHANGED: 2026-10-06T12:00:00Z
# CHANGE: refactor bazel_node_config_impl under 500 lines
# CODE_HASH: 31c6893834dc
# --- END CLEANROOM METADATA ---

import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, Type
from . import bazel_manifest_loader, bazel_target
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.agent.lib import agent_file_alias, agent_config, agent_node_config
from update_with_ai.parts.agent.lib.agent_session import agent_session
from update_with_ai.parts.core.lib import file_paths
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
                self._command, shell=True, capture_output=True, text=True,
                cwd=self._cwd, env=env, stdin=subprocess.DEVNULL,
            )
            out = res.stdout
            if res.stderr:
                out = f"{out}\n{res.stderr}".strip() if out else res.stderr
            return res.returncode == 0, agent_node_config.VerificationDiagnostic(out)
        except (OSError, subprocess.SubprocessError) as e:
            return False, agent_node_config.VerificationDiagnostic(str(e))


def _make_host_path(cls: Any, path: str) -> Any:
    if issubclass(cls, str):
        return cls(path)
    obj = object.__new__(cls)
    object.__setattr__(obj, "path", path)
    return obj


def _safe_get_singleton(cls: Any) -> Any:
    try:
        return get_singleton(cls)
    except (LifecycleResolutionError, KeyError, RuntimeError, ValueError, AttributeError):
        return None


def _parse_guide_markdown(content: str) -> agent_node_config.NodeGuide:
    lines = content.splitlines()
    preamble_lines, summary_lines, sections = [], [], []
    vf_lines: Optional[List[str]] = None
    curr_title, curr_sec = None, []

    def flush(title: Optional[str], sec: List[str]) -> None:
        nonlocal vf_lines
        if title is None:
            preamble_lines.extend(sec)
            return
        t = title.strip().lower()
        if t == "summary" or t.startswith("summary"):
            summary_lines.extend(sec)
        elif t.startswith("verification failure"):
            vf_lines = list(sec)
        elif not t.startswith("lint checks"):
            sections.append(agent_node_config.StepSection(
                index=agent_node_config.StepIndex(len(sections)),
                title=agent_node_config.StepTitle(title),
                content=agent_node_config.StepContent("\n".join(sec).strip()),
            ))

    for line in lines:
        if line.startswith("## "):
            flush(curr_title, curr_sec)
            curr_title, curr_sec = line[3:].strip(), []
        else:
            curr_sec.append(line)
    flush(curr_title, curr_sec)

    clean_preamble = [l for l in preamble_lines if not l.startswith("# ")]
    combined = (clean_preamble if any(l.strip() for l in clean_preamble) else []) + summary_lines
    summary = "\n".join(combined or preamble_lines).strip()
    vf = agent_node_config.VerificationFailureInstructions("\n".join(vf_lines).strip()) if vf_lines is not None else None
    return agent_node_config.NodeGuide(
        summary=agent_node_config.GuideSummary(summary),
        sections=sections,
        verification_failure=vf,
    )


def _read_cand_file(candidates: Sequence[str]) -> Optional[str]:
    for p in candidates:
        if p and os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return f.read()
            except (OSError, UnicodeDecodeError):
                pass
    return None


def _search_paths(rel_paths: Sequence[str], pkg_path: str = "") -> List[str]:
    ws_root = os.environ.get("BUILD_WORKSPACE_DIRECTORY", "")
    rf_bases = [b for b in [os.environ.get("RUNFILES_DIR", ""), os.environ.get("BAZEL_RUNFILES", ""),
                            os.environ.get("TEST_SRCDIR", ""), f"{sys.argv[0]}.runfiles" if sys.argv and sys.argv[0] else ""] if b]
    pkg_norm = os.path.normpath(pkg_path.strip("/")) if pkg_path else ""
    pvs = [pkg_norm] if pkg_norm and pkg_norm != "." else [""]
    if pkg_norm and pkg_norm != ".":
        parts = pkg_norm.split("/")
        pvs.extend("/".join(parts[i:]) for i in range(1, len(parts)))

    res, seen = [], set()

    def add(p: str) -> None:
        if p and p not in seen:
            seen.add(p); res.append(p)

    for rp in rel_paths:
        if not rp:
            continue
        bfn = os.path.basename(rp)
        for c in [rp, os.path.join("update_python_with_ai/guides", bfn)]:
            add(c)
            if ws_root: add(os.path.join(ws_root, c))
        for pv in pvs:
            if pv:
                for c in [os.path.join(pv, rp), os.path.join(pv, "guides", bfn)]:
                    add(c)
                    if ws_root: add(os.path.join(ws_root, c))
        for b in rf_bases:
            for c in [os.path.join(b, rp), os.path.join(b, "_main", rp),
                      os.path.join(b, "update_python_with_ai/guides", bfn),
                      os.path.join(b, "_main/update_python_with_ai/guides", bfn)]:
                add(c)
            for pv in pvs:
                if pv:
                    for c in [os.path.join(b, pv, rp), os.path.join(b, "_main", pv, rp),
                              os.path.join(b, pv, "guides", bfn),
                              os.path.join(b, "_main", pv, "guides", bfn)]:
                        add(c)
    return res


def _norm_node(node_util: Any, target_str: str) -> dag_storage.DagNode:
    if node_util is not None:
        try:
            return node_util.normalize_target(bazel_target.TargetIdentifier(target_str))
        except (ValueError, TypeError, KeyError, LookupError, AttributeError):
            pass
    return dag_storage.DagNode(unit_address=dag_storage.UnitAddress(target_str), role_address=dag_storage.RoleAddress(""))


def _make_bound(pkg: str, s: str, cls: Any, owner: dag_storage.DagNode) -> Any:
    norm_rel = os.path.normpath(s.lstrip("/") if (s.startswith(pkg + "/") or (pkg and s.startswith("/" + pkg + "/"))) else os.path.join(pkg, s))
    return cls(
        relative_path=agent_file_alias.RelativePath(norm_rel),
        workspace_path=_make_host_path(agent_file_alias.WorkspacePath, norm_rel),
        owning_node=owner,
    )


def _load_per_node_info(n: dag_storage.DagNode) -> agent_node_config.PerNodeInfo:
    storage = _safe_get_singleton(dag_storage.DagStorage)
    msgs = storage.get_messages(n) if storage else ()
    feedback = tuple(
        agent_node_config.NodeFeedback(m.content)
        for m in msgs if isinstance(m, dag_storage.FeedbackMessage) and m.content
    )
    loader = _safe_get_singleton(bazel_manifest_loader.BazelManifestLoader)
    node_util = _safe_get_singleton(bazel_target.BazelTarget)
    manifest = loader.retrieve_manifest(n) if loader else None
    pkg_path = node_util.extract_node_dir(n).path.lstrip("/") if node_util else ""

    rw_files: Set[agent_file_alias.ReadWriteFile] = set()
    src_alias: Optional[agent_file_alias.RelativePath] = None
    if manifest and manifest.source_file:
        rw = _make_bound(pkg_path, manifest.source_file, agent_file_alias.ReadWriteFile, n)
        rw_files.add(rw)
        src_alias = rw.relative_path
    for s_src in (manifest.silent_source_files if manifest else ()):
        rw_files.add(_make_bound(pkg_path, s_src, agent_file_alias.ReadWriteFile, n))

    templates: Dict[agent_file_alias.BoundFile, agent_file_alias.FileContent] = {}
    if manifest and manifest.template and rw_files:
        t_content = _read_cand_file(_search_paths([manifest.template], pkg_path))
        if t_content is not None:
            c_obj = agent_file_alias.FileContent(t_content)
            for rw in rw_files:
                if rw.owning_node == n: templates[rw] = c_obj

    unit_name = n.unit_address.split(":")[-1] if ":" in n.unit_address else os.path.basename(n.unit_address)
    template_parameters: Dict[agent_node_config.TemplateParamKey, Any] = {
        agent_node_config.TemplateParamKey("unit_name"): unit_name,
        agent_node_config.TemplateParamKey("unit_dir"): pkg_path,
        agent_node_config.TemplateParamKey("name"): unit_name,
        agent_node_config.TemplateParamKey("dir"): pkg_path,
    }
    allows_step_mode = manifest.allows_step_mode if manifest and manifest.allows_step_mode is not None else True

    guide_target = manifest.guide_target if manifest else None
    guide_file: Optional[agent_file_alias.UnboundFile] = None
    guide: Optional[agent_node_config.NodeGuide] = None
    if guide_target:
        c_labels = [guide_target]
        if guide_target.startswith(":"):
            if pkg_path: c_labels = [f"//{pkg_path}{guide_target}", f"//{pkg_path}:{guide_target.lstrip(':')}"]
        elif not guide_target.startswith("//") and pkg_path:
            c_labels.extend([f"//{pkg_path}:{guide_target}", f"//{pkg_path}/{guide_target}"])

        g_manifest: Optional[bazel_manifest_loader.TargetManifest] = None
        if loader:
            for cl in c_labels:
                try:
                    g_manifest = loader.retrieve_manifest(_norm_node(node_util, cl))
                    if g_manifest: break
                except (LifecycleResolutionError, KeyError, LookupError, RuntimeError, ValueError, AttributeError):
                    pass

        g_fn = str(g_manifest.source_file) if g_manifest and g_manifest.source_file and "\n" not in str(g_manifest.source_file) else (guide_target.split(":")[-1] if ":" in guide_target else os.path.basename(guide_target))
        if not g_fn.endswith(".md"): g_fn += ".md"
        guide_file = agent_file_alias.UnboundFile(relative_path=agent_file_alias.RelativePath(g_fn))

        cands = [g_fn, guide_target, f"{guide_target}.md", os.path.basename(guide_target), f"{os.path.basename(guide_target)}.md"]
        if g_manifest and g_manifest.source_file:
            cands.extend([str(g_manifest.source_file), os.path.basename(str(g_manifest.source_file))])
        if g_manifest and g_manifest.template and not str(g_manifest.template).startswith("#") and "\n" not in str(g_manifest.template):
            cands.extend([str(g_manifest.template), os.path.basename(str(g_manifest.template))])
        g_text = _read_cand_file(_search_paths(cands, pkg_path))
        if g_text is not None:
            guide = _parse_guide_markdown(g_text)

    deps = list(manifest.dependencies) if manifest else []
    star_deps = list(manifest.star_dependencies) if manifest else []
    silent_deps = set(manifest.silent_dependencies) if manifest else set()
    feedback_deps = set(manifest.feedback_dependencies) if manifest else set()

    star_closure: List[str] = []
    star_seen: Set[str] = set()
    frontier = [sd for sd in star_deps if sd not in silent_deps]
    while frontier:
        curr_label = frontier.pop(0)
        if curr_label in star_seen: continue
        star_seen.add(curr_label); star_closure.append(curr_label)
        dm = loader.retrieve_manifest(_norm_node(node_util, curr_label)) if loader else None
        if dm: frontier.extend(s for s in dm.star_dependencies if s not in star_seen and s not in silent_deps)

    blame_targets: Set[agent_file_alias.BoundFile] = set()
    read_only_files: Set[agent_file_alias.ReadOnlyFile] = set()
    rw_paths = {rw.workspace_path.path for rw in rw_files}
    for dep_label in deps + [sd for sd in star_closure if sd not in deps]:
        if dep_label in silent_deps: continue
        dep_node = _norm_node(node_util, dep_label)
        is_blame = dep_label in feedback_deps
        dep_m = loader.retrieve_manifest(dep_node) if loader else None
        dep_pkg = node_util.extract_node_dir(dep_node).path.lstrip("/") if node_util else ""
        dep_srcs: List[str] = []
        if dep_m and dep_m.source_file:
            dep_srcs.append(dep_m.source_file)
        elif "guides" in dep_label:
            g_f = dep_label.split(":")[-1]
            dep_srcs.append(g_f if g_f.endswith(".md") else f"{g_f}.md")
        elif "specs" in dep_label:
            tb = dep_label.split(":")[-1].replace("_low", "").replace("_high", "").replace("_lib", "")
            dep_srcs.append(f"high/{tb}.md" if dep_label.endswith("_high") else f"grounding/{tb}.pyi")
        else:
            dep_srcs.append(f"{dep_label.split(':')[-1]}.py")

        for ds in dep_srcs:
            bf = _make_bound(dep_pkg, ds, agent_file_alias.ReadOnlyFile, dep_node)
            if bf.workspace_path.path not in rw_paths: read_only_files.add(bf)
            if is_blame: blame_targets.add(bf)

    ws_dir = os.environ.get("BUILD_WORKSPACE_DIRECTORY") or os.getcwd()
    v_cmd = str(manifest.verification_check).strip() if manifest and manifest.verification_check else ""
    v_checks = (_CommandVerificationCheck(command=v_cmd, cwd=ws_dir),) if v_cmd else ()

    return agent_node_config.PerNodeInfo(
        read_only_files=read_only_files, read_write_files=rw_files, templates=templates,
        template_parameters=template_parameters, allows_step_mode=allows_step_mode,
        guide_file=guide_file, guide=guide, blame_targets=blame_targets,
        verification_checks=v_checks, src_file_alias=src_alias,
        verification_success_message=None, feedback=feedback,
    )


class NodeConfig(agent_node_config.NodeConfig, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._per_node_cache: Dict[dag_storage.DagNode, agent_node_config.PerNodeInfo] = {}
        self._cached_version: int = -1
        self._allows_step_mode_override: Optional[bool] = None
        self._is_step_mode_override: Optional[bool] = None

    def initialize(self) -> None:
        self._sync_cache()

    def _sync_cache(self) -> None:
        role_cfg = _safe_get_singleton(agent_node_config.RoleConfig)
        if not role_cfg or role_cfg.version == self._cached_version:
            return
        active = set(role_cfg.nodes)
        for n in list(self._per_node_cache.keys()):
            if n not in active: del self._per_node_cache[n]
        for n in role_cfg.nodes:
            if n not in self._per_node_cache: self._per_node_cache[n] = _load_per_node_info(n)
        self._cached_version = role_cfg.version

    def _active_per_node_infos(self) -> List[agent_node_config.PerNodeInfo]:
        role_cfg = _safe_get_singleton(agent_node_config.RoleConfig)
        if role_cfg:
            return [self._per_node_cache[n] for n in role_cfg.nodes if n in self._per_node_cache]
        return list(self._per_node_cache.values())

    @property
    def per_node_info_by_node(self) -> Mapping[dag_storage.DagNode, agent_node_config.PerNodeInfo]:
        self._sync_cache(); return dict(self._per_node_cache)

    @property
    def read_only_files(self) -> Set[agent_file_alias.ReadOnlyFile]:
        self._sync_cache(); rw_paths = {rw.workspace_path.path for rw in self.read_write_files}
        return {ro for pni in self._active_per_node_infos() for ro in pni.read_only_files
                if ro.workspace_path.path not in rw_paths and not (self.is_step_mode and self.guide_file and ro.relative_path == self.guide_file.relative_path)}

    @property
    def read_write_files(self) -> Set[agent_file_alias.ReadWriteFile]:
        self._sync_cache(); return {f for pni in self._active_per_node_infos() for f in pni.read_write_files}

    @property
    def allows_step_mode(self) -> bool:
        if self._allows_step_mode_override is not None: return self._allows_step_mode_override
        self._sync_cache(); infos = self._active_per_node_infos()
        return infos[0].allows_step_mode if len(infos) == 1 else (True if not infos else False)

    @property
    def is_step_mode(self) -> bool:
        if self._is_step_mode_override is not None: return self._is_step_mode_override
        self._sync_cache(); infos = self._active_per_node_infos()
        if len(infos) != 1: return False
        m_cfg = _safe_get_singleton(agent_config.AgentConfig)
        return bool(m_cfg and m_cfg.is_step_mode and self.allows_step_mode and not self.feedback)

    @property
    def guide_file(self) -> Optional[agent_file_alias.UnboundFile]:
        self._sync_cache(); infos = self._active_per_node_infos()
        return infos[0].guide_file if self.is_step_mode and len(infos) == 1 else None

    @property
    def templates(self) -> Mapping[agent_file_alias.BoundFile, agent_file_alias.FileContent]:
        self._sync_cache(); return {k: v for pni in self._active_per_node_infos() for k, v in pni.templates.items()}

    @property
    def template_parameters(self) -> Mapping[agent_node_config.TemplateParamKey, Any]:
        self._sync_cache(); return {k: v for pni in self._active_per_node_infos() for k, v in pni.template_parameters.items()}

    @property
    def guide(self) -> Optional[agent_node_config.NodeGuide]:
        self._sync_cache(); infos = self._active_per_node_infos()
        return infos[0].guide if len(infos) == 1 else None

    @property
    def blame_targets_by_node(self) -> Mapping[dag_storage.DagNode, Set[agent_file_alias.BoundFile]]:
        self._sync_cache(); return {n: set(pni.blame_targets) for n, pni in self._per_node_cache.items()}

    @property
    def verification_checks(self) -> Sequence[agent_node_config.VerificationCheck]:
        self._sync_cache(); return [c for pni in self._active_per_node_infos() for c in pni.verification_checks]

    @property
    def verification_checks_by_node(self) -> Mapping[dag_storage.DagNode, Sequence[agent_node_config.VerificationCheck]]:
        self._sync_cache(); return {n: tuple(pni.verification_checks) for n, pni in self._per_node_cache.items()}

    @property
    def src_file_alias_by_node(self) -> Mapping[dag_storage.DagNode, agent_file_alias.RelativePath]:
        self._sync_cache(); return {n: pni.src_file_alias for n, pni in self._per_node_cache.items() if pni.src_file_alias is not None}

    @property
    def verification_success_message(self) -> Optional[agent_node_config.VerificationSuccessMessage]:
        self._sync_cache(); infos = self._active_per_node_infos()
        return infos[0].verification_success_message if len(infos) == 1 else None

    @property
    def feedback(self) -> Sequence[agent_node_config.NodeFeedback]:
        self._sync_cache(); return tuple(fb for pni in self._active_per_node_infos() for fb in pni.feedback)

    @property
    def blame_targets(self) -> Mapping[agent_file_alias.ReadWriteFile, agent_file_alias.ReadOnlyFile]:
        self._sync_cache(); res = {}
        for pni in self._active_per_node_infos():
            ro = [bt for bt in pni.blame_targets if isinstance(bt, agent_file_alias.ReadOnlyFile)]
            if ro:
                for rw in pni.read_write_files: res[rw] = ro[0]
        return res

    @property
    def messages(self) -> Mapping[agent_file_alias.ReadWriteFile, Sequence[dag_storage.DagMessage]]:
        self._sync_cache(); storage = _safe_get_singleton(dag_storage.DagStorage)
        if not storage: return {}
        return {rw: tuple(storage.get_messages(n)) for n, pni in self._per_node_cache.items() for rw in pni.read_write_files}


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
        fp_mgr = _safe_get_singleton(file_paths.FilePathManager)
        root = fp_mgr.get_workspace_root().path if fp_mgr and hasattr(fp_mgr, "get_workspace_root") else (os.environ.get("BUILD_WORKSPACE_DIRECTORY") or os.getcwd())
        self._workspace_root: file_paths.WorkspaceRoot = _make_host_path(file_paths.WorkspaceRoot, os.path.normpath(str(root)))

    def initialize(self) -> None:
        self._sync_cache()

    def _sync_cache(self) -> None:
        role_cfg, n_cfg = _safe_get_singleton(agent_node_config.RoleConfig), _safe_get_singleton(agent_node_config.NodeConfig)
        if not role_cfg or not n_cfg or role_cfg.version == self._cached_version:
            return
        self._aliases.clear(); self._paths.clear(); self._short_name_to_aliases.clear(); self._masking_patterns.clear()
        declared = n_cfg.read_write_files | n_cfg.read_only_files
        for f in sorted(declared, key=lambda x: len(x.workspace_path.path), reverse=True):
            self._aliases[f.relative_path] = f
            norm_ws = os.path.normpath(f.workspace_path.path)
            abs_p = os.path.normpath(os.path.join(self._workspace_root.path, norm_ws))
            self._paths[abs_p] = self._paths[norm_ws] = f.relative_path
            self._masking_patterns.append((re.compile(r"/?(?:[^\s:;\"\'`()<>{}\[\]/]+/)*" + re.escape(norm_ws) + r"(?=[:\s;\"\'`()<>{}\[\]]|$)"), f.relative_path))
        for f in declared:
            self._short_name_to_aliases.setdefault(os.path.basename(f.relative_path), []).append(f)
        if n_cfg.guide_file is not None:
            self._aliases[n_cfg.guide_file.relative_path] = n_cfg.guide_file
        self._cached_version = role_cfg.version

    @property
    def actual_type(self) -> Type[agent_file_alias.FileAlias]: return agent_file_alias.FileAlias
    @property
    def wire_type(self) -> Type[str]: return str

    def convert(self, wire_value: str) -> agent_file_alias.FileAlias:
        self._sync_cache(); s = str(wire_value)
        if s in self._aliases: return self._aliases[s]
        matches = self._short_name_to_aliases.get(s)
        return matches[0] if matches and len(matches) == 1 else agent_file_alias.UnboundFile(relative_path=agent_file_alias.RelativePath(s))

    def to_file_alias(self, wire_path: str) -> agent_file_alias.FileAlias: return self.convert(wire_path)

    def sanitize_text(self, text: agent_file_alias.UnsanitizedText) -> agent_file_alias.SanitizedText:
        self._sync_cache(); res = str(text)
        for pat, rel in self._masking_patterns: res = pat.sub(rel, res)
        for hp, rel in self._paths.items():
            if hp in res: res = res.replace(hp, rel)
        if self._workspace_root and self._workspace_root.path:
            ws_slash = self._workspace_root.path.rstrip("/") + "/"
            if ws_slash in res: res = res.replace(ws_slash, "")
            if self._workspace_root.path in res: res = res.replace(self._workspace_root.path, "")
        return agent_file_alias.SanitizedText(_EXECROOT_PATTERN.sub("", _WORKSPACE_PATTERN.sub("", res)))

    @property
    def workspace_root(self) -> file_paths.WorkspaceRoot: return self._workspace_root


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(NodeConfig, keys=[NodeConfig, agent_node_config.NodeConfig], tier=agent_session)
    reg.register_singleton(AliasManager, keys=[AliasManager, agent_file_alias.AliasManager, tool_provider.ParameterType], tier=agent_session)
