from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class RiskLevel(SQLModel, table=True):
    __tablename__ = "risk_levels"
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    degree: int = Field(default=0)
    description: str | None = Field(default=None)


class Decision(SQLModel, table=True):
    __tablename__ = "decisions"
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: str | None = Field(default=None)
    risk_level_id: int | None = Field(default=None, foreign_key="risk_levels.id")
    justification: str | None = Field(default=None)


class Blacklist(SQLModel, table=True):
    __tablename__ = "blacklist"
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    reason: str | None = Field(default=None)


class DecisionResult(SQLModel, table=True):
    __tablename__ = "decision_results"
    id: int | None = Field(default=None, primary_key=True)
    decision_name: str = Field(index=True)
    status: str = Field(default="pending")
    confidence: float | None = Field(default=None)
    details: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Subscription(SQLModel, table=True):
    __tablename__ = "subscriptions"
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    callback_url: str
    cell_ids: list[int] = Field(sa_column=Column(JSON, nullable=False))
    event_types: list[str] = Field(sa_column=Column(JSON, nullable=False))
    expiry_time: datetime = Field(
        sa_column=Column(DateTime(timezone=False)),
        default_factory=lambda: datetime.now() + timedelta(weeks=2),
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
