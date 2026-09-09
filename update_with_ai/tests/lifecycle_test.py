"""Unit tests for the Cleanroom Lifecycle Management Architecture and Assembly Tree."""

from __future__ import annotations

import unittest
from typing import List, Optional, Protocol
from update_with_ai.lib.lifecycle import (
    Initializable,
    LifecycleError,
    LifecycleInitializationError,
    LifecycleIsolationError,
    LifecycleRegistry,
    LifecycleResolutionError,
    LifecycleScope,
    Singleton,
    enter_phase,
    get_active_scope,
    get_default_registry,
    get_singleton,
    singleton,
)


class Logger(Protocol):
    def log(self, msg: str) -> None: ...


class Storage(Protocol):
    def get_data(self) -> str: ...


class GraphReader(Protocol):
    def read_node(self) -> str: ...


class Config(Protocol):
    def get_mode(self) -> str: ...


class CleanedNode(Protocol):
    @property
    def node_id(self) -> str: ...
    def set_node_id(self, node_id: str) -> None: ...


class Runner(Protocol):
    def run(self) -> str: ...


class MockLogger(Initializable):
    def __init__(self) -> None:
        self.logs: List[str] = []
        self.initialized = False
        self.closed = False

    def initialize(self) -> None:
        self.initialized = True
        self.logs.append("logger_initialized")

    def log(self, msg: str) -> None:
        self.logs.append(msg)

    def close(self) -> None:
        self.closed = True


class MockConfig(Initializable):
    def __init__(self) -> None:
        self.initialized = False

    def initialize(self) -> None:
        self.initialized = True

    def get_mode(self) -> str:
        return "fast"


class MockStorage(Initializable):
    def __init__(self) -> None:
        self.initialized = False
        self.mode = ""
        self.closed = False

    def initialize(self) -> None:
        # Resolves Config and Logger on demand during initialize()
        config = get_singleton(Config)
        self.mode = config.get_mode()
        logger = get_singleton(Logger)
        logger.log(f"storage_initialized_with_mode_{self.mode}")
        self.initialized = True

    def get_data(self) -> str:
        return f"storage-data-{self.mode}"

    def read_node(self) -> str:
        return "node-data"

    def teardown(self) -> None:
        self.closed = True


class ServiceA(Protocol):
    def ping(self) -> None: ...


class ServiceB(Protocol):
    def pong(self) -> None: ...


class MockServiceA(Initializable):
    def __init__(self) -> None:
        pass

    def initialize(self) -> None:
        # Accesses B during initialization
        b = get_singleton(ServiceB)
        b.pong()

    def ping(self) -> None:
        pass


class MockServiceB(Initializable):
    def __init__(self) -> None:
        pass

    def initialize(self) -> None:
        # Accesses A during initialization -> cycle!
        a = get_singleton(ServiceA)
        a.ping()

    def pong(self) -> None:
        pass


class MockCleanedNode(Initializable):
    def __init__(self) -> None:
        self._node_id: Optional[str] = None
        self.initialized = False

    def initialize(self) -> None:
        self.initialized = True

    @property
    def node_id(self) -> str:
        assert self._node_id is not None, "CleanedNode.node_id accessed before set_node_id"
        return self._node_id

    def set_node_id(self, node_id: str) -> None:
        self._node_id = node_id


class MockRunner(Initializable):
    def __init__(self) -> None:
        self.initialized = False

    def initialize(self) -> None:
        self.initialized = True

    def run(self) -> str:
        cleaned_node = get_singleton(CleanedNode)
        storage = get_singleton(Storage)
        return f"cleaned {cleaned_node.node_id} with {storage.get_data()}"


class TestLifecycle(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = LifecycleRegistry()

    def test_multi_key_aliasing_returns_identical_instance(self) -> None:
        self.registry.register(MockStorage, keys=[Storage, GraphReader], phase="system")
        self.registry.register(MockConfig, keys=[Config], phase="system")
        self.registry.register(MockLogger, keys=[Logger], phase="system")

        with enter_phase("system", registry=self.registry) as scope:
            storage_instance = scope.get(Storage)
            graph_instance = scope.get(GraphReader)

            self.assertIs(storage_instance, graph_instance)
            self.assertEqual(storage_instance.get_data(), "storage-data-fast")
            self.assertEqual(graph_instance.read_node(), "node-data")

    def test_phase_startup_creates_and_initializes_topologically(self) -> None:
        self.registry.register(MockLogger, keys=[Logger], phase="system")
        self.registry.register(MockConfig, keys=[Config], phase="system")
        self.registry.register(MockStorage, keys=[Storage], phase="system")

        with enter_phase("system", registry=self.registry) as scope:
            logger = scope.get(Logger)
            assert isinstance(logger, MockLogger)
            self.assertTrue(logger.initialized)

            storage = scope.get(Storage)
            assert isinstance(storage, MockStorage)
            self.assertTrue(storage.initialized)

            # Check that Storage.initialize() called Logger during startup
            self.assertIn("storage_initialized_with_mode_fast", logger.logs)

    def test_mutual_dependency_in_initialize_raises_cycle_error(self) -> None:
        self.registry.register(MockServiceA, keys=[ServiceA], phase="system")
        self.registry.register(MockServiceB, keys=[ServiceB], phase="system")

        with self.assertRaises(LifecycleInitializationError) as ctx:
            with enter_phase("system", registry=self.registry):
                pass
        self.assertIn("circular dependency", str(ctx.exception).lower())

    def test_agent_session_child_phase_and_cleaned_node_configuration(self) -> None:
        self.registry.register(MockLogger, keys=[Logger], phase="system")
        self.registry.register(MockConfig, keys=[Config], phase="system")
        self.registry.register(MockStorage, keys=[Storage], phase="system")
        self.registry.register(MockCleanedNode, keys=[CleanedNode], phase="agent_session")
        self.registry.register(MockRunner, keys=[Runner], phase="agent_session")

        with enter_phase("system", registry=self.registry) as system_scope:
            # System phase cannot access session singletons
            with self.assertRaises(LifecycleIsolationError):
                system_scope.get(CleanedNode)

            with self.assertRaises(LifecycleIsolationError):
                get_singleton(Runner)

            # Enter child phase agent_session
            with enter_phase("agent_session", registry=self.registry) as session_scope:
                # 1. Singletons created & initialized
                cleaned_node = get_singleton(CleanedNode)
                assert isinstance(cleaned_node, MockCleanedNode)
                self.assertTrue(cleaned_node.initialized)

                # 2. Block-level configuration of CleanedNode
                cleaned_node.set_node_id("//path/to:dirty_target")
                self.assertEqual(cleaned_node.node_id, "//path/to:dirty_target")

                # 3. Runner resolves CleanedNode (session) and Storage (delegated to system)
                runner = session_scope.get(Runner)
                result = runner.run()
                self.assertEqual(result, "cleaned //path/to:dirty_target with storage-data-fast")

                # 4. Ambient get_singleton works identically
                self.assertIs(get_singleton(Runner), runner)
                self.assertIs(get_singleton(Storage), system_scope.get(Storage))

            # Outside session block, CleanedNode and Runner are inaccessible
            with self.assertRaises(LifecycleIsolationError):
                get_singleton(CleanedNode)

    def test_reverse_order_teardown_on_phase_exit(self) -> None:
        self.registry.register(MockLogger, keys=[Logger], phase="system")
        self.registry.register(MockConfig, keys=[Config], phase="system")
        self.registry.register(MockStorage, keys=[Storage], phase="system")

        logger_ref: Optional[MockLogger] = None
        storage_ref: Optional[MockStorage] = None

        with enter_phase("system", registry=self.registry) as scope:
            logger = scope.get(Logger)
            assert isinstance(logger, MockLogger)
            logger_ref = logger

            storage = scope.get(Storage)
            assert isinstance(storage, MockStorage)
            storage_ref = storage

            self.assertFalse(logger_ref.closed)
            self.assertFalse(storage_ref.closed)

        assert logger_ref is not None
        assert storage_ref is not None
        self.assertTrue(logger_ref.closed)
        self.assertTrue(storage_ref.closed)

    def test_decorator_registration(self) -> None:
        test_reg = LifecycleRegistry()

        @singleton(keys=[Config], phase="system", registry=test_reg)
        class LocalConfig(Initializable):
            def initialize(self) -> None: ...
            def get_mode(self) -> str:
                return "decorator-mode"

        with enter_phase("system", registry=test_reg) as scope:
            cfg = scope.get(Config)
            self.assertEqual(cfg.get_mode(), "decorator-mode")

    def test_assembly_initialize_traversal(self) -> None:
        from update_with_ai.lib import (
            bazel_asm,
            agent_asm,
            dag_asm,
            sandbox_asm,
            bazel_runner_impl,
            agent_runner_impl,
            dag_cleaner_impl,
            sandbox_impl,
        )

        test_reg = LifecycleRegistry()
        # Verify bazel_asm recursively invokes constituent assemblies without error
        bazel_asm.__initialize__(test_reg)

        # Confirm constituents are registered in bazel_asm CONSTITUENTS
        self.assertIn(agent_asm, bazel_asm.CONSTITUENTS)
        self.assertIn(dag_asm, bazel_asm.CONSTITUENTS)
        self.assertIn(sandbox_asm, bazel_asm.CONSTITUENTS)
        self.assertIn(bazel_runner_impl, bazel_asm.CONSTITUENTS)
        self.assertIn(agent_runner_impl, agent_asm.CONSTITUENTS)
        self.assertIn(dag_cleaner_impl, dag_asm.CONSTITUENTS)
        self.assertIn(sandbox_impl, sandbox_asm.CONSTITUENTS)

    def test_register_instance_for_mock_injection(self) -> None:
        """CUJ: Unit test sets up mock instances for collaborator singletons.

        Verifies that an existing pre-constructed mock instance can be registered directly
        under an interface protocol key into a test LifecycleRegistry and resolved
        identically via get_singleton inside a lifecycle scope.
        """
        # Testing requirement: Pre-constructed mock instance registered directly under interface protocol
        test_reg = LifecycleRegistry()

        class FakeCustomLogger:
            def __init__(self, prefix: str) -> None:
                self.prefix = prefix
                self.messages: List[str] = []

            def log(self, msg: str) -> None:
                self.messages.append(f"{self.prefix}: {msg}")

        custom_mock = FakeCustomLogger(prefix="TEST")
        test_reg.register_instance(custom_mock, keys=[Logger], tier="system")

        with enter_phase("system", registry=test_reg) as scope:
            # Testing requirement: Resolved singleton instance is identical to injected mock
            resolved = scope.get(Logger)
            self.assertIs(resolved, custom_mock)
            resolved.log("hello world")
            self.assertEqual(custom_mock.messages, ["TEST: hello world"])
            # Testing requirement: get_singleton in ambient scope resolves the mock instance
            self.assertIs(get_singleton(Logger), custom_mock)

    def test_ambient_system_lifecycle(self) -> None:
        """CUJ: System lifecycle is ambiently active without explicit enter_phase.

        Verifies that system-tier singletons can be resolved on-demand from module-level
        ambient scope, whereas attempting to resolve an agent_session singleton outside
        of an active session phase raises LifecycleIsolationError.
        """
        # Testing requirement: Ambient system scope can resolve system-tier singletons
        from update_with_ai.lib.bazel_node_id_utils_impl import BazelNodeIdentifierUtility
        from update_with_ai.lib.bazel_node_config_impl import NodeConfig
        from update_with_ai.lib import bazel_asm
        bazel_asm.__initialize__()

        util = get_singleton(BazelNodeIdentifierUtility)
        self.assertIsNotNone(util)

        # Testing requirement: Resolving session singleton outside session raises LifecycleIsolationError
        with self.assertRaises(LifecycleIsolationError):
            get_singleton(NodeConfig)

    def test_singleton_tier_declaration_and_empty_initialize(self) -> None:
        """CUJ: Singletons subclass Singleton, declare their tier, and inherit empty initialize hook.

        Verifies that classes implementing Singleton with tier='system' or tier='agent_session'
        do not need boilerplate initialize() methods, and that tier mismatches during registration
        raise LifecycleError.
        """
        # Testing requirement: Subclass Singleton without explicit initialize does not fail
        class MyService(Singleton):
            tier = "system"

            def get_val(self) -> str:
                return "val"

        test_reg = LifecycleRegistry()
        # Testing requirement: register_singleton infers tier from class
        desc = test_reg.register_singleton(MyService, keys=[MyService])
        self.assertEqual(desc.phase, "system")

        # Testing requirement: Tier mismatch raises LifecycleError
        with self.assertRaises(LifecycleError):
            test_reg.register_singleton(MyService, keys=[MyService], tier="agent_session")

    def test_caller_tier_isolation_enforcement(self) -> None:
        """CUJ: System singleton cannot access agent_session singleton even inside active session.

        Verifies that if a Singleton declaring tier='system' calls get_singleton on an
        agent_session singleton, LifecycleIsolationError is raised to prevent cross-tier state leaks.
        """
        test_reg = LifecycleRegistry()

        class DummySessionItem(Singleton):
            tier = "agent_session"

        class DummySystemCaller(Singleton):
            tier = "system"

            def illegal_access(self) -> None:
                get_singleton(DummySessionItem)

        test_reg.register_singleton(DummySessionItem, keys=[DummySessionItem])
        test_reg.register_singleton(DummySystemCaller, keys=[DummySystemCaller])

        with enter_phase("agent_session", registry=test_reg) as session:
            # Testing requirement: Session code can resolve session items
            item = session.get_singleton(DummySessionItem)
            self.assertIsInstance(item, DummySessionItem)

            # Testing requirement: System singleton caller is blocked from accessing session items
            caller = session.get_singleton(DummySystemCaller)
            with self.assertRaises(LifecycleIsolationError):
                caller.illegal_access()

    def test_enter_phase_scoped_get_singleton(self) -> None:
        """CUJ: enter_phase yields scope providing scoped get_singleton and direct call resolver.

        Verifies that transition boundaries can use session.get_singleton(key) or session(key)
        to resolve singletons within the entered phase.
        """
        test_reg = LifecycleRegistry()

        class AlphaService(Singleton):
            tier = "agent_session"
            value = 42

        test_reg.register_singleton(AlphaService, keys=[AlphaService])

        with enter_phase("agent_session", registry=test_reg) as session:
            # Testing requirement: session.get_singleton resolves phase singleton
            svc1 = session.get_singleton(AlphaService)
            self.assertEqual(svc1.value, 42)
            # Testing requirement: session callable resolver session(key)
            svc2 = session(AlphaService)
            self.assertIs(svc1, svc2)


if __name__ == "__main__":
    unittest.main()
