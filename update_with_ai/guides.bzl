"""Guide-node entry points.

update_guide_with_ai creates a guide node by delegating to the general
update_with_ai macro (macros.bzl); the node's agent updates the guide file
per the display name given.
"""

load("//update_with_ai:macros.bzl", "update_with_ai")

def update_guide_with_ai(name, src, deps, display_name):
    """Create a guide node whose agent updates the guide file.

    Args:
        name: Target name.
        src: The guide file path the agent updates (e.g. "high_level_spec.md").
        deps: Dependency node targets readable by the guide's agent.
        display_name: Human-readable description of what the guide is.
    """
    update_with_ai(
        name = name,
        src = src,
        deps = deps,
        prompt = "Update %s, which is a %s." % (src, display_name),
        visibility = ["//visibility:public"],
    )
