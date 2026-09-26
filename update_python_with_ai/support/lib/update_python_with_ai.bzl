"""Specification-node entry points.

update_python_with_ai defines a unit and convenience node targets for each role.
All node machinery (manifest, *_clean, *_feedback, *_dirty, *_change, *_prompt targets)
comes from update_with_ai.

The macro returns its own label (":" + name) so a BUILD file can bind the
result to a variable and pass it to a dependent node's module deps. Module deps
are plain labels (same or other packages); the graph is resolved at run
time from the loaded manifests.
"""

load(
    "//update_with_ai/support/lib:update_with_ai.bzl",
    "define_node",
    "define_unit",
)

PYTHON_ROLES = ["high", "requirements", "grounding", "low", "lib", "test", "qa", "coverage"]

def update_python_with_ai(name, module_deps = [], template_parameters = None, visibility = None):
    """Create a unit and convenience node targets for each role.

    Args:
        name: Target name prefix (e.g. "dag_storage").
        module_deps: List of dependency unit labels (e.g. [":dag_clean_logic"]).
        template_parameters: Optional dictionary of template parameters (kept for compatibility).
        visibility: Optional visibility applied to all generated targets.

    Returns:
        The created unit label (":" + name).
    """
    is_impl = name.endswith("_impl")
    is_asm = name.endswith("_asm")
    is_ext = name.endswith("_ext")
    component_type = "implementation" if is_impl else ("assembly" if is_asm else ("external" if is_ext else "interface"))

    # 1. Define the unit
    define_unit(
        name = name,
        unit_deps = module_deps,
        component_type = component_type,
        visibility = visibility,
    )

    # 2. Define flat set of convenience node targets for each role
    for role in PYTHON_ROLES:
        define_node(
            name = name + "_" + role,
            unit = ":" + name,
            role = "//update_python_with_ai:" + role,
            visibility = visibility,
        )

    return ":" + name


