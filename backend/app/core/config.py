from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    allowed_origins: list[str] = ["http://localhost:5173"]
    model_config = SettingsConfigDict(env_prefix="FRAUDLENS_", env_file=".env", extra="ignore")


settings = Settings()
