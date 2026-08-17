# pyright_library.bzl
load("@rules_python//python:defs.bzl", "py_library", "py_test", "py_binary")
load("@rules_shell//shell:sh_test.bzl", "sh_test")

def _pyright_test_impl(ctx):
    """Implementation for pyright_test rule."""
    
    # Collect all Python files from srcs
    py_files = []
    for src in ctx.files.srcs:
        py_files.append(src)
    
    # Collect from dependencies
    for dep in ctx.attr.deps + ctx.attr.pyright_deps:
        if hasattr(dep, "files"):
            for f in dep.files.to_list():
                if f.path.endswith(".py"):
                    py_files.append(f)
    
    # Create a file list for pyright
    file_list = ctx.actions.declare_file(ctx.label.name + "_files.txt")
    
    # Write unique paths to file list
    unique_paths = sorted(set([f.path for f in py_files]))
    file_list_content = "\n".join(unique_paths)
    ctx.actions.write(file_list, file_list_content)
    
    # Create a wrapper script
    wrapper = ctx.actions.declare_file(ctx.label.name + "_wrapper.sh")
    
    # Set up PYTHONPATH with all dependency paths
    dep_paths = []
    for dep in ctx.attr.deps + ctx.attr.pyright_deps:
        if hasattr(dep, "files"):
            for f in dep.files.to_list():
                if f.path.endswith(".py"):
                    dep_paths.append(f.dirname)
    
    unique_dep_paths = sorted(set(dep_paths))
    
    wrapper_content = """#!/bin/bash
set -e

# Set PYTHONPATH to include all dependencies
if [ -n "$PYTHONPATH" ]; then
    export PYTHONPATH="{dep_paths}:$PYTHONPATH"
else
    export PYTHONPATH="{dep_paths}"
fi

# Read files from the file list and run pyright on them
# Use xargs to handle large numbers of files
cat {file_list} | xargs python3 -m pyright
""".format(
        dep_paths=":".join(unique_dep_paths),
        file_list=file_list.path
    )
    ctx.actions.write(wrapper, wrapper_content, is_executable=True)
    
    return [
        DefaultInfo(
            executable = wrapper,
            files = depset([wrapper, file_list] + py_files),
        ),
    ]

def _get_type_check_target(dep):
    """Get the type_check target for a dependency."""
    dep_str = str(dep)
    
    if dep_str.startswith("@"):
        return None
    
    if dep_str.startswith("//"):
        if ":" in dep_str:
            return dep_str + "_type_check"
        else:
            package = dep_str[2:]
            target_name = package.split("/")[-1]
            return "//{}:{}_type_check".format(package, target_name)
    
    if dep_str.startswith(":"):
        return dep_str + "_type_check"
    
    return ":" + dep_str + "_type_check"

def _get_type_check_all_target(dep):
    """Get the type_check_all target for a dependency."""
    dep_str = str(dep)
    
    if dep_str.startswith("@"):
        return None
    
    if dep_str.startswith("//"):
        if ":" in dep_str:
            return dep_str + "_type_check_all"
        else:
            package = dep_str[2:]
            target_name = package.split("/")[-1]
            return "//{}:{}_type_check_all".format(package, target_name)
    
    if dep_str.startswith(":"):
        return dep_str + "_type_check_all"
    
    return ":" + dep_str + "_type_check_all"

def _deduplicate_list(lst):
    """Remove duplicates from a list while preserving order."""
    result = []
    seen = {}
    for item in lst:
        if item not in seen:
            seen[item] = True
            result.append(item)
    return result

def pyright_library(name, srcs, deps = [], pyright_deps = [], **kwargs):
    """Create a Python library with type checking."""
    
    # Create the actual py_library
    py_library(
        name = name,
        srcs = srcs,
        deps = deps + pyright_deps,
        **kwargs
    )
    
    # Create type check test
    _pyright_test(
        name = name + "_type_check",
        srcs = srcs,
        deps = deps,
        pyright_deps = pyright_deps,
        tags = ["type_check"],
    )
    
    # Create the test suite
    transitive_checks = [":" + name + "_type_check"]
    
    for dep in pyright_deps:
        target = _get_type_check_all_target(dep)
        if target:
            transitive_checks.append(target)
    
    for dep in pyright_deps:
        target = _get_type_check_target(dep)
        if target:
            transitive_checks.append(target)
    
    transitive_checks = [t for t in transitive_checks if t]
    transitive_checks = _deduplicate_list(transitive_checks)
    
    if transitive_checks:
        native.test_suite(
            name = name + "_type_check_all",
            tests = transitive_checks,
            tags = ["type_check"],
        )

def pyright_test(name, srcs, deps = [], pyright_deps = [], **kwargs):
    """Create a Python test with type checking."""
    
    # Create the actual py_test
    py_test(
        name = name,
        srcs = srcs,
        deps = deps + pyright_deps,
        **kwargs
    )
    
    # Create type check test
    _pyright_test(
        name = name + "_type_check",
        srcs = srcs,
        deps = deps,
        pyright_deps = pyright_deps,
        tags = ["type_check"],
    )
    
    # Create the test suite
    transitive_checks = [":" + name + "_type_check"]
    
    for dep in pyright_deps:
        target = _get_type_check_all_target(dep)
        if target:
            transitive_checks.append(target)
    
    for dep in pyright_deps:
        target = _get_type_check_target(dep)
        if target:
            transitive_checks.append(target)
    
    transitive_checks = [t for t in transitive_checks if t]
    transitive_checks = _deduplicate_list(transitive_checks)
    
    if transitive_checks:
        native.test_suite(
            name = name + "_type_check_all",
            tests = transitive_checks,
            tags = ["type_check"],
        )

def pyright_binary(name, srcs, main, deps = [], pyright_deps = [], **kwargs):
    """Create a Python binary with type checking."""
    
    # Create the actual py_binary
    py_binary(
        name = name,
        srcs = srcs,
        main = main,
        deps = deps + pyright_deps,
        **kwargs
    )
    
    # Create type check test
    _pyright_test(
        name = name + "_type_check",
        srcs = srcs,
        deps = deps,
        pyright_deps = pyright_deps,
        tags = ["type_check"],
    )
    
    # Create the test suite
    transitive_checks = [":" + name + "_type_check"]
    
    for dep in pyright_deps:
        target = _get_type_check_all_target(dep)
        if target:
            transitive_checks.append(target)
    
    for dep in pyright_deps:
        target = _get_type_check_target(dep)
        if target:
            transitive_checks.append(target)
    
    transitive_checks = [t for t in transitive_checks if t]
    transitive_checks = _deduplicate_list(transitive_checks)
    
    if transitive_checks:
        native.test_suite(
            name = name + "_type_check_all",
            tests = transitive_checks,
            tags = ["type_check"],
        )

# Define the rule
_pyright_test = rule(
    implementation = _pyright_test_impl,
    attrs = {
        "srcs": attr.label_list(allow_files = [".py"]),
        "deps": attr.label_list(providers = [DefaultInfo]),
        "pyright_deps": attr.label_list(providers = [DefaultInfo]),
    },
    test = True,
)