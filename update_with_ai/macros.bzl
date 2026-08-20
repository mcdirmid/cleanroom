"""
Starlark rules and macro for AI agent nodes.

This module provides:
- update_with_ai rule: Produces a manifest file describing a node
- update_with_ai macro: Convenience wrapper that also generates a *_clean target
- bazel_ai_graph rule: Produces a graph manifest for the entire DAG

The approach uses DATA-DRIVEN loading at runtime, NOT code generation:
- Analysis phase: Build manifest files with graph structure
- Execution phase: Python runtime loads manifests and constructs objects

Agent/model configuration: the generated *_clean binaries resolve an
`agent_config` target (see update_with_ai/agent_config.bzl) in this order:
  1. --config //pkg:name passed to the binary (bazel run ... -- --config //pkg:name)
  2. AGENT_CONFIG_TARGET environment variable
  3. the `config` attribute on update_with_ai(...)
  4. the --define=AGENT_CONFIG=//pkg:name build setting (command line,
     .bazelrc, or the user's ~/.bazelrc for a personal default)
  5. the //agent_configs:default convention

Usage:
  update_with_ai(
    name = "my_node",
    prompt = "...",
  )
  # Automatically generates:
  #   //pkg:my_node           — the node manifest
  #   //pkg:my_node_clean     — binary that runs DAG cleaning on this node
  #   //pkg:my_node_feedback  — binary that injects feedback into dependencies
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

    # Build the manifest
    manifest_content = {
        "label": str(ctx.label),
        "name": ctx.attr.name,
        "prompt": ctx.attr.prompt,
        "tools": [str(t) for t in ctx.attr.tools],
        "deps": _all_deps,
        "silent_deps": [str(dep.label) for dep in ctx.attr.silent_deps],
        "feedback_deps": [str(dep.label) for dep in ctx.attr.feedback_deps],
        "star_deps": [str(dep.label) for dep in ctx.attr.star_deps],
        "srcs": [str(s) for s in ctx.attr.srcs],
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

# Rule definition (private name)
_update_with_ai_rule = rule(
    implementation = _update_with_ai_impl,
    attrs = {
        "prompt": attr.string(
            mandatory = True,
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
            doc = "List of dependency node targets whose transitive closure over deps/star deps is readable; these nodes are automatically included in deps",
        ),
        "srcs": attr.string_list(
            doc = "File paths the agent can write (these files need not pre-exist)",
        ),
        "silent_srcs": attr.label_list(
            doc = "Files agent can write that are NOT readable by deps",
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
        prompt,
        tools = [],
        deps = [],
        silent_deps = [],
        feedback_deps = [],
        star_deps = [],
        srcs = [],
        silent_srcs = [],
        verify = "",
        config = None,
        visibility = None):
    """
    Macro to create an AI agent node with clean and feedback targets.

    This macro wraps the update_with_ai rule and automatically generates two
    sibling targets:
      - `name + "_clean"`     runs DAG cleaning on the node
      - `name + "_feedback"`  delivers CLI feedback messages to the node's own
                              pending messages, marking it dirty with feedback
      - `name + "_prompt"`    prints the node's initial agent prompt
                              (bazel run //pkg:name_prompt)

    The clean target runs the DAG cleaning logic:
    1. Reads the node's manifest (JSON)
    2. Gets the node label from the manifest
    3. Builds the graph (loads all deps)
    4. Runs the cleaning pass

    The feedback target delivers each positional CLI argument as a feedback
    message to the node's own pending message store, so the node becomes dirty
    and a subsequent *_clean run processes the feedback.

    Agent/model configuration: the *_clean target resolves an `agent_config`
    target (see update_with_ai/agent_config.bzl) in this priority order:
      1. `--config //pkg:name` passed to the *_clean binary
         (bazel run //pkg:node_clean -- --config //pkg:name)
      2. The AGENT_CONFIG_TARGET environment variable
      3. The `config` attribute of this macro (if given)
      4. The --define=AGENT_CONFIG=//pkg:name build setting (command line,
         .bazelrc, or the user's ~/.bazelrc for a personal default)
      5. The //agent_configs:default convention

    Usage:
      bazel run //pkg:node_name_clean     # runs cleaning pass on node_name
      bazel run //pkg:node_name_feedback -- "feedback message" ["more"...]
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
            over deps/star deps is readable; these nodes are automatically
            included in deps (cleaned before run)
        srcs: Files agent can write that are readable by deps
        silent_srcs: Files agent can write that are NOT readable by deps
        verify: Shell command to run when the agent calls verify()
            (default: empty = no verify tool)
        config: Optional agent_config target label used as the default
            configuration for this node's *_clean target (overrides
            --define=AGENT_CONFIG; may still be overridden by --config or
            AGENT_CONFIG_TARGET at run time).
        visibility: Optional visibility applied to all targets this macro
            generates — the node manifest (`name`), the clean target
            (`name + "_clean"`), the feedback target
            (`name + "_feedback"`), and the prompt target
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

    # Create the node target (using the rule directly)
    _update_with_ai_rule(
        name = name,
        prompt = prompt,
        tools = tools,
        deps = deps,
        silent_deps = silent_deps,
        feedback_deps = feedback_deps,
        star_deps = star_deps,
        srcs = srcs,
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

    # Create a prompt target that prints the node's initial agent prompt
    # (bazel run //pkg:name_prompt).
    _prompt_target = name + "_prompt"
    _update_ai_node_prompt_rule(
        name = _prompt_target,
        node = ":{}".format(name),  # the node manifest
        **_rule_kwargs
    )

# ============================================================================
# Aspect: collect all transitive node manifests for runfiles
# ============================================================================

def _collect_manifests_impl(target, ctx):
    """Collect the target's own manifest plus all transitive node manifests.

    Bazel runfiles are explicit, not transitive: a node target's runfiles
    contain only its own manifest, so a *_clean binary would not see the
    manifests of its deps' deps. This aspect walks the node graph (deps,
    silent_deps, feedback_deps, star_deps) and returns every *_manifest.json
    reachable, so consumers (the clean rule, the lint test rule) can put the
    full transitive manifest set into runfiles for run-time graph loading.
    """
    own = [
        f
        for f in target[DefaultInfo].files.to_list()
        if f.basename.endswith("_manifest.json")
    ]
    transitive = []
    for attr_name in ("deps", "silent_deps", "feedback_deps", "star_deps"):
        for dep in getattr(ctx.rule.attr, attr_name, []):
            if OutputGroupInfo in dep:
                manifests = getattr(dep[OutputGroupInfo], "manifests", None)
                if manifests != None:
                    transitive.append(manifests)
    return [OutputGroupInfo(manifests = depset(own, transitive = transitive))]

_collect_manifests = aspect(
    implementation = _collect_manifests_impl,
    attr_aspects = ["deps", "silent_deps", "feedback_deps", "star_deps"],
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

    # Resolve the default agent/model configuration target for this binary:
    #   1. the `config` attribute on update_with_ai(...) — most specific
    #   2. the --define=AGENT_CONFIG=//pkg:name build setting (command line,
    #      .bazelrc, or the user's ~/.bazelrc) — the (personal) default
    #   3. the //agent_configs:default convention
    # At run time the wrapper still lets --config / AGENT_CONFIG_TARGET
    # override this default (see the generated main()).
    _config_attr = ctx.attr.config
    _define_target = ctx.var.get("AGENT_CONFIG", "")
    if _config_attr:
        _default_config_target = _apparent_label(_config_attr.label)
    elif _define_target:
        _default_config_target = _define_target
    else:
        _default_config_target = "//agent_configs:default"

    # Generate a Python wrapper
    _wrapper_py = ctx.actions.declare_file(ctx.label.name + ".py")
    _lines = [
        "#!/usr/bin/env python3",
        "import json",
        "import sys",
        "import os",
        "",
        "# Default agent_config target (from the config attribute, the",
        "# --define=AGENT_CONFIG build setting, or the //agent_configs:default convention).",
        "_DEFAULT_CONFIG_TARGET = {}".format(json.encode(_default_config_target)),
        "",
        "# Ensure lib is importable from runfiles",
        "_runfiles_root = None",
        'for base in (os.environ.get("RUNFILES_DIR", ""), os.environ.get("BAZEL_RUNFILES", "")):',
        '    if os.path.isdir(os.path.join(base, "lib")):',
        "        _runfiles_root = base",
        "        break",
        "if not _runfiles_root:",
        "    _runfiles_root = os.getcwd()",
        "sys.path.insert(0, _runfiles_root)",
        "from update_with_ai.lib.bazel_runner_impl import BazRunnerImpl",
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
        '                print("--config requires a target label (e.g. //agent_configs:default)", file=sys.stderr)',
        "                sys.exit(2)",
        "            config_target = args[i]",
        '        elif args[i].startswith("--config="):',
        '            config_target = args[i].split("=", 1)[1]',
        "        else:",
        "            rest.append(args[i])",
        "        i += 1",
        "    resolved_config = config_target or os.environ.get(\"AGENT_CONFIG_TARGET\") or _DEFAULT_CONFIG_TARGET",
        "",
        "    # Determine workspace root from runfiles or cwd",
        "    _runfiles_root = None",
        '    for base in (os.environ.get("RUNFILES_DIR", ""), os.environ.get("BAZEL_RUNFILES", "")):',
        '        if os.path.isdir(os.path.join(base, "_main")):',
        '            _runfiles_root = os.path.join(base, "_main")',
        "            break",
        "    workspace_root = rest[0] if rest else (_runfiles_root or os.getcwd())",
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
        '        node_label = json.load(f).get("label")',
        "",
        "    runner = BazRunnerImpl()",
        '    print(f"Agent config: {resolved_config}")',
        "    result = runner.run_dag(node_label, workspace_root, config_target=resolved_config)",
        "    if isinstance(result, tuple):",
        "        success, error = result",
        "        sys.exit(0 if success else 1)",
        "    else:",
        "        sys.exit(0)",
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
    # //agent_configs:all_configs bundle) plus the explicit `config`
    # attribute, so any of them can be selected at run time and found in
    # runfiles. Configs selected at run time that are NOT bundled are
    # resolved from bazel-bin instead.
    _config_files = []
    if ctx.attr.config:
        _config_files.extend(ctx.attr.config[DefaultInfo].files.to_list())
    _config_files.extend(ctx.attr._agent_configs[DefaultInfo].files.to_list())

    # All transitive node manifests (via the manifest-collecting aspect), so
    # run-time graph loading can resolve the full star-dep closure: Bazel
    # runfiles are explicit, not transitive.
    _manifest_depsets = [
        ctx.attr.node[OutputGroupInfo].manifests,
    ] + [dep[OutputGroupInfo].manifests for dep in ctx.attr.deps]

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
        "config": attr.label(
            providers = [DefaultInfo],
            doc = "Optional agent_config target used as the default agent/model " +
                  "configuration for this *_clean binary (overrides " +
                  "--define=AGENT_CONFIG; may still be overridden by --config " +
                  "or AGENT_CONFIG_TARGET at run time).",
        ),
        "_agent_configs": attr.label(
            default = Label("//agent_configs:all_configs"),
            providers = [DefaultInfo],
            doc = "Bundle of all agent_config targets included in runfiles, so any " +
                  "bundled config can be selected at run time (--config, " +
                  "AGENT_CONFIG_TARGET, or a personal --define default) without a " +
                  "separate build. Add personal configs to //agent_configs:all_configs.",
        ),
        "_dag_runner": attr.label(
            default = Label("//update_with_ai/lib:bazel_runner_impl"),
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
        '    if os.path.isdir(os.path.join(base, "lib")):',
        "        _runfiles_root = base",
        "        break",
        "if not _runfiles_root:",
        "    _runfiles_root = os.getcwd()",
        "sys.path.insert(0, _runfiles_root)",
        "from update_with_ai.lib.bazel_runner_impl import BazRunnerImpl",
        "from update_with_ai.lib.dag_clean_logic import FailureResult",
        "",
        "def main():",
        "    messages = sys.argv[1:]",
        "    # Determine workspace root from runfiles or cwd",
        "    _runfiles_root = None",
        '    for base in (os.environ.get("RUNFILES_DIR", ""), os.environ.get("BAZEL_RUNFILES", "")):',
        '        if os.path.isdir(os.path.join(base, "_main")):',
        '            _runfiles_root = os.path.join(base, "_main")',
        "            break",
        "    workspace_root = _runfiles_root or os.getcwd()",
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
        "    runner = BazRunnerImpl()",
        "    result = runner.inject_feedback(node_label, workspace_root, messages)",
        "    if isinstance(result, tuple):",
        "        success, error = result",
        "        if isinstance(error, FailureResult):",
        '            print(f"Error: {error}", file=sys.stderr)',
        "        sys.exit(0 if success else 1)",
        "    else:",
        "        sys.exit(0)",
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
    # from the dag runner.
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
            default = Label("//update_with_ai/lib:bazel_runner_impl"),
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
