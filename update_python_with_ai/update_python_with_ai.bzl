"""Specification-node entry points.

update_python_with_ai creates a high-level specification (HLS) node, a
low-level specification (LLS) node, a lib-python node, a test node (for
implementations), and a QA arbiter node (for implementations). All are thin
wrappers over update_with_ai (update_with_ai.bzl): they differ only in the
spec-specific data they pass — the prompt, the guide dep, the module deps,
and a *_lint test target that gates the node's verify tool (hls_lint for HLS
nodes, lls_lint for LLS nodes; the lib and test nodes verify through the
type-check / test targets in the BUILD files one level up, and the QA node
verifies by running the tests via bazel test). All node machinery (manifest,
*_clean, *_feedback, *_dirty, *_change, *_prompt targets) comes from
update_with_ai.

The macro returns its own label (":" + name) so a BUILD file can bind the
result to a variable and pass it to a dependent node's module deps. Module deps
are plain labels (same or other packages); the graph is resolved at run
time from the loaded manifests.
"""

load("//update_with_ai/support/lib:update_with_ai.bzl", "collect_node_manifests", "update_with_ai")

def _apparent_label_str(label):
    """Return the apparent (user-facing) label for a main-repo label.

    With bzlmod, str(label) yields the canonical repository-qualified form;
    the apparent form (//pkg:name) is what users write. Used for prompt
    text only.
    """
    s = str(label)
    if s.startswith("@" + "@"):
        s = s[2:]
    elif s.startswith("@") and "//" in s:
        s = s[s.index("//"):]
    return s

# ============================================================================
# Specification lint rules: hls_lint and lls_lint
# ============================================================================
#
# Each lint rule creates a bazel test target that lints the spec file and
# verifies that every spec referenced in the text is covered by the lint's
# deps (the "dependencies are synced" check). hls_lint (walk mode) reads the
# covered spec paths at test time from each spec_dep's manifest in runfiles
# (data-driven transitive closure); lls_lint (direct mode) passes exactly the
# module_deps md files (dep_srcs) — the dependency comment lists the direct
# deps, and the transitive closure lives in the node's star_deps for
# run-time reading. hls_lint validates high-level specs per
# update_python_with_ai/guides/high_level_spec.md; lls_lint validates
# low-level specs per update_python_with_ai/guides/high_to_low.md.


def _spec_lint_test_impl(ctx):
    """Implementation of a spec-lint test rule: a test that lints a spec file.

    Shared by the hls_lint and lls_lint rules; the linter script and the
    reference corpus come from the private `_linter` and `_corpus` attrs.
    """

    # The spec files to lint.
    src_files = ctx.files.srcs
    src_args = " ".join(['"$ws"/{}'.format(f.short_path) for f in src_files])
    linter = ctx.file._linter.short_path

    script = ctx.actions.declare_file(ctx.label.name + ".sh")

    # Direct-deps mode (lls_lint): the --deps list is exactly the specified
    # module-dep md files (dep_srcs) plus the external-doc files
    # (external_deps). The dependency comment lists the direct deps, so no
    # transitive closure is computed here; the closure lives in the node's
    # star_deps (module_deps) for run-time reading.
    if ctx.attr._direct_deps:
        dep_files = ctx.files.dep_srcs
        if dep_files:
            deps_literal = " ".join(['"$ws"/{}'.format(f.short_path) for f in dep_files])
            deps_cmd = 'python3 "$ws/{linter}" --deps {deps} -- {targets}\n'.format(
                linter = linter,
                deps = deps_literal,
                targets = src_args,
            )
        else:
            deps_cmd = 'python3 "$ws/{linter}" {targets}\n'.format(linter = linter, targets = src_args)
    # Walk mode (hls_lint): each spec_dep's manifest (in runfiles) lists the
    # spec files it owns; the test script reads them at runtime and passes
    # the package-qualified paths to the linter as --deps. The closure is
    # computed from the manifests: the module deps' own sources plus,
    # recursively, the sources of every node in their deps/star_deps closure
    # (never silent_deps), so lint coverage matches exactly what the agent
    # can read at run time.
    else:
        dep_manifest_paths = [f.short_path for f in ctx.files.spec_deps]
        if dep_manifest_paths:
            paths_literal = " ".join(dep_manifest_paths)
            deps_cmd = (
                'deps=$("${{PYTHON:-python3}}" - "$ws" {paths} <<\'PYEOF\'\n' +
                "import json, os, sys\n" +
                "def rel(name):\n" +
                "    s = name\n" +
                "    if s.startswith('@' + '@'):\n" +
                "        s = s[2:]\n" +
                "    elif s.startswith('@') and '//' in s:\n" +
                "        s = s[s.index('//'):]\n" +
                "    if s.startswith('//'):\n" +
                "        s = s[2:]\n" +
                "    return s.replace(':', '/') + '_manifest.json'\n" +
                "ws, paths = sys.argv[1], sys.argv[2:]\n" +
                "out = []\n" +
                "seen = set()\n" +
                "queue = list(paths)\n" +
                "while queue:\n" +
                "    p = queue.pop(0)\n" +
                "    if p in seen:\n" +
                "        continue\n" +
                "    seen.add(p)\n" +
                "    mpath = os.path.join(ws, p)\n" +
                "    if not os.path.isfile(mpath):\n" +
                "        continue\n" +
                "    with open(mpath) as f:\n" +
                "        m = json.load(f)\n" +
                "    s = m.get('src')\n" +
                "    if s:\n" +
                "        out.append(os.path.join(ws, os.path.dirname(p), s))\n" +
                "    follow = list(m.get('deps', []))\n" +
                "    for sd in m.get('star_deps', []):\n" +
                "        if sd not in follow:\n" +
                "            follow.append(sd)\n" +
                "    for fd in m.get('feedback_deps', []):\n" +
                "        if fd not in follow:\n" +
                "            follow.append(fd)\n" +
                "    for d in follow:\n" +
                "        queue.append(rel(d))\n" +
                "print(' '.join(sorted(out)))\n" +
                "PYEOF\n)\n" +
                'if [ -n "$deps" ]; then\n' +
                '    python3 "$ws/{linter}" --deps $deps -- {targets}\n' +
                "else\n" +
                '    python3 "$ws/{linter}" {targets}\n' +
                "fi\n"
            ).format(linter = linter, paths = paths_literal, targets = src_args)
        else:
            deps_cmd = 'python3 "$ws/{linter}" {targets}\n'.format(linter = linter, targets = src_args)
    script_content = (
        "#!/bin/bash\n" +
        "set -euo pipefail\n" +
        'ws="$TEST_SRCDIR/${TEST_WORKSPACE:-cleanroom}"\n' +
        deps_cmd
    )
    ctx.actions.write(output = script, content = script_content)

    # All transitive spec-dep manifests (via the manifest-collecting aspect),
    # so the run-time closure walk in the script below can resolve the whole
    # deps/star_deps closure (Bazel runfiles are explicit, not transitive).
    transitive_manifests = depset(
        transitive = [dep[OutputGroupInfo].manifests for dep in ctx.attr.spec_deps],
    )

    runfiles = ctx.runfiles(
        files = (
            [ctx.file._linter] + ctx.files._corpus + src_files +
            ctx.files.spec_deps + ctx.files.dep_srcs
        ),
        transitive_files = transitive_manifests,
    )
    return [
        DefaultInfo(executable = script, runfiles = runfiles),
    ]

_hls_lint_test = rule(
    implementation = _spec_lint_test_impl,
    test = True,
    attrs = {
        "srcs": attr.label_list(
            allow_files = True,
            doc = "Spec file(s) to lint",
        ),
        "spec_deps": attr.label_list(
            doc = "Spec dependency node targets whose coverage is verified against the text's references",
            aspects = [collect_node_manifests],
        ),
        "dep_srcs": attr.label_list(
            allow_files = True,
            doc = "Dep spec files whose Data Types names the closure checks import against",
        ),
        "_linter": attr.label(
            default = Label("//update_with_ai/support/lib:hls_lint.py"),
            allow_single_file = True,
        ),
        "_direct_deps": attr.bool(
            default = False,
            doc = "True when --deps comes from dep_srcs directly; False when it comes from the spec_deps manifest closure walk (hls_lint)",
        ),
        "_corpus": attr.label(
            default = Label("//update_with_ai/specs:high_specs"),
            doc = "Canonical spec corpus used for term-ownership reference resolution",
        ),
    },
)

def _lls_lint_test_impl(ctx):
    src_file = ctx.file.src
    dep_files = ctx.files.dep_srcs
    tool = ctx.file._tool
    script = ctx.actions.declare_file(ctx.label.name + ".sh")

    all_files = [src_file] + dep_files
    files_str = " ".join(['"$ws/{}"'.format(f.short_path) for f in all_files])

    script_content = (
        "#!/bin/bash\n" +
        "set -euo pipefail\n" +
        'ws="$TEST_SRCDIR/${{TEST_WORKSPACE:-cleanroom}}"\n' +
        'python3 "$ws/{tool}" --check {files}\n'
    ).format(
        tool = tool.short_path,
        files = files_str,
    )
    ctx.actions.write(output = script, content = script_content)
    runfiles = ctx.runfiles(files = [tool] + all_files)
    return [DefaultInfo(executable = script, runfiles = runfiles)]

_lls_lint_test = rule(
    implementation = _lls_lint_test_impl,
    test = True,
    attrs = {
        "src": attr.label(
            allow_single_file = True,
            mandatory = True,
            doc = "Grounding .pyi file to check",
        ),
        "dep_srcs": attr.label_list(
            allow_files = True,
            doc = "Dep grounding .pyi files for symbol linking",
        ),
        "_tool": attr.label(
            default = Label("//update_with_ai/support/lib:grounding_tool.py"),
            allow_single_file = True,
        ),
    },
)

# ============================================================================
# Macro: update_python_with_ai (specification nodes)
# ============================================================================

def _update_python_with_ai(name, prompt = "", src = "", deps = [], module_deps = [], star_deps = [], feedback_deps = [], silent_deps = [], silent_srcs = [], template = None, template_parameters = None, guide = None, allows_step_mode = True, verify = "", visibility = None):
    """Create a spec node by delegating to update_with_ai.

    The single common spec-node entry: forwards the spec-specific arguments
    to update_with_ai (which generates the node, *_clean, *_feedback, and
    *_prompt targets) and returns the node's own label. The module deps are
    kept separate from the declared deps and passed as star_deps: they are
    cleaned before run and their sources (and, recursively, the sources of
    their whole deps/star_deps closure) are readable by the node.

    Args:
        name: Target name.
        prompt: The agent prompt for the spec node.
        src: The spec file path the agent writes.
        deps: Declared readable dependency node labels (e.g. the guide).
        module_deps: Whole-module spec targets the current spec depends on
            (must be _update_python_with_ai targets); their module names feed
            the module pyright_deps. Passed to update_with_ai as star_deps.
        star_deps: Additional dependency node labels passed directly to
            update_with_ai as star_deps (e.g. a spec-part target like
            "<name>_low"); combined with module_deps. Their transitive
            closure over star deps is readable by the node.
        feedback_deps: Dependency node labels that can receive feedback from
            this node (the node's blame targets); automatically included in
            deps, so their declared sources are readable.
        silent_deps: Declared silent dependency node labels (cleaned before
            the node; their sources are not readable to it).
        silent_srcs: Paths (relative to the node's package directory) the
            agent can write that deps cannot read (e.g. a package BUILD
            file one level up).
        template: Optional template file label whose content initializes the
            spec file at run start when the file does not exist on disk.
        guide: Optional node target whose declared source is the run's guide.
        allows_step_mode: Whether the node permits guide step mode.
        verify: Shell command to run when the agent calls verify()
            (default: empty = no verify tool).
        visibility: Optional visibility applied to all generated targets;
            needed for cross-package deps.

    Returns:
        The node's own label (":" + name).
    """

    # Module deps are passed as star_deps (not deps): the node can read the
    # module dep's sources and, recursively, the sources of the whole
    # transitive closure of its module deps (computed at run time from the
    # manifests). Star deps are automatically included in deps, so they are
    # still cleaned before run.
    update_with_ai(
        name = name,
        prompt = prompt,
        src = src,
        template = template,
        template_parameters = template_parameters,
        guide = guide,
        allows_step_mode = allows_step_mode,
        deps = deps,
        silent_deps = silent_deps,
        star_deps = module_deps + star_deps,
        feedback_deps = feedback_deps,
        silent_srcs = silent_srcs,
        verify = verify,
        visibility = visibility,
    )
    return ":" + name

def _merge_dicts(base, overrides):
    """Merge two dictionaries, with overrides taking precedence."""
    merged = dict(base)
    if overrides:
        for k, v in overrides.items():
            merged[k] = v
    return merged

def update_python_with_ai(name, module_deps, template_parameters = None, visibility = None):
    """Create a spec node for each root in spec_dep_roots.

    Args:
        name: Target name prefix (e.g. "dag_storage").
        module_deps: List of dependency spec/module labels (e.g. [":dag_clean_logic"]); each is a readable spec dependency and a pyright_dep of the module.
        template_parameters: Optional dictionary of template parameters for template evaluation.
        visibility: Optional visibility applied to all generated targets
            (node, *_clean, *_feedback, *_prompt); needed for cross-package
            deps.

    Returns:
        List of the created spec node labels (":" + name).
    """
    is_impl = name.endswith("_impl")
    is_asm = name.endswith("_asm")
    is_ext = name.endswith("_ext")
    is_interface = not (is_impl or is_asm or is_ext)
    component_type = "implementation" if is_impl else ("assembly" if is_asm else ("external" if is_ext else "interface"))
    dep_names = [dep.split(":")[-1] for dep in module_deps]

    base_params = {
        "name": name,
        "component_name": name,
        "component_type": component_type,
        "is_impl": is_impl,
        "is_asm": is_asm,
        "is_ext": is_ext,
        "is_interface": is_interface,
        "is_not_ext": not is_ext,
        "needs_implements": is_impl or is_asm,
        "target_module": name,
        "target_impl": name,
        "module_deps": dep_names,
    }

    high_params = _merge_dicts(base_params, {
        "target_file": "high/" + name + ".md",
        "spec_file": name + ".md",
    })
    if template_parameters:
        high_params = _merge_dicts(high_params, template_parameters)

    low_params = _merge_dicts(base_params, {
        "target_file": "grounding/" + name + ".pyi",
        "spec_file": name + ".pyi",
    })
    if template_parameters:
        low_params = _merge_dicts(low_params, template_parameters)

    lib_params = _merge_dicts(base_params, {
        "target_file": name + ".py",
        "spec_file": name + ".pyi",
    })
    if template_parameters:
        lib_params = _merge_dicts(lib_params, template_parameters)

    if is_impl:
        test_params = _merge_dicts(base_params, {
            "target_file": name + "_test.py",
            "target_impl": name,
            "spec_file": name + ".pyi",
        })
        if template_parameters:
            test_params = _merge_dicts(test_params, template_parameters)

        qa_params = _merge_dicts(base_params, {
            "target_file": name + "_qa.log",
            "target_impl": name,
            "spec_file": name + ".pyi",
        })
        if template_parameters:
            qa_params = _merge_dicts(qa_params, template_parameters)

        coverage_params = _merge_dicts(base_params, {
            "target_file": name + "_coverage.log",
            "target_impl": name,
            "spec_file": name + ".pyi",
        })
        if template_parameters:
            coverage_params = _merge_dicts(coverage_params, template_parameters)

    hls_spec_deps = [dep + "_high" for dep in module_deps]
    _update_python_with_ai(
        name = name + "_high",
        prompt = (
            "Align the high-level specification for component %s (%s.md) with its " +
            "dependencies per the guide."
        ) % (name, name),
        src = "high/" + name + ".md",
        template = "//update_python_with_ai/templates:hls",
        template_parameters = high_params,
        guide = "//update_python_with_ai/guides:high_level_spec",
        module_deps = hls_spec_deps,
        verify = "cd $BUILD_WORKSPACE_DIRECTORY && bazel test //{}:{}_high_lint --test_output=errors --noshow_progress 2>&1".format(
            native.package_name(),
            name,
        ),
        visibility = visibility,
    )

    _hls_lint_test(
        name = name + "_high_lint",
        srcs = ["high/" + name + ".md"],
        spec_deps = hls_spec_deps,
        dep_srcs = native.glob(["high/" + dep.split(":")[-1] + ".md" for dep in module_deps], allow_empty = True),
        tags = ["high_lint", "high"],
    )
    _lls_lint_test(
        name = name + "_low_lint",
        src = "grounding/" + name + ".pyi",
        dep_srcs = native.glob(["grounding/*.pyi"], exclude = ["grounding/" + name + ".pyi"], allow_empty = True),
        tags = ["low_lint", "low"],
        visibility = visibility,
    )
    lls_spec_deps = [dep + "_low" for dep in module_deps]
    _update_python_with_ai(
        name = name + "_low",
        prompt = (
            "Align the grounding specification for component %s (%s.pyi) with the " +
            "high-level specification (%s.md) per the guide."
        ) % (name, name, name),
        src = "grounding/" + name + ".pyi",
        template = "//update_python_with_ai/templates:empty",
        template_parameters = low_params,
        guide = "//update_python_with_ai/guides:high_to_grounding",
        module_deps = lls_spec_deps,
        deps = [":" + name + "_high"],
        verify = "cd $BUILD_WORKSPACE_DIRECTORY && bazel test //{}:{}_low_lint --test_output=errors --noshow_progress 2>&1".format(
            native.package_name(),
            name,
        ),
        visibility = visibility,
    )



    # The lib and tests directories are one level up from this package (the
    # parent of the instantiation package): the lib-python node writes
    # ../lib/<name>.py and the test node writes ../tests/<name>_test.py. The
    # package BUILD files (../lib/BUILD.bazel, ../tests/BUILD.bazel) are
    # silent sources: the agent may edit them to add the module's
    # pyright_library / pyright_test entry, whose type-check (and test)
    # targets gate the node's verify() tool.
    _parent_pkg = "/".join(native.package_name().split("/")[:-1])

    # The lib-python node: the module that implements the LLS per
    # low_to_lib.md. Its verify runs the module's type check once the agent
    # adds the pyright_library entry to ../lib/BUILD.bazel. The module kind
    # follows the spec: an interface spec's module defines the Protocol and
    # types only; an implementation spec's module subclasses the interface's
    # Protocol per the LLS; an assembly spec's module (name ending in _asm)
    # performs configuration and assembly of other modules only, is never
    # tested, and has no _test or _qa node; external boundary specs (name
    # ending in _ext) have no library implementation file and no _lib, _test,
    # or _qa node.
    _lib_deps = []
    if name.endswith("_impl") or name.endswith("_asm"):
        _lib_deps = ["//update_python_with_ai:lifecycle"]

    if not is_ext:
        if name.endswith("_impl"):
            _lib_kind_clause = (
                "This is an implementation module: it realizes concrete singleton " +
                "classes and functions defined in the grounding specification."
            )
        elif name.endswith("_asm"):
            _lib_kind_clause = (
                "This is an assembly module: it wires concrete implementations into " +
                "configured interface components and provides the assembled result."
            )
        else:
            _lib_kind_clause = (
                "This is an interface module: it defines the interface's protocol " +
                "and types."
            )

        _update_python_with_ai(
            name = name + "_lib",
            prompt = (
                "Align the lib module for component %s (%s.py) with its grounding " +
                "specification (%s.pyi) per the guide. " +
                _lib_kind_clause
            ).strip() % (name, name, name),
            src = "../lib/" + name + ".py",
            template = "//update_python_with_ai/templates:lib",
            template_parameters = lib_params,
            guide = "//update_python_with_ai/guides:grounding_to_lib",
            deps = _lib_deps,
            module_deps = [":" + name + "_low"],
            silent_deps = [dep + "_lib" for dep in module_deps if not dep.endswith("_ext")],
            verify = (
                "cd $BUILD_WORKSPACE_DIRECTORY && python3 update_with_ai/support/lib/lib_lint.py " +
                "{}/lib/BUILD.bazel {}/lib/{}.py --pyi {}/specs/grounding/{}.pyi {} {} && " +
                "bazel test //{}/lib:{}_type_check --test_output=errors --noshow_progress 2>&1"
            ).format(
                _parent_pkg,
                _parent_pkg,
                name,
                _parent_pkg,
                name,
                "--deps " + ",".join([dep.split(":")[-1] for dep in module_deps])
                if module_deps
                else "",
                "--pyi-deps " + ",".join(["{}/specs/grounding/{}.pyi".format(_parent_pkg, dep.split(":")[-1]) for dep in module_deps])
                if module_deps
                else "",
                _parent_pkg,
                name,
            ),
            visibility = visibility,
        )

    # The test node (implementations only, per grounding_to_test.md: one test
    # module per implementation grounding spec): written from the implementation grounding spec
    # alone. The implementation module is a silent dep — cleaned before this
    # node (so the tests type-check against it) but not readable to it (the
    # implementation Python file is never consulted). Verify gates on the
    # tests' BUILD entry and their type check only: the tests themselves are
    # not run here — the implementation's conformance is verified later, in a
    # separate agent run against the final implementation.
    if name.endswith("_impl"):
        _update_python_with_ai(
            name = name + "_test",
            prompt = (
                "Write the test module for component %s (%s_test.py) from the " +
                "grounding specification (%s.pyi) per the guide."
            ) % (name, name, name),
            src = "../tests/" + name + "_test.py",
            template = "//update_python_with_ai/templates:test",
            template_parameters = test_params,
            guide = "//update_python_with_ai/guides:grounding_to_test",
            deps = _lib_deps,
            module_deps = [":" + name + "_low"],
            silent_deps = [":" + name + "_lib"] + [dep + "_lib" for dep in module_deps if not dep.endswith("_ext")],
            verify = (
                "cd $BUILD_WORKSPACE_DIRECTORY && python3 update_with_ai/support/lib/test_lint.py " +
                "{}/tests/BUILD.bazel {}/tests/{}_test.py --lib-pkg {}/lib {} && " +
                "bazel test //{}/tests:{}_test_type_check --test_output=errors --noshow_progress 2>&1"
            ).format(
                _parent_pkg,
                _parent_pkg,
                name,
                _parent_pkg,
                "--deps " + ",".join([name] + [dep.split(":")[-1] for dep in module_deps])
                if module_deps
                else "",
                _parent_pkg,
                name,
            ),
            visibility = visibility,
        )

        # The QA arbiter node (implementations only, like the test node):
        # runs the implementation's tests (bazel test on the test node's
        # pyright_test target) via the verification callback and arbitrates
        # blame between the lib module and the test module against the LLS
        # when a test fails. The lib and test nodes are feedback deps: their
        # declared sources are readable (the QA reads the lib and test code)
        # and they are the QA's blame targets — the agent blames an artifact
        # by its file's virtual name (e.g. foo.py / foo_test.py), which the
        # sandbox resolves to the owning node. The low spec nodes are star
        # deps, so the whole LLS closure is readable as the contract. The log
        # (logs/<name>_qa.log, committed empty in the specs package) is the
        # run's persistent record of problems across the feedback loop; the
        # verification runs the tests and then, when the tests pass, fails
        # with feedback directing the agent to empty the log when it is not
        # empty, so a run whose tests pass succeeds only with an empty log.
        _qa_log_path = "{}/logs/{}_qa.log".format(native.package_name(), name)
        _update_python_with_ai(
            name = name + "_qa",
            prompt = "Evaluate test execution and arbitrate failures per the guide.",
            src = "logs/" + name + "_qa.log",
            template = "//update_python_with_ai/templates:empty",
            template_parameters = qa_params,
            guide = "//update_python_with_ai/guides:qa",
            allows_step_mode = False,
            deps = _lib_deps,
            star_deps = [":" + name + "_low"],
            feedback_deps = [":" + name + "_lib", ":" + name + "_test"],
            verify = (
                "cd $BUILD_WORKSPACE_DIRECTORY && bazel test //{}/tests:{}_test --test_output=errors --noshow_progress 2>&1 && " +
                "if [ -s {} ]; then echo 'QA log is not empty: delete all lines (0 bytes, remove any headers).'; exit 1; fi"
            ).format(_parent_pkg, name, _qa_log_path),
            visibility = visibility,
        )

        # The coverage arbiter node (implementations only):
        # evaluates statement coverage of the implementation module exercised by
        # its unit test suite, updates logs/<name>_coverage.log with coverage metrics,
        # and guides the agent to translate missing coverage into missing grounding
        # requirements to deliver blame feedback to the test agent (or add # pragma: no cover
        # for impossible cases/caller assumptions).
        _coverage_log_path = "{}/logs/{}_coverage.log".format(native.package_name(), name)
        _update_python_with_ai(
            name = name + "_coverage",
            prompt = "Evaluate test execution and evaluate test coverage per the guide.",
            src = "logs/" + name + "_coverage.log",
            template = "//update_python_with_ai/templates:empty",
            template_parameters = coverage_params,
            guide = "//update_python_with_ai/guides:coverage",
            allows_step_mode = False,
            deps = _lib_deps,
            silent_deps = [":" + name + "_qa"],
            star_deps = [":" + name + "_low"],
            feedback_deps = [":" + name + "_lib", ":" + name + "_test"],
            verify = (
                "cd $BUILD_WORKSPACE_DIRECTORY && " +
                "bazel test //{}/tests:{}_test --test_output=errors --noshow_progress 2>&1 && " +
                "python3 update_with_ai/support/lib/evaluate_coverage.py --impl {}/lib/{}.py --test {}/tests/{}_test.py --threshold 100.0 && " +
                "if [ -s {} ]; then echo 'Coverage log is not empty: delete all lines (0 bytes, remove any headers).'; exit 1; fi"
            ).format(_parent_pkg, name, _parent_pkg, name, _parent_pkg, name, _coverage_log_path),
            visibility = visibility,
        )
    elif name.endswith("_asm"):
        # The QA aggregation node for assemblies: has no prompt and no src file.
        # It depends on the _qa targets of all composed implementations and
        # sub-assemblies so that cleaning this node verifies the whole composite subsystem.
        _qa_deps = [dep + "_qa" for dep in module_deps if dep.endswith("_impl") or dep.endswith("_asm")]
        _update_python_with_ai(
            name = name + "_qa",
            prompt = "",
            src = "",
            deps = _qa_deps,
            visibility = visibility,
        )

        # The coverage aggregation node for assemblies: has no prompt and no src file.
        # It depends on the _coverage targets of all composed implementations and
        # sub-assemblies so that cleaning this node verifies coverage across the composite subsystem.
        _coverage_deps = [dep + "_coverage" for dep in module_deps if dep.endswith("_impl") or dep.endswith("_asm")]
        _update_python_with_ai(
            name = name + "_coverage",
            prompt = "",
            src = "",
            deps = _coverage_deps,
            visibility = visibility,
        )
    return ":" + name


