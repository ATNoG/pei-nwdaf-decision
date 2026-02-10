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
