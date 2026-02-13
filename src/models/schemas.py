from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class DecisionStatus(str, Enum):
    """Valid statuses for a decision result."""
    pending = "pending"
    applied = "applied"
    rejected = "rejected"


class DecisionEntry(BaseModel):
    """Represents a decision in the system."""
    name: str
    description: str | None = None


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
