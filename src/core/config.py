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
    LLM_PROMPT_PATH: str = "llm/prompt.txt"
    LLM_SYSTEM_PATH: str = "llm/system.txt"
    LLM_TEMPERATURE: float = 0.3
    LLM_TOP_K: int = 10
    LLM_TOP_P: float = 0.9
    LLM_NUM_PREDICT: int = 1024
    LLM_REPEAT_PENALTY: float = 1.3
    LLM_TIMEOUT: int = 60
    DB_PATH: str = "/app/data/decision.db"

    @property
    def DATABASE_URL(self) -> str:
        return f"sqlite:///{self.DB_PATH}"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
