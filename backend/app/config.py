from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ticket_master_key: str = ""

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    virtuoso_sparql_url: str = "http://localhost:8890/sparql"
    virtuoso_sparql_auth_url: str = "http://localhost:8890/sparql-auth"
    virtuoso_user: str = "dba"
    virtuoso_password: str = "dba"
    virtuoso_default_graph: str = "https://planorama.example.org/graphs/events"
    virtuoso_users_graph: str = "https://planorama.example.org/graphs/users"


settings = Settings()
