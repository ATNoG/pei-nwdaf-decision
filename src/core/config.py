from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Decision Service"
    DEBUG: bool = False

    DEFAULT_DECISIONS: list[str] = ["ALLOCATE X", "SUBVERT Y", "ABDUCT Z"]
    BLACKLIST_ENABLED: bool = True

    DB_HOST: str = "db"
    DB_PORT: int = 5432
    DB_USER: str = "decision"
    DB_PASSWORD: str = "decision"
    DB_NAME: str = "decision_db"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()

