import asyncio
import logging
from contextlib import asynccontextmanager

from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from bot import bot, dp
from settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EndpointFilter(logging.Filter):
    """Filter out access logs for the root and health endpoints."""

    def __init__(self, excluded_paths: list[str] | None = None):
        super().__init__()
        self.excluded_paths = excluded_paths or ["/", "/health"]

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not any(
            f" {path} " in message or message.endswith(f" {path}")
            for path in self.excluded_paths
        )


logging.getLogger("uvicorn.access").addFilter(EndpointFilter())


WEBHOOK_URL = (
    settings.tg.webhook_url.rstrip("/") + settings.tg.webhook_endpoint
    if settings.tg.webhook_url
    else None
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    polling_task: asyncio.Task | None = None

    if settings.tg.mode == "polling":
        # getUpdates can't run while a webhook is registered — clear it first
        # (keeping pending updates so the queued ones still get delivered).
        await bot.delete_webhook(drop_pending_updates=settings.tg.drop_pending_updates)
        # Pull updates outbound (through the proxy). handle_signals=False —
        # uvicorn owns the process signals, not aiogram.
        polling_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))
        logger.info("Update mode: long-polling (getUpdates)")
    else:
        if not WEBHOOK_URL:
            raise RuntimeError("TG__WEBHOOK_URL is required in webhook mode")
        is_success = await bot.set_webhook(
            url=WEBHOOK_URL,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=settings.tg.drop_pending_updates,
            secret_token=settings.tg.webhook_secret_token,
        )
        if not is_success:
            logger.error(f"Failed to set webhook to {WEBHOOK_URL}")
            raise RuntimeError("Failed to set webhook")
        logger.info(f"Update mode: webhook -> {WEBHOOK_URL}")

    # Cache the bot's @username once so /health doesn't hit the Telegram API on
    # every probe.
    me = await bot.get_me()
    app.state.bot_username = f"@{me.username}" if me.username else None
    logger.info(f"Bot is {app.state.bot_username}")

    yield

    if polling_task is not None:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
    # In webhook mode we deliberately do NOT delete the webhook on shutdown:
    # during a rolling update the replacement pod has already re-set it, and
    # deleting here would race and leave the bot with no webhook.
    await bot.session.close()


app = FastAPI(title="Qalby TG Channel", lifespan=lifespan)


class SendRequest(BaseModel):
    # int for numeric chat ids, str for @channel usernames.
    chat_id: int | str
    text: str


class SendResponse(BaseModel):
    ok: bool
    chat_id: int | str
    message_id: int


@app.get("/health")
@app.get("/")
async def root():
    # 200 OK + the bot's @username (cached at startup).
    return {"status": "ok", "bot": getattr(app.state, "bot_username", None)}


@app.post("/send", response_model=SendResponse)
async def send(req: SendRequest) -> SendResponse:
    """Relay a text message to a chat through the current bot."""
    message = await bot.send_message(chat_id=req.chat_id, text=req.text)
    return SendResponse(
        ok=True,
        chat_id=message.chat.id,
        message_id=message.message_id,
    )


@app.post(settings.tg.webhook_endpoint)
async def webhook(
    update: Update,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    if settings.tg.webhook_secret_token and (
        x_telegram_bot_api_secret_token != settings.tg.webhook_secret_token
    ):
        raise HTTPException(status_code=403, detail="Invalid secret token")

    # Feed the update in the background so we ack Telegram immediately and
    # don't hold the webhook connection open while handlers run.
    asyncio.create_task(dp.feed_update(bot, update))
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.app_host, port=settings.app_port)
