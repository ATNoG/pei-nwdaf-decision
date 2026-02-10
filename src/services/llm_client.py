import json
import os
import logging
import httpx
from typing import Any
from ..schemas import DecisionRequest

PROMPT_PATH: str = "llm/prompt.txt"
SYSTEM_PATH: str = "llm/system.txt"

logger = logging.getLogger("LLM_client")


class LLMClient:
    def __init__(self) -> None:
        # TODO load config from src/core/config

        self._url: str | None = os.environ.get("LLM_URL")
        self._api_key: str | None = os.environ.get("LLM_API_KEY")
        self._model: str | None = os.environ.get("LLM_MODEL")

        with open(PROMPT_PATH) as f:
            self._prompt_template: str = f.read()

        with open(SYSTEM_PATH) as f:
            self._system: str = f.read()

        self._call_count: int = 0

        logger.info(
            f"Created new LLMCLient\nURL:{self._url}\nSystem:{SYSTEM_PATH}\nPROMPT:{PROMPT_PATH}"
        )

    async def query(self, request: DecisionRequest) -> dict:
        """Send the prompt to the model and return the answer"""
        payload = self._prepare_request(request)

        async with httpx.AsyncClient() as client:
            response = await client.post(self._url, json=payload)
            response.raise_for_status()

        self._call_count += 1
        return response.json()

    def _prepare_request(self, request: DecisionRequest) -> dict:
        """prepares the request message"""

        # fill prompt template
        context: dict = {
            "domain": request.domain,
            "data": request.data,
        }

        prompt = self._prompt_template.format(
            data=json.dumps(context, indent=2),
            decisions="\n".join(f"- {d}" for d in request.decisions),
        )

        return {
            "model": self._model,
            "system": self._system,
            "prompt": prompt,
            "stream": False,
            "format": {
                "type": "object",
                "properties": {
                    "decision": {"type": "string"},
                    "reasoning": {"type": "string"},
                    "alternatives": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["decision", "reasoning", "alternatives"],
            },
        }

    def _mask_api_key(self) -> str:
        """Return masked API key"""

        # TODO maybe change these numbers?
        mask_left: int = 3
        mask_right: int = 4

        if not self._api_key:
            return "None"

        if len(self._api_key) < mask_left + mask_right:
            return "***"

        return f"{self._api_key[:4]}...{self._api_key[-3:]}"

    def info(self) -> dict[str, Any]:
        return {
            "url": self._url,
            "system": self._system,
            "api_key": self._mask_api_key(),
            "prompt_template": self._prompt_template,
            "call_count": self._call_count,
        }
