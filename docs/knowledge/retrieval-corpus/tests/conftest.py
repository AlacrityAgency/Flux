"""Pytest fixtures and native asyncio runner hook for Flux Engine test suite."""

import asyncio
import inspect
import pytest

from flux.storage.database import init_db
from flux.storage.repository import Repository
from flux.providers.fake import FakeProvider
from flux.engine.orchestrator import FluxEngine
from flux.engine.scheduler import ConcurrencyLimiter


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    """Enable running async test functions natively without external plugins."""
    if inspect.iscoroutinefunction(pyfuncitem.obj):
        testargs = {
            arg: pyfuncitem.funcargs[arg]
            for arg in pyfuncitem._fixtureinfo.argnames
            if arg in pyfuncitem.funcargs
        }
        asyncio.run(pyfuncitem.obj(**testargs))
        return True
    return None


@pytest.fixture
def db_conn():
    conn = init_db(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def repo(db_conn):
    return Repository(db_conn)


@pytest.fixture
def fake_provider():
    return FakeProvider()


@pytest.fixture
def limiter():
    return ConcurrencyLimiter(max_concurrent=2)


@pytest.fixture
def engine(repo, fake_provider, limiter):
    return FluxEngine(repo=repo, provider=fake_provider, concurrency_limiter=limiter)


@pytest.fixture
def sample_task_data():
    return {
        "workflow": "auto",  # Preserve coverage of the legacy execution path.
        "task_id": "task_demo_001",
        "root_id": "task_demo_001",
        "project_id": "flux_core",
        "human_owner": "Danial",
        "objective": "Produce complete documentation for Flux agentic engine architecture.",
        "scope": ["Architecture", "Engine components", "Contract definitions"],
        "out_of_scope": ["GUI panel", "CRM"],
        "acceptance_criteria": [
            "Documentation draft matches requirements",
            "Clear component diagram included"
        ],
        "dependencies": [],
        "allowed_tools": ["file_read", "file_write"],
        "allowed_paths": ["docs/"],
        "artifact_refs": [],
        "budget_cap_usd": 0.50,
        "max_attempts": 3,
        "priority": "P1",
        "data_class": "internal"
    }
