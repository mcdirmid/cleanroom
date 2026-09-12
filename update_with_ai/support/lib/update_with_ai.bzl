"""
Starlark rules and macro for AI agent nodes.

This module provides:
- update_with_ai rule: Produces a manifest file describing a node
- update_with_ai macro: Convenience wrapper that also generates a *_clean target
- bazel_ai_graph rule: Produces a graph manifest for the entire DAG

The approach uses DATA-DRIVEN loading at runtime, NOT code generation:
- Analysis phase: Build manifest files with graph structure
- Execution phase: Python runtime loads manifests and constructs objects

Model configuration: the generated *_clean binaries resolve a
`model_config` target (see update_with_ai/support/lib/model_config.bzl) in this order:
  1. --config //pkg:name passed to the binary (bazel run ... -- --config //pkg:name)
  2. MODEL_CONFIG_TARGET or AGENT_CONFIG_TARGET environment variable
  3. the `config` attribute on update_with_ai(...)
  4. the --define=MODEL_CONFIG=//pkg:name build setting (command line,
     .bazelrc, or the user's ~/.bazelrc for a personal default)
  5. the //model_configs:default convention

Usage:
  update_with_ai(
    name = "my_node",
    prompt = "...",
  )
  # Automatically generates:
  #   //pkg:my_node           — the node manifest
  #   //pkg:my_node_clean     — binary that runs DAG cleaning on this node
  #   //pkg:my_node_feedback  — binary that delivers feedback to this node
  #   //pkg:my_node_dirty     — binary that delivers a change (nudge) to this node
  #   //pkg:my_node_change    — binary that broadcasts a change from this node
  #   //pkg:my_node_prompt    — binary that prints the node's initial agent prompt
  # Run with: bazel run //pkg:my_node_clean
  #           bazel run //pkg:my_node_prompt
"""

# ============================================================================
# Rule: update_with_ai (internal implementation)
# ============================================================================

def _update_with_ai_impl(ctx):
    """Implementation of update_with_ai rule."""

    # Create the manifest file
    manifest = ctx.actions.declare_file("{}_manifest.json".format(ctx.label.name))

    # Gather dependency information
    deps_data = []
    for dep in ctx.attr.deps:
        if hasattr(dep, "files"):
            # Collect all files from dependencies
            for f in dep.files.to_list():
                deps_data.append({
                    "label": str(dep.label),
                    "path": f.short_path,
                })

    # Feedback deps are automatically included in deps: the manifest's deps
    # list is the union of the declared deps and the feedback deps (deduped),
    # so feedback deps are cleaned before run and their srcs output is
    # readable, exactly like declared deps.
    _all_deps = [str(dep.label) for dep in ctx.attr.deps]
    _seen = {dep_label: True for dep_label in _all_deps}
    for dep in ctx.attr.feedback_deps:
        dep_label = str(dep.label)
        if dep_label not in _seen:
            _all_deps.append(dep_label)
            _seen[dep_label] = True
    # Star deps are automatically included in deps for the same reason: the
    # star dep and the nodes in its transitive closure over deps/star deps
    # are cleaned before run, and their srcs output is readable (the closure
    # is computed at run time from the manifests).
    for dep in ctx.attr.star_deps:
        dep_label = str(dep.label)
        if dep_label not in _seen:
            _all_deps.append(dep_label)
            _seen[dep_label] = True
    # The guide node is automatically included in deps so it is cleaned before
    # this node and its manifest reaches the graph for runtime loading.
    if ctx.attr.guide:
        guide_label = str(ctx.attr.guide.label)
        if guide_label not in _seen:
            _all_deps.append(guide_label)
            _seen[guide_label] = True

    # Build the manifest with apparent canonical labels
    manifest_content = {
        "label": _apparent_label(ctx.label),
        "name": ctx.attr.name,
        "prompt": ctx.attr.prompt,
        "tools": [str(t) for t in ctx.attr.tools],
        "deps": [_apparent_label(dep_label) for dep_label in _all_deps],
        "silent_deps": [_apparent_label(dep.label) for dep in ctx.attr.silent_deps],
        "feedback_deps": [_apparent_label(dep.label) for dep in ctx.attr.feedback_deps],
        "star_deps": [_apparent_label(dep.label) for dep in ctx.attr.star_deps],
        "src": ctx.attr.src,
        "template": ctx.file.template.short_path if ctx.file.template else None,
        "template_parameters": json.decode(ctx.attr.template_parameters) if ctx.attr.template_parameters else {},
        "guide": _apparent_label(ctx.attr.guide.label) if ctx.attr.guide else None,
        "allows_step_mode": ctx.attr.allows_step_mode,
        "silent_srcs": [str(s) for s in ctx.attr.silent_srcs],
        "verify": ctx.attr.verify if ctx.attr.verify else None,
        "dependency_paths": deps_data,
    }

    ctx.actions.write(
        output = manifest,
        content = json.encode(manifest_content),
    )

    # Create default provider so this target can be depended upon
    return [
        DefaultInfo(
            files = depset([manifest]),
            runfiles = ctx.runfiles(files = [manifest]),
        ),
    ]

# ============================================================================
# Aspect: collect all transitive node manifests for runfiles
# ============================================================================

def _collect_manifests_impl(target, ctx):
    """Collect the target's own manifest plus all transitive node manifests.

    Bazel runfiles are explicit, not transitive: a node target's runfiles
    contain only its own manifest, so a *_clean binary would not see the
    manifests of its deps' deps. This aspect walks the node graph (deps,
    silent_deps, feedback_deps, star_deps, guide) and returns every *_manifest.json
    reachable, so consumers (the clean rule, the lint test rule) can put the
    full transitive manifest set into runfiles for run-time graph loading.
    """
    own = [
        f
        for f in target[DefaultInfo].files.to_list()
        if f.basename.endswith("_manifest.json")
    ]
    transitive = []
    for attr_name in ("deps", "silent_deps", "feedback_deps", "star_deps", "guide"):
        val = getattr(ctx.rule.attr, attr_name, None)
        if val == None:
            continue
        dep_list = val if type(val) == "list" else [val]
        for dep in dep_list:
            if OutputGroupInfo in dep:
                manifests = getattr(dep[OutputGroupInfo], "manifests", None)
                if manifests != None:
                    transitive.append(manifests)
    return [OutputGroupInfo(manifests = depset(own, transitive = transitive))]

_collect_manifests = aspect(
    implementation = _collect_manifests_impl,
    attr_aspects = ["deps", "silent_deps", "feedback_deps", "star_deps", "guide"],
)

# Rule definition (private name)
_update_with_ai_rule = rule(
    implementation = _update_with_ai_impl,
    attrs = {
        "prompt": attr.string(
            mandatory = False,
            default = "",
            doc = "The agent prompt for this node",
        ),

        "tools": attr.label_list(
            doc = "List of tool targets",
        ),
        "deps": attr.label_list(
            doc = "List of dependency node targets (cleaned before run) whose srcs output is readable",
        ),
        "silent_deps": attr.label_list(
            doc = "List of dependency node targets whose output is not readable and whose changes do not propagate to this node",
        ),
        "feedback_deps": attr.label_list(
            doc = "List of dependency node targets that can receive feedback; these nodes are automatically included in deps",
        ),
        "star_deps": attr.label_list(
            doc = "List of dependency node targets whose transitive closure over star deps is readable; these nodes are automatically included in deps",
        ),
        "src": attr.string(
            doc = "The node's declared source file path: the single file the agent can write that deps can read (the file need not pre-exist; when a template is configured and the file is missing on disk, the template's content initializes it at run start)",
        ),
        "template": attr.label(
            allow_single_file = True,
            doc = "Optional file label whose content initializes the declared source file at run start when the file does not exist on disk; the manifest stores the template file's repo-relative path and the runtime reads its content",
        ),
        "template_parameters": attr.string(
            default = "{}",
            doc = "JSON-encoded dictionary of template parameters",
        ),
        "guide": attr.label(
            aspects = [_collect_manifests],
            doc = "Optional node target whose declared source is the run's guide: a readable file in the guide format (# Guide: ... ## Summary ...). The guide node is cleaned before this node; the guide's readable and delivery treatment follows the agent configuration's step-sections gate (when step mode is enabled the guide is not readable and its content reaches the agent only through advance outputs).",
        ),
        "allows_step_mode": attr.bool(
            default = True,
            doc = "Whether the node permits guide step mode. Stepping is active when model config enables stepping unless disabled by this attribute.",
        ),
        "silent_srcs": attr.string_list(
            doc = "Paths (relative to the node's package directory) the agent can write that are NOT readable by deps",
        ),
        "verify": attr.string(
            mandatory = False,
            default = "",
            doc = "Shell command to run when the agent calls verify()",
        ),
    },
)

# ============================================================================
# Macro: update_with_ai with clean and feedback targets
# ============================================================================

def update_with_ai(
        name,
        prompt = "",
        tools = [],
        deps = [],
        silent_deps = [],
        feedback_deps = [],
        star_deps = [],
        src = "",
        template = None,
        template_parameters = None,
        guide = None,
        allows_step_mode = True,
        step_mode = None,
        step_sections = None,
        silent_srcs = [],
        verify = "",
        config = None,
        visibility = None):
    """
    Macro to create an AI agent node with clean and feedback targets.

    This macro wraps the update_with_ai rule and automatically generates four
    sibling targets:
      - `name + "_clean"`     runs DAG cleaning on the node
      - `name + "_feedback"`  delivers CLI feedback messages to the node's own
                              pending messages, marking it dirty with feedback
      - `name + "_dirty"`     delivers a CLI change message to the node's own
                              pending messages, marking it dirty (a gentler
                              nudge; the change text defaults to "check")
      - `name + "_change"`    pretends the node was cleaned with changes:
                              broadcasts the CLI argument (as the change part
                              of the message) to the node's known reverse
                              dependencies and clears the node's data
      - `name + "_prompt"`    prints the node's initial agent prompt
                              (bazel run //pkg:name_prompt)

    The clean target runs the DAG cleaning logic:
    1. Reads the node's manifest (JSON)
    2. Gets the node label from the manifest
    3. Builds the graph (loads all deps)
    4. Runs the cleaning pass

    The feedback target delivers each positional CLI argument as a feedback
    message to the node's own pending message store, so the node becomes
    dirty and a subsequent *_clean run processes the feedback; when cleaned,
    a node with pending feedback must change, blame, or fail.

    Model configuration: the *_clean target resolves a `model_config`
    target (see update_with_ai/support/lib/model_config.bzl) in this priority order:
      1. `--config //pkg:name` passed to the *_clean binary
         (bazel run //pkg:node_clean -- --config //pkg:name)
      2. The MODEL_CONFIG_TARGET or AGENT_CONFIG_TARGET environment variable
      3. The `config` attribute of this macro (if given)
      4. The --define=MODEL_CONFIG=//pkg:name build setting (command line,
         .bazelrc, or the user's ~/.bazelrc for a personal default)
      5. The //model_configs:default convention

    Usage:
      bazel run //pkg:node_name_clean     # runs cleaning pass on node_name
      bazel run //pkg:node_name_feedback -- "feedback message" ["more"...]
      bazel run //pkg:node_name_dirty     # adds the change "check"
      bazel run //pkg:node_name_dirty -- "check the new behavior"
      bazel run //pkg:node_name_change -- "changed hello world"
      bazel run //pkg:node_name_prompt    # prints the node's initial agent prompt

    Args:
        name: Target name
        prompt: Agent prompt string
        tools: List of tool targets
        deps: List of dependency node targets (cleaned before run) whose
            srcs output is readable
        silent_deps: List of dependency node targets whose output is not
            readable and whose changes do not propagate to this node
        feedback_deps: List of dependency node targets that can receive
            feedback; these nodes are automatically included in deps
        star_deps: List of dependency node targets whose transitive closure
            over star deps is readable; these nodes are automatically
            included in deps (cleaned before run)
        src: The node's declared source file (writable, readable by deps); when a
            template is configured and this file does not exist on disk, the
            template's content initializes it at run start
        template: Optional file label whose content initializes src at run start
            when src does not exist on disk
        guide: Optional node target whose declared source is the run's guide
            (a readable file in the guide format); the guide node is cleaned
            before this node, and the guide's readable/delivery treatment
            follows the agent configuration's step-sections gate
        silent_srcs: Paths (relative to the node's package directory) the agent can write that are NOT readable by deps
        verify: Shell command to run when the agent calls verify()
            (default: empty = no verify tool)
        config: Optional agent_config target label used as the default
            configuration for this node's *_clean target (overrides
            --define=AGENT_CONFIG; may still be overridden by --config or
            AGENT_CONFIG_TARGET at run time).
        visibility: Optional visibility applied to all targets this macro
            generates — the node manifest (`name`), the clean target
            (`name + "_clean"`), the feedback target
            (`name + "_feedback"`), the dirty target (`name + "_dirty"`),
            the change target (`name + "_change"`), and the prompt target
            (`name + "_prompt"`). None (default) leaves each target with
            Bazel's default (package-private) visibility. Set to
            ["//visibility:public"] (or a package list) to allow other
            packages to depend on this node or run its *_clean / *_feedback
            binaries.
    """

    # Forward visibility to the generated targets only when it is given:
    # passing None to a rule is not allowed, and Bazel's default visibility
    # applies when the attribute is absent.
    _rule_kwargs = {}
    if visibility != None:
        _rule_kwargs["visibility"] = visibility

    if step_mode != None:
        allows_step_mode = step_mode
    elif step_sections != None:
        allows_step_mode = step_sections

    template_params_json = "{}"
    if template_parameters != None:
        if type(template_parameters) == "string":
            template_params_json = template_parameters
        else:
            template_params_json = json.encode(template_parameters)

    # Create the node target (using the rule directly)
    _update_with_ai_rule(
        name = name,
        prompt = prompt,
        tools = tools,
        deps = deps,
        silent_deps = silent_deps,
        feedback_deps = feedback_deps,
        star_deps = star_deps,
        src = src,
        template = template,
        template_parameters = template_params_json,
        guide = guide,
        allows_step_mode = allows_step_mode,
        silent_srcs = silent_srcs,
        verify = verify,
        **_rule_kwargs
    )

    # Create a clean target that runs DAG cleaning.
    # This calls a helper rule that produces a binary wrapper.
    _clean_target = name + "_clean"
    _update_ai_node_clean_rule(
        name = _clean_target,
        node = ":{}".format(name),  # the node manifest
        # dependency manifests for graph resolution: deps (which includes
        # feedback_deps and star_deps), silent_deps, feedback_deps, and
        # star_deps (explicit, so a star dep declared without a deps entry
        # is still resolvable, and its manifest reaches runfiles)
        deps = deps + silent_deps + feedback_deps + star_deps,
        guide = guide,  # the guide node's manifest reaches runfiles
        config = config,  # optional agent_config default for this node
        **_rule_kwargs
    )

    # Create a feedback target that delivers feedback to the node itself,
    # marking it dirty so a subsequent *_clean run processes the feedback.
    _feedback_target = name + "_feedback"
    _update_ai_node_feedback_rule(
        name = _feedback_target,
        node = ":{}".format(name),  # the node manifest
        **_rule_kwargs
    )

    # Create a dirty target that delivers a change message (a nudge) to the
    # node itself, marking it dirty; when cleaned, the node may succeed
    # without changing (the change text defaults to "check").
    _dirty_target = name + "_dirty"
    _update_ai_node_dirty_rule(
        name = _dirty_target,
        node = ":{}".format(name),  # the node manifest
        **_rule_kwargs
    )

    # Create a change target that pretends the node was cleaned with changes:
    # the CLI argument becomes the change part of a message broadcast to the
    # node's known reverse dependencies, and the node's own data is cleared.
    _change_target = name + "_change"
    _update_ai_node_change_rule(
        name = _change_target,
        node = ":{}".format(name),  # the node manifest
        **_rule_kwargs
    )

    # Create a prompt target that prints the node's initial agent prompt
    # (bazel run //pkg:name_prompt).
    _prompt_target = name + "_prompt"
    _update_ai_node_prompt_rule(
        name = _prompt_target,
        node = ":{}".format(name),  # the node manifest
        **_rule_kwargs
    )

# ============================================================================
# Rule: update_ai_node_clean (generates a clean target per node)
# ============================================================================

def _apparent_label(label):
    """Return the apparent (user-facing) label for a main-repo target.

    With bzlmod, str(label) yields the canonical repository-qualified form;
    users select configs with the apparent form (//pkg:name), so embed that.
    """
    s = str(label)
    if s.startswith("@" + "@"):
        s = s[2:]
    elif s.startswith("@") and "//" in s:
        # @repo//pkg:name: configs live in the main repo; drop the repo part.
        s = s[s.index("//"):]
    return s

def _update_ai_node_clean_impl(ctx):
    """Generates a Python binary that runs DAG cleaning on a node."""
    _node = ctx.attr.node
    _manifest = _node[DefaultInfo].files.to_list()[0]  # _manifest.json
    _manifest_filename = _manifest.basename  # just the filename

    # Resolve the default model configuration target for this binary:
    #   1. the `config` attribute on update_with_ai(...) — most specific
    #   2. the --define=MODEL_CONFIG=//pkg:name build setting (command line,
    #      .bazelrc, or the user's ~/.bazelrc) — the (personal) default
    #   3. the //model_configs:default convention
    # At run time the wrapper still lets --config / MODEL_CONFIG_TARGET
    # override this default (see the generated main()).
    _config_attr = ctx.attr.config
    _define_target = ctx.var.get("MODEL_CONFIG", "") or ctx.var.get("AGENT_CONFIG", "")
    if _config_attr:
        _default_config_target = _apparent_label(_config_attr.label)
    elif _define_target:
        _default_config_target = _define_target
    else:
        _default_config_target = "//model_configs:default"

    # Generate a Python wrapper
    _wrapper_py = ctx.actions.declare_file(ctx.label.name + ".py")
    _lines = [
        "#!/usr/bin/env python3",
        "import json",
        "import sys",
        "import os",
        "",
        "# Default model_config target (from the config attribute, the",
        "# --define=MODEL_CONFIG build setting, or the //model_configs:default convention).",
        "_DEFAULT_CONFIG_TARGET = {}".format(json.encode(_default_config_target)),
        "",
        "# Ensure lib is importable from runfiles",
        "_runfiles_root = None",
        'for base in (os.environ.get("RUNFILES_DIR", ""), os.environ.get("BAZEL_RUNFILES", "")):',
        '    if base and os.path.isdir(base):',
        "        _runfiles_root = base",
        "        break",
        "if not _runfiles_root:",
        "    _runfiles_root = os.getcwd()",
        "for cand in (_runfiles_root, os.path.join(_runfiles_root, '_main'), os.path.join(_runfiles_root, 'update_with_ai'), os.path.join(_runfiles_root, 'update_python_with_ai'), os.path.join(_runfiles_root, '_main', 'update_with_ai'), os.path.join(_runfiles_root, '_main', 'update_python_with_ai')):",
        "    if os.path.isdir(cand) and cand not in sys.path:",
        "        sys.path.insert(0, cand)",
        "try:",
        "    from support.lib.lifecycle import get_singleton",
        "    from lib import bazel_asm",
        "    from lib.bazel_runner import BazelRunner",
        "    from lib.bazel_manifest_loader import BazelManifestLoader, Manifest",
        "    from lib.dag_storage import DagStorage",
        "    from lib.bazel_node_id_utils import BazelNodeIdentifierUtility",
        "except ImportError:",
        "    try:",
        "        from update_python_with_ai.support.lib.lifecycle import get_singleton",
        "    except ImportError:",
        "        from update_with_ai.support.lib.lifecycle import get_singleton",
        "    from update_with_ai.lib import bazel_asm",
        "    from update_with_ai.lib.bazel_runner import BazelRunner",
        "    from update_with_ai.lib.bazel_manifest_loader import BazelManifestLoader, Manifest",
        "    from update_with_ai.lib.dag_storage import DagStorage",
        "    from update_with_ai.lib.bazel_node_id_utils import BazelNodeIdentifierUtility",
        "",
        "def main():",
        "    args = sys.argv[1:]",
        "    # Parse --config <label> (or --config=<label>); remaining positional",
        "    # args are kept for backward compatibility (first = workspace root).",
        "    config_target = None",
        "    rest = []",
        "    i = 0",
        "    while i < len(args):",
        '        if args[i] == "--config":',
        "            i += 1",
        "            if i >= len(args):",
        '                print("--config requires a target label (e.g. //model_configs:default)", file=sys.stderr)',
        "                sys.exit(2)",
        "            config_target = args[i]",
        '        elif args[i].startswith("--config="):',
        '            config_target = args[i].split("=", 1)[1]',
        "        else:",
        "            rest.append(args[i])",
        "        i += 1",
        "    resolved_config = config_target or os.environ.get(\"MODEL_CONFIG_TARGET\") or os.environ.get(\"AGENT_CONFIG_TARGET\") or _DEFAULT_CONFIG_TARGET",
        "    os.environ[\"MODEL_CONFIG_TARGET\"] = resolved_config",
        "    os.environ[\"AGENT_CONFIG_TARGET\"] = resolved_config",
        "",
        "    # Determine workspace root from runfiles or cwd",
        "    _runfiles_root = None",
        '    for base in (os.environ.get("RUNFILES_DIR", ""), os.environ.get("BAZEL_RUNFILES", "")):',
        '        if os.path.isdir(os.path.join(base, "_main")):',
        '            _runfiles_root = os.path.join(base, "_main")',
        "            break",
        "    workspace_root = rest[0] if rest else (os.environ.get(\"BUILD_WORKSPACE_DIRECTORY\", \"\") or _runfiles_root or os.getcwd())",
        '    if "BUILD_WORKSPACE_DIRECTORY" in os.environ and os.path.isdir(os.environ["BUILD_WORKSPACE_DIRECTORY"]):',
        '        os.chdir(os.environ["BUILD_WORKSPACE_DIRECTORY"])',
        "",
        "    # Find the manifest in runfiles",
        "    _manifest_path = None",
        '    manifest_name = "{}"'.format(_manifest_filename),
        '    for base in (os.environ.get("RUNFILES_DIR", ""), os.environ.get("BAZEL_RUNFILES", "")):',
        "        if base:",
        "            candidate = os.path.join(base, manifest_name)",
        "            if os.path.isfile(candidate):",
        "                _manifest_path = candidate",
        "                break",
        "",
        "    if not _manifest_path:",
        "        # Fallback: manifest is alongside the executable",
        '        _script_dir = os.path.dirname(os.path.abspath(__file__)) or "."',
        "        _manifest_path = os.path.join(_script_dir, manifest_name)",
        "",
        "    with open(_manifest_path) as f:",
        "        manifest_raw = f.read()",
        "        node_label = json.loads(manifest_raw).get(\"label\")",
        "",
        "    bazel_asm.__initialize__()",
        "    node_util = get_singleton(BazelNodeIdentifierUtility)",
        "    root_node = node_util.normalize(node_label)",
        "    loader = get_singleton(BazelManifestLoader)",
        "    storage = get_singleton(DagStorage)",
        "    loader.load_manifest(Manifest(manifest_raw), storage)",
        "    runner = get_singleton(BazelRunner)",
        "",
        '    print(f"Model config: {resolved_config}")',
        "    try:",
        "        res = runner.run_cleaning_pass(root_node)",
        "        result = res.success",
        "    except KeyboardInterrupt:",
        '        print("Interrupted.", file=sys.stderr)',
        "        sys.exit(130)",
        "    if not result:",
        '        print(f"Error: {res.summary}", file=sys.stderr)',
        "    sys.exit(0 if result else 1)",
        "",
        'if __name__ == "__main__":',
        "    main()",
        "",
    ]
    ctx.actions.write(
        output = _wrapper_py,
        content = "\n".join(_lines),
        is_executable = True,
    )

    # Return a py_binary via DefaultInfo
    # (We can't call py_binary from a rule implementation directly,
    #  so we return the wrapper as the executable)
    _dep_manifests = []
    for _dep in ctx.attr.deps:
        _dep_manifests.extend(_dep[DefaultInfo].files.to_list())

    # Include the generated config files for the bundled configs (the
    # //model_configs:all_configs bundle) plus the explicit `config`
    # attribute, so any of them can be selected at run time and found in
    # runfiles. Configs selected at run time that are NOT bundled are
    # resolved from bazel-bin instead.
    _config_files = []
    if ctx.attr.config:
        _config_files.extend(ctx.attr.config[DefaultInfo].files.to_list())
    _config_files.extend(ctx.attr._model_configs[DefaultInfo].files.to_list())

    # All transitive node manifests (via the manifest-collecting aspect), so
    # run-time graph loading can resolve the full star-dep closure: Bazel
    # runfiles are explicit, not transitive. The guide node's manifest also
    # reaches runfiles (the guide is declared separately from deps), so the
    # graph storage can resolve the guide node and wire its file into the
    # sandbox config.
    _manifest_depsets = [
        ctx.attr.node[OutputGroupInfo].manifests,
    ] + [dep[OutputGroupInfo].manifests for dep in ctx.attr.deps]
    if ctx.attr.guide:
        _manifest_depsets.append(ctx.attr.guide[OutputGroupInfo].manifests)

    _runfiles = ctx.runfiles(
        files = [
            _wrapper_py,
            _manifest,
        ] + _dep_manifests + _config_files,
        transitive_files = depset(
            transitive = _manifest_depsets + [
                ctx.attr.node[DefaultInfo].transitive_sources if hasattr(ctx.attr.node[DefaultInfo], "transitive_sources") else depset([]),
            ],
        ),
    ).merge(ctx.runfiles(transitive_files = ctx.attr._dag_runner[PyInfo].transitive_sources))

    return [
        DefaultInfo(
            executable = _wrapper_py,
            runfiles = _runfiles,
        ),
    ]

_update_ai_node_clean_rule = rule(
    implementation = _update_ai_node_clean_impl,
    executable = True,
    attrs = {
        "node": attr.label(
            mandatory = True,
            doc = "The node target (must produce a manifest)",
            aspects = [_collect_manifests],
        ),
        "deps": attr.label_list(
            doc = "Dependency node targets whose manifests are needed for graph resolution",
            aspects = [_collect_manifests],
        ),
        "guide": attr.label(
            aspects = [_collect_manifests],
            doc = "Optional guide node target whose manifest must reach runfiles " +
                  "for graph resolution (the guide is declared separately from deps).",
        ),
        "config": attr.label(
            providers = [DefaultInfo],
            doc = "Optional model_config target used as the default model " +
                  "configuration for this *_clean binary (overrides " +
                  "--define=MODEL_CONFIG; may still be overridden by --config " +
                  "or MODEL_CONFIG_TARGET / AGENT_CONFIG_TARGET at run time).",
        ),
        "_model_configs": attr.label(
            default = Label("//model_configs:all_configs"),
            providers = [DefaultInfo],
            doc = "Bundle of all model_config targets included in runfiles, so any " +
                  "bundled config can be selected at run time (--config, " +
                  "MODEL_CONFIG_TARGET, or a personal --define default) without a " +
                  "separate build. Add personal configs to //model_configs:all_configs.",
        ),
        "_dag_runner": attr.label(
            default = Label("//update_with_ai/lib:bazel_asm"),
            providers = [PyInfo],
        ),
    },
)

# ============================================================================
# Rule: update_ai_node_feedback (generates a feedback target per node)
# ============================================================================

def _update_ai_node_feedback_impl(ctx):
    """Generates a Python binary that delivers feedback to the node itself."""
    _node = ctx.attr.node
    _manifest = _node[DefaultInfo].files.to_list()[0]  # _manifest.json
    _manifest_filename = _manifest.basename  # just the filename

    # Generate a Python wrapper
    _wrapper_py = ctx.actions.declare_file(ctx.label.name + ".py")
    _lines = [
        "#!/usr/bin/env python3",
        "import json",
        "import sys",
        "import os",
        "",
        "# Ensure lib is importable from runfiles",
        "_runfiles_root = None",
        'for base in (os.environ.get("RUNFILES_DIR", ""), os.environ.get("BAZEL_RUNFILES", "")):',
        '    if base and os.path.isdir(base):',
        "        _runfiles_root = base",
        "        break",
        "if not _runfiles_root:",
        "    _runfiles_root = os.getcwd()",
        "for cand in (_runfiles_root, os.path.join(_runfiles_root, '_main'), os.path.join(_runfiles_root, 'update_with_ai'), os.path.join(_runfiles_root, 'update_python_with_ai'), os.path.join(_runfiles_root, '_main', 'update_with_ai'), os.path.join(_runfiles_root, '_main', 'update_python_with_ai')):",
        "    if os.path.isdir(cand) and cand not in sys.path:",
        "        sys.path.insert(0, cand)",
        "try:",
        "    from support.lib.lifecycle import get_singleton",
        "    from lib import bazel_asm",
        "    from lib.bazel_runner import BazelRunner",
        "    from lib.dag_storage import Feedback",
        "    from lib.bazel_node_id_utils import BazelNodeIdentifierUtility",
        "except ImportError:",
        "    try:",
        "        from update_python_with_ai.support.lib.lifecycle import get_singleton",
        "    except ImportError:",
        "        from update_with_ai.support.lib.lifecycle import get_singleton",
        "    from update_with_ai.lib import bazel_asm",
        "    from update_with_ai.lib.bazel_runner import BazelRunner",
        "    from update_with_ai.lib.dag_storage import Feedback",
        "    from update_with_ai.lib.bazel_node_id_utils import BazelNodeIdentifierUtility",
        "",
        "def main():",
        "    messages = sys.argv[1:]",
        "    # Determine workspace root from runfiles or cwd",
        "    _runfiles_root = None",
        '    for base in (os.environ.get("RUNFILES_DIR", ""), os.environ.get("BAZEL_RUNFILES", "")):',
        '        if os.path.isdir(os.path.join(base, "_main")):',
        '            _runfiles_root = os.path.join(base, "_main")',
        "            break",
        "    workspace_root = os.environ.get(\"BUILD_WORKSPACE_DIRECTORY\", \"\") or _runfiles_root or os.getcwd()",
        '    if "BUILD_WORKSPACE_DIRECTORY" in os.environ and os.path.isdir(os.environ["BUILD_WORKSPACE_DIRECTORY"]):',
        '        os.chdir(os.environ["BUILD_WORKSPACE_DIRECTORY"])',
        "",
        "    # Find the manifest in runfiles",
        "    _manifest_path = None",
        '    manifest_name = "{}"'.format(_manifest_filename),
        '    for base in (os.environ.get("RUNFILES_DIR", ""), os.environ.get("BAZEL_RUNFILES", "")):',
        "        if base:",
        "            candidate = os.path.join(base, manifest_name)",
        "            if os.path.isfile(candidate):",
        "                _manifest_path = candidate",
        "                break",
        "",
        "    if not _manifest_path:",
        "        # Fallback: manifest is alongside the executable",
        '        _script_dir = os.path.dirname(os.path.abspath(__file__)) or "."',
        "        _manifest_path = os.path.join(_script_dir, manifest_name)",
        "",
        "    with open(_manifest_path) as f:",
        "        node_label = json.load(f).get('label')",
        "",
        "    if not messages:",
        '        print("No feedback message given.", file=sys.stderr)',
        '        print("Usage: bazel run <this target> -- \\"feedback message\\" [more...]", file=sys.stderr)',
        "        sys.exit(1)",
        "",
        "    bazel_asm.__initialize__()",
        "    node_util = get_singleton(BazelNodeIdentifierUtility)",
        "    target_node = node_util.normalize(node_label)",
        "    runner = get_singleton(BazelRunner)",
        "    try:",
        "        for m in messages:",
        "            runner.inject_node_feedback(target_node, Feedback(content=m))",
        "    except KeyboardInterrupt:",
        '        print("Interrupted.", file=sys.stderr)',
        "        sys.exit(130)",
        "    sys.exit(0)",
        "",
        'if __name__ == "__main__":',
        "    main()",
        "",
    ]
    ctx.actions.write(
        output = _wrapper_py,
        content = "\n".join(_lines),
        is_executable = True,
    )

    # Return the wrapper as the executable with the manifest and lib sources
    # from the dag_cleaner runner.
    _runfiles = ctx.runfiles(
        files = [
            _wrapper_py,
            _manifest,
        ],
        transitive_files = ctx.attr.node[DefaultInfo].transitive_sources if hasattr(ctx.attr.node[DefaultInfo], "transitive_sources") else depset([]),
    ).merge(ctx.runfiles(transitive_files = ctx.attr._dag_runner[PyInfo].transitive_sources))

    return [
        DefaultInfo(
            executable = _wrapper_py,
            runfiles = _runfiles,
        ),
    ]

_update_ai_node_feedback_rule = rule(
    implementation = _update_ai_node_feedback_impl,
    executable = True,
    attrs = {
        "node": attr.label(
            mandatory = True,
            doc = "The node target (must produce a manifest)",
        ),
        "_dag_runner": attr.label(
            default = Label("//update_with_ai/lib:bazel_asm"),
            providers = [PyInfo],
        ),
    },
)

# ============================================================================
# Rule: update_ai_node_dirty (generates a dirty target per node)
# ============================================================================
#
# A gentler sibling of *_feedback: the CLI argument is delivered as a
# change-kind message to the node's own pending store (marking the node
# dirty), so when cleaned the node may succeed without changing. With no
# argument, the change text defaults to "check".

def _update_ai_node_dirty_impl(ctx):
    """Generates a Python binary that delivers a change message to the node itself."""
    _node = ctx.attr.node
    _manifest = _node[DefaultInfo].files.to_list()[0]  # _manifest.json
    _manifest_filename = _manifest.basename  # just the filename

    # Generate a Python wrapper
    _wrapper_py = ctx.actions.declare_file(ctx.label.name + ".py")
    _lines = [
        "#!/usr/bin/env python3",
        "import json",
        "import sys",
        "import os",
        "",
        "# Ensure lib is importable from runfiles",
        "_runfiles_root = None",
        'for base in (os.environ.get("RUNFILES_DIR", ""), os.environ.get("BAZEL_RUNFILES", "")):',
        '    if base and os.path.isdir(base):',
        "        _runfiles_root = base",
        "        break",
        "if not _runfiles_root:",
        "    _runfiles_root = os.getcwd()",
        "for cand in (_runfiles_root, os.path.join(_runfiles_root, '_main'), os.path.join(_runfiles_root, 'update_with_ai'), os.path.join(_runfiles_root, 'update_python_with_ai'), os.path.join(_runfiles_root, '_main', 'update_with_ai'), os.path.join(_runfiles_root, '_main', 'update_python_with_ai')):",
        "    if os.path.isdir(cand) and cand not in sys.path:",
        "        sys.path.insert(0, cand)",
        "try:",
        "    from support.lib.lifecycle import get_singleton",
        "    from lib import bazel_asm",
        "    from lib.bazel_runner import BazelRunner",
        "    from lib.dag_storage import Change",
        "    from lib.bazel_node_id_utils import BazelNodeIdentifierUtility",
        "except ImportError:",
        "    try:",
        "        from update_python_with_ai.support.lib.lifecycle import get_singleton",
        "    except ImportError:",
        "        from update_with_ai.support.lib.lifecycle import get_singleton",
        "    from update_with_ai.lib import bazel_asm",
        "    from update_with_ai.lib.bazel_runner import BazelRunner",
        "    from update_with_ai.lib.dag_storage import Change",
        "    from update_with_ai.lib.bazel_node_id_utils import BazelNodeIdentifierUtility",
        "",
        "def main():",
        "    # The change text defaults to 'check' when no argument is given.",
        "    change = sys.argv[1] if len(sys.argv) > 1 else 'check'",
        "    # Determine workspace root from runfiles or cwd",
        "    _runfiles_root = None",
        '    for base in (os.environ.get("RUNFILES_DIR", ""), os.environ.get("BAZEL_RUNFILES", "")):',
        '        if os.path.isdir(os.path.join(base, "_main")):',
        '            _runfiles_root = os.path.join(base, "_main")',
        "            break",
        "    workspace_root = os.environ.get(\"BUILD_WORKSPACE_DIRECTORY\", \"\") or _runfiles_root or os.getcwd()",
        '    if "BUILD_WORKSPACE_DIRECTORY" in os.environ and os.path.isdir(os.environ["BUILD_WORKSPACE_DIRECTORY"]):',
        '        os.chdir(os.environ["BUILD_WORKSPACE_DIRECTORY"])',
        "",
        "    # Find the manifest in runfiles",
        "    _manifest_path = None",
        '    manifest_name = "{}"'.format(_manifest_filename),
        '    for base in (os.environ.get("RUNFILES_DIR", ""), os.environ.get("BAZEL_RUNFILES", "")):',
        "        if base:",
        "            candidate = os.path.join(base, manifest_name)",
        "            if os.path.isfile(candidate):",
        "                _manifest_path = candidate",
        "                break",
        "",
        "    if not _manifest_path:",
        "        # Fallback: manifest is alongside the executable",
        '        _script_dir = os.path.dirname(os.path.abspath(__file__)) or "."',
        "        _manifest_path = os.path.join(_script_dir, manifest_name)",
        "",
        "    with open(_manifest_path) as f:",
        "        node_label = json.load(f).get('label')",
        "",
        "    bazel_asm.__initialize__()",
        "    node_util = get_singleton(BazelNodeIdentifierUtility)",
        "    target_node = node_util.normalize(node_label)",
        "    runner = get_singleton(BazelRunner)",
        "    try:",
        "        runner.mark_node_dirty(target_node, Change(content=change))",
        "    except KeyboardInterrupt:",
        '        print("Interrupted.", file=sys.stderr)',
        "        sys.exit(130)",
        "    sys.exit(0)",
        "",
        'if __name__ == "__main__":',
        "    main()",
        "",
    ]
    ctx.actions.write(
        output = _wrapper_py,
        content = "\n".join(_lines),
        is_executable = True,
    )

    # Return the wrapper as the executable with the manifest and lib sources
    # from the dag_cleaner runner.
    _runfiles = ctx.runfiles(
        files = [
            _wrapper_py,
            _manifest,
        ],
        transitive_files = ctx.attr.node[DefaultInfo].transitive_sources if hasattr(ctx.attr.node[DefaultInfo], "transitive_sources") else depset([]),
    ).merge(ctx.runfiles(transitive_files = ctx.attr._dag_runner[PyInfo].transitive_sources))

    return [
        DefaultInfo(
            executable = _wrapper_py,
            runfiles = _runfiles,
        ),
    ]

_update_ai_node_dirty_rule = rule(
    implementation = _update_ai_node_dirty_impl,
    executable = True,
    attrs = {
        "node": attr.label(
            mandatory = True,
            doc = "The node target (must produce a manifest)",
        ),
        "_dag_runner": attr.label(
            default = Label("//update_with_ai/lib:bazel_asm"),
            providers = [PyInfo],
        ),
    },
)

# ============================================================================
# Rule: update_ai_node_change (generates a change target per node)
# ============================================================================
#
# Pretends the node was cleaned with changes: the CLI argument becomes the
# change part of a message broadcast to the node's known reverse dependencies
# (per build_runner's broadcast_change), and the node's own data is cleared —
# for changes made outside of agent cleaning.

def _update_ai_node_change_impl(ctx):
    """Generates a Python binary that broadcasts a change from the node."""
    _node = ctx.attr.node
    _manifest = _node[DefaultInfo].files.to_list()[0]  # _manifest.json
    _manifest_filename = _manifest.basename  # just the filename

    # Generate a Python wrapper
    _wrapper_py = ctx.actions.declare_file(ctx.label.name + ".py")
    _lines = [
        "#!/usr/bin/env python3",
        "import json",
        "import sys",
        "import os",
        "",
        "# Ensure lib is importable from runfiles",
        "_runfiles_root = None",
        'for base in (os.environ.get("RUNFILES_DIR", ""), os.environ.get("BAZEL_RUNFILES", "")):',
        '    if base and os.path.isdir(base):',
        "        _runfiles_root = base",
        "        break",
        "if not _runfiles_root:",
        "    _runfiles_root = os.getcwd()",
        "for cand in (_runfiles_root, os.path.join(_runfiles_root, '_main'), os.path.join(_runfiles_root, 'update_with_ai'), os.path.join(_runfiles_root, 'update_python_with_ai'), os.path.join(_runfiles_root, '_main', 'update_with_ai'), os.path.join(_runfiles_root, '_main', 'update_python_with_ai')):",
        "    if os.path.isdir(cand) and cand not in sys.path:",
        "        sys.path.insert(0, cand)",
        "try:",
        "    from support.lib.lifecycle import get_singleton",
        "    from lib import bazel_asm",
        "    from lib.bazel_runner import BazelRunner",
        "    from lib.dag_storage import Change",
        "    from lib.bazel_node_id_utils import BazelNodeIdentifierUtility",
        "except ImportError:",
        "    try:",
        "        from update_python_with_ai.support.lib.lifecycle import get_singleton",
        "    except ImportError:",
        "        from update_with_ai.support.lib.lifecycle import get_singleton",
        "    from update_with_ai.lib import bazel_asm",
        "    from update_with_ai.lib.bazel_runner import BazelRunner",
        "    from update_with_ai.lib.dag_storage import Change",
        "    from update_with_ai.lib.bazel_node_id_utils import BazelNodeIdentifierUtility",
        "",
        "def main():",
        "    args = sys.argv[1:]",
        "    if not args:",
        '        print("No change text given.", file=sys.stderr)',
        '        print("Usage: bazel run <this target> -- \\"change text\\"", file=sys.stderr)',
        "        sys.exit(1)",
        "    change = args[0]",
        "    # Determine workspace root from runfiles or cwd",
        "    _runfiles_root = None",
        '    for base in (os.environ.get("RUNFILES_DIR", ""), os.environ.get("BAZEL_RUNFILES", "")):',
        '        if os.path.isdir(os.path.join(base, "_main")):',
        '            _runfiles_root = os.path.join(base, "_main")',
        "            break",
        "    workspace_root = os.environ.get(\"BUILD_WORKSPACE_DIRECTORY\", \"\") or _runfiles_root or os.getcwd()",
        '    if "BUILD_WORKSPACE_DIRECTORY" in os.environ and os.path.isdir(os.environ["BUILD_WORKSPACE_DIRECTORY"]):',
        '        os.chdir(os.environ["BUILD_WORKSPACE_DIRECTORY"])',
        "",
        "    # Find the manifest in runfiles",
        "    _manifest_path = None",
        '    manifest_name = "{}"'.format(_manifest_filename),
        '    for base in (os.environ.get("RUNFILES_DIR", ""), os.environ.get("BAZEL_RUNFILES", "")):',
        "        if base:",
        "            candidate = os.path.join(base, manifest_name)",
        "            if os.path.isfile(candidate):",
        "                _manifest_path = candidate",
        "                break",
        "",
        "    if not _manifest_path:",
        "        # Fallback: manifest is alongside the executable",
        '        _script_dir = os.path.dirname(os.path.abspath(__file__)) or "."',
        "        _manifest_path = os.path.join(_script_dir, manifest_name)",
        "",
        "    with open(_manifest_path) as f:",
        "        node_label = json.load(f).get('label')",
        "",
        "    bazel_asm.__initialize__()",
        "    node_util = get_singleton(BazelNodeIdentifierUtility)",
        "    origin_node = node_util.normalize(node_label)",
        "    runner = get_singleton(BazelRunner)",
        "    try:",
        "        runner.broadcast_node_change(origin_node, Change(content=change))",
        "    except KeyboardInterrupt:",
        '        print("Interrupted.", file=sys.stderr)',
        "        sys.exit(130)",
        "    sys.exit(0)",
        "",
        'if __name__ == "__main__":',
        "    main()",
        "",
    ]
    ctx.actions.write(
        output = _wrapper_py,
        content = "\n".join(_lines),
        is_executable = True,
    )

    # Return the wrapper as the executable with the manifest and lib sources
    # from the dag_cleaner runner.
    _runfiles = ctx.runfiles(
        files = [
            _wrapper_py,
            _manifest,
        ],
        transitive_files = ctx.attr.node[DefaultInfo].transitive_sources if hasattr(ctx.attr.node[DefaultInfo], "transitive_sources") else depset([]),
    ).merge(ctx.runfiles(transitive_files = ctx.attr._dag_runner[PyInfo].transitive_sources))

    return [
        DefaultInfo(
            executable = _wrapper_py,
            runfiles = _runfiles,
        ),
    ]

_update_ai_node_change_rule = rule(
    implementation = _update_ai_node_change_impl,
    executable = True,
    attrs = {
        "node": attr.label(
            mandatory = True,
            doc = "The node target (must produce a manifest)",
        ),
        "_dag_runner": attr.label(
            default = Label("//update_with_ai/lib:bazel_asm"),
            providers = [PyInfo],
        ),
    },
)

# ============================================================================
# Rule: update_ai_node_prompt (generates a prompt target per node)
# ============================================================================

def _update_ai_node_prompt_impl(ctx):
    """Generates a Python binary that prints the node's initial agent prompt."""
    _node = ctx.attr.node
    _manifest = _node[DefaultInfo].files.to_list()[0]  # _manifest.json
    _manifest_filename = _manifest.basename  # just the filename

    # Generate a Python wrapper that reads the manifest and prints the prompt.
    _wrapper_py = ctx.actions.declare_file(ctx.label.name + ".py")
    _lines = [
        "#!/usr/bin/env python3",
        "import json",
        "import os",
        "import sys",
        "",
        "def main():",
        "    # Find the manifest in runfiles",
        "    _manifest_path = None",
        '    manifest_name = "{}"'.format(_manifest_filename),
        '    for base in (os.environ.get("RUNFILES_DIR", ""), os.environ.get("BAZEL_RUNFILES", "")):',
        "        if base:",
        "            candidate = os.path.join(base, manifest_name)",
        "            if os.path.isfile(candidate):",
        "                _manifest_path = candidate",
        "                break",
        "",
        "    if not _manifest_path:",
        "        # Fallback: manifest is alongside the executable",
        '        _script_dir = os.path.dirname(os.path.abspath(__file__)) or "."',
        "        _manifest_path = os.path.join(_script_dir, manifest_name)",
        "",
        "    with open(_manifest_path) as f:",
        "        prompt = json.load(f).get('prompt', '')",
        "",
        "    print(prompt)",
        "",
        'if __name__ == "__main__":',
        "    main()",
        "",
    ]
    ctx.actions.write(
        output = _wrapper_py,
        content = "\n".join(_lines),
        is_executable = True,
    )

    # Return the wrapper as the executable with the manifest in runfiles.
    _runfiles = ctx.runfiles(files = [_wrapper_py, _manifest])

    return [
        DefaultInfo(
            executable = _wrapper_py,
            runfiles = _runfiles,
        ),
    ]

_update_ai_node_prompt_rule = rule(
    implementation = _update_ai_node_prompt_impl,
    executable = True,
    attrs = {
        "node": attr.label(
            mandatory = True,
            doc = "The node target (must produce a manifest)",
        ),
    },
)

# ============================================================================
# Rule: bazel_ai_graph_dag
# ============================================================================

def _bazel_ai_graph_dag_impl(ctx):
    """Implementation of bazel_ai_graph_dag rule."""

    # Create the graph manifest
    manifest = ctx.actions.declare_file("{}_graph.json".format(ctx.label.name))

    # Build the graph structure
    graph_data = {
        "root": str(ctx.attr.root.label),
        "nodes": {},
    }

    # Add root node info
    graph_data["nodes"][str(ctx.attr.root.label)] = {
        "label": str(ctx.attr.root.label),
        "name": ctx.attr.root.label.name,
    }

    # Add dependencies
    for dep in ctx.attr.deps:
        if hasattr(dep, "label"):
            graph_data["nodes"][str(dep.label)] = {
                "label": str(dep.label),
                "name": dep.label.name,
            }

    ctx.actions.write(
        output = manifest,
        content = json.encode(graph_data),
    )

    return [
        DefaultInfo(
            files = depset([manifest]),
            runfiles = ctx.runfiles(files = [manifest]),
        ),
    ]

_bazel_ai_graph_dag_rule = rule(
    implementation = _bazel_ai_graph_dag_impl,
    attrs = {
        "root": attr.label(
            mandatory = True,
            doc = "Root node target",
        ),
        "deps": attr.label_list(
            doc = "List of dependency node targets",
        ),
    },
)

# Export symbols
# At module level, the macro shadows the rule — this is the intended behavior.
# Users call the macro `update_with_ai()`, which internally calls
# the rule `_update_with_ai_rule()` to produce the manifest target.
bazel_ai_graph_dag = _bazel_ai_graph_dag_rule
collect_node_manifests = _collect_manifests
