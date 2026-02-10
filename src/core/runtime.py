from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.core.config import settings
from src.models import Decision, Blacklist, DecisionEntry, BlacklistEntry
from src.core.database import init_db, engine
from sqlmodel import Session, select
import logging

logger = logging.getLogger(__name__)


class DecisionRuntime:
    __slots__ = ("decisions", "blacklist")

    def __init__(self, decisions: list[DecisionEntry], blacklist: list[BlacklistEntry] | None = None):
        self.decisions: list[DecisionEntry] = decisions
        self.blacklist: list[BlacklistEntry] = blacklist or []

    def decision_names(self) -> set[str]:
        """Return set of decision names for lookup."""
        return {d.name for d in self.decisions}

    def blacklist_names(self) -> set[str]:
        """Return set of blacklist entry names for lookup."""
        return {b.name for b in self.blacklist}

    def reload_from_db(self):
        """Reload decisions and blacklist from database."""
        with Session(engine) as session:
            decisions = session.exec(select(Decision)).all()
            blacklist = session.exec(select(Blacklist)).all()

            self.decisions = [DecisionEntry(name=d.name, description=d.description) for d in decisions]
            self.blacklist = [BlacklistEntry(name=b.name, reason=b.reason) for b in blacklist]

        logger.info(f"Reloaded {len(self.decisions)} decisions and {len(self.blacklist)} blacklist entries from database")

    def persist_decision(self, entry: DecisionEntry) -> Decision:
        """Persist a decision to database."""
        with Session(engine) as session:
            db_decision = Decision(name=entry.name, description=entry.description)
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

    def delete_decision(self, name: str) -> bool:
        """Delete a decision from database."""
        with Session(engine) as session:
            decision = session.exec(select(Decision).where(Decision.name == name)).first()
            if decision:
                session.delete(decision)
                session.commit()
                return True
            return False

    def delete_blacklist(self, name: str) -> bool:
        """Delete a blacklist entry from database."""
        with Session(engine) as session:
            entry = session.exec(select(Blacklist).where(Blacklist.name == name)).first()
            if entry:
                session.delete(entry)
                session.commit()
                return True
            return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} runtime...")

    init_db()

    with Session(engine) as session:
        existing_decisions = session.exec(select(Decision)).all()

        if not existing_decisions:
            default_decisions = [Decision(name=d) for d in settings.DEFAULT_DECISIONS]
            for d in default_decisions:
                session.add(d)
            session.commit()
            logger.info(f"Created {len(default_decisions)} default decisions")

        decisions = [DecisionEntry(name=d.name, description=d.description) for d in session.exec(select(Decision)).all()]
        blacklist = [BlacklistEntry(name=b.name, reason=b.reason) for b in session.exec(select(Blacklist)).all()]

    runtime = DecisionRuntime(decisions=decisions, blacklist=blacklist)

    app.state.decision_runtime = runtime

    logger.info("Runtime initialized successfully.")

    yield

    logger.info("Shutting down runtime...")
