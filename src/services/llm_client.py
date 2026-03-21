import json
import logging
from typing import Any

import httpx

from ..core.config import settings
from ..schemas import DecisionRequest


logger = logging.getLogger("LLM_client")


def require(x: str, y) -> None:
    """Raise exception if y is None"""
    if y is None:
        raise ValueError("x can't be None")


class LLMClient:
    def __init__(self) -> None:
        self._url: str = settings.LLM_URL
        require("LLM_URL", self._url)

        self._api_key: str = settings.LLM_API_KEY
        require("LLM_API_KEY", self._api_key)

        self._model: str = settings.LLM_MODEL
        require("LLM_MODEL", self._model)

        with open(settings.LLM_PROMPT_PATH) as f:
            self._prompt_template: str = f.read()

        with open(settings.LLM_SYSTEM_PATH) as f:
            self._system: str = f.read()

        self._call_count: int = 0

        logger.info(
            f"Created new LLMCLient\nURL:{self._url}\nModel:{self._model}\nSystem:{settings.LLM_SYSTEM_PATH}\nPROMPT:{settings.LLM_PROMPT_PATH}"
        )

    async def query(self, request: DecisionRequest) -> dict:
        """Send the prompt to the model and return the answer"""
        payload = self._prepare_request(request)

        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self._url, json=payload, headers=headers, timeout=settings.LLM_TIMEOUT
            )
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
            "format": "json",
            # Performance optimizations for faster inference
            "options": {
                "temperature": settings.LLM_TEMPERATURE,
                "top_k": settings.LLM_TOP_K,
                "top_p": settings.LLM_TOP_P,
                "num_predict": settings.LLM_NUM_PREDICT,
                "repeat_penalty": settings.LLM_REPEAT_PENALTY,
            },
            # Strict schema validation (slower but more reliable):
            # "format": {
            #     "type": "object",
            #     "properties": {
            #         "decisions": {
            #             "type": "array",
            #             "items": {
            #                 "type": "object",
            #                 "properties": {
            #                     "id": {"type": "string"},
            #                     "args": {"type": "object"},
            #                 },
            #                 "required": ["id", "args"],
            #             },
            #         },
            #         "reasoning": {"type": "string"},
            #         "alternatives": {
            #             "type": "array",
            #             "items": {
            #                 "type": "object",
            #                 "properties": {
            #                     "id": {"type": "string"},
            #                     "args": {"type": "object"},
            #                 },
            #                 "required": ["id", "args"],
            #             },
            #         },
            #     },
            #     "required": ["decisions", "reasoning", "alternatives"],
            # },
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
