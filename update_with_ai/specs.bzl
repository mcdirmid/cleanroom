"""Specification-node entry points.

update_hls_with_ai creates a high-level specification (HLS) node and
update_lls_with_ai creates a low-level specification (LLS) node. Both are
thin wrappers over update_with_ai (macros.bzl): they differ only in the
spec-specific data they pass — the prompt, the guide dep, the spec deps,
and (for HLS) a *_lint test target that gates the node's verify tool. All
node machinery (manifest, *_clean, *_feedback, *_prompt targets) comes from
update_with_ai.

Each macro returns its own label (":" + name) so a BUILD file can bind the
result to a variable and pass it to a dependent node's spec deps. Spec deps
are plain labels (same or other packages); the graph is resolved at run
time from the loaded manifests.
"""

load("//update_with_ai:macros.bzl", "collect_node_manifests", "update_with_ai")

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
# Specification lint rule: hls_lint
# ============================================================================
#
# The hls_lint rule creates a bazel test target that lints the spec file and
# verifies that every spec referenced in the text is covered by spec_deps
# (the "dependencies are synced" check). Covered spec paths are read at test
# time from each spec_dep's manifest in runfiles (data-driven).

def _hls_lint_impl(ctx):
    """Implementation of the hls_lint rule: a test that lints a spec file."""

    # The spec files to lint.
    src_files = ctx.files.srcs
    src_args = " ".join(['"$ws"/{}'.format(f.short_path) for f in src_files])

    # Each spec_dep's manifest (in runfiles) lists the spec files it owns;
    # the test script reads them at runtime and passes the package-qualified
    # paths to hls_lint.py as --deps. The closure is computed from the
    # manifests: the spec deps' own sources plus, recursively, the sources
    # of every node in their deps/star_deps closure (never silent_deps), so
    # lint coverage matches exactly what the agent can read at run time.
    dep_manifest_paths = [f.short_path for f in ctx.files.spec_deps]

    script = ctx.actions.declare_file(ctx.label.name + ".sh")

    # Emit --deps only when there are deps: an empty --deps would consume
    # the target file as a dep and leave nothing to lint.
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
            "    for s in m.get('srcs', []):\n" +
            "        out.append(os.path.dirname(p) + '/' + s)\n" +
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
            '    python3 "$ws/bin/hls_lint.py" --deps $deps -- {targets}\n' +
            "else\n" +
            '    python3 "$ws/bin/hls_lint.py" {targets}\n' +
            "fi\n"
        ).format(paths = paths_literal, targets = src_args)
    else:
        deps_cmd = 'python3 "$ws/bin/hls_lint.py" {targets}\n'.format(targets = src_args)
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
        files = [ctx.file._hls_lint] + ctx.files._high_specs + src_files + ctx.files.spec_deps,
        transitive_files = transitive_manifests,
    )
    return [
        DefaultInfo(executable = script, runfiles = runfiles),
    ]

_hls_lint_test = rule(
    implementation = _hls_lint_impl,
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
        "_hls_lint": attr.label(
            default = Label("//bin:hls_lint.py"),
            allow_single_file = True,
        ),
        "_high_specs": attr.label(
            default = Label("//update_with_ai/specs:high_specs"),
            doc = "Canonical spec corpus used for term-ownership reference resolution",
        ),
    },
)

# ============================================================================
# Macro: update_hls_with_ai (high-level specification nodes)
# ============================================================================

def _update_spec_with_ai(name, prompt, srcs, deps, spec_deps, verify = "", visibility = None):
    """Create a spec node by delegating to update_with_ai.

    The single common spec-node entry: forwards the spec-specific arguments
    to update_with_ai (which generates the node, *_clean, *_feedback, and
    *_prompt targets) and returns the node's own label. The spec deps are
    kept separate from the declared deps and passed as star_deps: they are
    cleaned before run and their sources (and, recursively, the sources of
    their whole deps/star_deps closure) are readable by the node.

    Args:
        name: Target name.
        prompt: The agent prompt for the spec node.
        srcs: Spec file paths the agent writes.
        deps: Declared readable dependency node labels (e.g. the guide).
        spec_deps: spec targets the current spec depends on (must be _update_spec_with_ai targets).
        verify: Shell command to run when the agent calls verify()
            (default: empty = no verify tool).
        visibility: Optional visibility applied to all generated targets;
            needed for cross-package deps.

    Returns:
        The node's own label (":" + name).
    """

    # Spec deps are passed as star_deps (not deps): the node can read the
    # spec dep's sources and, recursively, the sources of the whole
    # transitive closure of its spec deps (computed at run time from the
    # manifests). Star deps are automatically included in deps, so they are
    # still cleaned before run.
    update_with_ai(
        name = name,
        prompt = prompt,
        srcs = srcs,
        deps = deps,
        star_deps = spec_deps,
        verify = verify,
        visibility = visibility,
    )
    return ":" + name

def update_spec_with_ai(name, spec_deps, visibility = None):
    """Create a spec node for each root in spec_dep_roots.

    Args:
        name: Target name prefix (e.g. "dag_storage").
        spec_deps: List of spec dep target labels (e.g. [":dag_clean_logic"]).
        visibility: Optional visibility applied to all generated targets
            (node, *_clean, *_feedback, *_prompt); needed for cross-package
            deps.

    Returns:
        List of the created spec node labels (":" + name).
    """
    hls_spec_deps = [dep + "_high" for dep in spec_deps]
    _update_spec_with_ai(
        name = name + "_high",
        prompt = "Updates the high-level specification for %s (in file %s-high.md), the HLS must conform to high-level-spec.md" % (name, name),
        srcs = [name + "-high.md"],
        deps = ["//guides:high_level_spec"],
        spec_deps = hls_spec_deps,
        verify = "cd $BUILD_WORKSPACE_DIRECTORY && bazel test //{}:{}_high_lint --test_output=errors 2>&1".format(
            native.package_name(),
            name,
        ),
        visibility = visibility,
    )

    _hls_lint_test(
        name = name + "_high_lint",
        srcs = [name + "-high.md"],
        spec_deps = hls_spec_deps,
    )
    lls_spec_deps = [dep + "_low" for dep in spec_deps]
    _update_spec_with_ai(
        name = name + "_low",
        prompt = (
            "Convert the high-level specification (HLS) for %s (in %s-high.md) into the " +
            "low-level specification (LLS) for %s (in %s-low.md); if the LLS already exists, " +
            "update it rather than create it. The LLS must be aligned with the HLS according to " +
            "high_to_low.md. Make targeted edits only for substantive issues; do not chase " +
            "formatting nits; re-read the file (read_file with include_line_numbers=True) " +
            "before each replace_lines edit."
        ) % (name, name, name, name),
        srcs = [name + "-low.md"],
        deps = ["//guides:high_to_low"],
        spec_deps = lls_spec_deps + [":" + name + "_high"],
        visibility = visibility,
    )
    return ":" + name
