import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from src.core.subscriptions import SubscriptionRuntime
from src.models import SubscriptionEntry

router = APIRouter(tags=["Subscriptions"])
logger = logging.getLogger(__name__)

_CANCEL_TIMEOUT = 5.0


def get_subscription_runtime(request: Request) -> SubscriptionRuntime:
    return request.app.state.subscription_runtime


@router.get("/subscriptions")
async def list_subscriptions(
    runtime: SubscriptionRuntime = Depends(get_subscription_runtime),
):
    """Returns all active subscriptions."""
    subscriptions = runtime.get_all()
    return {
        "subscriptions": [s.model_dump() for s in subscriptions],
        "count": len(subscriptions),
    }


@router.get("/subscriptions/{subscription_id}")
async def get_subscription(
    subscription_id: str,
    runtime: SubscriptionRuntime = Depends(get_subscription_runtime),
):
    """Returns a specific subscription by ID."""
    subscription = runtime.get(subscription_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription.model_dump()


@router.post("/subscriptions", status_code=201)
async def create_subscription(
    entry: SubscriptionEntry,
    runtime: SubscriptionRuntime = Depends(get_subscription_runtime),
):
    """Creates a new subscription."""
    if not entry.tags_filter.to_match_dict():
        raise HTTPException(status_code=400, detail="tags_filter must have at least one field set")
    if not entry.event_types:
        raise HTTPException(status_code=400, detail="event_types cannot be empty")

    subscription = runtime.add(entry)
    return subscription.model_dump()


@router.delete("/subscriptions/{subscription_id}", status_code=200)
async def cancel_subscription(
    subscription_id: str,
    runtime: SubscriptionRuntime = Depends(get_subscription_runtime),
):
    """Cancel a subscription.

    Sends a termination notification to the subscriber's callback URL before
    removing the subscription (Nnwdaf_EventsSubscription_Unsubscribe).
    """
    entry = runtime.get(subscription_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Subscription not found")

    # Notify subscriber of cancellation before removing
    try:
        async with httpx.AsyncClient(timeout=_CANCEL_TIMEOUT) as client:
            await client.post(
                entry.callback_url,
                json={
                    "subscription_id": subscription_id,
                    "event": "subscription_cancelled",
                    "tags_filter": entry.tags_filter.model_dump(exclude_none=True),
                    "event_types": entry.event_types,
                },
            )
    except Exception as e:
        logger.warning("Failed to notify %s of cancellation: %s", entry.callback_url, e)

    runtime.remove(subscription_id)
    return {"subscription_id": subscription_id, "status": "cancelled"}
