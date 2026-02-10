from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.core.config import settings, DecisionEntry, BlacklistEntry
import logging

logger = logging.getLogger()

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} runtime...")

    default_decisions = [DecisionEntry(name=d) for d in settings.DEFAULT_DECISIONS]
    runtime = DecisionRuntime(decisions=default_decisions)

    app.state.decision_runtime = runtime

    logger.info("Runtime initialized successfully.")

    yield

    logger.info("Shutting down runtime...")
