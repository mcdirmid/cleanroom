# Requirements specified in cleanroom_mcp_runner_impl.pyi
from __future__ import annotations
import argparse
import importlib
import os
import sys
from typing import Optional, Sequence

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
for _p in [_repo_root, os.path.join(_repo_root, "update_python_with_ai"), os.path.join(_repo_root, "update_with_ai")]:
    if _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)  # pragma: no cover (assumption: bootstrap path insertion when run directly)
if not os.environ.get("BUILD_WORKSPACE_DIRECTORY"):
    os.environ["BUILD_WORKSPACE_DIRECTORY"] = _repo_root

if not __package__:  # pragma: no cover (assumption: standalone execution bootstrap)
    __package__ = "update_with_ai.parts.systems.lib"
    sys.modules.setdefault(__package__, importlib.import_module(__package__))

from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    enter_phase,
    get_default_registry,
    get_singleton,
    system,
)
from update_with_ai.parts.core.lib import runner_logger
from update_with_ai.parts.mcp.lib import mcp_server
from . import cleanroom_mcp_runner


class McpRunner(cleanroom_mcp_runner.McpRunner, Singleton):
    tier = system

    def __init__(self) -> None:
        pass

    def run(self, options: cleanroom_mcp_runner.RunnerOptions) -> None:
        os.environ["BATCH_SIZE"] = str(options.batch_size)
        server = get_singleton(mcp_server.McpServer)
        if options.transport == "sse":
            os.environ["MCP_HOST"] = options.host
            os.environ["MCP_PORT"] = str(options.port)
            logger = get_singleton(runner_logger.RunnerLogger)
            logger.consume(
                runner_logger.LogEvent(
                    event_name="runner_start",
                    summary=f"Starting Cleanroom FastMCP server on SSE at http://{options.host}:{options.port}/sse",
                    transcript_representation=f"Cleanroom FastMCP SSE server listening on http://{options.host}:{options.port}/sse",
                )
            )
            server.start("sse")
        else:
            server.start("stdio")

    def parse_arguments(
        self, arguments: Sequence[str]
    ) -> cleanroom_mcp_runner.RunnerOptions:
        parser = argparse.ArgumentParser(
            prog="cleanroom_mcp_server",
            description="Run Cleanroom FastMCP Server",
            exit_on_error=False,
        )
        parser.add_argument(
            "--transport",
            choices=["stdio", "sse"],
            default="stdio",
            help="Transport protocol (stdio or sse)",
        )
        parser.add_argument(
            "--host",
            default="127.0.0.1",
            help="Listening host for SSE transport (default: 127.0.0.1)",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=8765,
            help="Listening port for SSE transport (default: 8765)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=10,
            help="Maximum number of dirty nodes processed together in a batch (default: 10)",
        )
        try:
            parsed, unknown = parser.parse_known_args(arguments)
            if unknown:
                raise ValueError(f"Unknown arguments: {unknown}")
            return cleanroom_mcp_runner.RunnerOptions(
                transport=parsed.transport,
                host=parsed.host,
                port=parsed.port,
                batch_size=parsed.batch_size,
            )
        except SystemExit:  # pragma: no cover (assumption: CLI help exit)
            sys.exit(0)  # pragma: no cover (assumption: CLI help exit)
        except argparse.ArgumentError as e:
            raise ValueError(f"Invalid arguments: {e}") from e


def __initialize__(registry: Optional[LifecycleRegistry] = None) -> None:
    reg = get_default_registry() if registry is None else registry
    reg.register_singleton(
        McpRunner,
        keys=[McpRunner, cleanroom_mcp_runner.McpRunner],
        tier=system,
    )

_initialize_ = __initialize__


def main(
    argv: Optional[Sequence[str]] = None,
    registry: Optional[LifecycleRegistry] = None,
) -> None:
    args_list = list(sys.argv[1:]) if argv is None else list(argv)
    for i, a in enumerate(args_list):
        if a == "--batch-size" and i + 1 < len(args_list):
            os.environ["BATCH_SIZE"] = args_list[i + 1]
            break
        elif a.startswith("--batch-size="):
            os.environ["BATCH_SIZE"] = a.split("=", 1)[1]
            break
    reg = get_default_registry() if registry is None else registry
    if reg.get_prototype(system).get_descriptor(cleanroom_mcp_runner.McpRunner) is None:  # pragma: no cover (assumption: uninitialized registry fallback)
        import importlib

        try:
            asm = importlib.import_module(
                "update_with_ai.parts.systems.lib.bazel_mcp_system_asm"
            )
            asm.__initialize__(reg)
        except (ImportError, AttributeError):
            pass
    with enter_phase(system, registry=reg) as scope:
        runner = scope.get_singleton(cleanroom_mcp_runner.McpRunner)
        args_list = list(sys.argv[1:]) if argv is None else list(argv)
        opts = runner.parse_arguments(args_list)
        runner.run(opts)


if __name__ == "__main__":  # pragma: no cover (assumption: CLI entrypoint)
    main()
