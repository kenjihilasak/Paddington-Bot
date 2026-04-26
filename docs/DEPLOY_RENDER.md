# Deploy to Render

This repo includes a ready-to-use [render.yaml](../render.yaml) Blueprint for:

- a public FastAPI web service
- a managed Render Postgres database
- a managed Render Key Value instance for Redis

## What Render will create

- `luke-bot-web`
- `luke-bot-db`
- `luke-bot-redis`

## Before you start

You need:

- the repo pushed to GitHub
- a Render account connected to GitHub
- your real Meta credentials ready:
  - `META_VERIFY_TOKEN`
  - `META_ACCESS_TOKEN`
  - `META_PHONE_NUMBER_ID`

## Deploy steps

1. Push your latest code to GitHub.
2. Go to Render.
3. Click `New` -> `Blueprint`.
4. Select this repository.
5. Render will detect `render.yaml`.
6. Review the resources to be created.
7. When Render prompts for secret values, provide:
   - `META_VERIFY_TOKEN`
   - `META_ACCESS_TOKEN`
   - `META_PHONE_NUMBER_ID`
   - `LLM_API_KEY` only if you actually use it
   - `INTENT_CLASSIFIER_API_KEY` only if you actually use it
8. Create the Blueprint and wait for the first deploy to finish.

## How this deploy works

- Render injects a Postgres connection string into `DATABASE_URL`.
- The app now converts Render's `postgresql://...` URL into the async SQLAlchemy format automatically.
- The start command runs `alembic upgrade head` before starting Uvicorn.

## After deploy

Open your web service URL:

- `https://YOUR-RENDER-SERVICE.onrender.com/health`

You should get a healthy response.

## Connect Meta webhook

In Meta Developers / WhatsApp webhook settings, use:

- Callback URL:
  `https://YOUR-RENDER-SERVICE.onrender.com/webhook/meta`
- Verify token:
  exactly the same value as `META_VERIFY_TOKEN`

Then subscribe to:

- `messages`

## Important note about app mode

If the Meta app is still unpublished / in development mode, Meta only sends test webhooks from the dashboard.

For real inbound WhatsApp messages to reach this backend, the Meta app must be live / published.

## Updating the webhook URL later

You can change the Meta webhook URL later.

If you later move from the default `onrender.com` URL to your own domain:

1. update the Render custom domain
2. update the Meta callback URL
3. verify again with the same token

## Recommended Render settings

- Web service plan: `Starter`
- Postgres plan: `Starter`
- Key Value plan: `Starter`
- Region: keep all services in the same region

## If you prefer manual Render setup

Use these values:

- Runtime: `Python`
- Build Command:
  `pip install -r requirements.txt`
- Start Command:
  `bash -lc "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT"`
- Health Check Path:
  `/health`

Set environment variables manually:

- `DATABASE_URL`
- `REDIS_URL`
- `APP_ENV=production`
- `DEBUG=false`
- `USE_FAKE_REDIS=false`
- `AUTO_CREATE_SCHEMA=false`
- `WEBHOOK_LOG_PAYLOADS=true`
- `META_VERIFY_TOKEN`
- `META_ACCESS_TOKEN`
- `META_PHONE_NUMBER_ID`
- `META_GRAPH_VERSION=v25.0`

## Verification checklist

After deployment, confirm:

1. `/health` returns `ok`
2. Meta webhook verification succeeds
3. a dashboard test webhook reaches `/webhook/meta`
4. a real WhatsApp message creates an `INBOUND` row in the database
