import logging

from .config import settings

logger = logging.getLogger(__name__)

_disclaimer: str | None = None


def load_disclaimer() -> None:
    global _disclaimer
    with open(settings.LLM_DISCLAIMER_PATH) as f:
        _disclaimer = f.read().strip()
    logger.info("Loaded disclaimer from %s", settings.LLM_DISCLAIMER_PATH)


def get_disclaimer() -> str:
    if _disclaimer is None:
        raise RuntimeError("Disclaimer not loaded — call load_disclaimer() at startup")
    return _disclaimer
