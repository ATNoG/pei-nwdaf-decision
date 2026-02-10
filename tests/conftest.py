from fastapi.testclient import TestClient
from src.models.db import Decision, Blacklist, RiskLevel
from src.core.database import get_session
from src.core.runtime import DecisionRuntime
from src.models import DecisionEntry, BlacklistEntry, RiskLevelEntry
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

    # Initialize runtime with default risk levels and decisions
    with Session(test_engine) as session:
        # Create default risk levels
        default_risk_levels = [
            RiskLevel(name="Low Risk", degree=30, description="Minimal oversight required"),
            RiskLevel(name="Medium Risk", degree=60, description="Standard review process"),
            RiskLevel(name="High Risk", degree=90, description="Requires senior approval"),
        ]
        for rl in default_risk_levels:
            session.add(rl)
        session.commit()

        # Get low risk level for default decisions
        low_risk = session.exec(select(RiskLevel).where(RiskLevel.name == "Low Risk")).first()

        # Create default decisions
        default_decisions = [
            Decision(name="ALLOCATE X", risk_level_id=low_risk.id if low_risk else None),
            Decision(name="SUBVERT Y", risk_level_id=low_risk.id if low_risk else None),
            Decision(name="ABDUCT Z", risk_level_id=low_risk.id if low_risk else None),
        ]
        for d in default_decisions:
            session.add(d)
        session.commit()

        # Reload to get IDs
        decisions_db = session.exec(select(Decision)).all()
        blacklist_db = session.exec(select(Blacklist)).all()
        risk_levels_db = session.exec(select(RiskLevel)).all()

        decisions = [
            DecisionEntry(
                name=d.name,
                description=d.description,
                risk_level_id=d.risk_level_id,
                justification=d.justification
            ) for d in decisions_db
        ]
        blacklist = [
            BlacklistEntry(name=b.name, reason=b.reason)
            for b in blacklist_db
        ]
        risk_levels = [
            RiskLevelEntry(
                name=r.name,
                degree=r.degree,
                description=r.description
            ) for r in risk_levels_db
        ]

    # Mock risk level with id for persist_risk_level
    class MockRiskLevel:
        def __init__(self, id_num):
            self.id = id_num

    _risk_id_counter = [len(risk_levels) + 1]

    def mock_persist_risk_level(entry):
        mock_rl = MockRiskLevel(_risk_id_counter[0])
        _risk_id_counter[0] += 1
        return mock_rl

    # Create a mock runtime that doesn't use PostgreSQL
    runtime = Mock(spec=DecisionRuntime)
    runtime.decisions = decisions
    runtime.blacklist = blacklist
    runtime.risk_levels = risk_levels
    runtime.decision_names = lambda: {d.name for d in runtime.decisions}
    runtime.blacklist_names = lambda: {b.name for b in runtime.blacklist}
    runtime.risk_level_names = lambda: {r.name for r in runtime.risk_levels}
    runtime.persist_decision = lambda entry: None
    runtime.persist_blacklist = lambda entry: None
    runtime.persist_risk_level = mock_persist_risk_level
    runtime.delete_decision = lambda name: None
    runtime.delete_blacklist = lambda name: None
    runtime.delete_risk_level = lambda name: None

    test_app.state.decision_runtime = runtime

    with TestClient(test_app) as test_client:
        yield test_client

    test_app.dependency_overrides.clear()
