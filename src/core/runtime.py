import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import Session, select

from src.core.config import settings
from src.core.database import engine, init_db
from src.models import (
    Blacklist,
    BlacklistEntry,
    Decision,
    DecisionEntry,
    RiskLevel,
    RiskLevelEntry,
)

logger = logging.getLogger(__name__)


class DecisionRuntime:
    __slots__ = ("decisions", "blacklist", "risk_levels")

    def __init__(
        self,
        decisions: list[DecisionEntry],
        blacklist: list[BlacklistEntry] | None = None,
        risk_levels: list[RiskLevelEntry] | None = None,
    ):
        self.decisions: list[DecisionEntry] = decisions
        self.blacklist: list[BlacklistEntry] = blacklist or []
        self.risk_levels: list[RiskLevelEntry] = risk_levels or []

    def decision_names(self) -> set[str]:
        """Return set of decision names for lookup."""
        return {d.name for d in self.decisions}

    def blacklist_names(self) -> set[str]:
        """Return set of blacklist entry names for lookup."""
        return {b.name for b in self.blacklist}

    def risk_level_names(self) -> set[str]:
        """Return set of risk level names for lookup."""
        return {r.name for r in self.risk_levels}

    def reload_from_db(self):
        """Reload decisions, blacklist, and risk levels from database."""
        with Session(engine) as session:
            decisions = session.exec(select(Decision)).all()
            blacklist = session.exec(select(Blacklist)).all()
            risk_levels = session.exec(select(RiskLevel)).all()

            self.decisions = [
                DecisionEntry(
                    name=d.name,
                    description=d.description,
                    risk_level_id=d.risk_level_id,
                    justification=d.justification,
                )
                for d in decisions
            ]
            self.blacklist = [
                BlacklistEntry(name=b.name, reason=b.reason) for b in blacklist
            ]
            self.risk_levels = [
                RiskLevelEntry(name=r.name, degree=r.degree, description=r.description)
                for r in risk_levels
            ]

        logger.info(
            f"Reloaded {len(self.decisions)} decisions, "
            f"{len(self.blacklist)} blacklist entries, "
            f"and {len(self.risk_levels)} risk levels from database"
        )

    def persist_decision(self, entry: DecisionEntry) -> Decision:
        """Persist a decision to database."""
        with Session(engine) as session:
            db_decision = Decision(
                name=entry.name,
                description=entry.description,
                risk_level_id=entry.risk_level_id,
                justification=entry.justification,
            )
            session.add(db_decision)
            session.commit()
            session.refresh(db_decision)
            return db_decision

    def persist_blacklist(self, entry: BlacklistEntry) -> Blacklist:
        """Persist a blacklist entry to database."""
        with Session(engine) as session:
            db_entry = Blacklist(name=entry.name, reason=entry.reason)
            session.add(db_entry)
            session.commit()
            session.refresh(db_entry)
            return db_entry

    def persist_risk_level(self, entry: RiskLevelEntry) -> RiskLevel:
        """Persist a risk level to database."""
        with Session(engine) as session:
            db_risk_level = RiskLevel(
                name=entry.name, degree=entry.degree, description=entry.description
            )
            session.add(db_risk_level)
            session.commit()
            session.refresh(db_risk_level)
            return db_risk_level

    def delete_decision(self, name: str) -> bool:
        """Delete a decision from database."""
        with Session(engine) as session:
            decision = session.exec(
                select(Decision).where(Decision.name == name)
            ).first()
            if decision:
                session.delete(decision)
                session.commit()
                return True
            return False

    def delete_blacklist(self, name: str) -> bool:
        """Delete a blacklist entry from database."""
        with Session(engine) as session:
            entry = session.exec(
                select(Blacklist).where(Blacklist.name == name)
            ).first()
            if entry:
                session.delete(entry)
                session.commit()
                return True
            return False

    def delete_risk_level(self, name: str) -> bool:
        """Delete a risk level from database."""
        with Session(engine) as session:
            risk_level = session.exec(
                select(RiskLevel).where(RiskLevel.name == name)
            ).first()
            if risk_level:
                session.delete(risk_level)
                session.commit()
                return True
            return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} runtime...")

    init_db()

    with Session(engine) as session:
        # Initialize default risk levels if none exist
        existing_risk_levels = session.exec(select(RiskLevel)).all()
        if not existing_risk_levels:
            default_risk_levels = [
                RiskLevel(
                    name="Low Risk", degree=30, description="Minimal oversight required"
                ),
                RiskLevel(
                    name="Medium Risk", degree=60, description="Standard review process"
                ),
                RiskLevel(
                    name="High Risk", degree=90, description="Requires senior approval"
                ),
                RiskLevel(
                    name="Critical Risk",
                    degree=100,
                    description="Executive approval only",
                ),
            ]
            for rl in default_risk_levels:
                session.add(rl)
            session.commit()
            logger.info(f"Created {len(default_risk_levels)} default risk levels")

        # Seed do_nothing decision if no decisions exist
        existing_decisions = session.exec(select(Decision)).all()
        if not existing_decisions:
            low_risk = session.exec(
                select(RiskLevel).where(RiskLevel.name == "Low Risk")
            ).first()
            session.add(
                Decision(
                    name="do_nothing", risk_level_id=low_risk.id if low_risk else None
                )
            )
            session.commit()
            logger.info("Seeded 'do_nothing' decision")

        # Load all data
        decisions = [
            DecisionEntry(
                name=d.name,
                description=d.description,
                risk_level_id=d.risk_level_id,
                justification=d.justification,
            )
            for d in session.exec(select(Decision)).all()
        ]
        blacklist = [
            BlacklistEntry(name=b.name, reason=b.reason)
            for b in session.exec(select(Blacklist)).all()
        ]
        risk_levels = [
            RiskLevelEntry(name=r.name, degree=r.degree, description=r.description)
            for r in session.exec(select(RiskLevel)).all()
        ]

    runtime = DecisionRuntime(
        decisions=decisions, blacklist=blacklist, risk_levels=risk_levels
    )

    app.state.decision_runtime = runtime

    if settings.KAFKA_ENABLED:
        from src.services.decision_pipeline import setup_anomaly_pipeline

        setup_anomaly_pipeline(runtime)
        logger.info("Kafka anomaly pipeline started")

    logger.info("Runtime initialized successfully.")

    yield

    logger.info("Shutting down runtime...")
