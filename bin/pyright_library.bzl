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
    
    # Create a wrapper script
    wrapper = ctx.actions.declare_file(ctx.label.name + "_wrapper.sh")
    
    # Set up PYTHONPATH with all dependency paths (always include workspace root '.')
    dep_paths = ["."]
    
    # Process target imports relative to package
    for imp in getattr(ctx.attr, "imports", []):
        if imp == ".":
            dep_paths.append(ctx.label.package if ctx.label.package else ".")
        else:
            pkg_parts = ctx.label.package.split("/") if ctx.label.package else []
            imp_parts = imp.split("/")
            for part in imp_parts:
                if part == "..":
                    if pkg_parts:
                        pkg_parts.pop()
                elif part != ".":
                    pkg_parts.append(part)
            resolved = "/".join(pkg_parts) if pkg_parts else "."
            dep_paths.append(resolved)

    for dep in ctx.attr.deps + ctx.attr.pyright_deps:
        dep_label = str(dep.label)
        if dep_label.endswith(":framework") or dep_label == "//update_with_ai/support/lib:framework":
            fail("Target {} is not allowed to depend on framework ({})".format(ctx.label, dep_label))

        if hasattr(dep, "files"):
            for f in dep.files.to_list():
                if f.path.endswith(".py"):
                    if "site-packages" in f.short_path:
                        idx = f.short_path.find("site-packages")
                        dep_paths.append(f.short_path[:idx + len("site-packages")])
                    else:
                        parts = f.short_path.split("/")
                        if parts:
                            dep_paths.append(parts[0])
                        if "support/lib" in f.short_path:
                            dep_paths.append("update_with_ai")
                        else:
                            dep_paths.append(f.short_path.rsplit("/", 1)[0] if "/" in f.short_path else ".")
                            if len(parts) > 2:
                                dep_paths.append("/".join(parts[:-2]))
    
    for f in ctx.files.srcs:
        parts = f.short_path.split("/")
        if parts:
            dep_paths.append(parts[0])
        dep_paths.append(f.short_path.rsplit("/", 1)[0] if "/" in f.short_path else ".")
        if len(parts) > 2:
            dep_paths.append("/".join(parts[:-2]))
    
    unique_dep_paths = sorted(set(dep_paths))

    # Generate target-specific hermetic pyright configuration
    config_file = ctx.actions.declare_file(ctx.label.name + "_pyrightconfig.json")
    
    pkg_parts = ctx.label.package.split("/") if ctx.label.package else []
    root_rel = "/".join([".." for _ in pkg_parts]) if pkg_parts else "."
    
    include_paths = []
    for f in ctx.files.srcs:
        if root_rel == ".":
            include_paths.append(f.short_path)
        else:
            include_paths.append(root_rel + "/" + f.short_path)
    unique_include_paths = _deduplicate_list(sorted(include_paths))
    
    extra_paths = []
    for p in unique_dep_paths:
        if root_rel == ".":
            extra_paths.append(p)
        else:
            extra_paths.append(root_rel if p == "." else root_rel + "/" + p)
    unique_extra_paths = _deduplicate_list(sorted(extra_paths))
    
    config_dict = {
        "include": unique_include_paths,
        "exclude": [],
        "extraPaths": unique_extra_paths,
        "pythonVersion": "3.12",
        "reportMissingImports": "none",
        "reportUnknownMemberType": False,
        "reportUnknownVariableType": False,
        "reportUnknownArgumentType": False,
    }
    ctx.actions.write(config_file, json.encode(config_dict))
    
    wrapper_content = """#!/bin/bash
set -e -o pipefail

# Set PYTHONPATH to include all dependencies
if [ -n "$PYTHONPATH" ]; then
    export PYTHONPATH="{dep_paths}:$PYTHONPATH"
else
    export PYTHONPATH="{dep_paths}"
fi

python3 -m pyright --project {config_path}
""".format(
        dep_paths=":".join(unique_dep_paths),
        config_path=config_file.short_path,
    )
    ctx.actions.write(wrapper, wrapper_content, is_executable=True)
    
    runfiles = ctx.runfiles(files = [wrapper, config_file] + py_files)
    for dep in ctx.attr.deps + ctx.attr.pyright_deps:
        if DefaultInfo in dep:
            runfiles = runfiles.merge(dep[DefaultInfo].default_runfiles)
    
    return [
        DefaultInfo(
            executable = wrapper,
            files = depset([wrapper, config_file] + py_files),
            runfiles = runfiles,
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

def _ensure_type_check_suite():
    """Ensure a package-level type_check test_suite exists."""
    if not native.existing_rule("type_check"):
        native.test_suite(
            name = "type_check",
            tags = ["type_check"],
        )

def type_check(name = "type_check", tags = ["type_check"], **kwargs):
    """Test suite that includes all direct _type_check tests in the package."""
    if not native.existing_rule(name):
        native.test_suite(
            name = name,
            tags = tags,
            **kwargs
        )

def pyright_library(name, srcs, deps = [], pyright_deps = [], imports = [".."], **kwargs):
    """Create a Python library with type checking."""
    _ensure_type_check_suite()
    
    # Create the actual py_library
    py_library(
        name = name,
        srcs = srcs,
        deps = deps + pyright_deps,
        imports = imports,
        **kwargs
    )
    
    # Create type check test
    _pyright_test(
        name = name + "_type_check",
        srcs = srcs,
        deps = deps,
        pyright_deps = pyright_deps,
        imports = imports,
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
            tags = ["type_check_transition", "type_check_transitions"],
        )

def pyright_test(name, srcs, deps = [], pyright_deps = [], imports = [".."], **kwargs):
    """Create a Python test with type checking."""
    _ensure_type_check_suite()
    
    # Create the actual py_test
    py_test(
        name = name,
        srcs = srcs,
        deps = deps + pyright_deps,
        imports = imports,
        **kwargs
    )
    
    # Create type check test
    _pyright_test(
        name = name + "_type_check",
        srcs = srcs,
        deps = deps,
        pyright_deps = pyright_deps,
        imports = imports,
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
            tags = ["type_check_transition", "type_check_transitions"],
        )

def pyright_binary(name, srcs, main, deps = [], pyright_deps = [], imports = [".."], **kwargs):
    """Create a Python binary with type checking."""
    _ensure_type_check_suite()
    
    # Create the actual py_binary
    py_binary(
        name = name,
        srcs = srcs,
        main = main,
        deps = deps + pyright_deps,
        imports = imports,
        **kwargs
    )
    
    # Create type check test
    _pyright_test(
        name = name + "_type_check",
        srcs = srcs,
        deps = deps,
        pyright_deps = pyright_deps,
        imports = imports,
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
            tags = ["type_check_transition", "type_check_transitions"],
        )

# Define the rule
_pyright_test = rule(
     implementation = _pyright_test_impl,
     attrs = {
         "srcs": attr.label_list(allow_files = [".py"]),
         "deps": attr.label_list(providers = [DefaultInfo]),
         "pyright_deps": attr.label_list(providers = [DefaultInfo]),
         "imports": attr.string_list(default = []),
     },
     test = True,
)