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
