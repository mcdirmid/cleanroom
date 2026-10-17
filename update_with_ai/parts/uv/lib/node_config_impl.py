# --- CLEANROOM METADATA ---
# LAST_CLEANED: 2026-10-15T17:42:47Z
# LAST_CHANGED: 2026-10-11T05:10:00Z
# CHANGE: Resolve declared feedback dependencies into per-node blame targets and read-only files, include the guide target manifest source file in guide candidates, construct workspace paths through the declared frozen constructors, derive role-aware dependency fallbacks, prune uncontracted members and dead override state, and register the alias manager with the realized parameterized key
# CODE_HASH: 01341ac51e9b
# COVERAGE_AUDIT: 2026-10-15T17:42:47Z
# QA_AUDIT: 2026-10-15T17:42:47Z
# --- END CLEANROOM METADATA ---

import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, Type

from . import manifest_loader
from update_with_ai.parts.dag.lib import dag_storage
from update_with_ai.parts.agent.lib import file_alias, agent_config, node_config
from update_with_ai.parts.agent.lib.session import session as agent_session
from update_with_ai.parts.core.lib import file_paths
from support.lib.lifecycle import (
    LifecycleRegistry,
    LifecycleResolutionError,
    Singleton,
    get_default_registry,
    get_singleton,
)


# Contract: session verification checks evaluated during session advancement
class _CommandVerificationCheck(node_config.VerificationCheck):
    def __init__(self, command: str, cwd: Optional[str] = None) -> None:
        self._command = command
        self._cwd = cwd

    def verify(self) -> Tuple[bool, node_config.VerificationDiagnostic]:
        env = os.environ.copy()
        ws_root = env.get("BUILD_WORKSPACE_DIRECTORY") or self._cwd or os.getcwd()
        if not env.get("BUILD_WORKSPACE_DIRECTORY"):
            env["BUILD_WORKSPACE_DIRECTORY"] = ws_root
        pypaths: List[str] = []
        for root_cand in [ws_root, os.getcwd()]:
            if root_cand and os.path.isdir(root_cand):
                try:
                    for entry in os.listdir(root_cand):
                        pkg_dir = os.path.join(root_cand, entry)
                        if os.path.isdir(pkg_dir) and not entry.startswith((".", "bazel-", "venv", "__pycache__")):
                            sup_lib = os.path.join(pkg_dir, "support", "lib")
                            if os.path.isdir(sup_lib):
                                pypaths.append(pkg_dir)
                                pypaths.append(sup_lib)
                except OSError:
                    pass
        for sp in sys.path:
            if sp and os.path.isdir(sp) and sp not in pypaths:
                pypaths.append(sp)
        if "PYTHONPATH" in env and env["PYTHONPATH"]:
            pypaths.append(env["PYTHONPATH"])
        seen_p: Set[str] = set()
        dedup_pypaths: List[str] = []
        for p in pypaths:
            if p and p not in seen_p:
                seen_p.add(p)
                dedup_pypaths.append(p)
        env["PYTHONPATH"] = os.pathsep.join(dedup_pypaths)
        try:
            res = subprocess.run(
                self._command, shell=True, capture_output=True, text=True,
                cwd=self._cwd, env=env, stdin=subprocess.DEVNULL,
            )
            out = res.stdout
            if res.stderr:
                out = f"{out}\n{res.stderr}".strip() if out else res.stderr
            return res.returncode == 0, node_config.VerificationDiagnostic(out)
        except (OSError, subprocess.SubprocessError) as e:
            return False, node_config.VerificationDiagnostic(str(e))


def _workspace_path(relative: str) -> file_paths.WorkspacePath:
    """Builds a workspace-relative host path record from a relative path string."""
    return file_paths.WorkspacePath(path=file_paths.PathString(relative))


def _safe_get_singleton(cls: Any) -> Any:
    try:
        return get_singleton(cls)
    except (LifecycleResolutionError, KeyError, RuntimeError, ValueError, AttributeError):
        return None


# Contract: parse markdown sections into NodeGuide summaries, step sections, and verification failure instructions
def _parse_guide_markdown(content: str) -> node_config.NodeGuide:
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
            sections.append(node_config.StepSection(
                index=node_config.StepIndex(len(sections)),
                title=node_config.StepTitle(title),
                content=node_config.StepContent("\n".join(sec).strip()),
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
    vf = node_config.VerificationFailureInstructions("\n".join(vf_lines).strip()) if vf_lines is not None else None
    return node_config.NodeGuide(
        summary=node_config.GuideSummary(summary),
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
    ws_root = os.environ.get("BUILD_WORKSPACE_DIRECTORY", "") or os.getcwd()
    pkg_norm = os.path.normpath(pkg_path.strip("/")) if pkg_path else ""
    pvs = [pkg_norm] if pkg_norm and pkg_norm != "." else [""]
    if pkg_norm and pkg_norm != ".":
        parts = pkg_norm.split("/")
        pvs.extend("/".join(parts[i:]) for i in range(1, len(parts)))

    res: List[str] = []
    seen: Set[str] = set()

    def add(p: str) -> None:
        if p and p not in seen:
            seen.add(p); res.append(p)

    for rp in rel_paths:
        if not rp:
            continue
        bfn = os.path.basename(rp)
        for c in [rp, os.path.join("guides", bfn)]:
            add(c)
            if ws_root:
                add(os.path.join(ws_root, c))
                try:
                    for entry in os.listdir(ws_root):
                        sub_guides = os.path.join(ws_root, entry, "guides", bfn)
                        add(sub_guides)
                except OSError:
                    pass
        for pv in pvs:
            if pv:
                for c in [os.path.join(pv, rp), os.path.join(pv, "guides", bfn)]:
                    add(c)
                    if ws_root: add(os.path.join(ws_root, c))
    return res


def _norm_node(target_str: str) -> dag_storage.DagNode:
    if "#" in target_str:
        u, r = target_str.split("#", 1)
        return dag_storage.DagNode(unit_address=dag_storage.UnitAddress(u), role_address=dag_storage.RoleAddress(r))
    return dag_storage.DagNode(unit_address=dag_storage.UnitAddress(target_str), role_address=dag_storage.RoleAddress(""))


def _extract_pkg(n: dag_storage.DagNode) -> str:
    unit = n.unit_address
    if unit.startswith("//"):
        unit = unit[2:]
    return unit.split(":")[0] if ":" in unit else os.path.dirname(unit)


def _get_manifest(n: dag_storage.DagNode) -> Optional[Any]:
    loader = _safe_get_singleton(manifest_loader.UvManifestLoader)
    if loader is not None:
        try:
            return loader.retrieve_manifest(n)
        except (OSError, KeyError, LookupError, AttributeError, TypeError, ValueError):
            pass
    return None


def _make_bound(pkg: str, s: str, cls: Any, owner: dag_storage.DagNode) -> Any:
    norm_rel = os.path.normpath(s.lstrip("/") if (s.startswith(pkg + "/") or (pkg and s.startswith("/" + pkg + "/"))) else os.path.join(pkg, s))
    return cls(
        relative_path=file_alias.RelativePath(norm_rel),
        workspace_path=_workspace_path(norm_rel),
        owning_node=owner,
    )


def _dependency_source_paths(dep_label: str, dep_manifest: Optional[Any]) -> List[str]:
    """Resolves the declared source paths of an upstream dependency target."""
    if dep_manifest is not None and dep_manifest.source_file:
        return [str(dep_manifest.source_file)]
    unit_part, _, role_part = dep_label.partition("#")
    if "guides" in dep_label or role_part.strip().lower() == "guide":
        unit_name = unit_part.split(":")[-1].split("/")[-1]
        return [unit_name if unit_name.endswith(".md") else f"{unit_name}.md"]

    dep_node = _norm_node(dep_label)
    m = dep_manifest or _get_manifest(dep_node)
    if m is not None and m.source_file:
        return [str(m.source_file)]

    root = os.environ.get("BUILD_WORKSPACE_DIRECTORY") or os.getcwd()
    loader = _safe_get_singleton(manifest_loader.UvManifestLoader)
    pkg = _extract_pkg(dep_node)
    clean_role = role_part.strip().lower()
    if loader is not None and hasattr(loader, "_get_methodology_roles"):
        try:
            _, roles_dict = loader._get_methodology_roles(root, pkg)
            r_cfg = roles_dict.get(clean_role)
            if r_cfg and r_cfg.get("src_pattern"):
                unit_name = unit_part.split(":")[-1].split("/")[-1]
                pat = r_cfg["src_pattern"].format(unit_dir=pkg, unit_name=unit_name)
                if pat.startswith(pkg + "/") or pat.startswith(pkg + "\\"):
                    pat = pat[len(pkg) + 1 :]
                return [pat]
        except Exception:
            pass

    return []


# Contract: mapping each active node to its per node info (PerNodeInfo)
def _load_per_node_info(n: dag_storage.DagNode) -> node_config.PerNodeInfo:
    storage = _safe_get_singleton(dag_storage.DagStorage)
    msgs = storage.get_messages(n) if storage else ()
    feedback = tuple(
        node_config.NodeFeedback(m.content)
        for m in msgs if isinstance(m, dag_storage.FeedbackMessage) and m.content
    )
    manifest = _get_manifest(n)
    pkg_path = _extract_pkg(n)

    rw_files: Set[file_alias.ReadWriteFile] = set()
    src_alias: Optional[file_alias.RelativePath] = None
    if manifest and manifest.source_file:
        rw = _make_bound(pkg_path, str(manifest.source_file), file_alias.ReadWriteFile, n)
        rw_files.add(rw)
        src_alias = rw.relative_path
    for s_src in (manifest.silent_source_files if manifest else ()):
        rw_files.add(_make_bound(pkg_path, str(s_src), file_alias.ReadWriteFile, n))

    templates: Dict[file_alias.BoundFile, file_alias.FileContent] = {}
    if manifest and manifest.template and rw_files:
        t_content = _read_cand_file(_search_paths([str(manifest.template)], pkg_path))
        if t_content is not None:
            c_obj = file_alias.FileContent(t_content)
            for rw in rw_files:
                if rw.owning_node == n: templates[rw] = c_obj

    unit_name = n.unit_address.split(":")[-1] if ":" in n.unit_address else os.path.basename(n.unit_address)
    template_parameters: Dict[node_config.TemplateParamKey, Any] = {
        node_config.TemplateParamKey("unit_name"): unit_name,
        node_config.TemplateParamKey("unit_dir"): pkg_path,
        node_config.TemplateParamKey("name"): unit_name,
        node_config.TemplateParamKey("dir"): pkg_path,
    }
    allows_step_mode = manifest.allows_step_mode if manifest and manifest.allows_step_mode is not None else True

    guide_target = str(manifest.guide_target) if manifest and manifest.guide_target else None
    guide_file: Optional[file_alias.UnboundFile] = None
    guide: Optional[node_config.NodeGuide] = None
    resolved_guide_path: Optional[str] = None
    if guide_target:
        guide_paths: List[str] = []
        guide_manifest = _get_manifest(_norm_node(guide_target))
        if guide_manifest is not None and guide_manifest.source_file:
            guide_paths.append(str(guide_manifest.source_file))
        g_fn = guide_target.split(":")[-1] if ":" in guide_target else os.path.basename(guide_target)
        if not g_fn.endswith(".md"): g_fn += ".md"
        guide_file = file_alias.UnboundFile(relative_path=file_alias.RelativePath(g_fn))
        guide_paths.extend([g_fn, guide_target, f"{guide_target}.md", os.path.basename(guide_target), f"{os.path.basename(guide_target)}.md"])
        cands = _search_paths(guide_paths, pkg_path)
        for c in cands:
            if c and os.path.isfile(c):
                resolved_guide_path = c
                break
        g_text = _read_cand_file(cands)
        if g_text is not None: guide = _parse_guide_markdown(g_text)

    deps = list(manifest.dependencies) if manifest else []
    star_deps = list(manifest.star_dependencies) if manifest else []
    silent_deps = set(manifest.silent_dependencies) if manifest else set()
    feedback_deps = list(manifest.feedback_dependencies) if manifest else []
    feedback_labels = {str(label) for label in feedback_deps}

    blame_targets: Set[file_alias.BoundFile] = set()
    read_only_files: Set[file_alias.ReadOnlyFile] = set()
    if resolved_guide_path:
        ws_root = os.environ.get("BUILD_WORKSPACE_DIRECTORY", "") or os.getcwd()
        g_rel = os.path.relpath(resolved_guide_path, ws_root) if os.path.isabs(resolved_guide_path) else resolved_guide_path
        read_only_files.add(
            file_alias.ReadOnlyFile(
                relative_path=file_alias.RelativePath(g_rel),
                workspace_path=_workspace_path(g_rel),
                owning_node=n,
            )
        )
    rw_paths = {rw.workspace_path.path for rw in rw_files}
    referenced_deps = list(dict.fromkeys(deps + [sd for sd in star_deps if sd not in deps] + feedback_deps))
    for dep_label in referenced_deps:
        dep_str = str(dep_label)
        if dep_str in silent_deps: continue
        dep_node = _norm_node(dep_str)
        dep_m = _get_manifest(dep_node)
        dep_pkg = _extract_pkg(dep_node)
        for ds in _dependency_source_paths(dep_str, dep_m):
            bf = _make_bound(dep_pkg, ds, file_alias.ReadOnlyFile, dep_node)
            if bf.workspace_path.path not in rw_paths: read_only_files.add(bf)
            if dep_str in feedback_labels: blame_targets.add(bf)

    for fb_label in feedback_deps:
        fb_str = str(fb_label)
        if fb_str not in silent_deps: continue
        fb_node = _norm_node(fb_str)
        fb_m = _get_manifest(fb_node)
        for ds in _dependency_source_paths(fb_str, fb_m):
            blame_targets.add(
                _make_bound(_extract_pkg(fb_node), ds, file_alias.ReadOnlyFile, fb_node)
            )

    ws_dir = os.environ.get("BUILD_WORKSPACE_DIRECTORY") or os.getcwd()
    v_cmd = str(manifest.verification_check).strip() if manifest and manifest.verification_check else ""
    v_checks = (_CommandVerificationCheck(command=v_cmd, cwd=ws_dir),) if v_cmd else ()

    v_success_msg = None
    if manifest and manifest.verification_success_message:
        v_success_msg = node_config.VerificationSuccessMessage(
            str(manifest.verification_success_message)
        )

    return node_config.PerNodeInfo(
        read_only_files=read_only_files, read_write_files=rw_files, templates=templates,
        template_parameters=template_parameters, allows_step_mode=allows_step_mode,
        guide_file=guide_file, guide=guide, blame_targets=blame_targets,
        verification_checks=v_checks, src_file_alias=src_alias,
        verification_success_message=v_success_msg, feedback=feedback,
    )


class NodeConfig(node_config.NodeConfig, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._per_node_cache: Dict[dag_storage.DagNode, node_config.PerNodeInfo] = {}
        self._cached_version: int = -1

    def initialize(self) -> None:
        self._sync_cache()

    def _sync_cache(self) -> None:
        role_cfg = _safe_get_singleton(node_config.RoleConfig)
        if not role_cfg or role_cfg.version == self._cached_version: return
        active = set(role_cfg.nodes)
        for n in list(self._per_node_cache.keys()):
            if n not in active: del self._per_node_cache[n]
        for n in role_cfg.nodes:
            if n not in self._per_node_cache: self._per_node_cache[n] = _load_per_node_info(n)
        self._cached_version = role_cfg.version

    def _active_per_node_infos(self) -> List[node_config.PerNodeInfo]:
        role_cfg = _safe_get_singleton(node_config.RoleConfig)
        return [self._per_node_cache[n] for n in role_cfg.nodes if n in self._per_node_cache] if role_cfg else list(self._per_node_cache.values())

    # Contract: mapping each active node to its per node info
    @property
    def per_node_info_by_node(self) -> Mapping[dag_storage.DagNode, node_config.PerNodeInfo]:
        self._sync_cache(); return dict(self._per_node_cache)

    # Contract: aggregate read-only files across active nodes, excluding read-write files
    @property
    def read_only_files(self) -> Set[file_alias.ReadOnlyFile]:
        self._sync_cache(); rw_paths = {rw.workspace_path.path for rw in self.read_write_files}
        return {ro for pni in self._active_per_node_infos() for ro in pni.read_only_files
                if ro.workspace_path.path not in rw_paths and not (self.is_step_mode and self.guide_file and ro.relative_path == self.guide_file.relative_path)}

    # Contract: aggregate read-write files and templates across active nodes
    @property
    def read_write_files(self) -> Set[file_alias.ReadWriteFile]:
        self._sync_cache(); return {f for pni in self._active_per_node_infos() for f in pni.read_write_files}

    # Contract: check step mode eligibility on the single active node manifest
    @property
    def allows_step_mode(self) -> bool:
        self._sync_cache(); infos = self._active_per_node_infos()
        return infos[0].allows_step_mode if len(infos) == 1 else (True if not infos else False)

    # Contract: activate step mode when permitted by agent config with single-node session lacking feedback
    @property
    def is_step_mode(self) -> bool:
        self._sync_cache(); infos = self._active_per_node_infos()
        if len(infos) != 1: return False
        m_cfg = _safe_get_singleton(agent_config.AgentConfig)
        return bool(m_cfg and m_cfg.is_step_mode and self.allows_step_mode and not self.feedback)

    # Contract: unbound guide file configured when guide step mode is active
    @property
    def guide_file(self) -> Optional[file_alias.UnboundFile]:
        self._sync_cache(); infos = self._active_per_node_infos()
        return infos[0].guide_file if len(infos) == 1 else None

    # Contract: templates mapping read-write files to initial file content across active nodes
    @property
    def templates(self) -> Mapping[file_alias.BoundFile, file_alias.FileContent]:
        self._sync_cache(); return {k: v for pni in self._active_per_node_infos() for k, v in pni.templates.items()}

    # Contract: parameter bindings for template evaluation across active nodes
    @property
    def template_parameters(self) -> Mapping[node_config.TemplateParamKey, Any]:
        self._sync_cache(); return {k: v for pni in self._active_per_node_infos() for k, v in pni.template_parameters.items()}

    # Contract: structured instructional text for guide step mode
    @property
    def guide(self) -> Optional[node_config.NodeGuide]:
        self._sync_cache(); infos = self._active_per_node_infos()
        return infos[0].guide if len(infos) == 1 else None

    # Contract: bound files owned by upstream dependency nodes mapped by session node
    @property
    def blame_targets_by_node(self) -> Mapping[dag_storage.DagNode, Set[file_alias.BoundFile]]:
        self._sync_cache(); return {n: set(pni.blame_targets) for n, pni in self._per_node_cache.items()}

    # Contract: aggregate verification checks across active nodes
    @property
    def verification_checks(self) -> Sequence[node_config.VerificationCheck]:
        self._sync_cache(); return [c for pni in self._active_per_node_infos() for c in pni.verification_checks]

    # Contract: session verification checks mapped by session node
    @property
    def verification_checks_by_node(self) -> Mapping[dag_storage.DagNode, Sequence[node_config.VerificationCheck]]:
        self._sync_cache(); return {n: tuple(pni.verification_checks) for n, pni in self._per_node_cache.items()}

    # Contract: relative path of declared source file alias mapped by session node
    @property
    def src_file_alias_by_node(self) -> Mapping[dag_storage.DagNode, file_alias.RelativePath]:
        self._sync_cache(); return {n: pni.src_file_alias for n, pni in self._per_node_cache.items() if pni.src_file_alias is not None}

    # Contract: informative verification feedback when configured
    @property
    def verification_success_message(self) -> Optional[node_config.VerificationSuccessMessage]:
        self._sync_cache(); infos = self._active_per_node_infos()
        return infos[0].verification_success_message if len(infos) == 1 else None

    # Contract: combine feedback messages from graph storage across active nodes
    @property
    def feedback(self) -> Sequence[node_config.NodeFeedback]:
        self._sync_cache(); return tuple(fb for pni in self._active_per_node_infos() for fb in pni.feedback)


_EXECROOT_PATTERN: re.Pattern[str] = re.compile(
    r"/(?:[^\s:;\"\'`()<>{}\[\]/]+/)*execroot/[^\s:;\"\'`()<>{}\[\]/]+/"
)
_WORKSPACE_PATTERN: re.Pattern[str] = re.compile(
    r"/(?:[^\s:;\"\'`()<>{}\[\]/]+/)*workspace/"
)


class AliasManager(file_alias.AliasManager, Singleton):
    tier = agent_session

    def __init__(self) -> None:
        self._aliases: Dict[str, file_alias.FileAlias] = {}
        self._short_name_to_aliases: Dict[str, List[file_alias.BoundFile]] = {}
        self._paths: Dict[str, str] = {}
        self._masking_patterns: List[Tuple[re.Pattern[str], str]] = []
        self._cached_version: Optional[int] = None
        fp_mgr = _safe_get_singleton(file_paths.FilePathManager)
        root = fp_mgr.get_workspace_root().path if fp_mgr and hasattr(fp_mgr, "get_workspace_root") else (os.environ.get("BUILD_WORKSPACE_DIRECTORY") or os.getcwd())
        self._workspace_root: file_paths.WorkspaceRoot = file_paths.WorkspaceRoot(
            path=file_paths.PathString(os.path.normpath(str(root)))
        )

    def initialize(self) -> None:
        self._sync_cache()

    def _sync_cache(self) -> None:
        role_cfg, n_cfg = _safe_get_singleton(node_config.RoleConfig), _safe_get_singleton(node_config.NodeConfig)
        if not role_cfg or not n_cfg or role_cfg.version == self._cached_version: return
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
    def actual_type(self) -> Type[file_alias.FileAlias]: return file_alias.FileAlias
    @property
    def wire_type(self) -> Type[str]: return str

    # Contract: convert path string to file alias (BoundFile if matched, UnboundFile otherwise)
    def to_alias(self, path: str) -> file_alias.FileAlias:
        self._sync_cache(); s = str(path)
        if s in self._aliases: return self._aliases[s]
        matches = self._short_name_to_aliases.get(s)
        return matches[0] if matches and len(matches) == 1 else file_alias.UnboundFile(relative_path=file_alias.RelativePath(s))

    # Contract: sanitize output text by masking paths with relative aliases
    def sanitize_text(self, text: file_alias.UnsanitizedText) -> file_alias.SanitizedText:
        self._sync_cache(); res = str(text)
        for pat, rel in self._masking_patterns: res = pat.sub(rel, res)
        for hp, rel in self._paths.items():
            if hp in res: res = res.replace(hp, rel)
        if self._workspace_root and self._workspace_root.path:
            ws_slash = self._workspace_root.path.rstrip("/") + "/"
            if ws_slash in res: res = res.replace(ws_slash, "")
            if self._workspace_root.path in res: res = res.replace(self._workspace_root.path, "")
        return file_alias.SanitizedText(_EXECROOT_PATTERN.sub("", _WORKSPACE_PATTERN.sub("", res)))

    # Contract: configured absolute workspace root path
    @property
    def workspace_root(self) -> file_paths.WorkspaceRoot: return self._workspace_root


# --- CLEANROOM AUTO-GENERATED: DO NOT EDIT ---
def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    """Registers constituent singletons into the lifecycle registry."""
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        NodeConfig,
        keys=[NodeConfig, node_config.NodeConfig],
        tier=agent_session,
    )
    reg.register_singleton(
        AliasManager,
        keys=[AliasManager, file_alias.AliasManager],
        tier=agent_session,
    )


_initialize_ = __initialize__
# --- END CLEANROOM AUTO-GENERATED ---
