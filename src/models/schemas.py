from pydantic import BaseModel


class DecisionEntry(BaseModel):
    """Represents a decision in the system."""
    name: str
    description: str | None = None


class BlacklistEntry(BaseModel):
    """Represents a blacklisted decision."""
    name: str
    reason: str | None = None
