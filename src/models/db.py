from datetime import datetime, timezone

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class Decision(SQLModel, table=True):
    __tablename__ = "decisions"
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: str | None = Field(default=None)


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
