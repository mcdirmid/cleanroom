"""build_derived_test.bzl — Macro to verify that targets in lib/BUILD.bazel or tests/BUILD.bazel
are strictly derived from the parent part/*/BUILD.bazel file.
"""

load("@rules_python//python:defs.bzl", "py_test")

def build_derived_test(name = "targets_derived_test", kind = None, tags = ["lint"], **kwargs):
    """Create a test verifying that targets in the current BUILD.bazel are derived from parent BUILD.bazel."""
    pkg = native.package_name()
    if not kind:
        if pkg.endswith("/lib"):
            kind = "lib"
        elif pkg.endswith("/tests"):
            kind = "test"
        elif pkg.endswith("/grounding"):
            kind = "grounding"
        else:
            fail("kind must be specified as 'lib', 'test', or 'grounding'")

    parent_pkg = pkg.rsplit("/", 1)[0]
    build_file_rel = pkg + "/BUILD.bazel"
    parent_build_file_rel = parent_pkg + "/BUILD.bazel"

    src_py_glob = native.glob(["*.py"], allow_empty = True)

    data = [
        "//update_python_with_ai/support/lib:check_build_derived.py",
        "//update_python_with_ai/support/lib:build_lint_common.py",
        ":BUILD.bazel",
        "//" + parent_pkg + ":BUILD.bazel",
        "//" + parent_pkg + ":grounding_specs",
    ] + src_py_glob


    kwargs_test = dict(kwargs)
    kwargs_test.setdefault("size", "small")

    py_test(
        name = name,
        srcs = ["//update_python_with_ai/support/lib:check_build_derived.py"],
        main = "check_build_derived.py",
        args = [
            "--kind=" + kind,
            "--build-file=" + build_file_rel,
            "--parent-build-file=" + parent_build_file_rel,
        ],
        data = data,
        tags = tags,
        **kwargs_test
    )
