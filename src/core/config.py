from pydantic import BaseModel
from pydantic_settings import BaseSettings

class DecisionEntry(BaseModel):
    """Represents a decision in the system."""
    name: str
    description: str | None = None

class BlacklistEntry(BaseModel):
    """Represents a blacklisted decision."""
    name: str
    reason: str | None = None

class Settings(BaseSettings):
    APP_NAME: str = "Decision Service"
    DEBUG: bool = False

    DEFAULT_DECISIONS: list[str] = ["ALLOCATE X", "SUBVERT Y", "ABDUCT Z"]
    BLACKLIST_ENABLED: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
