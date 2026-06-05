from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class TgSettings(BaseModel):
    """Telegram bot + webhook configuration."""

    # Bot token issued by @BotFather.
    token: str
    # Public base URL Telegram can reach this service at, e.g.
    # https://tg.channels.example.com (no trailing path).
    webhook_url: str
    # Path the webhook is registered + served on. Telegram POSTs updates here.
    webhook_endpoint: str = "/webhook/telegram"
    # Optional shared secret. When set, Telegram echoes it back in the
    # X-Telegram-Bot-Api-Secret-Token header and we reject mismatches.
    webhook_secret_token: str | None = None
    # Drop updates that piled up while the bot was offline when (re)setting
    # the webhook on startup.
    drop_pending_updates: bool = False


class Settings(BaseSettings):
    """Application settings, sourced from environment variables.

    Nested fields use a double-underscore delimiter, e.g. the bot token is
    read from ``TG__TOKEN`` and the webhook URL from ``TG__WEBHOOK_URL``.
    """

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    tg: TgSettings

    # Optional proxy for all outbound calls to the Telegram API. Supports
    # http(s) and socks5 (socks5://user:pass@host:1080) — aiogram routes
    # through it via aiohttp-socks. Leave unset to connect directly.
    proxy_url: str | None = None

    app_host: str = "0.0.0.0"
    app_port: int = 8080


settings = Settings()
