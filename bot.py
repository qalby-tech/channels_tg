from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message

from settings import settings


# Route updates that arrive via the webhook. This is intentionally minimal —
# the service's main job is relaying outbound messages via /send — but the
# webhook is wired up so incoming updates have somewhere to go.
router = Router()


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    # Hand back the chat id so the user can paste it into the platform's
    # Telegram card. message.chat.id is the value /send expects — the user's id
    # in a private chat, the group/channel id elsewhere.
    await message.answer(
        f"👋 Connected. Your chat ID is <code>{message.chat.id}</code>"
    )


@router.message()
async def on_message(message: Message) -> None:
    # Echo plain text so it is obvious the webhook is delivering updates.
    if message.text:
        await message.answer(message.text)


def build_bot() -> Bot:
    # Route Telegram API traffic through a proxy (http or socks5) when configured.
    session = AiohttpSession(proxy=settings.proxy_url) if settings.proxy_url else None
    return Bot(
        token=settings.tg.token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


bot = build_bot()
dp = Dispatcher()
dp.include_router(router)
