# cloud-tg

A small Telegram channel service: a FastAPI app with Telegram **webhook**
integration (via aiogram) plus a `/send` endpoint that relays messages to any
chat through the bot.

## Endpoints

| Method | Path                  | Purpose                                                          |
| ------ | --------------------- | --------------------------------------------------------------- |
| GET    | `/health`, `/`        | Probe — returns `200 {"status":"ok","bot":"@yourbot"}`.         |
| POST   | `/send`               | Relay a text message to a chat (`{chat_id, text}`).             |
| POST   | `/webhook/telegram`   | Receives updates from Telegram (registered on startup).         |

Send the bot **`/start`** in Telegram and it replies with your chat ID — paste
that into `/send` (or the platform's Telegram card). A bot can't message you
until you've started it (or it's been added to your group/channel).

### Sending a message

```bash
curl -X POST http://localhost:8080/send \
  -H 'Content-Type: application/json' \
  -d '{"chat_id": 123456789, "text": "Hello from cloud-tg"}'
```

`chat_id` accepts a numeric id or a `@channel`/`@username` string.

## Configuration

Settings are read from environment variables via `pydantic-settings`. Nested
fields use a `__` delimiter. See [`.env.example`](.env.example).

| Variable                    | Required | Description                                   |
| --------------------------- | -------- | --------------------------------------------- |
| `TG__TOKEN`                 | yes      | Bot token from @BotFather.                    |
| `TG__WEBHOOK_URL`           | yes      | Public base URL Telegram reaches the service. |
| `TG__WEBHOOK_ENDPOINT`      | no       | Webhook path (default `/webhook/telegram`).   |
| `TG__WEBHOOK_SECRET_TOKEN`  | no       | Shared secret validated on incoming updates.  |
| `PROXY_URL`                 | no       | Outbound proxy (http or socks5) for Telegram. |
| `APP_HOST` / `APP_PORT`     | no       | Bind address (default `0.0.0.0:8080`).        |

## Run locally

```bash
uv sync
cp .env.example .env   # then edit
uv run main.py
```

## Docker

```bash
docker build -t cloud-tg .
docker run --env-file .env -p 8080:8080 cloud-tg
```

## Helm

The chart lives in `qalby/cloud_charts/charts/channels/tg`.
