"""Notification service for posting events to subscribers.

Looks up subscriptions by cell_id and event_type, then sends
HTTP POST requests to callback URLs.
"""

import asyncio
import logging

import httpx

from src.core.subscriptions import SubscriptionRuntime
from src.models import SubscriptionEntry

logger = logging.getLogger(__name__)

# Timeout for HTTP requests to callbacks
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
        cell_id: int,
        event_types: set[str],
        payload: dict,
    ) -> int:
        """Send notification to all subscribers for this cell/event.

        Returns number of successful notifications.
        """
        subscribers = set()
        for event_type in event_types:
            subscribers.update(
                entry.callback_url
                for entry in self.subscription_runtime.get_by_cell_event(
                    cell_id, event_type
                )
            )

        if not subscribers:
            logger.debug("No subscribers for cell %s, event [%s]", cell_id, event_types)
            return 0

        decisions_info = payload.get("decisions", {})
        notification = {
            "cell_id": cell_id,
            "event_type": list(event_types),
            "decisions": decisions_info.get("decisions", []),
            "reasoning": decisions_info.get("reasoning", ""),
            "alternatives": decisions_info.get("alternatives", []),
        }

        tasks = [self._send_notification(sub, notification) for sub in subscribers]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for r in results if r is True)

        logger.info(
            "Notified %d/%d subscribers for cell %s, event %s",
            success_count,
            len(subscribers),
            cell_id,
            event_types,
        )

        return success_count

    async def _send_notification(
        self,
        subscription_url: str,
        notification: dict,
    ) -> bool:
        """Send notification to a single subscriber."""
        try:
            client = await self._get_client()
            response = await client.post(
                subscription_url,
                json=notification,
            )
            response.raise_for_status()
            logger.debug(
                "Notification sent to %s",
                subscription_url,
            )
            return True

        except httpx.TimeoutException:
            logger.warning(
                "Timeout sending notification to %s (subscription %s)",
                subscription_url,
            )
            return False

        except httpx.HTTPStatusError as e:
            logger.warning(
                "HTTP %d ",
                e.response.status_code,
                subscription_url,
            )
            return False

        except Exception as e:
            logger.error(
                "Failed to notify %s (subscription %s)",
                subscription_url,
                e,
            )
            return False
