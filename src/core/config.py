from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Decision Service"
    DEBUG: bool = False

    BLACKLIST_ENABLED: bool = True

    KAFKA_HOST: str = "kafka"
    KAFKA_PORT: str = "9092"
    KAFKA_INPUT_TOPIC: str = "network.ml.results"
    KAFKA_OUTPUT_TOPIC: str = "network.decisions"
    KAFKA_ENABLED: bool = True
    KAFKA_DEBOUNCE_SECONDS: int = 60

    LLM_URL: str = "localhost"
    LLM_API_KEY: str = "my-api-key"
    LLM_MODEL: str = "my-model"
    DB_PATH: str = "/app/data/decision.db"

    @property
    def DATABASE_URL(self) -> str:
        return f"sqlite:///{self.DB_PATH}"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
