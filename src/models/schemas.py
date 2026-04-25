from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class DecisionStatus(str, Enum):
    """Valid statuses for a decision result."""

    pending = "pending"
    applied = "applied"
    rejected = "rejected"


class RiskLevelEntry(BaseModel):
    """Represents a risk level in the system."""

    name: str
    degree: int
    description: str | None = None


class DecisionEntry(BaseModel):
    """Represents a decision in the system."""

    name: str
    description: str | None = None
    risk_level_id: int | None = None
    justification: str | None = None


class BlacklistEntry(BaseModel):
    """Represents a blacklisted decision."""

    name: str
    reason: str | None = None


class DecisionResultResponse(BaseModel):
    """Represents the result of a decision."""

    id: int
    decision_name: str
    status: DecisionStatus
    confidence: float | None = None
    details: dict | None = None
    created_at: datetime


class TagsFilter(BaseModel):
    """Partial tag filter for NWDAF event subscriptions.

    A subscription matches an incoming result if every non-None field here
    equals the corresponding field in the result's tags.
    At least one field must be set.
    """

    snssai_sst: str | None = None
    snssai_sd: str | None = None
    dnn: str | None = None
    event: str | None = None

    def to_match_dict(self) -> dict[str, str]:
        """Return only the fields that were explicitly set (non-None)."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


class SubscriptionEntry(BaseModel):
    """Represents a subscription to slice analytics events (NWDAF Nnwdaf_EventsSubscription)."""

    id: str | None = None
    callback_url: str
    tags_filter: TagsFilter
    event_types: list[str]
    created_at: datetime | None = None
