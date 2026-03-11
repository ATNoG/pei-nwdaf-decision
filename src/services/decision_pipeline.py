"""Kafka-driven decision pipeline.

Consumes ML results from Kafka, loads available decisions from the runtime,
expands templates, and asks the LLM to pick actions.
"""

import asyncio
import json
import logging
import re
import time

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
            decisions = self._build_decisions(content)
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

            # Notify subscribers
            if self.notification_service:
                event_types = set()
                for result in content.get("results", []):
                    if x := result.get("event_type"):
                        event_types.add(x)

                await self.notification_service.notify(
                    cell_id=cell_id,
                    event_types=event_types,
                    payload={
                        "content": content,
                        "decisions": llm_response,
                    },
                )

        except Exception:
            logger.exception("Decision pipeline error for cell %s", cell_id)

    def _build_decisions(self, content: dict) -> list[str]:
        """Build decisions list, expanding <<attribute>> templates.

        Collects all unique values for each placeholder from the entire
        content tree (flattened from all results).
        """
        self.runtime.reload_from_db()
        blacklisted = self.runtime.blacklist_names()

        # Flatten all values from content for template expansion
        flat_values = self._extract_values(content)

        decisions: list[str] = []
        for d in self.runtime.decisions:
            if d.name in blacklisted:
                continue

            placeholders = self._TEMPLATE_RE.findall(d.name)
            if not placeholders:
                decisions.append(d.name)
                continue

            value_sets: dict[str, set[str]] = {}
            for ph in placeholders:
                value_sets[ph] = flat_values.get(ph, set())

            expanded = self._expand_template(d.name, placeholders, value_sets)
            for e in expanded:
                if e not in blacklisted:
                    decisions.append(e)

        return decisions

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
