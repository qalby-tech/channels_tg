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


WEBHOOK_URL = settings.tg.webhook_url.rstrip("/") + settings.tg.webhook_endpoint


@asynccontextmanager
async def lifespan(app: FastAPI):
    is_success = await bot.set_webhook(
        url=WEBHOOK_URL,
        allowed_updates=dp.resolve_used_update_types(),
        drop_pending_updates=settings.tg.drop_pending_updates,
        secret_token=settings.tg.webhook_secret_token,
    )
    if not is_success:
        logger.error(f"Failed to set webhook to {WEBHOOK_URL}")
        raise RuntimeError("Failed to set webhook")
    logger.info(f"Webhook set to {WEBHOOK_URL}")

    yield

    # Leave pending updates so a replacement pod can pick them up on rollout.
    await bot.delete_webhook(drop_pending_updates=False)
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
    return {"message": "🤖 Qalby TG Channel is running"}


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
