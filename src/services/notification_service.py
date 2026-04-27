"""Notification service for posting events to subscribers.

Looks up subscriptions by tags and event_type, then sends
HTTP POST requests to callback URLs.
"""

import asyncio
import logging

import httpx

from src.core.subscriptions import SubscriptionRuntime

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10.0


class NotificationService:
    """Sends event notifications to subscribers."""

    def __init__(self, subscription_runtime: SubscriptionRuntime):
        self.subscription_runtime = subscription_runtime
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy init HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def notify(
        self,
        tags: dict,
        event: str | None,
        payload: dict,
    ) -> int:
        """Send notification to all subscribers matching tags/event.

        Returns number of successful notifications.
        """
        subscribers = list({
            entry.callback_url
            for entry in self.subscription_runtime.get_matching(tags, event)
        })

        if not subscribers:
            logger.debug("No subscribers for tags %s, event %s", tags, event)
            return 0

        decisions_info = payload.get("decisions", {})
        notification = {
            "tags": tags,
            "event": event,
            "decisions": decisions_info.get("decisions", []),
            "reasoning": decisions_info.get("reasoning", ""),
            "alternatives": decisions_info.get("alternatives", []),
            "timestamp": payload.get("timestamp"),
        }

        tasks = [self._send_notification(sub, notification) for sub in subscribers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for r in results if r is True)

        logger.info(
            "Notified %d/%d subscribers for tags %s, event %s",
            success_count,
            len(subscribers),
            tags,
            event,
        )

        return success_count

    async def _send_notification(self, subscription_url: str, notification: dict) -> bool:
        """Send notification to a single subscriber."""
        try:
            client = await self._get_client()
            response = await client.post(subscription_url, json=notification)
            response.raise_for_status()
            logger.debug("Notification sent to %s", subscription_url)
            return True

        except httpx.TimeoutException:
            logger.warning("Timeout sending notification to %s", subscription_url)
            return False

        except httpx.HTTPStatusError as e:
            logger.warning("HTTP %d from %s", e.response.status_code, subscription_url)
            return False

        except Exception as e:
            logger.error("Failed to notify %s: %s", subscription_url, e)
            return False
