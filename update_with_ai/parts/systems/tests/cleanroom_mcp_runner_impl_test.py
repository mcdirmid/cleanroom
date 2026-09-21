import os
import unittest
from typing import Any, Optional, Sequence
from support.lib.lifecycle import (
    LifecycleRegistry,
    Singleton,
    enter_phase,
    system,
)
from update_with_ai.parts.core.lib import runner_logger
from update_with_ai.parts.mcp.lib import mcp_server
from update_with_ai.parts.systems.lib import cleanroom_mcp_runner
from update_with_ai.parts.systems.lib import cleanroom_mcp_runner_impl


class MockRunnerLogger(runner_logger.RunnerLogger, Singleton):
    tier = system

    def __init__(self) -> None:
        self.events: list[runner_logger.LogEvent] = []

    def consume(self, event: runner_logger.LogEvent) -> None:
        self.events.append(event)


class MockMcpServer(mcp_server.McpServer, Singleton):
    tier = system

    def __init__(self) -> None:
        self.started_transports: list[str] = []
        self.stopped: bool = False

    def register_role_agent(self, conversation_id: Any, role_address: str, unit_root: str) -> str:
        return "mock"

    def deregister_role_agent(self, conversation_id: Any) -> str:
        return "mock"

    def execute_domain_tool(self, conversation_id: Any, tool_name: str, arguments: Any) -> str:
        return "mock"

    def handle_validate_access(self, conversation_id: Any, tool_name: str, file_path: str) -> Any:
        return {}

    def handle_filter_dir(self, conversation_id: Any, directory_path: str, entries: Sequence[str]) -> Sequence[str]:
        return entries

    def start(self, transport: str) -> None:
        self.started_transports.append(transport)

    def stop(self) -> None:
        self.stopped = True


class CleanroomMcpRunnerImplTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()
        cleanroom_mcp_runner_impl.__initialize__(self.registry)
        self.registry.register_singleton(
            MockRunnerLogger,
            keys=[MockRunnerLogger, runner_logger.RunnerLogger],
            tier=system,
        )
        self.registry.register_singleton(
            MockMcpServer,
            keys=[MockMcpServer, mcp_server.McpServer],
            tier=system,
        )

    def test_parse_arguments_default(self) -> None:
        with enter_phase(system, registry=self.registry) as scope:
            runner = scope.get_singleton(cleanroom_mcp_runner.McpRunner)

            # Requirement: The transport resolves from `--transport`, accepting `stdio` or `sse`, defaulting to `stdio`.
            # Requirement: The host resolves from `--host`, defaulting to `127.0.0.1`.
            # Requirement: The port resolves from `--port` as an integer, defaulting to 8765.
            # Requirement: The batch size resolves from `--batch-size` as an integer, defaulting to 10.
            opts = runner.parse_arguments([])
            self.assertEqual(opts.transport, "stdio")
            self.assertEqual(opts.host, "127.0.0.1")
            self.assertEqual(opts.port, 8765)
            self.assertEqual(opts.batch_size, 10)

    def test_parse_arguments_custom(self) -> None:
        with enter_phase(system, registry=self.registry) as scope:
            runner = scope.get_singleton(cleanroom_mcp_runner.McpRunner)

            # Requirement: The transport resolves from `--transport`, accepting `stdio` or `sse`, defaulting to `stdio`.
            # Requirement: The host resolves from `--host`, defaulting to `127.0.0.1`.
            # Requirement: The port resolves from `--port` as an integer, defaulting to 8765.
            # Requirement: The batch size resolves from `--batch-size` as an integer, defaulting to 10.
            opts = runner.parse_arguments([
                "--transport", "sse",
                "--host", "0.0.0.0",
                "--port", "9999",
                "--batch-size", "4",
            ])
            self.assertEqual(opts.transport, "sse")
            self.assertEqual(opts.host, "0.0.0.0")
            self.assertEqual(opts.port, 9999)
            self.assertEqual(opts.batch_size, 4)

    def test_parse_arguments_invalid(self) -> None:
        with enter_phase(system, registry=self.registry) as scope:
            runner = scope.get_singleton(cleanroom_mcp_runner.McpRunner)

            # Requirement: Parsing arguments signals an error when invalid or unknown options are provided.
            with self.assertRaises(ValueError):
                runner.parse_arguments(["--unknown-flag"])

            with self.assertRaises(ValueError):
                runner.parse_arguments(["--transport", "websocket"])

            with self.assertRaises(ValueError):
                runner.parse_arguments(["--port", "not-a-number"])

    def test_run_stdio(self) -> None:
        with enter_phase(system, registry=self.registry) as scope:
            runner = scope.get_singleton(cleanroom_mcp_runner.McpRunner)
            mock_server = scope.get_singleton(MockMcpServer)

            # Requirement: Executing the runner validates runner options and starts the server using the configured transport.
            # Requirement: When standard input/output transport is requested, the runner starts the server over standard input/output.
            # Requirement: The runner sets the batch size in the execution environment.
            opts = cleanroom_mcp_runner.RunnerOptions(transport="stdio", batch_size=10)
            runner.run(opts)
            self.assertEqual(mock_server.started_transports, ["stdio"])
            self.assertEqual(os.environ.get("BATCH_SIZE"), "10")

    def test_run_sse(self) -> None:
        with enter_phase(system, registry=self.registry) as scope:
            runner = scope.get_singleton(cleanroom_mcp_runner.McpRunner)
            mock_server = scope.get_singleton(MockMcpServer)
            mock_logger = scope.get_singleton(MockRunnerLogger)

            # Requirement: When Server-Sent Events transport is requested, the runner configures server host and port parameters, logs startup progress to the runner logger, and starts the server over Server-Sent Events.
            # Requirement: The runner sets the batch size in the execution environment.
            opts = cleanroom_mcp_runner.RunnerOptions(
                transport="sse",
                host="127.0.0.1",
                port=8765,
                batch_size=5,
            )
            runner.run(opts)
            self.assertEqual(mock_server.started_transports, ["sse"])
            self.assertEqual(os.environ.get("MCP_HOST"), "127.0.0.1")
            self.assertEqual(os.environ.get("MCP_PORT"), "8765")
            self.assertEqual(os.environ.get("BATCH_SIZE"), "5")
            self.assertTrue(any("runner_start" == e.event_name for e in mock_logger.events))

    def test_main(self) -> None:
        # Test main CLI entrypoint invocation
        cleanroom_mcp_runner_impl.main(
            ["--transport", "stdio"], registry=self.registry
        )


if __name__ == "__main__":
    unittest.main()

# Untested requirements: None
