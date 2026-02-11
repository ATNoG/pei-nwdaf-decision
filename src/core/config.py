from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Decision Service"
    DEBUG: bool = False

    DEFAULT_DECISIONS: list[str] = ["ALLOCATE X", "SUBVERT Y", "ABDUCT Z"]
    BLACKLIST_ENABLED: bool = True

    DB_PATH: str = "/app/data/decision.db"

    @property
    def DATABASE_URL(self) -> str:
        return f"sqlite:///{self.DB_PATH}"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()

