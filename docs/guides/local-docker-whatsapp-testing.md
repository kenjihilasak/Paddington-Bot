# Local Docker WhatsApp Testing

Use this guide to run the backend locally with Docker and expose the WhatsApp webhook through ngrok.

## Prerequisites

- Docker Desktop is running.
- `.env` exists in the repo root.
- Meta WhatsApp variables are configured if you want real outbound replies:
  - `META_VERIFY_TOKEN`
  - `META_ACCESS_TOKEN`
  - `META_PHONE_NUMBER_ID`

Create `.env` if needed:

```powershell
Copy-Item .env.example .env
```

For Docker, use container hostnames:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/paddington_bot
REDIS_URL=redis://redis:6379/0
```

## Start The Stack

```powershell
docker compose up --build -d
docker compose exec app alembic upgrade head
docker compose ps
docker compose logs -f app
```

Check health:

```text
http://localhost:8000/health
```

## Expose The Webhook

```powershell
ngrok http 8000
```

If `ngrok` is not on `PATH`, run the installed executable directly:

```powershell
& "C:\Users\kenjihilasak\AppData\Local\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe" http 8000
```

Use the public URL in Meta:

```text
Callback URL: https://YOUR-NGROK-DOMAIN/webhook/meta
Verify token: same value as META_VERIFY_TOKEN
```

Subscribe to:

```text
messages
```

## Switch WhatsApp Numbers

When moving from the Meta test number to a real/new number, update:

```env
META_ACCESS_TOKEN=...
META_PHONE_NUMBER_ID=...
```

Then restart:

```powershell
docker compose down
docker compose up --build -d
```

## Common Commands

```powershell
docker compose up --build -d
docker compose exec app alembic upgrade head
docker compose logs -f app
docker compose down
ngrok http 8000
```

## Common Issues

- Docker Desktop is paused: resume Docker Desktop.
- `.env` is missing: copy `.env.example`.
- Meta webhook verification fails: check `/webhook/meta` and `META_VERIFY_TOKEN`.
- Bot receives but does not reply: check `META_ACCESS_TOKEN` and `META_PHONE_NUMBER_ID`.
