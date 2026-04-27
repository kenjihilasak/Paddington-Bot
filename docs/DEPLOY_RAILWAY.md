# Deploy to Railway

This project can be deployed to Railway directly from GitHub.

The repo now includes [railway.json](../railway.json), which tells Railway to:

- build with the existing Dockerfile
- run `alembic upgrade head` before each deploy
- use `/health` as the healthcheck

The Dockerfile now starts Uvicorn on Railway's dynamic `$PORT`.

## Recommended first setup

For the cheapest initial deployment:

- 1 web service from this repo
- 1 PostgreSQL service
- no Redis service yet
- `USE_FAKE_REDIS=true`

This is acceptable for a first live MVP if:

- you run only one web replica
- you accept that in-memory conversation state is lost on restart

Later, if needed, you can add a Railway Redis service and switch to `USE_FAKE_REDIS=false`.

## Option A: cheapest setup now

Use:

- Railway web service
- Railway PostgreSQL
- fake Redis in memory

## Option B: safer production setup

Use:

- Railway web service
- Railway PostgreSQL
- Railway Redis
- `USE_FAKE_REDIS=false`

## Deploy steps

1. Push your latest code to GitHub.
2. Go to Railway.
3. Create a new project.
4. Click `Deploy from GitHub repo`.
5. Select this repository.
6. Railway will detect the repo and use [railway.json](../railway.json).
7. In the same project, immediately add PostgreSQL.
8. Set the required environment variables on the web service.
9. Trigger a redeploy if the first deployment started before variables were ready.
10. After the service is healthy, go to `Settings -> Networking`.
11. Click `Generate Domain`.

Your public app URL will look like:

- `https://your-service.up.railway.app`

## Add PostgreSQL

1. In the same Railway project, click `+ New`.
2. Add `PostgreSQL`.
3. Wait until it is ready.

Railway will create a Postgres service with variables such as `DATABASE_URL`.

## Cheapest variable setup

On your web service, go to `Variables` and set:

- `DATABASE_URL=${{Postgres.DATABASE_URL}}`
- `APP_ENV=production`
- `DEBUG=false`
- `USE_FAKE_REDIS=true`
- `AUTO_CREATE_SCHEMA=false`
- `WEBHOOK_LOG_PAYLOADS=true`
- `META_VERIFY_TOKEN=...`
- `META_ACCESS_TOKEN=...`
- `META_PHONE_NUMBER_ID=...`
- `META_GRAPH_VERSION=v25.0`

Optional LLM variables only if you use them:

- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`

For this cheapest setup:

- do not add `REDIS_URL`
- keep `USE_FAKE_REDIS=true`
- keep only one Railway replica

## If you want real Redis later

1. In the same Railway project, click `+ New`.
2. Add `Redis`.
3. On your web service, set:
   - `REDIS_URL=${{Redis.REDIS_URL}}`
   - `USE_FAKE_REDIS=false`
4. Redeploy the web service.

Note:

- `Postgres` and `Redis` in the examples above are the service names used in Railway reference variables.
- If your Railway services use different names, replace them with the exact service names shown in your project.

## Important variable notes

- Do not paste your whole local `.env` blindly into Railway.
- Do not keep the local `DATABASE_URL=postgresql+asyncpg://...localhost...` in Railway.
- Railway should provide the database URL through a reference variable.

## Health check

After deploy, open:

- `https://your-service.up.railway.app/health`

It should return a healthy response.

## Connect Meta webhook

In Meta Developers, configure:

- Callback URL:
  `https://your-service.up.railway.app/webhook/meta`
- Verify token:
  exactly the same value as `META_VERIFY_TOKEN`

Subscribe to:

- `messages`

## Important app mode note

If the Meta app is still unpublished / in development mode, Meta only sends dashboard test webhooks.

For real inbound WhatsApp messages, the Meta app must be live / published.

## What to do in Railway if deploy fails

Check, in this order:

1. `Deployments` logs
2. whether `DATABASE_URL` is set on the web service
3. whether `META_*` variables are set correctly
4. whether the Railway domain has been generated
5. whether `/health` responds

## Suggested first live path

To minimize cost and complexity:

1. deploy web service
2. add PostgreSQL
3. use `USE_FAKE_REDIS=true`
4. verify `/health`
5. connect Meta webhook
6. test dashboard webhook
7. test real inbound WhatsApp message

Only add Redis if you confirm you need persistent queue/state behavior across restarts.
