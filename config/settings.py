from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Recruitment Agent"
    app_env: str = "dev"
    gemini_api_key: str = ""
    gemini_flash_model: str = "gemini-1.5-flash"
    gemini_pro_model: str = "gemini-1.5-pro"
    redis_url: str = "redis://localhost:6379/0"
    postgres_dsn: str = "postgresql://postgres:postgres@localhost:5432/recruitment"
    pinecone_api_key: str = ""
    pinecone_index: str = "ai-recruitment"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
