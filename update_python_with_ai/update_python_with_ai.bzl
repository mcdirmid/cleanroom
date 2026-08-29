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

load("//update_with_ai/lib:update_with_ai.bzl", "collect_node_manifests", "update_with_ai")

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
# low-level specs per update_python_with_ai/guides/low_level_spec.md.

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
            ctx.files.spec_deps + ctx.files.dep_srcs + ctx.files._external_corpus
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
            default = Label("//update_python_with_ai/bin:hls_lint.py"),
            allow_single_file = True,
        ),
        "_direct_deps": attr.bool(
            default = False,
            doc = "True when --deps comes from dep_srcs directly (lls_lint); False when it comes from the spec_deps manifest closure walk (hls_lint)",
        ),
        "_corpus": attr.label(
            default = Label("//update_with_ai/specs:high_specs"),
            doc = "Canonical spec corpus used for term-ownership reference resolution",
        ),
        "_external_corpus": attr.label(
            default = Label("//update_with_ai/specs:external_specs"),
            doc = "External dependency docs (specs/external/*.md); in runfiles (unused by hls_lint)",
        ),
    },
)

_lls_lint_test = rule(
    implementation = _spec_lint_test_impl,
    test = True,
    attrs = {
        "srcs": attr.label_list(
            allow_files = True,
            doc = "Spec file(s) to lint",
        ),
        "spec_deps": attr.label_list(
            doc = "Spec dependency node targets whose coverage is verified against the dependency comment's entries",
            aspects = [collect_node_manifests],
        ),
        "dep_srcs": attr.label_list(
            allow_files = True,
            doc = "Dep spec files whose Data Types names the closure checks import against",
        ),
        "_linter": attr.label(
            default = Label("//update_python_with_ai/bin:lls_lint.py"),
            allow_single_file = True,
        ),
        "_direct_deps": attr.bool(
            default = True,
            doc = "True when --deps comes from dep_srcs directly (lls_lint); False when it comes from the spec_deps manifest closure walk (hls_lint)",
        ),
        "_external_corpus": attr.label(
            default = Label("//update_with_ai/specs:external_specs"),
            doc = "External dependency docs (specs/external/*.md); in runfiles so the linter's external-doc resolution finds them in the sandbox",
        ),
        "_corpus": attr.label(
            default = Label("//update_with_ai/specs:low_specs"),
            doc = "Canonical low-level spec corpus (runfiles only)",
        ),
    },
)
# ============================================================================
# Macro: update_python_with_ai (specification nodes)
# ============================================================================

def _update_python_with_ai(name, prompt, src, deps = [], module_deps = [], star_deps = [], feedback_deps = [], silent_deps = [], silent_srcs = [], template = None, guide = None, verify = "", visibility = None):
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
        guide = guide,
        deps = deps,
        silent_deps = silent_deps,
        star_deps = module_deps + star_deps,
        feedback_deps = feedback_deps,
        silent_srcs = silent_srcs,
        verify = verify,
        visibility = visibility,
    )
    return ":" + name

def update_python_with_ai(name, module_deps, external_deps = [], visibility = None):
    """Create a spec node for each root in spec_dep_roots.

    Args:
        name: Target name prefix (e.g. "dag_storage").
        module_deps: List of dependency spec/module labels (e.g. [":dag_clean_logic"]); each is a readable spec dependency and a pyright_dep of the module.
        external_deps: List of external-dependency doc node labels (update_with_ai
            targets, e.g. [":openai_api"]); added to the _low node's deps and the
            _low_lint's --deps directly (no transitive closure; the doc files are
            readable but their own deps are not pulled in).
        visibility: Optional visibility applied to all generated targets
            (node, *_clean, *_feedback, *_prompt); needed for cross-package
            deps.

    Returns:
        List of the created spec node labels (":" + name).
    """
    hls_spec_deps = [dep + "_high" for dep in module_deps]
    _update_python_with_ai(
        name = name + "_high",
        prompt = (
            "Ensure the high-level specification for %s (in high/%s.md) conforms to " +
            "high_level_spec.md with minimal changes: make only the targeted edits " +
            "needed to fix deviations, and leave conformant content untouched. If the " +
            "file is a template, fill it in. A write is followed by an automatic " +
            "re-read with line numbers, so a line-range edit (replace_lines) may " +
            "follow a write without a further read."
        ) % (name, name),
        src = "high/" + name + ".md",
        template = "//update_python_with_ai/templates:hls",
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
    )
    lls_spec_deps = [dep + "_low" for dep in module_deps]
    _update_python_with_ai(
        name = name + "_low",
        prompt = (
            "Ensure the low-level specification (LLS) for %s (in low/%s.md) is aligned " +
            "with the high-level specification (HLS) for %s (in high/%s.md) according to " +
            "high_to_low.md, with minimal changes: make only the targeted edits needed to " +
            "fix misalignments, and leave conformant content untouched. If the file is a " +
            "template, fill it in. A write is followed by an automatic re-read with line " +
            "numbers, so a line-range edit (replace_lines) may follow a write without a " +
            "further read."
        ) % (name, name, name, name),
        src = "low/" + name + ".md",
        template = "//update_python_with_ai/templates:lls",
        guide = "//update_python_with_ai/guides:high_to_low",
        module_deps = lls_spec_deps,
        deps = [":" + name + "_high"] + external_deps,
        verify = "cd $BUILD_WORKSPACE_DIRECTORY && bazel test //{}:{}_low_lint --test_output=errors --noshow_progress 2>&1".format(
            native.package_name(),
            name,
        ),
        visibility = visibility,
    )

    # The LLS is validated by a lls_lint test that mirrors the HLS's hls_lint
    # test. The target is created only once the spec file exists on disk (low
    # specs are generated as the graph is walked; a lint target with a missing
    # src would fail to build). The template initializes the file at run start,
    # so the target materializes on the next bazel invocation after the agent
    # writes the spec, which is when the node's verify tool gates on it. The
    # lint's --deps are the module_deps md files directly (no transitive
    # closure: the comment lists the direct deps, and the closure lives in the
    # node's star_deps) plus the external-doc files.
    if native.glob(["low/" + name + ".md"], allow_empty = True):
        _lls_lint_test(
            name = name + "_low_lint",
            srcs = ["low/" + name + ".md"],
            dep_srcs = native.glob(["low/" + dep.split(":")[-1] + ".md" for dep in module_deps], allow_empty = True),
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
    # tested, and has no _test or _qa node (the test/qa nodes below are
    # created only for _impl names).
    if name.endswith("_impl"):
        _lib_kind_clause = (
            "This is an implementation module: it subclasses the interface's " +
            "Protocol class per the LLS."
        )
    elif name.endswith("_asm"):
        _lib_kind_clause = (
            "This is an assembly module: it performs no functionality beyond " +
            "configuration and assembly of other modules — it wires the " +
            "concrete implementations into the configured interface-only " +
            "components and provides the assembled result. It implements no " +
            "interface and is never tested (no test module exists for it)."
        )
    else:
        _lib_kind_clause = (
            "This is an interface module: it defines the interface's Protocol " +
            "and types only, never an implementation class (implementations " +
            "live in the `_impl` module, which implements an implementation " +
            "LLS; this spec has none). If the template has an " +
            "implementation-class half, delete it."
        )
    _update_python_with_ai(
        name = name + "_lib",
        prompt = (
            "Ensure the lib module for %s (the file %s.py) implements " +
            "its LLS per low_to_lib.md, with minimal changes: make only the " +
            "targeted edits needed to fix deviations, and leave conformant content " +
            "untouched. If the file is a template, fill it in. " +
            "Call advance() regularly to re-run the type check: after fixing type " +
            "errors, call advance() to confirm they are really gone, and after each " +
            "edit or small series of edits, call advance() to confirm no new type " +
            "errors were introduced. " +
            _lib_kind_clause + " " +
            "A write is " +
            "followed by an automatic re-read with line numbers, so a line-range edit " +
            "(replace_lines) may follow a write without a further read."
        ) % (name, name),
        src = "../lib/" + name + ".py",
        template = "//update_python_with_ai/templates:lib",
        guide = "//update_python_with_ai/guides:low_to_lib",
        module_deps = [":" + name + "_low"],
        silent_deps = [dep + "_lib" for dep in module_deps],
        verify = (
            "cd $BUILD_WORKSPACE_DIRECTORY && python3 update_python_with_ai/bin/lib_lint.py " +
            "{}/lib/BUILD.bazel {}/lib/{}.py {} && " +
            "bazel test //{}/lib:{}_type_check --test_output=errors --noshow_progress 2>&1"
        ).format(
            _parent_pkg,
            _parent_pkg,
            name,
            "--deps " + ",".join([dep.split(":")[-1] for dep in module_deps])
            if module_deps
            else "",
            _parent_pkg,
            name,
        ),
        visibility = visibility,
    )

    # The test node (implementations only, per low_to_test.md: one test
    # module per implementation LLS): written from the implementation LLS
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
                "Ensure the test module for %s (the file %s_test.py) is written from " +
                "the implementation LLS per low_to_test.md, " +
                "with minimal changes: make only the targeted edits needed to fix " +
                "deviations, and leave conformant content untouched. The implementation " +
                "Python file is never consulted. If the file is a template, fill it in. " +
                "Write incrementally: append one test class per edit, never the whole " +
                "file in one edit (an edit that exceeds the response limit is lost). " +
                "Call advance() regularly to re-run the type check: after fixing type " +
                "errors, call advance() to confirm they are really gone, and after each " +
                "edit or small series of edits, call advance() to confirm no new type " +
                "errors were introduced. " +
                "A write is followed by an automatic re-read with line numbers, so a " +
                "line-range edit (replace_lines) may follow a write without a further " +
                "read."
            ) % (name, name),
            src = "../tests/" + name + "_test.py",
            template = "//update_python_with_ai/templates:test",
            guide = "//update_python_with_ai/guides:low_to_test",
            module_deps = [":" + name + "_low"],
            silent_deps = [":" + name + "_lib"] + [dep + "_lib" for dep in module_deps],
            verify = (
                "cd $BUILD_WORKSPACE_DIRECTORY && python3 update_python_with_ai/bin/test_lint.py " +
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
            prompt = (
                "Call advance() to start. Do not try to execute the tests " +
                "yourself: advance runs the tests and gives you feedback " +
                "about any test failures."
            ),
            src = "logs/" + name + "_qa.log",
            template = "//update_python_with_ai/templates:empty",
            guide = "//update_python_with_ai/guides:qa",
            star_deps = [":" + name + "_low"],
            feedback_deps = [":" + name + "_lib", ":" + name + "_test"],
            verify = (
                "cd $BUILD_WORKSPACE_DIRECTORY && bazel test //{}/tests:{}_test --test_output=errors --noshow_progress 2>&1 && " +
                "if [ -s {} ]; then echo 'QA log is not empty: delete all lines (0 bytes, remove any headers) and call advance again.'; exit 1; fi"
            ).format(_parent_pkg, name, _qa_log_path),
            visibility = visibility,
        )
    return ":" + name
