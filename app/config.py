from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database values are only needed on your computer (from .env).
    # On Azure, the single DATABASE_URL setting is used instead.
    database_hostname: str = ""
    database_port: str = "5432"
    database_password: str = ""
    database_name: str = ""
    database_username: str = ""

    # These three are required both locally and on Azure
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # --- App behaviour ---
    app_name: str = "Gupshup"
    environment: str = "development"  # "production" on Azure
    # Comma-separated list. The HTML frontend is served by this same app, so it
    # does not need CORS; this is only for *other* sites calling your API.
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"
    # Used to build the link inside password-reset emails.
    app_base_url: str = "http://localhost:8000"
    reset_token_expire_minutes: int = 30

    # --- Uploads ---
    media_dir: str = "media"
    max_upload_mb: int = 5

    # --- Email ---
    # "console" prints emails to the terminal (no setup, perfect for learning).
    # "smtp" sends real email through any SMTP server.
    email_backend: str = "console"
    email_from: str = "no-reply@gupshup.local"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
