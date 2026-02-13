from datetime import datetime, timezone

from fastapi.testclient import TestClient
from src.models.db import Decision, Blacklist, DecisionResult
from src.core.database import get_session
from src.core.runtime import DecisionRuntime
from src.models import DecisionEntry, BlacklistEntry
from src.routers.v1 import router as v1_router
from sqlmodel import SQLModel, create_engine, Session, select
import pytest
from unittest.mock import Mock
from sqlalchemy.pool import StaticPool


# Use in-memory SQLite for tests
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Setup test database before each test."""
    SQLModel.metadata.create_all(test_engine)
    yield
    SQLModel.metadata.drop_all(test_engine)


@pytest.fixture
def client(setup_test_db):
    """Test client for FastAPI app."""
    from fastapi import FastAPI

    # Create a fresh app without lifespan for testing
    test_app = FastAPI()
    test_app.include_router(v1_router, prefix="/api/v1")

    @test_app.get("/health")
    async def health():
        return {"status": "healthy"}

    # Override the database dependency
    def override_get_session():
        with Session(test_engine) as session:
            yield session

    test_app.dependency_overrides[get_session] = override_get_session

    # Initialize runtime with default decisions
    with Session(test_engine) as session:
        default_decisions = [
            Decision(name="ALLOCATE X"),
            Decision(name="SUBVERT Y"),
            Decision(name="ABDUCT Z"),
        ]
        for d in default_decisions:
            session.add(d)
        session.commit()

        decisions = [DecisionEntry(name=d.name, description=d.description) for d in session.exec(select(Decision)).all()]
        blacklist = [BlacklistEntry(name=b.name, reason=b.reason) for b in session.exec(select(Blacklist)).all()]

    # Create a mock runtime that doesn't use PostgreSQL
    runtime = Mock(spec=DecisionRuntime)
    runtime.decisions = decisions
    runtime.blacklist = blacklist
    runtime.decision_names = lambda: {d.name for d in runtime.decisions}
    runtime.blacklist_names = lambda: {b.name for b in runtime.blacklist}
    runtime.persist_decision = lambda entry: None
    runtime.persist_blacklist = lambda entry: None
    runtime.delete_decision = lambda name: None
    runtime.delete_blacklist = lambda name: None

    test_app.state.decision_runtime = runtime

    with TestClient(test_app) as test_client:
        yield test_client

    test_app.dependency_overrides.clear()


@pytest.fixture
def seed_decision_results(client):
    """Seed the test database with decision results."""
    with Session(test_engine) as session:
        result1 = DecisionResult(
            decision_name="ALLOCATE X",
            status="applied",
            confidence=0.85,
            details={"reason": "high traffic detected"},
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        result2 = DecisionResult(
            decision_name="SUBVERT Y",
            status="pending",
            confidence=0.72,
            details=None,
            created_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
        )
        session.add(result1)
        session.add(result2)
        session.commit()
