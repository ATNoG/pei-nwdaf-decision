from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App basics
    APP_NAME: str = "Decision Engine"
    DEBUG: bool = False

    # Decision Runtime Config
    DEFAULT_DECISIONS: list[str] = ["APPROVE", "REVIEW", "DENY"]
    BLACKLIST_ENABLED: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
