from pydantic_settings import BaseSettings


class Settings(BaseSettings):
  database_url: str = "sqlite+aiosqlite:///./mail_client.db"
  search_prefix_length: int = 3
  collector_interval_seconds: int = 300
  default_imap_port: int = 993
  default_imap_ssl: bool = True

  class Config:
    env_file = ".env"


settings = Settings()
