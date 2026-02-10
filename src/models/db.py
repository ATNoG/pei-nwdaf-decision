from typing import Optional
from sqlmodel import Field, SQLModel


class Decision(SQLModel, table=True):
    """Database model for decisions."""
    __tablename__ = "decisions"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: Optional[str] = None


class Blacklist(SQLModel, table=True):
    """Database model for blacklist entries."""
    __tablename__ = "blacklist"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    reason: Optional[str] = None
