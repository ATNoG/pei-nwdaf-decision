import json
import logging
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict

from ..core.config import settings
from ..schemas import DecisionRequest


class _LLMDecisionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    args: dict


class _LLMResponseSchema(BaseModel):
    """Strict response shape the LLM must produce."""
    model_config = ConfigDict(extra="forbid")
    decisions: list[_LLMDecisionItem]
    reasoning: str
    alternatives: list[_LLMDecisionItem]


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
        raw = response.json()

        logger.info("LLM raw response: %s", json.dumps(raw)[:2000])

        # OpenAI chat-completions shape: choices[0].message.content holds the model output.
        # Decision pipeline expects {"response": "..."} (Ollama generate shape), so we
        # adapt OpenAI responses to that shape for backwards compatibility.
        if "choices" in raw:
            msg = raw["choices"][0]["message"]
            content = msg.get("content") or ""
            # Reasoning models (qwen3.6, deepseek-r1) sometimes put answer in
            # reasoning_content when content is empty.
            if not content.strip():
                content = msg.get("reasoning_content") or ""
            logger.info("LLM extracted content (len=%d): %s", len(content), content[:1000])
            # Strip markdown code fences if present.
            stripped = content.strip()
            if stripped.startswith("```"):
                stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped[3:]
                if stripped.rstrip().endswith("```"):
                    stripped = stripped.rstrip()[:-3]
            return {"response": stripped.strip()}
        return raw

    def _prepare_request(self, request: DecisionRequest) -> dict:
        """prepares the request message"""

        # fill prompt template
        context: dict = {
            "domain": request.domain,
            "data": request.data,
        }

        history_str = ""
        if request.previous_decisions:
            history_str = "\n\nPREVIOUS DECISIONS FOR THIS CELL (oldest first):\n" + "\n".join(
                f"- [{e['timestamp']}] {', '.join(d['id'] for d in e['decisions'])}"
                for e in request.previous_decisions
            )

        prompt = self._prompt_template.format(
            data=json.dumps(context, indent=2),
            decisions="\n".join(f"- {d}" for d in request.decisions),
            previous_decisions=history_str,
        )

        # OpenAI chat-completions format (skynet / OpenWebUI / Groq / OpenAI proper).
        # Pydantic-generated json_schema forces the model to emit exactly this shape.
        schema = _LLMResponseSchema.model_json_schema()
        return {
            "model": self._model,
            "messages": [
                {"role": "system", "content": self._system},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "decision_response", "strict": True, "schema": schema},
            },
            "temperature": settings.LLM_TEMPERATURE,
            "top_p": settings.LLM_TOP_P,
            "max_tokens": settings.LLM_NUM_PREDICT,
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
