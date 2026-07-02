from pydantic_settings import BaseSettings


class Settings(BaseSettings):
  database_url: str = "sqlite+aiosqlite:///./mail_client.db"
  search_prefix_length: int = 3
  collector_interval_seconds: int = 300
  default_imap_port: int = 993
  default_imap_ssl: bool = True

  app_username: str = "admin"
  app_password: str = "admin"
  secret_key: str = "change-me-in-production"
  access_token_expire_minutes: int = 1440
  cookie_name: str = "mail_v_token"
  cookie_path: str = "/"
  cookie_secure: bool = False

  class Config:
    env_file = ".env"


settings = Settings()
