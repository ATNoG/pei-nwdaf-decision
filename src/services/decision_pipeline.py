"""Kafka-driven decision pipeline.

Consumes ML results from Kafka, loads available decisions from the runtime,
expands templates, and asks the LLM to pick actions.
"""

import asyncio
import base64
import gzip
import json
import logging
import os
import re
import time
from datetime import datetime, timezone

import httpx

from src.core.config import settings
from src.core.runtime import DecisionRuntime
from src.core.subscriptions import SubscriptionRuntime
from src.schemas.decision import DecisionRequest
from src.services.llm_client import LLMClient
from src.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


def _tags_key(tags: dict) -> str:
    """Stable string key from tags dict for debouncing and history."""
    return ":".join(f"{k}={v}" for k, v in sorted(tags.items()) if v is not None)


class DecisionPipeline:

    _TEMPLATE_RE = re.compile(r"<<(\w+)>>")

    def __init__(
        self,
        bridge,
        llm_client: LLMClient,
        runtime: DecisionRuntime,
        notification_service: NotificationService | None = None,
    ):
        self.bridge = bridge
        self.llm_client = llm_client
        self.runtime = runtime
        self.notification_service = notification_service
        self._last_run: dict[str, float] = {}
        self._decision_history: dict[str, list[dict]] = {}
        self._HISTORY_SIZE = int(os.getenv("DECISION_HISTORY_SIZE", 20))

    def _compress_data(self, data: dict) -> dict:
        """Compress decision data for Kafka."""
        json_str = json.dumps(data)
        compressed = gzip.compress(json_str.encode("utf-8"))
        encoded = base64.b64encode(compressed).decode("utf-8")
        return {"compression": "gzip", "data": encoded}

    def _sanitize_for_llm(self, content: dict) -> dict:
        """Strip routing tags from ML content; keep only event_type and analytics.

        The LLM only needs to see what was measured, not which slice/DNN it came from.
        """
        sanitized = {k: v for k, v in content.items() if k != "tags"}
        event_type = content.get("tags", {}).get("event")
        if event_type:
            sanitized["event_type"] = event_type
        return sanitized

    async def _publish_decision(
        self, tags: dict, ml_result: dict, llm_response: dict, timestamp: str
    ) -> list[dict]:
        """Publish decision results to Kafka. Returns decisions_data with risk levels."""
        if not settings.KAFKA_ENABLED:
            return []

        chosen_decisions = llm_response.get("decisions", [])

        decisions_data = []
        for decision_obj in chosen_decisions:
            decision_id = (
                decision_obj.get("id")
                if isinstance(decision_obj, dict)
                else decision_obj
            )
            args = (
                decision_obj.get("args", {}) if isinstance(decision_obj, dict) else {}
            )

            decision_entry = next(
                (d for d in self.runtime.decisions if d.name == decision_id), None
            )

            description = decision_entry.description if decision_entry else decision_id
            if description and args:
                for key, value in args.items():
                    description = description.replace(f"<<{key}>>", str(value))

            decisions_data.append(
                {
                    "id": decision_id,
                    "name": decision_id,
                    "description": description,
                    "args": args,
                    "risk_level_id": (
                        decision_entry.risk_level_id if decision_entry else None
                    ),
                }
            )

        decision_message = {
            "timestamp": timestamp,
            "tags": tags,
            "decisions": decisions_data,
            "reasoning": llm_response.get("reasoning"),
            "alternatives": llm_response.get("alternatives", []),
            "llm_model": settings.LLM_MODEL,
            "llm_provider_url": settings.LLM_URL,
            "ml_result": ml_result,
        }

        compressed = self._compress_data(decision_message)
        message_json = json.dumps(compressed)

        key = _tags_key(tags)
        try:
            success = self.bridge.produce(settings.KAFKA_OUTPUT_TOPIC, message_json)
            if success:
                logger.info("Published decision for %s: %s", key, chosen_decisions)
            else:
                logger.error("Failed to publish decision for %s", key)
        except Exception as e:
            logger.exception("Error publishing decision to Kafka: %s", e)

        return decisions_data

    def on_message(self, data: dict) -> dict:
        """Kafka bind callback — schedules async processing."""
        try:
            content = json.loads(data["content"])
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning("Decision pipeline: bad message: %s", e)
            return data

        tags = content.get("tags")
        if not tags:
            logger.debug("Decision pipeline: message missing 'tags', skipping")
            return data

        results = content.get("results", [])
        if not results:
            return data

        if self.notification_service:
            if not self.notification_service.subscription_runtime.get_matching(tags, tags.get("event")):
                logger.debug("No subscribers for tags %s, skipping LLM", tags)
                return data

        key = _tags_key(tags)
        now = time.monotonic()
        if now - self._last_run.get(key, 0) < settings.KAFKA_DEBOUNCE_SECONDS:
            return data
        self._last_run[key] = now

        loop = asyncio.get_event_loop()
        loop.create_task(self._process(key, tags, content))
        return data

    async def _process(self, key: str, tags: dict, content: dict):
        """Send sanitized ML results to LLM with expanded decisions."""
        try:
            decisions = self._build_decisions()
            if not decisions:
                logger.debug("No decisions configured, skipping LLM call for %s", key)
                return

            history = self._decision_history.get(key, [])
            llm_data = self._sanitize_for_llm(content)
            request = DecisionRequest(
                domain="ml_results",
                data=[llm_data],
                decisions=decisions,
                previous_decisions=history,
            )
            logger.info("Querying LLM for %s with %d decisions", key, len(decisions))
            decision_timestamp = datetime.now(timezone.utc).isoformat()
            response = await self.llm_client.query(request)

            llm_response = response.get("response", response)
            if isinstance(llm_response, str):
                try:
                    llm_response = json.loads(llm_response)
                except (json.JSONDecodeError, TypeError):
                    pass

            logger.info("LLM decisions for %s: %s", key, json.dumps(llm_response, indent=2))

            chosen = (
                llm_response.get("decisions", [])
                if isinstance(llm_response, dict)
                else []
            )
            if chosen:
                history = self._decision_history.setdefault(key, [])
                history.append({"timestamp": decision_timestamp, "decisions": chosen})
                self._decision_history[key] = history[-self._HISTORY_SIZE :]

            decisions_data = await self._publish_decision(
                tags, content, llm_response, decision_timestamp
            )

            if self.notification_service:
                llm = llm_response if isinstance(llm_response, dict) else {}
                await self.notification_service.notify(
                    tags=tags,
                    event=tags.get("event"),
                    payload={
                        "timestamp": decision_timestamp,
                        "decisions": {
                            "decisions": decisions_data,
                            "reasoning": llm.get("reasoning", ""),
                            "alternatives": llm.get("alternatives", []),
                        },
                    },
                )

        except (httpx.TimeoutException, httpx.ConnectTimeout, httpx.ReadTimeout) as e:
            logger.error("LLM timeout for %s: %s (check LLM availability)", key, type(e).__name__)
        except Exception:
            logger.exception("Decision pipeline error for %s", key)

    def _build_decisions(self) -> list[str]:
        """Build decisions list with templates (not expanded).

        Templates like "ban <<ip_src>>" are sent as-is to the LLM.
        """
        self.runtime.reload_from_db()

        all_decisions = {d.name for d in self.runtime.decisions}
        blacklisted = set(self.runtime.blacklist_names())

        return list(all_decisions - blacklisted)

    def _extract_values(
        self, obj, collected: dict[str, set[str]] | None = None
    ) -> dict[str, set[str]]:
        """Recursively extract all key-value pairs from nested dicts/lists."""
        if collected is None:
            collected = {}

        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (str, int, float)):
                    collected.setdefault(k, set()).add(str(v))
                else:
                    self._extract_values(v, collected)
        elif isinstance(obj, list):
            for item in obj:
                self._extract_values(item, collected)

        return collected

    def _expand_template(
        self, template: str, placeholders: list[str], value_sets: dict[str, set[str]]
    ) -> list[str]:
        """Expand a template with placeholder values."""
        if not placeholders:
            return [template]

        ph = placeholders[0]
        rest = placeholders[1:]
        results = []
        for val in sorted(value_sets.get(ph, set())):
            partial = template.replace(f"<<{ph}>>", val)
            results.extend(self._expand_template(partial, rest, value_sets))
        return results


def setup_anomaly_pipeline(
    runtime: DecisionRuntime,
    subscription_runtime: SubscriptionRuntime | None = None,
):
    """Start the Kafka decision pipeline in a daemon thread."""
    from threading import Thread

    def _worker():
        try:
            asyncio.run(_start_pipeline(runtime, subscription_runtime))
        except Exception as e:
            logger.error("Kafka decision pipeline crashed: %s", e)

    thread = Thread(target=_worker, daemon=True, name="kafka-decision-thread")
    thread.start()
    logger.info("Kafka decision pipeline thread started")


async def _start_pipeline(
    runtime: DecisionRuntime,
    subscription_runtime: SubscriptionRuntime | None = None,
):
    from utils.kmw import PyKafBridge

    bridge = PyKafBridge(
        settings.KAFKA_INPUT_TOPIC,
        hostname=settings.KAFKA_HOST,
        port=settings.KAFKA_PORT,
    )

    llm_client = LLMClient()
    notification_service = (
        NotificationService(subscription_runtime) if subscription_runtime else None
    )
    pipeline = DecisionPipeline(bridge, llm_client, runtime, notification_service)
    bridge.bind_topic(settings.KAFKA_INPUT_TOPIC, pipeline.on_message)
    await bridge.start_consumer()

    if bridge._consumer_task:
        await bridge._consumer_task
