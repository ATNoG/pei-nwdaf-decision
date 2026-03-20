"""Kafka-driven decision pipeline.

Consumes ML results from Kafka, loads available decisions from the runtime,
expands templates, and asks the LLM to pick actions.
"""

import asyncio
import base64
import gzip
import json
import logging
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
        self._last_run: dict[int, float] = {}

    def _compress_data(self, data: dict) -> dict:
        """Compress decision data for Kafka."""
        json_str = json.dumps(data)
        compressed = gzip.compress(json_str.encode("utf-8"))
        encoded = base64.b64encode(compressed).decode("utf-8")
        return {"compression": "gzip", "data": encoded}

    async def _publish_decision(
        self, cell_id: int, ml_result: dict, llm_response: dict, timestamp: str
    ):
        """Publish decision results to Kafka."""
        if not settings.KAFKA_ENABLED:
            return

        # LLM response format: {"decisions": ["name1", "name2"], "reasoning": "...", "alternatives": [...]}
        chosen_decisions = llm_response.get("decisions", [])

        # Build decision data with risk levels from runtime
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

            # Expand template if args provided
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

        # Build decision message
        decision_message = {
            "timestamp": timestamp,
            "cell_id": cell_id,
            "decisions": decisions_data,
            "reasoning": llm_response.get("reasoning"),
            "alternatives": llm_response.get("alternatives", []),
            "llm_model": settings.LLM_MODEL,
            "llm_provider_url": settings.LLM_URL,
            "ml_result": ml_result,
        }

        # Compress and publish
        compressed = self._compress_data(decision_message)
        message_json = json.dumps(compressed)

        try:
            success = self.bridge.produce(settings.KAFKA_OUTPUT_TOPIC, message_json)
            if success:
                logger.info(
                    "Published decision to Kafka for cell %s: %s",
                    cell_id,
                    chosen_decisions,
                )
            else:
                logger.error("Failed to publish decision to Kafka for cell %s", cell_id)
        except Exception as e:
            logger.exception("Error publishing decision to Kafka: %s", e)

    def on_message(self, data: dict) -> dict:
        """Kafka bind callback — schedules async processing."""
        try:
            content = json.loads(data["content"])
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning("Decision pipeline: bad message: %s", e)
            return data

        cell_id = content.get("cell_id") or content.get("cell_index")
        if cell_id is None:
            return data

        cell_id = int(cell_id)
        now = time.monotonic()
        if now - self._last_run.get(cell_id, 0) < settings.KAFKA_DEBOUNCE_SECONDS:
            return data
        self._last_run[cell_id] = now

        results = content.get("results", [])
        if not results:
            return data

        loop = asyncio.get_event_loop()
        loop.create_task(self._process(cell_id, content))
        return data

    async def _process(self, cell_id: int, content: dict):
        """Send raw ML results to LLM with expanded decisions."""
        try:
            # Build decisions, expanding templates against the flat data
            decisions = self._build_decisions()
            if not decisions:
                logger.debug(
                    "No decisions configured, skipping LLM call for cell %s", cell_id
                )
                return

            request = DecisionRequest(
                domain="ml_results",
                data=[content],
                decisions=decisions,
            )
            logger.info(
                "Querying LLM for cell %s with %d decisions",
                cell_id,
                len(decisions),
            )
            decision_timestamp = datetime.now(timezone.utc).isoformat()
            response = await self.llm_client.query(request)

            llm_response = response.get("response", response)
            if isinstance(llm_response, str):
                try:
                    llm_response = json.loads(llm_response)
                except (json.JSONDecodeError, TypeError):
                    pass

            logger.info(
                "LLM decisions for cell %s: %s",
                cell_id,
                json.dumps(llm_response, indent=2),
            )

            # Publish decisions to Kafka
            await self._publish_decision(
                cell_id, content, llm_response, decision_timestamp
            )

            # Notify subscribers
            if self.notification_service:
                event_types = set()
                for result in content.get("results", []):
                    if x := result.get("type"):
                        event_types.add(x)

                await self.notification_service.notify(
                    cell_id=cell_id,
                    event_types=event_types,
                    payload={
                        "content": content,
                        "decisions": llm_response,
                    },
                )

        except (httpx.TimeoutException, httpx.ConnectTimeout, httpx.ReadTimeout) as e:
            logger.error(
                "LLM timeout for cell %s: %s (check LLM service availability)",
                cell_id,
                type(e).__name__,
            )
        except Exception:
            logger.exception("Decision pipeline error for cell %s", cell_id)

    def _build_decisions(self) -> list[str]:
        """Build decisions list with templates (not expanded).

        Templates like "ban <<ip_src>>" are sent as-is to the LLM.
        The LLM prompt explains that <<param>> indicates a parameter
        to be filled from the ML results.
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
