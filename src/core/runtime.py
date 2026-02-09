from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.core.config import settings
import logging

logger = logging.getLogger()

class DecisionRuntime:
    __slots__ = ("decisions", "blacklist")

    def __init__(self, decisions: list[str], blacklist: list[str]):
        self.decisions: list[str] = decisions
        self.blacklist: list[str] = blacklist

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} runtime...")

    runtime = DecisionRuntime(decisions=settings.DEFAULT_DECISIONS)

    app.state.decision_runtime = runtime

    logger.info("Runtime initialized successfully.")

    yield

    logger.info("Shutting down runtime...")
