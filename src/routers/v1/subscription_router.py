from fastapi import APIRouter, Depends, HTTPException, Request

from src.core.subscriptions import SubscriptionRuntime
from src.models import SubscriptionEntry

router = APIRouter(tags=["Subscriptions"])


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
    if not entry.cell_ids:
        raise HTTPException(status_code=400, detail="cell_ids cannot be empty")
    if not entry.event_types:
        raise HTTPException(status_code=400, detail="event_types cannot be empty")

    subscription = runtime.add(entry)
    return subscription.model_dump()


@router.delete("/subscriptions/{subscription_id}")
async def delete_subscription(
    subscription_id: str,
    runtime: SubscriptionRuntime = Depends(get_subscription_runtime),
):
    """Deletes a subscription by ID."""
    if not runtime.remove(subscription_id):
        raise HTTPException(status_code=404, detail="Subscription not found")
    return {"message": "Subscription deleted", "subscription_id": subscription_id}
