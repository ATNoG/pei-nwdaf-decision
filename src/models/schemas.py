from pydantic import BaseModel


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
